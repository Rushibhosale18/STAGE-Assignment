"""Standard library test runner for STAGE test suite (zero third-party dependencies)."""
import os
import sys
import traceback
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import test modules
from tests import (
    test_duplicates_and_stale,
    test_conflict_resolution,
    test_tool_failures,
    test_goal_rule_correction,
    test_verifier_and_safety
)


def run_all_tests():
    modules = [
        test_duplicates_and_stale,
        test_conflict_resolution,
        test_tool_failures,
        test_goal_rule_correction,
        test_verifier_and_safety
    ]

    total = 0
    passed = 0
    failed = 0
    errors = []

    print("==================================================")
    print("      STAGE: One User, One Agent Test Suite      ")
    print("==================================================")

    import tempfile
    import shutil

    for mod in modules:
        mod_name = mod.__name__.split(".")[-1]
        print(f"\n[SUITE] {mod_name}")
        for attr in dir(mod):
            if attr.startswith("test_"):
                total += 1
                func = getattr(mod, attr)
                test_name = attr
                try:
                    # Provide test fixtures if requested by signature
                    import inspect
                    sig = inspect.signature(func)
                    params = {}
                    temp_dir = None
                    if "test_setup" in sig.parameters:
                        from src.replay_harness import ReplayHarness
                        temp_dir = tempfile.mkdtemp()
                        params["test_setup"] = ReplayHarness("one_user_one_agent_pack", temp_dir)
                    if "judge_setup" in sig.parameters:
                        from src.data_loader import DataLoader
                        from src.outcome_judge import OutcomeJudge
                        l = DataLoader("one_user_one_agent_pack")
                        l.load_all_static()
                        params["judge_setup"] = OutcomeJudge(l)
                    if "verifier_setup" in sig.parameters:
                        from src.data_loader import DataLoader
                        from src.verifier import ActionVerifier
                        l = DataLoader("one_user_one_agent_pack")
                        l.load_all_static()
                        params["verifier_setup"] = (l, ActionVerifier(l))
                    if "tmp_path" in sig.parameters:
                        temp_dir = tempfile.mkdtemp()
                        params["tmp_path"] = Path(temp_dir)

                    func(**params)
                    print(f"  [PASS] {test_name}")
                    passed += 1

                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)

                except Exception as e:
                    print(f"  [FAIL] {test_name} -> {e}")
                    failed += 1
                    errors.append((mod_name, test_name, traceback.format_exc()))

    print("\n==================================================")
    print(f"RESULTS: {passed}/{total} Passed, {failed} Failed.")
    print("==================================================")

    if errors:
        print("\nFAILURE DETAILS:")
        for m, t, tb in errors:
            print(f"\n--- {m}.{t} ---")
            print(tb)
        sys.exit(1)
    else:
        print("\nAll unit, integration, and safety tests passed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
