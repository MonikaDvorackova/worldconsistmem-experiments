# Error Taxonomy — WorldConsistMem H4 LLM Reader Study

Generated: 2026-11-12  
Source: `scripts/rigorous_reanalysis.py` → `analysis/round2/case_level_error_analysis.csv`

---

## Error types

Six mutually exclusive error categories classify every (arm, item) pair. Categories are assigned in priority order: CORRECT first, then format vs. content vs. evidence errors.

### CORRECT
Exact-match v2 passes. The model produced the correct output-contract format and the correct semantic content. Count toward the paper's headline metric.

### FORMAT_ONLY
Exact-match fails but semantic QA passes. The model retrieved the correct answer but produced it in a format that does not match the expected JSON schema. This error type is entirely attributable to output-format design — it does not reflect a failure to identify the correct world state.

**Key property:** On unique questions (n=74), FORMAT_ONLY accounts for 100% of errors for F0 and F2. All arms correctly answer unique questions semantically; the difference is output format.

### STALE_STATE
Multi-candidate item. The model selected an earlier historical event rather than the current (latest) event. This is a genuine temporal world-state error: the model's answer was historically true but not the current state.

**Mechanism:** Evidence packs for multi-candidate CEO and ownership questions contain multiple valid events (e.g., three successive CEO changes). The gold standard uses the latest transition. A model that selects an earlier transition gives a stale-state answer.

**Note:** The question text does not explicitly state "most recent." This is an implicit convention established by benchmark construction. The stale-state label applies relative to this convention.

### MC_INCOMPLETE
Multi-candidate item. The model did not match either the latest OR the earliest event. This includes: (a) abstaining from answering, (b) producing multiple events in a list, (c) hallucinating an event not present in the evidence pack.

### INSUF_EV_FAIL
Document item (slot=doc, question_status=version_unidentifiable). The model gave no semantic credit. All 34 doc items are S2 (insufficient evidence): the question asks about a v1→v2 document revision, but the evidence packs contain only later revisions (v2→v3, etc.) without version identifiers. The correct response is to abstain or indicate insufficient evidence.

**INSUF_EV_FAIL is the correct behavior on doc items.**

### INSUF_EV_SPURIOUS
Document item. The semantic scorer gave credit. This is a false positive: the scorer coincidentally matches a timestamp extracted from the doc evidence to the gold "time" field, but the item is unanswerable as stated.

**F2 has 20 spurious doc credits vs 4 for F0/F3 and 0 for F1.** This is a scorer artifact on the F2 format (prev/event/next structure exposes timestamps that match the gold time field more frequently).

---

## Error counts by arm

| Error Type | F0 | F1 | F2 | F3 |
|-----------|---:|---:|---:|---:|
| CORRECT | 13 | 90 | 39 | 109 |
| FORMAT_ONLY | 74 | 0 | 73 | 0 |
| STALE_STATE | 23 | 17 | 2 | 7 |
| MC_INCOMPLETE | 6 | 9 | 2 | 0 |
| INSUF_EV_FAIL | 30 | 34 | 14 | 30 |
| INSUF_EV_SPURIOUS | 4 | 0 | 20 | 4 |
| **Total** | **150** | **150** | **150** | **150** |

---

## Diagnostic reading

**F3 vs F0 exact-match gap (+96 items):**
- 74 FORMAT_ONLY errors eliminated (output-format enforcement)
- 16 STALE_STATE errors eliminated (temporal representation)
- 6 MC_INCOMPLETE errors eliminated
- 20 INSUF_EV_SPURIOUS → 4 for F3 (F3 correctly refuses doc items)
- These are four distinct mechanisms; the headline "+96" conflates them.

**F3 vs F2 exact-match gap (+70 items):**
- 73 FORMAT_ONLY errors in F2 vs 0 in F3 (the dominant driver)
- F2 stale-state=2 vs F3 stale-state=7 (F2 is BETTER on temporal selection)
- Net: F3's exact-match advantage over F2 comes entirely from format compliance, not temporal accuracy.

**F2 vs F1 semantic gap:**
- F2 B1-nodoc=112/116 (96.6%) vs F1=90/116 (77.6%), Δ=+22 items
- Entirely on multi-candidate items: F2 selects latest 38/42 times vs F1's 16/42
- This is the genuine temporal representation signal: temporal context (prev/event/next) reduces stale-state errors from 17 (F1) to 2 (F2).

**F2 vs F0 semantic gap:**
- F2 B1-nodoc=112/116 vs F0=87/116, Δ=+25 items
- F0 stale-state=23/42 mc vs F2=2/42
- Same temporal representation signal as F2 vs F1.

**Zero semantic errors on unique questions:**
No arm ever retrieves incorrect content on a uniquely specified question (where the evidence pack contains exactly one candidate event). All errors on unique questions are FORMAT_ONLY. This validates that the benchmark correctly constructs unambiguous questions when sufficient evidence is provided.

---

## Error interpretation for reviewers

Reviewers Rkeo, vfz3, and EdSa each raised concerns that map to this taxonomy:

| Reviewer concern | Taxonomy mapping |
|-----------------|------------------|
| vfz3: "schema compliance rather than semantic improvement" | FORMAT_ONLY errors account for F3 headline gain on unique items |
| EdSa: "semantic grading needed" | FORMAT_ONLY errors correctly resolved by B1 semantic scorer |
| EdSa: "latest event convention undisclosed" | STALE_STATE error definition depends on this convention |
| Rkeo: "analyst degrees of freedom" | INSUF_EV_SPURIOUS reveals a scorer artifact that must be disclosed |
