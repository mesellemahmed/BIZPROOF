# BIZPROOF V0.9 — Symbolic Adapter Equivalence Certification

V0.9 proves symbolic equivalence between selected semantic slices extracted directly
from locked external Python ASTs and the corresponding V0.7 adapters.

For each rule, the solver checks the negated equivalence obligation:

`domain AND (external_semantics != adapter_semantics)`

`PROVED` means this formula is UNSAT.

The deliberately incorrect V0.7 mutant is checked against the same external symbolic
semantics. It must be `DISPROVED`, with a concrete satisfying model.

## Claim boundary

The certification applies only to the explicitly selected semantic slice and the
declared BVC input domain.

For `CountCondition.is_satisfied`, V0.9 proves the post-aggregation threshold predicate
`num_matches >= self.value`. It does not symbolically certify the preceding basket loop;
that loop-to-scalar abstraction was source-executed and differentially validated in V0.8.
