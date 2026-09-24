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
