# Manuscript Revision Checklist — WorldConsistMem

**Status:** Pre-revision. This checklist identifies every claim, table, figure, and
section in the submitted manuscript that requires revision based on Round 2
findings. Items are grouped by section in submission order.

Each item is marked: **REQUIRED** (factually incorrect or missing disclosed
limitation) or **RECOMMENDED** (would strengthen the paper).

---

## Abstract

| # | Claim as submitted | Required change | Priority |
|---|-------------------|-----------------|----------|
| A1 | F3 outperforms F0 by ~65 pp | Qualify: "under exact-match scoring, attributable to output-contract compliance on uniquely specified questions" | REQUIRED |
| A2 | (no mention of semantic scoring) | Add sentence: "Under schema-agnostic semantic scoring, all arms score 100% on uniquely specified questions; F2 leads on multi-candidate questions" | REQUIRED |

---

## Section 3 (Benchmark Design)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| B1 | "latest event" convention not stated | Add explicit disclosure: gold standard uses the most recent event when multiple events of the same type exist for the same entity | REQUIRED |
| B2 | Document question phrasing ("v1 to v2") | Add disclosure: 34 document items ask "v1 to v2" but evidence packs contain no version identifiers; these items are unanswerable as stated and are excluded from the B1-nodoc analysis | REQUIRED |
| B3 | Gold-support recall = 1 described as a property | Clarify this means gold answer can always be retrieved from evidence; it does not mean all questions have a unique answer | RECOMMENDED |

---

## Section 4 (Evaluation Protocol)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| C1 | Scorer v2 described without noting F2 event-unwrapping | Add note: F2 responses use prev/event/next format; the event sub-object is extracted before scoring | REQUIRED |
| C2 | M5 audit description ("0 format-only wins") | Clarify scope: M5 tested wrapping transformations; it did not test whether correct scalar answers for "When?" questions are penalised for missing unrequested fields. That gap is now closed by the semantic scorer (Scenario B1) | REQUIRED |
| C3 | No semantic evaluation | Add Scenarios B1 and B1-nodoc as main results; demote exact-match A to "originally reported" | REQUIRED |

---

## Section 4 (Results — Table 2: main results table)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| D1 | Table shows only Scenario A (exact-match) | Add columns for B1 (semantic) and B1-nodoc (semantic, excluding doc) | REQUIRED |
| D2 | No breakdown by question type | Add rows for unique (74 items) and multi-candidate (42 items) | REQUIRED |
| D3 | F3 headline advantage presented without qualification | Add footnote: "On unique questions, the semantic gap F3−F0 = 0 (Table X)" | REQUIRED |
| D4 | Published S1+S2 slice only | Show full 150-item results alongside S1+S2; note S2 items are unanswerable | REQUIRED |

---

## Section 4 (Results — any figures comparing arms)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| E1 | Bar chart or figure showing F3 vs F0 advantage | Add paired semantic bar; annotate that unique-question bars are equal under semantic scoring | REQUIRED |
| E2 | No display of sensitivity range | Add sensitivity envelope (E-lower to E-upper) for each arm | RECOMMENDED |

---

## Section 5 (M5 Audit)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| F1 | "0 format-only wins" claim | Reframe: M5 tested one specific hypothesis (wrapping); it cannot rule out that exact-match penalises semantically correct scalar answers. Report the semantic-scorer result as the definitive test | REQUIRED |
| F2 | Audit conclusion presented as ruling out schema confounding | Revise conclusion: M5 rules out wrapping as the sole explanation; schema confounding on a different axis (missing unrequested fields) is confirmed by Scenario C2-B1 | REQUIRED |

---

## Section 6 (Human Evaluation)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| G1 | Round 1 κ = 0.336 presented without comment on scale | Note that Round 2 revised the rubric to separate output-contract from semantic correctness; κ improved to 0.758 | REQUIRED |
| G2 | No mention of intra-rater inconsistency | Add: Reviewer B showed label inconsistency across 3 cases (C22, C24, C29) for responses with identical answer content, confirming that multi-candidate labelling is genuinely difficult | RECOMMENDED |
| G3 | 6 discordant items described as "pending" | Report the rule-based proposals and the fact that none affect mechanical evaluation scenarios | RECOMMENDED |

---

## Section 7 (Limitations)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| H1 | No disclosure of "latest event" convention | Add: the gold standard uses the latest event of a given type; this convention is implicit and not stated in question text. 42/150 items are ambiguous under any other convention | REQUIRED |
| H2 | No disclosure of document question defect | Add: 34/150 document items ask "v1 to v2" but evidence packs lack version identifiers; these items are excluded in B1-nodoc | REQUIRED |
| H3 | No cross-model comparison | Acknowledge as a limitation; note that benchmark structure is model-agnostic and cross-model replication is future work | RECOMMENDED |
| H4 | Single world-model setting | Note that benchmark uses fixed 18 worlds; generalization to larger or more diverse world sets has not been tested | RECOMMENDED |

---

## Appendix (Pre-registration / Protocol)

| # | Issue | Required change | Priority |
|---|-------|-----------------|----------|
| I1 | Protocol hash not shown in submission | Include SHA-256 of evaluation protocol document, dated before Round 2 annotation | RECOMMENDED |
| I2 | No description of private arm mapping | Add: 120-entry mapping verified against frozen output SHA-256s; mapping held separately from annotators | RECOMMENDED |

---

## Summary Counts

| Priority | Count |
|----------|-------|
| REQUIRED changes | 15 |
| RECOMMENDED changes | 7 |
| **Total** | **22** |

**Minimum viable revision:** items A1, A2, B1, B2, C2, C3, D1, D2, D3, F1, F2,
G1, H1, H2 (14 items) are needed before the paper's main claims are accurately
stated.

---

## Suggested Revised Main Finding (replace abstract claim)

> *"Under exact-match scoring, F3 outperforms F0 by 64.0 pp [57.8, 70.0] on the
> full 150-item set. This advantage has two components: (1) on 74 uniquely
> specified questions, the advantage is entirely output-contract compliance — all
> four arms retrieve the correct content under schema-agnostic semantic scoring
> (100% each); (2) on 42 multi-candidate questions, F2 and F3 achieve comparable
> semantic accuracy (90.5% and 83.3% respectively, p = 0.508). These findings
> qualify the original claims: structured prompting improves output format
> compliance and temporal event selection, not necessarily world-state retrieval."*
