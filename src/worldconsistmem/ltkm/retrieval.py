"""Store-routed retrieval for LTKM (no universal observation scan)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..models import Query
from .memory import (
    HierarchicalMemory,
    fact_key_doc,
    fact_key_emp,
    fact_key_owner,
    fact_key_project_manager,
    fact_key_role,
)
from .models import LifecycleOp


STORE_ROUTING = {
    "current_state": ["current"],
    "historical_state": ["archive", "current"],
    "transition": ["current", "archive", "transitions"],
    "conflict_validity": ["conflict", "archive"],
    "multi_hop": ["graph", "current"],
    "provenance": ["provenance", "current", "archive"],
    "temporal_order": ["events"],
    "contradiction": ["conflict", "current"],
    "counterfactual": ["current", "archive"],
}


@dataclass
class RetrievalPack:
    stores: list[str] = field(default_factory=list)
    record_ids: list[str] = field(default_factory=list)
    payloads: dict[str, Any] = field(default_factory=dict)
    n_consulted: int = 0


class LTKMRetriever:
    def __init__(self, memory: HierarchicalMemory):
        self.mem = memory

    def retrieve(self, query: Query) -> RetrievalPack:
        family = query.family.value
        slot = query.metadata.get("slot", "")
        stores = list(STORE_ROUTING.get(family, ["current"]))

        # Slot-level overrides for conflict / provenance routing
        if slot.startswith("conf_") or slot == "conflict_no_silent_resolution":
            stores = ["conflict", "archive"]
        if slot.endswith("_provenance") or slot in (
            "ceo_provenance",
            "owner_provenance",
            "doc_provenance",
            "emp_provenance",
            "conf_provenance",
        ):
            stores = ["provenance", "current", "archive", "conflict", "transitions"]
        if slot.endswith("_transition") or slot in (
            "ceo_transition",
            "owner_transition",
            "doc_transition",
            "emp_transition",
            "conf_transition",
        ):
            stores = ["current", "archive", "transitions", "conflict"]
        if slot in ("ceo_employer", "owner_mgr_align", "emp_role_compat", "conf_subject"):
            stores = ["graph", "current", "archive", "conflict"]
        if slot in ("ceo_order", "doc_order"):
            stores = ["events"]

        # Ablation: drop disabled stores
        if not self.mem.config.enable_archive:
            stores = [s for s in stores if s != "archive"]
        if not self.mem.config.enable_graph:
            stores = [s for s in stores if s != "graph"]
        if not self.mem.config.enable_conflict:
            stores = [s for s in stores if s != "conflict"]
        if not self.mem.config.enable_provenance:
            stores = [s for s in stores if s != "provenance"]

        pack = RetrievalPack(stores=stores)
        s = query.structured
        t = query.target_time

        if slot in ("ceo_current", "ceo_historical", "ceo_provenance", "ceo_employer", "ceo_contradiction", "ceo_counterfactual", "ceo_transition"):
            org = s.get("org_id") or (s.get("claim") or {}).get("org_id")
            role = s.get("role") or (s.get("claim") or {}).get("role") or "CEO"
            fk = fact_key_role(org, role)
            self._pull_fact(pack, fk, t, stores)
            if "transitions" in stores or family == "transition":
                tr = self.mem.transition_index.get(fk, [])
                pack.payloads["transitions"] = tr
                pack.n_consulted += len(tr)
                pack.record_ids.extend([f"tr:{fk}:{i}" for i in range(len(tr))])
            if slot == "ceo_employer" and "graph" in stores:
                cur = pack.payloads.get("fact")
                if cur:
                    person = cur.value if hasattr(cur, "value") else cur.get("value")
                    edges = self.mem.graph.neighbors(person, "member_of", t or 10**9)
                    pack.payloads["member_edges"] = edges
                    pack.n_consulted += len(edges)
                    pack.record_ids.extend([e.edge_id for e in edges])
            if slot == "ceo_order" or family == "temporal_order":
                self._pull_events(pack, s.get("before_event"), s.get("after_event"))

        elif slot in ("owner_current", "owner_historical", "owner_transition", "owner_provenance", "owner_mgr_align"):
            pid = s["project_id"]
            fk = fact_key_owner(pid)
            self._pull_fact(pack, fk, t, stores)
            tr = self.mem.transition_index.get(fk, [])
            pack.payloads["transitions"] = tr
            pack.n_consulted += len(tr)
            if slot == "owner_mgr_align":
                mfk = fact_key_project_manager(pid)
                self._pull_fact(pack, mfk, t, stores, dest="manager_fact")
                mgr = pack.payloads.get("manager_fact")
                if mgr and "graph" in stores:
                    person = mgr.value if hasattr(mgr, "value") else mgr.get("value")
                    edges = self.mem.graph.neighbors(person, "member_of", t or 10**9)
                    pack.payloads["member_edges"] = edges
                    pack.n_consulted += len(edges)

        elif slot == "conflict_no_silent_resolution":
            if "conflict" in stores:
                unresolved = self.mem.conflicts.unresolved()
                pack.payloads["unresolved"] = unresolved
                pack.n_consulted += len(unresolved)

        elif slot.startswith("doc_") or slot in ("doc_version", "doc_hist_version", "doc_transition", "doc_approve_project", "doc_provenance", "doc_order"):
            base = s.get("base_doc_id")
            if base:
                fk = fact_key_doc(base)
                self._pull_fact(pack, fk, t, stores)
                pack.payloads["doc_versions"] = self.mem.doc_versions.get(base, [])
                pack.n_consulted += len(pack.payloads["doc_versions"])
                tr = self.mem.transition_index.get(fk, [])
                pack.payloads["transitions"] = tr
                pack.n_consulted += len(tr)
            if slot == "doc_order":
                self._pull_events(pack, s.get("before_event"), s.get("after_event"))

        elif slot.startswith("emp_") or slot in ("emp_current", "emp_historical", "emp_transition", "emp_provenance", "emp_role_compat", "emp_contradiction"):
            person = s.get("person_id")
            if person:
                fk = fact_key_emp(person)
                self._pull_fact(pack, fk, t, stores)
                tr = self.mem.transition_index.get(fk, [])
                pack.payloads["transitions"] = tr
                pack.n_consulted += len(tr)

        elif slot.startswith("conf_"):
            cid = s.get("conflict_id")
            if cid:
                c = self.mem.conflicts.get(cid)
                pack.payloads["conflict"] = c
                pack.n_consulted += 1
                if c:
                    pack.record_ids.append(cid)

        elif family == "temporal_order":
            self._pull_events(pack, s.get("before_event"), s.get("after_event"))

        self.mem.lifecycle._log(
            LifecycleOp.RETRIEVE,
            t or 0,
            query.query_id,
            {"stores": stores, "n": pack.n_consulted, "slot": slot},
            stores,
        )
        # Matched consultation budget: truncate record_ids / trim bulky lists
        max_r = self.mem.config.max_retrieval_records
        if max_r is not None and len(pack.record_ids) > max_r:
            pack.record_ids = pack.record_ids[:max_r]
            # Keep primary fact; drop overflow transitions/versions
            if "transitions" in pack.payloads and isinstance(pack.payloads["transitions"], list):
                pack.payloads["transitions"] = pack.payloads["transitions"][-max(1, max_r // 2) :]
            if "doc_versions" in pack.payloads and isinstance(pack.payloads["doc_versions"], list):
                pack.payloads["doc_versions"] = pack.payloads["doc_versions"][-max(1, max_r // 2) :]
            pack.n_consulted = min(pack.n_consulted, max_r)
        return pack

    def _pull_fact(
        self,
        pack: RetrievalPack,
        fk: str,
        t: Optional[int],
        stores: list[str],
        dest: str = "fact",
    ) -> None:
        consulted = 0
        rec = None
        if t is None:
            if "current" in stores:
                rec = self.mem.current.get(fk)
                consulted += 1
        else:
            # Prefer archive/current with temporal validity
            if self.mem.config.enable_temporal_validity:
                if "current" in stores:
                    cur = self.mem.current.get(fk)
                    consulted += 1
                    if cur and cur.active_at(t):
                        rec = cur
                if rec is None and "archive" in stores:
                    # scan only this key's archive chain (bounded), not all obs
                    chain = self.mem.archive.for_key(fk)
                    consulted += len(chain)
                    rec = self.mem.archive.at_time(fk, t)
                    if rec is None and "current" in stores:
                        cur = self.mem.current.get(fk)
                        if cur and cur.valid_from <= t and (
                            cur.valid_to is None or t < cur.valid_to
                        ):
                            rec = cur
            else:
                # No temporal validity: latest current only (ablation harm)
                if "current" in stores:
                    rec = self.mem.current.get(fk)
                    consulted += 1
        pack.payloads[dest] = rec
        pack.n_consulted += consulted
        if rec:
            pack.record_ids.append(rec.record_id)

    def _pull_events(self, pack: RetrievalPack, before_id: Optional[str], after_id: Optional[str]) -> None:
        events = {}
        for eid in (before_id, after_id):
            if eid and eid in self.mem.event_index:
                events[eid] = self.mem.event_index[eid]
                pack.record_ids.append(f"event:{eid}")
        pack.payloads["events"] = events
        pack.n_consulted += len(events)
