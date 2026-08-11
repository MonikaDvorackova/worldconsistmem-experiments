# Partial consistency findings (frozen recomputation)

Paper shape: **BENCHMARK ONLY**. Architecture superiority closed.

BCR is unchanged (fraction of bundles with Φ=1). CSR/PConsAcc are complementary.

## Integrity

- `smoke`: `3aa67ed1b6a39be3d9e1805d14f7d5ce7cc05f4655bdce0bc4ff49900c14c7ab`
- `run1_qwen_cache`: `9bb7cfb1737a6d6a2ec15f1fc641bd1b0cd00919d1c473a2039d22ec776f8af3`
- `system_results_csv`: `70b5ce4f27d1b70d796678029bb375487d37cbf0701f1d75a56b4224c2a941bd`
- `run2_qwen_cache`: `4024b825d89cec3835add27b04a881fe327f859e67a82290cf3b5a7d73e7000c`

## Qwen system table (Acc / BCR / CSR)

| System | Acc | BCR | mean CSR | median CSR | mean viol. | ConsAcc | PConsAcc(0.5,0.8) | PConsAcc(0.8,0.9) | Abs | Mal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_flat_cap150_compact | 0.0960 | 0.0000 | 0.2581 | 0.3333 | 3.594 | 0.0000 | 0.0000 | 0.0000 | 0.7278 | 0.0071 |
| B3_recency_k8 | 0.0929 | 0.0000 | 0.2581 | 0.3333 | 3.594 | 0.0000 | 0.0000 | 0.0000 | 0.7278 | 0.0071 |
| B4_bm25_k8 | 0.1484 | 0.0000 | 0.3291 | 0.3333 | 3.328 | 0.0000 | 0.0000 | 0.0000 | 0.5786 | 0.0008 |
| H0_ltkm_cap150_ret8 | 0.1849 | 0.0000 | 0.2844 | 0.2917 | 3.500 | 0.0000 | 0.0000 | 0.0000 | 0.4825 | 0.0286 |

## Does H0 improve CSR under Qwen?

- H0 mean CSR − B1_flat_cap150_compact: **+0.0263** (H0=0.2844, B1_flat_cap150_compact=0.2581; Acc Δ=+0.0889)
- H0 mean CSR − B3_recency_k8: **+0.0263** (H0=0.2844, B3_recency_k8=0.2581; Acc Δ=+0.0921)
- H0 mean CSR − B4_bm25_k8: **-0.0447** (H0=0.2844, B4_bm25_k8=0.3291; Acc Δ=+0.0365)

Interpretation rule: Acc gains without CSR gains are **not** consistency claims.

## BCR floor diagnostics (Qwen)

### B1_flat_cap150_compact

- mean CSR: 0.2580729166666671
- mean violations/bundle: 3.59375
- frac exactly one violation: 0.03125
- frac multiple violations: 0.96875
- most frequent violated family: `transition`
- family hit counts: `{'temporal': 68, 'transition': 192, 'relational': 120, 'provenance': 180, 'multi_hop': 78, 'uniqueness': 42, 'contradiction': 10}`

### B3_recency_k8

- mean CSR: 0.2580729166666671
- mean violations/bundle: 3.59375
- frac exactly one violation: 0.03125
- frac multiple violations: 0.96875
- most frequent violated family: `transition`
- family hit counts: `{'temporal': 68, 'transition': 192, 'relational': 120, 'provenance': 180, 'multi_hop': 78, 'uniqueness': 42, 'contradiction': 10}`

### B4_bm25_k8

- mean CSR: 0.32907986111111154
- mean violations/bundle: 3.328125
- frac exactly one violation: 0.17708333333333334
- frac multiple violations: 0.8229166666666666
- most frequent violated family: `transition`
- family hit counts: `{'temporal': 62, 'transition': 192, 'relational': 120, 'provenance': 139, 'multi_hop': 78, 'uniqueness': 34, 'contradiction': 14}`

### H0_ltkm_cap150_ret8

- mean CSR: 0.28437500000000066
- mean violations/bundle: 3.5
- frac exactly one violation: 0.0
- frac multiple violations: 1.0
- most frequent violated family: `transition`
- family hit counts: `{'temporal': 54, 'transition': 192, 'relational': 120, 'provenance': 192, 'multi_hop': 78, 'contradiction': 36}`


## Acc–CSR correlation (Qwen)

- B1_flat_cap150_compact: pearson(Acc_b, CSR_b) = 0.3096
- B3_recency_k8: pearson(Acc_b, CSR_b) = 0.3048
- B4_bm25_k8: pearson(Acc_b, CSR_b) = 0.4267
- H0_ltkm_cap150_ret8: pearson(Acc_b, CSR_b) = -0.0352

## Allowed reading

- Acc and BCR/CSR remain empirically distinct under Qwen (BCR=0 for all; CSR varies).
- Do **not** convert H0 Acc/abstention gains into architecture-superiority claims.
- Strict BCR floor (all zero) motivates reporting CSR and the PConsAcc grid.
