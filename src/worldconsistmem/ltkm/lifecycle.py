"""Deterministic knowledge lifecycle operations for LTKM."""

from __future__ import annotations

from typing import Any, Optional

from .archive_store import ArchiveStore
from .conflict_store import ConflictStore
from .current_store import CurrentStore
from .graph_store import GraphStore
from .models import (
    ConflictRecord,
    FactRecord,
    GraphEdge,
    LifecycleOp,
    LifecycleRecord,
    ProvenanceLink,
)
from .provenance_store import ProvenanceStore


class LifecycleEngine:
    """Applies lifecycle ops across stores; emits auditable records."""

    def __init__(
        self,
        current: CurrentStore,
        archive: ArchiveStore,
        graph: GraphStore,
        provenance: ProvenanceStore,
        conflicts: ConflictStore,
        *,
        enable_archive: bool = True,
        enable_graph: bool = True,
        enable_provenance: bool = True,
        enable_conflict: bool = True,
        enable_temporal_validity: bool = True,
    ):
        self.current = current
        self.archive = archive
        self.graph = graph
        self.provenance = provenance
        self.conflicts = conflicts
        self.enable_archive = enable_archive
        self.enable_graph = enable_graph
        self.enable_provenance = enable_provenance
        self.enable_conflict = enable_conflict
        self.enable_temporal_validity = enable_temporal_validity
        self.log: list[LifecycleRecord] = []
        self._seq = 0

    def _rid(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}:{self._seq}"

    def _log(self, op: LifecycleOp, t: int, obs_id: str, detail: dict, stores: list[str]) -> None:
        self.log.append(
            LifecycleRecord(op=op, t=t, observation_id=obs_id, detail=detail, affected_stores=stores)
        )

    def _link_prov(
        self, subject_id: str, prov: str, obs_id: str, kind: str, t: int
    ) -> None:
        if not self.enable_provenance:
            return
        self.provenance.add(
            ProvenanceLink(
                link_id=self._rid("pl"),
                subject_id=subject_id,
                provenance_id=prov,
                observation_id=obs_id,
                kind=kind,
                t=t,
            )
        )

    def insert(
        self,
        fact_key: str,
        value: Any,
        t: int,
        obs_id: str,
        prov: str,
        *,
        exclusive: bool = True,
        metadata: Optional[dict] = None,
    ) -> FactRecord:
        """Insert a new active fact. Fails if exclusive key already active (use supersede)."""
        existing = self.current.get(fact_key)
        if existing and exclusive and existing.exclusive:
            raise ValueError(f"insert blocked: exclusive key active {fact_key}")
        rec = FactRecord(
            record_id=self._rid("fact"),
            fact_key=fact_key,
            value=value,
            valid_from=t if self.enable_temporal_validity else 0,
            valid_to=None,
            observation_id=obs_id,
            provenance_id=prov,
            status="active",
            exclusive=exclusive,
            metadata=metadata or {},
        )
        self.current.put(rec)
        self._link_prov(rec.record_id, prov, obs_id, "current", t)
        self._log(LifecycleOp.INSERT, t, obs_id, {"fact_key": fact_key, "value": value}, ["current", "provenance"])
        return rec

    def supersede(
        self,
        fact_key: str,
        new_value: Any,
        t: int,
        obs_id: str,
        prov: str,
        *,
        metadata: Optional[dict] = None,
        seed_prior: Optional[tuple[Any, int, str]] = None,
    ) -> FactRecord:
        """Close prior active fact into archive; install new current value."""
        prior = self.current.get(fact_key)
        if prior is None and seed_prior is not None:
            # Seed archival prior from observation-licensed old value (e.g. ownership transfer)
            seed_val, seed_from, seed_prov = seed_prior
            prior = FactRecord(
                record_id=self._rid("fact"),
                fact_key=fact_key,
                value=seed_val,
                valid_from=seed_from,
                valid_to=None,
                observation_id=obs_id,
                provenance_id=seed_prov,
                status="active",
                exclusive=True,
                metadata={"seeded": True},
            )
            self.current.put(prior)
            self._link_prov(prior.record_id, seed_prov, obs_id, "historical", t)

        if prior is None:
            return self.insert(fact_key, new_value, t, obs_id, prov, metadata=metadata)

        if self.enable_temporal_validity:
            prior.valid_to = t
        prior.status = "superseded"
        prior.successor_id = None
        if self.enable_archive:
            self.archive.add(prior)
        self.current.remove(fact_key)
        self._link_prov(prior.record_id, prior.provenance_id, prior.observation_id, "historical", t)
        self._log(
            LifecycleOp.SUPERSEDE,
            t,
            obs_id,
            {"fact_key": fact_key, "old": prior.value, "new": new_value},
            ["current", "archive", "provenance"],
        )
        self._log(LifecycleOp.ARCHIVE, t, obs_id, {"record_id": prior.record_id}, ["archive"])

        new = FactRecord(
            record_id=self._rid("fact"),
            fact_key=fact_key,
            value=new_value,
            valid_from=t if self.enable_temporal_validity else 0,
            valid_to=None,
            observation_id=obs_id,
            provenance_id=prov,
            status="active",
            predecessor_id=prior.record_id,
            exclusive=prior.exclusive,
            metadata=metadata or {},
        )
        prior.successor_id = new.record_id
        self.current.put(new)
        self._link_prov(new.record_id, prov, obs_id, "current", t)
        self._log(LifecycleOp.UPDATE, t, obs_id, {"fact_key": fact_key, "value": new_value}, ["current"])
        return new

    def terminate_fact(self, fact_key: str, t: int, obs_id: str, prov: str) -> Optional[FactRecord]:
        prior = self.current.get(fact_key)
        if prior is None:
            return None
        if self.enable_temporal_validity:
            prior.valid_to = t
        prior.status = "terminated"
        if self.enable_archive:
            self.archive.add(prior)
        self.current.remove(fact_key)
        self._link_prov(prior.record_id, prov, obs_id, "transition", t)
        self._log(
            LifecycleOp.TERMINATE_RELATION,
            t,
            obs_id,
            {"fact_key": fact_key, "value": prior.value},
            ["current", "archive"],
        )
        return prior

    def add_edge(
        self,
        rel_type: str,
        source: str,
        target: str,
        t: int,
        obs_id: str,
        prov: str,
        edge_id: Optional[str] = None,
    ) -> Optional[GraphEdge]:
        if not self.enable_graph:
            return None
        eid = edge_id or self._rid("edge")
        edge = GraphEdge(
            edge_id=eid,
            rel_type=rel_type,
            source_id=source,
            target_id=target,
            valid_from=t if self.enable_temporal_validity else 0,
            valid_to=None,
            provenance_id=prov,
            observation_id=obs_id,
        )
        self.graph.upsert_edge(edge)
        self._link_prov(eid, prov, obs_id, "current", t)
        self._log(LifecycleOp.INSERT, t, obs_id, {"edge_id": eid, "rel": rel_type}, ["graph"])
        return edge

    def terminate_edge(self, edge_id: str, t: int, obs_id: str) -> None:
        if not self.enable_graph:
            return
        self.graph.terminate(edge_id, t if self.enable_temporal_validity else t)
        self._log(LifecycleOp.TERMINATE_RELATION, t, obs_id, {"edge_id": edge_id}, ["graph"])

    def detect_conflict(
        self,
        conflict_id: str,
        fact_key: str,
        claim_a: Any,
        claim_b: Any,
        t: int,
        obs_id: str,
        prov: str,
    ) -> Optional[ConflictRecord]:
        if not self.enable_conflict:
            return None
        rec = ConflictRecord(
            conflict_id=conflict_id,
            fact_key=fact_key,
            claim_a=claim_a,
            claim_b=claim_b,
            valid_from=t,
            valid_to=None,
            provenance_id=prov,
            observation_id=obs_id,
        )
        self.conflicts.put(rec)
        self._link_prov(conflict_id, prov, obs_id, "conflict", t)
        self._log(
            LifecycleOp.DETECT_CONFLICT,
            t,
            obs_id,
            {"conflict_id": conflict_id, "a": claim_a, "b": claim_b},
            ["conflict"],
        )
        return rec

    def resolve_conflict(
        self,
        conflict_id: str,
        resolved_value: Any,
        t: int,
        obs_id: str,
        prov: str,
    ) -> Optional[ConflictRecord]:
        if not self.enable_conflict:
            return None
        c = self.conflicts.get(conflict_id)
        if c is None or c.resolved:
            return c
        c.resolved = True
        c.resolved_value = resolved_value
        c.resolution_provenance_id = prov
        c.resolution_observation_id = obs_id
        c.resolution_t = t
        if self.enable_temporal_validity:
            c.valid_to = t
        self._link_prov(conflict_id, prov, obs_id, "transition", t)
        self._log(
            LifecycleOp.RESOLVE_CONFLICT,
            t,
            obs_id,
            {"conflict_id": conflict_id, "value": resolved_value},
            ["conflict"],
        )
        return c

    def temporary_update(
        self,
        fact_key: str,
        temp_value: Any,
        original: Any,
        t: int,
        obs_id: str,
        prov: str,
        mark_id: str,
    ) -> FactRecord:
        """Apply temporary state; keep original in metadata for reversion."""
        cur = self.current.get(fact_key)
        if cur is None:
            rec = self.insert(
                fact_key,
                temp_value,
                t,
                obs_id,
                prov,
                metadata={"temporary": True, "original": original, "mark_id": mark_id},
            )
        else:
            rec = self.supersede(
                fact_key,
                temp_value,
                t,
                obs_id,
                prov,
                metadata={"temporary": True, "original": original, "mark_id": mark_id},
            )
        self._log(LifecycleOp.UPDATE, t, obs_id, {"temporary": True, "mark_id": mark_id}, ["current"])
        return rec

    def revert(self, mark_id: str, t: int, obs_id: str, prov: str) -> Optional[FactRecord]:
        for rec in self.current.items():
            if rec.metadata.get("mark_id") == mark_id and rec.metadata.get("temporary"):
                original = rec.metadata.get("original")
                return self.supersede(
                    rec.fact_key,
                    original,
                    t,
                    obs_id,
                    prov,
                    metadata={"reverted_from": mark_id},
                )
        self._log(LifecycleOp.REVERT, t, obs_id, {"mark_id": mark_id, "status": "miss"}, [])
        return None

    def promote(self, t: int, obs_id: str, detail: dict) -> None:
        """Explicit promotion marker (session→durable); already durable on insert for smoke."""
        self._log(LifecycleOp.PROMOTE, t, obs_id, detail, ["current"])

    def check_invariants(self) -> list[str]:
        errors: list[str] = []
        # exclusive uniqueness in current
        seen = {}
        for r in self.current.items():
            if r.exclusive:
                if r.fact_key in seen:
                    errors.append(f"duplicate exclusive current {r.fact_key}")
                seen[r.fact_key] = r.record_id
            if not r.provenance_id:
                errors.append(f"active fact missing provenance {r.record_id}")
            if r.valid_to is not None:
                errors.append(f"active fact has valid_to set {r.record_id}")
        if self.enable_archive:
            for r in self.archive.all_records():
                if not r.provenance_id:
                    errors.append(f"archived fact missing provenance {r.record_id}")
                if self.enable_temporal_validity and r.valid_to is None and r.status == "superseded":
                    errors.append(f"superseded without valid_to {r.record_id}")
        # unresolved conflicts must not appear as definitive current values for same key
        if self.enable_conflict:
            for c in self.conflicts.unresolved():
                cur = self.current.get(c.fact_key)
                if cur and cur.value in (c.claim_a, c.claim_b) and cur.metadata.get("from_conflict"):
                    errors.append(f"unresolved conflict exposed as definitive {c.conflict_id}")
        return errors
