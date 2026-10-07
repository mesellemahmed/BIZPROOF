# BIZPROOF V0.12 — External Cohort Freeze

## Frozen cohort

This directory freezes the prospective external validation cohort before
any BIZPROOF external certification outcome is observed.

- source-universe projects: 18
- selected projects: 12
- cases per project: 10
- selected cases: 120
- unique selected source bodies: 120
- historical source-body overlap: 0
- cohort SHA-256: `8278187b459ce67d400230b7acce84943968e2ba502e7e9371c53987251f9033`

## Prospective construction

The source snapshot, project ranking, shape classification, function
ranking, duplicate policy and deficit-fill algorithm were committed and
tagged before construction of this cohort.

The same 18 materialized repositories and frozen commits were used for
the successful construction run.

A Windows newline-translation issue was observed only while serializing
already-selected source bodies. The frozen construction algorithm,
selection rules, repositories, project ranking inputs and function
ranking inputs were not modified.

The successful run disabled platform newline translation only for
Path.write_text so that serialized source bodies preserve the exact
Python string whose SHA-256 was already computed by the frozen
algorithm.

## Byte preservation

`cases/*.py` is marked `-text` in `.gitattributes`.

This prevents Git line-ending filters from altering frozen source-body
bytes. Every committed case must therefore preserve its frozen
source SHA-256 exactly.

## Evaluation lock

From this freeze onward:

- all 120 cases must be evaluated;
- evaluation order is frozen;
- no case may be removed or substituted;
- no project may be substituted;
- no V0.12 semantic capability may be added because of an external
  outcome;
- external failures remain V0.12 failures and may motivate V0.13.

## Status

- external cohort: FROZEN
- BIZPROOF external execution: NOT STARTED
- external outcomes observed: NONE
