"""Tests for independent safety verification, holdout protection, and policy rules."""
try:
    import pytest
except ImportError:
    class _MockPytest:
        @staticmethod
        def fixture(func):
            return func
    pytest = _MockPytest()
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_loader import DataLoader
from src.verifier import ActionVerifier
from src.models import ViewerState
from src.config import parse_iso


@pytest.fixture
def verifier_setup():
    loader = DataLoader("one_user_one_agent_pack")
    loader.load_all_static()
    verifier = ActionVerifier(loader)
    return loader, verifier


def test_holdout_arm_receives_zero_actions(verifier_setup):
    """Verifier must reject any active intervention on a holdout arm user."""
    loader, verifier = verifier_setup
    publish_dt = parse_iso("2026-10-01T10:00:00Z")
    state = ViewerState(user_id="U-HOLDOUT", arm="holdout")

    # Attempting to publish a HOME_PAGE for a holdout user
    is_valid, passed, failed = verifier.verify_decision(
        user_id="U-HOLDOUT",
        arm="holdout",
        action_type="HOME_PAGE",
        action_payload={"type": "home_page", "dialect": "d2", "rows": []},
        goal={"goal_id": "G01"},
        state=state,
        publish_dt=publish_dt,
        event_age_s=10.0
    )
    assert is_valid is False
    assert any("holdout_safety_violation" in f for f in failed)

    # NO_ACTION on holdout is compliant and valid
    is_valid_abstain, passed_abstain, _ = verifier.verify_decision(
        user_id="U-HOLDOUT",
        arm="holdout",
        action_type="NO_ACTION",
        action_payload=None,
        goal={"goal_id": "G01"},
        state=state,
        publish_dt=publish_dt,
        event_age_s=10.0
    )
    assert is_valid_abstain is True
    assert "holdout_compliance" in passed_abstain


def test_unsupported_model_claim_rejected(verifier_setup):
    """Model asserts user is eligible for G04 (trial_to_paid), but state is 'never'."""
    loader, verifier = verifier_setup
    publish_dt = parse_iso("2026-10-01T10:00:00Z")
    state = ViewerState(user_id="U-01991", subscription_status="never")

    is_valid, passed, failed = verifier.verify_decision(
        user_id="U-01991",
        arm="agent",
        action_type="HOME_PAGE",
        action_payload={"type": "home_page", "dialect": "d2", "rows": []},
        goal={"goal_id": "G04", "name": "trial_to_paid_7d"},
        state=state,
        publish_dt=publish_dt,
        event_age_s=5.0
    )
    assert is_valid is False
    assert any("unsupported_claim" in f for f in failed)


def test_quiet_hours_enforcement(verifier_setup):
    """Messages scheduled during 22:00-08:00 IST must be rejected by the verifier."""
    loader, verifier = verifier_setup
    # 23:30 IST = 18:00 UTC (quiet hours)
    night_dt = parse_iso("2026-10-01T18:00:00Z")
    state = ViewerState(user_id="U-TEST", notifications_opt_in=True)

    push_payload = {
        "type": "push",
        "send_at": "2026-10-01T18:00:00.000Z",
        "title_id": "T0042",
        "text": {"title": "Hello", "body": "World"}
    }

    is_valid, passed, failed = verifier.verify_decision(
        user_id="U-TEST",
        arm="agent",
        action_type="PUSH",
        action_payload=push_payload,
        goal={"goal_id": "G01"},
        state=state,
        publish_dt=night_dt,
        event_age_s=5.0
    )
    assert is_valid is False
    assert any("quiet_hours_violation" in f for f in failed)


def test_withdrawn_title_blocked(verifier_setup):
    """A withdrawn title cannot be used after its withdrawal timestamp."""
    loader, verifier = verifier_setup
    withdrawal_dt = parse_iso("2026-10-01T07:00:00.000Z")
    loader.withdraw_title("T0001", withdrawal_dt)

    assert loader.is_title_available("T0001", parse_iso("2026-10-01T06:59:00Z")) is True
    assert loader.is_title_available("T0001", parse_iso("2026-10-01T07:01:00Z")) is False


def test_row_with_fewer_than_three_titles_dropped(verifier_setup):
    """Rows with fewer than 3 valid titles are dropped by platform rules."""
    loader, verifier = verifier_setup
    publish_dt = parse_iso("2026-10-01T10:00:00Z")
    state = ViewerState(user_id="U-TEST", app_dialect="d1")

    payload = {
        "type": "home_page",
        "dialect": "d1",
        "hero_title_id": None,
        "rows": [
            # Row 1 has only 2 titles (dropped)
            {"row_type": "popular_in_dialect", "title_ids": ["T0001", "T0003"]}
        ]
    }

    is_valid, passed, failed = verifier.verify_decision(
        user_id="U-TEST",
        arm="agent",
        action_type="HOME_PAGE",
        action_payload=payload,
        goal={"goal_id": "G01"},
        state=state,
        publish_dt=publish_dt,
        event_age_s=5.0
    )
    # Since only row had < 3 titles and was dropped, home page becomes empty and is rejected
    assert is_valid is False
    assert "home_page_empty_after_filtering" in failed
