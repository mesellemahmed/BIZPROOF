# BIZPROOF V0.5 Rare-Witness Challenge Benchmark

This benchmark is designed to break the ceiling effect observed in V0.4.

It contains 30 fixed business rules across banking, e-commerce, and insurance. Each rule has:

- one correct implementation;
- one realistic rare-witness mutant;
- an analytically known witness density;
- a large bounded domain.

The challenge intentionally separates three questions:

1. Can a method detect a rare business-rule violation under a fixed budget?
2. Can a method prove a correct implementation?
3. What runtime is required?

Search-based baselines are never credited with a proof when they merely fail to find a counterexample.

Families:

- `single_magic`
- `pair_magic`
- `narrow_boundary`
- `guarded_magic`
- `linear_magic`
- `triple_magic`

The catalog is fixed and versioned. No rule is generated during the experiment.
