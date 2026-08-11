"""Prediction schema helpers."""

from __future__ import annotations

from typing import Any

from .models import Prediction, Query, QueryBundle, to_jsonable


REQUIRED_PRED_FIELDS = {
    "bundle_id",
    "query_id",
    "predicted_answer",
    "system_id",
    "run_id",
}


def validate_prediction_row(row: dict[str, Any]) -> list[str]:
    errors = []
    for f in REQUIRED_PRED_FIELDS:
        if f not in row:
            errors.append(f"missing field: {f}")
    return errors


def gold_predictions(
    bundles: list[QueryBundle], system_id: str = "gold", run_id: str = "gold"
) -> list[Prediction]:
    preds: list[Prediction] = []
    for b in bundles:
        for q in b.queries:
            preds.append(
                Prediction(
                    bundle_id=b.bundle_id,
                    query_id=q.query_id,
                    predicted_answer=q.gold_answer,
                    predicted_provenance=(
                        q.supporting_provenance_ids[0]
                        if q.supporting_provenance_ids
                        else None
                    ),
                    system_id=system_id,
                    run_id=run_id,
                    metadata={"source": "gold"},
                )
            )
    return preds


def prediction_from_dict(row: dict[str, Any]) -> Prediction:
    errs = validate_prediction_row(row)
    if errs:
        raise ValueError("; ".join(errs))
    return Prediction(
        bundle_id=row["bundle_id"],
        query_id=row["query_id"],
        predicted_answer=row["predicted_answer"],
        predicted_provenance=row.get("predicted_provenance"),
        system_id=row["system_id"],
        run_id=row["run_id"],
        metadata=row.get("metadata") or {},
    )


def serialize_predictions(preds: list[Prediction]) -> list[dict[str, Any]]:
    return [to_jsonable(p.to_dict()) for p in preds]
