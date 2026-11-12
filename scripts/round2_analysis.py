#!/usr/bin/env python3
"""WorldConsistMem Round 2: reviewer agreement, ambiguity audit, adjudication
proposals and F0-F3 sensitivity analysis.

Usage:
    python scripts/round2_analysis.py               # full run (needs private snapshot)
    python scripts/round2_analysis.py --public-only  # reliability + audit only

Public inputs (committed): Round 1 and Round 2 reviewer files, the blind
packet, and ``data/scaled/bundles.jsonl``.
Private inputs (git-ignored, see scripts/build_round2_private_snapshot.py):
frozen raw F0-F3 outputs, evidence packs, and the response-ID -> arm mapping.

Row-level outputs keyed by response ID never contain the arm, so that they can
be shown to a blind human adjudicator. No input file is modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from worldconsistmem import round2_audit as ra  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _round2_report  # noqa: E402

HE = REPO / "human_evaluation"
R1_REVIEWER_1 = HE / "reviewer_1" / "WCM_COMPLETED_ANNOTATION.csv"
R1_REVIEWER_2 = HE / "reviewer_2" / "WCM_COMPLETED_ANNOTATION.json"
R2_PACKET = HE / "round_2" / "reviewer_1" / "BLIND_REVIEW_PACKET.json"
R2_PACKET_COPY = HE / "round_2" / "reviewer_2" / "BLIND_REVIEW_PACKET.json"
R2_A = HE / "round_2" / "completed" / "reviewer_A__WCM_round_2_reviewer_1_COMPLETED.csv"
R2_B = HE / "round_2" / "completed" / "reviewer_B__WCM_round_2_reviewer_1_COMPLETED2.csv"
BUNDLES = REPO / "data" / "scaled" / "bundles.jsonl"
OUT = REPO / "analysis" / "round2"
PRIVATE = OUT / "private"

EXPECTED_SHA256 = {
    R2_A: "aa897fa1737cea16ae549d11006bcd3b8d4c8f797efbc9da16ef4015b4e2dcd5",
    R2_B: "bfda954f8cc717ad2d13c4ffe0e374fd0d0f44b31d9a2cbf84f985febc4ea3fe",
}
N_BOOT = 10000
SEED = 20261111


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_csv(p: Path) -> list[dict[str, str]]:
    with p.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_jsonl(p: Path) -> list[dict]:
    with p.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_csv(p: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def pct(k: int, n: int) -> str:
    return f"{k}/{n} ({100 * k / n:.1f}%)" if n else "0/0"


# --------------------------------------------------------------------------
# 1. Load + validate
# --------------------------------------------------------------------------


def load_public() -> dict[str, Any]:
    a, b = read_csv(R2_A), read_csv(R2_B)
    packet = json.loads(R2_PACKET.read_text(encoding="utf-8"))
    r1_rows = read_csv(R1_REVIEWER_1)
    r1 = {r["response_id"]: r for r in r1_rows}
    r2 = json.loads(R1_REVIEWER_2.read_text(encoding="utf-8"))

    v: dict[str, Any] = {"files": {}}
    for p in (R2_A, R2_B, R2_PACKET, R2_PACKET_COPY, R1_REVIEWER_1, R1_REVIEWER_2, BUNDLES):
        v["files"][str(p.relative_to(REPO))] = sha256_file(p)
    v["round2_files_match_received_sha256"] = all(sha256_file(p) == h for p, h in EXPECTED_SHA256.items())
    ids_a, ids_b = [r["response_id"] for r in a], [r["response_id"] for r in b]
    ids_p = [r["response_id"] for r in packet]
    v["n_rows"] = {"reviewer_A": len(a), "reviewer_B": len(b), "packet": len(packet)}
    v["duplicate_ids"] = {"reviewer_A": len(ids_a) - len(set(ids_a)), "reviewer_B": len(ids_b) - len(set(ids_b))}
    v["ids_aligned_A_B"] = ids_a == ids_b
    v["ids_match_packet"] = ids_a == ids_p
    v["packets_identical"] = sha256_file(R2_PACKET) == sha256_file(R2_PACKET_COPY)
    v["content_identical_A_B"] = all(
        x[k] == y[k] for x, y in zip(a, b) for k in ("case_id", "question", "evidence_json", "raw_model_response")
    )
    v["content_matches_packet"] = all(
        x["question"] == p["question"]
        and json.loads(x["evidence_json"]) == p["evidence_json"]
        and x["raw_model_response"] == p["raw_model_response"]
        for x, p in zip(a, packet)
    )
    v["content_matches_round1"] = all(
        r1[x["response_id"]]["raw_model_response"] == x["raw_model_response"]
        and r1[x["response_id"]]["evidence_json"] == x["evidence_json"]
        for x in a
    )
    for name, rows in (("reviewer_A", a), ("reviewer_B", b)):
        v[f"{name}_invalid_labels"] = sum(r["semantic_correct"] not in ra.LABELS for r in rows)
        v[f"{name}_label_counts"] = dict(Counter(r["semantic_correct"] for r in rows))
        v[f"{name}_evidence_sufficient_counts"] = dict(Counter(r["evidence_sufficient"] for r in rows))
        v[f"{name}_blank_notes"] = sum(not r["notes"].strip() for r in rows)
        v[f"{name}_blank_rubric_reason"] = sum(not r["rubric_reason"].strip() for r in rows)
    v["n_cases"] = len({r["case_id"] for r in a})
    r1_disc = sorted(i for i in r1 if r1[i]["semantic_correct"] != r2[i]["semantic_correct"])
    v["round2_ids_equal_round1_discordant"] = sorted(ids_a) == r1_disc
    v["round1_ids_aligned"] = set(r1) == set(r2) and len(r1_rows) == len(r1) == 120
    hard = (
        "round2_files_match_received_sha256", "ids_aligned_A_B", "ids_match_packet", "packets_identical",
        "content_identical_A_B", "content_matches_packet", "content_matches_round1",
        "round2_ids_equal_round1_discordant", "round1_ids_aligned",
    )
    failed = [k for k in hard if not v[k]]
    if failed or any(v["duplicate_ids"].values()) or v["reviewer_A_invalid_labels"] or v["reviewer_B_invalid_labels"]:
        raise SystemExit(f"input validation failed: {failed} {v['duplicate_ids']}")

    gold_by_text: dict[str, list[dict]] = defaultdict(list)
    gold_by_qid: dict[str, dict] = {}
    for bundle in read_jsonl(BUNDLES):
        for q in bundle["queries"]:
            if q.get("family") == "transition":
                gold_by_text[q["text"]].append(q)
                gold_by_qid[q["query_id"]] = q
    return {"A": a, "B": b, "r1": r1, "r1_order": [r["response_id"] for r in r1_rows], "r2": r2,
            "validation": v, "gold_by_text": gold_by_text, "gold_by_qid": gold_by_qid}


# --------------------------------------------------------------------------
# 2. Agreement
# --------------------------------------------------------------------------


def agreement(pub: dict[str, Any]) -> dict[str, Any]:
    a = [r["semantic_correct"] for r in pub["A"]]
    b = [r["semantic_correct"] for r in pub["B"]]
    cases = [r["case_id"] for r in pub["A"]]
    k = ra.cohen_kappa(a, b)
    out: dict[str, Any] = {
        "round2": {
            **k,
            "confusion_A_rows_B_cols": ra.confusion_matrix(a, b),
            "freq_A": dict(Counter(a)),
            "freq_B": dict(Counter(b)),
            "per_label_joint": {l: sum(x == y == l for x, y in zip(a, b)) for l in ra.LABELS},
            "kappa_case_cluster_bootstrap": ra.cluster_bootstrap_kappa(a, b, cases, N_BOOT, SEED),
            "discordant_ids": [r["response_id"] for r, x, y in zip(pub["A"], a, b) if x != y],
        }
    }
    # Specific agreement per label: 2*n_ll / (n_l. + n_.l)
    ca, cb = Counter(a), Counter(b)
    out["round2"]["specific_agreement"] = {
        l: (2 * out["round2"]["per_label_joint"][l] / (ca[l] + cb[l]) if ca[l] + cb[l] else None) for l in ra.LABELS
    }
    # Case-level view: cases where every response got the same label from both reviewers.
    by_case: dict[str, list[bool]] = defaultdict(list)
    for c, x, y in zip(cases, a, b):
        by_case[c].append(x == y)
    out["round2"]["n_cases"] = len(by_case)
    out["round2"]["n_cases_fully_agreed"] = sum(all(vs) for vs in by_case.values())

    ids = pub["r1_order"]
    x1 = [pub["r1"][i]["semantic_correct"] for i in ids]
    x2 = [pub["r2"][i]["semantic_correct"] for i in ids]
    k1 = ra.cohen_kappa(x1, x2)
    out["round1"] = {**k1, "confusion_R1_rows_R2_cols": ra.confusion_matrix(x1, x2),
                     "freq_reviewer_1": dict(Counter(x1)), "freq_reviewer_2": dict(Counter(x2)),
                     "kappa_case_cluster_bootstrap": ra.cluster_bootstrap_kappa(
                         x1, x2, [i.split("-")[0] for i in ids], N_BOOT, SEED)}
    return out


# --------------------------------------------------------------------------
# 3. Structural audit of the 50 Round 2 responses
# --------------------------------------------------------------------------


def _gold_for_question(pub: dict[str, Any], text: str) -> dict | None:
    golds = {json.dumps(q["gold_answer"], sort_keys=True) for q in pub["gold_by_text"].get(text, [])}
    return json.loads(next(iter(golds))) if len(golds) == 1 else None


def _short(v: str) -> str:
    return v.split(":", 1)[1] if ":" in v else v


def audit_round2(pub: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for ra_row, rb_row in zip(pub["A"], pub["B"]):
        ev = json.loads(ra_row["evidence_json"])
        au = ra.audit_response(ra_row["question"], ev, ra_row["raw_model_response"])
        la, lb = ra_row["semantic_correct"], rb_row["semantic_correct"]
        joint = f"joint_{la}" if la == lb else "disagreement"
        gold = _gold_for_question(pub, ra_row["question"])
        gold_pos, matches_gold = "", ""
        if gold is not None:
            sem = ra.score_semantic(au["slot"], ra_row["raw_model_response"], gold)
            matches_gold = sem["question_aligned"]
            ts = [c["t"] for c in au["candidates"]]
            if gold["t"] in ts:
                i = ts.index(gold["t"])
                gold_pos = "only" if len(ts) == 1 else "earliest" if i == 0 else "latest" if i == len(ts) - 1 else "middle"
            else:
                gold_pos = "not_in_evidence"
        if au["question_status"] == "unique":
            conf = ("high: one candidate event; classification is a deterministic comparison of the stated "
                    "fields with that event")
        elif au["question_status"] == "multi_candidate":
            conf = ("high that the evidence documents several candidate events and that the question text names "
                    "none of them; whether an unstated 'most recent' reading should be assumed is a rubric decision, "
                    "not a fact recoverable from the packet")
        else:
            conf = "high that the supplied evidence cannot identify the asked event; no human sufficiency rating exists"
        rows.append({
            "response_id": ra_row["response_id"],
            "case_id": ra_row["case_id"],
            "question": ra_row["question"],
            "transition_type": au["slot"],
            "reviewer_A": la,
            "reviewer_B": lb,
            "human_status": joint,
            "n_evidence_events": au["n_evidence_events"],
            "evidence_chronology": ra.chronology(ev),
            "n_candidate_events": len(au["candidates"]),
            "candidate_event_ids": ";".join(c["id"] for c in au["candidates"]),
            "candidate_event_times": ";".join(str(c["t"]) for c in au["candidates"]),
            "question_uniquely_identifies_event": au["question_unique"],
            "ambiguity_source": "" if au["question_unique"] else ra.AMBIGUITY_SOURCE[au["slot"]],
            "extracted_answer": " || ".join(ra.claim_summary(c) for c in au["claims"]),
            "n_events_in_answer": len(au["claims"]),
            "answer_matches_documented_event": bool(au["matched"]),
            "matched_event_id": ";".join(m["id"] for m in au["matched"]),
            "matched_event_position": ";".join(au["matched_positions"]),
            "benchmark_gold_event_position": gold_pos,
            "answer_matches_benchmark_gold": matches_gold,
            "audit_class": au["audit_class"],
            "reasoning": au["reasoning"],
            "confidence": conf,
            "classification_source": "automated structural rule (not a human judgment)",
        })
    return rows


AUDIT_FIELDS = [
    "response_id", "case_id", "question", "transition_type", "reviewer_A", "reviewer_B", "human_status",
    "n_evidence_events", "evidence_chronology", "n_candidate_events", "candidate_event_ids",
    "candidate_event_times", "question_uniquely_identifies_event", "ambiguity_source", "extracted_answer",
    "n_events_in_answer", "answer_matches_documented_event", "matched_event_id", "matched_event_position",
    "benchmark_gold_event_position", "answer_matches_benchmark_gold", "audit_class", "reasoning", "confidence",
    "classification_source",
]


def intra_rater_inconsistencies(audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same case, same extracted answer content, different label from the same reviewer."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in audit:
        groups[(r["case_id"], r["matched_event_id"] or r["extracted_answer"])].append(r)
    out = []
    for (case, key), rs in sorted(groups.items()):
        for who in ("reviewer_A", "reviewer_B"):
            labels = {r["response_id"]: r[who] for r in rs}
            if len(set(labels.values())) > 1:
                out.append({"case_id": case, "reviewer": who, "same_answer_event": key, "labels": labels})
    return out


# --------------------------------------------------------------------------
# 4. Adjudication proposals
# --------------------------------------------------------------------------


def adjudication(pub: dict[str, Any], audit: list[dict[str, Any]], incons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {r["response_id"]: r for r in audit}
    raw = {r["response_id"]: r["raw_model_response"] for r in pub["A"]}
    rows = []
    for r in audit:
        if r["human_status"] != "disagreement":
            continue
        rid = r["response_id"]
        siblings = [s for s in audit if s["case_id"] == r["case_id"] and s["response_id"] != rid]
        sib = "; ".join(f"{s['response_id']}: A={s['reviewer_A']}, B={s['reviewer_B']}, answer event "
                        f"{_short(s['matched_event_id']) or 'n/a'}" for s in siblings)
        inc = [i for i in incons if i["case_id"] == r["case_id"] and rid in i["labels"]]
        inc_txt = "; ".join(
            f"{i['reviewer']} labelled the same answer content differently within this case ({i['labels']})" for i in inc)
        if r["audit_class"] == ra.SUPPORTED_AMBIGUOUS:
            proposal, rule = "ambiguous", "8 and 5"
            issue = (f"The evidence documents {r['n_candidate_events']} candidate events (t={r['candidate_event_times']}) "
                     f"and the question does not say which is meant. The answer matches the {r['matched_event_position']} one.")
            expl = ("Protocol rule 8/5: a question that admits several documented events is 'ambiguous' unless context "
                    "fixes one; selecting an existing event does not make the answer correct. The 'correct' vote would "
                    "require assuming an unstated earliest/latest convention.")
        elif r["audit_class"] == ra.SUPPORTED_UNIQUE:
            proposal, rule = "correct", "3"
            issue = ("No ambiguity or contradiction found: the evidence documents exactly one candidate event and the "
                     "answer reproduces its time and participants.")
            expl = ("Protocol rule 3: the answer is supported by the supplied evidence and the question identifies a "
                    "single event. The 'ambiguous' vote is not explained (notes are blank).")
        else:
            proposal, rule, issue, expl = "", "", r["reasoning"], "No rule-based proposal can be justified; left unresolved."
        rows.append({
            "response_id": rid,
            "case_id": r["case_id"],
            "question": r["question"],
            "reviewer_A_label": r["reviewer_A"],
            "reviewer_B_label": r["reviewer_B"],
            "model_answer": raw[rid],
            "relevant_evidence": r["evidence_chronology"],
            "candidate_event_ids": r["candidate_event_ids"],
            "exact_ambiguity_or_contradiction": issue,
            "same_case_labels": sib,
            "intra_rater_inconsistency": inc_txt,
            "proposed_adjudication": proposal,
            "protocol_rule": rule,
            "explanation": expl,
            "proposal_source": "automated rule application (NOT an independent human judgment)",
            "independent_human_adjudication_still_required": "yes (protocol step 5: third evaluator)",
            "final_human_consensus": "",
            "status": "unresolved_pending_human_adjudication",
        })
    assert all(by_id[r["response_id"]] for r in rows)
    return rows


ADJ_FIELDS = [
    "response_id", "case_id", "question", "reviewer_A_label", "reviewer_B_label", "model_answer",
    "relevant_evidence", "candidate_event_ids", "exact_ambiguity_or_contradiction", "same_case_labels",
    "intra_rater_inconsistency", "proposed_adjudication", "protocol_rule", "explanation", "proposal_source",
    "independent_human_adjudication_still_required", "final_human_consensus", "status",
]


def agreement_rows(pub: dict[str, Any], audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for r in audit:
        rid = r["response_id"]
        rows.append({
            "response_id": rid,
            "case_id": r["case_id"],
            "round1_reviewer_1": pub["r1"][rid]["semantic_correct"],
            "round1_reviewer_2": pub["r2"][rid]["semantic_correct"],
            "round2_reviewer_A": r["reviewer_A"],
            "round2_reviewer_B": r["reviewer_B"],
            "round2_agree": r["reviewer_A"] == r["reviewer_B"],
            "round2_status": r["human_status"],
            "round2_agreed_label": r["reviewer_A"] if r["reviewer_A"] == r["reviewer_B"] else "",
        })
    return rows


AGREE_FIELDS = ["response_id", "case_id", "round1_reviewer_1", "round1_reviewer_2", "round2_reviewer_A",
                "round2_reviewer_B", "round2_agree", "round2_status", "round2_agreed_label"]


# --------------------------------------------------------------------------
# 5. F0-F3 scenarios (private inputs)
# --------------------------------------------------------------------------


def load_private() -> dict[str, Any]:
    outs = read_jsonl(PRIVATE / "f0_f3_frozen_outputs.jsonl")
    packs = {r["query_id"]: r for r in read_jsonl(PRIVATE / "evidence_packs.jsonl")}
    mapping = json.loads((PRIVATE / "PRIVATE_MAPPING.json").read_text(encoding="utf-8"))
    manifest = json.loads((PRIVATE / "SNAPSHOT_MANIFEST.json").read_text(encoding="utf-8"))
    sha = {p.name: sha256_file(p) for p in sorted(PRIVATE.glob("*.json*"))}
    return {"outputs": outs, "packs": packs, "mapping": mapping, "manifest": manifest, "sha256": sha}


def build_items(pub: dict[str, Any], priv: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per (query, arm) with every score used downstream."""
    items = []
    for o in priv["outputs"]:
        q = pub["gold_by_qid"][o["query_id"]]
        gold = q["gold_answer"]
        au = ra.audit_response(q["text"], priv["packs"][o["query_id"]]["evidence_json"], o["raw_output"])
        ans = ra.scoring_answer(o["raw_output"])
        sem = ra.score_semantic(au["slot"], o["raw_output"], gold)
        v2_pub = ra.score_v2(ra.scorable_transition(ans), gold)
        items.append({
            "query_id": o["query_id"],
            "world_id": o["query_id"].split(":")[0],
            "arm": o["arm"],
            "slot": au["slot"],
            "question_status": au["question_status"],
            "unique": au["question_unique"],
            "original_sufficiency_label": priv["packs"][o["query_id"]]["original_sufficiency_label"],
            "abstain": au["abstain"],
            "parse_ok": au["parse_ok"],
            "n_claims": len(au["claims"]),
            "audit_class": au["audit_class"],
            "matched_any_candidate": bool(au["matched"]),
            "matched_positions": au["matched_positions"],
            "exact_v2": v2_pub,
            "exact_v2_no_event_unwrap": ra.score_v2(ans, gold),
            "exact_v1": ra.answers_equal_v1(ra.scorable_transition(ans), gold),
            "semantic_qa": sem["question_aligned"],
            "semantic_tuple": sem["tuple_content"],
            "online_ok": o["online_status"] == "ok",
            "recorded_v2": o["recorded_correct_v2"],
            "recorded_v1": o["recorded_correct_v1"],
        })
    return items


