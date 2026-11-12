# Submission-Ready Package — WorldConsistMem Round 2

**Purpose:** Anonymized, submission-ready summary of Round 2 findings for ICLR
OpenReview response. This document consolidates reviewer-response content,
remaining human decisions, and a reproducibility checklist.

**Date:** 2026-11-12
**Branch:** research/rebuttal-revision-v2

---

## 1. Verified Statistics

All statistics below were independently recomputed from raw reviewer CSV files
(`human_evaluation/round_2/completed/`) and cross-checked against stored results
(`analysis/round2/round2_results.json`). Verification script:
`scripts/adjudication_sensitivity.py` (47 tests pass).

### 1.1 Round 2 Inter-Rater Reliability

| Metric | Value |
|--------|-------|
| Items rated | 50 |
| Annotators | 2 independent |
| Agreed labels | 44 (88.0%) |
| Cohen's κ | 0.758 |
| Wilson 95% CI | [76.2%, 94.4%] |
| Cluster-bootstrap 95% CI (by case, n=10 000) | [51.7%, 95.7%] |
| Specific agreement: "ambiguous" | 89.3% |
| Specific agreement: "correct" | 86.4% |
| McNemar p (direction symmetry) | 0.219 (not significant) |
| Jointly-ambiguous items (both = ambiguous) | 25 |
| Jointly-correct items (both = correct) | 19 |
| Jointly-incorrect | 0 |
| Discordant | 6 |

### 1.2 Mechanical Evaluation Scenarios (reproduced)

| Scenario | Description | F0 | F1 | F2 | F3 | n |
|----------|-------------|----|----|----|-----|---|
| A | Original exact-match (scorer v2) | 13 | 90 | 39 | 109 | 150 |
| B1 | Semantic question-aligned | 91 | 90 | **132** | 113 | 150 |
| B1-nodoc | Semantic, excluding doc items | 87 | 90 | **112** | 109 | 116 |
| C2-A | Unique questions, exact-match | 10 | 74 | 12 | 74 | 74 |
| C2-B1 | Unique questions, semantic | 74 | 74 | 74 | 74 | 74 |
| NU-latest | Multi-candidate, latest-event | 13 | 16 | 38 | 35 | 42 |
| D | Conservative: non-unique → fail | 74 | 74 | 74 | 74 | 150 |
| E-lower | Sensitivity lower bound (= D) | 74 | 74 | 74 | 74 | 150 |
| E-upper | Sensitivity upper: any event credited | 144 | 149 | 150 | 150 | 150 |

### 1.3 Key Contrasts

| Contrast | Δ | 95% CI | p |
|----------|---|--------|---|
| F3−F0, Scenario A | +64.0 pp | [+57.8, +70.0] | 6.2e−28 |
| F3−F0, Scenario B1 | +14.7 pp | [+6.2, +22.9] | 1.1e−4 |
| F3−F2, Scenario B1 | **−12.7 pp** | [−19.7, −6.2] | 3.1e−4 |
| F3−F2, Scenario NU-latest | −7.1 pp | [−25.0, +8.6] | 0.508 (ns) |
| F3−F0, Scenario C2-B1 | 0.0 pp | [0, 0] | 1.000 |
| F3−F0, Scenario A, S1+S2 | +41.9 pp | [+33.3, +50.5] | 3.8e−11 |

---

## 2. Structural Decomposition

The 150 items per arm decompose into:

| Subset | n | Description |
|--------|---|-------------|
| Unique | 74 | Single candidate event; unambiguous answer |
| Multi-candidate | 42 | Multiple candidate events; answer depends on convention |
| Document (version-unidentifiable) | 34 | Unanswerable as stated (no version identifiers in evidence) |

On **unique** items: all arms retrieve the correct content under semantic scoring
(100%). The exact-match gap is entirely output-contract compliance.

On **multi-candidate** items: F2 and F3 both benefit from the temporal representation
instruction. F2 (38/42, 90.5%) and F3 (35/42, 83.3%) are not significantly different
(p = 0.508). The "latest event" convention drives this sub-score.

On **document** items: items are unanswerable as stated. F2 scores 20/34 semantically
under B1 due to a spurious match (see manuscript_revision_checklist item B2).
B1-nodoc excludes these items.

---

## 3. Remaining Human Decisions

**All 6 items require an independent third evaluator.** None affect any mechanical
evaluation scenario. They affect only the final Round 2 consensus human label.

