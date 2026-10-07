# BIZPROOF

**Evidence-Carrying Business-Semantic Validation of Software Systems**

BIZPROOF is a research prototype for validating whether executable software behavior conforms to explicitly represented business semantics.

The system combines source analysis, semantic projection, proof obligations, SMT-based reasoning, concrete replay, semantic mutation, and evidence grading.

This repository contains the implementation, regression tests, experimental artifacts, and reproducibility material associated with the BIZPROOF research project and its first scientific article.

---

## Overview

Traditional software verification techniques are often expressed in terms of low-level program properties, while business requirements are usually formulated at a higher semantic level.

BIZPROOF investigates this gap by constructing an evidence-carrying path from executable source code to bounded formal claims.

The central workflow is:

```text
Business intent
      |
      v
Executable source
      |
      v
AST analysis
      |
      v
Semantic shape
      |
      v
Semantic projection
      |
      v
Boundary abstraction
      |
      v
Observation slicing
      |
      v
Proof closure
      |
      v
SMT certification
      |
      +----------> Concrete replay
      |
      +----------> Semantic mutation
      |
      v
Evidence grading
      |
      v
Bounded certification claim
```

BIZPROOF deliberately follows a **fail-closed** philosophy: when the available semantic or formal evidence is insufficient, the system does not silently promote the result into a proof.

---

# Quick Start

BIZPROOF is designed to be executed through Docker.

## Requirements

You only need:

- Git
- Docker
- Docker Compose

No local Python environment is required.

Clone the repository:

```bash
git clone https://github.com/mesellemahmed/BIZPROOF.git
cd BIZPROOF
```

Build the environment:

```bash
./run.sh build
```

Run the complete validation suite:

```bash
./run.sh check
```

Run the core differential verification:

```bash
./run.sh differential
```

For most users and reviewers, these three commands are sufficient:

```bash
./run.sh build
./run.sh check
./run.sh differential
```

---

# Current Validation Status

The Article-1 repository state currently passes the complete maintained-code validation.

Expected result for:

```bash
./run.sh check
```

is:

```text
Ruff linting        PASS
Ruff formatting     PASS
MyPy                PASS
Pytest              PASS
```

Current regression status:

```text
382 tests passed
```

Expected result for:

```bash
./run.sh differential
```

is:

```text
Differential verification
Contracts checked: 3
Enum/Z3 verdict disagreements: 0
Invalid Z3 counterexamples after concrete replay: 0
Unexpected UNKNOWN verdicts: 0
PASS
```

---

# Verification Principle

For a business precondition \(P\), implementation semantics \(S\), and business postcondition \(Q\), the core symbolic verifier searches for a satisfying assignment to:

```text
P ∧ S ∧ ¬Q
```

A satisfying assignment represents a candidate violation of the declared business property.

Before verification, BIZPROOF separately checks whether the declared input domain and business precondition are satisfiable. This prevents an unsatisfiable precondition from producing a vacuous proof.

A symbolic counterexample is not accepted as a confirmed violation until it has been replayed against the concrete Python implementation.

The replay must confirm that:

1. the declared precondition is satisfied;
2. the concrete implementation executes consistently with the candidate model;
3. the declared postcondition is violated.

If symbolic and concrete execution disagree, the result is not promoted into a confirmed violation.

---

# Core Verification Outcomes

The original verification core uses a deliberately conservative verdict space:

```text
PROVED
DISPROVED
UNKNOWN
```

The meaning is:

- `PROVED`: no violating state was found within the formally declared verification model and domain;
- `DISPROVED`: a violating state was found and validated through concrete replay;
- `UNKNOWN`: the available semantic or formal evidence is insufficient for a justified conclusion.

`UNKNOWN` is therefore a safety outcome, not a failure of the system.

---

# Soundness Principles

BIZPROOF follows several conservative verification rules:

- explicit satisfiability checking of business preconditions;
- rejection of vacuous proofs;
- concrete replay of symbolic counterexamples;
- symbolic/concrete consistency validation;
- explicit detection of unsupported constructs;
- explicit reason codes for inconclusive outcomes;
- differential verification between independent reasoning mechanisms;
- evidence preservation for certification decisions;
- bounded certification claims;
- no silent promotion of unsupported behavior into proof evidence.

