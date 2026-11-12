from __future__ import annotations

import json

from worldconsistmem.rebuttal_temporal import (
    CONDITIONS,
    generate_experiment,
    score_response,
    validate_scorer,
    world_clustered_analysis,
)


def test_generate_100_worlds_and_all_four_conditions():
    prompts, gold = generate_experiment(100)
    assert len({r["world_id"] for r in gold}) == 100
    assert len(gold) == 200
    assert len(prompts) == 800
    assert {r["condition"] for r in prompts} == set(CONDITIONS)
    for world_id in {r["world_id"] for r in prompts}:
        records = [r for r in prompts if r["world_id"] == world_id]
        assert len(records) == 8
        assert sorted(r["inference_order"] for r in records) == list(range(8))


def test_prompts_exclude_gold_label_fields_and_share_question_wording():
    prompts, _gold = generate_experiment(1)
    for query_id in {r["query_id"] for r in prompts}:
        records = [r for r in prompts if r["query_id"] == query_id]
        assert {r["condition"] for r in records} == set(CONDITIONS)
        assert len({r["prompt"].split("\nHistory:", 1)[0] for r in records}) == 1
        for row in records:
            lower = row["prompt"].lower()
            assert "gold_answer" not in lower
            assert "answer_key" not in lower
            assert "supporting_event_ids" not in lower


def test_scorer_known_correct_stale_ambiguous_and_malformed_cases():
    assert validate_scorer()["passed"]
    correct = score_response('{"answer":"p:2","abstain":false,"provenance":null}', "p:2")
    stale = score_response('{"answer":"p:1","abstain":false,"provenance":null}', "p:2", ["p:1"])
    malformed = score_response("{broken", "p:2")
    abstain = score_response('{"answer":null,"abstain":true,"provenance":null}', "p:2")
    assert correct["correct"] == 1 and correct["status"] == "ok"
    assert stale["correct"] == 0 and stale["stale_state"] == 1
    assert malformed["status"] == "malformed"
    assert abstain["status"] == "abstain"


def test_world_clustered_statistics_weight_worlds_not_queries():
    rows = []
    # World one has two queries; mean difference is +1. World two has one
    # query; mean difference is -1. Correct cluster-level estimate is zero.
    for q in ("q1", "q2"):
        rows.extend([
            {"world_id": "w1", "query_id": q, "condition": "B", "correct": 1},
            {"world_id": "w1", "query_id": q, "condition": "C", "correct": 0},
        ])
    rows.extend([
        {"world_id": "w2", "query_id": "q3", "condition": "B", "correct": 0},
        {"world_id": "w2", "query_id": "q3", "condition": "C", "correct": 1},
    ])
    result = world_clustered_analysis(rows, bootstrap_draws=100, signflip_draws=1000, seed=7)
    assert result["n_worlds"] == 2
    assert result["n_queries"] == 3
    assert result["mean_world_paired_difference"] == 0
    assert result["world_bootstrap_95_percentile_ci"] == [-1.0, 1.0]
    assert 0 <= result["paired_sign_flip_two_sided_p"] <= 1


def test_world_clustered_statistics_are_reproducible():
    rows = []
    for i in range(6):
        rows.extend([
            {"world_id": f"w{i}", "query_id": f"q{i}", "condition": "B", "correct": i % 2},
            {"world_id": f"w{i}", "query_id": f"q{i}", "condition": "C", "correct": 1 - (i % 2)},
        ])
    assert world_clustered_analysis(rows, bootstrap_draws=200, signflip_draws=1000, seed=99) == world_clustered_analysis(
        rows, bootstrap_draws=200, signflip_draws=1000, seed=99
    )


def test_prompt_length_association_is_reported_when_token_counts_exist():
    rows = []
    for i in range(8):
        difference = 1 if i < 4 else -1
        b_tokens, c_tokens = (300, 100) if difference == 1 else (110, 100)
        rows.extend([
            {"world_id": f"w{i}", "query_id": f"q{i}", "condition": "B", "correct": int(difference == 1), "prompt_tokens": b_tokens},
            {"world_id": f"w{i}", "query_id": f"q{i}", "condition": "C", "correct": int(difference == -1), "prompt_tokens": c_tokens},
        ])
    result = world_clustered_analysis(rows, bootstrap_draws=100, signflip_draws=200, seed=3)
    assert result["prompt_length_effect_association"]["n_worlds"] == 8
    assert result["prompt_length_effect_association"]["pearson_r"] > 0
