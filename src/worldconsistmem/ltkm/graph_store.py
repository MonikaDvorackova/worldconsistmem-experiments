"""Relational graph index."""

from __future__ import annotations

from typing import Optional

from .models import GraphEdge


class GraphStore:
    def __init__(self) -> None:
        self._edges: dict[str, GraphEdge] = {}
        self._nodes: set[str] = set()

    def upsert_edge(self, edge: GraphEdge) -> None:
        self._edges[edge.edge_id] = edge
        self._nodes.add(edge.source_id)
        self._nodes.add(edge.target_id)

    def terminate(self, edge_id: str, end_t: int) -> Optional[GraphEdge]:
        e = self._edges.get(edge_id)
        if e and e.valid_to is None:
            e.valid_to = end_t
            e.status = "terminated"
        return e

    def active_edges(self, rel_type: Optional[str] = None, t: Optional[int] = None) -> list[GraphEdge]:
        out = []
        for e in self._edges.values():
            if rel_type and e.rel_type != rel_type:
                continue
            if t is None:
                if e.valid_to is None:
                    out.append(e)
            elif e.active_at(t):
                out.append(e)
        return out

    def neighbors(self, source_id: str, rel_type: str, t: int) -> list[GraphEdge]:
        return [
            e
            for e in self._edges.values()
            if e.source_id == source_id and e.rel_type == rel_type and e.active_at(t)
        ]

    def edges(self) -> list[GraphEdge]:
        return list(self._edges.values())

    @property
    def n_nodes(self) -> int:
        return len(self._nodes)

    def __len__(self) -> int:
        return len(self._edges)
