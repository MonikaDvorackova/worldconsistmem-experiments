"""Partial / non-saturating consistency diagnostics (complementary to BCR).

BCR remains the fraction of bundles with Φ=1 (all applicable constraints pass).
These metrics do not redefine BCR, ConsAcc_strict, or Gap_query.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

from .metrics import BundleMetrics
from .models import ConstraintFamily, ConstraintResult, QueryBundle, to_jsonable
from .stats_world import bootstrap_ci, mean


# Predeclared PConsAcc grid (do not cherry-pick a single cell).
PCONSACC_ACC_TAUS = (0.5, 0.8)
PCONSACC_CSR_TAUS = (0.8, 0.9)


def csr_from_results(results: Sequence[ConstraintResult]) -> float:
    """Constraint Satisfaction Rate for one bundle: satisfied / applicable."""
    n = len(results)
    if n == 0:
        return 1.0
    return sum(1 for r in results if r.passed) / n


def n_violations(results: Sequence[ConstraintResult]) -> int:
    return sum(1 for r in results if not r.passed)


def n_applicable(results: Sequence[ConstraintResult]) -> int:
    return len(results)


@dataclass
class PartialBundleRow:
    bundle_id: str
    world_id: str
    system: str
    mean_query_accuracy: float
    all_correct: bool
    consistent: bool  # Φ=1 (strict BCR unit)
    csr: float
    n_applicable: int
    n_violated: int
    normalized_violations: float  # n_violated / n_applicable (0 if none)
    difficulty: Optional[str] = None
    tier: Optional[str] = None
    family_violations: dict[str, int] = field(default_factory=dict)
    family_applicable: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self.__dict__)


def partial_from_bundle_metrics(
    bm: BundleMetrics,
    *,
    system: str,
    difficulty: Optional[str] = None,
    tier: Optional[str] = None,
) -> PartialBundleRow:
    results = bm.constraint_results
    n_app = n_applicable(results)
    n_viol = n_violations(results)
    csr = csr_from_results(results)
    # Integrity: BCR unit (consistent) iff CSR == 1 when applicable constraints exist,
    # and also when n_app==0 (vacuous consistency).
    assert bm.consistent == (csr == 1.0), (
        f"BCR/CSR mismatch on {bm.bundle_id}: consistent={bm.consistent} csr={csr}"
    )
    fam_viol: dict[str, int] = defaultdict(int)
    fam_app: dict[str, int] = defaultdict(int)
    for r in results:
        key = r.constraint_type.value
        fam_app[key] += 1
        if not r.passed:
            fam_viol[key] += 1
    return PartialBundleRow(
        bundle_id=bm.bundle_id,
        world_id=bm.world_id,
        system=system,
        mean_query_accuracy=bm.mean_query_accuracy,
        all_correct=bm.all_correct,
        consistent=bm.consistent,
        csr=csr,
        n_applicable=n_app,
        n_violated=n_viol,
        normalized_violations=(n_viol / n_app) if n_app else 0.0,
        difficulty=difficulty,
        tier=tier,
        family_violations=dict(fam_viol),
        family_applicable=dict(fam_app),
    )


def enrich_partial_rows(
    bundle_metrics: list[BundleMetrics],
    bundles: list[QueryBundle],
    system: str,
) -> list[PartialBundleRow]:
    meta = {b.bundle_id: b.metadata for b in bundles}
    rows = []
    for bm in bundle_metrics:
        m = meta.get(bm.bundle_id, {}) or {}
        rows.append(
            partial_from_bundle_metrics(
                bm,
                system=system,
                difficulty=m.get("difficulty"),
                tier=m.get("tier"),
            )
        )
    return rows


def pconsacc(
    rows: list[PartialBundleRow],
    acc_tau: float,
    csr_tau: float,
) -> float:
    """Partial Consistent Accuracy: Acc_b >= tau and CSR_b >= tau_c."""
    if not rows:
        return 0.0
    return mean(
        [1.0 if (r.mean_query_accuracy >= acc_tau and r.csr >= csr_tau) else 0.0 for r in rows]
    )


def pconsacc_grid(rows: list[PartialBundleRow]) -> dict[str, float]:
    out: dict[str, float] = {}
    for a in PCONSACC_ACC_TAUS:
        for c in PCONSACC_CSR_TAUS:
            out[f"pconsacc_acc{a}_csr{c}"] = pconsacc(rows, a, c)
    return out


def pearson_corr(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2 or n != len(ys):
        return float("nan")
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0.0 or dy == 0.0:
        return float("nan")
    return num / (dx * dy)


def median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def histogram(xs: list[float], edges: Sequence[float]) -> dict[str, int]:
    """Count values into bins defined by ascending edges (right-open except last)."""
    counts = {f"[{edges[i]},{edges[i+1]})": 0 for i in range(len(edges) - 1)}
    last = f"[{edges[-2]},{edges[-1]}]"
    counts[last] = 0
    # simpler: labeled bins
    labels = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        closed = i == len(edges) - 2
        labels.append((lo, hi, closed, f"[{lo:.1f},{hi:.1f}]" + ("" if closed else ")")))
    out = {lab: 0 for *_, lab in labels}
    for x in xs:
        for lo, hi, closed, lab in labels:
            if closed and lo <= x <= hi:
                out[lab] += 1
                break
            if (not closed) and lo <= x < hi:
                out[lab] += 1
                break
    return out


@dataclass
class PartialSystemSummary:
    system: str
    reader: str
    n_bundles: int
    n_queries: int
    mean_query_accuracy: float
    bcr: float
    mean_csr: float
    median_csr: float
    mean_violations: float
    median_violations: float
    mean_normalized_violations: float
    consacc_strict: float
    gap_query: float
    high_acc_inconsistent_rate: float
    abstention_rate: Optional[float]
    malformed_rate: Optional[float]
    pconsacc: dict[str, float]
    acc_csr_pearson: float
    csr_hist: dict[str, int]
    csr_world_mean: float
    csr_world_ci95_lo: float
    csr_world_ci95_hi: float
    bcr_world_ci95_lo: float
    bcr_world_ci95_hi: float
    notes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = to_jsonable(self.__dict__)
        # flatten pconsacc into top-level for CSV friendliness
        for k, v in self.pconsacc.items():
            d[k] = v
        return d


def summarize_partial_system(
    rows: list[PartialBundleRow],
    *,
    system: str,
    reader: str = "symbolic",
    n_queries: int = 0,
    abstention_rate: Optional[float] = None,
    malformed_rate: Optional[float] = None,
    high_acc_threshold: float = 0.8,
    bootstrap_seed: int = 0,
) -> PartialSystemSummary:
    n_b = len(rows)
    mean_acc = mean([r.mean_query_accuracy for r in rows])
    bcr = mean([1.0 if r.consistent else 0.0 for r in rows])
    csrs = [r.csr for r in rows]
    viols = [float(r.n_violated) for r in rows]
    norm_v = [r.normalized_violations for r in rows]
    consacc = mean([1.0 if (r.all_correct and r.consistent) else 0.0 for r in rows])
    high_inconsist = mean(
        [
            1.0 if (r.mean_query_accuracy >= high_acc_threshold and not r.consistent) else 0.0
            for r in rows
        ]
    )
    # world-level CSR / BCR
    by_w: dict[str, list[PartialBundleRow]] = defaultdict(list)
    for r in rows:
        by_w[r.world_id].append(r)
    world_csr = [mean([x.csr for x in by_w[w]]) for w in sorted(by_w)]
    world_bcr = [mean([1.0 if x.consistent else 0.0 for x in by_w[w]]) for w in sorted(by_w)]
    csr_ci = bootstrap_ci(world_csr, seed=bootstrap_seed)
    bcr_ci = bootstrap_ci(world_bcr, seed=bootstrap_seed + 1)
    return PartialSystemSummary(
        system=system,
        reader=reader,
        n_bundles=n_b,
        n_queries=n_queries or sum(
            # best-effort: not stored on PartialBundleRow; caller should pass
            0 for _ in rows
        ),
        mean_query_accuracy=mean_acc,
        bcr=bcr,
        mean_csr=mean(csrs),
        median_csr=median(csrs),
        mean_violations=mean(viols),
        median_violations=median(viols),
        mean_normalized_violations=mean(norm_v),
        consacc_strict=consacc,
        gap_query=mean_acc - bcr,
        high_acc_inconsistent_rate=high_inconsist,
        abstention_rate=abstention_rate,
        malformed_rate=malformed_rate,
        pconsacc=pconsacc_grid(rows),
        acc_csr_pearson=pearson_corr(
            [r.mean_query_accuracy for r in rows], csrs
        ),
        csr_hist=histogram(csrs, (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)),
        csr_world_mean=csr_ci["mean"],
        csr_world_ci95_lo=csr_ci["lo"],
        csr_world_ci95_hi=csr_ci["hi"],
        bcr_world_ci95_lo=bcr_ci["lo"],
        bcr_world_ci95_hi=bcr_ci["hi"],
        notes={
            "bcr_unchanged": "BCR = fraction of bundles with CSR=1",
            "pconsacc": "grid over acc∈{0.5,0.8} × csr∈{0.8,0.9}; report full grid",
        },
    )


def constraint_family_csr_rows(rows: list[PartialBundleRow]) -> list[dict[str, Any]]:
    """Per-system × family: mean family CSR and violation rate."""
    # Aggregate applicable/violated counts across bundles
    by_sys: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for fam, n_app in r.family_applicable.items():
            n_viol = r.family_violations.get(fam, 0)
            fam_csr = 1.0 - (n_viol / n_app) if n_app else 1.0
            by_sys[r.system][fam].append(fam_csr)
    out = []
    for sys, fams in sorted(by_sys.items()):
        for fam, vals in sorted(fams.items()):
            out.append(
                {
                    "system": sys,
                    "constraint_family": fam,
                    "mean_family_csr": round(mean(vals), 6),
                    "median_family_csr": round(median(vals), 6),
                    "n_bundles_with_family": len(vals),
                    "frac_bundles_any_violation": round(
                        mean([1.0 if v < 1.0 else 0.0 for v in vals]), 6
                    ),
                }
            )
    return out


def difficulty_csr_rows(rows: list[PartialBundleRow]) -> list[dict[str, Any]]:
    out = []
    by: dict[tuple[str, str, str], list[PartialBundleRow]] = defaultdict(list)
    for r in rows:
        diff = r.difficulty or "unknown"
        tier = r.tier or "unknown"
        by[(r.system, diff, tier)].append(r)
    for (sys, diff, tier), group in sorted(by.items()):
        csrs = [g.csr for g in group]
        out.append(
            {
                "system": sys,
                "difficulty": diff,
                "tier": tier,
                "n_bundles": len(group),
                "mean_acc": round(mean([g.mean_query_accuracy for g in group]), 6),
                "bcr": round(mean([1.0 if g.consistent else 0.0 for g in group]), 6),
                "mean_csr": round(mean(csrs), 6),
                "median_csr": round(median(csrs), 6),
                "mean_violations": round(mean([float(g.n_violated) for g in group]), 6),
            }
        )
    return out


def bcr_floor_diagnostics(rows: list[PartialBundleRow]) -> dict[str, Any]:
    """Is BCR=0 from one recurring constraint or widespread violations?"""
    if not rows:
        return {}
    viol_counts = [r.n_violated for r in rows]
    fully = sum(1 for r in rows if r.csr == 1.0)
    # Dominant failing family among bundles with ≥1 violation
    fam_counter: Counter[str] = Counter()
    single_viol = 0
    multi_viol = 0
    for r in rows:
        if r.n_violated == 0:
            continue
        if r.n_violated == 1:
            single_viol += 1
        else:
            multi_viol += 1
        for fam, n in r.family_violations.items():
            if n > 0:
                fam_counter[fam] += 1
    return {
        "n_bundles": len(rows),
        "frac_csr_eq_1": fully / len(rows),
        "bcr": mean([1.0 if r.consistent else 0.0 for r in rows]),
        "mean_csr": mean([r.csr for r in rows]),
        "mean_violations": mean([float(x) for x in viol_counts]),
        "median_violations": median([float(x) for x in viol_counts]),
        "frac_exactly_one_violation": single_viol / len(rows),
        "frac_multiple_violations": multi_viol / len(rows),
        "bundles_with_family_violation": dict(fam_counter),
        "most_frequent_violated_family": (
            fam_counter.most_common(1)[0][0] if fam_counter else None
        ),
    }
