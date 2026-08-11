"""H4 operational runtime helpers (persistence, progress, config hash).

Does not change scientific protocol: same models, prompts, metrics, subset.
Only makes checkpointed resume and progress reporting reliable on M1 8GB.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Frozen decoding tag embedded in cache keys (must stay aligned with run_h4_llm).
PROMPT_TAG = "prompt_v3_k3_mt48"
RUN_ID = "h4_llm"
TEMPERATURE = 0.0
MAX_TOKENS = 48

H4_MODELS = (
    "mlx-community/Qwen2.5-3B-Instruct-4bit",
    "mlx-community/Phi-3.5-mini-instruct-4bit",
)

MEM_SYSTEMS = [
    "B1_flat_cap150_compact",
    "B3_recency_k8",
    "B4_bm25_k8",
    "H0_ltkm_cap150_ret8",
]

REQUIRED_CACHE_FIELDS = (
    "cache_key",
    "model_id",
    "memory_system",
    "query_id",
    "status",
    "predicted_answer",
    "malformed",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def prediction_key(
    model_id: str,
    system_id: str,
    world_id: str,
    bundle_id: str,
    query_id: str,
    run_id: str = RUN_ID,
) -> str:
    """Stable unique key for one H4 prediction cell."""
    material = "|".join(
        [model_id, system_id, run_id, world_id, bundle_id, query_id, PROMPT_TAG]
    )
    return hashlib.sha256(material.encode()).hexdigest()


def cache_key(model_id: str, system: str, query_id: str) -> str:
    """Legacy cache key used by existing jsonl caches (must remain stable)."""
    material = (
        f"{model_id}|{system}|{query_id}|t{TEMPERATURE}|m{MAX_TOKENS}|{PROMPT_TAG}"
    )
    return hashlib.sha256(material.encode()).hexdigest()


def frozen_config_hash(
    *,
    models: tuple[str, ...] = H4_MODELS,
    systems: list[str] | None = None,
    prompt_tag: str = PROMPT_TAG,
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
    max_evidence_items: int = 3,
    evidence_json_cap: int = 1200,
) -> str:
    systems = systems or list(MEM_SYSTEMS)
    payload = {
        "models": list(models),
        "systems": systems,
        "prompt_tag": prompt_tag,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "max_evidence_items": max_evidence_items,
        "evidence_json_cap": evidence_json_cap,
        "run_id": RUN_ID,
        "subset": "first_6_worlds_per_tier_seed100",
    }
    return sha_bytes(json.dumps(payload, sort_keys=True).encode())


def is_valid_cache_row(row: Any) -> bool:
    """True if row is a durable completed cell (success or typed terminal failure)."""
    if not isinstance(row, dict):
        return False
    for k in REQUIRED_CACHE_FIELDS:
        if k not in row:
            return False
    if not row.get("cache_key"):
        return False
    # Typed terminal failures are complete (do not retry forever).
    if row.get("failure_type") == "terminal_timeout_or_error":
        return True
    # Transient/legacy error rows without failure_type are incomplete — retry.
    if row.get("status") == "error":
        return False
    return True


def load_cache_rows(path: Path) -> tuple[dict[str, dict], list[dict[str, Any]]]:
    """Load cache jsonl; last valid row wins per cache_key. Skip corrupt lines."""
    out: dict[str, dict] = {}
    diagnostics: list[dict[str, Any]] = []
    if not path.exists():
        return out, diagnostics
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as e:
                diagnostics.append({"line": i, "error": f"json:{e}"})
                continue
            if not is_valid_cache_row(row):
                diagnostics.append(
                    {
                        "line": i,
                        "error": "invalid_schema_or_error_status",
                        "cache_key": row.get("cache_key") if isinstance(row, dict) else None,
                    }
                )
                continue
            ck = row["cache_key"]
            if ck in out:
                diagnostics.append({"line": i, "error": "duplicate", "cache_key": ck})
            out[ck] = row
    return out, diagnostics


def atomic_append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Append one JSONL record under an exclusive lock with flush/fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    payload = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    # Stage to temp then append under lock (single-line append is atomic enough with lock)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(payload, encoding="utf-8")
    with lock_path.open("a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(tmp.read_text(encoding="utf-8"))
                f.flush()
                os.fsync(f.fileno())
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
    try:
        tmp.unlink(missing_ok=True)
    except TypeError:
        if tmp.exists():
            tmp.unlink()


def write_progress_atomic(path: Path, progress: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    data = json.dumps(progress, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    tmp.write_text(data, encoding="utf-8")
    with tmp.open("r+", encoding="utf-8") as f:
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def rolling_throughput(timestamps: list[float], window_s: float = 1800.0) -> float:
    """Queries completed in the last window_s, scaled to per-30-minutes rate."""
    if not timestamps:
        return 0.0
    now = time.time()
    recent = [t for t in timestamps if now - t <= window_s]
    return float(len(recent))  # already per 30 min if window_s=1800


class ProgressTracker:
    def __init__(
        self,
        path: Path,
        *,
        total_expected: int,
        model: Optional[str] = None,
        system: Optional[str] = None,
        pid: Optional[int] = None,
        restart_count: int = 0,
        last_restart_reason: Optional[str] = None,
    ) -> None:
        self.path = path
        self.total_expected = total_expected
        self.model = model
        self.system = system
        self.pid = pid or os.getpid()
        self.restart_count = restart_count
        self.last_restart_reason = last_restart_reason
        self.completed_valid = 0
        self.skipped_from_cache = 0
        self.newly_generated = 0
        self.failed = 0
        self.last_key: Optional[str] = None
        self.last_query_id: Optional[str] = None
        self.last_completion_ts: Optional[str] = None
        self._completion_times: list[float] = []
        self.timeout_count = 0
        self.batch_since_write = 0

    def note_cache_skip(self, key: str, query_id: str) -> None:
        self.completed_valid += 1
        self.skipped_from_cache += 1
        self.last_key = key
        self.last_query_id = query_id
        self.last_completion_ts = utc_now()
        self.batch_since_write += 1
        if self.batch_since_write >= 50:
            self.flush()

    def note_generated(self, key: str, query_id: str) -> None:
        self.completed_valid += 1
        self.newly_generated += 1
        self.last_key = key
        self.last_query_id = query_id
        self.last_completion_ts = utc_now()
        self._completion_times.append(time.time())
        # keep last ~2h of timestamps
        cutoff = time.time() - 7200
        self._completion_times = [t for t in self._completion_times if t >= cutoff]
        self.batch_since_write += 1
        if self.batch_since_write >= 10:
            self.flush()

    def note_failed(self, key: str, query_id: str) -> None:
        self.failed += 1
        self.last_key = key
        self.last_query_id = query_id
        self.last_completion_ts = utc_now()
        self.timeout_count += 1
        self.flush()

    def to_dict(self) -> dict[str, Any]:
        remaining = max(self.total_expected - self.completed_valid - self.failed, 0)
        thr = rolling_throughput(self._completion_times)
        eta_h = None
        if thr > 0 and remaining > 0:
            eta_h = round(remaining / thr * 0.5, 2)  # thr is per-30min
        return {
            "model": self.model,
            "system": self.system,
            "total_expected": self.total_expected,
            "completed_valid": self.completed_valid,
            "remaining": remaining,
            "failed": self.failed,
            "skipped_from_cache": self.skipped_from_cache,
            "newly_generated": self.newly_generated,
            "last_completed_key": self.last_key,
            "last_query_id": self.last_query_id,
            "last_completion_timestamp": self.last_completion_ts,
            "rolling_queries_per_30min": round(thr, 2),
            "estimated_hours_remaining": eta_h,
            "restart_count": self.restart_count,
            "last_restart_reason": self.last_restart_reason,
            "timeout_count": self.timeout_count,
            "current_process_pid": self.pid,
            "updated_at": utc_now(),
        }

    def flush(self) -> None:
        write_progress_atomic(self.path, self.to_dict())
        self.batch_since_write = 0


def summarize_cache_completeness(
    cache_dir: Path,
    query_ids: list[str],
    model_ids: tuple[str, ...] = H4_MODELS,
    systems: list[str] | None = None,
) -> dict[str, Any]:
    systems = systems or list(MEM_SYSTEMS)
    by_model: dict[str, Any] = {}
    total_expected = len(model_ids) * len(systems) * len(query_ids)
    total_done = 0
    for mid in model_ids:
        slug = mid.split("/")[-1]
        path = cache_dir / f"{slug}.jsonl"
        rows, diag = load_cache_rows(path)
        miss: Counter[str] = Counter()
        done_sys: Counter[str] = Counter()
        for sys in systems:
            for qid in query_ids:
                ck = cache_key(mid, sys, qid)
                if ck in rows:
                    done_sys[sys] += 1
                    total_done += 1
                else:
                    miss[sys] += 1
        by_model[slug] = {
            "unique_valid": len(rows),
            "completed_by_system": dict(done_sys),
            "missing_by_system": dict(miss),
            "missing_total": sum(miss.values()),
            "diagnostics_n": len(diag),
            "duplicates_seen": sum(1 for d in diag if d.get("error") == "duplicate"),
            "corrupt_lines": sum(1 for d in diag if str(d.get("error", "")).startswith("json")),
            "mtime": path.stat().st_mtime if path.exists() else None,
        }
    return {
        "total_expected": total_expected,
        "completed_valid": total_done,
        "remaining": total_expected - total_done,
        "by_model": by_model,
        "updated_at": utc_now(),
    }
