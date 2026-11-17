# Rebuttal number audit (PR #10)

Scope: every number in the canonical draft `analysis/round2/final_rebuttal_openreview.md`. Recomputed by `scripts/verify_rebuttal_numbers.py` from committed per-item tables; Qwen numbers recomputed by `scripts/audit_rebuttal_temporal_outputs.py`. No raw output or scoring rule was changed.

Status key: **Verified** = recomputed here and matches; **Verified (reported value)** = a committed analysis output that this script does not reproduce exactly (noted); **Removed** = not verifiable in the repository; **Unresolved** = stated with a limitation.

## 1. Round 2 reliability

| Claim | Value | Source / calculation | Status |
|---|---|---|---|
| Items re-rated | 50 Round 1 disagreements | `analysis/round2/reviewer_agreement.csv`; all 50 rows have `round1_reviewer_1 != round1_reviewer_2` | Verified |
| Cases | 20 | `reviewer_agreement.csv` `case_id` | Verified |
| Agreement | 44/50 | count of `round2_reviewer_A == round2_reviewer_B` | Verified |
| κ | 0.758 (0.7581) | Cohen's κ on the 50 pairs | Verified |
| κ CI | [0.517, 0.957] | `analysis/round2/round2_results.json` `ci95_lo` 0.51714, case-cluster bootstrap (`scripts/round2_analysis.py`) | Verified (reported value). Our seed-0 cluster bootstrap gives [0.521, 0.957]; the committed run's seed is not recorded, so the lower bound differs at the third decimal. |
| Unresolved | 6 | `reviewer_agreement.csv` `round2_status == disagreement` | Verified |
| Rated fields | semantic label only; `evidence_sufficient` = `unclear` in all 100 rows; `notes` and `rubric_reason` blank | `analysis/round2/evaluation_report.md` §2 (protocol deviation) | Verified |

Round 2 is described as a re-rating of the selected disputed subset, not a before–after reliability comparison.

## 2. Stale-state, latest selection, and the world sign test (42 multi-candidate items, 12 worlds)

| Claim | Value | Source / calculation | Status |
|---|---|---|---|
| Stale (earliest matched, latest not) | F0 23, F1 17, F2 2, F3 7 of 42 | `analysis/round2/case_level_error_analysis.csv` `{arm}_positions` | Verified |
| Latest-event selection | F0 19, F1 16, F2 38, F3 35 of 42 | `analysis/round2/temporal_state_analysis.csv` `{arm}_temporal_correct` | Verified |
| Worlds with these items | 12 | `case_level_error_analysis.csv` `world_id` | Verified |
| World sign test (stale, F2 vs F0) | **10 of 10 non-tied worlds favour F2, 0 favour F0, 2 tie** | per-world stale counts | Verified. Corrected wording: earlier drafts and `final_statistical_audit.md` §B say "10/12 non-tied worlds"; 10 of 12 would be the wrong denominator. |
| One-sided exact p | 0.00098 | P(X ≥ 10), X ~ Bin(10, 0.5) = 1/1024 | Verified. Earlier "p=0.001" in some drafts is the same value; 10/12 would give 0.019. |
| Latest F2−F0 item-level | +45.2 pp; discordant (21, 2) | `temporal_state_analysis.csv`; (21−2)/42 | Verified |
| Latest F2−F0 CI | [+27.5, +62.9] | `analysis/round2/sensitivity_analysis.csv` / `final_statistical_audit_results.json` `paired_temporal` `F0_vs_F2` (item-level, treated as independent) | Verified (reported value); descriptive only |
| Latest F2−F0 p | 6.6×10⁻⁵ | exact binomial two-sided, n = 23 discordant | Verified |
| F1 asymmetry | ownership stale 0/22; CEO stale 17/20 | `final_statistical_audit_results.json` `f1_slot_asymmetry` | Verified |

## 3. B1 semantic scoring and sensitivity analyses

