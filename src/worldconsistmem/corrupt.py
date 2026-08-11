"""Controlled corruption suite proving accuracy ≠ consistency."""

from __future__ import annotations

import copy
from typing import Any, Optional

from .models import Prediction, Query, QueryBundle
from .predict import gold_predictions


def _clone_preds(preds: list[Prediction], system_id: str, run_id: str) -> list[Prediction]:
    out = []
    for p in preds:
        out.append(
            Prediction(
                bundle_id=p.bundle_id,
                query_id=p.query_id,
                predicted_answer=copy.deepcopy(p.predicted_answer),
                predicted_provenance=copy.deepcopy(p.predicted_provenance),
                system_id=system_id,
                run_id=run_id,
                metadata={**p.metadata, "corruption": run_id},
            )
        )
    return out


def _by_qid(preds: list[Prediction]) -> dict[str, Prediction]:
    return {p.query_id: p for p in preds}


def _slot_query(bundle: QueryBundle, slot: str) -> Optional[Query]:
    for q in bundle.queries:
        if q.metadata.get("slot") == slot:
            return q
    return None


def corrupt_single_answer(bundle: QueryBundle, gold: list[Prediction]) -> list[Prediction]:
    preds = _clone_preds(gold, "corrupt", "single_answer")
    q = _slot_query(bundle, "ceo_current") or bundle.queries[0]
    pm = _by_qid(preds)
    # Flip entity / boolean / scalar
    ans = pm[q.query_id].predicted_answer
    if isinstance(ans, bool):
        pm[q.query_id].predicted_answer = not ans
    elif isinstance(ans, (int, float)):
        pm[q.query_id].predicted_answer = ans + 1
    elif isinstance(ans, str):
        pm[q.query_id].predicted_answer = ans + "__WRONG"
    elif isinstance(ans, dict):
        pm[q.query_id].predicted_answer = {**ans, "_corrupt": True}
    else:
        pm[q.query_id].predicted_answer = "WRONG"
    return preds


def corrupt_entity_swap(bundle: QueryBundle, gold: list[Prediction]) -> list[Prediction]:
    """Swap related entity answers to break relational consistency while looking plausible."""
    preds = _clone_preds(gold, "corrupt", "entity_swap")
    pm = _by_qid(preds)
    q_ceo = _slot_query(bundle, "ceo_current")
    q_emp = _slot_query(bundle, "ceo_employer")
    q_con = _slot_query(bundle, "ceo_contradiction")
    if q_ceo and q_emp:
        # Keep CEO correct; set employer to a different org id string
        pm[q_emp.query_id].predicted_answer = str(pm[q_emp.query_id].predicted_answer) + "_OTHER"
        if q_con:
            # Also assert dual exclusive holders — uniqueness violation
            pm[q_con.query_id].predicted_answer = True
        return preds
    q_own = _slot_query(bundle, "owner_current")
    q_align = _slot_query(bundle, "owner_mgr_align")
    if q_own and q_align:
        # Dual owners (list) breaks uniqueness; flip alignment for relational
        cur = pm[q_own.query_id].predicted_answer
        pm[q_own.query_id].predicted_answer = [cur, str(cur) + "_OTHER"]
        pm[q_align.query_id].predicted_answer = not bool(pm[q_align.query_id].predicted_answer)
        return preds
    # fallback
    return corrupt_single_answer(bundle, gold)


def corrupt_temporal_mismatch(bundle: QueryBundle, gold: list[Prediction]) -> list[Prediction]:
    preds = _clone_preds(gold, "corrupt", "temporal_mismatch")
    pm = _by_qid(preds)
    q_tr = (
        _slot_query(bundle, "ceo_transition")
        or _slot_query(bundle, "owner_transition")
        or _slot_query(bundle, "doc_transition")
        or _slot_query(bundle, "emp_transition")
    )
    q_hist = (
        _slot_query(bundle, "ceo_historical")
        or _slot_query(bundle, "owner_historical")
        or _slot_query(bundle, "doc_hist_version")
    )
    if q_tr and isinstance(pm[q_tr.query_id].predicted_answer, dict):
        tr = copy.deepcopy(pm[q_tr.query_id].predicted_answer)
        hist_t = q_hist.target_time if q_hist else 1
        tr["t"] = max(0, (hist_t or 1) - 1)
        pm[q_tr.query_id].predicted_answer = tr
    q_ord = _slot_query(bundle, "ceo_order") or _slot_query(bundle, "doc_order")
    if q_ord:
        pm[q_ord.query_id].predicted_answer = False
    return preds


