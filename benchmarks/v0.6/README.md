# BIZPROOF V0.6 — External Business Rule Corpus

V0.6 evaluates BIZPROOF against independently developed Python systems.

The source code is **not vendored** into this repository. Each external repository is cloned
into `external_sources/v0.6/`, which is ignored by Git. The exact resolved commit SHA is
recorded in `benchmarks/v0.6/LOCK.json` and committed with the experiment.

Selected systems:

- OpenFisca-France — tax and social-benefit legislation as code.
- Django-Oscar — domain-driven e-commerce.
- pretix — ticketing, pricing, quotas, orders, and payments.

The first V0.6 experiment is an **eligibility and evidence audit**. It does not silently
discard unsupported functions. Every business-relevant function is classified as one of:

- `DIRECT_CANDIDATE`: structurally close to the current BIZPROOF supported subset.
- `ADAPTATION_REQUIRED`: potentially verifiable after explicit scalar/interface adaptation.
- `UNSUPPORTED`: contains constructs currently outside the supported verifier semantics.

The results are committed under `benchmarks/v0.6/results/`.