| Claim | Value | Source / calculation | Status |
|---|---|---|---|
| Exact match, unique items (74) | F0 10, F1 74, F2 12, F3 74 | `final_statistical_audit_results.json` `unique_questions` | Verified (reported) |
| Semantic, unique items | 74/74 all arms | same file | Verified (reported) |
| B1 all 150 | F0 91, F1 90, F2 132, F3 113 | `case_level_error_analysis.csv` `{arm}_semantic` sums | Verified |
| B1-nodoc (n=116) | F0 87, F1 90, F2 112, F3 109 | same, `question_status != version_unidentifiable` | Verified |
| F3−F0 B1-nodoc | +19.0 pp; discordant (23, 1); exact p = 2.98×10⁻⁶ | item level | Verified |
| F3−F0 B1-nodoc world CI | [+9.65, +29.06] | `sensitivity_analysis.csv` row B1-nodoc, `paired_contrast` (world-cluster bootstrap, 18 worlds, 10,000 draws) | Verified (reported). Our seed-0 reproduction gives [9.82, 29.20]; point estimate identical. |
| F3−F0 B1 all 150 | +14.7 pp; CI [+6.2, +22.9] | `sensitivity_analysis.csv` row B1, `paired_contrast` | Verified (reported); point estimate = (113−91)/150 |
| F2−F3 B1-nodoc | +2.6 pp (F2 − F3); discordant (6, 3); exact p = 0.508 | item level | Verified |
| F2−F3 world CI | **[−3.15, +9.01]** (= sign-flipped `F3-F2` row −2.59 [−9.01, +3.15]) | `sensitivity_analysis.csv` row B1-nodoc, `paired_contrast` `F3-F2` | Verified (reported). **Correction:** the earlier draft presented [−2.5, +7.6] as the interval; that value is the item-level paired interval in `final_statistical_audit.md` §C. Both are now labelled. |
| F2−F3 item CI | [−2.5, +7.6] | `final_statistical_audit.md` §C, `paired_semantic_nondoc` | Verified (reported) |
| Document spurious credits | F0 4, F1 0, F2 20, F3 4 of 34 | `case_level_error_analysis.csv` doc rows | Verified |
| Document items | 34, "no version identifiers" | `case_level_error_analysis.csv` `version_unidentifiable`; `final_statistical_audit.md` §D | Verified (reported) |
| Sensitivity upper bound (E-upper) | F0 144, F1 149, F2 150, F3 150 of 150 | `sensitivity_analysis.csv` row E-upper | Verified |
| Scenario count | **18 distinct labels** (A, A-S1S2, A-v1, A-nounwrap, B1, B1-nodoc, B2, C1-A, C1-B1, C2-A, C2-B1, C2-B2, D, E-lower, E-mid, E-upper, NU-latest, H) | `sensitivity_analysis.csv` `scenario` column | **Resolved:** "17-scenario" matches no count in the CSV and is removed. |
| Old 77/150 relabelling figure | not in any table | searched all committed files; appears only in `rebuttal/ICLR2027_reviewer_responses_WORKING_DRAFT.md` and `reviewer_b_response.md` | **Removed.** Evidence-sufficiency relabelling is not claimed. |
| Scorer v1 → v2 | exact F0 0/150 → 13/150 | `sensitivity_analysis.csv` rows A-v1 and A | Verified |

## 4. BCR

| Claim | Value | Source / calculation | Status |
|---|---|---|---|
| Bundles | 1,088 | `data/scaled/bundles.jsonl` | Verified |
| Mean queries per bundle | 6.56 (draft earlier said 6.6) | `len(queries)` per bundle | Verified; draft now reports 6.56 |
| Expected consistent bundles at 0.185 | 0.017 (draft says about 0.02) | 1,088 × 0.185^6.56 | Verified |
| BCR = 0 | reported as H0 result | `final_statistical_audit.md` §E | Reported; interpretation limited to the independence baseline |

## 5. Leakage, preregistration, and hashes

