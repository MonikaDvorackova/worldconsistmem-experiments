"""H4 LLM evidence isolation and decoding freeze tests."""

from __future__ import annotations

import json

import pytest

from worldconsistmem.baselines.load import EXPECTED_SMOKE_SHA256, assert_frozen_smoke
from worldconsistmem.llm_reader import (
    H4_MODELS,
    MAX_TOKENS,
    TEMPERATURE,
    EvidencePack,
    assert_no_gold_leakage,
    build_evidence_from_observations,
    format_prompt,
    _json_complete,
    _parse_json_answer,
)
from worldconsistmem.models import AnswerSchema, Observation, Query, QueryFamily
from worldconsistmem.baselines.interface import ABSTAIN_TOKEN


def test_smoke_freeze_untouched_during_h4():
    assert assert_frozen_smoke() == EXPECTED_SMOKE_SHA256


def test_h4_models_exactly_two_families():
    assert len(H4_MODELS) == 2
    assert "Qwen2.5-3B-Instruct-4bit" in H4_MODELS[0]
    assert "Phi-3.5-mini-instruct-4bit" in H4_MODELS[1]


def test_decoding_freeze_constants():
    assert TEMPERATURE == 0.0
    assert MAX_TOKENS == 48


def test_evidence_isolation_rejects_gold_fields():
    with pytest.raises(AssertionError):
        assert_no_gold_leakage({"gold_answer": "x"})
    with pytest.raises(AssertionError):
        assert_no_gold_leakage({"applicable_constraints": ["temporal"]})


def test_build_evidence_excludes_gold():
    q = Query(
        query_id="t:q",
        bundle_id="t:b",
        family=QueryFamily.CURRENT_STATE,
        text="Who?",
        structured={"attribute": "role"},
        target_time=1,
        target_interval=None,
        gold_answer="secret",
        answer_schema=AnswerSchema.ENTITY_ID,
        applicable_constraints=[],
        supporting_event_ids=["e1"],
        supporting_provenance_ids=["p1"],
        metadata={},
    )
    obs = [
        Observation(
            observation_id="w:obs:1",
            event_id="w:e:1",
            t=1,
            provenance_id="p1",
            structured={"event_type": "role_assignment", "t": 1},
            text_canonical="ceo",
            text_paraphrase="ceo",
        )
    ]
    pack = build_evidence_from_observations(q, obs)
    prompt = format_prompt(pack)
    assert "secret" not in prompt
    assert "gold_answer" not in prompt
    assert "supporting_event_ids" not in prompt
    assert_no_gold_leakage(pack.to_prompt_dict())


def test_json_early_stop_helper_and_parser():
    assert _json_complete('{"answer": 1, "abstain": false}')
    assert not _json_complete('{"answer": 1')
    ans, abstain, prov, malformed, obj = _parse_json_answer(
        'noise {"answer": "x", "abstain": false, "provenance": "p"} trailing'
    )
    assert ans == "x" and not abstain and prov == "p" and not malformed
    ans, abstain, _, malformed, _ = _parse_json_answer("not json")
    assert ans == ABSTAIN_TOKEN and malformed
