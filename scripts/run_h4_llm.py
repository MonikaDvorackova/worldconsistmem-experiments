#!/usr/bin/env python3
"""H4 local-LLM reader evaluation only.

Does not regenerate scaled data or modify symbolic system results.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.baselines.adapters import BM25RetrievalMemory, RecencyWeightedMemory
from worldconsistmem.baselines.capacity import CapacityFlatMemory
from worldconsistmem.baselines.load import EXPECTED_SMOKE_SHA256, assert_frozen_smoke, load_bundles
from worldconsistmem.baselines.load import load_observations as load_obs_file
from worldconsistmem.error_decompose import classify_error
from worldconsistmem.evaluate import evaluate_predictions
from worldconsistmem.io_util import read_jsonl, write_csv, write_json, write_jsonl
from worldconsistmem.h4_runtime import (
    PROMPT_TAG,
    RUN_ID,
    ProgressTracker,
    atomic_append_jsonl,
    cache_key as runtime_cache_key,
    frozen_config_hash,
    is_valid_cache_row,
    load_cache_rows,
    prediction_key,
    summarize_cache_completeness,
    utc_now,
    write_progress_atomic,
)
from worldconsistmem.llm_reader import (
    EVIDENCE_JSON_CAP,
    H4_MODELS,
    MAX_EVIDENCE_ITEMS,
    MAX_TOKENS,
    TEMPERATURE,
    MLXLLMReader,
    build_evidence_from_ltkm_pack,
    build_evidence_from_observations,
    format_prompt,
)
from worldconsistmem.ltkm.adapter import LTKMAdapter
from worldconsistmem.ltkm.memory import LTKMConfig
from worldconsistmem.ltkm.retrieval import LTKMRetriever
from worldconsistmem.metrics import answers_equal
from worldconsistmem.models import (
    AnswerSchema,
    ConstraintFamily,
    Prediction,
    Query,
    QueryBundle,
    QueryFamily,
)
from worldconsistmem.observe import generate_observations
from worldconsistmem.scaled_generate import generate_scaled_world
from worldconsistmem.scaled_queries import generate_scaled_bundles
from worldconsistmem.stats_world import bootstrap_ci, mean, world_metric

OUT = ROOT / "results" / "scaled"
DATA = ROOT / "data" / "scaled"
PRED_DIR = OUT / "llm_reader_predictions"
CACHE_DIR = OUT / "llm_reader_cache"
RELAXED = 0.8
SEED = 100
WPT = 34

# Frozen H4 protocol (wired subset; B1 uses compact per H4 decision criteria)
MEM_SYSTEMS = [
    ("B1_flat_cap150_compact", "compact", 150),
    ("B3_recency_k8", "ret", 8),
    ("B4_bm25_k8", "ret", 8),
    ("H0_ltkm_cap150_ret8", "ltkm", 150),
]

FREEZE_PATHS = [
    DATA / "manifest.json",
    DATA / "observations.jsonl",
    DATA / "bundles.jsonl",
    OUT / "system_results.csv",
    OUT / "capacity_results.csv",
    OUT / "dataset_statistics.json",
]


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def freeze_checksums() -> dict[str, str]:
    out = {}
    for p in FREEZE_PATHS:
        if p.exists():
            out[str(p.relative_to(ROOT))] = sha_file(p)
    out["smoke"] = assert_frozen_smoke()
    return out


def load_bundles_from_disk() -> list[QueryBundle]:
    rows = read_jsonl(DATA / "bundles.jsonl")
    bundles = []
    for row in rows:
        queries = []
        for q in row["queries"]:
            queries.append(
                Query(
                    query_id=q["query_id"],
                    bundle_id=q["bundle_id"],
                    family=QueryFamily(q["family"]),
                    text=q["text"],
                    structured=q["structured"],
                    target_time=q.get("target_time"),
                    target_interval=None,
                    gold_answer=q["gold_answer"],
                    answer_schema=AnswerSchema(q["answer_schema"]),
                    applicable_constraints=[
                        ConstraintFamily(c) for c in q["applicable_constraints"]
                    ],
                    supporting_event_ids=q["supporting_event_ids"],
                    supporting_provenance_ids=q["supporting_provenance_ids"],
                    metadata=q.get("metadata") or {},
                )
            )
        bundles.append(
            QueryBundle(
                bundle_id=row["bundle_id"],
                world_id=row["world_id"],
                focal_entities=row["focal_entities"],
                queries=queries,
                description=row.get("description", ""),
                metadata=row.get("metadata") or {},
            )
        )
    return bundles


def make_adapter(name: str):
    if name == "B1_flat_cap150_compact":
        return CapacityFlatMemory(150, "compact_padding", seed=0), "flat"
    if name == "B3_recency_k8":
        return RecencyWeightedMemory(k=8, run_id="recency_k8"), "ret"
    if name == "B4_bm25_k8":
        return BM25RetrievalMemory(k=8, run_id="bm25_k8"), "ret"
    if name == "H0_ltkm_cap150_ret8":
        return (
            LTKMAdapter(
                LTKMConfig(
                    system_id=name,
                    run_id=name,
                    max_logical_records=150,
                    max_retrieval_records=8,
                )
            ),
            "ltkm",
        )
    raise ValueError(name)


def cache_key(model_id: str, system: str, query_id: str) -> str:
    # Stable legacy key — must match existing cache files (prompt_v3_k3_mt48).
    return runtime_cache_key(model_id, system, query_id)


def load_cache(model_slug: str) -> dict[str, dict]:
    path = CACHE_DIR / f"{model_slug}.jsonl"
    rows, _diag = load_cache_rows(path)
    return rows


def append_cache(model_slug: str, row: dict) -> None:
    """Durable append with lock + fsync (operational only; schema unchanged)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    atomic_append_jsonl(CACHE_DIR / f"{model_slug}.jsonl", row)


