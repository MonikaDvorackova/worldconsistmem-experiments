# FINAL EXPERIMENT STATUS — WorldConsistMem

**Status:** FROZEN  
**Paper shape:** **BENCHMARK ONLY**  
**Architecture claim:** CLOSED (not supported)  
**Date:** 2026-08-04  

Do not rerun, reinterpret, or optimize completed experiments. Do not run Phi. Do not revive hierarchy-superiority claims.

---

## Paper-shape verdict

**BENCHMARK ONLY**

Final authoritative Qwen H4 (Run1 reuse + Run2 Option A):

| System | Acc | BCR |
|---|---:|---:|
| B1 compact (`B1_flat_cap150_compact`) | 0.096 | 0 |
| B3 recency (`B3_recency_k8`) | 0.093 | 0 |
| B4 BM25 (`B4_bm25_k8`) | 0.148 | 0 |
| H0 LTKM (`H0_ltkm_cap150_ret8`) | 0.185 | 0 |

H0 improves answer accuracy and abstention relative to the other tested Qwen systems but does **not** improve strict bundle consistency (all BCR = 0).

---

## Completed runs (immutable)

| Run | Artefacts | Notes |
|---|---|---|
| Smoke validation | `data/smoke/`, `outputs/benchmark_validation.md`, `outputs/smoke_metrics.json` | Gold Acc=BCR=1; corruption suite Acc≠consistency |
| Symbolic scaled study | `data/scaled/`, `outputs/scaled/system_results.csv`, `predictions/*.jsonl` | Seed 100; capacity / retrieval / ablations |
| Baseline study | `outputs/baselines/` | Flat / retrieval / reservoir baselines |
| LTKM prototype study | `outputs/ltkm/` | Symbolic H0 prototype |
| H4-Run1 | `outputs/scaled/run1/` | Qwen B1 complete; Qwen B3 partial (1046/1260); Phi not used for Option A |
| H4-Run2 Option A | `outputs/scaled/run2/` | Qwen B3 tail + B4 + H0; **2734/2734**; finalize merge |
| Partial consistency recompute | `outputs/scaled/partial_consistency_*.csv/md` | Offline only; no new inference |

---

## Checksums (authoritative)

| Object | SHA-256 |
|---|---|
| Smoke dataset | `3aa67ed1b6a39be3d9e1805d14f7d5ce7cc05f4655bdce0bc4ff49900c14c7ab` |
| Run1 Qwen cache | `9bb7cfb1737a6d6a2ec15f1fc641bd1b0cd00919d1c473a2039d22ec776f8af3` |
| Symbolic `system_results.csv` | `eb5bd5fa87496586bd830e5f685b9950e119f9fd0ac491194b3f003343f9a2a8` |
| Scaled manifest | `37aa8604c3e6d87691332f66d2f7c0ab93578f2fe468bc29f7e8217c1675af3f` |
| H4 frozen config hash | `1d8a74f29b6b328853f7484a62e52d06ca4237e472e278258bad20acdb090db2` |

---

## Model and system coverage

| Reader | Systems evaluated | Coverage |
|---|---|---|
| Symbolic exact-match | Flat, recency, BM25, reservoir, capacity-matched, H0 LTKM, selective ablations | Full scaled (seed 100) |
| `mlx-community/Qwen2.5-3B-Instruct-4bit` | B1 compact, B3 k8, B4 k8, H0 cap150 ret8 | H4 subset: 18 worlds, 192 bundles, 1260 queries × 4 |
| Phi | **Not run** for final Option A | Do not run |

---

## Authoritative result files

- Symbolic: `outputs/scaled/system_results.csv`, `capacity_results.csv`, `constraint_family_results.csv`, `statistical_analysis.md`, `research_findings.md`, `gate_summary.json`
- Qwen H4: `outputs/scaled/run2/qwen_system_results.csv`, `qwen_query_family_results.csv`, `qwen_constraint_family_results.csv`, `qwen_error_decomposition.csv`, `qwen_statistical_analysis.md`, `qwen_h4_findings.md`, `run2_completeness.json`
- Partial (complementary): `outputs/scaled/partial_consistency_results.csv`, `partial_consistency_by_constraint.csv`, `partial_consistency_by_difficulty.csv`, `partial_consistency_findings.md`
- Shared gate: `outputs/scaled/gate_summary.json` → `"paper": "BENCHMARK ONLY"`

---

## Rejected architecture claims

Do **not** claim:

- H0 superiority under LLM readers;
- necessity of hierarchical / five-layer memory;
- architecture gains that are LLM-independent on the completed Qwen evaluation;
- SOTA;
- general real-world validity;
- revival of hierarchy-superiority as a contribution headline.

Claim form permitted only as **limitation / negative result**: structured lifecycle-aware memory helps evidence availability and **symbolic** consistency under matched budgets in places, but **does not** survive the completed Qwen reader evaluation on strict BCR.

---

## Permitted benchmark claims

1. Per-query accuracy and global cross-query consistency are empirically distinct.  
2. High-retrieval / higher-Acc systems can still violate temporal, relational, transition, and provenance constraints across dependent queries.  
3. Strict BCR can floor under weaker readers; partial CSR / PConsAcc provide complementary diagnostics without redefining BCR.  
4. (Limitation) Architecture superiority is unsupported under the completed Qwen H4 protocol.

Central contribution: **cross-query consistency exposes failures that isolated per-query accuracy does not characterize.**

---

## Metric freeze

- Primary: `Gap_query = MeanQueryAccuracy − BCR`  
- Secondary: `Gap_bundle = BundleAccuracy − ConsAcc_strict`  
- BCR = fraction of bundles with Φ = 1 (unchanged)  
- CSR / violations / PConsAcc grid = complementary only (`configs/METRIC_FREEZE.md` + `partial_consistency.py`)
