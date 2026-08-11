"""Load frozen smoke artefacts and rebuild runtime objects."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..generate import GeneratedWorld, generate_world
from ..io_util import read_jsonl
from ..models import (
    AnswerSchema,
    ConstraintFamily,
    Event,
    EventType,
    Observation,
    Query,
    QueryBundle,
    QueryFamily,
)
from ..world import WorldState, replay


ROOT = Path(__file__).resolve().parents[3]
SMOKE = ROOT / "data" / "smoke"


def smoke_checksum(data_dir: Path | None = None) -> str:
    data_dir = data_dir or SMOKE
    h = hashlib.sha256()
    for f in sorted(data_dir.glob("*.jsonl")):
        h.update(f.name.encode())
        h.update(b"\0")
        h.update(f.read_bytes())
    return h.hexdigest()


EXPECTED_SMOKE_SHA256 = "3aa67ed1b6a39be3d9e1805d14f7d5ce7cc05f4655bdce0bc4ff49900c14c7ab"


def assert_frozen_smoke(data_dir: Path | None = None) -> str:
    digest = smoke_checksum(data_dir)
    if digest != EXPECTED_SMOKE_SHA256:
        raise RuntimeError(
            f"Smoke checksum mismatch: got {digest}, expected {EXPECTED_SMOKE_SHA256}. "
            "Refusing to run baselines against a mutated benchmark."
        )
    return digest


def load_observations(path: Path | None = None) -> dict[str, list[Observation]]:
    path = path or (SMOKE / "observations.jsonl")
    by_world: dict[str, list[Observation]] = {}
    for row in read_jsonl(path):
        obs = Observation(
            observation_id=row["observation_id"],
            event_id=row["event_id"],
            t=row["t"],
            provenance_id=row["provenance_id"],
            structured=row["structured"],
            text_canonical=row["text_canonical"],
            text_paraphrase=row["text_paraphrase"],
            is_distractor=row.get("is_distractor", False),
        )
        wid = row.get("world_id") or obs.observation_id.split(":obs:")[0]
        by_world.setdefault(wid, []).append(obs)
    for wid in by_world:
        by_world[wid].sort(key=lambda o: (o.t, o.observation_id))
    return by_world


def load_bundles(path: Path | None = None) -> list[QueryBundle]:
    path = path or (SMOKE / "query_bundles.jsonl")
    bundles = []
    for row in read_jsonl(path):
        queries = []
        for q in row["queries"]:
            queries.append(
                Query(
                    query_id=q["query_id"],
                    bundle_id=q["bundle_id"],
                    family=QueryFamily(q["family"]),
                    text=q["text"],
                    structured=q["structured"],
                    target_time=q.get("target_time"),
                    target_interval=None,
                    gold_answer=q["gold_answer"],
                    answer_schema=AnswerSchema(q["answer_schema"]),
                    applicable_constraints=[
                        ConstraintFamily(c) for c in q["applicable_constraints"]
                    ],
                    supporting_event_ids=q["supporting_event_ids"],
                    supporting_provenance_ids=q["supporting_provenance_ids"],
                    metadata=q.get("metadata") or {},
                )
            )
        bundles.append(
            QueryBundle(
                bundle_id=row["bundle_id"],
                world_id=row["world_id"],
                focal_entities=row["focal_entities"],
                queries=queries,
                description=row.get("description", ""),
                metadata=row.get("metadata") or {},
            )
        )
    return bundles


def load_worlds_via_seed(seed: int = 42, n_worlds: int = 25) -> dict[str, GeneratedWorld]:
    """Rebuild worlds deterministically from the frozen generator seed.

    Does not rewrite smoke files. Oracle uses these regenerated gold states,
    which must match frozen worlds (verified by checksum of event ids).
    """
    worlds = {}
    for i in range(n_worlds):
        w = generate_world(seed, i, min_events=20)
        worlds[w.world_id] = w
    return worlds


def verify_worlds_match_frozen(worlds: dict[str, GeneratedWorld], path: Path | None = None) -> None:
    path = path or (SMOKE / "events.jsonl")
    frozen_ids = []
    for row in read_jsonl(path):
        frozen_ids.append(row["event_id"])
    regen_ids = []
    for wid in sorted(worlds):
        regen_ids.extend([e.event_id for e in worlds[wid].events])
    if frozen_ids != regen_ids:
        raise RuntimeError("Regenerated worlds do not match frozen events.jsonl")
