# H4 execution-state inspection (pre-resume operational fix)

Recorded while worker PID 75170 was still healthy on Qwen×B3.

## Active processes (at inspection)

* `python scripts/run_h4_llm.py` — primary worker (loaded Qwen only).
* `python scripts/watch_h4.py --adopt-existing` — progress-based watchdog (harness-managed).
* Prior incomplete runs died under M1 8GB memory pressure / shell lifecycle; weak existence-only watchdog.

## Expected matrix

* Models: 2 (`Qwen2.5-3B-Instruct-4bit`, `Phi-3.5-mini-instruct-4bit`)
* Systems: 4 (`B1_flat_cap150_compact`, `B3_recency_k8`, `B4_bm25_k8`, `H0_ltkm_cap150_ret8`)
* Queries (H4 subset): 1260 (18 worlds × frozen bundles)
* **Total expected predictions: 10080**

## Cache at B1 completion / B3 start

| Model | Lines | Unique valid | Duplicates | Corrupt |
| --- | ---: | ---: | ---: | ---: |
| Qwen2.5-3B-Instruct-4bit | ≥1260 | B1 complete | 0 | 0 |
| Phi-3.5-mini-instruct-4bit | 22 | 22 (old partial B1) | 0 | 0 |

* Last B1 metrics (Qwen): Acc=0.096, BCR=0.0, mal=0.0071, abs=0.7278
* Throughput observed: ~193 queries / 30 min when healthy; ~7–11 s/query on M1 8GB.

## Model integrity

* Qwen `model.safetensors`: 1 736 293 090 bytes — complete; smoke OK at worker start.
* Phi `model.safetensors`: 2 149 696 133 bytes — complete; smoke deferred until Qwen unload (single-model policy).
* mlx / mlx_lm: see `model_download_validation.md`.

## Root cause of prior incomplete run

1. **Memory pressure on M1 8GB** (Docker + dual-model probes) → process kills / thrashing.
2. **Watchdog monitored process existence only**, not durable prediction growth; nohup watchdogs died with parent shells.
3. **Non-atomic append** risked truncated trailing lines on kill (not observed as corrupt in current cache).
4. **No `h4_progress.json`** / completeness gate → hard to resume operationally.

## Operational fixes applied (protocol unchanged)

* `h4_runtime.py`: atomic locked append + fsync; valid-row loader; progress tracker; frozen config hash; completeness summary.
* `run_h4_llm.py`: resume skips valid keys; SIGALRM per-query timeout (600s) with typed terminal failures; progress/completeness files.
* `watch_h4.py`: stall = no durable cache growth for 900s; finite restarts; adopts healthy workers.
* Tests: `tests/test_h4_resume.py` + existing `tests/test_h4_llm.py`.

Scientific inputs (subset, systems, prompts, decoding, metrics) were **not** changed.
