"""B0 gold-replay oracle and observation-memory baselines B1–B5."""

from __future__ import annotations

import hashlib
import math
import random
import re
from collections import Counter, defaultdict
from typing import Any, Optional

from ..generate import GeneratedWorld
from ..models import EventType, Observation, Query
from .interface import ABSTAIN_TOKEN, AnswerResult, BaselineAdapter
from .reader import StructuredReader, filter_observations


# ---------------------------------------------------------------------------
# B0 — Oracle
# ---------------------------------------------------------------------------


class GoldReplayOracle(BaselineAdapter):
    """Answer from structured gold world history (not query.gold_answer)."""

    baseline_id = "B0_oracle"

    def __init__(self, worlds: dict[str, GeneratedWorld], run_id: str = "oracle"):
        self.worlds = worlds
        self.run_id = run_id
        self._world: Optional[GeneratedWorld] = None
        self._obs: list[Observation] = []

    def reset(self) -> None:
        self._world = None
        self._obs = []

    def bind_world(self, world_id: str) -> None:
        self._world = self.worlds[world_id]

    def ingest(self, observation: Observation) -> None:
        self._obs.append(observation)
        # Infer world from observation id prefix
        wid = observation.observation_id.rsplit(":obs:", 1)[0]
        if wid.endswith(":obs:distractor".split(":obs:")[0]):
            pass
        # observation_id like w0042_000:obs:1
        parts = observation.observation_id.split(":obs:")
        if parts:
            self._world = self.worlds.get(parts[0], self._world)

    def memory_size(self) -> int:
        return 1  # logical gold store

    def answer(self, query: Query, as_of_t: Optional[int] = None) -> AnswerResult:
        # Prefer world bound via query bundle world — set externally
        w = self._world
        if w is None:
            # try parse from query id
            wid = query.query_id.split(":b:")[0]
            w = self.worlds.get(wid)
        if w is None:
            return AnswerResult(ABSTAIN_TOKEN, status="error", detail="no_world")
        # Use gold answer derived path: recompute from world state like query generator
        # Safe: uses gold *world*, never reads query.gold_answer field.
        from ..queries import generate_bundles

        # Direct slot-based gold reconstruction
        ans, prov = _oracle_answer(w, query)
        if ans is _MISSING:
            return AnswerResult(ABSTAIN_TOKEN, status="abstain", detail="oracle_unsupported")
        return AnswerResult(
            answer=ans,
            provenance=prov,
            retrieved_observation_ids=[],
            status="ok",
            detail="gold_world",
        )


_MISSING = object()


