# Qwen H4 findings (Run1 reuse + Run2 Option A)

- H4 status: `not_supported`
- Paper shape: `BENCHMARK ONLY`
- Model: `mlx-community/Qwen2.5-3B-Instruct-4bit`
- Run2 newly generated (this process stats): {'newly_generated': 2321, 'reused_run1': 2306, 'failures': 0, 'timeouts': 0, 'initial_todo': 2321, 'wall_hours': 3.264}
- Wall runtime hours (this finalize process may be resume): 3.26

## System table

- **B1_flat_cap150_compact**: Acc=0.096 BCR=0.0 [0.0,0.0] ConsAcc=0.0 abs=0.7278 mal=0.0071 high_inconsist=0.0
- **B3_recency_k8**: Acc=0.0929 BCR=0.0 [0.0,0.0] ConsAcc=0.0 abs=0.7278 mal=0.0071 high_inconsist=0.0
- **B4_bm25_k8**: Acc=0.1484 BCR=0.0 [0.0,0.0] ConsAcc=0.0 abs=0.5786 mal=0.0008 high_inconsist=0.0
- **H0_ltkm_cap150_ret8**: Acc=0.1849 BCR=0.0 [0.0,0.0] ConsAcc=0.0 abs=0.4825 mal=0.0286 high_inconsist=0.0

## Decision notes

```json
{
  "systems": {
    "B1_flat_cap150_compact": {
      "bcr": 0.0,
      "acc": 0.096,
      "abs": 0.7278,
      "mal": 0.0071,
      "high_inconsist": 0.0
    },
    "B3_recency_k8": {
      "bcr": 0.0,
      "acc": 0.0929,
      "abs": 0.7278,
      "mal": 0.0071,
      "high_inconsist": 0.0
    },
    "B4_bm25_k8": {
      "bcr": 0.0,
      "acc": 0.1484,
      "abs": 0.5786,
      "mal": 0.0008,
      "high_inconsist": 0.0
    },
    "H0_ltkm_cap150_ret8": {
      "bcr": 0.0,
      "acc": 0.1849,
      "abs": 0.4825,
      "mal": 0.0286,
      "high_inconsist": 0.0
    }
  },
  "beats_ret": false,
  "beats_flat": false,
  "not_via_abs": true,
  "mal_ok": true
}
```
