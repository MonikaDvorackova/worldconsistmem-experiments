"""Evaluate a predictions JSONL against smoke (or provided) bundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worldconsistmem.evaluate import evaluate_predictions, load_prediction_rows
from worldconsistmem.generate import generate_worlds
from worldconsistmem.io_util import read_jsonl, write_json
from worldconsistmem.models import Query, QueryBundle, QueryFamily, AnswerSchema, ConstraintFamily
from worldconsistmem.queries import generate_bundles


def _bundle_from_dict(row: dict) -> QueryBundle:
    queries = []
    for q in row["queries"]:
        queries.append(
            Query(
                query_id=q["query_id"],
                bundle_id=q["bundle_id"],
                family=QueryFamily(q["family"]),
                text=q["text"],
                structured=q["structured"],
                target_time=q.get("target_time"),
                target_interval=None,
                gold_answer=q["gold_answer"],
                answer_schema=AnswerSchema(q["answer_schema"]),
                applicable_constraints=[ConstraintFamily(c) for c in q["applicable_constraints"]],
                supporting_event_ids=q["supporting_event_ids"],
                supporting_provenance_ids=q["supporting_provenance_ids"],
                metadata=q.get("metadata") or {},
            )
        )
    return QueryBundle(
        bundle_id=row["bundle_id"],
        world_id=row["world_id"],
        focal_entities=row["focal_entities"],
        queries=queries,
        description=row.get("description", ""),
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", required=True)
    p.add_argument("--bundles", default=str(ROOT / "data/smoke/query_bundles.jsonl"))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-worlds", type=int, default=25)
    p.add_argument("--out", default=str(ROOT / "results/eval_metrics.json"))
    args = p.parse_args()

    worlds = {w.world_id: w for w in generate_worlds(args.seed, args.n_worlds)}
    bundles = [_bundle_from_dict(r) for r in read_jsonl(args.bundles)]
    preds = load_prediction_rows(read_jsonl(args.predictions))
    _, agg, viols = evaluate_predictions(worlds, bundles, preds)
    write_json(args.out, {"metrics": agg.to_dict(), "n_violations": len(viols)})
    print(json.dumps(agg.to_dict(), indent=2))


if __name__ == "__main__":
    main()
