# V0.11 paper-results snapshot

## RQ1 — External generalization

- Cohort: 90 candidates.
- Certified: 50/90.
- CERTIFIED_A1: 33.
- CERTIFIED_A2: 17.
- Unweighted certification yield: 55.556%.
- Weighted certification yield: 45.904%.
- Unsupported: 38.
- Semantic ambiguity: 2.

## RQ2 — Structural variation

See `results_by_source.csv`,
`results_by_complexity.csv`, and
`weighted_breakdowns.json`.

## RQ3 — Matched baseline comparison

The predeclared matched comparison contains
14 frozen A2 projections:

- BIZPROOF: 14/14 mutants formally disproved;
  14/14 correct projections formally established
  by frozen V0.11 evidence.
- Hypothesis: 14/14 mutants detected with
  100, 1,000, and 10,000-example budgets.
- CrossHair: 5/14 mutants detected at 0.5 s
  per condition and 7/14 at 2.0 s.

These outcomes must not be interpreted as a
direct runtime race: the methods provide
different guarantee levels.

## RQ4 — Certification boundary

V0.11 contains 38 unsupported candidates and
2 semantic ambiguities.

`unsupported_taxonomy_preliminary.csv` is a
traceable keyword-derived first taxonomy.
It must be manually reviewed before its
category counts are quoted in the paper.
