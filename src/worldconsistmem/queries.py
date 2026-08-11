"""Dependent query-bundle generation."""

from __future__ import annotations

from typing import Any

from .generate import GeneratedWorld
from .models import (
    AnswerSchema,
    ConstraintFamily,
    Query,
    QueryBundle,
    QueryFamily,
)


def _q(
    bundle_id: str,
    suffix: str,
    family: QueryFamily,
    text: str,
    structured: dict[str, Any],
    gold: Any,
    schema: AnswerSchema,
    constraints: list[ConstraintFamily],
    support_events: list[str],
    support_prov: list[str],
    target_time: int | None = None,
    metadata: dict | None = None,
) -> Query:
    return Query(
        query_id=f"{bundle_id}:{suffix}",
        bundle_id=bundle_id,
        family=family,
        text=text,
        structured=structured,
        target_time=target_time,
        target_interval=None,
        gold_answer=gold,
        answer_schema=schema,
        applicable_constraints=constraints,
        supporting_event_ids=support_events,
        supporting_provenance_ids=support_prov,
        metadata=metadata or {},
    )


def _ceo_bundle(world: GeneratedWorld, bi: int) -> QueryBundle:
    m = world.meta
    T = world.T
    org = m["ceo_org"]
    bid = f"{world.world_id}:b:ceo:{bi}"
    replace_t = m["ceo_replace_t"]
    hist_t = m["hist_ceo_time"]
    final = world.final
    hist_state = world.states[hist_t]
    ceo_now = final.role_holder(org, "CEO")
    ceo_then = hist_state.role_holder(org, "CEO")
    assert ceo_now and ceo_then
    replace_ev = next(e for e in world.events if e.t == replace_t)
    assign_ev = next(
        e
        for e in world.events
        if e.event_type.value == "role_assignment"
        and e.payload.get("role") == "CEO"
        and e.payload.get("org_id") == org
    )

    transition = {
        "from": ceo_then.person_id,
        "to": ceo_now.person_id,
        "t": replace_t,
        "role": "CEO",
        "org_id": org,
    }
    queries = [
        _q(
            bid, "current", QueryFamily.CURRENT_STATE,
            f"Who is the CEO of {org} at t={T}?",
            {"attribute": "role_holder", "org_id": org, "role": "CEO", "t": T},
            ceo_now.person_id, AnswerSchema.ENTITY_ID,
            [ConstraintFamily.UNIQUENESS, ConstraintFamily.TRANSITION, ConstraintFamily.RELATIONAL],
            [replace_ev.event_id], [ceo_now.provenance_id], T,
            {"slot": "ceo_current"},
        ),
        _q(
            bid, "historical", QueryFamily.HISTORICAL_STATE,
            f"Who was the CEO of {org} at t={hist_t}?",
            {"attribute": "role_holder", "org_id": org, "role": "CEO", "t": hist_t},
            ceo_then.person_id, AnswerSchema.ENTITY_ID,
            [ConstraintFamily.TEMPORAL, ConstraintFamily.TRANSITION],
            [assign_ev.event_id], [ceo_then.provenance_id], hist_t,
            {"slot": "ceo_historical"},
        ),
        _q(
            bid, "transition", QueryFamily.TRANSITION,
            f"When and how did the CEO of {org} change?",
            {"attribute": "role_replacement", "org_id": org, "role": "CEO"},
            transition, AnswerSchema.TRANSITION_TUPLE,
            [ConstraintFamily.TRANSITION, ConstraintFamily.TEMPORAL, ConstraintFamily.CONTRADICTION],
            [replace_ev.event_id], [replace_ev.provenance_id], replace_t,
            {"slot": "ceo_transition"},
        ),
        _q(
            bid, "multihop", QueryFamily.MULTI_HOP,
            f"Which organization employs the current CEO of {org} at t={T}?",
            {"path": ["ceo_of", "employed_by"], "org_id": org, "t": T},
            final.employer_of(ceo_now.person_id), AnswerSchema.ENTITY_ID,
            [ConstraintFamily.MULTI_HOP, ConstraintFamily.RELATIONAL],
            [replace_ev.event_id], [ceo_now.provenance_id], T,
            {"slot": "ceo_employer", "person_id": ceo_now.person_id},
        ),
        _q(
            bid, "provenance", QueryFamily.PROVENANCE,
            f"Which provenance supports the current CEO of {org}?",
            {"attribute": "role_holder", "org_id": org, "role": "CEO", "t": T},
            ceo_now.provenance_id, AnswerSchema.PROVENANCE_ID,
            [ConstraintFamily.PROVENANCE],
            [replace_ev.event_id], [ceo_now.provenance_id], T,
            {"slot": "ceo_provenance", "fact_value": ceo_now.person_id},
        ),
        _q(
            bid, "temporal_order", QueryFamily.TEMPORAL_ORDER,
            f"Did the initial CEO assignment occur before the CEO replacement for {org}?",
            {"before_event": assign_ev.event_id, "after_event": replace_ev.event_id},
            True, AnswerSchema.BOOLEAN,
            [ConstraintFamily.TEMPORAL],
            [assign_ev.event_id, replace_ev.event_id],
            [assign_ev.provenance_id, replace_ev.provenance_id],
            None,
            {"slot": "ceo_order", "t_before": assign_ev.t, "t_after": replace_t},
        ),
        _q(
            bid, "contradiction", QueryFamily.CONTRADICTION,
            f"Can {ceo_then.person_id} and {ceo_now.person_id} both be exclusive CEO of {org} at t={T}?",
            {"org_id": org, "role": "CEO", "t": T, "candidates": [ceo_then.person_id, ceo_now.person_id]},
            False, AnswerSchema.BOOLEAN,
            [ConstraintFamily.CONTRADICTION, ConstraintFamily.UNIQUENESS],
            [replace_ev.event_id], [ceo_now.provenance_id], T,
            {"slot": "ceo_contradiction"},
        ),
        _q(
            bid, "counterfactual", QueryFamily.COUNTERFACTUAL,
            f"Would claiming {ceo_then.person_id} is still CEO of {org} at t={T} contradict history?",
            {"claim": {"person_id": ceo_then.person_id, "org_id": org, "role": "CEO", "t": T}},
            True, AnswerSchema.BOOLEAN,
            [ConstraintFamily.CONTRADICTION, ConstraintFamily.TRANSITION],
            [replace_ev.event_id], [replace_ev.provenance_id], T,
            {"slot": "ceo_counterfactual", "false_claim_person": ceo_then.person_id},
        ),
    ]
    return QueryBundle(
        bid, world.world_id, [org, m["ceo0"], m["ceo1"]], queries,
        f"CEO succession for {org}",
    )


