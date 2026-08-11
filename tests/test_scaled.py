"""Scaled study tests — do not mutate smoke fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from worldconsistmem.baselines.capacity import CapacityFlatMemory
from worldconsistmem.baselines.load import EXPECTED_SMOKE_SHA256, assert_frozen_smoke, load_bundles
from worldconsistmem.error_decompose import classify_error, decompose_predictions
from worldconsistmem.evaluate import evaluate_predictions
from worldconsistmem.llm_reader import build_evidence_from_observations
from worldconsistmem.ltkm.adapter import LTKMAdapter
from worldconsistmem.ltkm.memory import HierarchicalMemory, LTKMConfig
from worldconsistmem.metrics import aggregate_metrics, answers_equal
from worldconsistmem.models import Prediction
from worldconsistmem.observe import generate_observations
from worldconsistmem.predict import gold_predictions
from worldconsistmem.scaled_generate import TIERS, generate_scaled_world
from worldconsistmem.scaled_queries import generate_scaled_bundles
from worldconsistmem.baselines.interface import ABSTAIN_TOKEN

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "data" / "smoke"


def test_smoke_regression_preserved():
    assert assert_frozen_smoke() == EXPECTED_SMOKE_SHA256
    # smoke files untouched presence
    assert (SMOKE / "observations.jsonl").exists()


def test_scaled_deterministic_generation():
    a = generate_scaled_world(100, 3, "medium")
    b = generate_scaled_world(100, 3, "medium")
    assert [e.event_id for e in a.events] == [e.event_id for e in b.events]
    assert a.world_id == b.world_id


def test_world_diversity_across_tiers():
    sizes = {}
    for tier in TIERS:
        w = generate_scaled_world(101, 0, tier)
        sizes[tier] = len(w.events)
    assert sizes["small"] < sizes["medium"] < sizes["large"]
    assert 20 <= sizes["small"] <= 50
    assert 70 <= sizes["medium"] <= 140
    assert 180 <= sizes["large"] <= 320


def test_event_preconditions_scaled():
    w = generate_scaled_world(102, 1, "small")
    # all events applied successfully into replay length
    assert len(w.states) == len(w.events) + 1


def test_constraint_coverage_by_tier():
    for tier in TIERS:
        w = generate_scaled_world(103, 0, tier)
        bundles = generate_scaled_bundles(w)
        fams = {c for b in bundles for q in b.queries for c in q.applicable_constraints}
        assert len(fams) >= 4
        diffs = {b.metadata.get("difficulty") for b in bundles}
        assert diffs & {"simple", "intermediate", "complex"}


def test_capacity_accounting_no_hidden_overflow():
    w = generate_scaled_world(104, 0, "medium")
    obs = generate_observations(w)
    cap = 40
    mem = CapacityFlatMemory(capacity=cap, policy="recency")
    for o in obs:
        mem.ingest(o)
    assert mem.memory_size() <= cap
    # distractors ignored
    assert all(not o.is_distractor for o in mem._obs)


def test_ltkm_capacity_no_hidden_overflow():
    w = generate_scaled_world(104, 1, "medium")
    obs = generate_observations(w)
    cap = 80
    m = HierarchicalMemory(LTKMConfig(max_logical_records=cap))
    for o in obs:
        m.ingest(o)
    assert m.logical_record_count() <= cap


def test_matched_retrieval_budget_accounting():
    w = generate_scaled_world(105, 0, "small")
    obs = generate_observations(w)
    adapter = LTKMAdapter(LTKMConfig(max_retrieval_records=3))
    for o in obs:
        adapter.ingest(o)
    bundles = generate_scaled_bundles(w)
    q = bundles[0].queries[0]
    from worldconsistmem.ltkm.retrieval import LTKMRetriever

    pack = LTKMRetriever(adapter.memory).retrieve(q)
    assert len(pack.record_ids) <= 3


def test_deterministic_eviction():
    w = generate_scaled_world(106, 0, "medium")
    obs = [o for o in generate_observations(w) if not o.is_distractor]
    a = CapacityFlatMemory(30, "recency", seed=0)
    b = CapacityFlatMemory(30, "recency", seed=0)
    for o in obs:
        a.ingest(o)
        b.ingest(o)
    assert [o.observation_id for o in a._obs] == [o.observation_id for o in b._obs]


def test_llm_evidence_isolation_no_gold_leakage():
    w = generate_scaled_world(107, 0, "small")
    obs = generate_observations(w)[:5]
    bundles = generate_scaled_bundles(w)
    q = bundles[0].queries[0]
    pack = build_evidence_from_observations(q, obs)
    blob = json.dumps(pack.__dict__)
    assert "gold_answer" not in blob
    assert q.gold_answer is not None  # gold exists on query but not in evidence pack
    assert "gold_answer" not in json.dumps(pack.evidence)


def test_prediction_schema_compatibility_scaled():
    w = generate_scaled_world(108, 0, "small")
    bundles = generate_scaled_bundles(w)
    preds = gold_predictions(bundles, system_id="gold")
    for p in preds:
        d = p.to_dict()
        assert "query_id" in d and "predicted_answer" in d


def test_scaled_eval_matches_smoke_metric_semantics():
    """Gold predictions on smoke still yield Acc=BCR=1 under same evaluate path."""
    from worldconsistmem.baselines.load import load_worlds_via_seed, load_observations

    worlds = load_worlds_via_seed(42, 3)
    bundles = [b for b in load_bundles() if b.world_id in worlds][:5]
    # trim to those worlds' bundles
    bundles = [b for b in load_bundles() if b.world_id in worlds]
    preds = gold_predictions(bundles)
    _, agg, _ = evaluate_predictions(worlds, bundles, preds)
    assert agg.mean_query_accuracy == 1.0
    assert agg.bcr == 1.0
    assert agg.gap_mean_acc_minus_bcr == 0.0
    assert "primary_gap" in agg.notes or "PRIMARY" in agg.notes.get("gap_mean_acc_minus_bcr", "")


def test_error_decomposition_labeling():
    w = generate_scaled_world(109, 0, "small")
    bundles = generate_scaled_bundles(w)
    q = bundles[0].queries[0]
    p = Prediction(
        bundle_id=q.bundle_id,
        query_id=q.query_id,
        predicted_answer=ABSTAIN_TOKEN,
        metadata={"status": "abstain"},
    )
    label = classify_error(q, p, support_event_ids=list(q.supporting_event_ids))
    assert label == "typed_abstention"
    rows = decompose_predictions(bundles, [p])
    assert rows[0]["error_label"] == "typed_abstention"


def test_reproducibility_by_seed_scaled_bundles():
    w1 = generate_scaled_world(110, 2, "large")
    w2 = generate_scaled_world(110, 2, "large")
    b1 = generate_scaled_bundles(w1)
    b2 = generate_scaled_bundles(w2)
    assert [b.bundle_id for b in b1] == [b.bundle_id for b in b2]
    assert [q.gold_answer for b in b1 for q in b.queries] == [
        q.gold_answer for b in b2 for q in b.queries
    ]
