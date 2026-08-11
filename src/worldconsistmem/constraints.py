"""Machine-checkable cross-query constraint library."""

from __future__ import annotations

from typing import Any, Optional

from .generate import GeneratedWorld
from .models import (
    ConstraintFamily,
    ConstraintResult,
    Prediction,
    Query,
    QueryBundle,
    QueryFamily,
)


def _by_slot(queries: list[Query]) -> dict[str, Query]:
    out: dict[str, Query] = {}
    for q in queries:
        slot = q.metadata.get("slot")
        if slot:
            out[slot] = q
    return out


def _pred_map(preds: list[Prediction]) -> dict[str, Prediction]:
    return {p.query_id: p for p in preds}


def _ans(pm: dict[str, Prediction], q: Optional[Query]) -> Any:
    if q is None or q.query_id not in pm:
        return None
    return pm[q.query_id].predicted_answer


def _prov(pm: dict[str, Prediction], q: Optional[Query]) -> Any:
    if q is None or q.query_id not in pm:
        return None
    return pm[q.query_id].predicted_provenance


def _result(
    passed: bool,
    ctype: ConstraintFamily,
    cid: str,
    qids: list[str],
    values: dict[str, Any],
    explanation: str,
    evidence: dict[str, Any],
) -> ConstraintResult:
    return ConstraintResult(
        passed=passed,
        constraint_type=ctype,
        constraint_id=cid,
        involved_query_ids=qids,
        involved_predicted_values=values,
        explanation=explanation,
        gold_evidence=evidence,
    )


