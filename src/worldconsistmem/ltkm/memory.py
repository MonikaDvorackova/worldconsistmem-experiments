"""Hierarchical LTKM memory: observation ingest → lifecycle → stores."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from ..models import Observation
from .archive_store import ArchiveStore
from .conflict_store import ConflictStore
from .current_store import CurrentStore
from .graph_store import GraphStore
from .lifecycle import LifecycleEngine
from .provenance_store import ProvenanceStore


def fact_key_role(org_id: str, role: str) -> str:
    return f"{org_id}|role|{role}"


def fact_key_emp(person_id: str) -> str:
    return f"{person_id}|employment|"


def fact_key_owner(project_id: str) -> str:
    return f"{project_id}|owner|"


def fact_key_doc(base_doc_id: str) -> str:
    return f"{base_doc_id}|canonical_version|"


def fact_key_project_status(project_id: str) -> str:
    return f"{project_id}|project_status|"


def fact_key_project_manager(project_id: str) -> str:
    return f"{project_id}|manager|"


@dataclass
class LTKMConfig:
    enable_archive: bool = True
    enable_graph: bool = True
    enable_provenance: bool = True
    enable_conflict: bool = True
    enable_temporal_validity: bool = True
    max_logical_records: Optional[int] = None  # matched-storage optional
    max_retrieval_records: Optional[int] = None  # matched consultation budget
    system_id: str = "H0_ltkm"
    run_id: str = "ltkm"


class HierarchicalMemory:
    """Lifecycle-aware hierarchical memory.

    Anti-triviality: raw observations are sealed in `_audit_obs` and are not
    readable by answer/retrieval paths (`get_audit_obs` raises if answering).
    """

    def __init__(self, config: Optional[LTKMConfig] = None):
        self.config = config or LTKMConfig()
        self.current = CurrentStore()
        self.archive = ArchiveStore()
        self.graph = GraphStore()
        self.provenance = ProvenanceStore()
        self.conflicts = ConflictStore()
        self.lifecycle = LifecycleEngine(
            self.current,
            self.archive,
            self.graph,
            self.provenance,
            self.conflicts,
            enable_archive=self.config.enable_archive,
            enable_graph=self.config.enable_graph,
            enable_provenance=self.config.enable_provenance,
            enable_conflict=self.config.enable_conflict,
            enable_temporal_validity=self.config.enable_temporal_validity,
        )
        self._audit_obs: list[Observation] = []
        self._answering = False
        self._ingest_count = 0
        self.event_index: dict[str, dict[str, Any]] = {}  # event_id -> {t, type, ...} for temporal_order
        self.doc_versions: dict[str, list[dict]] = {}
        self.transition_index: dict[str, list[dict]] = {}  # fact_key -> transition records

    def reset(self) -> None:
        self.__init__(self.config)  # noqa: PLC2801 — intentional full reset

    def seal_start_answering(self) -> None:
        self._answering = True

    def seal_end_answering(self) -> None:
        self._answering = False

    def get_audit_obs(self) -> list[Observation]:
        if self._answering:
            raise RuntimeError("raw observation audit inaccessible during answering")
        return list(self._audit_obs)

    def ingest(self, obs: Observation) -> None:
        if obs.is_distractor:
            return
        self._audit_obs.append(obs)
        self._ingest_count += 1
        s = obs.structured
        et = s.get("event_type")
        p = s.get("payload") or {}
        t = int(s.get("t", obs.t))
        prov = s.get("provenance_id") or obs.provenance_id
        eid = s.get("event_id") or obs.event_id
        oid = obs.observation_id

        self.event_index[eid] = {
            "t": t,
            "event_type": et,
            "payload": dict(p),
            "provenance_id": prov,
            "observation_id": oid,
        }

        if et == "person_joins_org":
            self.lifecycle.insert(
                fact_key_emp(p["person_id"]),
                p["org_id"],
                t,
                oid,
                prov,
                metadata={"person_id": p["person_id"]},
            )
            self.lifecycle.add_edge("member_of", p["person_id"], p["org_id"], t, oid, prov)
            self.lifecycle.promote(t, oid, {"kind": "employment"})

        elif et == "person_leaves_org":
            terminated = self.lifecycle.terminate_fact(fact_key_emp(p["person_id"]), t, oid, prov)
            self.transition_index.setdefault(fact_key_emp(p["person_id"]), []).append(
                {
                    "action": "leave",
                    "person_id": p["person_id"],
                    "org_id": p["org_id"],
                    "t": t,
                    "prov": prov,
                    "obs_id": oid,
                }
            )
            # terminate role facts for this person at org
            for rec in list(self.current.items()):
                if rec.fact_key.startswith(f"{p['org_id']}|role|") and rec.value == p["person_id"]:
                    self.lifecycle.terminate_fact(rec.fact_key, t, oid, prov)
            # terminate member_of edges
            for e in list(self.graph.edges()):
                if (
                    e.rel_type == "member_of"
                    and e.source_id == p["person_id"]
                    and e.target_id == p["org_id"]
                    and e.valid_to is None
                ):
                    self.lifecycle.terminate_edge(e.edge_id, t, oid)

        elif et == "role_assignment":
            fk = fact_key_role(p["org_id"], p["role"])
            exclusive = bool(p.get("exclusive", True))
            if exclusive and self.current.get(fk):
                self.lifecycle.supersede(fk, p["person_id"], t, oid, prov)
            else:
                self.lifecycle.insert(fk, p["person_id"], t, oid, prov, exclusive=exclusive)
            self.lifecycle.add_edge(
                f"role:{p['role']}", p["person_id"], p["org_id"], t, oid, prov
            )

        elif et == "role_replacement":
            fk = fact_key_role(p["org_id"], p["role"])
            old = self.current.get(fk)
            old_val = old.value if old else p.get("old_person_id")
            self.lifecycle.supersede(fk, p["new_person_id"], t, oid, prov)
            self.transition_index.setdefault(fk, []).append(
                {
                    "from": old_val,
                    "to": p["new_person_id"],
                    "t": t,
                    "role": p["role"],
                    "org_id": p["org_id"],
                    "prov": prov,
                    "obs_id": oid,
                }
            )
            # update role edges
            for e in list(self.graph.edges()):
                if (
                    e.rel_type == f"role:{p['role']}"
                    and e.target_id == p["org_id"]
                    and e.valid_to is None
                ):
                    self.lifecycle.terminate_edge(e.edge_id, t, oid)
            self.lifecycle.add_edge(
                f"role:{p['role']}", p["new_person_id"], p["org_id"], t, oid, prov
            )

        elif et == "project_ownership_transfer":
            fk = fact_key_owner(p["project_id"])
            old_org = p.get("old_org_id")
            seed = None
            if old_org is not None and self.current.get(fk) is None:
                seed = (old_org, 0, f"{prov}:prior")
            self.lifecycle.supersede(
                fk, p["new_org_id"], t, oid, prov, seed_prior=seed
            )
            self.transition_index.setdefault(fk, []).append(
                {
                    "from": old_org or (seed[0] if seed else None),
                    "to": p["new_org_id"],
                    "t": t,
                    "project_id": p["project_id"],
                    "prov": prov,
                    "obs_id": oid,
                }
            )
            if old_org:
                for e in list(self.graph.edges()):
                    if (
                        e.rel_type == "owns"
                        and e.target_id == p["project_id"]
                        and e.valid_to is None
                    ):
                        self.lifecycle.terminate_edge(e.edge_id, t, oid)
            self.lifecycle.add_edge("owns", p["new_org_id"], p["project_id"], t, oid, prov)

        elif et == "project_status_change":
            sfk = fact_key_project_status(p["project_id"])
            if self.current.get(sfk):
                self.lifecycle.supersede(sfk, p["status"], t, oid, prov)
            else:
                self.lifecycle.insert(sfk, p["status"], t, oid, prov)
            if "manager_id" in p and p["manager_id"]:
                fk = fact_key_project_manager(p["project_id"])
                if self.current.get(fk):
                    self.lifecycle.supersede(fk, p["manager_id"], t, oid, prov)
                else:
                    self.lifecycle.insert(fk, p["manager_id"], t, oid, prov)
                self.lifecycle.add_edge(
                    "manages_project", p["manager_id"], p["project_id"], t, oid, prov
                )

        elif et == "document_creation":
            base = p.get("base_doc_id", p["doc_id"])
            self.doc_versions.setdefault(base, []).append(
                {"version": 1, "doc_id": p["doc_id"], "t": t, "prov": prov, "obs_id": oid, "project_id": p["project_id"], "approved_by": None}
            )
            self.lifecycle.insert(
                fact_key_doc(base),
                1,
                t,
                oid,
                prov,
                metadata={"doc_id": p["doc_id"], "project_id": p["project_id"]},
            )

        elif et == "document_revision":
            base = p["base_doc_id"]
            versions = self.doc_versions.setdefault(base, [])
            prev = versions[-1]["version"] if versions else 0
            new_v = prev + 1
            versions.append(
                {
                    "version": new_v,
                    "doc_id": p["doc_id"],
                    "t": t,
                    "prov": prov,
                    "obs_id": oid,
                    "project_id": versions[-1]["project_id"] if versions else None,
                    "approved_by": None,
                    "from_version": prev,
                }
            )
            self.lifecycle.supersede(
                fact_key_doc(base),
                new_v,
                t,
                oid,
                prov,
                metadata={"doc_id": p["doc_id"], "from_version": prev},
            )
            self.transition_index.setdefault(fact_key_doc(base), []).append(
                {
                    "from_version": prev,
                    "to_version": new_v,
                    "t": t,
                    "base_doc_id": base,
                    "prov": prov,
                    "obs_id": oid,
                }
            )

        elif et == "document_approval":
            for base, versions in self.doc_versions.items():
                for d in versions:
                    if d["doc_id"] == p["doc_id"]:
                        d["approved_by"] = p["approver_id"]
                        d["approve_prov"] = prov
                        d["approve_obs"] = oid
                        # annotate current doc fact metadata
                        cur = self.current.get(fact_key_doc(base))
                        if cur and cur.metadata.get("doc_id") == p["doc_id"]:
                            cur.metadata["approved_by"] = p["approver_id"]
                            cur.metadata["approve_prov"] = prov

        elif et == "relationship_creation":
            self.lifecycle.add_edge(
                p["rel_type"],
                p["source_id"],
                p["target_id"],
                t,
                oid,
                prov,
                edge_id=p.get("rel_id"),
            )

        elif et == "relationship_termination":
            self.lifecycle.terminate_edge(p["rel_id"], t, oid)

        elif et == "conflict_introduction":
            fk = f"{p['subject']}|{p['attribute']}|"
            self.lifecycle.detect_conflict(
                p["conflict_id"], fk, p["value_a"], p["value_b"], t, oid, prov
            )

        elif et == "conflict_resolution":
            self.lifecycle.resolve_conflict(
                p["conflict_id"], p["resolved_value"], t, oid, prov
            )

        elif et == "temporary_state":
            if p["attribute"] == "project_status":
                self.lifecycle.temporary_update(
                    fact_key_project_status(p["entity_id"]),
                    p["temporary_value"],
                    p["original_value"],
                    t,
                    oid,
                    prov,
                    p["mark_id"],
                )

        elif et == "reversion":
            self.lifecycle.revert(p["mark_id"], t, oid, prov)

        elif et == "location_change":
            fk = f"{p['person_id']}|location|"
            if self.current.get(fk):
                self.lifecycle.supersede(fk, p["location_id"], t, oid, prov)
            else:
                self.lifecycle.insert(fk, p["location_id"], t, oid, prov)

        # optional capacity compaction
        if self.config.max_logical_records is not None:
            self._compact_if_needed()

    def _compact_if_needed(self) -> None:
        """Deterministic overflow: no hidden store; all logical records count.

        Priority (drop first → last):
          1. padding event_index (location/status)
          2. remaining non-focal event_index oldest
          3. oldest provenance entries
          4. terminated graph edges
          5. oldest non-protected archive
          6. remaining event_index
          7. remaining archive
          8. transition_index oldest
          9. current store oldest (last resort)

        Protected archive keys (kept longer): role|CEO, ownership, canonical_version,
        employment for known persons — until non-protected archive is exhausted.
        """
        cap = self.config.max_logical_records
        if cap is None or self.logical_record_count() <= cap:
            return
        padding_types = {"location_change", "project_status_change"}

        def is_protected_archive(r) -> bool:
            k = r.fact_key
            return (
                "|role|CEO" in k
                or k.endswith("|owner|")
                or "|canonical_version|" in k
                or "|employment|" in k
            )

        def drop_event(eid: str) -> None:
            self.event_index.pop(eid, None)

        while self.logical_record_count() > cap:
            pad_eids = sorted(
                (
                    eid
                    for eid, info in self.event_index.items()
                    if info.get("event_type") in padding_types
                ),
                key=lambda e: (self.event_index[e].get("t", 0), e),
            )
            if pad_eids:
                drop_event(pad_eids[0])
                continue
            # provenance early (metadata tax) — still counted, drop before focal archive
            if self.provenance._links and len(self.provenance) > max(10, cap // 10):
                pid = sorted(self.provenance._links.keys())[0]
                link = self.provenance._links.pop(pid)
                subj = self.provenance._by_subject.get(link.subject_id, [])
                if pid in subj:
                    subj.remove(pid)
                provs = self.provenance._by_prov.get(link.provenance_id, [])
                if pid in provs:
                    provs.remove(pid)
                continue
            edges = sorted(
                [e for e in self.graph.edges() if getattr(e, "valid_to", None) is not None],
                key=lambda e: (e.valid_from, e.edge_id),
            )
            if edges:
                self.graph._edges.pop(edges[0].edge_id, None)
                continue
            archived = sorted(
                self.archive.all_records(), key=lambda r: (r.valid_from, r.record_id)
            )
            nonprot = [r for r in archived if not is_protected_archive(r)]
            if nonprot:
                victim = nonprot[0]
                self.archive._records.pop(victim.record_id, None)
                ids = self.archive._by_key.get(victim.fact_key, [])
                if victim.record_id in ids:
                    ids.remove(victim.record_id)
                continue
            if self.event_index:
                eid = sorted(
                    self.event_index.keys(),
                    key=lambda e: (self.event_index[e].get("t", 0), e),
                )[0]
                drop_event(eid)
                continue
            if archived:
                victim = archived[0]
                self.archive._records.pop(victim.record_id, None)
                ids = self.archive._by_key.get(victim.fact_key, [])
                if victim.record_id in ids:
                    ids.remove(victim.record_id)
                continue
            if self.provenance._links:
                pid = sorted(self.provenance._links.keys())[0]
                link = self.provenance._links.pop(pid)
                subj = self.provenance._by_subject.get(link.subject_id, [])
                if pid in subj:
                    subj.remove(pid)
                provs = self.provenance._by_prov.get(link.provenance_id, [])
                if pid in provs:
                    provs.remove(pid)
                continue
            if self.transition_index:
                fk = sorted(self.transition_index.keys())[0]
                if self.transition_index[fk]:
                    self.transition_index[fk].pop(0)
                    if not self.transition_index[fk]:
                        del self.transition_index[fk]
                    continue
                del self.transition_index[fk]
                continue
            items = sorted(self.current.items(), key=lambda r: (r.valid_from, r.record_id))
            if items:
                self.current.remove(items[0].fact_key)
                continue
            break

    def logical_record_count(self) -> int:
        return (
            len(self.current)
            + len(self.archive)
            + len(self.graph)
            + len(self.provenance)
            + len(self.conflicts)
            + len(self.event_index)
            + sum(len(v) for v in self.transition_index.values())
        )

    def serialized_bytes(self) -> int:
        blob = {
            "current": [r.to_dict() for r in self.current.items()],
            "archive": [r.to_dict() for r in self.archive.all_records()],
            "graph": [e.to_dict() for e in self.graph.edges()],
            "conflicts": [c.to_dict() for c in self.conflicts.all()],
            "n_prov": len(self.provenance),
            "events": len(self.event_index),
        }
        return len(json.dumps(blob, sort_keys=True).encode())

    def resource_snapshot(self) -> dict[str, Any]:
        return {
            "n_current": len(self.current),
            "n_archive": len(self.archive),
            "n_graph_edges": len(self.graph),
            "n_graph_nodes": self.graph.n_nodes,
            "n_provenance": len(self.provenance),
            "n_conflicts": len(self.conflicts),
            "n_unresolved_conflicts": len(self.conflicts.unresolved()),
            "n_event_index": len(self.event_index),
            "logical_records": self.logical_record_count(),
            "serialized_bytes": self.serialized_bytes(),
            "n_ingest": self._ingest_count,
            "n_audit_obs_sealed": len(self._audit_obs),
        }
