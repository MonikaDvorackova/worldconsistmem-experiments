"""Round 2 human-evaluation audit and F0-F3 sensitivity analysis (stdlib only).

Three independent layers, kept separate on purpose:

1. Reliability statistics on reviewer labels (agreement, Cohen's kappa).
2. A *structural* audit of each (question, evidence pack, response) triple:
   how many documented events could answer the question, and which of them
   (if any) the response selects. This layer never looks at reviewer labels,
   arm names, or the benchmark gold answer.
3. Gold-referenced scoring of responses under several explicit rules
   (exact tuple v1/v2, question-aligned semantic, tuple-content semantic).

Automated classifications produced here are deterministic rule outputs. They
are not human judgments and must not be reported as such.
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from typing import Any, Iterable, Optional, Sequence

LABELS = ("correct", "incorrect", "ambiguous")
ARMS = ("F0", "F1", "F2", "F3")

# --------------------------------------------------------------------------
# Reliability
# --------------------------------------------------------------------------


def confusion_matrix(a: Sequence[str], b: Sequence[str], labels: Sequence[str] = LABELS) -> dict[str, dict[str, int]]:
    if len(a) != len(b):
        raise ValueError("label sequences differ in length")
    m = {x: {y: 0 for y in labels} for x in labels}
    for x, y in zip(a, b):
        m[x][y] += 1
    return m


def cohen_kappa(a: Sequence[str], b: Sequence[str], labels: Sequence[str] = LABELS) -> dict[str, float]:
    """Unweighted Cohen's kappa. kappa is NaN when expected agreement is 1."""
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("need two non-empty label sequences of equal length")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    kappa = float("nan") if pe >= 1.0 else (po - pe) / (1.0 - pe)
    return {"n": n, "n_agree": sum(x == y for x, y in zip(a, b)), "po": po, "pe": pe, "kappa": kappa}


def cluster_bootstrap_kappa(
    a: Sequence[str], b: Sequence[str], clusters: Sequence[str], n_boot: int = 10000, seed: int = 20261111
) -> dict[str, Any]:
    """Percentile CI for kappa, resampling whole clusters (cases) with replacement."""
    rng = random.Random(seed)
    by: dict[str, list[int]] = {}
    for i, c in enumerate(clusters):
        by.setdefault(c, []).append(i)
    keys = sorted(by)
    vals = []
    for _ in range(n_boot):
        idx = [i for k in (rng.choice(keys) for _ in keys) for i in by[k]]
        k = cohen_kappa([a[i] for i in idx], [b[i] for i in idx])["kappa"]
        if not math.isnan(k):
            vals.append(k)
    vals.sort()
    return {
        "n_clusters": len(keys),
        "n_boot": n_boot,
        "n_defined": len(vals),
        "seed": seed,
        "ci95_lo": _percentile(vals, 2.5),
        "ci95_hi": _percentile(vals, 97.5),
    }


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    pos = (len(sorted_vals) - 1) * q / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


# --------------------------------------------------------------------------
# Statistics for paired arm comparisons
# --------------------------------------------------------------------------


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(x: Sequence[bool], y: Sequence[bool]) -> dict[str, Any]:
    """Exact two-sided McNemar test for paired binary outcomes (y minus x)."""
    b = sum(1 for u, v in zip(x, y) if (not u) and v)  # y only
    c = sum(1 for u, v in zip(x, y) if u and (not v))  # x only
    n = b + c
    if n == 0:
        p = 1.0
    else:
        tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / 2**n
        p = min(1.0, 2 * tail)
    return {"y_only": b, "x_only": c, "n_discordant": n, "p_two_sided": p}


def cluster_bootstrap_diff(
    x: Sequence[bool], y: Sequence[bool], clusters: Sequence[str], n_boot: int = 10000, seed: int = 20261111
) -> dict[str, Any]:
    """Percentile CI for mean(y) - mean(x) on paired items, resampling clusters."""
    n = len(x)
    if n == 0:
        return {"delta": float("nan"), "ci95_lo": float("nan"), "ci95_hi": float("nan"), "n_clusters": 0}
    rng = random.Random(seed)
    by: dict[str, list[int]] = {}
    for i, c in enumerate(clusters):
        by.setdefault(c, []).append(i)
    keys = sorted(by)
    sums = {k: (sum(int(y[i]) - int(x[i]) for i in by[k]), len(by[k])) for k in keys}
    vals = []
    for _ in range(n_boot):
        s = m = 0
        for _k in keys:
            ds, dn = sums[rng.choice(keys)]
            s += ds
            m += dn
        vals.append(s / m)
    vals.sort()
    return {
        "delta": (sum(map(int, y)) - sum(map(int, x))) / n,
        "ci95_lo": _percentile(vals, 2.5),
        "ci95_hi": _percentile(vals, 97.5),
        "n_clusters": len(keys),
        "n_boot": n_boot,
        "seed": seed,
    }


