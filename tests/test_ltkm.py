"""LTKM core and anti-triviality tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.baselines.load import (
    EXPECTED_SMOKE_SHA256,
    assert_frozen_smoke,
    load_bundles,
    load_observations,
    load_worlds_via_seed,
)
from worldconsistmem.evaluate import evaluate_predictions
from worldconsistmem.ltkm.adapter import LTKMAdapter, make_ablation
from worldconsistmem.ltkm.diagnostics import assert_no_raw_scan_in_answer_path, store_routing_table
from worldconsistmem.ltkm.memory import HierarchicalMemory, LTKMConfig
from worldconsistmem.ltkm.retrieval import LTKMRetriever
from worldconsistmem.metrics import answers_equal
from worldconsistmem.models import Observation, Query, QueryFamily, AnswerSchema


def test_freeze_unchanged():
    assert assert_frozen_smoke() == EXPECTED_SMOKE_SHA256


def test_deterministic_ingestion():
    obs = load_observations()["w0042_000"]
    m1, m2 = HierarchicalMemory(), HierarchicalMemory()
    for o in obs:
        m1.ingest(o)
        m2.ingest(o)
    assert [r.to_dict() for r in m1.current.items()] == [r.to_dict() for r in m2.current.items()]
    assert len(m1.archive) == len(m2.archive)


def test_invariants_after_each_obs():
    m = HierarchicalMemory()
    for o in load_observations()["w0042_000"]:
        m.ingest(o)
        errs = m.lifecycle.check_invariants()
        assert errs == [], errs


def test_no_raw_obs_during_answer():
    m = HierarchicalMemory()
    for o in load_observations()["w0042_000"][:5]:
        m.ingest(o)
    assert_no_raw_scan_in_answer_path(m)


def test_no_gold_answer_access():
    worlds = load_worlds_via_seed(42, 1)
    obs = load_observations()
    bundles = [b for b in load_bundles() if b.world_id in worlds]
    b = bundles[0]
    for q in b.queries:
        q.gold_answer = "POISON"
    ad = LTKMAdapter()
    for o in obs[b.world_id]:
        ad.ingest(o)
    preds = ad.answer_bundle(b)
    assert all(p.predicted_answer != "POISON" for p in preds)


def test_no_materialized_world_access():
    # Adapter constructor does not take worlds
    ad = LTKMAdapter()
    assert not hasattr(ad, "worlds")
    assert not hasattr(ad.memory, "worlds")


def test_store_routing_not_universal_scan():
    table = store_routing_table()
    assert "current_state" in table
    assert "archive" in table["historical_state"]
    ad = LTKMAdapter()
    wid = "w0042_000"
    for o in load_observations()[wid]:
        ad.ingest(o)
    b = next(x for x in load_bundles() if x.world_id == wid and "ceo" in x.bundle_id)
    q = next(q for q in b.queries if q.metadata.get("slot") == "ceo_current")
    pack = LTKMRetriever(ad.memory).retrieve(q)
    n_obs = len([o for o in load_observations()[wid] if not o.is_distractor])
    assert pack.n_consulted < n_obs
    assert pack.n_consulted <= 5


def test_prediction_schema_and_eval():
    worlds = load_worlds_via_seed(42, 2)
    obs = load_observations()
    bundles = [b for b in load_bundles() if b.world_id in worlds]
    ad = LTKMAdapter()
    preds = []
    from collections import defaultdict

    by = defaultdict(list)
    for b in bundles:
        by[b.world_id].append(b)
    for wid, bl in by.items():
        ad.reset()
        for o in obs[wid]:
            ad.ingest(o)
        for b in bl:
            preds.extend(ad.answer_bundle(b))
    _, agg, viol = evaluate_predictions(worlds, bundles, preds)
    assert agg.mean_query_accuracy == 1.0
    assert agg.bcr == 1.0
    assert viol == []


def test_archive_ablation_harms_historical():
    worlds = load_worlds_via_seed(42, 2)
    obs = load_observations()
    bundles = [b for b in load_bundles() if b.world_id in worlds]

    def run(ad):
        preds = []
        from collections import defaultdict

        by = defaultdict(list)
        for b in bundles:
            by[b.world_id].append(b)
        for wid, bl in by.items():
            ad.reset()
            for o in obs[wid]:
                ad.ingest(o)
            for b in bl:
                preds.extend(ad.answer_bundle(b))
        return evaluate_predictions(worlds, bundles, preds)[1]

    full = run(LTKMAdapter())
    ab = run(make_ablation("H-archive"))
    assert ab.family_accuracy.get("historical_state", 1) < full.family_accuracy.get("historical_state", 0) - 0.05 or ab.bcr < full.bcr - 0.05


def test_graph_ablation_harms_multihop():
    worlds = load_worlds_via_seed(42, 2)
    obs = load_observations()
    bundles = [b for b in load_bundles() if b.world_id in worlds]

    def run(ad):
        preds = []
        from collections import defaultdict

        by = defaultdict(list)
        for b in bundles:
            by[b.world_id].append(b)
        for wid, bl in by.items():
            ad.reset()
            for o in obs[wid]:
                ad.ingest(o)
            for b in bl:
                preds.extend(ad.answer_bundle(b))
        return evaluate_predictions(worlds, bundles, preds)[1]

    full = run(LTKMAdapter())
    ab = run(make_ablation("H-graph"))
    assert ab.family_accuracy.get("multi_hop", 1) < full.family_accuracy.get("multi_hop", 0) - 0.05


def test_temporal_ablation_harms_consistency():
    worlds = load_worlds_via_seed(42, 2)
    obs = load_observations()
    bundles = [b for b in load_bundles() if b.world_id in worlds]

    def run(ad):
        preds = []
        from collections import defaultdict

        by = defaultdict(list)
        for b in bundles:
            by[b.world_id].append(b)
        for wid, bl in by.items():
            ad.reset()
            for o in obs[wid]:
                ad.ingest(o)
            for b in bl:
                preds.extend(ad.answer_bundle(b))
        return evaluate_predictions(worlds, bundles, preds)[1]

    full = run(LTKMAdapter())
    ab = run(make_ablation("H-temporal-validity"))
    assert ab.bcr < full.bcr - 0.05 or ab.temporal_violation_rate > full.temporal_violation_rate + 0.05


def test_resource_accounting():
    ad = LTKMAdapter()
    for o in load_observations()["w0042_000"]:
        ad.ingest(o)
    snap = ad.memory.resource_snapshot()
    assert snap["n_current"] > 0
    assert snap["n_archive"] > 0
    assert snap["logical_records"] > 0
    assert snap["serialized_bytes"] > 0


def test_no_future_leak_historical():
    m = HierarchicalMemory()
    early = Observation(
        "w:obs:1",
        "w:e:1",
        1,
        "w:prov:1",
        {
            "event_type": "role_assignment",
            "t": 1,
            "event_id": "w:e:1",
            "payload": {"person_id": "p0", "org_id": "o0", "role": "CEO", "exclusive": True},
            "provenance_id": "w:prov:1",
            "affected_ids": [],
            "actor_id": None,
            "preconditions": [],
        },
        "",
        "",
    )
    late = Observation(
        "w:obs:5",
        "w:e:5",
        5,
        "w:prov:5",
        {
            "event_type": "role_replacement",
            "t": 5,
            "event_id": "w:e:5",
            "payload": {
                "org_id": "o0",
                "role": "CEO",
                "new_person_id": "p1",
                "old_person_id": "p0",
            },
            "provenance_id": "w:prov:5",
            "affected_ids": [],
            "actor_id": None,
            "preconditions": [],
        },
        "",
        "",
    )
    m.ingest(early)
    m.ingest(late)
    from worldconsistmem.ltkm.memory import fact_key_role

    hist = m.archive.at_time(fact_key_role("o0", "CEO"), 2)
    assert hist is not None and hist.value == "p0"
    cur = m.current.get(fact_key_role("o0", "CEO"))
    assert cur is not None and cur.value == "p1"
