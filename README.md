# BIZPROOF

**Evidence-Carrying Business-Semantic Validation of Software Systems**

BIZPROOF is a research prototype for validating whether executable software behavior conforms to business rules that can be understood and approved by non-developers.

## V0.1.1 verifier-hardening principles

The public verdict space is intentionally limited to:

- `PROVED`
- `DISPROVED`
- `UNKNOWN`

`UNKNOWN` is mandatory whenever BIZPROOF cannot justify a sound verdict.

The V0.1.1 hardening release adds:

- explicit satisfiability checking of business preconditions;
- rejection of vacuous proofs;
- concrete replay of every symbolic counterexample;
- symbolic/concrete result consistency checks;
- path-coverage checks;
- rejection of decorated functions;
- rejection of division and modulo in the symbolic subset;
- rejection of external calls and unsupported constructs;
- Z3 exception containment;
- explicit reason codes for `UNKNOWN`;
- differential verification between finite enumeration and Z3;
- clarified evidence fields (`postcondition_satisfied`, `replay_validated`).

## Soundness rule

A symbolic counterexample is never exposed as `DISPROVED` until it has been replayed on the concrete Python implementation and has been confirmed to satisfy the business precondition and violate the business postcondition.

If symbolic and concrete execution disagree, the verdict is `UNKNOWN`.

## Verification condition

For precondition `P`, implementation semantics `S`, and postcondition `Q`, BIZPROOF searches for:

```text
P ∧ S ∧ ¬Q
```

Before verification, it separately checks that the declared input domain and `P` are satisfiable. Therefore, an unsatisfiable precondition never produces a vacuous `PROVED` result.

## Supported symbolic Python subset

- pure functions;
- `int` and `bool` inputs;
- simple local assignments;
- `if` / `else`;
- `return`;
- arithmetic `+`, `-`, `*`;
- comparisons;
- Boolean `and`, `or`, `not`;
- conditional expressions.

The symbolic backend intentionally returns `UNKNOWN` for:

- loops;
- function or method calls;
- decorators;
- object mutation;
- I/O;
- networking;
- reflection;
- dynamic execution;
- division and modulo;
- unsupported truthiness coercions;
- incomplete path coverage.

## Docker workflow

```bash
./run.sh build
./run.sh check
./run.sh test
./run.sh demo-enum
./run.sh demo-z3
./run.sh demo-vacuous
./run.sh differential
```

Expected core invariants:

```text
defective implementation  -> DISPROVED
correct implementation    -> PROVED
unsupported loop          -> UNKNOWN
vacuous precondition      -> UNKNOWN
unsupported decorator     -> UNKNOWN
unsupported division      -> UNKNOWN
unsupported external call -> UNKNOWN
```

Expected differential summary:

```text
Differential verification
Contracts checked: 3
Enum/Z3 verdict disagreements: 0
Invalid Z3 counterexamples after concrete replay: 0
Unexpected UNKNOWN verdicts: 0
PASS
```

## Security note

The finite enumeration backend imports and executes the target Python module. Research experiments must therefore run inside isolated containers with untrusted networking and host access disabled. The symbolic backend itself does not execute source code until concrete replay of a candidate counterexample.

## Research scope

V0.1.1 is a verifier-hardening milestone. It is not yet the full multi-language BSIR architecture. The next scientific step is to validate semantic fidelity and proof coverage on a controlled benchmark before expanding language coverage.

## V0.2 differential semantic validation

V0.2 adds deterministic differential fuzzing for the supported Python semantic subset.
The generator produces correct and intentionally mutated implementations from six template families:

- threshold comparisons;
- Boolean conjunction/disjunction;
- arithmetic assignments;
- conditional branches with Boolean inputs;
- nested branches;
- early-return control flow.

Each generated contract is checked independently by finite enumeration and Z3. The finite bounded domain acts as the reference oracle. Every Z3 counterexample must still pass concrete replay.

Run the 1,000-case campaign with:

```bash
./run.sh fuzz-differential
```

The campaign passes only if all of the following are zero:

- oracle-label mismatches;
- enum/Z3 verdict disagreements;
- false `PROVED` verdicts;
- false `DISPROVED` verdicts;
- unexpected `UNKNOWN` verdicts;
- invalid concrete replays;
- unexpected crashes.

