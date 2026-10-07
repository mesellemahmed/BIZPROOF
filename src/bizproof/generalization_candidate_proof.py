from __future__ import annotations

import argparse
import ast
import hashlib
import json
import textwrap
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeAlias

import z3

JsonDict: TypeAlias = dict[str, Any]

COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"

TARGET_CANDIDATE_ID = "aab5348ee173d6e3"

TARGET_METADATA = {
    "source": "django_oscar",
    "file": "src/oscar/apps/offer/abstract_models.py",
    "class": "AbstractBenefit",
    "function": "shipping_discount",
    "complexity": "LOW",
}

TARGET_LINES = [
    819,
    820,
]

EXPECTED_OSCAR_COMMIT = "5699d78449954f047d6d715fd2b6c5d19594e0f3"


def _load_json(
    path: Path,
) -> JsonDict:

    value = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(f"expected JSON object: {path}")

    return value


def _load_jsonl(
    path: Path,
) -> list[JsonDict]:

    records: list[JsonDict] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue

        value = json.loads(raw)

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(f"expected JSON object: {path}")

        records.append(value)

    return records


def _sha256_bytes(
    value: bytes,
) -> str:

    return hashlib.sha256(value).hexdigest()


def _sha256_text(
    value: str,
) -> str:

    return _sha256_bytes(value.encode("utf-8"))


# PHASE-P-CANONICAL-COHORT-SCHEMA
def _candidate_container(
    record: JsonDict,
) -> JsonDict:

    nested = record.get("candidate")

    if isinstance(
        nested,
        dict,
    ):
        merged = dict(nested)

        for key, value in record.items():
            if key != "candidate" and key not in merged:
                merged[key] = value

        return merged

    return dict(record)


def _candidate_field(
    record: JsonDict,
    names: tuple[str, ...],
    *,
    required: bool = True,
    allow_none: bool = False,
) -> Any:

    container = _candidate_container(record)

    for name in names:
        if name not in container:
            continue

        value = container[name]

        if value is None and not allow_none:
            continue

        return value

    if required:
        raise ValueError(
            "missing candidate field; "
            f"accepted aliases={names}; "
            f"available={sorted(container.keys())}"
        )

    return None


def _candidate_lines(
    record: JsonDict,
) -> list[int]:

    container = _candidate_container(record)

    direct = container.get("lines")

    if (
        isinstance(
            direct,
            list,
        )
        and len(direct) == 2
    ):
        return [
            int(direct[0]),
            int(direct[1]),
        ]

    pairs = (
        (
            "start_line",
            "end_line",
        ),
        (
            "line_start",
            "line_end",
        ),
        (
            "lineno",
            "end_lineno",
        ),
        (
            "function_start_line",
            "function_end_line",
        ),
        (
            "start_lineno",
            "end_lineno",
        ),
    )

    for (
        start_key,
        end_key,
    ) in pairs:
        if start_key in container and end_key in container:
            return [
                int(container[start_key]),
                int(container[end_key]),
            ]

    raise ValueError(
        f"candidate source-line schema unresolved; available={sorted(container.keys())}"
    )


