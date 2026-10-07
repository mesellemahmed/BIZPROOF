from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypeAlias

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"
EXPECTED_BINDING_CANDIDATES = 36

TYPE_BOOL = "BOOL"
TYPE_NUMERIC = "NUMERIC"
TYPE_ORDERABLE = "ORDERABLE"
TYPE_ANY = "ANY"

TYPE_PRIORITY = {
    TYPE_ANY: 0,
    TYPE_ORDERABLE: 1,
    TYPE_NUMERIC: 2,
    TYPE_BOOL: 3,
}

OPENFISCA_ENTITY_PRIMITIVES = {
    "foyer_fiscal",
    "individu",
    "famille",
    "menage",
}

SEMANTIC_LIBRARY_PRIMITIVES = {
    "not_",
    "min_",
    "max_",
    "where",
}


def _load_json(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[JsonDict]:
    records: list[JsonDict] = []

    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = line.strip()
        if not line:
            continue

        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"record {number} in {path} is not an object")

        records.append(value)

    return records


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _binding_family_class(
    binding: JsonDict,
) -> str:
    kind = str(binding["kind"])
    primitive = str(binding["primitive"])

    if kind == "GLOBAL_NAME":
        return "GLOBAL_CONSTANT"

    if kind == "ATTRIBUTE":
        return "OBJECT_ATTRIBUTE"

    if kind == "CALL":
        if primitive in OPENFISCA_ENTITY_PRIMITIVES:
            return "OPENFISCA_ENTITY_LOOKUP"

        if primitive in SEMANTIC_LIBRARY_PRIMITIVES:
            return "SEMANTIC_LIBRARY_PRIMITIVE"

        return "EXTERNAL_CALL"

    return "OTHER"


def _parse_call_descriptor(
    binding: JsonDict,
) -> JsonDict | None:
    if str(binding["kind"]) != "CALL":
        return None

    expression = str(binding["source_expression"])

    try:
        node = ast.parse(
            expression,
            mode="eval",
        ).body
    except SyntaxError:
        return None

    if not isinstance(node, ast.Call):
        return None

    arguments: list[JsonDict] = []

    for argument in node.args:
        if isinstance(argument, ast.Constant):
            arguments.append(
                {
                    "kind": "CONSTANT",
                    "value": argument.value,
                }
            )
        else:
            arguments.append(
                {
                    "kind": "EXPRESSION",
                    "value": ast.unparse(argument),
                }
            )

    keyword_arguments = [
        {
            "name": keyword.arg,
            "value": ast.unparse(keyword.value),
        }
        for keyword in node.keywords
    ]

    variable_name: str | None = None

    if (
        str(binding["primitive"]) in OPENFISCA_ENTITY_PRIMITIVES
        and arguments
        and arguments[0]["kind"] == "CONSTANT"
        and isinstance(arguments[0]["value"], str)
    ):
        variable_name = str(arguments[0]["value"])

    return {
        "arguments": arguments,
        "keyword_arguments": keyword_arguments,
        "openfisca_variable_name": variable_name,
    }


def _record_requirement(
    requirements: dict[str, set[str]],
    binding_id: str,
    required_type: str,
) -> None:
    requirements[binding_id].add(required_type)


