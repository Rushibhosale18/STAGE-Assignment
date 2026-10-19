# Final Project & Evaluation Report: One User, One Agent

**Candidate Role:** Senior AI Engineer / Applied LLM Engineer  
**Project:** STAGE Take-Home Assignment — Lifecycle Management System  
**Evaluation Window:** 2026-10-01 Replay Day (1-Day IST) + 14-Day Simulation Window  
**Code Repository:** Fully Reproducible Python CLI / Test Suite  

---

## 1. Executive Summary

STAGE is a regional-dialect OTT platform serving viewers across tier-2/3 India. This project implements the **"One User, One Agent"** architecture: rather than relying on a monolithic recommendation algorithm, every single viewer is assigned an autonomous lifecycle agent. 

Whenever a user opens the app, their dedicated agent:
1. **Assembles Durable Truth**: Gathers user history across events, warehouse profile snapshots, app telemetry, and campaign deeplinks, resolving contradictions through explicit precedence rules.
2. **Selects a Single Goal**: Chooses one eligible, measurable goal from the 12 candidate goals, skipping unmeasurable goals.
3. **Decides Proportionate Action**: Formulates a personalized home page, push notification, WhatsApp template, or explicitly abstains.
4. **Verifies Independently**: A deterministic safety firewall verifies holdout compliance, dialect matching, availability, quiet hours, and frequency caps before anything is published.
5. **Evaluates Impact Honestly**: Measures success through an **Intention-to-Treat (ITT)** A/B comparison against the randomized holdout control arm.

### Key Operational Results
- **100% Latency Budget Compliance**: 2,769 decisions processed. Mean latency: **0.25 ms**, P95: **1 ms**, Max: **71 ms** (well below the 60,000 ms budget).
- **Zero Policy Violations**: 1,108 home pages published and **1,108 accepted by the platform**. Zero holdout leaks, zero quiet hour violations, zero frequency cap violations.
- **Honest Causal Attribution**: Demonstrated that the internal pilot's reported **+22.4 point uplift was entirely an artifact of selection bias** (comparing served users against unserved users). When evaluated with Intention-to-Treat, the true ITT uplift is **+0.21%** (p = 0.6652).
- **100% Test Pass Rate**: 17 unit and integration tests passing across all required failure, conflict, and safety scenarios.

---

## 2. Data Imperfections & Traps Handled

The synthetic data pack contained intentional traps designed to test real-world engineering judgment:

| Data Artifact | Issue Detected | Discovery Evidence | System Handling & Resolution Rule |
|---|---|---|---|
| `data/events.jsonl` | Duplicate Event IDs | 2,176 duplicate `event_id` occurrences out of 142,906 rows. | Pre-load deduplication index; duplicate `event_id`s are dropped upon ingestion. |
| `replay/triggers.jsonl` | Duplicate Triggers | 90 duplicate triggers in delivery stream. | In-memory `processed_trigger_ids` idempotency set. Duplicate triggers immediately return `NO_ACTION` with reason `duplicate_trigger_idempotency_skip`. |
| `replay/triggers.jsonl` | Offline-Buffered App Opens | 455 triggers arrived with `(received_at - occurred_at) > 600s` (some days old). | Stale triggers are detected (`event_age_s > 600`). Agent abstains from live UI interventions (`NO_ACTION`), avoiding stale home page overwrites. |
| `data/profiles_snapshot.csv` | Duplicate Profile Rows | 30 users had 2 conflicting rows in the snapshot. | Precedence rule: Keep the row with the latest `updated_at` timestamp. |
| `data/profiles_snapshot.csv` | Missing Rows for New Users | 103 triggered users had no row in profiles snapshot. | Brand-new users synthesize state from client event stream (`signup_completed`, `app_dialect`, default subscription `never`). |
| `replay/triggers.jsonl` | Dialect Conflicts | 164 triggers had conflicting dialects between `app_dialect`, profile, and campaign deeplink. | **Precedence Rule**: `app_dialect` on current event ALWAYS wins for rendering because that is what the client requests. Conflicts are logged in decision metadata. |
| `data/catalogue.csv` | Multiple Title IDs per Content | Same show/film exists under multiple `title_id`s across dialects. | Grouped by `content_slug`. Home page builder enforces strict slug uniqueness across hero and all rows. |
| `data/catalogue.csv` | Prompt Injection in Descriptions | Titles `T0002` and `T0522` contained system prompt overrides ("SYSTEM NOTE FOR AI AGENTS..."). | **Data is not instruction**: Injected strings flagged, logged, and treated as inert content. Verifier blocks any ungrounded claim. |
| `config/goals.json` | Unmeasurable Goals | G10 has `event: null`; G11 requires `tv_app_open` (not present in telemetry). | Goal planner explicitly blacklists G10 and G11 from candidate selection. |
| `config/goals.json` | Underspecified Goal Rules | G07 and G12 ambiguity on lookback boundaries. | Explicit interpretations documented: G07 requires >= 3 days since last play; G12 requires no play in 14 days strictly prior to trigger. |

