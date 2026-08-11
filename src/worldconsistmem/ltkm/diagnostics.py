"""Diagnostics helpers for LTKM anti-triviality and resources."""

from __future__ import annotations

from typing import Any

from .memory import HierarchicalMemory
from .retrieval import STORE_ROUTING


def assert_no_raw_scan_in_answer_path(memory: HierarchicalMemory) -> None:
    memory.seal_start_answering()
    try:
        try:
            memory.get_audit_obs()
            raise AssertionError("raw obs readable during answering")
        except RuntimeError:
            pass
    finally:
        memory.seal_end_answering()


def store_routing_table() -> dict[str, list[str]]:
    return dict(STORE_ROUTING)


def summarize_resources(snap: dict[str, Any]) -> str:
    return (
        f"current={snap['n_current']} archive={snap['n_archive']} "
        f"graph={snap['n_graph_edges']} prov={snap['n_provenance']} "
        f"conflicts={snap['n_conflicts']} logical={snap['logical_records']} "
        f"bytes≈{snap['serialized_bytes']}"
    )
