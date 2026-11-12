# Response to Reviewers EdSa and Rkeo — Final

---

## Reviewer EdSa

> **ED1: "Semantic grading is needed; correct answers in natural-language format should not be penalized."**

Done. The B1 semantic scorer extracts answer content from raw outputs without requiring any specific JSON structure. Full results for all 600 items are in `analysis/round2/case_level_error_analysis.csv`.

Under B1, the original headline claim reverses on some dimensions. F2 leads all arms overall (132/150), but this is driven by 20 spurious credits on 34 unanswerable document items. After excluding those items (B1-nodoc, n=116):

| Arm | Semantic (B1-nodoc) | Rate |
|-----|-------------------:|-----:|
| F0 | 87/116 | 75.0% |
| F1 | 90/116 | 77.6% |
| F2 | 112/116 | 96.6% |
| F3 | 109/116 | 94.0% |

F2 and F3 are not significantly different (McNemar p=0.508; RD=+2.6pp [−2.5, +7.6]). **We revise the paper to use B1-nodoc as the primary semantic metric and remove any claim that F3 achieves higher semantic accuracy than F2.**

> **ED2: "F3 claims need qualification; evidence for semantic world-state improvement is weak."**

We accept this. The F3 exact-match advantage over F0 (96 items) decomposes as: (1) format compliance on 74 unique questions (semantic gap = 0), (2) reduced stale-state errors on 42 multi-candidate questions (a genuine signal, discussed below), and (3) a scorer artifact on 30 unanswerable doc items. The claim "F3 improves semantic world-state tracking" is not supported. We revise to: "F3 improves output-format compliance; F2 and F3 achieve comparable semantic accuracy on answerable questions."

> **ED3: "The 'latest event' convention should be disclosed."**

We add explicit disclosure in Section 3: "For multi-candidate questions (CEO succession, ownership transfer), the gold answer uses the most recent event at world end-time. This convention is not stated in the question text." We also report results under the alternative "any documented event" convention in Appendix X.

> **ED4: "Cross-model replication."**

Acknowledged as future work (Section 7). The BCR finding (main claim) uses four evaluated systems; the H4 reader study uses a single LLM. We do not claim the reader-study findings generalize across model families.

---

## Reviewer Rkeo

> **RK1: "Potential leakage."**

Forensic audit PASS on all 26 checks. Key properties: (1) no gold answer values in prompts; (2) frozen output timestamps predate Round 1 annotation; (3) private arm mapping held in a separate process, not available to annotators; (4) world event data is procedurally generated from a seeded simulator. Full SHA-256 chain in `forensic/FORENSIC_AUDIT.md`.

> **RK2: "Analyst degrees of freedom: many design choices could have been made differently."**

The evaluation protocol was pre-registered before Round 2 annotation began (hash on file). We provide a 17-scenario sensitivity analysis in `analysis/round2/sensitivity_analysis.csv`. The main qualitative conclusion — that exact-match conflates format compliance with semantic accuracy — holds across all scenarios. We additionally disclose findings that run counter to the original framing: (a) F2 spurious doc credits, (b) F2 ≥ F3 on temporal event selection, (c) F1 selects the latest ownership transfer without temporal representation.

> **RK3: "F1 and F2 appear post-hoc."**

We acknowledge per the working draft: F1 and F2 were designed after observing F3, as an explanatory factorization. We label them accordingly in the revised paper. The pre-registered comparison is F3 vs F0. F1 and F2 are reported as exploratory ablations. The factorization remains informative: F1 (schema-only, no temporal structure) selects the earliest CEO event 85% of the time (17/20), while F2 (prev/event/next structure) selects the latest 80% of the time (16/20). Whether this effect is causal or a prompt-template artifact cannot be determined from this design.

> **RK4: "Presentation issues."**

Specific manuscript revisions committed:
1. Terminology glossary (Table 0): exact-match v2, B1 semantic, B1-nodoc, stale-state error, FORMAT_ONLY, multi-candidate, unique, version_unidentifiable.
2. Error taxonomy figure: decision tree with six error types.
3. Consistent metric naming throughout.
4. F1/F2 labeled as exploratory ablations.
5. BCR=0 caveat added: "BCR=0 is not surprising at Acc=0.185 (expected ~0 under independence); the finding demonstrates a metric property, not the absence of a world model."
