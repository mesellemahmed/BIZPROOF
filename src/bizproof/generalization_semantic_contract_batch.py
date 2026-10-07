from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeAlias

from .generalization_protocol_closure import _signature
from .generalization_semantic_evidence import (
    _load_json,
    _load_jsonl,
)
from .generalization_symbol_trace import _trace_symbol

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_OCCURRENCES = 170
EXPECTED_PROTOCOL_GROUPS = 8
EXPECTED_OPENFISCA_CORE_VERSION = "44.0.4"

TARGET_DEPENDENCY_SYMBOLS = (
    "not_",
    "min_",
    "where",
)


def _sha256_file(path: Path) -> str:

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _module_name_from_file(
    relative_file: str,
) -> str:

    parts = list(Path(relative_file).parts)

    if parts and parts[0] == "src":
        parts = parts[1:]

    if not parts:
        raise ValueError("empty module path")

    if parts[-1] == "__init__.py":
        parts = parts[:-1]

    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]

    if not parts:
        raise ValueError("invalid module path")

    return ".".join(parts)


def _protocol_subject(
    item: JsonDict,
) -> str:

    binding = item.get("authoritative_binding")

    if not isinstance(
        binding,
        dict,
    ):
        return ""

    status = str(item["resolution_status"])

    if status == "FUNCTION_PARAMETER_BOUNDARY":
        return str(binding.get("parameter") or "")

    if status == "PARAMETER_METHOD_BOUNDARY":
        return str(binding.get("receiver_root") or binding.get("receiver") or "")

    return ""


def _validate_decimal_contract(
    occurrences: list[JsonDict],
) -> JsonDict:

    items = [item for item in occurrences if (str(item.get("primitive")) == "D")]

    if len(items) != 1:
        raise ValueError("expected exactly one D occurrence")

    item = items[0]

    binding = item.get("authoritative_binding")

    if not isinstance(
        binding,
        dict,
    ):
        raise ValueError("D authoritative binding missing")

    expected_binding = {
        "binding_kind": "EXPLICIT_IMPORT",
        "target_module": "decimal",
        "target_symbol": "Decimal",
    }

    for key, expected in expected_binding.items():
        if str(binding.get(key)) != expected:
            raise ValueError(f"unexpected D binding {key}: {binding.get(key)!r}")

    expression = str(item["source_expression"])

    parsed = ast.parse(
        expression,
        mode="eval",
    ).body

    if not (
        isinstance(
            parsed,
            ast.Call,
        )
        and isinstance(
            parsed.func,
            ast.Name,
        )
        and parsed.func.id == "D"
        and len(parsed.args) == 1
        and isinstance(
            parsed.args[0],
            ast.Constant,
        )
        and parsed.args[0].value == "0.00"
        and not parsed.keywords
    ):
        raise ValueError("unexpected D invocation shape")

    runtime_value = Decimal("0.00")

    value_tuple = runtime_value.as_tuple()

    if str(runtime_value) != "0.00":
        raise ValueError("Decimal runtime representation changed")

    if runtime_value != Decimal(0):
        raise ValueError("Decimal numeric value changed")

    if value_tuple.exponent != -2:
        raise ValueError("Decimal scale changed")

    return {
        "contract_id": "SC-D-DECIMAL-001",
        "primitive": "D",
        "scope": "observed invocation D('0.00')",
        "source_id": str(item["source_id"]),
        "candidate_id": str(item["candidate_id"]),
        "file": str(item["file"]),
        "function": str(item["function"]),
        "source_expression": expression,
        "binding_contract": {
            "local_name": "D",
            "module": "decimal",
            "symbol": "Decimal",
            "import_source": str(binding.get("source")),
        },
        "semantic_type": "decimal.Decimal",
        "constructor_argument": "0.00",
        "runtime_validation": {
            "string_representation": str(runtime_value),
            "numeric_zero": bool(runtime_value == Decimal(0)),
            "sign": int(value_tuple.sign),
            "digits": list(value_tuple.digits),
            "exponent": int(value_tuple.exponent),
        },
        "semantic_contract_status": "VALIDATED",
        "candidate_certification": False,
        "certification_claim": False,
    }


