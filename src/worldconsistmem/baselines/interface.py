"""Common baseline adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from ..models import Observation, Prediction, Query, QueryBundle


ABSTAIN_TOKEN = "__ABSTAIN__"
ABSTAIN = {"__abstain__": True, "reason": "unsupported_or_insufficient_evidence"}


def abstain_answer(reason: str = "unsupported_or_insufficient_evidence"):
    """Scalar-safe abstention token (dicts break set membership in constraints)."""
    return ABSTAIN_TOKEN



@dataclass
class AnswerResult:
    answer: Any
    provenance: Optional[str] = None
    retrieved_observation_ids: list[str] = field(default_factory=list)
    retrieval_scores: list[float] = field(default_factory=list)
    status: str = "ok"  # ok | abstain | unsupported | error
    detail: str = ""


@dataclass
class MemoryDiagnostics:
    memory_size: int = 0
    n_retrieved: int = 0
    latency_ms: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


class BaselineAdapter(ABC):
    """Incremental observation → memory → structured query answering."""

    baseline_id: str = "base"
    run_id: str = "default"

    def reset(self) -> None:
        """Clear memory for a new world."""

    @abstractmethod
    def ingest(self, observation: Observation) -> None:
        """Ingest one observation (caller guarantees timestamp order)."""

    @abstractmethod
    def answer(self, query: Query, as_of_t: Optional[int] = None) -> AnswerResult:
        """Answer a query using only current memory (no gold answers)."""

    def memory_size(self) -> int:
        return 0

    def answer_bundle(self, bundle: QueryBundle) -> list[Prediction]:
        import time

        preds: list[Prediction] = []
        for q in bundle.queries:
            t0 = time.perf_counter()
            # Historical queries must not see future obs — adapters enforce via as_of
            as_of = q.target_time
            result = self.answer(q, as_of_t=as_of)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            preds.append(
                Prediction(
                    bundle_id=bundle.bundle_id,
                    query_id=q.query_id,
                    predicted_answer=result.answer,
                    predicted_provenance=result.provenance,
                    system_id=self.baseline_id,
                    run_id=self.run_id,
                    metadata={
                        "retrieved_observation_ids": list(result.retrieved_observation_ids),
                        "retrieval_scores": list(result.retrieval_scores),
                        "memory_state_size": self.memory_size(),
                        "latency_ms": latency_ms,
                        "status": result.status,
                        "detail": result.detail,
                        "n_retrieved": len(result.retrieved_observation_ids),
                    },
                )
            )
        return preds
