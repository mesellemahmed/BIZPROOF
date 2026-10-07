# BIZPROOF V0.13 — Universal Certification Closure

This development checkpoint connects the generic semantic projection
layer to the existing scalar formal-certification engine.

The closure is generic:

- no candidate IDs;
- no project-specific dispatch;
- no historical TARGETS table;
- no human-authored per-case semantic ADAPTERS.

Supported closure transformations include:

- component-wise scalarization of tuple/list/dict returns;
- parametric abstraction of parameter-rooted attribute observations;
- finite lowering of `all`, `any`, and `sum` over fixed typed tuples;
- explicit state-variable observation for parameter attribute writes;
- structural recording of known external effect calls.

Scientific boundary:

External effect occurrence may be recorded structurally, but BIZPROOF
does not infer the meaning of calls such as `save()`.

Therefore a source containing external effects is capped at A1 in this
checkpoint even when its scalar state-transition obligations receive
A2 evidence.

The external 120-case holdout remains forbidden during development.
