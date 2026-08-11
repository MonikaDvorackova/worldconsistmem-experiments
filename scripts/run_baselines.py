"""Run all WorldConsistMem baselines on the frozen smoke benchmark."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.baselines.adapters import (
    BM25RetrievalMemory,
    FlatAppendMemory,
    GoldReplayOracle,
    LatestStateMemory,
    RecencyWeightedMemory,
    ReservoirMemory,
)
from worldconsistmem.baselines.interface import BaselineAdapter
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
from worldconsistmem.metrics import answers_equal
from worldconsistmem.models import Prediction


OUT = ROOT / "results" / "baselines"
K = 5
RELAXED = 0.8


def _run_adapter(
    adapter: BaselineAdapter,
    worlds: dict,
    obs_by_world: dict,
    bundles: list,
) -> list[Prediction]:
    preds: list[Prediction] = []
    bundles_by_world: dict[str, list] = defaultdict(list)
    for b in bundles:
        bundles_by_world[b.world_id].append(b)

    for world_id, w_bundles in bundles_by_world.items():
        adapter.reset()
        if isinstance(adapter, GoldReplayOracle):
            adapter.bind_world(world_id)
        for obs in obs_by_world.get(world_id, []):
            adapter.ingest(obs)
        for b in w_bundles:
            if isinstance(adapter, GoldReplayOracle):
                adapter.bind_world(b.world_id)
            preds.extend(adapter.answer_bundle(b))
    return preds


def _provenance_accuracy(bundles, preds: list[Prediction]) -> float:
    pmap = {p.query_id: p for p in preds}
    hits = n = 0
    for b in bundles:
        for q in b.queries:
            if q.family.value != "provenance":
                continue
            n += 1
            p = pmap.get(q.query_id)
            if p and answers_equal(p.predicted_answer, q.gold_answer):
                hits += 1
    return hits / n if n else 0.0


def _recall_at_k(bundles, preds: list[Prediction]) -> float:
    """Fraction of queries where ≥1 supporting event's observation was retrieved."""
    pmap = {p.query_id: p for p in preds}
    hits = n = 0
    for b in bundles:
        for q in b.queries:
            p = pmap.get(q.query_id)
            if not p:
                continue
            retrieved = p.metadata.get("retrieved_observation_ids") or []
            if not retrieved:
                continue
            n += 1
            # Map supporting event ids to obs ids: world:e:t -> world:obs:t
            support_obs = []
            for eid in q.supporting_event_ids:
                if ":e:" in eid:
                    support_obs.append(eid.replace(":e:", ":obs:"))
            if any(oid in retrieved for oid in support_obs):
                hits += 1
    return hits / n if n else float("nan")


