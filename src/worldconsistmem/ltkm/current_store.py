"""Current-state store."""

from __future__ import annotations

from typing import Optional

from .models import FactRecord


class CurrentStore:
    """One active exclusive value per fact key (unresolved conflicts excluded)."""

    def __init__(self) -> None:
        self._by_key: dict[str, FactRecord] = {}

    def get(self, fact_key: str) -> Optional[FactRecord]:
        return self._by_key.get(fact_key)

    def put(self, rec: FactRecord) -> None:
        self._by_key[rec.fact_key] = rec

    def remove(self, fact_key: str) -> Optional[FactRecord]:
        return self._by_key.pop(fact_key, None)

    def items(self) -> list[FactRecord]:
        return list(self._by_key.values())

    def __len__(self) -> int:
        return len(self._by_key)
