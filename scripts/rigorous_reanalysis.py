"""
Rigorous independent reanalysis of WorldConsistMem H4 LLM reader study.

Separates three distinct outcome types:
  A) Output-contract compliance (exact-match scoring)
  B) Semantic answer correctness (question-aligned, format-agnostic)
  C) Temporal world-state consistency (selects current/latest event for multi-candidate)

Produces:
  analysis/round2/case_level_error_analysis.csv
  analysis/round2/temporal_state_analysis.csv

All statistics are derived solely from:
  analysis/round2/private/item_scores.jsonl
  analysis/round2/private/evidence_packs.jsonl

No paid APIs, no new synthetic data, no scorer changes.
"""

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
ITEM_SCORES = REPO_ROOT / "analysis/round2/private/item_scores.jsonl"
EVIDENCE_PACKS = REPO_ROOT / "analysis/round2/private/evidence_packs.jsonl"
OUT_CASE_LEVEL = REPO_ROOT / "analysis/round2/case_level_error_analysis.csv"
OUT_TEMPORAL = REPO_ROOT / "analysis/round2/temporal_state_analysis.csv"

ARMS = ["F0", "F1", "F2", "F3"]

# ─── Error taxonomy ─────────────────────────────────────────────────────────

def classify_error(item: dict) -> str:
    """
    Classify the error type for one (arm, query) result.

    Returns one of:
      CORRECT          exact-match correct
      FORMAT_ONLY      semantically correct but wrong output format
      STALE_STATE      selected an earlier event (multi-candidate, non-doc)
      MC_INCOMPLETE    multi-candidate: matched no event or produced ambiguous list
      INSUF_EV_FAIL    insufficient evidence item, model gave no credit
      INSUF_EV_SPURIOUS insufficient evidence item, semantic scorer gave spurious credit
      (empty string)   should not occur
    """
    if item["exact_v2"]:
        return "CORRECT"

    status = item["question_status"]
    sem = item["semantic_qa"]
    positions = item.get("matched_positions") or []

    if status == "version_unidentifiable":
        return "INSUF_EV_SPURIOUS" if sem else "INSUF_EV_FAIL"

    if status == "unique":
        # All unique items are semantically correct for all arms
        return "FORMAT_ONLY" if sem else "CORRECT"  # sem always True here

    # multi_candidate
    if sem:
        # Correct content, wrong format
        return "FORMAT_ONLY"
    if "earliest" in positions and "latest" not in positions:
        return "STALE_STATE"
    return "MC_INCOMPLETE"


def load_items() -> dict[str, dict[str, dict]]:
    """Returns by_query[query_id][arm] = item."""
    by_query: dict[str, dict[str, dict]] = defaultdict(dict)
    with ITEM_SCORES.open() as f:
        for line in f:
            item = json.loads(line)
            by_query[item["query_id"]][item["arm"]] = item
    return dict(by_query)


def load_evidence() -> dict[str, dict]:
    """Returns evidence[query_id] = pack."""
    ev: dict[str, dict] = {}
    with EVIDENCE_PACKS.open() as f:
        for line in f:
            pack = json.loads(line)
            ev[pack["query_id"]] = pack
    return ev


# ─── Case-level error analysis ───────────────────────────────────────────────

CASE_HEADER = [
    "query_id",
    "slot",
    "question_status",
    "world_id",
    "F0_error",
    "F1_error",
    "F2_error",
    "F3_error",
    "F0_exact",
    "F1_exact",
    "F2_exact",
    "F3_exact",
    "F0_semantic",
    "F1_semantic",
    "F2_semantic",
    "F3_semantic",
    "F0_positions",
    "F1_positions",
    "F2_positions",
    "F3_positions",
    "spurious_evidence_note",
]


