# BIZPROOF V0.11 — Key Empirical Findings

1. External certification:
   - 50/90 certified.
   - 33 A1.
   - 17 A2.
   - 55.556% unweighted yield.
   - 45.904% weighted yield.

2. Source sensitivity:
   - OpenFisca France: 25/30.
   - Django-Oscar: 14/30.
   - Pretix: 11/30.

3. Complexity sensitivity:
   - LOW: 25/30.
   - MEDIUM: 13/30.
   - HIGH: 12/30.

4. Matched baseline:
   - BIZPROOF: 14/14 mutants formally disproved.
   - Hypothesis: 14/14 at all tested budgets.
   - CrossHair: 5/14 at 0.5 s; 7/14 at 2.0 s.

5. Formal distinction:
   - Counterexample detection is not equivalent to proof.
   - BIZPROOF retains formal equivalence evidence for the accepted A2 projections.

6. Main certification frontier:
   - Framework/external effects: 19/38 unsupported.
   - Non-scalar/reference semantics: 10/38.
   - Combined: 29/38 = 76.3%.

7. Statistical evidence:
   - Unweighted yield Wilson CI95: 45.27%–65.38%.
   - Source/certification: chi-square 14.67, p=0.000652, Cramer's V=0.404.
   - Complexity/certification: chi-square 14.13, p=0.000854, Cramer's V=0.396.
