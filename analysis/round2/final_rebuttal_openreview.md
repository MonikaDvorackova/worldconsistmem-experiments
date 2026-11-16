# ICLR 2027 Rebuttal — WorldConsistMem (Submission 49130)

**Canonical draft (PR #10). Not submitted to OpenReview.** This file contains the three reviewer comments only, revised against the reviewer texts supplied for this round. Word counts include headings. Verify each comment against the full OpenReview review text before posting; that text is not in the repository, so the concerns quoted here come from the authors' response drafts. Numbers are traced in `analysis/round2/REBUTTAL_NUMBER_AUDIT.md`. The Qwen temporal-control result is not included in any reviewer reply because no quoted reviewer concern asks about it; it is documented in the audit file.

---

**To vfz3: schema compliance, the 77/150 issue, and the scorer/parser question**

Schema compliance: on the 74 uniquely specified questions, all four arms are semantically correct in 74/74 cases under the schema-agnostic, question-aligned rule B1. Exact match is F0 10/74, F1 74/74, F2 12/74, F3 74/74. F0 was prompted with schema=transition_tuple, but that prompt did not enumerate every gold field. Its exact-match failures on these items therefore reflect output format, since its answers are semantically correct. The 64-item F3-F0 exact-match gap on this subset is an output-format effect, not a semantic gain.

Multi-candidate questions (42): the wording does not state the latest-event convention the gold labels use. Stale-state errors are F0 23/42, F1 17/42, F2 2/42, F3 7/42. Under that convention, 10 of 10 non-tied worlds favour F2 over F0, none favour F0, and two tie (one-sided exact sign-test p = 0.00098). This is an association under an implicit convention, not evidence of temporal reasoning.

The 77/150 figure: we withdraw it as unreproducible. No repository table supports it. Round 2 did not rate evidence sufficiency. It re-rated semantic correctness for the 50 Round 1 disagreements: 44/50 agreement (kappa = 0.758; case-cluster bootstrap 95% CI [0.517, 0.957] over 20 cases), with six unresolved. Because the sample was selected on disagreement, this is not a before-after reliability comparison.

The 34 document-version items are the original S2 items. They cannot be answered from the evidence packs, which contain no version identifiers, so we report them separately and do not count them as reasoning failures.

Scorer/parser: under the v1 scorer (strict keys), exact match is F0 0/150, F1 86/150, F2 7/150, F3 109/150. The original online parser marked all 150 F3 outputs malformed, because they are bare JSON without the wrapper. The 109/150 figure comes from offline rescoring with a corrected parser, not from the online run.

---

**To EdSa: sensitivity analyses, the latest-event convention, and generalization**

B1 is a deterministic rule-based scorer applied to all 600 outputs. We report B1 and B1-nodoc as sensitivity analyses. Human review covered 50 Round 2 responses, with six unresolved disagreements.

Latest-event convention: the question wording does not state it, and the gold labels use the most recent event at world end-time. Every comparison on the 42 multi-candidate questions depends on it.

B1-nodoc (n = 116) excludes the 34 document items. These are the original S2 items and are unanswerable from the evidence packs, which contain no version identifiers. The exclusion was decided after Round 2, so this subset is post hoc. Semantic correctness is F0 87/116, F1 90/116, F2 112/116, F3 109/116. The F3-F0 contrast is +19.0 pp (world-cluster bootstrap 95% CI [+9.6, +29.1], 18 worlds). Its item-level exact McNemar p = 3x10^-6 ignores clustering and multiple comparisons. All arms are 74/74 on uniquely specified items, so the contrast comes entirely from the multi-candidate questions and depends on the convention. On all 150 items under B1, the contrast is +14.7 pp (world-cluster bootstrap 95% CI [+6.2, +22.9]).

F2 minus F3 on B1-nodoc is +2.6 pp (world-cluster CI [-3.2, +9.0]; item-level paired CI [-2.5, +7.6]; exact McNemar p = 0.508). The evidence does not establish a difference.

Generalization: a full F0-F3 replication on another model was not run. The separate Qwen2.5-3B local B-C control is not that replication. It is a negative result for the explicit-edge condition, confounded with prompt length, and it does not support generalization of the F0-F3 findings.

Baseline: F0 is a generic response interface, not a representative production-memory baseline. The contrast tested is interface-conditioned structured accuracy, not generic memory-system capability.

We will remove the claim that F3 has the highest semantic accuracy.

---

**To Rkeo: leakage, post-result arms, scorer/parser, and typography**

Leakage: no repository artifact substantiates a 26-check forensic audit, so we do not cite one, and nothing here rules out leakage in subtype-schema selection. What the artifacts do show: the response-to-arm mapping and the evidence blocks were checked in a git-ignored private snapshot, and evaluation_report.md reports identical evidence blocks for all 150 queries. That snapshot is not public, so the check cannot be reproduced from this repository.

Blinding: the arm can often be guessed from the answer format (F3 is bare JSON; F2 is prev/event/next), so human review was not blind to arm in practice.

Post-result arms: F1 and F2 were designed after observing F3 and are exploratory post-result factorizations. F3 versus F0 is the comparison designated primary. We cannot verify when that designation was fixed, so we do not call it preregistered.

Scorer/parser: under the v1 scorer (strict keys), exact match is F0 0/150, F1 86/150, F2 7/150, F3 109/150. The original online parser marked all 150 F3 outputs malformed, because they are bare JSON without the wrapper. The 109/150 figure comes from offline rescoring with a corrected parser; the online run and the offline rescoring are different measurements.

Typography: we commit to correcting the PDF's typography, figure labelling, float placement, and notation before camera-ready. The correction has not been made yet.
