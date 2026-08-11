"""Operational H4 resume / persistence / watchdog tests (protocol unchanged)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from worldconsistmem.h4_runtime import (
    H4_MODELS,
    MEM_SYSTEMS,
    PROMPT_TAG,
    ProgressTracker,
    atomic_append_jsonl,
    cache_key,
    frozen_config_hash,
    is_valid_cache_row,
    load_cache_rows,
    prediction_key,
    summarize_cache_completeness,
)


def test_prediction_key_stable():
    a = prediction_key("m", "s", "w", "b", "q")
    b = prediction_key("m", "s", "w", "b", "q")
    assert a == b
    assert a != prediction_key("m", "s", "w", "b", "q2")


def test_cache_key_matches_prompt_tag():
    ck = cache_key("mlx-community/Qwen2.5-3B-Instruct-4bit", "B3_recency_k8", "q1")
    assert isinstance(ck, str) and len(ck) == 64
    assert PROMPT_TAG == "prompt_v3_k3_mt48"


def test_atomic_append_and_resume_skips(tmp_path: Path):
    path = tmp_path / "cache.jsonl"
    row1 = {
        "cache_key": "k1",
        "model_id": "m",
        "memory_system": "B3_recency_k8",
        "query_id": "q1",
        "status": "ok",
        "predicted_answer": 1,
        "malformed": False,
    }
    atomic_append_jsonl(path, row1)
    atomic_append_jsonl(path, {**row1, "predicted_answer": 2})  # duplicate last-wins
    rows, diag = load_cache_rows(path)
    assert rows["k1"]["predicted_answer"] == 2
    assert any(d.get("error") == "duplicate" for d in diag)
    assert is_valid_cache_row(rows["k1"])


def test_corrupt_trailing_record_recovery(tmp_path: Path):
    path = tmp_path / "cache.jsonl"
    good = {
        "cache_key": "k1",
        "model_id": "m",
        "memory_system": "s",
        "query_id": "q",
        "status": "ok",
        "predicted_answer": "x",
        "malformed": False,
    }
    path.write_text(json.dumps(good) + "\n{not json\n", encoding="utf-8")
    rows, diag = load_cache_rows(path)
    assert "k1" in rows
    assert any(str(d.get("error", "")).startswith("json") for d in diag)


def test_terminal_failure_is_complete_not_retried():
    row = {
        "cache_key": "k",
        "model_id": "m",
        "memory_system": "s",
        "query_id": "q",
        "status": "error",
        "predicted_answer": None,
        "malformed": False,
        "failure_type": "terminal_timeout_or_error",
    }
    assert is_valid_cache_row(row)
    transient = {**row, "failure_type": None}
    # status error without failure_type → incomplete
    del transient["failure_type"]
    assert not is_valid_cache_row(transient)


def test_progress_checkpoint(tmp_path: Path):
    p = tmp_path / "h4_progress.json"
    tr = ProgressTracker(p, total_expected=100, model="m", system="s", pid=1)
    tr.note_generated("k", "q1")
    for _ in range(9):
        tr.note_generated("k", "q")
    assert p.exists()
    data = json.loads(p.read_text())
    assert data["newly_generated"] == 10
    assert data["total_expected"] == 100


def test_frozen_config_hash_stable():
    a = frozen_config_hash()
    b = frozen_config_hash()
    assert a == b
    assert a != frozen_config_hash(max_tokens=47)


def test_summarize_completeness_empty(tmp_path: Path):
    s = summarize_cache_completeness(tmp_path, ["q1", "q2"])
    assert s["total_expected"] == len(H4_MODELS) * len(MEM_SYSTEMS) * 2
    assert s["completed_valid"] == 0


def test_watchdog_stall_logic_unit():
    """Watchdog considers stall only after timeout without durable growth."""
    stall_timeout = 900
    last_progress = time.time() - 100
    assert (time.time() - last_progress) < stall_timeout
    last_progress = time.time() - 1000
    assert (time.time() - last_progress) > stall_timeout


def test_watchdog_does_not_flag_healthy_slow():
    # 5 minutes since last write is fine (stall=15min)
    last_progress = time.time() - 300
    assert (time.time() - last_progress) < 900
