# Rebuttal and manuscript text — local run completed

**Status:** The frozen 100-world run completed locally on Apple Silicon. The result is negative for the prespecified B−C contrast. The difference is large, but B prompts were substantially longer than C prompts, so this result does not identify a causal effect of temporal-transition structure alone.

## Results

| Condition | Semantic correct | Accuracy | Stale-state | Mean prompt tokens |
|---|---:|---:|---:|---:|
| A — chronological prose | 100/200 | 50.0% | 95/200 | 4,999 |
| B — explicit transitions | 1/200 | 0.5% | 128/200 | 28,228 |
| C — neutral field/value | 73/200 | 36.5% | 66/200 | 13,577 |
| D — ordered records, no edges | 98/200 | 49.0% | 74/200 | 6,607 |

Primary world-clustered paired B−C difference: **−0.360** (−36.0 percentage points), 95% world-bootstrap percentile CI **[−0.405, −0.315]**, two-sided sign-flip Monte Carlo **p=0.000010** (100,000 draws; minimum attainable p with the +1 correction). The estimate averages each world's two questions before averaging across the 100 worlds.

By question type, CEO latest-state accuracy was 0/100 in both B and C; ownership accuracy was 1/100 in B and 73/100 in C. Thus the aggregate primary difference is driven by ownership questions. Format validity was 200/200 in all four conditions.

B averaged **14,650 more input tokens than C** (28,228 vs 13,577; 2.08×). The reported across-world prompt-length/effect association was r=−0.128, permutation p=0.203. This non-significant association does not adjust away the large between-condition length imbalance and is not evidence that length had no effect. A/B/C/D therefore remain a comparison of the complete prompt implementations; the B−C estimate cannot be attributed to temporal edges alone.

## Manuscript addition

> We ran the preregistered post-review local follow-up on 100 newly generated worlds (200 latest-state questions; four prompt conditions per question) using Qwen2.5-3B-Instruct-4bit with temperature 0 and a shared JSON schema. The primary world-clustered B−C semantic-accuracy difference was −36.0 percentage points (95% world-bootstrap CI [−40.5, −31.5]; two-sided sign-flip Monte Carlo p=0.000010). Accuracy was 0.5% for explicit transitions (B) and 36.5% for the neutral field/value condition (C). However, B prompts averaged 28,228 tokens and C prompts 13,577 tokens. The observed negative contrast does not support the directional hypothesis for these prompt implementations, but the large input-length imbalance prevents attributing the difference to temporal-transition structure alone. We treat the follow-up as post-review evidence with this limitation and make no claim about internal model representations.

## Reviewer-specific response on format confounds

> We agree that the original comparison did not isolate temporal structure from presentation. We completed a controlled four-condition local follow-up with fact-equivalent histories and a common question and output schema. The prespecified B−C comparison did not favor explicit transitions: accuracy was 0.5% in B and 36.5% in C (world-clustered difference −36.0 pp, 95% CI [−40.5, −31.5], sign-flip p=0.000010). We also found a substantial prompt-length imbalance (mean 28,228 tokens in B vs 13,577 in C). We therefore do not present this as clean causal evidence that temporal edges impair reasoning; it shows that the tested B prompt implementation performed worse, while leaving representation and context-length effects unresolved. The result does not support our original directional hypothesis.

## Existing stale-state statistics correction

> We distinguish the stale-state count from the marginal latest-selection count. A stale response matches an earlier event but not the latest; a response may match both positions, or neither. The audited stale counts remain F0 23/42, F1 17/42, F2 2/42, and F3 7/42. The paired latest-selection margins are F0 19/42, F1 16/42, F2 38/42, and F3 35/42. The prior F0 and F2 latest-selection entries copied concordant-pair cells instead of the arm-level margins and have been corrected.

**Artifact note:** The runner writes `raw_predictions.jsonl`, `scored_predictions.jsonl`, and `evaluation_results.json` under the experiment data directory on the Mac. Those machine-generated rows have not yet been transferred into this PR, so the summary above is based on the completed terminal report and remains pending raw-file hash/coverage review.