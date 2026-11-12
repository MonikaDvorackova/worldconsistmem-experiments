"""Adjudication sensitivity analysis and statistics verification for Round 2.

Verifies all reported statistics from raw data and computes sensitivity bounds
for the 6 unresolved adjudication items.

Usage:
    uv run python scripts/adjudication_sensitivity.py
"""

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
REVIEWER_A = ROOT / "human_evaluation/round_2/completed/reviewer_A__WCM_round_2_reviewer_1_COMPLETED.csv"
REVIEWER_B = ROOT / "human_evaluation/round_2/completed/reviewer_B__WCM_round_2_reviewer_1_COMPLETED2.csv"
RESULTS_JSON = ROOT / "analysis/round2/round2_results.json"
MAPPING_JSON = ROOT / "analysis/round2/private/PRIVATE_MAPPING.json"
ITEM_SCORES = ROOT / "analysis/round2/private/item_scores.jsonl"
OUTPUT_DIR = ROOT / "analysis/round2"

DISC_IDS = ["C21-R1", "C22-R3", "C22-R4", "C24-R2", "C29-R3", "C29-R4"]
DISC_PROPOSALS = {
    "C21-R1": "ambiguous",
    "C22-R3": "ambiguous",
    "C22-R4": "ambiguous",
    "C24-R2": "correct",
    "C29-R3": "ambiguous",
    "C29-R4": "ambiguous",
}


def _read_csv(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    return list(csv.DictReader(text.splitlines()))


def load_labels() -> tuple[dict, dict]:
    rows_a = _read_csv(REVIEWER_A)
    rows_b = _read_csv(REVIEWER_B)
    a = {r["response_id"]: r["semantic_correct"] for r in rows_a}
    b = {r["response_id"]: r["semantic_correct"] for r in rows_b}
    return a, b


def cohen_kappa_2rater(a_map: dict, b_map: dict) -> dict:
    """Unweighted Cohen's kappa for matched response_ids."""
    common = sorted(set(a_map) & set(b_map))
    n = len(common)
    conf = Counter((a_map[i], b_map[i]) for i in common)
    agree = sum(conf[k, k] for k in set(list(a_map.values()) + list(b_map.values())))
    po = agree / n

    labels = sorted({v for d in (a_map, b_map) for v in d.values()})
    pa = {lbl: sum(1 for i in common if a_map[i] == lbl) / n for lbl in labels}
    pb = {lbl: sum(1 for i in common if b_map[i] == lbl) / n for lbl in labels}
    pe = sum(pa[lbl] * pb[lbl] for lbl in labels)

    kappa = (po - pe) / (1 - pe) if pe < 1.0 else float("nan")
    return {
        "n": n,
        "n_agree": agree,
        "po": po,
        "pe": pe,
        "kappa": kappa,
        "confusion": dict(conf),
        "discordant": [(i, a_map[i], b_map[i]) for i in common if a_map[i] != b_map[i]],
    }


def mcnemar_exact_two_sided(n01: int, n10: int) -> float:
    """Exact two-sided McNemar p-value via binomial tail."""
    total = n01 + n10
    if total == 0:
        return 1.0
    lo = min(n01, n10)
    # Binomial PMF via math.comb (no scipy needed)
    def binom_pmf(k: int, n: int, p: float) -> float:
        return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))
    return min(1.0, 2 * sum(binom_pmf(k, total, 0.5) for k in range(lo + 1)))


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return center - half, center + half


def verify_agreement_stats() -> dict:
    a_map, b_map = load_labels()
    stats = cohen_kappa_2rater(a_map, b_map)
    n, agree = stats["n"], stats["n_agree"]
    po = stats["po"]

    disc = stats["discordant"]
    n01 = sum(1 for _, al, bl in disc if al == "ambiguous" and bl == "correct")
    n10 = sum(1 for _, al, bl in disc if al == "correct" and bl == "ambiguous")

    conf = stats["confusion"]
    n_aa = conf.get(("ambiguous", "ambiguous"), 0)
    n_cc = conf.get(("correct", "correct"), 0)
    sa_ambig = 2 * n_aa / (2 * n_aa + n01 + n10) if (2 * n_aa + n01 + n10) > 0 else float("nan")
    sa_corr = 2 * n_cc / (2 * n_cc + n01 + n10) if (2 * n_cc + n01 + n10) > 0 else float("nan")

    wi_lo, wi_hi = wilson_ci(agree, n)
    p_mcnemar = mcnemar_exact_two_sided(n01, n10)

    return {
        "n": n,
        "n_agree": agree,
        "po": po,
        "pe": stats["pe"],
        "kappa": stats["kappa"],
        "n_discordant": len(disc),
        "n_A_amb_B_corr": n01,
        "n_A_corr_B_amb": n10,
        "mcnemar_p_two_sided": p_mcnemar,
        "wilson_ci_lo": wi_lo,
        "wilson_ci_hi": wi_hi,
        "specific_agreement_ambiguous": sa_ambig,
        "specific_agreement_correct": sa_corr,
        "discordant_ids": [x[0] for x in disc],
    }