---

# Supported Core Symbolic Python Subset

The original symbolic core conservatively supports a restricted Python subset including:

- pure functions;
- `int` inputs;
- `bool` inputs;
- local assignments;
- `if` / `else`;
- `return`;
- arithmetic:
  - `+`
  - `-`
  - `*`
- comparisons;
- Boolean operators:
  - `and`
  - `or`
  - `not`
- conditional expressions.

The core symbolic backend intentionally avoids pretending that arbitrary Python programs are directly SMT-verifiable.

Unsupported behavior is handled conservatively.

Examples include:

- loops;
- unsupported external calls;
- decorators;
- uncontrolled object mutation;
- I/O;
- networking;
- reflection;
- dynamic execution;
- unsupported arithmetic semantics;
- incomplete symbolic path coverage.

Later BIZPROOF stages increase practical applicability through semantic projection, boundary abstraction, observation slicing, controlled execution, and evidence-carrying certification rather than by unsafely extending the original scalar symbolic subset.

---

# BIZPROOF Architecture

The current research architecture can be understood through the following main stages.

## 1. Source Acquisition

The system identifies and freezes the source artifact to be analyzed.

Source identity and provenance are preserved whenever the experiment requires immutable source evidence.

## 2. AST Analysis

Python source code is parsed into an abstract syntax tree.

The AST is used to identify:

- control flow;
- expressions;
- function parameters;
- local assignments;
- calls;
- attributes;
- external bindings;
- potential unsupported constructs.

## 3. Semantic Shape Analysis

Functions are characterized according to their structural and semantic shape.

Examples include:

- scalar control logic;
- structured-container manipulation;
- nested or higher-order computation;
- state/effect-bearing logic;
- externally bound domain logic.

## 4. Semantic Projection

Program behavior relevant to the target business property is projected into a smaller semantic representation.

The objective is not to reproduce the complete program implementation, but to preserve the portion of behavior required by the declared business claim.

## 5. Boundary Abstraction

External frameworks, objects, dependencies, and runtime boundaries are represented explicitly.

A boundary is not automatically assumed to have known semantics.

Unresolved behavior remains an explicit obligation.

## 6. Observation Slicing

The system identifies the portion of program state and behavior that can affect the declared observation or business property.

This reduces irrelevant implementation detail while retaining the evidence required by the target claim.

## 7. Proof Closure

The system evaluates whether all semantic dependencies required for the proof obligation have been resolved.

Missing semantic evidence prevents certification.

## 8. SMT Certification

When the projected semantics fall inside the supported formal model, BIZPROOF constructs and evaluates the corresponding SMT obligation.

## 9. Concrete Replay

Candidate counterexamples are executed against concrete Python behavior before they are accepted as validated violations.

## 10. Semantic Mutation

Controlled mutations are used as an independent mechanism for checking whether the verification process can distinguish intended behavior from deliberately corrupted behavior.

## 11. Evidence Grading

The final claim is bounded by the strength of the available evidence.

BIZPROOF therefore distinguishes between different levels of semantic support rather than treating all successful analyses as equivalent.

---

# Claim-Bounded Certification

A central principle of BIZPROOF is that a certification claim applies only to the semantic object that has actually been justified.

A successful result does **not** automatically imply verification of:

- the complete application;
- every execution environment;
- every external dependency;
- every possible input;
- every behavior of the original framework.

Claims are bounded by factors such as:

- the selected source slice;
- the declared domain;
- semantic contracts;
- source provenance;
- boundary assumptions;
- abstractions;
- observation scope;
- proof obligations;
- replay evidence;
- certification level.

This prevents local evidence from being incorrectly presented as universal program verification.

---

# Repository Structure

```text
BIZPROOF/
│
├── src/
│   └── bizproof/
│       Core BIZPROOF implementation
│
├── tests/
│       Regression and verification tests
│
├── contracts/
│       Business contracts and differential-verification cases
│
├── examples/
│       Executable examples
│
├── benchmarks/
│       Controlled benchmarks, frozen cohorts, results, and evidence
│
├── experiments/
│       Experimental protocols and reproducibility material
│
├── external_sources/
│       External-source material used by selected experiments
│
├── Dockerfile
│       Reproducible execution environment
│
├── compose.yaml
│       Docker Compose configuration
│
├── pyproject.toml
│       Python and validation-tool configuration
│
├── run.sh
│       Main public execution interface
│
└── VALIDATION.json
        Validation metadata
```

