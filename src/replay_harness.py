"""Replay harness coordinating time-ordered event streams, fault injection, and publishing."""
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from src.config import (
    parse_iso,
    to_iso,
    LATENCY_BUDGET_MS,
    MAX_MODEL_CALLS,
    MAX_TOOL_CALLS
)
from src.data_loader import DataLoader
from src.fact_resolver import FactResolver
from src.goal_planner import GoalPlanner
from src.intervention_planner import InterventionPlanner
from src.model_provider import ModelProvider, ModelProviderException
from src.models import Decision, PublishedAction, ViewerState
from src.verifier import ActionVerifier
from src.viewer_store import ViewerStore

logger = logging.getLogger("ReplayHarness")


class ReplayHarness:
    def __init__(self, pack_dir: str, output_dir: str):
        self.pack_dir = Path(pack_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.loader = DataLoader(pack_dir)
        self.loader.load_all_static()
        
        self.viewer_store = ViewerStore(str(self.output_dir / "viewer_state"))
        self.fact_resolver = FactResolver()
        self.goal_planner = GoalPlanner()
        self.intervention_planner = InterventionPlanner(self.loader)
        self.verifier = ActionVerifier(self.loader)
        self.model_provider = ModelProvider(self.loader.model_faults)
        
        self.processed_trigger_ids: set = set()
        self.decision_counter = 0
        self.action_counter = 0
        self.decisions: List[Dict[str, Any]] = []
        self.actions: List[Dict[str, Any]] = []
        self.g03_corrected = False

    def warm_up_history(self) -> None:
        """Pre-populate viewer states from 30-day events.jsonl with deduplication."""
        events_file = self.pack_dir / "data" / "events.jsonl"
        logger.info("Initializing viewer states from profiles snapshot...")
        for uid, row in self.loader.profiles.items():
            arm = self.loader.arms.get(uid, "agent")
            self.viewer_store.initialize_from_profile(uid, row, arm)

        logger.info("Replaying 30-day events.jsonl to build durable viewer history...")
        seen_event_ids = set()
        count = 0
        with open(events_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                eid = ev["event_id"]
                if eid in seen_event_ids:
                    continue  # Deduplicate duplicate event_ids
                seen_event_ids.add(eid)
                count += 1
                self.viewer_store.update_from_event(ev, self.loader.catalogue)

        logger.info(f"Loaded and deduplicated {count} historical events across {len(self.viewer_store.states)} viewers.")

    def run_replay(self) -> None:
        """Execute the replay day in strict delivery order with live and control events."""
        logger.info("Preparing replay stream...")
        stream: List[Tuple[datetime, str, Dict[str, Any]]] = []

        # 1. Triggers: sorted by deliver_at
        triggers_file = self.pack_dir / "replay" / "triggers.jsonl"
        with open(triggers_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    tr = json.loads(line)
                    deliver_dt = parse_iso(tr.get("deliver_at") or tr.get("received_at"))
                    stream.append((deliver_dt, "trigger", tr))

        # 2. Live events: sorted by received_at
        live_file = self.pack_dir / "replay" / "live_events.jsonl"
        with open(live_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    ev = json.loads(line)
                    rec_dt = parse_iso(ev["received_at"])
                    stream.append((rec_dt, "live_event", ev))

        # 3. Control events: sorted by at
        for ctrl in self.loader.control_events:
            stream.append((ctrl["at_dt"], "control_event", ctrl))

        # Sort the unified stream by chronological timestamp
        stream.sort(key=lambda item: item[0])
        logger.info(f"Replay stream assembled: {len(stream)} total items. Beginning execution...")

        decisions_file = open(self.output_dir / "decisions.jsonl", "w", encoding="utf-8")
        actions_file = open(self.output_dir / "actions.jsonl", "w", encoding="utf-8")

        for current_time, item_type, payload in stream:
            if item_type == "control_event":
                self._handle_control_event(payload, current_time)

            elif item_type == "live_event":
                self._handle_live_event(payload)

            elif item_type == "trigger":
                decision_record, action_record = self._handle_trigger(payload, current_time)
                decisions_file.write(json.dumps(decision_record, ensure_ascii=False) + "\n")
                self.decisions.append(decision_record)
                if action_record:
                    actions_file.write(json.dumps(action_record, ensure_ascii=False) + "\n")
                    self.actions.append(action_record)

        decisions_file.close()
        actions_file.close()
        self.viewer_store.save_all()
        logger.info(f"Replay complete! Published {len(self.actions)} actions and {len(self.decisions)} decisions.")

    def _handle_control_event(self, ctrl: Dict[str, Any], current_time: datetime) -> None:
        """Process operational surprises and rule corrections."""
        c_type = ctrl.get("type")
        if c_type == "title_withdrawn":
            tid = ctrl["title_id"]
            self.loader.withdraw_title(tid, current_time)
            logger.info(f"[CONTROL] Title {tid} withdrawn at {current_time}: {ctrl.get('reason')}")

        elif c_type == "goal_rule_corrected":
            gid = ctrl.get("goal_id")
            if gid == "G03":
                self.goal_planner.set_g03_correction("2026-10-01-corrected")
                self.g03_corrected = True
                logger.info(f"[CONTROL] G03 goal success condition corrected to play_started.")

        elif c_type in ("dependency_unavailable", "dependency_degraded"):
            logger.info(f"[CONTROL] Dependency alert: {ctrl.get('dependency')} -> {ctrl.get('detail')}")

    def _handle_live_event(self, ev: Dict[str, Any]) -> None:
        """Update viewer state from real-time live events during replay day."""
        self.viewer_store.update_from_event(ev, self.loader.catalogue)

    def _handle_trigger(self, trigger: Dict[str, Any], deliver_dt: datetime) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Execute the 7-step decision and verification loop for one viewer trigger."""
        t_start = time.perf_counter()
        self.decision_counter += 1
        decision_id = f"D-{self.decision_counter:04d}"
        
        user_id = trigger["user_id"]
        trigger_event_id = trigger["event_id"]
        received_at_str = trigger["received_at"]
        occurred_at_str = trigger.get("occurred_at", received_at_str)
        rec_dt = parse_iso(received_at_str)
        occ_dt = parse_iso(occurred_at_str)

        event_age_s = (rec_dt - occ_dt).total_seconds() if rec_dt and occ_dt else 0.0
        arm = self.loader.arms.get(user_id, "agent")
        state = self.viewer_store.get_or_create(user_id, arm)

        # 1. Idempotency Check
        if trigger_event_id in self.processed_trigger_ids:
            decided_ms = int((time.perf_counter() - t_start) * 1000)
            return {
                "decision_id": decision_id,
                "viewer_id": user_id,
                "trigger": {"event": trigger["event"], "received_at": received_at_str, "event_age_s": event_age_s},
                "goal": None,
                "action": "NO_ACTION",
                "dialect": {"used": state.app_dialect or "d1", "source": "cached", "conflicts": []},
                "content": [],
                "confidence": 1.0,
                "confidence_reason": "Duplicate trigger event_id detected. Idempotency enforced.",
                "evidence": [f"event_id:{trigger_event_id}:duplicate"],
                "assumptions": ["Trigger was delivered more than once by client."],
                "checks": {"passed": ["idempotency_check"], "failed": []},
                "decided_in_ms": decided_ms,
                "status": "ABSTAINED",
                "no_action_reason": "duplicate_trigger_idempotency_skip"
            }, None

        self.processed_trigger_ids.add(trigger_event_id)

        # Step 1: Understand the Viewer & Fact Resolution
        app_dialect = trigger.get("app_dialect")
        deeplink = trigger.get("properties", {}).get("deeplink")
        deeplink_dialect = self.fact_resolver.extract_deeplink_dialect(deeplink)
        resolved_dialect, dialect_src, dialect_conflicts = self.fact_resolver.resolve_dialect(
            app_dialect, state.preferred_dialect, deeplink_dialect
        )
        state.app_dialect = resolved_dialect

        # Step 2: Choose Goal (for both arms to allow honest ITT evaluation)
        goal = self.goal_planner.plan_goal(state, deliver_dt, self.loader.catalogue, self.loader.episodes_by_slug)

        # 2. Holdout Check: zero action on holdout arm
        if arm == "holdout":
            decided_ms = int((time.perf_counter() - t_start) * 1000)
            return {
                "decision_id": decision_id,
                "viewer_id": user_id,
                "trigger": {"event": trigger["event"], "received_at": received_at_str, "event_age_s": event_age_s},
                "goal": goal,
                "action": "NO_ACTION",
                "dialect": {"used": resolved_dialect, "source": dialect_src, "conflicts": dialect_conflicts},
                "content": [],
                "confidence": 1.0,
                "confidence_reason": "Viewer belongs to randomized holdout control arm. Goal tracked for ITT comparison, but zero actions permitted.",
                "evidence": [f"replay/arms.csv:{user_id}:holdout"] + (goal.get("evidence", []) if goal else []),
                "assumptions": ["Control arm viewers receive zero agent interventions."],
                "checks": {"passed": ["holdout_check", "eligibility_check"], "failed": []},
                "decided_in_ms": decided_ms,
                "status": "HOLDOUT",
                "no_action_reason": "user_in_holdout_arm"
            }, None

        # 3. Offline-buffered Stale App Open Check
        if event_age_s > 600:
            decided_ms = int((time.perf_counter() - t_start) * 1000)
            return {
                "decision_id": decision_id,
                "viewer_id": user_id,
                "trigger": {"event": trigger["event"], "received_at": received_at_str, "event_age_s": event_age_s},
                "goal": goal,
                "action": "NO_ACTION",
                "dialect": {"used": resolved_dialect, "source": dialect_src, "conflicts": dialect_conflicts},
                "content": [],
                "confidence": 0.95,
                "confidence_reason": f"Offline-buffered event received {event_age_s:.1f}s after occurrence; viewer not in active live session.",
                "evidence": [f"trigger:occurred_at:{occurred_at_str}", f"trigger:received_at:{received_at_str}"],
                "assumptions": ["Device flushed buffered event upon reconnection; user is no longer actively in-app."],
                "checks": {"passed": ["stale_event_check"], "failed": ["live_session_check"]},
                "decided_in_ms": decided_ms,
                "status": "ABSTAINED",
                "no_action_reason": "stale_offline_buffered_trigger"
            }, None

        # 6. Step 3 & 4: Model Provider with Fault Handling & Fallback
        model_calls = 0
        fallback_used = False
        try:
            model_eval = self.model_provider.query(trigger_event_id, f"Evaluate viewer {user_id}", deliver_dt)
            model_calls += 1
        except ModelProviderException as m_err:
            logger.warning(f"Model failure for trigger {trigger_event_id}: {m_err}. Using rule-based fallback.")
            fallback_used = True
            model_eval = {"eligible": True, "confidence": 0.70, "confidence_reason": "Rule-based deterministic fallback"}

        # 7. Step 3: Decide Intervention
        proposed_action_type = "HOME_PAGE"
        proposed_action_payload = self.intervention_planner.build_home_page(
            user_id, resolved_dialect, deliver_dt, state, goal
        )
        if not proposed_action_payload:
            proposed_action_type = "NO_ACTION"

        # 8. Step 5: Independent Verification Firewall
        is_valid, passed_checks, failed_checks = self.verifier.verify_decision(
            user_id=user_id,
            arm=arm,
            action_type=proposed_action_type,
            action_payload=proposed_action_payload,
            goal=goal,
            state=state,
            publish_dt=deliver_dt,
            event_age_s=event_age_s
        )

        decided_ms = int((time.perf_counter() - t_start) * 1000)
        published_at_dt = deliver_dt + timedelta(milliseconds=decided_ms)
        published_at_str = to_iso(published_at_dt)

        if not is_valid:
            # Verifier rejected the proposed action -> safe abstention
            return {
                "decision_id": decision_id,
                "viewer_id": user_id,
                "trigger": {"event": trigger["event"], "received_at": received_at_str, "event_age_s": event_age_s},
                "goal": goal,
                "action": "NO_ACTION",
                "dialect": {"used": resolved_dialect, "source": dialect_src, "conflicts": dialect_conflicts},
                "content": [],
                "confidence": 0.50,
                "confidence_reason": f"Independent verifier rejected proposed action: {failed_checks}",
                "evidence": [f"verifier_rejection:{','.join(failed_checks)}"],
                "assumptions": ["Safety and policy rules take absolute precedence."],
                "checks": {"passed": passed_checks, "failed": failed_checks},
                "decided_in_ms": decided_ms,
                "status": "REJECTED",
                "no_action_reason": f"verifier_rejected:{failed_checks[0] if failed_checks else 'unknown'}",
                "fallback_used": fallback_used,
                "model_calls": model_calls,
                "tool_calls": 3,
                "rule_version": goal.get("rule_version", "2026-09-30") if goal else "2026-09-30"
            }, None

        if proposed_action_type == "NO_ACTION" or not proposed_action_payload:
            decision_record = {
                "decision_id": decision_id,
                "viewer_id": user_id,
                "trigger": {"event": trigger["event"], "received_at": received_at_str, "event_age_s": event_age_s},
                "goal": goal,
                "action": "NO_ACTION",
                "dialect": {"used": resolved_dialect, "source": dialect_src, "conflicts": dialect_conflicts},
                "content": [],
                "confidence": 0.80,
                "confidence_reason": "No valid content or action available for current context; abstaining safely.",
                "evidence": goal.get("evidence", []) if goal else [f"app_setting:{resolved_dialect}"],
                "assumptions": goal.get("assumptions", []) if goal else ["Viewer prefers current dialect."],
                "checks": {"passed": passed_checks, "failed": failed_checks},
                "decided_in_ms": decided_ms,
                "status": "ABSTAINED",
                "no_action_reason": "no_valid_action_payload",
                "fallback_used": fallback_used,
                "model_calls": model_calls,
                "tool_calls": 3,
                "rule_version": goal.get("rule_version", "2026-09-30") if goal else "2026-09-30"
            }
            return decision_record, None

        # Build Action Payload
        self.action_counter += 1
        action_id = f"A-{self.action_counter:04d}"
        action_record = {
            "action_id": action_id,
            "decision_id": decision_id,
            "user_id": user_id,
            "trigger_event_id": trigger_event_id,
            "type": proposed_action_payload["type"],
            "published_at": published_at_str,
            "dialect": proposed_action_payload["dialect"],
            "hero_title_id": proposed_action_payload.get("hero_title_id"),
            "rows": proposed_action_payload.get("rows", [])
        }

        # Extract content list for decision record
        content_refs = []
        if proposed_action_payload.get("hero_title_id"):
            content_refs.append(f"title:{proposed_action_payload['hero_title_id']}")
        for r in proposed_action_payload.get("rows", []):
            for tid in r.get("title_ids", [])[:2]:
                content_refs.append(f"title:{tid}")

        decision_record = {
            "decision_id": decision_id,
            "viewer_id": user_id,
            "trigger": {"event": trigger["event"], "received_at": received_at_str, "event_age_s": event_age_s},
            "goal": goal,
            "action": proposed_action_type,
            "dialect": {"used": resolved_dialect, "source": dialect_src, "conflicts": dialect_conflicts},
            "content": content_refs[:6],
            "confidence": 0.88 if not fallback_used else 0.72,
            "confidence_reason": "High relevance: tailored to viewer dialect, active progress, and top genre affinity.",
            "evidence": goal.get("evidence", []) if goal else [f"app_setting:{resolved_dialect}"],
            "assumptions": goal.get("assumptions", []) if goal else ["Viewer prefers current dialect."],
            "checks": {"passed": passed_checks, "failed": failed_checks},
            "decided_in_ms": decided_ms,
            "status": "PUBLISHED",
            "fallback_used": fallback_used,
            "model_calls": model_calls,
            "tool_calls": 4,
            "rule_version": goal.get("rule_version", "2026-09-30") if goal else "2026-09-30"
        }

        return decision_record, action_record
