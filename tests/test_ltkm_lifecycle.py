"""LTKM lifecycle operation tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.ltkm.lifecycle import LifecycleEngine
from worldconsistmem.ltkm.archive_store import ArchiveStore
from worldconsistmem.ltkm.conflict_store import ConflictStore
from worldconsistmem.ltkm.current_store import CurrentStore
from worldconsistmem.ltkm.graph_store import GraphStore
from worldconsistmem.ltkm.provenance_store import ProvenanceStore
from worldconsistmem.ltkm.models import LifecycleOp


def _engine():
    return LifecycleEngine(
        CurrentStore(), ArchiveStore(), GraphStore(), ProvenanceStore(), ConflictStore()
    )


def test_insert_supersede_archive_chain():
    eng = _engine()
    a = eng.insert("k|role|CEO", "p0", 1, "obs1", "prov1")
    b = eng.supersede("k|role|CEO", "p1", 5, "obs5", "prov5")
    assert eng.current.get("k|role|CEO").value == "p1"
    assert a.valid_to == 5
    assert eng.archive.at_time("k|role|CEO", 2).value == "p0"
    assert b.predecessor_id == a.record_id
    ops = [r.op for r in eng.log]
    assert LifecycleOp.INSERT in ops
    assert LifecycleOp.SUPERSEDE in ops
    assert LifecycleOp.ARCHIVE in ops


def test_conflict_detect_resolve():
    eng = _engine()
    eng.detect_conflict("c1", "subj|attr|", "A", "B", 3, "o3", "p3")
    assert eng.conflicts.unresolved()
    eng.resolve_conflict("c1", "A", 7, "o7", "p7")
    assert eng.conflicts.get("c1").resolved
    assert eng.conflicts.get("c1").resolved_value == "A"
    assert not eng.conflicts.unresolved()


def test_reversion():
    eng = _engine()
    eng.insert("proj|project_status|", "planned", 1, "o1", "p1")
    eng.temporary_update("proj|project_status|", "paused", "planned", 4, "o4", "p4", "mark1")
    assert eng.current.get("proj|project_status|").value == "paused"
    eng.revert("mark1", 8, "o8", "p8")
    assert eng.current.get("proj|project_status|").value == "planned"


def test_graph_terminate():
    eng = _engine()
    e = eng.add_edge("member_of", "p0", "org0", 1, "o1", "p1", edge_id="e1")
    assert e is not None
    eng.terminate_edge("e1", 4, "o4")
    assert eng.graph.edges()[0].valid_to == 4