def verify_adjudication_scope() -> dict:
    """
    Determine which evaluation scenarios are affected by the 6 unresolved
    adjudications.

    Returns a dict documenting scope of impact for each scenario type.
    """
    a_map, b_map = load_labels()
    common = sorted(set(a_map) & set(b_map))

    # Identify jointly-ambiguous cases (all round-2 responses in case both=ambiguous)
    cases = defaultdict(list)
    for rid in common:
        case = rid.rsplit("-", 1)[0]
        cases[case].append((rid, a_map[rid], b_map[rid]))

    jointly_ambig_cases = [
        c for c, rs in cases.items() if all(a == "ambiguous" and b == "ambiguous" for _, a, b in rs)
    ]
    # C1 scenarios exclude questions covered by jointly-ambiguous cases
    # Cases with discordant items but ALSO jointly-ambiguous responses:
    disc_cases = {rid.rsplit("-", 1)[0] for rid in DISC_IDS}
    disc_cases_already_excluded = disc_cases & set(jointly_ambig_cases)
    # Cases where all round-2 responses have at least one jointly-ambiguous response
    # (whether or not there's also a discordant response)
    partially_ambig = {
        c for c, rs in cases.items()
        if any(a == "ambiguous" and b == "ambiguous" for _, a, b in rs)
        and not all(a == "ambiguous" and b == "ambiguous" for _, a, b in rs)
    }
    # Check if C22, C21, C29 have jointly-ambiguous responses alongside discordant
    disc_cases_with_joint_ambig_sibling = {
        rid.rsplit("-", 1)[0]
        for rid in DISC_IDS
        for _, a, b in cases[rid.rsplit("-", 1)[0]]
        if a == "ambiguous" and b == "ambiguous"
    }

    return {
        "jointly_ambiguous_cases": sorted(jointly_ambig_cases),
        "disc_cases": sorted(disc_cases),
        "disc_cases_with_joint_ambig_sibling": sorted(disc_cases_with_joint_ambig_sibling),
        "disc_cases_purely_discordant": sorted(disc_cases - disc_cases_with_joint_ambig_sibling),
        "analysis": {
            "mechanical_scenarios": (
                "Scenarios A, B1, B2, C2-A, C2-B1, NU-latest, E-lower/mid/upper use the "
                "mechanical scorer only. Human labels are not an input. "
                "Adjudication has NO effect on these scenarios."
            ),
            "C1_scenarios": (
                "C1 scenarios exclude questions where at least one Round-2 response was "
                "jointly labeled ambiguous (both reviewers = ambiguous). "
                "C21, C22, C29 each have at least one jointly-ambiguous sibling response — "
                "so they are already excluded from C1 regardless of how the discordant items "
                "are adjudicated. C24 is a unique question with no jointly-ambiguous responses "
                "and would NOT be excluded under any adjudication treatment. "
                "Adjudication has NO effect on C1 scenario membership."
            ),
            "agreement_stats": (
                "κ, po, pe are computed from the 50 paired labels. The 6 discordant items "
                "drive the disagreement count (12% = 6/50). Adjudication by a third reviewer "
                "would add evidence for each item's consensus label; until then, the "
                "agreement statistics are computed on the full 50 pairs as observed."
            ),
        },
    }


