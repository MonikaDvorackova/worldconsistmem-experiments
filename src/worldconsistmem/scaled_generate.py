"""Configurable scaled world grammar (does not alter smoke generate_world defaults)."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Optional

from .generate import (
    FIRST_NAMES,
    LOC_STEMS,
    ORG_STEMS,
    PROJECT_STEMS,
    GeneratedWorld,
    _eid,
    _event,
    _prov,
)
from .models import EventType, Interval, Location, Organization, Person, Project, ProjectOwnership
from .world import WorldState, apply_event, replay


@dataclass
class TierConfig:
    name: str
    n_persons: int
    n_orgs: int
    n_projects: int
    n_locations: int
    target_events: int
    extra_ceo_replacements: int
    extra_ownership_transfers: int
    extra_doc_revisions: int
    extra_conflicts: int
    extra_temp_cycles: int
    n_bundles: int
    relation_density: float  # 0-1 controls padding relation events


TIERS = {
    "small": TierConfig(
        "small", 4, 2, 2, 3, 35, 0, 0, 1, 1, 1, 10, 0.2
    ),
    "medium": TierConfig(
        "medium", 6, 3, 3, 4, 100, 2, 2, 3, 2, 2, 10, 0.5
    ),
    "large": TierConfig(
        "large", 8, 4, 4, 5, 220, 4, 4, 5, 4, 3, 12, 0.8
    ),
}


def _rng(seed: int, world_idx: int, tier: str) -> random.Random:
    material = f"worldconsistmem:scaled:{tier}:{seed}:{world_idx}".encode()
    digest = hashlib.sha256(material).hexdigest()
    return random.Random(int(digest[:16], 16))


def _bootstrap(rng: random.Random, world_id: str, cfg: TierConfig) -> tuple[WorldState, dict[str, Any]]:
    w = WorldState(t=0)
    for i in range(cfg.n_locations):
        lid = _eid(world_id, "loc", i)
        w.locations[lid] = Location(lid, f"{rng.choice(LOC_STEMS)}-{world_id[-4:]}-{i}")
    locs = list(w.locations.keys())
    for i in range(cfg.n_persons):
        pid = _eid(world_id, "person", i)
        w.persons[pid] = Person(pid, f"{rng.choice(FIRST_NAMES)}-{i}", rng.choice(locs))
    for i in range(cfg.n_orgs):
        oid = _eid(world_id, "org", i)
        w.orgs[oid] = Organization(oid, f"{rng.choice(ORG_STEMS)}-{world_id[-4:]}-{i}")
    for i in range(cfg.n_projects):
        prid = _eid(world_id, "project", i)
        w.projects[prid] = Project(prid, f"{rng.choice(PROJECT_STEMS)}-{i}", "planned")

    persons = list(w.persons.keys())
    orgs = list(w.orgs.keys())
    projects = list(w.projects.keys())
    meta = {
        "tier": cfg.name,
        "persons": persons,
        "orgs": orgs,
        "projects": projects,
        "locations": locs,
        "ceo_org": orgs[0],
        "other_org": orgs[1 % len(orgs)],
        "focal_project": projects[0],
        "other_project": projects[1 % len(projects)],
        "ceo0": persons[0],
        "ceo1": persons[1],
        "employee": persons[2],
        "outsider": persons[3 % len(persons)],
    }
    for i, proj in enumerate(projects):
        org = orgs[i % len(orgs)]
        w.ownerships.append(
            ProjectOwnership(proj, org, Interval(0), f"{world_id}:prov:init_own:{i}")
        )
    return w, meta


def generate_scaled_world(
    seed: int, world_idx: int, tier: str = "small"
) -> GeneratedWorld:
    cfg = TIERS[tier]
    world_id = f"s{tier[0]}{seed:04d}_{world_idx:03d}"
    rng = _rng(seed, world_idx, tier)
    w0, meta = _bootstrap(rng, world_id, cfg)

    org_a, org_b = meta["ceo_org"], meta["other_org"]
    persons = meta["persons"]
    p0, p1, p2, p3 = meta["ceo0"], meta["ceo1"], meta["employee"], meta["outsider"]
    proj, proj2 = meta["focal_project"], meta["other_project"]
    locs = meta["locations"]
    orgs = meta["orgs"]
    projects = meta["projects"]

    base_doc = _eid(world_id, "docbase", 0)
    doc_counter = [0]
    rel_counter = [0]
    conflict_counter = [0]
    temp_counter = [0]

    def next_doc():
        d = _eid(world_id, "doc", doc_counter[0])
        doc_counter[0] += 1
        return d

    def next_rel():
        r = _eid(world_id, "rel", rel_counter[0])
        rel_counter[0] += 1
        return r

    def next_conflict():
        c = _eid(world_id, "conflict", conflict_counter[0])
        conflict_counter[0] += 1
        return c

    def next_temp():
        t = _eid(world_id, "temp", temp_counter[0])
        temp_counter[0] += 1
        return t

    doc_v1 = next_doc()
    rel_id = next_rel()
    conflict_id = next_conflict()
    temp_id = next_temp()

    plan: list[tuple] = [
        (EventType.PERSON_JOINS_ORG, {"person_id": p0, "org_id": org_a}, [p0, org_a], [], None, "join"),
        (EventType.ROLE_ASSIGNMENT, {"person_id": p0, "org_id": org_a, "role": "CEO", "exclusive": True}, [p0, org_a], [], p0, "ceo"),
        (EventType.PERSON_JOINS_ORG, {"person_id": p1, "org_id": org_a}, [p1, org_a], [], None, "join"),
        (EventType.PERSON_JOINS_ORG, {"person_id": p2, "org_id": org_a}, [p2, org_a], [], None, "join"),
        (EventType.PROJECT_STATUS_CHANGE, {"project_id": proj, "status": "active", "manager_id": p0}, [proj], [], p0, "status"),
        (EventType.RELATIONSHIP_CREATION, {"rel_id": rel_id, "rel_type": "manages", "source_id": p0, "target_id": proj}, [p0, proj], [], p0, "rel"),
        (EventType.DOCUMENT_CREATION, {"doc_id": doc_v1, "base_doc_id": base_doc, "title": f"Charter-{proj}", "project_id": proj, "author_id": p2}, [doc_v1], [], p2, "doc"),
        (EventType.DOCUMENT_APPROVAL, {"doc_id": doc_v1, "approver_id": p0}, [doc_v1], [], p0, "approve"),
        (EventType.LOCATION_CHANGE, {"person_id": p2, "location_id": locs[1 % len(locs)]}, [p2], [], p2, "loc"),
        (EventType.ROLE_ASSIGNMENT, {"person_id": p2, "org_id": org_a, "role": "Engineer", "exclusive": False}, [p2], [], p2, "eng"),
        (EventType.CONFLICT_INTRODUCTION, {"conflict_id": conflict_id, "subject": proj, "attribute": "priority", "value_a": "P0", "value_b": "P2"}, [proj], [], p1, "conf"),
        (EventType.TEMPORARY_STATE, {"mark_id": temp_id, "entity_id": proj2, "attribute": "project_status", "temporary_value": "paused", "original_value": "planned"}, [proj2], [], p3, "temp"),
        (EventType.PERSON_JOINS_ORG, {"person_id": p3, "org_id": org_b}, [p3, org_b], [], None, "join"),
        (EventType.ROLE_ASSIGNMENT, {"person_id": p3, "org_id": org_b, "role": "CEO", "exclusive": True}, [p3], [], p3, "ceo_b"),
        (EventType.DOCUMENT_REVISION, {"base_doc_id": base_doc, "doc_id": next_doc(), "author_id": p2, "expected_prev_version": 1}, [], [], p2, "rev"),
        (EventType.ROLE_REPLACEMENT, {"org_id": org_a, "role": "CEO", "new_person_id": p1, "old_person_id": p0}, [p0, p1], [], p1, "replace"),
        (EventType.RELATIONSHIP_TERMINATION, {"rel_id": rel_id}, [rel_id], [], p0, "endrel"),
        (EventType.RELATIONSHIP_CREATION, {"rel_id": next_rel(), "rel_type": "manages", "source_id": p1, "target_id": proj}, [p1, proj], [], p1, "rel2"),
        (EventType.PROJECT_OWNERSHIP_TRANSFER, {"project_id": proj, "new_org_id": org_b, "old_org_id": org_a}, [proj, org_a, org_b], [], p3, "own"),
        (EventType.PROJECT_STATUS_CHANGE, {"project_id": proj, "status": "transferred", "manager_id": p1}, [proj], [], p1, "status2"),
        (EventType.CONFLICT_RESOLUTION, {"conflict_id": conflict_id, "resolved_value": "P0"}, [conflict_id], [], p1, "resolve"),
        (EventType.REVERSION, {"mark_id": temp_id}, [temp_id], [], p3, "revert"),
        (EventType.PERSON_LEAVES_ORG, {"person_id": p0, "org_id": org_a}, [p0], [], p0, "leave"),
        (EventType.LOCATION_CHANGE, {"person_id": p1, "location_id": locs[2 % len(locs)]}, [p1], [], p1, "loc2"),
    ]
    # approve latest doc if exists
    last_doc = f"{world_id}:doc:{doc_counter[0]-1}"
    plan.append((EventType.DOCUMENT_APPROVAL, {"doc_id": last_doc, "approver_id": p1}, [last_doc], [], p1, "approve2"))

    # Extra persons join other orgs
    for pi, person in enumerate(persons[4:], start=4):
        org = orgs[pi % len(orgs)]
        # skip if already in plan as employed — only new persons
        plan.append((EventType.PERSON_JOINS_ORG, {"person_id": person, "org_id": org}, [person, org], [], None, "xjoin"))

    # Extra CEO replacement cycles (alternate between remaining people in org_a)
    ceo_pool = [p for p in persons if p != p0][: max(2, cfg.n_persons // 2)]
    cur_ceo = p1
    for i in range(cfg.extra_ceo_replacements):
        # ensure candidate employed at org_a
        nxt = ceo_pool[i % len(ceo_pool)]
        if nxt == cur_ceo:
            nxt = ceo_pool[(i + 1) % len(ceo_pool)]
        plan.append((EventType.PERSON_JOINS_ORG, {"person_id": nxt, "org_id": org_a}, [nxt, org_a], [], None, "ceojoin"))
        # leave may fail if already employed elsewhere — try join only if not employed; apply_event will reject
        # Use role replacement only; join might fail — handle by catching during apply and skipping
        plan.append((EventType.ROLE_REPLACEMENT, {"org_id": org_a, "role": "CEO", "new_person_id": nxt, "old_person_id": cur_ceo}, [cur_ceo, nxt], [], nxt, "xreplace"))
        cur_ceo = nxt

    # Ownership ping-pong
    cur_owner = org_b
    for i in range(cfg.extra_ownership_transfers):
        nxt = orgs[(i + 2) % len(orgs)]
        if nxt == cur_owner:
            nxt = orgs[(i + 1) % len(orgs)]
        plan.append(
            (
                EventType.PROJECT_OWNERSHIP_TRANSFER,
                {"project_id": proj, "new_org_id": nxt, "old_org_id": cur_owner},
                [proj, cur_owner, nxt],
                [],
                p3,
                "xown",
            )
        )
        cur_owner = nxt

    # Doc revisions
    prev_v = 2  # after first revision in core
    for i in range(cfg.extra_doc_revisions):
        nd = next_doc()
        plan.append(
            (
                EventType.DOCUMENT_REVISION,
                {"base_doc_id": base_doc, "doc_id": nd, "author_id": p2, "expected_prev_version": prev_v},
                [nd],
                [],
                p2,
                "xrev",
            )
        )
        plan.append((EventType.DOCUMENT_APPROVAL, {"doc_id": nd, "approver_id": cur_ceo}, [nd], [], cur_ceo, "xappr"))
        prev_v += 1

    # Extra conflicts
    for i in range(cfg.extra_conflicts):
        cid = next_conflict()
        subj = projects[i % len(projects)]
        plan.append(
            (
                EventType.CONFLICT_INTRODUCTION,
                {"conflict_id": cid, "subject": subj, "attribute": "priority", "value_a": f"A{i}", "value_b": f"B{i}"},
                [subj],
                [],
                p1,
                "xconf",
            )
        )
        plan.append(
            (
                EventType.CONFLICT_RESOLUTION,
                {"conflict_id": cid, "resolved_value": f"A{i}"},
                [cid],
                [],
                p1,
                "xres",
            )
        )

    # Temp cycles on other projects
    for i in range(cfg.extra_temp_cycles):
        pr = projects[(i + 1) % len(projects)]
        mid = next_temp()
        # status may not be planned — use a status change first then temp
        plan.append((EventType.PROJECT_STATUS_CHANGE, {"project_id": pr, "status": "planned"}, [pr], [], p3, "xstat"))
        plan.append(
            (
                EventType.TEMPORARY_STATE,
                {
                    "mark_id": mid,
                    "entity_id": pr,
                    "attribute": "project_status",
                    "temporary_value": "paused",
                    "original_value": "planned",
                },
                [pr],
                [],
                p3,
                "xtemp",
            )
        )
        plan.append((EventType.REVERSION, {"mark_id": mid}, [mid], [], p3, "xrevt"))

    # Density padding
    pad_target = cfg.target_events
    statuses = ["active", "review", "hold", "planned"]
    while len(plan) < pad_target:
        i = len(plan)
        if rng.random() < cfg.relation_density and i % 5 == 0:
            a, b = rng.sample(persons, 2) if len(persons) >= 2 else (p0, p1)
            rid = next_rel()
            plan.append(
                (
                    EventType.RELATIONSHIP_CREATION,
                    {"rel_id": rid, "rel_type": "collaborates", "source_id": a, "target_id": b},
                    [a, b],
                    [],
                    a,
                    "padrel",
                )
            )
            if rng.random() < 0.5:
                plan.append((EventType.RELATIONSHIP_TERMINATION, {"rel_id": rid}, [rid], [], a, "padend"))
        elif i % 2 == 0:
            plan.append(
                (
                    EventType.LOCATION_CHANGE,
                    {"person_id": rng.choice(persons), "location_id": rng.choice(locs)},
                    [],
                    [],
                    None,
                    "padloc",
                )
            )
        else:
            plan.append(
                (
                    EventType.PROJECT_STATUS_CHANGE,
                    {"project_id": rng.choice(projects), "status": rng.choice(statuses)},
                    [],
                    [],
                    None,
                    "padstat",
                )
            )

    events = []
    state = w0.clone()
    t = 0
    for etype, payload, affected, pre, actor, narr in plan:
        # Skip invalid joins if already employed
        if etype == EventType.PERSON_JOINS_ORG:
            pid = payload["person_id"]
            if state.employer_of(pid, state.t) is not None or state.employer_of(pid) is not None:
                # already employed — skip
                continue
        if etype == EventType.ROLE_REPLACEMENT:
            holder = state.role_holder(payload["org_id"], payload["role"])
            if holder is None:
                continue
            # ensure new person employed
            if state.employer_of(payload["new_person_id"]) != payload["org_id"]:
                # try join first as separate event
                t += 1
                join = _event(
                    world_id,
                    t,
                    EventType.PERSON_JOINS_ORG,
                    {"person_id": payload["new_person_id"], "org_id": payload["org_id"]},
                    [payload["new_person_id"], payload["org_id"]],
                    [],
                    None,
                    "autojoin",
                )
                try:
                    state = apply_event(state, join)
                    events.append(join)
                except Exception:
                    t -= 1
                    continue
        t += 1
        ev = _event(world_id, t, etype, payload, affected, pre, actor, narr)
        try:
            state = apply_event(state, ev)
        except Exception:
            t -= 1
            continue
        events.append(ev)

    # Ensure we have enough events by safe padding
    while len(events) < max(20, cfg.target_events // 2):
        t += 1
        loc = locs[t % len(locs)]
        ev = _event(
            world_id,
            t,
            EventType.LOCATION_CHANGE,
            {"person_id": p2, "location_id": loc},
            [p2, loc],
            [],
            p2,
            "safepad",
        )
        try:
            state = apply_event(state, ev)
            events.append(ev)
        except Exception:
            break

    states = replay(w0, events)

    # Meta from final history
    ceo_replaces = [
        e
        for e in events
        if e.event_type == EventType.ROLE_REPLACEMENT and e.payload.get("org_id") == org_a
    ]
    owns = [
        e
        for e in events
        if e.event_type == EventType.PROJECT_OWNERSHIP_TRANSFER and e.payload.get("project_id") == proj
    ]
    revs = [e for e in events if e.event_type == EventType.DOCUMENT_REVISION]
    conf_intros = [e for e in events if e.event_type == EventType.CONFLICT_INTRODUCTION]
    conf_res = [e for e in events if e.event_type == EventType.CONFLICT_RESOLUTION]

    meta.update(
        {
            "tier": cfg.name,
            "ceo_replace_t": ceo_replaces[-1].t,
            "ownership_transfer_t": owns[-1].t,
            "doc_revision_t": revs[-1].t,
            "conflict_intro_t": conf_intros[0].t,
            "conflict_resolve_t": conf_res[0].t,
            "base_doc": base_doc,
            "doc_v1": doc_v1,
            "doc_v2": revs[0].payload["doc_id"] if revs else doc_v1,
            "rel_id": rel_id,
            "conflict_id": conf_intros[0].payload["conflict_id"],
            "temp_id": temp_id,
            "n_ceo_replacements": len(ceo_replaces),
            "n_ownership_transfers": len(owns),
            "n_doc_revisions": len(revs),
            "n_conflicts": len(conf_intros),
            "target_bundles": cfg.n_bundles,
        }
    )
    meta["hist_ceo_time"] = meta["ceo_replace_t"] - 1

    return GeneratedWorld(world_id, seed, world_idx, w0, events, states, meta)


def generate_scaled_dataset(
    seed: int = 100,
    worlds_per_tier: int = 34,
) -> list[GeneratedWorld]:
    worlds: list[GeneratedWorld] = []
    idx = 0
    for tier in ("small", "medium", "large"):
        for i in range(worlds_per_tier):
            worlds.append(generate_scaled_world(seed + idx, i, tier=tier))
            idx += 1
    return worlds
