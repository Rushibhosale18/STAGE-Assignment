"""Tests for precedence rules and explicit conflict resolution."""
from datetime import datetime
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fact_resolver import FactResolver


def test_dialect_conflict_resolution():
    """App setting must take precedence over profile and campaign link, with conflicts visible."""
    app_dialect = "d3"
    profile_dialect = "d1"
    deeplink = "ott://c/diwali_promo/d5/title/T0123"
    deeplink_dialect = FactResolver.extract_deeplink_dialect(deeplink)
    assert deeplink_dialect == "d5"

    resolved, source, conflicts = FactResolver.resolve_dialect(
        app_dialect=app_dialect,
        profile_dialect=profile_dialect,
        deeplink_dialect=deeplink_dialect
    )

    # 1. App setting wins because that is what the app actually requests and renders
    assert resolved == "d3"
    assert source == "app_setting"
    
    # 2. Conflicts must be explicitly tracked and visible
    assert len(conflicts) == 3
    assert "app_setting:d3" in conflicts
    assert "profile:d1" in conflicts
    assert "campaign_link:d5" in conflicts


def test_subscription_status_conflict_resolution():
    """A newer purchase event must beat a stale profile snapshot."""
    # Profile says 'never' as of snapshot 2026-09-29T10:00:00Z
    profile_status = "never"
    profile_updated_at = "2026-09-29T10:00:00Z"

    # A newer billing event arrives at 2026-09-30T14:00:00Z
    billing_event = {
        "event": "purchase_completed",
        "received_at": "2026-09-30T14:00:00Z",
        "properties": {
            "plan_id": "P_MONTH",
            "price_inr": 149,
            "is_trial": False
        }
    }

    resolved_status, source, at = FactResolver.resolve_subscription(
        profile_status=profile_status,
        profile_updated_at=profile_updated_at,
        latest_billing_event=billing_event
    )

    assert resolved_status == "active", "Newer purchase event must upgrade status to active"
    assert source == "events:purchase_completed"
    assert at == "2026-09-30T14:00:00Z"


def test_consent_override_by_opt_out():
    """A subsequent notification_opt_out event overrides profile opt-in."""
    profile_opt_in = True
    opted_out_channels = ["push"]

    # Push consent should now be False
    push_consent = FactResolver.resolve_consent(profile_opt_in, "push", opted_out_channels)
    assert push_consent is False

    # WhatsApp consent was not opted out, remains True
    wa_consent = FactResolver.resolve_consent(profile_opt_in, "whatsapp", opted_out_channels)
    assert wa_consent is True
