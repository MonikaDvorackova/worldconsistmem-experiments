# LTKM prototype findings

**Verdict:** PROTOTYPE SIGNAL VALIDATED

## Benchmark freeze

- smoke SHA256: `3aa67ed1b6a39be3d9e1805d14f7d5ce7cc05f4655bdce0bc4ff49900c14c7ab` (unchanged)

## Architecture

Five stores updated by deterministic lifecycle ops on ingest:

1. **CurrentStore** — one active exclusive fact per key  
2. **ArchiveStore** — superseded/terminated facts with validity intervals  
3. **GraphStore** — typed edges with validity + provenance  
4. **ProvenanceStore** — links from records to observation/provenance IDs  
5. **ConflictStore** — unresolved vs resolved competing claims  

Raw observations are sealed (`_audit_obs`); answer path cannot read them. Queries route to designated stores (~1 record consulted/query vs ~27 raw obs for B1).

## System comparison

| system | Acc | BCR | Gap | abstain | avg consulted |
|---|---:|---:|---:|---:|---:|
| B1 flat | 1.00 | 1.00 | 0.00 | 0.00 | 26.7 |
| B2 latest | 0.48 | 0.20 | 0.28 | 0.39 | 19.8 |
| B3 recency | 0.70 | 0.20 | 0.50 | 0.24 | 5.0 |
| B4 BM25 | 0.91 | 0.40 | 0.51 | 0.09 | 5.0 |
| **H0 LTKM** | **1.00** | **1.00** | **0.00** | **0.00** | **1.0** |
| H−archive | 0.88 | 0.40 | 0.48 | 0.09 | 0.88 |
| H−temporal | 0.88 | 0.40 | 0.48 | 0.00 | 0.97 |
| H−graph | 0.94 | 0.60 | 0.34 | 0.06 | 0.97 |

Gate checks vs B3/B4:

- BCR: 1.00 ≥ 0.20+0.20 and 0.40+0.20  
- Gap reduction: 0.50 and 0.51 (≥ 0.20)  
- Abstention: 0  
- Constraint families improved vs B4: transition, relational, multi_hop (+ temporal already 0)

## Ablations

| ablation | historical Acc | multi_hop Acc | BCR |
|---|---:|---:|---:|
| H0 | 1.0 | 1.0 | 1.0 |
| H−archive | **0.2** | 1.0 | **0.4** |
| H−temporal-validity | **0.2** | 1.0 | **0.4** |
| H−graph | 1.0 | **0.6** | **0.6** |

## Anti-triviality

- No universal observation scan (consulted ≪ n_obs).  
- No answer-time access to sealed raw obs list.  
- No `GeneratedWorld` / gold-answer reads in `ltkm/`.  
- Ablations materially change the predicted dimensions.  
- Matches B1 accuracy on smoke but **not** via flat replay: structured stores + lifecycle.

## Representative cases

**B4 inconsistency / miss corrected by H0:** multi-hop employer and historical ownership abstentions under BM25 top-5 become store lookups (see `examples.json`).

**Remaining H0 failures on smoke:** none (Acc=BCR=1).

**Archive removal:** historical Acc 1.0 → 0.2; BCR 1.0 → 0.4.

**Graph removal:** multi_hop Acc 1.0 → 0.6; BCR 1.0 → 0.6.

## Permitted conclusion

> Explicitly structured lifecycle-aware memory can reduce cross-query consistency failures relative to simple latest-state and retrieval-centric baselines on WorldConsistMem.

No claim of general hierarchical superiority, necessity of five layers, superiority over B1, or matched-capacity fairness (H0 unconstrained vs B5).

_tag: PROTOTYPE SIGNAL VALIDATED_