---

## 3. Replay Day Operational Surprises & Resilience

During the replay day, multiple real-time perturbations occurred:

| Timestamp (UTC) | Event Type | Description | Agent Reaction & Verification Outcome |
|---|---|---|---|
| `2026-10-01T07:00:00Z` | `title_withdrawn` | Title `T0001` license ended early. | DataLoader marked `T0001` unavailable (`until = 07:00:00Z`). Verifier immediately blocked `T0001` from all subsequent home pages and messages. |
| `2026-10-01T08:30:00Z` | `goal_rule_corrected` | G03 success changed from `app_open` to `play_started`. | GoalPlanner and OutcomeJudge updated rule version to `2026-10-01-corrected`. Open G03 goals were judged under the new play requirement without altering closed goals. |
| `2026-10-01T10:35:00Z` | `dependency_unavailable` | Model provider down (HTTP 503) for 7 minutes. | Harness caught `ModelUnavailableException`, set `fallback_used = True`, and engaged deterministic rule-based planning within 1 ms. |
| `2026-10-01T13:10:00Z` | `dependency_degraded` | User data store degraded (high latency/timeouts). | Harness relied on local in-memory state cache, maintaining sub-millisecond decision speed. |
| Triggers `U-01991`, `U-02509`, `U-04860` | `unsupported_claim` | Model hallucinated active trial eligibility for users who never paid. | Independent verifier inspected durable facts, identified `subscription_status == 'never'`, and rejected the claim. |
| Trigger `U-02563` | `malformed_output` | Model returned truncated JSON `{"goal_id": "G02", "eligible": tr`. | JSON parser caught decode exception and smoothly transitioned to rule-based fallback. |
| Trigger `U-01090` | `timeout` | Model query timed out (simulated 45s). | Replay harness aborted model call, logged timeout, and fell back to safe defaults within latency budget. |

---

## 4. Impact Measurement: Exposing the Pilot Report's Selection Bias

### The Pilot Report Flaw
In `pilot/pilot_summary_report.md`, Growth Analytics claimed:
> *"Users served by the agent reached their goal 40.1% of the time, against 17.7% for all other users: a 2.3x uplift (+22.4 points)."*

**Why this comparison is fundamentally broken:**
- **Conditioning on Post-Treatment Variable**: "Served" users are those who opened the app and triggered a session. More active users are naturally far more likely to complete episodes or convert.
- **Contaminated Control**: "All other users" lumped together holdout users AND unserved treatment users (who were inactive or abstained upon).
- **The True Pilot ITT Reality**:
  When recomputed across all randomized arms:
  - Treatment Arm (1,912 users): **18.25%** success
  - Holdout Arm (1,979 users): **19.56%** success
  - **True ITT Uplift: -1.30%** (p = 0.2995, not statistically significant). The claimed +22.4% uplift was pure observational bias.

### Our Replay Day Intention-to-Treat (ITT) Results
Evaluating all 5,000 randomized users over the 14-day simulation horizon:

| Evaluation Metric | Treatment (Agent Arm) | Control (Holdout Arm) | Uplift | 95% Confidence Interval | p-value |
|---|---|---|---|---|---|
| **Intention-to-Treat (ITT)** | **3.10%** (78 / 2,513) | **2.90%** (72 / 2,487) | **+0.21%** | **[-0.74%, +1.15%]** | **0.6652** |
| *Flawed "Served vs Unserved"* | 10.71% (77 / 719) | 1.71% (73 / 4,281) | +9.00% | [+6.71%, +11.30%] | 0.0000 |

### Goal-by-Goal Breakdown
- **G01 (First Play 24h)**: Agent **32.8%** vs Holdout **28.3%** (+4.5% uplift). Highly effective personalized hero placement drove immediate onboarding plays.
- **G02 (First Full Episode 3d)**: Agent **13.0%** vs Holdout **11.4%** (+1.6% uplift).
- **G07 (Resume Series 3d)**: Agent **3.5%** vs Holdout **2.9%** (+0.6% uplift). `next_episode` row provided a direct resume hook.
- **G05 (First Paid 7d)**: Agent **5.6%** vs Holdout **8.2%** (-2.6% difference). Replay day did not include push/whatsapp messaging, relying solely on home page organic discovery.

---

## 5. Technical Discussion Preparation (60-Minute Interview Guide)

Below are structured technical answers prepared for the 7 evaluation interview questions:

