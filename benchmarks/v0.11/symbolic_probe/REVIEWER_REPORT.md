# BIZPROOF V0.11 Symbolic Front-End Probe

This phase tests structural translation into a conservative BSIR skeleton for the preregistered F0/F1 candidates.

A `SYMBOLIC_FRONTEND_READY` result is NOT a proof and is NOT a certification verdict. It only means the selected function can be represented by the current structural front-end while leaving external calls/attributes as explicit binding obligations.

- Attempted candidates: 40
- Ready: 38
- Structural review: 2
- Source mismatches: 0
- Extraction failures: 0
- Distinct binding primitives: 57

## Most recurrent binding primitives

- `CALL:foyer_fiscal` — 13 candidates / 44 occurrences
- `CALL:individu` — 8 candidates / 39 occurrences
- `ATTRIBUTE:name` — 4 candidates / 5 occurrences
- `CALL:not_` — 3 candidates / 6 occurrences
- `CALL:min_` — 3 candidates / 4 occurrences
- `CALL:where` — 3 candidates / 3 occurrences
- `ATTRIBUTE:code` — 2 candidates / 3 occurrences
- `ATTRIBUTE:rate` — 2 candidates / 3 occurrences
- `ATTRIBUTE:age_max` — 2 candidates / 2 occurrences
- `ATTRIBUTE:chomeur` — 2 candidates / 2 occurrences
- `ATTRIBUTE:emploi_salarie_domicile` — 2 candidates / 2 occurrences
- `ATTRIBUTE:full_id` — 2 candidates / 2 occurrences
- `ATTRIBUTE:taux` — 2 candidates / 2 occurrences
- `CALL:menage` — 2 candidates / 2 occurrences
- `CALL:period` — 2 candidates / 2 occurrences
- `ATTRIBUTE:formation` — 1 candidates / 2 occurrences
- `ATTRIBUTE:gross` — 1 candidates / 2 occurrences
- `ATTRIBUTE:metropole` — 1 candidates / 2 occurrences
- `ATTRIBUTE:net` — 1 candidates / 2 occurrences
- `ATTRIBUTE:plafond` — 1 candidates / 2 occurrences

## Interpretation boundary

The generated IR and binding catalog are engineering evidence for subsequent contract/domain construction. No candidate is reported as PROVED, DISPROVED, or CERTIFIED in this phase.
