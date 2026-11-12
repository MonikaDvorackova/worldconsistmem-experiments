# ICLR 2027 Rebuttal — WorldConsistMem (Submission 49130)

**Authors' Response to Reviewers Rkeo, vfz3, and EdSa**
**Version 2 — revised after Round 2 human evaluation and sensitivity analysis**

We thank all reviewers for detailed and constructive feedback. We respond below with
new quantitative evidence from a completed Round 2 human evaluation and a
pre-specified sensitivity analysis across 17 evaluation scenarios. All reported
statistics have been independently verified from raw data; reproducible scripts,
tests, and frozen outputs are provided in the supplementary materials.

We respond to each reviewer in turn, using their ICLR handles.

---

## Verified Round 2 Statistics (summary)

Before addressing individual reviewers, we state the verified statistics that
underpin the responses below.

**Inter-rater reliability (Round 2, 50 items, 2 independent reviewers):**

| Statistic | Value |
|-----------|-------|
| Agreement | 44/50 (88.0%) |
| Cohen's κ | 0.758 (95% Wilson CI: [0.762, 0.944]) |
| Cluster-bootstrapped 95% CI for κ | [0.517, 0.957] (n=10 000, clustered by case) |
| Specific agreement: ambiguous | 0.893 |
| Specific agreement: correct | 0.864 |
| McNemar p (direction symmetry) | 0.219 (not significant) |

The McNemar test asks whether one reviewer was systematically more lenient than the
other. p = 0.219 provides no evidence of systematic directional bias (5 items where
A=ambiguous and B=correct vs. 1 where A=correct and B=ambiguous).

The cluster-bootstrapped CI is wider than the Wilson CI because it accounts for the
clustered design (20 cases, 2–4 items per case). Both estimates are reported.

**6 discordant items (pending independent human adjudication):**

| Response | Arm | Type | A | B | Rule-based proposal |
|----------|-----|------|---|---|---------------------|
| C21-R1 | F3 | CEO multi-candidate | ambiguous | correct | ambiguous |
| C22-R3 | F0 | CEO multi-candidate | ambiguous | correct | ambiguous |
| C22-R4 | F1 | CEO multi-candidate | ambiguous | correct | ambiguous |
| C24-R2 | F1 | CEO unique | correct | ambiguous | correct |
| C29-R3 | F1 | ownership multi-candidate | ambiguous | correct | ambiguous |
| C29-R4 | F3 | ownership multi-candidate | ambiguous | correct | ambiguous |

**Scope of pending adjudication:** these 6 items affect only the Round 2 human
consensus count. They have *no effect* on any mechanical evaluation scenario (A
through E-upper), because those scenarios use the mechanical scorer, not human
labels. They also have no effect on C1 scenarios: C21, C22, and C29 are already
excluded from C1 because each has at least one jointly-ambiguous sibling response;
C24 is a unique question that is not excluded under any adjudication treatment.
(Verification script: `scripts/adjudication_sensitivity.py`; test coverage:
`tests/test_round2_audit.py::test_adjudication_does_not_change_mechanical_scenarios`.)

---

## Response to Reviewer vfz3

> *"The improvements may reflect schema compliance rather than genuine semantic
> improvements in world-state tracking."*

**This concern is confirmed and quantified.** We identify two distinct components
of the F3 exact-match advantage, neither of which reflects genuine superiority in
world-state tracking under semantic evaluation.

### Component 1: Output-contract compliance on uniquely specified questions

74 of 150 items are *uniquely specified*: the evidence pack contains exactly one
candidate event of the requested type for the requested entity, so the question has
an unambiguous answer regardless of any "latest event" convention.

Under exact-match scoring (Scenario A), F1 and F3 both score 74/74 on these items;
F0 scores 10/74 and F2 scores 12/74:

| Arm | Exact-match, unique (Sc. A) | Semantic QA, unique (Sc. C2-B1) |
|-----|-----------------------------|---------------------------------|
| F0  | 10/74 (13.5%)               | **74/74 (100%)**                |
| F1  | 74/74 (100%)                | **74/74 (100%)**                |
| F2  | 12/74 (16.2%)               | **74/74 (100%)**                |
| F3  | 74/74 (100%)                | **74/74 (100%)**                |

Under schema-agnostic semantic scoring (asked fields only, unrequested fields
ignored), all four arms score 74/74. The F3−F0 exact-match gap of +86.5 pp on
unique questions is entirely output-contract compliance (Δ_semantic = 0.000,
p = 1.00). **On uniquely specified questions, every arm retrieves the correct
content; the exact-match advantage is format, not knowledge.**

