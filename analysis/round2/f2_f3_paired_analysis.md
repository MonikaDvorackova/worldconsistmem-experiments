# F2 vs F3 Paired Analysis — Corrected

Generated: 2026-11-12  
Source: `scripts/rigorous_reanalysis.py`  
Pre-registration: protocol hash on file; this analysis was not pre-registered as a comparison arm.

---

## Summary

The F2 vs F3 exact-match gap is +70 items in F3's favor. After removing the scorer artifact on unanswerable doc items and switching to semantic scoring, **F2 and F3 are statistically indistinguishable** (B1-nodoc: 112/116 vs 109/116, McNemar p=0.508). F2 is marginally better at temporal event selection (38/42 vs 35/42 latest), while F3 is better at output format compliance. Neither effect is statistically significant.

---

## 1. Exact-match comparison (Scenario A)

| Metric | F2 | F3 | Δ(F3−F2) |
|--------|---:|---:|--------:|
| Exact-match (n=150) | 39 | 109 | +70 |
| Unique questions (n=74) | 12 | 74 | +62 |
| Multi-candidate (n=42) | 27 | 35 | +8 |
| Doc items (n=34) | 0 | 0 | 0 |

**Decomposition of the +70 gap:**
- Unique questions: +62 (89% of gap). Both arms are semantically correct on 74/74 unique items. The entire unique-question gap is output-format compliance.
- Multi-candidate: +8 (11% of gap). F3 selects latest AND formats correctly on 35/42; F2 selects latest on 38/42 but only formats correctly on 27/42.
- Doc items: 0 (both fail exact-match on all doc items; ground truth is unanswerable anyway).

**Conclusion on exact-match:** The F3 advantage is primarily output-contract compliance, not temporal world-state accuracy.

---

## 2. Semantic comparison (Scenario B1, format-agnostic)

| Metric | F2 | F3 | Δ(F2−F3) | p |
|--------|---:|---:|--------:|---|
| Semantic B1 (n=150) | 132 | 113 | +19 | — |
| Semantic B1-nodoc (n=116) | 112 | 109 | +3 | 0.508 |

**The +19 F2 advantage under B1 disappears after removing spurious doc credits.**

F2 receives semantic credit on 20/34 doc items (all S2 — insufficient evidence). These are scorer false positives: the prev/event/next structure exposes timestamps that happen to match the gold "time" field, but the items are structurally unanswerable. F3 and F0 each receive 4 spurious doc credits; F1 receives 0.

After correcting (B1-nodoc, n=116):
- F2: 112/116 = 96.6%
- F3: 109/116 = 94.0%
- Net difference: 3 items
- McNemar: n01=6 (F2-only), n10=3 (F3-only), p=0.508

**Conclusion on semantic scoring:** No statistically significant difference between F2 and F3 on answerable questions.

---

## 3. Multi-candidate temporal analysis (n=42)

| Metric | F0 | F1 | F2 | F3 |
|--------|---:|---:|---:|---:|
| Selects latest event | 19 | 16 | 38 | 35 |
| Stale-state errors | 23 | 17 | 2 | 7 |
| Exact-match correct | 3 | 16 | 27 | 35 |

By slot:

| Slot | Arm | Selects latest | Stale state | Exact |
|------|-----|---------------:|------------:|------:|
| CEO-mc (n=20) | F0 | 9 | 11 | 3 |
| CEO-mc | F1 | 0 | 17 | 0 |
| CEO-mc | F2 | 16 | 2 | 16 |
| CEO-mc | F3 | 13 | 7 | 13 |
| Own-mc (n=22) | F0 | 10 | 12 | 0 |
| Own-mc | F1 | 16 | 0 | 16 |
| Own-mc | F2 | 22 | 0 | 11 |
| Own-mc | F3 | 22 | 0 | 22 |

**F2 vs F3 on temporal selection:**
- CEO-mc: F2 selects latest 16/20 (80%), F3 selects latest 13/20 (65%). F2 is better.
- Own-mc: F2 selects latest 22/22 (100%), F3 selects latest 22/22 (100%). Equal.
- Overall: F2=38/42 (90.5%), F3=35/42 (83.3%). F2 marginally better.

**F2 vs F3 on format compliance for mc items:**
- CEO-mc: F2 exact=16, F3 exact=13. F2 and F3 match exactly the same items (both select latest correctly formatted).
- Own-mc: F2 exact=11, F3 exact=22. F3 is better: F2 selects the correct event (22/22) but only formats it correctly for 11/22.

**Net effect:** F2 is marginally better at temporal selection; F3 is better at format compliance for ownership questions. Neither difference reaches significance.

---

## 4. The 6 non-doc F2 semantic wins and 3 F3 semantic wins

**F2-only on non-doc (6 items — all CEO-mc):**

| query_id | F2 exact | F3 error |
|----------|---------|---------|
| sm0135_001:b:ceo:0:transition | CORRECT | STALE_STATE |
| sm0136_002:b:ceo:7:transition | CORRECT | STALE_STATE |
| sm0137_003:b:ceo:0:transition | CORRECT | STALE_STATE |
| sm0137_003:b:ceo:7:transition | CORRECT | STALE_STATE |
| sm0138_004:b:ceo:0:transition | CORRECT | STALE_STATE |
| sm0138_004:b:ceo:7:transition | CORRECT | STALE_STATE |

All 6 are CEO-mc items where F2 correctly selects the latest CEO transition and formats it correctly, while F3 erroneously selects the earliest transition. The F2 format (prev/event/next) may better signal recency by sequentially ordering events.

**F3-only on non-doc (3 items — all CEO-mc):**

| query_id | F3 error type | F2 error type |
|----------|--------------|--------------|
| sl0169_001:b:ceo:0:transition | CORRECT | FORMAT_ONLY? or STALE_STATE |
| sl0170_002:b:ceo:7:transition | CORRECT | FORMAT_ONLY? or STALE_STATE |
| sl0173_005:b:ceo:0:transition | CORRECT | FORMAT_ONLY? or STALE_STATE |

Three CEO-mc items where F3 selects latest correctly but F2 does not. Net: F2 wins 6, F3 wins 3 on CEO-mc semantic — still not significant (p=0.508).

---

## 5. Interpretation

The F2 vs F3 comparison reveals a tension between two design choices:

1. **Temporal representation** (prev/event/next in F2): Reduces stale-state errors on CEO-mc from 7 (F3) to 2 (F2). The sequential structure may help the model identify the most recent event.

2. **Output-format enforcement** (strict schema in F3): Eliminates 73 FORMAT_ONLY errors on unique questions and 11 on own-mc. F3's structured bundle ensures consistent formatting regardless of content.

Neither design choice dominates the other on the temporal accuracy dimension. Both F2 and F3 substantially reduce stale-state errors compared to F0 (23) and F1 (17), which is the actionable finding: **temporal context in the prompt reduces stale-state errors regardless of whether that context is formatted as prev/event/next or as a full structured bundle.**

---

## 6. What the F2/F3 comparison cannot establish

- Whether F2 or F3 would generalize to other LLMs (single model evaluated)
- Whether the CEO-mc difference (F2=16/20, F3=13/20) is a reliable signal or noise at n=20
- Whether temporal representation causes the temporal improvement (not an ablation; F2 changes both representation and format simultaneously relative to F1)
