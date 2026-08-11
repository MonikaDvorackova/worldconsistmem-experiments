"""Regression: ownership-transfer observations must expose the prior owner."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.generate import generate_world
from worldconsistmem.models import EventType
from worldconsistmem.observe import generate_observations
from worldconsistmem.baselines.reader import StructuredReader, filter_observations
from worldconsistmem.queries import generate_bundles


def test_ownership_transfer_exposes_prior_owner():
    w = generate_world(42, 0)
    ev = next(e for e in w.events if e.event_type == EventType.PROJECT_OWNERSHIP_TRANSFER)
    assert "old_org_id" in ev.payload
    assert ev.payload["old_org_id"] != ev.payload["new_org_id"]
    assert ev.payload["old_org_id"] in ev.affected_ids

    obs = generate_observations(w, include_distractors=False)
    reader = StructuredReader()
    bundles = generate_bundles(w)
    own = next(b for b in bundles if "own" in b.bundle_id)
    for q in own.queries:
        if q.metadata.get("slot") in ("owner_historical", "owner_transition"):
            r = reader.answer(q, obs, as_of_t=q.target_time)
            assert r.status == "ok", f"{q.metadata.get('slot')} abstained: {r.detail}"
            assert r.answer == q.gold_answer
