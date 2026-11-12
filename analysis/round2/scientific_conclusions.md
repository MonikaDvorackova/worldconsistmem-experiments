# Scientific Conclusions — WorldConsistMem

Generated: 2026-11-12  
Source: Independent reanalysis; `analysis/round2/hypothesis_assessment.md`

This document states the strongest claims this experiment can defensibly support and the claims it cannot support. It is written evidence-first, not framing-first.

---

## What the experiment demonstrates

### 1. BCR diverges from per-query accuracy (STRONG)

**The claim:** A system can achieve non-trivial per-query accuracy (Acc=0.185 for LTKM) while being entirely inconsistent across queries within the same bundle (BCR=0 for all systems).

**Evidence:** Full benchmark, 102 worlds, 1088 bundles, 7140 queries, four systems. All systems BCR=0. This is a large-n, structurally robust finding.

**What it means:** Benchmarks that report only per-query accuracy give an incomplete — and misleading — picture of knowledge consistency. A system that achieves 18.5% single-query accuracy while failing to give consistent answers about the same entity across related questions is not reliably consistent. BCR measures this gap directly.

**Strongest defensible framing:** The benchmark demonstrates that existing systems do not achieve cross-query consistency even at modest accuracy levels. The BCR metric is a useful complement to accuracy in evaluating temporal world-state reasoning.

---

### 2. Exact-match benchmarks overstate format-related gaps (STRONG)

**The claim:** On questions with unambiguous answers (n=74 unique questions), all evaluated arms correctly identify the answer content. The entire exact-match gap between schema-enforcing prompts (F1, F3) and non-schema prompts (F0, F2) reflects output-format compliance, not semantic understanding.

**Evidence:** Semantic B1 scorer: all arms 74/74 on unique questions. Exact-match: F0=10/74, F2=12/74, F1=F3=74/74. Format gap: 86.5 pp exact, 0 pp semantic.

**What it means:** Benchmarks that require specific JSON schemas will show large performance gaps between models that happen to produce the right format and those that don't, even when both retrieve the correct answer content. This is a general methodological finding: format compliance ≠ semantic accuracy.

**Strongest defensible framing:** The evaluation design artifact — requiring exact JSON output — inflates the apparent performance advantage of schema-enforcing prompts. Future evaluations should use semantic scorers as the primary metric.

---

### 3. Temporal context in prompts reduces stale-state errors (MODERATE)

**The claim:** Including explicit temporal structure in the prompt (prev/event/next for F2; full context bundle for F3) reduces the rate at which a model selects an earlier historical event rather than the current state.

**Evidence:** Multi-candidate stale-state errors: F0=23/42 (54.8%), F1=17/42 (40.5%), F2=2/42 (4.8%), F3=7/42 (16.7%). Effect is consistent across both temporal-context arms (F2, F3) relative to both baseline arms (F0, F1). Effect size is large (factor of ~5-10x reduction).

**What it means:** Models without temporal context default to selecting earlier historical events roughly half the time. Providing explicit temporal structure in the prompt causes near-elimination of this error. This is actionable: prompt design affects temporal reasoning.

**Caveats:**
- Sample n=42 multi-candidate items. The effect is large enough to be meaningful at this n, but replication at larger scale is needed.
- The design is not a clean ablation: F2 and F3 differ from F0/F1 in ways beyond temporal structure (e.g., length, context).
- Single LLM evaluated.

**Strongest defensible framing:** As a preliminary finding requiring replication, this is defensible: "Temporal representation in prompts is associated with dramatically fewer stale-state errors in this study (F0: 55% → F2: 5%). Cross-model replication is needed."

---

## What the experiment does not demonstrate

### X1. F3 (bundled structured prompt) achieves higher semantic accuracy than F2 or F0

**Not supported.** Under corrected semantic scoring (B1-nodoc): F2=96.6%, F3=94.0%, difference 3 items, p=0.508. F3's headline exact-match advantage is output-format compliance.

### X2. Architecture differences drive consistency improvements (REJECTED)

**Explicitly rejected.** All systems (B1, B3, B4, H0) achieve BCR=0. H0 (LTKM) achieves highest accuracy but BCR=0. Architecture type does not explain consistency differences in this evaluation.

### X3. The H4 reader study generalizes across LLMs

**Untested.** Single LLM (Qwen-72B). The format-compliance finding (X2 error taxonomy) is structural and likely robust to model choice. The stale-state finding may differ across models with stronger temporal reasoning.

### X4. BCR improvements require specific prompt design

**Unknown.** The H4 study evaluates prompt design for the reader (inference) component. BCR=0 for all systems on the full benchmark regardless of system architecture. No arm achieves BCR > 0.

---

## Recommended framing for revised paper

**Title-level contribution:** A benchmark demonstrating that cross-query consistency (BCR) diverges from per-query accuracy for temporal world-state knowledge.

**Supported claims for abstract:**
1. BCR exposes failures invisible to accuracy: all systems, including the best-performing architecture, achieve BCR=0.
2. Exact-match evaluation conflates output-format compliance with semantic accuracy; semantic scoring should be used.
3. Temporal context in prompts reduces stale-state errors from ~50% to ~5-17% in preliminary evaluation (single LLM, replication needed).

**Claims to remove or weaken:**
1. Remove: "F3 achieves highest semantic accuracy." Replace with: "F2 and F3 are statistically indistinguishable on semantic accuracy."
2. Weaken: Any claim about architecture superiority.
3. Add: Explicit disclosure of the latest-event convention and the unanswerable doc items.

---

## Strongest contribution ranking

1. **BCR methodology** (H1): Strong, large-scale, directly demonstrated. The core contribution.
2. **Format-compliance confound** (H2): Strong, structural. A methodological contribution to evaluation science.
3. **Temporal representation reduces stale-state errors** (H3): Moderate, preliminary. A suggestive finding that motivates follow-up.
4. **Human evaluation methodology** (H6): Demonstrates a path to reliable annotation for temporal world-state questions, with appropriate disclosure of Round 1 limitations.

The paper is fundamenally a benchmark paper, not an architecture paper. The strongest path to acceptance is to frame it as such: BCR as a contribution, the evaluation-confound finding as a secondary contribution, and the temporal representation result as preliminary motivation for future work.