def _propagate_requirement(
    node: Any,
    required_type: str,
    requirements: dict[str, set[str]],
) -> None:
    if not isinstance(node, dict):
        return

    op = str(node.get("op", ""))

    if op == "binding":
        binding_id = str(node["binding_id"])
        _record_requirement(
            requirements,
            binding_id,
            required_type,
        )
        return

    if op in {"not"}:
        _propagate_requirement(
            node["value"],
            TYPE_BOOL,
            requirements,
        )
        return

    if op in {"and", "or"}:
        for value in node["values"]:
            _propagate_requirement(
                value,
                TYPE_BOOL,
                requirements,
            )
        return

    if op in {"add", "sub", "mul"}:
        _propagate_requirement(
            node["left"],
            TYPE_NUMERIC,
            requirements,
        )
        _propagate_requirement(
            node["right"],
            TYPE_NUMERIC,
            requirements,
        )
        return

    if op == "compare":
        operators = [str(value) for value in node["operators"]]

        if any(value in {"lt", "le", "gt", "ge"} for value in operators):
            comparison_type = TYPE_ORDERABLE
        else:
            comparison_type = TYPE_ANY

        _propagate_requirement(
            node["left"],
            comparison_type,
            requirements,
        )

        for value in node["comparators"]:
            _propagate_requirement(
                value,
                comparison_type,
                requirements,
            )

        return

    if op == "ite":
        _propagate_requirement(
            node["condition"],
            TYPE_BOOL,
            requirements,
        )
        _propagate_requirement(
            node["then"],
            required_type,
            requirements,
        )
        _propagate_requirement(
            node["else"],
            required_type,
            requirements,
        )
        return

    if op in {"neg", "pos"}:
        _propagate_requirement(
            node["value"],
            TYPE_NUMERIC,
            requirements,
        )
        return

    for value in node.values():
        if isinstance(value, dict):
            _propagate_requirement(
                value,
                required_type,
                requirements,
            )
        elif isinstance(value, list):
            for child in value:
                _propagate_requirement(
                    child,
                    required_type,
                    requirements,
                )


def _root_type(ir: JsonDict) -> str:
    node = ir["return"]
    op = str(node.get("op", ""))

    if op in {"compare", "not", "and", "or"}:
        return TYPE_BOOL

    if op in {"add", "sub", "mul", "neg", "pos"}:
        return TYPE_NUMERIC

    if op == "const":
        const_type = str(node.get("type"))

        if const_type == "bool":
            return TYPE_BOOL

        if const_type in {"int", "float"}:
            return TYPE_NUMERIC

        return TYPE_ANY

    return TYPE_ANY


def _normalize_requirements(
    values: set[str],
) -> JsonDict:
    normalized = sorted(
        values,
        key=lambda value: (
            TYPE_PRIORITY.get(value, 99),
            value,
        ),
    )

    incompatible = TYPE_BOOL in values and (TYPE_NUMERIC in values or TYPE_ORDERABLE in values)

    if incompatible:
        inferred = "CONFLICT"
    elif TYPE_BOOL in values:
        inferred = TYPE_BOOL
    elif TYPE_NUMERIC in values:
        inferred = TYPE_NUMERIC
    elif TYPE_ORDERABLE in values:
        inferred = TYPE_ORDERABLE
    else:
        inferred = TYPE_ANY

    return {
        "requirements": normalized,
        "inferred_type": inferred,
        "conflict": incompatible,
    }


def _candidate_contract_skeleton(
    probe: JsonDict,
) -> JsonDict:
    ir = probe["ir"]

    if not isinstance(ir, dict):
        raise ValueError(f"probe is not IR-ready: {probe['candidate_id']}")

    requirements: dict[str, set[str]] = defaultdict(set)

    _propagate_requirement(
        ir["return"],
        _root_type(ir),
        requirements,
    )

    obligations: list[JsonDict] = []

    for binding in probe["required_bindings"]:
        binding_id = str(binding["binding_id"])
        normalized = _normalize_requirements(
            requirements.get(
                binding_id,
                {TYPE_ANY},
            )
        )

        descriptor = _parse_call_descriptor(binding)

        obligations.append(
            {
                "binding_id": binding_id,
                "kind": str(binding["kind"]),
                "primitive": str(binding["primitive"]),
                "source_expression": str(binding["source_expression"]),
                "family_class": _binding_family_class(binding),
                "type_requirements": normalized["requirements"],
                "inferred_type": normalized["inferred_type"],
                "type_conflict": normalized["conflict"],
                "call_descriptor": descriptor,
                "resolution_status": "UNRESOLVED",
            }
        )

    conflicts = [item for item in obligations if bool(item["type_conflict"])]

    unknowns = [item for item in obligations if str(item["inferred_type"]) == TYPE_ANY]

    if conflicts:
        readiness = "TYPE_CONFLICT_REVIEW"
    elif unknowns:
        readiness = "TYPE_SKELETON_PARTIAL"
    else:
        readiness = "TYPE_SKELETON_READY"

    return {
        "candidate_id": str(probe["candidate_id"]),
        "source_id": str(probe["source_id"]),
        "file": str(probe["file"]),
        "enclosing_class": probe["enclosing_class"],
        "function": str(probe["function"]),
        "adaptation_complexity": str(probe["adaptation_complexity"]),
        "semantic_shape": str(probe["semantic_shape"]),
        "function_parameters": probe["function_parameters"],
        "input_references": probe["input_references"],
        "output_type_skeleton": _root_type(ir),
        "binding_obligations": obligations,
        "binding_count": len(obligations),
        "unresolved_binding_count": len(obligations),
        "type_conflict_count": len(conflicts),
        "unknown_type_count": len(unknowns),
        "readiness": readiness,
        "domain_status": "UNRESOLVED",
        "contract_status": "SKELETON_ONLY",
        "certification_claim": False,
    }


