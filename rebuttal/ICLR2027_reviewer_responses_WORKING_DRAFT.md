# ICLR 2027 rebuttal working draft — WorldConsistMem (Submission 49130)

**Status:** evidence-backed draft, **NOT submitted to OpenReview**. Last updated 2026-11-11. Do not assert that semantic grading of all 150 cases, cross-model replication, evidence-sufficiency adjudication, or manuscript corrections have been completed: they have not been verified here.

## Core response / positioning

We thank the reviewers for identifying a central construct-validity issue: exact-match transition tuple accuracy is not equivalent to the semantic correctness of a natural-language answer. We agree that a response such as a correct scalar timestamp to a “when” question must not be interpreted as evidence of failed temporal reasoning merely because it lacks fields absent from the user-facing question. We will distinguish (i) factual answer correctness, (ii) full transition-tuple completeness, and (iii) output-contract/schema compliance, and revise the headline claim accordingly. The controlled result remains a large improvement in **exact-match structured transition output** under matched evidence and one fixed GPT-4.1 snapshot; we do not claim that its full magnitude measures a gain in underlying temporal reasoning.

Our new independent annotation exercise covers **120 responses across 30 cases (four responses/case)**. Reviewer 1 assigned 75 correct, 19 incorrect, and 26 ambiguous; Reviewer 2 assigned 55 correct and 65 incorrect. Exact agreement is 70/120 (58.33%); unweighted three-category Cohen’s κ = 0.3363. In 26 cases Reviewer 1 used “ambiguous” where Reviewer 2 used “incorrect”. This is preliminary evidence of rubric sensitivity, **not** a resolved human-validated accuracy estimate. We will preserve both raw sets and report adjudication separately rather than collapse ambiguity into error. Neither evidence sufficiency nor all 150 experimental items has been independently human-rated in these files.

## Response to Reviewer vfz3 — schema compliance and sufficiency labels

**Schema-confounding concern.** We agree. A correct scalar timestamp can answer the question while failing the tuple contract. The existing forensic M5 audit of format-only wins was narrower than this concern: it did not test whether a correct short answer is semantically equivalent to the asked question. We will explicitly distinguish strict tuple accuracy from question-aligned semantic accuracy, and avoid describing the entire F0→F3 gain as improved reconstruction until semantic regrading of F0–F3 is complete. **Pending:** verify full 150-item arm-aligned raw predictions, implement a rubric that treats a correct scalar response as correct for the asked timestamp but incomplete for full tuple reconstruction, and report paired estimates with case-clustered uncertainty.

**Evidence sufficiency.** We agree that a re-audit changing 77/150 labels cannot be reconciled by continuing to interpret the original S1–S5 labels as stable ground truth. We will distinguish historical labels from corrected sufficiency assessments, provide a transition table, and separate insufficient evidence from incorrect reasoning. In particular, the original S2 set is collinear with document transitions (34/34); missing version identifiers cannot be counted as model reasoning failures. **Pending:** verify per-item gold and evidence packs and adjudicate corrected labels.

## Response to Reviewer EdSa — semantic grading, replication, baseline and document floor

**Semantic grading.** We agree this is the decisive check. The 120-response human annotation exercise is now complete, but low agreement (κ = 0.3363) and differing use of “ambiguous” prevent us from claiming a validated semantic effect. We will report it as a diagnostic, establish a common rubric, and adjudicate disagreements before deriving semantic accuracy. The exercise is a 30-case subset, not a substitute for grading all 150 items across F0–F3.

**Cross-model replication.** The confirmatory effect is demonstrated for a single GPT-4.1 snapshot. We do not claim model-family generality. **Pending:** execute and verify a second-model matched F0–F3 experiment before reporting any replication numbers. A prepared but unexecuted Gemini protocol is not evidence.

**F0 baseline.** We will characterize F0 explicitly as a generic response interface rather than a representative production-memory baseline unless we can document its provenance. The key causal contrast is interface-conditioned structured accuracy, not an estimate of generic memory-system incapacity.

**Document/S2 failures.** We will report that all 34 original S2 cases are document transitions, so evidence sufficiency and subtype cannot be disentangled. We will not attribute the 0/34 floor to reasoning incapacity when required version identifiers are absent from the packs.

## Response to Reviewer Rkeo — leakage, analyst degrees of freedom, scorer/parser and presentation

**Leakage/schema selection.** The manuscript reports a forensic leakage PASS, but the rebuttal must provide a compact, reproducible mapping from public query-id subtype slots to the schema, identify what information was frozen, and show no gold answer values or future labels were used in schema selection. **Pending:** retrieve and inspect prompt/source manifest before adding technical claims.

**Post-result factorization.** F1/F2 were designed after observing F3. We will continue to label them post-result and distinguish the preregistered bundled comparison from exploratory factorization. A transparent execution/freeze timeline, hashes, and runner details should be added after verification.

**Scorer/parser sensitivity.** The scorer v1→v2 alias normalization changes the generic baseline from 0/150 to 13/150; the bare-JSON runner repair is documented. These corrections must not be equated with a semantic grading test. **Pending:** reconstruct the original online-parser/scorer comparisons from frozen outputs and report a table without extrapolation.

**Presentation.** We accept the criticism. The revised manuscript should fix malformed typography, contradictory Figure 1 baseline labels, float placement, inconsistent notation, and overly defensive framing. We will put the exact-match versus semantic distinction in the abstract, introduction, and primary results.

## Remaining acceptance-critical gates

1. Full F0/F1/F2/F3 arm mapping for the 120 annotation rows from the actual experiment manifest; do **not** infer R1–R4 correspondence from response format or row order.
2. Predefined semantic rubric, adjudication of 50 reviewer disagreements, and explicit treatment of 26 ambiguous/incorrect mismatches.
3. Full 150-item semantic regrade with matched per-item comparisons and appropriate clustered uncertainty.
4. Reclassification and verification of evidence sufficiency, especially all 34 document cases and the reported 77/150 changes.
5. A second-model full four-arm replication if feasible, with model version and fixed prompts/evidence documented.
6. LaTeX/PDF cleanup and upload of revised manuscript.

**Important:** The human evaluation results are not yet a positive rebuttal to the reviewers' soundness concerns; the low agreement is a diagnostic finding that requires follow-up. Do not submit this draft verbatim as a claim of completed experiments.
