"""Tests for the Round 2 audit / sensitivity analysis.

Unit tests use synthetic fixtures. Integration tests run on the committed
reviewer files; tests that need the git-ignored private snapshot are skipped
when it is absent.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

from worldconsistmem import round2_audit as ra

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "analysis" / "round2"
PRIVATE = OUT / "private"

_spec = importlib.util.spec_from_file_location("round2_analysis", REPO / "scripts" / "round2_analysis.py")
r2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r2)

needs_private = pytest.mark.skipif(
    not (PRIVATE / "f0_f3_frozen_outputs.jsonl").exists(), reason="private snapshot not available")


def ev(i, et, t, **p):
    return {"id": f"w:obs:{i}", "s": {"et": et, "p": p, "prov": f"w:prov:{i}", "t": t}, "t": t}


CEO_Q = "When and how did the CEO of w:org:0 change?"
CEO_ONE = [ev(16, "role_replacement", 16, old_person_id="w:person:0", new_person_id="w:person:1", org_id="w:org:0", role="CEO"),
           ev(2, "role_assignment", 2, person_id="w:person:0", org_id="w:org:0", role="CEO")]
CEO_TWO = CEO_ONE + [ev(28, "role_replacement", 28, old_person_id="w:person:1", new_person_id="w:person:2", org_id="w:org:0", role="CEO")]
OWN_Q = "When did ownership of w:project:0 transfer?"
OWN_TWO = [ev(19, "project_ownership_transfer", 19, old_org_id="w:org:0", new_org_id="w:org:1", project_id="w:project:0"),
           ev(30, "project_ownership_transfer", 30, old_org_id="w:org:1", new_org_id="w:org:0", project_id="w:project:0")]


# ---------------------------------------------------------------- reliability

def test_kappa_perfect_and_chance():
    a = ["correct", "incorrect", "ambiguous", "correct"]
    assert ra.cohen_kappa(a, a)["kappa"] == pytest.approx(1.0)
    k = ra.cohen_kappa(["correct", "correct", "incorrect", "incorrect"], ["correct", "incorrect", "correct", "incorrect"])
    assert k["po"] == 0.5 and k["kappa"] == pytest.approx(0.0)


def test_kappa_undefined_when_single_category():
    assert math.isnan(ra.cohen_kappa(["correct"] * 3, ["correct"] * 3)["kappa"])


def test_kappa_hand_computed_round2_table():
    a = ["ambiguous"] * 30 + ["correct"] * 20
    b = ["ambiguous"] * 25 + ["correct"] * 5 + ["ambiguous"] * 1 + ["correct"] * 19
    k = ra.cohen_kappa(a, b)
    assert k["n_agree"] == 44 and k["pe"] == pytest.approx(0.504)
    assert k["kappa"] == pytest.approx((0.88 - 0.504) / 0.496)


def test_mcnemar_exact():
    x = [False] * 5 + [True]
    y = [True] * 5 + [False]
    m = ra.mcnemar_exact(x, y)
    assert (m["y_only"], m["x_only"]) == (5, 1)
    assert m["p_two_sided"] == pytest.approx(2 * (1 + 6) / 64)
    assert ra.mcnemar_exact([True], [True])["p_two_sided"] == 1.0


def test_bootstrap_diff_degenerate_and_sign():
    cl = ["a", "a", "b", "b"]
    same = ra.cluster_bootstrap_diff([True] * 4, [True] * 4, cl, n_boot=200)
    assert same["delta"] == 0 and same["ci95_lo"] == 0 and same["ci95_hi"] == 0
    up = ra.cluster_bootstrap_diff([False] * 4, [True] * 4, cl, n_boot=200)
    assert up["delta"] == 1 and up["ci95_lo"] == 1


# ---------------------------------------------------------------- parsing

@pytest.mark.parametrize("raw", [
    '{"answer": 21, "abstain": false, "provenance": "x"}',
    '{"answer": {"t": 21}, "abstain": false}',
    '{"answer": {"time": "21"}}',
    '{"when": 21}',
    "21",
])
def test_time_extracted_regardless_of_shape(raw):
    claims = ra.extract_claims("conf", ra.parse_response(raw)["answer"])
    assert claims == [{"time": {21}}]


def test_abstain_and_unparseable():
    assert ra.parse_response('{"answer": null, "abstain": true}')["abstain"]
    assert ra.parse_response('{"abstain": true, "answer": null}')["abstain"]
    assert not ra.parse_response("not json")["parse_ok"]


def test_prev_event_next_roles_are_context_dependent():
    ans = {"prev_state": {"CEO": "w:person:0"}, "event": {"old_person_id": "w:person:0", "new_person_id": "w:person:1", "t": 16},
           "resulting_state": {"person_id": "w:person:1", "role": "CEO"}}
    (claim,) = ra.extract_claims("ceo", ans)
    assert claim["from"] == {"w:person:0"} and claim["to"] == {"w:person:1"} and claim["time"] == {16}


def test_internally_conflicting_answer_does_not_match():
    ans = {"prev_state": {"CEO": "w:person:9"}, "event": {"old_person_id": "w:person:0", "new_person_id": "w:person:1", "t": 16}}
    raw = json.dumps({"answer": ans})
    assert ra.audit_response(CEO_Q, CEO_ONE, raw)["audit_class"] == ra.CONTRADICTED


def test_unknown_question_template_raises():
    with pytest.raises(ValueError):
        ra.parse_question("Who is the CEO?")


# ---------------------------------------------------------------- structural audit

def test_unique_question_supported_answer_any_schema():
    for raw in ('{"from": "w:person:0", "to": "w:person:1", "t": 16, "org_id": "w:org:0", "role": "CEO"}',
                '{"answer": {"when": 16, "how": {"old_person_id": "w:person:0", "new_person_id": "w:person:1"}}}'):
        a = ra.audit_response(CEO_Q, CEO_ONE, raw)
        assert a["question_unique"] and a["audit_class"] == ra.SUPPORTED_UNIQUE


def test_documented_event_is_not_correct_when_question_is_ambiguous():
    raw = '{"from": "w:person:0", "to": "w:person:1", "t": 16, "org_id": "w:org:0", "role": "CEO"}'
    a = ra.audit_response(CEO_Q, CEO_TWO, raw)
    assert not a["question_unique"] and len(a["candidates"]) == 2
    assert a["audit_class"] == ra.SUPPORTED_AMBIGUOUS and a["matched_positions"] == ["earliest"]


def test_wrong_time_is_contradicted_even_if_question_ambiguous():
    assert ra.audit_response(OWN_Q, OWN_TWO, '{"answer": 25}')["audit_class"] == ra.CONTRADICTED


def test_mixed_events_are_contradicted():
    raw = '{"from": "w:person:0", "to": "w:person:2", "t": 28}'
    assert ra.audit_response(CEO_Q, CEO_TWO, raw)["audit_class"] == ra.CONTRADICTED


def test_ceo_time_only_answer_does_not_answer_when_and_how():
    assert ra.audit_response(CEO_Q, CEO_ONE, '{"answer": 16}')["audit_class"] == ra.CONTRADICTED


def test_distractor_entities_are_not_candidates():
    other = ev(14, "role_replacement", 14, old_person_id="w:person:5", new_person_id="w:person:6", org_id="w:org:1", role="CEO")
    assert ra.audit_response(CEO_Q, CEO_ONE + [other], '{"answer": 16}')["question_unique"]


def test_document_without_version_ids_is_insufficient():
    q = "When was w:docbase:0 revised from v1 to v2?"
    pack = [ev(31, "document_revision", 31, base_doc_id="w:docbase:0", doc_id="w:doc:2", author_id="w:person:2"),
            ev(33, "document_revision", 33, base_doc_id="w:docbase:0", doc_id="w:doc:3", author_id="w:person:2")]
    a = ra.audit_response(q, pack, '{"answer": 33}')
    assert a["question_status"] == "version_unidentifiable" and a["audit_class"] == ra.INSUFFICIENT
    pack[0]["s"]["p"]["expected_prev_version"] = 1
    assert ra.audit_response(q, pack, '{"answer": 31}')["audit_class"] == ra.SUPPORTED_UNIQUE


def test_abstention_classification_depends_on_uniqueness():
    raw = '{"answer": null, "abstain": true}'
    assert ra.audit_response(CEO_Q, CEO_ONE, raw)["audit_class"] == ra.CONTRADICTED
    assert ra.audit_response(CEO_Q, CEO_TWO, raw)["audit_class"] == ra.INSUFFICIENT


# ---------------------------------------------------------------- gold scoring

GOLD_CONF = {"conflict_id": "w:conflict:0", "resolved_value": "P0", "t": 21}
GOLD_CEO = {"from": "w:person:0", "to": "w:person:1", "t": 16, "org_id": "w:org:0", "role": "CEO"}


def test_scalar_timestamp_is_semantically_correct_but_not_exact():
    raw = '{"answer": 21, "abstain": false}'
    s = ra.score_semantic("conf", raw, GOLD_CONF)
    assert s == {"question_aligned": True, "tuple_content": False}
    assert not ra.score_v2(ra.scoring_answer(raw), GOLD_CONF)


def test_wrong_extra_field_breaks_semantic_score():
    raw = json.dumps({"conflict_id": "w:conflict:0", "resolved_value": "P2", "t": 21})
    assert not ra.score_semantic("conf", raw, GOLD_CONF)["question_aligned"]


def test_semantic_rule_is_schema_blind():
    shapes = [GOLD_CEO,
              {"answer": {"old_person_id": "w:person:0", "new_person_id": "w:person:1", "time": 16, "org_id": "w:org:0", "role": "CEO"}},
              {"answer": {"previous_state": {"CEO": "w:person:0"}, "event": {"t": 16, "org_id": "w:org:0", "role": "CEO"},
                          "resulting_state": {"CEO": "w:person:1"}}}]
    for s in shapes:
        assert ra.score_semantic("ceo", json.dumps(s), GOLD_CEO) == {"question_aligned": True, "tuple_content": True}


def test_list_answer_is_never_scored_correct():
    raw = json.dumps({"answer": [{"old_person_id": "w:person:0", "new_person_id": "w:person:1", "t": 16}]  * 2})
    assert ra.score_semantic("ceo", raw, GOLD_CEO) == {"question_aligned": False, "tuple_content": False}


def test_scorer_v1_v2_alias_behaviour():
    alias = {"old_person_id": "w:person:0", "new_person_id": "w:person:1", "time": 16, "org_id": "w:org:0", "role": "CEO"}
    assert not ra.answers_equal_v1(alias, GOLD_CEO) and ra.score_v2(alias, GOLD_CEO)
    assert not ra.score_v2({**GOLD_CEO, "time": 17}, GOLD_CEO)  # conflicting alias rejects
    assert ra.score_v2({**GOLD_CEO, "t": "16"}, GOLD_CEO)
    assert not ra.score_v2({"when": 16, **{k: v for k, v in GOLD_CEO.items() if k != "t"}}, GOLD_CEO)
    nested = {"prev_state": {}, "event": alias}
    assert not ra.score_v2(nested, GOLD_CEO) and ra.score_v2(ra.scorable_transition(nested), GOLD_CEO)


# ---------------------------------------------------------------- committed data

@pytest.fixture(scope="module")
def pub():
    return r2.load_public()


def test_source_files_unchanged():
    for path, sha in r2.EXPECTED_SHA256.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha


def test_round2_inputs_valid(pub):
    v = pub["validation"]
    assert v["n_rows"] == {"reviewer_A": 50, "reviewer_B": 50, "packet": 50} and v["n_cases"] == 20
    assert v["ids_aligned_A_B"] and v["content_matches_packet"] and v["round2_ids_equal_round1_discordant"]


def test_round2_agreement_reproduced(pub):
    a = r2.agreement(pub)
    x = a["round2"]
    assert (x["n"], x["n_agree"]) == (50, 44) and x["kappa"] == pytest.approx(0.7581, abs=5e-5)
    assert x["per_label_joint"] == {"correct": 19, "incorrect": 0, "ambiguous": 25}
    assert x["discordant_ids"] == ["C21-R1", "C22-R3", "C22-R4", "C24-R2", "C29-R3", "C29-R4"]
    assert (a["round1"]["n_agree"], a["round1"]["n"]) == (70, 120)
    assert a["round1"]["kappa"] == pytest.approx(0.3363, abs=5e-5)


def test_round2_audit_structure(pub):
    audit = r2.audit_round2(pub)
    assert len(audit) == 50
    amb = [r for r in audit if r["human_status"] == "joint_ambiguous"]
    assert len(amb) == 25 and all(r["n_candidate_events"] >= 2 and r["answer_matches_documented_event"] for r in amb)
    assert all(r["audit_class"] == ra.SUPPORTED_AMBIGUOUS for r in amb)
    cor = [r for r in audit if r["human_status"] == "joint_correct"]
    assert len(cor) == 19 and all(r["audit_class"] == ra.SUPPORTED_UNIQUE for r in cor)


def test_adjudication_never_claims_human_consensus(pub):
    audit = r2.audit_round2(pub)
    adj = r2.adjudication(pub, audit, r2.intra_rater_inconsistencies(audit))
    assert len(adj) == 6
    for r in adj:
        assert r["final_human_consensus"] == "" and r["status"] == "unresolved_pending_human_adjudication"
        assert "NOT an independent human judgment" in r["proposal_source"]
        assert r["reviewer_A_label"] != r["reviewer_B_label"]


def _csv(name):
    with (OUT / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_committed_outputs_map_to_original_ids_and_hide_arm(pub):
    ids = [r["response_id"] for r in pub["A"]]
    assert [r["response_id"] for r in _csv("reviewer_agreement.csv")] == ids
    assert [r["response_id"] for r in _csv("ambiguous_case_audit.csv")] == ids
    assert {r["response_id"] for r in _csv("adjudication_proposals.csv")} <= set(ids)
    for name in ("reviewer_agreement.csv", "ambiguous_case_audit.csv", "adjudication_proposals.csv"):
        header = (OUT / name).read_text(encoding="utf-8").splitlines()[0].split(",")
        assert "arm" not in header and "query_id" not in header


def test_committed_csvs_match_fresh_computation(pub):
    audit = r2.audit_round2(pub)
    for row, fresh in zip(_csv("ambiguous_case_audit.csv"), audit):
        assert row["audit_class"] == fresh["audit_class"] and row["reviewer_A"] == fresh["reviewer_A"]


# ---------------------------------------------------------------- private snapshot

@needs_private
def test_published_exact_match_numbers_reproduced(pub):
    items = r2.build_items(pub, r2.load_private())
    rep = r2.check_reproduction(items)
    assert {a: rep[a]["exact_v2"] for a in ra.ARMS} == r2.PUBLISHED["all"]
    assert all(rep[a]["row_level_mismatches_vs_recorded_v2"] == 0 for a in ra.ARMS)
    assert all(rep[a]["n"] == 150 for a in ra.ARMS)


@needs_private
def test_scenarios_use_identical_items_across_arms_and_match_committed_csv(pub):
    priv = r2.load_private()
    items = r2.build_items(pub, priv)
    _, hsum = r2.human_subset(pub, priv, r2.audit_round2(pub), items)
    rows, summary = r2.run_scenarios(items, set(hsum["human_ambiguous_query_ids"]))
    for s in summary.values():
        assert len({v["n"] for v in s["arms"].values()}) == 1
    assert summary["A-S1S2"]["arms"] == {a: {"k": k, "n": 93} for a, k in r2.PUBLISHED["S1+S2"].items()}
    assert summary["D"]["arms"]["F0"]["k"] == summary["C2-B1"]["arms"]["F0"]["k"]
    for a in ra.ARMS:  # bounds are ordered
        assert summary["E-lower"]["arms"][a]["k"] <= summary["E-mid"]["arms"][a]["k"] <= summary["E-upper"]["arms"][a]["k"]
    committed = {(r["scenario"], r["arm_or_contrast"]): r for r in _csv("sensitivity_analysis.csv") if r["scenario"] != "H"}
    for r in rows:
        if r["row_type"] == "arm":
            assert committed[(r["scenario"], r["arm_or_contrast"])]["n_correct"] == str(r["n_correct"])


@needs_private
def test_private_mapping_verified_against_frozen_outputs(pub):
    priv = r2.load_private()
    items = r2.build_items(pub, priv)
    _, hsum = r2.human_subset(pub, priv, r2.audit_round2(pub), items)
    assert hsum["checks"]["sha_matches_frozen_output"] == 120 and hsum["checks"]["cases_with_all_four_arms"] == 30
    assert sum(sum(t.values()) for t in hsum["table"].values()) == 120