# --------------------------------------------------------------------------
# Questions and evidence
# --------------------------------------------------------------------------

_QUESTION_PATTERNS: tuple[tuple[str, re.Pattern[str], tuple[str, ...]], ...] = (
    ("ceo", re.compile(r"^When and how did the CEO of (\S+) change\?$"), ("org_id",)),
    ("own", re.compile(r"^When did ownership of (\S+) transfer\?$"), ("project_id",)),
    ("conf", re.compile(r"^When was conflict (\S+) resolved\?$"), ("conflict_id",)),
    ("emp", re.compile(r"^When did (\S+) leave (\S+)\?$"), ("person_id", "org_id")),
    ("doc", re.compile(r"^When was (\S+) revised from v(\d+) to v(\d+)\?$"), ("base_doc_id", "from_version", "to_version")),
)

# Fields the user-facing question literally asks for.
ASKED_ROLES: dict[str, tuple[str, ...]] = {
    "ceo": ("time", "from", "to"),  # "When and how"
    "own": ("time",),
    "conf": ("time",),
    "emp": ("time",),
    "doc": ("time",),
}

SLOT_EVENT_TYPE = {
    "ceo": "role_replacement",
    "own": "project_ownership_transfer",
    "conf": "conflict_resolution",
    "emp": "person_leaves_org",
    "doc": "document_revision",
}

AMBIGUITY_SOURCE = {
    "ceo": "multiple CEO replacements for the same organisation",
    "own": "multiple ownership transfers of the same project",
    "conf": "multiple resolutions of the same conflict",
    "emp": "multiple departures of the same person from the same organisation",
    "doc": "multiple revisions of the same base document; evidence carries no version identifiers",
}


def parse_question(text: str) -> dict[str, Any]:
    for slot, pat, names in _QUESTION_PATTERNS:
        m = pat.match(text.strip())
        if m:
            keys = dict(zip(names, m.groups()))
            for k in ("from_version", "to_version"):
                if k in keys:
                    keys[k] = int(keys[k])
            return {"slot": slot, "keys": keys}
    raise ValueError(f"unrecognised question template: {text!r}")


def event_roles(ev: dict) -> dict[str, Any]:
    """Canonical roles asserted by one evidence event (pack format id/s{et,p,t})."""
    s = ev["s"]
    p = s.get("p", {})
    et = s.get("et")
    roles: dict[str, Any] = {"time": s.get("t", ev.get("t"))}
    if et == "role_replacement":
        roles.update({"from": p.get("old_person_id"), "to": p.get("new_person_id"), "org_id": p.get("org_id"), "role": p.get("role")})
    elif et == "project_ownership_transfer":
        roles.update({"from": p.get("old_org_id"), "to": p.get("new_org_id"), "project_id": p.get("project_id")})
    elif et == "conflict_resolution":
        roles.update({"conflict_id": p.get("conflict_id"), "resolved_value": p.get("resolved_value")})
    elif et == "person_leaves_org":
        roles.update({"person_id": p.get("person_id"), "org_id": p.get("org_id"), "action": "leave"})
    elif et == "document_revision":
        roles.update({"base_doc_id": p.get("base_doc_id"), "doc_id": p.get("doc_id")})
        # Version identifiers are only present if the pack states them.
        if "expected_prev_version" in p:
            roles.update({"from_version": p["expected_prev_version"], "to_version": p["expected_prev_version"] + 1})
    return roles


