"""Core data models for WorldConsistMem."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    PERSON_JOINS_ORG = "person_joins_org"
    PERSON_LEAVES_ORG = "person_leaves_org"
    ROLE_ASSIGNMENT = "role_assignment"
    ROLE_REPLACEMENT = "role_replacement"
    PROJECT_OWNERSHIP_TRANSFER = "project_ownership_transfer"
    PROJECT_STATUS_CHANGE = "project_status_change"
    DOCUMENT_CREATION = "document_creation"
    DOCUMENT_REVISION = "document_revision"
    DOCUMENT_APPROVAL = "document_approval"
    LOCATION_CHANGE = "location_change"
    RELATIONSHIP_CREATION = "relationship_creation"
    RELATIONSHIP_TERMINATION = "relationship_termination"
    CONFLICT_INTRODUCTION = "conflict_introduction"
    CONFLICT_RESOLUTION = "conflict_resolution"
    TEMPORARY_STATE = "temporary_state"
    REVERSION = "reversion"


class QueryFamily(str, Enum):
    CURRENT_STATE = "current_state"
    HISTORICAL_STATE = "historical_state"
    TRANSITION = "transition"
    CONFLICT_VALIDITY = "conflict_validity"
    MULTI_HOP = "multi_hop"
    PROVENANCE = "provenance"
    TEMPORAL_ORDER = "temporal_order"
    CONTRADICTION = "contradiction"
    COUNTERFACTUAL = "counterfactual"


class ConstraintFamily(str, Enum):
    UNIQUENESS = "uniqueness"
    TEMPORAL = "temporal"
    TRANSITION = "transition"
    RELATIONAL = "relational"
    PROVENANCE = "provenance"
    MULTI_HOP = "multi_hop"
    CONTRADICTION = "contradiction"


class AnswerSchema(str, Enum):
    ENTITY_ID = "entity_id"
    SCALAR = "scalar"
    BOOLEAN = "boolean"
    ORDERED_LIST = "ordered_list"
    INTERVAL = "interval"
    TRANSITION_TUPLE = "transition_tuple"
    PROVENANCE_ID = "provenance_id"
    ENTITY_PAIR = "entity_pair"


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj


@dataclass
class Interval:
    start: int
    end: Optional[int] = None  # None = open / current

    def contains(self, t: int) -> bool:
        if t < self.start:
            return False
        if self.end is None:
            return True
        return t < self.end

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}


@dataclass
class Employment:
    person_id: str
    org_id: str
    interval: Interval
    provenance_id: str

    def to_dict(self) -> dict:
        return {
            "person_id": self.person_id,
            "org_id": self.org_id,
            "interval": self.interval.to_dict(),
            "provenance_id": self.provenance_id,
        }


@dataclass
class RoleHolder:
    person_id: str
    org_id: str
    role: str
    exclusive: bool
    interval: Interval
    provenance_id: str

    def to_dict(self) -> dict:
        return {
            "person_id": self.person_id,
            "org_id": self.org_id,
            "role": self.role,
            "exclusive": self.exclusive,
            "interval": self.interval.to_dict(),
            "provenance_id": self.provenance_id,
        }


@dataclass
class ProjectOwnership:
    project_id: str
    org_id: str
    interval: Interval
    provenance_id: str

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "org_id": self.org_id,
            "interval": self.interval.to_dict(),
            "provenance_id": self.provenance_id,
        }


@dataclass
class Relationship:
    rel_id: str
    rel_type: str
    source_id: str
    target_id: str
    interval: Interval
    provenance_id: str

    def to_dict(self) -> dict:
        return {
            "rel_id": self.rel_id,
            "rel_type": self.rel_type,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "interval": self.interval.to_dict(),
            "provenance_id": self.provenance_id,
        }


@dataclass
class ConflictClaim:
    conflict_id: str
    subject: str
    attribute: str
    value_a: Any
    value_b: Any
    interval: Interval
    resolved: bool
    resolved_value: Optional[Any]
    provenance_id: str
    resolution_provenance_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "conflict_id": self.conflict_id,
            "subject": self.subject,
            "attribute": self.attribute,
            "value_a": self.value_a,
            "value_b": self.value_b,
            "interval": self.interval.to_dict(),
            "resolved": self.resolved,
            "resolved_value": self.resolved_value,
            "provenance_id": self.provenance_id,
            "resolution_provenance_id": self.resolution_provenance_id,
        }


@dataclass
class TemporaryMark:
    mark_id: str
    entity_id: str
    attribute: str
    temporary_value: Any
    original_value: Any
    interval: Interval
    reverted: bool
    provenance_id: str
    reversion_provenance_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "mark_id": self.mark_id,
            "entity_id": self.entity_id,
            "attribute": self.attribute,
            "temporary_value": self.temporary_value,
            "original_value": self.original_value,
            "interval": self.interval.to_dict(),
            "reverted": self.reverted,
            "provenance_id": self.provenance_id,
            "reversion_provenance_id": self.reversion_provenance_id,
        }


@dataclass
class Person:
    person_id: str
    name: str
    location_id: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Organization:
    org_id: str
    name: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Project:
    project_id: str
    name: str
    status: str
    manager_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Document:
    doc_id: str
    title: str
    project_id: str
    version: int
    author_id: str
    approved: bool = False
    approved_by: Optional[str] = None
    canonical: bool = True
    provenance_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Location:
    location_id: str
    name: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Event:
    event_id: str
    event_type: EventType
    t: int
    actor_id: Optional[str]
    affected_ids: list[str]
    payload: dict[str, Any]
    preconditions: list[str]
    provenance_id: str
    narrative: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d


@dataclass
class Observation:
    observation_id: str
    event_id: str
    t: int
    provenance_id: str
    structured: dict[str, Any]
    text_canonical: str
    text_paraphrase: str
    is_distractor: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Query:
    query_id: str
    bundle_id: str
    family: QueryFamily
    text: str
    structured: dict[str, Any]
    target_time: Optional[int]
    target_interval: Optional[Interval]
    gold_answer: Any
    answer_schema: AnswerSchema
    applicable_constraints: list[ConstraintFamily]
    supporting_event_ids: list[str]
    supporting_provenance_ids: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "bundle_id": self.bundle_id,
            "family": self.family.value,
            "text": self.text,
            "structured": to_jsonable(self.structured),
            "target_time": self.target_time,
            "target_interval": self.target_interval.to_dict() if self.target_interval else None,
            "gold_answer": to_jsonable(self.gold_answer),
            "answer_schema": self.answer_schema.value,
            "applicable_constraints": [c.value for c in self.applicable_constraints],
            "supporting_event_ids": list(self.supporting_event_ids),
            "supporting_provenance_ids": list(self.supporting_provenance_ids),
            "metadata": to_jsonable(self.metadata),
        }


@dataclass
class QueryBundle:
    bundle_id: str
    world_id: str
    focal_entities: list[str]
    queries: list[Query]
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "bundle_id": self.bundle_id,
            "world_id": self.world_id,
            "focal_entities": list(self.focal_entities),
            "description": self.description,
            "queries": [q.to_dict() for q in self.queries],
            "metadata": to_jsonable(self.metadata),
        }


@dataclass
class Prediction:
    bundle_id: str
    query_id: str
    predicted_answer: Any
    predicted_provenance: Optional[Any] = None
    system_id: str = "unknown"
    run_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "bundle_id": self.bundle_id,
            "query_id": self.query_id,
            "predicted_answer": to_jsonable(self.predicted_answer),
            "predicted_provenance": to_jsonable(self.predicted_provenance),
            "system_id": self.system_id,
            "run_id": self.run_id,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass
class ConstraintResult:
    passed: bool
    constraint_type: ConstraintFamily
    constraint_id: str
    involved_query_ids: list[str]
    involved_predicted_values: dict[str, Any]
    explanation: str
    gold_evidence: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "constraint_type": self.constraint_type.value,
            "constraint_id": self.constraint_id,
            "involved_query_ids": list(self.involved_query_ids),
            "involved_predicted_values": to_jsonable(self.involved_predicted_values),
            "explanation": self.explanation,
            "gold_evidence": to_jsonable(self.gold_evidence),
        }