def build_contract_skeletons(
    *,
    probe_summary_path: Path,
    probe_path: Path,
    workplan_summary_path: Path,
    queue_path: Path,
    output_dir: Path,
) -> JsonDict:
    probe_summary = _load_json(probe_summary_path)
    workplan_summary = _load_json(workplan_summary_path)

    if str(probe_summary["cohort_sha256"]) != EXPECTED_COHORT_SHA256:
        raise ValueError("probe cohort digest mismatch")

    if str(workplan_summary["cohort_sha256"]) != EXPECTED_COHORT_SHA256:
        raise ValueError("workplan cohort digest mismatch")

    probes = _load_jsonl(probe_path)
    queue = _load_jsonl(queue_path)

    probe_map = {str(item["candidate_id"]): item for item in probes}

    binding_candidate_ids = [
        str(item["candidate_id"]) for item in queue if str(item["route"]) == "BINDING_DEFINITION"
    ]

    if len(binding_candidate_ids) != EXPECTED_BINDING_CANDIDATES:
        raise ValueError(
            f"expected {EXPECTED_BINDING_CANDIDATES} "
            "BINDING_DEFINITION candidates, got "
            f"{len(binding_candidate_ids)}"
        )

    skeletons: list[JsonDict] = []

    for candidate_id in binding_candidate_ids:
        probe = probe_map.get(candidate_id)

        if probe is None:
            raise ValueError(f"missing symbolic probe for {candidate_id}")

        if str(probe["probe_status"]) != "SYMBOLIC_FRONTEND_READY":
            raise ValueError(f"binding candidate is not IR-ready: {candidate_id}")

        skeletons.append(_candidate_contract_skeleton(probe))

    readiness_counts = Counter(str(item["readiness"]) for item in skeletons)

    family_class_counts = Counter(
        str(obligation["family_class"])
        for item in skeletons
        for obligation in item["binding_obligations"]
    )

    inferred_type_counts = Counter(
        str(obligation["inferred_type"])
        for item in skeletons
        for obligation in item["binding_obligations"]
    )

    primitive_groups: dict[
        tuple[str, str, str],
        list[JsonDict],
    ] = defaultdict(list)

    for item in skeletons:
        for obligation in item["binding_obligations"]:
            primitive_key = (
                str(obligation["family_class"]),
                str(obligation["kind"]),
                str(obligation["primitive"]),
            )
            primitive_groups[primitive_key].append(
                {
                    "candidate_id": item["candidate_id"],
                    "binding_id": obligation["binding_id"],
                    "source_expression": obligation["source_expression"],
                    "inferred_type": obligation["inferred_type"],
                    "call_descriptor": obligation["call_descriptor"],
                }
            )

    registry_entries: list[JsonDict] = []

    for (
        family_class,
        kind,
        primitive,
    ), occurrences in primitive_groups.items():
        candidate_ids = sorted({str(item["candidate_id"]) for item in occurrences})

        types = sorted({str(item["inferred_type"]) for item in occurrences})

        registry_id = (
            "BR-"
            + hashlib.sha256(
                (family_class + "|" + kind + "|" + primitive).encode("utf-8")
            ).hexdigest()[:12]
        )

        registry_entries.append(
            {
                "registry_id": registry_id,
                "family_class": family_class,
                "kind": kind,
                "primitive": primitive,
                "candidate_count": len(candidate_ids),
                "occurrence_count": len(occurrences),
                "candidate_ids": candidate_ids,
                "observed_inferred_types": types,
                "resolution_status": "UNRESOLVED",
                "semantic_definition_status": "MISSING",
                "domain_definition_status": "MISSING",
                "implementation_status": "NOT_IMPLEMENTED",
                "examples": [str(item["source_expression"]) for item in occurrences[:10]],
                "certification_claim": False,
            }
        )

    registry_entries.sort(
        key=lambda item: (
            -int(item["candidate_count"]),
            -int(item["occurrence_count"]),
            str(item["family_class"]),
            str(item["primitive"]),
        )
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "CONTRACT_AND_BINDING_SKELETON",
        "cohort_sha256": EXPECTED_COHORT_SHA256,
        "binding_candidates": len(skeletons),
        "readiness_counts": dict(sorted(readiness_counts.items())),
        "family_class_counts": dict(sorted(family_class_counts.items())),
        "inferred_type_counts": dict(sorted(inferred_type_counts.items())),
        "binding_registry_entries": len(registry_entries),
        "all_bindings_unresolved": all(
            item["resolution_status"] == "UNRESOLVED" for item in registry_entries
        ),
        "certification_claim": False,
        "passed": (len(skeletons) == EXPECTED_BINDING_CANDIDATES),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_dir / "contract_skeletons.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in skeletons
        ),
        encoding="utf-8",
    )

    (output_dir / "binding_registry.json").write_text(
        json.dumps(
            {
                "benchmark_version": "0.11.0",
                "phase": "BINDING_REGISTRY_SKELETON",
                "cohort_sha256": EXPECTED_COHORT_SHA256,
                "entries": registry_entries,
                "certification_claim": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    report = [
        "# BIZPROOF V0.11 Contract and Binding Skeleton",
        "",
        (
            "This phase derives conservative type/context skeletons for the "
            "36 BINDING_DEFINITION candidates. It does not invent business "
            "semantics, finite domains, or binding implementations."
        ),
        "",
        f"- Binding candidates: {len(skeletons)}",
        (f"- Binding registry entries: {len(registry_entries)}"),
        "",
        "## Readiness",
        "",
    ]

    for readiness_name, value in sorted(readiness_counts.items()):
        report.append(f"- `{readiness_name}`: {value}")

    report.extend(
        [
            "",
            "## Binding family classes",
            "",
        ]
    )

    for family_class_name, value in sorted(family_class_counts.items()):
        report.append(f"- `{family_class_name}`: {value}")

    report.extend(
        [
            "",
            "## Scientific boundary",
            "",
            (
                "All registry entries remain UNRESOLVED. Inferred types come "
                "only from structural use in the current BSIR skeleton and are "
                "not substitutes for business-domain definitions."
            ),
            "",
        ]
    )

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--probe-summary",
        type=Path,
        default=Path("benchmarks/v0.11/symbolic_probe/summary.json"),
    )
    parser.add_argument(
        "--probe",
        type=Path,
        default=Path("benchmarks/v0.11/symbolic_probe/probe.jsonl"),
    )
    parser.add_argument(
        "--workplan-summary",
        type=Path,
        default=Path("benchmarks/v0.11/workplan/summary.json"),
    )
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path("benchmarks/v0.11/workplan/queue.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/contracts"),
    )

    args = parser.parse_args()

    summary = build_contract_skeletons(
        probe_summary_path=args.probe_summary,
        probe_path=args.probe,
        workplan_summary_path=args.workplan_summary,
        queue_path=args.queue,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 contract/binding skeleton")
    print(
        "Binding candidates:",
        summary["binding_candidates"],
    )
    print(
        "Readiness:",
        summary["readiness_counts"],
    )
    print(
        "Binding registry entries:",
        summary["binding_registry_entries"],
    )
    print(
        "All bindings unresolved:",
        summary["all_bindings_unresolved"],
    )
    print("Certification claim: NO")
    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