def candidate_events(question: dict[str, Any], evidence: Iterable[dict]) -> list[dict]:
    """Evidence events of the asked transition type about the asked entity, by time.

    Version numbers in document questions are not used for filtering: whether
    the pack can identify the asked version transition is assessed separately.
    """
    slot, keys = question["slot"], question["keys"]
    out = []
    for ev in evidence:
        if ev["s"].get("et") != SLOT_EVENT_TYPE[slot]:
            continue
        roles = event_roles(ev)
        if all(roles.get(k) == v for k, v in keys.items() if k not in ("from_version", "to_version")):
            out.append({"id": ev["id"], "t": roles["time"], "roles": roles})
    return sorted(out, key=lambda e: e["t"])


def chronology(evidence: Iterable[dict]) -> str:
    """Compact, time-ordered rendering of every evidence event."""
    parts = []
    for ev in sorted(evidence, key=lambda e: (e["s"].get("t", e.get("t")), e["id"])):
        p = ev["s"].get("p", {})
        short = {k: (v.split(":", 1)[1] if isinstance(v, str) and ":" in v else v) for k, v in sorted(p.items())}
        parts.append(f"t={ev['s'].get('t', ev.get('t'))} {ev['s'].get('et')} {json.dumps(short, sort_keys=True)} [{ev['id']}]")
    return " | ".join(parts)


# --------------------------------------------------------------------------
# Responses
# --------------------------------------------------------------------------

_PREV = {"prev_state", "previous_state"}
_NEXT = {"next_state", "resulting_state", "result_state", "new_state"}
_TIME_KEYS = {"t", "time", "when", "timestamp"}
_VERSION_RE = re.compile(r"^v?(\d+)$")


def parse_response(raw: str) -> dict[str, Any]:
    """Parse a raw model response without penalising wrapper shape.

    Accepts ``{"answer": X, "abstain": ..}`` wrappers and bare JSON values.
    """
    try:
        d = json.loads(raw)
    except (TypeError, ValueError):
        return {"parse_ok": False, "abstain": False, "answer": None, "wrapped": False}
    if isinstance(d, dict) and "answer" in d:
        ans = d["answer"]
        abstain = bool(d.get("abstain")) or ans is None
        return {"parse_ok": True, "abstain": abstain, "answer": ans, "wrapped": True}
    if isinstance(d, dict) and d.get("abstain") is True:
        return {"parse_ok": True, "abstain": True, "answer": None, "wrapped": False}
    return {"parse_ok": True, "abstain": d is None, "answer": d, "wrapped": False}


