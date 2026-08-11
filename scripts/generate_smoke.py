"""End-to-end smoke benchmark generation and validation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from worldconsistmem.corrupt import (
    CORRUPTION_FN,
    apply_all_corruptions,
    corrupt_consistent_wrong_world,
    corrupt_high_acc_inconsistent,
    select_example_bundle,
)
from worldconsistmem.evaluate import evaluate_predictions
from worldconsistmem.generate import GeneratedWorld, generate_worlds
from worldconsistmem.io_util import write_csv, write_json, write_jsonl
from worldconsistmem.observe import generate_observations
from worldconsistmem.predict import gold_predictions
from worldconsistmem.queries import generate_bundles


ROOT = Path(__file__).resolve().parents[1]


def build_smoke(
    seed: int = 42,
    n_worlds: int = 25,
    min_events: int = 20,
    min_bundles: int = 5,
    relaxed_acc_threshold: float = 0.8,
    out_data: Path | None = None,
    out_metrics: Path | None = None,
) -> dict[str, Any]:
    out_data = out_data or (ROOT / "data" / "smoke")
    out_metrics = out_metrics or (ROOT / "results")
    out_data.mkdir(parents=True, exist_ok=True)
    out_metrics.mkdir(parents=True, exist_ok=True)

    worlds = generate_worlds(seed, n_worlds, min_events=min_events)
    world_map = {w.world_id: w for w in worlds}

    all_events = []
    all_obs = []
    all_bundles = []
    for w in worlds:
        for e in w.events:
            row = e.to_dict()
            row["world_id"] = w.world_id
            all_events.append(row)
        for o in generate_observations(w):
            row = o.to_dict()
            row["world_id"] = w.world_id
            all_obs.append(row)
        all_bundles.extend(generate_bundles(w, min_bundles=min_bundles))

    gold = gold_predictions(all_bundles)
    corrupt_map = apply_all_corruptions(all_bundles)
    corrupted_rows = []
    for name, preds in corrupt_map.items():
        for p in preds:
            row = p.to_dict()
            row["corruption_type"] = name
            corrupted_rows.append(row)

    write_jsonl(out_data / "worlds.jsonl", [w.to_dict() for w in worlds])
    write_jsonl(out_data / "events.jsonl", all_events)
    write_jsonl(out_data / "observations.jsonl", all_obs)
    write_jsonl(out_data / "query_bundles.jsonl", [b.to_dict() for b in all_bundles])
    write_jsonl(out_data / "gold_predictions.jsonl", [p.to_dict() for p in gold])
    write_jsonl(out_data / "corrupted_predictions.jsonl", corrupted_rows)

    # Gold metrics
    _, gold_agg, gold_viol = evaluate_predictions(
        world_map, all_bundles, gold, relaxed_acc_threshold=relaxed_acc_threshold
    )

    # Per-corruption metrics
    corruption_rows = []
    all_corrupt_violations = []
    for name, preds in corrupt_map.items():
        bms, agg, viols = evaluate_predictions(
            world_map, all_bundles, preds, relaxed_acc_threshold=relaxed_acc_threshold
        )
        corruption_rows.append(
            {
                "corruption": name,
                "mean_query_accuracy": round(agg.mean_query_accuracy, 4),
                "bcr": round(agg.bcr, 4),
                "consacc_strict": round(agg.consacc_strict, 4),
                "consacc_relaxed": round(agg.consacc_relaxed, 4),
                "gap_mean_acc_minus_bcr": round(agg.gap_mean_acc_minus_bcr, 4),
                "gap_bundle_acc_minus_consacc": round(agg.gap_bundle_acc_minus_consacc, 4),
                "high_acc_inconsistent_rate": round(agg.high_acc_inconsistent_rate, 4),
                "temporal_violation_rate": round(agg.temporal_violation_rate, 4),
                "provenance_violation_rate": round(agg.provenance_violation_rate, 4),
            }
        )
        for v in viols:
            d = v.to_dict()
            d["corruption"] = name
            all_corrupt_violations.append(d)

    write_json(out_metrics / "smoke_metrics.json", {
        "gold": gold_agg.to_dict(),
        "scale": _scale_report(worlds, all_bundles, all_events),
        "corruption": corruption_rows,
    })
    write_csv(out_metrics / "corruption_metrics.csv", corruption_rows)
    write_jsonl(out_metrics / "constraint_violations.jsonl", all_corrupt_violations)

    # Validation report with full example
    example = select_example_bundle(all_bundles)
    ex_world = world_map[example.world_id]
    ex_gold = gold_predictions([example])
    ex_high = corrupt_high_acc_inconsistent(example, ex_gold)
    ex_wrong = corrupt_consistent_wrong_world(example, ex_gold)
    high_bm, high_agg, high_viol = evaluate_predictions(
        {ex_world.world_id: ex_world}, [example], ex_high, relaxed_acc_threshold
    )
    wrong_bm, wrong_agg, wrong_viol = evaluate_predictions(
        {ex_world.world_id: ex_world}, [example], ex_wrong, relaxed_acc_threshold
    )
    gold_bm, _, _ = evaluate_predictions(
        {ex_world.world_id: ex_world}, [example], ex_gold, relaxed_acc_threshold
    )

    report = _validation_markdown(
        worlds,
        all_bundles,
        all_events,
        gold_agg,
        corruption_rows,
        example,
        ex_world,
        gold_bm[0],
        high_bm[0],
        wrong_bm[0],
        ex_gold,
        ex_high,
        ex_wrong,
    )
    (out_metrics / "benchmark_validation.md").write_text(report, encoding="utf-8")

    verdict = _decide_verdict(gold_agg, corruption_rows, worlds, all_bundles)
    return {
        "verdict": verdict,
        "gold": gold_agg.to_dict(),
        "corruption": corruption_rows,
        "scale": _scale_report(worlds, all_bundles, all_events),
        "paths": {
            "data": str(out_data),
            "metrics": str(out_metrics),
        },
    }


def _scale_report(worlds, bundles, events) -> dict[str, Any]:
    qfam = Counter()
    for b in bundles:
        for q in b.queries:
            qfam[q.family.value] += 1
    # Constraint families are defined in library; count applicable annotations
    cfam = Counter()
    for b in bundles:
        for q in b.queries:
            for c in q.applicable_constraints:
                cfam[c.value] += 1
    return {
        "n_worlds": len(worlds),
        "n_events": len(events),
        "min_events_per_world": min(len(w.events) for w in worlds),
        "n_bundles": len(bundles),
        "min_bundles_per_world": min(
            sum(1 for b in bundles if b.world_id == w.world_id) for w in worlds
        ),
        "n_queries": sum(len(b.queries) for b in bundles),
        "min_queries_per_bundle": min(len(b.queries) for b in bundles),
        "query_family_distribution": dict(qfam),
        "constraint_family_annotation_counts": dict(cfam),
    }


def _decide_verdict(gold_agg, corruption_rows, worlds, bundles) -> str:
    if gold_agg.mean_query_accuracy < 1.0 or gold_agg.bcr < 1.0:
        return "INVALID"
    by = {r["corruption"]: r for r in corruption_rows}
    high = by.get("high_acc_inconsistent")
    wrong = by.get("consistent_wrong_world")
    if not high or not wrong:
        return "INVALID"
    if high["mean_query_accuracy"] < 0.8 or high["bcr"] >= high["mean_query_accuracy"]:
        return "INVALID"
    if high["gap_mean_acc_minus_bcr"] <= 0:
        return "INVALID"
    if wrong["bcr"] <= wrong["mean_query_accuracy"]:
        # need BCR high while Acc low — at least BCR > Acc
        if wrong["bcr"] < 0.5 or wrong["mean_query_accuracy"] > wrong["bcr"]:
            return "PARTIALLY VALIDATED"
    # Scale checks
    if len(worlds) < 25 or min(len(w.events) for w in worlds) < 20:
        return "PARTIALLY VALIDATED"
    if len(bundles) < 25 * 5:
        return "PARTIALLY VALIDATED"
    return "VALIDATED"


def _validation_markdown(
    worlds,
    bundles,
    events,
    gold_agg,
    corruption_rows,
    example,
    ex_world,
    gold_bm,
    high_bm,
    wrong_bm,
    ex_gold,
    ex_high,
    ex_wrong,
) -> str:
    scale = _scale_report(worlds, bundles, events)
    lines = [
        "# WorldConsistMem smoke benchmark validation",
        "",
        "## Scale",
        "",
        f"- worlds: {scale['n_worlds']}",
        f"- events: {scale['n_events']} (min/world={scale['min_events_per_world']})",
        f"- bundles: {scale['n_bundles']} (min/world={scale['min_bundles_per_world']})",
        f"- queries: {scale['n_queries']} (min/bundle={scale['min_queries_per_bundle']})",
        f"- query-family distribution: `{scale['query_family_distribution']}`",
        f"- constraint-family annotation counts: `{scale['constraint_family_annotation_counts']}`",
        "",
        "## Metric definition note",
        "",
        "Planning `consistency-metrics.md` defines "
        "`Gap_bundle = Acc_bundle - ConsAcc`. "
        "The implementation milestone brief defines "
        "`Gap = MeanQueryAccuracy - BCR`. "
        "**Both are reported**; they are not identical.",
        "",
        "## Gold metrics",
        "",
        f"- mean_query_accuracy: {gold_agg.mean_query_accuracy}",
        f"- BCR: {gold_agg.bcr}",
        f"- ConsAcc strict: {gold_agg.consacc_strict}",
        f"- ConsAcc relaxed (threshold={gold_agg.relaxed_acc_threshold}): {gold_agg.consacc_relaxed}",
        f"- Gap (MeanQueryAcc - BCR): {gold_agg.gap_mean_acc_minus_bcr}",
        f"- Gap_bundle (Acc_bundle - ConsAcc): {gold_agg.gap_bundle_acc_minus_consacc}",
        "",
        "## Corruption suite",
        "",
        "| corruption | Acc | BCR | ConsAcc | Gap(Acc-BCR) |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in corruption_rows:
        lines.append(
            f"| {r['corruption']} | {r['mean_query_accuracy']} | {r['bcr']} | "
            f"{r['consacc_strict']} | {r['gap_mean_acc_minus_bcr']} |"
        )

    lines += [
        "",
        "## Full bundle example",
        "",
        f"World: `{example.world_id}`  Bundle: `{example.bundle_id}`",
        "",
        "### Gold history (event summaries)",
        "",
    ]
    for e in ex_world.events:
        lines.append(f"- t={e.t} `{e.event_type.value}` {e.payload} prov={e.provenance_id}")

    lines += ["", "### Questions and answers", ""]
    gmap = {p.query_id: p for p in ex_gold}
    hmap = {p.query_id: p for p in ex_high}
    wmap = {p.query_id: p for p in ex_wrong}
    for q in example.queries:
        lines.append(f"**{q.query_id}** ({q.family.value})")
        lines.append(f"- Q: {q.text}")
        lines.append(f"- gold: `{gmap[q.query_id].predicted_answer}`")
        lines.append(f"- high-acc corrupt: `{hmap[q.query_id].predicted_answer}`")
        lines.append(f"- consistent-wrong: `{wmap[q.query_id].predicted_answer}`")
        lines.append("")

    lines += [
        "### Gold bundle metrics",
        f"- mean Acc: {gold_bm.mean_query_accuracy}",
        f"- consistent (Φ): {gold_bm.consistent}",
        f"- BCR contribution: {1 if gold_bm.consistent else 0}",
        "",
        "### High-accuracy inconsistent corruption",
        f"- mean Acc: {high_bm.mean_query_accuracy}",
        f"- consistent: {high_bm.consistent}",
        f"- triggered constraints:",
    ]
    for v in high_bm.constraint_results:
        if not v.passed:
            lines.append(f"  - [{v.constraint_type.value}] {v.constraint_id}: {v.explanation}")

    lines += [
        "",
        "### Consistent-but-wrong corruption",
        f"- mean Acc: {wrong_bm.mean_query_accuracy}",
        f"- consistent: {wrong_bm.consistent}",
        f"- triggered constraints:",
    ]
    for v in wrong_bm.constraint_results:
        if not v.passed:
            lines.append(f"  - [{v.constraint_type.value}] {v.constraint_id}: {v.explanation}")
    if all(v.passed for v in wrong_bm.constraint_results):
        lines.append("  - (none — internally consistent alternate world)")

    lines += [
        "",
        f"- Gap on high-acc example: Acc - consistent = "
        f"{high_bm.mean_query_accuracy} - {1.0 if high_bm.consistent else 0.0}",
        "",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import json

    result = build_smoke()
    print(json.dumps({"verdict": result["verdict"], "scale": result["scale"]}, indent=2))
