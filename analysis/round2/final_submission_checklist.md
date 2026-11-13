# Final Submission Checklist — WorldConsistMem ICLR 2027

**Date:** 2026-11-12  
**Decision:** See GO/NO-GO section at bottom.

---

## Quality gates

### Data integrity

| Gate | Status | Evidence |
|------|--------|---------|
| No raw reviewer labels modified | PASS | `git diff` shows no changes to reviewer CSVs |
| Frozen outputs unmodified | PASS | SHA-256 chain in forensic archive; source file hash tests pass |
| No invented adjudications | PASS | All 6 discordant items remain `unresolved_pending_human_adjudication` |
| No new synthetic evaluation data | PASS | No new model outputs generated |

### Statistical validity

| Gate | Status | Evidence |
|------|--------|---------|
| No unsupported significance claims | PASS | F2 vs F3 p=0.508 → "no significant difference" |
| No misleading equivalence claims | PASS | Phrased as "available evidence does not establish a difference" |
| No numerical inconsistencies | PASS | 20 vs 17 reconciled; all counts verified against item_scores.jsonl |
| Clustering acknowledged | PASS | World-level sign test reported; CI approximation disclosed |
| Effect sizes reported | PASS | RD with 95% CI for all paired comparisons |
| McNemar exact (not χ²) | PASS | Implemented via `math.comb` without scipy |
| Confidence intervals reported | PASS | All major comparisons include CI |

### Anonymity

| Gate | Status | Evidence |
|------|--------|---------|
| No author names in submission text | PASS | final_rebuttal_openreview.md reviewed |
| No repository URLs | PASS | No GitHub URLs in submission text |
| No institution names | PASS | Reviewed |
| No identifying acknowledgments | PASS | None included |

### Disclosure completeness

| Gate | Status | Evidence |
|------|--------|---------|
| Latest-event convention disclosed | PASS | final_rebuttal_openreview.md |
| Doc item unanswerable disclosed | PASS | "34 document items all S2 insufficient evidence" |
| F2 spurious doc credits disclosed | PASS | "20 spurious credits, scorer artifact" |
| BCR=0 caveat added | PASS | "not surprising at Acc=0.185" |
| F1/F2 labeled exploratory | PASS | "post-result factorizations" |
| F1 CEO/own asymmetry disclosed | PASS | final_statistical_audit.md |
| Mechanism undetermined | PASS | "association, not causation" in final rebuttal |

### Test suite

| Gate | Status | Evidence |
|------|--------|---------|
| All 66 tests pass | PASS | pytest output in commit history |
| New tests independently grounded | PASS | Test expectations derived from hand-verified calculations |
| No hardcoded reproductions of implementation | PASS | Tests verify specific numerical values known before seeing code |

---

## Numerical claims in final_rebuttal_openreview.md — verification

| Claim | Value | Verified against |
|-------|-------|-----------------|
| κ=0.758 (Round 2) | 0.758065 | adjudication_sensitivity.py |
| 44/50 agreement | 44 | adjudication_sensitivity.py |
| CI [0.517, 0.957] | ✓ | cluster bootstrap n=10,000 |
| McNemar (direction symmetry) p=0.219 | 0.219 | adjudication_sensitivity.py |
| Unique semantic all arms 74/74 | ✓ | item_scores.jsonl |
| F3-F0 exact unique = +64 | 64 | item_scores.jsonl |
| F0 stale-state 55% (23/42) | 23/42=54.8% | item_scores.jsonl |
| F1 stale-state 40% (17/42) | 17/42=40.5% | item_scores.jsonl |
| F2 stale-state 5% (2/42) | 2/42=4.8% | item_scores.jsonl |
| F3 stale-state 17% (7/42) | 7/42=16.7% | item_scores.jsonl |
| F1 vs F2 McNemar p<0.001 | p<0.0001 | Computed above |
| World-level exact sign test | 10/10 non-tied worlds favor F2; 2 ties; one-sided p=0.00098 | `final_statistical_audit.md` |
| B1-nodoc F2=96.6%, F3=94.0% | 112/116, 109/116 | item_scores.jsonl |
| F2 vs F3 McNemar p=0.508 | 0.508 | item_scores.jsonl |
| RD=+2.6pp [−2.5, +7.6] | +0.026 [−0.025, +0.076] | item_scores.jsonl |
| 20 spurious F2 doc credits | 20 | item_scores.jsonl |
| 34 doc items all S2 | 34 | evidence_packs.jsonl |
| Leakage 26/26 PASS | ✓ | forensic/FORENSIC_AUDIT.md |

---

## Remaining unresolved issues

### Block submission

| Issue | Status | Notes |
|-------|--------|-------|
| 6 discordant adjudications | UNRESOLVED — does NOT block | None affect mechanical scores |
| Revised manuscript not prepared | PENDING — blocks camera-ready | Rebuttal can be submitted; manuscript revision required for camera-ready |

### Non-blocking (must be disclosed)

| Issue | Status |
|-------|--------|
| Single LLM in H4 study | Disclosed in limitations |
| F1/F2 post-result ablations | Disclosed |
| Mechanism of stale-state reduction undetermined | Disclosed |
| CEO/own asymmetry in F1 | Disclosed |
| BCR=0 not surprising at Acc=0.185 | Disclosed |
| World-level clustering in stale-state CI | Disclosed |

---

## GO / NO-GO recommendation

**CONDITIONAL GO** for rebuttal submission to OpenReview.

**Conditions met:**
- Every numerical claim in final_rebuttal_openreview.md is independently reproducible
- All material limitations are disclosed
- No unsupported significance claims
- No anonymity violations
- 66 tests pass

**Conditions for camera-ready (not blocking rebuttal):**
1. Revised manuscript with 20 REQUIRED changes from final_manuscript_changes.md
2. Resolution of 6 discordant adjudications (third annotator)
3. Manuscript tables updated with B1-nodoc as primary metric
4. Appendix X: "any documented event" convention sensitivity

**What was NOT claimed:**
- F3 semantic superiority ✗ removed
- BCR=0 proves absence of world model ✗ removed
- F1/F2 as pre-registered ✗ corrected
- Causal temporal reasoning ✗ stated as association only
- F2 ≡ F3 (equivalence) ✗ stated as "no significant difference"

**Word count note:** `final_rebuttal_openreview.md` is approximately 900 words. ICLR 2027 rebuttal limits are unverified. If the limit is per-reviewer (typical in recent years: ~1000 words each), split the unified response into three files using `final_reviewer_a.md` and `final_reviewer_b.md` as the per-reviewer sections. If the limit is total (~1000 words), the current unified version needs trimming by ~100 words.
