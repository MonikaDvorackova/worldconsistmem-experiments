"""Deterministic evolving-world generator."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Optional

from .models import Interval, ProjectOwnership
from .models import Event, EventType, Location, Organization, Person, Project
from .world import WorldState, apply_event, replay

FIRST_NAMES = [
    "Ada", "Blake", "Casey", "Dana", "Eden", "Finn", "Gray", "Harper",
    "Indigo", "Jordan", "Kai", "Logan", "Morgan", "Noa", "Oakley", "Parker",
]
ORG_STEMS = ["Acme", "Globex", "Initech", "Umbrella", "Hooli", "Stark", "Wayne"]
PROJECT_STEMS = ["Orion", "Nova", "Atlas", "Helix", "Pulse", "Quartz", "Ridge"]
LOC_STEMS = ["Berlin", "Cairo", "Dublin", "Oslo", "Tokyo", "Lima", "Nairobi"]


def _rng(seed: int, world_idx: int) -> random.Random:
    material = f"worldconsistmem:{seed}:{world_idx}".encode()
    digest = hashlib.sha256(material).hexdigest()
    return random.Random(int(digest[:16], 16))


def _eid(world_id: str, kind: str, i: int) -> str:
    return f"{world_id}:{kind}:{i}"


def _prov(world_id: str, t: int) -> str:
    return f"{world_id}:prov:{t}"


def _event(
    world_id: str,
    t: int,
    etype: EventType,
    payload: dict[str, Any],
    affected: list[str],
    preconditions: list[str],
    actor: Optional[str] = None,
    narrative: str = "",
) -> Event:
    return Event(
        event_id=f"{world_id}:e:{t}",
        event_type=etype,
        t=t,
        actor_id=actor,
        affected_ids=affected,
        payload=payload,
        preconditions=preconditions,
        provenance_id=_prov(world_id, t),
        narrative=narrative,
    )


@dataclass
class GeneratedWorld:
    world_id: str
    seed: int
    world_idx: int
    initial: WorldState
    events: list[Event]
    states: list[WorldState]
    meta: dict[str, Any]

    @property
    def final(self) -> WorldState:
        return self.states[-1]

    @property
    def T(self) -> int:
        return self.final.t

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "seed": self.seed,
            "world_idx": self.world_idx,
            "T": self.T,
            "meta": self.meta,
            "W0": self.initial.to_dict(),
            "states": [s.to_dict() for s in self.states],
            "event_ids": [e.event_id for e in self.events],
            "gold_history": {
                "events": [e.to_dict() for e in self.events],
                "n_states": len(self.states),
            },
        }


def _bootstrap(rng: random.Random, world_id: str) -> tuple[WorldState, dict[str, Any]]:
    w = WorldState(t=0)
    for i in range(3):
        lid = _eid(world_id, "loc", i)
        w.locations[lid] = Location(lid, f"{rng.choice(LOC_STEMS)}-{world_id[-4:]}-{i}")
    locs = list(w.locations.keys())
    for i in range(4):
        pid = _eid(world_id, "person", i)
        w.persons[pid] = Person(pid, f"{rng.choice(FIRST_NAMES)}-{i}", rng.choice(locs))
    for i in range(2):
        oid = _eid(world_id, "org", i)
        w.orgs[oid] = Organization(oid, f"{rng.choice(ORG_STEMS)}-{world_id[-4:]}-{i}")
    for i in range(2):
        prid = _eid(world_id, "project", i)
        w.projects[prid] = Project(prid, f"{rng.choice(PROJECT_STEMS)}-{i}", "planned")

    persons = list(w.persons.keys())
    orgs = list(w.orgs.keys())
    projects = list(w.projects.keys())
    meta = {
        "persons": persons,
        "orgs": orgs,
        "projects": projects,
        "locations": locs,
        "ceo_org": orgs[0],
        "other_org": orgs[1],
        "focal_project": projects[0],
        "other_project": projects[1],
        "ceo0": persons[0],
        "ceo1": persons[1],
        "employee": persons[2],
        "outsider": persons[3],
    }
    # Initial exclusive ownership (open from t=0)
    w.ownerships.append(
        ProjectOwnership(projects[0], orgs[0], Interval(0), f"{world_id}:prov:init_own")
    )
    w.ownerships.append(
        ProjectOwnership(projects[1], orgs[1], Interval(0), f"{world_id}:prov:init_own2")
    )
    return w, meta


def generate_world(seed: int, world_idx: int, min_events: int = 20) -> GeneratedWorld:
    world_id = f"w{seed:04d}_{world_idx:03d}"
    rng = _rng(seed, world_idx)
    w0, meta = _bootstrap(rng, world_id)

    org_a, org_b = meta["ceo_org"], meta["other_org"]
    p0, p1, p2, p3 = meta["ceo0"], meta["ceo1"], meta["employee"], meta["outsider"]
    proj, proj2 = meta["focal_project"], meta["other_project"]
    locs = meta["locations"]
    base_doc = _eid(world_id, "docbase", 0)
    doc_v1, doc_v2 = _eid(world_id, "doc", 0), _eid(world_id, "doc", 1)
    rel_id = _eid(world_id, "rel", 0)
    conflict_id = _eid(world_id, "conflict", 0)
    temp_id = _eid(world_id, "temp", 0)

    plan: list[tuple] = [
        (EventType.PERSON_JOINS_ORG, {"person_id": p0, "org_id": org_a}, [p0, org_a], ["not_employed"], None, f"{p0} joins {org_a}"),
        (EventType.ROLE_ASSIGNMENT, {"person_id": p0, "org_id": org_a, "role": "CEO", "exclusive": True}, [p0, org_a], ["employed"], p0, f"{p0} CEO of {org_a}"),
        (EventType.PERSON_JOINS_ORG, {"person_id": p1, "org_id": org_a}, [p1, org_a], ["not_employed"], None, f"{p1} joins {org_a}"),
        (EventType.PERSON_JOINS_ORG, {"person_id": p2, "org_id": org_a}, [p2, org_a], ["not_employed"], None, f"{p2} joins {org_a}"),
        (EventType.PROJECT_STATUS_CHANGE, {"project_id": proj, "status": "active", "manager_id": p0}, [proj, p0], [], p0, f"{proj} active"),
        (EventType.RELATIONSHIP_CREATION, {"rel_id": rel_id, "rel_type": "manages", "source_id": p0, "target_id": proj}, [p0, proj], [], p0, f"{p0} manages {proj}"),
        (EventType.DOCUMENT_CREATION, {"doc_id": doc_v1, "base_doc_id": base_doc, "title": f"Charter-{proj}", "project_id": proj, "author_id": p2}, [doc_v1, proj], [], p2, f"create {doc_v1}"),
        (EventType.DOCUMENT_APPROVAL, {"doc_id": doc_v1, "approver_id": p0}, [doc_v1, p0], [], p0, f"approve {doc_v1}"),
        (EventType.LOCATION_CHANGE, {"person_id": p2, "location_id": locs[1]}, [p2, locs[1]], [], p2, f"{p2} relocates"),
        (EventType.ROLE_ASSIGNMENT, {"person_id": p2, "org_id": org_a, "role": "Engineer", "exclusive": False}, [p2, org_a], [], p2, f"{p2} Engineer"),
        (EventType.CONFLICT_INTRODUCTION, {"conflict_id": conflict_id, "subject": proj, "attribute": "priority", "value_a": "P0", "value_b": "P2"}, [proj], [], p1, "conflict intro"),
        (EventType.TEMPORARY_STATE, {"mark_id": temp_id, "entity_id": proj2, "attribute": "project_status", "temporary_value": "paused", "original_value": "planned"}, [proj2], [], p3, "temp pause"),
        (EventType.PERSON_JOINS_ORG, {"person_id": p3, "org_id": org_b}, [p3, org_b], [], None, f"{p3} joins {org_b}"),
        (EventType.ROLE_ASSIGNMENT, {"person_id": p3, "org_id": org_b, "role": "CEO", "exclusive": True}, [p3, org_b], [], p3, f"{p3} CEO {org_b}"),
        (EventType.DOCUMENT_REVISION, {"base_doc_id": base_doc, "doc_id": doc_v2, "author_id": p2, "expected_prev_version": 1}, [doc_v2], [], p2, "doc revision"),
        (EventType.ROLE_REPLACEMENT, {"org_id": org_a, "role": "CEO", "new_person_id": p1, "old_person_id": p0}, [p0, p1, org_a], [], p1, "CEO replace"),
        (EventType.RELATIONSHIP_TERMINATION, {"rel_id": rel_id}, [rel_id], [], p0, "end manages"),
        (EventType.RELATIONSHIP_CREATION, {"rel_id": _eid(world_id, "rel", 1), "rel_type": "manages", "source_id": p1, "target_id": proj}, [p1, proj], [], p1, f"{p1} manages"),
        (EventType.PROJECT_OWNERSHIP_TRANSFER, {"project_id": proj, "new_org_id": org_b, "old_org_id": org_a}, [proj, org_a, org_b], [], p3, "ownership transfer"),
        (EventType.PROJECT_STATUS_CHANGE, {"project_id": proj, "status": "transferred", "manager_id": p1}, [proj], [], p1, "status transferred"),
        (EventType.CONFLICT_RESOLUTION, {"conflict_id": conflict_id, "resolved_value": "P0"}, [conflict_id], [], p1, "conflict resolve"),
        (EventType.REVERSION, {"mark_id": temp_id}, [temp_id], [], p3, "reversion"),
        (EventType.PERSON_LEAVES_ORG, {"person_id": p0, "org_id": org_a}, [p0, org_a], [], p0, f"{p0} leaves"),
        (EventType.LOCATION_CHANGE, {"person_id": p1, "location_id": locs[2]}, [p1, locs[2]], [], p1, f"{p1} relocates"),
        (EventType.DOCUMENT_APPROVAL, {"doc_id": doc_v2, "approver_id": p1}, [doc_v2, p1], [], p1, f"approve {doc_v2}"),
    ]

    while len(plan) < min_events:
        i = len(plan)
        if i % 2 == 0:
            plan.append((EventType.LOCATION_CHANGE, {"person_id": p2, "location_id": locs[i % len(locs)]}, [p2], [], p2, "pad loc"))
        else:
            plan.append((EventType.PROJECT_STATUS_CHANGE, {"project_id": proj2, "status": "active" if i % 4 else "review"}, [proj2], [], p3, "pad status"))

    for j in range(rng.randint(0, 3)):
        plan.append((EventType.PROJECT_STATUS_CHANGE, {"project_id": proj2, "status": rng.choice(["active", "review", "planned", "hold"])}, [proj2], [], p3, f"rng pad {j}"))

    events: list[Event] = []
    state = w0.clone()
    for i, (etype, payload, affected, pre, actor, narr) in enumerate(plan, start=1):
        ev = _event(world_id, i, etype, payload, affected, pre, actor, narr)
        try:
            state = apply_event(state, ev)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed {etype} t={i} in {world_id}: {exc}") from exc
        events.append(ev)

    states = replay(w0, events)
    meta.update({
        "ceo_replace_t": next(e.t for e in events if e.event_type == EventType.ROLE_REPLACEMENT and e.payload.get("org_id") == org_a),
        "ownership_transfer_t": next(e.t for e in events if e.event_type == EventType.PROJECT_OWNERSHIP_TRANSFER and e.payload.get("project_id") == proj),
        "doc_revision_t": next(e.t for e in events if e.event_type == EventType.DOCUMENT_REVISION),
        "conflict_intro_t": next(e.t for e in events if e.event_type == EventType.CONFLICT_INTRODUCTION),
        "conflict_resolve_t": next(e.t for e in events if e.event_type == EventType.CONFLICT_RESOLUTION),
        "base_doc": base_doc,
        "doc_v1": doc_v1,
        "doc_v2": doc_v2,
        "rel_id": rel_id,
        "conflict_id": conflict_id,
        "temp_id": temp_id,
    })
    meta["hist_ceo_time"] = meta["ceo_replace_t"] - 1

    return GeneratedWorld(world_id, seed, world_idx, w0, events, states, meta)


def generate_worlds(seed: int, n_worlds: int, min_events: int = 20) -> list[GeneratedWorld]:
    return [generate_world(seed, i, min_events=min_events) for i in range(n_worlds)]
