#!/usr/bin/env python3
"""Progress-based watchdog for H4-Run2 (Qwen Option A)."""

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
RUN2 = ROOT / "results" / "scaled" / "run2"
CACHE = RUN2 / "llm_reader_cache" / "Qwen2.5-3B-Instruct-4bit.jsonl"
WORKER_LOG = RUN2 / "run2_worker.log"
WATCH_LOG = RUN2 / "run2_watchdog.log"
DONE_MARKER = "RUN2_COMPLETE"
STALL_TIMEOUT_S = 900
MAX_RESTARTS = 8
POLL_S = 60


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    RUN2.mkdir(parents=True, exist_ok=True)
    line = f"{utc_now()} {msg}"
    print(line, flush=True)
    with WATCH_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def cache_state() -> tuple[float, int]:
    if not CACHE.exists():
        return 0.0, 0
    return CACHE.stat().st_mtime, sum(1 for l in CACHE.open() if l.strip())


def worker_pids() -> list[int]:
    """Return PIDs of live Run2 workers.

    Match on ``run_h4_run2.py`` only: the watchdog starts the worker with an
    absolute script path, so ``python scripts/run_h4_run2.py`` never matches
    and previously caused false ``process_dead`` double-starts.
    """
    try:
        out = subprocess.check_output(["pgrep", "-f", "run_h4_run2.py"], text=True)
    except subprocess.CalledProcessError:
        return []
    pids: list[int] = []
    for x in out.split():
        try:
            pid = int(x)
        except ValueError:
            continue
        # Drop the watchdog itself and shell wrappers.
        try:
            cmd = subprocess.check_output(
                ["ps", "-p", str(pid), "-o", "command="], text=True
            ).strip()
        except Exception:
            cmd = ""
        if "watch_h4_run2" in cmd:
            continue
        if "run_h4_run2.py" not in cmd:
            continue
        if "python" not in cmd.lower() and "Python" not in cmd:
            continue
        pids.append(pid)
    return pids


def is_complete() -> bool:
    if WORKER_LOG.exists() and DONE_MARKER in WORKER_LOG.read_text(
        encoding="utf-8", errors="ignore"
    ):
        return True
    comp = RUN2 / "run2_completeness.json"
    if comp.exists():
        try:
            d = json.loads(comp.read_text())
            return bool(d.get("complete")) and (RUN2 / "qwen_h4_findings.md").exists()
        except Exception:
            return False
    return False


def capture_diagnostics(pids: list[int], reason: str) -> Path:
    diag = {
        "timestamp": utc_now(),
        "reason": reason,
        "pids": pids,
        "last_log_lines": [],
        "ps": [],
    }
    if WORKER_LOG.exists():
        diag["last_log_lines"] = WORKER_LOG.read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()[-40:]
    for pid in pids:
        try:
            diag["ps"].append(
                subprocess.check_output(
                    ["ps", "-p", str(pid), "-o", "pid,etime,pcpu,pmem,rss,state"],
                    text=True,
                )
            )
        except Exception as e:
            diag["ps"].append(str(e))
    path = RUN2 / f"run2_stall_diag_{int(time.time())}.json"
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
        logf.write(
            f"\n=== watchdog start {utc_now()} reason={reason} restart={restart_count} ===\n"
        )
        logf.flush()
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "run_h4_run2.py")],
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
    parser.add_argument("--adopt-existing", action="store_true")
    args = parser.parse_args()

    RUN2.mkdir(parents=True, exist_ok=True)
    restarts = 0
    last_signatures: list[str] = []
    last_mtime, last_count = cache_state()
    last_progress_time = time.time()

    pids = worker_pids()
    if pids and args.adopt_existing:
        # Keep a single worker if duplicates somehow exist.
        if len(pids) > 1:
            keep = pids[0]
            log(f"multiple workers at adopt {pids}; keeping {keep}")
            stop_workers([p for p in pids if p != keep])
            pids = worker_pids()
        log(f"adopt existing worker pids={pids} count={last_count}")
    elif not pids:
        pid = start_worker(restarts, "initial")
        log(f"started worker pid={pid}")
        # Grace period: absolute-path workers can lag in pgrep briefly.
        time.sleep(8)
        last_progress_time = time.time()
    elif pids and not args.adopt_existing:
        log(f"worker already running pids={pids}; adopting (no second start)")

    while True:
        if is_complete():
            log("COMPLETE — watchdog exit")
            return 0
        pids = worker_pids()
        if len(pids) > 1:
            keep = min(pids)
            log(f"duplicate workers {pids}; stopping extras, keep {keep}")
            stop_workers([p for p in pids if p != keep])
            pids = worker_pids()
            last_progress_time = time.time()
        mtime, count = cache_state()
        if count > last_count or mtime > last_mtime:
            last_count, last_mtime = count, mtime
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
                stop_workers(pids)
            last_signatures.append(sig)
            if len(last_signatures) >= 3 and len(set(last_signatures[-3:])) == 1:
                log(f"identical failure 3x ({sig}) — stop")
                (RUN2 / "run2_watchdog_failure.json").write_text(
                    json.dumps(
                        {"timestamp": utc_now(), "signature": sig, "restarts": restarts},
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return 2
            if restarts >= args.max_restarts:
                log("max restarts — stop")
                return 2
            restarts += 1
            pid = start_worker(restarts, reason)
            log(f"restarted pid={pid} restart={restarts}")
            last_progress_time = time.time()
            last_mtime, last_count = cache_state()
        time.sleep(args.poll)


if __name__ == "__main__":
    raise SystemExit(main())
