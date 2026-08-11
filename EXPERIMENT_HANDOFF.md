# WorldConsistMem — Experimental Handoff

This repository contains **experimental infrastructure, benchmark data, tests, and pilot results only**.

The work already present here is **PILOT VALIDATION**, not the required final experimental study. Treat existing numbers as a **reproducible starting point and sanity check**, not as target results to match or defend.

---

## Main empirical question

Does **per-query accuracy systematically overestimate** the quality of a long-term memory system when the same system is evaluated for **joint cross-query consistency** over an evolving world history?

## Secondary question

Do different memory/retrieval strategies exhibit **distinguishable consistency profiles** under **BCR**, **CSR**, and **constraint-family** diagnostics?

---

## Verified existing pilot

The following have been implemented and exercised in this codebase:

| Component | Status in pilot |
|-----------|-----------------|
| Frozen WorldConsistMem benchmark | Yes (`data/smoke/`, `data/scaled/`) |
| Symbolic reader | Yes |
| Recency retrieval | Yes |
| BM25 retrieval | Yes |
| H0 structured/hierarchical reference (LTKM) | Yes |
| Qwen2.5-3B-Instruct-4bit pilot (mlx-lm / Apple Silicon) | Yes (subset) |
| Acc (per-query accuracy) | Yes |
| BCR (bundle consistency rate) | Yes |
| CSR (complementary partial consistency) | Yes (offline recompute) |
| ConsAcc / PConsAcc | Yes |
| Accuracy–consistency gaps | Yes |
| Constraint-family diagnostics | Yes |

Authoritative pilot freeze notes and tables live under `results/scaled/` (notably `FINAL_EXPERIMENT_STATUS.md`, symbolic CSVs, and Qwen H4 artefacts under `results/scaled/run2/`). Historical freeze documents may still say `outputs/`; in this repo those paths are **`results/`**.

### Verified scale

**Full symbolic benchmark**

- 102 worlds  
- 1,088 bundles  
- 7,140 queries  

**LLM pilot subset**

- 18 worlds  
- 192 bundles  
- 1,260 queries  

---

## Collaborator freedom

You are free to determine the final:

- models  
- baselines  
- memory budgets  
- retrieval budgets  
- ablations  
- seeds / number of runs  
- statistical comparisons  
- experimental scale  
- inference stack  

Do **not** treat the pilot’s model choice, subset size, or reported gaps as fixed requirements. The pilot shows that the benchmark and metrics run end-to-end and that accuracy vs consistency can diverge; the definitive study design is yours.

---

## What this repo is / is not

**Is:** runnable generators, metrics, baselines, H0 reference, frozen data, tests, and pilot result artefacts for experimental collaboration.

**Is not:** the theoretical manuscript, publication drafts, planning notes, or other private research materials. Those were intentionally excluded from this handoff.

---

## Reproducibility (exact commands)

From the repository root (see also `README.md`):

```bash
pip install -r requirements.txt
export PYTHONPATH=src

# tests
python -m pytest tests/ -q

# smoke generation
python scripts/generate_smoke.py

# scaled generation
python scripts/generate_scaled.py

# symbolic baselines (smoke)
python scripts/run_baselines.py

# H0 / LTKM (smoke)
python scripts/run_ltkm.py

# scaled symbolic study
python scripts/run_scaled_study.py

# evaluate a predictions JSONL
python scripts/evaluate_predictions.py --predictions path/to/predictions.jsonl

# CSR / partial consistency recompute (frozen predictions; does not redefine BCR)
python scripts/recompute_partial_consistency.py

# existing LLM pilot scripts (optional; mlx-lm / Apple Silicon — may need adaptation)
python scripts/run_h4_llm.py
python scripts/run_h4_run2.py
python scripts/finalize_scaled.py
```

`mlx-lm` is **not** a mandatory dependency for symbolic experiments. The LLM path is optional and platform-specific in the current implementation.

---

## Suggested reading order

1. This file (questions + scope)  
2. `README.md` (install + commands)  
3. `configs/METRIC_FREEZE.md`  
4. `configs/scaled.yaml`  
5. `results/scaled/FINAL_EXPERIMENT_STATUS.md` (pilot freeze; not final-study targets)  
6. `src/worldconsistmem/` + `tests/`
