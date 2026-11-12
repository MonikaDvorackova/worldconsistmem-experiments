# Final Independent Statistical Audit — WorldConsistMem Round 2

**Date:** 2026-11-12  
**Status:** COMPLETE  
**Auditor role:** Independent verification pass, not a new research cycle  
**Script:** `scripts/rigorous_reanalysis.py` + inline Python (see commit)  
**Data sources:** `analysis/round2/private/item_scores.jsonl` only

All numerical claims below were computed from raw item records, not from prior Markdown summaries.

---

## A. Unique questions

**Claim:** n=74, all arms 74/74 semantic, F3−F0 exact=+64, semantic diff=0.

| Arm | Exact | Semantic |
|-----|------:|--------:|
| F0 | 10/74 | 74/74 |
| F1 | 74/74 | 74/74 |
| F2 | 12/74 | 74/74 |
| F3 | 74/74 | 74/74 |

**VERIFIED.** Zero semantic failures on unique questions for any arm. All 74 unique questions present across all 4 arms. F3−F0 exact = +64. F3−F0 semantic = 0.

**Interpretation:** The exact-match gap on unique questions is entirely output-contract compliance. F0 and F2 produce correct answer content but in a format that doesn't match the required JSON schema. F1 and F3 enforce the schema and get exact credit.

**Scoring note:** F0 exact=10 (not 0) because CEO-unique items happen to elicit correct JSON tuples from F0. F2 exact=12 because CEO-unique and 2 own-unique items match. All other exact-match differences on unique questions are schema compliance only.

---

## B. Temporal stale-state errors