def _normalise_cohort_record(
    record: JsonDict,
) -> JsonDict:

    container = _candidate_container(record)

    candidate_id = str(
        _candidate_field(
            record,
            ("candidate_id",),
        )
    )

    source = str(
        _candidate_field(
            record,
            (
                "source",
                "source_id",
            ),
        )
    )

    relative_file = str(
        _candidate_field(
            record,
            (
                "file",
                "relative_file",
                "file_path",
                "path",
            ),
        )
    )

    function = str(
        _candidate_field(
            record,
            (
                "function",
                "function_name",
                "method",
                "method_name",
            ),
        )
    )

    class_value = _candidate_field(
        record,
        (
            "class",
            "class_name",
            "enclosing_class",
        ),
        required=False,
        allow_none=True,
    )

    complexity = str(
        _candidate_field(
            record,
            (
                "complexity",
                "adaptation_complexity",
            ),
        )
    )

    evidence = _candidate_field(
        record,
        (
            "evidence",
            "evidence_bucket",
            "evidence_class",
            "evidence_status",
        ),
        required=False,
        allow_none=True,
    )

    canonical = dict(container)

    canonical["candidate_id"] = candidate_id

    canonical["source"] = source

    canonical["file"] = relative_file

    canonical["class"] = None if class_value is None else str(class_value)

    canonical["function"] = function

    canonical["complexity"] = complexity

    canonical["evidence"] = None if evidence is None else str(evidence)

    canonical["lines"] = _candidate_lines(record)

    canonical["_cohort_schema"] = {
        "nested_candidate": isinstance(
            record.get("candidate"),
            dict,
        ),
        "source_alias": ("source" if "source" in container else "source_id"),
        "class_alias": (
            "class"
            if "class" in container
            else ("class_name" if "class_name" in container else "enclosing_class")
        ),
        "complexity_alias": (
            "complexity" if "complexity" in container else "adaptation_complexity"
        ),
        "evidence_alias": (
            "evidence"
            if "evidence" in container
            else (
                "evidence_bucket"
                if "evidence_bucket" in container
                else ("evidence_class" if "evidence_class" in container else "evidence_status")
            )
        ),
    }

    return canonical


def _candidate_record(
    cohort: list[JsonDict],
    candidate_id: str,
) -> JsonDict:

    matches = [item for item in cohort if (str(item.get("candidate_id")) == candidate_id)]

    if len(matches) != 1:
        raise ValueError(f"candidate lookup is not unique: {candidate_id}")

    return matches[0]


def _find_method(
    source: str,
    *,
    class_name: str,
    function_name: str,
) -> ast.FunctionDef:

    tree = ast.parse(source)

    classes = [
        node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.ClassDef,
            )
            and node.name == class_name
        )
    ]

    if len(classes) != 1:
        raise ValueError(f"class lookup is not unique: {class_name}")

    methods = [
        node
        for node in classes[0].body
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name == function_name
        )
    ]

    if len(methods) != 1:
        raise ValueError(f"method lookup is not unique: {class_name}.{function_name}")

    return methods[0]


def _executable_body(
    function: ast.FunctionDef,
) -> list[ast.stmt]:

    body = list(function.body)

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


def _validate_constant_decimal_method(
    function: ast.FunctionDef,
) -> JsonDict:

    parameter_names = [
        argument.arg
        for argument in (
            list(function.args.posonlyargs)
            + list(function.args.args)
            + list(function.args.kwonlyargs)
        )
    ]

    if parameter_names != [
        "self",
        "charge",
        "currency",
    ]:
        raise ValueError(f"unexpected shipping_discount parameters: {parameter_names}")

    body = _executable_body(function)

    if len(body) != 1:
        raise ValueError("shipping_discount has unexpected executable statement count")

    statement = body[0]

    if not isinstance(
        statement,
        ast.Return,
    ):
        raise ValueError("shipping_discount is not a single-return slice")

    value = statement.value

    if not isinstance(
        value,
        ast.Call,
    ):
        raise ValueError("shipping_discount return is not a call")

    if not (
        isinstance(
            value.func,
            ast.Name,
        )
        and value.func.id == "D"
    ):
        raise ValueError("shipping_discount does not return D(...)")

    if len(value.args) != 1 or value.keywords:
        raise ValueError("unexpected D invocation shape")

    argument = value.args[0]

    if not (
        isinstance(
            argument,
            ast.Constant,
        )
        and argument.value == "0.00"
    ):
        raise ValueError("shipping_discount is not D('0.00')")

    return {
        "parameters": parameter_names,
        "semantic_shape": "CONSTANT_DECIMAL_RETURN",
        "constructor": "decimal.Decimal",
        "literal": "0.00",
    }


def _adapter_shipping_discount() -> Decimal:

    return Decimal("0.00")


def _mutant_shipping_discount() -> Decimal:

    return Decimal("0.01")


def _decimal_representation(
    value: Decimal,
) -> JsonDict:

    parts = value.as_tuple()

    coefficient = 0

    for digit in parts.digits:
        coefficient = coefficient * 10 + int(digit)

    if parts.sign:
        coefficient = -coefficient

    return {
        "coefficient": coefficient,
        "exponent": int(parts.exponent),
        "sign": int(parts.sign),
        "string": str(value),
    }