# Per-query wall-clock bound (seconds). Slowest observed ~256s; 600s is conservative.
QUERY_TIMEOUT_S = int(os.environ.get("H4_QUERY_TIMEOUT_S", "600"))
MAX_QUERY_RETRIES = int(os.environ.get("H4_QUERY_RETRIES", "2"))


def evidence_recall(support_ids: list[str], retrieved_ids: list[str], kind: str) -> float:
    if not support_ids:
        return 1.0
    if kind == "ltkm":
        # LTKM retrieves fact/edge ids; treat non-empty retrieval as partial credit proxy
        return 1.0 if retrieved_ids else 0.0
    # observation ids contain world:obs:t — map support event ids via substring / t
    hits = 0
    for sid in support_ids:
        # event id like wid:e:T — observation wid:obs:T
        if ":e:" in sid:
            t = sid.split(":e:")[-1]
            if any(f":obs:{t}" in rid or rid.endswith(f":{t}") for rid in retrieved_ids):
                hits += 1
        elif any(sid in rid for rid in retrieved_ids):
            hits += 1
    return hits / len(support_ids)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    before = freeze_checksums()
    assert before["smoke"] == EXPECTED_SMOKE_SHA256
    write_json(OUT / "_h4_checksums_before.json", before)
    print("Freeze checksums recorded.", flush=True)

    # Reconstruct ONLY the H4 subset worlds in-memory from frozen seeds.
    # Do not call generate_scaled_dataset (would materialize all 102 worlds).
    # Do not write under data/scaled/.
    print("Loading H4 subset worlds in-memory from frozen seeds (no dataset rewrite)…", flush=True)
    index = json.loads((DATA / "world_index.json").read_text(encoding="utf-8"))
    by_tier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in index:
        by_tier[row["tier"]].append(row)
    subset_rows: list[dict[str, Any]] = []
    for tier in ("small", "medium", "large"):
        subset_rows.extend(by_tier[tier][:6])
    world_list = []
    for row in subset_rows:
        # world_id like ss0100_000 → world_idx from suffix; seed from index
        wid = row["world_id"]
        world_idx = int(wid.rsplit("_", 1)[-1])
        world_list.append(
            generate_scaled_world(int(row["seed"]), world_idx, tier=row["tier"])
        )
        assert world_list[-1].world_id == wid, (world_list[-1].world_id, wid)
    worlds = {w.world_id: w for w in world_list}
    sid = set(worlds)
    # Prefer disk observations/bundles to avoid any drift
    obs_all = load_obs_file(DATA / "observations.jsonl")
    obs_by_world = {wid: obs_all[wid] for wid in sid if wid in obs_all}
    all_bundles = load_bundles_from_disk()
    bundles = [b for b in all_bundles if b.world_id in sid]
    print(
        f"H4 subset: {len(sid)} worlds, {len(bundles)} bundles, "
        f"{sum(len(b.queries) for b in bundles)} queries",
        flush=True,
    )

    n_queries = sum(len(b.queries) for b in bundles)
    total_expected = len(H4_MODELS) * len(MEM_SYSTEMS) * n_queries
    query_ids = [q.query_id for b in bundles for q in b.queries]
    cfg_hash = frozen_config_hash(
        max_evidence_items=MAX_EVIDENCE_ITEMS,
        evidence_json_cap=EVIDENCE_JSON_CAP,
    )
    manifest_hash = sha_file(DATA / "manifest.json")
    write_json(
        OUT / "h4_frozen_config.json",
        {
            "frozen_config_hash": cfg_hash,
            "manifest_sha256": manifest_hash,
            "prompt_tag": PROMPT_TAG,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "max_evidence_items": MAX_EVIDENCE_ITEMS,
            "evidence_json_cap": EVIDENCE_JSON_CAP,
            "models": list(H4_MODELS),
            "systems": [s[0] for s in MEM_SYSTEMS],
            "n_queries": n_queries,
            "total_expected": total_expected,
            "run_id": RUN_ID,
        },
    )
    completeness0 = summarize_cache_completeness(CACHE_DIR, query_ids)
    write_json(OUT / "h4_completeness.json", completeness0)
    print(
        f"Completeness at start: {completeness0['completed_valid']}/{completeness0['total_expected']} "
        f"(remaining {completeness0['remaining']})",
        flush=True,
    )

    progress = ProgressTracker(
        OUT / "h4_progress.json",
        total_expected=total_expected,
        pid=os.getpid(),
        restart_count=int(os.environ.get("H4_RESTART_COUNT", "0")),
        last_restart_reason=os.environ.get("H4_RESTART_REASON"),
    )
    progress.completed_valid = completeness0["completed_valid"]
    progress.flush()

    def refresh_progress_counts() -> None:
        c = summarize_cache_completeness(CACHE_DIR, query_ids)
        progress.completed_valid = c["completed_valid"]
        progress.failed = max(progress.failed, 0)
        write_json(OUT / "h4_completeness.json", c)

    download_report = {
        "mlx_lm": None,
        "mlx": None,
        "models": {},
        "disk_free_gb_start": None,
    }
    import importlib.metadata as md
    import shutil

    download_report["mlx_lm"] = md.version("mlx-lm")
    try:
        download_report["mlx"] = md.version("mlx")
    except Exception:
        download_report["mlx"] = None
    download_report["disk_free_gb_start"] = shutil.disk_usage(str(ROOT)).free / 1e9
    download_report["decoding"] = {
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "early_stop_on_json": True,
        "sampler": "make_sampler(temp=0.0)",
        "path": "mlx_lm.stream_generate",
    }

    # Do NOT smoke-load all models up front (8GB Mac + Metal: probing both
    # leaves fragmented residency). Probe each model immediately before its pass.
    available_models: list[str] = list(H4_MODELS)
    for mid in H4_MODELS:
        hub = Path.home() / ".cache/huggingface/hub" / f"models--{mid.replace('/', '--')}"
        weight_ok = False
        weight_bytes = 0
        if hub.exists():
            for snap in (hub / "snapshots").glob("*"):
                for f in snap.iterdir():
                    if f.name.endswith((".safetensors", ".npz", ".bin", ".gguf")):
                        try:
                            weight_bytes += f.resolve().stat().st_size
                            weight_ok = weight_bytes > 100_000_000
                        except Exception:
                            pass
        download_report["models"][mid] = {
            "model_id": mid,
            "available": weight_ok,  # confirmed at pass start via smoke
            "load_error": None if weight_ok else "weights_missing_or_tiny",
            "smoke_ok": None,
            "smoke_output_preview": None,
            "weight_bytes_on_disk": weight_bytes,
            "cache_dir": str(hub) if hub.exists() else None,
        }

    def _write_download_validation() -> None:
        lines = [
            "# Model download validation (H4)\n\n",
            f"- mlx: `{download_report['mlx']}`\n",
            f"- mlx_lm: `{download_report['mlx_lm']}`\n",
            f"- disk free at start: {download_report['disk_free_gb_start']:.2f} GB\n",
            f"- decoding: `{json.dumps(download_report['decoding'])}`\n",
            f"- evidence_json_cap_chars: {EVIDENCE_JSON_CAP}; max_tokens: {MAX_TOKENS}; "
            f"max_evidence_items: {MAX_EVIDENCE_ITEMS}\n\n",
        ]
        for mid, e in download_report["models"].items():
            lines.append(f"## {mid}\n\n")
            lines.append(f"- available: {e['available']}\n")
            lines.append(f"- load_error: {e.get('load_error')}\n")
            lines.append(f"- smoke_ok: {e.get('smoke_ok')}\n")
            lines.append(f"- smoke_preview: {e.get('smoke_output_preview')!r}\n")
            lines.append(f"- weight_bytes_on_disk: {e.get('weight_bytes_on_disk')}\n")
            hub = Path.home() / ".cache/huggingface/hub" / f"models--{mid.replace('/', '--')}"
            if hub.exists():
                lines.append(f"- cache_dir: `{hub}`\n")
                for snap in (hub / "snapshots").glob("*"):
                    for f in sorted(snap.iterdir()):
                        try:
                            sz = f.resolve().stat().st_size
                        except Exception:
                            sz = -1
                        lines.append(f"  - {f.name}: {sz} bytes\n")
                lines.append("\n")
        (OUT / "model_download_validation.md").write_text("".join(lines), encoding="utf-8")
        write_json(OUT / "model_download_validation.json", download_report)

    _write_download_validation()

    if not available_models:
        prior = {}
        if (OUT / "gate_summary.json").exists():
            prior = json.loads((OUT / "gate_summary.json").read_text())
        write_csv(
            OUT / "llm_reader_results.csv",
            [
                {
                    "reader_model": "NONE",
                    "memory_system": "N/A",
                    "note": "no_models_loaded",
                    "bcr": None,
                    "mean_query_accuracy": None,
                }
            ],
        )
        write_json(
            OUT / "gate_summary.json",
            {
                **prior,
                "verdict": "INCOMPLETE",
                "h4_status": "incomplete",
                "paper": "INCOMPLETE",
                "llm_note": "models unavailable",
            },
        )
        print("INCOMPLETE — no models", flush=True)
        return

    llm_rows = []
    failure_rows = []
    llm_error_rows = []
    stored_events = {
        wid: {o.event_id for o in obs if not o.is_distractor}
        for wid, obs in obs_by_world.items()
        if wid in sid
    }

    for mid in available_models:
        print(f"=== Loading {mid} for H4 pass ===", flush=True)
        reader = MLXLLMReader(mid)
        entry = download_report["models"].setdefault(mid, {"model_id": mid})
        if not reader.available:
            entry["available"] = False
            entry["load_error"] = reader.load_error
            entry["smoke_ok"] = False
            _write_download_validation()
            print("reload failed", reader.load_error, flush=True)
            continue
        try:
            smoke_out = reader.smoke_generate()
            entry["available"] = True
            entry["smoke_ok"] = bool(smoke_out)
            entry["smoke_output_preview"] = smoke_out[:200]
            entry["load_error"] = None
            print(f"  smoke OK: {smoke_out[:80]!r}", flush=True)
        except Exception as e:  # noqa: BLE001
            entry["available"] = False
            entry["smoke_ok"] = False
            entry["load_error"] = f"smoke_fail:{e}"
            _write_download_validation()
            print(f"  smoke fail: {e}", flush=True)
            del reader
            continue
        _write_download_validation()
        model_slug = reader.model_id.split("/")[-1]
        cache = load_cache(model_slug)
        progress.model = reader.model_id
        for sname, _kind_hint, _param in MEM_SYSTEMS:
            adapter, kind = make_adapter(sname)
            print(f"H4 {reader.model_id} × {sname}", flush=True)
            progress.system = sname
            progress.flush()
            preds: list[Prediction] = []
            n_done = 0
            n_cache_hits = 0
            t_sys = time.time()
            by_w = defaultdict(list)
            for b in bundles:
                by_w[b.world_id].append(b)
            for wid, blist in by_w.items():
                adapter.reset()
                for o in obs_by_world[wid]:
                    adapter.ingest(o)
                for b in blist:
                    for q in b.queries:
                        ck = cache_key(reader.model_id, sname, q.query_id)
                        pred_key = prediction_key(
                            reader.model_id, sname, wid, b.bundle_id, q.query_id
                        )
                        cached = cache.get(ck)
                        if cached and is_valid_cache_row(cached):
                            gen = cached
                            rids = gen.get("retrieved_evidence_ids") or []
                            result_answer = gen["predicted_answer"]
                            result_prov = gen.get("predicted_provenance")
                            status = gen["status"]
                            detail = gen.get("detail", "")
                            malformed = gen.get("malformed", False)
                            latency_ms = gen.get("latency_ms", 0.0)
                            prompt_tokens = gen.get("prompt_tokens", 0)
                            evidence_tokens = gen.get("evidence_tokens", 0)
                            raw_output = gen.get("raw_output", "")
                            parsed = gen.get("parsed_output")
                            peak_mem = gen.get("peak_memory_gb")
                            evid_count = gen.get("evidence_count", len(rids))
                            n_cache_hits += 1
                            progress.skipped_from_cache += 1
                            progress.last_key = pred_key
                            progress.last_query_id = q.query_id
                        else:
                            # Generate with bounded wall-clock timeout (operational only).
                            detailed = None
                            last_err = None
                            for attempt in range(1, MAX_QUERY_RETRIES + 2):
                                try:

                                    def _timeout_handler(signum, frame):  # noqa: ARG001
                                        raise TimeoutError(
                                            f"query_timeout_{QUERY_TIMEOUT_S}s"
                                        )

                                    old = signal.signal(signal.SIGALRM, _timeout_handler)
                                    signal.alarm(QUERY_TIMEOUT_S)
                                    try:
                                        if kind == "ltkm":
                                            pack = LTKMRetriever(adapter.memory).retrieve(q)
                                            rids = list(pack.record_ids)[:MAX_EVIDENCE_ITEMS]
                                            evid = build_evidence_from_ltkm_pack(
                                                q, pack.payloads, rids
                                            )
                                        else:
                                            if hasattr(adapter, "retrieve"):
                                                retrieved, _scores = adapter.retrieve(
                                                    q, q.target_time
                                                )
                                            else:
                                                from worldconsistmem.baselines.adapters import (
                                                    RecencyWeightedMemory,
                                                )

                                                tmp = RecencyWeightedMemory(
                                                    k=MAX_EVIDENCE_ITEMS,
                                                    run_id="flat_reader_k",
                                                )
                                                tmp._obs = list(getattr(adapter, "_obs", []))
                                                retrieved, _scores = tmp.retrieve(
                                                    q, q.target_time
                                                )
                                            retrieved = list(retrieved)[:MAX_EVIDENCE_ITEMS]
                                            evid = build_evidence_from_observations(
                                                q, retrieved
                                            )
                                            rids = [o.observation_id for o in retrieved]
                                        detailed = reader.answer_evidence_detailed(evid)
                                    finally:
                                        signal.alarm(0)
                                        signal.signal(signal.SIGALRM, old)
                                    break
                                except TimeoutError as e:
                                    last_err = e
                                    print(
                                        f"  TIMEOUT {q.query_id} attempt={attempt}",
                                        flush=True,
                                    )
                                    progress.timeout_count += 1
                                except Exception as e:  # noqa: BLE001
                                    last_err = e
                                    print(
                                        f"  ERROR {q.query_id} attempt={attempt}: {e}",
                                        flush=True,
                                    )
                            if detailed is None:
                                # Typed terminal failure — not an abstention.
                                status = "error"
                                detail = f"terminal_failure:{last_err}"
                                result_answer = None
                                result_prov = None
                                malformed = False
                                latency_ms = 0.0
                                prompt_tokens = 0
                                evidence_tokens = 0
                                raw_output = ""
                                parsed = None
                                peak_mem = None
                                rids = []
                                evid_count = 0
                                cache_row = {
                                    "cache_key": ck,
                                    "prediction_key": pred_key,
                                    "model_id": reader.model_id,
                                    "memory_system": sname,
                                    "world_id": wid,
                                    "bundle_id": b.bundle_id,
                                    "query_id": q.query_id,
                                    "predicted_answer": result_answer,
                                    "predicted_provenance": result_prov,
                                    "status": status,
                                    "detail": detail,
                                    "malformed": malformed,
                                    "latency_ms": latency_ms,
                                    "prompt_tokens": prompt_tokens,
                                    "evidence_tokens": evidence_tokens,
                                    "raw_output": raw_output,
                                    "parsed_output": parsed,
                                    "peak_memory_gb": peak_mem,
                                    "retrieved_evidence_ids": rids,
                                    "evidence_count": evid_count,
                                    "failure_type": "terminal_timeout_or_error",
                                }
                                append_cache(model_slug, cache_row)
                                cache[ck] = cache_row
                                progress.note_failed(pred_key, q.query_id)
                                with (OUT / "h4_failures.jsonl").open(
                                    "a", encoding="utf-8"
                                ) as ff:
                                    ff.write(
                                        json.dumps(cache_row, sort_keys=True) + "\n"
                                    )
                            else:
                                result_answer = detailed.answer
                                result_prov = detailed.provenance
                                status = detailed.status
                                detail = detailed.detail
                                malformed = detailed.malformed
                                latency_ms = detailed.latency_ms
                                prompt_tokens = detailed.prompt_tokens
                                evidence_tokens = detailed.evidence_tokens
                                raw_output = detailed.raw_output
                                parsed = detailed.parsed
                                peak_mem = detailed.peak_memory_gb
                                evid_count = len(evid.evidence)
                                cache_row = {
                                    "cache_key": ck,
                                    "prediction_key": pred_key,
                                    "model_id": reader.model_id,
                                    "memory_system": sname,
                                    "world_id": wid,
                                    "bundle_id": b.bundle_id,
                                    "query_id": q.query_id,
                                    "predicted_answer": result_answer,
                                    "predicted_provenance": result_prov,
                                    "status": status,
                                    "detail": detail,
                                    "malformed": malformed,
                                    "latency_ms": latency_ms,
                                    "prompt_tokens": prompt_tokens,
                                    "evidence_tokens": evidence_tokens,
                                    "raw_output": raw_output,
                                    "parsed_output": parsed,
                                    "peak_memory_gb": peak_mem,
                                    "retrieved_evidence_ids": rids,
                                    "evidence_count": evid_count,
                                }
                                append_cache(model_slug, cache_row)
                                cache[ck] = cache_row
                                progress.newly_generated += 1
                                progress.last_key = pred_key
                                progress.last_query_id = q.query_id
                                progress.last_completion_ts = utc_now()
                                progress._completion_times.append(time.time())
                                if progress.newly_generated % 10 == 0:
                                    refresh_progress_counts()
                                    progress.flush()

                        correct = answers_equal(result_answer, q.gold_answer) and status not in (
                            "malformed",
                            "error",
                        )
                        recall = evidence_recall(list(q.supporting_event_ids), rids, kind)
                        if correct:
                            err_label = "correct"
                        else:
                            err_label = classify_error(
                                q,
                                Prediction(
                                    b.bundle_id,
                                    q.query_id,
                                    result_answer,
                                    result_prov,
                                    metadata={
                                        "status": status,
                                        "malformed": malformed,
                                        "retrieved_observation_ids": rids,
                                    },
                                ),
                                support_event_ids=list(q.supporting_event_ids),
                                stored_event_ids=stored_events.get(wid),
                                reader_kind=f"llm:{model_slug}",
                            )
                            # refine: if evidence recall high and not abstain → reader failed
                            if (
                                err_label
                                not in (
                                    "malformed_output",
                                    "typed_abstention",
                                    "required_evidence_absent",
                                    "evidence_stored_not_retrieved",
                                )
                                and recall >= 0.5
                                and status == "ok"
                            ):
                                err_label = "reader_failed_on_correct_evidence"

                        pred = Prediction(
                            bundle_id=b.bundle_id,
                            query_id=q.query_id,
                            predicted_answer=result_answer,
                            predicted_provenance=result_prov,
                            system_id=f"LLM:{model_slug}|{sname}",
                            run_id="h4_llm",
                            metadata={
                                "status": status,
                                "detail": detail,
                                "malformed": malformed,
                                "retrieved_observation_ids": rids,
                                "n_retrieved": len(rids),
                                "evidence_count": evid_count,
                                "evidence_tokens": evidence_tokens,
                                "prompt_tokens": prompt_tokens,
                                "latency_ms": latency_ms,
                                "peak_memory_gb": peak_mem,
                                "raw_output": raw_output,
                                "parsed_output": parsed,
                                "reader_model": reader.model_id,
                                "memory_system": sname,
                                "correct": correct,
                                "error_label": err_label,
                                "evidence_recall": recall,
                                "query_family": q.family.value,
                                "world_id": wid,
                            },
                        )
                        preds.append(pred)
                        n_done += 1
                        # Frequent Metal cache clears keep latency stable on 8GB Macs.
                        if n_done % 50 == 0:
                            try:
                                import gc
                                import mlx.core as mx  # type: ignore

                                gc.collect()
                                if hasattr(mx, "clear_cache"):
                                    mx.clear_cache()
                            except Exception:
                                pass
                        if n_done % 50 == 0:
                            elapsed = time.time() - t_sys
                            rate = n_done / max(elapsed, 1e-6)
                            print(
                                f"  … {n_done} queries ({rate:.2f} q/s, {elapsed:.0f}s) "
                                f"cache_hits={n_cache_hits} restarts={progress.restart_count}",
                                flush=True,
                            )
                            refresh_progress_counts()
                            progress.flush()
                        if not correct:
                            failure_rows.append(
                                {
                                    "model": reader.model_id,
                                    "system": sname,
                                    "world_id": wid,
                                    "bundle_id": b.bundle_id,
                                    "query_id": q.query_id,
                                    "family": q.family.value,
                                    "error_label": err_label,
                                    "status": status,
                                    "malformed": malformed,
                                    "evidence_recall": recall,
                                    "gold": q.gold_answer,
                                    "pred": result_answer,
                                    "raw_output": raw_output[:500],
                                }
                            )
                            llm_error_rows.append(
                                {
                                    "system_id": pred.system_id,
                                    "system": sname,
                                    "reader_model": reader.model_id,
                                    "world_id": wid,
                                    "bundle_id": b.bundle_id,
                                    "query_id": q.query_id,
                                    "family": q.family.value,
                                    "difficulty": b.metadata.get("difficulty"),
                                    "tier": b.metadata.get("tier"),
                                    "correct": False,
                                    "error_label": err_label,
                                    "status": status,
                                    "source": "h4_llm",
                                }
                            )

            bms, agg, _ = evaluate_predictions(
                worlds, bundles, preds, relaxed_acc_threshold=RELAXED
            )
            brows = [
                {
                    "bundle_id": m.bundle_id,
                    "world_id": m.world_id,
                    "mean_query_accuracy": m.mean_query_accuracy,
                    "all_correct": m.all_correct,
                    "consistent": m.consistent,
                }
                for m in bms
            ]
            world_ids = sorted(sid)
            bcr_vals = [world_metric(brows, w, "bcr") for w in world_ids]
            acc_vals = [world_metric(brows, w, "mean_acc") for w in world_ids]
            cons_vals = [world_metric(brows, w, "consacc") for w in world_ids]
            bcr_ci = bootstrap_ci(bcr_vals, seed=17)
            acc_ci = bootstrap_ci(acc_vals, seed=17)
            cons_ci = bootstrap_ci(cons_vals, seed=17)

            n_b = len(bms) or 1
            high_inconsist = sum(
                1 for m in bms if m.mean_query_accuracy >= RELAXED and not m.consistent
            ) / n_b
            consist_wrong = sum(
                1 for m in bms if m.consistent and not m.all_correct
            ) / n_b
            abs_rate = sum(1 for p in preds if p.metadata.get("status") == "abstain") / max(
                len(preds), 1
            )
            mal_rate = sum(1 for p in preds if p.metadata.get("malformed")) / max(len(preds), 1)
            reader_fail_rate = sum(
                1
                for p in preds
                if p.metadata.get("error_label") == "reader_failed_on_correct_evidence"
            ) / max(len(preds), 1)
            avg_evid_tok = mean([p.metadata.get("evidence_tokens", 0) for p in preds])
            avg_lat = mean([p.metadata.get("latency_ms", 0) for p in preds])
            avg_recall = mean([p.metadata.get("evidence_recall", 0) for p in preds])

            row = {
                "reader_model": reader.model_id,
                "memory_system": sname,
                "mean_query_accuracy": round(agg.mean_query_accuracy, 4),
                "bcr": round(agg.bcr, 4),
                "consacc_strict": round(agg.consacc_strict, 4),
                "consacc_relaxed": round(agg.consacc_relaxed, 4),
                "bundle_accuracy": round(agg.bundle_accuracy_rate, 4),
                "gap_query": round(agg.gap_mean_acc_minus_bcr, 4),
                "gap_bundle": round(agg.gap_bundle_acc_minus_consacc, 4),
                "high_acc_inconsistent_rate": round(high_inconsist, 4),
                "consistent_wrong_rate": round(consist_wrong, 4),
                "malformed_rate": round(mal_rate, 4),
                "abstention_rate": round(abs_rate, 4),
                "reader_fail_on_evidence_rate": round(reader_fail_rate, 4),
                "avg_evidence_tokens": round(avg_evid_tok, 2),
                "avg_latency_ms": round(avg_lat, 2),
                "avg_evidence_recall": round(avg_recall, 4),
                "bcr_world_mean": round(bcr_ci["mean"], 4),
                "bcr_world_ci95_lo": round(bcr_ci["lo"], 4),
                "bcr_world_ci95_hi": round(bcr_ci["hi"], 4),
                "acc_world_mean": round(acc_ci["mean"], 4),
                "acc_world_ci95_lo": round(acc_ci["lo"], 4),
                "acc_world_ci95_hi": round(acc_ci["hi"], 4),
                "consacc_world_mean": round(cons_ci["mean"], 4),
                "n_worlds": len(sid),
                "n_queries": len(preds),
                "family_accuracy": json.dumps({k: round(v, 4) for k, v in agg.family_accuracy.items()}),
                "constraint_violation_rates": json.dumps(
                    {k: round(v, 4) for k, v in agg.constraint_violation_rates.items()}
                ),
            }
            llm_rows.append(row)
            out_path = PRED_DIR / f"{model_slug}__{sname}.jsonl"
            write_jsonl(out_path, [p.to_dict() for p in preds])
            print(
                f"  Acc={row['mean_query_accuracy']} BCR={row['bcr']} "
                f"mal={row['malformed_rate']} abs={row['abstention_rate']}",
                flush=True,
            )
            write_csv(OUT / "llm_reader_results.csv", llm_rows)

        # Free model before loading the next family
        del reader
        try:
            import gc
            import mlx.core as mx  # type: ignore

            gc.collect()
            if hasattr(mx, "clear_cache"):
                mx.clear_cache()
            elif hasattr(mx, "metal") and hasattr(mx.metal, "clear_cache"):
                mx.metal.clear_cache()
        except Exception:
            pass

    write_csv(OUT / "llm_reader_results.csv", llm_rows)
    write_jsonl(OUT / "llm_reader_failures.jsonl", failure_rows)

    # Merge LLM errors into error_decomposition without removing symbolic rows
    existing_err = []
    err_path = OUT / "error_decomposition.csv"
    if err_path.exists():
        import csv

        with err_path.open() as f:
            existing_err = list(csv.DictReader(f))
        existing_err = [r for r in existing_err if r.get("source") != "h4_llm"]
    merged = existing_err + llm_error_rows
    write_csv(err_path, merged)

    # H4 decision
    h4_status, paper, notes = decide_h4(llm_rows, available_models)
    write_h4_findings(llm_rows, h4_status, paper, notes, download_report, sid, bundles)
    update_gate_and_research(h4_status, paper, notes, llm_rows, before)

    after = freeze_checksums()
    write_json(OUT / "_h4_checksums_after.json", after)
    assert after == before, f"Freeze checksum mismatch: {before} vs {after}"
    # Verify frozen H4 config hash unchanged
    cfg_after = frozen_config_hash(
        max_evidence_items=MAX_EVIDENCE_ITEMS,
        evidence_json_cap=EVIDENCE_JSON_CAP,
    )
    assert cfg_after == cfg_hash, f"H4 config hash changed: {cfg_hash} vs {cfg_after}"
    completeness_final = summarize_cache_completeness(CACHE_DIR, query_ids)
    write_json(OUT / "h4_completeness.json", completeness_final)
    refresh_progress_counts()
    progress.flush()
    print(
        f"Freeze checksums unchanged. H4 status: {h4_status} {paper} "
        f"completeness={completeness_final['completed_valid']}/{completeness_final['total_expected']}",
        flush=True,
    )


