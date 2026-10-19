"""Unified Command-Line Interface (CLI) for STAGE: One User, One Agent."""
import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_loader import DataLoader
from src.impact_reporter import ImpactReporter
from src.outcome_judge import OutcomeJudge
from src.replay_harness import ReplayHarness

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("STAGE-CLI")


def cmd_replay(args):
    """Run the replay harness on the trigger stream."""
    logger.info(f"Starting replay on pack '{args.pack}' -> output '{args.out}'...")
    harness = ReplayHarness(pack_dir=args.pack, output_dir=args.out)
    harness.warm_up_history()
    harness.run_replay()
    logger.info("Replay phase completed successfully!")


def cmd_simulate(args):
    """Run the official simulator on published actions."""
    sim_script = Path(args.pack) / "simulator" / "simulate_outcomes.py"
    if not sim_script.exists():
        logger.error(f"Simulator script not found at {sim_script}")
        sys.exit(1)

    cmd = [
        sys.executable,
        str(sim_script),
        "--pack", str(args.pack),
        "--actions", str(args.actions),
        "--out", str(args.out),
        "--seed", str(args.seed)
    ]
    logger.info(f"Invoking outcome simulator: {' '.join(cmd)}")
    res = subprocess.run(cmd, check=True)
    logger.info("Simulation completed successfully!")


def cmd_judge(args):
    """Judge outcomes from simulated outcome events."""
    out_dir = Path(args.out)
    pack_dir = Path(args.pack)
    
    loader = DataLoader(str(pack_dir))
    loader.load_all_static()
    judge = OutcomeJudge(loader)

    decisions_path = out_dir / "decisions.jsonl"
    sim_outcomes_path = out_dir / "sim" / "outcome_events.jsonl"
    outcomes_file_path = out_dir / "outcomes.jsonl"

    if not decisions_path.exists():
        logger.error(f"Decisions file not found at {decisions_path}")
        sys.exit(1)
    if not sim_outcomes_path.exists():
        logger.error(f"Outcome events file not found at {sim_outcomes_path}")
        sys.exit(1)

    logger.info("Loading outcome events by user...")
    events_by_user = {}
    with open(sim_outcomes_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ev = json.loads(line)
                uid = ev["user_id"]
                if uid not in events_by_user:
                    events_by_user[uid] = []
                events_by_user[uid].append(ev)

    judgments = []
    logger.info("Evaluating decisions against outcome telemetry...")
    with open(decisions_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                uid = d["viewer_id"]
                u_events = events_by_user.get(uid, [])
                j = judge.judge_goal(d, u_events, g03_corrected=True)
                judgments.append(j.to_dict())

    with open(outcomes_file_path, "w", encoding="utf-8") as f:
        for j in judgments:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")

    logger.info(f"Judged {len(judgments)} decisions -> {outcomes_file_path}")


def cmd_report(args):
    """Generate latency report, impact report, and final executive report."""
    out_dir = Path(args.out)
    pack_dir = Path(args.pack)
    reporter = ImpactReporter(str(pack_dir))

    decisions = []
    with open(out_dir / "decisions.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                decisions.append(json.loads(line))

    outcomes = []
    with open(out_dir / "outcomes.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                outcomes.append(json.loads(line))

    actions = []
    with open(out_dir / "actions.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                actions.append(json.loads(line))

    loader = DataLoader(str(pack_dir))
    loader.load_arms()

    # 1. Latency Report
    lat_path = out_dir / "latency_report.json"
    reporter.generate_latency_report(decisions, str(lat_path))
    logger.info(f"Latency report written to {lat_path}")

    # 2. Impact Report
    imp_path = out_dir / "impact_report.md"
    reporter.generate_impact_report(loader.arms, outcomes, actions, str(imp_path))
    logger.info(f"Impact report written to {imp_path}")


def cmd_run_all(args):
    """Run the entire end-to-end pipeline in one single command."""
    logger.info("=== STEP 1: REPLAY STREAM ===")
    cmd_replay(args)

    logger.info("\n=== STEP 2: SIMULATE 14-DAY OUTCOMES ===")
    args.actions = Path(args.out) / "actions.jsonl"
    args.sim_out = Path(args.out) / "sim"
    cmd_simulate(argparse.Namespace(
        pack=args.pack,
        actions=args.actions,
        out=args.sim_out,
        seed=args.seed
    ))

    logger.info("\n=== STEP 3: JUDGE GOALS & ATTRIBUTION ===")
    cmd_judge(args)

    logger.info("\n=== STEP 4: GENERATE IMPACT & LATENCY REPORTS ===")
    cmd_report(args)

    logger.info("\n=== FULL PIPELINE COMPLETED SUCCESSFULLY! ===")


def main():
    parser = argparse.ArgumentParser(description="STAGE: One User, One Agent Lifecycle System")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    default_pack = os.environ.get("STAGE_PACK_DIR", "one_user_one_agent_pack")

    # Replay
    p_replay = subparsers.add_parser("replay", help="Run the replay harness")
    p_replay.add_argument("--pack", default=default_pack, help="Root path of the data pack")
    p_replay.add_argument("--out", default="sample_run", help="Output directory")

    # Simulate
    p_sim = subparsers.add_parser("simulate", help="Run the simulator")
    p_sim.add_argument("--pack", default=default_pack, help="Root path of the data pack")
    p_sim.add_argument("--actions", default="sample_run/actions.jsonl", help="Path to actions JSONL")
    p_sim.add_argument("--out", default="sample_run/sim", help="Simulator output directory")
    p_sim.add_argument("--seed", default="oua-practice", help="Simulation seed")

    # Judge
    p_judge = subparsers.add_parser("judge", help="Judge outcomes")
    p_judge.add_argument("--pack", default=default_pack, help="Root path of the data pack")
    p_judge.add_argument("--out", default="sample_run", help="Directory with decisions and sim outcomes")

    # Report
    p_report = subparsers.add_parser("report", help="Generate reports")
    p_report.add_argument("--pack", default=default_pack, help="Root path of the data pack")
    p_report.add_argument("--out", default="sample_run", help="Directory with outputs")

    # Run-All
    p_all = subparsers.add_parser("run-all", help="Run the full pipeline end-to-end")
    p_all.add_argument("--pack", default=default_pack, help="Root path of the data pack")
    p_all.add_argument("--out", default="sample_run", help="Output directory")
    p_all.add_argument("--seed", default="oua-practice", help="Simulation seed")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "replay":
        cmd_replay(args)
    elif args.command == "simulate":
        cmd_simulate(args)
    elif args.command == "judge":
        cmd_judge(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "run-all":
        cmd_run_all(args)


if __name__ == "__main__":
    main()
