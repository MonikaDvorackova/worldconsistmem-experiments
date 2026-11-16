# ICLR 2027 Rebuttal — WorldConsistMem (Submission 49130)

**Canonical draft (PR #10). Not submitted to OpenReview.** This file contains the three reviewer comments only. Word counts include headings. Verify each comment against the full OpenReview review text before posting; that text is not in the repository, so the concerns quoted here come from the authors' response drafts. Numbers are traced in `analysis/round2/REBUTTAL_NUMBER_AUDIT.md`. The Qwen temporal-control result is not included in any reviewer reply because no quoted reviewer concern asks about it; it is documented in the audit file.

---

**To vfz3: schema compliance and label stability**

**Concern and answer.** The concern is that exact-match gains reflect schema compliance rather than semantic improvement. Yes. On the 74 uniquely specified questions, all four arms are semantically correct in 74/74 cases under the schema-agnostic, question-aligned rule B1. Exact match is F0 10/74, F1 74/74, F2 12/74, F3 74/74. The 64-item F3–F0 gap on this subset is therefore an output-format effect, not a semantic gain.

**Multi-candidate questions (42, 12 worlds).** Stale-state errors (matching an earlier event but not the latest) are F0 23/42, F1 17/42, F2 2/42, F3 7/42. The question wording does not state the latest-event convention the gold labels use. Under that convention, 10 of 10 non-tied worlds favour F2 over F0, none favour F0, and two tie (one-sided exact sign-test p = 0.00098). This is an association under an implicit convention, not evidence of temporal reasoning.

**Label stability.** Round 2 re-rated the 50 Round 1 responses on which the two reviewers disagreed, under a revised rubric that judges the answer to the asked question. Reviewers agreed on 44/50 (kappa = 0.758; case-cluster bootstrap 95% CI [0.517, 0.957] over 20 cases); six remain unresolved. Round 2 rated semantic correctness only; evidence-sufficiency fields were not completed. Because the sample was selected on Round 1 disagreement, this is not a before-after reliability comparison.

**Document items.** The 34 document-version items cannot be answered from the evidence packs, which contain no version identifiers. We report them separately, not as reasoning failures.

---

**To EdSa: semantic grading, document items, and generalization**

**Concern and answer.** The concern is that semantic grading is not yet established. Our semantic results are sensitivity analyses. B1 is a deterministic rule-based scorer applied to all 600 outputs. Human review covered only 50 Round 2 responses, with six unresolved disagreements.

**B1-nodoc (sensitivity; n = 116).** We excluded the 34 document items after Round 2 showed they lack version identifiers, so this subset was chosen post hoc. Semantic correctness is F0 87/116, F1 90/116, F2 112/116, F3 109/116. The prespecified F3–F0 contrast is +19.0 pp (world-cluster bootstrap 95% CI [+9.6, +29.1], 18 worlds). Its item-level exact McNemar p = 3x10^-6 ignores clustering and multiple comparisons. All arms are 74/74 on uniquely specified items, so the contrast comes entirely from the 42 multi-candidate questions and depends on the latest-event convention. It is convention-dependent sensitivity evidence, not evidence of general semantic reasoning. On all 150 items under B1 the contrast is +14.7 pp (CI [+6.2, +22.9]).

**F2 versus F3 (B1-nodoc).** F2 minus F3 is +2.6 pp: world-cluster CI [-3.2, +9.0]; item-level paired CI [-2.5, +7.6]; exact McNemar p = 0.508. The evidence does not establish a difference.

**Document items.** Under full B1 scoring F2 receives 20 credits on these items, F0 and F3 four each, F1 none. We have not established the mechanism.

**Baseline and generalization.** F0 is a generic response interface, not a representative production-memory baseline. All results are for one model snapshot (gpt-4.1-2025-04-14); cross-model replication has not been run. We will remove the claim that F3 has the highest semantic accuracy.

---

**To Rkeo: leakage, analysis choices, scorer changes, and an exploratory follow-up**

**Concern and answer.** The concern is leakage, analysis degrees of freedom, and scorer changes. **Leakage.** We have not located a forensic leakage audit or a preregistration hash, so we do not claim that a leakage audit passed. We will add one to the supplement only after it is re-run and checked. Round 2 item-level outputs are in a git-ignored private snapshot; the committed per-item tables reproduce the reported counts.

**Analysis timeline.** F3 versus F0 is the primary comparison. F1 and F2 were designed after the F3 results and are exploratory. We cannot verify when the F3–F0 designation was fixed, so we do not call it preregistered, and we will not describe the arms as a prespecified 2x2 design.

**Scorer.** Scorer v2 (alias normalization) replaced v1. Exact-match F0 scores 0/150 under v1 and 13/150 under v2. Both are reported; the change concerns exact match, not semantic grading.

**BCR.** At system H0 accuracy 0.185 and 6.56 queries per bundle, independent errors predict about 0.017 consistent bundles out of 1,088. BCR = 0 is therefore unsurprising and is not evidence that models lack an internal world model.

**Presentation.** We will label F1 and F2 as exploratory and separate exact-match, semantic, and temporal-selection results.
