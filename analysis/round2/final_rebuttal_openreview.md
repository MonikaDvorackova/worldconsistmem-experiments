# ICLR 2027 Rebuttal — WorldConsistMem (Submission 49130)

**Revised draft — not submitted.** Check the final manuscript and current OpenReview word/page limit before use. This replaces older, conflicting rebuttal drafts.

We thank reviewers Rkeo, vfz3, and EdSa. We agree that exact-match tuple accuracy, question-aligned semantic correctness, and cross-query consistency are distinct outcomes. We have narrowed our interpretation accordingly. The H4 findings are limited to one model snapshot, 18 worlds, and 150 questions.

## vfz3: schema compliance and label stability

We re-scored all 600 outputs with the schema-agnostic, question-aligned B1 rule. On the 74 structurally unique questions, every arm is semantically correct on 74/74, while exact-match is F0 10/74, F1 74/74, F2 12/74, and F3 74/74. Thus the F3–F0 exact-match gap on this subset is 64 items, while the semantic difference is zero. We will describe this as an output-contract effect on these questions, not a semantic-reasoning gain.

For 42 multi-candidate questions, the gold convention selects the latest event, but the question text does not state that convention. Under that convention, stale-state counts are F0 23/42, F1 17/42, F2 2/42, and F3 7/42; the separate latest-selection counts are 19/42, 16/42, 38/42, and 35/42. These measures are reported separately. F0 versus F2 latest selection has item-level RD +45.2 pp (95% CI [+27.5, +62.9], exact McNemar p=0.000066). Because the 42 items cluster in 12 worlds, we also report the world-level sign test: 10 non-tied worlds favor F2, none favor F0, and two tie; the one-sided exact p-value over the 10 non-tied worlds is 0.00098. The item-level result is not treated as 42 independent replications.

This is an association under an implicit gold convention, not proof of temporal reasoning. F1, which has no temporal structure, has zero stale ownership answers among 22 ownership items but 17/20 stale CEO answers, indicating substantial question-template asymmetry. Under a sensitivity rule crediting any single documented candidate event, semantic scores are F0 144/150, F1 149/150, F2 150/150, and F3 150/150. We will disclose the dependence on this scoring convention.

Round 2 agreement was 44/50 (κ=0.758; clustered bootstrap 95% CI [0.517, 0.957]) under a revised rubric. Six disagreements remain unresolved. This is evidence about agreement under that rubric, not independent validation of every gold label; we do not characterize Round 1 κ=0.336 as “noise” or as fully resolved by the second round.

## EdSa: semantic grading, document items, and generalization

On B1-nodoc, excluding the 34 document questions whose requested version transition cannot be identified from the supplied evidence, semantic scores are F0 87/116 (75.0%), F1 90/116 (77.6%), F2 112/116 (96.6%), and F3 109/116 (94.0%). The paired F2–F3 difference is +2.6 pp (95% CI [−2.5, +7.6], exact McNemar p=0.508); the evidence does not establish a difference. Under full B1 scoring, F2 receives 20 spurious document credits because of the prev/event/next format. We will separate these items and remove any claim that F3 has the highest semantic accuracy.

B1 is a deterministic rule-based scorer, not human grading of all 600 outputs. Human review covered a 50-response Round 2 sample, with six unresolved disagreements. Cross-model generalization remains untested.

## Rkeo: leakage, analysis choices, and presentation

The forensic audit passed its 26 checks. The 17-scenario sensitivity analysis is reported with the limitations above. We clarify the analysis timeline: **F3 versus F0 is the prespecified comparison; F1 and F2 are exploratory post-result factorizations.** We will not describe the four arms as a prespecified 2×2 design. This replaces an earlier draft that said otherwise.

BCR is a stricter bundle-level metric than per-query accuracy, but BCR=0 at per-query accuracy around 18.5% is not surprising under independent errors. We therefore do not use BCR=0 as evidence that models lack an internal world model or as evidence of excess dependence beyond an independence baseline. We will frame BCR as a complementary joint-success measure and state what the current results do and do not establish.

## Post-review local temporal-control experiment

As an exploratory follow-up, we ran 100 new worlds and 800 local predictions with Qwen2.5-3B-Instruct-4bit. The prespecified B–C world-paired difference was −36.0 pp (95% CI [−40.5, −31.5], sign-flip p=0.000010); accuracies were 0.5% for B and 36.5% for C. This does not support the directional hypothesis for these prompt implementations. B prompts averaged 28,228 tokens versus 13,577 for C, and this run used a different model from the original H4 study. We do not attribute the contrast to temporal edges or treat it as a replication.

## Revisions to the paper

We will distinguish exact-match compliance, question-aligned semantic scoring, and temporal selection; disclose the implicit latest-event convention and the 34 unidentifiable document items; label F1/F2 exploratory; report the BCR independence caveat; remove semantic-superiority claims for F3; and limit H4 conclusions to the tested model and worlds. 
