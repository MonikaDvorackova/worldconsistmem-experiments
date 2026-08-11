# WorldConsistMem smoke benchmark validation

## Scale

- worlds: 25
- events: 668 (min/world=25)
- bundles: 125 (min/world=5)
- queries: 825 (min/bundle=6)
- query-family distribution: `{'current_state': 125, 'historical_state': 125, 'transition': 125, 'multi_hop': 125, 'provenance': 125, 'temporal_order': 50, 'contradiction': 50, 'counterfactual': 50, 'conflict_validity': 50}`
- constraint-family annotation counts: `{'uniqueness': 100, 'transition': 300, 'relational': 200, 'temporal': 300, 'contradiction': 225, 'multi_hop': 125, 'provenance': 125}`

## Metric definition note

Planning `consistency-metrics.md` defines `Gap_bundle = Acc_bundle - ConsAcc`. The implementation milestone brief defines `Gap = MeanQueryAccuracy - BCR`. **Both are reported**; they are not identical.

## Gold metrics

- mean_query_accuracy: 1.0
- BCR: 1.0
- ConsAcc strict: 1.0
- ConsAcc relaxed (threshold=0.8): 1.0
- Gap (MeanQueryAcc - BCR): 0.0
- Gap_bundle (Acc_bundle - ConsAcc): 0.0

## Corruption suite

| corruption | Acc | BCR | ConsAcc | Gap(Acc-BCR) |
|---|---:|---:|---:|---:|
| single_answer | 0.8485 | 0.0 | 0.0 | 0.8485 |
| entity_swap | 0.7879 | 0.0 | 0.0 | 0.7879 |
| temporal_mismatch | 0.8182 | 0.2 | 0.2 | 0.6182 |
| wrong_provenance | 0.8485 | 0.0 | 0.0 | 0.8485 |
| transition_inconsistency | 0.9394 | 0.6 | 0.6 | 0.3394 |
| multihop_inconsistency | 0.9394 | 0.6 | 0.6 | 0.3394 |
| high_acc_inconsistent | 0.8485 | 0.0 | 0.0 | 0.8485 |
| consistent_wrong_world | 0.3939 | 1.0 | 0.0 | -0.6061 |

## Full bundle example

World: `w0042_000`  Bundle: `w0042_000:b:ceo:0`

### Gold history (event summaries)

- t=1 `person_joins_org` {'person_id': 'w0042_000:person:0', 'org_id': 'w0042_000:org:0'} prov=w0042_000:prov:1
- t=2 `role_assignment` {'person_id': 'w0042_000:person:0', 'org_id': 'w0042_000:org:0', 'role': 'CEO', 'exclusive': True} prov=w0042_000:prov:2
- t=3 `person_joins_org` {'person_id': 'w0042_000:person:1', 'org_id': 'w0042_000:org:0'} prov=w0042_000:prov:3
- t=4 `person_joins_org` {'person_id': 'w0042_000:person:2', 'org_id': 'w0042_000:org:0'} prov=w0042_000:prov:4
- t=5 `project_status_change` {'project_id': 'w0042_000:project:0', 'status': 'active', 'manager_id': 'w0042_000:person:0'} prov=w0042_000:prov:5
- t=6 `relationship_creation` {'rel_id': 'w0042_000:rel:0', 'rel_type': 'manages', 'source_id': 'w0042_000:person:0', 'target_id': 'w0042_000:project:0'} prov=w0042_000:prov:6
- t=7 `document_creation` {'doc_id': 'w0042_000:doc:0', 'base_doc_id': 'w0042_000:docbase:0', 'title': 'Charter-w0042_000:project:0', 'project_id': 'w0042_000:project:0', 'author_id': 'w0042_000:person:2'} prov=w0042_000:prov:7
- t=8 `document_approval` {'doc_id': 'w0042_000:doc:0', 'approver_id': 'w0042_000:person:0'} prov=w0042_000:prov:8
- t=9 `location_change` {'person_id': 'w0042_000:person:2', 'location_id': 'w0042_000:loc:1'} prov=w0042_000:prov:9
- t=10 `role_assignment` {'person_id': 'w0042_000:person:2', 'org_id': 'w0042_000:org:0', 'role': 'Engineer', 'exclusive': False} prov=w0042_000:prov:10
- t=11 `conflict_introduction` {'conflict_id': 'w0042_000:conflict:0', 'subject': 'w0042_000:project:0', 'attribute': 'priority', 'value_a': 'P0', 'value_b': 'P2'} prov=w0042_000:prov:11
- t=12 `temporary_state` {'mark_id': 'w0042_000:temp:0', 'entity_id': 'w0042_000:project:1', 'attribute': 'project_status', 'temporary_value': 'paused', 'original_value': 'planned'} prov=w0042_000:prov:12
- t=13 `person_joins_org` {'person_id': 'w0042_000:person:3', 'org_id': 'w0042_000:org:1'} prov=w0042_000:prov:13
- t=14 `role_assignment` {'person_id': 'w0042_000:person:3', 'org_id': 'w0042_000:org:1', 'role': 'CEO', 'exclusive': True} prov=w0042_000:prov:14
- t=15 `document_revision` {'base_doc_id': 'w0042_000:docbase:0', 'doc_id': 'w0042_000:doc:1', 'author_id': 'w0042_000:person:2', 'expected_prev_version': 1} prov=w0042_000:prov:15
- t=16 `role_replacement` {'org_id': 'w0042_000:org:0', 'role': 'CEO', 'new_person_id': 'w0042_000:person:1', 'old_person_id': 'w0042_000:person:0'} prov=w0042_000:prov:16
- t=17 `relationship_termination` {'rel_id': 'w0042_000:rel:0'} prov=w0042_000:prov:17
- t=18 `relationship_creation` {'rel_id': 'w0042_000:rel:1', 'rel_type': 'manages', 'source_id': 'w0042_000:person:1', 'target_id': 'w0042_000:project:0'} prov=w0042_000:prov:18
- t=19 `project_ownership_transfer` {'project_id': 'w0042_000:project:0', 'new_org_id': 'w0042_000:org:1', 'old_org_id': 'w0042_000:org:0'} prov=w0042_000:prov:19
- t=20 `project_status_change` {'project_id': 'w0042_000:project:0', 'status': 'transferred', 'manager_id': 'w0042_000:person:1'} prov=w0042_000:prov:20
- t=21 `conflict_resolution` {'conflict_id': 'w0042_000:conflict:0', 'resolved_value': 'P0'} prov=w0042_000:prov:21
- t=22 `reversion` {'mark_id': 'w0042_000:temp:0'} prov=w0042_000:prov:22
- t=23 `person_leaves_org` {'person_id': 'w0042_000:person:0', 'org_id': 'w0042_000:org:0'} prov=w0042_000:prov:23
- t=24 `location_change` {'person_id': 'w0042_000:person:1', 'location_id': 'w0042_000:loc:2'} prov=w0042_000:prov:24
- t=25 `document_approval` {'doc_id': 'w0042_000:doc:1', 'approver_id': 'w0042_000:person:1'} prov=w0042_000:prov:25
- t=26 `project_status_change` {'project_id': 'w0042_000:project:1', 'status': 'planned'} prov=w0042_000:prov:26
- t=27 `project_status_change` {'project_id': 'w0042_000:project:1', 'status': 'active'} prov=w0042_000:prov:27

