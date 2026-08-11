"""Capacity-matched flat structured memory (B1 variants)."""

from __future__ import annotations

import json
import random
from typing import Literal, Optional

from ..models import Observation, Query
from .adapters import FlatAppendMemory
from .interface import AnswerResult
from .reader import StructuredReader

EvictionPolicy = Literal["recency", "reservoir", "compact_padding"]

_PADDING_TYPES = frozenset({"location_change", "project_status_change"})


class CapacityFlatMemory(FlatAppendMemory):
    """B1 with hard logical-record budget (1 observation = 1 record).

    No hidden overflow: discarded observations are gone.
    """

    baseline_id = "B1_flat_capacity"

    def __init__(
        self,
        capacity: int,
        policy: EvictionPolicy = "recency",
        seed: int = 0,
        run_id: Optional[str] = None,
    ):
        super().__init__(run_id=run_id or f"flat_cap{capacity}_{policy}")
        self.capacity = capacity
        self.policy = policy
        self.seed = seed
        self.baseline_id = f"B1_flat_cap{capacity}_{policy}"
        self._rng = random.Random(seed)
        self._seen = 0
        self._evicted = 0

    def reset(self) -> None:
        super().reset()
        self._rng = random.Random(self.seed)
        self._seen = 0
        self._evicted = 0

    def ingest(self, observation: Observation) -> None:
        if observation.is_distractor:
            return
        self._seen += 1
        if self.policy == "reservoir":
            if len(self._obs) < self.capacity:
                self._obs.append(observation)
                return
            j = self._rng.randint(1, self._seen)
            if j <= self.capacity:
                self._obs[j - 1] = observation
                self._evicted += 1
            else:
                self._evicted += 1
            return

        self._obs.append(observation)
        self._enforce()

    def _enforce(self) -> None:
        while len(self._obs) > self.capacity:
            if self.policy == "compact_padding":
                pad_idxs = [
                    i
                    for i, o in enumerate(self._obs)
                    if (o.structured.get("event_type") or "") in _PADDING_TYPES
                ]
                if pad_idxs:
                    self._obs.pop(pad_idxs[0])
                    self._evicted += 1
                    continue
            # recency (and compact fallback): drop oldest
            self._obs.pop(0)
            self._evicted += 1

    def memory_size(self) -> int:
        return len(self._obs)

    def serialized_bytes(self) -> int:
        blob = [o.to_dict() for o in self._obs]
        return len(json.dumps(blob, sort_keys=True).encode())

    def answer(self, query: Query, as_of_t: Optional[int] = None) -> AnswerResult:
        result = self.reader.answer(query, self._obs, as_of_t=as_of_t)
        # annotate capacity diagnostics via detail (adapter metadata fills elsewhere)
        if result.detail:
            result.detail = f"{result.detail}|cap={self.capacity}|evicted={self._evicted}"
        return result
