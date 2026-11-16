#!/usr/bin/env python3
"""Recompute every number cited in the ICLR 2027 rebuttal (PR #10) from committed
per-item tables. Read-only: no input is modified.

Usage: python scripts/verify_rebuttal_numbers.py
"""

from __future__ import annotations

import csv
import random
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
R2 = REPO / "analysis" / "round2"
ARMS = ["F0", "F1", "F2", "F3"]


def rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def binom_two_sided(k: int, n: int) -> float:
    """Exact two-sided binomial p for k successes of n at p=0.5."""
    lo = min(k, n - k)
    return min(1.0, 2 * sum(comb(n, i) for i in range(lo + 1)) / 2**n)


def mcnemar_exact(n_a_only: int, n_b_only: int) -> float:
    n = n_a_only + n_b_only
    return 1.0 if n == 0 else binom_two_sided(min(n_a_only, n_b_only), n)


def sign_test_one_sided(k: int, n: int) -> float:
    """P(X >= k) for X ~ Binomial(n, 0.5)."""
    return sum(comb(n, i) for i in range(k, n + 1)) / 2**n


def cohen_kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    cats = sorted({c for p in pairs for c in p})
    po = sum(a == b for a, b in pairs) / n
    pe = sum(
        (sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n)
        for c in cats
    )
    return (po - pe) / (1 - pe)


def cluster_bootstrap(items: list, key, stat, draws: int = 10000, seed: int = 0):
    """Percentile bootstrap resampling clusters (worlds or cases) with replacement."""
    by = defaultdict(list)
    for it in items:
        by[key(it)].append(it)
    clusters = list(by)
    rng = random.Random(seed)
    vals = []
    for _ in range(draws):
        sample = []
        for _ in clusters:
            sample.extend(by[rng.choice(clusters)])
        vals.append(stat(sample))
    vals.sort()
    return vals[int(0.025 * draws)], vals[int(0.975 * draws) - 1]


