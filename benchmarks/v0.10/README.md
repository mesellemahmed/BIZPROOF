# BIZPROOF V0.10 — Evidence-Carrying Certification Pipeline

V0.10 turns the validated V0.7–V0.9 evidence into a reviewer-facing certification bundle.

A semantic slice receives `CERTIFIED` only when all of the following agree:

1. the external repository commit equals the frozen V0.6.2 lock;
2. the external source file and adapter exist and their hashes are recorded;
3. V0.7 proves the adapter contract and disproves the controlled mutant with replay;
4. V0.8 observes zero source/adaptor mismatches and detects the controlled mutant;
5. V0.9 proves symbolic external/adaptor equivalence and disproves the mutant;
6. cross-version provenance fields and file hashes are consistent.

Outputs:

- one JSON certificate per semantic slice;
- a canonical SHA-256 digest for each certificate;
- `results/index.json`;
- `results/summary.json`;
- `results/REVIEWER_REPORT.md`.

`CERTIFIED` applies to the selected semantic slice and declared domain. It is not an
end-to-end certification of OpenFisca-France or Django-Oscar.


## Frozen evidence snapshots

V0.10.1 freezes the exact V0.7, V0.8 and V0.9 evidence used by the
certification pipeline under `benchmarks/v0.10/evidence/`.

The original milestone result directories are restored from their
respective release tags (`v0.7.0`, `v0.8.0`, `v0.9.0`) and are no
longer used as mutable inputs to V0.10 certification.

This separates historical milestone artifacts from certification-time
evidence and prevents later reproduction runs from silently changing
the evidence underlying an issued certificate.
