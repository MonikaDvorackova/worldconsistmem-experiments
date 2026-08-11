"""Deterministic evolving world state and event application."""

from __future__ import annotations

import copy
from typing import Any, Optional

from .models import (
    ConflictClaim,
    Document,
    Employment,
    Event,
    EventType,
    Interval,
    Location,
    Organization,
    Person,
    Project,
    ProjectOwnership,
    Relationship,
    RoleHolder,
    TemporaryMark,
)


class InvalidEventError(ValueError):
    """Raised when an event violates preconditions."""


class WorldState:
    """Materialized world snapshot at a discrete revision index."""

    def __init__(self, t: int = 0):
        self.t = t
        self.persons: dict[str, Person] = {}
        self.orgs: dict[str, Organization] = {}
        self.projects: dict[str, Project] = {}
        self.documents: dict[str, Document] = {}
        self.locations: dict[str, Location] = {}
        self.employments: list[Employment] = []
        self.roles: list[RoleHolder] = []
        self.ownerships: list[ProjectOwnership] = []
        self.relationships: list[Relationship] = []
        self.conflicts: list[ConflictClaim] = []
        self.temporary_marks: list[TemporaryMark] = []
        self.doc_versions: dict[str, list[Document]] = {}  # base_doc_id -> versions

    def clone(self) -> "WorldState":
        return copy.deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "t": self.t,
            "persons": {k: v.to_dict() for k, v in self.persons.items()},
            "orgs": {k: v.to_dict() for k, v in self.orgs.items()},
            "projects": {k: v.to_dict() for k, v in self.projects.items()},
            "documents": {k: v.to_dict() for k, v in self.documents.items()},
            "locations": {k: v.to_dict() for k, v in self.locations.items()},
            "employments": [e.to_dict() for e in self.employments],
            "roles": [r.to_dict() for r in self.roles],
            "ownerships": [o.to_dict() for o in self.ownerships],
            "relationships": [r.to_dict() for r in self.relationships],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "temporary_marks": [m.to_dict() for m in self.temporary_marks],
            "doc_versions": {
                k: [d.to_dict() for d in vs] for k, vs in self.doc_versions.items()
            },
        }

    # --- queries over state ---

    def active_employments(self, t: Optional[int] = None) -> list[Employment]:
        tt = self.t if t is None else t
        return [e for e in self.employments if e.interval.contains(tt)]

    def employer_of(self, person_id: str, t: Optional[int] = None) -> Optional[str]:
        for e in self.active_employments(t):
            if e.person_id == person_id:
                return e.org_id
        return None

    def role_holder(
        self, org_id: str, role: str, t: Optional[int] = None
    ) -> Optional[RoleHolder]:
        tt = self.t if t is None else t
        holders = [
            r
            for r in self.roles
            if r.org_id == org_id and r.role == role and r.interval.contains(tt)
        ]
        if not holders:
            return None
        return holders[0]

    def owner_of(self, project_id: str, t: Optional[int] = None) -> Optional[str]:
        tt = self.t if t is None else t
        for o in self.ownerships:
            if o.project_id == project_id and o.interval.contains(tt):
                return o.org_id
        return None

    def canonical_doc(self, base_doc_id: str) -> Optional[Document]:
        versions = self.doc_versions.get(base_doc_id, [])
        for d in versions:
            if d.canonical:
                return d
        return self.documents.get(base_doc_id)

    def active_relationships(
        self, rel_type: Optional[str] = None, t: Optional[int] = None
    ) -> list[Relationship]:
        tt = self.t if t is None else t
        out = [r for r in self.relationships if r.interval.contains(tt)]
        if rel_type is not None:
            out = [r for r in out if r.rel_type == rel_type]
        return out

    def unresolved_conflicts(self, t: Optional[int] = None) -> list[ConflictClaim]:
        tt = self.t if t is None else t
        return [
            c
            for c in self.conflicts
            if (not c.resolved) and c.interval.contains(tt)
        ]

    def check_no_exclusive_role_collisions(self, t: Optional[int] = None) -> list[str]:
        tt = self.t if t is None else t
        errors: list[str] = []
        seen: dict[tuple[str, str], str] = {}
        for r in self.roles:
            if not r.exclusive or not r.interval.contains(tt):
                continue
            key = (r.org_id, r.role)
            if key in seen and seen[key] != r.person_id:
                errors.append(
                    f"exclusive role collision at t={tt}: {key} held by "
                    f"{seen[key]} and {r.person_id}"
                )
            seen[key] = r.person_id
        return errors

    def check_single_owner(self, t: Optional[int] = None) -> list[str]:
        tt = self.t if t is None else t
        errors: list[str] = []
        owners: dict[str, list[str]] = {}
        for o in self.ownerships:
            if o.interval.contains(tt):
                owners.setdefault(o.project_id, []).append(o.org_id)
        for pid, orgs in owners.items():
            if len(set(orgs)) > 1:
                errors.append(f"multiple owners for {pid} at t={tt}: {orgs}")
        return errors

    def check_single_canonical_doc(self) -> list[str]:
        errors: list[str] = []
        for base, versions in self.doc_versions.items():
            cans = [d for d in versions if d.canonical]
            if len(cans) > 1:
                errors.append(f"multiple canonical versions for {base}")
            if versions and len(cans) == 0:
                errors.append(f"no canonical version for {base}")
        return errors