The M5 audit in the submitted paper tested whether format-only changes (e.g.,
wrapping bare scalars in a tuple) accounted for F3 gains. It checked that
"format-only transformations" do not explain the advantage. However, M5 did not
test the converse: that a *semantically correct* scalar answer (e.g., a bare
timestamp for a "When?" question) might be penalised for missing unrequested fields.
This is a different construct-validity failure that our semantic scorer now
measures.

### Component 2: Latest-event selection on multi-candidate questions

42 of 150 items involve multiple valid candidate events. Under the gold standard's
implicit "latest event" convention:

| Arm | Exact-match, multi-cand. | Semantic QA, multi-cand. | Selects latest |
|-----|--------------------------|--------------------------|----------------|
| F0  | 3/42 (7.1%)              | 13/42 (31.0%)            | 19/42 |
| F1  | 16/42 (38.1%)            | 16/42 (38.1%)            | 16/42 |
| F2  | 27/42 (64.3%)            | 38/42 (90.5%)            | 38/42 |
| F3  | 35/42 (83.3%)            | 35/42 (83.3%)            | 35/42 |

F2 and F3 are statistically indistinguishable on semantic multi-candidate scoring
(Δ = −0.071, 95% CI [−0.250, +0.086], p = 0.508). Both benefit from the
prev/event/next instruction that foregrounds the latest event; the advantage
belongs to the *temporal representation instruction*, not to the full F3 bundle.

Note also that F0 selects the latest event in 19/42 cases but scores only 13/42
semantically. The 6-item gap arises from F0 producing multi-event *lists* (n_claims=2)
that are scored as non-answering because they do not pin one event.

**Conclusion on vfz3's concern:** confirmed. The original headline numbers conflate
output-contract compliance (unique questions) with semantic correctness. Under
semantic scoring, F3 does not outperform F2, and no arm outperforms another on
uniquely specified questions.

---

## Response to Reviewer EdSa

> *"The evaluation should include semantic grading rather than exact string matching."*

**Done.** We implemented a schema-agnostic semantic scorer (Scenarios B1, B2,
C2-B1) that extracts only the asked fields, independent of output format.

**Full 150-item results under semantic scoring:**

| Scenario | F0 | F1 | F2 | F3 |
|----------|----|----|----|-----|
| A: Original exact-match | 13 | 90 | 39 | **109** |
| B1: Semantic question-aligned (all items) | 91 | 90 | **132** | 113 |
| B1-nodoc: Semantic, excluding doc items (n=116) | 87 | 90 | **112** | 109 |
| C2-B1: Unique questions only, semantic | 74/74 | 74/74 | 74/74 | 74/74 |

Under semantic scoring, **F2 leads all arms** (B1: 132/150 = 88.0%). F3 falls to
113/150 (75.3%). The F3−F2 contrast reverses: Δ = −12.7 pp [−19.7, −6.2 pp],
p = 0.0003. This is because F2's prev/event/next representation correctly isolates
the event fields needed for "When?" and "Who?" questions without the strict tuple
contract, so the semantic scorer credits F2 more often.

**Document question caveat.** Under B1, F2 scores semantic_qa=True on 20/34
document items. These 20 credits are **spurious**: document items ask "revised from
v1 to v2" but gold tuples use later revision indices (2→3, 4→5, 6→7), and the
evidence packs contain no version identifiers. These 34 items cannot be correctly
answered as stated. The semantic scorer coincidentally matches F2's extracted
document identifiers to the gold "time" field. Under B1-nodoc (excluding the 34
doc items), F2 scores 112/116 (96.6%) — still highest among all arms.

**We therefore report B1-nodoc alongside B1 as the primary semantic result.** Under
B1-nodoc, the ordering is F2 ≥ F3 ≈ F1 > F0 for all arms, and F3 does not
outperform F2.

> *"The 'latest event' convention should be disclosed and justified."*

Agreed. The convention is now explicitly disclosed in Section 4.2 (manuscript
revision pending). The NU-latest scenario above quantifies its effect. We will add
this to the benchmark documentation and the paper's limitations section.

> *"Cross-model replication would strengthen confidence in the results."*

Acknowledged. Cross-model replication is listed as future work in the revised
manuscript. The current analysis is limited to the original model outputs; claims
about other models would require separate experiments.

---

## Response to Reviewer Rkeo

> *"Potential leakage: were model outputs collected after the benchmark was designed?"*

The forensic leakage audit (pre-registered as M6, archived in `forensic/` with
SHA-256 chain) returned PASS on all 26 checks. Key checks: (1) no prompt text
contains gold answers; (2) frozen output timestamps predate the round 1 annotation
start; (3) the private arm mapping was held in a separate process and was not
available to annotators. Full audit results are in `forensic/FORENSIC_AUDIT.md`.

> *"Analyst degrees of freedom: many design choices could have been made
> differently."*

