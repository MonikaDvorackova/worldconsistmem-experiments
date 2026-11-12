#!/usr/bin/env python3
"""Build the private (git-ignored) input snapshot for the Round 2 analysis.

The frozen F0-F3 raw model outputs and the response-ID -> arm mapping are not
committed to this repository (blinding of human reviewers/adjudicators). This
script copies the minimum needed fields from the frozen experiment directory
into ``analysis/round2/private/`` and records SHA-256 hashes of every source
file so the committed analysis can pin its inputs.

Nothing in the source directories is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "analysis" / "round2" / "private"

ARM_SOURCES = {
    "F0": ("matched_reader_rescue/api_cache.jsonl", "matched_reader_rescue/b4_native_prompts.jsonl"),
    "F1": (
        "final_validation_post_scorer_v2/factorized_ablation/run/api_cache_F1.jsonl",
        "final_validation_post_scorer_v2/factorized_ablation/F1_prompts_exact.jsonl",
    ),
    "F2": (
        "final_validation_post_scorer_v2/factorized_ablation/run/api_cache_F2.jsonl",
        "final_validation_post_scorer_v2/factorized_ablation/F2_prompts_exact.jsonl",
    ),
    "F3": (
        "final_validation_post_scorer_v2/structured_prompt/api_cache.jsonl",
        "final_validation_post_scorer_v2/structured_prompt/structured_prompts_exact.jsonl",
    ),
}
PAIRED_ROWS = "final_validation_post_scorer_v2/structured_prompt/analysis/paired_rows.jsonl"
F3_ONLINE_PREDICTIONS = "final_validation_post_scorer_v2/structured_prompt/predictions.jsonl"
EVIDENCE_RE = re.compile(r"(?:evidence=|Evidence:\n)(\[.*?\])\n", re.S)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirmatory-root", type=Path, required=True,
                    help="Path to results/confirmatory of the frozen experiment tree")
    ap.add_argument("--private-mapping", type=Path, required=True,
                    help="PRIVATE_MAPPING.json produced when the blinded annotation sample was drawn")
    ap.add_argument("--source-manifest", type=Path, default=None,
                    help="Optional SOURCE_MANIFEST.json of the blinded annotation sample")
    args = ap.parse_args()
    root: Path = args.confirmatory_root

    paired = read_jsonl(root / PAIRED_ROWS)
    qids = [r["query_id"] for r in paired]
    if len(qids) != 150 or len(set(qids)) != 150:
        raise SystemExit(f"expected 150 unique transition query ids, got {len(qids)}")
    qset = set(qids)
    sources: dict[str, str] = {PAIRED_ROWS: sha256_file(root / PAIRED_ROWS)}

    # Scores recorded by the frozen experiment (used only to check our re-scoring).
    recorded = {("F0", r["query_id"]): {"v1": r["orig_v1"], "v2": r["orig_v2"]} for r in paired}
    recorded.update({("F3", r["query_id"]): {"v1": r["sp_v1"], "v2": r["sp_v2"]} for r in paired})

    outputs: list[dict] = []
    evidence: dict[str, dict[str, str]] = {q: {} for q in qids}
    for arm, (cache_rel, prompt_rel) in ARM_SOURCES.items():
        sources[cache_rel] = sha256_file(root / cache_rel)
        sources[prompt_rel] = sha256_file(root / prompt_rel)
        prompts = {r["query_id"]: r for r in read_jsonl(root / prompt_rel) if r["query_id"] in qset}
        rows = [r for r in read_jsonl(root / cache_rel) if r["query_id"] in qset]
        if sorted(r["query_id"] for r in rows) != sorted(qids):
            raise SystemExit(f"{arm}: cache does not cover the 150 query ids exactly once")
        for r in rows:
            q = r["query_id"]
            prompt = prompts[q]["prompt"]
            m = EVIDENCE_RE.search(prompt)
            if not m:
                raise SystemExit(f"{arm} {q}: could not locate evidence block in prompt")
            evidence[q][arm] = m.group(1)
            if arm in ("F1", "F2"):
                recorded[(arm, q)] = {"v1": None, "v2": r["correct_v2"]}
            outputs.append({
                "arm": arm,
                "query_id": q,
                "raw_output": r["raw_output"],
                "raw_output_sha256": hashlib.sha256(r["raw_output"].encode("utf-8")).hexdigest(),
                "model_resolved": r.get("model_resolved"),
                "temperature": r.get("temperature"),
                "max_tokens": r.get("max_tokens"),
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "online_status": r.get("status"),
                "online_malformed": r.get("malformed"),
                "recorded_correct_v1": recorded[(arm, q)]["v1"],
                "recorded_correct_v2": recorded[(arm, q)]["v2"],
            })

    packs = []
    orig_suff = {r["query_id"]: r["sufficiency"] for r in paired}
    for q in qids:
        variants = set(evidence[q].values())
        if len(variants) != 1:
            raise SystemExit(f"{q}: evidence block differs across arms")
        packs.append({
            "query_id": q,
            "evidence_json": json.loads(next(iter(variants))),
            "evidence_sha256": hashlib.sha256(next(iter(variants)).encode("utf-8")).hexdigest(),
            "original_sufficiency_label": orig_suff[q],
        })

    sources[F3_ONLINE_PREDICTIONS] = sha256_file(root / F3_ONLINE_PREDICTIONS)
    mapping = json.loads(args.private_mapping.read_text(encoding="utf-8"))

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "f0_f3_frozen_outputs.jsonl").open("w", encoding="utf-8") as fh:
        for row in sorted(outputs, key=lambda r: (r["query_id"], r["arm"])):
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    with (OUT / "evidence_packs.jsonl").open("w", encoding="utf-8") as fh:
        for row in packs:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (OUT / "PRIVATE_MAPPING.json").write_text(json.dumps(mapping, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "confirmatory_root": str(root),
        "source_sha256": sources,
        "private_mapping_sha256": sha256_file(args.private_mapping),
        "n_outputs": len(outputs),
        "n_packs": len(packs),
        "evidence_identical_across_arms": True,
    }
    if args.source_manifest:
        manifest["annotation_source_manifest"] = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    (OUT / "SNAPSHOT_MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(outputs)} outputs and {len(packs)} packs to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
