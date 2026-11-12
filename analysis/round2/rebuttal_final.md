# ICLR 2027 Rebuttal — WorldConsistMem (Submission 49130)

**Authors' Response to Reviewers Rkeo, vfz3, and EdSa**

We thank all reviewers for detailed and constructive feedback. This response presents new quantitative evidence from a completed Round 2 human evaluation and a rigorous independent reanalysis. We organized the analysis to separate three distinct outcome types: (A) output-contract compliance, (B) semantic answer correctness, and (C) temporal world-state consistency. All results are reproducible from `scripts/rigorous_reanalysis.py` and the frozen outputs in `analysis/round2/private/`.

---

## Round 2 Human Evaluation

We conducted a second round of human evaluation on 50 responses (20 questions × up to 3 responses each, via private arm mapping). Two independent reviewers applied a revised rubric with explicit guidance on multi-candidate questions.

**Inter-rater reliability:**
- Agreement: 44/50 (88.0%), Wilson CI [76.2%, 94.4%]
- Cohen's κ = 0.758 (bootstrap CI: [0.517, 0.957], n=10,000 resamples, cluster by case)
- McNemar p = 0.219 (no systematic directional bias between reviewers)

The 25 jointly-ambiguous responses arise entirely on multi-candidate questions (CEO succession, ownership transfer), where the evidence pack contains multiple valid historical events and the gold standard uses the latest event without stating this convention. We now disclose this convention explicitly (see below).

The 6 discordant items do not affect any mechanical evaluation result; a third-annotator adjudication will be completed before camera-ready.

---

## Response to Reviewer vfz3

> *"The improvements may reflect schema compliance rather than genuine semantic world-state tracking."*

**Confirmed and quantified.** We identify three distinct components of the observed arm differences.

### Component 1: Output-contract compliance on uniquely specified questions (n=74)

74 of 150 questions have exactly one valid candidate event. Under exact-match scoring:

| Arm | Exact (unique, n=74) | Semantic (unique, n=74) | Δ(exact − semantic) |
|-----|--------------------:|-----------------------:|-------------------:|
| F0 | 10/74 (13.5%) | 74/74 (100%) | −86.5 pp |
| F1 | 74/74 (100%) | 74/74 (100%) | 0 |
| F2 | 12/74 (16.2%) | 74/74 (100%) | −83.8 pp |
| F3 | 74/74 (100%) | 74/74 (100%) | 0 |

**The F3−F0 gap of +64 items on unique questions vanishes entirely under semantic scoring (Δ = 0, p = 1.00).** All four arms correctly retrieve the answer content; only F1 and F3 wrap it in the required JSON schema.

### Component 2: Temporal representation on multi-candidate questions (n=42)

For 42 questions with multiple valid historical events, the arms diverge:

| Arm | Stale-state errors | Selects latest | Exact-match |
|-----|------------------:|---------------:|------------:|
| F0 | 23/42 (54.8%) | 19/42 (45.2%) | 3/42 (7.1%) |
| F1 | 17/42 (40.5%) | 16/42 (38.1%) | 16/42 (38.1%) |
| F2 | 2/42 (4.8%) | 38/42 (90.5%) | 27/42 (64.3%) |
| F3 | 7/42 (16.7%) | 35/42 (83.3%) | 35/42 (83.3%) |

A stale-state error is selecting an earlier historical event rather than the current state. F2 and F3 include explicit temporal context in the prompt; both dramatically reduce stale-state errors relative to F0/F1.

### Component 3: Unanswerable document questions (n=34)

34 of 150 questions ask about a document revision (v1→v2) but the evidence packs contain only later revisions without version identifiers. These items cannot be answered as stated. The semantic scorer gives F2 spurious credit on 20/34 of these items (scorer artifact on the prev/event/next format). After removing them (B1-nodoc, n=116):

| Arm | F0 | F1 | F2 | F3 |
|-----|----|----|----|-----|
| Semantic B1-nodoc | 87/116 (75.0%) | 90/116 (77.6%) | 112/116 (96.6%) | 109/116 (94.0%) |

