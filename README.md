# WorldConsistMem Experiments

Standalone experimental infrastructure, frozen benchmark data, tests, and pilot results for **WorldConsistMem** — a benchmark for **cross-query consistency** over evolving synthetic worlds.

This repository is an **experimental handoff**. Existing results are **pilot validation**, not the required final experimental study. See [`EXPERIMENT_HANDOFF.md`](EXPERIMENT_HANDOFF.md).

Pilot artefacts that previously lived under `outputs/` are shipped here under `results/`. Runtime scripts write to `results/`.

## Install

Uses [uv](https://docs.astral.sh/uv/) with a `pyproject.toml` (src layout, editable install — no `PYTHONPATH` needed):

```bash
cd worldconsistmem-experiments
uv sync
```

This installs the `worldconsistmem` package plus runtime deps (`PyYAML`) and the dev group (`pytest`). Without uv: `pip install -e '.[llm]'` or `pip install -e .` in a venv.

### Optional: local LLM reader (Apple Silicon)

The existing LLM pilot uses **mlx-lm** on Apple Silicon (`mlx-community/Qwen2.5-3B-Instruct-4bit`). That stack is **not** required for symbolic experiments, tests, smoke/scaled generation, baselines, H0, prediction evaluation, or CSR recomputation. Collaborators may adapt or replace the inference stack.

```bash
# optional, Apple Silicon only — versions used in the pilot notes:
# mlx 0.32.0 / mlx-lm 0.31.3 (see results/scaled/model_download_validation.md)
uv sync --extra llm
```

## Tests

```bash
uv run pytest tests/ -q
```

## Reproduce / regenerate (from repo root)

### Smoke generation

```bash
uv run python scripts/generate_smoke.py
```

Writes `data/smoke/` and metrics under `results/` (including validation artefacts).

### Scaled generation

```bash
uv run python scripts/generate_scaled.py
```

Writes `data/scaled/` using `configs/scaled.yaml` (smoke left untouched).

### Symbolic baselines (smoke)

```bash
uv run python scripts/run_baselines.py
```

Writes `results/baselines/`.

### H0 / LTKM reference (smoke)

```bash
uv run python scripts/run_ltkm.py
```

Writes `results/ltkm/`.

### Scaled symbolic study

```bash
uv run python scripts/run_scaled_study.py
```

Writes predictions and tables under `results/scaled/`.

### Prediction evaluation

```bash
uv run python scripts/evaluate_predictions.py \
  --predictions results/baselines/B3_recency_retrieval_predictions.jsonl
```

Optional flags: `--bundles`, `--seed`, `--n-worlds`, `--out` (default `results/eval_metrics.json`).

### CSR / partial consistency recomputation

Offline only; does **not** redefine BCR. Recomputes CSR, violations/bundle, and PConsAcc from frozen predictions:

```bash
uv run python scripts/recompute_partial_consistency.py
```

Writes `results/scaled/partial_consistency_*.csv` and `partial_consistency_findings.md`.

### Existing LLM experiment (optional; mlx-lm / Apple Silicon)

Pilot H4 runner and Qwen completion scripts:

```bash
uv run python scripts/run_h4_llm.py
uv run python scripts/run_h4_run2.py
uv run python scripts/finalize_scaled.py
```

These expect local mlx-lm model availability and may need adaptation on non-Apple platforms.

## Layout

| Path | Contents |
|------|----------|
| `src/worldconsistmem/` | Generator, constraints, metrics, CSR/partial, baselines, H0/LTKM, LLM reader |
| `scripts/` | Smoke/scaled generation, baselines, H0, scaled study, H4, CSR recompute |
| `configs/` | Smoke / scaled / LTKM configs + metric freeze notes |
| `tests/` | Unit/integration tests including CSR and frozen integrity hashes |
| `data/smoke/`, `data/scaled/` | Frozen benchmark datasets |
| `results/baselines/`, `results/ltkm/`, `results/scaled/` | Pilot experimental outputs |
| `EXPERIMENT_HANDOFF.md` | Collaborator brief: questions, verified pilot, freedom of design |

## Freeze references

- Metric freeze: `configs/METRIC_FREEZE.md`
- Experiment freeze notes: `results/scaled/FINAL_EXPERIMENT_STATUS.md`
- Smoke checksum: `3aa67ed1b6a39be3d9e1805d14f7d5ce7cc05f4655bdce0bc4ff49900c14c7ab`