def corrupt_wrong_provenance(bundle: QueryBundle, gold: list[Prediction]) -> list[Prediction]:
    preds = _clone_preds(gold, "corrupt", "wrong_provenance")
    pm = _by_qid(preds)
    q_p = (
        _slot_query(bundle, "ceo_provenance")
        or _slot_query(bundle, "owner_provenance")
        or _slot_query(bundle, "doc_provenance")
        or _slot_query(bundle, "emp_provenance")
        or _slot_query(bundle, "conf_provenance")
    )
    if q_p:
        pm[q_p.query_id].predicted_answer = "prov:NOT_A_REAL_SOURCE"
        pm[q_p.query_id].predicted_provenance = "prov:NOT_A_REAL_SOURCE"
    return preds


def corrupt_transition_inconsistency(bundle: QueryBundle, gold: list[Prediction]) -> list[Prediction]:
    preds = _clone_preds(gold, "corrupt", "transition_inconsistency")
    pm = _by_qid(preds)
    q_tr = _slot_query(bundle, "ceo_transition") or _slot_query(bundle, "owner_transition")
    q_cur = _slot_query(bundle, "ceo_current") or _slot_query(bundle, "owner_current")
    q_hist = _slot_query(bundle, "ceo_historical") or _slot_query(bundle, "owner_historical")
    if q_tr and q_cur and q_hist and isinstance(pm[q_tr.query_id].predicted_answer, dict):
        tr = copy.deepcopy(pm[q_tr.query_id].predicted_answer)
        # Swap from/to direction while leaving current/historical correct
        tr["from"], tr["to"] = tr.get("to"), tr.get("from")
        pm[q_tr.query_id].predicted_answer = tr
    return preds


def corrupt_multihop_inconsistency(bundle: QueryBundle, gold: list[Prediction]) -> list[Prediction]:
    preds = _clone_preds(gold, "corrupt", "multihop_inconsistency")
    pm = _by_qid(preds)
    q_hop = _slot_query(bundle, "ceo_employer") or _slot_query(bundle, "owner_mgr_align")
    if q_hop:
        ans = pm[q_hop.query_id].predicted_answer
        if isinstance(ans, bool):
            pm[q_hop.query_id].predicted_answer = not ans
        else:
            pm[q_hop.query_id].predicted_answer = str(ans) + "_HOP_BREAK"
    return preds


def corrupt_high_acc_inconsistent(bundle: QueryBundle, gold: list[Prediction]) -> list[Prediction]:
    """Change only one answer so mean Acc stays high (≥1-1/n) but BCR=0."""
    preds = _clone_preds(gold, "corrupt", "high_acc_inconsistent")
    pm = _by_qid(preds)
    # Single provenance corruption keeps Acc high while breaking BCR.
    q_p = (
        _slot_query(bundle, "ceo_provenance")
        or _slot_query(bundle, "owner_provenance")
        or _slot_query(bundle, "doc_provenance")
        or _slot_query(bundle, "emp_provenance")
        or _slot_query(bundle, "conf_provenance")
    )
    if q_p:
        pm[q_p.query_id].predicted_answer = "prov:SUPERSEDED_OR_WRONG"
        pm[q_p.query_id].predicted_provenance = "prov:SUPERSEDED_OR_WRONG"
        return preds
    q_tr = _slot_query(bundle, "ceo_transition") or _slot_query(bundle, "owner_transition")
    if q_tr and isinstance(pm[q_tr.query_id].predicted_answer, dict):
        tr = copy.deepcopy(pm[q_tr.query_id].predicted_answer)
        tr["t"] = 0
        pm[q_tr.query_id].predicted_answer = tr
    return preds


