# Response to Reviewer vfz3

---

**RC1: Schema compliance versus genuine semantic improvement**

Your concern is confirmed by the data.

We applied a schema-agnostic semantic scorer (B1) to all 150 × 4 items. For the 74 uniquely specified questions — where the evidence pack contains exactly one candidate event — all four arms score 74/74 semantically. Exact-match scores range from 10/74 (F0) to 74/74 (F3). The semantic gap is exactly zero.

| Metric | F0 | F1 | F2 | F3 |
|--------|---:|---:|---:|---:|
| Exact-match (unique, n=74) | 10 | 74 | 12 | 74 |
| Semantic B1 (unique, n=74) | 74 | 74 | 74 | 74 |
| Semantic gap F3 − F0 | | | | **0** |

We revise the main result accordingly: "F3's exact-match advantage on uniquely specified questions is entirely attributable to output-format compliance; all arms retrieve the correct content under semantic scoring."

**RC2: Label instability between rounds**

Round 1 κ = 0.336 reflects a systematic rubric gap, not random noise. Reviewer A consistently used "ambiguous" where Reviewer B used "incorrect/correct" for multi-candidate questions (multiple valid events, no convention stated in the question). Round 2 adds Rule 8 (multi-candidate question without stated convention → ambiguous), producing κ = 0.758 (44/50 agreement; bootstrap CI [0.517, 0.957]; McNemar p = 0.219). The improvement is structural: a specific rubric ambiguity was identified and corrected.

The low Round 1 κ was itself a diagnostic finding — it revealed that multi-candidate items require explicit convention guidance. We now state the gold-standard convention explicitly in Section 3 of the revised manuscript: "For multi-candidate questions (CEO succession, ownership transfer), the gold answer uses the most recent event at world end-time. This convention is not stated in the question text."

Reviewer B shows documented intra-rater inconsistency across cases C22, C24, C29 (identical response content, different labels within the same session). This is disclosed in the supplementary materials. It does not affect any mechanical score.

Six discordant items remain unresolved pending independent adjudication. None affect the reported B1, B1-nodoc, or exact-match results, which derive from frozen model outputs and a deterministic scorer.

**RC3: M5 audit conclusion too narrow**

Agreed. The M5 audit tested whether wrapping transformations of F0 outputs matched F3's scores. It did not test whether a correct scalar timestamp answer to a "When?" question is semantically correct while failing the tuple contract. The semantic B1 scorer closes this gap. We revise M5's conclusion to: "The M5 audit rules out wrapping as the sole source of format gains; the semantic scorer (B1) tests the broader question and confirms that all arms answer unique questions correctly."
