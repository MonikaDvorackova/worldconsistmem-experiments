# H4 Run2 plan (not started)

Run1 is frozen at **2328 / 10080 (23.10%)**.  
Run2 must **not** merge into Run1 files. Use a separate output root (e.g. `outputs/scaled/run2/`) and a distinct run id.

Do **not** regenerate datasets, change prompts, systems, metrics, models, or the H4 subset.

## Goal

Reach the **smallest additional prediction matrix** that restores balanced coverage for the frozen H4 decision — not another blind 10 080-cell run.

## What Run1 already covers (do not redo)

| Cell | Status |
| --- | --- |
| Qwen × B1_flat_cap150_compact | **Complete (1260)** — reuse |
| Qwen × B3_recency_k8 | **1046 / 1260** — finish **214-query tail only** |
| Qwen × B4 / H0 | Missing |
| Phi × B1 | **22** logical (legacy cache_key) — treat as partial; **re-run or continue with current hasher** for remaining 1238 to avoid key fragmentation |
| Phi × B3 / B4 / H0 | Missing |

## Recommended minimum matrices

### Option A — One-model H4 gate (architecture-capable for Qwen only)

Complete Qwen remaining systems only:

| Work | Cells |
| --- | ---: |
| Qwen B3 tail | 214 |
| Qwen B4_bm25_k8 | 1260 |
| Qwen H0_ltkm_cap150_ret8 | 1260 |
| **Total** | **2734** |

**Estimated runtime** at Run1 observed ~193 queries / 30 min: **≈ 7.1 hours**.  
At degraded ~0.06 q/s (~110 / 30 min): **≈ 12–13 hours**.

**Verdict power:** enables H4 criteria on **one** model family → at best **H4 partially supported** (or not supported) per frozen rules; cannot claim two-family support.

### Option B — Two-model balanced H4 (full protocol)

Option A plus Phi full four systems (re-key Phi B1 under current hasher for consistency, or finish remaining 1238 B1 + 3×1260):

| Work | Cells |
| --- | ---: |
| Option A | 2734 |
| Phi B1 remaining (prefer full 1260 re-issue under current key if merging risk) | 1238–1260 |
| Phi B3 + B4 + H0 | 3780 |
| **Total** | **≈ 7752–7774** |

**Estimated runtime** at 193 / 30 min: **≈ 20 hours**.  
At 110 / 30 min: **≈ 35 hours**.

### Option C — Stratified subsample (only if Option A/B infeasible)

If wall-clock still blocks Option A, **do not** invent new systems. Instead freeze a **pre-registered** balanced subsample **before** seeing new outcomes:

- Keep all **18 worlds**.  
- Per world, take a fixed fraction of bundles (e.g. 50% by deterministic bundle_id sort) **identical across all systems**.  
- Still require cells: Qwen × {B1 already done ∩ subsample, B3/B4/H0 on subsample} and preferably Phi × same.

Example: 50% bundles ≈ 630 queries / system → Qwen remaining ≈ `0.5×(214 leftover in B3 ∩ subsample) + 630 + 630` ≈ **1.3–1.5k** cells if B1 subsample already covered — **must be specified in a Run2 pre-registration file before launch**.

Option C weakens precision vs full matrix; mark all results **SUBSAMPLE**.

## Priority order (operational)

1. Finish **Qwen B3 tail (214)** — closes deterministic missingness.  
2. Run **Qwen B4** then **Qwen H0** (single model resident).  
3. Unload Qwen; integrity-smoke Phi; run Phi systems.  
4. Stop when Option A (or B) cell list is complete; then recompute H4 gate on Run2-only + explicit Run1 reuse map.

## Reuse rules

- **Reuse** Run1 Qwen×B1 in full.  
- **Reuse** Run1 Qwen×B3 for the 1046 completed keys; generate only missing keys.  
- **Do not rewrite** Run1 cache files; copy forward into Run2 index by logical key.  
- Phi: prefer regenerating under current `cache_key` for all Phi cells to avoid dual-key ambiguity (22 legacy rows remain archival in Run1 only).

## What Run2 should not do

- No second full 10 080 from scratch.  
- No protocol redesign.  
- No manuscript drafting.  
- No merging Run2 lines into `run1/` artefacts.

## Success criterion for closing H4

At least Option A complete → apply frozen H4 decision tree; paper shape ∈ {BENCHMARK+SYSTEM, BENCHMARK-FIRST WITH STRUCTURED BASELINE, BENCHMARK ONLY, INCOMPLETE} with Run1 cited as interrupted precursor.
