# Scaled study research findings

**Verdict:** `PARTIAL RESEARCH SIGNAL`

## Answers

1. Metric distinction survives scaling: **yes** (B3 Gap_query=0.5044, B4 Gap_query=0.338).
2. H0 vs matched flat:
   - vs **recency** eviction: best ΔBCR=0.194, ΔConsAcc=0.194 (gate≥0.10: pass).
   - vs **compact_padding**: best ΔBCR=-0.139 (gate: fail).
   - At cap=150, H0 BCR=0.844 vs flat-recency 0.625 vs flat-compact **1.000**.
3. Strongest H0-over-recency regime: **medium budget (150)**; high (400) saturates both; low (60) helps Acc more than BCR.
4. LLM readers: **Phi-3.5-mini-instruct-4bit download incomplete (weights .incomplete); H4 not executed**. H4 **not confirmed**.
5. Selective ablations (family Acc drop≥0.05): **4/5** (archive, temporal, graph fire; provenance store ablation does not reduce provenance Acc under deterministic reader; conflict harms conflict_validity).
6. Error modes: see `error_decomposition.csv` — retrieval baselines show high Acc with BCR collapse; capacity misses concentrate on historical/transition.
7. Consistency vs accuracy: B4 Acc stays high across tiers while BCR remains materially lower (H5 supported directionally).
8. Strongest defensible paper: **benchmark (+ weakened architecture claims; H0 does not beat compact flat)**.

## Gate checklist

- Acc–BCR gap persists: True
- Matched lift≥0.10 vs recency flat: True (ΔBCR=0.194)
- Matched lift≥0.10 vs compact flat: False (ΔBCR=-0.139)
- Not primarily abstention: True (max H0 abs=0.1587)
- ≥3 selective ablations: True (4)
- LLM advantage: False (Phi-3.5-mini-instruct-4bit download incomplete (weights .incomplete); H4 not executed)
- Seed reproducibility: True
- Not sole query family: True

## Fairness limitations

- Absolute logical-record budgets tax H0 metadata (provenance/graph/event_index); unconstrained H0 stores ~458 logical records vs B1 ~121 observations.
- Task-agnostic compact flat drops location/status padding and can retain all focal lifecycle events within budget 150 — then matches unconstrained B1/H0.
- top-k lexical retrieval ≠ store-routed H0 packs at matched k.
- H4 blocked by incomplete local MLX weight download.
- Bundle difficulty labels are structural; templates reuse smoke query families.

## Bugs / benchmark changes

- Smoke freeze untouched (`3aa67ed1b6a39be3d9e1805d14f7d5ce7cc05f4655bdce0bc4ff49900c14c7ab`).
- Flat reader ownership transition now uses **last** transfer (smoke single-transfer behaviour unchanged).
- QueryBundle optional `metadata`; metric freeze docs; capacity accounting modules.
- No change to BCR/constraint semantics.

## Manuscript drafting

Drafting **may begin only as a benchmark / evaluation paper**. Architecture superiority claims must be **weakened**: H0 beats matched **recency** flat under medium budget, but **does not** beat matched **compact** flat when focal events fit the budget, and LLM-reader robustness was not completed.

## H4 update

- Run2 Option A (Qwen-only) completed.
- H4 status: `not_supported`
- Paper shape: `BENCHMARK ONLY`
- See `run2/qwen_h4_findings.md`.
