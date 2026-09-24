# BIZPROOF V0.3 Business Validation Benchmark

This benchmark is a fixed, curated synthetic business-rule suite used to test BIZPROOF outside the V0.2 random program generator.

## Scope

- 60 business rules
- 20 banking rules
- 20 e-commerce rules
- 20 insurance rules
- 10 semantic rule families
- 1 correct implementation and 4 semantic mutants per rule
- 300 implementation/contract pairs in the full campaign

## Ground truth

Ground truth is determined independently from the BIZPROOF verifier by a concrete reference oracle implemented in `business_benchmark.py`.

For every generated implementation, the benchmark first compares concrete program outputs with the independent oracle over the complete declared bounded domain. Only then is the expected label assigned:

- equivalent to the oracle -> `PROVED`
- different from the oracle -> `DISPROVED`

BIZPROOF's enumeration and Z3 backends are evaluated against this label.

## Scientific limitation

This benchmark is synthetic and curated. It is independent from verifier execution, but it is not an external industrial benchmark and must not be presented as evidence of industrial generalization.

Its purpose is to bridge the gap between V0.2 random semantic fuzzing and later evaluations on externally sourced software artifacts and human participants.

## Metrics

The benchmark reports:

- false `PROVED` verdicts;
- false `DISPROVED` verdicts;
- enum/Z3 disagreements;
- `UNKNOWN` verdicts;
- concrete replay validity;
- counterexample availability;
- mutation kill rate;
- proof coverage;
- counterexample coverage;
- per-domain results;
- per-family results.
