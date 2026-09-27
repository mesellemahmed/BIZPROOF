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


## Semantic hardening

Function parameters are modeled as symbolic inputs. Free/global names are
preserved as explicit `GLOBAL_NAME` binding obligations. Stub, `None`, and
constant-return bodies are routed to semantic-scope review.

`families/` groups recurrent unresolved obligations without assigning business
meaning or certification verdicts.


## Contract skeleton

`contracts/` contains conservative per-candidate type/context skeletons and an
unresolved binding registry. Structural type inference is not treated as a
business-domain definition or certification result.


## Semantic source evidence

`semantic_evidence/` records source/import/parameter provenance for binding
occurrences. `context_inferred_type` and `semantic_type` are deliberately
separated. Semantic types remain `UNRESOLVED` in this phase.
