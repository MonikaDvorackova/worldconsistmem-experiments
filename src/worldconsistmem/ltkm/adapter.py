"""LTKM baseline adapter (BaselineAdapter-compatible)."""

from __future__ import annotations

import time
from typing import Optional

from ..baselines.interface import AnswerResult, BaselineAdapter
from ..models import Observation, Prediction, Query, QueryBundle
from .memory import HierarchicalMemory, LTKMConfig
from .reader import LTKMReader


class LTKMAdapter(BaselineAdapter):
    baseline_id = "H0_ltkm"

    def __init__(self, config: Optional[LTKMConfig] = None):
        self.config = config or LTKMConfig()
        self.baseline_id = self.config.system_id
        self.run_id = self.config.run_id
        self.memory = HierarchicalMemory(self.config)
        self.reader = LTKMReader(self.memory)

    def reset(self) -> None:
        self.memory = HierarchicalMemory(self.config)
        self.reader = LTKMReader(self.memory)

    def ingest(self, observation: Observation) -> None:
        self.memory.ingest(observation)

    def memory_size(self) -> int:
        return self.memory.logical_record_count()

    def answer(self, query: Query, as_of_t: Optional[int] = None) -> AnswerResult:
        return self.reader.answer(query)

    def answer_bundle(self, bundle: QueryBundle) -> list[Prediction]:
        preds: list[Prediction] = []
        for q in bundle.queries:
            t0 = time.perf_counter()
            result = self.answer(q, as_of_t=q.target_time)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            snap = self.memory.resource_snapshot()
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
                        "n_consulted_records": len(result.retrieved_observation_ids),
                        "resource": snap,
                    },
                )
            )
        return preds


def make_ablation(name: str) -> LTKMAdapter:
    cfg = LTKMConfig(system_id=name, run_id=name)
    if name in ("H_minus_archive", "H-archive"):
        cfg.enable_archive = False
        cfg.system_id = "H-archive"
    elif name in ("H_minus_graph", "H-graph"):
        cfg.enable_graph = False
        cfg.system_id = "H-graph"
    elif name in ("H_minus_provenance", "H-provenance"):
        cfg.enable_provenance = False
        cfg.system_id = "H-provenance"
    elif name in ("H_minus_conflict", "H-conflict"):
        cfg.enable_conflict = False
        cfg.system_id = "H-conflict"
    elif name in ("H_minus_temporal", "H-temporal-validity"):
        cfg.enable_temporal_validity = False
        cfg.system_id = "H-temporal-validity"
    elif name in ("H0_ltkm", "H0"):
        cfg.system_id = "H0_ltkm"
    else:
        raise ValueError(name)
    cfg.run_id = cfg.system_id
    return LTKMAdapter(cfg)
