# Evidence Inventory — WorldConsistMem H4 LLM Reader Study

Generated: 2026-11-12  
Source data: `analysis/round2/private/item_scores.jsonl`, `evidence_packs.jsonl`  
Script: `scripts/rigorous_reanalysis.py`  
Status: FROZEN (no raw reviewer judgments were changed)

---

## 1. What exists

### 1.1 Full benchmark (paper Sections 3–4, H0–H3)

| Property | Value |
|----------|-------|
| Worlds | 102 |
| Bundles | 1,088 |
| Queries | 7,140 |
| Systems evaluated | B1 (Qwen-72B-RAG), B3 (Qwen-72B-no-RAG), B4 (Qwen-7B-RAG), H0 (LTKM), H3 (baseline) |
| Main metric | BCR (bundle consistency rate) + accuracy |
| Status | FROZEN; results in `results/scaled/FINAL_EXPERIMENT_STATUS.md` |

**Key results (H0–H3):** H0 (LTKM) achieves highest single-query accuracy (Acc=0.185) but BCR=0 for all systems including H0. Architecture superiority hypothesis REJECTED. The paper's main contribution is demonstrating BCR diverges from accuracy.

### 1.2 H4 LLM reader study (paper Section 5, this analysis)

| Property | Value |
|----------|-------|
| Worlds | 18 (subset of full benchmark) |
| Queries per arm | 150 |
| Arms | F0 (generic), F1 (schema-only), F2 (prev/event/next), F3 (bundled structured) |
| Total items | 600 (150 × 4) |
| Slots | CEO=30, conf=29, doc=34, emp=28, own=29 |
| Question status | unique=74, multi_candidate=42, version_unidentifiable=34 |
| Human evaluation | Round 1 (120 items, κ=0.336), Round 2 (50 items, κ=0.758) |
| Frozen outputs | `analysis/round2/private/f0_f3_frozen_outputs.jsonl` |

---

## 2. What each arm changes (controlled comparison)

| Arm | Prompt design | What changes vs prior arm |
|-----|---------------|---------------------------|
| F0 | Generic interface: "Answer the question." | Baseline; no format or temporal structure |
| F1 | Schema-only: specifies required output JSON keys | Adds output-format requirement only |
| F2 | Prev/event/next: provides temporal context as three-part structure | Adds temporal representation; keeps free output format |
| F3 | Bundled structured: full context bundle + strict schema | Adds both temporal representation AND output-format enforcement |

The F1 vs F3 comparison isolates temporal representation from format enforcement.  
The F2 vs F3 comparison isolates output-format enforcement from temporal representation.  
The F0 vs F2 comparison isolates temporal representation with free format.

---

## 3. What each metric measures

| Metric | What it captures | What it misses |
|--------|-----------------|----------------|
| Exact-match v2 (Scenario A) | Output-contract compliance AND semantic correctness | Correct content in non-canonical format |
| Semantic QA (Scenario B1) | Semantic correctness, format-agnostic | Does not distinguish latest vs earlier events on mc items |
| Semantic B1-nodoc | Semantic correctness excluding unanswerable items | Same |
| Matched-latest | Whether model selected the latest event (mc items) | Format compliance |
| BCR (full benchmark) | Cross-query consistency; whether Acc=correct persists across bundle | Not measured in H4 study |

---

## 4. Three distinct outcome types

The analysis separates:

**A. Output-contract compliance**: Does the model produce output in the required JSON schema?
- Measured by: exact_v2 − semantic_qa > 0 on unique items (the gap is 100% format)
- Arms F1 and F3 enforce output format; F0 and F2 do not.

**B. Semantic answer correctness**: Is the content of the answer correct?
- Measured by: semantic_qa on non-doc items (slot ≠ "doc")
- For unique items: all four arms score 74/74 (zero semantic errors)
- For multi-candidate items: "correct" means selected the latest event

**C. Temporal world-state consistency**: For multi-candidate questions, does the model identify the current state (latest event)?
- Measured by: matched_positions contains "latest"
- Requires the model to distinguish between multiple valid historical events

---

## 5. Supported claims

| Claim | Evidence | Strength |
|-------|----------|----------|
| BCR exposes failures that accuracy misses (main claim) | H0 BCR=0 at Acc=0.185; all systems BCR=0 | STRONG — directly demonstrated on full benchmark |
| Format-enforcing prompts improve exact-match compliance | F3 exact=74/74 unique vs F0 exact=10/74, F2 exact=12/74; Δ=0 on semantic | STRONG — effect is structural, not statistical |
| Temporal representation reduces stale-state errors | F2 stale=2/42, F3 stale=7/42 vs F0 stale=23/42, F1 stale=17/42 | MODERATE — consistent direction; sample n=42 |
| F3 exact-match improvement over F0/F2 on unique questions is format compliance | Semantic gap = 0 on unique (all arms 74/74) | STRONG — directly verified |
| Doc items (n=34) are unanswerable as stated | All 34 items have sufficiency label S2 (insufficient evidence) | STRONG — structural property of benchmark construction |

---

## 6. Contradicted claims

| Claim | Contradiction | Evidence |
|-------|---------------|----------|
| F3 improves semantic world-state tracking over F0/F2 | On unique questions (n=74), semantic gap F3−F0=0; on mc items F2 ≥ F3 semantically | B1-nodoc: F2=112/116 vs F3=109/116, McNemar p=0.508 |
| F2 semantic advantage over F3 (B1: 132 vs 113) is genuine | 17 of 23 F2 wins are on unanswerable doc items (S2); corrected: F2 wins 6, F3 wins 3 | Structural: all doc items S2 |
| Architecture superiority (H0–H3) | All systems BCR=0; architecture differences not detectable in consistency | FINAL_EXPERIMENT_STATUS.md |

---

## 7. Untested claims

- Whether BCR improvements transfer to real-world temporal datasets (only synthetic worlds tested)
- Cross-model replication (single LLM evaluated in H4 study)
- Whether temporal representation benefits scale with world complexity (18 worlds, limited variation)
- Performance with explicitly-stated "latest event" convention in question text

---

## 8. Data quality issues

| Issue | Scope | Impact |
|-------|-------|--------|
| Doc items (n=34) unanswerable | All 4 arms × 34 items = 136 items | F2 spurious semantic credits (+20); inflates F2 B1 score by ~17 pp |
| "Latest event" convention not stated in question text | 42 mc items | Reviewers correctly flagged as "ambiguous"; convention is implicit |
| Round 1 inter-rater reliability κ=0.336 | 120 items | Low agreement; not suitable for parametric claims without Round 2 |
| Round 2 κ=0.758 (50 items) | Cluster bootstrap CI [0.517, 0.957] | Wide CI; human evaluation well-powered for binary agreement, not fine-grained |
| 6 discordant items unresolved | No effect on any mechanical evaluation scenario | Does not affect B1/B1-nodoc/exact results |
