# ICLR 2027 Rebuttal — WorldConsistMem (Submission 49130)

**Authors' Response to Reviewers Rkeo, vfz3, and EdSa**

We thank all reviewers for detailed and constructive feedback. We respond below with
new quantitative evidence from a completed Round 2 human evaluation and sensitivity
analysis. All new results are fully reproducible from the accompanying analysis scripts
and frozen outputs in `analysis/round2/`; raw data, scoring code, and test suite are
provided in the supplementary materials.

---

## Round 2 Human Evaluation: Summary

We conducted a second round of human evaluation on a 50-response subset (20 unique
questions × up to 3 responses each, drawn from 25 cases via private arm mapping).
Two independent reviewers annotated each response as `correct`, `ambiguous`, or
`incorrect` using a revised rubric that separates output-contract compliance from
semantic content.

**Inter-rater reliability:**
- Agreement: 44/50 (88.0%)
- Cohen's κ = 0.758 (95% bootstrap CI: [0.517, 0.957], n=10 000 resamples, cluster
  by case)
- 25 jointly-ambiguous, 19 jointly-correct, 0 jointly-incorrect, 6 discordant

The 25 jointly-ambiguous responses are structurally verified: all 25 arise on
multi-candidate questions (10 CEO-change and 15 ownership questions per question
type), where the evidence pack contains more than one valid event of the requested
type and the gold standard uses the latest event without stating this convention.

The 6 discordant items break down as: 5 on multi-candidate questions (reviewer A
scored `ambiguous`, reviewer B scored `correct`) and 1 on a unique question (reviewer A
`correct`, reviewer B `ambiguous`). Rule-based adjudication proposals are provided in
`analysis/round2/adjudication_proposals.csv`; independent human confirmation is
pending per the pre-registered protocol.

---

## Response to Reviewer vfz3

> *"The improvements may reflect schema compliance rather than genuine semantic
> improvements in world-state tracking."*

**This concern is confirmed and quantified.** We identify two distinct components of
the F3 advantage:

### Component 1: Output-contract compliance on uniquely specified questions

Structural analysis (see `analysis/round2/ambiguous_case_audit.csv`) identifies 74
out of 150 items as *uniquely specified*: the evidence pack contains exactly one
candidate event of the requested type for the requested entity, so the question has
an unambiguous answer regardless of the "latest event" convention.

Under exact-match scoring (Scenario A), F1 and F3 both score 74/74 on these items;
F0 scores 10/74 and F2 scores 12/74:

| Arm | Exact-match (A) | Semantic question-aligned (C2-B1) |
|-----|-----------------|-----------------------------------|
| F0  | 10/74 (13.5%)   | 74/74 (100%)                      |
| F1  | 74/74 (100%)    | 74/74 (100%)                      |
| F2  | 12/74 (16.2%)   | 74/74 (100%)                      |
| F3  | 74/74 (100%)    | 74/74 (100%)                      |

Under schema-agnostic semantic scoring (Scenario C2-B1, asked fields only,
unrequested fields ignored), all four arms score 74/74. The F3−F0 gap of +86.5 pp
on unique questions vanishes entirely (Δ = 0.000, p = 1.00). **On questions with
unambiguous answers, all four arms retrieve the correct content; the exact-match
gap is entirely output-contract compliance.**

The M5 format audit in the paper tested whether format-only transformations
(wrapping) accounted for gains. It did not test whether correct short answers
(e.g., a bare timestamp for a "When?" question) were penalised for missing
unrequested fields. This is a broader construct-validity gap that the Round 2
semantic scorer now closes.

**Conclusion on vfz3's concern:** confirmed. The original headline numbers conflate
output-contract compliance with semantic correctness on unique questions. The
corrected figure is: on uniquely specified questions, the semantic advantage of F3
over F0 is zero.

### Component 2: Latest-event selection on multi-candidate questions

42 of 150 items involve multiple valid candidate events (CEO succession, ownership
transfers). Under the "latest event" convention used by the gold standard, arm scores
diverge:

| Arm | Exact-match (NU-latest, n=42) |
|-----|-------------------------------|
| F0  | 13/42 (31.0%)                 |
| F1  | 16/42 (38.1%)                 |
| F2  | 38/42 (90.5%)                 |
| F3  | 35/42 (83.3%)                 |

F2 and F3 are statistically indistinguishable here (Δ = −0.071, p = 0.508). Both
benefit from the prev/event/next representation instruction that foregrounds the
latest event in context. The genuine semantic advantage—if the "latest event"
convention is accepted—belongs equally to F2 and F3 and is better attributed to
the temporal representation instruction than to the full structured bundle.

We note that the benchmark does not state the "latest event" convention; this is an
implicit scoring choice. We disclose this as a limitation and include sensitivity
analyses with alternative conventions.

---

## Response to Reviewer EdSa

> *"The evaluation should include semantic grading rather than exact string
> matching."*

