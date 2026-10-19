# Known Limitations & Intentional Architectural Trade-Offs

**Candidate Role:** Senior AI Engineer / Applied LLM Engineer  
**Assignment:** STAGE — One User, One Agent  

In accordance with Section 14 and 17 of the Candidate Brief, this document describes what was intentionally left incomplete, the architectural trade-offs made, and how these components would be expanded in a full-scale production system.

---

## 1. Storage Architecture: Local JSON vs. Distributed Partitioned Key-Value Store

### What Was Built
- Viewer states are stored as individual JSON files in `sample_run/viewer_state/<user_id>.json` with an in-memory dictionary cache during the replay run.
- **Why**: This provides 100% auditability, portability, and zero-dependency reproducibility for take-home evaluators.

### Production Scaling (10 Million Users)
- **Bottleneck**: Storing 10 million JSON files on local disk causes filesystem inode exhaustion and directory scan degradation.
- **Production Solution**: Replace local JSON with a distributed, partitioned NoSQL store:
  - **Primary Store**: DynamoDB, ScyllaDB, or Cassandra partitioned by `hash(user_id)`.
  - **In-Memory Cache**: Redis cluster for low-latency session state (P99 read latency < 2 ms).
  - **Streaming Ingestion**: Apache Kafka and Apache Flink to process incoming telemetry streams and continuously update viewer facts asynchronously.

---

## 2. Model Provider: Mock/Replay Mode vs. Live Hosted LLM Cluster

### What Was Built
- A `ModelProvider` class that operates in mock replay mode by default, accurately simulating realistic latency, reproducing exact injected faults from `model_faults.jsonl` (malformed JSON, 45s timeout, unsupported claims), and handling HTTP 503 provider outages during control event windows.
- **Why**: The brief explicitly required that evaluators must be able to run the assignment with **one command without requiring personal API keys** or incurring cloud costs.

### Production Scaling
- **Production Solution**: A hybrid two-tier decision engine:
  - **Tier 1 (Deterministic Fast Path)**: Pre-computed rule engine processes 95% of routine app opens in < 2 ms (hero selection, dialect filtering, slug deduplication).
  - **Tier 2 (Asynchronous LLM Worker)**: For ambiguous viewers (e.g. users with complex multi-dialect cross-genre browsing), trigger an asynchronous offline LLM job via vLLM / self-hosted open models (e.g. Gemma 2 / Llama 3) to synthesize personalized recommendations and cache them before the viewer's next visit.

---

## 3. Deliberate Blacklisting of Unmeasurable Goals (G10 and G11)

### What Was Built
- The goal planner explicitly refuses to consider:
  - `G10 (meaningful_engagement_7d)`: The catalog defines `success: {"event": null, "condition": "engages meaningfully"}`.
  - `G11 (tv_activation_14d)`: The catalog defines `success: {"event": "tv_app_open"}`, but the STAGE event telemetry does not include TV events.
- **Why**: Claiming success on unmeasurable or un-instrumented metrics is an engineering anti-pattern. We deliberately skip these goals and document the exact reason.

### Production Solution
- Work with Product & Platform Analytics to establish clear event definitions:
  - Define `meaningful_engagement` as `>= 3 play sessions with completion >= 50%`.
  - Instrument TV app client SDKs to emit `tv_app_open` before launching TV-oriented campaigns.

---

## 4. Replay Horizon vs. Continuous Daemon Lifecycle

### What Was Built
- The harness ingests a single replay day (2026-10-01 IST) in chronological order, publishes actions, and runs the 14-day outcome simulator.
- **Why**: Strictly adheres to the evaluation framework specified by the brief and simulator.

### Production Solution
- Implement a long-running, event-driven daemon:
  - Real-time event consumer listening to user Kafka topics.
  - Periodic cron sweepers to evaluate expired goal windows and transition lifecycle states.
  - Dynamic budget throttlers to shed non-critical model calls during peak evening traffic spikes (19:00–22:00 IST).
