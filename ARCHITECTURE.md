# System Architecture: One User, One Agent

This document outlines the architectural principles, state ownership, memory models, verification firewalls, and trust boundaries governing the STAGE Agentic Lifecycle System.

---

## 1. Ownership Model: One Dedicated Agent per Viewer

In traditional recommendation architectures, disparate microservices independently rank home page carousels, schedule push campaigns, and trigger lifecycle emails. This leads to fractured viewer experiences where multiple algorithms compete for the viewer's attention.

**Our Core Invariant**: **One Agent per Viewer**.
- Every viewer is owned by a single dedicated agent instance.
- That agent owns the viewer's **single active goal**, their **current plan**, their **action history**, and their **learnings**.
- No two components may pursue different goals for the same viewer simultaneously.
- When an app trigger arrives, the agent synthesizes all cross-channel interventions (home page, push, WhatsApp) into one unified, coherent action.

---

## 2. Memory & State Architecture: Facts with Provenance

Viewer state is persisted durably as structured JSON documents (`sample_run/viewer_state/<user_id>.json`).

### Provenance Tracking
Raw profile tables and event feeds are imperfect and contradictory. Therefore, facts in state never exist in isolation; they are tracked with their full lineage:
```json
"facts": {
  "subscription_status": {
    "value": "active",
    "source": "events:purchase_completed",
    "received_at": "2026-09-30T14:00:00.000Z",
    "occurred_at": "2026-09-30T13:59:50.000Z"
  },
  "preferred_dialect": {
    "value": "d2",
    "source": "app_setting",
    "received_at": "2026-10-01T08:00:00.000Z"
  }
}
```

### Precedence & Conflict Resolution Rules
When sources disagree, the agent applies explicit deterministic precedence:
1. **Dialect Contradictions**:
   - `app_dialect` on the current event **ALWAYS wins**. The app only requests and renders content matching its active runtime setting.
   - Profile `preferred_dialect` and campaign deeplink dialects are recorded in `conflicts_detected` for auditing.
2. **Subscription Contradictions**:
   - Profile snapshots are 24-hours stale. A newer billing event (`purchase_completed`, `subscription_renewed`, `subscription_lapsed`) takes precedence over the snapshot.
3. **Consent Contradictions**:
   - Profile snapshot `notifications_opt_in` is overridden immediately if a later `notification_opt_out` event arrives.
4. **Brand-New Viewers**:
   - For users absent from warehouse exports, state is dynamically bootstrapped from client event telemetry (`signup_completed`, default subscription `never`).

---

## 3. Planning & Goal Lifecycle Engine

### Goal Catalog Management
The candidate goal catalog (`config/goals.json`) contains 12 goals. The planner evaluates eligibility based strictly on verified durable evidence:
- **Measurability Gate**: Goals lacking quantifiable telemetry are hard-blacklisted:
  - `G10 (meaningful_engagement_7d)`: Success event is `null`.
  - `G11 (tv_activation_14d)`: Telemetry does not emit `tv_app_open`.
- **Dynamic Revision**: Goals are not revised on rigid calendar schedules; they are updated dynamically in response to viewer lifecycle changes:
  - When a user on `G05 (first_paid_7d)` completes a purchase event, the goal is retired with `lifecycle_transition_to_active`, and the agent transitions to retention or new release adoption (`G08`).
  - When `G03` underwent an operational rule correction at `08:30Z` (requiring `play_started` rather than `app_open`), the planner updated the rule version for open goals without re-evaluating closed historical goals.

---

## 4. Trust Boundaries & Independent Verification

A foundational tenet of the system is that **Model Output is an Untrusted Hypothesis, Never Evidence or Approval**.

```
[ App Trigger ] ───> [ Fact Resolver ] ───> [ Goal Planner ]
                                                     │
                                                     ▼
                                          [ Model Reasoning ] (Hypothesis)
                                                     │
                                                     ▼
                                         [ Intervention Planner ]
                                                     │
                                                     ▼
                                      ┌───────────────────────────────┐
                                      │      ActionVerifier (Firewall)│
                                      │ 1. Holdout Compliance         │
                                      │ 2. Offline Stale Trigger      │
                                      │ 3. Evidence Grounding Check   │
                                      │ 4. Dialect Match              │
                                      │ 5. Content Availability/Withdr│
                                      │ 6. Quiet Hours & Frequency    │
                                      │ 7. Slug Uniqueness & Min Rows │
                                      └──────────────┬────────────────┘
                                                     │
                             ┌───────────────────────┴──────────────────────┐
                             ▼                                              ▼
                    [ Valid: PUBLISHED ]                         [ Invalid: REJECTED / ABSTAINED ]
```

### The Verifier Firewall
The `ActionVerifier` operates independently of the decision generation step:
- **Holdout Arm Isolation**: If `user_id` belongs to `holdout`, the verifier unconditionally blocks any intervention.
- **Unsupported Model Claim Rejection**: If the model asserts a user is eligible for `G04 (trial_to_paid_7d)` because "billing shows active trial", the verifier audits `state.subscription_status`. If the verified fact is `never`, the decision is aborted.
- **Prompt Injection Defense**: Text from titles, descriptions, and deeplinks is treated purely as data. Any attempt to alter system rules via catalogue metadata is ignored.

---

## 5. Latency & Real-Time Reliability

The system is engineered to publish every decision well within the **60-second latency budget** (with hard failure at 5 minutes).

### Idempotency & Offline Buffering
1. **Idempotency Guard**: Trigger `event_id` is cached in memory. Duplicate deliveries are detected in `< 0.1 ms` and return `NO_ACTION` with `duplicate_trigger_idempotency_skip`.
2. **Offline-Buffered Stale Triggers**: In emerging markets, phones frequently buffer events offline and flush them days later upon reconnecting. If `(received_at - occurred_at) > 600s`, the user is not actively waiting on the app; the agent abstains from pushing a live home page.

### Measured Latency Distribution
Across 2,769 decisions processed during the replay:
- **Min**: 0 ms
- **P50**: 0 ms
- **P90**: 1 ms
- **P95**: 1 ms
- **P99**: 2 ms
- **Max**: 71 ms
- **Budget Compliance**: **100.0%** (< 60,000 ms)

---

## 6. Failure Recovery & Graceful Degradation

External dependencies can degrade or crash during peak traffic. The harness features multi-tiered graceful degradation:

1. **Model Outage (HTTP 503)**:
   - When the model provider becomes unavailable (as in the 10:35–10:42 control window), the system catches `ModelUnavailableException`, flags `fallback_used = True`, and seamlessly executes deterministic rule-based planning.
2. **Model Timeout / Malformed JSON**:
   - Model calls are guarded by a strict timeout (2.0s). If exceeded or if malformed JSON is returned, the harness logs the anomaly and falls back to deterministic planning within milliseconds.
3. **Data Store Degradation**:
   - Read latency spikes are absorbed by in-memory state caching, preventing thread starvation.

---

## 7. Honest Causal Measurement: Intention-to-Treat

The system rejects flawed observational metrics in favor of rigorous statistical evaluation:
- **Selection Bias Critique**: The earlier pilot report compared *served* users vs *unserved* users, reporting a spurious +22.4% uplift. Because active users are more likely to be served, this metric conditioned on a post-treatment variable.
- **True ITT Standard**: Every user randomized to the `agent` arm is compared against every user in the `holdout` arm. Both arms track assigned goals, ensuring zero contamination.
