# ICLR 2027 Rebuttal — WorldConsistMem (Submission 49130)

**Canonical draft (PR #10). Not submitted to OpenReview.** This is the only rebuttal draft to paste; the others are listed as superseded in `analysis/round2/STALE_DRAFTS.md`. Every number here is traced to a source in `analysis/round2/REBUTTAL_NUMBER_AUDIT.md`. Check the current OpenReview length limit before posting.

We thank reviewers Rkeo, vfz3, and EdSa. We distinguish exact-match tuple accuracy, question-aligned semantic correctness, and cross-query consistency, and we narrow our interpretation accordingly. The H4 findings are limited to one model snapshot (gpt-4.1-2025-04-14), 18 worlds, and 150 questions (600 outputs).

## To vfz3: schema compliance and label stability

Schema compliance explains the exact-match gap on the 74 structurally unique questions. We re-scored all 600 outputs (150 questions × 4 arms) with the schema-agnostic, question-aligned rule B1. On these 74 questions every arm is semantically correct in 74/74 cases, while exact match is F0 10/74, F1 74/74, F2 12/74, and F3 74/74. The F3–F0 exact-match gap of 64 items on this subset is therefore an output-format effect. We will not describe it as a semantic-reasoning gain.

On the 42 multi-candidate questions, the question wording does not state the latest-event convention that the gold labels use. Under that convention, stale-state errors (matching an earlier event but not the latest) are F0 23/42, F1 17/42, F2 2/42, and F3 7/42. Latest-event selection is a separate count: F0 19/42, F1 16/42, F2 38/42, and F3 35/42. For stale-state errors, 10 of 10 non-tied worlds favour F2 over F0, none favour F0, and two worlds tie (one-sided exact sign-test p = 0.00098; 12 worlds contain these items). For latest-event selection, the item-level paired F2−F0 difference is +45.2 pp (item-level 95% CI [+27.5, +62.9]; exact McNemar p = 6.6×10⁻⁵). That item-level test treats clustered items as independent and is descriptive only.

These results are an association under an implicit convention, not evidence of temporal reasoning. F1 shows strong question-template asymmetry: 0/22 stale on ownership questions and 17/20 stale on CEO questions. Under a sensitivity rule that credits any single documented candidate event, semantic correctness is F0 144/150, F1 149/150, F2 150/150, and F3 150/150.

Round 2 re-rated the 50 Round 1 responses on which the two reviewers disagreed, under a revised rubric that judges the answer to the asked question rather than the output schema. Reviewers agreed on 44/50 (κ = 0.758; case-cluster bootstrap 95% CI [0.517, 0.957] over 20 cases). Six disagreements remain unresolved. Round 2 rated semantic correctness only: the evidence-sufficiency fields and reviewer notes were not completed. Because the sample was selected on Round 1 disagreement, this is not a before–after reliability comparison, and we do not use Round 1's κ = 0.336 as a comparator. The κ is agreement on that selected subset under the revised rubric. It is not independent validation of every gold label.

The 34 document-version items cannot be answered from the supplied evidence packs, which contain no version identifiers. We report them separately and do not count them as reasoning failures.

## To EdSa: semantic grading, document items, and generalization

B1 is a deterministic rule-based scorer applied to all 600 outputs. It is not human grading of all outputs. The human check covers only the 50 Round 2 responses described above, with six unresolved disagreements. We therefore present semantic results as sensitivity analyses.

**B1-nodoc (sensitivity analysis).** After excluding the 34 document items, semantic correctness (n = 116) is F0 87/116 (75.0%), F1 90/116 (77.6%), F2 112/116 (96.6%), and F3 109/116 (94.0%). The document exclusion was decided after Round 2 identified that these items lack version identifiers, so B1-nodoc is a post hoc subset. The F3–F0 contrast on B1-nodoc is +19.0 pp (world-cluster bootstrap 95% CI [+9.6, +29.1], 18 worlds). Its item-level exact McNemar p = 3×10⁻⁶ ignores within-world clustering and multiple comparisons. All arms are 74/74 on the uniquely specified questions, so this contrast comes entirely from the 42 multi-candidate questions and depends on the latest-event convention. We report it as a convention-dependent sensitivity result, not as evidence of general semantic reasoning. On all 150 items under B1, the F3–F0 contrast is +14.7 pp (world-cluster 95% CI [+6.2, +22.9]).

**F2 versus F3 on B1-nodoc.** F2 − F3 = +2.6 pp. The world-cluster bootstrap 95% CI is [−3.2, +9.0] (18 worlds). The item-level paired 95% CI is [−2.5, +7.6], with exact item-level McNemar p = 0.508. The evidence does not establish a difference.

**Document items.** Under full B1 scoring, F2 receives 20 credits on the 34 document items, against 4 for F0, 0 for F1, and 4 for F3. These are scoring artifacts on unanswerable items. We have not established their mechanism; the prev/event/next format is a hypothesis.

F0 is a generic response interface. We do not treat it as a representative production-memory baseline. The contrast tested is interface-conditioned structured accuracy, not generic memory-system capability.

All results are for one model snapshot, gpt-4.1-2025-04-14. Cross-model replication has not been run, and we make no generality claim. We will remove the claim that F3 has the highest semantic accuracy.

## To Rkeo: leakage, analysis choices, scorer changes, and the temporal-control run

**Leakage.** We have not located a forensic leakage audit or a preregistration hash in the repository, so we do not claim that any leakage audit passed. The Round 2 item-level outputs are held in a git-ignored private snapshot, so the four-arm analyses cannot be reproduced from the public repository. The committed per-item tables (`temporal_state_analysis.csv`, `case_level_error_analysis.csv`) and the verification script reproduce the reported counts. We will add a leakage audit to the supplement only after it has been re-run and checked.

**Analysis timeline.** F3 versus F0 is the comparison designated as primary. F1 and F2 were designed after the F3 results and are exploratory post-result factorizations. We cannot verify from repository artifacts when the F3–F0 designation was fixed, so we do not describe it as preregistered. We will not describe the four arms as a prespecified 2×2 design.

**Scorer changes.** Scorer v2 (alias normalization) replaced v1. Under v1, exact-match F0 scores 0/150; under v2 it scores 13/150 (`sensitivity_analysis.csv`, rows A-v1 and A). The bare-JSON runner was repaired. Both scorer versions are reported. These changes concern exact-match scoring, not semantic grading.

**Sensitivity analyses.** `sensitivity_analysis.csv` reports exact match under both scorers, exclusion of ambiguous and non-unique items, bounds on the latest-event convention, and the B1-nodoc analysis. We disclose results that run against our original framing: F2's credits on document items; F2 at least as good as F3 on temporal selection; and F1 avoiding stale ownership answers without any temporal representation.

**BCR.** For system H0 (accuracy 0.185) with 6.56 queries per bundle, an independent-error baseline predicts about 0.017 consistent bundles out of 1,088, so BCR = 0 is unsurprising under that baseline. We do not use BCR = 0 as evidence that models lack an internal world model. We treat BCR as a complementary joint-success measure.

**Post-review temporal-control experiment (exploratory; separate from the H4 study).** We generated 100 new worlds (200 latest-state questions, 800 prompts) and ran local inference with `mlx-community/Qwen2.5-3B-Instruct-4bit`, revision `4f83f8f146fdf28b512a06562b671d7af4fab457`, greedy decoding, and a 48-token limit. This is a different model from the H4 study. The prespecified primary contrast, explicit temporal edges (B) minus a neutral field/value ledger (C), is −36.0 pp (world-bootstrap 95% CI [−40.5, −31.5]; two-sided sign-flip p = 0.000010). Latest-state accuracy is 0.5% (1/200) for B and 36.5% (73/200) for C. Format validity was 200/200 in every condition. All 800 scored rows were recalculated from raw outputs with the frozen scorer and show zero mismatches. The manifest records only five scorer-validation examples, and we do not document the arm-blinded normalization check described in the protocol as completed. B prompts averaged 28,228 tokens and C prompts 13,577, so the condition is confounded with input length (about 2.1×). An across-world length association (Pearson r = −0.13, permutation p = 0.20) does not adjust for this imbalance and cannot separate length from representation. This is a negative result for the explicit-edge implementation tested. It is not a replication of the H4 findings, and it does not isolate temporal-edge effects.

**Presentation.** We will revise terminology, label F1 and F2 as exploratory, and separate exact-match, semantic, and temporal-selection results throughout. No manuscript file was revised in this audit; these revisions are planned and not yet made.