def _ownership_bundle(world: GeneratedWorld, bi: int) -> QueryBundle:
    m = world.meta
    T = world.T
    proj = m["focal_project"]
    bid = f"{world.world_id}:b:own:{bi}"
    transfer_t = m["ownership_transfer_t"]
    hist_t = transfer_t - 1
    final = world.final
    hist = world.states[hist_t]
    owner_now = final.owner_of(proj)
    owner_then = hist.owner_of(proj)
    ev = next(e for e in world.events if e.t == transfer_t)
    manager = final.projects[proj].manager_id
    mgr_org = final.employer_of(manager) if manager else None

    transition = {"from": owner_then, "to": owner_now, "t": transfer_t, "project_id": proj}
    queries = [
        _q(bid, "current", QueryFamily.CURRENT_STATE,
           f"Which organization owns {proj} at t={T}?",
           {"attribute": "owner", "project_id": proj, "t": T},
           owner_now, AnswerSchema.ENTITY_ID,
           [ConstraintFamily.UNIQUENESS, ConstraintFamily.RELATIONAL],
           [ev.event_id], [ev.provenance_id], T, {"slot": "owner_current"}),
        _q(bid, "historical", QueryFamily.HISTORICAL_STATE,
           f"Which organization owned {proj} at t={hist_t}?",
           {"attribute": "owner", "project_id": proj, "t": hist_t},
           owner_then, AnswerSchema.ENTITY_ID,
           [ConstraintFamily.TEMPORAL, ConstraintFamily.TRANSITION],
           [ev.event_id], [f"{world.world_id}:prov:init_own"], hist_t, {"slot": "owner_historical"}),
        _q(bid, "transition", QueryFamily.TRANSITION,
           f"When did ownership of {proj} transfer?",
           {"attribute": "ownership_transfer", "project_id": proj},
           transition, AnswerSchema.TRANSITION_TUPLE,
           [ConstraintFamily.TRANSITION, ConstraintFamily.TEMPORAL],
           [ev.event_id], [ev.provenance_id], transfer_t, {"slot": "owner_transition"}),
        _q(bid, "multihop", QueryFamily.MULTI_HOP,
           f"Does the manager of {proj} work for the owning organization at t={T}?",
           {"path": ["project_manager", "employer", "owner"], "project_id": proj, "t": T},
           mgr_org == owner_now, AnswerSchema.BOOLEAN,
           [ConstraintFamily.MULTI_HOP, ConstraintFamily.RELATIONAL],
           [ev.event_id], [ev.provenance_id], T,
           {"slot": "owner_mgr_align", "manager_id": manager, "manager_org": mgr_org, "owner": owner_now}),
        _q(bid, "provenance", QueryFamily.PROVENANCE,
           f"Which provenance supports current ownership of {proj}?",
           {"attribute": "owner", "project_id": proj, "t": T},
           ev.provenance_id, AnswerSchema.PROVENANCE_ID,
           [ConstraintFamily.PROVENANCE],
           [ev.event_id], [ev.provenance_id], T, {"slot": "owner_provenance", "fact_value": owner_now}),
        _q(bid, "conflict_validity", QueryFamily.CONFLICT_VALIDITY,
           f"During the unresolved priority conflict on {proj}, was a definitive current priority asserted as gold?",
           {"subject": proj, "attribute": "priority", "window": [m["conflict_intro_t"], m["conflict_resolve_t"] - 1]},
           False, AnswerSchema.BOOLEAN,
           [ConstraintFamily.CONTRADICTION],
           [next(e.event_id for e in world.events if e.t == m["conflict_intro_t"])],
           [next(e.provenance_id for e in world.events if e.t == m["conflict_intro_t"])],
           m["conflict_intro_t"], {"slot": "conflict_no_silent_resolution"}),
    ]
    return QueryBundle(bid, world.world_id, [proj, m["ceo_org"], m["other_org"]], queries,
                       f"Ownership transfer for {proj}")


