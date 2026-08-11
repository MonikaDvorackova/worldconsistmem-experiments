# H4-Run1 INTERIM REPORT

**Status:** frozen. No new predictions after stop.  
**All metrics below are INTERIM** (computed only on completed predictions; missing cells are not imputed).

## 1. Stop point

| Field | Value |
| --- | --- |
| Stop method | Wait for durable cache append → `SIGTERM` (no `kill -9`) |
| Timestamp (manifest) | see `run1_manifest.json` |
| Git commit | `9fc6743608aaefdbd95de4ded98de41c050eef38` |
| Last system | `B3_recency_k8` (Qwen) |
| Last query ID | `sl0171_003:b:doc:2:temporal_order` |
| Qwen × B1 | **1260 / 1260** (100%) |
| Qwen × B3 | **1046 / 1260** (83.02%) |
| Qwen × B4 | **0 / 1260** |
| Qwen × H0 | **0 / 1260** |
| Phi (all systems) | **22 / 5040** (1.75% of B1 only) |

Matching rule: logical `(model_slug, system, query_id)`.  
Phi’s 22 rows use a **legacy `cache_key` hash** that does not match the current hasher; they are retained as completed logical predictions for those cells.

## 2. Completion

| Quantity | Value |
| --- | ---: |
| Expected matrix | 10 080 |
| Completed | **2 328** |
| Completion | **23.10%** |

## 3. Coverage summary

### By model

| Model | Done | Expected | % |
| --- | ---: | ---: | ---: |
| Qwen2.5-3B-Instruct-4bit | 2306 | 5040 | 45.75 |
| Phi-3.5-mini-instruct-4bit | 22 | 5040 | 0.44 |

### By system (both models)

| System | Done | Expected | % |
| --- | ---: | ---: | ---: |
| B1_flat_cap150_compact | 1282 | 2520 | 50.87 |
| B3_recency_k8 | 1046 | 2520 | 41.51 |
| B4_bm25_k8 | 0 | 2520 | 0.00 |
| H0_ltkm_cap150_ret8 | 0 | 2520 | 0.00 |

### By model × system

| Cell | Done / Expected | % |
| --- | ---: | ---: |
| Qwen \| B1 compact | 1260 / 1260 | 100.00 |
| Qwen \| B3 recency | 1046 / 1260 | 83.02 |
| Qwen \| B4 BM25 | 0 / 1260 | 0.00 |
| Qwen \| H0 LTKM | 0 / 1260 | 0.00 |
| Phi \| B1 compact | 22 / 1260 | 1.75 |
| Phi \| B3 / B4 / H0 | 0 / 1260 each | 0.00 |

### By tier / family / world / bundle

- **Tier:** coverage ~23% each (small / medium / large) — schedule-driven, not tier-blocked.  
- **Query families:** coverage ~23% each — not family-blocked.  
- **Worlds:** all 18 H4 worlds appear in completed Qwen×B1; Qwen×B3 stops mid–large-tier traversal.  
- **Bundles:** 192/192 have some completion; **0/192** have all 8 model×system cells; mean bundle coverage ≈ 23%.

Full tables: `coverage.json`.

## 4. INTERIM metrics (completed only)

BCR / ConsAcc use **fully covered bundles only** for that model×system.  
Query accuracy / abstention / malformed use **all completed queries**.  
World-level bootstrap CIs reported when ≥3 worlds contribute.

### Qwen × B1 compact (INTERIM; 100% query coverage)

| Metric | Value |
| --- | --- |
| Mean query Acc (completed) | **0.096** |
| Acc world mean [95% CI] | 0.0958 [0.0854, 0.1056] |
| BCR (192/192 bundles) | **0.0** [0.0, 0.0] |
| ConsAcc strict / relaxed | 0.0 / 0.0 |
| Gap_query (Acc − BCR) | **0.096** |
| Abstention rate | **0.728** |
| Malformed rate | 0.007 |
| High-acc inconsistent bundle rate | 0.0 |

