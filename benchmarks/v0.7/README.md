# BIZPROOF V0.7 — External Semantic Validation Pilot

V0.7 moves beyond external applicability auditing and verifies a small set of explicit
semantic adapters derived from independently developed business software.

The pilot contains four rules from two locked external systems:

- OpenFisca-France:
  - apprenticeship-tax liability;
  - housing tax after relief.
- Django-Oscar:
  - CountCondition partial-satisfaction boundary;
  - CountCondition satisfaction threshold.

## Scientific claim boundary

A `PROVED` result in V0.7 means:

> the tracked scalar adapter satisfies its tracked business contract over the declared
> BIZPROOF input domain.

It does **not** mean that BIZPROOF has proved the full original OpenFisca or Django-Oscar
function end-to-end.

Each case records:

- the external repository commit;
- source file and symbol;
- source anchors;
- an external test/YAML evidence file;
- the exact adapter operations;
- representation changes, if any;
- the correct adapter contract;
- a secondary injected mutant used only to validate counterexample sensitivity.

The mutation experiment is secondary evidence and is never treated as external validity.