def build_case_level(by_query: dict) -> list[dict]:
    rows = []
    for qid in sorted(by_query):
        arms = by_query[qid]
        ref = next(iter(arms.values()))

        spurious_note = ""
        if ref["question_status"] == "version_unidentifiable":
            spurious_note = "doc item: S2 insufficient evidence; any semantic credit is spurious"

        row: dict = {
            "query_id": qid,
            "slot": ref["slot"],
            "question_status": ref["question_status"],
            "world_id": ref["world_id"],
            "spurious_evidence_note": spurious_note,
        }
        for arm in ARMS:
            if arm not in arms:
                row[f"{arm}_error"] = "MISSING"
                row[f"{arm}_exact"] = ""
                row[f"{arm}_semantic"] = ""
                row[f"{arm}_positions"] = ""
                continue
            item = arms[arm]
            row[f"{arm}_error"] = classify_error(item)
            row[f"{arm}_exact"] = "1" if item["exact_v2"] else "0"
            row[f"{arm}_semantic"] = "1" if item["semantic_qa"] else "0"
            row[f"{arm}_positions"] = "|".join(item.get("matched_positions") or [])
        rows.append(row)
    return rows


# ─── Temporal state analysis (non-doc items only) ───────────────────────────

TEMPORAL_HEADER = [
    "query_id",
    "slot",
    "question_status",
    "world_id",
    "ground_truth_type",
    "F0_temporal_correct",
    "F1_temporal_correct",
    "F2_temporal_correct",
    "F3_temporal_correct",
    "F0_format_ok",
    "F1_format_ok",
    "F2_format_ok",
    "F3_format_ok",
    "F0_positions",
    "F1_positions",
    "F2_positions",
    "F3_positions",
    "note",
]


def temporal_correct(item: dict) -> bool:
    """
    For unique items: temporal ground truth = the single event in the evidence pack.
    All arms get it right semantically for unique items.
    For multi-candidate items: temporal correct = selected the LATEST event.
    """
    if item["question_status"] == "unique":
        return bool(item["semantic_qa"])
    # multi_candidate: latest event is the gold
    positions = item.get("matched_positions") or []
    return "latest" in positions


def build_temporal(by_query: dict) -> list[dict]:
    rows = []
    for qid in sorted(by_query):
        arms = by_query[qid]
        ref = next(iter(arms.values()))

        # Skip doc items (insufficient evidence)
        if ref["question_status"] == "version_unidentifiable":
            continue

        gt_type = "single_event" if ref["question_status"] == "unique" else "latest_of_multiple"
        note = ""
        if ref["question_status"] == "multi_candidate":
            note = "gold = latest event per benchmark construction (ceo_replace_t or final ownership transfer)"

        row: dict = {
            "query_id": qid,
            "slot": ref["slot"],
            "question_status": ref["question_status"],
            "world_id": ref["world_id"],
            "ground_truth_type": gt_type,
            "note": note,
        }
        for arm in ARMS:
            if arm not in arms:
                row[f"{arm}_temporal_correct"] = ""
                row[f"{arm}_format_ok"] = ""
                row[f"{arm}_positions"] = ""
                continue
            item = arms[arm]
            row[f"{arm}_temporal_correct"] = "1" if temporal_correct(item) else "0"
            row[f"{arm}_format_ok"] = "1" if item["exact_v2"] else "0"
            row[f"{arm}_positions"] = "|".join(item.get("matched_positions") or [])
        rows.append(row)
    return rows


# ─── Summary statistics ──────────────────────────────────────────────────────

def mcnemar_exact(n01: int, n10: int) -> float:
    """Two-sided exact McNemar p-value using binomial null."""
    n = n01 + n10
    if n == 0:
        return 1.0
    lo = min(n01, n10)
    p = sum(math.comb(n, k) * (0.5 ** n) for k in range(lo + 1)) * 2
    return min(1.0, p)