def _oracle_answer(w: GeneratedWorld, query: Query) -> tuple[Any, Optional[str]]:
    """Mirror gold derivation from world states (no query.gold_answer read)."""
    slot = query.metadata.get("slot")
    s = query.structured
    t = query.target_time
    m = w.meta

    if slot == "ceo_current":
        r = w.final.role_holder(s["org_id"], s["role"])
        return (r.person_id, r.provenance_id) if r else (_MISSING, None)
    if slot == "ceo_historical":
        r = w.states[t].role_holder(s["org_id"], s["role"])
        return (r.person_id, r.provenance_id) if r else (_MISSING, None)
    if slot == "ceo_transition":
        replace_t = m["ceo_replace_t"]
        hist = w.states[replace_t - 1].role_holder(s["org_id"], s["role"])
        now = w.states[replace_t].role_holder(s["org_id"], s["role"])
        ev = next(e for e in w.events if e.t == replace_t)
        return {
            "from": hist.person_id,
            "to": now.person_id,
            "t": replace_t,
            "role": "CEO",
            "org_id": s["org_id"],
        }, ev.provenance_id
    if slot == "ceo_employer":
        r = w.final.role_holder(s["org_id"], "CEO")
        return w.final.employer_of(r.person_id), r.provenance_id
    if slot == "ceo_provenance":
        r = w.final.role_holder(s["org_id"], s["role"])
        return r.provenance_id, r.provenance_id
    if slot == "ceo_order":
        return True, None
    if slot == "ceo_contradiction":
        return False, None
    if slot == "ceo_counterfactual":
        return True, None

    if slot == "owner_current":
        ev = next(e for e in w.events if e.t == m["ownership_transfer_t"])
        return w.final.owner_of(s["project_id"]), ev.provenance_id
    if slot == "owner_historical":
        return w.states[t].owner_of(s["project_id"]), f"{w.world_id}:prov:init_own"
    if slot == "owner_transition":
        tt = m["ownership_transfer_t"]
        ev = next(e for e in w.events if e.t == tt)
        return {
            "from": w.states[tt - 1].owner_of(s["project_id"]),
            "to": w.states[tt].owner_of(s["project_id"]),
            "t": tt,
            "project_id": s["project_id"],
        }, ev.provenance_id
    if slot == "owner_mgr_align":
        proj = s["project_id"]
        owner = w.final.owner_of(proj)
        mgr = w.final.projects[proj].manager_id
        return (w.final.employer_of(mgr) == owner), None
    if slot == "owner_provenance":
        ev = next(e for e in w.events if e.t == m["ownership_transfer_t"])
        return ev.provenance_id, ev.provenance_id
    if slot == "conflict_no_silent_resolution":
        return False, None

    if slot == "doc_version":
        d = w.final.canonical_doc(s["base_doc_id"])
        return d.version, d.provenance_id
    if slot == "doc_hist_version":
        d = w.states[t].canonical_doc(s["base_doc_id"])
        return d.version, d.provenance_id
    if slot == "doc_transition":
        rt = m["doc_revision_t"]
        ev = next(e for e in w.events if e.t == rt)
        hist = w.states[rt - 1].canonical_doc(s["base_doc_id"])
        cur = w.states[rt].canonical_doc(s["base_doc_id"])
        return {
            "from_version": hist.version,
            "to_version": cur.version,
            "t": rt,
            "base_doc_id": s["base_doc_id"],
        }, ev.provenance_id
    if slot == "doc_approve_project":
        d = w.final.canonical_doc(s["base_doc_id"])
        return {"approver": d.approved_by, "project_id": d.project_id}, None
    if slot == "doc_provenance":
        d = w.final.canonical_doc(s["base_doc_id"])
        return d.provenance_id, d.provenance_id
    if slot == "doc_order":
        return True, None

    if slot == "emp_current":
        return w.final.employer_of(s["person_id"]) == s["org_id"], None
    if slot == "emp_historical":
        return w.states[t].employer_of(s["person_id"]) == s["org_id"], None
    if slot == "emp_transition":
        leave = next(
            e
            for e in w.events
            if e.event_type == EventType.PERSON_LEAVES_ORG
            and e.payload.get("person_id") == s["person_id"]
        )
        return {
            "person_id": s["person_id"],
            "org_id": s["org_id"],
            "t": leave.t,
            "action": "leave",
        }, leave.provenance_id
    if slot == "emp_role_compat":
        return False, None
    if slot == "emp_provenance":
        leave = next(
            e
            for e in w.events
            if e.event_type == EventType.PERSON_LEAVES_ORG
            and e.payload.get("person_id") == s.get("person_id")
        )
        return leave.provenance_id, leave.provenance_id
    if slot == "emp_contradiction":
        return False, None

    if slot == "conf_resolved":
        return True, next(e for e in w.events if e.t == m["conflict_resolve_t"]).provenance_id
    if slot == "conf_unresolved_hist":
        return True, next(e for e in w.events if e.t == m["conflict_intro_t"]).provenance_id
    if slot == "conf_value":
        return "P0", next(e for e in w.events if e.t == m["conflict_resolve_t"]).provenance_id
    if slot == "conf_transition":
        rt = m["conflict_resolve_t"]
        ev = next(e for e in w.events if e.t == rt)
        return {"conflict_id": m["conflict_id"], "t": rt, "resolved_value": "P0"}, ev.provenance_id
    if slot == "conf_subject":
        return True, None
    if slot == "conf_provenance":
        return next(e for e in w.events if e.t == m["conflict_resolve_t"]).provenance_id, None
    if slot == "conf_counterfactual":
        return True, None

    return _MISSING, None


# ---------------------------------------------------------------------------
# B1 — Flat append-only
# ---------------------------------------------------------------------------


class FlatAppendMemory(BaselineAdapter):
    baseline_id = "B1_flat_append"

    def __init__(self, run_id: str = "flat"):
        self.run_id = run_id
        self._obs: list[Observation] = []
        self.reader = StructuredReader()

    def reset(self) -> None:
        self._obs = []

    def ingest(self, observation: Observation) -> None:
        self._obs.append(observation)

    def memory_size(self) -> int:
        return len([o for o in self._obs if not o.is_distractor])

    def answer(self, query: Query, as_of_t: Optional[int] = None) -> AnswerResult:
        return self.reader.answer(query, self._obs, as_of_t=as_of_t)


# ---------------------------------------------------------------------------
# B2 — Latest-state-only
# ---------------------------------------------------------------------------


