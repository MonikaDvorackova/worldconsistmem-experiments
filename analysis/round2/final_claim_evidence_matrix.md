# Final Claim–Evidence Matrix — WorldConsistMem

**Date:** 2026-11-12  
**Purpose:** Every claim in the final rebuttal traces to a specific data source, calculation, and limitation.

---

## Claim 1: BCR exposes consistency failures that accuracy misses

**Claim text:** "The BCR metric reveals that no evaluated system achieves full within-bundle consistency, despite non-trivial per-query accuracy (18.5% for H0)."

| Item | Value |
|------|-------|
| Data source | `results/scaled/FINAL_EXPERIMENT_STATUS.md`, `outputs/scaled/run2/` |
| Sample | 1088 bundles, 7140 queries, 4 systems (B1, B3, B4, H0) |
| Calculation | BCR = fraction of bundles where all consistency constraints pass |
| Result | BCR=0 for all systems; H0 Acc=0.185, BCR=0 |
| Uncertainty | None — BCR=0 is not a statistical estimate |
| Limitation | BCR=0 is not surprising at Acc=0.185 (expected ~0 under independence). The finding is a demonstration of the metric property, not proof of a specific cognitive deficit. |
| Rebuttal sentence | "BCR=0 at Acc=18.5% demonstrates that the gap metric captures a form of failure — within-bundle inconsistency — that per-query accuracy misses entirely; accurate individual answers coexist with inconsistent paired answers about the same entity." |
| Status | VERIFIED |

---

## Claim 2: Exact-match gap on unique questions is output-contract compliance

**Claim text:** "On 74 uniquely specified questions, all four arms retrieve the correct content (74/74 semantically). The entire F3−F0 exact-match difference (+64 items) reflects output-format compliance."

| Item | Value |
|------|-------|
| Data source | `analysis/round2/private/item_scores.jsonl` |
| Sample | 74 unique questions × 4 arms = 296 items |
| Calculation | Exact-match v2 and semantic_qa counts; verified F3-F0 diff |
| Result | Exact: F0=10, F1=74, F2=12, F3=74. Semantic: all 74/74. Diff: exact +64, semantic 0. |
| Uncertainty | None — structural comparison |
| Limitation | F0 exact=10 (not 0) because CEO-unique questions happen to elicit correct JSON format from F0. This is a small exception but does not affect the main claim. |
| Rebuttal sentence | "On 74 uniquely specified questions, the semantic gap F3−F0 is exactly 0 (74/74 for both); the exact-match gap (+64 items) is entirely attributable to output-format compliance." |
| Status | VERIFIED |

---

## Claim 3: Temporal representation is associated with fewer stale-state errors

**Claim text:** "Temporal representation is associated with substantially fewer stale-state errors (selecting an earlier historical event instead of the current state): F0: 23/42 (55%), F1: 17/42 (40%), F2: 2/42 (5%), F3: 7/42 (17%)."

| Item | Value |
|------|-------|
| Data source | `analysis/round2/private/item_scores.jsonl` |
| Sample | 42 multi-candidate items × 4 arms |
| Calculation | STALE_STATE = `matched_positions` contains 'earliest' but not 'latest' |
| Result | F0=23, F1=17, F2=2, F3=7 |
| Paired effects | F0 vs F2: RD=+0.452 [+0.275, +0.629], p=0.0001; F0 vs F3: RD=+0.381 [+0.173, +0.589], p=0.0025; F1 vs F2: RD=+0.524 [+0.373, +0.675], p<0.0001; F2 vs F3: RD=−0.071 [−0.210, +0.067], p=0.508 |
| Uncertainty | 42 items in 12 worlds; CI is approximate under item-level independence. World-level sign test confirms direction (p=0.001). |
| Limitation | (a) F1 asymmetry: F1/CEO-mc stale=85%, F1/own-mc stale=0%. The improvement from F1→F2 is entirely on CEO questions. For own-mc, schema-only (F1) already avoids stale-state. (b) F2 vs F3 is not significant (p=0.508) — both temporal-representation arms perform comparably. (c) Mechanism is unidentified: could be positional-cue exploitation rather than temporal reasoning. |
| Rebuttal sentence | "Including temporal structure in evidence presentation is associated with substantially fewer stale-state CEO errors (F2: 10%, F3: 35% vs F1: 85%, F0: 55%; McNemar p<0.001 for F1 vs F2). F2 and F3 perform comparably on temporal accuracy (McNemar p=0.508)." |
| Status | VERIFIED with F1-asymmetry qualification |

---

## Claim 4: F2 and F3 are statistically indistinguishable on semantic accuracy

**Claim text:** "The available evidence does not establish a semantic accuracy difference between F2 and F3 (B1-nodoc: 96.6% vs 94.0%, McNemar p=0.508)."

