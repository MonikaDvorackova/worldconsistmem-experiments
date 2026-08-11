"""World-level bootstrap CIs and paired comparisons."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Callable, Iterable


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def bootstrap_ci(
    values: list[float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0, "n": 0}
    rng = random.Random(seed)
    boots = []
    n = len(values)
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        boots.append(mean(sample))
    boots.sort()
    lo_i = int(alpha / 2 * n_boot)
    hi_i = int((1 - alpha / 2) * n_boot) - 1
    return {
        "mean": mean(values),
        "lo": boots[max(0, lo_i)],
        "hi": boots[min(n_boot - 1, hi_i)],
        "n": float(n),
    }


def world_metric(
    bundle_rows: list[dict[str, Any]],
    world_id: str,
    metric: str,
) -> float:
    rows = [r for r in bundle_rows if r["world_id"] == world_id]
    if not rows:
        return 0.0
    if metric == "bcr":
        return mean([1.0 if r["consistent"] else 0.0 for r in rows])
    if metric == "consacc":
        return mean([1.0 if r["all_correct"] and r["consistent"] else 0.0 for r in rows])
    if metric == "bundle_acc":
        return mean([1.0 if r["all_correct"] else 0.0 for r in rows])
    if metric == "mean_acc":
        return mean([r["mean_query_accuracy"] for r in rows])
    raise KeyError(metric)


def paired_deltas(
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
    metric: str,
) -> list[float]:
    worlds = sorted({r["world_id"] for r in rows_a} & {r["world_id"] for r in rows_b})
    return [
        world_metric(rows_a, w, metric) - world_metric(rows_b, w, metric) for w in worlds
    ]


def cohen_d(deltas: list[float]) -> float:
    if len(deltas) < 2:
        return 0.0
    m = mean(deltas)
    var = sum((x - m) ** 2 for x in deltas) / (len(deltas) - 1)
    sd = math.sqrt(var) if var > 0 else 0.0
    return m / sd if sd else 0.0


def holm_correct(pvals: list[tuple[str, float]]) -> list[tuple[str, float, float]]:
    """Return (name, p, p_holm) sorted by p."""
    ordered = sorted(pvals, key=lambda x: x[1])
    m = len(ordered)
    out = []
    for i, (name, p) in enumerate(ordered):
        adj = min(1.0, p * (m - i))
        out.append((name, p, adj))
    # enforce monotonicity
    for i in range(1, len(out)):
        if out[i][2] < out[i - 1][2]:
            out[i] = (out[i][0], out[i][1], out[i - 1][2])
    return out


def sign_test_p(deltas: list[float]) -> float:
    """Two-sided sign test p-value (exact binomial), ignoring zeros."""
    pos = sum(1 for d in deltas if d > 0)
    neg = sum(1 for d in deltas if d < 0)
    n = pos + neg
    if n == 0:
        return 1.0
    # exact two-sided
    from math import comb

    def cdf(k):
        return sum(comb(n, i) for i in range(k + 1)) / (2**n)

    p = 2 * min(cdf(min(pos, neg)), 1 - cdf(min(pos, neg) - 1) if min(pos, neg) > 0 else 1)
    return min(1.0, p)
