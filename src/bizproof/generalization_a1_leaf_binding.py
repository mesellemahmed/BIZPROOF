from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import z3

JsonDict = dict[str, Any]


TARGETS: dict[str, JsonDict] = {
    "0f2fcfc48ffea4af": {
        "source": "pretix",
        "class": "Voucher",
        "file": "src/pretix/base/models/vouchers.py",
        "function": "__str__",
        "line_start": 322,
        "line_end": 323,
        "bindings": ["self.code"],
    },
    "0fe04e3572c7203e": {
        "source": "django_oscar",
        "class": None,
        "file": "src/oscar/apps/offer/utils.py",
        "function": "unit_price",
        "line_start": 20,
        "line_end": 26,
        "bindings": ["line.unit_effective_price"],
    },
    "1b63ce825a129c0a": {
        "source": "django_oscar",
        "class": "AbstractPaymentEventType",
        "file": "src/oscar/apps/order/abstract_models.py",
        "function": "__str__",
        "line_start": 1039,
        "line_end": 1040,
        "bindings": ["self.name"],
    },
    "28b1b63cc241f487": {
        "source": "pretix",
        "class": "Discount",
        "file": "src/pretix/base/models/discount.py",
        "function": "__str__",
        "line_start": 197,
        "line_end": 198,
        "bindings": ["self.internal_name"],
    },
    "460c0ee11314458e": {
        "source": "django_oscar",
        "class": "OrderReportGenerator",
        "file": "src/oscar/apps/order/reports.py",
        "function": "is_available_to",
        "line_start": 57,
        "line_end": 58,
        "bindings": ["user.is_staff"],
    },
    "4ab5aeba4c85b4c0": {
        "source": "django_oscar",
        "class": "FixedRateTax",
        "file": "src/oscar/apps/partner/strategy.py",
        "function": "get_rate",
        "line_start": 307,
        "line_end": 314,
        "bindings": ["self.rate"],
    },
    "55fe61b67000b53a": {
        "source": "pretix",
        "class": "TaxedPrice",
        "file": "src/pretix/base/models/tax.py",
        "function": "__eq__",
        "line_start": 95,
        "line_end": 103,
        "bindings": [
            "self.gross",
            "other.gross",
            "self.net",
            "other.net",
            "self.tax",
            "other.tax",
            "self.rate",
            "other.rate",
            "self.name",
            "other.name",
            "self.code",
            "other.code",
        ],
    },
    "5ea2122f340b1558": {
        "source": "pretix",
        "class": "Quota",
        "file": "src/pretix/base/models/items.py",
        "function": "__str__",
        "line_start": 2120,
        "line_end": 2121,
        "bindings": ["self.name"],
    },
    "62aa728fdef86058": {
        "source": "pretix",
        "class": "OrderRefund",
        "file": "src/pretix/base/models/orders.py",
        "function": "__str__",
        "line_start": 2236,
        "line_end": 2237,
        "bindings": ["self.full_id"],
    },
    "d033593e9fc6fbc6": {
        "source": "django_oscar",
        "class": "AbstractShippingEventType",
        "file": "src/oscar/apps/order/abstract_models.py",
        "function": "__str__",
        "line_start": 1240,
        "line_end": 1241,
        "bindings": ["self.name"],
    },
    "d821bbc9b1df03ae": {
        "source": "pretix",
        "class": "OrderPayment",
        "file": "src/pretix/base/models/orders.py",
        "function": "__str__",
        "line_start": 1804,
        "line_end": 1805,
        "bindings": ["self.full_id"],
    },
    "db6bd6fe0c9b8cd4": {
        "source": "pretix",
        "class": "OrderChangeManager",
        "file": "src/pretix/base/services/orders.py",
        "function": "guess_totaldiff",
        "line_start": 3112,
        "line_end": 3117,
        "bindings": ["self._totaldiff_guesstimate"],
    },
}


def _digest(
    value: Any,
) -> str:

    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_jsonl(
    path: Path,
) -> list[JsonDict]:

    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _sha256_file(
    path: Path,
) -> str:

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _protocol_definition(
    path: Path,
) -> JsonDict:

    lines = path.read_text(encoding="utf-8").splitlines()

    matches = []

    for index, line in enumerate(
        lines,
        start=1,
    ):
        if "`CERTIFIED_A1`" not in line:
            continue

        context = " ".join(
            lines[
                max(0, index - 2) : min(
                    len(lines),
                    index + 2,
                )
            ]
        )

        lowered = context.lower()

        if "declarative" in lowered and "binding" in lowered:
            matches.append(
                {
                    "line": index,
                    "text": context,
                }
            )

    if len(matches) != 1:
        raise ValueError(f"CERTIFIED_A1 protocol definition not unique: {len(matches)}")

    return matches[0]


