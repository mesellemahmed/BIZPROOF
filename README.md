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
