# BIZPROOF V0.13 — Universal Engine Freeze

This checkpoint freezes the generic BIZPROOF V0.13 certification engine
before prospective external evaluation.

The hardening suite addresses a central scientific risk: the semantic
projection and the formal proof pipeline share source-derived structure.
Therefore the development freeze adds an independent concrete runtime
oracle that is not used by the certification engine.

Hardening gates:

- deterministic repeated certification;
- AST round-trip metamorphic preservation;
- independent concrete execution oracle;
- independently constructed semantic mutants;
- unsupported negative controls;
- full project regression;
- differential backend regression;
- explicit audit against candidate-specific routing.

Important boundary:

The independent development oracles are intentionally case-specific test
oracles. They are NOT engine adapters, are NOT used by source routing,
and are NOT used during external evaluation.

The V0.12 external 120-case holdout remains outcome-untouched at this
freeze.

After this tag, V0.13 engine semantics are frozen for the external
evaluation campaign.