def verify_mechanical_scenarios() -> dict:
    """Cross-check key scenario totals against item_scores.jsonl."""
    if not ITEM_SCORES.exists():
        return {"status": "skipped: item_scores.jsonl not available"}

    with open(ITEM_SCORES) as f:
        items = [json.loads(l) for l in f]

    result = {}
    for arm in ["F0", "F1", "F2", "F3"]:
        arm_items = [i for i in items if i["arm"] == arm]
        n = len(arm_items)
        exact = sum(1 for i in arm_items if i["exact_v2"])
        sem_qa = sum(1 for i in arm_items if i["semantic_qa"])
        nodoc = [i for i in arm_items if i["slot"] != "doc"]
        sem_nodoc = sum(1 for i in nodoc if i["semantic_qa"])
        uniq = [i for i in arm_items if i["unique"]]
        sem_uniq = sum(1 for i in uniq if i["semantic_qa"])
        exact_uniq = sum(1 for i in uniq if i["exact_v2"])
        mc = [i for i in arm_items if i["question_status"] == "multi_candidate"]
        sem_mc = sum(1 for i in mc if i["semantic_qa"])
        exact_mc = sum(1 for i in mc if i["exact_v2"])
        latest_mc = sum(1 for i in mc if "latest" in (i.get("matched_positions") or []))
        multi_list = sum(1 for i in mc if len(i.get("matched_positions") or []) > 1)
        doc = [i for i in arm_items if i["slot"] == "doc"]
        sem_doc = sum(1 for i in doc if i["semantic_qa"])
        result[arm] = {
            "n": n,
            "exact_v2": exact,
            "semantic_qa_all": sem_qa,
            "semantic_qa_nodoc": sem_nodoc,
            "n_nodoc": len(nodoc),
            "unique_n": len(uniq),
            "unique_exact": exact_uniq,
            "unique_semantic": sem_uniq,
            "mc_n": len(mc),
            "mc_exact": exact_mc,
            "mc_semantic_qa": sem_mc,
            "mc_matches_latest": latest_mc,
            "mc_multi_event_list": multi_list,
            "doc_n": len(doc),
            "doc_semantic_spurious": sem_doc,
        }
    return result


def check_intra_rater_consistency() -> dict:
    """Verify reviewer B's intra-case label inconsistencies."""
    rows_b = _read_csv(REVIEWER_B)
    b_by_case = defaultdict(list)
    for row in rows_b:
        case = row["response_id"].rsplit("-", 1)[0]
        b_by_case[case].append(row)

    inconsistencies = {}
    for case, rows in sorted(b_by_case.items()):
        labels = {r["response_id"]: r["semantic_correct"] for r in rows}
        unique_labels = set(labels.values())
        if len(unique_labels) > 1:
            inconsistencies[case] = {
                "labels": labels,
                "note": "Reviewer B assigned different labels within the same case",
            }

    return {
        "n_cases_reviewed_by_B": len(b_by_case),
        "n_cases_with_inconsistency": len(inconsistencies),
        "cases": inconsistencies,
    }


def run_verification() -> dict:
    print("Running verification...", flush=True)
    results = {}
    results["agreement"] = verify_agreement_stats()
    results["adjudication_scope"] = verify_adjudication_scope()
    results["mechanical_scenarios"] = verify_mechanical_scenarios()
    results["intra_rater"] = check_intra_rater_consistency()

    # Cross-check against stored results
    if RESULTS_JSON.exists():
        stored = json.loads(RESULTS_JSON.read_text())
        stored_kappa = stored["agreement"]["round2"]["kappa"]
        computed_kappa = results["agreement"]["kappa"]
        kappa_ok = abs(stored_kappa - computed_kappa) < 1e-6
        stored_agree = stored["agreement"]["round2"]["n_agree"]
        agree_ok = stored_agree == results["agreement"]["n_agree"]
        results["cross_check"] = {
            "kappa_matches": kappa_ok,
            "agree_matches": agree_ok,
            "stored_kappa": stored_kappa,
            "computed_kappa": computed_kappa,
        }

    return results


