#!/usr/bin/env python3
"""H4-Run2 Option A: Qwen-only completion of missing cells.

Does not modify Run1 artefacts or regenerate the scaled benchmark.
Protocol (prompt, decoding, systems, subset) is frozen.
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
from worldconsistmem.baselines.load import EXPECTED_SMOKE_SHA256, assert_frozen_smoke
from worldconsistmem.baselines.load import load_observations as load_obs_file
from worldconsistmem.error_decompose import classify_error
from worldconsistmem.evaluate import evaluate_predictions
from worldconsistmem.h4_runtime import (
    PROMPT_TAG,
    ProgressTracker,
    atomic_append_jsonl,
    cache_key,
    frozen_config_hash,
    is_valid_cache_row,
    load_cache_rows,
    prediction_key,
    utc_now,
    write_progress_atomic,
)
from worldconsistmem.io_util import read_jsonl, write_csv, write_json, write_jsonl
from worldconsistmem.llm_reader import (
    EVIDENCE_JSON_CAP,
    MAX_EVIDENCE_ITEMS,
    MAX_TOKENS,
    TEMPERATURE,
    MLXLLMReader,
    build_evidence_from_ltkm_pack,
    build_evidence_from_observations,
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
from worldconsistmem.scaled_generate import generate_scaled_world
from worldconsistmem.stats_world import bootstrap_ci, mean, world_metric

OUT = ROOT / "results" / "scaled"
DATA = ROOT / "data" / "scaled"
RUN1 = OUT / "run1"
RUN2 = OUT / "run2"
RUN1_CACHE = RUN1 / "llm_reader_cache"
RUN2_CACHE = RUN2 / "llm_reader_cache"
PRED_DIR = RUN2 / "run2_predictions"
RELAXED = 0.8

MODEL_ID = "mlx-community/Qwen2.5-3B-Instruct-4bit"
MODEL_SLUG = "Qwen2.5-3B-Instruct-4bit"
RUN_ID = "h4_run2"

# Generate only these (B1 fully reused from Run1; B3 partially)
RUN2_SYSTEMS = [
    ("B3_recency_k8", "ret", 8),
    ("B4_bm25_k8", "ret", 8),
    ("H0_ltkm_cap150_ret8", "ltkm", 150),
]
ALL_QWEN_SYSTEMS = [
    "B1_flat_cap150_compact",
    "B3_recency_k8",
    "B4_bm25_k8",
    "H0_ltkm_cap150_ret8",
]

FREEZE_PATHS = [
    DATA / "manifest.json",
    DATA / "observations.jsonl",
    DATA / "bundles.jsonl",
    OUT / "system_results.csv",
    OUT / "capacity_results.csv",
    RUN1 / "llm_reader_cache" / f"{MODEL_SLUG}.jsonl",
    RUN1 / "run1_manifest.json",
]

QUERY_TIMEOUT_S = int(os.environ.get("H4_QUERY_TIMEOUT_S", "600"))
MAX_QUERY_RETRIES = int(os.environ.get("H4_QUERY_RETRIES", "2"))
EXPECTED_NEW = 2734


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze_checksums() -> dict[str, str]:
    out = {}
    for p in FREEZE_PATHS:
        if p.exists():
            try:
                out[str(p.relative_to(ROOT))] = sha_file(p)
            except ValueError:
                out[str(p)] = sha_file(p)
    out["smoke"] = assert_frozen_smoke()
    return out


def load_bundles_from_disk() -> list[QueryBundle]:
    rows = read_jsonl(DATA / "bundles.jsonl")
    bundles = []
    for row in rows:
        queries = [
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
            for q in row["queries"]
        ]
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


def evidence_recall(support_ids: list[str], retrieved_ids: list[str], kind: str) -> float:
    if not support_ids:
        return 1.0
    if kind == "ltkm":
        return 1.0 if retrieved_ids else 0.0
    hits = 0
    for sid in support_ids:
        if ":e:" in sid:
            t = sid.split(":e:")[-1]
            if any(f":obs:{t}" in rid or rid.endswith(f":{t}") for rid in retrieved_ids):
                hits += 1
        elif any(sid in rid for rid in retrieved_ids):
            hits += 1
    return hits / len(support_ids)


def load_logical_cache(path: Path) -> dict[tuple[str, str], dict]:
    """Index by (system, query_id) for valid rows."""
    rows, _ = load_cache_rows(path) if path.exists() else ({}, [])
    # Also accept by re-scan for last-wins on system+query
    out: dict[tuple[str, str], dict] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not is_valid_cache_row(r):
            continue
        out[(r["memory_system"], r["query_id"])] = r
    return out


def append_run2(row: dict) -> None:
    RUN2_CACHE.mkdir(parents=True, exist_ok=True)
    atomic_append_jsonl(RUN2_CACHE / f"{MODEL_SLUG}.jsonl", row)


def h4_subset() -> tuple[dict[str, Any], list[QueryBundle], dict[str, list]]:
    index = json.loads((DATA / "world_index.json").read_text(encoding="utf-8"))
    by_tier: dict[str, list] = defaultdict(list)
    for row in index:
        by_tier[row["tier"]].append(row)
    subset_rows = []
    for tier in ("small", "medium", "large"):
        subset_rows.extend(by_tier[tier][:6])
    worlds = {}
    for row in subset_rows:
        wid = row["world_id"]
        widx = int(wid.rsplit("_", 1)[-1])
        w = generate_scaled_world(int(row["seed"]), widx, tier=row["tier"])
        assert w.world_id == wid
        worlds[wid] = w
    sid = set(worlds)
    obs_all = load_obs_file(DATA / "observations.jsonl")
    obs_by_world = {wid: obs_all[wid] for wid in sid if wid in obs_all}
    bundles = [b for b in load_bundles_from_disk() if b.world_id in sid]
    return worlds, bundles, obs_by_world


def decide_qwen_h4(rows: list[dict]) -> tuple[str, str, dict]:
    by = {r["memory_system"]: r for r in rows}
    h0 = by.get("H0_ltkm_cap150_ret8")
    b1 = by.get("B1_flat_cap150_compact")
    b3 = by.get("B3_recency_k8")
    b4 = by.get("B4_bm25_k8")
    notes: dict[str, Any] = {"systems": {k: {
        "bcr": v.get("bcr"), "acc": v.get("mean_query_accuracy"),
        "abs": v.get("abstention_rate"), "mal": v.get("malformed_rate"),
        "high_inconsist": v.get("high_acc_inconsistent_rate"),
    } for k, v in by.items()}}
    if not all([h0, b1, b3, b4]):
        return "inconclusive", "INCONCLUSIVE", notes
    if any(r.get("coverage_pct", 100) < 99.9 for r in (h0, b1, b3, b4)):
        return "inconclusive", "INCONCLUSIVE", {**notes, "reason": "incomplete_coverage"}

    beats_ret = h0["bcr"] >= b3["bcr"] + 0.10 and h0["bcr"] >= b4["bcr"] + 0.10
    beats_flat = h0["bcr"] >= b1["bcr"] + 0.05 or (
        b1["high_acc_inconsistent_rate"] - h0["high_acc_inconsistent_rate"] >= 0.05
    )
    not_via_abs = h0["abstention_rate"] <= max(
        b3["abstention_rate"], b4["abstention_rate"], b1["abstention_rate"]
    ) + 0.05
    mal_ok = h0["malformed_rate"] < 0.5
    notes.update({
        "beats_ret": beats_ret,
        "beats_flat": beats_flat,
        "not_via_abs": not_via_abs,
        "mal_ok": mal_ok,
    })
    if beats_ret and beats_flat and not_via_abs and mal_ok:
        return "supported", "BENCHMARK + SYSTEM", notes
    if beats_ret and not beats_flat and not_via_abs and mal_ok:
        return "partial", "BENCHMARK-FIRST WITH STRUCTURED BASELINE", notes
    if not beats_ret:
        return "not_supported", "BENCHMARK ONLY", notes
    return "inconclusive", "INCONCLUSIVE", notes


def finalize(
    worlds: dict,
    bundles: list[QueryBundle],
    run1_logical: dict,
    run2_logical: dict,
    before: dict,
    t0: float,
    stats: dict,
) -> None:
    """Merge Run1+Run2 Qwen predictions and write metrics (does not alter Run1 files)."""
    merged: dict[tuple[str, str], dict] = {}
    merged.update(run1_logical)
    # Run2 overwrites only if same key (should only be new keys)
    for k, v in run2_logical.items():
        if k in merged and k[0] == "B3_recency_k8":
            # should not overwrite Run1 B3 unless regenerating — skip if Run1 has it
            continue
        merged[k] = v
    # Actually for B3: Run1 has completed; Run2 has tail only — union is correct:
    merged = {**run1_logical, **run2_logical}

    llm_rows = []
    error_rows = []
    family_rows = []
    constraint_rows = []

    for sname, _k, _p in [
        ("B1_flat_cap150_compact", None, None),
        ("B3_recency_k8", None, None),
        ("B4_bm25_k8", None, None),
        ("H0_ltkm_cap150_ret8", None, None),
    ]:
        preds: list[Prediction] = []
        n_exp = sum(len(b.queries) for b in bundles)
        missing = 0
        for b in bundles:
            for q in b.queries:
                row = merged.get((sname, q.query_id))
                if not row:
                    missing += 1
                    continue
                preds.append(
                    Prediction(
                        bundle_id=b.bundle_id,
                        query_id=q.query_id,
                        predicted_answer=row.get("predicted_answer"),
                        predicted_provenance=row.get("predicted_provenance"),
                        system_id=f"LLM:{MODEL_SLUG}|{sname}",
                        run_id="h4_run1_run2_merge",
                        metadata={
                            "status": row.get("status"),
                            "malformed": row.get("malformed", False),
                            "retrieved_observation_ids": row.get("retrieved_evidence_ids") or [],
                            "evidence_tokens": row.get("evidence_tokens", 0),
                            "prompt_tokens": row.get("prompt_tokens", 0),
                            "latency_ms": row.get("latency_ms", 0),
                            "evidence_count": row.get("evidence_count", 0),
                            "reader_model": MODEL_ID,
                            "memory_system": sname,
                            "world_id": b.world_id,
                            "query_family": q.family.value,
                        },
                    )
                )
        # classify errors
        for b in bundles:
            for q in b.queries:
                row = merged.get((sname, q.query_id))
                if not row:
                    continue
                st = row.get("status")
                correct = answers_equal(row.get("predicted_answer"), q.gold_answer) and st not in (
                    "malformed",
                    "error",
                )
                kind = "ltkm" if "ltkm" in sname or sname.startswith("H0") else "ret"
                if sname.startswith("B1"):
                    kind = "flat"
                rids = row.get("retrieved_evidence_ids") or []
                recall = evidence_recall(list(q.supporting_event_ids), rids, "ltkm" if kind == "ltkm" else kind)
                if correct:
                    err = "correct"
                else:
                    err = classify_error(
                        q,
                        Prediction(
                            b.bundle_id,
                            q.query_id,
                            row.get("predicted_answer"),
                            row.get("predicted_provenance"),
                            metadata={"status": st, "malformed": row.get("malformed"), "retrieved_observation_ids": rids},
                        ),
                        support_event_ids=list(q.supporting_event_ids),
                        stored_event_ids=None,
                        reader_kind=f"llm:{MODEL_SLUG}",
                    )
                    if (
                        err
                        not in (
                            "malformed_output",
                            "typed_abstention",
                            "required_evidence_absent",
                            "evidence_stored_not_retrieved",
                        )
                        and recall >= 0.5
                        and st == "ok"
                    ):
                        err = "reader_failed_on_correct_evidence"
                for p in preds:
                    if p.query_id == q.query_id:
                        p.metadata["correct"] = correct
                        p.metadata["error_label"] = err
                        p.metadata["evidence_recall"] = recall
                if not correct:
                    error_rows.append({
                        "system_id": f"LLM:{MODEL_SLUG}|{sname}",
                        "system": sname,
                        "reader_model": MODEL_ID,
                        "world_id": b.world_id,
                        "bundle_id": b.bundle_id,
                        "query_id": q.query_id,
                        "family": q.family.value,
                        "correct": False,
                        "error_label": err,
                        "status": st,
                        "source": "h4_run2_merge",
                    })

        if missing:
            print(f"WARN {sname}: missing {missing}/{n_exp}", flush=True)
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
        wids = sorted(worlds)
        bcr_vals = [world_metric(brows, w, "bcr") for w in wids]
        acc_vals = [world_metric(brows, w, "mean_acc") for w in wids]
        cons_vals = [world_metric(brows, w, "consacc") for w in wids]
        bcr_ci = bootstrap_ci(bcr_vals, seed=17)
        acc_ci = bootstrap_ci(acc_vals, seed=17)
        cons_ci = bootstrap_ci(cons_vals, seed=17)
        n_b = len(bms) or 1
        high_inconsist = sum(
            1 for m in bms if m.mean_query_accuracy >= RELAXED and not m.consistent
        ) / n_b
        consist_wrong = sum(1 for m in bms if m.consistent and not m.all_correct) / n_b
        abs_rate = sum(1 for p in preds if p.metadata.get("status") == "abstain") / max(len(preds), 1)
        mal_rate = sum(1 for p in preds if p.metadata.get("malformed")) / max(len(preds), 1)
        reader_fail = sum(
            1 for p in preds if p.metadata.get("error_label") == "reader_failed_on_correct_evidence"
        ) / max(len(preds), 1)
        avg_evid = mean([p.metadata.get("evidence_tokens", 0) for p in preds])
        avg_lat = mean([p.metadata.get("latency_ms", 0) for p in preds])
        avg_rec = mean([p.metadata.get("evidence_recall", 0) for p in preds])
        cov = 100.0 * len(preds) / n_exp if n_exp else 0.0
        row = {
            "reader_model": MODEL_ID,
            "memory_system": sname,
            "coverage_pct": round(cov, 2),
            "n_queries": len(preds),
            "n_expected": n_exp,
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
            "reader_fail_on_evidence_rate": round(reader_fail, 4),
            "avg_evidence_tokens": round(avg_evid, 2),
            "avg_latency_ms": round(avg_lat, 2),
            "avg_evidence_recall": round(avg_rec, 4),
            "bcr_world_mean": round(bcr_ci["mean"], 4),
            "bcr_world_ci95_lo": round(bcr_ci["lo"], 4),
            "bcr_world_ci95_hi": round(bcr_ci["hi"], 4),
            "acc_world_mean": round(acc_ci["mean"], 4),
            "acc_world_ci95_lo": round(acc_ci["lo"], 4),
            "acc_world_ci95_hi": round(acc_ci["hi"], 4),
            "consacc_world_mean": round(cons_ci["mean"], 4),
            "consacc_world_ci95_lo": round(cons_ci["lo"], 4),
            "consacc_world_ci95_hi": round(cons_ci["hi"], 4),
            "n_worlds": len(wids),
            "family_accuracy": json.dumps({k: round(v, 4) for k, v in agg.family_accuracy.items()}),
            "constraint_violation_rates": json.dumps(
                {k: round(v, 4) for k, v in agg.constraint_violation_rates.items()}
            ),
        }
        llm_rows.append(row)
        for fam, acc in agg.family_accuracy.items():
            family_rows.append({
                "reader_model": MODEL_ID,
                "memory_system": sname,
                "query_family": fam,
                "accuracy": round(acc, 4),
            })
        for cf, rate in agg.constraint_violation_rates.items():
            constraint_rows.append({
                "reader_model": MODEL_ID,
                "memory_system": sname,
                "constraint_family": cf,
                "violation_rate": round(rate, 4),
            })
        write_jsonl(PRED_DIR / f"{MODEL_SLUG}__{sname}.jsonl", [p.to_dict() for p in preds])
        print(
            f"FINAL {sname}: Acc={row['mean_query_accuracy']} BCR={row['bcr']} "
            f"abs={row['abstention_rate']} cov={row['coverage_pct']}%",
            flush=True,
        )

    write_csv(RUN2 / "qwen_system_results.csv", llm_rows)
    write_csv(RUN2 / "qwen_query_family_results.csv", family_rows)
    write_csv(RUN2 / "qwen_constraint_family_results.csv", constraint_rows)
    write_csv(RUN2 / "qwen_error_decomposition.csv", error_rows)

    h4_status, paper, notes = decide_qwen_h4(llm_rows)
    runtime_h = (time.time() - t0) / 3600.0

    findings = [
        "# Qwen H4 findings (Run1 reuse + Run2 Option A)\n\n",
        f"- H4 status: `{h4_status}`\n",
        f"- Paper shape: `{paper}`\n",
        f"- Model: `{MODEL_ID}`\n",
        f"- Run2 newly generated (this process stats): {stats}\n",
        f"- Wall runtime hours (this finalize process may be resume): {runtime_h:.2f}\n\n",
        "## System table\n\n",
    ]
    for r in llm_rows:
        findings.append(
            f"- **{r['memory_system']}**: Acc={r['mean_query_accuracy']} "
            f"BCR={r['bcr']} [{r['bcr_world_ci95_lo']},{r['bcr_world_ci95_hi']}] "
            f"ConsAcc={r['consacc_strict']} abs={r['abstention_rate']} "
            f"mal={r['malformed_rate']} high_inconsist={r['high_acc_inconsistent_rate']}\n"
        )
    findings.append("\n## Decision notes\n\n")
    findings.append(f"```json\n{json.dumps(notes, indent=2)}\n```\n")
    (RUN2 / "qwen_h4_findings.md").write_text("".join(findings), encoding="utf-8")

    stats_md = [
        "# Qwen H4 statistical analysis (Run2 merge)\n\n",
        "World-level bootstrap 95% CIs (queries not treated as independent).\n\n",
    ]
    for r in llm_rows:
        stats_md.append(
            f"## {r['memory_system']}\n\n"
            f"- Acc world mean {r['acc_world_mean']} CI[{r['acc_world_ci95_lo']},{r['acc_world_ci95_hi']}]\n"
            f"- BCR world mean {r['bcr_world_mean']} CI[{r['bcr_world_ci95_lo']},{r['bcr_world_ci95_hi']}]\n"
            f"- ConsAcc world mean {r['consacc_world_mean']} "
            f"CI[{r['consacc_world_ci95_lo']},{r['consacc_world_ci95_hi']}]\n\n"
        )
    (RUN2 / "qwen_statistical_analysis.md").write_text("".join(stats_md), encoding="utf-8")

    # Update scaled LLM outputs only (not symbolic)
    write_csv(OUT / "llm_reader_results.csv", llm_rows)
    # merge error decomposition: keep non-h4_run2_merge, append
    existing = []
    err_path = OUT / "error_decomposition.csv"
    if err_path.exists() and err_path.stat().st_size > 0:
        import csv as csvmod

        with err_path.open() as f:
            existing = [
                r for r in csvmod.DictReader(f)
                if r.get("source") not in ("h4_run2_merge", "h4_llm")
            ]
    write_csv(err_path, existing + error_rows)

    gate = {}
    if (OUT / "gate_summary.json").exists():
        gate = json.loads((OUT / "gate_summary.json").read_text())
    gate.update({
        "verdict": paper if paper != "INCONCLUSIVE" else gate.get("verdict", "PARTIAL RESEARCH SIGNAL"),
        "h4_status": h4_status,
        "paper": paper,
        "h4_run": "run2_option_a_qwen",
        "llm_note": f"Qwen Option A complete; status={h4_status}",
        "h4_notes": notes,
    })
    write_json(OUT / "gate_summary.json", gate)

    findings_path = OUT / "research_findings.md"
    base = findings_path.read_text() if findings_path.exists() else ""
    marker = "\n## H4 update\n"
    if marker in base:
        base = base.split(marker)[0].rstrip() + "\n"
    base += (
        f"{marker}\n"
        f"- Run2 Option A (Qwen-only) completed.\n"
        f"- H4 status: `{h4_status}`\n"
        f"- Paper shape: `{paper}`\n"
        f"- See `run2/qwen_h4_findings.md`.\n"
    )
    findings_path.write_text(base, encoding="utf-8")

    after = freeze_checksums()
    # Run1 cache must be unchanged
    r1_key = str((RUN1_CACHE / f"{MODEL_SLUG}.jsonl").relative_to(ROOT))
    assert after.get(r1_key) == before.get(r1_key), "Run1 cache checksum changed!"
    assert after["smoke"] == before["smoke"]
    write_json(RUN2 / "_run2_checksums_after.json", after)

    write_json(
        RUN2 / "run2_manifest.json",
        {
            "experiment": "H4-Run2-OptionA",
            "timestamp_utc": utc_now(),
            "model": MODEL_ID,
            "expected_new_predictions": EXPECTED_NEW,
            "stats": stats,
            "h4_status": h4_status,
            "paper": paper,
            "runtime_hours_finalize_wall": round(runtime_h, 3),
            "frozen_config_hash": frozen_config_hash(
                max_evidence_items=MAX_EVIDENCE_ITEMS,
                evidence_json_cap=EVIDENCE_JSON_CAP,
            ),
            "run1_unchanged": True,
            "run1_cache_sha256": before.get(r1_key),
        },
    )
    print("Freeze/Run1 checksums OK. H4:", h4_status, paper, flush=True)
    print("RUN2_COMPLETE", paper, flush=True)


def main() -> None:
    RUN2.mkdir(parents=True, exist_ok=True)
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    RUN2_CACHE.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    before = freeze_checksums()
    write_json(RUN2 / "_run2_checksums_before.json", before)
    assert before["smoke"] == EXPECTED_SMOKE_SHA256
    print("Run2 freeze checksums recorded; Run1 read-only.", flush=True)

    worlds, bundles, obs_by_world = h4_subset()
    n_queries = sum(len(b.queries) for b in bundles)
    assert n_queries == 1260
    print(f"H4 subset: {len(worlds)} worlds, {len(bundles)} bundles, {n_queries} queries", flush=True)

    run1_logical = load_logical_cache(RUN1_CACHE / f"{MODEL_SLUG}.jsonl")
    run2_logical = load_logical_cache(RUN2_CACHE / f"{MODEL_SLUG}.jsonl")
    # Union of completed for skip
    completed = {**run1_logical, **run2_logical}

    # Build worklist
    work: list[tuple[str, str, QueryBundle, Query]] = []
    for sname, _k, _p in RUN2_SYSTEMS:
        for b in bundles:
            for q in b.queries:
                if (sname, q.query_id) in completed:
                    continue
                work.append((sname, "ltkm" if sname.startswith("H0") else "ret", b, q))

    # Verify expected new count at cold start
    r1_b1 = sum(1 for (s, _) in run1_logical if s == "B1_flat_cap150_compact")
    r1_b3 = sum(1 for (s, _) in run1_logical if s == "B3_recency_k8")
    print(f"Run1 reuse: B1={r1_b1} B3={r1_b3}; Run2 cache={len(run2_logical)}; todo={len(work)}", flush=True)
    write_json(
        RUN2 / "run2_completeness.json",
        {
            "expected_new": EXPECTED_NEW,
            "todo_now": len(work),
            "run1_b1": r1_b1,
            "run1_b3": r1_b3,
            "run2_done": len(run2_logical),
            "updated_at": utc_now(),
        },
    )

    progress = ProgressTracker(
        RUN2 / "run2_progress.json",
        total_expected=EXPECTED_NEW,
        model=MODEL_ID,
        pid=os.getpid(),
        restart_count=int(os.environ.get("H4_RESTART_COUNT", "0")),
        last_restart_reason=os.environ.get("H4_RESTART_REASON"),
    )
    progress.completed_valid = EXPECTED_NEW - len(work)
    progress.skipped_from_cache = progress.completed_valid
    progress.newly_generated = len(run2_logical)
    progress.flush()

    if not work:
        print("No missing cells — finalizing.", flush=True)
        finalize(worlds, bundles, run1_logical, run2_logical, before, t0, {
            "newly_generated": 0,
            "reused_run1": r1_b1 + r1_b3,
            "failures": 0,
            "timeouts": 0,
        })
        return

    print(f"=== Loading {MODEL_ID} for Run2 ===", flush=True)
    reader = MLXLLMReader(MODEL_ID)
    if not reader.available:
        raise RuntimeError(f"model unavailable: {reader.load_error}")
    smoke = reader.smoke_generate()
    print(f"smoke OK: {smoke[:80]!r}", flush=True)
    write_json(
        RUN2 / "model_smoke.json",
        {
            "model": MODEL_ID,
            "smoke_ok": True,
            "preview": smoke[:200],
            "mlx": reader.mlx_version,
            "mlx_lm": reader.mlx_lm_version,
        },
    )

    # Group work by system then world for efficient ingest
    by_sys: dict[str, list] = defaultdict(list)
    for item in work:
        by_sys[item[0]].append(item)

    newly = 0
    failures = 0
    timeouts = 0
    failure_rows = []

    for sname, _k, _p in RUN2_SYSTEMS:
        items = by_sys.get(sname, [])
        if not items:
            print(f"Run2 {sname}: nothing to do", flush=True)
            continue
        adapter, kind = make_adapter(sname)
        print(f"Run2 {MODEL_ID} × {sname} ({len(items)} remaining)", flush=True)
        progress.system = sname
        progress.flush()

        by_w: dict[str, list] = defaultdict(list)
        for s, knd, b, q in items:
            by_w[b.world_id].append((s, knd, b, q))

        n_sys = 0
        t_sys = time.time()
        for wid, witems in by_w.items():
            adapter.reset()
            for o in obs_by_world[wid]:
                adapter.ingest(o)
            for sname_i, kind_i, b, q in witems:
                pred_key = prediction_key(
                    MODEL_ID, sname_i, wid, b.bundle_id, q.query_id, run_id=RUN_ID
                )
                ck = cache_key(MODEL_ID, sname_i, q.query_id)
                detailed = None
                last_err = None
                rids: list[str] = []
                evid = None
                for attempt in range(1, MAX_QUERY_RETRIES + 2):
                    try:

                        def _timeout_handler(signum, frame):  # noqa: ARG001
                            raise TimeoutError(f"query_timeout_{QUERY_TIMEOUT_S}s")

                        old = signal.signal(signal.SIGALRM, _timeout_handler)
                        signal.alarm(QUERY_TIMEOUT_S)
                        try:
                            if kind_i == "ltkm":
                                pack = LTKMRetriever(adapter.memory).retrieve(q)
                                rids = list(pack.record_ids)[:MAX_EVIDENCE_ITEMS]
                                evid = build_evidence_from_ltkm_pack(q, pack.payloads, rids)
                            else:
                                if hasattr(adapter, "retrieve"):
                                    retrieved, _scores = adapter.retrieve(q, q.target_time)
                                else:
                                    tmp = RecencyWeightedMemory(
                                        k=MAX_EVIDENCE_ITEMS, run_id="flat_reader_k"
                                    )
                                    tmp._obs = list(getattr(adapter, "_obs", []))
                                    retrieved, _scores = tmp.retrieve(q, q.target_time)
                                retrieved = list(retrieved)[:MAX_EVIDENCE_ITEMS]
                                evid = build_evidence_from_observations(q, retrieved)
                                rids = [o.observation_id for o in retrieved]
                            detailed = reader.answer_evidence_detailed(evid)
                        finally:
                            signal.alarm(0)
                            signal.signal(signal.SIGALRM, old)
                        break
                    except TimeoutError as e:
                        last_err = e
                        timeouts += 1
                        print(f"  TIMEOUT {q.query_id} attempt={attempt}", flush=True)
                    except Exception as e:  # noqa: BLE001
                        last_err = e
                        print(f"  ERROR {q.query_id} attempt={attempt}: {e}", flush=True)

                if detailed is None:
                    failures += 1
                    cache_row = {
                        "cache_key": ck,
                        "prediction_key": pred_key,
                        "model_id": MODEL_ID,
                        "memory_system": sname_i,
                        "world_id": wid,
                        "bundle_id": b.bundle_id,
                        "query_id": q.query_id,
                        "predicted_answer": None,
                        "predicted_provenance": None,
                        "status": "error",
                        "detail": f"terminal_failure:{last_err}",
                        "malformed": False,
                        "latency_ms": 0.0,
                        "prompt_tokens": 0,
                        "evidence_tokens": 0,
                        "raw_output": "",
                        "parsed_output": None,
                        "peak_memory_gb": None,
                        "retrieved_evidence_ids": [],
                        "evidence_count": 0,
                        "failure_type": "terminal_timeout_or_error",
                        "run": "run2",
                    }
                    append_run2(cache_row)
                    run2_logical[(sname_i, q.query_id)] = cache_row
                    failure_rows.append(cache_row)
                    with (RUN2 / "run2_failures.jsonl").open("a", encoding="utf-8") as ff:
                        ff.write(json.dumps(cache_row, sort_keys=True) + "\n")
                    progress.note_failed(pred_key, q.query_id)
                else:
                    cache_row = {
                        "cache_key": ck,
                        "prediction_key": pred_key,
                        "model_id": MODEL_ID,
                        "memory_system": sname_i,
                        "world_id": wid,
                        "bundle_id": b.bundle_id,
                        "query_id": q.query_id,
                        "predicted_answer": detailed.answer,
                        "predicted_provenance": detailed.provenance,
                        "status": detailed.status,
                        "detail": detailed.detail,
                        "malformed": detailed.malformed,
                        "latency_ms": detailed.latency_ms,
                        "prompt_tokens": detailed.prompt_tokens,
                        "evidence_tokens": detailed.evidence_tokens,
                        "raw_output": detailed.raw_output,
                        "parsed_output": detailed.parsed,
                        "peak_memory_gb": detailed.peak_memory_gb,
                        "retrieved_evidence_ids": rids,
                        "evidence_count": len(evid.evidence) if evid else 0,
                        "run": "run2",
                    }
                    append_run2(cache_row)
                    run2_logical[(sname_i, q.query_id)] = cache_row
                    newly += 1
                    progress.note_generated(pred_key, q.query_id)

                n_sys += 1
                if n_sys % 50 == 0:
                    try:
                        import gc
                        import mlx.core as mx  # type: ignore

                        gc.collect()
                        if hasattr(mx, "clear_cache"):
                            mx.clear_cache()
                    except Exception:
                        pass
                    elapsed = time.time() - t_sys
                    rate = n_sys / max(elapsed, 1e-6)
                    filled = sum(
                        1 for sn, _, bb, qq in work if (sn, qq.query_id) in run2_logical
                    )
                    progress.completed_valid = (EXPECTED_NEW - len(work)) + filled
                    progress.newly_generated = filled
                    progress.failed = failures
                    progress.timeout_count = timeouts
                    progress.flush()
                    print(
                        f"  … {n_sys}/{len(items)} ({rate:.2f} q/s, {elapsed:.0f}s) "
                        f"filled={filled}/{len(work)}",
                        flush=True,
                    )
                    write_json(
                        RUN2 / "run2_completeness.json",
                        {
                            "expected_new": EXPECTED_NEW,
                            "filled_of_initial_todo": filled,
                            "initial_todo": len(work),
                            "failures": failures,
                            "timeouts": timeouts,
                            "updated_at": utc_now(),
                        },
                    )

        print(f"  done system {sname}", flush=True)

    # Reload run2 after writes
    run2_logical = load_logical_cache(RUN2_CACHE / f"{MODEL_SLUG}.jsonl")
    filled = sum(1 for sn, _, bb, qq in work if (sn, qq.query_id) in run2_logical)
    still_missing = [
        (sn, qq.query_id)
        for sn, _, bb, qq in work
        if (sn, qq.query_id) not in run2_logical and (sn, qq.query_id) not in run1_logical
    ]
    stats = {
        "newly_generated": filled,
        "reused_run1": r1_b1 + r1_b3,
        "failures": failures,
        "timeouts": timeouts,
        "initial_todo": len(work),
        "wall_hours": round((time.time() - t0) / 3600.0, 3),
    }
    write_json(RUN2 / "run2_completeness.json", {
        "expected_new": EXPECTED_NEW,
        "filled": filled,
        "still_missing": len(still_missing),
        "failures": failures,
        "complete": len(still_missing) == 0,
        "updated_at": utc_now(),
        "stats": stats,
    })
    if still_missing:
        print(f"INCOMPLETE: {len(still_missing)} still missing — not finalizing", flush=True)
        progress.flush()
        sys.exit(2)

    finalize(worlds, bundles, run1_logical, run2_logical, before, t0, stats)


if __name__ == "__main__":
    import faulthandler
    import traceback

    faulthandler.enable()
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
