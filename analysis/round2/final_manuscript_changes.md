# Final Manuscript Changes

**Date:** 2026-11-12  
**Status:** Required changes before camera-ready  
**Priority:** REQUIRED (factually incorrect or missing) | RECOMMENDED (strengthening)

---

## Abstract

| # | Current claim | Corrected claim | Priority |
|---|---------------|-----------------|----------|
| A1 | "F3 achieves the highest accuracy" or similar | "On uniquely specified questions, all arms achieve equivalent semantic accuracy; F3's exact-match advantage is output-format compliance. F2 and F3 achieve comparable semantic accuracy on answerable questions (96.6% vs 94.0%)." | REQUIRED |
| A2 | No mention of BCR=0 caveat | Add: "BCR=0 at Acc=0.185 demonstrates that per-query accuracy and within-bundle consistency can diverge; this is the benchmark's primary contribution." | REQUIRED |
| A3 | No disclosure of evaluation dimensions | Add: "We distinguish three evaluation dimensions: output-contract compliance, semantic correctness, and temporal state consistency." | RECOMMENDED |

---

## Section 3 (Benchmark Design)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| B1 | "Latest event" convention not stated | Add: "For multi-candidate questions (CEO succession, ownership transfer), the gold answer uses the most recent event at world simulation end-time. This convention is not stated in question text." | REQUIRED |
| B2 | 34 document items (v1→v2) described without disclosure | Add: "34 document questions ask about v1→v2 transitions; evidence packs contain only later revisions without version identifiers. These items are unanswerable as stated and are excluded from the B1-nodoc analysis." | REQUIRED |
| B3 | F1 and F2 presented as pre-registered ablation arms | Revise: "F1 and F2 are exploratory post-result factorizations designed to identify components of the F3 advantage; the pre-registered arm comparison is F3 vs F0." | REQUIRED |

---

## Section 4 (Evaluation Protocol)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| C1 | M5 audit conclusion overstated | Revise to: "The M5 audit rules out wrapping as the sole source of format gains; the semantic scorer (B1) tests the broader question and confirms that all arms retrieve correct content on uniquely specified questions." | REQUIRED |
| C2 | Only exact-match reported as primary metric | Add B1-nodoc as primary semantic metric; demote exact-match to "originally reported" | REQUIRED |
| C3 | F2 event-unwrapping not disclosed | Add note: "F2's prev/event/next structure requires extracting the 'event' sub-object before scoring; this is applied consistently and does not affect other arms." | RECOMMENDED |

---

## Section 5 (H4 Results — Tables)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| D1 | Table shows only Scenario A (exact-match) | Add columns: B1 semantic (all), B1-nodoc (non-doc semantic) | REQUIRED |
| D2 | No breakdown by question type | Add rows for unique (n=74) and multi-candidate (n=42) | REQUIRED |
| D3 | F3 headline advantage not qualified | Add footnote: "On unique questions, the F3 semantic gap is 0 (Table X); the exact-match advantage is format compliance." | REQUIRED |
| D4 | Error taxonomy absent | Add error taxonomy table (CORRECT/FORMAT_ONLY/STALE_STATE/MC_INCOMPLETE/INSUF_EV per arm) | REQUIRED |
| D5 | Stale-state errors not reported | Add: paired McNemar results for F0 vs F2, F0 vs F3, F1 vs F2 | REQUIRED |

---

## Section 6 (Human Evaluation)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| E1 | Round 1 κ=0.336 presented without explanation | Add: "Low Round 1 reliability reflects a rubric gap on multi-candidate items; Round 2 corrects this with explicit Rule 8." | REQUIRED |
| E2 | 6 discordant items not addressed | Add: "Six discordant items remain pending independent adjudication. None affect mechanical evaluation results." | REQUIRED |
| E3 | Reviewer B intra-rater inconsistency | Disclose: B inconsistency across cases C22, C24, C29 for identical response content | RECOMMENDED |

---

## Section 7 (Limitations)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| F1 | No BCR=0 caveat | Add: "BCR=0 is consistent with expectations at Acc=0.185 under item independence; the finding demonstrates that the BCR and accuracy metrics diverge, not that systems lack any world-state knowledge." | REQUIRED |
| F2 | No disclosure of temporal interpretation limit | Add: "The mechanism underlying the stale-state reduction is not established; positional-cue effects in the evidence structure cannot be ruled out." | REQUIRED |
| F3 | Single LLM | Add: "The H4 reader study evaluates a single LLM; generalization across model families requires replication." | REQUIRED |
| F4 | CEO/own asymmetry in F1 | Add: "F1 (schema-only) avoids stale-state errors on ownership questions without temporal representation, suggesting that question-template effects contribute to the observed stale-state differences." | RECOMMENDED |

---

## Appendix

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| G1 | Pre-registration not documented | Include SHA-256 of evaluation protocol dated before Round 2 | RECOMMENDED |
| G2 | No "any documented event" convention results | Add Appendix X: results under alternative convention where any historically documented event is accepted | RECOMMENDED |
| G3 | No glossary | Add Table 0: glossary of exact-match v2, B1 semantic, B1-nodoc, stale-state error, FORMAT_ONLY, multi-candidate, version_unidentifiable | REQUIRED |

---

## Updated counts

| Priority | Count |
|----------|-------|
| REQUIRED | 20 |
| RECOMMENDED | 7 |
| **Total** | **27** |

---

## Claims to remove entirely

1. "F3 achieves the highest semantic accuracy" — remove
2. Any statement implying F1/F2 were pre-registered — revise
3. Any statement implying BCR=0 proves absence of a world model — revise
4. "F2 leads all arms semantically (88.0%)" without doc-item disclosure — remove or qualify
