# AI Collaboration Log: Human Oversight and Rejected AI Suggestions

**Candidate Role:** Senior AI Engineer / Applied LLM Engineer  
**Assignment:** STAGE — One User, One Agent  

In accordance with Section 14 and 16 of the Candidate Brief, this log documents how AI tools were utilized, how their outputs were verified, and critical instances where AI-generated suggestions were **explicitly rejected or corrected** to maintain architectural rigor, safety, and statistical honesty.

---

## 1. How AI Tools Were Utilized

AI assistance was utilized as a force multiplier for:
- **Rapid Prototyping**: Generating boilerplate schemas for data models and configuration constants.
- **Data Exploration**: Drafting initial inspection scripts to identify duplicate `event_id`s, offline-buffered app opens, and prompt injections in descriptions.
- **Statistical Modeling**: Providing formulas for two-proportion z-tests, standard errors, and confidence intervals.

---

## 2. Examples of Rejected or Corrected AI Suggestions

### Example 1: Rejection of LLM-Based Home Page Title Generation
- **AI Suggestion**: The AI assistant initially suggested feeding the user's watch history and the catalogue descriptions into an LLM prompt, asking the model to return 6 title IDs in JSON format for the personalized home page.
- **Why It Was Rejected**:
  1. **Latency Budget Violation**: An LLM call per home page adds 2,000–5,000 ms of latency, threatening the 60-second budget during peak spikes and failing sub-second UI responsiveness.
  2. **Hallucination Risk**: LLMs frequently hallucinate non-existent title IDs or mix dialect variants across language families (e.g., suggesting a Bhojpuri `d1` title for a Maithili `d4` viewer).
  3. **Constraint Infeasibility**: LLMs struggle with combinatorial constraints like ensuring each `content_slug` appears only once across 6 rows and guaranteeing >= 3 titles per row.
- **Our Resolution**: We rejected the LLM generation and built a deterministic, in-memory inverted index (`InterventionPlanner`) that sorts candidate titles by dialect, availability, and user genre affinity in `< 1 ms` with 100% adherence to platform rules.

---

### Example 2: Rejection of Flawed "Served vs Unserved" Uplift Metric
- **AI Suggestion**: When tasked with writing the outcome evaluation script, the AI assistant drafted a summary function that computed uplift as:
  $$\text{Uplift} = \text{Rate}(\text{Users who received an Action}) - \text{Rate}(\text{Users who received No Action})$$
- **Why It Was Rejected**:
  This suggestion repeated the **exact fatal flaw present in the internal pilot report** (`pilot/pilot_summary_report.md`):
  1. **Selection Bias**: Users who are served must have opened the app. They are already more motivated and active, making their conversion rate artificially high.
  2. **Violates Randomization**: Comparing served treatment users against unserved users breaks the randomized trial balance.
- **Our Resolution**: We rejected the observational code and implemented a strict **Intention-to-Treat (ITT)** framework. All 2,513 randomized agent-arm users were compared against all 2,487 holdout-arm users, preserving unbiased statistical attribution.

---

### Example 3: Correction of Holdout Arm Goal Tracking
- **AI Suggestion**: When implementing the holdout arm logic in the replay harness, the AI assistant initially wrote:
  ```python
  if arm == "holdout":
      return Decision(action="NO_ACTION", goal=None, status="HOLDOUT"), None
  ```
- **Why It Was Rejected**:
  If holdout users have `goal = None`, the outcome judge cannot evaluate whether those control users achieved their goal organically. This artificially renders holdout success as 0.0%, creating a bogus "100% uplift" for the agent arm.
- **Our Resolution**: We corrected the logic so the agent determines the candidate goal for holdout users identically to treatment users, but enforces the holdout rule by publishing **zero actions**. This enabled a genuine apples-to-apples comparison of organic success (2.90%) vs agent intervention success (3.10%).

---

### Example 4: Rejection of Self-Verification by the Language Model
- **AI Suggestion**: The assistant proposed asking the LLM to verify whether its own suggested intervention complied with the messaging policy.
- **Why It Was Rejected**:
  Section 5 of the Candidate Brief explicitly mandates: *"Verification: Use checks that can disagree with the decision step. Generated text is never treated as evidence or as approval."* Furthermore, `model_faults.jsonl` contained explicit injected model hallucinations claiming trial eligibility without billing events.
- **Our Resolution**: We created an independent, deterministic `ActionVerifier` firewall. The verifier audits raw state facts and hard-coded business rules (quiet hours, frequency caps, holdout flags) and has full authority to veto any model suggestion.

---

## 3. Engineering Conclusion

AI coding assistants are effective accelerators for standard syntax and boilerplate, but they default to optimistic, ungrounded patterns that fail real-world data constraints. Rigorous software engineering requires treating AI outputs with the same skepticism as untrusted user input: validating with independent checks, enforcing causal evaluation standards, and prioritizing deterministic safety over generative fluff.
