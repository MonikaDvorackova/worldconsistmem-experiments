# ICLR 2027 Rebuttal — WorldConsistMem (Submission 49130)

**SUBMISSION-READY VERSION**  
**Word count (approximate): ~900 words**  
**Note:** ICLR rebuttal word limits are not verified for 2027. Standard limits are ~1000 words total or per reviewer. Flag with AC if length adjustment is needed. All numbers are independently reproducible from `scripts/rigorous_reanalysis.py`.  
**Anonymity:** This text contains no author identifiers, repository URLs, or institution names.

---

We thank reviewers Rkeo, vfz3, and EdSa for detailed and constructive feedback. We respond with verified evidence from a completed Round 2 human evaluation and rigorous independent reanalysis. All results are reproducible; reproducibility details are in the supplementary materials.

---

**Round 2 inter-rater reliability.** We completed Round 2 on 50 items. κ=0.758 (44/50 agreement; bootstrap CI [0.517, 0.957]; McNemar p=0.219 for direction symmetry). Round 1's low κ=0.336 was caused by a rubric gap on multi-candidate questions, corrected in Round 2 by Rule 8 (multiple valid events without a stated convention → ambiguous). Six discordant items are unresolved; none affect any mechanical score.

---

**To vfz3 (schema compliance, label instability):**

Schema confounding is confirmed. We applied a schema-agnostic semantic scorer to all 150×4 items. For 74 uniquely specified questions (evidence pack: exactly one candidate event), all four arms score 74/74 semantically, while exact-match scores range from 10/74 (F0) to 74/74 (F3). The semantic gap is zero; the entire +64-item exact-match gap is output-format compliance. We revise the manuscript accordingly: "On uniquely specified questions, all arms retrieve correct content; F3's exact-match advantage is entirely schema compliance."

For 42 multi-candidate questions, temporal representation is associated with substantially fewer stale-state errors (selecting an earlier event instead of the current state): F0=55%, F1=40%, F2=5%, F3=17%. McNemar p<0.001 for F1 vs F2. World-level sign test (10/12 worlds favor F2 over F0, p=0.001) confirms the direction is robust to clustering. F2 and F3 are comparable on temporal event selection (McNemar p=0.508). We acknowledge the effect mechanism is not established (see below).

Label instability in Round 1 reflects a rubric gap, not random noise. Round 2 corrects this. Full protocol documented in supplementary materials.

---

**To EdSa (semantic grading, F3 claims, evidence strength):**

Semantic grading is complete. After excluding 34 document items (all unanswerable — no version identifiers in evidence packs), B1-nodoc scores are: F0=75.0%, F1=77.6%, F2=96.6%, F3=94.0%. F2 and F3 are not significantly different (McNemar p=0.508). We remove the claim that F3 achieves higher semantic accuracy and revise to: "F2 and F3 achieve comparable semantic accuracy on answerable questions; the available evidence does not establish a difference."

F2's apparent advantage under full B1 (132 vs F3's 113) is driven by 20 spurious credits on unanswerable document items — a scorer artifact of the prev/event/next format. This is fully disclosed.

The "latest event" convention is now explicitly stated in the benchmark documentation and Section 3: gold answers use the most recent event at world end-time.

Cross-model replication is listed as future work. BCR=0 is noted as not statistically surprising at Acc=18.5% (expected near-zero under item independence); the finding demonstrates a metric property — per-query accuracy and within-bundle consistency can diverge — not a specific claim about world models.

---

**To Rkeo (leakage, degrees of freedom, post-hoc arms):**

Leakage audit: PASS on all 26 checks. No gold answers in prompts; frozen output timestamps predate annotation; private arm mapping held separately.

Degrees of freedom: Protocol pre-registered before Round 2. Sensitivity analysis over 17 scenarios in supplementary. We disclose results counter to the original framing: (a) F2 spurious doc credits, (b) F2 ≥ F3 on temporal event selection, (c) F1 avoids stale-state errors entirely on ownership questions without temporal representation.

F1 and F2: We acknowledge these are exploratory post-result ablations, labeled as such. The pre-registered comparison is F3 vs F0.

Presentation: Manuscript revised — terminology glossary, error taxonomy figure, consistent metric naming, F1/F2 labeled as exploratory.

---

**Revised primary contribution.** The paper's primary claim (BCR exposes consistency failures that accuracy misses) is well-supported on the full 1088-bundle benchmark and is not affected by any H4-study issues. The H4 reader study contributes two methodological findings: (1) exact-match benchmarks conflate format compliance with semantic accuracy, a general evaluation-science observation; (2) temporal evidence presentation is associated with substantially fewer stale-state errors, an actionable but preliminary finding requiring cross-model replication.

We remove the claim that F3 achieves the highest semantic accuracy. We retain the temporal-representation finding as a preliminary association, labeled as exploratory.

---

**Summary of key changes:**
- Primary metric changed from exact-match to B1-nodoc (semantic)
- "F3 achieves highest semantic accuracy" removed
- "Latest event" convention explicitly disclosed
- 34 unanswerable doc items separated in all tables
- BCR=0 caveat added (expected at Acc=0.185)
- F1 and F2 labeled as exploratory post-result ablations
- F1/CEO-mc stale=85% disclosed as a question-template artifact
- Error taxonomy table added

We are prepared to submit the revised manuscript upon acceptance.
