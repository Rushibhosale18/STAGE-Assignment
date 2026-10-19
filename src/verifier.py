"""Independent safety verification firewall. Model output is never proof."""
from datetime import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple, Set

from src.config import (
    is_quiet_hours,
    get_ist_date_str,
    parse_iso,
    MAX_HOME_PAGE_ROWS,
    MIN_TITLES_PER_ROW,
    MAX_TITLES_PER_ROW,
    VALID_PRICES_INR
)
from src.data_loader import DataLoader
from src.models import ViewerState

logger = logging.getLogger("Verifier")


class VerificationResult:
    def __init__(self, passed: bool, check_name: str, reason: str = ""):
        self.passed = passed
        self.check_name = check_name
        self.reason = reason


class ActionVerifier:
    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader

    def verify_decision(
        self,
        user_id: str,
        arm: str,
        action_type: str,
        action_payload: Optional[Dict[str, Any]],
        goal: Optional[Dict[str, Any]],
        state: ViewerState,
        publish_dt: datetime,
        event_age_s: float
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Run all independent checks before publishing.
        Returns: (is_valid, passed_checks, failed_checks)
        """
        passed: List[str] = []
        failed: List[str] = []

        # 1. Holdout Check: NEVER allow actions on holdout arm users
        if arm == "holdout":
            if action_type != "NO_ACTION":
                failed.append("holdout_safety_violation: action attempted on holdout arm user")
                return False, passed, failed
            else:
                passed.append("holdout_compliance")
                return True, passed, failed

        # 2. Offline-buffered Stale Trigger Check
        if event_age_s > 600:
            if action_type in ("HOME_PAGE", "IN_APP_MESSAGE"):
                failed.append("offline_buffered_stale_trigger: event age > 600s, user session inactive")
                return False, passed, failed
            passed.append("stale_trigger_check")
        else:
            passed.append("fresh_trigger_check")

        if action_type == "NO_ACTION":
            passed.append("safe_abstention")
            return True, passed, failed

        # 3. Eligibility & Unsupported Model Claim Check
        if goal:
            goal_id = goal.get("goal_id")
            if goal_id == "G04":
                # Must be trial_active
                if state.subscription_status != "trial_active":
                    failed.append(f"unsupported_claim: user status is {state.subscription_status}, not trial_active")
                    return False, passed, failed
            elif goal_id == "G05":
                if state.subscription_status != "never":
                    failed.append(f"unsupported_claim: user status is {state.subscription_status}, not never")
                    return False, passed, failed
            elif goal_id == "G06":
                if state.subscription_status != "lapsed":
                    failed.append(f"unsupported_claim: user status is {state.subscription_status}, not lapsed")
                    return False, passed, failed
            elif goal_id in ("G08", "G09"):
                if state.subscription_status != "active":
                    failed.append(f"unsupported_claim: user status is {state.subscription_status}, not active")
                    return False, passed, failed
            passed.append("eligibility_verification")

        # 4. Action-specific verifications
        if action_type == "HOME_PAGE":
            if not action_payload:
                failed.append("empty_home_page_payload")
                return False, passed, failed

            page_dialect = action_payload.get("dialect")
            # Dialect match check
            expected_dialect = state.app_dialect or state.preferred_dialect or "d1"
            if page_dialect != expected_dialect:
                failed.append(f"dialect_mismatch: page is {page_dialect}, app expects {expected_dialect}")
                return False, passed, failed
            passed.append("dialect_match")

            # Check Hero and Rows
            hero_tid = action_payload.get("hero_title_id")
            seen_slugs: Set[str] = set()

            if hero_tid:
                if not self.loader.is_title_available(hero_tid, publish_dt):
                    failed.append(f"hero_unavailable: {hero_tid}")
                    return False, passed, failed
                hero_obj = self.loader.catalogue.get(hero_tid)
                if not hero_obj or hero_obj["dialect"] != page_dialect:
                    failed.append(f"hero_wrong_dialect: {hero_tid}")
                    return False, passed, failed
                seen_slugs.add(hero_obj["content_slug"])
                passed.append("hero_valid")

            rows = action_payload.get("rows", [])
            if len(rows) > MAX_HOME_PAGE_ROWS:
                failed.append(f"rows_exceed_max: {len(rows)} > {MAX_HOME_PAGE_ROWS}")
                return False, passed, failed

            valid_rows = []
            for r in rows:
                tids = r.get("title_ids", [])
                clean_tids = []
                for tid in tids:
                    t = self.loader.catalogue.get(tid)
                    if not t:
                        continue
                    if t["dialect"] != page_dialect:
                        continue
                    if not self.loader.is_title_available(tid, publish_dt):
                        continue
                    if t["content_slug"] in seen_slugs:
                        continue
                    seen_slugs.add(t["content_slug"])
                    clean_tids.append(tid)

                if len(clean_tids) >= MIN_TITLES_PER_ROW:
                    valid_rows.append(dict(r, title_ids=clean_tids[:MAX_TITLES_PER_ROW]))
                else:
                    # Row dropped below minimum 3 titles
                    logger.info(f"Row dropped below minimum titles: had {len(clean_tids)}")

            if not valid_rows and not hero_tid:
                failed.append("home_page_empty_after_filtering")
                return False, passed, failed

            action_payload["rows"] = valid_rows
            passed.append("slug_uniqueness")
            passed.append("row_constraints")

        elif action_type in ("PUSH", "WHATSAPP"):
            if not action_payload:
                failed.append("empty_message_payload")
                return False, passed, failed

            # Consent check
            ch = "push" if action_type == "PUSH" else "whatsapp"
            if ch == "push":
                if not state.notifications_opt_in or "push" in state.opted_out_channels:
                    failed.append("consent_missing: push notifications not opted in or opted out")
                    return False, passed, failed
            else:
                if not state.whatsapp_opt_in or "whatsapp" in state.opted_out_channels:
                    failed.append("consent_missing: whatsapp not opted in or opted out")
                    return False, passed, failed
            passed.append("consent_verified")

            # Quiet Hours & Scheduling Check
            send_at_str = action_payload.get("send_at")
            send_dt = parse_iso(send_at_str) if send_at_str else publish_dt
            if is_quiet_hours(send_dt):
                failed.append(f"quiet_hours_violation: scheduled at {send_dt} IST")
                return False, passed, failed
            passed.append("quiet_hours_verified")

            # Frequency Cap Check (max 1 message per user per IST day across push & whatsapp)
            target_ist_day = get_ist_date_str(send_dt)
            prior_messages = [
                m for m in state.messages_sent
                if m.get("ist_day") == target_ist_day and m.get("channel") in ("push", "whatsapp")
            ]
            if len(prior_messages) >= 1:
                failed.append(f"frequency_cap_exceeded: already sent {len(prior_messages)} messages on {target_ist_day}")
                return False, passed, failed
            passed.append("frequency_cap_verified")

            # Content Check
            tid = action_payload.get("title_id")
            if tid:
                if not self.loader.is_title_available(tid, send_dt):
                    failed.append(f"title_unavailable_or_withdrawn: {tid}")
                    return False, passed, failed
                t_obj = self.loader.catalogue.get(tid)
                expected_dialect = state.app_dialect or state.preferred_dialect or "d1"
                if t_obj and t_obj["dialect"] != expected_dialect:
                    failed.append(f"message_dialect_mismatch: {t_obj['dialect']} != {expected_dialect}")
                    return False, passed, failed
                passed.append("message_content_verified")

        return True, passed, failed
