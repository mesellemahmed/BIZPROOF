# Threats to Validity

## Construct Validity

Certification yield measures the proportion of candidates for which BIZPROOF can produce evidence satisfying its frozen certification criteria. It must not be interpreted as the proportion of all business logic that is correct, nor as a generic measure of software quality.

The matched baseline experiment evaluates mutation detection and the nature of the conclusions produced by each method. BIZPROOF proof results are therefore not semantically equivalent to Hypothesis `NO_COUNTEREXAMPLE` outcomes or budget-limited CrossHair outcomes.

## Internal Validity

Candidate selection, terminal outcomes, the V0.11 source checkpoint, and the primary matched-comparison tier were frozen before baseline execution. Baseline failures, misses, or timeouts were not used to remove candidates from the primary benchmark.

The same frozen correct projections and mutants were used across the compared methods wherever the matched protocol applied. Two additional harness pairs recovered after the original freeze were documented but were not promoted into the primary matched comparison.

The experimental runner was corrected after a pre-execution mechanical consistency error: it initially assumed a hard-coded cohort size. The correction changed the runner to derive the expected size from the frozen protocol and was committed before successful baseline execution.

## External Validity

The external-generalization cohort contains 90 candidates drawn from three software sources and balanced source/complexity strata. Although this design exposes BIZPROOF to heterogeneous business logic, it does not establish universal performance across all programming languages, frameworks, business domains, or repository structures.

The weighted certification yield should therefore be interpreted relative to the frozen sampling frame represented in V0.11 rather than as a universal software-population estimate.

## Statistical Conclusion Validity

The primary certification results are reported descriptively together with an unweighted Wilson confidence interval. The weighted yield is reported without a confidence interval because a design-based variance estimator was not frozen in the evaluation protocol.

Chi-square tests for source and complexity are exploratory analyses of the frozen cohort. They are not substituted for the sampling-weighted estimates and should not be interpreted as population-level causal evidence.

The matched baseline contains 14 candidates. Consequently, percentage differences correspond to small absolute numbers of mutants and should be interpreted together with the raw counts.

## Baseline Validity

Hypothesis, CrossHair, and BIZPROOF have different objectives and guarantee levels. Hypothesis performs generated counterexample search. CrossHair conducts symbolic analysis under a time budget. BIZPROOF's frozen A2 evidence includes formal equivalence and mutant-disproof claims within its supported semantic slice.

Accordingly, the study does not claim that equal mutation-detection rates imply equivalent verification strength. Runtime measurements are descriptive and are not used to rank the tools.

## Mutation Validity

The comparison uses frozen mutants already associated with the certified projections. These mutations provide a controlled sensitivity benchmark but cannot represent every realistic business-logic defect. Future evaluation should expand the mutation operators and include independently seeded defects.

## Limitation-Taxonomy Validity

The first unsupported-case taxonomy was generated through keyword-based evidence extraction. Its initial category counts are therefore not treated as final results. All 38 unsupported candidates must be reviewed against their frozen evidence before category frequencies are used in the paper.
