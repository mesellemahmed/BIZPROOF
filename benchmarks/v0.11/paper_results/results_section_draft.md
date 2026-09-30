# Experimental Results

## RQ1 — External Generalization

BIZPROOF was evaluated on a frozen external cohort of 90 business-rule candidates. The framework certified 50 candidates, including 33 at level A1 and 17 at level A2. The resulting unweighted certification yield was 55.556% (50/90), with a Wilson 95% confidence interval of 45.3%–65.4%. The frozen population-weighted estimate was 45.904%. No confidence interval is reported for the weighted estimate because the V0.11 evaluation did not freeze a design-based variance estimator.

Among the remaining candidates, 38 were terminalized as `NOT_CERTIFIED_UNSUPPORTED` and 2 as `NOT_CERTIFIED_SEMANTIC_AMBIGUITY`. Importantly, no post-sampling scope extension was used to increase the certification yield.

## RQ2 — Variation Across Sources and Structural Complexity

Certification performance varied substantially across the three external sources. OpenFisca France achieved the highest unweighted certification yield, with 25/30 candidates certified (83.3%). Django-Oscar reached 14/30 (46.7%), whereas Pretix reached 11/30 (36.7%).

The same pattern was visible across adaptation-complexity strata. LOW-complexity candidates achieved 25/30 certifications (83.3%), compared with 13/30 for MEDIUM complexity (43.3%) and 12/30 for HIGH complexity (40.0%).

As an exploratory cohort-level analysis, the association between source and certification outcome produced chi-square=14.670, df=2, p=0.000652, with Cramer's V=0.404. The corresponding association between adaptation complexity and certification outcome produced chi-square=14.130, df=2, p=0.000854, with Cramer's V=0.396. These tests describe the frozen 90-candidate cohort and are not used as weighted population-level inference.

## RQ3 — Matched Baseline Comparison

A predeclared matched comparison was conducted on 14 frozen A2 projections for which the same correct implementation, frozen mutant, compatible input representation, and analysis domain could be supplied to the compared methods.

BIZPROOF formally disproved all 14 frozen mutants and retained formal source-equivalence evidence for all 14 corresponding correct projections.

Hypothesis detected all 14 mutants with each of the evaluated budgets: 100, 1,000, and 10,000 generated examples. This result demonstrates strong counterexample-finding effectiveness on the selected mutants. It does not, however, turn the absence of a discovered counterexample on a correct implementation into a proof of correctness.

CrossHair detected 5/14 mutants (35.7%) at a 0.5-second per-condition budget and 7/14 mutants (50.0%) at 2.0 seconds. The improvement with additional analysis time indicates budget sensitivity on this benchmark.

Runtime measurements are reported descriptively only. BIZPROOF, Hypothesis, and CrossHair do not provide identical semantic guarantees, so their wall-clock values should not be interpreted as a direct performance race.

## RQ4 — Certification Boundary

The frozen evaluation contains 38 unsupported candidates and 2 semantic ambiguities. The current automated evidence scan suggests that unsupported cases are concentrated around stateful, object-oriented, container-rich, and language-semantic constructs. However, the preliminary keyword-derived taxonomy is intentionally not treated as a final empirical result.

A candidate-level manual-review artifact has therefore been generated. Final limitation-category counts should be reported only after this evidence-backed review is completed.

## Main Empirical Finding

The V0.11 evaluation shows that BIZPROOF does not merely act as a counterexample detector. On the matched benchmark, Hypothesis was equally effective at exposing the selected mutants, while BIZPROOF's distinguishing evidence is the combination of formal equivalence for the accepted projection and formal refutation of the corresponding mutant. At the broader generalization level, certification success remains strongly dependent on the structural form of the business logic, with substantially higher coverage on low-complexity and declarative rules than on more structurally demanding cases.
