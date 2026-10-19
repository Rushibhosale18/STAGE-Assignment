"""Outcome judge for evaluating goal success, attribution, and rule corrections."""
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

from src.config import parse_iso, to_iso, get_ist_date_str, UTC
from src.data_loader import DataLoader
from src.models import OutcomeJudgment, ViewerState

logger = logging.getLogger("OutcomeJudge")


class OutcomeJudge:
    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader

    def judge_goal(
        self,
        decision: Dict[str, Any],
        user_events: List[Dict[str, Any]],
        g03_corrected: bool = True
    ) -> OutcomeJudgment:
        """
        Evaluate whether the goal in a decision succeeded based strictly on attributable events
        within the defined goal window [started_at, deadline].
        """
        user_id = decision["viewer_id"]
        decision_id = decision["decision_id"]
        goal = decision.get("goal")

        if not goal:
            return OutcomeJudgment(
                judgment_id=f"J-{decision_id}",
                decision_id=decision_id,
                user_id=user_id,
                goal_id="NONE",
                goal_name="NONE",
                goal_started_at=decision["trigger"]["received_at"],
                deadline=decision["trigger"]["received_at"],
                status="INCONCLUSIVE",
                reason="No active goal was set for this decision."
            )

        goal_id = goal.get("goal_id") or goal.get("id")
        goal_name = goal.get("name") or goal.get("id")
        start_dt = parse_iso(goal.get("started_at") or decision["trigger"]["received_at"])
        deadline_dt = parse_iso(goal.get("deadline"))
        rule_version = goal.get("rule_version", "2026-09-30")

        # Events attributable strictly within [start_dt, deadline_dt]
        attributable_events = []
        for e in user_events:
            rec_dt = parse_iso(e["received_at"])
            if start_dt <= rec_dt <= deadline_dt:
                attributable_events.append((rec_dt, e))
        attributable_events.sort(key=lambda x: x[0])

        succeeded = False
        succ_event = None
        reason = ""

        # G01: first_play_24h
        if goal_id == "G01" or goal_name == "first_play_24h":
            for dt, ev in attributable_events:
                if ev["event"] == "play_started":
                    succeeded = True
                    succ_event = ev
                    reason = f"Play started on title {ev.get('properties', {}).get('title_id')} at {ev['received_at']}"
                    break

        # G02: first_full_episode_3d
        elif goal_id == "G02" or goal_name == "first_full_episode_3d":
            for dt, ev in attributable_events:
                if ev["event"] == "episode_completed":
                    succeeded = True
                    succ_event = ev
                    reason = f"Completed episode {ev.get('properties', {}).get('episode_id')} at {ev['received_at']}"
                    break

        # G03: second_day_return_2d
        elif goal_id == "G03" or goal_name == "second_day_return_2d":
            start_ist_day = get_ist_date_str(start_dt)
            # Rule correction check:
            # Control event corrected G03 mid-replay from 'app_open' to 'play_started'
            target_event_type = "play_started" if g03_corrected or rule_version != "2026-09-30" else "app_open"
            for dt, ev in attributable_events:
                if ev["event"] == target_event_type:
                    ev_ist_day = get_ist_date_str(dt)
                    if ev_ist_day > start_ist_day:
                        succeeded = True
                        succ_event = ev
                        reason = f"Achieved {target_event_type} on later IST day ({ev_ist_day} > {start_ist_day})"
                        break

        # G04: trial_to_paid_7d & G05: first_paid_7d
        elif goal_id in ("G04", "G05") or goal_name in ("trial_to_paid_7d", "first_paid_7d"):
            for dt, ev in attributable_events:
                if ev["event"] == "purchase_completed":
                    props = ev.get("properties", {})
                    if not props.get("is_trial", False):
                        succeeded = True
                        succ_event = ev
                        reason = f"Purchased paid plan {props.get('plan_id')} for INR {props.get('price_inr')}"
                        break

        # G06: reactivate_lapsed_14d
        elif goal_id == "G06" or goal_name == "reactivate_lapsed_14d":
            for dt, ev in attributable_events:
                if ev["event"] == "purchase_completed":
                    succeeded = True
                    succ_event = ev
                    reason = f"Lapsed subscriber renewed with plan {ev.get('properties', {}).get('plan_id')}"
                    break

        # G07: resume_series_3d
        elif goal_id == "G07" or goal_name == "resume_series_3d":
            target_slug = goal.get("target_slug")
            for dt, ev in attributable_events:
                if ev["event"] == "play_started":
                    tid = ev.get("properties", {}).get("title_id")
                    t_obj = self.loader.catalogue.get(tid)
                    if t_obj and (not target_slug or t_obj["content_slug"] == target_slug):
                        succeeded = True
                        succ_event = ev
                        reason = f"Resumed series {t_obj['content_slug']} with title {tid}"
                        break

        # G08: try_new_release_7d
        elif goal_id == "G08" or goal_name == "try_new_release_7d":
            for dt, ev in attributable_events:
                if ev["event"] == "play_started":
                    tid = ev.get("properties", {}).get("title_id")
                    t_obj = self.loader.catalogue.get(tid)
                    if t_obj and t_obj.get("release_date"):
                        rel_dt = parse_iso(t_obj["release_date"])
                        # released in the 30 days before goal start
                        if rel_dt and (start_dt - rel_dt).total_seconds() <= 30 * 86400:
                            succeeded = True
                            succ_event = ev
                            reason = f"Played new release {tid} (released {t_obj['release_date']})"
                            break

        # G09: weekly_habit_14d
        elif goal_id == "G09" or goal_name == "weekly_habit_14d":
            play_ist_days = set()
            for dt, ev in attributable_events:
                if ev["event"] == "play_started":
                    play_ist_days.add(get_ist_date_str(dt))
                    if len(play_ist_days) >= 3:
                        succeeded = True
                        succ_event = ev
                        reason = f"Played on 3 distinct IST days: {sorted(list(play_ist_days))}"
                        break

        # G12: return_after_absence_7d
        elif goal_id == "G12" or goal_name == "return_after_absence_7d":
            for dt, ev in attributable_events:
                if ev["event"] == "play_started":
                    succeeded = True
                    succ_event = ev
                    reason = f"Played title {ev.get('properties', {}).get('title_id')} after absence"
                    break

        status = "SUCCEEDED" if succeeded else "FAILED"
        if not reason:
            reason = f"No qualifying success event occurred within the {goal.get('window_hours', 0)}h window."

        return OutcomeJudgment(
            judgment_id=f"J-{decision_id}",
            decision_id=decision_id,
            user_id=user_id,
            goal_id=goal_id,
            goal_name=goal_name,
            goal_started_at=to_iso(start_dt),
            deadline=to_iso(deadline_dt),
            status=status,
            success_event_id=succ_event.get("event_id") if succ_event else None,
            success_event_type=succ_event.get("event") if succ_event else None,
            evaluated_at=to_iso(datetime.now(UTC)),
            rule_version=rule_version,
            reason=reason
        )
