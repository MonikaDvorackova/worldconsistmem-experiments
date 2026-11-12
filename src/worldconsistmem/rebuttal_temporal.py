"""Frozen, local-only temporal-structure follow-up experiment.

This module generates prompt-only inputs separately from gold labels. It never
loads or downloads a model; inference is performed by the explicit local runner.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .scaled_generate import generate_scaled_world

CONDITIONS = ("A", "B", "C", "D")
N_WORLDS = 100
NAMESPACE = "rebuttal-temporal-v1"
MODEL_ID = "mlx-community/Qwen2.5-3B-Instruct-4bit"
OUTPUT_SCHEMA = '{"answer": "<entity_id>", "abstain": false, "provenance": null}'
MAX_TOKENS = 48
TEMPERATURE = 0.0


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _seed_for(index: int, attempt: int = 0) -> int:
    digest = hashlib.sha256(f"{NAMESPACE}:{index}:{attempt}".encode()).hexdigest()
    # Large deterministic seeds avoid the seed ranges used by existing studies.
    return 1_000_000 + int(digest[:12], 16) % 8_000_000


def _event_record(event: Any) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "t": event.t,
        "actor_id": event.actor_id,
        "affected_ids": list(event.affected_ids),
        "payload": event.payload,
        "preconditions": list(event.preconditions),
        "provenance_id": event.provenance_id,
        "narrative": event.narrative,
    }


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        out: list[tuple[str, Any]] = []
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            out.extend(_flatten(value[key], path))
        return out
    if isinstance(value, list):
        out = []
        for idx, item in enumerate(value):
            out.extend(_flatten(item, f"{prefix}[{idx}]"))
        if not value:
            return [(prefix, [])]
        return out
    return [(prefix, value)]


def _canonical_facts(initial: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for path, value in _flatten(initial, "initial"):
        facts.append({"order": 0, "record_id": "initial", "field": path, "value": value})
    for ev in events:
        for path, value in _flatten(ev):
            facts.append({
                "order": ev["t"], "record_id": ev["event_id"], "field": path, "value": value,
            })
    return facts


def _transition_edges(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entities_by_record: dict[str, set[str]] = {}
    for fact in facts:
        path = fact["field"]
        leaf = path.rsplit(".", 1)[-1]
        value = fact["value"]
        if path.startswith("payload.") and leaf.endswith("_id") and isinstance(value, str):
            entities_by_record.setdefault(fact["record_id"], set()).add(value)
    last: dict[tuple[str, str], Any] = {}
    edges = []
    for fact in facts:
        path = fact["field"]
        record_id = fact["record_id"]
        entities = sorted(entities_by_record.get(record_id, set())) or ["world"]
        key = ("|".join(entities), path)
        before = last.get(key)
        edges.append({
            "event": record_id,
            "order": fact["order"],
            "entity": entities,
            "attribute": path,
            "from": before,
            "to": fact["value"],
            "source_field": path,
        })
        last[key] = fact["value"]
    return edges


def _render_data(condition: str, initial: dict[str, Any], events: list[dict[str, Any]]) -> Any:
    facts = _canonical_facts(initial, events)
    if condition == "A":
        return {"initial": initial, "events": events}
    elif condition == "B":
        return {"edges": _transition_edges(facts)}
    elif condition == "C":
        return {"facts": facts}
    elif condition == "D":
        rows = [{"order": 0, "record_id": "initial", "fields": _flatten(initial, "initial")}]
        rows.extend({"order": ev["t"], "record_id": ev["event_id"], "event_type": ev["event_type"], "fields": _flatten(ev)} for ev in events)
        return {"records": rows}
    else:
        raise ValueError(f"unknown condition: {condition}")


def _represented_facts(condition: str, data: Any) -> list[tuple[int, str, str]]:
    if condition == "A":
        facts = _canonical_facts(data["initial"], data["events"])
    elif condition == "B":
        facts = [{"order": e["order"], "field": e["source_field"], "value": e["to"]} for e in data["edges"]]
    elif condition == "C":
        facts = data["facts"]
    elif condition == "D":
        facts = []
        for record in data["records"]:
            for path, value in record["fields"]:
                facts.append({"order": record["order"], "field": path, "value": value})
    else:
        raise ValueError(f"unknown condition: {condition}")
    return sorted((f["order"], f["field"], _json(f["value"])) for f in facts)


def _render(condition: str, initial: dict[str, Any], events: list[dict[str, Any]], end_time: int) -> str:
    data = _render_data(condition, initial, events)
    if condition == "A":
        lines = ["Chronological prose history (all times are ordered):", "At time 0, initial facts: " + _json(data["initial"]) + "."]
        for ev in data["events"]:
            fields = "; ".join(f"{k} = {_json(v)}" for k, v in sorted(ev.items()) if k != "t")
            lines.append(f"At time {ev['t']}, {ev['event_type']}: {fields}.")
        body = "\n".join(lines)
    elif condition == "B":
        body = "Explicit ordered state transitions; 'from' is the prior recorded value and 'to' is this event's recorded value.\n" + _json(data)
    elif condition == "C":
        body = "Neutral ordered field/value listing without transition links.\n" + _json(data)
    else:
        body = "Ordered event records retain all source fields and order; no before/after edges are supplied.\n" + _json(data)
    if _represented_facts(condition, data) != _source_facts_from_history(condition, initial, events):
        raise AssertionError(f"renderer did not preserve source facts for condition {condition}")
    return f"History through final event time {end_time}:\n{body}"


def make_prompt(condition: str, history: str, question: str) -> str:
    prompt = (
        "Answer using only the supplied history. Treat the final available event time as the as-of time. "
        f"{question}\nOutput exactly one JSON object matching this schema: {OUTPUT_SCHEMA}\n"
        f"History:\n{history}"
    )
    assert_no_answer_leakage(prompt)
    return prompt


def assert_no_answer_leakage(prompt: str) -> None:
    lowered = prompt.lower()
    forbidden = ("gold_answer", "gold_world", "supporting_event_ids", "applicable_constraints", "answer_key")
    for marker in forbidden:
        if marker in lowered:
            raise AssertionError(f"answer-label metadata leaked into prompt: {marker}")


def _source_facts_from_history(condition: str, initial: dict[str, Any], events: list[dict[str, Any]]) -> list[tuple[int, str, str]]:
    # Facts are normalized before rendering; all four arms must encode this same
    # multiset. This is a construction check, not model scoring.
    return sorted((x["order"], x["field"], _json(x["value"])) for x in _canonical_facts(initial, events))


def generate_experiment(n_worlds: int = N_WORLDS) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return prompt-only records and a separately stored gold-label table."""
    prompt_rows: list[dict[str, Any]] = []
    gold_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx in range(n_worlds):
        attempt = 0
        while True:
            seed = _seed_for(idx, attempt)
            world = generate_scaled_world(seed, idx, tier="large")
            initial = world.initial.to_dict()
            all_events = [_event_record(e) for e in world.events]
            # The existing large grammar's discretionary replacement can be
            # skipped when its preconditions fail. Advance only the deterministic
            # seed until the preregistered structural minimum is realized.
            ceo_events = [e for e in all_events if e["event_type"] == "role_replacement" and e["payload"].get("org_id") == world.meta["ceo_org"]]
            own_events = [e for e in all_events if e["event_type"] == "project_ownership_transfer" and e["payload"].get("project_id") == world.meta["focal_project"]]
            if len(ceo_events) >= 3 and len(own_events) >= 3:
                break
            attempt += 1
            if attempt > 1000:
                raise AssertionError(f"generator could not meet transition minimum for index {idx}")
        if world.world_id in seen_ids:
            raise AssertionError(f"duplicate generated world id: {world.world_id}")
        seen_ids.add(world.world_id)
        # Preserve every answer-relevant CEO/ownership transition and add eight
        # deterministic, ordered distractor events from the same generated world.
        relevant_types = {"role_replacement", "project_ownership_transfer"}
        relevant_ids = {
            e["event_id"] for e in all_events
            if e["event_type"] in relevant_types
            or (e["event_type"] == "role_assignment" and e["payload"].get("role") == "CEO")
        }
        distractor_pool = [e for e in all_events if e["event_id"] not in relevant_ids]
        distractor_rng = random.Random(int(hashlib.sha256(f"{world.world_id}:distractors".encode()).hexdigest()[:16], 16))
        distractor_events = distractor_rng.sample(distractor_pool, k=min(8, len(distractor_pool)))
        selected_ids = relevant_ids | {e["event_id"] for e in distractor_events}
        events = [e for e in all_events if e["event_id"] in selected_ids]
        facts = _source_facts_from_history("", initial, events)
        gold_queries = [
            {"query_id": f"{world.world_id}:latest_ceo", "kind": "ceo", "entity_id": world.meta["ceo_org"], "answer": world.final.role_holder(world.meta["ceo_org"], "CEO", world.T).person_id},
            {"query_id": f"{world.world_id}:latest_owner", "kind": "owner", "entity_id": world.meta["focal_project"], "answer": world.final.owner_of(world.meta["focal_project"], world.T)},
        ]
        ceo_history = [e["payload"].get("person_id") for e in events if e["event_type"] == "role_assignment" and e["payload"].get("org_id") == world.meta["ceo_org"] and e["payload"].get("role") == "CEO"]
        ceo_history.extend(e["payload"].get("old_person_id") for e in ceo_events)
        ceo_history.extend(e["payload"].get("new_person_id") for e in ceo_events)
        owner_history = [world.initial.owner_of(world.meta["focal_project"], 0)]
        owner_history.extend(e["payload"].get("old_org_id") for e in own_events)
        owner_history.extend(e["payload"].get("new_org_id") for e in own_events)
        for query in gold_queries:
            history = ceo_history if query["kind"] == "ceo" else owner_history
            query["stale_answers"] = sorted({x for x in history if x and x != query["answer"]})
            gold_rows.append({
                "world_id": world.world_id,
                "seed": seed,
                "seed_attempt": attempt,
                "query_id": query["query_id"],
                "question_kind": query["kind"],
                "answer": query["answer"],
                "stale_answers": query["stale_answers"],
                "n_ceo_replacements": len(ceo_events),
                "n_ownership_transfers": len(own_events),
                "n_distractor_events": len(distractor_events),
            })
        condition_histories = {c: _render(c, initial, events, world.T) for c in CONDITIONS}
        canonical_signatures = {c: _source_facts_from_history(c, initial, events) for c in CONDITIONS}
        if any(sig != facts for sig in canonical_signatures.values()):
            raise AssertionError(f"source-fact mismatch in {world.world_id}")
        query_prompts = []
        tasks = [(query, condition) for query in gold_queries for condition in CONDITIONS]
        random.Random(seed ^ 0x5A17C0DE).shuffle(tasks)
        for query in gold_queries:
            if not query["answer"]:
                raise AssertionError(f"unanswerable generated query: {query['query_id']}")
        for order, (query, condition) in enumerate(tasks):
            question = (
                f"What is the latest CEO person identifier for organization {query['entity_id']}?"
                if query["kind"] == "ceo"
                else f"What is the current owner organization identifier of project {query['entity_id']}?"
            )
            prompt = make_prompt(condition, condition_histories[condition], question)
            query_prompts.append({
                "world_id": world.world_id,
                "query_id": query["query_id"],
                "condition": condition,
                "question_kind": query["kind"],
                "prompt": prompt,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "prompt_chars": len(prompt),
                "end_time": world.T,
                "inference_order": order,
            })
        prompt_rows.extend(query_prompts)
    if len(seen_ids) != n_worlds:
        raise AssertionError("world IDs are not unique")
    return prompt_rows, gold_rows


