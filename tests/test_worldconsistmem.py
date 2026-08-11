"""WorldConsistMem unit and integration tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.constraints import check_bundle_constraints
from worldconsistmem.corrupt import CORRUPTION_FN, corrupt_consistent_wrong_world, corrupt_high_acc_inconsistent
from worldconsistmem.evaluate import evaluate_predictions
from worldconsistmem.generate import generate_world, generate_worlds
from worldconsistmem.models import EventType
from worldconsistmem.observe import generate_observations
from worldconsistmem.predict import gold_predictions, validate_prediction_row
from worldconsistmem.queries import generate_bundles
from worldconsistmem.world import InvalidEventError, apply_event, replay


def test_deterministic_generation_by_seed():
    a = generate_world(42, 0)
    b = generate_world(42, 0)
    c = generate_world(42, 1)
    assert [e.to_dict() for e in a.events] == [e.to_dict() for e in b.events]
    assert a.final.to_dict() == b.final.to_dict()
    assert a.world_id != c.world_id
    assert [e.event_id for e in a.events] != [e.event_id for e in c.events]


def test_event_precondition_enforcement():
    w = generate_world(7, 0)
    # Duplicate exclusive CEO assignment without replacement must fail
    bad = w.events[1].__class__(
        event_id="bad",
        event_type=EventType.ROLE_ASSIGNMENT,
        t=w.T + 1,
        actor_id=None,
        affected_ids=[],
        payload={
            "person_id": w.meta["ceo0"],
            "org_id": w.meta["ceo_org"],
            "role": "CEO",
            "exclusive": True,
        },
        preconditions=[],
        provenance_id="badprov",
    )
    with pytest.raises(InvalidEventError):
        apply_event(w.final, bad)


def test_state_replay_from_event_log():
    w = generate_world(3, 2)
    states = replay(w.initial, w.events)
    assert len(states) == len(w.events) + 1
    assert states[-1].to_dict() == w.final.to_dict()
    for i, s in enumerate(states):
        assert s.t == i


def test_no_contradictions_in_gold_world():
    for w in generate_worlds(11, 5, min_events=20):
        for s in w.states:
            assert s.check_no_exclusive_role_collisions() == []
            assert s.check_single_owner() == []
            assert s.check_single_canonical_doc() == []


def test_validity_intervals():
    w = generate_world(5, 0)
    replace_t = w.meta["ceo_replace_t"]
    org = w.meta["ceo_org"]
    before = w.states[replace_t - 1].role_holder(org, "CEO")
    after = w.states[replace_t].role_holder(org, "CEO")
    assert before is not None and after is not None
    assert before.person_id != after.person_id
    # Closed interval is materialised on the post-transition state.
    closed = next(
        r
        for r in w.states[replace_t].roles
        if r.org_id == org and r.role == "CEO" and r.person_id == before.person_id
    )
    assert closed.interval.end == replace_t
    assert after.interval.start == replace_t
    assert closed.interval.contains(replace_t - 1)
    assert not closed.interval.contains(replace_t)
    assert after.interval.contains(replace_t)


def test_query_gold_correctness_and_support():
    w = generate_world(9, 0)
    bundles = generate_bundles(w, min_bundles=5)
    for b in bundles:
        assert len(b.queries) >= 5
        entities = set(b.focal_entities)
        for q in b.queries:
            assert q.supporting_event_ids, f"no support events for {q.query_id}"
            assert q.gold_answer is not None or q.gold_answer is False
            # dependency: structured query references focal subgraph somehow
            blob = json.dumps(q.structured) + q.text
            assert any(e in blob or e.split(":")[-1] in blob for e in entities) or any(
                e in blob for e in w.meta["persons"] + w.meta["orgs"] + w.meta["projects"]
            )


def test_bundle_dependency():
    w = generate_world(9, 1)
    for b in generate_bundles(w):
        families = {q.family.value for q in b.queries}
        assert "current_state" in families
        assert "historical_state" in families
        assert "transition" in families or "conflict_validity" in families
        assert "multi_hop" in families
        assert "provenance" in families
        # Shared entities across queries
        texts = " ".join(q.text + json.dumps(q.structured) for q in b.queries)
        shared = 0
        for e in b.focal_entities:
            if e in texts:
                shared += 1
        assert shared >= 1


def test_every_constraint_fires_on_known_violation():
    w = generate_world(42, 0)
    bundles = generate_bundles(w)
    ceo = next(b for b in bundles if any(q.metadata.get("slot") == "ceo_current" for q in b.queries))
    gold = gold_predictions([ceo])
    fired = set()
    for name, fn in CORRUPTION_FN.items():
        preds = fn(ceo, gold)
        results = check_bundle_constraints(w, ceo, preds)
        for r in results:
            if not r.passed:
                fired.add(r.constraint_type.value)
    # Across suite, major families should fire at least once on CEO bundle + others
    for b in bundles:
        gold_b = gold_predictions([b])
        for name, fn in CORRUPTION_FN.items():
            results = check_bundle_constraints(w, b, fn(b, gold_b))
            for r in results:
                if not r.passed:
                    fired.add(r.constraint_type.value)
    required = {
        "uniqueness",
        "temporal",
        "transition",
        "relational",
        "provenance",
        "multi_hop",
        "contradiction",
    }
    missing = required - fired
    assert not missing, f"constraint families never fired: {missing}"


def test_gold_predictions_perfect():
    worlds = generate_worlds(42, 3)
    bundles = []
    wmap = {}
    for w in worlds:
        wmap[w.world_id] = w
        bundles.extend(generate_bundles(w))
    gold = gold_predictions(bundles)
    _, agg, viol = evaluate_predictions(wmap, bundles, gold)
    assert agg.mean_query_accuracy == 1.0
    assert agg.bcr == 1.0
    assert agg.consacc_strict == 1.0
    assert viol == []


def test_high_acc_corruption_gap():
    w = generate_world(42, 0)
    b = next(x for x in generate_bundles(w) if any(q.metadata.get("slot") == "ceo_current" for q in x.queries))
    gold = gold_predictions([b])
    bad = corrupt_high_acc_inconsistent(b, gold)
    bms, agg, _ = evaluate_predictions({w.world_id: w}, [b], bad)
    assert bms[0].mean_query_accuracy >= 0.8
    assert bms[0].consistent is False
    assert agg.bcr < agg.mean_query_accuracy
    assert agg.gap_mean_acc_minus_bcr > 0


def test_consistent_wrong_world():
    w = generate_world(42, 0)
    b = next(x for x in generate_bundles(w) if any(q.metadata.get("slot") == "ceo_current" for q in x.queries))
    gold = gold_predictions([b])
    alt = corrupt_consistent_wrong_world(b, gold)
    bms, agg, _ = evaluate_predictions({w.world_id: w}, [b], alt)
    assert bms[0].mean_query_accuracy < 1.0
    assert bms[0].consistent is True
    assert agg.bcr > agg.mean_query_accuracy


def test_prediction_schema_validation():
    ok = {
        "bundle_id": "b",
        "query_id": "q",
        "predicted_answer": 1,
        "system_id": "s",
        "run_id": "r",
    }
    assert validate_prediction_row(ok) == []
    assert validate_prediction_row({"bundle_id": "b"}) != []


def test_unique_ids_and_stable_serialization():
    worlds = generate_worlds(42, 5)
    event_ids, query_ids, bundle_ids, obs_ids = set(), set(), set(), set()
    for w in worlds:
        for e in w.events:
            assert e.event_id not in event_ids
            event_ids.add(e.event_id)
        for o in generate_observations(w):
            assert o.observation_id not in obs_ids
            obs_ids.add(o.observation_id)
        for b in generate_bundles(w):
            assert b.bundle_id not in bundle_ids
            bundle_ids.add(b.bundle_id)
            for q in b.queries:
                assert q.query_id not in query_ids
                query_ids.add(q.query_id)
        s1 = json.dumps(w.to_dict(), sort_keys=True)
        s2 = json.dumps(generate_world(w.seed, w.world_idx).to_dict(), sort_keys=True)
        assert s1 == s2


def test_all_event_families_present():
    w = generate_world(1, 0)
    types = {e.event_type for e in w.events}
    required = set(EventType)
    missing = required - types
    assert not missing, f"missing event families: {missing}"