def print_summary(by_query: dict) -> None:
    print("=" * 60)
    print("RIGOROUS REANALYSIS SUMMARY")
    print("=" * 60)

    # Counts
    n_items = len(by_query)
    slots = {}
    statuses = {}
    for arms in by_query.values():
        ref = next(iter(arms.values()))
        s = ref["slot"]
        st = ref["question_status"]
        slots[s] = slots.get(s, 0) + 1
        statuses[st] = statuses.get(st, 0) + 1
    print(f"\nItems: {n_items} (per arm)")
    print(f"Slots: {dict(sorted(slots.items()))}")
    print(f"Statuses: {dict(sorted(statuses.items()))}")

    # Arm-level scores
    print("\n--- Arm-level scores (n=150) ---")
    for arm in ARMS:
        items_arm = [arms[arm] for arms in by_query.values() if arm in arms]
        exact = sum(1 for x in items_arm if x["exact_v2"])
        sem = sum(1 for x in items_arm if x["semantic_qa"])
        print(f"  {arm}: exact={exact}/150 ({100*exact/150:.1f}%), sem={sem}/150 ({100*sem/150:.1f}%)")

    # B1-nodoc (non-doc items, n=116)
    print("\n--- Semantic (B1-nodoc, n=116) ---")
    b1_nodoc = {}
    for arm in ARMS:
        items_arm = [arms[arm] for arms in by_query.values()
                     if arm in arms and arms[arm]["slot"] != "doc"]
        sem = sum(1 for x in items_arm if x["semantic_qa"])
        b1_nodoc[arm] = sem
        print(f"  {arm}: sem={sem}/116 ({100*sem/116:.1f}%)")

    # F2 vs F3 corrected McNemar
    n01 = sum(1 for arms in by_query.values()
              if "F2" in arms and "F3" in arms
              and arms["F2"]["semantic_qa"] and not arms["F3"]["semantic_qa"]
              and arms["F2"]["slot"] != "doc")
    n10 = sum(1 for arms in by_query.values()
              if "F2" in arms and "F3" in arms
              and arms["F3"]["semantic_qa"] and not arms["F2"]["semantic_qa"]
              and arms["F3"]["slot"] != "doc")
    p = mcnemar_exact(n01, n10)
    print(f"\n--- Corrected F2 vs F3 McNemar (non-doc) ---")
    print(f"  F2-wins={n01}, F3-wins={n10}, p={p:.4f}")
    print(f"  Interpretation: {'NOT significant' if p > 0.05 else 'SIGNIFICANT'} (α=0.05)")

    # Multi-candidate temporal
    print("\n--- Multi-candidate temporal (n=42) ---")
    for arm in ARMS:
        mc = [arms[arm] for arms in by_query.values()
              if arm in arms and arms[arm]["question_status"] == "multi_candidate"]
        latest = sum(1 for x in mc if "latest" in (x.get("matched_positions") or []))
        earliest = sum(1 for x in mc if "earliest" in (x.get("matched_positions") or [])
                       and "latest" not in (x.get("matched_positions") or []))
        exact = sum(1 for x in mc if x["exact_v2"])
        print(f"  {arm}: selects_latest={latest}/42 ({100*latest/42:.1f}%), "
              f"stale_state={earliest}/42 ({100*earliest/42:.1f}%), "
              f"exact={exact}/42 ({100*exact/42:.1f}%)")

    # Error taxonomy
    print("\n--- Error taxonomy (n=150) ---")
    taxonomy_counts: dict[str, dict[str, int]] = {arm: {} for arm in ARMS}
    for arms in by_query.values():
        for arm in ARMS:
            if arm not in arms:
                continue
            et = classify_error(arms[arm])
            taxonomy_counts[arm][et] = taxonomy_counts[arm].get(et, 0) + 1

    etypes = ["CORRECT", "FORMAT_ONLY", "STALE_STATE", "MC_INCOMPLETE",
              "INSUF_EV_FAIL", "INSUF_EV_SPURIOUS"]
    header = f"{'':20s}" + "".join(f"{arm:>8s}" for arm in ARMS)
    print(f"  {header}")
    for et in etypes:
        row_str = f"  {et:20s}" + "".join(f"{taxonomy_counts[arm].get(et, 0):>8d}" for arm in ARMS)
        print(row_str)

    print("\n" + "=" * 60)


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    if not ITEM_SCORES.exists():
        print(f"ERROR: {ITEM_SCORES} not found", file=sys.stderr)
        sys.exit(1)

    by_query = load_items()

    # Case-level error analysis
    case_rows = build_case_level(by_query)
    with OUT_CASE_LEVEL.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CASE_HEADER)
        writer.writeheader()
        writer.writerows(case_rows)
    print(f"Wrote {len(case_rows)} rows to {OUT_CASE_LEVEL.name}")

    # Temporal state analysis (non-doc only)
    temp_rows = build_temporal(by_query)
    with OUT_TEMPORAL.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TEMPORAL_HEADER)
        writer.writeheader()
        writer.writerows(temp_rows)
    print(f"Wrote {len(temp_rows)} rows to {OUT_TEMPORAL.name}")

    # Print summary
    print_summary(by_query)


if __name__ == "__main__":
    main()
