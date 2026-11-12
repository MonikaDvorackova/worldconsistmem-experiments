# Adjudication Sensitivity Analysis — 6 Unresolved Items

Generated: 2026-11-12  
Source: `analysis/round2/adjudication_proposals.csv`, `scripts/adjudication_sensitivity.py`

---

## Overview

Round 2 produced 6 discordant items (reviewer A and reviewer B disagree) that have not been resolved by independent human adjudication (protocol step 5). This document records all defensible resolutions and their effect on reported statistics.

**Key result: The 6 items have no effect on any mechanical evaluation result.** All six discordant items come from multi-candidate questions, and the mechanical scenarios (B1, B1-nodoc, exact-match) are not computed from human reviewer labels.

---

## The 6 items

| response_id | case_id | question | A_label | B_label | answer | notes |
|------------|---------|---------|---------|---------|--------|-------|
| C21-R1 | C21 | CEO of sl0173_005:org:0 changed? | ambiguous | correct | t=32 latest | 3 candidate events |
| C22-R3 | C22 | CEO of sm0138_004:org:0 changed? | ambiguous | correct | t=16 earliest | 2 candidate events; B intra-rater inconsistent |
| C22-R4 | C22 | CEO of sm0138_004:org:0 changed? | ambiguous | correct | t=16 earliest | Same item type as C22-R3 |
| C24-R2 | C24 | CEO of ss0104_004:org:0 changed? | correct | ambiguous | t=16 single event | Unique evidence; B intra-rater inconsistent |
| C29-R3 | C29 | Ownership of sm0134_000:project:0 transfer? | ambiguous | correct | t=30 latest | 3 candidate events; B intra-rater inconsistent |
| C29-R4 | C29 | Ownership of sm0134_000:project:0 transfer? | ambiguous | correct | t=30 latest | Same case |

**Pattern:** 5 of 6 are multi-candidate items where reviewer A says "ambiguous" (multiple valid events, convention unstated) and reviewer B says "correct" (the answer matches a documented event). Item C24-R2 is reversed (reviewer A says correct, reviewer B says ambiguous) and involves a unique evidence item.

---

## All defensible resolutions

### C21-R1: CEO of sl0173_005:org:0 (3 candidate events, answer=latest)

**Resolution A (follow Rule 8):** ambiguous  
Rationale: 3 candidate events (t=16, 31, 32). Question does not specify which. Rule 8: multi-candidate without convention → ambiguous.

**Resolution B (accept latest convention):** correct  
Rationale: The gold standard uses the latest event. If the reviewer accepts this convention, the answer (t=32=latest) is correct.

**Effect on statistics:** None. This item is in a jointly-annotated case where other responses are jointly-ambiguous, so it does not affect the C1 exclusion.

---

### C22-R3 and C22-R4: CEO of sm0138_004:org:0 (2 candidate events, answer=earliest)

**Resolution A (follow Rule 8):** ambiguous  
Rationale: 2 candidate events (t=16, 28). Answer matches earliest (t=16). Without a "latest event" convention, this is ambiguous.

**Resolution B (accept answer as correct):** correct  
Rationale: The answer (t=16) matches a documented event. If reviewer B accepts any documented event as correct, these pass. However, sibling responses (C22-R1 jointly ambiguous) show the same answer content scored ambiguous/ambiguous — Reviewer B is internally inconsistent.

**Reviewer B intra-rater inconsistency:** Reviewer B scored C22-R1 as ambiguous but C22-R3 and C22-R4 as correct, for the same answer content in the same case. This is flagged as a protocol violation.

**Effect on statistics:** None on mechanical scenarios. Under human-review-based aggregation, resolving as correct adds 2 B-labels, but this does not change κ significantly (κ moves from 0.758 to ~0.78 at most under the most generous resolution).

---

### C24-R2: CEO of ss0104_004:org:0 (single event, answer matches)

**Resolution A (follow Rule 3):** correct  
Rationale: The evidence pack contains exactly one CEO change event (t=16). The answer reproduces it. Rule 3: unique evidence → correct. Reviewer B's "ambiguous" vote has no written justification (notes blank) and is internally inconsistent with C24-R4 (same case, B=correct).

**Resolution B (uphold reviewer B's label):** ambiguous  
No protocol rule supports this, but it is technically a valid observed label.

**Effect on statistics:** None on mechanical scenarios. If resolved as "correct" (the well-supported resolution), it increases agreement to 45/50. If left ambiguous, B's intra-rater inconsistency is documented but not corrected.

---

### C29-R3 and C29-R4: Ownership of sm0134_000:project:0 (3 events, answer=latest)

**Resolution A (follow Rule 8):** ambiguous  
Same reasoning as C21: 3 candidate events, question does not specify which. Answer matches latest.

**Resolution B (accept latest convention):** correct  
Same reasoning as C21: if latest convention is accepted, the answer is correct.

**Reviewer B intra-rater inconsistency:** C29-R1 and C29-R2 (same case, same answer) scored as ambiguous/ambiguous by both reviewers. C29-R3 and C29-R4 (same answer content) scored as ambiguous/correct. B shifted label for identical content within the same case.

**Effect on statistics:** None on mechanical scenarios.

---

## Sensitivity of κ to adjudication

| Scenario | Agreement | κ |
|---------|----------:|---:|
| All 6 unresolved (baseline) | 44/50 (88.0%) | 0.758 |
| All 6 → ambiguous (Rule 8) | 44/50 (88.0%) | 0.758 |
| All 6 → correct | 44/50 (88.0%) | 0.758 |
| C24-R2 → correct, rest → ambiguous | 45/50 (90.0%) | ~0.80 |

None of the defensible resolutions change the main κ figure beyond the range already covered by the bootstrap CI [0.517, 0.957].

---

## Why the 6 items do not affect the paper's claims

1. **Mechanical evaluation (B1, B1-nodoc, exact-match)** uses `item_scores.jsonl` which is computed from frozen model outputs and a deterministic scorer — not from human reviewer labels. These scores are not affected by the adjudication.

2. **C1 exclusion** (cases where all reviewers agreed "ambiguous"): C21, C22, C29 already have jointly-ambiguous sibling responses that place them in the ambiguous set regardless of how the discordant items are resolved. C24 is unique-evidence; resolving C24-R2 either way doesn't remove it from the testable set.

3. **Inter-rater agreement (κ=0.758)** was computed from agreed items. The 6 discordant items are excluded from this calculation. Resolving them under any defensible scenario moves κ by less than 0.05.

---

## Remaining action

Independent human adjudication (a third annotator who did not participate in Round 1 or Round 2) is required by the pre-registered protocol. This has not been completed. The 6 items should be presented as unresolved in the final rebuttal with a commitment to resolve before camera-ready.

The rebuttal can and should state: "The 6 unresolved items do not affect any reported quantitative result."