class LatestStateMemory(BaselineAdapter):
    """Keep only latest observation per coarse fact key; discard history."""

    baseline_id = "B2_latest_only"

    def __init__(self, run_id: str = "latest"):
        self.run_id = run_id
        self._latest: dict[str, Observation] = {}
        self._all_keys_order: list[str] = []
        self.reader = StructuredReader()

    def reset(self) -> None:
        self._latest = {}
        self._all_keys_order = []

    def _key(self, obs: Observation) -> str:
        s = obs.structured
        et = s.get("event_type", "")
        p = s.get("payload") or {}
        if et in ("role_assignment", "role_replacement"):
            return f"role:{p.get('org_id')}:{p.get('role', 'CEO')}"
        if et in ("person_joins_org", "person_leaves_org"):
            return f"emp:{p.get('person_id')}"
        if et == "project_ownership_transfer":
            return f"own:{p.get('project_id')}"
        if et in ("document_creation", "document_revision", "document_approval"):
            return f"doc:{p.get('base_doc_id') or p.get('doc_id')}"
        if et in ("conflict_introduction", "conflict_resolution"):
            return f"conf:{p.get('conflict_id')}"
        if et == "project_status_change":
            return f"proj:{p.get('project_id')}"
        if et in ("relationship_creation", "relationship_termination"):
            return f"rel:{p.get('rel_id') or p.get('source_id')}"
        return f"{et}:{obs.observation_id}"

    def ingest(self, observation: Observation) -> None:
        if observation.is_distractor:
            return
        k = self._key(observation)
        self._latest[k] = observation
        if k not in self._all_keys_order:
            self._all_keys_order.append(k)

    def memory_size(self) -> int:
        return len(self._latest)

    def stored_observations(self) -> list[Observation]:
        return list(self._latest.values())

    def answer(self, query: Query, as_of_t: Optional[int] = None) -> AnswerResult:
        # Only latest facts — historical depth unavailable by design
        obs = self.stored_observations()
        # For historical queries, still only have latest → expected failures
        return self.reader.answer(query, obs, as_of_t=as_of_t)


# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def lexical_score(query_text: str, doc_text: str) -> float:
    """Deterministic overlap score (Jaccard on token sets) + shared ID bonus."""
    qt = set(_tokenize(query_text))
    dt = set(_tokenize(doc_text))
    if not qt or not dt:
        return 0.0
    inter = len(qt & dt)
    union = len(qt | dt)
    return inter / union if union else 0.0