| # | Response | Arm | Type | A | B | Proposal | Decision needed |
|---|----------|-----|------|---|---|----------|-----------------|
| 1 | C21-R1 | F3 | CEO multi-cand. | ambiguous | correct | ambiguous | Is selecting one of 3 documented events correct without a stated convention? |
| 2 | C22-R3 | F0 | CEO multi-cand. | ambiguous | correct | ambiguous | Is selecting the earliest of 2 events correct? (Reviewer B inconsistent within case) |
| 3 | C22-R4 | F1 | CEO multi-cand. | ambiguous | correct | ambiguous | Same question as C22-R3; Reviewer B inconsistent with C22-R1 |
| 4 | C24-R2 | F1 | CEO unique | correct | ambiguous | correct | Single event; answer exact match. Why did Reviewer B mark ambiguous? (notes blank) |
| 5 | C29-R3 | F1 | own multi-cand. | ambiguous | correct | ambiguous | Reviewer B inconsistent: R1/R2 labeled ambiguous, R3/R4 labeled correct (same answer) |
| 6 | C29-R4 | F3 | own multi-cand. | ambiguous | correct | ambiguous | Same as C29-R3; Reviewer B inconsistent within case |

**Intra-rater note:** Reviewer B assigned different labels to responses with the
same answer content in cases C22 (R1=ambiguous vs R3/R4=correct), C24 (R2=ambiguous
vs R4=correct), and C29 (R1/R2=ambiguous vs R3/R4=correct). This should be noted to
the third evaluator as potentially affecting their judgment.

**Sensitivity check:** under any resolution of the 6 items:
- Scenario A, B1, B2, C2-A, C2-B1, NU-latest, D, E-lower/mid/upper: **unchanged**
- C1-A, C1-B1 (exclude human-established ambiguous questions): **unchanged**
  (C21/C22/C29 are already excluded because they have jointly-ambiguous sibling
  responses; C24 is a unique question not excluded under any treatment)

---

## 4. Reproducibility Checklist

### For reviewers / meta-reviewers

- [ ] `uv run pytest tests/test_round2_audit.py -q` → 47 tests pass
- [ ] `uv run python scripts/adjudication_sensitivity.py` → all verifications pass
- [ ] `analysis/round2/round2_results.json` → machine-readable all results
- [ ] `analysis/round2/sensitivity_analysis.csv` → 17 scenarios × 4 arms + contrasts
- [ ] `analysis/round2/reviewer_agreement.csv` → 50 paired labels + status
- [ ] `analysis/round2/adjudication_proposals.csv` → 6 unresolved items with evidence
- [ ] `analysis/round2/ambiguous_case_audit.csv` → 50 items with structural classification

### Private snapshot (not in git; holds frozen outputs and arm mapping)

- [ ] Regenerate with `uv run python scripts/build_round2_private_snapshot.py`
  (requires original Downloads files and `~/.Trash/wcm_validation/PRIVATE_MAPPING.json`)
- [ ] After regenerating: `uv run python scripts/round2_analysis.py` → reproduces all scenarios

### Key file hashes (committed reviewer CSVs)

| File | SHA-256 prefix |
|------|---------------|
| reviewer_A__WCM_round_2_reviewer_1_COMPLETED.csv | aa897fa1... |
| reviewer_B__WCM_round_2_reviewer_1_COMPLETED2.csv | bfda954f... |

---

## 5. Files in This Analysis

| File | Description |
|------|-------------|
| `analysis/round2/rebuttal.md` | Anonymized ICLR rebuttal (v2) |
| `analysis/round2/evaluation_report.md` | Full 9-section technical report |
| `analysis/round2/sensitivity_analysis.csv` | All 17 scenarios |
| `analysis/round2/reviewer_agreement.csv` | 50 paired labels |
| `analysis/round2/ambiguous_case_audit.csv` | Structural audit of 50 items |
| `analysis/round2/adjudication_proposals.csv` | 6 unresolved items |
| `analysis/round2/adjudication_sensitivity_results.json` | Verification output |
| `analysis/round2/manuscript_revision_checklist.md` | 22 manuscript changes |
| `analysis/round2/submission_package.md` | This file |
| `scripts/adjudication_sensitivity.py` | Verification script |
| `scripts/round2_analysis.py` | Full pipeline |
| `scripts/_round2_report.py` | Report renderer |
| `src/worldconsistmem/round2_audit.py` | Core library |
| `tests/test_round2_audit.py` | 47 tests |
| `human_evaluation/round_2/completed/` | Blinded reviewer CSVs |