F2 vs F3 (B1-nodoc): n01=6, n10=3, McNemar p=0.508. **No significant difference.**

---

## Response to Reviewer EdSa

> *"Semantic grading is needed."*

Done. Under B1 semantic scoring (format-agnostic), exact-match differences on unique questions collapse to zero. The B1-nodoc comparison shows F2 and F3 are statistically indistinguishable (p=0.508). Full results in `analysis/round2/case_level_error_analysis.csv` and `temporal_state_analysis.csv`.

> *"The 'latest event' convention should be disclosed and justified."*

Agreed. We add explicit disclosure:

> *"For multi-candidate questions, the gold answer uses the most recent event at world simulation end-time. This convention is not stated in the question text. Sensitivity analyses under the 'any documented event' convention are in Appendix X."*

Under the "any documented event" convention, all responses matching any historically documented event are correct. This convention is less informative for world-state consistency evaluation, but we report it for completeness.

> *"Cross-model replication would strengthen the results."*

Acknowledged and listed as future work. The paper's primary claim (H1: BCR diverges from per-query accuracy) is demonstrated on the full benchmark across four systems and is robust to this limitation.

---

## Response to Reviewer Rkeo

> *"Potential leakage."*

Forensic audit PASS on all 26 checks. Key checks: (1) no prompt text contains gold answers; (2) frozen output timestamps predate Round 1 annotation start; (3) private arm mapping was kept separate. Full results in `forensic/FORENSIC_AUDIT.md`.

> *"Analyst degrees of freedom."*

Pre-registration hash on file. All four arms reported together in all 17 sensitivity scenarios. We explicitly disclose results that run counter to the original paper framing (F2 spurious doc credits, F2 ≥ F3 on temporal event selection). The main qualitative conclusions hold across all scenarios.

> *"F1 and F2 appear post-hoc."*

F0–F3 are a 2×2 ablation designed before data collection. The design is in the pre-registration.

---

## Summary of key new findings

| Finding | Evidence | Status |
|---------|----------|--------|
| F3 exact-match advantage on unique questions is 100% format compliance | Semantic gap = 0 on unique questions | **New (confirmed)** |
| Temporal representation reduces stale-state errors | F0: 23/42, F1: 17/42 → F2: 2/42, F3: 7/42 | **New (confirmed)** |
| F2 and F3 statistically indistinguishable on semantic accuracy | B1-nodoc: 112 vs 109, p=0.508 | **New (confirmed)** |
| F2 spurious doc credits are scorer artifacts | 20/34 doc items scored spuriously for F2 | **New (disclosed)** |
| Latest-event convention is implicit | Disclosed; sensitivity analysis provided | **New (disclosed)** |
| 34 doc items unanswerable as stated | All 34 are S2 insufficient evidence | **New (disclosed)** |
| Round 2 κ = 0.758 | 44/50 agreement, CI [0.517, 0.957] | **Completed** |
| Leakage audit PASS (26/26) | Forensic archive | **Completed** |

---

## Revised framing

Based on the evidence, we propose revising the paper's framing:

**Primary contribution (unchanged):** The BCR metric exposes consistency failures that per-query accuracy misses. All evaluated systems achieve BCR=0 at non-trivial accuracy. This is demonstrated on 102 worlds, 1088 bundles, 7140 queries.

**H4 secondary contribution (revised):** The H4 LLM reader study demonstrates that (a) exact-match benchmarks conflate output-format compliance with semantic accuracy — a methodological finding relevant beyond this benchmark — and (b) temporal context in prompts reduces stale-state errors, with both F2 and F3 achieving 83–90% latest-event selection vs. 38–45% for F0/F1. The claim that F3 achieves higher semantic accuracy than other arms is not supported; we remove this claim from the paper.

**Limitation added:** The H4 study is limited to a single LLM, 18 worlds, and 150 questions. The temporal representation finding is a consistent signal but not statistically strong at this scale. Cross-model and cross-benchmark replication is needed.