def _bundle_rates(bmetrics, threshold=0.8):
    high_inconsist = sum(
        1 for m in bmetrics if m.mean_query_accuracy >= threshold and not m.consistent
    )
    consist_wrong = sum(
        1
        for m in bmetrics
        if m.consistent and m.mean_query_accuracy < 1.0 and not m.all_correct
    )
    n = len(bmetrics) or 1
    return high_inconsist / n, consist_wrong / n


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    digest = assert_frozen_smoke()
    print(f"Frozen smoke checksum OK: {digest}")

    worlds = load_worlds_via_seed(42, 25)
    verify_worlds_match_frozen(worlds)
    obs_by_world = load_observations()
    bundles = load_bundles()

    adapters: list[BaselineAdapter] = [
        GoldReplayOracle(worlds, run_id="oracle"),
        FlatAppendMemory(run_id="flat"),
        LatestStateMemory(run_id="latest"),
        RecencyWeightedMemory(k=K, recency_coef=0.15, run_id=f"recency_k{K}"),
        BM25RetrievalMemory(k=K, run_id=f"bm25_k{K}"),
        ReservoirMemory(capacity=8, seed=0),
        ReservoirMemory(capacity=8, seed=1),
        ReservoirMemory(capacity=8, seed=2),
        ReservoirMemory(capacity=16, seed=0),
        ReservoirMemory(capacity=16, seed=1),
        ReservoirMemory(capacity=16, seed=2),
    ]

    comparison_rows = []
    family_rows = []
    constraint_rows = []
    retrieval_rows = []
    failure_rows = []
    findings_examples = {"high_acc_inconsistent": [], "consistent_wrong": []}

    for adapter in adapters:
        print(f"Running {adapter.baseline_id} / {adapter.run_id} ...")
        preds = _run_adapter(adapter, worlds, obs_by_world, bundles)
        out_name = f"{adapter.baseline_id}_{adapter.run_id}_predictions.jsonl"
        write_jsonl(OUT / out_name, [p.to_dict() for p in preds])
        # Also write canonical name without run for primary baselines
        if adapter.run_id in ("oracle", "flat", "latest") or adapter.run_id.startswith(
            ("recency", "bm25")
        ):
            write_jsonl(
                OUT / f"{adapter.baseline_id}_predictions.jsonl",
                [p.to_dict() for p in preds],
            )

        bms, agg, viols = evaluate_predictions(
            worlds, bundles, preds, relaxed_acc_threshold=RELAXED
        )
        high_rate, cw_rate = _bundle_rates(bms, RELAXED)
        avg_mem = sum(p.metadata.get("memory_state_size", 0) for p in preds) / max(len(preds), 1)
        avg_ret = sum(p.metadata.get("n_retrieved", 0) for p in preds) / max(len(preds), 1)
        avg_lat = sum(p.metadata.get("latency_ms", 0) for p in preds) / max(len(preds), 1)
        prov_acc = _provenance_accuracy(bundles, preds)
        recall = _recall_at_k(bundles, preds)

        comparison_rows.append(
            {
                "baseline_id": adapter.baseline_id,
                "run_id": adapter.run_id,
                "mean_query_accuracy": round(agg.mean_query_accuracy, 4),
                "bcr": round(agg.bcr, 4),
                "consacc_strict": round(agg.consacc_strict, 4),
                "consacc_relaxed": round(agg.consacc_relaxed, 4),
                "gap_mean_acc_minus_bcr": round(agg.gap_mean_acc_minus_bcr, 4),
                "gap_bundle_acc_minus_consacc": round(agg.gap_bundle_acc_minus_consacc, 4),
                "high_acc_inconsistent_rate": round(high_rate, 4),
                "consistent_wrong_rate": round(cw_rate, 4),
                "provenance_accuracy": round(prov_acc, 4),
                "recall_at_k": None if recall != recall else round(recall, 4),
                "avg_stored_items": round(avg_mem, 2),
                "avg_retrieved_items": round(avg_ret, 2),
                "avg_latency_ms": round(avg_lat, 4),
                "n_violations": len(viols),
            }
        )

        for fam, acc in agg.family_accuracy.items():
            family_rows.append(
                {
                    "baseline_id": adapter.baseline_id,
                    "run_id": adapter.run_id,
                    "query_family": fam,
                    "accuracy": round(acc, 4),
                }
            )

        for fam, rate in agg.constraint_violation_rates.items():
            constraint_rows.append(
                {
                    "baseline_id": adapter.baseline_id,
                    "run_id": adapter.run_id,
                    "constraint_family": fam,
                    "bundle_violation_rate": round(rate, 4),
                }
            )

        retrieval_rows.append(
            {
                "baseline_id": adapter.baseline_id,
                "run_id": adapter.run_id,
                "k": K if "bm25" in adapter.baseline_id.lower() or "recency" in adapter.baseline_id.lower() else None,
                "recall_at_k": None if recall != recall else round(recall, 4),
                "avg_retrieved": round(avg_ret, 2),
                "avg_stored": round(avg_mem, 2),
            }
        )

        # Failures + examples
        qmap = {q.query_id: q for b in bundles for q in b.queries}
        bmap = {b.bundle_id: b for b in bundles}
        for m in bms:
            if m.mean_query_accuracy >= RELAXED and not m.consistent:
                if len(findings_examples["high_acc_inconsistent"]) < 5:
                    findings_examples["high_acc_inconsistent"].append(
                        {
                            "baseline_id": adapter.baseline_id,
                            "bundle_id": m.bundle_id,
                            "mean_acc": m.mean_query_accuracy,
                            "violations": [
                                r.to_dict() for r in m.constraint_results if not r.passed
                            ][:5],
                        }
                    )
            if m.consistent and not m.all_correct and m.mean_query_accuracy < 1.0:
                if len(findings_examples["consistent_wrong"]) < 5:
                    findings_examples["consistent_wrong"].append(
                        {
                            "baseline_id": adapter.baseline_id,
                            "bundle_id": m.bundle_id,
                            "mean_acc": m.mean_query_accuracy,
                        }
                    )
            for qid, acc in m.per_query.items():
                if acc < 1.0:
                    p = next((x for x in preds if x.query_id == qid), None)
                    q = qmap[qid]
                    failure_rows.append(
                        {
                            "baseline_id": adapter.baseline_id,
                            "run_id": adapter.run_id,
                            "bundle_id": m.bundle_id,
                            "query_id": qid,
                            "family": q.family.value,
                            "gold": q.gold_answer,
                            "predicted": None if p is None else p.predicted_answer,
                            "status": None if p is None else p.metadata.get("status"),
                        }
                    )

    write_csv(OUT / "baseline_comparison.csv", comparison_rows)
    write_csv(OUT / "query_family_results.csv", family_rows)
    write_csv(OUT / "constraint_family_results.csv", constraint_rows)
    write_csv(OUT / "retrieval_diagnostics.csv", retrieval_rows)
    write_jsonl(OUT / "baseline_failures.jsonl", failure_rows[:5000])
    write_json(OUT / "findings_examples.json", findings_examples)

    report = _write_findings(digest, comparison_rows, family_rows, constraint_rows, findings_examples)
    (OUT / "baseline_findings.md").write_text(report, encoding="utf-8")
    print(report.splitlines()[0])
    print("Wrote", OUT)


