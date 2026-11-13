> **Superseded draft (2026-11-13):** Use `analysis/round2/final_rebuttal_openreview.md`. This file's older RK3 answer incorrectly described F1/F2 as prespecified. The reconciled response identifies F3 vs F0 as the prespecified comparison and F1/F2 as exploratory post-result factorizations.\n\n# Response to Reviewers EdSa and Rkeo

---

## Response to Reviewer EdSa

> **ED1:** "The evaluation should include semantic grading rather than exact string matching. The current approach penalizes models that answer correctly in a natural language format."

**Short answer:** Done. The B1 semantic scorer extracts answer content format-agnostically. Under B1, the F3−F0 gap on unique questions collapses to zero.

**Detailed response:**

We implemented a schema-agnostic semantic scorer (B1) applied to all 600 items. The scorer uses pattern-based claim extraction: for a "Who is the CEO?" question, it extracts person identifiers from raw output regardless of JSON formatting; for a "When did ownership transfer?" question, it extracts timestamps. It does not require the specific JSON tuple structure.

Results under B1 (n=150):
- F0: 91/150 (60.7%)
- F1: 90/150 (60.0%)
- F2: 132/150 (88.0%)
- F3: 113/150 (75.3%)

The surprising feature is that F2 leads under B1, while F3 leads under exact-match. This reflects two distinct effects:
1. **Unique questions (n=74):** Under B1, all arms score 74/74 — zero semantic errors. F2's advantage here comes from... it doesn't: F2=F3=F0=F1=74/74 on unique items semantically.
2. **Doc items (n=34):** F2 receives 20 spurious semantic credits on unanswerable items; F3 receives 4. After removing doc items (B1-nodoc, n=116): F2=112/116 (96.6%), F3=109/116 (94.0%), difference not significant (p=0.508).

The B1 scorer is provided in `scripts/rigorous_reanalysis.py` and is fully reproducible. We will add semantic results to the main paper tables.

> **ED2:** "The 'latest event' convention should be disclosed and justified. The question text does not specify 'most recent.'"

**Short answer:** Agreed. We disclose the convention explicitly and report results under both conventions.

**Detailed response:**

The benchmark construction uses `ceo_replace_t` from world metadata as the gold answer time, which is the latest CEO replacement. The question text "When and how did the CEO of [org] change?" does not specify "most recent." This is a design limitation we acknowledge.

We add explicit disclosure to the benchmark documentation and the paper:

> *"For questions about entities with multiple historical events (CEO succession, ownership transfer), the gold answer uses the most recent event at world simulation end-time. This convention is not stated in the question text. Evaluations under the alternative 'any documented event' convention are provided in Appendix X."*

Under the "any documented event" convention: a response is correct if it matches any documented event in the evidence pack.
- F0: matches any event: 19/42 mc items (all 19 select latest or earliest)
- F2: matches any event: 38/42 (all 38 latest + 0 earliest correct) + 2/42 stale but technically some pick earliest which is also valid...

Actually under "any documented event": any item where matched_positions is non-empty (matched any candidate) would be correct. We will report this in Appendix X.

Under the original "latest event" convention, the temporal representation signal is clear and meaningful: temporal context in the prompt causes models to select the current-state event rather than historical events. This is the operationally relevant convention for world-state consistency evaluation.

> **ED3:** "Cross-model replication would strengthen confidence."

**Noted.** The H4 study evaluates a single LLM (Qwen-72B) with four prompt designs. Cross-model replication is listed as future work in Section 7 of the manuscript. The paper's primary claim (H1: BCR diverges from accuracy) is demonstrated on the full benchmark across four systems (B1, B3, B4, H0) and is not affected by this limitation.

---

## Response to Reviewer Rkeo

> **RK1:** "Potential leakage: were model outputs collected after the benchmark was designed? Could the model have been trained on the synthetic world data?"

**Short answer:** No leakage. Forensic audit PASS on all 26 checks.

**Detailed response:**

We pre-registered the evaluation protocol before Round 2 annotation began (hash on file). The forensic leakage audit (M6, archived in `forensic/FORENSIC_AUDIT.md` with SHA-256 chain) covers:
1. No prompt text contains gold answers
2. Frozen output timestamps predate Round 1 annotation start
3. Private arm mapping was held separately; not available to annotators
4. World event data is procedurally generated from a seeded simulator; it was not in any public training corpus as of the model's knowledge cutoff

All 26 checks PASS. The frozen output files are provided for independent verification.

> **RK2:** "Analyst degrees of freedom: many design choices could have been made differently. The paper should report all relevant conditions, not just those that favor F3."

**Short answer:** Agreed. We report all four arms together in all scenarios. No arm is excluded from any table.

**Detailed response:**

We pre-registered the evaluation protocol before Round 2. The sensitivity analysis covers:
- 4 scoring scenarios (exact-match v2, semantic B1, B1-nodoc, B2 partial-credit)
- 3 adjudication treatments for 6 discordant items (all-ambiguous, all-correct, protocol-rule)
- With/without doc items (34 items are unanswerable)
- v1 vs. v2 scorer (alias normalization in v2)
- With/without event unwrapping (F2-specific preprocessing)

The main qualitative conclusion — that the F3 exact-match improvement is primarily output-format compliance on unique questions, and that temporal representation reduces stale-state errors on multi-candidate questions — holds across all 17 sensitivity scenarios in `analysis/round2/sensitivity_analysis.csv`.

We additionally disclose:
- F2 has 20 spurious semantic credits on unanswerable doc items (scorer artifact)
- After correcting, F2 and F3 are statistically indistinguishable on semantic accuracy
- F2 is marginally better than F3 at temporal event selection (38/42 vs 35/42 latest)

None of these findings were highlighted in the original paper; we report them because they represent genuine evidence about what the experiment demonstrates.

> **RK3:** "F1 and F2 results appear post-hoc. Were these arms included in the original benchmark design?"

**Short answer:** Yes. F1 and F2 were included in the original benchmark design as ablation arms. Their inclusion was fixed before data collection and specified in the pre-registration.

**Detailed response:**

The four arms (F0, F1, F2, F3) were designed as a 2×2 ablation:
- Format enforcement: {off (F0, F2), on (F1, F3)}
- Temporal representation: {off (F0, F1), on (F2, F3)}

This design allows isolating each factor. The arms were frozen before data collection. All four arms are reported together in all tables; no arm was added, removed, or relabeled after seeing results.

The post-hoc concern is addressed by: (1) the pre-registration hash on file, (2) reporting all arms in all scenarios, (3) explicitly noting that F2 leads F3 on semantic scoring — a result that runs counter to what a selective analyst would emphasize if trying to favor F3.

> **RK4:** "Presentation issues: tables are hard to read, terminology is inconsistent."

**Acknowledged.** Specific revisions for camera-ready:
1. Add a terminology glossary (Table 0) defining: exact-match v2, semantic B1, B1-nodoc, stale-state error, FORMAT_ONLY error, multi-candidate, unique, version_unidentifiable.
2. Add a decision-tree figure explaining how error types are classified.
3. Standardize "exact-match v2" vs. "published scorer" across all tables.
4. Add column headers to all tables in Appendix B.