def _close_interval(interval: Interval, end_t: int) -> None:
    if interval.end is not None:
        raise InvalidEventError(f"interval already closed: {interval}")
    if end_t < interval.start:
        raise InvalidEventError(
            f"cannot close interval starting {interval.start} at {end_t}"
        )
    interval.end = end_t


def apply_event(state: WorldState, event: Event) -> WorldState:
    """Apply event to a clone of state; reject invalid transitions."""
    if event.t != state.t + 1:
        raise InvalidEventError(
            f"event t={event.t} does not follow state t={state.t}"
        )

    s = state.clone()
    s.t = event.t
    et = event.event_type
    p = event.payload
    prov = event.provenance_id

    if et == EventType.PERSON_JOINS_ORG:
        person_id, org_id = p["person_id"], p["org_id"]
        if person_id not in s.persons or org_id not in s.orgs:
            raise InvalidEventError("join: unknown person or org")
        # Employment intervals are half-open [start, end); check prior tick.
        if s.employer_of(person_id, event.t - 1) is not None:
            raise InvalidEventError(f"{person_id} already employed at join")
        s.employments.append(
            Employment(person_id, org_id, Interval(event.t), prov)
        )

    elif et == EventType.PERSON_LEAVES_ORG:
        person_id, org_id = p["person_id"], p["org_id"]
        emp = next(
            (
                e
                for e in s.employments
                if e.person_id == person_id
                and e.org_id == org_id
                and e.interval.contains(event.t - 1)
            ),
            None,
        )
        if emp is None:
            raise InvalidEventError(f"leave: {person_id} not in {org_id}")
        _close_interval(emp.interval, event.t)
        for r in s.roles:
            if (
                r.person_id == person_id
                and r.org_id == org_id
                and r.interval.contains(event.t - 1)
            ):
                _close_interval(r.interval, event.t)

    elif et == EventType.ROLE_ASSIGNMENT:
        person_id, org_id, role = p["person_id"], p["org_id"], p["role"]
        exclusive = bool(p.get("exclusive", True))
        # Employment may have started at a prior tick; also allow start==event.t
        # after append in a previous event (join then later role).
        emp_now = s.employer_of(person_id, event.t - 1)
        emp_open = next(
            (
                e.org_id
                for e in s.employments
                if e.person_id == person_id and e.interval.start <= event.t and (
                    e.interval.end is None or event.t < e.interval.end
                )
            ),
            None,
        )
        if emp_now != org_id and emp_open != org_id:
            raise InvalidEventError("role_assignment: person not employed by org")
        if exclusive:
            existing = s.role_holder(org_id, role, event.t - 1)
            if existing is not None:
                raise InvalidEventError(
                    f"role_assignment: exclusive {role} already held; use replacement"
                )
        s.roles.append(
            RoleHolder(person_id, org_id, role, exclusive, Interval(event.t), prov)
        )

    elif et == EventType.ROLE_REPLACEMENT:
        org_id, role = p["org_id"], p["role"]
        new_person = p["new_person_id"]
        old = s.role_holder(org_id, role, event.t - 1)
        if old is None:
            raise InvalidEventError("role_replacement: no current holder")
        emp_open = next(
            (
                e.org_id
                for e in s.employments
                if e.person_id == new_person and e.interval.start <= event.t and (
                    e.interval.end is None or event.t < e.interval.end
                )
            ),
            None,
        )
        if emp_open != org_id:
            raise InvalidEventError("role_replacement: new person not in org")
        _close_interval(old.interval, event.t)
        s.roles.append(
            RoleHolder(
                new_person,
                org_id,
                role,
                old.exclusive,
                Interval(event.t),
                prov,
            )
        )

    elif et == EventType.PROJECT_OWNERSHIP_TRANSFER:
        project_id, new_org = p["project_id"], p["new_org_id"]
        if project_id not in s.projects or new_org not in s.orgs:
            raise InvalidEventError("ownership transfer: unknown project/org")
        cur = next(
            (
                o
                for o in s.ownerships
                if o.project_id == project_id and o.interval.contains(event.t - 1)
            ),
            None,
        )
        if cur is None:
            raise InvalidEventError("ownership transfer: no current owner")
        if cur.org_id == new_org:
            raise InvalidEventError("ownership transfer: same owner")
        _close_interval(cur.interval, event.t)
        s.ownerships.append(
            ProjectOwnership(project_id, new_org, Interval(event.t), prov)
        )

    elif et == EventType.PROJECT_STATUS_CHANGE:
        project_id, new_status = p["project_id"], p["status"]
        if project_id not in s.projects:
            raise InvalidEventError("status change: unknown project")
        s.projects[project_id].status = new_status
        if "manager_id" in p:
            s.projects[project_id].manager_id = p["manager_id"]

    elif et == EventType.DOCUMENT_CREATION:
        doc = Document(
            doc_id=p["doc_id"],
            title=p["title"],
            project_id=p["project_id"],
            version=1,
            author_id=p["author_id"],
            approved=False,
            canonical=True,
            provenance_id=prov,
        )
        if p["project_id"] not in s.projects:
            raise InvalidEventError("doc create: unknown project")
        if p["author_id"] not in s.persons:
            raise InvalidEventError("doc create: unknown author")
        base = p.get("base_doc_id", p["doc_id"])
        s.documents[doc.doc_id] = doc
        s.doc_versions.setdefault(base, []).append(doc)

    elif et == EventType.DOCUMENT_REVISION:
        base = p["base_doc_id"]
        versions = s.doc_versions.get(base, [])
        if not versions:
            raise InvalidEventError("revision: no prior version")
        prev = next((d for d in versions if d.canonical), versions[-1])
        if p.get("expected_prev_version") is not None:
            if prev.version != p["expected_prev_version"]:
                raise InvalidEventError("revision: version mismatch")
        prev.canonical = False
        new_doc = Document(
            doc_id=p["doc_id"],
            title=prev.title,
            project_id=prev.project_id,
            version=prev.version + 1,
            author_id=p["author_id"],
            approved=False,
            canonical=True,
            provenance_id=prov,
        )
        s.documents[new_doc.doc_id] = new_doc
        versions.append(new_doc)

    elif et == EventType.DOCUMENT_APPROVAL:
        doc_id = p["doc_id"]
        approver = p["approver_id"]
        if doc_id not in s.documents:
            raise InvalidEventError("approval: unknown document")
        doc = s.documents[doc_id]
        if not doc.canonical:
            raise InvalidEventError("approval: document not canonical")
        if approver not in s.persons:
            raise InvalidEventError("approval: unknown approver")
        doc.approved = True
        doc.approved_by = approver

    elif et == EventType.LOCATION_CHANGE:
        person_id, loc_id = p["person_id"], p["location_id"]
        if person_id not in s.persons or loc_id not in s.locations:
            raise InvalidEventError("location change: unknown ids")
        s.persons[person_id].location_id = loc_id

    elif et == EventType.RELATIONSHIP_CREATION:
        rel = Relationship(
            rel_id=p["rel_id"],
            rel_type=p["rel_type"],
            source_id=p["source_id"],
            target_id=p["target_id"],
            interval=Interval(event.t),
            provenance_id=prov,
        )
        s.relationships.append(rel)

    elif et == EventType.RELATIONSHIP_TERMINATION:
        rel_id = p["rel_id"]
        rel = next((r for r in s.relationships if r.rel_id == rel_id), None)
        if rel is None or not rel.interval.contains(event.t - 1):
            raise InvalidEventError("relationship termination: not active")
        _close_interval(rel.interval, event.t)

    elif et == EventType.CONFLICT_INTRODUCTION:
        c = ConflictClaim(
            conflict_id=p["conflict_id"],
            subject=p["subject"],
            attribute=p["attribute"],
            value_a=p["value_a"],
            value_b=p["value_b"],
            interval=Interval(event.t),
            resolved=False,
            resolved_value=None,
            provenance_id=prov,
        )
        s.conflicts.append(c)

    elif et == EventType.CONFLICT_RESOLUTION:
        cid = p["conflict_id"]
        c = next((x for x in s.conflicts if x.conflict_id == cid), None)
        if c is None or c.resolved:
            raise InvalidEventError("conflict resolution: missing or already resolved")
        c.resolved = True
        c.resolved_value = p["resolved_value"]
        c.resolution_provenance_id = prov
        _close_interval(c.interval, event.t)

    elif et == EventType.TEMPORARY_STATE:
        mark = TemporaryMark(
            mark_id=p["mark_id"],
            entity_id=p["entity_id"],
            attribute=p["attribute"],
            temporary_value=p["temporary_value"],
            original_value=p["original_value"],
            interval=Interval(event.t),
            reverted=False,
            provenance_id=prov,
        )
        # apply temporary value to project status or person location
        if mark.attribute == "project_status":
            if mark.entity_id not in s.projects:
                raise InvalidEventError("temporary: unknown project")
            if s.projects[mark.entity_id].status != mark.original_value:
                raise InvalidEventError("temporary: original_value mismatch")
            s.projects[mark.entity_id].status = mark.temporary_value
        elif mark.attribute == "location":
            if mark.entity_id not in s.persons:
                raise InvalidEventError("temporary: unknown person")
            if s.persons[mark.entity_id].location_id != mark.original_value:
                raise InvalidEventError("temporary: original location mismatch")
            s.persons[mark.entity_id].location_id = mark.temporary_value
        else:
            raise InvalidEventError(f"temporary: unsupported attribute {mark.attribute}")
        s.temporary_marks.append(mark)

    elif et == EventType.REVERSION:
        mid = p["mark_id"]
        mark = next((m for m in s.temporary_marks if m.mark_id == mid), None)
        if mark is None or mark.reverted:
            raise InvalidEventError("reversion: missing or already reverted")
        if mark.attribute == "project_status":
            s.projects[mark.entity_id].status = mark.original_value
        elif mark.attribute == "location":
            s.persons[mark.entity_id].location_id = mark.original_value
        mark.reverted = True
        mark.reversion_provenance_id = prov
        _close_interval(mark.interval, event.t)

    else:
        raise InvalidEventError(f"unknown event type {et}")

    # post-apply integrity
    for err in s.check_no_exclusive_role_collisions(event.t):
        raise InvalidEventError(err)
    for err in s.check_single_owner(event.t):
        raise InvalidEventError(err)
    for err in s.check_single_canonical_doc():
        raise InvalidEventError(err)

    return s


def replay(initial: WorldState, events: list[Event]) -> list[WorldState]:
    """Replay event log from W0; returns [W0, W1, ..., WT]."""
    states = [initial.clone()]
    cur = initial.clone()
    for ev in events:
        cur = apply_event(cur, ev)
        states.append(cur)
    return states