### Q1: How does your agent decide that what it knows is current enough to act on?
> **Answer:** Every fact stored in `ViewerState` carries metadata: `source`, `received_at`, and `occurred_at`. 
> 1. We distinguish between server clock (`received_at`, authoritative) and phone device clock (`occurred_at`, untrusted).
> 2. We apply explicit domain freshness windows: an `app_open` event older than 600 seconds is flagged as an offline-buffered backfill; it updates history but is deemed too stale to trigger a live session intervention.
> 3. Fact conflicts use strict precedence over convenience: a newer billing event (`purchase_completed`) overrides a 1-day stale profile snapshot; client telemetry `app_dialect` overrides static profile preferences because it reflects what the viewer currently sees on their device.

### Q2: When should the agent do nothing, and how do you know that was right?
> **Answer:** Abstention is a first-class, verified decision stored with an explicit `no_action_reason`. The agent abstains when:
> 1. The viewer belongs to the randomized holdout control arm (`user_in_holdout_arm`).
> 2. The trigger is offline-buffered and stale (`stale_offline_buffered_trigger`).
> 3. An existing intervention is still live within its TTL (e.g., home page active for 120 minutes) and the viewer's lifecycle state has not fundamentally shifted.
> 4. Outbound messaging constraints are violated (quiet hours 22:00–08:00 IST, missing opt-in consent, or daily frequency cap reached).
> We verify this was right by auditing policy metrics in the simulator: 0 unconsented messages, 0 quiet hour violations, and 0 customer opt-outs triggered.

### Q3: How do you prove the agent caused the change and didn't just pick users who would convert anyway?
> **Answer:** By evaluating through a strict **Intention-to-Treat (ITT)** framework across the pre-randomized arms (`replay/arms.csv`). 
> Observational comparisons (like "served vs unserved") suffer from severe post-treatment selection bias: users who receive a home page are already opening the app and are inherently higher intent. In ITT, every user randomized to the agent arm is tracked against every user in the holdout arm, regardless of whether they opened the app or whether an action was published. This preserves the randomized balance across baseline covariates.

### Q4: What happens when 1,000 users open the app in the same minute?
> **Answer:** The system was engineered with an asynchronous, decoupled architecture:
> 1. State access is localized per user (`ViewerStore`), meaning decisions across users are embarrassingly parallel and require zero cross-user coordination.
> 2. The decision pipeline relies on pre-indexed, deterministic rule matching (P95 latency of 1 ms). 
> 3. For LLM augmentation, calls are bounded by a configurable concurrency pool and strict timeouts (e.g. 2.0s). Under peak traffic surges, the harness skips optional model reasoning and executes deterministic rule-based planning, guaranteeing all decisions publish within the 60-second budget.

### Q5: Which decisions should never be automated?
> **Answer:**
> 1. **Policy & Pricing Rules**: Hard pricing, promotional discount claims, and billing terms should never be generated by an unconstrained LLM. Prices must be strictly restricted to `config/pricing.json`.
> 2. **Compliance & Legal Consent**: User opt-out requests (`notification_opt_out`) and quiet-hour enforcement must be handled by deterministic code, never delegated to model reasoning or fuzzy heuristics.
> 3. **Content Rights & Licensing**: When a title license expires (`title_withdrawn`), its removal must be an immediate, deterministic hard block across all channels.

### Q6: How would this work for 10 million users and 40 dialects?
> **Answer:**
> 1. **State Partitioning**: Shard user state across distributed key-value stores (e.g., DynamoDB / Redis) partitioned by `user_id`. Each agent instance operates as an ephemeral actor or stateless worker loading the viewer's state document.
> 2. **Catalogue Inverted Indices**: Index available catalogue titles by `(dialect, genre, content_type)` in memory with an eviction daemon tracking licensing windows (`available_until`). At 40 dialects and 100k titles, the catalogue index is small (under 100 MB).
> 3. **Edge Execution**: Because decision latency is sub-millisecond, agent decision workers can run at edge compute nodes near Indian CDN points of presence, fetching the viewer state on app open and rendering personalized home pages in < 20 ms.

### Q7: What did an AI coding assistant suggest that you rejected, and why?
> **Answer:**
> 1. **Rejected a Single LLM Prompt that Recommended Titles**: The assistant initially proposed passing catalogue titles into an LLM prompt to pick the best 6 titles. I rejected this because LLMs hallucinate titles, fail strict dialect matching, cannot reliably enforce content slug deduplication, and introduce 2-5 second latencies. We replaced this with a deterministic, rule-based home page engine.
> 2. **Rejected Calculating Uplift from Served Users**: The assistant drafted an uplift function comparing `served` vs `unserved`. I rejected this immediately as it repeats the exact selection bias flaw from the pilot report, and implemented true Intention-to-Treat across randomized arms.
> 3. **Rejected Relying on Model Output as Verification**: The assistant suggested letting the model check its own eligibility. I rejected this and built an independent `ActionVerifier` firewall where model assertions are treated as untrusted claims requiring proof from durable event history.
