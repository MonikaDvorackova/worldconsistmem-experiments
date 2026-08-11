"""Historical archive store."""

from __future__ import annotations

from typing import Optional

from .models import FactRecord


class ArchiveStore:
    """Superseded / terminated assertions with validity intervals."""

    def __init__(self) -> None:
        self._records: dict[str, FactRecord] = {}
        self._by_key: dict[str, list[str]] = {}

    def add(self, rec: FactRecord) -> None:
        self._records[rec.record_id] = rec
        self._by_key.setdefault(rec.fact_key, []).append(rec.record_id)

    def get(self, record_id: str) -> Optional[FactRecord]:
        return self._records.get(record_id)

    def for_key(self, fact_key: str) -> list[FactRecord]:
        return [self._records[i] for i in self._by_key.get(fact_key, []) if i in self._records]

    def at_time(self, fact_key: str, t: int) -> Optional[FactRecord]:
        cands = [r for r in self.for_key(fact_key) if r.active_at(t)]
        if not cands:
            return None
        return sorted(cands, key=lambda r: r.valid_from)[-1]

    def all_records(self) -> list[FactRecord]:
        return list(self._records.values())

    def __len__(self) -> int:
        return len(self._records)