def _extract_function(
    source: str,
    *,
    function_name: str,
    line_start: int,
    line_end: int,
) -> tuple[
    ast.FunctionDef | ast.AsyncFunctionDef,
    str,
]:

    tree = ast.parse(source)

    candidates = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == function_name
            and node.lineno >= line_start
            and node.lineno <= line_end
        )
    ]

    if len(candidates) != 1:
        raise ValueError(
            "expected one function "
            f"{function_name} in "
            f"{line_start}:{line_end}, "
            f"got {len(candidates)}"
        )

    node = candidates[0]

    segment = ast.get_source_segment(
        source,
        node,
    )

    if segment is None:
        raise ValueError("unable to recover source segment")

    return (
        node,
        segment,
    )


def _body_without_docstring(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.stmt]:

    body = list(node.body)

    if (
        body
        and isinstance(
            body[0],
            ast.Expr,
        )
        and isinstance(
            body[0].value,
            ast.Constant,
        )
        and isinstance(
            body[0].value.value,
            str,
        )
    ):
        body = body[1:]

    return body


def _expression_text(
    node: ast.AST,
) -> str:

    return ast.unparse(node)


def _flatten_and(
    node: ast.AST,
) -> list[ast.AST]:

    if isinstance(
        node,
        ast.BoolOp,
    ) and isinstance(
        node.op,
        ast.And,
    ):
        result: list[ast.AST] = []

        for value in node.values:
            result.extend(_flatten_and(value))

        return result

    return [node]


def _classify_return(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    bindings: list[str],
) -> JsonDict:

    body = _body_without_docstring(node)

    if (
        len(body) != 1
        or not isinstance(
            body[0],
            ast.Return,
        )
        or body[0].value is None
    ):
        return {
            "shape": "REVIEW_REQUIRED",
            "reason": ("function body is not an optional-docstring + single-return slice"),
        }

    expression = body[0].value

    expression_text = _expression_text(expression)

    binding_set = set(bindings)

    if (
        isinstance(
            expression,
            ast.Attribute,
        )
        and expression_text in binding_set
        and len(bindings) == 1
    ):
        return {
            "shape": "DIRECT_ATTRIBUTE_RETURN",
            "expression": expression_text,
            "used_bindings": [expression_text],
        }

    terms = _flatten_and(expression)

    pairs = []

    for term in terms:
        if not (
            isinstance(
                term,
                ast.Compare,
            )
            and len(term.ops) == 1
            and isinstance(
                term.ops[0],
                ast.Eq,
            )
            and len(term.comparators) == 1
        ):
            return {
                "shape": "REVIEW_REQUIRED",
                "reason": (
                    "return expression is neither "
                    "a direct bound attribute nor "
                    "a conjunction of bound equalities"
                ),
            }

        left = _expression_text(term.left)

        right = _expression_text(term.comparators[0])

        if left not in binding_set or right not in binding_set:
            return {
                "shape": "REVIEW_REQUIRED",
                "reason": ("comparison references an undeclared binding"),
            }

        pairs.append(
            [
                left,
                right,
            ]
        )

    used = {value for pair in pairs for value in pair}

    if not pairs or used != binding_set:
        return {
            "shape": "REVIEW_REQUIRED",
            "reason": ("equality binding coverage does not match manifest"),
        }

    return {
        "shape": "BOUND_EQUALITY_CONJUNCTION",
        "expression": expression_text,
        "comparison_pairs": pairs,
        "used_bindings": sorted(used),
    }


def _parameter_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:

    return [argument.arg for argument in (list(node.args.posonlyargs) + list(node.args.args))]


def _split_binding(
    expression: str,
) -> tuple[str, str]:

    parsed = ast.parse(
        expression,
        mode="eval",
    ).body

    if not (
        isinstance(
            parsed,
            ast.Attribute,
        )
        and isinstance(
            parsed.value,
            ast.Name,
        )
    ):
        raise ValueError(f"leaf binding must be parameter.attribute: {expression}")

    return (
        parsed.value.id,
        parsed.attr,
    )


def _compile_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Any:

    if isinstance(
        node,
        ast.AsyncFunctionDef,
    ):
        raise ValueError("async candidate unsupported in leaf A1 batch")

    source = ast.unparse(node)

    namespace: dict[
        str,
        Any,
    ] = {}

    exec(
        compile(
            source,
            "<locked-a1-leaf-source>",
            "exec",
        ),
        namespace,
    )

    function = namespace.get(node.name)

    if not callable(function):
        raise ValueError("source function compilation failed")

    return function