The main public interface of the repository is:

```bash
./run.sh
```

Users should normally not need to invoke internal Python modules directly.

---

# Article-1 Empirical Artifact

The primary confirmatory study uses a prospectively frozen cohort of **60 functions** drawn from six open-source Python projects:

- `ansible/awx`
- `django-cms/django-cms`
- `odoo/odoo`
- `openstack/horizon`
- `pretalx/pretalx`
- `wagtail/wagtail`

Ten functions are selected from each project.

The final denominator is therefore:

```text
6 projects × 10 functions = 60 functions
```

The cohort is additionally balanced across five semantic-shape strata.

---

# Semantic-Shape Stratification

The confirmatory cohort uses five predeclared semantic-shape strata.

## S1 — Local Scalar Control

Typical characteristics:

- local scalar assignments;
- comparisons;
- Boolean expressions;
- simple branching.

## S2 — Structured Containers

Typical characteristics:

- dictionaries;
- lists;
- sets;
- tuples;
- structured collection manipulation.

## S3 — Nested / Vector / Higher-Order Logic

Typical characteristics:

- nested transformations;
- aggregation;
- iterator patterns;
- higher-order operations;
- functional composition.

## S4 — State / Effect Logic

Typical characteristics:

- object state mutation;
- persistence;
- updates;
- writes;
- publication;
- effect-bearing operations.

## S5 — External / Domain-Bound Logic

Typical characteristics:

- framework-specific objects;
- externally defined semantics;
- domain-bound calls;
- application-specific dependencies.

The confirmatory cohort contains:

```text
12 functions per stratum
```

for a total of:

```text
5 × 12 = 60 functions
```

---

# Frozen Article-1 Evidence

The final confirmatory-study material is retained under:

```text
benchmarks/v0.14/
```

Important reproducibility directories include:

```text
benchmarks/v0.14/engine_freeze/

benchmarks/v0.14/design_freeze/

benchmarks/v0.14/confirmatory60_construction_freeze/

benchmarks/v0.14/confirmatory60_cohort_freeze/

benchmarks/v0.14/confirmatory60_campaign/
```

These directories contain scientific artifacts and should not be reformatted or rewritten casually.

In particular, frozen source snippets may intentionally:

- depend on framework context;
- omit surrounding imports;
- represent extracted class methods;
- retain original indentation;
- contain code that is not intended to execute as a standalone Python module.

They are experimental data, not maintained BIZPROOF source files.

For this reason, maintained-code quality checks target:

```text
src/
tests/
```

rather than applying source-code linting rules to frozen external research data.

---

# Confirmatory-Study Safeguards

The confirmatory evaluation follows a frozen experimental protocol.

Important safeguards include:

- engine freeze before confirmatory evaluation;
- cohort freeze before outcome observation;
- deterministic cohort construction;
- no case substitution;
- no early stopping;
- no outcome-guided case replacement;
- no engine retuning after freeze;
- no threshold retuning after freeze;
- preservation of raw experimental evidence;
- explicit distinction between scientific outcomes and infrastructure failures;
- immutable source identities for the selected cohort.

These constraints are part of the scientific reproducibility boundary.

---

# Core Controlled Benchmark

BIZPROOF is also evaluated on controlled semantic-validation benchmarks.

The controlled benchmark contains:

```text
300 cases
```

including:

```text
240 semantic mutants
60 non-mutated controls
```

The benchmark is used to evaluate whether BIZPROOF can detect intentionally introduced semantic violations while avoiding false alarms on valid implementations.

Independent comparison mechanisms include property-based testing and symbolic contract checking.

Absence of a discovered counterexample from a search-based baseline is not automatically interpreted as a formal proof.

---

# Differential Verification

BIZPROOF contains an independent differential-validation path for its core symbolic subset.

Run:

```bash
./run.sh differential
```

The differential experiment compares independently derived verification outcomes.

The expected result is:

```text
Differential verification
Contracts checked: 3
Enum/Z3 verdict disagreements: 0
Invalid Z3 counterexamples after concrete replay: 0
Unexpected UNKNOWN verdicts: 0
PASS
```

