# BIZPROOF V0.11 — Final Scientific Freeze

This directory marks the final closure of the V0.11 scientific
evaluation and paper-evidence campaign.

No new experiment is required by the W21-W23 closure process.

## Final accounting

- External cohort: 90
- Terminalized: 90/90
- Certified: 50
- CERTIFIED_A1: 33
- CERTIFIED_A2: 17
- Unsupported: 38
- Semantic ambiguity: 2

## A2 accounting

- STRICT_CORE: 6
- EXTENDED_TYPED_SUPPORTED: 8
- Deferred finite-set/domain-Enum: 1
- Recovered after original freeze: 2
- Total: 17

The paper matched benchmark remains exactly 14 cases.

The three remaining A2 cases are fully accounted for and intentionally
remain outside the primary comparison.

## Reproducibility

Five full matched-baseline replication rounds produced 349 exact
matches over 350 candidate/tool/budget comparisons.

The single variation was localized to one CrossHair result at the
0.5-second search budget.

Targeted follow-up runs on that case produced:

- CrossHair 0.5 s: 30/30 detections
- CrossHair 2.0 s: 30/30 detections
- errors/UNKNOWN: 0

The frozen article result is preserved as the result of the originally
executed experiment.

## Integrity

`SCIENTIFIC_FREEZE.json` records the final scientific invariants and
hashes of the principal evidence files.

`TRACKED_EVIDENCE_SHA256.json` records SHA-256 checksums for the tracked
evaluation evidence used by the final campaign.

The Git commit and annotated freeze tag provide the repository-level
integrity boundary.
