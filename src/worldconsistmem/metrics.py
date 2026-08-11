"""Benchmark metrics for WorldConsistMem."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .constraints import bundle_is_consistent, check_bundle_constraints
from .generate import GeneratedWorld
from .models import ConstraintFamily, ConstraintResult, Prediction, Query, QueryBundle, to_jsonable


def answers_equal(pred: Any, gold: Any) -> bool:
    """Structured exact equality."""
    if isinstance(pred, dict) and isinstance(gold, dict):
        if set(pred.keys()) != set(gold.keys()):
            # allow gold keys subset if values match on gold keys
            return all(answers_equal(pred.get(k), gold[k]) for k in gold.keys())
        return all(answers_equal(pred[k], gold[k]) for k in gold.keys())
    if isinstance(pred, (list, tuple)) and isinstance(gold, (list, tuple)):
        return len(pred) == len(gold) and all(answers_equal(a, b) for a, b in zip(pred, gold))
    return pred == gold


def per_query_accuracy(query: Query, prediction: Prediction) -> float:
    return 1.0 if answers_equal(prediction.predicted_answer, query.gold_answer) else 0.0


@dataclass
class BundleMetrics:
    bundle_id: str
    world_id: str
    n_queries: int
    mean_query_accuracy: float
    all_correct: bool
    consistent: bool
    constraint_results: list[ConstraintResult] = field(default_factory=list)
    per_query: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "world_id": self.world_id,
            "n_queries": self.n_queries,
            "mean_query_accuracy": self.mean_query_accuracy,
            "all_correct": self.all_correct,
            "consistent": self.consistent,
            "per_query": self.per_query,
            "violations": [r.to_dict() for r in self.constraint_results if not r.passed],
        }


@dataclass
class AggregateMetrics:
    n_bundles: int
    n_queries: int
    mean_query_accuracy: float
    bundle_accuracy_rate: float  # fraction bundles with all answers correct
    bcr: float
    consacc_strict: float
    consacc_relaxed: float
    relaxed_acc_threshold: float
    # User brief Gap = MeanQueryAccuracy - BCR
    gap_mean_acc_minus_bcr: float
    # Planning doc Gap_bundle = Acc_bundle - ConsAcc
    gap_bundle_acc_minus_consacc: float
    high_acc_inconsistent_rate: float
    temporal_violation_rate: float
    provenance_violation_rate: float
    constraint_violation_rates: dict[str, float]
    family_accuracy: dict[str, float]
    notes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self.__dict__)


def evaluate_bundle(
    world: GeneratedWorld,
    bundle: QueryBundle,
    predictions: list[Prediction],
) -> BundleMetrics:
    qmap = {q.query_id: q for q in bundle.queries}
    pmap = {p.query_id: p for p in predictions}
    per_q: dict[str, float] = {}
    for qid, q in qmap.items():
        if qid not in pmap:
            per_q[qid] = 0.0
        else:
            per_q[qid] = per_query_accuracy(q, pmap[qid])
    mean_acc = sum(per_q.values()) / len(per_q) if per_q else 0.0
    results = check_bundle_constraints(world, bundle, predictions)
    return BundleMetrics(
        bundle_id=bundle.bundle_id,
        world_id=bundle.world_id,
        n_queries=len(bundle.queries),
        mean_query_accuracy=mean_acc,
        all_correct=all(v == 1.0 for v in per_q.values()),
        consistent=bundle_is_consistent(results),
        constraint_results=results,
        per_query=per_q,
    )


def aggregate_metrics(
    bundle_metrics: list[BundleMetrics],
    bundles: list[QueryBundle],
    relaxed_acc_threshold: float = 0.8,
    high_acc_threshold: float = 0.8,
) -> AggregateMetrics:
    n_b = len(bundle_metrics)
    n_q = sum(m.n_queries for m in bundle_metrics)
    mean_acc = (
        sum(m.mean_query_accuracy * m.n_queries for m in bundle_metrics) / n_q if n_q else 0.0
    )
    bundle_acc_rate = sum(1 for m in bundle_metrics if m.all_correct) / n_b if n_b else 0.0
    bcr = sum(1 for m in bundle_metrics if m.consistent) / n_b if n_b else 0.0
    consacc_strict = (
        sum(1 for m in bundle_metrics if m.all_correct and m.consistent) / n_b if n_b else 0.0
    )
    consacc_relaxed = (
        sum(
            1
            for m in bundle_metrics
            if m.mean_query_accuracy >= relaxed_acc_threshold and m.consistent
        )
        / n_b
        if n_b
        else 0.0
    )
    high_acc_inconsist = [
        m for m in bundle_metrics if m.mean_query_accuracy >= high_acc_threshold and not m.consistent
    ]
    high_acc_inconsistent_rate = len(high_acc_inconsist) / n_b if n_b else 0.0

    # Constraint family violation rates (fraction of bundles with ≥1 violation of type)
    fam_counts = {c.value: 0 for c in ConstraintFamily}
    temporal_viol_bundles = 0
    prov_viol_bundles = 0
    for m in bundle_metrics:
        failed_types = {r.constraint_type for r in m.constraint_results if not r.passed}
        for ft in failed_types:
            fam_counts[ft.value] += 1
        if ConstraintFamily.TEMPORAL in failed_types or ConstraintFamily.TRANSITION in failed_types:
            temporal_viol_bundles += 1
        if ConstraintFamily.PROVENANCE in failed_types:
            prov_viol_bundles += 1
    constraint_violation_rates = {
        k: (v / n_b if n_b else 0.0) for k, v in fam_counts.items()
    }

    # Per query-family accuracy
    fam_hits: dict[str, list[float]] = {}
    bmap = {b.bundle_id: b for b in bundles}
    for m in bundle_metrics:
        b = bmap[m.bundle_id]
        for q in b.queries:
            fam_hits.setdefault(q.family.value, []).append(m.per_query.get(q.query_id, 0.0))
    family_accuracy = {k: (sum(v) / len(v) if v else 0.0) for k, v in fam_hits.items()}

    return AggregateMetrics(
        n_bundles=n_b,
        n_queries=n_q,
        mean_query_accuracy=mean_acc,
        bundle_accuracy_rate=bundle_acc_rate,
        bcr=bcr,
        consacc_strict=consacc_strict,
        consacc_relaxed=consacc_relaxed,
        relaxed_acc_threshold=relaxed_acc_threshold,
        gap_mean_acc_minus_bcr=mean_acc - bcr,
        gap_bundle_acc_minus_consacc=bundle_acc_rate - consacc_strict,
        high_acc_inconsistent_rate=high_acc_inconsistent_rate,
        temporal_violation_rate=temporal_viol_bundles / n_b if n_b else 0.0,
        provenance_violation_rate=prov_viol_bundles / n_b if n_b else 0.0,
        constraint_violation_rates=constraint_violation_rates,
        family_accuracy=family_accuracy,
        notes={
            "primary_gap": "Gap_query = MeanQueryAccuracy - BCR (frozen primary)",
            "secondary_gap": "Gap_bundle = BundleAccuracy - ConsAcc_strict (frozen secondary)",
            "gap_mean_acc_minus_bcr": "PRIMARY Gap_query: MeanQueryAccuracy - BCR",
            "gap_bundle_acc_minus_consacc": (
                "SECONDARY Gap_bundle: Acc_bundle - ConsAcc_strict "
                "(Acc_bundle = fraction of fully-correct bundles)"
            ),
            "metric_freeze": (
                "configs/METRIC_FREEZE.md — BCR/ConsAcc/Acc semantics unchanged from smoke; "
                "primary=Gap_query, secondary=Gap_bundle."
            ),
        },
    )