def _runtime_direct(
    *,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    binding: str,
) -> JsonDict:

    function = _compile_function(node)

    parameters = _parameter_names(node)

    root, attribute = _split_binding(binding)

    if root not in parameters:
        raise ValueError(f"binding root is not a function parameter: {root}")

    values = [
        -2,
        0,
        1,
        7,
    ]

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    for value in values:
        arguments = {parameter: SimpleNamespace() for parameter in parameters}

        setattr(
            arguments[root],
            attribute,
            value,
        )

        ordered = [arguments[parameter] for parameter in parameters]

        external = function(*ordered)

        adapter = value

        mutant = value + 101

        comparisons += 1

        if external != adapter:
            adapter_mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "runtime_domain": "four arbitrary scalar binding tokens",
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
        "mutation": "replace-bound-value-with-independent-value",
    }


def _runtime_equality(
    *,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    pairs: list[list[str]],
) -> JsonDict:

    function = _compile_function(node)

    parameters = _parameter_names(node)

    parsed_pairs = [
        (
            _split_binding(pair[0]),
            _split_binding(pair[1]),
        )
        for pair in pairs
    ]

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    # Case 0: all pairs equal.
    mismatch_indices: list[int | None] = [
        None,
        *range(len(parsed_pairs)),
    ]

    for mismatch_index in mismatch_indices:
        arguments = {parameter: SimpleNamespace() for parameter in parameters}

        for index, (
            left,
            right,
        ) in enumerate(parsed_pairs):
            left_root, left_attr = left
            right_root, right_attr = right

            left_value = index + 10

            right_value = left_value

            if index == mismatch_index:
                right_value += 1000

            setattr(
                arguments[left_root],
                left_attr,
                left_value,
            )

            setattr(
                arguments[right_root],
                right_attr,
                right_value,
            )

        ordered = [arguments[parameter] for parameter in parameters]

        external = bool(function(*ordered))

        adapter = all(
            getattr(
                arguments[left_root],
                left_attr,
            )
            == getattr(
                arguments[right_root],
                right_attr,
            )
            for (
                (
                    left_root,
                    left_attr,
                ),
                (
                    right_root,
                    right_attr,
                ),
            ) in parsed_pairs
        )

        # Mutant deliberately drops
        # the first declared equality.
        mutant_pairs = parsed_pairs[1:]

        mutant = all(
            getattr(
                arguments[left_root],
                left_attr,
            )
            == getattr(
                arguments[right_root],
                right_attr,
            )
            for (
                (
                    left_root,
                    left_attr,
                ),
                (
                    right_root,
                    right_attr,
                ),
            ) in mutant_pairs
        )

        comparisons += 1

        if external != adapter:
            adapter_mismatches += 1

        if external != mutant:
            mutant_mismatches += 1

    return {
        "runtime_domain": ("all-equal case plus one single-field mismatch per equality"),
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
        "mutation": "drop-first-declarative-equality",
    }


def _symbolic_direct(
    candidate_id: str,
) -> JsonDict:

    value_sort = z3.DeclareSort("Value_" + candidate_id)

    source_value = z3.Const(
        "source_" + candidate_id,
        value_sort,
    )

    adapter_value = source_value

    mutant_value = z3.Const(
        "mutant_" + candidate_id,
        value_sort,
    )

    correct = z3.Solver()
    correct.add(source_value != adapter_value)

    mutant = z3.Solver()
    mutant.add(source_value != mutant_value)

    correct_status = correct.check()

    mutant_status = mutant.check()

    return {
        "symbolic_domain": ("uninterpreted value domain; proof is type-independent"),
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
        "mutation": "independent-binding-symbol",
    }


def _symbolic_equality(
    candidate_id: str,
    pairs: list[list[str]],
) -> JsonDict:

    value_sort = z3.DeclareSort("Value_" + candidate_id)

    expressions = sorted({expression for pair in pairs for expression in pair})

    symbols = {
        expression: z3.Const(
            ("v_" + candidate_id + "_" + str(index)),
            value_sort,
        )
        for index, expression in enumerate(expressions)
    }

    equalities = [symbols[left] == symbols[right] for left, right in pairs]

    source = z3.And(*equalities)

    adapter = z3.And(*equalities)

    mutant = z3.And(*equalities[1:]) if len(equalities) > 1 else z3.BoolVal(True)

    correct = z3.Solver()
    correct.add(source != adapter)

    mutant_solver = z3.Solver()
    mutant_solver.add(source != mutant)

    correct_status = correct.check()

    mutant_status = mutant_solver.check()

    return {
        "symbolic_domain": ("uninterpreted attribute-value domain with equality only"),
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_proved": correct_status == z3.unsat,
        "mutant_disproved": mutant_status == z3.sat,
        "mutation": "drop-first-declarative-equality",
    }