def _document_bundle(world: GeneratedWorld, bi: int) -> QueryBundle:
    m = world.meta
    T = world.T
    bid = f"{world.world_id}:b:doc:{bi}"
    base = m["base_doc"]
    rev_t = m["doc_revision_t"]
    final = world.final
    canon = final.canonical_doc(base)
    assert canon is not None
    hist = world.states[rev_t - 1].canonical_doc(base)
    assert hist is not None
    rev_ev = next(e for e in world.events if e.t == rev_t)
    create_ev = next(e for e in world.events if e.event_type.value == "document_creation")
    approve_ev = next(
        e for e in world.events
        if e.event_type.value == "document_approval" and e.payload.get("doc_id") == canon.doc_id
    )
    transition = {"from_version": hist.version, "to_version": canon.version, "t": rev_t, "base_doc_id": base}
    queries = [
        _q(bid, "current", QueryFamily.CURRENT_STATE,
           f"What is the canonical document version for {base} at t={T}?",
           {"attribute": "canonical_version", "base_doc_id": base, "t": T},
           canon.version, AnswerSchema.SCALAR,
           [ConstraintFamily.UNIQUENESS],
           [rev_ev.event_id], [canon.provenance_id], T, {"slot": "doc_version"}),
        _q(bid, "historical", QueryFamily.HISTORICAL_STATE,
           f"What was the canonical version of {base} at t={rev_t - 1}?",
           {"attribute": "canonical_version", "base_doc_id": base, "t": rev_t - 1},
           hist.version, AnswerSchema.SCALAR,
           [ConstraintFamily.TEMPORAL, ConstraintFamily.TRANSITION],
           [create_ev.event_id], [hist.provenance_id], rev_t - 1, {"slot": "doc_hist_version"}),
        _q(bid, "transition", QueryFamily.TRANSITION,
           f"When was {base} revised from v1 to v2?",
           {"attribute": "document_revision", "base_doc_id": base},
           transition, AnswerSchema.TRANSITION_TUPLE,
           [ConstraintFamily.TRANSITION, ConstraintFamily.TEMPORAL],
           [rev_ev.event_id], [rev_ev.provenance_id], rev_t, {"slot": "doc_transition"}),
        _q(bid, "multihop", QueryFamily.MULTI_HOP,
           f"Who approved the canonical version of {base}, and for which project?",
           {"path": ["canonical_doc", "approved_by", "project"], "base_doc_id": base},
           {"approver": canon.approved_by, "project_id": canon.project_id},
           AnswerSchema.ENTITY_PAIR,
           [ConstraintFamily.MULTI_HOP, ConstraintFamily.RELATIONAL],
           [approve_ev.event_id], [approve_ev.provenance_id], T,
           {"slot": "doc_approve_project"}),
        _q(bid, "provenance", QueryFamily.PROVENANCE,
           f"Which provenance created the current canonical version of {base}?",
           {"attribute": "canonical_doc", "base_doc_id": base},
           canon.provenance_id, AnswerSchema.PROVENANCE_ID,
           [ConstraintFamily.PROVENANCE],
           [rev_ev.event_id], [canon.provenance_id], T,
           {"slot": "doc_provenance", "fact_value": canon.version}),
        _q(bid, "temporal_order", QueryFamily.TEMPORAL_ORDER,
           f"Is revision of {base} after creation?",
           {"before_event": create_ev.event_id, "after_event": rev_ev.event_id},
           True, AnswerSchema.BOOLEAN,
           [ConstraintFamily.TEMPORAL],
           [create_ev.event_id, rev_ev.event_id],
           [create_ev.provenance_id, rev_ev.provenance_id], None,
           {"slot": "doc_order", "t_before": create_ev.t, "t_after": rev_t}),
    ]
    return QueryBundle(bid, world.world_id, [base, m["focal_project"]], queries,
                       f"Document versioning for {base}")