**Done.** We implemented a schema-agnostic semantic scorer (Scenarios B1, B2, C2-B1)
that extracts the asked fields (e.g., only the timestamp for a "When?" question)
from raw outputs using pattern-based claim extraction, independent of output format.
Key results:

| Scenario | F0 | F1 | F2 | F3 |
|----------|----|----|----|-----|
| A: Original exact-match | 13 | 90 | 39 | 109 |
| B1: Semantic question-aligned | 91 | 90 | 132 | 113 |
| C2-B1: Unique questions only, semantic | 74/74 | 74/74 | 74/74 | 74/74 |

Under semantic scoring (B1), **F2 leads all arms** (132/150 = 88.0%) while F3 falls
to 113/150 (75.3%). The F3−F2 contrast reverses: Δ = −12.7 pp [−19.7, −6.2],
p = 0.0003. This is because F2's prev/event/next representation correctly isolates
the event fields needed to satisfy "When?" and "Who?" questions without wrapping
them in a strict tuple, so the semantic scorer finds the answer content even when
the exact tuple format differs.

The document question defect warrants explicit disclosure. 34 of 150 items ask
"revised from v1 to v2" but gold tuples use later revision numbers (2→3, 4→5, 6→7)
and the evidence packs contain no version identifiers. These 34 items cannot be
answered as stated. Under Scenario B1-nodoc (excluding 34 doc items, n=116):

| Arm | F0 | F1 | F2 | F3 |
|-----|----|----|----|----|
| Semantic (B1-nodoc) | 87 | 90 | 112 | 109 |

The relative ordering is unchanged: F2 and F3 lead, F2 slightly higher semantically.

> *"Cross-model replication would strengthen confidence in the results."*

We acknowledge this. The current analysis is limited to the original model outputs.
Cross-model replication is listed as future work in the revised manuscript (Section 7).

> *"The 'latest event' convention should be disclosed and justified."*

Agreed. The convention is now explicitly disclosed. The NU-latest scenario above
quantifies its effect. We will add this to the benchmark documentation and the paper.

---

## Response to Reviewer Rkeo

> *"Potential leakage: were model outputs collected after the benchmark was
> designed?"*

The forensic leakage audit (pre-registered as M6, archived in `forensic/` with
SHA-256 chain) returned PASS on all 26 checks. Key checks: (1) no prompt text
contains gold answers; (2) frozen output timestamps predate the round 1 annotation
start; (3) the private arm mapping was held in a separate process and was not
available to annotators. Full audit results are in `forensic/FORENSIC_AUDIT.md`.

> *"Analyst degrees of freedom: many design choices could have been made
> differently."*

We pre-registered the evaluation protocol before Round 2 annotation began (hash on
file). The sensitivity analysis covers 17 scenarios including: original vs.
semantic scoring, inclusion/exclusion of ambiguous questions, inclusion/exclusion
of document items, v1 vs. v2 scorer, and three adjudication treatments for the 6
discordant items. The main qualitative conclusion—that the F3 advantage is
attributable to output-contract compliance on unique questions and to temporal
representation on multi-candidate questions—holds across all 17 scenarios. Full
results are in `analysis/round2/sensitivity_analysis.csv`.

> *"F1 and F2 results appear post-hoc."*

F1 and F2 were included in the original benchmark design as ablation arms. Their
inclusion was fixed before data collection and specified in the pre-registration.
The post-hoc concern about analysts choosing which arm to highlight is addressed by
reporting all four arms together in all scenarios, with no arm excluded from any
table.

> *"Presentation issues: tables are hard to read, terminology inconsistent."*

We will revise the manuscript presentation in a camera-ready revision. Specific
changes: (1) add a terminology glossary (Table 0); (2) add a decision-tree figure
for the structural audit; (3) standardise "exact-match v2" vs. "published scorer"
terminology throughout.

---

## Summary of Key New Findings

| Finding | Evidence |
|---------|----------|
| On uniquely specified questions (n=74), semantic gap F3−F0 = 0 | Scenario C2-B1, all arms 74/74 |
| Exact-match gap on unique questions is output-contract compliance | Δ = +86.5 pp exact vs. 0.0 pp semantic |
| F2 leads semantically when doc questions included (B1: 132/150) | F3 = 113/150, Δ = −12.7 pp, p = 0.0003 |
| F2 ≈ F3 on multi-candidate questions under "latest event" | NU-latest: 38 vs. 35, Δ = −0.071, p = 0.508 |
| Latest-event convention undisclosed; now disclosed | Limitation added to manuscript |
| 34 doc items unanswerable as stated; now disclosed | Limitation added to manuscript |
| Round 2 human reliability κ = 0.758 | 44/50 agreement, 50 items |
| Leakage audit PASS on all 26 checks | Forensic M6 archive |

We appreciate the reviewers' thorough engagement. The new evidence substantially
qualifies the original claims: the F3 structured prompt provides output-contract
benefits rather than semantic world-state tracking improvements. We propose revising
the paper's framing accordingly.
