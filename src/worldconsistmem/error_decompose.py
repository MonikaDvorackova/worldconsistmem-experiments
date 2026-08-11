"""Error decomposition for incorrect predictions."""

from __future__ import annotations

from typing import Any, Optional

from .metrics import answers_equal
from .models import Prediction, Query, QueryBundle
from .baselines.interface import ABSTAIN_TOKEN


ERROR_LABELS = (
    "required_evidence_absent",
    "evidence_stored_not_retrieved",
    "incompatible_versions_co_retrieved",
    "reader_failed_on_correct_evidence",
    "temporal_selection_error",
    "relational_composition_error",
    "provenance_mismatch",
    "conflict_resolution_error",
    "malformed_output",
    "typed_abstention",
)


def classify_error(
    query: Query,
    pred: Prediction,
    *,
    support_event_ids: list[str],
    stored_event_ids: Optional[set[str]] = None,
    retrieved_ids: Optional[list[str]] = None,
    reader_kind: str = "symbolic",
) -> str:
    """Classify a single incorrect (or abstaining) prediction."""
    status = pred.metadata.get("status", "ok")
    if status == "malformed" or pred.metadata.get("malformed"):
        return "malformed_output"
    if status == "abstain" or pred.predicted_answer == ABSTAIN_TOKEN:
        return "typed_abstention"

    retrieved = list(retrieved_ids or pred.metadata.get("retrieved_observation_ids") or [])
    stored = stored_event_ids

    # Map retrieved observation ids to event ids when possible
    retrieved_events = set()
    for rid in retrieved:
        if ":obs:" in str(rid):
            # observation id encodes t; support uses event ids
            retrieved_events.add(str(rid))
        else:
            retrieved_events.add(str(rid))

    support = set(support_event_ids or query.supporting_event_ids)

    if stored is not None and support and not (support & stored):
        return "required_evidence_absent"

    if stored is not None and support and (support & stored):
        # evidence in memory — check retrieval
        # For LTKM, retrieved are fact/edge ids not event ids; use n_consulted and detail
        if retrieved is not None and len(retrieved) == 0 and reader_kind == "symbolic":
            return "evidence_stored_not_retrieved"
        # Heuristic: historical miss often temporal
        if query.family.value == "historical_state":
            return "temporal_selection_error"
        if query.family.value == "multi_hop":
            return "relational_composition_error"
        if query.family.value == "provenance":
            if pred.predicted_answer != query.gold_answer:
                return "provenance_mismatch"
        if "conflict" in query.family.value or query.metadata.get("slot", "").startswith("conf"):
            return "conflict_resolution_error"
        if reader_kind.startswith("llm"):
            return "reader_failed_on_correct_evidence"
        # incompatible co-retrieval if many records and transition/historical wrong
        if len(retrieved) >= 3 and query.family.value in ("transition", "historical_state"):
            return "incompatible_versions_co_retrieved"
        return "reader_failed_on_correct_evidence"

    if query.family.value == "historical_state":
        return "temporal_selection_error"
    if query.family.value == "multi_hop":
        return "relational_composition_error"
    if query.family.value == "provenance":
        return "provenance_mismatch"
    if status == "abstain":
        return "typed_abstention"
    return "required_evidence_absent"


def decompose_predictions(
    bundles: list[QueryBundle],
    preds: list[Prediction],
    *,
    stored_events_by_world: Optional[dict[str, set[str]]] = None,
    reader_kind: str = "symbolic",
) -> list[dict[str, Any]]:
    qmap = {q.query_id: q for b in bundles for q in b.queries}
    bmap = {b.bundle_id: b for b in bundles}
    rows = []
    for p in preds:
        q = qmap.get(p.query_id)
        if q is None:
            continue
        correct = answers_equal(p.predicted_answer, q.gold_answer)
        if correct and p.metadata.get("status") not in ("abstain", "malformed"):
            label = "correct"
        else:
            wid = bmap[p.bundle_id].world_id
            stored = None
            if stored_events_by_world is not None:
                stored = stored_events_by_world.get(wid)
            label = classify_error(
                q,
                p,
                support_event_ids=list(q.supporting_event_ids),
                stored_event_ids=stored,
                reader_kind=reader_kind,
            )
        rows.append(
            {
                "system_id": p.system_id,
                "world_id": bmap[p.bundle_id].world_id,
                "bundle_id": p.bundle_id,
                "query_id": p.query_id,
                "family": q.family.value,
                "difficulty": bmap[p.bundle_id].metadata.get("difficulty"),
                "tier": bmap[p.bundle_id].metadata.get("tier"),
                "correct": correct,
                "error_label": label,
                "status": p.metadata.get("status"),
            }
        )
    return rows
