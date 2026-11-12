# Reviewer-motivated temporal-structure experiment — frozen protocol v1

Date: 2026-11-12. Status: **PROTOCOL ONLY — no new model observations**.
This study is post-review and exploratory with respect to the original ICLR submission; the following design is fixed *before any new model outputs are inspected*.

## Hypothesis and estimand
H1: An explicit, correct temporal-state representation (B) improves semantic accuracy for latest-state queries relative to a format-matched, fact-equivalent control (C).
H0: No difference in world-averaged semantic accuracy B − C.
Primary estimand: mean within-world difference in proportion of semantically correct latest-state answers (B minus C), with worlds as independent units. A positive estimate alone is insufficient to assert causality if factual equivalence or prompt comparability fails.

## Four conditions
A: chronological prose history, identical output schema.
B: explicit temporal state transitions (entity, attribute, old value, new value, event order), identical output schema.
C: format-only control with the same factual history, neutral field/value listing and identical output schema, but no explicit state-transition edges.
D: structural ablation with all facts and ordering information retained, but transition edges removed; do **not** randomize timestamps, remove events, or introduce contradictions.

A, B, C and D must expose identical source facts, entity identifiers, ordering and answerability; condition D must differ from B in representation only. Each must receive the same question and a fixed JSON output contract. Record token counts and test whether differences in input length explain the effect. Condition B vs C is the single primary comparison; all others are secondary/exploratory.

## Dataset and split
Use the existing procedural generator to produce **100 new independent worlds** with deterministic seeds derived from a new fixed namespace (e.g. `rebuttal-temporal-v1`). Check for duplicate world IDs and overlap with existing frozen smoke/scaled and H4 evaluation data; if overlap occurs, abort. Include repeated CEO/ownership transitions, reversals, distractors, and at least three sequential updates where generator capabilities permit. Freeze and hash the generated worlds before inference. All questions must explicitly specify latest valid state at world end-time; unanswerable cases must be labelled and reported separately. No filtering based on model performance.

## Execution
Use exclusively local inference with a pinned Qwen2.5-3B-Instruct 4-bit MLX checkpoint on Apple Silicon (M4 Pro, 24 GB RAM). No network/API model calls, no paid services, and no silent model downloads during the evaluation run. Record checkpoint revision, weights hash where practical, MLX/MLX-LM versions, temperature=0, generation settings, and prompt-independent deterministic ground truth for all arms. Verify model availability locally before running; if the weights are absent, mark execution blocked until the user installs them locally. Randomize the order of conditions within each world using a recorded seed. Never include gold answers or future event information in prompts. Freeze complete prompt hashes, raw responses, token usage, model identifier and API cost. All model inference must run locally. Zero paid API calls are authorized. Label findings as local Qwen evidence, not a replication of GPT-4.1. Record elapsed time, peak memory if measurable, and any OOM/retry behavior.

## Scoring and statistical plan
Primary metric: semantic accuracy of the latest state, using deterministic answer normalization independent of the output schema; format failures are reported separately. Validate normalization on an arm-blinded stratified sample. Secondary: stale-state rate (old value instead of latest), bundle consistency (BCR, with number of eligible constraints), exact-match format compliance, and performance by transition depth. Missing responses count as incorrect in the intention-to-evaluate analysis, with a separately reported complete-case sensitivity analysis.

Compute per-world paired differences B − C; report world-level bootstrap 95% percentile CI (10,000 resamples, fixed seed) and a two-sided paired sign-flip randomization test (at least 100,000 Monte Carlo draws, fixed seed). Report absolute counts, n worlds, n queries, uncertainty and all failures. No claim of equivalence from p>0.05. All comparisons beyond B vs C are explicitly exploratory. Do not run multiple exploratory alternatives and selectively report favorable ones.

## Go/no-go gates before inference
1. Fact-equivalence assertions for A/B/C/D on every world.
2. No gold-answer leakage.
3. No overlap with original evaluation worlds.
4. Same output contract, model, decoding and question wording.
5. Independent world-level inference; no treating queries as independent replicates.
6. Scorer checks against known positive, stale, ambiguous and malformed examples.
7. All data generation, scorer and analysis code tested.
8. Offline local model and dependencies available; zero paid API calls.
9. Existing audit discrepancy resolved: the published 23/42 vs 2/42 stale-state counts must not be conflated with the separate latest-selection paired table.

## Publication rule
Publish results whether favorable, negative or inconclusive. Label as a post-review additional experiment. Do not claim discovery of internal world representations from behavioral responses. Do not update rebuttal/manuscript until results and integrity gates are verified. No OpenReview submission or merge without explicit review.