**Definition:** A stale-state error occurs when `matched_positions` contains `'earliest'` but NOT `'latest'`. Items with both positions are classified as MC_INCOMPLETE (conservative — does not inflate any arm's stale count).

| Arm | Stale/42 | Rate | Latest/42 | MC_incomplete |
|-----|--------:|-----:|--------:|-------------:|
| F0 | 23 | 54.8% | 19 | 6 (both latest+earliest) |
| F1 | 17 | 40.5% | 16 | 9 |
| F2 | 2 | 4.8% | 38 | 2 |
| F3 | 7 | 16.7% | 35 | 0 |

**VERIFIED.**

### Paired McNemar test (item-level, temporal correctness = selects latest)

| Comparison | Discordant | RD | 95% CI | McNemar p |
|-----------|-----------|----|---------:|----------|
| F2 wins, F0 wins | 21, 2 | +0.452 | [+0.275, +0.629] | 0.0001 |
| F3 wins, F0 wins | 21, 5 | +0.381 | [+0.173, +0.589] | 0.0025 |
| F2 wins, F1 wins | 22, 0 | +0.524 | [+0.373, +0.675] | <0.0001 |
| F3 wins, F2 wins | 3, 6 | −0.071 | [−0.210, +0.067] | 0.508 |

**Clustering caveat:** 42 items span 12 worlds (mean 3.5 items/world). Item-level McNemar treats items as independent, which is approximate. World-level sign test: F2 has fewer stale than F0 in 10/12 non-tied worlds, more in 0/12 (sign test p=0.001 one-sided). The item-level direction is robust but confidence intervals should be interpreted with awareness of within-world correlation.

### Slot-level asymmetry (critical finding)

| Arm | CEO-mc (n=20) stale | Own-mc (n=22) stale |
|-----|-------------------:|-------------------:|
| F0 | 11/20 (55%) | 12/22 (55%) |
| F1 | 17/20 (85%) | 0/22 (0%) |
| F2 | 2/20 (10%) | 0/22 (0%) |
| F3 | 7/20 (35%) | 0/22 (0%) |

**F1 asymmetry:** F1 (schema-only, no temporal representation) selects the latest ownership transfer for 16/22 own-mc items (73%) but selects the EARLIEST CEO change for 17/20 CEO-mc items (85%). The schema-only prompt appears to reliably elicit the earliest CEO event while happening to elicit the latest ownership event. This is likely a question-template effect, not a temporal reasoning effect.

**Implication:** The F2 vs F1 improvement on stale-state is driven entirely by CEO questions. For ownership questions, F1 (schema-only) already performs comparably to F2. The claim "temporal representation reduces stale-state errors" is accurate but its mechanism is confounded by question-template effects on F1.

### World-level F3 stale analysis

F3's 7 stale-state errors are all CEO-mc items. 5 of 7 are in worlds sm0135–sm0138, the same worlds where F2 excels. In world sm0138, F2 selects latest for both CEO organizations (ceo:0 and ceo:7), while F3 selects earliest for ceo:0 and ceo:7. The within-world correlation means the F2 vs F3 difference on CEO-mc (6 vs 3 discordant items) comes from only 4 effective worlds, not 6 independent items.

---

## C. F2 vs F3 semantic correctness (non-doc)

**Claim:** F2=112/116, F3=109/116, McNemar p=0.508.

| Arm | Semantic (B1-nodoc) | Rate |
|-----|-------------------:|-----:|
| F0 | 87/116 | 75.0% |
| F1 | 90/116 | 77.6% |
| F2 | 112/116 | 96.6% |
| F3 | 109/116 | 94.0% |

Paired table (n=116): both=106, F2-only=6, F3-only=3, neither=1.

RD(F2−F3) = +0.026 [−0.025, +0.076], McNemar p = 0.508.

**VERIFIED.**

**Correct phrasing:** "The available evidence does not establish a semantic accuracy difference between F2 and F3." F3 has 3 items where F2 picks 'middle' position (3-event CEO sequences), which is semantically wrong. F2 has 6 items where F3 picks 'earliest' in CEO-mc. Both effects are small, inconsistent in direction, and non-significant.

---

## D. Document artifact reconciliation

**Two numbers reported:**
- 20: Total F2 spurious semantic credits on doc items (all 34 doc items are S2 insufficient evidence)
- 17: F2-only paired wins over F3 on doc items (F2 sem=1, F3 sem=0 on the same doc item)

**Reconciliation:**

| Doc item pairs | Count |
|----------------|------:|
| Both F2 and F3 spurious | 3 |
| F2 spurious, F3 not (F2-only) | 17 |
| F3 spurious, F2 not (F3-only) | 1 |
| Neither spurious | 13 |
| **Total doc** | **34** |

**20 = 17 (F2-only) + 3 (both)**. These are different denominators counting the same phenomenon: 20 is F2's total spurious credits; 17 is the net F2-over-F3 advantage attributable solely to doc artifacts in paired analysis.

There is no inconsistency. Both numbers must be reported with their denominators.

**F0 and F3 each have 4 spurious doc credits. F1 has 0.** The F2 artifact (20) is specifically caused by the prev/event/next structure exposing timestamps that coincidentally match the gold "time" field.

---

## E. BCR=0 — validity and limitations

**Definition:** BCR (Bundle Consistency Rate) = fraction of bundles where all within-bundle consistency constraints pass. From `src/worldconsistmem/metrics.py`: a bundle is "consistent" when `bundle_is_consistent(results)` returns True, where constraints check semantic coherence across related queries.

**Result:** BCR=0 for all systems (B1, B3, B4, H0) on the full 102-world benchmark. H0 achieves Acc=0.185 with BCR=0.

**Is BCR=0 surprising?**  
With Acc=0.185 and mean bundle size ~6.6 queries, the probability of a randomly-correct bundle under independent queries ≈ 0.185^6.6 ≈ 0.000016. Expected number of consistent bundles: 1088 × 0.000016 ≈ 0.02. So BCR=0 at this accuracy level is **not statistically surprising** under an independence model.

**What BCR=0 does and does not mean:**
- BCR=0 is consistent with both: (a) no coherent internal world model, and (b) a partial world model that correctly answers some queries in each bundle but fails at least one constraint.
- BCR=0 does NOT prove the absence of an internal world model.
- BCR=0 is meaningful as a **benchmark property demonstration**: even the strongest evaluated system fails to satisfy full within-bundle consistency, which accuracy alone would not reveal.

**Correct claim:** "The BCR metric reveals that no evaluated system achieves full within-bundle consistency, despite non-trivial per-query accuracy. The gap between mean query accuracy (18.5% for H0) and BCR (0%) illustrates the distinction between getting individual questions right and maintaining consistent answers about the same entity across related queries."

---

## F. Error taxonomy audit

**Circularity check:** The `classify_error()` function in `scripts/rigorous_reanalysis.py` applies categories in priority order (CORRECT → FORMAT_ONLY → STALE_STATE → MC_INCOMPLETE → INSUF_EV). No category depends on arm identity. F0's "both" items (6 items with both latest+earliest positions) are classified as MC_INCOMPLETE rather than STALE_STATE — this is conservative and slightly understates F0's temporal failures. The taxonomy does not favor any arm.

**Mutual exclusivity:** Categories are mutually exclusive by construction. INSUF_EV_SPURIOUS takes precedence for doc items regardless of other flags.

**Ambiguous item handling:** The 25 jointly-ambiguous items from human evaluation are on mc questions. Under the taxonomy, these items are scored mechanically (by matched positions), not by human label. This is correct: the mechanical taxonomy does not change raw human labels.

**Classification counts verified:**

| Error | F0 | F1 | F2 | F3 | Sum F0 | Sum F3 |
|-------|---:|---:|---:|---:|-------:|-------:|
| CORRECT | 13 | 90 | 39 | 109 | | |
| FORMAT_ONLY | 74 | 0 | 73 | 0 | | |
| STALE_STATE | 23 | 17 | 2 | 7 | | |
| MC_INCOMPLETE | 6 | 9 | 2 | 0 | | |
| INSUF_EV_FAIL | 30 | 34 | 14 | 30 | | |
| INSUF_EV_SPURIOUS | 4 | 0 | 20 | 4 | | |
| **Total** | **150** | **150** | **150** | **150** | | |

All rows sum to 150. ✓

---

## G. Causal interpretation assessment

**Claim under assessment:** "Explicit temporal representation is associated with fewer stale-state errors."

**What the design actually manipulates:**

| Comparison | What changes | What stays constant |
|-----------|-------------|-------------------|
| F0 vs F1 | Output schema | No temporal structure |
| F0 vs F2 | Evidence format (prev/event/next) + output format | — |
| F0 vs F3 | Full bundle structure | — |
| F1 vs F2 | Evidence format (prev/event/next) | Schema enforced |
| F1 vs F3 | Full bundle structure | Schema enforced |
| F2 vs F3 | Output format enforcement | Temporal structure present |

**Closest ablation for temporal representation:** F2 vs F1 (both schema-enforced, F2 adds prev/event/next evidence structure). But F2 vs F1 also changes the evidence presentation format and prompt length.

**Alternative explanations for the stale-state reduction:**
1. **Question-template effect on F1:** F1 CEO-mc stale=85% while F1 own-mc stale=0%. The F1 prompt template for CEO questions may default to the earliest event in the evidence sequence regardless of temporal representation. This is a template artifact, not proof that temporal representation is needed for ownership questions.
2. **Evidence-order effect:** The prev/event/next format in F2 explicitly positions the most recent event last (or as "event"). This may help the model identify recency through positional cues rather than temporal understanding.
3. **Context length effects:** F2 provides shorter, structured context vs. F1's flat evidence list. Shorter context may reduce primacy/recency bias artifacts.

**What can be defensibly claimed:**
- "Including a temporal sequential representation of evidence (prev/event/next format or full structured bundle) is associated with substantially fewer stale-state CEO errors (F2: 10%, F3: 35% vs F1: 85%, F0: 55%)."
- "The association holds at the world level (10 of 12 non-tied worlds show fewer F2 stale errors than F0)."

**What cannot be claimed:**
- "F2/F3 demonstrate temporal world-state reasoning." The experiment doesn't distinguish temporal understanding from positional-cue exploitation.
- "Temporal representation is causally necessary for avoiding stale-state errors." F1 avoids stale-state errors entirely on own-mc without temporal representation.

---

## Status summary

| Claim | Status | Note |
|-------|--------|------|
| n=74 unique, all arms 74/74 semantic | VERIFIED | ✓ |
| F3−F0 exact unique = +64, semantic = 0 | VERIFIED | ✓ |
| Stale-state: F0=23, F1=17, F2=2, F3=7 | VERIFIED | ✓ |
| F0 vs F2 McNemar (temporal) | NEW | RD=+0.452, p=0.0001 |
| F1 CEO-mc stale=17/20 (85%) | NEW FINDING | Asymmetry not in prior docs |
| F2 vs F3 semantic B1-nodoc p=0.508 | VERIFIED | ✓ |
| 20 vs 17 doc artifact reconciled | RESOLVED | Different denominators |
| BCR=0 caveat added | CORRECTED | Not surprising at Acc=0.185 |
| Taxonomy circularity | NONE FOUND | Conservative for F0 |
| Causal interpretation | QUALIFIED | Association, not causation |
