# Experimental Evaluation

## Experimental Objectives

The evaluation investigates four research questions.

**RQ1 — External generalization.**
To what extent can BIZPROOF certify business semantics extracted from previously unseen software systems?

**RQ2 — Structural variation.**
How does certification coverage vary across software sources and adaptation-complexity levels?

**RQ3 — Matched baseline comparison.**
How does BIZPROOF compare with Hypothesis and CrossHair when all methods operate on the same frozen program projection, mutant, and input representation?

**RQ4 — Certification boundary.**
Which classes of business logic remain outside the frozen BIZPROOF certification semantics?

---

## Experimental Protocol

The evaluation is based on the frozen BIZPROOF V0.11 checkpoint.

The external-generalization cohort contains **90 candidates**, stratified across three software sources and three adaptation-complexity levels. Candidate selection and terminal outcomes were frozen before the paper-level baseline experiments.

The terminal certification outcomes are:

- `CERTIFIED_A1`: **33** candidates;
- `CERTIFIED_A2`: **17** candidates;
- `NOT_CERTIFIED_UNSUPPORTED`: **38** candidates;
- `NOT_CERTIFIED_SEMANTIC_AMBIGUITY`: **2** candidates.

A total of **50/90 candidates** therefore reached a certification state.

The evaluation deliberately preserves unsupported and ambiguous candidates rather than extending the semantic scope after observing the sample. This prevents post-hoc inflation of the reported certification yield.

---

## RQ1 — External Generalization

BIZPROOF certified **50/90 candidates**, corresponding to an unweighted certification yield of **55.556%**.

The Wilson 95% confidence interval for this unweighted proportion is **45.27%–65.38%**.

The frozen population-weighted certification estimate is **45.904%**.

No confidence interval is reported for the weighted estimate because the frozen V0.11 protocol did not define a design-based variance estimator.

The result demonstrates substantial but incomplete external generalization. BIZPROOF successfully certifies a majority of the sampled candidates while preserving an explicit frontier for unsupported or semantically ambiguous cases.

---

## RQ2 — Variation Across Sources

Certification coverage varies considerably between the three evaluated software sources.

| Source | Certified | Total | Yield |
|---|---:|---:|---:|
| OpenFisca France | 25 | 30 | 83.3% |
| Django-Oscar | 14 | 30 | 46.7% |
| Pretix | 11 | 30 | 36.7% |

OpenFisca France exhibits the highest certification coverage, whereas Pretix exhibits the lowest.

An exploratory Pearson chi-square analysis of the frozen 90-candidate cohort produced:

- χ² = **14.670**;
- df = **2**;
- p = **0.000652**;
- Cramer's V = **0.404**.

This association is descriptive of the frozen cohort and is not interpreted as population-level causal evidence.

---

## RQ2 — Variation Across Structural Complexity

Certification also varies with adaptation complexity.

| Complexity | Certified | Total | Yield |
|---|---:|---:|---:|
| LOW | 25 | 30 | 83.3% |
| MEDIUM | 13 | 30 | 43.3% |
| HIGH | 12 | 30 | 40.0% |

The LOW-complexity stratum is therefore substantially more compatible with the frozen certification semantics than the MEDIUM and HIGH strata.

The exploratory association between complexity and certification produced:

- χ² = **14.130**;
- df = **2**;
- p = **0.000854**;
- Cramer's V = **0.396**.

Again, these statistics describe the frozen cohort rather than establishing causality.

---

## RQ3 — Matched Baseline Comparison

A matched comparison was conducted on **14 frozen A2 projections**.

The compared methods received the same frozen correct projection and mutant under the matched protocol.

The primary comparison is:

| Method | Budget | Mutants detected | Detection rate |
|---|---:|---:|---:|
| BIZPROOF | frozen formal evidence | 14/14 | 100.0% |
| Hypothesis | 100 examples | 14/14 | 100.0% |
| Hypothesis | 1,000 examples | 14/14 | 100.0% |
| Hypothesis | 10,000 examples | 14/14 | 100.0% |
| CrossHair | 0.5 s/condition | 5/14 | 35.7% |
| CrossHair | 2.0 s/condition | 7/14 | 50.0% |

BIZPROOF and Hypothesis both expose all frozen mutants in this matched benchmark.

The interpretation, however, is fundamentally different.

For BIZPROOF, the frozen A2 evidence contains both:

1. formal equivalence evidence for the accepted correct projection; and
2. formal disproof of the corresponding mutant.

Hypothesis performs counterexample search. Detecting a mutant is strong evidence of sensitivity, but the absence of a discovered counterexample on the correct implementation is not a proof of correctness.

CrossHair performs symbolic assertion analysis under a finite time budget. Its mutant-detection rate increases from **35.7%** at 0.5 seconds to **50.0%** at 2 seconds, showing clear budget sensitivity on this benchmark.

Runtime values are therefore reported only descriptively. The tools provide different guarantee levels, so wall-clock time is not treated as a direct ranking criterion.

---

## RQ4 — Certification Boundary

Among the 90 external candidates, **38** terminate as unsupported and **2** as semantic ambiguities.

