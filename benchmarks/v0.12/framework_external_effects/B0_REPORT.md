# V0.12-B0 Framework / External-Effects Frontier

Frozen target: 19 candidates.

Recovery claims in B0: 0.

Grouping is derived from the frozen V0.11 reason codes; AST evidence is diagnostic.

## Exact reason-code groups

### G1 — OBJECT_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET

- candidates: 2
- source resolved: 0
- source unresolved: 2

- `4b57e2d73c695a41` | django_oscar | MEDIUM | function=UNRESOLVED
- `7cf281a33e5781df` | pretix | MEDIUM | function=UNRESOLVED

### G2 — HTTP_RESPONSE_RETURN

- candidates: 1
- source resolved: 1
- source unresolved: 0

- `4d7d61b18dde0ad5` | django_oscar | MEDIUM | function=json_response

### G3 — SCALAR_RETURN_LARGE_PARAMETERIZED_FORMULA | AGGREGATE_HELPER_SEMANTICS_OUTSIDE_FROZEN_SCALAR_A2_SCOPE

- candidates: 1
- source resolved: 1
- source unresolved: 0

- `7bc9603bfbda7dc9` | openfisca_france | HIGH | function=formula_2017_04_01

### G4 — SIDE_EFFECT_ONLY_REDIS_CACHE

- candidates: 1
- source resolved: 1
- source unresolved: 0

- `1311d905af0ebcb5` | pretix | MEDIUM | function=rebuild_cache

### G5 — CONDITIONAL_STRING_CONSTRUCTION_OUTSIDE_FROZEN_FORMAL_SCOPE

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `a09e038870c9b436` | pretix | MEDIUM | function=UNRESOLVED

### G6 — FORM_STATE_MUTATION_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `2309036b0c69ad48` | django_oscar | HIGH | function=UNRESOLVED

### G7 — FRAMEWORK_DICT_MUTATION_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `bcb091a940a8d0dd` | django_oscar | HIGH | function=UNRESOLVED

### G8 — FRAMEWORK_SIGNAL_BASKET_SIDE_EFFECTS_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `63e7979762bf860b` | django_oscar | HIGH | function=UNRESOLVED

### G9 — MODEL_SAVE_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `a79d9687185720aa` | django_oscar | HIGH | function=UNRESOLVED

### G10 — MODEL_SAVE_TRANSACTION_STATE_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `03e2adf4e4f323b1` | pretix | HIGH | function=UNRESOLVED

### G11 — MULTI_OBJECT_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `d7f578c3a5f20b8a` | pretix | MEDIUM | function=UNRESOLVED

### G12 — MULTI_STATE_MUTATION_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `91b2dc32504282fc` | django_oscar | MEDIUM | function=UNRESOLVED

### G13 — NONSCALAR_LIST_SEMANTICS_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `eb12d3a44210a486` | pretix | HIGH | function=UNRESOLVED

### G14 — OPERATION_LIST_MUTATION_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `8048a564541f5408` | pretix | MEDIUM | function=UNRESOLVED

### G15 — PLUGIN_SIGNAL_SET_SEMANTICS_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `8a754dadf1672d0a` | pretix | HIGH | function=UNRESOLVED

### G16 — REFUND_OBJECT_SIDE_EFFECTS_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `882c5eae0d8fd4ec` | pretix | HIGH | function=UNRESOLVED

### G17 — SERVICE_CACHE_OBJECT_SEMANTICS_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `7460029971aad8de` | pretix | HIGH | function=UNRESOLVED

### G18 — SESSION_STATE_MUTATION_OUTSIDE_FORMAL_SUBSET

- candidates: 1
- source resolved: 0
- source unresolved: 1

- `b2996c3dd81aca55` | pretix | MEDIUM | function=UNRESOLVED

## Candidate structural profiles

### 03e2adf4e4f323b1

- source: pretix
- complexity: HIGH
- frozen reason: MODEL_SAVE_TRANSACTION_STATE_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### 1311d905af0ebcb5

