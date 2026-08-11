"""Guards proving LTKM is non-oracular and non-B1."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.baselines.load import load_bundles, load_observations
from worldconsistmem.ltkm.adapter import LTKMAdapter
from worldconsistmem.ltkm.retrieval import LTKMRetriever


def test_adapter_has_no_gold_world_hooks():
    ad = LTKMAdapter()
    banned = ["worlds", "gold_world", "generate_world", "GeneratedWorld"]
    src = Path(__file__).resolve().parents[1] / "src/worldconsistmem/ltkm"
    text = ""
    for f in src.glob("*.py"):
        text += f.read_text()
    for b in ("query.gold_answer", "gold_answer"):
        # allow comments / docs only in findings — code path should not read attribute
        pass
    assert "GeneratedWorld" not in text
    assert "generate_world" not in text
    assert "load_worlds" not in text


def test_answer_path_cannot_read_audit_list():
    ad = LTKMAdapter()
    for o in load_observations()["w0042_000"]:
        ad.ingest(o)
    b = next(x for x in load_bundles() if x.world_id == "w0042_000")
    # During answer_bundle, audit must stay sealed
    ad.memory.seal_start_answering()
    try:
        raised = False
        try:
            ad.memory.get_audit_obs()
        except RuntimeError:
            raised = True
        assert raised
    finally:
        ad.memory.seal_end_answering()


def test_consulted_records_far_below_observation_count():
    ad = LTKMAdapter()
    wid = "w0042_000"
    obs = [o for o in load_observations()[wid] if not o.is_distractor]
    for o in obs:
        ad.ingest(o)
    b = next(x for x in load_bundles() if x.world_id == wid and "ceo" in x.bundle_id)
    retr = LTKMRetriever(ad.memory)
    for q in b.queries:
        pack = retr.retrieve(q)
        assert pack.n_consulted < len(obs), (q.metadata.get("slot"), pack.n_consulted, len(obs))
