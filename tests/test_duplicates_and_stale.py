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
from src.replay_harness import ReplayHarness
from src.config import parse_iso


@pytest.fixture
def test_setup(tmp_path):
    pack_dir = Path("one_user_one_agent_pack")
    output_dir = tmp_path / "test_run"
    harness = ReplayHarness(pack_dir=str(pack_dir), output_dir=str(output_dir))
    return harness


def test_duplicate_trigger_idempotency(test_setup):
    """Test that a duplicate trigger with the same event_id produces NO duplicate action."""
    harness = test_setup
    deliver_dt = parse_iso("2026-10-01T08:00:00Z")
    
    trigger = {
        "event_id": "test-dup-uuid-001",
        "user_id": "U-00042",
        "event": "app_open",
        "occurred_at": "2026-10-01T08:00:00Z",
        "sent_at": "2026-10-01T08:00:00Z",
        "received_at": "2026-10-01T08:00:00Z",
        "session_id": "sess-001",
        "app_dialect": "d2"
    }

    # First arrival: processes normally
    dec1, act1 = harness._handle_trigger(trigger, deliver_dt)
    assert dec1["status"] in ("PUBLISHED", "ABSTAINED")
    
    # Second arrival (exact same event_id): must be recognized as duplicate
    dec2, act2 = harness._handle_trigger(trigger, deliver_dt)
    assert act2 is None, "Duplicate trigger must not publish duplicate actions"
    assert dec2["status"] == "ABSTAINED"
    assert dec2["no_action_reason"] == "duplicate_trigger_idempotency_skip"
    assert "idempotency_check" in dec2["checks"]["passed"]


def test_stale_offline_buffered_trigger(test_setup):
    """Test that offline-buffered app opens (> 600s delay) are not treated as live sessions."""
    harness = test_setup
    deliver_dt = parse_iso("2026-10-01T12:00:00Z")
    
    # Event occurred 2 days ago, but only received now upon reconnect
    stale_trigger = {
        "event_id": "test-stale-uuid-002",
        "user_id": "U-00042",
        "event": "app_open",
        "occurred_at": "2026-09-29T10:00:00Z",  # 2 days old
        "sent_at": "2026-10-01T11:59:50Z",
        "received_at": "2026-10-01T12:00:00Z",
        "session_id": "sess-stale-002",
        "app_dialect": "d2"
    }

    dec, act = harness._handle_trigger(stale_trigger, deliver_dt)
    assert act is None, "Stale offline buffered trigger must not publish live actions"
    assert dec["status"] == "ABSTAINED"
    assert dec["no_action_reason"] == "stale_offline_buffered_trigger"
    assert dec["trigger"]["event_age_s"] > 600