The deterministic seed is `20260923`. Generated artifacts and result files are excluded from Git and can be reproduced from the seed.


## V0.4 — Baseline comparison

V0.4 compares BIZPROOF on the fixed V0.3 business benchmark against two independent baselines:

- Hypothesis property-based testing;
- CrossHair symbolic contract checking.

Run:

```bash
./run.sh baseline-comparison
```

The comparison reports violation-detection rate, false alarms, inconclusive/error cases, runtime, and paired mutant-detection counts. `NO_COUNTEREXAMPLE` from a testing baseline is never reported as a formal proof.


## V0.5 — Rare-Witness Challenge Benchmark

V0.5 addresses the ceiling effect observed in V0.4 by introducing fixed business rules whose mutant behavior differs from the reference behavior only on sparse regions of large bounded domains.

The challenge compares:

- BIZPROOF symbolic verification;
- Hypothesis with 100, 1,000, and 10,000-example budgets;
- CrossHair with 0.5-second and 2.0-second per-condition budgets.

Run:

```bash
./run.sh challenge-benchmark
```

Search-based methods are credited only when they find a counterexample. Absence of a counterexample remains inconclusive.


## V0.6 — External Business Rule Corpus

V0.6 introduces independently developed Python systems to measure external applicability and
coverage of the current verifier semantics.

External repositories are cloned outside the tracked corpus and pinned by commit SHA:

```bash
./run.sh external-acquire
./run.sh external-audit
```

Or run both:

```bash
./run.sh external-corpus
```

Reviewer-facing provenance and audit results are committed under `benchmarks/v0.6/`.
Unsupported external functions remain in the reported denominator.


## V0.7 — External Semantic Validation Pilot

V0.7 validates explicit scalar semantic adapters derived from
locked OpenFisca-France and Django-Oscar business rules.

Command:

./run.sh external-semantic

A V0.7 PROVED result applies to the tracked scalar adapter and
its contract only. It is not an end-to-end proof of the complete
external framework function.


## V0.8 — Source-Executed Adapter Semantic Preservation

V0.8 executes methods extracted directly from the locked external OpenFisca-France and
Django-Oscar source files and differentially compares them with the V0.7 scalar adapters.

Command:

./run.sh adapter-preservation

Zero mismatch is evidence of semantic preservation over the declared deterministic
validation domain. It is not presented as a universal proof outside that domain.


## V0.9 — Symbolic Adapter Equivalence Certification

V0.9 symbolically translates selected semantic slices directly from the locked external
source AST and proves equivalence with the corresponding V0.7 adapter over the declared
BVC domain.

Command:

./run.sh symbolic-equivalence

A PROVED result means that the negated equivalence obligation is UNSAT over the declared
domain. The claim applies to the selected semantic slice, not the complete external framework.


## V0.10 — Evidence-Carrying Certification Pipeline

V0.10 assembles the locked provenance, V0.7 contract-verification evidence, V0.8
source-executed preservation evidence and V0.9 symbolic-equivalence evidence into
mechanically checked reviewer-facing certification bundles.

Command:

./run.sh certification-bundle

Each certificate includes cryptographic hashes for its source, adapter, contract and
evidence layers. CERTIFIED applies to the selected semantic slice and declared domain,
not to the complete external framework.


## V0.11 — External Generalization Study

V0.11 evaluates BIZPROOF on a preregistered, deterministic 90-candidate
cohort sampled from 730 novel STRONG/ADAPTATION_REQUIRED external business-rule
candidates. The design balances the three external systems and three V0.6.2
adaptation-complexity levels.

The static feasibility phase routes each frozen candidate to one of four
engineering paths (`F0`–`F3`). These paths are not proof or certification
verdicts.

Commands:

./run.sh generalization-cohort
./run.sh generalization-feasibility


### V0.11 symbolic front-end probe

The V0.11 symbolic front-end probe attempts conservative structural translation
of all preregistered F0/F1 candidates into a BSIR skeleton. External calls and
attributes are preserved as explicit binding obligations.

Command:

./run.sh generalization-symbolic-probe

