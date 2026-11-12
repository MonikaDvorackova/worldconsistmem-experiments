# Response to Reviewer vfz3 — Final

---

> **RC1: "The improvements may reflect schema compliance rather than genuine semantic improvement in world-state tracking."**

You are correct, and this concern is now fully confirmed by the data.

We applied a schema-agnostic semantic scorer (B1) to all 150×4 items. For 74 uniquely specified questions — where the evidence pack contains exactly one candidate event — all four arms score 74/74 semantically, while exact-match scores vary from 10/74 (F0) to 74/74 (F3). The semantic gap is exactly zero; the entire exact-match gap (+64 items for F3 vs F0) is output-format compliance.

| Metric | F0 | F1 | F2 | F3 |
|--------|---:|---:|---:|---:|
| Exact (unique, n=74) | 10 | 74 | 12 | 74 |
| Semantic (unique, n=74) | 74 | 74 | 74 | 74 |
| Semantic gap F3−F0 | | | | **0** |

**Manuscript revision:** We revise the main result claim to: "F3's exact-match advantage on uniquely specified questions is entirely attributable to output-format compliance; all arms retrieve the correct content under semantic scoring."

> **RC2: "Label instability between rounds raises questions about annotation validity."**

Round 1 κ=0.336 reflects a systematic rubric gap, not random noise: reviewer A used "ambiguous" where reviewer B used "incorrect/correct" for multi-candidate items (multiple valid events, convention unstated). The Round 2 protocol adds Rule 8 (multi-candidate without stated convention → ambiguous), producing κ=0.758 (44/50 agreement; bootstrap CI [0.517, 0.957]; McNemar p=0.219). The inter-rater reliability improvement is structural: a rubric ambiguity was identified and corrected.

The low Round 1 κ was itself a diagnostic finding — it revealed that multi-candidate items require explicit convention guidance. We now state the gold-standard convention explicitly (Section 3 revision).

Reviewer B shows documented intra-rater inconsistency across cases C22, C24, C29 (same answer content, different labels within the same case). This is disclosed in the supplementary materials. It does not affect any mechanical score; it confirms that multi-candidate questions are genuinely difficult without a stated convention.

The 6 discordant items remain unresolved pending independent adjudication. None affect the reported B1/B1-nodoc/exact-match results, which derive from frozen model outputs and a deterministic scorer, not from human reviewer labels.

> **RC3: "The M5 audit conclusion ('0 format-only wins') is too narrow."**

Agreed. The M5 audit tested whether wrapping transformations of F0 outputs matched F3's scores — it did not test whether a correct scalar timestamp answer to a "When?" question is penalized for missing the "from" and "role" fields that the question did not ask for. The semantic B1 scorer now closes this gap. We revise M5's conclusion to: "The M5 audit rules out wrapping as the sole explanation; the semantic scorer (B1) tests the broader question and confirms that all arms answer unique questions correctly."