def _employment_bundle(world: GeneratedWorld, bi: int) -> QueryBundle:
    m = world.meta
    T = world.T
    bid = f"{world.world_id}:b:emp:{bi}"
    p0, org_a = m["ceo0"], m["ceo_org"]
    leave_ev = next(
        e for e in world.events
        if e.event_type.value == "person_leaves_org" and e.payload.get("person_id") == p0
    )
    leave_t = leave_ev.t
    hist_t = leave_t - 1
    final = world.final
    hist = world.states[hist_t]
    join_ev = next(
        e for e in world.events
        if e.event_type.value == "person_joins_org" and e.payload.get("person_id") == p0
    )
    queries = [
        _q(bid, "current", QueryFamily.CURRENT_STATE,
           f"Is {p0} employed by {org_a} at t={T}?",
           {"attribute": "employed", "person_id": p0, "org_id": org_a, "t": T},
           final.employer_of(p0) == org_a, AnswerSchema.BOOLEAN,
           [ConstraintFamily.RELATIONAL],
           [leave_ev.event_id], [leave_ev.provenance_id], T, {"slot": "emp_current"}),
        _q(bid, "historical", QueryFamily.HISTORICAL_STATE,
           f"Was {p0} employed by {org_a} at t={hist_t}?",
           {"attribute": "employed", "person_id": p0, "org_id": org_a, "t": hist_t},
           hist.employer_of(p0) == org_a, AnswerSchema.BOOLEAN,
           [ConstraintFamily.TEMPORAL, ConstraintFamily.TRANSITION],
           [join_ev.event_id], [join_ev.provenance_id], hist_t, {"slot": "emp_historical"}),
        _q(bid, "transition", QueryFamily.TRANSITION,
           f"When did {p0} leave {org_a}?",
           {"attribute": "leave", "person_id": p0, "org_id": org_a},
           {"person_id": p0, "org_id": org_a, "t": leave_t, "action": "leave"},
           AnswerSchema.TRANSITION_TUPLE,
           [ConstraintFamily.TRANSITION, ConstraintFamily.TEMPORAL],
           [leave_ev.event_id], [leave_ev.provenance_id], leave_t, {"slot": "emp_transition"}),
        _q(bid, "multihop", QueryFamily.MULTI_HOP,
           f"Can {p0} hold an exclusive role at {org_a} at t={T} without employment?",
           {"person_id": p0, "org_id": org_a, "t": T},
           False, AnswerSchema.BOOLEAN,
           [ConstraintFamily.MULTI_HOP, ConstraintFamily.RELATIONAL],
           [leave_ev.event_id], [leave_ev.provenance_id], T, {"slot": "emp_role_compat"}),
        _q(bid, "provenance", QueryFamily.PROVENANCE,
           f"Which provenance records {p0} leaving {org_a}?",
           {"attribute": "leave", "person_id": p0},
           leave_ev.provenance_id, AnswerSchema.PROVENANCE_ID,
           [ConstraintFamily.PROVENANCE],
           [leave_ev.event_id], [leave_ev.provenance_id], leave_t,
           {"slot": "emp_provenance", "fact_value": leave_t}),
        _q(bid, "contradiction", QueryFamily.CONTRADICTION,
           f"Can {p0} be both currently employed and not employed by {org_a} at t={T}?",
           {"person_id": p0, "org_id": org_a, "t": T},
           False, AnswerSchema.BOOLEAN,
           [ConstraintFamily.CONTRADICTION],
           [leave_ev.event_id], [leave_ev.provenance_id], T, {"slot": "emp_contradiction"}),
    ]
    return QueryBundle(bid, world.world_id, [p0, org_a], queries, f"Employment exit for {p0}")


