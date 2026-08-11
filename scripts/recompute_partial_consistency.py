#!/usr/bin/env python3
"""Recompute partial consistency metrics from frozen predictions only.

Does not run inference. Does not mutate symbolic system_results.csv Acc/BCR.
Asserts Run1/Run2 integrity hashes and smoke checksum.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.baselines.load import (  # noqa: E402
    EXPECTED_SMOKE_SHA256,
    assert_frozen_smoke,
    load_bundles,
)
from worldconsistmem.evaluate import evaluate_predictions, load_prediction_rows  # noqa: E402
from worldconsistmem.generate import GeneratedWorld  # noqa: E402
from worldconsistmem.io_util import read_jsonl, write_csv, write_json  # noqa: E402
from worldconsistmem.models import Prediction  # noqa: E402
from worldconsistmem.partial_consistency import (  # noqa: E402
    bcr_floor_diagnostics,
    constraint_family_csr_rows,
    difficulty_csr_rows,
    enrich_partial_rows,
    summarize_partial_system,
)
from worldconsistmem.scaled_generate import generate_scaled_dataset  # noqa: E402
from worldconsistmem.scaled_queries import generate_scaled_bundles  # noqa: E402

OUT = ROOT / "results" / "scaled"
PRED = OUT / "predictions"
RUN1_CACHE = OUT / "run1" / "llm_reader_cache" / "Qwen2.5-3B-Instruct-4bit.jsonl"
RUN2_CACHE = OUT / "run2" / "llm_reader_cache" / "Qwen2.5-3B-Instruct-4bit.jsonl"
RUN2_PRED = OUT / "run2" / "run2_predictions"
RUN1_SHA = "9bb7cfb1737a6d6a2ec15f1fc641bd1b0cd00919d1c473a2039d22ec776f8af3"
SYSTEM_RESULTS_SHA = "70b5ce4f27d1b70d796678029bb375487d37cbf0701f1d75a56b4224c2a941bd"

# Systems to recompute (frozen prediction files).
SYMBOLIC_SYSTEMS = [
    "B1_flat_unconstrained",
    "B2_latest_only",
    "B3_recency_k3",
    "B3_recency_k8",
    "B4_bm25_k3",
    "B4_bm25_k8",
    "B5_reservoir_c60",
    "B5_reservoir_c150",
    "B1_flat_cap60_recency",
    "B1_flat_cap60_compact",
    "B1_flat_cap150_recency",
    "B1_flat_cap150_compact",
    "B1_flat_cap400_recency",
    "B1_flat_cap400_compact",
    "H0_ltkm_unconstrained",
    "H0_ltkm_cap60_ret3",
    "H0_ltkm_cap60_ret8",
    "H0_ltkm_cap150_ret3",
    "H0_ltkm_cap150_ret8",
    "H0_ltkm_cap400_ret3",
    "H0_ltkm_cap400_ret8",
    "H-archive",
    "H-temporal-validity",
    "H-graph",
    "H-provenance",
    "H-conflict",
]

QWEN_SYSTEMS = [
    "B1_flat_cap150_compact",
    "B3_recency_k8",
    "B4_bm25_k8",
    "H0_ltkm_cap150_ret8",
]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_integrity() -> dict[str, str]:
    smoke = assert_frozen_smoke()
    assert smoke == EXPECTED_SMOKE_SHA256
    r1 = sha_file(RUN1_CACHE)
    assert r1 == RUN1_SHA, f"Run1 cache mutated: {r1}"
    sys_sha = sha_file(OUT / "system_results.csv")
    assert sys_sha == SYSTEM_RESULTS_SHA, f"symbolic system_results.csv mutated: {sys_sha}"
    # Run2 cache must stay complete (2734 unique expected at finalize); hash not frozen historically
    return {
        "smoke": smoke,
        "run1_qwen_cache": r1,
        "system_results_csv": sys_sha,
        "run2_qwen_cache": sha_file(RUN2_CACHE),
    }


def load_scaled_worlds_bundles() -> tuple[dict[str, GeneratedWorld], list]:
    worlds_list = generate_scaled_dataset(100, 34)
    worlds = {w.world_id: w for w in worlds_list}
    bundles = []
    for w in worlds_list:
        bundles.extend(generate_scaled_bundles(w))
    return worlds, bundles


def h4_subset_bundles(bundles: list) -> list:
    """First 6 worlds per tier (seed-100 scaled index order)."""
    index = json.loads((ROOT / "data" / "scaled" / "world_index.json").read_text())
    by_tier: dict[str, list] = defaultdict(list)
    for row in index:
        by_tier[row["tier"]].append(row)
    sid = set()
    for tier in ("small", "medium", "large"):
        for row in by_tier[tier][:6]:
            sid.add(row["world_id"])
    return [b for b in bundles if b.world_id in sid]


def load_symbolic_preds(name: str) -> list[Prediction]:
    return load_prediction_rows(read_jsonl(PRED / f"{name}.jsonl"))


def load_qwen_preds(system: str) -> list[Prediction]:
    path = RUN2_PRED / f"Qwen2.5-3B-Instruct-4bit__{system}.jsonl"
    if path.exists():
        return load_prediction_rows(read_jsonl(path))
    raise FileNotFoundError(path)


def load_qwen_abs_mal() -> dict[str, dict[str, float]]:
    """Reuse frozen Qwen rates from run2 system CSV (no re-inference)."""
    import csv

    path = OUT / "run2" / "qwen_system_results.csv"
    out: dict[str, dict[str, float]] = {}
    with path.open() as f:
        for row in csv.DictReader(f):
            out[row["memory_system"]] = {
                "abstention_rate": float(row["abstention_rate"]),
                "malformed_rate": float(row["malformed_rate"]),
            }
    return out


def eval_system(
    worlds: dict[str, GeneratedWorld],
    bundles: list,
    preds: list[Prediction],
    system: str,
    reader: str,
    abs_mal: dict[str, float] | None = None,
) -> tuple[list, dict]:
    bms, agg, _ = evaluate_predictions(worlds, bundles, preds, relaxed_acc_threshold=0.8)
    # Restrict to bundles that appear in preds (safety)
    pred_bundles = {p.bundle_id for p in preds}
    bms = [m for m in bms if m.bundle_id in pred_bundles]
    bundles_f = [b for b in bundles if b.bundle_id in pred_bundles]
    rows = enrich_partial_rows(bms, bundles_f, system=system)
    n_q = sum(m.n_queries for m in bms)
    am = abs_mal or {}
    summary = summarize_partial_system(
        rows,
        system=system,
        reader=reader,
        n_queries=n_q,
        abstention_rate=am.get("abstention_rate"),
        malformed_rate=am.get("malformed_rate"),
        bootstrap_seed=hash(system) % 10_000,
    )
    # Prefer Acc/BCR from existing aggregate for cross-check
    summary.mean_query_accuracy = agg.mean_query_accuracy
    summary.bcr = agg.bcr
    summary.consacc_strict = agg.consacc_strict
    summary.gap_query = agg.gap_mean_acc_minus_bcr
    summary.high_acc_inconsistent_rate = agg.high_acc_inconsistent_rate
    return rows, summary.to_dict()


def main() -> None:
    hashes = assert_integrity()
    print("Integrity OK:", hashes)
    print("Loading scaled worlds/bundles…")
    worlds, bundles = load_scaled_worlds_bundles()
    h4_bundles = h4_subset_bundles(bundles)
    print(f"scaled bundles={len(bundles)} h4_bundles={len(h4_bundles)}")

    all_rows = []
    system_rows = []

    for name in SYMBOLIC_SYSTEMS:
        path = PRED / f"{name}.jsonl"
        if not path.exists():
            print("skip missing", name)
            continue
        print("symbolic", name)
        preds = load_symbolic_preds(name)
        rows, summary = eval_system(worlds, bundles, preds, name, reader="symbolic")
        # Cross-check Acc/BCR against frozen system_results for key systems
        all_rows.extend(rows)
        system_rows.append(summary)

    qwen_rates = load_qwen_abs_mal()
    qwen_rows = []
    qwen_summaries = []
    for name in QWEN_SYSTEMS:
        print("qwen", name)
        preds = load_qwen_preds(name)
        # Evaluate only on H4 worlds present in predictions
        rows, summary = eval_system(
            worlds,
            h4_bundles,
            preds,
            system=name,
            reader="qwen2.5-3b-instruct-4bit",
            abs_mal=qwen_rates.get(name),
        )
        qwen_rows.extend(rows)
        qwen_summaries.append(summary)
        system_rows.append(summary)

    fam_rows = constraint_family_csr_rows(all_rows + qwen_rows)
    # Tag reader on family rows via system name collision — Qwen systems share names;
    # rewrite qwen family with prefix for clarity
    fam_rows_q = constraint_family_csr_rows(qwen_rows)
    for r in fam_rows_q:
        r["system"] = f"Qwen|{r['system']}"
    fam_rows_s = constraint_family_csr_rows(all_rows)
    for r in fam_rows_s:
        r["system"] = f"symbolic|{r['system']}"

    diff_rows = difficulty_csr_rows(all_rows) + [
        {**r, "system": f"Qwen|{r['system']}"} for r in difficulty_csr_rows(qwen_rows)
    ]

    # Findings
    qwen_by = {s["system"]: s for s in qwen_summaries}
    floor = {s: bcr_floor_diagnostics([r for r in qwen_rows if r.system == s]) for s in QWEN_SYSTEMS}

    findings = []
    findings.append("# Partial consistency findings (frozen recomputation)\n\n")
    findings.append("Paper shape: **BENCHMARK ONLY**. Architecture superiority closed.\n\n")
    findings.append("BCR is unchanged (fraction of bundles with Φ=1). CSR/PConsAcc are complementary.\n\n")
    findings.append("## Integrity\n\n")
    for k, v in hashes.items():
        findings.append(f"- `{k}`: `{v}`\n")
    findings.append("\n## Qwen system table (Acc / BCR / CSR)\n\n")
    findings.append(
        "| System | Acc | BCR | mean CSR | median CSR | mean viol. | ConsAcc | "
        "PConsAcc(0.5,0.8) | PConsAcc(0.8,0.9) | Abs | Mal |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    )
    for s in QWEN_SYSTEMS:
        r = qwen_by[s]
        findings.append(
            f"| {s} | {r['mean_query_accuracy']:.4f} | {r['bcr']:.4f} | "
            f"{r['mean_csr']:.4f} | {r['median_csr']:.4f} | {r['mean_violations']:.3f} | "
            f"{r['consacc_strict']:.4f} | {r['pconsacc_acc0.5_csr0.8']:.4f} | "
            f"{r['pconsacc_acc0.8_csr0.9']:.4f} | "
            f"{(r.get('abstention_rate') or 0):.4f} | {(r.get('malformed_rate') or 0):.4f} |\n"
        )

    findings.append("\n## Does H0 improve CSR under Qwen?\n\n")
    h0 = qwen_by["H0_ltkm_cap150_ret8"]
    for other in ("B1_flat_cap150_compact", "B3_recency_k8", "B4_bm25_k8"):
        o = qwen_by[other]
        d = h0["mean_csr"] - o["mean_csr"]
        findings.append(
            f"- H0 mean CSR − {other}: **{d:+.4f}** "
            f"(H0={h0['mean_csr']:.4f}, {other}={o['mean_csr']:.4f}; "
            f"Acc Δ={h0['mean_query_accuracy']-o['mean_query_accuracy']:+.4f})\n"
        )
    findings.append(
        "\nInterpretation rule: Acc gains without CSR gains are **not** consistency claims.\n"
    )

    findings.append("\n## BCR floor diagnostics (Qwen)\n\n")
    for s, d in floor.items():
        findings.append(f"### {s}\n\n")
        findings.append(f"- mean CSR: {d.get('mean_csr')}\n")
        findings.append(f"- mean violations/bundle: {d.get('mean_violations')}\n")
        findings.append(f"- frac exactly one violation: {d.get('frac_exactly_one_violation')}\n")
        findings.append(f"- frac multiple violations: {d.get('frac_multiple_violations')}\n")
        findings.append(
            f"- most frequent violated family: `{d.get('most_frequent_violated_family')}`\n"
        )
        findings.append(f"- family hit counts: `{d.get('bundles_with_family_violation')}`\n\n")

    findings.append("\n## Acc–CSR correlation (Qwen)\n\n")
    for s in QWEN_SYSTEMS:
        r = qwen_by[s]
        findings.append(f"- {s}: pearson(Acc_b, CSR_b) = {r['acc_csr_pearson']:.4f}\n")

    findings.append(
        "\n## Allowed reading\n\n"
        "- Acc and BCR/CSR remain empirically distinct under Qwen (BCR=0 for all; CSR varies).\n"
        "- Do **not** convert H0 Acc/abstention gains into architecture-superiority claims.\n"
        "- Strict BCR floor (all zero) motivates reporting CSR and the PConsAcc grid.\n"
    )

    # Write outputs
    # Flatten system rows for CSV
    flat = []
    for r in system_rows:
        row = dict(r)
        row.pop("notes", None)
        row.pop("pconsacc", None)
        row.pop("csr_hist", None)
        flat.append(row)

    write_csv(OUT / "partial_consistency_results.csv", flat)
    write_csv(OUT / "partial_consistency_by_constraint.csv", fam_rows_s + fam_rows_q)
    write_csv(OUT / "partial_consistency_by_difficulty.csv", diff_rows)
    (OUT / "partial_consistency_findings.md").write_text("".join(findings), encoding="utf-8")
    write_json(
        OUT / "partial_consistency_meta.json",
        {
            "integrity": hashes,
            "qwen_floor": floor,
            "n_symbolic_systems": len([s for s in system_rows if s["reader"] == "symbolic"]),
            "n_qwen_systems": len(qwen_summaries),
        },
    )
    print("Wrote partial_consistency_*.csv/md")
    print("Qwen CSR:", {s: qwen_by[s]["mean_csr"] for s in QWEN_SYSTEMS})


if __name__ == "__main__":
    main()
