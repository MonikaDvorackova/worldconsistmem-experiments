# Rebuttal and manuscript text — follow-up not yet run

**Status:** These are transparent, no-results drafts. They contain no experimental effect estimate. Replace this document only after the frozen experiment has run and passed its integrity gates.

## Manuscript addition (Methods / limitations)

> To separate explicit temporal-transition structure from a generic format effect, we prepared a post-review controlled follow-up with four fact-equivalent prompt renderings: chronological prose (A), explicit ordered transitions (B), a neutral field/value ledger (C), and ordered event records without transition edges (D). The planned primary estimand is the world-level paired difference in latest-state semantic accuracy between B and C over 100 newly generated worlds. The follow-up uses local Qwen2.5-3B-Instruct 4-bit inference, fixed decoding, a common JSON answer schema, blinded deterministic scoring, and world-clustered uncertainty. The dataset and analysis code were prepared, but model inference was not completed in the available execution environment; consequently, this follow-up supplies no empirical result and is not used to support the paper's claims.

## Response to reviewer concern about format confounds and causal interpretation

> We agree that the earlier comparison did not isolate temporal-transition structure from evidence formatting. We prepared a controlled follow-up that holds the generated world facts, event order, question wording, answer schema, and local model constant while comparing explicit temporal edges (B) with a neutral field/value control (C); chronological prose (A) and an edge-removed structural ablation (D) are exploratory controls. The primary analysis treats worlds, rather than individual questions, as independent units. However, the prescribed local checkpoint was not available in the execution environment, so no model outputs were obtained. We therefore do not claim that this follow-up confirms or refutes the hypothesis, and do not use it as new evidence in the present rebuttal.

## Existing stale-state statistics correction

> We distinguish the stale-state count from the marginal latest-selection count. A stale response matches an earlier event but not the latest event; a response may match both positions, or neither. The audited stale counts remain F0 23/42, F1 17/42, F2 2/42, and F3 7/42. The paired latest-selection margins are F0 19/42, F1 16/42, F2 38/42, and F3 35/42. We corrected the prior summary's F0 and F2 latest-selection entries, which had copied concordant-pair cells rather than the arm-level margins.

## After local execution

Only after the local model smoke test, full run, scorer validation, integrity checks, and world-clustered analysis pass should this document be updated with the observed B−C estimate, 95% world-bootstrap interval, sign-flip p-value, failures, and an explicitly qualified interpretation. Report a null or negative result as observed; do not frame a non-significant result as equivalence.