def _write_findings(digest, comparison, family_rows, constraint_rows, examples) -> str:
    # Verdict logic
    oracle = next(r for r in comparison if r["baseline_id"] == "B0_oracle")
    non_oracle = [r for r in comparison if r["baseline_id"] != "B0_oracle"]
    meaningful_gap = [
        r for r in non_oracle if r["gap_mean_acc_minus_bcr"] >= 0.05 and r["mean_query_accuracy"] >= 0.3
    ]
    high_acc_nat = [r for r in non_oracle if r["high_acc_inconsistent_rate"] >= 0.05]
    # Constraint families that fire while Acc not zero — approximate from rates
    multi_constraint = False
    by_base = defaultdict(list)
    for r in constraint_rows:
        if r["baseline_id"] != "B0_oracle" and r["bundle_violation_rate"] > 0:
            by_base[r["baseline_id"]].append(r["constraint_family"])
    for bid, fams in by_base.items():
        if len(set(fams)) >= 2:
            multi_constraint = True
            break

    if (
        oracle["mean_query_accuracy"] == 1.0
        and oracle["bcr"] == 1.0
        and meaningful_gap
        and high_acc_nat
        and multi_constraint
    ):
        verdict = "BASELINE SIGNAL VALIDATED"
    elif meaningful_gap or high_acc_nat:
        verdict = "PARTIAL SIGNAL"
    else:
        verdict = "NO NATURAL SIGNAL"

    lines = [
        "# WorldConsistMem baseline findings",
        "",
        f"**Verdict:** {verdict}",
        "",
        "## Benchmark freeze",
        "",
        f"- smoke SHA256: `{digest}`",
        f"- expected: `{EXPECTED_SMOKE_SHA256}`",
        "- worlds=25, events=668, bundles=125, queries=825",
        "",
        "## Fairness",
        "",
        "| Baseline | History | Capacity | Index | Retrieval | Reader |",
        "|---|---|---|---|---|---|",
        "| B0_oracle | gold world | n/a | gold states | none | gold reconstruct |",
        f"| B1_flat_append | full obs | unconstrained | append list | none (scan) | structured |",
        f"| B2_latest_only | latest only | #keys | key→obs | none | structured |",
        f"| B3_recency | full | unconstrained | list | lexical+recency k={K} | structured |",
        f"| B4_bm25 | full | unconstrained | NL BM25 | BM25 k={K} | structured |",
        "| B5_reservoir_c8/c16 | reservoir | 8 or 16 obs | reservoir | none | structured |",
        "",
        "Matched-capacity note: B5 is capacity-limited; B1/B3/B4 are unconstrained flat stores.",
        "Do not claim fair architectural comparison across unequal capacities.",
        "",
        "## Metric comparison",
        "",
        "| baseline | run | Acc | BCR | ConsAcc | Gap(Acc-BCR) | highAcc-incons | consist-wrong |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in comparison:
        lines.append(
            f"| {r['baseline_id']} | {r['run_id']} | {r['mean_query_accuracy']} | {r['bcr']} | "
            f"{r['consacc_strict']} | {r['gap_mean_acc_minus_bcr']} | "
            f"{r['high_acc_inconsistent_rate']} | {r['consistent_wrong_rate']} |"
        )

    lines += ["", "## Diagnostic answers", ""]
    lines += [
        "1. **High Acc / low BCR?** See non-oracle rows with positive Gap(Acc-BCR), especially B2/B3/B4.",
        "2. **Query families driving contradictions:** compare query_family_results.csv (historical/transition/provenance vs current).",
        "3. **Constraints beyond Acc:** transition, provenance, multi_hop, temporal rates in constraint_family_results.csv.",
        "4. **Latest-state:** strong current-state Acc expected; historical/transition collapse; bundles become inconsistent.",
        "5. **Flat memory:** near-complete observation replay; residual errors from unobserved W0 ownership seed and retrieval-free policy edge cases.",
        "6. **Retrieval inconsistencies:** missing evidence (low Recall@k), incompatible versions in top-k, temporal selection, provenance mismatch.",
        "7. **Recall vs Acc vs BCR:** see retrieval_diagnostics.csv.",
        "",
        "## Example high-accuracy inconsistent bundles",
        "",
    ]
    for ex in examples.get("high_acc_inconsistent", [])[:3]:
        lines.append(f"- `{ex['baseline_id']}` bundle `{ex['bundle_id']}` Acc={ex['mean_acc']:.3f}")
        for v in ex.get("violations", [])[:2]:
            lines.append(f"  - [{v['constraint_type']}] {v['explanation']}")
    if not examples.get("high_acc_inconsistent"):
        lines.append("- (none above threshold in this run)")

    lines += ["", "## Example consistent-but-wrong bundles", ""]
    for ex in examples.get("consistent_wrong", [])[:3]:
        lines.append(f"- `{ex['baseline_id']}` bundle `{ex['bundle_id']}` Acc={ex['mean_acc']:.3f}")
    if not examples.get("consistent_wrong"):
        lines.append("- (none in this run)")

    lines += [
        "",
        "## Interpretation limit",
        "",
        "Cross-query consistency reveals naturally occurring bundle-level failures that "
        "isolated per-query accuracy does not fully characterize.",
        "",
        "No claim of hierarchical LTKM superiority, external validity, LLM failure, "
        "or architectural causality is made at this stage.",
        "",
    ]
    lines.append(f"\n_Automated verdict tag: {verdict}_\n")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
