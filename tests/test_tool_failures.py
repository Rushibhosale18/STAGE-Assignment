try:
    import pytest
except ImportError:
    class _MockPytest:
        @staticmethod
        def raises(exc):
            class _RaisesContext:
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    if not exc_type:
                        raise AssertionError(f"Expected exception {exc}, but none was raised")
                    return issubclass(exc_type, exc)
            return _RaisesContext()
    pytest = _MockPytest()
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import parse_iso
from src.model_provider import (
    ModelProvider,
    ModelUnavailableException,
    ModelTimeoutException,
    ModelProviderException
)
from src.replay_harness import ReplayHarness


def test_model_provider_outage_simulation():
    """During 10:35-10:42 window, model call raises HTTP 503 and harness falls back safely."""
    faults = {}
    provider = ModelProvider(faults)
    outage_time = parse_iso("2026-10-01T10:38:00.000Z")

    with pytest.raises(ModelUnavailableException):
        provider.query("test-trigger-1", "Prompt", outage_time)


def test_model_provider_timeout_simulation():
    """Injected timeout raises ModelTimeoutException."""
    faults = {
        "timeout-trigger-id": {"fault": "timeout", "seconds": 45}
    }
    provider = ModelProvider(faults)
    normal_time = parse_iso("2026-10-01T06:00:00.000Z")

    with pytest.raises(ModelTimeoutException):
        provider.query("timeout-trigger-id", "Prompt", normal_time)


def test_model_provider_malformed_json_simulation():
    """Injected broken JSON is safely caught and raises ModelProviderException."""
    faults = {
        "broken-trigger-id": {"fault": "malformed_output", "model_output": '{"goal_id": "G02", "eligible": tr'}
    }
    provider = ModelProvider(faults)
    normal_time = parse_iso("2026-10-01T06:00:00.000Z")

    with pytest.raises(ModelProviderException):
        provider.query("broken-trigger-id", "Prompt", normal_time)


def test_harness_degrades_safely_on_model_failure(tmp_path):
    """When model fails, ReplayHarness must not crash and must set fallback_used = True."""
    pack_dir = Path("one_user_one_agent_pack")
    output_dir = tmp_path / "test_run"
    harness = ReplayHarness(pack_dir=str(pack_dir), output_dir=str(output_dir))

    # A trigger during the outage window
    outage_time = parse_iso("2026-10-01T10:36:00.000Z")
    trigger = {
        "event_id": "test-outage-uuid",
        "user_id": "U-00042",
        "event": "app_open",
        "occurred_at": "2026-10-01T10:36:00.000Z",
        "sent_at": "2026-10-01T10:36:00.000Z",
        "received_at": "2026-10-01T10:36:00.000Z",
        "session_id": "sess-outage",
        "app_dialect": "d2"
    }

    dec, act = harness._handle_trigger(trigger, outage_time)
    assert dec["fallback_used"] is True, "Harness must fall back when model provider is down"
    assert dec["status"] == "PUBLISHED"
    assert dec["decided_in_ms"] < 60000, "Decision must remain within latency budget"