The finite bounded backend acts as an independent reference mechanism for the supported domain.

---

# Additional Experiments

The repository contains additional research experiments developed during the evolution of BIZPROOF.

Examples include:

- deterministic differential fuzzing;
- controlled business-rule benchmarks;
- baseline comparisons;
- rare-witness experiments;
- external-source applicability studies;
- semantic-adapter preservation;
- symbolic-equivalence experiments;
- evidence-carrying certification;
- external generalization studies;
- semantic-contract construction;
- name-resolution analysis;
- dependency closure;
- source-to-proof certification experiments.

These experiments remain available through `run.sh`.

The minimal end-user workflow, however, remains:

```bash
./run.sh build
./run.sh check
./run.sh differential
```

---

# Using `run.sh`

`run.sh` is the primary interface for BIZPROOF.

The most important commands are:

```bash
./run.sh build
```

Build the Docker environment.

```bash
./run.sh check
```

Run:

- Ruff linting;
- Ruff formatting validation;
- MyPy static analysis;
- the complete Pytest regression suite.

```bash
./run.sh test
```

Run the test suite.

```bash
./run.sh differential
```

Run the core differential-verification experiment.

Additional experiment-specific commands are implemented in the same runner.

---

# Reproducibility

The recommended reproducibility procedure is:

```bash
git clone https://github.com/mesellemahmed/BIZPROOF.git
cd BIZPROOF

./run.sh build
./run.sh check
./run.sh differential
```

The Docker environment provides the intended execution boundary and prevents users from having to reproduce the Python dependency environment manually.

For scientific reproduction of individual experimental campaigns, use the frozen benchmark artifacts and protocols associated with the corresponding experiment.

---

# Security

Some BIZPROOF experiments analyze or execute Python extracted from external software projects.

External source material must therefore be treated as potentially untrusted code.

The recommended execution environment is the provided Docker environment.

Do not execute arbitrary external experimental material directly on the host operating system.

The symbolic backend itself operates on symbolic representations, but selected validation stages can perform concrete execution or concrete replay.

---

# Scientific Interpretation

BIZPROOF should not be interpreted as a universal Python verifier.

It is designed to study the conditions under which business-level semantic claims can be connected to executable implementations through explicit and reviewable evidence.

A successful BIZPROOF certification means that the declared property has been supported under the corresponding:

- source identity;
- semantic projection;
- abstraction;
- verification domain;
- business contract;
- dependency assumptions;
- proof obligations;
- replay evidence;
- certification level.

It does not imply unrestricted correctness of the complete software system.

---

# Research Scope

BIZPROOF investigates several related research questions:

- How can business intent be projected into formal verification obligations?
- How can semantic information be preserved between source code and proof models?
- How can unsupported semantic dependencies be identified explicitly?
- How can formal proof evidence be linked to executable source artifacts?
- How can claims remain bounded by their actual evidence?
- How large is the semantic projection gap in real software?
- Which program shapes prevent automated source-to-proof certification?
- How can static, symbolic, concrete, and provenance evidence be combined safely?

---

# Research Artifact Status

This repository is a research artifact.

It is intended for:

- scientific evaluation;
- reproducibility;
- experimentation;
- research on business-semantic verification;
- source-to-proof certification;
- semantic projection;
- program analysis;
- formal reasoning.

It is not intended to replace:

- conventional testing;
- static analysis;
- runtime verification;
- security auditing;
- full-program formal verification.

These techniques are complementary.

---

# Citation

If you use BIZPROOF, its datasets, experimental methodology, or implementation in academic work, please cite the associated BIZPROOF publication.

Publication metadata will be added after the corresponding article is published.

---

# Authors

**Ahmed Mesellem**  
Corresponding author

**Mohammed Mana**

---

# Minimal Reproduction Summary

For reviewers and users who only want to verify that the repository is operational:

```bash
git clone https://github.com/mesellemahmed/BIZPROOF.git
cd BIZPROOF

./run.sh build
./run.sh check
./run.sh differential
```

Expected final status:

```text
CHECK=PASS
DIFFERENTIAL=PASS
```

If both commands pass, the maintained BIZPROOF implementation and its core differential-verification path are operational in the provided Docker environment.