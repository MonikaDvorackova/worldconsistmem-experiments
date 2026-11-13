#!/usr/bin/env python3
"""Independently audit the transferred local rebuttal run artifacts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.rebuttal_temporal import (  # noqa: E402
    CONDITIONS,
    generate_experiment,
    score_response,
    world_clustered_analysis,
)

DATA = ROOT / "experiments" / "rebuttal_temporal_control" / "data"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["world_id"], row["query_id"], row["condition"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=DATA / "raw_predictions.jsonl.gz")
    parser.add_argument("--scored", type=Path, default=DATA / "scored_predictions.jsonl.gz")
    parser.add_argument("--results", type=Path, default=DATA / "evaluation_results.json")
    args = parser.parse_args()

    raw, scored = read_jsonl(args.raw), read_jsonl(args.scored)
    prompts = read_jsonl(DATA / "prompts.jsonl.gz")
    gold = read_jsonl(DATA / "gold_labels.jsonl")
    manifest = json.loads((DATA / "generation_manifest.json").read_text())
    result = json.loads(args.results.read_text())

    prompt_by_key = {key(row): row for row in prompts}
    gold_by_pair = {(r["world_id"], r["query_id"]): r for r in gold}
    expected = set(prompt_by_key)
    raw_keys, scored_keys = [key(r) for r in raw], [key(r) for r in scored]
    assert len(raw_keys) == len(set(raw_keys)) == 800
    assert len(scored_keys) == len(set(scored_keys)) == 800
    assert set(raw_keys) == set(scored_keys) == expected
    assert len({r["world_id"] for r in raw}) == 100
    assert {c: sum(r["condition"] == c for r in raw) for c in CONDITIONS} == {c: 200 for c in CONDITIONS}

    leaks = ("gold_answer", "gold_world", "supporting_event_ids", "applicable_constraints", "answer_key")
    assert not any(any(marker in p["prompt"].lower() for marker in leaks) for p in prompts)
    for row in raw:
        assert row["prompt_sha256"] == prompt_by_key[key(row)]["prompt_sha256"]
        assert row["model_id"] == "mlx-community/Qwen2.5-3B-Instruct-4bit"
        assert row["temperature"] == 0.0 and row["max_tokens"] == 48
        assert row["api_cost_usd"] == 0 and row["backend"] == "mlx-lm local"

    scored_by_key = {key(row): row for row in scored}
    mismatches = []
    for row in raw:
        label = gold_by_pair[(row["world_id"], row["query_id"])]
        expected_score = score_response(row["raw_output"], label["answer"], label["stale_answers"])
        saved = scored_by_key[key(row)]
        for field in ("status", "correct", "stale_state", "normalized_answer"):
            if saved[field] != expected_score[field]:
                mismatches.append({"key": key(row), "field": field})
    assert not mismatches, mismatches[:5]

    stats = world_clustered_analysis(scored)
    assert stats == result["primary"]
    assert hashlib.sha256((DATA / "prompts.jsonl.gz").read_bytes()).hexdigest() == manifest["prompt_sha256"]
    print(json.dumps({
        "audit": "PASS",
        "worlds": 100,
        "queries": 200,
        "conditions": 4,
        "raw_predictions": len(raw),
        "scored_predictions": len(scored),
        "scorer_mismatches": len(mismatches),
        "prompt_gold_leakage": False,
        "prompt_manifest_hash_match": True,
        "recomputed_primary": stats,
        "raw_sha256": sha256(args.raw),
        "scored_sha256": sha256(args.scored),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