def normalize_answer(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().strip("`\"'")
    if not text or text.lower() in {"null", "none", "abstain", "unknown"}:
        return None
    return re.sub(r"\s+", "", text).casefold()


def parse_response(raw: str) -> tuple[str | None, str]:
    try:
        obj = json.loads(raw.strip())
    except (json.JSONDecodeError, TypeError):
        return None, "malformed"
    if not isinstance(obj, dict) or set(obj) != {"answer", "abstain", "provenance"}:
        return None, "malformed"
    if not isinstance(obj["abstain"], bool):
        return None, "malformed"
    if obj["abstain"] or obj["answer"] is None:
        return None, "abstain"
    ans = normalize_answer(obj["answer"])
    return (ans, "ok") if ans else (None, "abstain")


def score_response(raw: str, gold: str, stale_answers: Iterable[str] = ()) -> dict[str, Any]:
    answer, status = parse_response(raw)
    normalized_gold = normalize_answer(gold)
    stale = {normalize_answer(x) for x in stale_answers}
    stale.discard(None)
    return {
        "status": status,
        "correct": int(answer is not None and answer == normalized_gold),
        "stale_state": int(answer is not None and answer in stale and answer != normalized_gold),
        "normalized_answer": answer,
    }


def world_clustered_analysis(rows: list[dict[str, Any]], *, condition_1: str = "B", condition_2: str = "C", bootstrap_draws: int = 10_000, signflip_draws: int = 100_000, seed: int = 20261112) -> dict[str, Any]:
    """World-level paired analysis; each world's queries receive equal weight."""
    arms: dict[tuple[str, str], int] = {}
    lengths: dict[tuple[str, str], int] = {}
    worlds: dict[str, set[str]] = {}
    for row in rows:
        if row["condition"] not in CONDITIONS:
            raise ValueError(f"unknown condition: {row['condition']}")
        world, query, condition = row["world_id"], row["query_id"], row["condition"]
        key = (query, condition)
        if key in arms:
            raise ValueError(f"duplicate prediction: {key}")
        arms[key] = int(bool(row.get("correct", 0)))
        if row.get("prompt_tokens") is not None:
            lengths[key] = int(row["prompt_tokens"])
        worlds.setdefault(world, set()).add(query)
    deltas = []
    length_deltas = []
    for world, queries in sorted(worlds.items()):
        diffs = []
        arm_lengths_1, arm_lengths_2 = [], []
        for query in sorted(queries):
            if (query, condition_1) not in arms or (query, condition_2) not in arms:
                raise ValueError(f"incomplete {condition_1}/{condition_2} pair: {query}")
            diffs.append(arms[(query, condition_1)] - arms[(query, condition_2)])
            if (query, condition_1) in lengths and (query, condition_2) in lengths:
                arm_lengths_1.append(lengths[(query, condition_1)])
                arm_lengths_2.append(lengths[(query, condition_2)])
        deltas.append(sum(diffs) / len(diffs))
        if arm_lengths_1 and len(arm_lengths_1) == len(diffs):
            length_deltas.append(sum(arm_lengths_1) / len(arm_lengths_1) - sum(arm_lengths_2) / len(arm_lengths_2))
    if not deltas:
        raise ValueError("no worlds to analyze")
    estimate = sum(deltas) / len(deltas)
    rng = random.Random(seed)
    boot = sorted(sum(deltas[rng.randrange(len(deltas))] for _ in deltas) / len(deltas) for _ in range(bootstrap_draws))
    def percentile(sorted_values: list[float], p: float) -> float:
        pos = (len(sorted_values) - 1) * p
        lo = math.floor(pos); hi = math.ceil(pos)
        if lo == hi:
            return sorted_values[lo]
        return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)
    exceed = 0
    for _ in range(signflip_draws):
        perm = sum((1 if rng.getrandbits(1) else -1) * d for d in deltas) / len(deltas)
        if abs(perm) >= abs(estimate) - 1e-15:
            exceed += 1
    result = {
        "comparison": f"{condition_1}_minus_{condition_2}",
        "n_worlds": len(deltas),
        "n_queries": sum(len(qs) for qs in worlds.values()),
        "mean_world_paired_difference": estimate,
        "world_bootstrap_95_percentile_ci": [percentile(boot, .025), percentile(boot, .975)],
        "paired_sign_flip_two_sided_p": (exceed + 1) / (signflip_draws + 1),
        "bootstrap_draws": bootstrap_draws,
        "signflip_draws": signflip_draws,
        "seed": seed,
    }
    if len(length_deltas) == len(deltas) and len(deltas) >= 3:
        def corr(xs: list[float], ys: list[float]) -> float:
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            dx, dy = [x - mx for x in xs], [y - my for y in ys]
            denom = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
            return sum(x * y for x, y in zip(dx, dy)) / denom if denom else 0.0
        observed_r = corr(length_deltas, deltas)
        length_exceed = 0
        shuffled = list(length_deltas)
        for _ in range(signflip_draws):
            rng.shuffle(shuffled)
            if abs(corr(shuffled, deltas)) >= abs(observed_r) - 1e-15:
                length_exceed += 1
        result["prompt_length_effect_association"] = {
            "method": "Pearson correlation between per-world paired accuracy and per-world mean token-count difference; two-sided permutation test",
            "pearson_r": observed_r,
            "permutation_p": (length_exceed + 1) / (signflip_draws + 1),
            "n_worlds": len(deltas),
            "mean_prompt_token_difference": sum(length_deltas) / len(length_deltas),
            "permutations": signflip_draws,
        }
    return result


def validate_scorer() -> dict[str, Any]:
    examples = [
        ('{"answer":"person:2","abstain":false,"provenance":null}', "person:2", [], 1, "ok"),
        ('{"answer":"person:1","abstain":false,"provenance":null}', "person:2", ["person:1"], 0, "ok"),
        ('{"answer":"mystery","abstain":false,"provenance":null}', "person:2", [], 0, "ok"),
        ('not json', "person:2", [], 0, "malformed"),
        ('{"answer":null,"abstain":true,"provenance":null}', "person:2", [], 0, "abstain"),
    ]
    for raw, gold, stale, expected, status in examples:
        scored = score_response(raw, gold, stale)
        if scored["correct"] != expected or scored["status"] != status:
            raise AssertionError(f"scorer validation failed: {raw!r}: {scored}")
    return {"examples": len(examples), "passed": True, "labels_seen": ["correct", "stale", "other", "malformed", "abstain"]}
