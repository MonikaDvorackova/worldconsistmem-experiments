#!/usr/bin/env python3
"""Progress-based H4 watchdog.

Monitors durable cache growth, not merely process existence.
Does not change scientific protocol.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "scaled"
CACHE = OUT / "llm_reader_cache"
WORKER_LOG = OUT / "h4_worker.log"
WATCH_LOG = OUT / "h4_watchdog.log"
PROGRESS = OUT / "h4_progress.json"
DONE_MARKER = "Freeze checksums unchanged. H4 status:"

# Slowest observed single-query ~256s (Phi); allow generous headroom.
STALL_TIMEOUT_S = 900  # 15 minutes without a new durable prediction
MAX_RESTARTS = 8
POLL_S = 60


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    line = f"{utc_now()} {msg}"
    print(line, flush=True)
    with WATCH_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def cache_mtime_and_count() -> tuple[float, int]:
    newest = 0.0
    total = 0
    if CACHE.exists():
        for p in CACHE.glob("*.jsonl"):
            try:
                newest = max(newest, p.stat().st_mtime)
                with p.open(encoding="utf-8") as f:
                    total += sum(1 for line in f if line.strip())
            except OSError:
                pass
    return newest, total


def worker_pids() -> list[int]:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "python scripts/run_h4_llm.py"], text=True
        )
        return [int(x) for x in out.split() if x.strip()]
    except subprocess.CalledProcessError:
        return []


def is_complete() -> bool:
    for log_path in (WORKER_LOG, OUT / "h4_run.log"):
        if log_path.exists() and DONE_MARKER in log_path.read_text(encoding="utf-8", errors="ignore"):
            return True
    return False


def capture_diagnostics(pids: list[int], reason: str) -> Path:
    diag = {
        "timestamp": utc_now(),
        "reason": reason,
        "pids": pids,
        "progress": None,
        "last_log_lines": [],
        "ps": [],
    }
    if PROGRESS.exists():
        try:
            diag["progress"] = json.loads(PROGRESS.read_text(encoding="utf-8"))
        except Exception as e:
            diag["progress"] = {"error": str(e)}
    for log_path in (WORKER_LOG, OUT / "h4_run.log"):
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            diag["last_log_lines"] = lines[-40:]
            break
    for pid in pids:
        try:
            ps = subprocess.check_output(
                ["ps", "-p", str(pid), "-o", "pid,etime,pcpu,pmem,rss,state"],
                text=True,
            )
            diag["ps"].append(ps)
        except Exception as e:
            diag["ps"].append(str(e))
    path = OUT / f"h4_stall_diag_{int(time.time())}.json"
    path.write_text(json.dumps(diag, indent=2) + "\n", encoding="utf-8")
    return path


def stop_workers(pids: list[int]) -> None:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(5)
    for pid in worker_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def start_worker(restart_count: int, reason: str) -> int:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONFAULTHANDLER"] = "1"
    env["PYTHONPATH"] = str(ROOT / "src")
    env["H4_RESTART_COUNT"] = str(restart_count)
    env["H4_RESTART_REASON"] = reason
    WORKER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with WORKER_LOG.open("a", encoding="utf-8") as logf:
        logf.write(f"\n=== watchdog start {utc_now()} reason={reason} restart={restart_count} ===\n")
        logf.flush()
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "run_h4_llm.py")],
            cwd=str(ROOT),
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return proc.pid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stall-timeout", type=int, default=STALL_TIMEOUT_S)
    parser.add_argument("--max-restarts", type=int, default=MAX_RESTARTS)
    parser.add_argument("--poll", type=int, default=POLL_S)
    parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="Do not start a worker if one is already running",
    )
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    restarts = 0
    last_signatures: list[str] = []
    last_mtime, last_count = cache_mtime_and_count()
    last_progress_time = time.time() if last_count > 0 else time.time()

    pids = worker_pids()
    if pids and args.adopt_existing:
        log(f"adopt existing worker pids={pids} count={last_count}")
    elif not pids:
        pid = start_worker(restarts, "initial")
        log(f"started worker pid={pid}")
        last_progress_time = time.time()

    while True:
        if is_complete():
            log("COMPLETE marker found — watchdog exit")
            return 0

        pids = worker_pids()
        mtime, count = cache_mtime_and_count()
        if count > last_count or mtime > last_mtime:
            last_count = count
            last_mtime = mtime
            last_progress_time = time.time()
            log(f"progress count={count} pids={pids}")

        stalled = (time.time() - last_progress_time) > args.stall_timeout
        dead = not pids

        if dead or stalled:
            reason = "process_dead" if dead else "no_durable_progress"
            sig = f"{reason}:count={count}"
            diag = capture_diagnostics(pids, reason)
            log(f"STALL/DEAD reason={reason} diag={diag}")
            if pids:
                # Only kill on confirmed stall (no durable writes for timeout)
                stop_workers(pids)
            last_signatures.append(sig)
            # identical failure signature limit
            if len(last_signatures) >= 3 and len(set(last_signatures[-3:])) == 1:
                log(f"identical failure repeated 3x ({sig}) — stopping")
                (OUT / "h4_watchdog_failure.json").write_text(
                    json.dumps(
                        {
                            "timestamp": utc_now(),
                            "signature": sig,
                            "restarts": restarts,
                            "count": count,
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return 2
            if restarts >= args.max_restarts:
                log(f"max restarts {args.max_restarts} reached — stopping")
                return 2
            restarts += 1
            pid = start_worker(restarts, reason)
            log(f"restarted worker pid={pid} restart={restarts}")
            last_progress_time = time.time()
            last_mtime, last_count = cache_mtime_and_count()

        time.sleep(args.poll)


if __name__ == "__main__":
    raise SystemExit(main())
