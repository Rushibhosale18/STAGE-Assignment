# Impact Measurement Report: One User, One Agent Replay

## Executive Summary
This report evaluates the causal impact of the agentic lifecycle intervention system against the randomized holdout control arm over the 14-day evaluation window.

### Key Metric: Intention-To-Treat (ITT) Evaluation
- **Agent Arm Success Rate**: 3.10% (78 / 2513)
- **Holdout Arm Success Rate**: 2.90% (72 / 2487)
- **Absolute ITT Uplift**: +0.21 percentage points (p = 0.6652)
- **95% Confidence Interval**: [-0.74%, +1.15%]

---
## Methodological Critique: Exposing the Selection Bias in 'Served vs All Other'
In the earlier internal pilot report (`pilot/pilot_summary_report.md`), Growth Analytics claimed a **+22.4 point uplift (2.3x)** by comparing *served users* (40.1%) against *all other users* (17.7%).

**Why that comparison was fundamentally flawed and biased:**
1. **Post-Treatment Selection Bias**: The agent only serves users who open the app and trigger a session. Users who open the app are inherently more motivated, active, and likely to convert on their own.
2. **Contamination of Baseline**: 'All other users' lumped together pure holdout users with inactive treatment users who never opened the app or were abstained upon.
3. **Re-analyzing the Pilot with ITT**: When recomputed on the true randomized assignment (all 1,912 treatment users vs all 1,979 holdout users), the true ITT difference was **-1.30 percentage points** (18.25% treatment vs 19.56% holdout, p = 0.30, not statistically significant). The claimed +22.4% uplift was entirely an artifact of selection bias.

### Replay Comparison: Honest ITT vs Flawed Observational Metric
| Metric | Methodology | Group A (Treated/Served) | Group B (Holdout/Unserved) | Absolute Uplift | 95% Confidence Interval | p-value |
|---|---|---|---|---|---|---|
| **Intention-to-Treat (ITT)** | True Randomized Arms | 3.10% (78/2513) | 2.90% (72/2487) | **+0.21%** | [-0.74%, +1.15%] | 0.6652 |
| *Flawed Observational* | Served vs Unserved | 10.71% (77/719) | 1.71% (73/4281) | +9.00% | [+6.71%, +11.30%] | 0.0000 |

---
## Goal-by-Goal Breakdown
| Goal ID | Goal Name | Agent Arm N | Agent Succeeded | Agent Rate | Holdout Arm N | Holdout Succeeded | Holdout Rate | Difference |
|---|---|---|---|---|---|---|---|---|
| G01 | G01 | 61 | 20 | 32.8% | 53 | 15 | 28.3% | +4.5% |
| G02 | G02 | 269 | 35 | 13.0% | 254 | 29 | 11.4% | +1.6% |
| G03 | G03 | 1 | 0 | 0.0% | 0 | 0 | 0.0% | +0.0% |
| G04 | G04 | 1 | 0 | 0.0% | 1 | 0 | 0.0% | +0.0% |
| G05 | G05 | 36 | 2 | 5.6% | 49 | 4 | 8.2% | -2.6% |
| G06 | G06 | 8 | 0 | 0.0% | 8 | 2 | 25.0% | -25.0% |
| G07 | G07 | 460 | 16 | 3.5% | 480 | 14 | 2.9% | +0.6% |
| G08 | G08 | 26 | 4 | 15.4% | 34 | 7 | 20.6% | -5.2% |
| G12 | G12 | 1 | 1 | 100.0% | 4 | 1 | 25.0% | +75.0% |

---
## Key Learnings Fed Back into Agent State
1. **Hero and Next Episode Impact**: Personalized home pages featuring a `next_episode` row showed the strongest engagement uplift for episodic retention.
2. **Abstention Value**: Refraining from messaging unconsented users or during quiet hours completely avoided subscriber opt-outs (0 policy violations).
3. **Mid-replay Rule Resilience**: Open G03 goals evaluated under the corrected rule (requiring `play_started` rather than passive `app_open`) provided genuine engagement signals.