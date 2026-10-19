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
from src.outcome_judge import OutcomeJudge


@pytest.fixture
def judge_setup():
    loader = DataLoader("one_user_one_agent_pack")
    loader.load_all_static()
    judge = OutcomeJudge(loader)
    return judge


def test_g03_old_rule_evaluation(judge_setup):
    """Under the original rule, an app_open on a later IST day was considered a return."""
    judge = judge_setup
    decision = {
        "decision_id": "D-TEST-001",
        "viewer_id": "U-TEST-1",
        "trigger": {"received_at": "2026-10-01T06:00:00Z"},
        "goal": {
            "id": "second_day_return_2d",
            "goal_id": "G03",
            "name": "second_day_return_2d",
            "started_at": "2026-10-01T06:00:00Z",
            "deadline": "2026-10-03T06:00:00Z",
            "window_hours": 48,
            "rule_version": "2026-09-30"
        }
    }

    # User only opened app on day 2, no play
    user_events = [
        {
            "event_id": "ev-01",
            "user_id": "U-TEST-1",
            "event": "app_open",
            "received_at": "2026-10-02T10:00:00Z",
            "properties": {}
        }
    ]

    # Without correction applied: app_open counts as success
    outcome_old = judge.judge_goal(decision, user_events, g03_corrected=False)
    assert outcome_old.status == "SUCCEEDED"
    assert outcome_old.success_event_type == "app_open"


def test_g03_corrected_rule_evaluation(judge_setup):
    """Under corrected rule, app_open does NOT count; only play_started counts."""
    judge = judge_setup
    decision = {
        "decision_id": "D-TEST-002",
        "viewer_id": "U-TEST-2",
        "trigger": {"received_at": "2026-10-01T06:00:00Z"},
        "goal": {
            "id": "second_day_return_2d",
            "goal_id": "G03",
            "name": "second_day_return_2d",
            "started_at": "2026-10-01T06:00:00Z",
            "deadline": "2026-10-03T06:00:00Z",
            "window_hours": 48,
            "rule_version": "2026-10-01-corrected"
        }
    }

    # Case A: User only opened app (no play) -> must FAIL under corrected rule
    user_events_app_open_only = [
        {
            "event_id": "ev-02",
            "user_id": "U-TEST-2",
            "event": "app_open",
            "received_at": "2026-10-02T10:00:00Z",
            "properties": {}
        }
    ]
    outcome_corrected_fail = judge.judge_goal(decision, user_events_app_open_only, g03_corrected=True)
    assert outcome_corrected_fail.status == "FAILED"

    # Case B: User actually started a play on a later IST day -> must SUCCEED
    user_events_with_play = [
        {
            "event_id": "ev-03",
            "user_id": "U-TEST-2",
            "event": "play_started",
            "received_at": "2026-10-02T10:05:00Z",
            "properties": {"title_id": "T0101"}
        }
    ]
    outcome_corrected_success = judge.judge_goal(decision, user_events_with_play, g03_corrected=True)
    assert outcome_corrected_success.status == "SUCCEEDED"
    assert outcome_corrected_success.success_event_type == "play_started"