def corrupt_consistent_wrong_world(bundle: QueryBundle, gold: list[Prediction]) -> list[Prediction]:
    """Internally coherent alternate history with low accuracy."""
    preds = _clone_preds(gold, "corrupt", "consistent_wrong_world")
    pm = _by_qid(preds)
    # CEO bundle: pretend first CEO never replaced
    q_cur = _slot_query(bundle, "ceo_current")
    q_hist = _slot_query(bundle, "ceo_historical")
    q_tr = _slot_query(bundle, "ceo_transition")
    q_emp = _slot_query(bundle, "ceo_employer")
    q_prov = _slot_query(bundle, "ceo_provenance")
    q_cf = _slot_query(bundle, "ceo_counterfactual")
    q_con = _slot_query(bundle, "ceo_contradiction")
    if q_cur and q_hist and q_tr:
        hist_person = pm[q_hist.query_id].predicted_answer
        pm[q_cur.query_id].predicted_answer = hist_person
        pm[q_tr.query_id].predicted_answer = {
            "from": hist_person,
            "to": hist_person,
            "t": pm[q_tr.query_id].predicted_answer.get("t")
            if isinstance(pm[q_tr.query_id].predicted_answer, dict)
            else 0,
            "role": "CEO",
            "org_id": q_tr.structured.get("org_id"),
        }
        hist_prov = q_hist.supporting_provenance_ids[0] if q_hist.supporting_provenance_ids else None
        if q_emp:
            pm[q_emp.query_id].predicted_answer = q_cur.structured.get("org_id")
        if q_prov and hist_prov:
            pm[q_prov.query_id].predicted_answer = hist_prov
            pm[q_prov.query_id].predicted_provenance = hist_prov
        if q_cf:
            pm[q_cf.query_id].predicted_answer = False
        if q_con:
            pm[q_con.query_id].predicted_answer = False
        return preds

    # Ownership: pretend no transfer
    q_oc = _slot_query(bundle, "owner_current")
    q_oh = _slot_query(bundle, "owner_historical")
    q_ot = _slot_query(bundle, "owner_transition")
    q_om = _slot_query(bundle, "owner_mgr_align")
    q_op = _slot_query(bundle, "owner_provenance")
    q_cv = _slot_query(bundle, "conflict_no_silent_resolution")
    if q_oc and q_oh and q_ot:
        hist_owner = pm[q_oh.query_id].predicted_answer
        pm[q_oc.query_id].predicted_answer = hist_owner
        pm[q_ot.query_id].predicted_answer = {
            "from": hist_owner,
            "to": hist_owner,
            "t": (q_oh.target_time or 0) + 1,
            "project_id": q_ot.structured.get("project_id"),
        }
        if q_om:
            mgr_org = q_om.metadata.get("manager_org")
            pm[q_om.query_id].predicted_answer = mgr_org == hist_owner
        if q_op:
            prov = q_oh.supporting_provenance_ids[0] if q_oh.supporting_provenance_ids else "init"
            pm[q_op.query_id].predicted_answer = prov
            pm[q_op.query_id].predicted_provenance = prov
        if q_cv:
            pm[q_cv.query_id].predicted_answer = False
        return preds

    # Document: pretend never revised (stay at historical version)
    q_dv = _slot_query(bundle, "doc_version")
    q_dh = _slot_query(bundle, "doc_hist_version")
    q_dt = _slot_query(bundle, "doc_transition")
    q_da = _slot_query(bundle, "doc_approve_project")
    q_dp = _slot_query(bundle, "doc_provenance")
    if q_dv and q_dh and q_dt:
        hist_v = pm[q_dh.query_id].predicted_answer
        pm[q_dv.query_id].predicted_answer = hist_v
        pm[q_dt.query_id].predicted_answer = {
            "from_version": hist_v,
            "to_version": hist_v,
            "t": (q_dh.target_time or 0) + 1,
            "base_doc_id": q_dt.structured.get("base_doc_id"),
        }
        if q_dp:
            prov = q_dh.supporting_provenance_ids[0] if q_dh.supporting_provenance_ids else None
            if prov:
                pm[q_dp.query_id].predicted_answer = prov
                pm[q_dp.query_id].predicted_provenance = prov
        # keep approve/project structure; may remain gold (hurts Acc less)
        return preds

    # Employment: pretend person never left
    q_ec = _slot_query(bundle, "emp_current")
    q_eh = _slot_query(bundle, "emp_historical")
    q_et = _slot_query(bundle, "emp_transition")
    q_er = _slot_query(bundle, "emp_role_compat")
    q_ep = _slot_query(bundle, "emp_provenance")
    q_econ = _slot_query(bundle, "emp_contradiction")
    if q_ec and q_eh and q_et:
        pm[q_ec.query_id].predicted_answer = True
        pm[q_eh.query_id].predicted_answer = True
        person = q_et.structured.get("person_id")
        org = q_et.structured.get("org_id")
        pm[q_et.query_id].predicted_answer = {
            "person_id": person,
            "org_id": org,
            "t": (q_eh.target_time or 1) + 1,
            "action": "stay",
        }
        if q_er:
            pm[q_er.query_id].predicted_answer = True
        if q_ep:
            # cite historical join provenance if available
            prov = q_eh.supporting_provenance_ids[0] if q_eh.supporting_provenance_ids else None
            if prov:
                pm[q_ep.query_id].predicted_answer = prov
                pm[q_ep.query_id].predicted_provenance = prov
        if q_econ:
            pm[q_econ.query_id].predicted_answer = False
        return preds

    # Conflict: pretend still unresolved (coherent non-resolution)
    q_cr = _slot_query(bundle, "conf_resolved")
    q_cu = _slot_query(bundle, "conf_unresolved_hist")
    q_cv2 = _slot_query(bundle, "conf_value")
    q_ct = _slot_query(bundle, "conf_transition")
    q_cp = _slot_query(bundle, "conf_provenance")
    q_ccf = _slot_query(bundle, "conf_counterfactual")
    if q_cr and q_cu and q_ct:
        pm[q_cr.query_id].predicted_answer = False
        pm[q_cu.query_id].predicted_answer = True
        if q_cv2:
            pm[q_cv2.query_id].predicted_answer = None
        pm[q_ct.query_id].predicted_answer = {
            "conflict_id": q_ct.structured.get("conflict_id"),
            "t": (q_cu.target_time or 0) + 1,
            "resolved_value": None,
        }
        if q_cp:
            # cite introduction provenance for unresolved claim
            intro = q_cu.supporting_provenance_ids[0] if q_cu.supporting_provenance_ids else None
            if intro:
                pm[q_cp.query_id].predicted_answer = intro
                pm[q_cp.query_id].predicted_provenance = intro
        if q_ccf:
            pm[q_ccf.query_id].predicted_answer = False
        return preds

    for q in bundle.queries:
        ans = pm[q.query_id].predicted_answer
        if isinstance(ans, bool):
            pm[q.query_id].predicted_answer = not ans
        elif isinstance(ans, str):
            pm[q.query_id].predicted_answer = "ALT_" + ans
    return preds


CORRUPTION_FN = {
    "single_answer": corrupt_single_answer,
    "entity_swap": corrupt_entity_swap,
    "temporal_mismatch": corrupt_temporal_mismatch,
    "wrong_provenance": corrupt_wrong_provenance,
    "transition_inconsistency": corrupt_transition_inconsistency,
    "multihop_inconsistency": corrupt_multihop_inconsistency,
    "high_acc_inconsistent": corrupt_high_acc_inconsistent,
    "consistent_wrong_world": corrupt_consistent_wrong_world,
}


def apply_all_corruptions(
    bundles: list[QueryBundle],
) -> dict[str, list[Prediction]]:
    """Return map corruption_name -> concatenated predictions across bundles."""
    out: dict[str, list[Prediction]] = {k: [] for k in CORRUPTION_FN}
    for b in bundles:
        gold = gold_predictions([b], system_id="gold", run_id="gold")
        for name, fn in CORRUPTION_FN.items():
            out[name].extend(fn(b, gold))
    return out


def select_example_bundle(bundles: list[QueryBundle]) -> QueryBundle:
    for b in bundles:
        if any(q.metadata.get("slot") == "ceo_current" for q in b.queries):
            return b
    return bundles[0]
