# BIZPROOF V0.11 — Out-of-primary A2 closure

All 17 `CERTIFIED_A2` candidates are now fully accounted for.

## Partition

- 6 `STRICT_CORE`
- 8 `EXTENDED_TYPED_SUPPORTED`
- 1 deferred finite-set/domain-Enum case
- 2 adapter/mutant pairs recovered after the original freeze

Therefore:

`6 + 8 + 1 + 2 = 17`

The frozen paper benchmark remains exactly 14 cases.

## Candidate 4008a63ee1ef3b44

This candidate already had a valid frozen adapter/mutant pair.
Its interface contains `frozenset[str]` and the domain-specific
`PermissionName` type.

It was deliberately deferred from the frozen 14-case execution.
Its final status is:

`INTENTIONALLY_OUT_OF_PRIMARY_PROTOCOL`

## Candidate 53abfcd7d20a9cd6

The candidate is already `CERTIFIED_A2`.
The `adapt_nbptr` / `mutant_nbptr` pair was recovered after the
original benchmark freeze.

Its interface also contains `dict[str, Any] -> Any`, outside the
generic frozen matched-runner input encoding.

Its final status is:

`INTENTIONALLY_OUT_OF_PRIMARY_PROTOCOL`

## Candidate 972b76d53a12b8ad

The candidate is already `CERTIFIED_A2`.
The RSA/TNS adapter-mutant pair was recovered after the original
benchmark freeze.

Retrospective promotion would violate the frozen anti-bias selection
rule.

Its final status is:

`INTENTIONALLY_OUT_OF_PRIMARY_PROTOCOL`

## Scientific interpretation

None of these three cases is a BIZPROOF certification failure.

Their absence from the 14-case baseline comparison is explained
entirely by frozen protocol scope and provenance timing.

No Hypothesis or CrossHair outcome was used to include or exclude
these candidates.