### Qwen × B3 recency (INTERIM; 83% queries; 159/192 full bundles)

| Metric | Value |
| --- | --- |
| Mean query Acc (completed) | **0.0966** |
| Acc world mean [95% CI] (16 worlds) | 0.0945 [0.0829, 0.1055] |
| BCR (159 full bundles) | **0.0** |
| ConsAcc strict / relaxed | 0.0 / 0.0 |
| Gap_query | **0.0966** |
| Abstention rate | **0.733** |
| Malformed rate | 0.006 |

### Phi × B1 (INTERIM; 22 queries; 3 full bundles)

| Metric | Value |
| --- | --- |
| Mean query Acc | 0.0455 |
| BCR (3 bundles) | 0.0 |
| World CI | **not reported** (n_worlds < 3 for CI policy) |
| Abstention | 0.227 |
| Malformed | high relative to n (see `interim_metrics.json`) |

### Qwen × B4, Qwen × H0, Phi × {B3,B4,H0}

No predictions — metrics undefined.

Source: `interim_metrics.csv` / `interim_metrics.json`.

## 5. Uncertainty

- High abstention (~73% on Qwen) dominates outcomes; Acc and BCR are both low.  
- BCR = 0 on all evaluated full-bundle sets → CIs collapse to 0 for BCR.  
- Qwen×B3 BCR is on a **prefix of worlds/bundles** (deterministic tail missing) — not a random subsample.  
- Phi is effectively unavailable for inference.  
- No extrapolation of missing cells.

## 6. Missing-data audit

**Not MCAR.** Missingness is structured:

1. **Blocked by model:** Phi ≈ 0.44% of its half-matrix.  
2. **Blocked by system:** B4 and H0 have **zero** completions.  
3. **Deterministic tail:** Qwen×B3 missing is a contiguous suffix of the world/bundle traversal (first gap index 1046; 0 holes before; 214 missing to end).  
4. **Not blocked by tier or query family** as primary cause (near-uniform family/tier %).

Details: `missing_data_audit.json`.

## 7. What conclusions are already justified

### A) Benchmark (cross-query consistency as diagnostic) — INTERIM / partial

Under **Qwen × matched compact flat (B1)** with full H4 subset coverage:

- Per-query Acc is low but **non-zero** (~0.10).  
- **BCR = 0** on all 192 bundles.  
- Acc−BCR gap remains **visible** under a local LLM reader for this one system.  
- This is consistent with the **symbolic** scaled finding that cross-query consistency is diagnostically stricter than Acc — but it is **not** a completed H4 multi-system confirmation.

Symbolic scaled study remains the authority for the frozen `PARTIAL RESEARCH SIGNAL` benchmark claim; Run1 does not reopen or replace it.

### B) Architecture (H0 vs flat / retrieval under LLM readers) — **NOT justified**

Cannot evaluate H4 decision criteria:

- H0 LTKM: **0** predictions.  
- B4 BM25: **0** predictions.  
- Compact-flat vs H0 comparison: **impossible**.  
- Second model family: **not competent coverage**.

### C) Neither (architecture)

Run1 alone supports **neither** an H4-supported nor H4-not-supported architecture verdict.  
Interim paper shape for architecture remains: **do not claim**; keep prior symbolic posture (benchmark-first / structured baseline deferred until LLM matrix completes).

## 8. Threats to validity (Run1)

- Incomplete matrix (23.1%).  
- Schedule-induced missingness (tail / unstarted systems), not random.  
- Extreme abstention may reflect evidence budget / local model competence, not memory-system ranking.  
- Single competent model family in practice (Qwen).  
- Phi legacy cache_key mismatch (operational; logical IDs still used).  
- M1 8GB throughput / thermal drift (~7–17 s/query) — does not change protocol but limited completion.

## 9. Artefacts

Frozen under `outputs/scaled/run1/` (copies; originals under `outputs/scaled/` untouched).  
See `run1_manifest.json` for checksums, config hash, and cache SHA-256.
