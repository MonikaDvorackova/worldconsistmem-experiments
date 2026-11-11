# WorldConsistMem — Round 2 independent adjudication protocol

Version: 1.0 (2026-11-11). Scope: 50 responses with discordant Round 1 labels, spanning 20 cases. **This is a prospective protocol, not an instruction to modify Round 1 labels.**

## Blinding and independence

Each reviewer receives the same **blind packet**, without Round 1 labels, the other reviewer's judgments, arm names (F0–F3), automatic scores, or expected result. Review independently and do not discuss examples until both packets are locked. Reviewer IDs remain distinct. Store outputs separately as Round 2; preserve both Round 1 source files unchanged. An independent third adjudicator should resolve remaining disagreement and explicitly record the rationale.

## Required fields

- `semantic_correct`: exactly `correct`, `incorrect`, or `ambiguous`.
- `evidence_sufficient`: exactly `yes`, `no`, or `unclear`.
- `notes`: a short case-specific explanation citing evidence IDs/timestamps where possible.
- `rubric_reason`: one of `factually_supported`, `factually_contradicted`, `multiple_plausible_answers`, `insufficient_evidence`, `unparseable_or_uninterpretable`, `other`.

## Decision rules

1. Judge **the answer to the user-facing question**, not compliance with a hidden JSON schema. A bare correct timestamp for “When?” is `correct` even if the answer lacks provenance, source/target IDs, or an `answer` wrapper. Record missing fields in notes only; do not turn them into semantic errors.
2. Read `raw_model_response` as the response actually given. If it is JSON, extract the answer-bearing content without penalizing key names, nesting, whitespace, or unrelated metadata. Do not hallucinate missing facts or repair contradictory values.
3. `correct`: the answer unambiguously answers the asked question and is supported by the supplied evidence, including relevant temporal scope. If the question asks for a timestamp, a correct scalar timestamp suffices. A correct time with contradictory additional answer-bearing content requires careful review; explain in notes.
4. `incorrect`: the response supplies a demonstrably wrong answer, identifies the wrong event/entity/version, or contradicts sufficiently informative evidence. An unsupported guess is not automatically demonstrably false: distinguish from insufficient evidence.
5. `ambiguous`: use when the question admits multiple defensible readings, evidence cannot distinguish candidate answers, or the response cannot be evaluated decisively against the evidence. **Do not use merely because the JSON shape is unusual.** Explain precisely why ambiguity remains.
6. `evidence_sufficient=yes` only when the supplied evidence alone supports a unique answer to the question; `no` when a required observation, version mapping, event, or identity is missing; `unclear` when sufficiency cannot be determined from the packet. Semantic label and sufficiency label are separate axes. If evidence is insufficient, normally use `ambiguous` unless the answer is independently contradicted by available evidence.
7. Document revision: do not infer v1→v2 mappings solely from doc IDs or timestamps if no version mapping is provided. Multiple revision events do not identify the asked version transition without a supported mapping.
8. Ownership transfers: distinguish first/last/specific transfer. If a project transfers repeatedly and the question simply asks “When did ownership transfer?”, mark `ambiguous` unless context establishes one intended event. Do not assume latest or earliest without justification.
9. Abstentions and null answers: `incorrect` when the question has a uniquely supported answer; `ambiguous` if the evidence does not establish that a unique answer exists. Explain.
10. If you cannot determine a label, use `ambiguous` and document the missing disambiguating fact. Never force a binary label for convenience.

## Procedure

1. Review all 50 rows in randomized or ID order independently; do not view Round 1 labels.
2. Fill every required field; retain the provided evidence and response unmodified.
3. Save completed JSON under `human_evaluation/round_2/reviewer_1/` or `reviewer_2/` with the original response IDs.
4. Compute exact agreement, unweighted three-class Cohen's κ, and a confusion matrix; also report category prevalence, not just κ.
5. Adjudicate any remaining discordant labels with a third evaluator and a documented decision; retain all raw judgments and the final consensus separately.
6. Report sensitivity analysis: treat unresolved `ambiguous` as excluded, as incorrect, and as a separate class; never choose one treatment after seeing which favors F3.

## Limitations

The blind packet intentionally includes only the supplied evidence, question, and raw model response. It does **not** provide independently verified gold targets. Thus annotators can judge support by supplied evidence but cannot certify dataset-level gold correctness. This round covers only the 50 initially disputed responses, so agreement after re-review must not be represented as agreement on a new random sample or as full 150-item semantic accuracy.
