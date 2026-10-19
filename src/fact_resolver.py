"""Fact resolver with precedence rules and explicit conflict tracking."""
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from src.config import parse_iso, to_iso
from src.models import ViewerState, Fact


class FactResolver:
    """Applies strict precedence rules across conflicting sources and logs conflicts."""

    @staticmethod
    def resolve_dialect(
        app_dialect: Optional[str],
        profile_dialect: Optional[str],
        deeplink_dialect: Optional[str] = None
    ) -> Tuple[str, str, List[str]]:
        """
        Precedence:
        1. app_dialect (app setting on current event: this is what the app UI will actually request).
        2. profile_dialect (from profile snapshot: 1-day stale preference).
        3. deeplink_dialect (marketing campaign source).
        
        Returns: (resolved_dialect, source, conflicts_list)
        """
        conflicts = []
        candidates = {}
        if app_dialect:
            candidates["app_setting"] = app_dialect
        if profile_dialect:
            candidates["profile"] = profile_dialect
        if deeplink_dialect:
            candidates["campaign_link"] = deeplink_dialect

        unique_values = set(candidates.values())
        if len(unique_values) > 1:
            for src, d in candidates.items():
                conflicts.append(f"{src}:{d}")

        if app_dialect:
            return app_dialect, "app_setting", conflicts
        if profile_dialect:
            return profile_dialect, "profile", conflicts
        if deeplink_dialect:
            return deeplink_dialect, "campaign_link", conflicts
        
        # Fallback default dialect if completely unknown
        return "d1", "fallback_default", conflicts

    @staticmethod
    def extract_deeplink_dialect(deeplink: Optional[str]) -> Optional[str]:
        """Extract dialect from campaign deeplink format: ott://c/<campaign>/<dialect>/title/<title_id>."""
        if not deeplink or "ott://c/" not in deeplink:
            return None
        parts = deeplink.split("/")
        # format: ['ott:', '', 'c', '<campaign>', '<dialect>', 'title', '<title_id>']
        if len(parts) >= 5 and parts[4].startswith("d"):
            return parts[4]
        return None

    @staticmethod
    def resolve_subscription(
        profile_status: Optional[str],
        profile_updated_at: Optional[str],
        latest_billing_event: Optional[Dict[str, Any]]
    ) -> Tuple[str, str, Optional[str]]:
        """
        Precedence:
        Newer billing event (purchase_completed, subscription_renewed, subscription_lapsed)
        beats an older profile snapshot.
        """
        if not latest_billing_event:
            status = profile_status or "never"
            return status, "profile_snapshot", profile_updated_at

        billing_event_type = latest_billing_event["event"]
        billing_received_at = latest_billing_event["received_at"]
        billing_dt = parse_iso(billing_received_at)
        prof_dt = parse_iso(profile_updated_at) if profile_updated_at else None

        # If billing event occurred after profile export, billing event wins
        if prof_dt is None or (billing_dt and billing_dt >= prof_dt):
            if billing_event_type == "purchase_completed":
                is_trial = latest_billing_event.get("properties", {}).get("is_trial", False)
                status = "trial_active" if is_trial else "active"
                return status, f"events:{billing_event_type}", billing_received_at
            elif billing_event_type == "subscription_renewed":
                return "active", f"events:{billing_event_type}", billing_received_at
            elif billing_event_type == "subscription_lapsed":
                return "lapsed", f"events:{billing_event_type}", billing_received_at

        # Otherwise profile snapshot is fresher
        return profile_status or "never", "profile_snapshot", profile_updated_at

    @staticmethod
    def resolve_consent(
        profile_opt_in: bool,
        channel: str,
        opted_out_channels: List[str]
    ) -> bool:
        """
        Precedence:
        A later notification_opt_out event overrides the profile opt-in snapshot.
        """
        if channel in opted_out_channels:
            return False
        return bool(profile_opt_in)