### Questions and answers

**w0042_000:b:ceo:0:current** (current_state)
- Q: Who is the CEO of w0042_000:org:0 at t=27?
- gold: `w0042_000:person:1`
- high-acc corrupt: `w0042_000:person:1`
- consistent-wrong: `w0042_000:person:0`

**w0042_000:b:ceo:0:historical** (historical_state)
- Q: Who was the CEO of w0042_000:org:0 at t=15?
- gold: `w0042_000:person:0`
- high-acc corrupt: `w0042_000:person:0`
- consistent-wrong: `w0042_000:person:0`

**w0042_000:b:ceo:0:transition** (transition)
- Q: When and how did the CEO of w0042_000:org:0 change?
- gold: `{'from': 'w0042_000:person:0', 'to': 'w0042_000:person:1', 't': 16, 'role': 'CEO', 'org_id': 'w0042_000:org:0'}`
- high-acc corrupt: `{'from': 'w0042_000:person:0', 'to': 'w0042_000:person:1', 't': 16, 'role': 'CEO', 'org_id': 'w0042_000:org:0'}`
- consistent-wrong: `{'from': 'w0042_000:person:0', 'to': 'w0042_000:person:0', 't': 16, 'role': 'CEO', 'org_id': 'w0042_000:org:0'}`

**w0042_000:b:ceo:0:multihop** (multi_hop)
- Q: Which organization employs the current CEO of w0042_000:org:0 at t=27?
- gold: `w0042_000:org:0`
- high-acc corrupt: `w0042_000:org:0`
- consistent-wrong: `w0042_000:org:0`

**w0042_000:b:ceo:0:provenance** (provenance)
- Q: Which provenance supports the current CEO of w0042_000:org:0?
- gold: `w0042_000:prov:16`
- high-acc corrupt: `prov:SUPERSEDED_OR_WRONG`
- consistent-wrong: `w0042_000:prov:2`

**w0042_000:b:ceo:0:temporal_order** (temporal_order)
- Q: Did the initial CEO assignment occur before the CEO replacement for w0042_000:org:0?
- gold: `True`
- high-acc corrupt: `True`
- consistent-wrong: `True`

**w0042_000:b:ceo:0:contradiction** (contradiction)
- Q: Can w0042_000:person:0 and w0042_000:person:1 both be exclusive CEO of w0042_000:org:0 at t=27?
- gold: `False`
- high-acc corrupt: `False`
- consistent-wrong: `False`

**w0042_000:b:ceo:0:counterfactual** (counterfactual)
- Q: Would claiming w0042_000:person:0 is still CEO of w0042_000:org:0 at t=27 contradict history?
- gold: `True`
- high-acc corrupt: `True`
- consistent-wrong: `False`

### Gold bundle metrics
- mean Acc: 1.0
- consistent (Φ): True
- BCR contribution: 1

### High-accuracy inconsistent corruption
- mean Acc: 0.875
- consistent: False
- triggered constraints:
  - [provenance] w0042_000:b:ceo:0:prov_ceo_provenance: Cited provenance does not support the claimed fact.

### Consistent-but-wrong corruption
- mean Acc: 0.5
- consistent: True
- triggered constraints:
  - (none — internally consistent alternate world)

- Gap on high-acc example: Acc - consistent = 0.875 - 0.0

