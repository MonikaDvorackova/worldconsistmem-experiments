"""Scaled bundle generation with difficulty labels (extends smoke query builders)."""

from __future__ import annotations

from typing import Any

from .generate import GeneratedWorld
from .models import QueryBundle
from .queries import (
    _ceo_bundle,
    _conflict_bundle,
    _document_bundle,
    _employment_bundle,
    _ownership_bundle,
)


def _bundle_axes(bundle: QueryBundle, world: GeneratedWorld) -> dict[str, Any]:
    qs = bundle.queries
    entities = set(bundle.focal_entities)
    for q in qs:
        for v in q.structured.values():
            if isinstance(v, str) and ":" in v:
                entities.add(v)
    times = [q.target_time for q in qs if q.target_time is not None]
    temporal_dist = (max(times) - min(times)) if len(times) >= 2 else 0
    families = {q.family.value for q in qs}
    constraints = {c.value for q in qs for c in q.applicable_constraints}
    multi_hop = sum(1 for q in qs if q.family.value == "multi_hop")
    hist = sum(1 for q in qs if q.family.value == "historical_state")
    conflict = sum(1 for q in qs if "conflict" in q.family.value or "contradiction" in q.family.value)
    transition_chain = world.meta.get("n_ceo_replacements", 1) + world.meta.get(
        "n_ownership_transfers", 1
    )
    prov_competing = world.meta.get("n_doc_revisions", 1) + world.meta.get("n_conflicts", 1)
    return {
        "n_dependent_queries": len(qs),
        "n_involved_entities": len(entities),
        "temporal_distance": temporal_dist,
        "transition_chain_length": transition_chain,
        "multi_hop_depth": multi_hop,
        "n_competing_provenance": prov_competing,
        "n_constraint_families": len(constraints),
        "n_query_families": len(families),
        "has_historical": hist > 0,
        "has_conflict_axis": conflict > 0,
        "unresolved_vs_resolved": world.meta.get("n_conflicts", 0),
    }


def label_difficulty(axes: dict[str, Any], tier: str) -> str:
    """Label by structural axes — not by text length."""
    score = 0
    score += min(3, axes["n_dependent_queries"] // 3)
    score += 1 if axes["temporal_distance"] >= 10 else 0
    score += 1 if axes["temporal_distance"] >= 40 else 0
    score += min(2, axes["transition_chain_length"] // 2)
    score += axes["multi_hop_depth"]
    score += 1 if axes["n_competing_provenance"] >= 3 else 0
    score += 1 if axes["n_constraint_families"] >= 4 else 0
    if tier == "large":
        score += 1
    if score <= 4:
        return "simple"
    if score <= 8:
        return "intermediate"
    return "complex"


def annotate_bundle(bundle: QueryBundle, world: GeneratedWorld) -> QueryBundle:
    axes = _bundle_axes(bundle, world)
    difficulty = label_difficulty(axes, world.meta.get("tier", "small"))
    bundle.metadata = {
        "difficulty": difficulty,
        "tier": world.meta.get("tier"),
        "axes": axes,
    }
    return bundle


def generate_scaled_bundles(world: GeneratedWorld) -> list[QueryBundle]:
    target = int(world.meta.get("target_bundles", 10))
    builders = [
        _ceo_bundle,
        _ownership_bundle,
        _document_bundle,
        _employment_bundle,
        _conflict_bundle,
    ]
    bundles = [annotate_bundle(builders[i](world, i), world) for i in range(len(builders))]
    extras = [_ownership_bundle, _document_bundle, _ceo_bundle, _employment_bundle, _conflict_bundle]
    while len(bundles) < target:
        bi = len(bundles)
        b = extras[bi % len(extras)](world, bi)
        bundles.append(annotate_bundle(b, world))
    return bundles
