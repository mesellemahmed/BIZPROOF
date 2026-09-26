# BIZPROOF V0.8 — Source-Executed Adapter Semantic Preservation

V0.8 tests whether the scalar adapters introduced in V0.7 preserve the behavior of the
locked external source rules they represent.

The reference behavior is not manually reimplemented. The selected method is extracted
directly from the locked external Python file through the AST, compiled, and executed inside
a minimal controlled harness.

For every rule V0.8 records the locked commit, source-file SHA-256, exact extracted-method
SHA-256 and line range, adapter SHA-256, validation-domain definition, comparison count,
mismatch count, and first mismatch.

The deliberately wrong V0.7 mutant is compared with the same external source as a harness
sensitivity control.

## Claim boundary

Zero mismatches means that no semantic divergence was observed over the declared V0.8
validation domain. Except for the exhaustive Boolean rule, V0.8 is finite deterministic
differential validation, not a universal semantic-equivalence proof.
