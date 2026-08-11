"""Run H0 LTKM + ablations vs frozen baselines on smoke."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.baselines.adapters import (
    BM25RetrievalMemory,
    FlatAppendMemory,
    LatestStateMemory,
    RecencyWeightedMemory,
)
from worldconsistmem.baselines.load import (
    EXPECTED_SMOKE_SHA256,
    assert_frozen_smoke,
    load_bundles,
    load_observations,
    load_worlds_via_seed,
    verify_worlds_match_frozen,
)
from worldconsistmem.evaluate import evaluate_predictions
from worldconsistmem.io_util import write_csv, write_json, write_jsonl
from worldconsistmem.ltkm.adapter import LTKMAdapter, make_ablation
from worldconsistmem.ltkm.memory import LTKMConfig
from worldconsistmem.metrics import answers_equal

OUT = ROOT / "results" / "ltkm"
RELAXED = 0.8
K = 5


def _run(adapter, obs_by_world, bundles, worlds):
    preds = []
    by_w = defaultdict(list)
    for b in bundles:
        by_w[b.world_id].append(b)
    lifecycle = []
    for wid, blist in by_w.items():
        adapter.reset()
        for o in obs_by_world[wid]:
            adapter.ingest(o)
        if hasattr(adapter, "memory"):
            lifecycle.extend([r.to_dict() for r in adapter.memory.lifecycle.log])
        for b in blist:
            preds.extend(adapter.answer_bundle(b))
    bms, agg, viols = evaluate_predictions(worlds, bundles, preds, relaxed_acc_threshold=RELAXED)
    return preds, bms, agg, viols, lifecycle


def _rates(bms):
    n = len(bms) or 1
    high = sum(1 for m in bms if m.mean_query_accuracy >= RELAXED and not m.consistent) / n
    cw = sum(1 for m in bms if m.consistent and not m.all_correct) / n
    return high, cw


def _abstention_rate(preds):
    return sum(1 for p in preds if p.metadata.get("status") == "abstain") / max(len(preds), 1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    digest = assert_frozen_smoke()
    assert digest == EXPECTED_SMOKE_SHA256
    worlds = load_worlds_via_seed(42, 25)
    verify_worlds_match_frozen(worlds)
    obs = load_observations()
    bundles = load_bundles()

    systems = [
        ("B1_flat_append", FlatAppendMemory(run_id="flat")),
        ("B2_latest_only", LatestStateMemory(run_id="latest")),
        ("B3_recency_retrieval", RecencyWeightedMemory(k=K, run_id=f"recency_k{K}")),
        ("B4_bm25", BM25RetrievalMemory(k=K, run_id=f"bm25_k{K}")),
        ("H0_ltkm", LTKMAdapter(LTKMConfig(system_id="H0_ltkm", run_id="ltkm"))),
        ("H-archive", make_ablation("H-archive")),
        ("H-temporal-validity", make_ablation("H-temporal-validity")),
        ("H-graph", make_ablation("H-graph")),
    ]

    comparison = []
    family_rows = []
    constraint_rows = []
    ablation_rows = []
    resource_rows = []
    failures = []
    examples = {"corrected_vs_b4": [], "ltkm_remaining": [], "ablation_archive": [], "ablation_graph": []}

    b4_preds = None
    h0_preds = None
    h0_bms = None
    lifecycle_log = []

    for name, adapter in systems:
        print("Running", name)
        preds, bms, agg, viols, life = _run(adapter, obs, bundles, worlds)
        if name == "H0_ltkm":
            write_jsonl(OUT / "ltkm_predictions.jsonl", [p.to_dict() for p in preds])
            lifecycle_log = life
            h0_preds = preds
            h0_bms = bms
            write_json(OUT / "ltkm_metrics.json", agg.to_dict())
        if name == "B4_bm25":
            b4_preds = preds

        high, cw = _rates(bms)
        abs_rate = _abstention_rate(preds)
        avg_stored = sum(p.metadata.get("memory_state_size", 0) for p in preds) / max(len(preds), 1)
        avg_cons = sum(p.metadata.get("n_consulted_records", p.metadata.get("n_retrieved", 0)) for p in preds) / max(len(preds), 1)
        avg_lat = sum(p.metadata.get("latency_ms", 0) for p in preds) / max(len(preds), 1)

        # provenance accuracy
        qmap = {q.query_id: q for b in bundles for q in b.queries}
        prov_hits = prov_n = 0
        for p in preds:
            q = qmap[p.query_id]
            if q.family.value != "provenance":
                continue
            prov_n += 1
            if answers_equal(p.predicted_answer, q.gold_answer):
                prov_hits += 1

        row = {
            "system": name,
            "mean_query_accuracy": round(agg.mean_query_accuracy, 4),
            "bcr": round(agg.bcr, 4),
            "consacc_strict": round(agg.consacc_strict, 4),
            "consacc_relaxed": round(agg.consacc_relaxed, 4),
            "gap_mean_acc_minus_bcr": round(agg.gap_mean_acc_minus_bcr, 4),
            "high_acc_inconsistent_rate": round(high, 4),
            "consistent_wrong_rate": round(cw, 4),
            "provenance_accuracy": round(prov_hits / prov_n if prov_n else 0, 4),
            "temporal_violation_rate": round(agg.temporal_violation_rate, 4),
            "abstention_rate": round(abs_rate, 4),
            "avg_stored_records": round(avg_stored, 2),
            "avg_records_consulted": round(avg_cons, 2),
            "avg_latency_ms": round(avg_lat, 4),
            "n_violations": len(viols),
        }
        comparison.append(row)
        if name.startswith("H"):
            ablation_rows.append(row)

        for fam, acc in agg.family_accuracy.items():
            family_rows.append({"system": name, "query_family": fam, "accuracy": round(acc, 4)})
        for fam, rate in agg.constraint_violation_rates.items():
            constraint_rows.append(
                {"system": name, "constraint_family": fam, "bundle_violation_rate": round(rate, 4)}
            )

        # resource from last prediction if LTKM
        if hasattr(adapter, "memory") and preds:
            snap = preds[-1].metadata.get("resource") or {}
            resource_rows.append({"system": name, **snap})

        for m in bms:
            for qid, acc in m.per_query.items():
                if acc < 1.0:
                    p = next(x for x in preds if x.query_id == qid)
                    q = qmap[qid]
                    failures.append(
                        {
                            "system": name,
                            "bundle_id": m.bundle_id,
                            "query_id": qid,
                            "family": q.family.value,
                            "slot": q.metadata.get("slot"),
                            "gold": q.gold_answer,
                            "predicted": p.predicted_answer,
                            "status": p.metadata.get("status"),
                            "detail": p.metadata.get("detail"),
                        }
                    )

    # Examples: B4 fail where H0 ok
    if b4_preds and h0_preds and h0_bms:
        b4m = {p.query_id: p for p in b4_preds}
        h0m = {p.query_id: p for p in h0_preds}
        qmap = {q.query_id: q for b in bundles for q in b.queries}
        for qid, q in qmap.items():
            if answers_equal(b4m[qid].predicted_answer, q.gold_answer):
                continue
            if answers_equal(h0m[qid].predicted_answer, q.gold_answer):
                examples["corrected_vs_b4"].append(
                    {
                        "query_id": qid,
                        "slot": q.metadata.get("slot"),
                        "b4": b4m[qid].predicted_answer,
                        "h0": h0m[qid].predicted_answer,
                        "gold": q.gold_answer,
                    }
                )
                if len(examples["corrected_vs_b4"]) >= 5:
                    break
        for m in h0_bms:
            if not m.all_correct:
                examples["ltkm_remaining"].append(
                    {"bundle_id": m.bundle_id, "mean_acc": m.mean_query_accuracy}
                )
                if len(examples["ltkm_remaining"]) >= 3:
                    break

    # Ablation effect notes from comparison
    by_sys = {r["system"]: r for r in comparison}
    if "H0_ltkm" in by_sys and "H-archive" in by_sys:
        examples["ablation_archive"].append(
            {
                "H0_bcr": by_sys["H0_ltkm"]["bcr"],
                "H_archive_bcr": by_sys["H-archive"]["bcr"],
                "H0_hist_acc": next(
                    (r["accuracy"] for r in family_rows if r["system"] == "H0_ltkm" and r["query_family"] == "historical_state"),
                    None,
                ),
                "H_archive_hist_acc": next(
                    (r["accuracy"] for r in family_rows if r["system"] == "H-archive" and r["query_family"] == "historical_state"),
                    None,
                ),
            }
        )
    if "H0_ltkm" in by_sys and "H-graph" in by_sys:
        examples["ablation_graph"].append(
            {
                "H0_bcr": by_sys["H0_ltkm"]["bcr"],
                "H_graph_bcr": by_sys["H-graph"]["bcr"],
                "H0_mh_acc": next(
                    (r["accuracy"] for r in family_rows if r["system"] == "H0_ltkm" and r["query_family"] == "multi_hop"),
                    None,
                ),
                "H_graph_mh_acc": next(
                    (r["accuracy"] for r in family_rows if r["system"] == "H-graph" and r["query_family"] == "multi_hop"),
                    None,
                ),
            }
        )

    write_csv(OUT / "system_comparison.csv", comparison)
    write_csv(OUT / "query_family_results.csv", family_rows)
    write_csv(OUT / "constraint_family_results.csv", constraint_rows)
    write_csv(OUT / "ablation_results.csv", ablation_rows)
    write_csv(OUT / "resource_usage.csv", resource_rows)
    write_jsonl(OUT / "lifecycle_log.jsonl", lifecycle_log[:5000])
    write_jsonl(OUT / "failures.jsonl", failures[:5000])
    write_json(OUT / "examples.json", examples)

    verdict = _verdict(by_sys, family_rows, constraint_rows)
    findings = _findings(digest, verdict, comparison, family_rows, constraint_rows, examples, by_sys)
    (OUT / "ltkm_findings.md").write_text(findings, encoding="utf-8")
    print(verdict)
    print("Wrote", OUT)


def _verdict(by_sys, family_rows, constraint_rows):
    h0 = by_sys.get("H0_ltkm")
    b3 = by_sys.get("B3_recency_retrieval")
    b4 = by_sys.get("B4_bm25")
    if not h0 or not b3 or not b4:
        return "NO PROTOTYPE SIGNAL"
    if h0["abstention_rate"] > 0.25:
        return "PARTIAL PROTOTYPE SIGNAL"
    bcr_ok = h0["bcr"] >= b3["bcr"] + 0.20 and h0["bcr"] >= b4["bcr"] + 0.20
    gap_ok = (b3["gap_mean_acc_minus_bcr"] - h0["gap_mean_acc_minus_bcr"] >= 0.20) and (
        b4["gap_mean_acc_minus_bcr"] - h0["gap_mean_acc_minus_bcr"] >= 0.20
    )
    # constraint families improved vs B4
    b4c = {r["constraint_family"]: r["bundle_violation_rate"] for r in constraint_rows if r["system"] == "B4_bm25"}
    h0c = {r["constraint_family"]: r["bundle_violation_rate"] for r in constraint_rows if r["system"] == "H0_ltkm"}
    improved = sum(1 for k in h0c if h0c[k] + 1e-9 < b4c.get(k, 1.0))
    archive = by_sys.get("H-archive")
    temporal = by_sys.get("H-temporal-validity")
    graph = by_sys.get("H-graph")
    archive_harm = archive and (
        archive["bcr"] + 0.05 < h0["bcr"]
        or next(
            (r["accuracy"] for r in family_rows if r["system"] == "H-archive" and r["query_family"] == "historical_state"),
            1,
        )
        + 0.05
        < next(
            (r["accuracy"] for r in family_rows if r["system"] == "H0_ltkm" and r["query_family"] == "historical_state"),
            0,
        )
    )
    temporal_harm = temporal and (
        temporal["temporal_violation_rate"] > h0["temporal_violation_rate"] + 0.05
        or temporal["bcr"] + 0.05 < h0["bcr"]
    )
    graph_harm = graph and (
        next(
            (r["accuracy"] for r in family_rows if r["system"] == "H-graph" and r["query_family"] == "multi_hop"),
            1,
        )
        + 0.05
        < next(
            (r["accuracy"] for r in family_rows if r["system"] == "H0_ltkm" and r["query_family"] == "multi_hop"),
            0,
        )
    )
    if bcr_ok and gap_ok and improved >= 3 and archive_harm and temporal_harm and graph_harm:
        return "PROTOTYPE SIGNAL VALIDATED"
    if h0["bcr"] > b4["bcr"] and h0["gap_mean_acc_minus_bcr"] < b4["gap_mean_acc_minus_bcr"]:
        return "PARTIAL PROTOTYPE SIGNAL"
    return "NO PROTOTYPE SIGNAL"


def _findings(digest, verdict, comparison, family_rows, constraint_rows, examples, by_sys):
    lines = [
        "# LTKM prototype findings",
        "",
        f"**Verdict:** {verdict}",
        "",
        f"- smoke checksum: `{digest}`",
        "",
        "## System comparison",
        "",
        "| system | Acc | BCR | Gap | abstain |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in comparison:
        lines.append(
            f"| {r['system']} | {r['mean_query_accuracy']} | {r['bcr']} | {r['gap_mean_acc_minus_bcr']} | {r['abstention_rate']} |"
        )
    lines += [
        "",
        "## Permitted conclusion",
        "",
        "Explicitly structured lifecycle-aware memory can reduce cross-query consistency "
        "failures relative to simple latest-state and retrieval-centric baselines on WorldConsistMem.",
        "",
        "No claim of general hierarchy superiority, necessity of five layers, or superiority over B1.",
        "",
        f"## Examples",
        "",
        f"- Corrected vs B4 (sample): {examples.get('corrected_vs_b4', [])[:2]}",
        f"- Remaining LTKM failures: {examples.get('ltkm_remaining', [])}",
        f"- Archive ablation: {examples.get('ablation_archive', [])}",
        f"- Graph ablation: {examples.get('ablation_graph', [])}",
        "",
        f"_tag: {verdict}_",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
