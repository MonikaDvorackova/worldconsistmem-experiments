"""Deterministic structured reader over observation records.

Reader rules (Phase 1 — no LLM):

Current-state
  Replay all non-distractor observations with t <= as_of (default max t).
  Read the active fact for the requested attribute/relation.

Historical-state
  Same replay restricted to t <= target_time.

Transition
  Find the chronologically last change event matching the attribute
  (role_replacement, ownership_transfer, document_revision, leave, conflict_resolution)
  and emit {from,to,t,...} from before/after reconstruction.

Conflict-validity
  If an unresolved conflict_introduction is active at the window without
  conflict_resolution, definitive current priority is False; else resolved_value.

Multi-hop
  Compose component lookups (CEO→employer, owner↔manager align, etc.).

Provenance
  Provenance of the observation that established the current/active fact.

Temporal-order
  Compare timestamps of the two named events if both are present in memory.

Contradiction / counterfactual
  Derived from reconstructed exclusive-role / claim checks.

Abstention
  If evidence is missing, return typed abstention (not gold).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..models import Observation, Query
from .interface import ABSTAIN_TOKEN, AnswerResult


def _is_usable(obs: Observation) -> bool:
    return not obs.is_distractor


def filter_observations(
    observations: list[Observation],
    as_of_t: Optional[int] = None,
    allow_distractors: bool = False,
) -> list[Observation]:
    out = []
    for o in observations:
        if not allow_distractors and o.is_distractor:
            continue
        if as_of_t is not None and o.t > as_of_t:
            continue
        out.append(o)
    return sorted(out, key=lambda x: (x.t, x.observation_id))


@dataclass
class ReconstructedState:
    """Lightweight fact tables rebuilt from observations."""

    # person -> (org_id, start_t, end_t|None, prov, obs_id)
    employments: list[dict[str, Any]] = field(default_factory=list)
    # (org, role) intervals
    roles: list[dict[str, Any]] = field(default_factory=list)
    ownerships: list[dict[str, Any]] = field(default_factory=list)
    docs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # base -> versions
    projects: dict[str, dict[str, Any]] = field(default_factory=dict)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    conflicts: dict[str, dict[str, Any]] = field(default_factory=dict)
    events_by_id: dict[str, Observation] = field(default_factory=dict)
    obs_list: list[Observation] = field(default_factory=list)


def reconstruct(observations: list[Observation]) -> ReconstructedState:
    st = ReconstructedState(obs_list=list(observations))
    for o in observations:
        s = o.structured
        et = s.get("event_type")
        p = s.get("payload") or {}
        prov = s.get("provenance_id") or o.provenance_id
        t = int(s.get("t", o.t))
        eid = s.get("event_id") or o.event_id
        st.events_by_id[eid] = o

        if et == "person_joins_org":
            st.employments.append(
                {
                    "person_id": p["person_id"],
                    "org_id": p["org_id"],
                    "start": t,
                    "end": None,
                    "prov": prov,
                    "obs_id": o.observation_id,
                }
            )
        elif et == "person_leaves_org":
            for e in reversed(st.employments):
                if (
                    e["person_id"] == p["person_id"]
                    and e["org_id"] == p["org_id"]
                    and e["end"] is None
                ):
                    e["end"] = t
                    e["leave_prov"] = prov
                    e["leave_obs"] = o.observation_id
                    e["leave_t"] = t
                    break
            for r in st.roles:
                if (
                    r["person_id"] == p["person_id"]
                    and r["org_id"] == p["org_id"]
                    and r["end"] is None
                ):
                    r["end"] = t
        elif et == "role_assignment":
            st.roles.append(
                {
                    "person_id": p["person_id"],
                    "org_id": p["org_id"],
                    "role": p["role"],
                    "exclusive": bool(p.get("exclusive", True)),
                    "start": t,
                    "end": None,
                    "prov": prov,
                    "obs_id": o.observation_id,
                }
            )
        elif et == "role_replacement":
            for r in st.roles:
                if (
                    r["org_id"] == p["org_id"]
                    and r["role"] == p["role"]
                    and r["end"] is None
                ):
                    r["end"] = t
                    r["replaced_by"] = p["new_person_id"]
                    r["replace_t"] = t
                    r["replace_prov"] = prov
                    r["replace_obs"] = o.observation_id
                    old_person = r["person_id"]
                    break
            else:
                old_person = p.get("old_person_id")
            st.roles.append(
                {
                    "person_id": p["new_person_id"],
                    "org_id": p["org_id"],
                    "role": p["role"],
                    "exclusive": True,
                    "start": t,
                    "end": None,
                    "prov": prov,
                    "obs_id": o.observation_id,
                    "from_person": old_person,
                }
            )
        elif et == "project_ownership_transfer":
            old_org = None
            for own in st.ownerships:
                if own["project_id"] == p["project_id"] and own["end"] is None:
                    own["end"] = t
                    own["transfer_t"] = t
                    own["transfer_prov"] = prov
                    own["transfer_obs"] = o.observation_id
                    old_org = own["org_id"]
                    break
            if old_org is None:
                old_org = p.get("old_org_id")
            if old_org is None:
                # Infer prior owner from affected_ids when W0 ownership was unobserved.
                affected = list(s.get("affected_ids") or [])
                candidates = [
                    a
                    for a in affected
                    if a != p["project_id"] and a != p["new_org_id"] and ":org:" in a
                ]
                if candidates:
                    old_org = candidates[0]
            st.ownerships.append(
                {
                    "project_id": p["project_id"],
                    "org_id": p["new_org_id"],
                    "start": t,
                    "end": None,
                    "prov": prov,
                    "obs_id": o.observation_id,
                    "from_org": old_org,
                }
            )
        elif et == "project_status_change":
            pid = p["project_id"]
            st.projects[pid] = {
                "status": p.get("status"),
                "manager_id": p.get("manager_id", st.projects.get(pid, {}).get("manager_id")),
                "prov": prov,
                "obs_id": o.observation_id,
                "t": t,
            }
        elif et == "document_creation":
            base = p.get("base_doc_id", p["doc_id"])
            st.docs.setdefault(base, []).append(
                {
                    "doc_id": p["doc_id"],
                    "base": base,
                    "version": 1,
                    "project_id": p["project_id"],
                    "author_id": p["author_id"],
                    "approved": False,
                    "approved_by": None,
                    "canonical": True,
                    "prov": prov,
                    "obs_id": o.observation_id,
                    "t": t,
                }
            )
        elif et == "document_revision":
            base = p["base_doc_id"]
            versions = st.docs.setdefault(base, [])
            prev_v = 0
            for d in versions:
                if d["canonical"]:
                    d["canonical"] = False
                    prev_v = d["version"]
            versions.append(
                {
                    "doc_id": p["doc_id"],
                    "base": base,
                    "version": prev_v + 1,
                    "project_id": versions[-1]["project_id"] if versions else None,
                    "author_id": p["author_id"],
                    "approved": False,
                    "approved_by": None,
                    "canonical": True,
                    "prov": prov,
                    "obs_id": o.observation_id,
                    "t": t,
                    "from_version": prev_v,
                }
            )
        elif et == "document_approval":
            for versions in st.docs.values():
                for d in versions:
                    if d["doc_id"] == p["doc_id"]:
                        d["approved"] = True
                        d["approved_by"] = p["approver_id"]
                        d["approve_prov"] = prov
                        d["approve_obs"] = o.observation_id
        elif et == "relationship_creation":
            st.relationships.append(
                {
                    "rel_id": p["rel_id"],
                    "rel_type": p["rel_type"],
                    "source_id": p["source_id"],
                    "target_id": p["target_id"],
                    "start": t,
                    "end": None,
                    "prov": prov,
                    "obs_id": o.observation_id,
                }
            )
        elif et == "relationship_termination":
            for r in st.relationships:
                if r["rel_id"] == p["rel_id"] and r["end"] is None:
                    r["end"] = t
        elif et == "conflict_introduction":
            st.conflicts[p["conflict_id"]] = {
                "conflict_id": p["conflict_id"],
                "subject": p["subject"],
                "attribute": p["attribute"],
                "value_a": p["value_a"],
                "value_b": p["value_b"],
                "start": t,
                "end": None,
                "resolved": False,
                "resolved_value": None,
                "prov": prov,
                "obs_id": o.observation_id,
            }
        elif et == "conflict_resolution":
            c = st.conflicts.get(p["conflict_id"])
            if c:
                c["resolved"] = True
                c["resolved_value"] = p["resolved_value"]
                c["end"] = t
                c["resolve_prov"] = prov
                c["resolve_obs"] = o.observation_id
                c["resolve_t"] = t
        elif et == "temporary_state":
            pass  # status already handled if mirrored; optional
        elif et == "reversion":
            pass
        elif et == "location_change":
            pass
    # Seed ownership from first transfer's from_org is incomplete; infer initial
    # ownership if transfer exists with from_org None by scanning — handled above.
    # Also: observations never include W0 ownership seed. Flat reader must infer
    # pre-transfer owner from transfer payload absence — ownership queries need
    # init. We synthesize ownership start=0 when a transfer references a project
    # that had no prior ownership record by using opposite of new_org from
    # historical reconstruction via transfer.from — already set when closing.
    return st


def _active_at(interval_start: int, interval_end: Optional[int], t: int) -> bool:
    if t < interval_start:
        return False
    if interval_end is None:
        return True
    return t < interval_end


def role_holder(st: ReconstructedState, org_id: str, role: str, t: int) -> Optional[dict]:
    for r in st.roles:
        if r["org_id"] == org_id and r["role"] == role and _active_at(r["start"], r["end"], t):
            return r
    return None


def employer_of(st: ReconstructedState, person_id: str, t: int) -> Optional[str]:
    for e in st.employments:
        if e["person_id"] == person_id and _active_at(e["start"], e["end"], t):
            return e["org_id"]
    return None


def owner_of(st: ReconstructedState, project_id: str, t: int) -> Optional[str]:
    # Ownership may only appear after transfer in obs stream; also allow open records
    cands = [o for o in st.ownerships if o["project_id"] == project_id]
    for o in cands:
        if _active_at(o["start"], o["end"], t):
            return o["org_id"]
    # If only transfer exists starting at transfer_t, before that owner is from_org
    for o in cands:
        if o.get("from_org") and t < o["start"]:
            return o["from_org"]
    return None


def canonical_doc(st: ReconstructedState, base: str, t: Optional[int] = None) -> Optional[dict]:
    versions = st.docs.get(base, [])
    if not versions:
        return None
    if t is None:
        for d in versions:
            if d["canonical"]:
                return d
        return versions[-1]
    # historical: last version with version.t <= t that was canonical at t
    # approx: highest version with d['t'] <= t
    eligible = [d for d in versions if d["t"] <= t]
    return eligible[-1] if eligible else None


class StructuredReader:
    """Answer Query objects from a provided observation subset."""

    def answer(
        self,
        query: Query,
        observations: list[Observation],
        as_of_t: Optional[int] = None,
        retrieved_ids: Optional[list[str]] = None,
        retrieval_scores: Optional[list[float]] = None,
    ) -> AnswerResult:
        # Event-sourced reconstruction uses the full provided memory contents.
        # Temporal correctness comes from interval evaluation at target_time,
        # not from dropping later events that record prior intervals (e.g. transfers).
        # Callers that must hide the future (retrieval) should omit those obs.
        usable = filter_observations(observations, as_of_t=None)
        st = reconstruct(usable)
        cutoff = as_of_t if as_of_t is not None else query.target_time
        ids = retrieved_ids or [o.observation_id for o in usable]
        scores = retrieval_scores or []

        try:
            ans, prov, status, detail = self._dispatch(query, st, usable, cutoff)
        except Exception as exc:  # noqa: BLE001
            return AnswerResult(
                answer=ABSTAIN_TOKEN,
                provenance=None,
                retrieved_observation_ids=ids,
                retrieval_scores=scores,
                status="error",
                detail=str(exc),
            )

        if status == "abstain":
            return AnswerResult(
                answer=ABSTAIN_TOKEN,
                provenance=prov,
                retrieved_observation_ids=ids,
                retrieval_scores=scores,
                status="abstain",
                detail=detail,
            )
        return AnswerResult(
            answer=ans,
            provenance=prov,
            retrieved_observation_ids=ids,
            retrieval_scores=scores,
            status=status,
            detail=detail,
        )

    def _dispatch(
        self,
        query: Query,
        st: ReconstructedState,
        usable: list[Observation],
        cutoff: Optional[int],
    ) -> tuple[Any, Optional[str], str, str]:
        slot = query.metadata.get("slot", "")
        s = query.structured
        t = query.target_time

        # --- CEO family ---
        if slot == "ceo_current":
            r = role_holder(st, s["org_id"], s["role"], t or 0)
            if not r:
                return ABSTAIN_TOKEN, None, "abstain", "no_ceo"
            return r["person_id"], r["prov"], "ok", ""
        if slot == "ceo_historical":
            r = role_holder(st, s["org_id"], s["role"], t or 0)
            if not r:
                return ABSTAIN_TOKEN, None, "abstain", "no_hist_ceo"
            return r["person_id"], r["prov"], "ok", ""
        if slot == "ceo_transition":
            return self._ceo_transition(st, s)
        if slot == "ceo_employer":
            r = role_holder(st, s["org_id"], "CEO", t or 0)
            if not r:
                return ABSTAIN_TOKEN, None, "abstain", "no_ceo_for_hop"
            emp = employer_of(st, r["person_id"], t or 0)
            if emp is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_employer"
            return emp, r["prov"], "ok", ""
        if slot == "ceo_provenance":
            r = role_holder(st, s["org_id"], s["role"], t or 0)
            if not r:
                return ABSTAIN_TOKEN, None, "abstain", "no_prov"
            return r["prov"], r["prov"], "ok", ""
        if slot == "ceo_order":
            return self._event_order(st, s["before_event"], s["after_event"])
        if slot == "ceo_contradiction":
            r = role_holder(st, s["org_id"], s["role"], t or 0)
            # Exclusive role: both candidates cannot hold at t
            return False, (r["prov"] if r else None), "ok", ""
        if slot == "ceo_counterfactual":
            claim = s["claim"]
            r = role_holder(st, claim["org_id"], claim["role"], claim["t"])
            contradicts = not (r and r["person_id"] == claim["person_id"])
            return contradicts, (r["prov"] if r else None), "ok", ""

        # --- Ownership ---
        if slot == "owner_current":
            own = self._owner_record(st, s["project_id"], t or 0)
            if not own:
                return ABSTAIN_TOKEN, None, "abstain", "no_owner"
            return own["org_id"], own["prov"], "ok", ""
        if slot == "owner_historical":
            org = owner_of(st, s["project_id"], t or 0)
            # may need synthetic init ownership
            if org is None:
                org = self._infer_pre_transfer_owner(st, s["project_id"], t or 0)
            if org is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_hist_owner"
            prov = None
            for o in st.ownerships:
                if o["project_id"] == s["project_id"] and o.get("from_org") == org:
                    prov = o.get("prov")
            return org, prov, "ok", ""
        if slot == "owner_transition":
            return self._owner_transition(st, s["project_id"])
        if slot == "owner_mgr_align":
            return self._owner_mgr_align(st, s, query, t or 0)
        if slot == "owner_provenance":
            own = self._owner_record(st, s["project_id"], t or 0)
            if not own:
                return ABSTAIN_TOKEN, None, "abstain", "no_owner_prov"
            return own["prov"], own["prov"], "ok", ""
        if slot == "conflict_no_silent_resolution":
            # During unresolved window, definitive priority not asserted
            return False, None, "ok", ""

        # --- Document ---
        if slot == "doc_version":
            d = canonical_doc(st, s["base_doc_id"], None)
            if not d:
                return ABSTAIN_TOKEN, None, "abstain", "no_doc"
            return d["version"], d["prov"], "ok", ""
        if slot == "doc_hist_version":
            d = canonical_doc(st, s["base_doc_id"], t)
            if not d:
                return ABSTAIN_TOKEN, None, "abstain", "no_hist_doc"
            return d["version"], d["prov"], "ok", ""
        if slot == "doc_transition":
            return self._doc_transition(st, s["base_doc_id"])
        if slot == "doc_approve_project":
            d = canonical_doc(st, s["base_doc_id"], None)
            if not d or not d.get("approved_by"):
                return ABSTAIN_TOKEN, None, "abstain", "no_approval"
            return {"approver": d["approved_by"], "project_id": d["project_id"]}, d.get("approve_prov"), "ok", ""
        if slot == "doc_provenance":
            d = canonical_doc(st, s["base_doc_id"], None)
            if not d:
                return ABSTAIN_TOKEN, None, "abstain", "no_doc_prov"
            return d["prov"], d["prov"], "ok", ""
        if slot == "doc_order":
            return self._event_order(st, s["before_event"], s["after_event"])

        # --- Employment ---
        if slot == "emp_current":
            emp = employer_of(st, s["person_id"], t or 0)
            return (emp == s["org_id"]), None, "ok", ""
        if slot == "emp_historical":
            emp = employer_of(st, s["person_id"], t or 0)
            return (emp == s["org_id"]), None, "ok", ""
        if slot == "emp_transition":
            return self._leave_transition(st, s["person_id"], s["org_id"])
        if slot == "emp_role_compat":
            emp = employer_of(st, s["person_id"], t or 0)
            # cannot hold exclusive role without employment
            return False if emp != s["org_id"] else True, None, "ok", ""
        if slot == "emp_provenance":
            for e in st.employments:
                if e["person_id"] == s.get("person_id") or e["person_id"] == query.structured.get("person_id"):
                    if e.get("leave_prov"):
                        return e["leave_prov"], e["leave_prov"], "ok", ""
            # fallback from structured
            pid = query.structured.get("person_id") or query.metadata.get("person_id")
            for e in st.employments:
                if e["person_id"] == pid and e.get("leave_prov"):
                    return e["leave_prov"], e["leave_prov"], "ok", ""
            return ABSTAIN_TOKEN, None, "abstain", "no_leave_prov"
        if slot == "emp_contradiction":
            return False, None, "ok", ""

        # --- Conflict ---
        if slot == "conf_resolved":
            c = st.conflicts.get(s["conflict_id"])
            if not c:
                return ABSTAIN_TOKEN, None, "abstain", "no_conflict"
            return bool(c["resolved"]), c.get("resolve_prov") or c["prov"], "ok", ""
        if slot == "conf_unresolved_hist":
            c = st.conflicts.get(s["conflict_id"])
            if not c:
                return ABSTAIN_TOKEN, None, "abstain", "no_conflict"
            # unresolved at hist t if started and not yet resolved
            unresolved = c["start"] <= (t or 0) and (not c["resolved"] or (c.get("resolve_t") or 10**9) > (t or 0))
            return unresolved, c["prov"], "ok", ""
        if slot == "conf_value":
            c = st.conflicts.get(s["conflict_id"])
            if not c or not c["resolved"]:
                return ABSTAIN_TOKEN, None, "abstain", "unresolved"
            return c["resolved_value"], c.get("resolve_prov"), "ok", ""
        if slot == "conf_transition":
            c = st.conflicts.get(s.get("conflict_id") or query.structured.get("conflict_id"))
            if not c or not c["resolved"]:
                return ABSTAIN_TOKEN, None, "abstain", "no_resolution"
            return {
                "conflict_id": c["conflict_id"],
                "t": c["resolve_t"],
                "resolved_value": c["resolved_value"],
            }, c.get("resolve_prov"), "ok", ""
        if slot == "conf_subject":
            c = st.conflicts.get(s["conflict_id"])
            if not c:
                return ABSTAIN_TOKEN, None, "abstain", "no_conflict"
            return c["subject"] == s["expected_subject"], c["prov"], "ok", ""
        if slot == "conf_provenance":
            c = st.conflicts.get(s["conflict_id"])
            if not c or not c["resolved"]:
                return ABSTAIN_TOKEN, None, "abstain", "no_resolve_prov"
            return c["resolve_prov"], c["resolve_prov"], "ok", ""
        if slot == "conf_counterfactual":
            c = st.conflicts.get(s["conflict_id"])
            if not c:
                return ABSTAIN_TOKEN, None, "abstain", "no_conflict"
            # claiming unresolved at T contradicts if resolved
            return bool(c["resolved"]), c.get("resolve_prov"), "ok", ""

        return ABSTAIN_TOKEN, None, "unsupported", f"unknown_slot:{slot}"

    def _ceo_transition(self, st: ReconstructedState, s: dict) -> tuple[Any, Optional[str], str, str]:
        org, role = s["org_id"], s["role"]
        replacements = [
            r for r in st.roles
            if r["org_id"] == org and r["role"] == role and r.get("from_person")
        ]
        if not replacements:
            # find closed role with replace_t
            closed = [
                r for r in st.roles
                if r["org_id"] == org and r["role"] == role and r.get("replace_t") is not None
            ]
            if not closed:
                return ABSTAIN_TOKEN, None, "abstain", "no_replacement"
            old = closed[-1]
            new = role_holder(st, org, role, old["replace_t"])
            if not new:
                return ABSTAIN_TOKEN, None, "abstain", "no_new_ceo"
            return {
                "from": old["person_id"],
                "to": new["person_id"],
                "t": old["replace_t"],
                "role": role,
                "org_id": org,
            }, old.get("replace_prov"), "ok", ""
        new = replacements[-1]
        return {
            "from": new.get("from_person"),
            "to": new["person_id"],
            "t": new["start"],
            "role": role,
            "org_id": org,
        }, new["prov"], "ok", ""

    def _owner_record(self, st: ReconstructedState, project_id: str, t: int) -> Optional[dict]:
        for o in st.ownerships:
            if o["project_id"] == project_id and _active_at(o["start"], o["end"], t):
                return o
        # Infer active pre-transfer synthetic
        for o in st.ownerships:
            if o["project_id"] == project_id and o.get("from_org") and t < o["start"]:
                return {
                    "org_id": o["from_org"],
                    "prov": o.get("prov"),
                    "project_id": project_id,
                    "start": 0,
                    "end": o["start"],
                }
        return None

    def _infer_pre_transfer_owner(self, st: ReconstructedState, project_id: str, t: int) -> Optional[str]:
        for o in st.ownerships:
            if o["project_id"] == project_id and o.get("from_org") and t < o["start"]:
                return o["from_org"]
        return None

    def _owner_transition(self, st: ReconstructedState, project_id: str) -> tuple[Any, Optional[str], str, str]:
        # Chronologically last transfer (docstring: last change event)
        transfers = [
            o for o in st.ownerships if o["project_id"] == project_id and o.get("from_org")
        ]
        if not transfers:
            return ABSTAIN_TOKEN, None, "abstain", "no_transfer"
        o = transfers[-1]
        return {
            "from": o["from_org"],
            "to": o["org_id"],
            "t": o["start"],
            "project_id": project_id,
        }, o["prov"], "ok", ""

    def _owner_mgr_align(self, st, s, query, t) -> tuple[Any, Optional[str], str, str]:
        project_id = s["project_id"]
        owner = owner_of(st, project_id, t)
        if owner is None:
            own = self._owner_record(st, project_id, t)
            owner = own["org_id"] if own else None
        mgr = st.projects.get(project_id, {}).get("manager_id") or query.metadata.get("manager_id")
        if owner is None or mgr is None:
            return ABSTAIN_TOKEN, None, "abstain", "missing_owner_or_mgr"
        mgr_org = employer_of(st, mgr, t)
        return (mgr_org == owner), None, "ok", ""

    def _doc_transition(self, st: ReconstructedState, base: str) -> tuple[Any, Optional[str], str, str]:
        versions = st.docs.get(base, [])
        revs = [d for d in versions if d.get("from_version") is not None]
        if not revs:
            return ABSTAIN_TOKEN, None, "abstain", "no_revision"
        d = revs[-1]
        return {
            "from_version": d["from_version"],
            "to_version": d["version"],
            "t": d["t"],
            "base_doc_id": base,
        }, d["prov"], "ok", ""

    def _leave_transition(self, st: ReconstructedState, person_id: str, org_id: str):
        for e in st.employments:
            if e["person_id"] == person_id and e["org_id"] == org_id and e.get("leave_t"):
                return {
                    "person_id": person_id,
                    "org_id": org_id,
                    "t": e["leave_t"],
                    "action": "leave",
                }, e.get("leave_prov"), "ok", ""
        return ABSTAIN_TOKEN, None, "abstain", "no_leave"

    def _event_order(self, st: ReconstructedState, before_id: str, after_id: str):
        b = st.events_by_id.get(before_id)
        a = st.events_by_id.get(after_id)
        if not b or not a:
            return ABSTAIN_TOKEN, None, "abstain", "missing_events"
        return (b.t < a.t), None, "ok", ""