def decide_h4(llm_rows: list[dict], readers: list) -> tuple[str, str, dict]:
    notes: dict[str, Any] = {"by_model": {}}
    if not llm_rows or not readers:
        return "incomplete", "INCOMPLETE", notes

    supported_models = []
    partial_models = []
    for model in {r["reader_model"] for r in llm_rows}:
        rows = {r["memory_system"]: r for r in llm_rows if r["reader_model"] == model}
        h0 = rows.get("H0_ltkm_cap150_ret8")
        b3 = rows.get("B3_recency_k8")
        b4 = rows.get("B4_bm25_k8")
        flat = rows.get("B1_flat_cap150_compact")
        if not h0 or not b3 or not b4 or not flat:
            continue
        beats_ret = h0["bcr"] >= b3["bcr"] + 0.10 and h0["bcr"] >= b4["bcr"] + 0.10
        beats_flat = h0["bcr"] >= flat["bcr"] + 0.05 or (
            flat["high_acc_inconsistent_rate"] - h0["high_acc_inconsistent_rate"] >= 0.05
        )
        not_via_abs = h0["abstention_rate"] <= max(b3["abstention_rate"], b4["abstention_rate"], flat["abstention_rate"]) + 0.05
        mal_ok = h0["malformed_rate"] < 0.5 and not (
            h0["malformed_rate"] + 0.1 < min(b3["malformed_rate"], b4["malformed_rate"]) and beats_ret
        )
        # constraint families: use violation rates — lower is better for H0
        try:
            h0_cv = json.loads(h0["constraint_violation_rates"])
            b4_cv = json.loads(b4["constraint_violation_rates"])
            better_families = sum(
                1 for k, v in h0_cv.items() if v + 0.05 < b4_cv.get(k, 1.0)
            )
        except Exception:
            better_families = 0
        across_two = better_families >= 2 or (
            json.loads(h0.get("family_accuracy") or "{}")
            and sum(
                1
                for k, v in json.loads(h0["family_accuracy"]).items()
                if v >= json.loads(b4.get("family_accuracy") or "{}").get(k, 0) + 0.05
            )
            >= 2
        )
        entry = {
            "beats_retrieval": beats_ret,
            "beats_flat_compact": beats_flat,
            "not_via_abstention": not_via_abs,
            "malformed_ok": mal_ok,
            "across_two_families": across_two,
            "h0_bcr": h0["bcr"],
            "flat_bcr": flat["bcr"],
            "b3_bcr": b3["bcr"],
            "b4_bcr": b4["bcr"],
            "h0_abs": h0["abstention_rate"],
            "h0_mal": h0["malformed_rate"],
            "better_constraint_families_vs_b4": better_families,
        }
        notes["by_model"][model] = entry
        if beats_ret and beats_flat and not_via_abs and across_two and mal_ok:
            supported_models.append(model)
        elif beats_ret and not_via_abs and mal_ok:
            partial_models.append(model)

    if supported_models:
        # Still need compact advantage for BENCHMARK+SYSTEM paper shape
        return "supported", "BENCHMARK + SYSTEM", {**notes, "supported_models": supported_models}
    if partial_models:
        return (
            "partial",
            "BENCHMARK-FIRST WITH STRUCTURED BASELINE",
            {**notes, "partial_models": partial_models},
        )
    # check if mostly malformed
    mal = mean([r["malformed_rate"] for r in llm_rows])
    if mal > 0.5:
        return "not_supported", "BENCHMARK ONLY", {**notes, "reason": "reader_failures_dominate"}
    return "not_supported", "BENCHMARK ONLY", notes


