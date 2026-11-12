# Response to Reviewer vfz3

---

> **RC1:** "The improvements in F3 may reflect schema compliance rather than genuine semantic improvements in world-state tracking. The evaluation should separate these two effects."

**Short answer:** You are correct. We confirm and quantify this. On questions where the answer is unambiguous (n=74 unique questions), the exact-match gap between F3 and F0 is +64 items; the semantic gap is 0.

**Detailed response:**

We completed a semantic scorer (B1) that extracts answer content from raw model outputs without requiring a specific JSON format. The scorer was applied to all 150 × 4 = 600 items.

On 74 uniquely specified questions (evidence pack contains exactly one candidate event):
- Exact-match: F0=10, F1=74, F2=12, F3=74
- Semantic B1: F0=74, F1=74, F2=74, F3=74 (all arms, 100%)
- Semantic gap F3−F0: **zero**

The entire exact-match advantage of F3 and F1 over F0 and F2 on unique questions is output-format compliance — the model correctly identifies the answer content regardless of arm, but only F1 and F3 produce it in the required JSON schema.

On 42 multi-candidate questions, schema compliance and temporal accuracy are entangled. See RC2.

> **RC2:** "For multi-candidate questions, it is unclear whether the model is demonstrating temporal understanding or simply following a 'latest event' heuristic from the prompt structure."

**Short answer:** The distinction between "temporal understanding" and "latest event heuristic" is philosophically debatable but empirically tractable. We can show that temporal representation in the prompt reduces stale-state errors.

**Detailed response:**

For 42 multi-candidate questions, we classify errors as STALE_STATE (model selected an earlier event) or other. Results:

| Arm | Stale-state errors | Selects latest |
|-----|------------------:|--------------:|
| F0 (no temporal context) | 23/42 (54.8%) | 19/42 (45.2%) |
| F1 (schema-only, no temporal context) | 17/42 (40.5%) | 16/42 (38.1%) |
| F2 (prev/event/next temporal structure) | 2/42 (4.8%) | 38/42 (90.5%) |
| F3 (bundled structured with temporal context) | 7/42 (16.7%) | 35/42 (83.3%) |

The difference between F0/F1 (no temporal context) and F2/F3 (with temporal context) is large and consistent. Whether this reflects "temporal understanding" or "heuristic from prompt structure" is a framing question; the empirical claim is that including explicit temporal structure in the prompt causes the model to select the current-state event rather than a historical one.

We acknowledge that the multi-candidate benchmark design contains a limitation: the question text does not explicitly state "most recent event," and the gold standard uses the latest event as an implicit convention. We disclose this convention, add it to the benchmark documentation, and report results under both the "latest event" and "any documented event" conventions. Under the "any documented event" convention, all responses that match any documented event are correct; under this convention F0 and F1 perform similarly to F2/F3.

> **RC3:** "Label instability between rounds raises questions about the validity of the annotation procedure."

**Short answer:** Round 1 κ=0.336 was caused by rubric ambiguity in the multi-candidate case; Round 2 addressed this with a revised rubric and achieved κ=0.758.

**Detailed response:**

Round 1 evaluated 120 items with a 3-class rubric (correct/incorrect/ambiguous). κ=0.336 reflects systematic disagreement on multi-candidate items: reviewer A consistently rated "ambiguous" while reviewer B rated "correct" or "incorrect" for the same items. This is not random noise — it identifies a genuine rubric gap.

Round 2 addressed this by:
1. Adding explicit Rule 8 (multi-candidate without stated convention → ambiguous)
2. Focusing evaluation on 50 items drawn to include multi-candidate cases
3. Computing κ from 2-class effective labels (correct vs. not)

Round 2: κ=0.758 (44/50 agreement, cluster bootstrap CI [0.517, 0.957], McNemar p=0.219 for direction symmetry). The wide bootstrap CI reflects the 50-item sample size, not an ambiguity in the labels themselves.

We document 6 discordant items (C21, C22, C24, C29) that remain unresolved. These have no effect on any mechanical evaluation result (B1/B1-nodoc/exact-match are computed from frozen model outputs, not human labels). We commit to resolving them via independent adjudication before camera-ready.

The annotation procedure is valid for its stated purpose: establishing that the benchmark rubric can be applied reliably (κ≥0.70) on the question types that appear in the evaluation. The low Round 1 κ was itself a diagnostic finding that led to the rubric improvement.
