# BIZPROOF V0.11 Hardened Symbolic Front-End Probe

Function parameters are symbolic inputs. Free names that are not local assignments or declared function parameters are preserved as GLOBAL_NAME binding obligations.

A `SYMBOLIC_FRONTEND_READY` result is NOT a proof and is NOT a certification verdict.

- Attempted candidates: 40
- Ready: 38
- Structural review: 2
- Source mismatches: 0
- Extraction failures: 0
- Distinct binding primitives: 58

## Semantic shapes

- `NAME_RETURN`: 1
- `NONE_RETURN`: 1
- `PASS_STUB`: 1
- `SUBSTANTIVE_EXPRESSION`: 35

## Binding kinds

- `ATTRIBUTE`: 62
- `CALL`: 107
- `GLOBAL_NAME`: 1

## Interpretation boundary

Generated IR and binding obligations are intermediate formal artifacts only. No candidate is reported as PROVED, DISPROVED, or CERTIFIED in this phase.
