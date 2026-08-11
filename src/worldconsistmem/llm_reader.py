"""Local MLX LLM reader over retrieved evidence only (no gold leakage).

Frozen decoding: temperature=0, stream_generate JSON early-stop, shared prompt.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .baselines.interface import ABSTAIN_TOKEN, AnswerResult
from .models import Observation, Query

H4_MODELS = (
    "mlx-community/Qwen2.5-3B-Instruct-4bit",
    "mlx-community/Phi-3.5-mini-instruct-4bit",
)

# Keep alias for older imports; H4 uses exactly H4_MODELS (two families).
RECOMMENDED_MODELS = H4_MODELS

MAX_TOKENS = 48
TEMPERATURE = 0.0
EVIDENCE_JSON_CAP = 1200  # chars; local Metal throughput requires short prompts
MAX_EVIDENCE_ITEMS = 3  # matched reader consultation budget across all systems

_PROMPT = """Answer using ONLY the evidence. Return ONE compact JSON object and nothing else:
{{"answer": <value or null>, "abstain": <true|false>, "provenance": <short id or null>}}
If evidence is insufficient, answer=null and abstain=true. No explanations.

schema={schema}
query={query_text}
structured={structured}
evidence={evidence}
"""


def _slim_structured(s: dict) -> dict:
    """Keep only high-signal fields for the LLM evidence pack."""
    payload = s.get("payload") or {}
    # Drop bulky/irrelevant keys to keep prompts short on local Metal.
    keep_keys = (
        "person_id",
        "org_id",
        "role",
        "project_id",
        "new_org_id",
        "old_org_id",
        "new_person_id",
        "old_person_id",
        "doc_id",
        "base_doc_id",
        "conflict_id",
        "resolved_value",
        "value_a",
        "value_b",
        "status",
        "rel_id",
        "rel_type",
        "source_id",
        "target_id",
        "approver_id",
        "author_id",
        "location_id",
        "manager_id",
        "exclusive",
    )
    slim_p = {k: payload[k] for k in keep_keys if k in payload}
    return {
        "et": s.get("event_type"),
        "t": s.get("t"),
        "p": slim_p,
        "prov": s.get("provenance_id"),
    }


@dataclass
class EvidencePack:
    """Serializable evidence passed to the LLM — no gold fields."""

    query_id: str
    query_text: str
    structured: dict[str, Any]
    answer_schema: str
    evidence: list[dict[str, Any]]

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "structured": self.structured,
            "answer_schema": self.answer_schema,
            "evidence": self.evidence,
        }


def assert_no_gold_leakage(obj: Any) -> None:
    blob = json.dumps(obj, sort_keys=True, default=str).lower()
    for banned in ("gold_answer", "gold_world", "supporting_event_ids", "applicable_constraints"):
        if banned in blob:
            raise AssertionError(f"gold/constraint leakage: {banned}")


def build_evidence_from_observations(query: Query, obs: list[Observation]) -> EvidencePack:
    evidence = []
    for o in obs:
        if o.is_distractor:
            continue
        evidence.append(
            {
                "id": o.observation_id,
                "t": o.t,
                "s": _slim_structured(o.structured),
            }
        )
        if len(evidence) >= MAX_EVIDENCE_ITEMS:
            break
    pack = EvidencePack(
        query_id=query.query_id,
        query_text=query.text,
        structured=dict(query.structured),
        answer_schema=query.answer_schema.value,
        evidence=evidence,
    )
    assert_no_gold_leakage(pack.to_prompt_dict())
    return pack


def build_evidence_from_ltkm_pack(
    query: Query, pack_payload: dict[str, Any], record_ids: list[str]
) -> EvidencePack:
    """Flatten LTKM retrieval payloads without gold."""
    evidence = []
    for rid in record_ids[:MAX_EVIDENCE_ITEMS]:
        evidence.append({"record_id": rid})
    # include a compact payload summary (bounded)
    for k, v in pack_payload.items():
        if v is None:
            continue
        if len(evidence) >= MAX_EVIDENCE_ITEMS + 2:
            break
        if hasattr(v, "to_dict"):
            d = v.to_dict()
            # keep small
            evidence.append({"key": k, "value": {kk: d[kk] for kk in list(d)[:6]}})
        elif isinstance(v, list):
            evidence.append({"key": k, "n": len(v), "tail": [str(x)[:80] for x in v[-2:]]})
        elif isinstance(v, dict):
            evidence.append({"key": k, "value": {kk: v[kk] for kk in list(v)[:6]}})
        else:
            evidence.append({"key": k, "value": str(v)[:120]})
    pack = EvidencePack(
        query_id=query.query_id,
        query_text=query.text,
        structured=dict(query.structured),
        answer_schema=query.answer_schema.value,
        evidence=evidence[: MAX_EVIDENCE_ITEMS + 2],
    )
    assert_no_gold_leakage(pack.to_prompt_dict())
    return pack


def format_prompt(pack: EvidencePack) -> str:
    return _PROMPT.format(
        schema=pack.answer_schema,
        query_text=pack.query_text,
        structured=json.dumps(pack.structured, sort_keys=True),
        evidence=json.dumps(pack.evidence, sort_keys=True)[:EVIDENCE_JSON_CAP],
    )


def _parse_json_answer(text: str) -> tuple[Any, bool, Optional[str], bool, Optional[dict]]:
    """Returns answer, abstain, provenance, malformed, parsed_obj."""
    text = text.strip()
    for mark in ("<|end|>", "<|endoftext|>", "<|assistant|>", "<|im_end|>"):
        text = text.replace(mark, " ")
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return ABSTAIN_TOKEN, True, None, True, None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return ABSTAIN_TOKEN, True, None, True, None
    if not isinstance(obj, dict) or "answer" not in obj:
        return ABSTAIN_TOKEN, True, None, True, None
    abstain = bool(obj.get("abstain")) or obj.get("answer") is None
    ans = obj.get("answer")
    if abstain:
        return ABSTAIN_TOKEN, True, obj.get("provenance"), False, obj
    return ans, False, obj.get("provenance"), False, obj


def _json_complete(text: str) -> bool:
    if "{" not in text:
        return False
    start = text.find("{")
    depth = 0
    in_str = False
    esc = False
    for ch in text[start:]:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return True
    return False


@dataclass
class LLMGenResult:
    raw_output: str
    answer: Any
    abstain: bool
    provenance: Optional[str]
    malformed: bool
    parsed: Optional[dict]
    latency_ms: float
    peak_memory_gb: Optional[float]
    prompt_tokens: int
    evidence_tokens: int
    status: str
    detail: str


@dataclass
class MLXLLMReader:
    """Lazy-loaded mlx_lm instruct model with frozen decoding."""

    model_id: str
    max_tokens: int = MAX_TOKENS
    _model: Any = field(default=None, repr=False)
    _tokenizer: Any = field(default=None, repr=False)
    available: bool = False
    load_error: Optional[str] = None
    mlx_lm_version: Optional[str] = None
    mlx_version: Optional[str] = None
    peak_memory_gb: Optional[float] = None

    def __post_init__(self) -> None:
        self._try_load()

    def _try_load(self) -> None:
        try:
            import importlib.metadata as md
            from mlx_lm import load  # type: ignore

            self.mlx_lm_version = md.version("mlx-lm")
            try:
                self.mlx_version = md.version("mlx")
            except Exception:  # noqa: BLE001
                self.mlx_version = None
        except Exception as e:  # noqa: BLE001
            self.load_error = f"mlx_lm_import:{e}"
            return
        try:
            self._model, self._tokenizer = load(self.model_id)
            self.available = True
        except Exception as e:  # noqa: BLE001
            self.load_error = f"model_load:{e}"

    def smoke_generate(self) -> str:
        """Minimal deterministic smoke prompt."""
        pack = EvidencePack(
            query_id="smoke",
            query_text="What is 1+1?",
            structured={"op": "add"},
            answer_schema="scalar",
            evidence=[{"fact": "1+1=2"}],
        )
        return self.generate_raw(format_prompt(pack))

    def generate_raw(self, user_prompt: str) -> str:
        from mlx_lm import stream_generate  # type: ignore
        from mlx_lm.sample_utils import make_sampler  # type: ignore

        assert self._model is not None and self._tokenizer is not None
        if hasattr(self._tokenizer, "apply_chat_template"):
            messages = [{"role": "user", "content": user_prompt}]
            prompt = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            prompt = user_prompt
        sampler = make_sampler(temp=TEMPERATURE)
        text = ""
        for resp in stream_generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self.max_tokens,
            sampler=sampler,
        ):
            text += resp.text
            if getattr(resp, "peak_memory", None) is not None:
                self.peak_memory_gb = float(resp.peak_memory)
            if _json_complete(text):
                break
            if "<|end|>" in text or "<|endoftext|>" in text or "<|im_end|>" in text:
                break
        for mark in ("<|end|>", "<|endoftext|>", "<|assistant|>", "<|im_end|>"):
            text = text.replace(mark, " ")
        return text.strip()

    def answer_evidence(self, pack: EvidencePack) -> AnswerResult:
        result = self.answer_evidence_detailed(pack)
        return AnswerResult(
            answer=result.answer if not result.abstain else ABSTAIN_TOKEN,
            provenance=result.provenance,
            retrieved_observation_ids=[
                e.get("observation_id") or e.get("record_id", "")
                for e in pack.evidence
                if isinstance(e, dict)
            ],
            status=result.status,
            detail=result.detail,
        )

    def answer_evidence_detailed(self, pack: EvidencePack) -> LLMGenResult:
        if not self.available:
            return LLMGenResult(
                raw_output="",
                answer=ABSTAIN_TOKEN,
                abstain=True,
                provenance=None,
                malformed=False,
                parsed=None,
                latency_ms=0.0,
                peak_memory_gb=None,
                prompt_tokens=0,
                evidence_tokens=0,
                status="error",
                detail=f"llm_unavailable:{self.load_error}",
            )
        assert_no_gold_leakage(pack.to_prompt_dict())
        user_prompt = format_prompt(pack)
        assert "gold_answer" not in user_prompt
        assert "supporting_event" not in user_prompt.lower() or "supporting_event" not in json.dumps(
            pack.structured
        )
        # token estimates
        evid_text = json.dumps(pack.evidence, sort_keys=True)[:EVIDENCE_JSON_CAP]
        try:
            prompt_tokens = len(self._tokenizer.encode(user_prompt))
            evidence_tokens = len(self._tokenizer.encode(evid_text))
        except Exception:  # noqa: BLE001
            prompt_tokens = max(1, len(user_prompt) // 4)
            evidence_tokens = max(1, len(evid_text) // 4)
        t0 = time.perf_counter()
        try:
            raw = self.generate_raw(user_prompt)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            ans, abstain, prov, malformed, parsed = _parse_json_answer(raw)
            if malformed:
                return LLMGenResult(
                    raw_output=raw,
                    answer=ABSTAIN_TOKEN,
                    abstain=True,
                    provenance=None,
                    malformed=True,
                    parsed=None,
                    latency_ms=latency_ms,
                    peak_memory_gb=self.peak_memory_gb,
                    prompt_tokens=prompt_tokens,
                    evidence_tokens=evidence_tokens,
                    status="malformed",
                    detail="json_parse_fail",
                )
            return LLMGenResult(
                raw_output=raw,
                answer=ans if not abstain else ABSTAIN_TOKEN,
                abstain=abstain,
                provenance=prov,
                malformed=False,
                parsed=parsed,
                latency_ms=latency_ms,
                peak_memory_gb=self.peak_memory_gb,
                prompt_tokens=prompt_tokens,
                evidence_tokens=evidence_tokens,
                status="abstain" if abstain else "ok",
                detail=f"llm:{self.model_id}",
            )
        except Exception as e:  # noqa: BLE001
            return LLMGenResult(
                raw_output="",
                answer=ABSTAIN_TOKEN,
                abstain=True,
                provenance=None,
                malformed=False,
                parsed=None,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                peak_memory_gb=self.peak_memory_gb,
                prompt_tokens=prompt_tokens,
                evidence_tokens=evidence_tokens,
                status="error",
                detail=f"gen_fail:{e}",
            )


def try_load_any(model_ids: tuple[str, ...] = H4_MODELS) -> list[MLXLLMReader]:
    loaded = []
    for mid in model_ids:
        r = MLXLLMReader(mid)
        if r.available:
            loaded.append(r)
    return loaded
