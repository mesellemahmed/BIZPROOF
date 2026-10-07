# Experimental protocol — verifier-hardening stage

## Gate before scientific benchmarking

No large-scale experiment starts until all of the following are green:

```bash
./run.sh build
./run.sh check
./run.sh test
./run.sh demo-enum
./run.sh demo-z3
./run.sh demo-vacuous
./run.sh differential
```

Required invariants:

- defective -> `DISPROVED`;
- correct -> `PROVED`;
- unsupported -> `UNKNOWN`;
- unsatisfiable precondition -> `UNKNOWN`;
- every symbolic counterexample is concretely replayed;
- zero enum/Z3 disagreements on the supported differential corpus;
- zero invalid replayed counterexamples.

## Primary scientific metrics

- precision;
- recall;
- F1;
- false positive rate;
- false negative rate;
- proof coverage;
- `UNKNOWN` rate;
- counterexample generation rate;
- concrete replay success rate;
- semantic mapping accuracy;
- mutation kill rate;
- runtime and timeout rate.

## Human-study metrics

- validation accuracy;
- false acceptance rate;
- false rejection rate;
- decision time;
- confidence calibration;
- task completion rate.

## Required ablations

- without business semantic projection;
- without symbolic verification;
- without explicit `UNKNOWN`;
- traceability-only;
- testing-only;
- without concrete counterexample replay;
- without business labels.

## V0.2 — Differential Semantic Validation

The V0.2 campaign validates the fidelity of the Python-to-symbolic semantics before any business-domain benchmark is attempted.

Protocol:

1. Generate 1,000 deterministic bounded programs with seed `20260923`.
2. Alternate between semantically correct implementations and intentionally mutated implementations.
3. Cover threshold, Boolean, arithmetic, branch, nested-branch, and early-return templates.
4. Evaluate every contract with exhaustive finite enumeration.
5. Evaluate the same contract with the Z3 symbolic backend.
6. Replay every Z3 counterexample on the concrete Python implementation.
7. Compare Z3 verdicts against the finite oracle.
8. Fail the campaign on any disagreement, unexpected `UNKNOWN`, invalid replay, label mismatch, or crash.

Primary validity criterion:

```text
FalseProofRate = 0
```

The generated corpus is deterministic and reproducible from the recorded seed. Generated source and contract files are experiment artifacts and are not committed to the repository.
