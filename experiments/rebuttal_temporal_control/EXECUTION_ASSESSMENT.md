# Execution and audit assessment

Date: 2026-11-12. Recorded before any model inference.

## Runtime and model availability

- Work execution host: Linux x86_64, 9.7 GiB RAM, 58 GiB free workspace disk; no Apple Silicon or Metal device.
- Initially installed: no `mlx`, `mlx-lm`, PyTorch, Transformers, llama.cpp, Ollama, or cached Qwen checkpoint. A zero-cost CPU MLX software check was later run in an isolated `uv` environment.
- The repository's earlier model-download report records the model identifier and file size, but does not record a Hub revision or a weights checksum. The requested protocol names `mlx-community/Qwen2.5-3B-Instruct-4bit` but does not contain an immutable model revision. The public checkpoint page currently identifies commit `4f83f8f146fdf28b512a06562b671d7af4fab457`; the repository's earlier run artifacts do not establish that this was their revision.
- The local cache scan found no `model.safetensors` or GGUF model weights. No model weights were downloaded.

## CPU backend assessment

The local CPU route can use MLX itself rather than convert the checkpoint to another format. For assessment only, an isolated `uv` invocation installed `mlx-lm[cpu]==0.32.2` and its `mlx-cpu==0.32.4` dependency. On this x86_64 host, the MLX default device was CPU, an MLX array computation passed, and the `mlx_lm.load`, `stream_generate`, and temperature-zero sampler APIs imported successfully. The official model card identifies the checkpoint as Qwen2.5-3B-Instruct converted to MLX format; its config specifies Qwen2 (`model_type=qwen2`), 4-bit weights and group size 64. The MLX-LM loader is the native loader documented for this checkpoint.

The isolated CPU check reported `mlx=0.32.4`, `mlx-lm=0.32.2`, `default_device=Device(cpu, 0)`, and `[1,2,3] + 1 = [2,3,4]`; `mlx_lm.load`, `stream_generate`, and the temperature-zero sampler imported successfully. This establishes a technically plausible zero-cost, same-format CPU execution route. It does **not** verify loading or generating with the target checkpoint here: the exact weights are absent, the previously used revision was not recorded, and the frozen protocol says to stop and have the user install absent weights locally. The optional CPU route would also be a documented hardware/runtime deviation from Apple Silicon + MLX-LM 0.31.3, and would need a real local model smoke test before the full run. No model inference was attempted.

`llama.cpp` was not selected. Its native input format is GGUF; converting the MLX checkpoint would change the representation and might alter quantization. No exact same-quantization GGUF file was found, so equivalence could not be verified.

## Deviation status

No deviation was used for model execution. The experiment implementation is backend-independent at the prompt/scoring layers and includes a local-only MLX runner. It accepts only a local model directory plus a manifest with a pinned revision and weight SHA-256, sets Hub offline flags, and never passes a repository identifier to the loader. The CPU MLX assessment is documented as an unexecuted fallback. The full run remains blocked until the exact intended model snapshot and immutable revision/checksum are available locally and pass the runner's preflight and smoke test.

Official compatibility references:

- MLX-LM documents model loading and its optional CPU dependency: <https://github.com/ml-explore/mlx-lm/blob/main/pyproject.toml>
- The checkpoint card documents MLX-LM loading and its model configuration: <https://huggingface.co/mlx-community/Qwen2.5-3B-Instruct-4bit/tree/4f83f8f146fdf28b512a06562b671d7af4fab457>
- llama.cpp documents that its model input must be GGUF: <https://github.com/ggml-org/llama.cpp/blob/master/docs/models.md>

## Synthetic preparation

The fixed namespace generated 100 new large-tier worlds, 200 latest-state questions (CEO and owner), and 800 prompts (four conditions per question). Every world has at least three realized CEO replacements and three focal-project ownership transfers. Each prompt includes all CEO/ownership records from its generated world plus eight deterministic distractor events. No world ID overlapped either the existing scaled-world index or the 18 H4 evaluation world IDs in `analysis/round2/temporal_state_analysis.csv`. Gold labels are stored separately from prompt inputs. Condition renderings are round-trip checked against the same normalized initial facts and complete selected event facts. Prompt hashes, input lengths, generation seeds, and randomized per-world inference order are recorded in `data/generation_manifest.json` and the JSONL files. The local runner records tokenizer counts and tests whether within-world B−C accuracy differences track within-world token-count differences; this check cannot be performed until inference exists.

## Existing stale-state count audit

The tracked summary supports stale-state counts of F0 23/42, F1 17/42, F2 2/42, and F3 7/42. Stale is defined as matching an earlier position without matching the latest. The separate paired latest-selection tables imply arm-level latest-selection margins of 19/42, 16/42, 38/42, and 35/42. These are not complements of stale counts: a response may match both earliest and latest, or neither. `analysis/round2/final/FINAL_CLAIMS_VERIFIED.md` previously listed 17 and 32 as the F0 and F2 latest margins; these are concordant-pair cells, not arm margins, and have been corrected to 19 and 38. The private item-level source used for the earlier audit is intentionally absent from this checkout, so this reconciliation is from the committed audit summary and paired tables, not a new raw-record reproduction.

## Result status

No model outputs, treatment effects, confidence intervals, or p-values exist for this follow-up. Do not present the synthetic generator or scorer tests as empirical model evidence. The manuscript and reviewer text in `DRAFT_REBUTTAL.md` explicitly state this limitation.