def _runtime_preservation(
    method_source: str,
) -> JsonDict:

    namespace: dict[
        str,
        Any,
    ] = {
        "D": Decimal,
    }

    executable_source = textwrap.dedent(method_source)

    exec(
        compile(
            executable_source,
            "<locked-shipping-discount>",
            "exec",
        ),
        namespace,
    )

    function = namespace.get("shipping_discount")

    if not callable(function):
        raise ValueError("source-executed shipping_discount is not callable")

    charges: list[object] = [
        Decimal("-100.00"),
        Decimal("0.00"),
        Decimal("0.01"),
        Decimal("12.34"),
        0,
        None,
    ]

    currencies: list[object] = [
        None,
        "USD",
        "EUR",
    ]

    comparisons = 0
    adapter_mismatches = 0
    mutant_mismatches = 0

    examples: list[JsonDict] = []

    for charge in charges:
        for currency in currencies:
            external = function(
                object(),
                charge,
                currency,
            )

            adapter = _adapter_shipping_discount()

            mutant = _mutant_shipping_discount()

            if not isinstance(
                external,
                Decimal,
            ):
                raise ValueError("external result is not Decimal")

            if external != adapter:
                adapter_mismatches += 1

            if external != mutant:
                mutant_mismatches += 1

            if len(examples) < 4:
                examples.append(
                    {
                        "charge_type": type(charge).__name__,
                        "currency": repr(currency),
                        "external": str(external),
                        "adapter": str(adapter),
                        "mutant": str(mutant),
                    }
                )

            comparisons += 1

    if comparisons != 18:
        raise ValueError("unexpected preservation comparison count")

    if adapter_mismatches != 0:
        raise ValueError("adapter/source mismatch detected")

    if mutant_mismatches != comparisons:
        raise ValueError("mutant sensitivity incomplete")

    return {
        "comparisons": comparisons,
        "adapter_mismatches": adapter_mismatches,
        "mutant_mismatches": mutant_mismatches,
        "examples": examples,
        "external_representation": _decimal_representation(Decimal("0.00")),
        "adapter_representation": _decimal_representation(_adapter_shipping_discount()),
        "mutant_representation": _decimal_representation(_mutant_shipping_discount()),
        "passed": True,
    }


def _symbolic_constant_equivalence() -> JsonDict:

    external_coefficient = z3.IntVal(0)

    external_exponent = z3.IntVal(-2)

    external_sign = z3.IntVal(0)

    adapter_coefficient = z3.IntVal(0)

    adapter_exponent = z3.IntVal(-2)

    adapter_sign = z3.IntVal(0)

    solver = z3.Solver()

    solver.add(
        z3.Or(
            external_coefficient != adapter_coefficient,
            external_exponent != adapter_exponent,
            external_sign != adapter_sign,
        )
    )

    correct_status = solver.check()

    if correct_status != z3.unsat:
        raise ValueError("correct symbolic representation was not proved equivalent")

    mutant_solver = z3.Solver()

    mutant_solver.add(
        z3.Or(
            external_coefficient != z3.IntVal(1),
            external_exponent != z3.IntVal(-2),
            external_sign != z3.IntVal(0),
        )
    )

    mutant_status = mutant_solver.check()

    if mutant_status != z3.sat:
        raise ValueError("mutant symbolic representation was not disproved")

    return {
        "representation": {
            "fields": [
                "coefficient",
                "exponent",
                "sign",
            ],
            "source": [
                0,
                -2,
                0,
            ],
            "adapter": [
                0,
                -2,
                0,
            ],
            "mutant": [
                1,
                -2,
                0,
            ],
        },
        "correct_solver_status": str(correct_status),
        "mutant_solver_status": str(mutant_status),
        "correct_equivalence_proved": (correct_status == z3.unsat),
        "mutant_disproved": (mutant_status == z3.sat),
    }


