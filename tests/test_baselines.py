"""Tests for WorldConsistMem baseline adapters."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.baselines.adapters import (
    BM25RetrievalMemory,
    FlatAppendMemory,
    GoldReplayOracle,
    LatestStateMemory,
    RecencyWeightedMemory,
    ReservoirMemory,
    _oracle_answer,
)
from worldconsistmem.baselines.load import (
    EXPECTED_SMOKE_SHA256,
    assert_frozen_smoke,
    load_bundles,
    load_observations,
    load_worlds_via_seed,
    verify_worlds_match_frozen,
)
from worldconsistmem.baselines.reader import StructuredReader, filter_observations
from worldconsistmem.evaluate import evaluate_predictions
from worldconsistmem.models import Observation, Query, QueryFamily, AnswerSchema
from worldconsistmem.predict import validate_prediction_row


@pytest.fixture(scope="module")
def smoke():
    digest = assert_frozen_smoke()
    assert digest == EXPECTED_SMOKE_SHA256
    worlds = load_worlds_via_seed(42, 3)
    # verify only first 3 worlds' events against frozen prefix
    obs = load_observations()
    bundles = [b for b in load_bundles() if b.world_id in worlds]
    return worlds, obs, bundles


def test_freeze_checksum():
    assert assert_frozen_smoke() == EXPECTED_SMOKE_SHA256


def test_oracle_perfect_on_smoke_subset(smoke):
    worlds, obs, bundles = smoke
    # Use full 25 worlds for oracle perfection on matching bundles
    all_worlds = load_worlds_via_seed(42, 25)
    verify_worlds_match_frozen(all_worlds)
    all_obs = load_observations()
    all_bundles = load_bundles()
    adapter = GoldReplayOracle(all_worlds, run_id="oracle")
    preds = []
    from collections import defaultdict

    by_w = defaultdict(list)
    for b in all_bundles:
        by_w[b.world_id].append(b)
    for wid, blist in by_w.items():
        adapter.reset()
        adapter.bind_world(wid)
        for o in all_obs[wid]:
            adapter.ingest(o)
        for b in blist:
            adapter.bind_world(wid)
            preds.extend(adapter.answer_bundle(b))
    _, agg, viol = evaluate_predictions(all_worlds, all_bundles, preds)
    assert agg.mean_query_accuracy == 1.0
    assert agg.bcr == 1.0
    assert agg.consacc_strict == 1.0
    assert viol == []


def test_no_baseline_reads_gold_answer_field(smoke):
    worlds, obs, bundles = smoke
    b = bundles[0]
    # Corrupt gold answers — baselines must not depend on them
    for q in b.queries:
        q.gold_answer = "POISONED_GOLD"
    adapter = FlatAppendMemory()
    for o in obs[b.world_id]:
        adapter.ingest(o)
    preds = adapter.answer_bundle(b)
    for p in preds:
        assert p.predicted_answer != "POISONED_GOLD" or p.metadata.get("status") == "abstain"


def test_oracle_does_not_read_gold_answer_field(smoke):
    worlds, obs, bundles = smoke
    b = next(x for x in bundles if "ceo" in x.bundle_id)
    original = [q.gold_answer for q in b.queries]
    for q in b.queries:
        q.gold_answer = "POISON"
    adapter = GoldReplayOracle(worlds)
    adapter.bind_world(b.world_id)
    for o in obs[b.world_id]:
        adapter.ingest(o)
    preds = adapter.answer_bundle(b)
    # Restore and compare against recomputed oracle from world
    for q, p, orig in zip(b.queries, preds, original):
        q.gold_answer = orig
        ans, _ = _oracle_answer(worlds[b.world_id], q)
        assert p.predicted_answer == ans


def test_latest_discards_superseded_state(smoke):
    worlds, obs, bundles = smoke
    wid = next(iter(worlds))
    mem = LatestStateMemory()
    for o in obs[wid]:
        mem.ingest(o)
    # Role key should have only one observation
    role_obs = [o for o in mem.stored_observations() if "role" in mem._key(o)]
    keys = [mem._key(o) for o in mem.stored_observations()]
    assert len(keys) == len(set(keys))
    assert mem.memory_size() < len([o for o in obs[wid] if not o.is_distractor])


def test_flat_replays_all_observations(smoke):
    worlds, obs, bundles = smoke
    wid = next(iter(worlds))
    mem = FlatAppendMemory()
    for o in obs[wid]:
        mem.ingest(o)
    assert mem.memory_size() == len([o for o in obs[wid] if not o.is_distractor])


def test_retrieval_uses_only_retrieved_records(smoke):
    worlds, obs, bundles = smoke
    b = next(x for x in bundles if "ceo" in x.bundle_id)
    mem = BM25RetrievalMemory(k=2)
    for o in obs[b.world_id]:
        mem.ingest(o)
    q = b.queries[0]
    result = mem.answer(q, as_of_t=q.target_time)
    assert len(result.retrieved_observation_ids) <= 2
    # Reader must not see non-retrieved: re-answer with only retrieved
    retrieved = [o for o in obs[b.world_id] if o.observation_id in result.retrieved_observation_ids]
    reader = StructuredReader()
    r2 = reader.answer(q, retrieved, as_of_t=q.target_time)
    assert r2.answer == result.answer


def test_reservoir_respects_capacity(smoke):
    worlds, obs, bundles = smoke
    wid = next(iter(worlds))
    mem = ReservoirMemory(capacity=5, seed=0)
    for o in obs[wid]:
        mem.ingest(o)
    assert mem.memory_size() == 5


def test_deterministic_by_seed(smoke):
    worlds, obs, bundles = smoke
    wid = next(iter(worlds))
    b = next(x for x in bundles if x.world_id == wid)

    def run(seed):
        m = ReservoirMemory(capacity=8, seed=seed)
        for o in obs[wid]:
            m.ingest(o)
        return [p.predicted_answer for p in m.answer_bundle(b)]

    assert run(0) == run(0)
    # Different seeds may differ
    assert isinstance(run(1), list)


def test_prediction_schema(smoke):
    worlds, obs, bundles = smoke
    b = bundles[0]
    mem = FlatAppendMemory()
    for o in obs[b.world_id]:
        mem.ingest(o)
    for p in mem.answer_bundle(b):
        assert validate_prediction_row(p.to_dict()) == []


def test_typed_abstention_or_coverage(smoke):
    worlds, obs, bundles = smoke
    b = bundles[0]
    mem = LatestStateMemory()
    for o in obs[b.world_id]:
        mem.ingest(o)
    for p in mem.answer_bundle(b):
        assert p.metadata.get("status") in ("ok", "abstain", "unsupported", "error")


def test_provenance_from_stored_only(smoke):
    worlds, obs, bundles = smoke
    b = next(x for x in bundles if "ceo" in x.bundle_id)
    mem = FlatAppendMemory()
    stored_provs = set()
    for o in obs[b.world_id]:
        mem.ingest(o)
        if not o.is_distractor:
            stored_provs.add(o.provenance_id)
    for p in mem.answer_bundle(b):
        if p.predicted_provenance is not None:
            assert p.predicted_provenance in stored_provs or p.metadata.get("status") != "ok"


def test_no_future_observation_leak():
    """Adversarial temporal-leakage test: later replacement must not change past holder."""
    reader = StructuredReader()
    early = Observation(
        observation_id="w:obs:1",
        event_id="w:e:1",
        t=1,
        provenance_id="w:prov:1",
        structured={
            "event_id": "w:e:1",
            "event_type": "role_assignment",
            "t": 1,
            "payload": {
                "person_id": "p0",
                "org_id": "o0",
                "role": "CEO",
                "exclusive": True,
            },
            "provenance_id": "w:prov:1",
            "affected_ids": [],
            "actor_id": None,
            "preconditions": [],
        },
        text_canonical="t=1 CEO p0",
        text_paraphrase="t=1 CEO p0",
    )
    late = Observation(
        observation_id="w:obs:5",
        event_id="w:e:5",
        t=5,
        provenance_id="w:prov:5",
        structured={
            "event_id": "w:e:5",
            "event_type": "role_replacement",
            "t": 5,
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
        text_canonical="t=5 CEO p1",
        text_paraphrase="t=5 CEO p1",
    )
    q = Query(
        query_id="q",
        bundle_id="b",
        family=QueryFamily.HISTORICAL_STATE,
        text="Who was CEO at t=2?",
        structured={"attribute": "role_holder", "org_id": "o0", "role": "CEO", "t": 2},
        target_time=2,
        target_interval=None,
        gold_answer="p0",
        answer_schema=AnswerSchema.ENTITY_ID,
        applicable_constraints=[],
        supporting_event_ids=["w:e:1"],
        supporting_provenance_ids=["w:prov:1"],
        metadata={"slot": "ceo_historical"},
    )
    # Interval semantics: even with the future replacement present, t=2 → p0.
    result = reader.answer(q, [early, late], as_of_t=2)
    assert result.answer == "p0"
    # Retrieval cut: if only the future obs is provided, must not invent p0/p1 wrongly as sole latest without history
    only_late = reader.answer(q, [late], as_of_t=2)
    assert only_late.status == "abstain" or only_late.answer != "p1"


def test_filter_observations_cuts_future():
    obs = [
        Observation("a", "e1", 1, "p1", {"t": 1, "event_type": "x", "payload": {}}, "", ""),
        Observation("b", "e2", 5, "p2", {"t": 5, "event_type": "x", "payload": {}}, "", ""),
    ]
    got = filter_observations(obs, as_of_t=2)
    assert [o.observation_id for o in got] == ["a"]


def test_reader_unit_ceo_current():
    reader = StructuredReader()
    o = Observation(
        "w:obs:1",
        "w:e:1",
        1,
        "w:prov:1",
        {
            "event_id": "w:e:1",
            "event_type": "role_assignment",
            "t": 1,
            "payload": {"person_id": "p0", "org_id": "o0", "role": "CEO", "exclusive": True},
            "provenance_id": "w:prov:1",
            "affected_ids": [],
            "actor_id": None,
            "preconditions": [],
        },
        "ceo",
        "ceo",
    )
    # Need join first for realism but reader doesn't require employment for role read
    q = Query(
        "q",
        "b",
        QueryFamily.CURRENT_STATE,
        "ceo?",
        {"attribute": "role_holder", "org_id": "o0", "role": "CEO", "t": 1},
        1,
        None,
        "p0",
        AnswerSchema.ENTITY_ID,
        [],
        ["w:e:1"],
        ["w:prov:1"],
        {"slot": "ceo_current"},
    )
    assert reader.answer(q, [o], as_of_t=1).answer == "p0"