def write_h4_findings(llm_rows, h4_status, paper, notes, download_report, sid, bundles):
    lines = [
        "# H4 findings — local LLM reader\n\n",
        f"**H4 status:** `{h4_status}`\n\n",
        f"**Paper shape:** `{paper}`\n\n",
        f"- Models attempted: {list(H4_MODELS)}\n",
        f"- mlx_lm: {download_report.get('mlx_lm')}; mlx: {download_report.get('mlx')}\n",
        f"- Subset: {len(sid)} worlds, {len(bundles)} bundles, "
        f"{sum(len(b.queries) for b in bundles)} queries\n",
        f"- Systems: {[m[0] for m in MEM_SYSTEMS]}\n",
        f"- Decoding: temperature={TEMPERATURE}, max_tokens={MAX_TOKENS}, "
        f"stream_generate JSON early-stop\n\n",
        "## Model × system\n\n",
    ]
    for r in llm_rows:
        lines.append(
            f"- {r['reader_model']} | {r['memory_system']}: "
            f"Acc={r['mean_query_accuracy']} BCR={r['bcr']} "
            f"ConsAcc={r['consacc_strict']} Gap_query={r['gap_query']} "
            f"mal={r['malformed_rate']} abs={r['abstention_rate']} "
            f"BCR_CI[{r['bcr_world_ci95_lo']},{r['bcr_world_ci95_hi']}]\n"
        )
    lines.append("\n## Decision notes\n\n")
    lines.append("```json\n" + json.dumps(notes, indent=2) + "\n```\n")
    (OUT / "h4_findings.md").write_text("".join(lines), encoding="utf-8")