def check_bundle_constraints(
    world: GeneratedWorld,
    bundle: QueryBundle,
    predictions: list[Prediction],
) -> list[ConstraintResult]:
    """Evaluate all applicable machine-checkable constraints for a bundle."""
    slots = _by_slot(bundle.queries)
    pm = _pred_map(predictions)
    results: list[ConstraintResult] = []

    # --- Uniqueness: exclusive role / owner / canonical version ---
    if "ceo_current" in slots and "ceo_contradiction" in slots:
        q_cur, q_con = slots["ceo_current"], slots["ceo_contradiction"]
        cur = _ans(pm, q_cur)
        conj = _ans(pm, q_con)
        # If system says both can be CEO (True) while asserting a single current CEO, fail uniqueness
        passed = not (conj is True and cur is not None)
        # Also: contradiction gold is False; if they answer True that's a uniqueness failure signal
        if conj is True:
            passed = False
        results.append(
            _result(
                passed,
                ConstraintFamily.UNIQUENESS,
                f"{bundle.bundle_id}:uniq_ceo",
                [q_cur.query_id, q_con.query_id],
                {"ceo_current": cur, "ceo_contradiction": conj},
                "Exclusive CEO cannot be dual-held at final time."
                if not passed
                else "Uniqueness OK for exclusive CEO.",
                {"gold_ceo": q_cur.gold_answer, "gold_contradiction": q_con.gold_answer},
            )
        )

    if "owner_current" in slots:
        q = slots["owner_current"]
        # Uniqueness of owner: answer must be a single entity id (not a list of two)
        ans = _ans(pm, q)
        passed = not isinstance(ans, list)
        results.append(
            _result(
                passed,
                ConstraintFamily.UNIQUENESS,
                f"{bundle.bundle_id}:uniq_owner",
                [q.query_id],
                {"owner_current": ans},
                "Ownership must be a single exclusive org."
                if not passed
                else "Single owner uniqueness OK.",
                {"gold_owner": q.gold_answer},
            )
        )

    if "doc_version" in slots:
        q = slots["doc_version"]
        ans = _ans(pm, q)
        passed = isinstance(ans, int) or (isinstance(ans, str) and str(ans).isdigit())
        results.append(
            _result(
                passed,
                ConstraintFamily.UNIQUENESS,
                f"{bundle.bundle_id}:uniq_doc",
                [q.query_id],
                {"doc_version": ans},
                "Canonical version must be a single scalar."
                if not passed
                else "Canonical document uniqueness OK.",
                {"gold_version": q.gold_answer},
            )
        )

    # --- Temporal ordering ---
    for slot_name in ("ceo_order", "doc_order"):
        if slot_name not in slots:
            continue
        q = slots[slot_name]
        ans = _ans(pm, q)
        t_before = q.metadata.get("t_before")
        t_after = q.metadata.get("t_after")
        # Predicted boolean must agree with ordering of gold times if claiming order
        coherent = (t_before is not None and t_after is not None and t_before < t_after)
        passed = (ans is True and coherent) or (ans is False and not coherent)
        # Also fail if answer says True but transition time precedes historical (checked elsewhere)
        results.append(
            _result(
                passed,
                ConstraintFamily.TEMPORAL,
                f"{bundle.bundle_id}:temp_{slot_name}",
                [q.query_id],
                {slot_name: ans},
                "Temporal order answer inconsistent with event times."
                if not passed
                else "Temporal order OK.",
                {"t_before": t_before, "t_after": t_after},
            )
        )

    # --- State-transition consistency (current/historical/transition triad) ---
    triad_specs = [
        ("ceo_current", "ceo_historical", "ceo_transition", "from", "to", "t"),
        ("owner_current", "owner_historical", "owner_transition", "from", "to", "t"),
        ("doc_version", "doc_hist_version", "doc_transition", "to_version", "from_version", "t"),
        ("emp_current", "emp_historical", "emp_transition", None, None, "t"),
        ("conf_resolved", "conf_unresolved_hist", "conf_transition", None, None, "t"),
    ]
    for cur_s, hist_s, tr_s, from_k, to_k, t_k in triad_specs:
        if not (cur_s in slots and hist_s in slots and tr_s in slots):
            continue
        q_c, q_h, q_t = slots[cur_s], slots[hist_s], slots[tr_s]
        a_c, a_h, a_t = _ans(pm, q_c), _ans(pm, q_h), _ans(pm, q_t)
        passed = True
        expl = "Transition triad consistent."
        if not isinstance(a_t, dict):
            passed = False
            expl = "Transition answer must be a structured tuple/dict."
        else:
            if from_k and to_k:
                # CEO / ownership style
                if cur_s.startswith("doc"):
                    # doc uses from_version/to_version; current is version scalar
                    if a_t.get("to_version") != a_c or a_t.get("from_version") != a_h:
                        passed = False
                        expl = "Document transition versions disagree with current/historical answers."
                    if a_t.get(t_k) is not None and q_h.target_time is not None:
                        if a_t[t_k] <= q_h.target_time:
                            passed = False
                            expl = "Revision time does not postdate historical version time."
                else:
                    if a_t.get(to_k) != a_c or a_t.get(from_k) != a_h:
                        passed = False
                        expl = "Transition from/to disagree with historical/current answers."
                    if a_t.get(t_k) is not None and q_h.target_time is not None:
                        if a_t[t_k] <= q_h.target_time:
                            passed = False
                            expl = "Transition time does not postdate historical query time."
            else:
                # employment / conflict: transition t must postdate historical
                if a_t.get(t_k) is not None and q_h.target_time is not None:
                    if a_t[t_k] <= q_h.target_time:
                        passed = False
                        expl = "Transition time inconsistent with historical time."
                # employment: if current says not employed and hist says employed, leave must exist
                if cur_s == "emp_current":
                    if a_h is True and a_c is True and a_t.get("action") == "leave":
                        passed = False
                        expl = "Cannot currently be employed after a leave transition without rehire."
                if cur_s == "conf_resolved":
                    if a_c is True and a_h is True and a_t.get("t") is not None:
                        # unresolved historically and resolved now is OK
                        pass
                    if a_c is False and isinstance(a_t, dict) and a_t.get("resolved_value"):
                        passed = False
                        expl = "Unresolved current conflict cannot cite a definitive resolution value."

        # Also emit temporal family when transition time precedes historical target
        if (
            isinstance(a_t, dict)
            and a_t.get(t_k) is not None
            and q_h.target_time is not None
            and a_t[t_k] <= q_h.target_time
        ):
            results.append(
                _result(
                    False,
                    ConstraintFamily.TEMPORAL,
                    f"{bundle.bundle_id}:temp_trans_{cur_s}",
                    [q_c.query_id, q_h.query_id, q_t.query_id],
                    {"transition_t": a_t.get(t_k), "historical_t": q_h.target_time},
                    "Reported transition time does not postdate historical state time.",
                    {"gold_transition": q_t.gold_answer},
                )
            )

        results.append(
            _result(
                passed,
                ConstraintFamily.TRANSITION,
                f"{bundle.bundle_id}:trans_{cur_s}",
                [q_c.query_id, q_h.query_id, q_t.query_id],
                {"current": a_c, "historical": a_h, "transition": a_t},
                expl,
                {
                    "gold_current": q_c.gold_answer,
                    "gold_historical": q_h.gold_answer,
                    "gold_transition": q_t.gold_answer,
                },
            )
        )

    # --- Relational consistency ---
    if "ceo_current" in slots and "ceo_employer" in slots:
        q_c, q_e = slots["ceo_current"], slots["ceo_employer"]
        a_c, a_e = _ans(pm, q_c), _ans(pm, q_e)
        # Employer of current CEO must be the CEO's org (ceo_org) if still employed there
        expected_org = world.meta["ceo_org"]
        # Relational: if they name person P as CEO of org A, employer answer should be A
        # (unless person left — gold CEO is still employed)
        passed = a_e == expected_org or a_e == world.final.employer_of(a_c) if a_c else False
        # Simpler mutual check: predicted employer must equal employer_of(predicted CEO) in gold world
        # OR equal predicted consistency: employer == ceo_org when CEO is of ceo_org
        gold_emp = world.final.employer_of(a_c) if isinstance(a_c, str) else None
        passed = a_e == gold_emp
        # For consistent-wrong alternate worlds, allow internal: employer == ceo_org when claiming CEO of that org
        if not passed and a_e == expected_org and a_c is not None:
            # Still fail against gold relational binding unless alternate coherent mode:
            # Internal relational: CEO-of-org implies employed-by-org
            passed = a_e == expected_org
        results.append(
            _result(
                passed,
                ConstraintFamily.RELATIONAL,
                f"{bundle.bundle_id}:rel_ceo_emp",
                [q_c.query_id, q_e.query_id],
                {"ceo": a_c, "employer": a_e},
                "CEO and employer answers are relationally inconsistent."
                if not passed
                else "CEO–employer relational consistency OK.",
                {"ceo_org": expected_org, "gold_emp_of_pred_ceo": gold_emp},
            )
        )

    if "owner_current" in slots and "owner_mgr_align" in slots:
        q_o, q_m = slots["owner_current"], slots["owner_mgr_align"]
        a_o, a_m = _ans(pm, q_o), _ans(pm, q_m)
        mgr = q_m.metadata.get("manager_id")
        mgr_org_gold = world.final.employer_of(mgr) if mgr else None
        # Predicted boolean must equal (mgr_org == predicted_owner) for internal consistency
        expected_bool = mgr_org_gold == a_o if a_o is not None else None
        passed = a_m == expected_bool
        results.append(
            _result(
                passed,
                ConstraintFamily.RELATIONAL,
                f"{bundle.bundle_id}:rel_owner_mgr",
                [q_o.query_id, q_m.query_id],
                {"owner": a_o, "mgr_align": a_m},
                "Owner/manager alignment disagrees with ownership and employment."
                if not passed
                else "Owner–manager relational consistency OK.",
                {"manager_id": mgr, "manager_org": mgr_org_gold},
            )
        )

    if "doc_approve_project" in slots and "doc_version" in slots:
        q_a, q_v = slots["doc_approve_project"], slots["doc_version"]
        a_a, a_v = _ans(pm, q_a), _ans(pm, q_v)
        passed = isinstance(a_a, dict) and "approver" in a_a and "project_id" in a_a
        if passed and a_a.get("project_id") != world.meta["focal_project"]:
            # still OK if internally linked to same project as gold doc
            pass
        results.append(
            _result(
                bool(passed),
                ConstraintFamily.RELATIONAL,
                f"{bundle.bundle_id}:rel_doc",
                [q_a.query_id, q_v.query_id],
                {"approve_project": a_a, "version": a_v},
                "Document approval relation malformed."
                if not passed
                else "Document relational structure OK.",
                {"gold": q_a.gold_answer},
            )
        )

    # --- Provenance consistency ---
    def _gold_answers_equal(a: Any, b: Any) -> bool:
        return a == b

    # Index provenances that can support a claimed atomic value
    value_to_provs: dict[str, set[str]] = {}
    for e in world.events:
        value_to_provs.setdefault(str(e.provenance_id), set()).add(e.provenance_id)
        for v in e.payload.values():
            value_to_provs.setdefault(str(v), set()).add(e.provenance_id)
        et = e.event_type.value
        if et == "person_joins_org":
            value_to_provs.setdefault("True", set()).add(e.provenance_id)
        if et == "person_leaves_org":
            value_to_provs.setdefault("False", set()).add(e.provenance_id)
        if et == "conflict_introduction":
            value_to_provs.setdefault("False", set()).add(e.provenance_id)
        if et == "conflict_resolution":
            value_to_provs.setdefault("True", set()).add(e.provenance_id)
    for s in world.states:
        for r in s.roles:
            value_to_provs.setdefault(str(r.person_id), set()).add(r.provenance_id)
            value_to_provs.setdefault(str(r.provenance_id), set()).add(r.provenance_id)
        for emp in s.employments:
            value_to_provs.setdefault(str(emp.org_id), set()).add(emp.provenance_id)
            value_to_provs.setdefault(str(emp.person_id), set()).add(emp.provenance_id)
        for o in s.ownerships:
            value_to_provs.setdefault(str(o.org_id), set()).add(o.provenance_id)
            value_to_provs.setdefault(str(o.provenance_id), set()).add(o.provenance_id)
        for d in s.documents.values():
            value_to_provs.setdefault(str(d.version), set()).add(d.provenance_id)
            value_to_provs.setdefault(str(d.provenance_id), set()).add(d.provenance_id)

    # Bundle-local: provenances supporting a gold answer value
    for q in bundle.queries:
        for pid in q.supporting_provenance_ids:
            value_to_provs.setdefault(str(q.gold_answer), set()).add(pid)
            value_to_provs.setdefault(str(pid), set()).add(pid)

    for slot, fact_slot in [
        ("ceo_provenance", "ceo_current"),
        ("owner_provenance", "owner_current"),
        ("doc_provenance", "doc_version"),
        ("emp_provenance", "emp_current"),
        ("conf_provenance", "conf_resolved"),
    ]:
        if slot not in slots:
            continue
        q_p = slots[slot]
        a_p = _ans(pm, q_p)
        cited = _prov(pm, q_p) or a_p
        fact_q = slots.get(fact_slot)
        fact_val = _ans(pm, fact_q) if fact_q else q_p.metadata.get("fact_value")
        gold_support = set(q_p.supporting_provenance_ids)
        if fact_q:
            gold_support |= set(fact_q.supporting_provenance_ids)

        supports = False
        if not isinstance(cited, (str, int)) and cited is not None:
            supports = False
        elif fact_q is not None and _gold_answers_equal(fact_val, fact_q.gold_answer):
            supports = cited in gold_support
        else:
            # Alternate or mismatched fact: cited must support the *claimed* value
            candidates = set(value_to_provs.get(str(fact_val), set()))
            # Also accept historical support when claiming the historical value
            for q in bundle.queries:
                if _gold_answers_equal(q.gold_answer, fact_val):
                    candidates.update(q.supporting_provenance_ids)
            supports = cited in candidates

        results.append(
            _result(
                supports,
                ConstraintFamily.PROVENANCE,
                f"{bundle.bundle_id}:prov_{slot}",
                [q_p.query_id] + ([fact_q.query_id] if fact_q else []),
                {"cited": cited, "fact": fact_val},
                "Cited provenance does not support the claimed fact."
                if not supports
                else "Provenance supports claimed fact.",
                {"gold_provenance": q_p.gold_answer, "gold_support": list(gold_support)},
            )
        )

    # --- Multi-hop consistency ---
    if "ceo_current" in slots and "ceo_employer" in slots:
        q_c, q_e = slots["ceo_current"], slots["ceo_employer"]
        a_c, a_e = _ans(pm, q_c), _ans(pm, q_e)
        # Multi-hop: employer-of(CEO) composition
        composed = world.final.employer_of(a_c) if isinstance(a_c, str) else None
        # Internal multi-hop: if claiming alternate CEO who is employed somewhere, answer must match
        # that person's gold employer OR equal ceo_org for coherent alt world where they never left
        passed = a_e == composed
        if not passed and isinstance(a_c, str):
            # Allow coherent alternate: CEO person still employed at ceo_org in prediction story
            if a_e == world.meta["ceo_org"] and a_c in world.meta["persons"]:
                # Only OK if not contradicting a leave for that person after final — use internal rule:
                # predicted hop equals predicted employer of predicted CEO under *predicted* employment
                # We approximate: hop consistent if employer == org of which they are claimed CEO
                passed = a_e == world.meta["ceo_org"]
        results.append(
            _result(
                passed,
                ConstraintFamily.MULTI_HOP,
                f"{bundle.bundle_id}:hop_ceo",
                [q_c.query_id, q_e.query_id],
                {"ceo": a_c, "employer": a_e, "composed_gold": composed},
                "Multi-hop employer disagrees with CEO component."
                if not passed
                else "Multi-hop CEO→employer OK.",
                {"gold_ceo": q_c.gold_answer, "gold_employer": q_e.gold_answer},
            )
        )

    if "owner_current" in slots and "owner_mgr_align" in slots:
        q_o, q_m = slots["owner_current"], slots["owner_mgr_align"]
        a_o, a_m = _ans(pm, q_o), _ans(pm, q_m)
        mgr = q_m.metadata.get("manager_id")
        mgr_org = world.final.employer_of(mgr) if mgr else None
        expected = (mgr_org == a_o) if a_o is not None else None
        passed = a_m == expected
        results.append(
            _result(
                passed,
                ConstraintFamily.MULTI_HOP,
                f"{bundle.bundle_id}:hop_owner",
                [q_o.query_id, q_m.query_id],
                {"owner": a_o, "align": a_m, "expected": expected},
                "Multi-hop owner/manager composition inconsistent."
                if not passed
                else "Multi-hop ownership composition OK.",
                {"manager_org": mgr_org, "gold_align": q_m.gold_answer},
            )
        )

    if "emp_role_compat" in slots and "emp_current" in slots:
        q_r, q_e = slots["emp_role_compat"], slots["emp_current"]
        a_r, a_e = _ans(pm, q_r), _ans(pm, q_e)
        # If not employed, cannot hold exclusive role → answer should be False when emp_current False
        passed = True
        if a_e is False and a_r is True:
            passed = False
        results.append(
            _result(
                passed,
                ConstraintFamily.MULTI_HOP,
                f"{bundle.bundle_id}:hop_emp_role",
                [q_e.query_id, q_r.query_id],
                {"employed": a_e, "can_hold_role": a_r},
                "Employment/role multi-hop contradiction."
                if not passed
                else "Employment/role hop OK.",
                {"gold_employed": q_e.gold_answer, "gold_role_compat": q_r.gold_answer},
            )
        )

    # --- Contradiction consistency ---
    if "ceo_current" in slots and "ceo_historical" in slots and "ceo_transition" in slots:
        q_c, q_h, q_t = slots["ceo_current"], slots["ceo_historical"], slots["ceo_transition"]
        a_c, a_h, a_t = _ans(pm, q_c), _ans(pm, q_h), _ans(pm, q_t)
        passed = True
        expl = "Current/historical difference justified by transition."
        if a_c != a_h:
            if not isinstance(a_t, dict) or a_t.get("from") != a_h or a_t.get("to") != a_c:
                passed = False
                expl = "Current≠historical without a matching transition."
        else:
            # same person: transition should not claim a different replacement
            if isinstance(a_t, dict) and a_t.get("from") != a_t.get("to") and (
                a_t.get("to") != a_c or a_t.get("from") != a_h
            ):
                # if answers equal but transition claims change — contradiction
                if a_t.get("from") != a_t.get("to"):
                    passed = False
                    expl = "Transition claims CEO change but current=historical."
        results.append(
            _result(
                passed,
                ConstraintFamily.CONTRADICTION,
                f"{bundle.bundle_id}:contr_ceo",
                [q_c.query_id, q_h.query_id, q_t.query_id],
                {"current": a_c, "historical": a_h, "transition": a_t},
                expl,
                {"gold_current": q_c.gold_answer, "gold_historical": q_h.gold_answer},
            )
        )

    if "conflict_no_silent_resolution" in slots and "conf_value" in slots:
        # During unresolved window, definitive priority must not be asserted as current without resolution
        q_n = slots.get("conflict_no_silent_resolution")
        # ownership bundle has this; conflict bundle has conf_value
        pass

    if "conf_unresolved_hist" in slots and "conf_resolved" in slots and "conf_value" in slots:
        q_u, q_r, q_v = slots["conf_unresolved_hist"], slots["conf_resolved"], slots["conf_value"]
        a_u, a_r, a_v = _ans(pm, q_u), _ans(pm, q_r), _ans(pm, q_v)
        passed = True
        expl = "Conflict resolution/contradiction OK."
        if a_u is True and a_r is False and a_v is not None:
            # unresolved now but giving definitive value without resolution — fail
            passed = False
            expl = "Unresolved conflict silently converted into definitive value."
        if a_r is True and a_u is True and a_v is None:
            passed = False
            expl = "Resolved conflict missing resolved value."
        results.append(
            _result(
                passed,
                ConstraintFamily.CONTRADICTION,
                f"{bundle.bundle_id}:contr_conflict",
                [q_u.query_id, q_r.query_id, q_v.query_id],
                {"unresolved_hist": a_u, "resolved_now": a_r, "value": a_v},
                expl,
                {"gold_value": q_v.gold_answer},
            )
        )

    if "ceo_counterfactual" in slots and "ceo_current" in slots:
        q_cf, q_c = slots["ceo_counterfactual"], slots["ceo_current"]
        a_cf, a_c = _ans(pm, q_cf), _ans(pm, q_c)
        false_person = q_cf.metadata.get("false_claim_person")
        # If they claim false_person is current CEO, counterfactual "would contradict" should be False
        # (because they're asserting the false world). If current is gold CEO, counterfactual True.
        passed = True
        if a_c == false_person and a_cf is True:
            passed = False
            expl = "Counterfactual contradiction flag inconsistent with asserted current CEO."
        elif a_c != false_person and a_cf is False:
            passed = False
            expl = "Failed to flag counterfactual contradiction against history."
        else:
            expl = "Counterfactual consistency OK."
        results.append(
            _result(
                passed,
                ConstraintFamily.CONTRADICTION,
                f"{bundle.bundle_id}:contr_cf",
                [q_c.query_id, q_cf.query_id],
                {"current": a_c, "counterfactual": a_cf},
                expl,
                {"false_claim_person": false_person, "gold_ceo": q_c.gold_answer},
            )
        )

    return results


def bundle_is_consistent(results: list[ConstraintResult]) -> bool:
    return all(r.passed for r in results) if results else True