def _validated_semantic_primitives(
    phase_n_root: Path,
    phase_o_root: Path,
) -> set[str]:

    result: set[str] = set()

    decimal_contract = _load_json(phase_n_root / "decimal_contract.json")

    if decimal_contract.get("semantic_contract_status") == "VALIDATED":
        result.add(str(decimal_contract["primitive"]))

    aliases = _load_json(phase_o_root / "numpy_alias_contracts.json")

    alias_records = aliases.get(
        "contracts",
        [],
    )

    if not isinstance(
        alias_records,
        list,
    ):
        raise ValueError("invalid NumPy alias contract list")

    for item in alias_records:
        if not isinstance(
            item,
            dict,
        ):
            continue

        status = str(item.get("semantic_contract_status"))

        if status.startswith("VALIDATED"):
            result.add(str(item["primitive"]))

    nb_enf = _load_json(phase_o_root / "nb_enf_contract.json")

    if str(nb_enf.get("semantic_contract_status")).startswith("VALIDATED"):
        result.add(str(nb_enf["primitive"]))

    return result


def _structural_protocol_primitives(
    phase_n_root: Path,
) -> set[str]:

    protocols = _load_json(phase_n_root / "protocol_contracts.json")

    groups = protocols.get(
        "groups",
        [],
    )

    if not isinstance(
        groups,
        list,
    ):
        raise ValueError("invalid structural protocol list")

    result: set[str] = set()

    for item in groups:
        if not isinstance(
            item,
            dict,
        ):
            continue

        if item.get("structural_protocol_status") == "VALIDATED":
            result.add(str(item["primitive"]))

    return result


def _frontier_status(
    primitives: set[str],
    *,
    validated_semantics: set[str],
    structural_protocols: set[str],
) -> tuple[
    str,
    list[str],
    list[str],
]:

    if not primitives:
        return (
            "NO_CONTRACT_OCCURRENCES",
            [],
            [],
        )

    unresolved = primitives - validated_semantics

    if not unresolved:
        return (
            "PRIMITIVE_CONTRACTS_CLOSED",
            [],
            [],
        )

    structural_only = unresolved & structural_protocols

    other_unresolved = unresolved - structural_protocols

    if structural_only and not other_unresolved:
        return (
            "STRUCTURAL_PROTOCOL_SEMANTICS_REMAIN",
            sorted(structural_only),
            [],
        )

    return (
        "UNRESOLVED_PRIMITIVES_REMAIN",
        sorted(structural_only),
        sorted(other_unresolved),
    )


def _build_frontier(
    *,
    cohort: list[JsonDict],
    occurrences: list[JsonDict],
    validated_semantics: set[str],
    structural_protocols: set[str],
) -> tuple[
    list[JsonDict],
    JsonDict,
]:

    by_candidate: dict[
        str,
        list[JsonDict],
    ] = defaultdict(list)

    for item in occurrences:
        by_candidate[str(item["candidate_id"])].append(item)

    records: list[JsonDict] = []

    status_counts: Counter[str] = Counter()

    for candidate in cohort:
        candidate_id = str(candidate["candidate_id"])

        candidate_occurrences = by_candidate.get(
            candidate_id,
            [],
        )

        primitives = {str(item["primitive"]) for item in candidate_occurrences}

        (
            status,
            structural_remaining,
            unresolved_remaining,
        ) = _frontier_status(
            primitives,
            validated_semantics=validated_semantics,
            structural_protocols=structural_protocols,
        )

        status_counts[status] += 1

        records.append(
            {
                "candidate_id": candidate_id,
                "source": candidate.get("source"),
                "file": candidate.get("file"),
                "class": candidate.get("class"),
                "function": candidate.get("function"),
                "complexity": candidate.get("complexity"),
                "evidence": candidate.get("evidence"),
                "contract_occurrence_count": len(candidate_occurrences),
                "contract_primitives": sorted(primitives),
                "validated_semantic_primitives": sorted(primitives & validated_semantics),
                "structural_semantics_remaining": structural_remaining,
                "unresolved_primitives_remaining": unresolved_remaining,
                "frontier_status": status,
                "candidate_certification": False,
                "terminal_outcome_assigned": False,
            }
        )

    summary: JsonDict = {
        "candidates": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "validated_semantic_primitives": sorted(validated_semantics),
        "structural_protocol_primitives": sorted(structural_protocols),
        "certification_claim": False,
    }

    return (
        records,
        summary,
    )


