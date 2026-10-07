# BIZPROOF V0.14 — Prospective Confirmatory-60 Campaign

This checkpoint freezes the complete confirmatory execution and
statistical-analysis protocol before any confirmatory outcome is
observed.

Frozen before execution:

- V0.14 engine;
- deterministic cohort construction procedure;
- six-project / sixty-case prospective cohort;
- exact scientific source bytes;
- case identities;
- evaluation order;
- confirmatory runner;
- statistical plan;
- analysis implementation.

Primary endpoints:

1. `(CERTIFIED_A1 + CERTIFIED_A2) / 60`;
2. `CERTIFIED_A2 / 60`.

Both endpoints use Wilson 95% confidence intervals.

No p-value or binary success threshold is predeclared because this
campaign estimates prospective certification coverage rather than
testing superiority over another method.

Infrastructure errors remain separate from `UNSUPPORTED`.

The denominator remains fixed at 60.

No case substitution, early stopping, engine retuning, threshold
retuning or candidate-specific exception is permitted.

The runner has at-most-once semantics:

- a case with a durable raw record is never executed again;
- completed cases cannot be replayed during resume;
- if execution is interrupted after a case starts but before a raw
  record becomes durable, that case is classified as
  `INFRA::InterruptedExecution`;
- at most two process-level resumes are permitted.

Runtime observations are descriptive only.

The frozen analyzer cannot run until raw evidence is marked
`RAW_FROZEN`.

At this protocol freeze:

- confirmatory cases frozen: 60/60;
- confirmatory cases executed: 0/60;
- confirmatory outcomes observed: 0.