`SYMBOLIC_FRONTEND_READY` is not a proof or certification verdict.


### V0.11 semantic hardening and family census

The hardened symbolic front-end distinguishes declared function parameters from
free/global names. Free names become explicit `GLOBAL_NAME` binding obligations.

Trivial stubs/default constant returns are routed to semantic-scope review and
are not counted as direct business-rule formalization.

The family census groups unresolved bindings, explicit-adapter blockers and
controlled-execution blockers into reusable engineering families.

Command:

./run.sh generalization-families


### V0.11 contract and binding skeleton

The Phase-F contract skeleton derives conservative type/context obligations for
all `BINDING_DEFINITION` candidates. It recognizes recurring OpenFisca entity
lookups and semantic-library calls, but all binding semantics and domains remain
explicitly unresolved until validated.

Command:

./run.sh generalization-contract-skeleton


### V0.11 semantic source evidence

Phase G separates structural usage constraints from source-backed semantic
evidence. Contextual types are never promoted to semantic types automatically.

All semantic types remain explicitly unresolved until a semantic contract is
defined and validated.

Command:

./run.sh generalization-semantic-evidence


### V0.11 source symbol tracing

Phase H recursively traces semantic-contract symbols through the locked source
snapshots. Local definitions, re-exports, dependency boundaries, callable
parameters, builtins and unresolved/ambiguous paths are recorded explicitly.

Tracing a definition establishes provenance only. It does not resolve semantic
types or certify a business contract.

Command:

./run.sh generalization-symbol-trace


### V0.11 contract readiness

Phase I converts source-trace outcomes into explicit contract-authoring queues:
local-source contracts, parameter protocols, external dependency locks, and
trace-review cases.

No semantic type or certification verdict is produced by this phase.

Command:

./run.sh generalization-contract-readiness


### V0.11 Python name-resolution hardening

Phase J applies Python lexical and module-level name-resolution precedence to the
170 binding occurrences. Function parameters shadow globals/imports, method
calls retain receiver context, and the last relevant module-level binding is
treated as authoritative.

This phase improves provenance precision only. Semantic types and semantic
contracts remain unresolved.

Command:

./run.sh generalization-name-resolution


### V0.11 protocol and dependency closure

Phase K groups parameter-call and parameter-method protocols, distinguishes
Python standard-library boundaries from external dependencies, discovers source
dependency constraints, and analyzes local assignments/definitions transitively.

No semantic type or semantic contract is validated in this phase.

Command:

./run.sh generalization-protocol-closure


### V0.11 certification-engine safety audit

Phase L inventories the exact V0.9/V0.10 proof and certification implementation
before V0.11 semantic contracts reuse it. It records the certificate reporter,
hashing helper, callsites, proof-related functions and relevant tests.

No semantic contract or new certification verdict is produced.

Command:

./run.sh generalization-certification-audit


### V0.11 certification negative-path hardening

Phase M hardens certification against missing artifact files and reduced FAILED
evidence. Critical artifact hashes fail closed without FileNotFoundError after
explicit existence checks, and the certification reviewer report tolerates
incomplete negative evidence.

The objective `NOT_CERTIFIED_SEMANTIC_AMBIGUITY` policy is frozen before
V0.11 terminal-outcome assignment.

No semantic contract is certified by Phase M itself.


### V0.11 first semantic contract batch

Phase N validates the first source-backed semantic primitive contract, validates
the observed callable protocol shapes independently, resolves the exact local
binding kind of `nb_enf`, locks the Python-3.12 OpenFisca-Core dependency from
the corpus lockfile, and advances `not_`, `min_`, `where`, and `ZERO_DISCOUNT`
through their transitive provenance.

Structural protocol validation does not imply validation of return-value
semantics or business-rule certification.

Command:

./run.sh generalization-semantic-contract-batch


### V0.11 semantic contract closure

Phase O validates the source-level aliases from OpenFisca-Core to the exact
NumPy runtime selected by the locked OpenFisca-France environment and validates
a bounded exhaustive semantic contract for `nb_enf`.

The NumPy environment is reconstructed with hashes from `uv.lock`. Candidate
certification remains separate from primitive semantic-contract validation.

Command:

./run.sh generalization-semantic-contract-closure