def bm25_scores(query: str, documents: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Simple BM25 without external dependencies."""
    tok_docs = [_tokenize(d) for d in documents]
    q_terms = _tokenize(query)
    N = len(tok_docs) or 1
    avgdl = sum(len(td) for td in tok_docs) / N
    df: Counter = Counter()
    for td in tok_docs:
        for t in set(td):
            df[t] += 1
    scores = []
    for td in tok_docs:
        tf = Counter(td)
        dl = len(td) or 1
        s = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            n_q = df.get(term, 0)
            idf = math.log(1 + (N - n_q + 0.5) / (n_q + 0.5))
            freq = tf[term]
            s += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores


# ---------------------------------------------------------------------------
# B3 — Recency-weighted lexical retrieval
# ---------------------------------------------------------------------------


class RecencyWeightedMemory(BaselineAdapter):
    baseline_id = "B3_recency_retrieval"

    def __init__(self, k: int = 5, recency_coef: float = 0.15, run_id: str = "recency"):
        self.k = k
        self.recency_coef = recency_coef
        self.run_id = run_id
        self._obs: list[Observation] = []
        self.reader = StructuredReader()

    def reset(self) -> None:
        self._obs = []

    def ingest(self, observation: Observation) -> None:
        self._obs.append(observation)

    def memory_size(self) -> int:
        return len([o for o in self._obs if not o.is_distractor])

    def retrieve(self, query: Query, as_of_t: Optional[int]) -> tuple[list[Observation], list[float]]:
        pool = filter_observations(self._obs, as_of_t=as_of_t)
        if not pool:
            return [], []
        tmax = max(o.t for o in pool) or 1
        qtext = query.text + " " + str(query.structured)
        scored = []
        for o in pool:
            lex = lexical_score(qtext, o.text_canonical + " " + str(o.structured))
            rec = self.recency_coef * (o.t / tmax)
            scored.append((lex + rec, o))
        # Tie-break: higher t, then observation_id
        scored.sort(key=lambda x: (-x[0], -x[1].t, x[1].observation_id))
        top = scored[: self.k]
        return [o for _, o in top], [s for s, _ in top]

    def answer(self, query: Query, as_of_t: Optional[int] = None) -> AnswerResult:
        # Temporal-order needs both events: retrieve without aggressive cutoff on text
        cutoff = as_of_t
        if query.metadata.get("slot") in ("ceo_order", "doc_order"):
            cutoff = None
            pool_cut = None
        else:
            pool_cut = cutoff
        retrieved, scores = self.retrieve(query, pool_cut)
        return self.reader.answer(
            query,
            retrieved,
            as_of_t=as_of_t,
            retrieved_ids=[o.observation_id for o in retrieved],
            retrieval_scores=scores,
        )


# ---------------------------------------------------------------------------
# B4 — BM25 over NL renderings
# ---------------------------------------------------------------------------


class BM25RetrievalMemory(BaselineAdapter):
    baseline_id = "B4_bm25"

    def __init__(self, k: int = 5, run_id: str = "bm25"):
        self.k = k
        self.run_id = run_id
        self._obs: list[Observation] = []
        self.reader = StructuredReader()

    def reset(self) -> None:
        self._obs = []

    def ingest(self, observation: Observation) -> None:
        self._obs.append(observation)

    def memory_size(self) -> int:
        return len([o for o in self._obs if not o.is_distractor])

    def retrieve(self, query: Query, as_of_t: Optional[int]) -> tuple[list[Observation], list[float]]:
        pool = filter_observations(self._obs, as_of_t=as_of_t)
        if not pool:
            return [], []
        docs = [o.text_canonical + " " + o.text_paraphrase for o in pool]
        scores = bm25_scores(query.text + " " + str(query.structured), docs)
        ranked = sorted(
            zip(scores, pool),
            key=lambda x: (-x[0], -x[1].t, x[1].observation_id),
        )
        top = ranked[: self.k]
        return [o for _, o in top], [s for s, _ in top]

    def answer(self, query: Query, as_of_t: Optional[int] = None) -> AnswerResult:
        cutoff = None if query.metadata.get("slot") in ("ceo_order", "doc_order") else as_of_t
        retrieved, scores = self.retrieve(query, cutoff)
        return self.reader.answer(
            query,
            retrieved,
            as_of_t=as_of_t,
            retrieved_ids=[o.observation_id for o in retrieved],
            retrieval_scores=scores,
        )


# ---------------------------------------------------------------------------
# B5 — Reservoir / fixed capacity
# ---------------------------------------------------------------------------


class ReservoirMemory(BaselineAdapter):
    baseline_id = "B5_reservoir"

    def __init__(self, capacity: int = 8, seed: int = 0, run_id: Optional[str] = None):
        self.capacity = capacity
        self.seed = seed
        self.run_id = run_id or f"reservoir_c{capacity}_s{seed}"
        self.baseline_id = f"B5_reservoir_c{capacity}"
        self._rng = random.Random(seed)
        self._obs: list[Observation] = []
        self._seen = 0
        self.reader = StructuredReader()

    def reset(self) -> None:
        self._rng = random.Random(self.seed)
        self._obs = []
        self._seen = 0

    def ingest(self, observation: Observation) -> None:
        if observation.is_distractor:
            return
        self._seen += 1
        if len(self._obs) < self.capacity:
            self._obs.append(observation)
            return
        # Algorithm R
        j = self._rng.randint(1, self._seen)
        if j <= self.capacity:
            self._obs[j - 1] = observation

    def memory_size(self) -> int:
        return len(self._obs)

    def answer(self, query: Query, as_of_t: Optional[int] = None) -> AnswerResult:
        return self.reader.answer(query, self._obs, as_of_t=as_of_t)


def make_baselines(
    worlds: dict[str, GeneratedWorld],
    k: int = 5,
    reservoir_capacities: tuple[int, ...] = (8, 16),
    reservoir_seeds: tuple[int, ...] = (0, 1, 2),
) -> list[BaselineAdapter]:
    bases: list[BaselineAdapter] = [
        GoldReplayOracle(worlds, run_id="oracle"),
        FlatAppendMemory(run_id="flat"),
        LatestStateMemory(run_id="latest"),
        RecencyWeightedMemory(k=k, recency_coef=0.15, run_id=f"recency_k{k}"),
        BM25RetrievalMemory(k=k, run_id=f"bm25_k{k}"),
    ]
    for cap in reservoir_capacities:
        for seed in reservoir_seeds:
            bases.append(ReservoirMemory(capacity=cap, seed=seed))
    return bases
