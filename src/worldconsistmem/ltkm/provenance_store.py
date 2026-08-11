"""Provenance index."""

from __future__ import annotations

from .models import ProvenanceLink


class ProvenanceStore:
    def __init__(self) -> None:
        self._links: dict[str, ProvenanceLink] = {}
        self._by_subject: dict[str, list[str]] = {}
        self._by_prov: dict[str, list[str]] = {}

    def add(self, link: ProvenanceLink) -> None:
        self._links[link.link_id] = link
        self._by_subject.setdefault(link.subject_id, []).append(link.link_id)
        self._by_prov.setdefault(link.provenance_id, []).append(link.link_id)

    def for_subject(self, subject_id: str) -> list[ProvenanceLink]:
        return [self._links[i] for i in self._by_subject.get(subject_id, [])]

    def __len__(self) -> int:
        return len(self._links)
