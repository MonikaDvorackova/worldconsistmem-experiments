# Hypothesis Assessment — WorldConsistMem H4 LLM Reader Study

Generated: 2026-11-12  
Source: `analysis/round2/evidence_inventory.md`, `error_taxonomy.md`, `f2_f3_paired_analysis.md`

Hypotheses as stated in the paper/pre-registration. Assessed against the independent reanalysis.

---

## H1: BCR exposes consistency failures that per-query accuracy misses

**Status: SUPPORTED (main paper claim)**

**Evidence:** On the full benchmark (102 worlds, 7140 queries), all systems including H0 (LTKM, highest accuracy Acc=0.185) achieve BCR=0. This demonstrates that a system can achieve non-trivial per-query accuracy while being entirely inconsistent across related queries in the same bundle. The H4 study does not directly test H1; this is the paper's primary empirical contribution.

**Strength:** Strong. Direct empirical demonstration on a large benchmark. Not dependent on any secondary analysis choices.

---

## H2: Output format significantly affects measured performance

**Status: SUPPORTED**

**Evidence:** On unique questions (n=74), exact-match scores diverge dramatically across arms:
- F0: 10/74 (13.5%)
- F1: 74/74 (100%)
- F2: 12/74 (16.2%)
- F3: 74/74 (100%)

Under semantic scoring (B1), all arms score 74/74 (zero semantic errors on unique questions). The entire exact-match variation is output-format compliance. F1 and F3 enforce output format; F0 and F2 do not.

**Implication:** Exact-match benchmarks that require specific JSON schemas overestimate the performance gap between schema-enforcing and non-schema-enforcing prompts. This confounds format compliance with semantic understanding.

**Strength:** Strong. The semantic-vs-exact gap is a structural property of the benchmark, not a statistical result.

---

## H3: Temporal representation in the prompt reduces stale-state errors

**Status: SUPPORTED (moderate)**

**Evidence:** Multi-candidate stale-state errors (model selects earlier event instead of latest):
- F0 (no temporal structure): 23/42 stale-state errors (54.8%)
- F1 (schema-only, no temporal structure): 17/42 stale-state errors (40.5%)
- F2 (prev/event/next temporal structure): 2/42 stale-state errors (4.8%)
- F3 (bundled structured with temporal context): 7/42 stale-state errors (16.7%)

Both F2 and F3 include temporal context; both dramatically reduce stale-state errors. F2 reduces stale-state errors more than F3 (2 vs 7), though the difference is not statistically significant at n=42.

**Caveat:** F2 and F3 differ in multiple ways from F0/F1 (temporal context AND other prompt elements). The comparison is not a clean ablation. However, the direction is consistent: temporal context in the prompt is associated with dramatically fewer stale-state errors.

**Strength:** Moderate. Consistent direction across two independent implementations (F2 and F3), large effect size (54.8% → 4.8% for F2). Limited by sample size (n=42 mc items) and confounded design.

---

## H4: F3 (full structured bundle) achieves higher semantic accuracy than F2

**Status: CONTRADICTED**

**Evidence:**
- B1 (all items): F2=132/150 (88.0%), F3=113/150 (75.3%), Δ=+19 for F2
- B1-nodoc (non-doc items): F2=112/116 (96.6%), F3=109/116 (94.0%), Δ=+3 for F2
- McNemar test (non-doc): n01=6, n10=3, p=0.508

The apparent F2 advantage under B1 is driven by 17 spurious semantic credits on unanswerable doc items. After correcting, F2 and F3 are statistically indistinguishable.

**Note:** If H4 was formulated as "F3 ≥ F2 on exact-match," that is supported (109 vs 39). But exact-match conflates format compliance with semantic accuracy; the semantic accuracy comparison favors neither arm.

**Strength of contradiction:** Moderate. The corrected comparison (p=0.508) is non-significant, but n=116 and there is a 3-item numerical gap in F2's favor. The claim that F3 achieves "higher semantic accuracy" is not supported.

---

## H5: Schema-enforcing prompts improve overall accuracy vs non-schema prompts

**Status: PARTIALLY SUPPORTED (depends on metric)**

**Evidence:**
- Exact-match: F3 (109/150) >> F0 (13/150), F1 (90/150) >> F0
- Semantic B1-nodoc: F2 (112/116) ≈ F3 (109/116) > F1 (90/116) > F0 (87/116)

Schema enforcement (F1 vs F0) improves exact-match from 13 to 90 and semantic B1-nodoc from 87 to 90 (marginal). The main semantic improvement comes from temporal representation (F2, F3 vs F0, F1), not schema enforcement per se.

**Qualified conclusion:** Schema enforcement improves format compliance substantially; it modestly improves semantic accuracy because it incidentally enforces the temporal representation structure in F3.

---

## H6: Human inter-rater reliability at κ ≥ 0.70 (Round 2 target)

**Status: ACHIEVED (Round 2)**

**Evidence:**
- Round 1: κ=0.336 (120 items, 3-class). Below the target; prompted Round 2.
- Round 2: κ=0.758 (50 items, 2-class effective). Exceeds target.
  - Agreement: 44/50 (88.0%), Wilson CI [76.2%, 94.4%]
  - Cluster bootstrap CI for κ: [0.517, 0.957] (n=10,000 resamples, cluster by case)
  - McNemar p=0.219 (no systematic directional bias between reviewers)

**Caveat:** Round 2 evaluated a 50-item subset (20 questions × up to 3 responses). The revised rubric that focuses on binary correct/incorrect (treating "ambiguous" as incorrect) achieves κ=0.758. The κ figure should be interpreted in the context of the 50-item sample and the revised rubric.

---

## Overall picture

| Hypothesis | Status | Strength |
|-----------|--------|---------|
| H1: BCR exposes consistency failures | SUPPORTED | Strong |
| H2: Format affects measured performance | SUPPORTED | Strong |
| H3: Temporal representation reduces stale-state errors | SUPPORTED | Moderate |
| H4: F3 semantically superior to F2 | CONTRADICTED | Moderate |
| H5: Schema enforcing improves accuracy | PARTIALLY SUPPORTED | Weak to moderate |
| H6: Human κ ≥ 0.70 (Round 2) | ACHIEVED | Strong |

**The paper's primary contribution (H1) is well-supported and not affected by any of the H4 issues.** The H4 study's most defensible positive finding is H3 (temporal representation reduces stale-state errors). H4 also provides a clear methodological contribution: demonstrating that exact-match scoring conflates format compliance with semantic accuracy (H2).
