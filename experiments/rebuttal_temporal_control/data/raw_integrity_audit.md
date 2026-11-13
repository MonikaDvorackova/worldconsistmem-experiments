# Raw-output integrity audit

Date: 2026-11-13. Audit performed after transfer of the user's local run artifacts.

## Checks

- Raw predictions: 800 rows; 800 unique `(world_id, query_id, condition)` keys; 100 unique worlds.
- Scored predictions: 800 rows; 800 unique keys. Both files cover the exact 800 expected prompt keys (100 worlds × 2 queries × 4 conditions).
- Condition coverage: 200 predictions each for A, B, C, and D.
- Every raw `prompt_sha256` matches its frozen prompt row. Deterministic prompt regeneration reproduces the manifest's compressed prompt hash `746c41b3badc71e403621f3310653767ede2d5c329249e5cd1b2510793dbfce5`.
- No answer-label metadata markers were found in prompts.
- All 800 scored rows were recalculated from raw outputs and separate gold labels using the frozen scorer: **zero mismatches**.
- Recomputed world-clustered primary analysis exactly matches saved results: B−C = −0.360; 95% world-bootstrap CI [−0.405, −0.315]; two-sided paired sign-flip Monte Carlo p=0.000010 (100,000 draws, +1 correction).
- Audit script: `python scripts/audit_rebuttal_temporal_outputs.py --raw experiments/rebuttal_temporal_control/data/raw_predictions.jsonl.gz --scored experiments/rebuttal_temporal_control/data/scored_predictions.jsonl.gz` (PASS).

## Checksums

| Artifact | SHA-256 |
|---|---|
| Raw predictions, JSONL | `09a0c15fb58cffa76be275a6f38e0ed594edc2b924c881f9a7111334b11bbdc4` |
| Raw predictions, gzip | `3a6367f416dc7820e1b4a9ddb8dbac799aaa07e2d35189e7ac97b557f7e66d99` |
| Scored predictions, JSONL | `68211cd1c963820e147f5925909ff7d982789eed41b6fef139f649e499abc085` |
| Scored predictions, gzip | `55578341cb28734f14718d92866aad8f32e95fcc2e395052aabdd4fdb34fc527` |
| Prompt dataset, gzip | `746c41b3badc71e403621f3310653767ede2d5c329249e5cd1b2510793dbfce5` |
| Evaluation report as transferred | `beb5ad5a15fbd8ad475f4e6e74107561ef2086404ad9c5874b6179630413bfa8` |

The raw/scored outputs remain accompanied by the limitation that condition B averaged 28,228 prompt tokens versus 13,577 for C. The negative contrast is verified for these prompt implementations; its causal source remains unresolved.
