# Execution and audit assessment

Date: 2026-11-12 assessment before inference; local run completed afterward.

## Work runtime and checkpoint preparation

- Work execution host: Linux x86_64, 9.7 GiB RAM, no Apple Silicon or Metal device. It had no local checkpoint, so no inference was run there.
- The protocol names `mlx-community/Qwen2.5-3B-Instruct-4bit` but did not freeze an immutable Hub revision. Before inference, the local run pinned revision `4f83f8f146fdf28b512a06562b671d7af4fab457`.
- Local checkpoint SHA-256: `f212cf6fb9923281a09c135e05d43a052ee5ef7121f5b1dc0b0fb2de80f97cfd`. Its configuration was verified as Qwen2, 4-bit, group size 64.
- Model was fetched explicitly to the user's Mac before inference. The runner then set Hub/Transformers offline flags and loaded the local directory only.
- The initial Conda environment command resolution selected Homebrew Python. This was diagnosed from `sys.executable` and resolved by invoking `/opt/miniconda3/envs/wcm-rebuttal/bin/python` directly. The correct environment imported MLX and MLX-LM, passed preflight and a short local generation smoke test.
- Local platform reported by preflight: macOS 26.2 arm64. Conda package list reported MLX 0.32.4 and MLX-LM 0.32.2. Preflight's Python distribution metadata reported MLX-LM as 0.0.0; the Conda package list is the available package-version evidence, and the discrepancy should be retained in reproducibility notes.
- No paid model API or remote inference was used.

## CPU backend assessment

Before the local Mac checkpoint became available, an isolated `uv` invocation installed `mlx-lm[cpu]==0.32.2` and `mlx-cpu==0.32.4` on this Linux host. MLX CPU array operations and MLX-LM APIs imported successfully. This only established software plausibility; it was not used for the experimental inference. `llama.cpp` was not selected because converting the MLX checkpoint to GGUF would change the model representation and quantization could not be verified equivalent.

## Synthetic preparation and integrity

The fixed namespace generated 100 unique worlds, 200 latest-state questions, and 800 prompts. There was no overlap with the existing scaled-world index or 18 H4 reference worlds. Gold labels were stored separately from prompts. The scorer's five known examples passed. A/B/C/D renderings were checked for source-fact equivalence and answer-label leakage before inference. All prompts passed context-fit preflight. The full test suite before the local run reported 154 passed, 11 skipped.

## Local model run

The user's Mac run completed 800 predictions in 19,956.244 seconds (5 h 32 min 36 s), with 100 worlds and 200 queries. Model: `mlx-community/Qwen2.5-3B-Instruct-4bit`, pinned revision above, verified weight SHA-256 above, temperature 0, max 48 tokens, local MLX-LM. The 8-token generic smoke test returned `local-inference-ok`.

Primary result from the terminal report: world-clustered B−C semantic accuracy difference −0.360, 95% world bootstrap percentile CI [−0.405, −0.315], two-sided paired sign-flip Monte Carlo p=0.000010 (100,000 draws; +1 correction). B accuracy was 1/200; C accuracy was 73/200. All four conditions had 200/200 schema-valid outputs. B's average prompt length was 28,227.61 tokens versus C's 13,577.15 (mean paired token difference +14,650.46). The across-world correlation of paired accuracy and token-length differences was r=−0.128, permutation p=0.203; this does not remove the between-condition length confound. CEO accuracy was 0/100 in both B and C; ownership accuracy was 1/100 in B and 73/100 in C.

**Interpretation:** The observed result does not support the directional hypothesis for the implemented prompt variants. It also does not establish that temporal edges themselves reduce accuracy, because B and C differed substantially in input length. Do not claim causal isolation or equivalence. The effect is concentrated in ownership questions; CEO latest-state accuracy was zero in both primary arms.

## Transferred artifact audit

The user-provided raw and scored JSONL files were independently audited against the committed generator, prompt index, gold labels, and frozen scorer. Both files contain 800 unique rows covering exactly the expected 100 worlds × 2 queries × 4 conditions. All raw prompt hashes match their generated prompt rows, and deterministic regeneration reproduces the prompt gzip SHA-256 recorded in the generation manifest (`746c41b3badc71e403621f3310653767ede2d5c329249e5cd1b2510793dbfce5`). The prompt audit found no gold-answer metadata markers. Re-scoring all 800 raw outputs against the separate gold table produced zero mismatches with the transferred scored file. Recomputed world-clustered statistics exactly match the stored primary result.

Artifact SHA-256 (uncompressed JSONL): raw `09a0c15fb58cffa76be275a6f38e0ed594edc2b924c881f9a7111334b11bbdc4`; scored `68211cd1c963820e147f5925909ff7d982789eed41b6fef139f649e499abc085`. Compressed archival files are committed alongside model metadata and `scripts/audit_rebuttal_temporal_outputs.py`. The audit script passes locally. This Work runtime does not include pytest (`No module named pytest`); the earlier complete test run recorded 154 passed and 11 skipped.

## Existing stale-state count audit

The tracked summary supports stale-state counts F0 23/42, F1 17/42, F2 2/42, and F3 7/42. Stale means matching an earlier position without matching the latest. Separate paired latest-selection tables imply margins F0 19/42, F1 16/42, F2 38/42, F3 35/42. They are not complements of stale counts. Earlier F0=17 and F2=32 values copied concordant-pair cells, not arm margins; the summary was corrected to 19 and 38. The private item-level source is absent from this checkout, so this reconciliation uses committed audit summaries and paired tables rather than fresh raw-record reanalysis.
