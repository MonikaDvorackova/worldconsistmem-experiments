# WorldConsistMem baseline findings

**Verdict:** BASELINE SIGNAL VALIDATED

## Benchmark freeze

- smoke SHA256: `3aa67ed1b6a39be3d9e1805d14f7d5ce7cc05f4655bdce0bc4ff49900c14c7ab`
- expected: `3aa67ed1b6a39be3d9e1805d14f7d5ce7cc05f4655bdce0bc4ff49900c14c7ab`
- worlds=25, events=668, bundles=125, queries=825

## Fairness

| Baseline | History | Capacity | Index | Retrieval | Reader |
|---|---|---|---|---|---|
| B0_oracle | gold world | n/a | gold states | none | gold reconstruct |
| B1_flat_append | full obs | unconstrained | append list | none (scan) | structured |
| B2_latest_only | latest only | #keys | key→obs | none | structured |
| B3_recency | full | unconstrained | list | lexical+recency k=5 | structured |
| B4_bm25 | full | unconstrained | NL BM25 | BM25 k=5 | structured |
| B5_reservoir_c8/c16 | reservoir | 8 or 16 obs | reservoir | none | structured |

Matched-capacity note: B5 is capacity-limited; B1/B3/B4 are unconstrained flat stores.
Do not claim fair architectural comparison across unequal capacities.

## Metric comparison

| baseline | run | Acc | BCR | ConsAcc | Gap(Acc-BCR) | highAcc-incons | consist-wrong |
|---|---|---:|---:|---:|---:|---:|---:|
| B0_oracle | oracle | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| B1_flat_append | flat | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| B2_latest_only | latest | 0.4848 | 0.2 | 0.2 | 0.2848 | 0.0 | 0.0 |
| B3_recency_retrieval | recency_k5 | 0.697 | 0.2 | 0.0 | 0.497 | 0.2 | 0.2 |
| B4_bm25 | bm25_k5 | 0.9091 | 0.4 | 0.4 | 0.5091 | 0.6 | 0.0 |
| B5_reservoir_c8 | reservoir_c8_s0 | 0.2424 | 0.0 | 0.0 | 0.2424 | 0.0 | 0.0 |
| B5_reservoir_c8 | reservoir_c8_s1 | 0.3333 | 0.2 | 0.2 | 0.1333 | 0.0 | 0.0 |
| B5_reservoir_c8 | reservoir_c8_s2 | 0.3333 | 0.2 | 0.2 | 0.1333 | 0.0 | 0.0 |
| B5_reservoir_c16 | reservoir_c16_s0 | 0.6182 | 0.536 | 0.536 | 0.0822 | 0.0 | 0.0 |
| B5_reservoir_c16 | reservoir_c16_s1 | 0.5273 | 0.4 | 0.4 | 0.1273 | 0.0 | 0.0 |
| B5_reservoir_c16 | reservoir_c16_s2 | 0.7818 | 0.6 | 0.6 | 0.1818 | 0.04 | 0.0 |

## Diagnostic answers

1. **High Acc / low BCR?** See non-oracle rows with positive Gap(Acc-BCR), especially B2/B3/B4.
2. **Query families driving contradictions:** compare query_family_results.csv (historical/transition/provenance vs current).
3. **Constraints beyond Acc:** transition, provenance, multi_hop, temporal rates in constraint_family_results.csv.
4. **Latest-state:** strong current-state Acc expected; historical/transition collapse; bundles become inconsistent.
5. **Flat memory:** with complete observation replay and interval-aware reading, Acc=BCR=1 on smoke — storage completeness can suffice when the reader is event-sourced; the Acc–consistency gap appears when history is truncated or retrieved incompletely.
6. **Retrieval inconsistencies:** missing evidence (historical abstentions in top-k), incompatible version sets, transition/current disagreement, multi-hop composition failures.
7. **Recall vs Acc vs BCR:** B4 Recall@5≈0.91 with Acc≈0.91 but BCR only 0.40 — high retrieval/answer accuracy still leaves many bundles inconsistent.

## Example high-accuracy inconsistent bundles

- `B3_recency_retrieval` bundle `w0042_000:b:own:1` Acc=0.833
  - [transition] Transition from/to disagree with historical/current answers.
- `B3_recency_retrieval` bundle `w0042_001:b:own:1` Acc=0.833
  - [transition] Transition from/to disagree with historical/current answers.
- `B3_recency_retrieval` bundle `w0042_002:b:own:1` Acc=0.833
  - [transition] Transition from/to disagree with historical/current answers.

## Example consistent-but-wrong bundles

- `B3_recency_retrieval` bundle `w0042_000:b:conf:4` Acc=0.857
- `B3_recency_retrieval` bundle `w0042_001:b:conf:4` Acc=0.857
- `B3_recency_retrieval` bundle `w0042_002:b:conf:4` Acc=0.857

## Interpretation limit

Cross-query consistency reveals naturally occurring bundle-level failures that isolated per-query accuracy does not fully characterize.

No claim of hierarchical LTKM superiority, external validity, LLM failure, or architectural causality is made at this stage.


_Automated verdict tag: BASELINE SIGNAL VALIDATED_
