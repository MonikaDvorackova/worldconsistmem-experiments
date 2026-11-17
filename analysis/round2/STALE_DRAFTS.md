# Stale rebuttal drafts (superseded by PR #10)

The only canonical rebuttal text is `analysis/round2/final_rebuttal_openreview.md`. Every file below now carries a "SUPERSEDED, do not paste" banner. Do not copy text from them.

| File | Copy-paste hazard found in this audit |
|---|---|
| `analysis/round2/rebuttal.md` | "forensic audit PASS on all 26 checks"; "pre-specified … hash on file"; "17 scenarios" |
| `analysis/round2/rebuttal_final.md` | "Forensic audit PASS on all 26 checks"; "Pre-registration hash on file"; "17 sensitivity scenarios" |
| `analysis/round2/reviewer_a_response.md` | "κ=0.336 was caused by rubric ambiguity … Round 2 … achieved κ=0.758" (before–after claim) |
| `analysis/round2/reviewer_b_response.md` | "Forensic audit PASS on all 26 checks"; "pre-registration hash on file" |
| `analysis/round2/final_reviewer_a.md` | "κ=0.336 reflects a systematic rubric gap, not random noise" (before–after claim) |
| `analysis/round2/final_reviewer_b.md` | "Forensic audit PASS on all 26 checks"; "pre-registered … hash on file"; "17-scenario" |
| `analysis/round2/final/OPENREVIEW_REVIEWER_A.md` | superseded OpenReview text; see canonical draft |
| `analysis/round2/final/OPENREVIEW_REVIEWER_B.md` | "Semantic grading is complete"; "Forensic audit: PASS on all 26 checks"; "hash on file"; "17-scenario" |
| `analysis/round2/final/SUBMISSION_READY.md` | "17-scenario sensitivity" as a completed item |
| `analysis/round2/final/FINAL_CLAIMS_VERIFIED.md` | sign test written as "10/12 worlds … p=0.001" (fixed in place; banner added) |
| `analysis/round2/final_claim_evidence_matrix.md` | "Forensic leakage audit PASS on all 26 checks"; "p=0.001" (fixed in place; banner added) |
| `analysis/round2/final_submission_checklist.md` | "Leakage 26/26 PASS … forensic/FORENSIC_AUDIT.md" |
| `analysis/round2/final_manuscript_changes.md` | "Round 2 corrects this" (before–after claim) |
| `analysis/round2/submission_package.md` | "17 scenarios" |
| `analysis/round2/manuscript_revision_checklist.md` | manuscript checklist; not verified against any manuscript file |
| `analysis/round2/evidence_inventory.md` | Round 1 κ=0.336 "not suitable … without Round 2" (before–after framing) |
| `analysis/round2/hypothesis_assessment.md` | "Round 1: κ=0.336 … prompted Round 2" (before–after framing) |
| `analysis/round2/f2_f3_paired_analysis.md` | "protocol hash on file" |
| `rebuttal/ICLR2027_reviewer_responses_WORKING_DRAFT.md` | "re-audit changing 77/150 labels" (no supporting table in the repository) |
| `experiments/rebuttal_temporal_control/DRAFT_REBUTTAL.md` | supporting manuscript text for the Qwen run; not rebuttal text |

## Also corrected in place (wording only; no data or scoring changed)

- `analysis/round2/final_statistical_audit.md` §B: "10/12 non-tied worlds" → "10 of 10 non-tied worlds, two ties; one-sided exact p = 0.00098".
- `analysis/round2/final/FINAL_CLAIMS_VERIFIED.md`: same correction.
- `analysis/round2/final_claim_evidence_matrix.md`: same correction.

## Removed claims (not verifiable in the repository)

- "Forensic audit passed its 26 checks" (no forensic archive present).
- "Pre-registration / protocol hash on file" (no hash file present).
- "17-scenario" count (the CSV has 18 distinct labels).
- "77/150 re-audited labels" (no table present).
- "Semantic grading is complete" in the sense of human grading (the semantic rule is B1; human review covers 50 responses).
