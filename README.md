# STAGE: One User, One Agent

> **Lifecycle AI Agent Engineering System for OTT Regional Dialect Streaming**  
> *Antigravity Implementation for STAGE Senior AI / Applied LLM Engineer Assessment*

---

## Quickstart: The One Command

To run the entire replay, simulator, outcome judgment, and impact reporting pipeline from start to finish:

```bash
python src/cli.py run-all --pack one_user_one_agent_pack --out sample_run
```

Or using the standard Python 3.11 executable:
```bash
py -3.11 src/cli.py run-all --pack one_user_one_agent_pack --out sample_run
```

### Running the Automated Test Suite (100% Pass)
```bash
py -3.11 tests/run_tests.py
```
*(Runs 17 unit and integration tests across idempotency, precedence rules, tool failures, rule corrections, and verifier safety with zero third-party dependencies).*

---

## Project Structure

```
stage-agent/
├── README.md                 # Setup, quickstart & replay instructions
├── ARCHITECTURE.md           # Ownership, planning, memory, verifier & trust boundaries
├── AI_COLLABORATION.md       # AI collaboration log & rejected suggestions
├── KNOWN_LIMITATIONS.md      # Intentional architectural trade-offs & scaling limits
├── src/                      # Core production package
│   ├── __init__.py
│   ├── config.py             # Constants, pricing, quiet hours & IST date utilities
│   ├── models.py             # Pydantic/dataclass schemas (ViewerState, Decision, Action)
│   ├── data_loader.py        # Pack loading, deduplication, indexer & prompt injection filter
│   ├── fact_resolver.py      # Precedence rules & explicit conflict tracking
│   ├── goal_planner.py       # Candidate goal selection, lifecycle & rule correction
│   ├── intervention_planner.py # Home page builder, push & WhatsApp generator
│   ├── model_provider.py     # Mock LLM provider with fault injection & outage simulation
│   ├── verifier.py           # Independent safety verification firewall
│   ├── outcome_judge.py      # Telemetry evaluator & goal attribution engine
│   ├── impact_reporter.py    # ITT statistical evaluator & selection bias analyzer
│   ├── replay_harness.py     # Chronological replay engine with latency tracking
│   └── cli.py                # Unified CLI entrypoint (replay, simulate, judge, report, run-all)
├── tests/                    # Automated test suite
│   ├── run_tests.py          # Standalone test runner (zero external dependencies)
│   ├── test_duplicates_and_stale.py
│   ├── test_conflict_resolution.py
│   ├── test_tool_failures.py
│   ├── test_goal_rule_correction.py
│   └── test_verifier_and_safety.py
├── sample_run/               # Completed replay evaluation artifacts
│   ├── decisions.jsonl       # Machine-readable decisions with evidence & provenance
│   ├── actions.jsonl         # Published actions (input to simulator)
│   ├── outcomes.jsonl        # Judged goal outcomes & learnings
│   ├── viewer_state/         # Durable per-viewer JSON states
│   ├── latency_report.json   # Latency percentiles & budget compliance
│   ├── impact_report.md      # Intention-to-Treat (ITT) evaluation & pilot critique
│   └── final_report.md       # Full executive report & technical discussion prep
└── one_user_one_agent_pack/  # Complete data pack & simulator
```

---

## Core Pipeline Workflow

The system implements the **7-Step Agent Loop**:

1. **Understand Viewer**: Ingests historical events and profiles, tracking facts with source provenance, timestamps, and freshness. Resolves dialect and subscription contradictions via strict precedence rules.
2. **Choose Goal**: Evaluates eligibility across 10 candidate goals (skipping unmeasurable G10 and G11). Sets deadlines and success conditions.
3. **Decide Intervention**: Constructs personalized home page (hero + up to 6 rows, slug uniqueness, >=3 titles/row) or compliant notifications.
4. **Act Within Budget**: Publishes decisions in sub-millisecond time (P95: 1 ms), well within the 60-second budget. Employs graceful fallback on model 503 outages or timeouts.
5. **Independent Verification**: An autonomous firewall independently validates holdout arm safety, consent, quiet hours (22:00–08:00 IST), daily frequency caps, dialect match, and title availability.
6. **Close the Loop**: Replays 14-day outcome telemetry, judges goal success, incorporates mid-replay G03 rule corrections, and records learnings in viewer state.
7. **Prove Impact**: Computes Intention-to-Treat (ITT) uplift against the randomized holdout arm, exposing and correcting the selection bias found in observational metrics.

---

## CLI Commands Reference

- **Full End-to-End Pipeline**:
  ```bash
  python src/cli.py run-all --pack one_user_one_agent_pack --out sample_run
  ```
- **Replay Only**:
  ```bash
  python src/cli.py replay --pack one_user_one_agent_pack --out sample_run
  ```
- **Simulator Only**:
  ```bash
  python src/cli.py simulate --pack one_user_one_agent_pack --actions sample_run/actions.jsonl --out sample_run/sim --seed oua-practice
  ```
- **Judge Outcomes Only**:
  ```bash
  python src/cli.py judge --pack one_user_one_agent_pack --out sample_run
  ```
- **Generate Reports Only**:
  ```bash
  python src/cli.py report --pack one_user_one_agent_pack --out sample_run
  ```
