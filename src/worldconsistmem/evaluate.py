"""Evaluator independent of any memory system implementation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Optional

from .constraints import check_bundle_constraints
from .generate import GeneratedWorld
from .metrics import AggregateMetrics, BundleMetrics, aggregate_metrics, evaluate_bundle
from .models import ConstraintResult, Prediction, QueryBundle
from .predict import prediction_from_dict


def index_predictions(preds: Iterable[Prediction]) -> dict[str, list[Prediction]]:
    by_bundle: dict[str, list[Prediction]] = defaultdict(list)
    for p in preds:
        by_bundle[p.bundle_id].append(p)
    return by_bundle


def evaluate_predictions(
    worlds: dict[str, GeneratedWorld],
    bundles: list[QueryBundle],
    predictions: list[Prediction],
    relaxed_acc_threshold: float = 0.8,
) -> tuple[list[BundleMetrics], AggregateMetrics, list[ConstraintResult]]:
    by_b = index_predictions(predictions)
    bmetrics: list[BundleMetrics] = []
    all_violations: list[ConstraintResult] = []
    for b in bundles:
        world = worlds[b.world_id]
        preds = by_b.get(b.bundle_id, [])
        bm = evaluate_bundle(world, b, preds)
        bmetrics.append(bm)
        all_violations.extend([r for r in bm.constraint_results if not r.passed])
    agg = aggregate_metrics(
        bmetrics, bundles, relaxed_acc_threshold=relaxed_acc_threshold
    )
    return bmetrics, agg, all_violations


def load_prediction_rows(rows: list[dict[str, Any]]) -> list[Prediction]:
    return [prediction_from_dict(r) for r in rows]
