#!/usr/bin/env python3
"""Generate, validate, or run the frozen local-only rebuttal experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import gzip
import importlib.metadata
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.rebuttal_temporal import (  # noqa: E402
    CONDITIONS, MODEL_ID, N_WORLDS, TEMPERATURE, MAX_TOKENS,
    generate_experiment, parse_response, score_response, validate_scorer,
    world_clustered_analysis,
)

EXPERIMENT = ROOT / "experiments" / "rebuttal_temporal_control"
DATA = EXPERIMENT / "data"


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows).encode()
    if path.suffix == ".gz":
        with path.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
                stream.write(payload)
        hashed = path.read_bytes()
    else:
        path.write_bytes(payload)
        hashed = payload
    return sha256_bytes(hashed)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as stream:
            return [json.loads(line) for line in stream if line.strip()]
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def generate() -> None:
    generation_started = time.perf_counter()
    prompts, gold = generate_experiment(N_WORLDS)
    known_ids = {r["world_id"] for r in json.loads((ROOT / "data/scaled/world_index.json").read_text())}
    h4_path = ROOT / "analysis/round2/temporal_state_analysis.csv"
    with h4_path.open(newline="") as f:
        h4_ids = {r["world_id"] for r in csv.DictReader(f) if r.get("world_id")}
    generated_ids = {r["world_id"] for r in gold}
    scaled_overlap, h4_overlap = known_ids & generated_ids, h4_ids & generated_ids
    if scaled_overlap or h4_overlap:
        raise SystemExit(f"ABORT: generated world overlap: scaled={sorted(scaled_overlap)}, H4={sorted(h4_overlap)}")
    prompt_sha = write_jsonl(DATA / "prompts.jsonl.gz", prompts)
    prompt_index = [{k: v for k, v in row.items() if k != "prompt"} for row in prompts]
    prompt_index_sha = write_jsonl(DATA / "prompt_index.jsonl", prompt_index)
    gold_sha = write_jsonl(DATA / "gold_labels.jsonl", gold)
    scorer = validate_scorer()
    manifest = {
        "status": "GENERATED_NO_MODEL_INFERENCE",
        "generation_elapsed_seconds": time.perf_counter() - generation_started,
        "protocol": "experiments/rebuttal_temporal_control/PROTOCOL.md",
        "namespace": "rebuttal-temporal-v1",
        "n_worlds": len({r["world_id"] for r in gold}),
        "queries_per_world": 2,
        "prompt_rows": len(prompts),
        "conditions": list(CONDITIONS),
        "prompt_sha256": prompt_sha,
        "prompt_index_sha256": prompt_index_sha,
        "gold_labels_sha256": gold_sha,
        "gold_labels_are_separate_from_prompts": True,
        "existing_scaled_world_overlap": 0,
        "existing_h4_worlds_checked": len(h4_ids),
        "existing_h4_world_overlap": 0,
        "scorer_validation": scorer,
        "min_realized_ceo_replacements": min(r["n_ceo_replacements"] for r in gold),
        "min_realized_ownership_transfers": min(r["n_ownership_transfers"] for r in gold),
        "max_seed_attempt": max(r["seed_attempt"] for r in gold),
        "mean_prompt_characters_by_condition": {
            c: sum(r["prompt_chars"] for r in prompts if r["condition"] == c) / sum(1 for r in prompts if r["condition"] == c)
            for c in CONDITIONS
        },
        "randomization": "seed derived per world from frozen namespace; all 8 query-condition calls shuffled within world with Python Random(selected_world_seed XOR 0x5A17C0DE)",
        "fixed_seed_rule": "candidate seed = 1,000,000 + int(SHA256(namespace:index:attempt)[0:12],16) mod 8,000,000; accept first candidate meeting >=3 realized CEO replacements and >=3 ownership transfers",
    }
    (DATA / "generation_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2))


def verify_model(model_dir: Path, metadata_path: Path) -> tuple[dict[str, Any], Path]:
    if not model_dir.is_dir():
        raise SystemExit(f"LOCAL MODEL NOT FOUND: {model_dir}")
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("model_id") != MODEL_ID:
        raise SystemExit(f"MODEL ID MISMATCH: expected {MODEL_ID}")
    if not metadata.get("revision") or metadata["revision"] in {"main", "latest"}:
        raise SystemExit("MODEL REVISION MUST BE A PINNED COMMIT SHA")
    if metadata.get("quantization") != "4-bit" or not metadata.get("weights_sha256"):
        raise SystemExit("MODEL METADATA MUST VERIFY the 4-bit quantization and weights_sha256")
    weights = model_dir / "model.safetensors"
    if not weights.is_file():
        raise SystemExit("MODEL CHECKPOINT MISSING model.safetensors")
    digest = hashlib.sha256()
    with weights.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != metadata["weights_sha256"]:
        raise SystemExit("WEIGHT HASH MISMATCH")
    for required in ("config.json", "tokenizer.json", "tokenizer_config.json"):
        if not (model_dir / required).is_file():
            raise SystemExit(f"MODEL CHECKPOINT MISSING {required}")
    config = json.loads((model_dir / "config.json").read_text())
    if config.get("model_type") != "qwen2":
        raise SystemExit(f"MODEL CONFIG TYPE MISMATCH: {config.get('model_type')!r}")
    quant = config.get("quantization", {})
    if quant.get("bits") != 4 or quant.get("group_size") != 64:
        raise SystemExit(f"MODEL QUANTIZATION MISMATCH: expected 4-bit group_size=64, got {quant!r}")
    return metadata, weights


def run_inference(model_dir: Path, metadata_path: Path) -> None:
    # This runner is intentionally local path only: repo IDs cannot be passed to
    # mlx_lm.load, and HF offline flags are set before importing MLX-LM.
    prompts_path = DATA / "prompts.jsonl.gz"
    if not prompts_path.is_file():
        raise SystemExit("Generate and validate the frozen dataset first")
    metadata, _weights = verify_model(model_dir, metadata_path)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        import mlx.core as mx  # type: ignore
        from mlx_lm import load, stream_generate  # type: ignore
        from mlx_lm.sample_utils import make_sampler  # type: ignore
    except Exception as exc:
        raise SystemExit(f"LOCAL MLX BACKEND UNAVAILABLE: {exc}") from exc
    model, tokenizer = load(str(model_dir.resolve()))
    prompts = read_jsonl(prompts_path)
    config = json.loads((model_dir / "config.json").read_text())
    context_limit = int(config.get("max_position_embeddings", 32768))
    prepared = []
    for row in prompts:
        rendered = tokenizer.apply_chat_template(
            [{"role": "user", "content": row["prompt"]}], tokenize=False, add_generation_prompt=True
        ) if hasattr(tokenizer, "apply_chat_template") else row["prompt"]
        prompt_tokens = len(tokenizer.encode(rendered))
        if prompt_tokens + MAX_TOKENS > context_limit:
            raise SystemExit(f"PROMPT EXCEEDS CONTEXT BEFORE INFERENCE: {row['query_id']} {row['condition']} ({prompt_tokens}+{MAX_TOKENS}>{context_limit})")
        prepared.append((row, rendered, prompt_tokens))
    predictions = []
    started = time.perf_counter()
    sampler = make_sampler(temp=TEMPERATURE)
    for row, rendered, prompt_tokens in prepared:
        t0 = time.perf_counter()
        raw = ""
        for chunk in stream_generate(model, tokenizer, prompt=rendered, max_tokens=MAX_TOKENS, sampler=sampler):
            raw += chunk.text
            if "}" in raw:
                break
            if any(mark in raw for mark in ("<|im_end|>", "<|end|>", "<|endoftext|>")):
                break
        answer, status = parse_response(raw)
        predictions.append({
            "world_id": row["world_id"], "query_id": row["query_id"],
            "condition": row["condition"], "prompt_sha256": row["prompt_sha256"],
            "raw_output": raw, "normalized_answer": answer, "status": status,
            "latency_seconds": time.perf_counter() - t0,
            "prompt_tokens": prompt_tokens, "generation_tokens": len(tokenizer.encode(raw)),
            "peak_memory_gb": float(mx.get_peak_memory() / (1024 ** 3)),
            "model_id": MODEL_ID, "model_revision": metadata["revision"],
            "model_weights_sha256": metadata["weights_sha256"],
            "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
            "backend": "mlx-lm local", "mlx_lm_version": importlib.metadata.version("mlx-lm"),
            "mlx_version": importlib.metadata.version("mlx"), "api_cost_usd": 0,
        })
    elapsed = time.perf_counter() - started
    write_jsonl(DATA / "raw_predictions.jsonl", predictions)
    score_and_report(predictions, elapsed, metadata)


def score_and_report(predictions: list[dict[str, Any]], elapsed: float, model: dict[str, Any]) -> None:
    # Gold labels are loaded only after all inference has completed.
    gold = {(r["query_id"], r["world_id"]): r for r in read_jsonl(DATA / "gold_labels.jsonl")}
    expected = {(r["query_id"], r["world_id"], r["condition"]) for r in read_jsonl(DATA / "prompts.jsonl.gz")}
    observed = [(r["query_id"], r["world_id"], r["condition"]) for r in predictions]
    if len(observed) != len(set(observed)) or set(observed) != expected:
        raise ValueError("prediction coverage mismatch; complete the run before analysis")
    scored = []
    for row in predictions:
        label = gold[(row["query_id"], row["world_id"])]
        result = score_response(row["raw_output"], label["answer"], label["stale_answers"])
        scored.append({**row, "correct": result["correct"], "stale_state": result["stale_state"], "gold_answer": label["answer"]})
    write_jsonl(DATA / "scored_predictions.jsonl", scored)
    stats = world_clustered_analysis(scored)
    by_condition = {}
    for condition in CONDITIONS:
        subset = [r for r in scored if r["condition"] == condition]
        by_condition[condition] = {
            "n_queries": len(subset),
            "semantic_correct": sum(r["correct"] for r in subset),
            "semantic_accuracy": sum(r["correct"] for r in subset) / len(subset) if subset else None,
            "stale_state": sum(r["stale_state"] for r in subset),
            "format_valid": sum(r["status"] in {"ok", "abstain"} for r in subset),
            "mean_prompt_tokens": sum(r["prompt_tokens"] for r in subset) / len(subset) if subset else None,
            "mean_generation_tokens": sum(r["generation_tokens"] for r in subset) / len(subset) if subset else None,
        }
    depth_breakdown = {}
    for condition in CONDITIONS:
        for kind in ("ceo", "owner"):
            subset = [r for r in scored if r["condition"] == condition and gold[(r["query_id"], r["world_id"])]["question_kind"] == kind]
            depth_breakdown[f"{condition}_{kind}"] = {
                "n_queries": len(subset), "semantic_correct": sum(r["correct"] for r in subset),
                "stale_state": sum(r["stale_state"] for r in subset),
            }
    report = {
        "status": "COMPLETED_LOCAL_INFERENCE",
        "n_predictions": len(predictions), "elapsed_seconds": elapsed,
        "primary": stats, "descriptive_by_condition": by_condition,
        "descriptive_by_query_type": depth_breakdown, "model": model,
    }
    (DATA / "evaluation_results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2))


def validate() -> None:
    prompts = read_jsonl(DATA / "prompts.jsonl.gz")
    gold = read_jsonl(DATA / "gold_labels.jsonl")
    generated_ids = {r["world_id"] for r in gold}
    scaled_ids = {r["world_id"] for r in json.loads((ROOT / "data/scaled/world_index.json").read_text())}
    with (ROOT / "analysis/round2/temporal_state_analysis.csv").open(newline="") as f:
        h4_ids = {r["world_id"] for r in csv.DictReader(f) if r.get("world_id")}
    if generated_ids & scaled_ids or generated_ids & h4_ids:
        raise SystemExit("generated worlds overlap existing scaled/H4 evaluation data")
    if len({r["world_id"] for r in gold}) != N_WORLDS:
        raise SystemExit("expected exactly 100 unique worlds")
    if len(gold) != 2 * N_WORLDS or len(prompts) != 8 * N_WORLDS:
        raise SystemExit("unexpected query or prompt row count")
    by_world_query: dict[tuple[str, str], list[dict[str, Any]]] = {}
    gold_keys = {(g["world_id"], g["query_id"]) for g in gold}
    for p in prompts:
        if (p["world_id"], p["query_id"]) not in gold_keys:
            raise SystemExit("prompt missing gold-table pair")
        if any(k in p["prompt"].lower() for k in ("gold_answer", "answer_key", "supporting_event_ids")):
            raise SystemExit("prompt contains gold-label field")
        by_world_query.setdefault((p["world_id"], p["query_id"]), []).append(p)
    for key, rows in by_world_query.items():
        if {r["condition"] for r in rows} != set(CONDITIONS):
            raise SystemExit(f"condition coverage failure: {key}")
        if len({r["question_kind"] for r in rows}) != 1:
            raise SystemExit(f"question mismatch across conditions: {key}")
    print(json.dumps({"valid": True, "worlds": 100, "queries": 200, "prompts": 800, "scaled_overlap": 0, "h4_reference_worlds_checked": len(h4_ids), "h4_overlap": 0, "scorer": validate_scorer()}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate")
    sub.add_parser("validate")
    pre = sub.add_parser("preflight")
    pre.add_argument("--model-dir", type=Path, required=True)
    pre.add_argument("--metadata", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--model-dir", type=Path, required=True)
    run.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "generate":
        generate()
    elif args.command == "validate":
        validate()
    elif args.command == "preflight":
        meta, weights = verify_model(args.model_dir, args.metadata)
        try:
            import mlx_lm  # type: ignore
        except Exception as exc:
            raise SystemExit(f"MODEL CHECKPOINT VERIFIED; MLX BACKEND UNAVAILABLE: {exc}")
        print(json.dumps({"model_id": meta["model_id"], "revision": meta["revision"], "weights": str(weights), "mlx_lm": importlib.metadata.version("mlx-lm"), "platform": platform.platform()}, indent=2))
    else:
        run_inference(args.model_dir, args.metadata)


if __name__ == "__main__":
    main()
