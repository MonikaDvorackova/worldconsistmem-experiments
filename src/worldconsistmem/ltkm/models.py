"""LTKM core record types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class LifecycleOp(str, Enum):
    INSERT = "insert"
    PROMOTE = "promote"
    UPDATE = "update"
    DETECT_CONFLICT = "detect_conflict"
    SUPERSEDE = "supersede"
    ARCHIVE = "archive"
    RESOLVE_CONFLICT = "resolve_conflict"
    TERMINATE_RELATION = "terminate_relation"
    REVERT = "revert"
    RETRIEVE = "retrieve"


@dataclass
class FactKey:
    entity_id: str
    attribute: str
    scope: str = ""  # e.g. org_id, project_id, role name

    def key(self) -> str:
        return f"{self.entity_id}|{self.attribute}|{self.scope}"


@dataclass
class FactRecord:
    record_id: str
    fact_key: str
    value: Any
    valid_from: int
    valid_to: Optional[int]  # None = open
    observation_id: str
    provenance_id: str
    status: str = "active"  # active | archived | superseded | temporary
    predecessor_id: Optional[str] = None
    successor_id: Optional[str] = None
    exclusive: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def active_at(self, t: int) -> bool:
        if t < self.valid_from:
            return False
        if self.valid_to is None:
            return True
        return t < self.valid_to

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    edge_id: str
    rel_type: str
    source_id: str
    target_id: str
    valid_from: int
    valid_to: Optional[int]
    provenance_id: str
    observation_id: str
    status: str = "active"

    def active_at(self, t: int) -> bool:
        if t < self.valid_from:
            return False
        if self.valid_to is None:
            return True
        return t < self.valid_to

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConflictRecord:
    conflict_id: str
    fact_key: str
    claim_a: Any
    claim_b: Any
    valid_from: int
    valid_to: Optional[int]
    provenance_id: str
    observation_id: str
    resolved: bool = False
    resolved_value: Optional[Any] = None
    resolution_provenance_id: Optional[str] = None
    resolution_observation_id: Optional[str] = None
    resolution_t: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProvenanceLink:
    link_id: str
    subject_id: str  # fact/edge/conflict/transition id
    provenance_id: str
    observation_id: str
    kind: str  # current | historical | version | transition | conflict
    t: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LifecycleRecord:
    op: LifecycleOp
    t: int
    observation_id: str
    detail: dict[str, Any]
    affected_stores: list[str]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["op"] = self.op.value
        return d
