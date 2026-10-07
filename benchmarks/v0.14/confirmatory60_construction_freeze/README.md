# BIZPROOF V0.14 — Confirmatory-60 Construction Freeze

This constructor is derived from the prospectively frozen V0.12
external-cohort constructor.

The V0.14 adaptation is intentionally limited to population/design
constraints:

- six projects instead of eighteen source-universe projects;
- all six projects are fixed reserve projects;
- six selected projects rather than twelve;
- ten cases per project;
- sixty total cases rather than one hundred twenty.

The following semantics are inherited unchanged:

- candidate source extraction;
- source-body normalization;
- path exclusions;
- minimum AST-node eligibility;
- historical source-body exclusion;
- within-project duplicate handling;
- source-body SHA-256 identity;
- function-ranking canonical payload and seed;
- project-ranking canonical payload and seed;
- five shape-classification strata and precedence;
- first-pass selection of two candidates per stratum;
- deterministic same-ranking deficit fill;
- global source-body uniqueness.

For the confirmatory design an additional post-construction gate requires
exactly two selected cases in every project × stratum cell. Therefore a
deficit-fill event causes the confirmatory freeze to stop rather than
silently changing the planned stratification.

No BIZPROOF certification engine is imported or executed by this
constructor.

The engine was frozen before this construction artifact.

No confirmatory outcome has been observed.