The final evidence-normalized taxonomy of the 38 unsupported candidates is:

| Limitation category | Count | Share |
|---|---:|---:|
| Framework or external effects | 19 | 50.0% |
| Non-scalar or reference semantics | 10 | 26.3% |
| Nested or higher-order logic | 3 | 7.9% |
| Other frozen-scope limitation | 2 | 5.3% |
| Stateful or side-effecting logic | 2 | 5.3% |
| Binding or unresolved domain | 1 | 2.6% |
| Complex-container semantics | 1 | 2.6% |

The dominant limitation is therefore interaction with framework or external-effect semantics, accounting for **half of all unsupported cases**.

The second-largest category is non-scalar or reference-oriented semantics, representing **26.3%** of unsupported candidates.

Together, these two categories account for **29/38 unsupported cases (76.3%)**.

These categories describe limitations of the frozen BIZPROOF certification semantics. They must not be interpreted as defects in the source systems.

---

## Discussion

The evaluation reveals a clear distinction between **bug finding** and **semantic certification**.

On the matched mutation benchmark, Hypothesis is already highly effective: it detects all 14 selected mutants even at the smallest evaluated budget. BIZPROOF should therefore not be positioned as merely a stronger mutation detector.

Its differentiating contribution is the ability to associate mutant refutation with formal evidence for the accepted business-semantic projection.

The external-generalization results also reveal the current structural boundary of the framework. Certification is strongest for declarative and low-complexity logic and decreases substantially when semantics depend on framework behavior, stateful interactions, references, non-scalar outputs, or more complex program structure.

This boundary is scientifically useful because BIZPROOF reports unsupported semantics explicitly rather than silently approximating them.

The results therefore support two complementary conclusions:

1. BIZPROOF provides strong formal evidence on the subset of business logic captured by its certification semantics.
2. Extending this semantic subset toward framework-aware, stateful, and non-scalar behavior is the main research direction required to improve external coverage.

---

## Threats to Validity

### Construct Validity

Certification yield measures the proportion of candidates for which BIZPROOF produces evidence satisfying the frozen certification criteria. It is not a measure of general software correctness or software quality.

Similarly, BIZPROOF proof outcomes are not semantically equivalent to Hypothesis `NO_COUNTEREXAMPLE` outcomes or budget-limited CrossHair outcomes.

### Internal Validity

Candidate selection, terminal outcomes, the V0.11 source checkpoint, and the matched baseline protocol were frozen before successful baseline execution.

Baseline failures, misses, and timeouts were not used to remove candidates.

Two additional harness pairs were discovered after the original selection freeze. They were documented but were not promoted into the primary matched comparison.

A mechanical runner error initially assumed a fixed candidate count. It was corrected before successful baseline execution so that the runner derives the expected cohort size from the frozen protocol.

### External Validity

The evaluation contains 90 candidates from three software systems. This diversity provides meaningful external validation but does not establish universal performance across all frameworks, programming languages, business domains, or repository structures.

The weighted yield is therefore interpreted relative to the frozen V0.11 sampling frame.

### Statistical Conclusion Validity

The unweighted yield is accompanied by a Wilson confidence interval.

No confidence interval is reported for the weighted yield because no design-based variance estimator was frozen.

The source and complexity chi-square analyses are exploratory cohort-level analyses and are not interpreted causally.

The matched baseline includes only 14 candidates, so percentages must be interpreted together with their absolute counts.

### Baseline Validity

BIZPROOF, Hypothesis, and CrossHair provide different guarantees.

Hypothesis performs generated counterexample search.

CrossHair performs budgeted symbolic analysis.

BIZPROOF provides formal evidence within its supported semantic slice.

Equal mutation-detection rates therefore do not imply equivalent verification strength.

### Mutation Validity

The comparison uses frozen mutants associated with the A2 projections. These mutants provide a controlled sensitivity benchmark but do not cover every realistic business-logic fault.

Future work should include broader mutation operators and independently seeded defects.

### Taxonomy Validity

The final unsupported-case taxonomy is derived from frozen candidate-level `reason_code` and reviewed reason evidence.

Although this is stronger than the preliminary keyword taxonomy, categories still aggregate heterogeneous program behaviors. The underlying candidate-level evidence should therefore remain available with the published evaluation artifacts.

---

## Summary of Empirical Findings

The frozen V0.11 evaluation establishes the following principal results:

1. BIZPROOF certifies **50/90 external candidates**, corresponding to **55.556% unweighted coverage** and **45.904% weighted coverage**.
2. Certification varies substantially across both software sources and adaptation-complexity strata.
3. On the 14-case matched mutation benchmark, BIZPROOF and Hypothesis both detect **14/14 mutants**, while CrossHair detects **5/14** at 0.5 seconds and **7/14** at 2 seconds.
4. BIZPROOF's principal advantage in this comparison is not greater mutant detection than Hypothesis, but the availability of formal correctness/equivalence evidence alongside mutant refutation.
5. **76.3% of unsupported cases** arise from framework/external-effect semantics or non-scalar/reference semantics, identifying the primary technical frontier for subsequent versions of the framework.
