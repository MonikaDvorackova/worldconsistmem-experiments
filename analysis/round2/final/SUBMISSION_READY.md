# Submission-Ready Status

**Date:** 2026-11-12  
**Decision: CONDITIONAL GO** for rebuttal submission to OpenReview

---

## Git integration status

| Item | Status |
|------|--------|
| PR #4 (`research/rigorous-reanalysis-v1`, commit `e5bd6cf`) | MERGED to main (3d4a27f) |
| Final audit commit `01058ba` | NOT in origin/main prior to this session |
| Integration branch | `research/final-audit-integration` (cherry-pick of `01058ba`) |
| Integration branch SHA | `a90d5e5` (cherry-pick of `01058ba`) |
| Integration PR | Requires creation — see NEXT ACTION |

The 8 final audit files are in `analysis/round2/` on branch `research/final-audit-integration`, pushed and ready for PR.

---

## Test results

```
uv run pytest tests/test_round2_audit.py
66 passed, 0 failed, 0 skipped  (1.75s)
```

New regression test `test_b1_nodoc_denominator_is_116` added in this session.

---

## Denominator reconciliation

**Correct denominator for B1-nodoc: 116**

- Total items: 150
- Doc items excluded: 34 (all version_unidentifiable / S2 / unanswerable)
- Non-doc items (B1-nodoc population): 116
- Figure "125" does not correspond to any valid population in the dataset

See `DENOMINATOR_RECONCILIATION.md` for full analysis.

---

## Statistical verification

All headline results independently reproduced from `item_scores.jsonl` via `scripts/rigorous_reanalysis.py`:

| Claim | Value | Status |
|-------|-------|--------|
| Unique n=74: all arms 74/74 semantic | verified | PASS |
| F3−F0 exact unique = +64, semantic = 0 | verified | PASS |
| Stale-state: F0=23/42, F2=2/42 | verified | PASS |
| F1 vs F2 stale-state McNemar p<0.0001 | p<0.0001 | PASS |
| F2 vs F3 stale-state McNemar p=0.508 | p=0.5078 | PASS |
| B1-nodoc: F2=112/116, F3=109/116 | verified | PASS |
| F2 vs F3 B1-nodoc McNemar p=0.508 | p=0.5078 | PASS |
| 20 F2 spurious doc credits | verified | PASS |
| 20 = 17 (F2-only) + 3 (both) | verified | PASS |
| κ Round 2 = 0.758 | 0.7581 | PASS |
| BCR=0 at Acc=0.185 not surprising | expected ≈0.02 bundles | PASS |

---

## Anonymity check

| Check | Status |
|-------|--------|
| No author names in submission text | PASS |
| No identifying affiliations | PASS |
| No personal websites | PASS |
| No GitHub repository URLs | PASS |
| No private paths or internal infra references | PASS |
| No deanonymizing acknowledgments | PASS |
| Reviewer response files reviewed | PASS |

---

## Reviewer concerns coverage

| Reviewer | Concern | Addressed |
|----------|---------|-----------|
| vfz3 RC1 | Schema confounding | YES — confirmed, tables provided |
| vfz3 RC2 | Label instability | YES — rubric gap explanation, Round 2 κ=0.758 |
| vfz3 RC3 | M5 audit scope | YES — revised scope statement |
| EdSa ED1 | Semantic grading | YES — B1-nodoc, all 600 items |
| EdSa ED2 | F3 claims | YES — superiority claim removed |
| EdSa ED3 | Latest-event convention | YES — added to Section 3 |
| EdSa ED4 | Cross-model replication | YES — acknowledged as future work |
| Rkeo RK1 | Leakage | YES — 26-check forensic PASS |
| Rkeo RK2 | Degrees of freedom | YES — 17-scenario sensitivity, counter-results disclosed |
| Rkeo RK3 | Post-hoc F1/F2 | YES — labeled exploratory throughout |
| Rkeo RK4 | Presentation | YES — glossary, taxonomy figure, metric naming |

---

## Content verified against: no unsupported claims

| Check | Status |
|-------|--------|
| No unsupported significance claims | PASS (F2 vs F3 p=0.508 → "no significant difference") |
| No misleading equivalence claims | PASS (stated as "available evidence does not establish a difference") |
| No claims of completed third-party adjudication | PASS (6 discordant items explicitly flagged as unresolved) |
| No promises of new experiments as completed | PASS (cross-model labeled "future work") |
| No causal overclaim on temporal reduction | PASS (stated as "associated with," mechanism undetermined) |
| Statistical non-significance ≠ equivalence | PASS (correctly distinguished throughout) |

---

## OpenReview response files

| File | Reviewer | Status |
|------|----------|--------|
| `OPENREVIEW_REVIEWER_A.md` | vfz3 | READY |
| `OPENREVIEW_REVIEWER_B.md` | EdSa + Rkeo | READY |
| `OPENREVIEW_ADDITIONAL_REVIEWER.md` | N/A | Not required (3 reviewers total; vfz3 has own file; EdSa/Rkeo combined) |

**Word count note:** ICLR 2027 rebuttal limits are not verified from an authoritative source. Standard recent practice is ~1000 words per reviewer. The reviewer responses above are within that range per reviewer. If a unified total limit applies (e.g., 1000 words total), trimming is required.

---

## Remaining conditions for camera-ready (not blocking rebuttal)

1. 20 REQUIRED manuscript changes from `final_manuscript_changes.md`
2. Resolution of 6 discordant adjudications (requires third annotator)
3. Tables updated to use B1-nodoc as primary metric
4. Appendix X: "any documented event" convention sensitivity analysis
5. LaTeX/PDF cleanup per Rkeo RK4