| Item | Value |
|------|-------|
| Data source | `analysis/round2/private/item_scores.jsonl` (non-doc items only) |
| Sample | 116 non-doc items × 2 arms |
| Calculation | Paired McNemar on `semantic_qa`; excludes 34 doc items (all S2 insufficient evidence) |
| Result | F2=112/116, F3=109/116; paired table: both=106, F2-only=6, F3-only=3, neither=1; RD=+0.026 [−0.025, +0.076]; p=0.508 |
| Uncertainty | n=116, 9 discordant pairs. The non-significance does not establish equivalence. |
| Limitation | Small discordant cell (n=9). The 6 F2-only wins cluster in 4 worlds (sm0135–sm0138) due to CEO-mc items — effective independent observations may be fewer than 6. |
| Rebuttal sentence | "After excluding the 34 unanswerable doc items, F2 and F3 show no significant semantic accuracy difference (112/116 vs 109/116; McNemar p=0.508; RD=+2.6pp [−2.5, +7.6])." |
| Status | VERIFIED — wording corrected to avoid equivalence claim |

---

## Claim 5: F2 spurious semantic credits are scorer artifacts on unanswerable items

**Claim text:** "F2 receives 20 spurious semantic credits on 34 document items that are unanswerable as stated (all 34 have S2 insufficient evidence). After exclusion, the apparent F2 advantage under B1 disappears."

| Item | Value |
|------|-------|
| Data source | `analysis/round2/private/item_scores.jsonl`, `evidence_packs.jsonl` |
| Sample | 34 doc items × 4 arms |
| Calculation | Spurious = `semantic_qa=True` on `question_status='version_unidentifiable'` |
| Result | F0=4, F1=0, F2=20, F3=4 spurious doc credits. Paired F2 vs F3 on doc: F2-only=17, F3-only=1, both=3, neither=13. |
| Uncertainty | None — structural property of benchmark |
| Limitation | "Unanswerable" is based on `original_sufficiency_label=S2`. The scorer artifact (timestamp extraction matching gold time field) is specific to F2's prev/event/next format. |
| Rebuttal sentence | "F2's B1 advantage (132/150 vs F3's 113/150) is entirely explained by 20 spurious credits on 34 doc items with insufficient evidence; after correction, the difference is 3 items (p=0.508)." |
| Status | VERIFIED, reconciliation complete |

---

## Claim 6: Round 2 κ=0.758 (reliable annotation)

**Claim text:** "Round 2 achieved κ=0.758 (44/50 agreement) with bootstrap CI [0.517, 0.957]."

| Item | Value |
|------|-------|
| Data source | `human_evaluation/reviewer_1/WCM_COMPLETED_ANNOTATION.csv`, reviewer_2 CSV |
| Sample | 50 items (20 questions × up to 3 responses each) |
| Calculation | Cohen's κ via `scripts/adjudication_sensitivity.py:cohen_kappa_2rater()` |
| Result | Agreement=44/50 (88.0%), κ=0.758065, CI=[0.517, 0.957] (cluster bootstrap, n=10,000) |
| Uncertainty | Wide CI reflects 50-item sample. McNemar p=0.219 (no systematic bias between reviewers). |
| Limitation | 6 discordant items unresolved; Reviewer B shows intra-rater inconsistency across cases C22, C24, C29. These do not affect mechanical scores. |
| Rebuttal sentence | "Round 2 inter-rater reliability: κ=0.758 (44/50, 88.0% agreement; bootstrap CI [0.517, 0.957])." |
| Status | VERIFIED |

---

## Claim 7: Leakage audit PASS

**Claim text:** "Forensic leakage audit PASS on all 26 checks."

| Item | Value |
|------|-------|
| Data source | `forensic/FORENSIC_AUDIT.md` with SHA-256 chain |
| Sample | 26 checks across prompt, arm mapping, timestamp, training corpus |
| Calculation | Per `forensic/FORENSIC_AUDIT.md` |
| Result | All 26 PASS |
| Limitation | Cannot rule out training corpus inclusion of synthetic world data entirely. World simulation is seeded and reproducible; probability of training data inclusion is assessed as negligible. |
| Rebuttal sentence | "Forensic audit PASS: 26/26 checks pass, confirming no gold-answer leakage into prompts, frozen outputs predating annotation, and private arm mapping held separately." |
| Status | VERIFIED (taken from existing forensic archive, not re-run) |

---

## Claims that cannot be made

| Claim | Reason |
|-------|--------|
| "F3 achieves higher semantic accuracy than F2" | Contradicted: p=0.508, corrected comparison |
| "F2/F3 demonstrate temporal world-state reasoning" | Experiment does not distinguish temporal reasoning from positional-cue effects |
| "BCR=0 proves lack of internal world model" | BCR=0 is expected at Acc=0.185 under independence |
| "Architecture superiority (H0 > B1/B3/B4 on consistency)" | All BCR=0; REJECTED in FINAL_EXPERIMENT_STATUS.md |
| "Round 1 κ=0.336 is a valid reliability estimate" | Known rubric gap identified; superseded by Round 2 |
| "Temporal representation causes stale-state reduction" | Association confirmed; causation not established |
| "F1 and F2 were pre-registered ablation arms" | They were post-result factorizations (per working draft) |
| "F2 and F3 are equivalent in semantic accuracy" | Non-significance ≠ equivalence; correct phrasing is "no significant difference" |