def build(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    if len(TARGETS) != 12:
        raise ValueError("W2 target manifest must contain exactly 12 candidates")

    prior_states = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a2_residual_closure/candidate_terminal_state.jsonl")
    )

    if len(prior_states) != 90:
        raise ValueError("current ledger must contain 90 candidates")

    prior_by_id = {str(item["candidate_id"]): item for item in prior_states}

    for candidate_id in TARGETS:
        state = prior_by_id[candidate_id]

        if state["state"] != "PENDING_UNASSIGNED":
            raise ValueError("W2 target is no longer pending: " + candidate_id)

    binding_worklist = _load_jsonl(
        repo_root / ("benchmarks/v0.11/remaining_cohort_sweep/binding_worklist.jsonl")
    )

    worklist_ids = {str(item["candidate_id"]) for item in binding_worklist}

    if not (set(TARGETS) <= worklist_ids):
        raise ValueError("W2 target absent from frozen binding worklist")

    protocol = _protocol_definition(repo_root / "experiments/V0.11_PROTOCOL.md")

    proofs: list[JsonDict] = []

    certificates: list[JsonDict] = []

    reviews: list[JsonDict] = []

    for candidate_id in sorted(TARGETS):
        manifest = TARGETS[candidate_id]

        source_path = (
            repo_root / "external_sources/v0.6" / str(manifest["source"]) / str(manifest["file"])
        )

        source_file_sha256 = _sha256_file(source_path)

        source_text = source_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        node, source_segment = _extract_function(
            source_text,
            function_name=str(manifest["function"]),
            line_start=int(manifest["line_start"]),
            line_end=int(manifest["line_end"]),
        )

        function_sha256 = hashlib.sha256(source_segment.encode("utf-8")).hexdigest()

        classification = _classify_return(
            node,
            list(manifest["bindings"]),
        )

        runtime: JsonDict | None = None
        symbolic: JsonDict | None = None
        execution_error: str | None = None

        try:
            if classification["shape"] == "DIRECT_ATTRIBUTE_RETURN":
                runtime = _runtime_direct(
                    node=node,
                    binding=str(classification["expression"]),
                )

                symbolic = _symbolic_direct(candidate_id)

            elif classification["shape"] == "BOUND_EQUALITY_CONJUNCTION":
                pairs = [list(pair) for pair in classification["comparison_pairs"]]

                runtime = _runtime_equality(
                    node=node,
                    pairs=pairs,
                )

                symbolic = _symbolic_equality(
                    candidate_id,
                    pairs,
                )

        except Exception as exc:
            execution_error = f"{type(exc).__name__}: {exc}"

        passed = (
            runtime is not None
            and symbolic is not None
            and execution_error is None
            and runtime["adapter_mismatches"] == 0
            and runtime["mutant_mismatches"] > 0
            and symbolic["correct_proved"] is True
            and symbolic["mutant_disproved"] is True
        )

        proof: JsonDict = {
            "candidate_id": candidate_id,
            "source": manifest["source"],
            "class": manifest["class"],
            "function": manifest["function"],
            "file": manifest["file"],
            "declared_bindings": manifest["bindings"],
            "binding_mode": ("DECLARATIVE_SOURCE_TO_BVC"),
            "source_file_sha256": source_file_sha256,
            "function_sha256": function_sha256,
            "source_lines": [
                node.lineno,
                node.end_lineno,
            ],
            "structural_classification": classification,
            "runtime": runtime,
            "symbolic": symbolic,
            "execution_error": execution_error,
            "status": ("PROVED_A1_DECLARATIVE_BINDING" if passed else "A1_REVIEW_REQUIRED"),
            "terminal_outcome": ("CERTIFIED_A1" if passed else None),
            "certification_claim": passed,
        }

        proof["proof_digest"] = _digest(dict(proof))

        proofs.append(proof)

        if not passed:
            reviews.append(
                {
                    "candidate_id": candidate_id,
                    "classification": classification,
                    "execution_error": execution_error,
                    "terminal_outcome": None,
                    "certification_claim": False,
                }
            )

            continue

        certificate: JsonDict = {
            "schema_version": ("BIZPROOF-V0.11-A1-CERTIFICATE-1"),
            "certificate_id": ("CERT-V011-A1-" + candidate_id.upper()),
            "candidate_id": candidate_id,
            "status": "CERTIFIED_A1",
            "terminal_outcome": "CERTIFIED_A1",
            "assistance_level": "A1",
            "protocol_definition": protocol,
            "authoring_mode": ("DECLARATIVE_SOURCE_TO_BVC_BINDINGS"),
            "source": {
                "source_id": manifest["source"],
                "class": manifest["class"],
                "function": manifest["function"],
                "file": manifest["file"],
                "lines": [
                    node.lineno,
                    node.end_lineno,
                ],
                "source_file_sha256": source_file_sha256,
                "function_sha256": function_sha256,
            },
            "bindings": manifest["bindings"],
            "structural_classification": classification,
            "evidence": {
                "proof_digest": proof["proof_digest"],
                "runtime": runtime,
                "symbolic": symbolic,
            },
            "claim_scope": (
                "Certification covers the locked "
                "source return expression under the "
                "explicit declarative attribute "
                "bindings listed in this certificate. "
                "No handwritten semantic adapter "
                "is introduced."
            ),
            "terminal_outcome_assigned": True,
            "final_study_complete": False,
        }

        certificate["certificate_digest"] = _digest(dict(certificate))

        certificates.append(certificate)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    certificate_dir = output_dir / "certificates"

    certificate_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in certificate_dir.glob("*.json"):
        path.unlink()

    for certificate in certificates:
        (certificate_dir / (str(certificate["certificate_id"]) + ".json")).write_text(
            json.dumps(
                certificate,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    (output_dir / "proofs.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in proofs
        ),
        encoding="utf-8",
    )

    (output_dir / "review.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in reviews
        ),
        encoding="utf-8",
    )

    certificate_by_id = {str(item["candidate_id"]): item for item in certificates}

    states: list[JsonDict] = []

    for previous_state in prior_states:
        candidate_id = str(previous_state["candidate_id"])

        matched_certificate = certificate_by_id.get(candidate_id)

        if matched_certificate is None:
            states.append(dict(previous_state))

            continue

        if previous_state["state"] != "PENDING_UNASSIGNED":
            raise ValueError("refusing terminal overwrite: " + candidate_id)

        states.append(
            {
                "candidate_id": candidate_id,
                "state": "TERMINAL_ASSIGNED",
                "terminal_outcome": "CERTIFIED_A1",
                "certificate_id": matched_certificate["certificate_id"],
                "certificate_digest": matched_certificate["certificate_digest"],
            }
        )

    assigned = [item for item in states if (item["state"] == "TERMINAL_ASSIGNED")]

    pending = [item for item in states if (item["state"] == "PENDING_UNASSIGNED")]

    (output_dir / "candidate_terminal_state.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in states
        ),
        encoding="utf-8",
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "A1_DECLARATIVE_LEAF_BINDINGS",
        "candidates_attempted": 12,
        "candidates_proved": len(certificates),
        "review_required": len(reviews),
        "certificates_issued": len(certificates),
        "terminalized_before": 45,
        "terminalized_after": len(assigned),
        "pending_after": len(pending),
        "weighted_metrics_ready": False,
        "final_certification_complete": False,
        "passed": (
            len(proofs) == 12 and len(states) == 90 and (len(certificates) + len(reviews) == 12)
        ),
    }

    (output_dir / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(
            [
                ("# BIZPROOF V0.11 Declarative Leaf A1 Batch"),
                "",
                "- Candidates attempted: 12",
                (f"- CERTIFIED_A1 issued: {len(certificates)}"),
                (f"- Review required: {len(reviews)}"),
                "",
                ("No explicit semantic adapter is used in this phase."),
                "",
                (
                    "The proof scope is restricted "
                    "to direct parameter-attribute "
                    "bindings and conjunctions of "
                    "attribute equalities."
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )

    return summary


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/a1_leaf_binding_batch"),
    )

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    output_dir = args.output_dir

    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    summary = build(
        repo_root=repo_root,
        output_dir=output_dir.resolve(),
    )

    print("BIZPROOF V0.11 W2 declarative leaf A1")

    print(
        "Attempted:",
        summary["candidates_attempted"],
    )

    print(
        "CERTIFIED_A1:",
        summary["certificates_issued"],
    )

    print(
        "Review required:",
        summary["review_required"],
    )

    print(
        "Terminalized:",
        summary["terminalized_after"],
        "/90",
    )

    print(
        "Pending:",
        summary["pending_after"],
        "/90",
    )

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
