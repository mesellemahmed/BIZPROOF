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


## Source symbol tracing

`symbol_trace/` recursively follows imported symbols inside the locked external
repositories. External dependencies and parameter/builtin/attribute boundaries
remain explicit. No semantic type is resolved by tracing alone.


## Contract readiness

`contract_readiness/` transforms the 15 semantic-contract candidates into
explicit work queues and records external dependency targets, callable-parameter
protocols, and local-source evidence. All contracts remain unresolved.


## Python name-resolution hardening

`name_resolution/` re-resolves all binding occurrences using Python scope and
module-binding precedence. This removes artificial mixed traces caused by
combining shadowed evidence sources. No semantic type is resolved.


## Protocol and dependency closure

`protocol_closure/` contains callable protocol groups, dependency-lock evidence,
local-source analysis, and the next-action queue. All semantic contracts remain
unresolved.


## Certification-engine safety audit

`certification_gate/` inventories the exact proof/certification implementation
and its negative-path risk surfaces before V0.11 certification attempts.


## Certification negative-path hardening

`certification_negative_paths/` records runtime and static regression evidence
for missing certification artifacts and reduced FAILED certificates.

`terminal_policy/` freezes the objective semantic-ambiguity rule before terminal
outcomes are assigned.


## First semantic contract batch

`semantic_contracts/` records the first validated primitive semantic contract,
structurally validated protocol contracts, exact `nb_enf` binding evidence,
locked OpenFisca-Core provenance traces, and the transitive `ZERO_DISCOUNT`
factory trace.


## Semantic contract closure

`semantic_contract_closure/` contains the exact NumPy lock, delegated primitive
contracts for `not_`, `min_`, and `where`, and the bounded exhaustive `nb_enf`
semantic contract.


## First candidate proof

`candidate_proof_frontier/` contains the 90-candidate semantic-contract frontier,
the first complete candidate source-slice proof, and the extracted A0/A1/A2
protocol context needed for terminal classification.


## First terminal certification

`terminal_certification/` contains the first evidence-carrying V0.11 terminal
certificate, the partial 90-candidate terminal-state ledger, the certification
summary and a reviewer report. Population-level yield remains unavailable until
all 90 candidates have terminal outcomes.
