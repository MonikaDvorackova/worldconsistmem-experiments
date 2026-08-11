#!/usr/bin/env python3
"""Generate scaled WorldConsistMem dataset under data/scaled/ (smoke untouched)."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.io_util import write_json, write_jsonl
from worldconsistmem.observe import generate_observations
from worldconsistmem.scaled_generate import TIERS, generate_scaled_dataset
from worldconsistmem.scaled_queries import generate_scaled_bundles

OUT = ROOT / "data" / "scaled"
SEED = 100
WORLDS_PER_TIER = 34


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    worlds = generate_scaled_dataset(seed=SEED, worlds_per_tier=WORLDS_PER_TIER)
    all_obs = []
    all_bundles = []
    world_rows = []
    for w in worlds:
        write_json(
            OUT / "worlds" / f"{w.world_id}.json",
            {
                "world_id": w.world_id,
                "seed": w.seed,
                "world_idx": w.world_idx,
                "meta": w.meta,
                "n_events": len(w.events),
                "T": w.T,
                "events": [e.to_dict() for e in w.events],
            },
        )
        obs = generate_observations(w, include_distractors=True)
        all_obs.extend([o.to_dict() for o in obs])
        bundles = generate_scaled_bundles(w)
        all_bundles.extend([b.to_dict() for b in bundles])
        world_rows.append(
            {
                "world_id": w.world_id,
                "seed": w.seed,
                "tier": w.meta["tier"],
                "n_events": len(w.events),
                "n_bundles": len(bundles),
                "n_queries": sum(len(b.queries) for b in bundles),
                "difficulties": Counter(
                    b.metadata.get("difficulty") for b in bundles
                ),
            }
        )

    write_jsonl(OUT / "observations.jsonl", all_obs)
    write_jsonl(OUT / "bundles.jsonl", all_bundles)

    # checksum over worlds+obs+bundles (scaled only)
    h = hashlib.sha256()
    for path in sorted((OUT / "worlds").glob("*.json")):
        h.update(path.read_bytes())
    h.update((OUT / "observations.jsonl").read_bytes())
    h.update((OUT / "bundles.jsonl").read_bytes())
    digest = h.hexdigest()

    n_q = sum(r["n_queries"] for r in world_rows)
    n_b = sum(r["n_bundles"] for r in world_rows)
    tier_counts = Counter(r["tier"] for r in world_rows)
    manifest = {
        "seed_base": SEED,
        "worlds_per_tier": WORLDS_PER_TIER,
        "n_worlds": len(worlds),
        "n_bundles": n_b,
        "n_queries": n_q,
        "tiers": dict(tier_counts),
        "tier_targets": {k: v.target_events for k, v in TIERS.items()},
        "sha256": digest,
        "smoke_untouched": True,
    }
    write_json(OUT / "manifest.json", manifest)
    write_json(OUT / "world_index.json", world_rows)
    print(json.dumps(manifest, indent=2))
    assert len(worlds) >= 100
    assert all(tier_counts[t] >= 25 for t in ("small", "medium", "large"))
    assert n_q >= 6000
    assert all(r["n_bundles"] >= 10 for r in world_rows)


if __name__ == "__main__":
    main()