def _conflict_bundle(world: GeneratedWorld, bi: int) -> QueryBundle:
    m = world.meta
    bid = f"{world.world_id}:b:conf:{bi}"
    cid = m["conflict_id"]
    intro_t, res_t = m["conflict_intro_t"], m["conflict_resolve_t"]
    intro = next(e for e in world.events if e.t == intro_t)
    reso = next(e for e in world.events if e.t == res_t)
    mid_t = intro_t
    queries = [
        _q(bid, "current", QueryFamily.CURRENT_STATE,
           f"Is conflict {cid} resolved at t={world.T}?",
           {"attribute": "conflict_resolved", "conflict_id": cid, "t": world.T},
           True, AnswerSchema.BOOLEAN,
           [ConstraintFamily.CONTRADICTION],
           [reso.event_id], [reso.provenance_id], world.T, {"slot": "conf_resolved"}),
        _q(bid, "historical", QueryFamily.HISTORICAL_STATE,
           f"Was conflict {cid} unresolved at t={mid_t}?",
           {"attribute": "conflict_unresolved", "conflict_id": cid, "t": mid_t},
           True, AnswerSchema.BOOLEAN,
           [ConstraintFamily.TEMPORAL, ConstraintFamily.CONTRADICTION],
           [intro.event_id], [intro.provenance_id], mid_t, {"slot": "conf_unresolved_hist"}),
        _q(bid, "conflict_validity", QueryFamily.CONFLICT_VALIDITY,
           f"What is the resolved priority value for conflict {cid}?",
           {"conflict_id": cid, "attribute": "resolved_value"},
           "P0", AnswerSchema.SCALAR,
           [ConstraintFamily.CONTRADICTION, ConstraintFamily.TRANSITION],
           [reso.event_id], [reso.provenance_id], res_t, {"slot": "conf_value"}),
        _q(bid, "transition", QueryFamily.TRANSITION,
           f"When was conflict {cid} resolved?",
           {"conflict_id": cid, "attribute": "resolution_time"},
           {"conflict_id": cid, "t": res_t, "resolved_value": "P0"},
           AnswerSchema.TRANSITION_TUPLE,
           [ConstraintFamily.TRANSITION, ConstraintFamily.TEMPORAL],
           [reso.event_id], [reso.provenance_id], res_t, {"slot": "conf_transition"}),
        _q(bid, "multihop", QueryFamily.MULTI_HOP,
           f"Does the conflict subject equal focal project {m['focal_project']}?",
           {"conflict_id": cid, "expected_subject": m["focal_project"]},
           True, AnswerSchema.BOOLEAN,
           [ConstraintFamily.MULTI_HOP, ConstraintFamily.RELATIONAL],
           [intro.event_id], [intro.provenance_id], intro_t, {"slot": "conf_subject"}),
        _q(bid, "provenance", QueryFamily.PROVENANCE,
           f"Which provenance resolved conflict {cid}?",
           {"conflict_id": cid},
           reso.provenance_id, AnswerSchema.PROVENANCE_ID,
           [ConstraintFamily.PROVENANCE],
           [reso.event_id], [reso.provenance_id], res_t,
           {"slot": "conf_provenance", "fact_value": "P0"}),
        _q(bid, "counterfactual", QueryFamily.COUNTERFACTUAL,
           f"Would asserting unresolved conflict {cid} at t={world.T} contradict history?",
           {"claim": "unresolved", "conflict_id": cid, "t": world.T},
           True, AnswerSchema.BOOLEAN,
           [ConstraintFamily.CONTRADICTION],
           [reso.event_id], [reso.provenance_id], world.T, {"slot": "conf_counterfactual"}),
    ]
    return QueryBundle(bid, world.world_id, [cid, m["focal_project"]], queries,
                       f"Conflict lifecycle for {cid}")


def generate_bundles(world: GeneratedWorld, min_bundles: int = 5) -> list[QueryBundle]:
    builders = [
        _ceo_bundle,
        _ownership_bundle,
        _document_bundle,
        _employment_bundle,
        _conflict_bundle,
    ]
    bundles = [builder(world, i) for i, builder in enumerate(builders)]
    extras = [_ownership_bundle, _document_bundle, _ceo_bundle]
    while len(bundles) < min_bundles:
        bi = len(bundles)
        bundles.append(extras[bi % len(extras)](world, bi))
    return bundles
