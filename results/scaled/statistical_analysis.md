# Statistical analysis (world-level)

Primary independent units are **worlds**. Bootstrap 95% CIs over world means.
Queries within a bundle are **not** treated as independent samples.

## Metric freeze

- **Primary:** `Gap_query = MeanQueryAccuracy − BCR`
- **Secondary:** `Gap_bundle = BundleAccuracy − ConsAcc_strict`
- Smoke checksum unchanged: `3aa67ed1b6a39be3d9e1805d14f7d5ce7cc05f4655bdce0bc4ff49900c14c7ab`
- BCR / ConsAcc / Acc semantics identical to smoke evaluation path.

## H1 — Acc–BCR gap persistence

- B3_recency_k8: Acc=0.5669, BCR=0.0625, Gap_query=0.5044
- B4_bm25_k8: Acc=0.929, BCR=0.591, Gap_query=0.338
- B2_latest_only: Acc=0.4905, BCR=0.2188, Gap_query=0.2717
- B1_flat_unconstrained: Acc=1.0, BCR=1.0, Gap_query=0.0
- H0_ltkm_unconstrained: Acc=1.0, BCR=1.0, Gap_query=0.0

## H2 — Matched capacity (paired world deltas)

- cap=60 vs flat-recency Δbcr(H0−flat)=0.0873 CI95[0.0108,0.1598] sign-p=0.0009865 d=0.236
- cap=60 vs flat-recency Δconsacc(H0−flat)=0.0124 CI95[-0.0523,0.0729] sign-p=0.0009865 d=0.041
- cap=60 vs flat-compact Δbcr(H0−flat)=-0.2706 CI95[-0.3230,-0.2109] sign-p=7.439e-07 d=-0.917
- cap=60 vs flat-compact Δconsacc(H0−flat)=-0.3454 CI95[-0.4075,-0.2766] sign-p=7.679e-08 d=-0.986
- cap=150 vs flat-recency Δbcr(H0−flat)=0.1944 CI95[0.1430,0.2516] sign-p=1.164e-10 d=0.704
- cap=150 vs flat-recency Δconsacc(H0−flat)=0.1944 CI95[0.1430,0.2516] sign-p=1.164e-10 d=0.704
- cap=150 vs flat-compact Δbcr(H0−flat)=-0.1389 CI95[-0.1797,-0.1021] sign-p=1.164e-10 d=-0.704
- cap=150 vs flat-compact Δconsacc(H0−flat)=-0.1389 CI95[-0.1797,-0.1021] sign-p=1.164e-10 d=-0.704
- cap=400 vs flat-recency Δbcr(H0−flat)=0.0000 CI95[0.0000,0.0000] sign-p=1 d=0.000
- cap=400 vs flat-recency Δconsacc(H0−flat)=0.0000 CI95[0.0000,0.0000] sign-p=1 d=0.000
- cap=150 vs reservoir ΔBCR=0.0556 CI[0.0408,0.0719]

### Cap=150 vs recency by tier

- small Δbcr=0.0000 CI[0.0000,0.0000]
- small Δconsacc=0.0000 CI[0.0000,0.0000]
- small Δmean_acc=0.0000 CI[0.0000,0.0000]
- medium Δbcr=0.0000 CI[0.0000,0.0000]
- medium Δconsacc=0.0000 CI[0.0000,0.0000]
- medium Δmean_acc=0.0000 CI[0.0000,0.0000]
- large Δbcr=0.5833 CI[0.5833,0.5833]
- large Δconsacc=0.5833 CI[0.5833,0.5833]
- large Δmean_acc=0.7708 CI[0.7708,0.7708]

## H3 — Ablations (Holm)

- H-archive: Acc=0.8762 BCR=0.375
- H-temporal-validity: Acc=0.8762 BCR=0.375
- H-graph: Acc=0.9381 BCR=0.5938
- H-provenance: Acc=1.0 BCR=1.0
- H-conflict: Acc=0.8 BCR=0.8125
- Holm H-archive: raw_p=3.944e-31 holm_p=1.972e-30
- Holm H-temporal-validity: raw_p=3.944e-31 holm_p=1.972e-30
- Holm H-graph: raw_p=3.944e-31 holm_p=1.972e-30
- Holm H-conflict: raw_p=3.944e-31 holm_p=1.972e-30
- Holm H-provenance: raw_p=1 holm_p=1

## H5 — Scaling curves (B4_bm25_k8 by tier)

- small: Acc=0.9333 BCR=0.6
- medium: Acc=0.9029 BCR=0.6
- large: Acc=0.9363 BCR=0.576