def _norm_time(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return v


def _norm_version(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        m = _VERSION_RE.match(v.strip())
        if m:
            return int(m.group(1))
    return v


def _leaves(x: Any, path: tuple[str, ...] = ()):  # dict leaves only; lists handled by caller
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _leaves(v, path + (str(k),))
    elif isinstance(x, list):
        for v in x:
            yield from _leaves(v, path + ("[]",))
    else:
        yield path, x


def _role_for(slot: str, path: tuple[str, ...]) -> Optional[str]:
    key = path[-1]
    parents = {p.lower() for p in path[:-1]}
    in_prev, in_next = bool(parents & _PREV), bool(parents & _NEXT)
    lk = key.lower()
    if lk in _TIME_KEYS:
        return "time"
    if slot == "ceo":
        if lk in ("ceo", "person_id") and (in_prev or in_next):
            return "from" if in_prev else "to"
        if lk in ("from", "old_person_id"):
            return "from"
        if lk in ("to", "new_person_id"):
            return "to"
        if lk in ("org_id", "role"):
            return lk
    elif slot == "own":
        if lk in ("owner", "owner_org_id", "org_id") and (in_prev or in_next):
            return "from" if in_prev else "to"
        if lk in ("from", "old_org_id", "from_org_id"):
            return "from"
        if lk in ("to", "new_org_id", "to_org_id"):
            return "to"
        if lk == "project_id":
            return lk
    elif slot == "conf":
        if lk in ("conflict_id", "resolved_value"):
            return lk
    elif slot == "emp":
        if lk in ("person_id", "org_id", "action"):
            return lk
    elif slot == "doc":
        if lk in ("base_doc_id", "from_version", "to_version"):
            return lk
        if lk == "doc_id":
            return "prev_doc_id" if in_prev else "doc_id"
    return None


def _claim_from(slot: str, obj: Any) -> Optional[dict[str, set]]:
    if isinstance(obj, bool) or obj is None:
        return None
    if isinstance(obj, (int, str)):
        t = _norm_time(obj)
        return {"time": {t}} if isinstance(t, int) else None
    if isinstance(obj, dict):
        claim: dict[str, set] = {}
        for path, v in _leaves(obj):
            role = _role_for(slot, path)
            if role is None or isinstance(v, (dict, list)) or v is None:
                continue
            if role == "time":
                v = _norm_time(v)
            elif role in ("from_version", "to_version"):
                v = _norm_version(v)
            claim.setdefault(role, set()).add(v)
        return claim or None
    return None


def extract_claims(slot: str, answer: Any) -> list[dict[str, set]]:
    """Answer-bearing content as role -> set(values); a list answer yields one claim per element."""
    if isinstance(answer, list):
        return [c for c in (_claim_from(slot, x) for x in answer) if c]
    c = _claim_from(slot, answer)
    return [c] if c else []


def claim_matches_roles(slot: str, claim: dict[str, set], roles: dict[str, Any], ignore: Sequence[str] = ()) -> bool:
    """True iff the claim states every asked field with the target's value and
    contradicts none of the other fields the target defines."""
    for r in ASKED_ROLES[slot]:
        if claim.get(r) != {roles.get(r)}:
            return False
    for r, vals in claim.items():
        if r in ignore or r not in roles or roles[r] is None:
            continue
        if vals != {roles[r]}:
            return False
    return True


def claim_summary(claim: dict[str, set]) -> str:
    def short(v: Any) -> Any:
        return v.split(":", 1)[1] if isinstance(v, str) and ":" in v else v

    return json.dumps({k: sorted((short(v) for v in vs), key=str) for k, vs in sorted(claim.items())}, sort_keys=True)


# Structural audit classes (no labels, no arm, no gold).
SUPPORTED_UNIQUE = "supported_answer_unique_question"
SUPPORTED_AMBIGUOUS = "supported_event_ambiguous_question"
INSUFFICIENT = "insufficient_evidence"
CONTRADICTED = "contradicted_answer"
DEFECT = "other_evaluation_defect"


def question_status(question: dict[str, Any], cands: Sequence[dict]) -> str:
    """unique | multi_candidate | version_unidentifiable | no_candidate (evidence-only)."""
    if not cands:
        return "no_candidate"
    if question["slot"] == "doc":
        k = question["keys"]
        hits = [c for c in cands if c["roles"].get("from_version") == k["from_version"] and c["roles"].get("to_version") == k["to_version"]]
        return "unique" if len(hits) == 1 else "version_unidentifiable"
    return "unique" if len(cands) == 1 else "multi_candidate"


def audit_response(question_text: str, evidence: Sequence[dict], raw: str) -> dict[str, Any]:
    """Structural audit of one (question, evidence, response) triple."""
    q = parse_question(question_text)
    slot = q["slot"]
    cands = candidate_events(q, evidence)
    status = question_status(q, cands)
    parsed = parse_response(raw)
    claims = extract_claims(slot, parsed["answer"]) if parsed["parse_ok"] and not parsed["abstain"] else []
    matched: list[dict] = []
    for claim in claims:
        for c in cands:
            if claim_matches_roles(slot, claim, c["roles"]) and c not in matched:
                matched.append(c)
    positions = []
    for m in matched:
        i = cands.index(m)
        positions.append("only" if len(cands) == 1 else "earliest" if i == 0 else "latest" if i == len(cands) - 1 else "middle")

    if not parsed["parse_ok"]:
        cls, why = DEFECT, "response is not parseable JSON"
    elif parsed["abstain"]:
        cls = CONTRADICTED if status == "unique" else INSUFFICIENT
        why = "abstention although the evidence identifies one event" if status == "unique" else "abstention; the evidence does not identify one asked event"
    elif status == "no_candidate":
        cls, why = INSUFFICIENT, "the evidence contains no event of the asked type for the asked entity"
    elif status == "version_unidentifiable":
        cls = INSUFFICIENT
        why = (
            f"the question asks for the v{q['keys']['from_version']}->v{q['keys']['to_version']} revision but the "
            f"{len(cands)} documented revision(s) carry no version identifiers, so the asked event cannot be identified"
        )
    elif len(claims) != 1:
        cls = SUPPORTED_AMBIGUOUS if status == "multi_candidate" and matched else CONTRADICTED
        why = f"response enumerates {len(claims)} events instead of answering with one"
    elif not matched:
        cls, why = CONTRADICTED, "the stated answer matches none of the documented candidate events"
    elif status == "unique":
        cls, why = SUPPORTED_UNIQUE, "exactly one documented event fits the question and the answer matches it"
    else:
        cls = SUPPORTED_AMBIGUOUS
        why = (
            f"the answer matches a documented event ({positions[0]} of {len(cands)} candidates), but the question "
            f"does not say which of the {len(cands)} events is meant ({AMBIGUITY_SOURCE[slot]})"
        )
    return {
        "slot": slot,
        "question_keys": q["keys"],
        "n_evidence_events": len(evidence),
        "candidates": cands,
        "question_status": status,
        "question_unique": status == "unique",
        "parse_ok": parsed["parse_ok"],
        "abstain": parsed["abstain"],
        "wrapped": parsed["wrapped"],
        "claims": claims,
        "matched": matched,
        "matched_positions": positions,
        "audit_class": cls,
        "reasoning": why,
    }


# --------------------------------------------------------------------------
# Gold-referenced scoring
# --------------------------------------------------------------------------

_V2_ALIASES = {"from": ("old_person_id",), "to": ("new_person_id",), "t": ("time",)}


def answers_equal_v1(pred: Any, gold: Any) -> bool:
    """Frozen v1 rule: exact structured equality on gold keys."""
    if isinstance(pred, dict) and isinstance(gold, dict):
        return all(answers_equal_v1(pred.get(k), gold[k]) for k in gold)
    if isinstance(pred, (list, tuple)) and isinstance(gold, (list, tuple)):
        return len(pred) == len(gold) and all(answers_equal_v1(a, b) for a, b in zip(pred, gold))
    return pred == gold


def score_v2(pred: Any, gold: dict) -> bool:
    """Frozen transition scorer v2: v1 after renaming three approved aliases and
    digit-string<->int coercion of ``t``; conflicting alias/canonical values reject."""
    if not isinstance(pred, dict):
        return answers_equal_v1(pred, gold)
    out = dict(pred)
    for canon, aliases in _V2_ALIASES.items():
        hits = [a for a in aliases if a in out]
        if not hits:
            continue
        vals = ([out[canon]] if canon in out else []) + [out[a] for a in hits]
        if any(v != vals[0] and _norm_time(v) != _norm_time(vals[0]) for v in vals[1:]):
            return False
        for a in hits:
            del out[a]
        out[canon] = vals[0]
    if "t" in out:
        out["t"] = _norm_time(out["t"])
    g = dict(gold)
    if "t" in g:
        g["t"] = _norm_time(g["t"])
    return answers_equal_v1(out, g)


def gold_roles(slot: str, gold: dict) -> dict[str, Any]:
    r = {k: v for k, v in gold.items() if k != "t"}
    r["time"] = gold["t"]
    return r


def score_semantic(slot: str, raw: str, gold: dict) -> dict[str, bool]:
    """Schema-agnostic gold-referenced scores for one response.

    question_aligned: the single stated answer gives every field the question
        asks for (time; plus from/to for "when and how") with the gold value,
        and contradicts no other gold field. Document version labels are not
        checked here because the question text itself asserts them.
    tuple_content: every gold tuple field is recoverable from the response
        with the gold value, regardless of key names or nesting.
    """
    parsed = parse_response(raw)
    if not parsed["parse_ok"] or parsed["abstain"]:
        return {"question_aligned": False, "tuple_content": False}
    claims = extract_claims(slot, parsed["answer"])
    if len(claims) != 1:
        return {"question_aligned": False, "tuple_content": False}
    claim, roles = claims[0], gold_roles(slot, gold)
    qa = claim_matches_roles(slot, claim, roles, ignore=("from_version", "to_version"))
    tc = all(claim.get(r) == {v} for r, v in roles.items())
    return {"question_aligned": qa, "tuple_content": tc}


def scoring_answer(raw: str) -> Any:
    """Answer object as seen by the exact-match scorers (wrapper removed, bare JSON accepted)."""
    p = parse_response(raw)
    return p["answer"] if p["parse_ok"] else None


def scorable_transition(pred: Any) -> Any:
    """Rule used by the frozen factorized analysis before scorer v2: a payload
    with a dict under ``event`` (prev/event/next shape) is scored on that sub-object."""
    if isinstance(pred, dict) and isinstance(pred.get("event"), dict):
        return pred["event"]
    return pred