def _validate_structural_protocols(
    occurrences: list[JsonDict],
    protocol_groups: list[JsonDict],
) -> list[JsonDict]:

    grouped: dict[
        tuple[
            str,
            str,
            str,
        ],
        list[JsonDict],
    ] = defaultdict(list)

    for item in occurrences:
        status = str(item["resolution_status"])

        if status not in {
            "FUNCTION_PARAMETER_BOUNDARY",
            "PARAMETER_METHOD_BOUNDARY",
        }:
            continue

        key = (
            str(item["primitive"]),
            status,
            _protocol_subject(item),
        )

        grouped[key].append(item)

    validated: list[JsonDict] = []

    for expected in protocol_groups:
        key = (
            str(expected["primitive"]),
            str(expected["resolution_status"]),
            str(expected["subject"]),
        )

        related = grouped.get(
            key,
            [],
        )

        signatures = Counter(_signature(str(item["source_expression"])) for item in related)

        actual_signatures = dict(sorted(signatures.items()))

        expected_signatures = {
            str(name): int(count) for name, count in dict(expected["signatures"]).items()
        }

        if len(related) != int(expected["occurrences"]):
            raise ValueError(f"protocol occurrence mismatch for {key}")

        if actual_signatures != expected_signatures:
            raise ValueError(f"protocol signature mismatch for {key}")

        validated.append(
            {
                "primitive": key[0],
                "resolution_status": key[1],
                "subject": key[2],
                "occurrences": len(related),
                "signatures": actual_signatures,
                "structural_protocol_status": "VALIDATED",
                "semantic_return_type": "UNRESOLVED",
                "semantic_value_contract": "UNRESOLVED",
                "candidate_certification": False,
                "certification_claim": False,
            }
        )

    if len(validated) != EXPECTED_PROTOCOL_GROUPS:
        raise ValueError(f"expected exactly {EXPECTED_PROTOCOL_GROUPS} validated protocol groups")

    return validated


