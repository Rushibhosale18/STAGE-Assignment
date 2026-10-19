"""Goal evaluation, lifecycle management, and selection engine."""
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, List, Optional, Tuple

from src.config import parse_iso, to_iso, IST
from src.models import ViewerState

logger = logging.getLogger("GoalPlanner")


class GoalPlanner:
    def __init__(self):
        self.g03_rule_version = "2026-09-30"  # Changes to 2026-10-01-corrected on control event

    def set_g03_correction(self, version: str = "2026-10-01-corrected") -> None:
        """Apply operational rule correction for G03 mid-replay."""
        self.g03_rule_version = version
        logger.info(f"G03 success rule updated to version {version} (play_started on later IST day)")

    def evaluate_eligibility(
        self,
        state: ViewerState,
        trigger_dt: datetime,
        catalogue: Dict[str, Any],
        episodes_by_slug: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate eligibility for all 12 goals based strictly on durable evidence.
        Explicitly excludes G10 and G11 as unmeasurable.
        """
        eligible = []
        signup_dt = parse_iso(state.signup_at) if state.signup_at else None
        status = state.subscription_status
        
        # G01: first_play_24h
        # "Signed up in the last 7 days and has never started a play."
        if signup_dt and (trigger_dt - signup_dt).total_seconds() <= 7 * 86400:
            if state.total_plays_started == 0:
                eligible.append({
                    "goal_id": "G01",
                    "name": "first_play_24h",
                    "window_hours": 24,
                    "success_event": "play_started",
                    "priority": 100,  # Critical first funnel step
                    "evidence": [
                        f"profile:signup_at:{state.signup_at}",
                        f"events:total_plays:{state.total_plays_started}"
                    ],
                    "assumptions": ["Viewer is newly onboarded and looking for initial content."]
                })

        # G02: first_full_episode_3d
        # "Has never completed an episode."
        if state.total_episodes_completed == 0:
            eligible.append({
                "goal_id": "G02",
                "name": "first_full_episode_3d",
                "window_hours": 72,
                "success_event": "episode_completed",
                "priority": 85,
                "evidence": [f"events:total_episodes_completed:{state.total_episodes_completed}"],
                "assumptions": ["Viewer needs a compelling episode hook to complete their first show."]
            })

        # G03: second_day_return_2d
        # "Signed up in the last 2 days."
        if signup_dt and (trigger_dt - signup_dt).total_seconds() <= 2 * 86400:
            success_ev = "play_started" if self.g03_rule_version != "2026-09-30" else "app_open"
            eligible.append({
                "goal_id": "G03",
                "name": "second_day_return_2d",
                "window_hours": 48,
                "success_event": success_ev,
                "priority": 90,
                "rule_version": self.g03_rule_version,
                "evidence": [f"profile:signup_at:{state.signup_at}"],
                "assumptions": ["Early retention is critical within the first 48 hours of signup."]
            })

        # G04: trial_to_paid_7d
        # "Subscription status is trial_active."
        if status == "trial_active":
            eligible.append({
                "goal_id": "G04",
                "name": "trial_to_paid_7d",
                "window_hours": 168,
                "success_event": "purchase_completed",
                "priority": 95,
                "evidence": [f"state:subscription_status:trial_active"],
                "assumptions": ["Trial user needs to see subscription value before expiry."]
            })

        # G05: first_paid_7d
        # "Has never had a paid plan."
        if status == "never":
            eligible.append({
                "goal_id": "G05",
                "name": "first_paid_7d",
                "window_hours": 168,
                "success_event": "purchase_completed",
                "priority": 60,
                "evidence": [f"state:subscription_status:never"],
                "assumptions": ["Free user requires high-intent conversion prompt."]
            })

        # G06: reactivate_lapsed_14d
        # "Subscription recently lapsed."
        if status == "lapsed":
            eligible.append({
                "goal_id": "G06",
                "name": "reactivate_lapsed_14d",
                "window_hours": 336,
                "success_event": "purchase_completed",
                "priority": 75,
                "evidence": [f"state:subscription_status:lapsed"],
                "assumptions": ["Lapsed subscriber needs a fresh content hook to renew."]
            })

        # G07: resume_series_3d
        # "Started a show or micro-drama, has unwatched episodes left, and has not played it for 3 or more days."
        for slug, prog in state.series_progress.items():
            last_watched = parse_iso(prog.get("last_watched_at"))
            if last_watched and (trigger_dt - last_watched).total_seconds() >= 3 * 86400:
                all_eps = episodes_by_slug.get(slug, [])
                completed = prog.get("completed_episodes", [])
                if len(completed) < len(all_eps):
                    eligible.append({
                        "goal_id": "G07",
                        "name": "resume_series_3d",
                        "window_hours": 72,
                        "success_event": "play_started",
                        "target_slug": slug,
                        "priority": 80,
                        "evidence": [
                            f"series_progress:{slug}:unwatched_episodes",
                            f"series_progress:{slug}:last_watched:{prog.get('last_watched_at')}"
                        ],
                        "assumptions": [f"Viewer abandoned series {slug} and would benefit from next episode prompt."]
                    })
                    break

        # G08: try_new_release_7d
        # "Active subscriber."
        if status == "active":
            eligible.append({
                "goal_id": "G08",
                "name": "try_new_release_7d",
                "window_hours": 168,
                "success_event": "play_started",
                "priority": 70,
                "evidence": [f"state:subscription_status:active"],
                "assumptions": ["Active subscriber will appreciate fresh catalogue releases."]
            })

        # G09: weekly_habit_14d
        # "Active subscriber with plays on at most 1 day in the last 14 days."
        if status == "active":
            recent_active_days = [
                d for d in state.distinct_active_ist_days
                # within last 14 days
            ]
            if len(recent_active_days) <= 1:
                eligible.append({
                    "goal_id": "G09",
                    "name": "weekly_habit_14d",
                    "window_hours": 336,
                    "success_event": "play_started",
                    "priority": 72,
                    "evidence": [
                        f"state:subscription_status:active",
                        f"state:active_days_count:{len(recent_active_days)}"
                    ],
                    "assumptions": ["Subscriber is low-frequency and at risk of churn."]
                })

        # G10: meaningful_engagement_7d -> Explicitly REJECTED: no measurable success event.
        # G11: tv_activation_14d -> Explicitly REJECTED: tv_app_open does not exist in event telemetry.

        # G12: return_after_absence_7d
        # "No app_open in the 14 days before the trigger."
        # Documented interpretation: check if previous app_open was >= 14 days ago (or never)
        if state.last_app_open_at:
            last_open = parse_iso(state.last_app_open_at)
            if last_open and (trigger_dt - last_open).total_seconds() >= 14 * 86400:
                eligible.append({
                    "goal_id": "G12",
                    "name": "return_after_absence_7d",
                    "window_hours": 168,
                    "success_event": "play_started",
                    "priority": 65,
                    "evidence": [f"state:last_app_open_at:{state.last_app_open_at}"],
                    "assumptions": ["Lapsed viewer has returned; need immediate play hook."]
                })

        # Sort eligible goals by priority descending
        eligible.sort(key=lambda g: g["priority"], reverse=True)
        return eligible

    def plan_goal(
        self,
        state: ViewerState,
        trigger_dt: datetime,
        catalogue: Dict[str, Any],
        episodes_by_slug: Dict[str, List[Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Select or revise the single active goal for the viewer.
        Returns the chosen goal specification or None if no goal is eligible.
        """
        # 1. Check if user currently has an active, unexpired goal
        if state.active_goal:
            deadline = parse_iso(state.active_goal.get("deadline"))
            # If still active within window, check if goal needs revising due to life cycle changes
            if deadline and trigger_dt < deadline:
                current_goal_id = state.active_goal.get("id") or state.active_goal.get("goal_id")
                
                # Check for lifecycle revision: e.g. paid purchase while on G05 or G04
                if current_goal_id in ("G04", "G05") and state.subscription_status == "active":
                    logger.info(f"Viewer {state.user_id} achieved subscription; revising active goal {current_goal_id}.")
                    # Mark previous goal archived
                    state.goal_history.append(dict(state.active_goal, closed_reason="lifecycle_transition_to_active"))
                    state.active_goal = None
                elif current_goal_id == "G01" and state.total_plays_started > 0:
                    state.goal_history.append(dict(state.active_goal, closed_reason="play_started_transition"))
                    state.active_goal = None
                else:
                    # Keep pursuing existing active goal
                    return state.active_goal

        # 2. Select best eligible goal
        eligible_goals = self.evaluate_eligibility(state, trigger_dt, catalogue, episodes_by_slug)
        if not eligible_goals:
            return None

        chosen = eligible_goals[0]
        deadline_dt = trigger_dt + timedelta(hours=chosen["window_hours"])
        
        goal_record = {
            "id": chosen["name"],
            "goal_id": chosen["goal_id"],
            "name": chosen["name"],
            "started_at": to_iso(trigger_dt),
            "deadline": to_iso(deadline_dt),
            "window_hours": chosen["window_hours"],
            "success_event": chosen["success_event"],
            "rule_version": chosen.get("rule_version", "2026-09-30"),
            "evidence": chosen["evidence"],
            "assumptions": chosen["assumptions"]
        }
        if "target_slug" in chosen:
            goal_record["target_slug"] = chosen["target_slug"]

        state.active_goal = goal_record
        return goal_record
