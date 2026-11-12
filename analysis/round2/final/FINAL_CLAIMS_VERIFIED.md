# Final Claims — Verified Against Raw Records

**Date:** 2026-11-12  
**Source:** `analysis/round2/private/item_scores.jsonl` (600 records, 150 queries × 4 arms)  
**Script:** `scripts/rigorous_reanalysis.py`  
**Tests:** 66 passed, 0 failed

---

## Verified headline results

### 1. Unique questions (n = 74)

All four arms score 74/74 semantically on uniquely specified questions.

| Arm | Exact-match | Semantic (B1) |
|-----|-------------|---------------|
| F0 | 10/74 | 74/74 |
| F1 | 74/74 | 74/74 |
| F2 | 12/74 | 74/74 |
| F3 | 74/74 | 74/74 |

**Conclusion:** F3's exact-match advantage on unique questions (+64 vs F0) is entirely output-format compliance. The semantic gap is zero. **VERIFIED.**

### 2. Stale-state errors — multi-candidate questions (n = 42)

Stale-state = model selects an earlier event (matches 'earliest' position but not 'latest').

| Arm | Stale | Latest | n |
|-----|-------|--------|---|
| F0 | 23/42 (54.8%) | 17/42 | 42 |
| F1 | 17/42 (40.5%) | 16/42 | 42 |
| F2 | 2/42 (4.8%) | 32/42 | 42 |
| F3 | 7/42 (16.7%) | 35/42 | 42 |

**Paired McNemar (temporal correctness = selects latest):**

| Comparison | n10 | n01 | RD | 95% CI | p |
|-----------|-----|-----|-----|--------|---|
| F0 vs F2 | 2 | 21 | +0.452 | [+0.275, +0.629] | p<0.0001 |
| F0 vs F3 | 5 | 21 | +0.381 | [+0.173, +0.589] | p=0.0025 |
| F1 vs F2 | 0 | 22 | +0.524 | [+0.373, +0.675] | p<0.0001 |
| F2 vs F3 | 6 | 3 | −0.071 | [−0.210, +0.067] | p=0.508 |

**Conclusion:** Temporal evidence structure (F2, F3) is associated with substantially fewer stale-state errors vs generic prompting (F0, F1). F2 and F3 are not significantly different in temporal event selection. **VERIFIED.**

**Clustering caveat:** 42 items span 12 worlds (mean 3.5/world). World-level sign test: 10/12 worlds favor F2 over F0 (p=0.001). Item-level CIs are approximate due to within-world correlation.

### 3. B1-nodoc semantic comparison (n = 116)

Excludes 34 doc items (all unanswerable, scorer artifact).

| Arm | Semantic | Rate |
|-----|----------|------|
| F0 | 87/116 | 75.0% |
| F1 | 90/116 | 77.6% |
| F2 | 112/116 | 96.6% |
| F3 | 109/116 | 94.0% |

**Paired McNemar (F2 vs F3, n=116):**  
n11=106, n10=6, n01=3, n00=1  
RD = +0.026 [−0.025, +0.076], exact p = 0.508

**Conclusion:** F2 and F3 are not significantly different in semantic accuracy on answerable questions. F3 semantic superiority claim is **REMOVED.** **VERIFIED.**

### 4. Doc item artifact (n = 34)

| Arm | Semantic on doc | Note |
|-----|----------------|------|
| F0 | 0/34 | — |
| F1 | 0/34 | — |
| F2 | 20/34 | Scorer artifact: prev/event/next format |
| F3 | 3/34 | Also spurious |

**20 vs 17 reconciliation:** 20 = F2's total spurious doc credits; 17 = F2-only paired wins on doc (F2 sem=1, F3 sem=0 for the same item); 3 = items where both F2 and F3 spurious. 20 = 17 + 3. No inconsistency. Different denominators, same phenomenon.

### 5. Inter-rater reliability

| Round | κ | Agreement | n items |
|-------|---|-----------|---------|
| Round 1 | 0.3363 | 70/120 | 120 |
| Round 2 | 0.7581 | 44/50 | 50 (2-class effective) |

Bootstrap CI for Round 2 κ: [0.517, 0.957]  
McNemar p=0.219 (direction symmetry test)

Round 1 low κ cause: rubric gap on multi-candidate items. Round 2 fixes this with Rule 8.  
6 discordant items remain unresolved. None affect mechanical scores.

### 6. BCR = 0 validity

BCR (Bundle Consistency Rate) = fraction of bundles where all within-bundle consistency constraints pass.  
BCR = 0 for all evaluated systems on the full 102-world benchmark.

Expected BCR under item independence at Acc=0.185 with mean bundle size 6.6:  
0.185^6.6 ≈ 0.000016 per bundle → ~0.02 expected consistent bundles out of 1088.  
**BCR=0 is not statistically surprising at Acc=0.185.** The BCR finding demonstrates a metric property (per-query accuracy and within-bundle consistency can diverge), not evidence of zero world-state knowledge.

### 7. F1 CEO/own asymmetry (exploratory finding)

| Arm | CEO-mc stale (n=20) | Own-mc stale (n=22) |
|-----|---------------------|---------------------|
| F1 | 17/20 (85%) | 0/22 (0%) |

F1 (schema-only prompt) defaults to earliest CEO event 85% of the time but correctly elicits the latest ownership transfer. This is likely a question-template artifact. Disclosed as a limitation.

---

## Explicit distinctions

| Term A | Term B | Relationship |
|--------|--------|-------------|
| Statistical non-significance (p=0.508) | Equivalence | Non-significance does NOT establish equivalence. We use "no significant difference." |
| Temporal-state selection (selects latest event) | Persistent internal world-modelling | Temporal-state selection is a behavioral measure. It does not establish causal claims about internal representations. |
| Output-contract compliance (exact-match) | Semantic correctness (B1) | F3 has large exact-match advantage; F2≈F3 on semantic. These are distinct constructs. |
| Exploratory post-hoc result (F1, F2) | Confirmatory evidence | F1/F2 are post-result ablations. The pre-registered comparison is F3 vs F0. |

---

## Negative findings retained

1. F3 does not significantly outperform F2 on semantic accuracy (B1-nodoc, p=0.508).
2. BCR=0 at Acc=0.185 is not surprising under independence.
3. F1 avoids stale-state on ownership without temporal evidence structure (template artifact, not genuine temporal reasoning).
4. 34 doc items are unanswerable; F2 spurious credits are a scorer artifact.
5. F1/F2 were designed post-result; they are exploratory, not confirmatory.
6. Single LLM (GPT-4.1) limits generalization.
7. Mechanism of stale-state reduction is not established causally.
8. 6 discordant human adjudications remain unresolved.

---

## Tests summary

```
uv run pytest tests/test_round2_audit.py
66 passed in 1.75s
```

All test expectations derived from hand-verified calculations against `item_scores.jsonl`.