def main() -> None:
    out = []

    def report(label: str, value, source: str) -> None:
        out.append((label, value, source))
        print(f"{label}: {value}   [{source}]")

    # ---- Round 2 reliability (reviewer_agreement.csv) ----
    ag = [r for r in rows(R2 / "reviewer_agreement.csv") if r["round2_reviewer_A"]]
    pairs = [(r["round2_reviewer_A"], r["round2_reviewer_B"]) for r in ag]
    agree = sum(a == b for a, b in pairs)
    kappa = cohen_kappa(pairs)
    lo, hi = cluster_bootstrap(
        [(r["case_id"], *p) for r, p in zip(ag, pairs)],
        key=lambda t: t[0],
        stat=lambda s: cohen_kappa([(t[1], t[2]) for t in s]),
    )
    report("Round 2 items", len(ag), "reviewer_agreement.csv, rows with Round 2 labels")
    report("Round 2 Round-1 discordant items",
           sum(r["round1_reviewer_1"] != r["round1_reviewer_2"] for r in ag),
           "reviewer_agreement.csv round1_reviewer_1 vs round1_reviewer_2")
    report("Round 2 cases", len({r["case_id"] for r in ag}), "reviewer_agreement.csv case_id")
    report("Round 2 agreement", f"{agree}/{len(ag)}", "reviewer_agreement.csv round2_reviewer_A vs _B")
    report("Round 2 kappa (unweighted)", round(kappa, 4), "Cohen kappa on the 50 pairs")
    report("Round 2 kappa case-cluster bootstrap 95% CI (20 cases, 10000 draws, seed 0)",
           (round(lo, 3), round(hi, 3)),
           "cluster_bootstrap over case_id; reproduces the reported [0.517, 0.957] only if the reported draw seed matches (seed not recorded)")

    # ---- Per-item temporal and semantic tables ----
    cl = rows(R2 / "case_level_error_analysis.csv")
    mc = [r for r in cl if r["question_status"] == "multi_candidate"]
    report("Multi-candidate items", len(mc), "case_level_error_analysis.csv question_status")
    for a in ARMS:
        stale = sum("earliest" in r[f"{a}_positions"] and "latest" not in r[f"{a}_positions"] for r in mc)
        report(f"{a} stale-state (earliest without latest)", f"{stale}/42",
               "case_level_error_analysis.csv {arm}_positions")

    tmp = rows(R2 / "temporal_state_analysis.csv")
    tmc = [r for r in tmp if r["question_status"] == "multi_candidate"]
    report("temporal_state_analysis multi-candidate rows", len(tmc), "temporal_state_analysis.csv")
    for a in ARMS:
        latest = sum(int(r[f"{a}_temporal_correct"]) for r in tmc)
        report(f"{a} latest-event selection", f"{latest}/42", "temporal_state_analysis.csv {arm}_temporal_correct")

    # Item-level McNemar, latest selection, F2 vs F0 (discordant counts)
    f2_only = sum(int(r["F2_temporal_correct"]) and not int(r["F0_temporal_correct"]) for r in tmc)
    f0_only = sum(int(r["F0_temporal_correct"]) and not int(r["F2_temporal_correct"]) for r in tmc)
    report("Latest F2 vs F0 discordant (F2 only, F0 only)", (f2_only, f0_only),
           "temporal_state_analysis.csv")
    report("Latest F2 minus F0 RD (pp)", round(100 * (f2_only - f0_only) / 42, 1), "(F2-only minus F0-only)/42")
    report("Latest F2 vs F0 exact McNemar p", f"{mcnemar_exact(f2_only, f0_only):.3g}", "exact binomial two-sided")

    # World-level sign test on stale-state counts, F2 vs F0
    per_world = defaultdict(lambda: {a: 0 for a in ARMS})
    worlds = {r["world_id"] for r in mc}
    for r in mc:
        for a in ARMS:
            if "earliest" in r[f"{a}_positions"] and "latest" not in r[f"{a}_positions"]:
                per_world[r["world_id"]][a] += 1
    f2_fewer = sum(per_world[w]["F2"] < per_world[w]["F0"] for w in worlds)
    f0_fewer = sum(per_world[w]["F0"] < per_world[w]["F2"] for w in worlds)
    ties = len(worlds) - f2_fewer - f0_fewer
    report("Worlds with MC items", len(worlds), "case_level_error_analysis.csv world_id")
    report("World sign test (stale F2<F0 / F0<F2 / ties)", (f2_fewer, f0_fewer, ties),
           "per-world stale counts from case_level_error_analysis.csv")
    report("One-sided exact sign test over non-tied worlds",
           f"{sign_test_one_sided(f2_fewer, f2_fewer + f0_fewer):.5f}",
           "P(X>=k), X~Bin(n_nontied, 0.5)")

    # ---- Semantic B1 and B1-nodoc (case_level semantic columns) ----
    sem = {a: sum(int(r[f"{a}_semantic"]) for r in cl) for a in ARMS}
    report("B1 semantic all 150 (F0..F3)", [sem[a] for a in ARMS], "case_level_error_analysis.csv {arm}_semantic")
    nodoc = [r for r in cl if r["question_status"] != "version_unidentifiable"]
    snod = {a: sum(int(r[f"{a}_semantic"]) for r in nodoc) for a in ARMS}
    report("B1-nodoc semantic (n=116, F0..F3)", [f"{snod[a]}/116" for a in ARMS],
           "case_level_error_analysis.csv, question_status != version_unidentifiable")

    def pair(x, y):
        xo = sum(int(r[f"{x}_semantic"]) and not int(r[f"{y}_semantic"]) for r in nodoc)
        yo = sum(int(r[f"{y}_semantic"]) and not int(r[f"{x}_semantic"]) for r in nodoc)
        return xo, yo

    f3o, f0o = pair("F3", "F0")
    report("B1-nodoc F3 vs F0 discordant (F3 only, F0 only)", (f3o, f0o), "item level")
    report("B1-nodoc F3-F0 RD (pp)", round(100 * (f3o - f0o) / 116, 2), "(F3-only minus F0-only)/116")
    report("B1-nodoc F3-F0 exact McNemar p", f"{mcnemar_exact(f3o, f0o):.3g}", "exact binomial two-sided")
    lo, hi = cluster_bootstrap(
        nodoc, key=lambda r: r["world_id"],
        stat=lambda s: 100 * (sum(int(r["F3_semantic"]) - int(r["F0_semantic"]) for r in s) / len(s)),
    )
    report("B1-nodoc F3-F0 world-cluster bootstrap 95% CI (pp, seed 0)", (round(lo, 2), round(hi, 2)),
           "cluster_bootstrap over world_id; reported [9.65, 29.06] in sensitivity_analysis.csv")
    f2o, f3o2 = pair("F2", "F3")
    report("B1-nodoc F2 vs F3 discordant (F2 only, F3 only)", (f2o, f3o2), "item level")
    report("B1-nodoc F2 vs F3 exact McNemar p", f"{mcnemar_exact(f2o, f3o2):.3f}", "exact binomial two-sided")

    doc = [r for r in cl if r["question_status"] == "version_unidentifiable"]
    report("Document items", len(doc), "case_level_error_analysis.csv")
    report("Document spurious semantic credits (F0..F3)",
           [sum(int(r[f"{a}_semantic"]) for r in doc) for a in ARMS],
           "case_level_error_analysis.csv, doc items")

    # ---- Sensitivity scenario labels ----
    sens = rows(R2 / "sensitivity_analysis.csv")
    labels = list(dict.fromkeys(r["scenario"] for r in sens))
    report("Sensitivity scenario labels (distinct)", len(labels), "sensitivity_analysis.csv scenario column")
    report("E-upper semantic (F0..F3)",
           [next(int(r["n_correct"]) for r in sens if r["scenario"] == "E-upper" and r["arm_or_contrast"] == a)
            for a in ARMS],
           "sensitivity_analysis.csv scenario E-upper")

    # ---- BCR expectation ----
    bundles = [l for l in (REPO / "data/scaled/bundles.jsonl").read_text().splitlines() if l.strip()]
    import json
    sizes = [len(json.loads(l)["queries"]) for l in bundles]
    mean_size = sum(sizes) / len(sizes)
    report("Bundles", len(sizes), "data/scaled/bundles.jsonl")
    report("Mean queries per bundle", round(mean_size, 2), "data/scaled/bundles.jsonl")
    report("Expected consistent bundles at acc 0.185 (independence)",
           round(len(sizes) * 0.185**mean_size, 4), "bundles x 0.185^mean_size")


if __name__ == "__main__":
    main()
