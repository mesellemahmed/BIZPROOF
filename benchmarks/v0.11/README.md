# BIZPROOF V0.11 — External Generalization Study

The V0.11 cohort is preregistered in `results/cohort.jsonl`.

`feasibility/` contains the static feasibility census over the exact frozen
cohort. Feasibility tiers are routing decisions only:

- F0_DIRECT_SYMBOLIC
- F1_DECLARATIVE_BINDING
- F2_EXPLICIT_ADAPTER
- F3_SEMANTIC_EXECUTION_REVIEW

No F0–F3 label is a certification verdict.


## Symbolic front-end probe

`symbolic_probe/` contains the conservative BSIR translation attempt for the
F0/F1 subset selected by the static feasibility phase. Calls and attributes
are left as explicit binding obligations. The probe never reports proof or
certification verdicts.
