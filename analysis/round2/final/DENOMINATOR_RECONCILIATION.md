# Denominator Reconciliation — B1-nodoc Population

**Date:** 2026-11-12  
**Status:** RESOLVED — single valid denominator is 116

---

## Item population

The H4 reader study contains 150 items × 4 arms = 600 records in `item_scores.jsonl`.

Each item belongs to exactly one slot. Slot distribution (verified from `item_scores.jsonl`):

| Slot | n | Sufficiency | question_status |
|------|---|-------------|-----------------|
| ceo | 30 | S1 | 20 multi_candidate, 10 unique |
| conf | 29 | S1 | 29 unique |
| doc | 34 | S2 | 34 version_unidentifiable |
| emp | 28 | S3 | 28 unique |
| own | 29 | S5 | 22 multi_candidate, 7 unique |
| **Total** | **150** | | |

No slot mismatches exist across arms (verified: every query_id has the same slot across all 4 arms).

---

## Why doc items are excluded

All 34 `doc` items are `question_status = version_unidentifiable` and `original_sufficiency_label = S2`. The evidence packs for these items contain only later document revisions without version identifiers; the gold answer asks about a v1→v2 transition that is unanswerable from the available evidence.

Any semantic credit on doc items is a scorer artifact (the prev/event/next structure of F2 produces false positives). F2 scores 20/34 semantically on doc items vs F3 at 3/34; this is a measurement artifact, not a genuine signal.

**Therefore:** the B1-nodoc evaluation population excludes all 34 doc items.

---

## B1-nodoc population: n = 116

**Definition:** All queries with `slot != 'doc'` and all 4 arms present.

| Fact | Value | Source |
|------|-------|--------|
| Total queries | 150 | item_scores.jsonl |
| Doc queries excluded | 34 | slot == 'doc' |
| Non-doc queries | 116 | 150 − 34 |
| Queries with all 4 arms present | 150/150 | verified |
| Paired B1-nodoc population | 116 | all 4 arms × 116 non-doc queries |

---

## The "125" figure

The task specification referenced "n = 125" appearing in a statistical audit output. This value does not appear in any project file for B1-nodoc:

- `final_statistical_audit_results.json` → `b1_nodoc.n = 116` for all arms
- `final_statistical_audit.md` → consistently uses n=116
- `analysis/round2/round2_results.json` → no B1-nodoc denominator of 125
- `analysis/round2/sensitivity_analysis.csv` → uses 150 or 140 (different populations), not 125

**Conclusion:** 125 does not correspond to any valid population definition in this dataset. The correct denominator for B1-nodoc is **116** in all final documents.

Possible origin of "125": sensitivity_analysis.csv row C1-A uses n=140 (excluding ambiguous questions); 150 − 25 = 125 would require excluding exactly 25 items but no coherent 25-item exclusion criterion exists in this dataset.

---

## All B1-nodoc claims use n = 116

| Document | Population label | n | Status |
|----------|-----------------|---|--------|
| final_statistical_audit.md | B1-nodoc | 116 | VERIFIED |
| final_claim_evidence_matrix.md | B1-nodoc, non-doc items | 116 | VERIFIED |
| final_reviewer_a.md | n/a (no B1-nodoc table) | — | — |
| final_reviewer_b.md | B1-nodoc, n=116 | 116 | VERIFIED |
| final_rebuttal_openreview.md | B1-nodoc | 116 (112/116, 109/116) | VERIFIED |

---

## Paired McNemar (F2 vs F3, B1-nodoc, n=116)

| Cell | Count |
|------|-------|
| Both correct (n11) | 106 |
| F2 only correct (n10) | 6 |
| F3 only correct (n01) | 3 |
| Neither correct (n00) | 1 |
| **Total (n)** | **116** |

Exact McNemar p = 0.507813  
RD = (6−3)/116 = +0.0259 (F2 − F3)  
95% CI: [−0.025, +0.076]

**Interpretation:** No significant difference (p=0.508). Cannot claim F3 semantic superiority.

---

## Regression test

`tests/test_round2_audit.py::test_b1_nodoc_denominator_is_116` verifies this count on every run.
