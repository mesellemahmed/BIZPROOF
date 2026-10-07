# BIZPROOF V0.12 — External Evaluation Protocol Freeze

## Purpose

This freeze is created after the prospective 120-case external cohort
has been frozen and before BIZPROOF is executed on any external case.

No external scientific outcome has been observed.

## Fixed denominator

All 120 prospectively selected external cases remain in the primary
denominator.

Cases cannot be removed or substituted because they are difficult,
unsupported, ambiguous, slow, or unsuccessful.

## Evaluation order

Cases are evaluated sequentially in the already-frozen
`evaluation_index` order from 1 through 120.

Semantic failures never trigger early stopping.

## V0.12 lock

The semantic implementation is frozen.

After external evaluation starts, V0.12 cannot receive:

- a new semantic capability;
- a candidate-specific adapter;
- a new projection rule motivated by an external case;
- a threshold change;
- a mutant change motivated by an observed outcome;
- a case or project substitution.

Such improvements belong to V0.13 or later.

## Scientific outcomes

The scientific outcomes are:

- `CERTIFIED_A1`
- `CERTIFIED_A2`
- `AMBIGUOUS`
- `UNSUPPORTED`

Infrastructure failure is tracked separately as
`INFRASTRUCTURE_RETRY_REQUIRED` and is not a scientific success.

A maximum of two infrastructure retries is allowed after the initial
attempt. Retries must preserve the same source, semantic implementation,
semantic configuration and case identity.

## Primary endpoints

External certification yield:

`(CERTIFIED_A1 + CERTIFIED_A2) / 120`

External A2 yield:

`CERTIFIED_A2 / 120`

All negative results remain reportable.

## Interpretation

This experiment provides prospective project-level external validation
evidence under the frozen V0.12 protocol.

It does not establish universal semantic coverage of arbitrary business
software.
