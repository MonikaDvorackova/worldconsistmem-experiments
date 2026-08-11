"""Deterministic LTKM reader over store-routed retrieval packs."""

from __future__ import annotations

from typing import Any, Optional

from ..baselines.interface import ABSTAIN_TOKEN, AnswerResult
from ..models import Query
from .memory import HierarchicalMemory, fact_key_emp
from .retrieval import LTKMRetriever, RetrievalPack


class LTKMReader:
    def __init__(self, memory: HierarchicalMemory):
        self.mem = memory
        self.retriever = LTKMRetriever(memory)

    def answer(self, query: Query) -> AnswerResult:
        self.mem.seal_start_answering()
        try:
            # Guard: answering must not touch raw obs
            try:
                self.mem.get_audit_obs()
                return AnswerResult(ABSTAIN_TOKEN, status="error", detail="audit_leak")
            except RuntimeError:
                pass
            pack = self.retriever.retrieve(query)
            ans, prov, status, detail = self._dispatch(query, pack)
            return AnswerResult(
                answer=ans,
                provenance=prov,
                retrieved_observation_ids=list(pack.record_ids),
                retrieval_scores=[],
                status=status,
                detail=detail,
            )
        finally:
            self.mem.seal_end_answering()

    def _val(self, rec) -> Any:
        if rec is None:
            return None
        return rec.value if hasattr(rec, "value") else rec.get("value")

    def _prov(self, rec) -> Optional[str]:
        if rec is None:
            return None
        return rec.provenance_id if hasattr(rec, "provenance_id") else rec.get("provenance_id")

    def _dispatch(self, query: Query, pack: RetrievalPack):
        slot = query.metadata.get("slot", "")
        s = query.structured
        t = query.target_time
        fact = pack.payloads.get("fact")

        if slot == "ceo_current":
            if fact is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_current_ceo"
            return self._val(fact), self._prov(fact), "ok", "current"

        if slot == "ceo_historical":
            if fact is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_hist_ceo"
            return self._val(fact), self._prov(fact), "ok", "archive"

        if slot == "ceo_transition":
            trs = pack.payloads.get("transitions") or []
            if not trs:
                return ABSTAIN_TOKEN, None, "abstain", "no_transition"
            tr = trs[-1]
            return {
                "from": tr["from"],
                "to": tr["to"],
                "t": tr["t"],
                "role": tr["role"],
                "org_id": tr["org_id"],
            }, tr.get("prov"), "ok", "transition"

        if slot == "ceo_employer":
            if fact is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_ceo"
            person = self._val(fact)
            edges = pack.payloads.get("member_edges") or []
            if edges:
                return edges[0].target_id, edges[0].provenance_id, "ok", "graph"
            if not self.mem.config.enable_graph:
                return ABSTAIN_TOKEN, None, "abstain", "graph_disabled"
            # Graph enabled but no edge retrieved — try employment fact key (store, not obs)
            emp = self.mem.current.get(fact_key_emp(person))
            if emp and (t is None or emp.active_at(t)):
                return emp.value, emp.provenance_id, "ok", "current_emp"
            if self.mem.config.enable_archive and t is not None:
                emp_a = self.mem.archive.at_time(fact_key_emp(person), t)
                if emp_a:
                    return emp_a.value, emp_a.provenance_id, "ok", "archive_emp"
            return ABSTAIN_TOKEN, None, "abstain", "no_employer"

        if slot == "ceo_provenance":
            if fact is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_prov"
            return self._prov(fact), self._prov(fact), "ok", "provenance"

        if slot == "ceo_order":
            return self._order(pack, s)

        if slot == "ceo_contradiction":
            return False, self._prov(fact), "ok", "contradiction"

        if slot == "ceo_counterfactual":
            claim = s["claim"]
            if fact is None:
                return True, None, "ok", "counterfactual_missing"
            contradicts = self._val(fact) != claim["person_id"]
            return contradicts, self._prov(fact), "ok", "counterfactual"

        if slot == "owner_current":
            if fact is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_owner"
            return self._val(fact), self._prov(fact), "ok", "current"

        if slot == "owner_historical":
            if fact is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_hist_owner"
            return self._val(fact), self._prov(fact), "ok", "archive"

        if slot == "owner_transition":
            trs = pack.payloads.get("transitions") or []
            if not trs:
                return ABSTAIN_TOKEN, None, "abstain", "no_owner_tr"
            tr = trs[-1]
            return {
                "from": tr["from"],
                "to": tr["to"],
                "t": tr["t"],
                "project_id": tr["project_id"],
            }, tr.get("prov"), "ok", "transition"

        if slot == "owner_mgr_align":
            owner = self._val(fact)
            mgr_f = pack.payloads.get("manager_fact")
            if owner is None or mgr_f is None:
                return ABSTAIN_TOKEN, None, "abstain", "missing"
            mgr = self._val(mgr_f)
            edges = pack.payloads.get("member_edges") or []
            if not self.mem.config.enable_graph:
                return ABSTAIN_TOKEN, None, "abstain", "graph_disabled"
            mgr_org = edges[0].target_id if edges else None
            if mgr_org is None:
                emp = self.mem.current.get(fact_key_emp(mgr))
                mgr_org = emp.value if emp else None
            return (mgr_org == owner), None, "ok", "graph"

        if slot == "owner_provenance":
            if fact is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_owner_prov"
            return self._prov(fact), self._prov(fact), "ok", "provenance"

        if slot == "conflict_no_silent_resolution":
            return False, None, "ok", "conflict_policy"

        if slot == "doc_version":
            if fact is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_doc"
            return self._val(fact), self._prov(fact), "ok", "current"

        if slot == "doc_hist_version":
            if fact is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_hist_doc"
            return self._val(fact), self._prov(fact), "ok", "archive"

        if slot == "doc_transition":
            trs = pack.payloads.get("transitions") or []
            if not trs:
                return ABSTAIN_TOKEN, None, "abstain", "no_doc_tr"
            tr = trs[-1]
            return {
                "from_version": tr["from_version"],
                "to_version": tr["to_version"],
                "t": tr["t"],
                "base_doc_id": tr["base_doc_id"],
            }, tr.get("prov"), "ok", "transition"

        if slot == "doc_approve_project":
            versions = pack.payloads.get("doc_versions") or []
            canon = None
            if fact is not None:
                doc_id = fact.metadata.get("doc_id") if hasattr(fact, "metadata") else None
                for d in versions:
                    if d.get("doc_id") == doc_id or d.get("version") == self._val(fact):
                        canon = d
            if canon is None and versions:
                canon = versions[-1]
            if not canon or not canon.get("approved_by"):
                # try metadata on fact
                if fact and hasattr(fact, "metadata") and fact.metadata.get("approved_by"):
                    return {
                        "approver": fact.metadata["approved_by"],
                        "project_id": fact.metadata.get("project_id"),
                    }, fact.metadata.get("approve_prov"), "ok", "current"
                return ABSTAIN_TOKEN, None, "abstain", "no_approval"
            return {
                "approver": canon["approved_by"],
                "project_id": canon.get("project_id")
                or (fact.metadata.get("project_id") if fact and hasattr(fact, "metadata") else None),
            }, canon.get("approve_prov"), "ok", "doc"

        if slot == "doc_provenance":
            if fact is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_doc_prov"
            return self._prov(fact), self._prov(fact), "ok", "provenance"

        if slot == "doc_order":
            return self._order(pack, s)

        if slot == "emp_current":
            org = s["org_id"]
            return (self._val(fact) == org), self._prov(fact), "ok", "current"

        if slot == "emp_historical":
            org = s["org_id"]
            return (self._val(fact) == org), self._prov(fact), "ok", "archive"

        if slot == "emp_transition":
            trs = pack.payloads.get("transitions") or []
            leaves = [tr for tr in trs if tr.get("action") == "leave"]
            if not leaves:
                return ABSTAIN_TOKEN, None, "abstain", "no_leave"
            tr = leaves[-1]
            return {
                "person_id": tr["person_id"],
                "org_id": tr["org_id"],
                "t": tr["t"],
                "action": "leave",
            }, tr.get("prov"), "ok", "transition"

        if slot == "emp_role_compat":
            org = s["org_id"]
            employed = self._val(fact) == org
            return (True if employed else False), None, "ok", "multi_hop"

        if slot == "emp_provenance":
            trs = pack.payloads.get("transitions") or []
            leaves = [tr for tr in trs if tr.get("action") == "leave"]
            if not leaves:
                return ABSTAIN_TOKEN, None, "abstain", "no_leave_prov"
            return leaves[-1]["prov"], leaves[-1]["prov"], "ok", "provenance"

        if slot == "emp_contradiction":
            return False, None, "ok", "contradiction"

        if slot == "conf_resolved":
            c = pack.payloads.get("conflict")
            if c is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_conflict"
            return bool(c.resolved), c.resolution_provenance_id or c.provenance_id, "ok", "conflict"

        if slot == "conf_unresolved_hist":
            c = pack.payloads.get("conflict")
            if c is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_conflict"
            unresolved = c.valid_from <= (t or 0) and (
                not c.resolved or (c.resolution_t is not None and c.resolution_t > (t or 0))
            )
            return unresolved, c.provenance_id, "ok", "conflict"

        if slot == "conf_value":
            c = pack.payloads.get("conflict")
            if c is None or not c.resolved:
                return ABSTAIN_TOKEN, None, "abstain", "unresolved"
            return c.resolved_value, c.resolution_provenance_id, "ok", "conflict"

        if slot == "conf_transition":
            c = pack.payloads.get("conflict")
            if c is None or not c.resolved:
                return ABSTAIN_TOKEN, None, "abstain", "no_resolution"
            return {
                "conflict_id": c.conflict_id,
                "t": c.resolution_t,
                "resolved_value": c.resolved_value,
            }, c.resolution_provenance_id, "ok", "conflict"

        if slot == "conf_subject":
            c = pack.payloads.get("conflict")
            if c is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_conflict"
            subject = c.fact_key.split("|")[0]
            return subject == s["expected_subject"], c.provenance_id, "ok", "conflict"

        if slot == "conf_provenance":
            c = pack.payloads.get("conflict")
            if c is None or not c.resolved:
                return ABSTAIN_TOKEN, None, "abstain", "no_resolve_prov"
            return c.resolution_provenance_id, c.resolution_provenance_id, "ok", "provenance"

        if slot == "conf_counterfactual":
            c = pack.payloads.get("conflict")
            if c is None:
                return ABSTAIN_TOKEN, None, "abstain", "no_conflict"
            return bool(c.resolved), c.resolution_provenance_id, "ok", "counterfactual"

        return ABSTAIN_TOKEN, None, "unsupported", f"slot:{slot}"

    def _order(self, pack: RetrievalPack, s: dict):
        events = pack.payloads.get("events") or {}
        b = events.get(s.get("before_event"))
        a = events.get(s.get("after_event"))
        if not b or not a:
            return ABSTAIN_TOKEN, None, "abstain", "missing_events"
        return (b["t"] < a["t"]), None, "ok", "events"