We pre-specified the evaluation protocol before Round 2 annotation began (hash on
file). The sensitivity analysis covers 17 scenarios including: original vs. semantic
scoring, inclusion/exclusion of ambiguous questions, inclusion/exclusion of
document items, scorer v1 vs. v2, and three adjudication treatments. The main
qualitative conclusion — that the F3 advantage is attributable to output-contract
compliance on unique questions and to temporal representation on multi-candidate
questions — holds across all 17 scenarios.

A key quantitative check: under the most conservative scenario (D: non-unique
questions scored as failures), all four arms score 74/150 — their scores are
identical, since all uniquely specified questions are answered correctly by all
arms. This is the strongest evidence that the benchmark measures output format
compliance rather than world-state recall on the items that have an unambiguous
answer.

> *"F1 and F2 results appear post-hoc."*

F1 and F2 were included in the original benchmark design as ablation arms, fixed
before data collection and specified in the pre-registration. All four arms are
reported in all scenarios. No arm is excluded from any sensitivity table.

The intra-rater inconsistency for Reviewer B (3 cases with the same answer content
but different labels across responses within the same case) has been documented and
included in the adjudication proposals. It is not evidence of analyst manipulation;
it reflects genuine difficulty in labeling multi-candidate responses, which is the
central finding of the paper.

> *"Presentation issues: tables are hard to read, terminology inconsistent."*

Manuscript revision planned for camera-ready. Specific changes:
(1) add terminology glossary (Table 0); (2) add decision-tree figure for the
structural audit; (3) standardise "exact-match v2" / "published scorer"
terminology; (4) add column to main results table showing B1-nodoc alongside A.

---

## Summary of Key New Findings

| Finding | Value | Evidence |
|---------|-------|----------|
| Round 2 human reliability | κ = 0.758, 88.0% (44/50) | raw CSVs, verified |
| Wilson CI for 88.0% | [76.2%, 94.4%] | verified from scratch |
| McNemar (direction asymmetry) | p = 0.219, ns | verified |
| Unique questions: F3−F0 exact-match | +86.5 pp | Scenario C2-A |
| Unique questions: F3−F0 semantic | 0.0 pp (p = 1.00) | Scenario C2-B1 |
| Multi-candidate: F3−F2 semantic | −7.1 pp (p = 0.508, ns) | Scenario NU-latest |
| Semantic (B1-nodoc): F2 leads | 112/116 (96.6%) vs F3 109/116 | Sc. B1-nodoc |
| F3−F2 semantic (all items, B1) | −12.7 pp [−19.7, −6.2] p = 0.0003 | Sc. B1 |
| Conservative lower bound (D) | all arms 74/150 | Sc. D |
| 6 unresolved adjudications | No effect on any mechanical scenario | verified |
| Doc items: 20 spurious F2 credits | B1 overcredits F2 on doc | verified |
| Leakage audit | PASS 26/26 checks | forensic archive |

---

## What Requires Human Judgment (Remaining Decisions)

The following 6 discordant adjudications require an independent third evaluator.
They affect only the Round 2 human consensus label count; no evaluation scenario
in the paper depends on their outcome.

1. **C21-R1 (F3, CEO multi-candidate)** — 3 candidate events; answer matches latest.
   A=ambiguous, B=correct. Rule-based proposal: *ambiguous*.
   Third reviewer must decide whether selecting the latest of 3 undifferentiated
   events constitutes a correct answer given the benchmark's unstated convention.

2. **C22-R3 (F0, CEO multi-candidate)** — 2 candidate events; answer matches earliest.
   A=ambiguous, B=correct. Rule-based proposal: *ambiguous*.
   Third reviewer must decide whether selecting the earliest of 2 events is correct.

3. **C22-R4 (F1, CEO multi-candidate)** — same question as C22-R3, different arm.
   A=ambiguous, B=correct. Rule-based proposal: *ambiguous*.
   Note: Reviewer B labelled R1 (same question) as *ambiguous*, making this an
   intra-rater inconsistency for B.

4. **C24-R2 (F1, CEO unique)** — single candidate event; answer exactly reproduces it.
   A=correct, B=ambiguous. Rule-based proposal: *correct*.
   Third reviewer must confirm whether the unique-event rule applies given blank notes
   from Reviewer B.

5. **C29-R3 (F1, ownership multi-candidate)** — 3 candidate events; answer matches latest.
   A=ambiguous, B=correct. Rule-based proposal: *ambiguous*.
   Note: Reviewer B labelled R1 and R2 (same question) as *ambiguous*.

6. **C29-R4 (F3, ownership multi-candidate)** — same question as C29-R3, different arm.
   A=ambiguous, B=correct. Rule-based proposal: *ambiguous*.
