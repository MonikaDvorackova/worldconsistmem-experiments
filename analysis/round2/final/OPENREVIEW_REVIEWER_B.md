# Response to Reviewers EdSa and Rkeo

---

## Reviewer EdSa

**ED1: Semantic grading of all 150 items**

Semantic grading is complete. We applied the B1 scorer to all 150 × 4 items. After excluding 34 document items (all unanswerable — evidence packs contain no version identifiers for the queried v1→v2 transitions), B1-nodoc scores are:

| Arm | Semantic (B1-nodoc, n=116) | Rate |
|-----|---------------------------:|-----:|
| F0 | 87/116 | 75.0% |
| F1 | 90/116 | 77.6% |
| F2 | 112/116 | 96.6% |
| F3 | 109/116 | 94.0% |

F2 and F3 are not significantly different (McNemar exact p = 0.508; RD = +2.6 pp [−2.5, +7.6]). We adopt B1-nodoc as the primary semantic metric and remove any claim that F3 achieves higher semantic accuracy.

F2's apparent overall lead (132/150 under full B1 vs F3's 113/150) is entirely explained by 20 spurious credits on unanswerable document items — a scorer artifact of F2's prev/event/next format. This is fully disclosed.

**ED2: F3 claims require qualification**

We accept this. We revise the main result to: "F3 improves output-format compliance; F2 and F3 achieve comparable semantic accuracy on answerable questions. The available evidence does not establish a semantic difference (p = 0.508)." We remove all claims of F3 semantic superiority.

**ED3: Latest-event convention not disclosed**

We add explicit disclosure in Section 3: "For multi-candidate questions (CEO succession, ownership transfer), the gold answer uses the most recent event at world end-time. This convention is not stated in the question text." We also report results under the alternative "any documented event" convention in a new Appendix.

**ED4: Cross-model replication**

Acknowledged as future work (Section 7 of revised manuscript). The H4 reader study evaluates a single LLM. We do not claim that the reader-study findings generalize across model families.

---

## Reviewer Rkeo

**RK1: Potential leakage**

Forensic audit: PASS on all 26 checks. Key properties: (1) no gold answer values appear in any prompt; (2) frozen output timestamps predate Round 1 annotation; (3) the arm-to-condition mapping was held in a separate process unavailable to annotators; (4) world event data is procedurally generated from a seeded simulator. The full SHA-256 chain is documented in the supplementary materials.

**RK2: Analyst degrees of freedom**

The evaluation protocol was finalized before Round 2 annotation began (hash on file). We provide a 17-scenario sensitivity analysis in the supplementary materials. The main qualitative conclusion — that exact-match conflates format compliance with semantic accuracy — holds across all 17 scenarios. We additionally disclose findings that run counter to the original framing: (a) F2 spurious credits on doc items, (b) F2 ≥ F3 on temporal event selection, (c) F1 selects the latest ownership transfer without any temporal evidence structure.

**RK3: F1 and F2 appear post-hoc**

We acknowledge this. F1 and F2 were designed after observing F3, as an explanatory factorization. We label them accordingly in the revised paper as exploratory post-result ablations. The pre-registered comparison is F3 vs F0. The factorization remains informative: F1 (schema-only) selects the earliest CEO event 85% of the time (17/20 items), while F2 (prev/event/next structure) selects the latest 76% of the time (32/42 items). Whether this effect is causal or attributable to prompt-template differences cannot be determined from this design.

**RK4: Presentation**

Specific manuscript revisions committed:
1. Terminology glossary (Table 0): exact-match v2, B1 semantic, B1-nodoc, stale-state error, FORMAT_ONLY, multi-candidate, unique, version_unidentifiable.
2. Error taxonomy figure: decision tree with six error types (CORRECT, FORMAT_ONLY, STALE_STATE, MC_INCOMPLETE, INSUF_EV_FAIL, INSUF_EV_SPURIOUS).
3. Consistent metric naming throughout all tables and figures.
4. F1/F2 labeled as exploratory post-result ablations everywhere they appear.
5. BCR=0 caveat added: "BCR=0 is not surprising at Acc=0.185 (expected near-zero under item independence); the finding demonstrates that per-query accuracy and within-bundle consistency can diverge."