def _resolve_local_binding(
    occurrence: JsonDict,
    external_root: Path,
    source_evidence: JsonDict | None = None,
) -> JsonDict:

    primitive = str(occurrence["primitive"])

    candidate_id = str(occurrence["candidate_id"])

    # -------------------------------------------------
    # Prefer the earlier source-symbol trace.
    #
    # The occurrence file is the business-rule file,
    # but a symbol may resolve through imports into a
    # different locked source file.
    # -------------------------------------------------

    if source_evidence is None:
        evidence_path = Path("benchmarks/v0.11/contract_readiness/local_source_contracts.json")

        if evidence_path.is_file():
            evidence_data = _load_json(evidence_path)

            raw_records = evidence_data.get(
                "records",
                [],
            )

            if not isinstance(
                raw_records,
                list,
            ):
                raise ValueError("invalid local-source evidence records")

            matches = [
                item
                for item in raw_records
                if (
                    isinstance(
                        item,
                        dict,
                    )
                    and str(item.get("candidate_id")) == candidate_id
                    and str(item.get("primitive")) == primitive
                    and str(item.get("terminal_kind")) == "LOCAL_DEFINITION"
                )
            ]

            if len(matches) > 1:
                raise ValueError(
                    f"multiple traced local definitions for {candidate_id}/{primitive}"
                )

            if len(matches) == 1:
                source_evidence = dict(matches[0])

    if source_evidence is not None:
        if str(source_evidence.get("candidate_id")) != candidate_id:
            raise ValueError("source-evidence candidate mismatch")

        if str(source_evidence.get("primitive")) != primitive:
            raise ValueError("source-evidence primitive mismatch")

        if str(source_evidence.get("terminal_kind")) != "LOCAL_DEFINITION":
            raise ValueError("source evidence is not a LOCAL_DEFINITION")

        source_id = str(source_evidence["source_id"])

        relative_file = str(source_evidence["file"])

        line = int(source_evidence["line"])

        binding: JsonDict = {
            "binding_kind": "LOCAL_DEFINITION",
            "line": line,
            "source": str(source_evidence.get("source") or ""),
            "trace_evidence": ("benchmarks/v0.11/contract_readiness/local_source_contracts.json"),
        }

        expected_sha = str(source_evidence.get("file_sha256") or "")

        provenance_basis = "PHASE_I_SOURCE_SYMBOL_TRACE"

    else:
        original_binding = occurrence.get("authoritative_binding")

        if not isinstance(
            original_binding,
            dict,
        ):
            raise ValueError("authoritative binding missing")

        raw_line = original_binding.get("line")

        if not isinstance(
            raw_line,
            int,
        ):
            raise ValueError("authoritative binding line missing")

        binding = dict(original_binding)

        line = raw_line

        source_id = str(occurrence["source_id"])

        relative_file = str(occurrence["file"])

        expected_sha = ""

        provenance_basis = "OCCURRENCE_FILE_BINDING"

    source_path = external_root / source_id / relative_file

    if not source_path.is_file():
        raise ValueError(f"locked source missing: {source_path}")

    actual_source_sha = _sha256_file(source_path)

    if expected_sha and actual_source_sha != expected_sha:
        raise ValueError(
            "traced source SHA mismatch for "
            f"{primitive}: "
            f"expected {expected_sha}, "
            f"actual {actual_source_sha}"
        )

    source = source_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    tree = ast.parse(
        source,
        filename=str(source_path),
    )

    exact_nodes = [
        node
        for node in tree.body
        if (
            getattr(
                node,
                "lineno",
                None,
            )
            == line
            and getattr(
                node,
                "name",
                None,
            )
            == primitive
        )
    ]

    named_nodes = [
        node
        for node in tree.body
        if (
            getattr(
                node,
                "name",
                None,
            )
            == primitive
        )
    ]

    selected = exact_nodes[0] if len(exact_nodes) == 1 else None

    result: JsonDict = {
        "primitive": primitive,
        "candidate_id": candidate_id,
        "source_id": source_id,
        "candidate_file": str(occurrence["file"]),
        "resolved_definition_file": relative_file,
        "resolved_definition_line": line,
        "source_sha256": actual_source_sha,
        "expected_source_sha256": (expected_sha or actual_source_sha),
        "provenance_basis": provenance_basis,
        "authoritative_binding": binding,
        "exact_line_matches": len(exact_nodes),
        "named_top_level_matches": len(named_nodes),
        "semantic_contract_status": "UNRESOLVED",
        "candidate_certification": False,
        "certification_claim": False,
    }

    if selected is None:
        result["binding_resolution_status"] = "BINDING_REVIEW_REQUIRED"

        return result

    result["node_type"] = type(selected).__name__

    result["binding_resolution_status"] = "RESOLVED"

    segment = ast.get_source_segment(
        source,
        selected,
    )

    if segment:
        result["definition_source"] = segment

        result["definition_sha256"] = hashlib.sha256(segment.encode("utf-8")).hexdigest()

        source_lines = segment.splitlines()

        result["definition_header"] = source_lines[0] if source_lines else ""

    if isinstance(
        selected,
        ast.ClassDef,
    ):
        result["definition_kind"] = "CLASS"

        result["bases"] = [ast.unparse(base) for base in selected.bases]

        result["methods"] = [
            child.name
            for child in selected.body
            if isinstance(
                child,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
        ]

    elif isinstance(
        selected,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        result["definition_kind"] = "FUNCTION"

        parameters = (
            list(selected.args.posonlyargs)
            + list(selected.args.args)
            + list(selected.args.kwonlyargs)
        )

        result["parameters"] = [argument.arg for argument in parameters]

        result["called_symbols"] = sorted(
            {
                ast.unparse(node.func)
                for node in ast.walk(selected)
                if isinstance(
                    node,
                    ast.Call,
                )
            }
        )

        result["return_expressions"] = [
            ast.unparse(node.value) if node.value is not None else None
            for node in ast.walk(selected)
            if isinstance(
                node,
                ast.Return,
            )
        ]

    else:
        result["definition_kind"] = type(selected).__name__

    return result


def _zero_discount_trace(
    occurrences: list[JsonDict],
    external_root: Path,
) -> JsonDict:

    items = [item for item in occurrences if (str(item.get("primitive")) == "ZERO_DISCOUNT")]

    if len(items) != 1:
        raise ValueError("expected one ZERO_DISCOUNT occurrence")

    item = items[0]

    binding = item.get("authoritative_binding")

    if not isinstance(
        binding,
        dict,
    ):
        raise ValueError("ZERO_DISCOUNT binding missing")

    source = str(binding.get("source") or "")

    statement = ast.parse(source).body[0]

    if not isinstance(
        statement,
        ast.Assign,
    ):
        raise ValueError("ZERO_DISCOUNT is not an assignment")

    if not isinstance(
        statement.value,
        ast.Call,
    ):
        raise ValueError("ZERO_DISCOUNT is not a factory call")

    call = statement.value

    if not isinstance(
        call.func,
        ast.Name,
    ):
        raise ValueError("ZERO_DISCOUNT factory is not a name")

    factory = call.func.id

    module_name = _module_name_from_file(str(item["file"]))

    trace = _trace_symbol(
        source_root=external_root / str(item["source_id"]),
        module_name=module_name,
        symbol=factory,
    )

    return {
        "primitive": "ZERO_DISCOUNT",
        "candidate_id": str(item["candidate_id"]),
        "assignment": source,
        "factory": factory,
        "factory_arguments": [ast.unparse(argument) for argument in call.args],
        "factory_trace": trace,
        "semantic_contract_status": "UNRESOLVED",
        "candidate_certification": False,
        "certification_claim": False,
    }


def _dependency_symbol_traces(
    *,
    dependency_source_root: Path,
    dependency_lock: JsonDict,
) -> list[JsonDict]:

    if str(dependency_lock["version"]) != EXPECTED_OPENFISCA_CORE_VERSION:
        raise ValueError("unexpected OpenFisca-Core version")

    if dependency_lock.get("wheel_hash_verified") is not True:
        raise ValueError("OpenFisca-Core wheel hash was not verified")

    model_api = dependency_source_root / "openfisca_core" / "model_api.py"

    if not model_api.is_file():
        raise ValueError("OpenFisca-Core model_api.py missing")

    results: list[JsonDict] = []

    for symbol in TARGET_DEPENDENCY_SYMBOLS:
        trace = _trace_symbol(
            source_root=dependency_source_root,
            module_name="openfisca_core.model_api",
            symbol=symbol,
        )

        results.append(
            {
                "symbol": symbol,
                "dependency": "openfisca-core",
                "version": EXPECTED_OPENFISCA_CORE_VERSION,
                "wheel_sha256": str(dependency_lock["wheel_sha256"]),
                "trace": trace,
                "semantic_contract_status": "UNRESOLVED",
                "candidate_certification": False,
                "certification_claim": False,
            }
        )

    return results


def build_batch(
    *,
    occurrences_path: Path,
    protocols_path: Path,
    dependency_lock_path: Path,
    external_root: Path,
    dependency_source_root: Path,
    output_dir: Path,
) -> JsonDict:

    occurrences = _load_jsonl(occurrences_path)

    if len(occurrences) != EXPECTED_OCCURRENCES:
        raise ValueError("occurrence count changed")

    protocol_groups = _load_json(protocols_path)["groups"]

    if len(protocol_groups) != EXPECTED_PROTOCOL_GROUPS:
        raise ValueError("protocol group count changed")

    dependency_lock = _load_json(dependency_lock_path)

    decimal_contract = _validate_decimal_contract(occurrences)

    validated_protocols = _validate_structural_protocols(
        occurrences,
        protocol_groups,
    )

    nb_items = [item for item in occurrences if (str(item.get("primitive")) == "nb_enf")]

    if len(nb_items) != 1:
        raise ValueError("expected one nb_enf occurrence")

    nb_enf_resolution = _resolve_local_binding(
        nb_items[0],
        external_root,
    )

    if nb_enf_resolution["binding_resolution_status"] != "RESOLVED":
        raise ValueError("nb_enf binding could not be resolved")

    dependency_traces = _dependency_symbol_traces(
        dependency_source_root=dependency_source_root,
        dependency_lock=dependency_lock,
    )

    zero_discount = _zero_discount_trace(
        occurrences,
        external_root,
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "FIRST_SEMANTIC_CONTRACT_BATCH",
        "binding_occurrences": len(occurrences),
        "semantic_contracts_validated": 1,
        "validated_semantic_contract_ids": [decimal_contract["contract_id"]],
        "structural_protocols_validated": len(validated_protocols),
        "nb_enf_binding_resolved": True,
        "nb_enf_definition_kind": nb_enf_resolution.get("definition_kind"),
        "dependency_locks_validated": 1,
        "openfisca_core_version": str(dependency_lock["version"]),
        "dependency_symbol_traces": len(dependency_traces),
        "zero_discount_factory_traced": True,
        "candidate_certifications_issued": 0,
        "terminal_outcomes_assigned": 0,
        "certification_claim": False,
        "passed": (
            len(validated_protocols) == EXPECTED_PROTOCOL_GROUPS
            and len(dependency_traces) == len(TARGET_DEPENDENCY_SYMBOLS)
        ),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    outputs = {
        "decimal_contract.json": decimal_contract,
        "protocol_contracts.json": {
            "groups": validated_protocols,
            "certification_claim": False,
        },
        "nb_enf_resolution.json": nb_enf_resolution,
        "openfisca_core_traces.json": {
            "dependency_lock": dependency_lock,
            "symbols": dependency_traces,
            "certification_claim": False,
        },
        "zero_discount_trace.json": zero_discount,
        "summary.json": summary,
    }

    for (
        filename,
        value,
    ) in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(
            [
                ("# BIZPROOF V0.11 First Semantic Contract Batch"),
                "",
                ("- Validated semantic primitive contracts: 1"),
                ("- Validated contract: `SC-D-DECIMAL-001`"),
                (f"- Structurally validated protocol groups: {len(validated_protocols)}"),
                (f"- nb_enf local binding resolved: {nb_enf_resolution['definition_kind']}"),
                (f"- OpenFisca-Core locked version: {dependency_lock['version']}"),
                (f"- OpenFisca-Core symbols traced: {len(dependency_traces)}"),
                ("- ZERO_DISCOUNT factory traced: yes"),
                ("- Candidate certifications issued: 0"),
                ("- Terminal outcomes assigned: 0"),
                "",
                (
                    "Structural protocol validation does not "
                    "constitute validation of return-value semantics."
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
        "--occurrences",
        type=Path,
        default=Path("benchmarks/v0.11/name_resolution/occurrence_resolution.jsonl"),
    )

    parser.add_argument(
        "--protocols",
        type=Path,
        default=Path("benchmarks/v0.11/protocol_closure/protocols.json"),
    )

    parser.add_argument(
        "--dependency-lock",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--external-root",
        type=Path,
        default=Path("external_sources/v0.6"),
    )

    parser.add_argument(
        "--dependency-source-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/semantic_contracts"),
    )

    args = parser.parse_args()

    summary = build_batch(
        occurrences_path=args.occurrences,
        protocols_path=args.protocols,
        dependency_lock_path=args.dependency_lock,
        external_root=args.external_root,
        dependency_source_root=args.dependency_source_root,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 first semantic contract batch")

    print(
        "Semantic contracts validated:",
        summary["semantic_contracts_validated"],
    )

    print(
        "Structural protocols validated:",
        summary["structural_protocols_validated"],
    )

    print(
        "nb_enf definition kind:",
        summary["nb_enf_definition_kind"],
    )

    print(
        "OpenFisca-Core version:",
        summary["openfisca_core_version"],
    )

    print(
        "Dependency symbols traced:",
        summary["dependency_symbol_traces"],
    )

    print("Candidate certifications issued: 0")

    print("Terminal outcomes assigned: 0")

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