def _terminal_protocol_excerpts(
    protocol_path: Path,
) -> JsonDict:

    text = protocol_path.read_text(encoding="utf-8")

    lines = text.splitlines()

    tokens = [
        "CERTIFIED_A0",
        "CERTIFIED_A1",
        "CERTIFIED_A2",
        "A0",
        "A1",
        "A2",
    ]

    matched_lines: set[int] = set()

    for index, line in enumerate(lines):
        if any(token in line for token in tokens):
            for selected in range(
                max(
                    0,
                    index - 3,
                ),
                min(
                    len(lines),
                    index + 4,
                ),
            ):
                matched_lines.add(selected)

    excerpts = [
        {
            "line": index + 1,
            "text": lines[index],
        }
        for index in sorted(matched_lines)
    ]

    return {
        "protocol": str(protocol_path).replace(
            "\\",
            "/",
        ),
        "matching_context_lines": excerpts,
        "automatic_level_assignment": False,
        "mapping_status": (
            "PROTOCOL_CONTEXT_FOUND_REVIEW_REQUIRED" if excerpts else "NO_A_LEVEL_DEFINITION_FOUND"
        ),
    }


def _locked_source_record(
    lock_path: Path,
    source_id: str,
) -> JsonDict:

    data = _load_json(lock_path)

    sources = data.get(
        "sources",
        [],
    )

    if not isinstance(
        sources,
        list,
    ):
        raise ValueError("invalid source lock")

    matches = [
        item
        for item in sources
        if (
            isinstance(
                item,
                dict,
            )
            and item.get("id") == source_id
        )
    ]

    if len(matches) != 1:
        raise ValueError("locked source lookup is not unique")

    return matches[0]


def _proof_digest(
    value: JsonDict,
) -> str:

    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=True,
    )

    return _sha256_text(canonical)