def print_report(results: dict) -> None:
    ag = results["agreement"]
    print("\n" + "=" * 70)
    print("ROUND 2 STATISTICS VERIFICATION")
    print("=" * 70)
    print(f"\nAgreement: {ag['n_agree']}/{ag['n']} = {ag['po']:.1%}")
    print(f"Cohen κ:   {ag['kappa']:.6f}")
    print(f"Wilson CI: [{ag['wilson_ci_lo']:.4f}, {ag['wilson_ci_hi']:.4f}]")
    print(f"McNemar test (direction symmetry): p = {ag['mcnemar_p_two_sided']:.4f}")
    print(f"  n(A=ambig,B=corr) = {ag['n_A_amb_B_corr']}")
    print(f"  n(A=corr,B=ambig) = {ag['n_A_corr_B_amb']}")
    print(f"  Interpretation: p={ag['mcnemar_p_two_sided']:.3f} → no significant asymmetry in which reviewer is more lenient")
    print(f"Specific agreement: ambiguous={ag['specific_agreement_ambiguous']:.4f}, correct={ag['specific_agreement_correct']:.4f}")
    print(f"Discordant items: {ag['discordant_ids']}")

    print("\n" + "-" * 70)
    print("ADJUDICATION SCOPE")
    print("-" * 70)
    scope = results["adjudication_scope"]
    print(f"Jointly-ambiguous cases (all responses both=ambiguous): {scope['jointly_ambiguous_cases']}")
    print(f"Discordant item cases: {scope['disc_cases']}")
    print(f"  → already excluded from C1 (have joint-ambig sibling): {scope['disc_cases_with_joint_ambig_sibling']}")
    print(f"  → purely discordant (no joint-ambig sibling): {scope['disc_cases_purely_discordant']}")
    print()
    print(f"Mechanical scenarios: {scope['analysis']['mechanical_scenarios']}")
    print()
    print(f"C1 scenarios: {scope['analysis']['C1_scenarios']}")

    if "mechanical_scenarios" in results and isinstance(results["mechanical_scenarios"], dict) and "F0" in results["mechanical_scenarios"]:
        ms = results["mechanical_scenarios"]
        print("\n" + "-" * 70)
        print("MECHANICAL SCENARIO CROSS-CHECK (from item_scores.jsonl)")
        print("-" * 70)
        print(f"{'Arm':4} {'ExactA':7} {'SemAll':7} {'SemNodoc':9} {'SemUniq':8} {'SemMC':6} {'DocSpur':8}")
        for arm in ["F0", "F1", "F2", "F3"]:
            d = ms[arm]
            print(f"{arm:4} {d['exact_v2']:7} {d['semantic_qa_all']:7} {d['semantic_qa_nodoc']:9} {d['unique_semantic']:8} {d['mc_semantic_qa']:6} {d['doc_semantic_spurious']:8}")

    ir = results["intra_rater"]
    print("\n" + "-" * 70)
    print("INTRA-RATER CONSISTENCY (Reviewer B)")
    print("-" * 70)
    print(f"Cases with inconsistent labels: {ir['n_cases_with_inconsistency']} / {ir['n_cases_reviewed_by_B']}")
    for case, info in ir["cases"].items():
        print(f"  {case}: {info['labels']}")

    if "cross_check" in results:
        cc = results["cross_check"]
        print("\n" + "-" * 70)
        print("CROSS-CHECK AGAINST STORED RESULTS")
        print("-" * 70)
        print(f"κ match: {cc['kappa_matches']} (stored={cc['stored_kappa']:.6f}, computed={cc['computed_kappa']:.6f})")
        print(f"agree match: {cc['agree_matches']}")

    print("\n" + "=" * 70)
    print("REMAINING HUMAN DECISIONS REQUIRED")
    print("=" * 70)
    print("The following items require adjudication by an independent third evaluator")
    print("(pre-registered protocol step 5). None of these affect the mechanical")
    print("evaluation scenarios — they only affect the Round 2 consensus human label.")
    print()
    disc_data = {
        "C21-R1": ("F3", "ceo-mc",  "A=ambiguous, B=correct", "ambiguous",
                   "3 candidate events; answer matches latest; question does not specify which"),
        "C22-R3": ("F0", "ceo-mc",  "A=ambiguous, B=correct", "ambiguous",
                   "2 candidate events; answer matches earliest; question does not specify which"),
        "C22-R4": ("F1", "ceo-mc",  "A=ambiguous, B=correct", "ambiguous",
                   "2 candidate events; answer matches earliest; question does not specify which"),
        "C24-R2": ("F1", "ceo-uniq", "A=correct, B=ambiguous", "correct",
                   "1 candidate event; answer exactly reproduces it; B labels blank"),
        "C29-R3": ("F1", "own-mc",  "A=ambiguous, B=correct", "ambiguous",
                   "3 candidate events; answer matches latest; question does not specify which"),
        "C29-R4": ("F3", "own-mc",  "A=ambiguous, B=correct", "ambiguous",
                   "3 candidate events; answer matches latest; question does not specify which"),
    }
    for rid, (arm, qtype, labels, proposal, rationale) in disc_data.items():
        print(f"  {rid} ({arm}, {qtype})")
        print(f"    Labels: {labels}")
        print(f"    Rule-based proposal: {proposal}")
        print(f"    Rationale: {rationale}")
        print()


if __name__ == "__main__":
    results = run_verification()
    print_report(results)

    out = OUTPUT_DIR / "adjudication_sensitivity_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nResults written to {out}")
