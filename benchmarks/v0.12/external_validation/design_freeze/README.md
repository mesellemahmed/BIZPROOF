# BIZPROOF V0.12 — Prospective External Validation Design

## Purpose

This phase evaluates whether the V0.12 semantic certification framework
generalizes beyond the historical development and boundary-expansion
cohort.

The historical V0.12 result is frozen at:

- 88/90 certified historical cases;
- 38/38 formerly unsupported historical cases recovered;
- 2 historical ambiguity cases remaining separate.

These historical values must never be changed by external evaluation.

## External cohort

The target external cohort contains 120 functions or methods from
12 projects that were not used in the historical development evidence.

Exactly 10 cases are selected per project.

Project selection and function selection are deterministic and frozen
before any external BIZPROOF certification outcome is observed.

No candidate may be removed, substituted, or reordered because it is
difficult to certify.

## Project-level holdout

Projects used during BIZPROOF development are excluded.

The external evaluation therefore tests project-level transfer rather
than merely new functions from already studied repositories.

## Static shape diversity

Before certification, source functions are grouped using only static
source/dependency characteristics into five shape strata:

1. local scalar/control;
2. structured/container;
3. nested/vector/higher-order;
4. state/effect;
5. binding/external/domain.

The target is two cases from each stratum per project.

If a project lacks two cases in a stratum, the deficit is filled using
the same deterministic hash ranking over the remaining eligible
functions. No outcome information is used.

## No adaptation rule

Once the 120-case cohort is frozen:

- every selected case must be evaluated;
- no early stopping is allowed;
- no post-selection substitution is allowed;
- V0.12 semantic behavior cannot be retuned;
- new candidate-specific exceptions cannot be introduced.

If an external case requires a genuinely new semantic capability, that
case remains a V0.12 external failure or unsupported case. The new
capability belongs to a later version such as V0.13.

## Main endpoints

Primary:

- certification yield over all 120 external cases;
- CERTIFIED_A2 yield over all 120 external cases.

Secondary:

- ambiguity rate;
- unsupported rate;
- per-project yield;
- macro project yield;
- yield by frozen source-shape stratum;
- exact-source replay success;
- mutant-refutation success for A2 attempts;
- failure taxonomy.

95% Wilson intervals are reported for cohort-level proportions.

## Claim boundary

The external cohort can provide evidence of generalization to unseen
projects under the frozen protocol.

It still cannot establish universal semantic coverage of arbitrary
software.