def build_candidate_proof(
    *,
    repo_root: Path,
    external_root: Path,
    output_dir: Path,
) -> JsonDict:

    cohort_path = repo_root / "benchmarks/v0.11/results/cohort.jsonl"

    occurrence_path = repo_root / ("benchmarks/v0.11/name_resolution/occurrence_resolution.jsonl")

    phase_n_root = repo_root / "benchmarks/v0.11/semantic_contracts"

    phase_o_root = repo_root / ("benchmarks/v0.11/semantic_contract_closure")

    protocol_path = repo_root / "experiments/V0.11_PROTOCOL.md"

    lock_candidates = [
        repo_root / "benchmarks/v0.6/LOCK.json",
        repo_root / "external_sources/v0.6/LOCK.json",
    ]

    lock_path = next(
        (path for path in lock_candidates if path.is_file()),
        None,
    )

    if lock_path is None:
        raise ValueError("V0.6 source lock missing")

    cohort = [_normalise_cohort_record(item) for item in _load_jsonl(cohort_path)]

    if len(cohort) != 90:
        raise ValueError("frozen cohort size changed")

    cohort_summary = _load_json(repo_root / "benchmarks/v0.11/results/summary.json")

    if cohort_summary.get("cohort_sha256") != COHORT_SHA256:
        raise ValueError("frozen cohort SHA changed")

    occurrences = _load_jsonl(occurrence_path)

    if len(occurrences) != 170:
        raise ValueError("name-resolution occurrence count changed")

    validated_semantics = _validated_semantic_primitives(
        phase_n_root,
        phase_o_root,
    )

    expected_validated = {
        "D",
        "nb_enf",
        "not_",
        "min_",
        "where",
    }

    if validated_semantics != expected_validated:
        raise ValueError(f"validated primitive set changed: {sorted(validated_semantics)}")

    structural_protocols = _structural_protocol_primitives(phase_n_root)

    (
        frontier,
        frontier_summary,
    ) = _build_frontier(
        cohort=cohort,
        occurrences=occurrences,
        validated_semantics=validated_semantics,
        structural_protocols=structural_protocols,
    )

    target = _candidate_record(
        cohort,
        TARGET_CANDIDATE_ID,
    )

    for key, expected in TARGET_METADATA.items():
        if target.get(key) != expected:
            raise ValueError(f"target cohort metadata mismatch for {key}: {target.get(key)!r}")

    if target.get("lines") != TARGET_LINES:
        raise ValueError("target source lines changed")

    target_frontier = [item for item in frontier if (item["candidate_id"] == TARGET_CANDIDATE_ID)]

    if len(target_frontier) != 1:
        raise ValueError("target frontier lookup failed")

    target_frontier_record = target_frontier[0]

    if target_frontier_record["frontier_status"] != "PRIMITIVE_CONTRACTS_CLOSED":
        raise ValueError("target primitive frontier is not closed")

    if target_frontier_record["contract_primitives"] != [
        "D",
    ]:
        raise ValueError("target contract primitive set changed")

    source_lock = _locked_source_record(
        lock_path,
        "django_oscar",
    )

    if source_lock["resolved_commit"] != EXPECTED_OSCAR_COMMIT:
        raise ValueError("locked Oscar commit changed")

    source_path = external_root / "django_oscar" / TARGET_METADATA["file"]

    if not source_path.is_file():
        raise ValueError("locked target source file missing")

    source = source_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    source_file_sha256 = _sha256_bytes(source_path.read_bytes())

    function = _find_method(
        source,
        class_name=str(TARGET_METADATA["class"]),
        function_name=str(TARGET_METADATA["function"]),
    )

    source_lines = [
        int(function.lineno),
        int(function.end_lineno or function.lineno),
    ]

    if source_lines != TARGET_LINES:
        raise ValueError("locked source method lines do not match frozen cohort")

    shape = _validate_constant_decimal_method(function)

    method_source = (
        ast.get_source_segment(
            source,
            function,
        )
        or ""
    )

    if not method_source:
        raise ValueError("unable to extract method source")

    preservation = _runtime_preservation(method_source)

    symbolic = _symbolic_constant_equivalence()

    protocol = _terminal_protocol_excerpts(protocol_path)

    proof: JsonDict = {
        "proof_id": "PROOF-V011-OSCAR-SHIPPING-001",
        "candidate_id": TARGET_CANDIDATE_ID,
        "source": "django_oscar",
        "locked_commit": EXPECTED_OSCAR_COMMIT,
        "source_file": TARGET_METADATA["file"],
        "source_file_sha256": source_file_sha256,
        "class": TARGET_METADATA["class"],
        "function": TARGET_METADATA["function"],
        "source_lines": source_lines,
        "source_slice": method_source,
        "source_slice_sha256": _sha256_text(method_source),
        "frozen_candidate_metadata": target,
        "frontier": target_frontier_record,
        "semantic_shape": shape,
        "required_primitive_contracts": [
            "SC-D-DECIMAL-001",
        ],
        "primitive_contracts_satisfied": True,
        "source_executed_preservation": preservation,
        "symbolic_equivalence": symbolic,
        "mutant_sensitivity": {
            "runtime_mutant_mismatches": preservation["mutant_mismatches"],
            "runtime_cases": preservation["comparisons"],
            "symbolic_mutant_status": symbolic["mutant_solver_status"],
            "passed": (
                preservation["mutant_mismatches"] == preservation["comparisons"]
                and symbolic["mutant_disproved"] is True
            ),
        },
        "proof_obligations": {
            "locked_provenance": True,
            "frozen_candidate_identity": True,
            "primitive_semantics_closed": True,
            "source_executed_preservation": preservation["passed"],
            "symbolic_equivalence": symbolic["correct_equivalence_proved"],
            "mutant_sensitivity": (
                preservation["mutant_mismatches"] == preservation["comparisons"]
                and symbolic["mutant_disproved"]
            ),
        },
        "candidate_proof_status": "PROVED_SOURCE_SLICE",
        "evidence_complete": True,
        "terminal_outcome_assigned": False,
        "terminal_outcome": None,
        "terminal_level_mapping_status": protocol["mapping_status"],
        "certification_claim": False,
    }

    obligations = proof["proof_obligations"]

    if not isinstance(
        obligations,
        dict,
    ):
        raise ValueError("invalid proof obligation structure")

    if not all(bool(value) for value in obligations.values()):
        raise ValueError("candidate proof obligations incomplete")

    digest_input = dict(proof)

    proof["proof_digest_sha256"] = _proof_digest(digest_input)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    frontier_path = output_dir / "candidate_frontier.jsonl"

    frontier_path.write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in frontier
        ),
        encoding="utf-8",
    )

    (output_dir / "frontier_summary.json").write_text(
        json.dumps(
            frontier_summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "shipping_discount_proof.json").write_text(
        json.dumps(
            proof,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "terminal_level_protocol.json").write_text(
        json.dumps(
            protocol,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "FIRST_CANDIDATE_PROOF",
        "cohort_size": len(cohort),
        "cohort_sha256": COHORT_SHA256,
        "validated_semantic_primitives": sorted(validated_semantics),
        "candidate_frontier_status_counts": frontier_summary["status_counts"],
        "proofs_completed": 1,
        "proved_candidate_ids": [
            TARGET_CANDIDATE_ID,
        ],
        "proved_candidate_status": "PROVED_SOURCE_SLICE",
        "source_execution_comparisons": preservation["comparisons"],
        "source_execution_mismatches": preservation["adapter_mismatches"],
        "mutant_mismatches": preservation["mutant_mismatches"],
        "symbolic_equivalences_proved": 1,
        "terminal_outcomes_assigned": 0,
        "terminal_level_mapping_status": protocol["mapping_status"],
        "candidate_certifications_issued": 0,
        "certification_claim": False,
        "passed": (
            preservation["passed"] is True
            and symbolic["correct_equivalence_proved"] is True
            and symbolic["mutant_disproved"] is True
            and proof["evidence_complete"] is True
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
                ("# BIZPROOF V0.11 First Candidate Proof"),
                "",
                (f"- Frozen cohort: {len(cohort)} candidates"),
                (f"- Proved candidate: `{TARGET_CANDIDATE_ID}`"),
                ("- Candidate slice: `AbstractBenefit.shipping_discount`"),
                ("- Candidate proof status: `PROVED_SOURCE_SLICE`"),
                ("- Required primitive contract: `SC-D-DECIMAL-001`"),
                (f"- Source-executed comparisons: {preservation['comparisons']}"),
                (f"- Adapter mismatches: {preservation['adapter_mismatches']}"),
                (f"- Mutant mismatches: {preservation['mutant_mismatches']}"),
                ("- Symbolic equivalence: PROVED"),
                ("- Terminal outcome assigned: NO"),
                ("- Candidate certification issued: NO"),
                "",
                (
                    "Terminal A-level classification is "
                    "kept separate until the preregistered "
                    "A0/A1/A2 mapping is read from the "
                    "frozen V0.11 protocol."
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
        "--external-root",
        type=Path,
        default=Path("external_sources/v0.6"),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/candidate_proof_frontier"),
    )

    args = parser.parse_args()

    summary = build_candidate_proof(
        repo_root=args.repo_root.resolve(),
        external_root=args.external_root.resolve(),
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 first candidate proof")

    print(
        "Cohort:",
        summary["cohort_size"],
    )

    print(
        "Validated semantic primitives:",
        summary["validated_semantic_primitives"],
    )

    print(
        "Frontier:",
        summary["candidate_frontier_status_counts"],
    )

    print(
        "Proved candidate:",
        summary["proved_candidate_ids"][0],
    )

    print(
        "Proof status:",
        summary["proved_candidate_status"],
    )

    print(
        "Source comparisons:",
        summary["source_execution_comparisons"],
    )

    print(
        "Source mismatches:",
        summary["source_execution_mismatches"],
    )

    print(
        "Mutant mismatches:",
        summary["mutant_mismatches"],
    )

    print(
        "Symbolic equivalences proved:",
        summary["symbolic_equivalences_proved"],
    )

    print("Terminal outcomes assigned: 0")

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
