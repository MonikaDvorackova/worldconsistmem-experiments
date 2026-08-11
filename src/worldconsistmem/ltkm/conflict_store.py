"""Conflict and unresolved-claim store."""

from __future__ import annotations

from typing import Optional

from .models import ConflictRecord


class ConflictStore:
    def __init__(self) -> None:
        self._by_id: dict[str, ConflictRecord] = {}

    def put(self, rec: ConflictRecord) -> None:
        self._by_id[rec.conflict_id] = rec

    def get(self, conflict_id: str) -> Optional[ConflictRecord]:
        return self._by_id.get(conflict_id)

    def unresolved(self, t: Optional[int] = None) -> list[ConflictRecord]:
        out = []
        for c in self._by_id.values():
            if c.resolved:
                continue
            if t is not None and (t < c.valid_from or (c.valid_to is not None and t >= c.valid_to)):
                continue
            out.append(c)
        return out

    def all(self) -> list[ConflictRecord]:
        return list(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)