| Claim | Status | Reason |
|---|---|---|
| "Forensic audit passed its 26 checks" | **Removed** | No `forensic/` directory, no `FORENSIC_AUDIT.md`, and no archive in the repository (searched the full branch). Citations in older drafts point to files that do not exist. |
| "Pre-registration hash on file" / "protocol hash" | **Removed** | No hash file exists in the repository. |
| "F3 versus F0 is the prespecified comparison" | **Unresolved** | The designation is stated in the analysis files; no pre-annotation timestamp or protocol hash supports it. Draft now says it cannot be verified and does not call it preregistered. |
| Qwen protocol preregistration | Verified | Protocol committed in `cb8d8bf` (2026-11-12) before the data-generation commit `c5e721e`. |

## 6. Qwen temporal-control run

| Claim | Value | Source / calculation | Status |
|---|---|---|---|
| Model and revision | `mlx-community/Qwen2.5-3B-Instruct-4bit`, revision `4f83f8f146fdf28b512a06562b671d7af4fab457` | `experiments/rebuttal_temporal_control/data/evaluation_results.json` `model`; `model_metadata.json` | Verified |
| Primary B−C | −0.360 (−36.0 pp); CI [−0.405, −0.315]; sign-flip p = 0.000010 | `evaluation_results.json` `primary`; recomputed by `audit_rebuttal_temporal_outputs.py` from scored rows | Verified |
| Accuracy | B 1/200 = 0.5%; C 73/200 = 36.5% | `evaluation_results.json` `descriptive_by_condition` | Verified |
| Format validity | 200/200 in all conditions | same | Verified |
| Prompt tokens | B 28,227.6; C 13,577.2 (≈2.1×) | same, `mean_prompt_tokens` | Verified |
| Length association | r = −0.128, permutation p = 0.203 | recomputed by `world_clustered_analysis` in the audit script | Verified (recomputed). **Not in the committed `evaluation_results.json`**; see §7. |
| Scoring check | 800/800 rows recalculated from raw outputs, 0 mismatches; audit PASS | `audit_rebuttal_temporal_outputs.py` output | Verified |
| Scorer-validation sample | 5 examples | `data/generation_manifest.json` `scorer_validation.examples` | Verified. The protocol asks for an arm-blinded stratified sample; not documented as done. Limitation stated. |
| Run status | `COMPLETED_LOCAL_INFERENCE_AUDITED` | `evaluation_results.json` | Verified |

## 7. Reconciliation problems found and how they were handled

1. **Qwen draft vs. run status.** `DRAFT_REBUTTAL.md` in its earlier form said inference had not run. The current file reports the completed run, and the committed evaluation summary and integrity audit agree with it.
2. **Manifest status.** `generation_manifest.json` still records `GENERATED_NO_MODEL_INFERENCE`. This is the generation-stage record, written before inference. It was not edited, because it is an input record; the completed status is in `evaluation_results.json` and `raw_integrity_audit.md`.
3. **Audit comparator.** `audit_rebuttal_temporal_outputs.py` asserted that the full recomputed primary dict equals the committed `primary` block. The committed audited summary has no `prompt_length_effect_association` key, so the assertion failed. We changed only the comparator to compare the committed primary fields, and print the length association from recomputation. The committed result file was not modified. With this change the script reports `audit: PASS`.
4. **κ and B1-nodoc intervals.** Our seed-0 bootstraps differ slightly from the committed intervals (κ lower bound 0.521 vs 0.517; B1-nodoc CI [9.82, 29.20] vs [9.65, 29.06]). The draft reports the committed values, labelled as reported, and this note records the difference.

## 8. Tests and checks run

- `tests/test_rebuttal_temporal.py` and `tests/test_round2_audit.py` (Python 3.12, `~/.venvs/eid`, `PYTHONPATH=src`): **62 passed, 11 skipped**.
- `scripts/verify_rebuttal_numbers.py`: all counts above reproduced.
- `scripts/audit_rebuttal_temporal_outputs.py` (with the comparator change in §7.3): `audit: PASS`, scorer mismatches 0.

## 9. Stale drafts

See `analysis/round2/STALE_DRAFTS.md`. Each superseded file now carries a banner so it cannot be pasted by mistake.

## 10. Manuscript

No manuscript file was revised or verified in this audit. Manuscript changes listed in the drafts are planned and not verified.