def check_reproduction(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare re-scored exact-match results with the scores recorded by the frozen analysis."""
    out: dict[str, Any] = {}
    for arm in ra.ARMS:
        rows = [i for i in items if i["arm"] == arm]
        # F2's recorded per-row flag is the online runner's (no event unwrapping); the published 39/150
        # comes from the analysis script. Compare like with like.
        ours = [i["exact_v2_no_event_unwrap"] if arm == "F2" else i["exact_v2"] for i in rows]
        out[arm] = {
            "n": len(rows),
            "exact_v2": sum(i["exact_v2"] for i in rows),
            "exact_v2_no_event_unwrap": sum(i["exact_v2_no_event_unwrap"] for i in rows),
            "exact_v1": sum(i["exact_v1"] for i in rows),
            "row_level_mismatches_vs_recorded_v2": sum(a != i["recorded_v2"] for a, i in zip(ours, rows)),
            "row_level_mismatches_vs_recorded_v1": sum(
                i["exact_v1"] != i["recorded_v1"] for i in rows if i["recorded_v1"] is not None),
            "online_runner_status_ok": sum(i["online_ok"] for i in rows),
        }
    return out


PUBLISHED = {"all": {"F0": 13, "F1": 90, "F2": 39, "F3": 109}, "S1+S2": {"F0": 13, "F1": 39, "F2": 26, "F3": 52}}


def scenario_defs(human_ambiguous_qids: set[str]) -> list[dict[str, Any]]:
    def allq(i):
        return True

    return [
        {"id": "A", "name": "Original exact-match (scorer v2, published rule)", "keep": allq, "ok": lambda i: i["exact_v2"]},
        {"id": "A-S1S2", "name": "Original exact-match, original S1+S2 slice",
         "keep": lambda i: i["original_sufficiency_label"] in ("S1", "S2"), "ok": lambda i: i["exact_v2"]},
        {"id": "A-v1", "name": "Exact-match under superseded scorer v1 (strict keys)", "keep": allq, "ok": lambda i: i["exact_v1"]},
        {"id": "A-nounwrap", "name": "Scorer v2 without the prev/event/next 'event' unwrapping", "keep": allq,
         "ok": lambda i: i["exact_v2_no_event_unwrap"]},
        {"id": "B1", "name": "Semantic, question-aligned (asked fields only, schema ignored)", "keep": allq,
         "ok": lambda i: i["semantic_qa"]},
        {"id": "B1-nodoc", "name": "Semantic, question-aligned, document items excluded (question/gold defect)",
         "keep": lambda i: i["slot"] != "doc", "ok": lambda i: i["semantic_qa"]},
        {"id": "B2", "name": "Semantic, full tuple content (all gold fields, schema ignored)", "keep": allq,
         "ok": lambda i: i["semantic_tuple"]},
        {"id": "C1-A", "name": "Exclude human-established ambiguous questions; exact-match v2",
         "keep": lambda i: i["query_id"] not in human_ambiguous_qids, "ok": lambda i: i["exact_v2"]},
        {"id": "C1-B1", "name": "Exclude human-established ambiguous questions; semantic question-aligned",
         "keep": lambda i: i["query_id"] not in human_ambiguous_qids, "ok": lambda i: i["semantic_qa"]},
        {"id": "C2-A", "name": "Uniquely specified questions only (structural rule); exact-match v2",
         "keep": lambda i: i["unique"], "ok": lambda i: i["exact_v2"]},
        {"id": "C2-B1", "name": "Uniquely specified questions only (structural rule); semantic question-aligned",
         "keep": lambda i: i["unique"], "ok": lambda i: i["semantic_qa"]},
        {"id": "C2-B2", "name": "Uniquely specified questions only (structural rule); semantic full tuple",
         "keep": lambda i: i["unique"], "ok": lambda i: i["semantic_tuple"]},
        {"id": "D", "name": "Conservative: non-unique questions count as failures; semantic question-aligned",
         "keep": allq, "ok": lambda i: i["unique"] and i["semantic_qa"]},
        {"id": "E-lower", "name": "Sensitivity lower bound (= D)", "keep": allq,
         "ok": lambda i: i["unique"] and i["semantic_qa"]},
        {"id": "E-mid", "name": "Sensitivity mid: benchmark 'latest event' convention (= B1)", "keep": allq,
         "ok": lambda i: i["semantic_qa"]},
        {"id": "E-upper", "name": "Sensitivity upper bound: any single documented candidate event credited",
         "keep": allq,
         "ok": lambda i: (i["unique"] and i["semantic_qa"]) or (not i["unique"] and i["n_claims"] == 1 and i["matched_any_candidate"])},
        {"id": "NU-latest", "name": "Non-unique questions only: answer selects the latest documented event (gold convention)",
         "keep": lambda i: not i["unique"] and i["slot"] != "doc", "ok": lambda i: i["semantic_qa"]},
    ]


def run_scenarios(items: list[dict[str, Any]], human_ambiguous_qids: set[str]) -> tuple[list[dict], dict]:
    by: dict[str, dict[str, dict]] = defaultdict(dict)
    for i in items:
        by[i["query_id"]][i["arm"]] = i
    qids = sorted(by)
    rows, summary = [], {}
    for sc in scenario_defs(human_ambiguous_qids):
        kept = [q for q in qids if sc["keep"](by[q]["F0"])]
        worlds = [q.split(":")[0] for q in kept]
        vec = {arm: [bool(sc["ok"](by[q][arm])) for q in kept] for arm in ra.ARMS}
        summary[sc["id"]] = {"name": sc["name"], "n": len(kept), "n_excluded": len(qids) - len(kept),
                             "n_worlds": len(set(worlds)), "arms": {}, "paired": {}}
        for arm in ra.ARMS:
            k, n = sum(vec[arm]), len(kept)
            lo, hi = ra.wilson_ci(k, n)
            summary[sc["id"]]["arms"][arm] = {"k": k, "n": n}
            rows.append({"scope": "F0-F3 frozen outputs (150 transition items)", "scenario": sc["id"],
                         "scenario_description": sc["name"], "row_type": "arm", "arm_or_contrast": arm,
                         "n_items": n, "n_excluded": len(qids) - n, "n_correct": k,
                         "accuracy": f"{k / n:.4f}" if n else "", "ci95_lo": f"{lo:.4f}" if n else "",
                         "ci95_hi": f"{hi:.4f}" if n else "", "ci_method": "Wilson (items treated as independent)"})
        for other in ("F0", "F1", "F2"):
            mc = ra.mcnemar_exact(vec[other], vec["F3"])
            bs = ra.cluster_bootstrap_diff(vec[other], vec["F3"], worlds, N_BOOT, SEED)
            summary[sc["id"]]["paired"][f"F3-{other}"] = {**mc, **bs}
            rows.append({"scope": "F0-F3 frozen outputs (150 transition items)", "scenario": sc["id"],
                         "scenario_description": sc["name"], "row_type": "paired_contrast",
                         "arm_or_contrast": f"F3-{other}", "n_items": len(kept), "n_excluded": len(qids) - len(kept),
                         "delta_pp": f"{100 * bs['delta']:.2f}" if kept else "",
                         "ci95_lo": f"{100 * bs['ci95_lo']:.2f}" if kept else "",
                         "ci95_hi": f"{100 * bs['ci95_hi']:.2f}" if kept else "",
                         "ci_method": f"world-cluster bootstrap, {bs['n_clusters']} worlds, {N_BOOT} resamples (pp)",
                         "f3_only": mc["y_only"], "other_only": mc["x_only"],
                         "mcnemar_exact_p": f"{mc['p_two_sided']:.3g}"})
    return rows, summary


def human_subset(pub: dict[str, Any], priv: dict[str, Any], audit: list[dict[str, Any]], items: list[dict[str, Any]]):
    """Arm-level tabulation of human labels on the 120-response annotation sample."""
    mp = {m["response_id"]: m for m in priv["mapping"]}
    raw_by_id = {rid: r["raw_model_response"] for rid, r in pub["r1"].items()}
    out_sha = {(o["arm"], o["query_id"]): o["raw_output_sha256"] for o in priv["outputs"]}
    checks = {
        "mapping_rows": len(mp),
        "ids_match_round1": set(mp) == set(pub["r1"]),
        "sha_matches_annotated_text": sum(
            hashlib.sha256(raw_by_id[r].encode("utf-8")).hexdigest() == m["raw_output_sha256"] for r, m in mp.items()),
        "sha_matches_frozen_output": sum(out_sha[(m["arm"], m["query_id"])] == m["raw_output_sha256"] for m in mp.values()),
        "cases_with_all_four_arms": sum(
            sorted(m["arm"] for m in mp.values() if m["response_id"].startswith(c + "-")) == list(ra.ARMS)
            for c in {r.split("-")[0] for r in mp}),
        "n_cases": len({r.split("-")[0] for r in mp}),
    }
    if not (checks["ids_match_round1"] and checks["sha_matches_annotated_text"] == 120
            and checks["sha_matches_frozen_output"] == 120 and checks["cases_with_all_four_arms"] == 30):
        raise SystemExit(f"private mapping failed verification: {checks}")

    r2 = {r["response_id"]: r for r in audit}
    item = {(i["arm"], i["query_id"]): i for i in items}
    status: dict[str, str] = {}
    for rid in mp:
        if rid in r2:
            status[rid] = {"joint_correct": "R2_joint_correct", "joint_ambiguous": "R2_joint_ambiguous",
                           "joint_incorrect": "R2_joint_incorrect"}.get(r2[rid]["human_status"], "R2_unresolved")
        else:
            status[rid] = "R1_agreed_" + pub["r1"][rid]["semantic_correct"]
    cats = ["R1_agreed_correct", "R1_agreed_incorrect", "R2_joint_correct", "R2_joint_incorrect",
            "R2_joint_ambiguous", "R2_unresolved"]
    table = {arm: {c: 0 for c in cats} for arm in ra.ARMS}
    by_struct = {arm: Counter() for arm in ra.ARMS}
    r1_agreed_nonunique = Counter()
    for rid, m in mp.items():
        table[m["arm"]][status[rid]] += 1
        it = item[(m["arm"], m["query_id"])]
        by_struct[m["arm"]][(it["question_status"], status[rid])] += 1
        if status[rid].startswith("R1_agreed") and not it["unique"]:
            r1_agreed_nonunique[(it["slot"], status[rid])] += 1

    rows = []
    treat = {}
    for arm in ra.ARMS:
        t = table[arm]
        cor = t["R1_agreed_correct"] + t["R2_joint_correct"]
        inc = t["R1_agreed_incorrect"] + t["R2_joint_incorrect"]
        amb, unr, n = t["R2_joint_ambiguous"], t["R2_unresolved"], sum(t.values())
        treat[arm] = {
            "ambiguous_and_unresolved_excluded": (cor, cor + inc),
            "ambiguous_as_incorrect_unresolved_as_incorrect (lower)": (cor, n),
            "ambiguous_as_incorrect_unresolved_as_correct": (cor + unr, n),
            "ambiguous_excluded_unresolved_as_correct (upper)": (cor + unr, cor + inc + unr),
        }
        for name, (k, d) in treat[arm].items():
            lo, hi = ra.wilson_ci(k, d)
            rows.append({"scope": "human labels, 120-response sample (30 cases x 4 arms)", "scenario": "H",
                         "scenario_description": name, "row_type": "arm", "arm_or_contrast": arm, "n_items": d,
                         "n_excluded": n - d, "n_correct": k, "accuracy": f"{k / d:.4f}" if d else "",
                         "ci95_lo": f"{lo:.4f}" if d else "", "ci95_hi": f"{hi:.4f}" if d else "",
                         "ci_method": "Wilson; stratified non-proportional sample, not a population estimate"})
    # Which queries have human-established ambiguity (>=1 response jointly labelled ambiguous in Round 2)?
    amb_q = sorted({mp[rid]["query_id"] for rid, s in status.items() if s == "R2_joint_ambiguous"})
    struct_vs_human = Counter()
    for rid, r in r2.items():
        struct_vs_human[(r["question_uniquely_identifies_event"], r["human_status"])] += 1
    return rows, {
        "checks": checks, "table": table, "treatments": {a: {k: list(v) for k, v in t.items()} for a, t in treat.items()},
        "by_structure": {a: {f"{k[0]}|{k[1]}": v for k, v in sorted(c.items())} for a, c in by_struct.items()},
        "round1_agreed_labels_on_nonunique_questions": {f"{k[0]}|{k[1]}": v for k, v in sorted(r1_agreed_nonunique.items())},
        "human_ambiguous_query_ids": amb_q,
        "sample_slot_counts": dict(Counter(m["query_id"].split(":")[2] for m in mp.values() if m["arm"] == "F0")),
        "structure_vs_round2_labels": {f"unique={k[0]}|{k[1]}": v for k, v in sorted(struct_vs_human.items())},
        "round2_by_arm": {arm: dict(Counter(status[r] for r in r2 if mp[r]["arm"] == arm)) for arm in ra.ARMS},
    }


SENS_FIELDS = ["scope", "scenario", "scenario_description", "row_type", "arm_or_contrast", "n_items", "n_excluded",
               "n_correct", "accuracy", "delta_pp", "ci95_lo", "ci95_hi", "ci_method", "f3_only", "other_only",
               "mcnemar_exact_p"]


def structure_tables(items: list[dict[str, Any]]) -> dict[str, Any]:
    f0 = [i for i in items if i["arm"] == "F0"]
    status = Counter((i["slot"], i["question_status"]) for i in f0)
    cells = defaultdict(lambda: {a: Counter() for a in ra.ARMS})
    for i in items:
        key = f"{i['slot']}|{i['question_status']}"
        c = cells[key][i["arm"]]
        c["n"] += 1
        c["exact_v2"] += i["exact_v2"]
        c["semantic_qa"] += i["semantic_qa"]
        c["semantic_tuple"] += i["semantic_tuple"]
        c["single_documented_event"] += i["n_claims"] == 1 and i["matched_any_candidate"]
        c["multi_event_list"] += i["n_claims"] > 1
        c["no_candidate_match"] += i["n_claims"] == 1 and not i["matched_any_candidate"]
        c["abstain"] += i["abstain"]
        c["unparseable"] += not i["parse_ok"]
    return {
        "question_status_by_slot": {f"{k[0]}|{k[1]}": v for k, v in sorted(status.items())},
        "n_unique": sum(i["unique"] for i in f0),
        "n_multi_candidate": sum(i["question_status"] == "multi_candidate" for i in f0),
        "n_version_unidentifiable": sum(i["question_status"] == "version_unidentifiable" for i in f0),
        "cells": {k: {a: dict(c) for a, c in v.items()} for k, v in sorted(cells.items())},
        "sufficiency_vs_structure": {f"{k[0]}|{k[1]}": v for k, v in sorted(
            Counter((i["original_sufficiency_label"], i["question_status"]) for i in f0).items())},
        "abstentions": {a: sum(i["abstain"] for i in items if i["arm"] == a) for a in ra.ARMS},
        "unparseable": {a: sum(not i["parse_ok"] for i in items if i["arm"] == a) for a in ra.ARMS},
    }


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--public-only", action="store_true", help="skip everything that needs the private snapshot")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    pub = load_public()
    agr = agreement(pub)
    audit = audit_round2(pub)
    incons = intra_rater_inconsistencies(audit)
    adj = adjudication(pub, audit, incons)
    write_csv(OUT / "reviewer_agreement.csv", agreement_rows(pub, audit), AGREE_FIELDS)
    write_csv(OUT / "ambiguous_case_audit.csv", audit, AUDIT_FIELDS)
    write_csv(OUT / "adjudication_proposals.csv", adj, ADJ_FIELDS)

    amb = [r for r in audit if r["human_status"] == "joint_ambiguous"]
    results: dict[str, Any] = {
        "validation": pub["validation"],
        "agreement": agr,
        "audit_summary": {
            "n_responses": len(audit),
            "class_by_human_status": {f"{k[0]}|{k[1]}": v for k, v in sorted(
                Counter((r["human_status"], r["audit_class"]) for r in audit).items())},
            "jointly_ambiguous": {
                "n_responses": len(amb),
                "n_questions": len({r["case_id"] for r in amb}),
                "all_have_multiple_candidate_events": all(r["n_candidate_events"] >= 2 for r in amb),
                "all_answers_match_a_documented_event": all(r["answer_matches_documented_event"] for r in amb),
                "by_type": dict(Counter(r["transition_type"] for r in amb)),
                "matched_position": dict(Counter(r["matched_event_position"] for r in amb)),
                "answer_matches_benchmark_gold": dict(Counter(str(r["answer_matches_benchmark_gold"]) for r in amb)),
            },
            "nonunique_questions_in_round2": {
                "n_questions": len({r["case_id"] for r in audit if not r["question_uniquely_identifies_event"]}),
                "n_responses": sum(not r["question_uniquely_identifies_event"] for r in audit),
                "case_ids": sorted({r["case_id"] for r in audit if not r["question_uniquely_identifies_event"]}),
            },
            "structure_vs_labels": {f"unique={k[0]}|A={k[1]}|B={k[2]}": v for k, v in sorted(Counter(
                (r["question_uniquely_identifies_event"], r["reviewer_A"], r["reviewer_B"]) for r in audit).items())},
            "intra_rater_inconsistencies": incons,
        },
        "adjudication": {
            "n_disagreements": len(adj),
            "n_with_rule_based_proposal": sum(bool(r["proposed_adjudication"]) for r in adj),
            "proposals": {r["response_id"]: r["proposed_adjudication"] for r in adj},
            "n_confirmed_by_independent_human": 0,
            "n_unresolved": len(adj),
        },
    }

    if not args.public_only:
        if not (PRIVATE / "f0_f3_frozen_outputs.jsonl").exists():
            raise SystemExit("private snapshot missing: run scripts/build_round2_private_snapshot.py or pass --public-only")
        priv = load_private()
        items = build_items(pub, priv)
        hrows, hsum = human_subset(pub, priv, audit, items)
        srows, ssum = run_scenarios(items, set(hsum["human_ambiguous_query_ids"]))
        write_csv(OUT / "sensitivity_analysis.csv", srows + hrows, SENS_FIELDS)
        with (PRIVATE / "item_scores.jsonl").open("w", encoding="utf-8") as fh:
            for i in items:
                fh.write(json.dumps(i, sort_keys=True) + "\n")
        hsum_public = {k: v for k, v in hsum.items() if k != "human_ambiguous_query_ids"}
        hsum_public["n_human_ambiguous_questions"] = len(hsum["human_ambiguous_query_ids"])
        results.update({
            "private_inputs": {"sha256": priv["sha256"], "source_sha256": priv["manifest"]["source_sha256"],
                               "evidence_identical_across_arms": priv["manifest"]["evidence_identical_across_arms"],
                               "annotation_source_manifest": priv["manifest"].get("annotation_source_manifest", {})},
            "run_config": dict(Counter(
                f"{o['arm']}|{o['model_resolved']}|T={o['temperature']}|max_tokens={o['max_tokens']}" for o in priv["outputs"])),
            "reproduction": {"rescored": check_reproduction(items), "published": PUBLISHED},
            "structure": structure_tables(items),
            "scenarios": ssum,
            "human_subset": hsum_public,
        })

    (OUT / "round2_results.json").write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if not args.public_only:
        (OUT / "evaluation_report.md").write_text(_round2_report.render(results, audit, adj), encoding="utf-8")
    r2 = agr["round2"]
    print(f"Round 2: {r2['n_agree']}/{r2['n']} agree, kappa={r2['kappa']:.4f}; disagreements: {r2['discordant_ids']}")
    print(f"Jointly ambiguous: {len(amb)} responses / {len({r['case_id'] for r in amb})} questions")
    if not args.public_only:
        for sid, s in results["scenarios"].items():
            print(f"{sid:10s} n={s['n']:3d} " + " ".join(f"{a}={s['arms'][a]['k']}" for a in ra.ARMS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
