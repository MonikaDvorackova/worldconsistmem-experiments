# Metric freeze for WorldConsistMem (smoke + scaled)

## Primary gap (Gap_query)

MeanQueryAccuracy − BCR

Where MeanQueryAccuracy is the mean structured exact-match over all queries,
and BCR is the fraction of bundles with Φ=1 (all applicable constraints pass).

## Secondary gap (Gap_bundle)

BundleAccuracy − ConsAcc_strict

Where BundleAccuracy is the fraction of bundles with all answers individually
correct, and ConsAcc_strict requires all answers correct AND Φ=1.

## Frozen semantics

- BCR, ConsAcc, constraint families, and structured exact-match Acc are unchanged
  from the smoke validation suite.
- Smoke checksum remains:
  3aa67ed1b6a39be3d9e1805d14f7d5ce7cc05f4655bdce0bc4ff49900c14c7ab
- Scaled evaluation must call the same `evaluate_predictions` / `aggregate_metrics`
  path as smoke.

## Complementary partial metrics (do not redefine BCR)

Added 2026-08-04 for BCR floor diagnostics under weaker readers:

- **CSR_b** = (# satisfied applicable constraints) / (# applicable constraints); BCR = 1 iff CSR = 1.
- **Violations/bundle** and normalized violations.
- **PConsAcc** grid: Acc τ ∈ {0.5, 0.8} × CSR τ_c ∈ {0.8, 0.9} (report full grid).

Implementation: `src/worldconsistmem/partial_consistency.py`.  
Offline recompute only: `scripts/recompute_partial_consistency.py`.
