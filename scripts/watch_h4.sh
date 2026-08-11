#!/bin/bash
# Restart H4 if the evaluator dies; resume from cache. Does not touch data/scaled.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG=results/scaled/h4_run.log
WATCH=results/scaled/h4_watchdog.log

done_marker() {
  grep -q 'Freeze checksums unchanged. H4 status:' "$LOG" 2>/dev/null
}

while true; do
  if done_marker; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) COMPLETE — watchdog exit" >> "$WATCH"
    exit 0
  fi
  if pgrep -f 'python scripts/run_h4_llm.py' >/dev/null; then
    n=$(wc -l < results/scaled/llm_reader_cache/Qwen2.5-3B-Instruct-4bit.jsonl 2>/dev/null || echo 0)
    p=$(wc -l < results/scaled/llm_reader_cache/Phi-3.5-mini-instruct-4bit.jsonl 2>/dev/null || echo 0)
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) alive qwen=$n phi=$p" >> "$WATCH"
    sleep 180
    continue
  fi
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) DEAD — restarting" >> "$WATCH"
  echo "" >> "$LOG"
  echo "=== watchdog restart $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG"
  set +e
  PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1 PYTHONPATH=src \
    python scripts/run_h4_llm.py >> "$LOG" 2>&1
  ec=$?
  set -e
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) process_exit=$ec" >> "$WATCH"
  if done_marker; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) COMPLETE — watchdog exit" >> "$WATCH"
    exit 0
  fi
  sleep 10
done