def update_gate_and_research(h4_status, paper, notes, llm_rows, before):
    gate_path = OUT / "gate_summary.json"
    gate = json.loads(gate_path.read_text()) if gate_path.exists() else {}
    # Preserve symbolic fields; update H4 / paper shape
    gate["h4_status"] = h4_status
    gate["llm_advantage"] = h4_status == "supported"
    gate["llm_note"] = json.dumps(notes.get("by_model", notes))[:500]
    gate["paper"] = paper
    if h4_status == "supported":
        gate["verdict"] = "RESEARCH SIGNAL VALIDATED"
    elif h4_status == "partial":
        gate["verdict"] = "PARTIAL RESEARCH SIGNAL"
    elif h4_status == "incomplete":
        gate["verdict"] = "INCOMPLETE"
    else:
        # benchmark distinction still valid from symbolic
        gate["verdict"] = "PARTIAL RESEARCH SIGNAL" if gate.get("gap_persists", True) else "BENCHMARK ONLY"
        if paper == "BENCHMARK ONLY":
            gate["verdict"] = "BENCHMARK ONLY"
    write_json(gate_path, gate)

    # Append H4 section to research_findings without rewriting symbolic core claim block wholesale
    findings_path = OUT / "research_findings.md"
    base = findings_path.read_text() if findings_path.exists() else ""
    # Strip old LLM / drafting paragraphs if present and append fresh H4 block
    marker = "\n## H4 update\n"
    if marker in base:
        base = base.split(marker)[0].rstrip() + "\n"
    h4_block = (
        f"{marker}\n"
        f"- H4 status: `{h4_status}`\n"
        f"- Paper shape: `{paper}`\n"
        f"- Updated verdict: `{gate['verdict']}`\n"
        f"- See `h4_findings.md` and `llm_reader_results.csv`.\n\n"
        f"## Manuscript drafting\n\n"
    )
    if paper == "BENCHMARK + SYSTEM":
        h4_block += "Benchmark + system manuscript drafting **may begin**.\n"
    elif paper == "BENCHMARK-FIRST WITH STRUCTURED BASELINE":
        h4_block += (
            "Benchmark/evaluation drafting **may begin**; present H0 as structured baseline; "
            "remove hierarchy-superiority claims.\n"
        )
    elif paper == "INCOMPLETE":
        h4_block += "H4 incomplete — do not finalize architecture claims.\n"
    else:
        h4_block += "Benchmark-only drafting **may begin**; architecture claims unsupported.\n"
    findings_path.write_text(base + h4_block, encoding="utf-8")

    stats_path = OUT / "statistical_analysis.md"
    stats = stats_path.read_text() if stats_path.exists() else ""
    h4_stats = "\n## H4 — LLM reader (world-level)\n\n"
    for r in llm_rows:
        h4_stats += (
            f"- {r['reader_model']} / {r['memory_system']}: "
            f"Acc={r['mean_query_accuracy']} BCR={r['bcr']} "
            f"CI[{r['bcr_world_ci95_lo']},{r['bcr_world_ci95_hi']}] "
            f"mal={r['malformed_rate']} abs={r['abstention_rate']}\n"
        )
    if "## H4 — LLM reader" in stats:
        pre = stats.split("## H4 — LLM reader")[0].rstrip()
        stats = pre + "\n" + h4_stats
    else:
        stats = stats.rstrip() + "\n" + h4_stats
    stats_path.write_text(stats, encoding="utf-8")


if __name__ == "__main__":
    import faulthandler
    import traceback

    faulthandler.enable()
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