- source: pretix
- complexity: MEDIUM
- frozen reason: SIDE_EFFECT_ONLY_REDIS_CACHE
- source resolved: True
- function: rebuild_cache
- calls: ['django_redis.get_redis_connection', 'p.execute', 'p.hdel', 'p.hdel', 'p.hdel', 'p.hdel', 'rc.pipeline', 'self.availability', 'str', 'str', 'str', 'str']
- attribute writes: []
- structural primitives: ['CALL_DEPENDENCY', 'NO_VALUE_RETURN', 'BRANCHING']

### 2309036b0c69ad48

- source: django_oscar
- complexity: HIGH
- frozen reason: FORM_STATE_MUTATION_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### 4b57e2d73c695a41

- source: django_oscar
- complexity: MEDIUM
- frozen reason: OBJECT_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### 4d7d61b18dde0ad5

- source: django_oscar
- complexity: MEDIUM
- frozen reason: HTTP_RESPONSE_RETURN
- source resolved: True
- function: json_response
- calls: ['JsonResponse', 'flash_messages.as_dict', 'render_to_string']
- attribute writes: []
- structural primitives: ['CALL_DEPENDENCY', 'VALUE_RETURN']

### 63e7979762bf860b

- source: django_oscar
- complexity: HIGH
- frozen reason: FRAMEWORK_SIGNAL_BASKET_SIDE_EFFECTS_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### 7460029971aad8de

- source: pretix
- complexity: HIGH
- frozen reason: SERVICE_CACHE_OBJECT_SEMANTICS_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### 7bc9603bfbda7dc9

- source: openfisca_france
- complexity: HIGH
- frozen reason: SCALAR_RETURN_LARGE_PARAMETERIZED_FORMULA | AGGREGATE_HELPER_SEMANTICS_OUTSIDE_FROZEN_SCALAR_A2_SCOPE
- source resolved: True
- function: formula_2017_04_01
- calls: ['famille', 'famille', 'famille', 'famille', 'famille', 'famille', 'famille', 'famille', 'famille.any', 'famille.members', 'famille.members', 'famille.sum', 'max_', 'max_', 'nb_enf', 'nb_enf', 'nb_enf', 'not_', 'not_', 'parameters', 'parameters']
- attribute writes: []
- structural primitives: ['CALL_DEPENDENCY', 'VALUE_RETURN']

### 7cf281a33e5781df

- source: pretix
- complexity: MEDIUM
- frozen reason: OBJECT_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### 8048a564541f5408

- source: pretix
- complexity: MEDIUM
- frozen reason: OPERATION_LIST_MUTATION_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### 882c5eae0d8fd4ec

- source: pretix
- complexity: HIGH
- frozen reason: REFUND_OBJECT_SIDE_EFFECTS_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### 8a754dadf1672d0a

- source: pretix
- complexity: HIGH
- frozen reason: PLUGIN_SIGNAL_SET_SEMANTICS_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### 91b2dc32504282fc

- source: django_oscar
- complexity: MEDIUM
- frozen reason: MULTI_STATE_MUTATION_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### a09e038870c9b436

- source: pretix
- complexity: MEDIUM
- frozen reason: CONDITIONAL_STRING_CONSTRUCTION_OUTSIDE_FROZEN_FORMAL_SCOPE
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### a79d9687185720aa

- source: django_oscar
- complexity: HIGH
- frozen reason: MODEL_SAVE_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### b2996c3dd81aca55

- source: pretix
- complexity: MEDIUM
- frozen reason: SESSION_STATE_MUTATION_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### bcb091a940a8d0dd

- source: django_oscar
- complexity: HIGH
- frozen reason: FRAMEWORK_DICT_MUTATION_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### d7f578c3a5f20b8a

- source: pretix
- complexity: MEDIUM
- frozen reason: MULTI_OBJECT_STATE_TRANSITION_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []

### eb12d3a44210a486

- source: pretix
- complexity: HIGH
- frozen reason: NONSCALAR_LIST_SEMANTICS_OUTSIDE_FORMAL_SUBSET
- source resolved: False
- function: UNRESOLVED
- calls: []
- attribute writes: []
- structural primitives: []
