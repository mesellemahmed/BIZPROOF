from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypeAlias

from .generalization_semantic_evidence import (
    _load_json,
    _load_jsonl,
)

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"

EXPECTED_OCCURRENCES = 170
EXPECTED_CONTRACTS = 15


def _expr(
    expression: str,
) -> ast.AST | None:

    try:
        return ast.parse(
            expression,
            mode="eval",
        ).body

    except SyntaxError:
        return None


def _arg_kind(
    node: ast.AST,
) -> str:

    if isinstance(
        node,
        ast.Constant,
    ):
        if isinstance(
            node.value,
            str,
        ):
            return "CONST_STR"

        if isinstance(
            node.value,
            bool,
        ):
            return "CONST_BOOL"

        if isinstance(
            node.value,
            (int, float),
        ):
            return "CONST_NUM"

        if node.value is None:
            return "CONST_NONE"

        return "CONST"

    if isinstance(
        node,
        ast.Name,
    ):
        return "NAME"

    if isinstance(
        node,
        ast.Attribute,
    ):
        return "ATTRIBUTE"

    if isinstance(
        node,
        ast.Call,
    ):
        return "CALL"

    return "EXPR"


def _signature(
    expression: str,
) -> str:

    node = _expr(expression)

    if not isinstance(
        node,
        ast.Call,
    ):
        return "UNPARSEABLE"

    positional = ",".join(_arg_kind(argument) for argument in node.args)

    keywords = ",".join(keyword.arg or "**" for keyword in node.keywords)

    if isinstance(
        node.func,
        ast.Name,
    ):
        prefix = "FUNCTION"

    elif isinstance(
        node.func,
        ast.Attribute,
    ):
        receiver = node.func.value

        if isinstance(
            receiver,
            ast.Name,
        ):
            receiver_kind = "NAME"

        elif isinstance(
            receiver,
            ast.Attribute,
        ):
            receiver_kind = "ATTRIBUTE"

        elif isinstance(
            receiver,
            ast.Call,
        ):
            receiver_kind = "CALL"

        else:
            receiver_kind = type(receiver).__name__

        prefix = f"METHOD:{receiver_kind}"

    else:
        prefix = type(node.func).__name__

    return f"{prefix}|pos={positional}|kw={keywords}"


def _protocol_groups(
    resolutions: list[JsonDict],
) -> list[JsonDict]:

    grouped: dict[
        tuple[
            str,
            str,
            str,
        ],
        list[JsonDict],
    ] = defaultdict(list)

    for item in resolutions:
        status = str(item["resolution_status"])

        if status not in {
            "FUNCTION_PARAMETER_BOUNDARY",
            "PARAMETER_METHOD_BOUNDARY",
        }:
            continue

        binding = item.get("authoritative_binding")

        if not isinstance(
            binding,
            dict,
        ):
            continue

        if status == "FUNCTION_PARAMETER_BOUNDARY":
            subject = str(binding.get("parameter") or "")

        else:
            subject = str(binding.get("receiver_root") or binding.get("receiver") or "")

        key = (
            str(item["primitive"]),
            status,
            subject,
        )

        grouped[key].append(item)

    result: list[JsonDict] = []

    for (
        primitive,
        status,
        subject,
    ), items in grouped.items():
        signatures = Counter(_signature(str(item["source_expression"])) for item in items)

        result.append(
            {
                "primitive": primitive,
                "resolution_status": status,
                "subject": subject,
                "occurrences": len(items),
                "candidate_ids": sorted({str(item["candidate_id"]) for item in items}),
                "signatures": dict(sorted(signatures.items())),
                "examples": [str(item["source_expression"]) for item in items[:8]],
                "protocol_status": "DRAFT_ONLY",
                "certification_claim": False,
            }
        )

    return sorted(
        result,
        key=lambda item: (
            -int(item["occurrences"]),
            str(item["primitive"]),
            str(item["resolution_status"]),
        ),
    )


def _dependency_modules(
    item: JsonDict,
) -> set[str]:

    modules: set[str] = set()

    binding = item.get("authoritative_binding")

    if isinstance(
        binding,
        dict,
    ):
        target = binding.get("target_module")

        if target:
            modules.add(str(target))

    trace = item.get("trace")

    if isinstance(
        trace,
        dict,
    ):
        for step in trace.get(
            "steps",
            [],
        ):
            if not isinstance(
                step,
                dict,
            ):
                continue

            module_name = step.get("module")

            target_module = step.get("target_module")

            if module_name:
                modules.add(str(module_name))

            if target_module:
                modules.add(str(target_module))

    return modules


def _manifest_evidence(
    source_root: Path,
    package_root: str,
) -> list[JsonDict]:

    variants = {
        package_root.lower(),
        package_root.lower().replace(
            "_",
            "-",
        ),
        package_root.lower().replace(
            "-",
            "_",
        ),
    }

    manifest_names = {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "requirements-dev.txt",
        "requirements_dev.txt",
        "Pipfile",
        "Pipfile.lock",
        "poetry.lock",
        "uv.lock",
    }

    evidence: list[JsonDict] = []

    for path in source_root.rglob("*"):
        if not path.is_file():
            continue

        if not (
            path.name in manifest_names
            or (path.name.startswith("requirements") and path.suffix == ".txt")
        ):
            continue

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        for (
            line_number,
            line,
        ) in enumerate(
            text.splitlines(),
            start=1,
        ):
            lowered = line.lower()

            if not any(variant in lowered for variant in variants):
                continue

            stripped = line.strip()

            evidence.append(
                {
                    "file": str(path.relative_to(source_root)).replace(
                        "\\",
                        "/",
                    ),
                    "line": line_number,
                    "text": stripped,
                    "exact_pin_detected": ("==" in stripped),
                }
            )

    return evidence


def _dependency_targets(
    resolutions: list[JsonDict],
    external_root: Path,
) -> list[JsonDict]:

    grouped: dict[
        tuple[
            str,
            str,
        ],
        JsonDict,
    ] = {}

    for item in resolutions:
        if str(item["resolution_status"]) not in {
            "EXTERNAL_DEPENDENCY_BOUNDARY",
            "WILDCARD_IMPORT_BOUNDARY",
        }:
            continue

        modules = _dependency_modules(item)

        if not modules:
            modules = {"UNKNOWN"}

        for module_name in modules:
            package_root = module_name.split(".")[0] if (module_name != "UNKNOWN") else "UNKNOWN"

            key = (
                str(item["source_id"]),
                package_root,
            )

            if key not in grouped:
                grouped[key] = {
                    "source_id": str(item["source_id"]),
                    "package_root": package_root,
                    "modules": set(),
                    "primitives": set(),
                    "candidate_ids": set(),
                    "occurrences": 0,
                }

            group = grouped[key]

            group["modules"].add(module_name)

            group["primitives"].add(str(item["primitive"]))

            group["candidate_ids"].add(str(item["candidate_id"]))

            group["occurrences"] += 1

    result: list[JsonDict] = []

    for group in grouped.values():
        source_id = str(group["source_id"])

        package_root = str(group["package_root"])

        standard_library = package_root in sys.stdlib_module_names

        evidence: list[JsonDict] = []

        if not standard_library and package_root != "UNKNOWN":
            source_root = external_root / source_id

            if source_root.is_dir():
                evidence = _manifest_evidence(
                    source_root,
                    package_root,
                )

        if standard_library:
            lock_status = "PYTHON_STDLIB"

        elif any(bool(item["exact_pin_detected"]) for item in evidence):
            lock_status = "EXACT_PIN_DISCOVERED"

        elif evidence:
            lock_status = "CONSTRAINT_DISCOVERED"

        else:
            lock_status = "LOCK_EVIDENCE_MISSING"

        result.append(
            {
                "source_id": source_id,
                "package_root": package_root,
                "modules": sorted(group["modules"]),
                "primitives": sorted(group["primitives"]),
                "candidate_ids": sorted(group["candidate_ids"]),
                "occurrences": int(group["occurrences"]),
                "standard_library": standard_library,
                "lock_status": lock_status,
                "manifest_evidence": evidence,
                "resolution_status": "UNRESOLVED",
                "certification_claim": False,
            }
        )

    return sorted(
        result,
        key=lambda item: (
            0 if bool(item["standard_library"]) else 1,
            str(item["package_root"]),
            str(item["source_id"]),
        ),
    )


def _local_analysis(
    resolutions: list[JsonDict],
    external_root: Path,
) -> list[JsonDict]:

    result: list[JsonDict] = []

    for item in resolutions:
        status = str(item["resolution_status"])

        if status not in {
            "LOCAL_ASSIGNMENT",
            "LOCAL_DEFINITION",
        }:
            continue

        binding = item.get("authoritative_binding")

        if not isinstance(
            binding,
            dict,
        ):
            continue

        record: JsonDict = {
            "candidate_id": str(item["candidate_id"]),
            "source_id": str(item["source_id"]),
            "primitive": str(item["primitive"]),
            "resolution_status": status,
            "analysis_status": "REVIEW_REQUIRED",
            "certification_claim": False,
        }

        # PHASE-K-AUTHORITATIVE-LOCAL-DEFINITION-SEED
        # Phase J already proved the LOCAL_DEFINITION binding.
        # AST body rediscovery below is enrichment only.
        if status == "LOCAL_DEFINITION":
            record["analysis_status"] = "LOCAL_DEFINITION_SEED"

        if status == "LOCAL_ASSIGNMENT":
            source = str(binding.get("source") or "")

            try:
                statement = ast.parse(source).body[0]

            except SyntaxError:
                statement = None

            if isinstance(
                statement,
                ast.Assign,
            ):
                value = statement.value

                if isinstance(
                    value,
                    ast.Call,
                ):
                    record["assignment_shape"] = "FACTORY_CALL"

                    record["factory"] = ast.unparse(value.func)

                    record["analysis_status"] = "TRANSITIVE_FACTORY_REVIEW"

                elif isinstance(
                    value,
                    ast.Constant,
                ):
                    record["assignment_shape"] = "LITERAL"

                    record["analysis_status"] = "LOCAL_LITERAL_SEED"

                else:
                    record["assignment_shape"] = type(value).__name__

        else:
            relative_file = str(item["file"])

            source_path = external_root / str(item["source_id"]) / relative_file

            line = binding.get("line")

            if source_path.is_file() and isinstance(
                line,
                int,
            ):
                text = source_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )

                tree = ast.parse(text)

                target = None

                for node in ast.walk(tree):
                    if (
                        isinstance(
                            node,
                            (
                                ast.FunctionDef,
                                ast.AsyncFunctionDef,
                            ),
                        )
                        and int(node.lineno) == line
                    ):
                        target = node
                        break

                if target is not None:
                    calls: set[str] = set()

                    control: set[str] = set()

                    for child in ast.walk(target):
                        if isinstance(
                            child,
                            ast.Call,
                        ):
                            calls.add(ast.unparse(child.func))

                        elif isinstance(
                            child,
                            ast.If,
                        ):
                            control.add("If")

                        elif isinstance(
                            child,
                            ast.For,
                        ):
                            control.add("For")

                        elif isinstance(
                            child,
                            ast.While,
                        ):
                            control.add("While")

                        elif isinstance(
                            child,
                            ast.IfExp,
                        ):
                            control.add("IfExp")

                    record["calls"] = sorted(calls)

                    record["control_flow"] = sorted(control)

                    record["analysis_status"] = "LOCAL_DEFINITION_SEED"

        result.append(record)

    return sorted(
        result,
        key=lambda item: (
            str(item["primitive"]),
            str(item["candidate_id"]),
        ),
    )


def _action(
    primitive: str,
    statuses: set[str],
    dependencies: list[JsonDict],
    local_analysis: list[JsonDict],
) -> str:

    if statuses == {"FUNCTION_PARAMETER_BOUNDARY"}:
        return "PARAMETER_PROTOCOL_SPEC_READY"

    if statuses == {"PARAMETER_METHOD_BOUNDARY"}:
        return "PARAMETER_METHOD_PROTOCOL_SPEC_READY"

    if statuses == {
        "FUNCTION_PARAMETER_BOUNDARY",
        "PARAMETER_METHOD_BOUNDARY",
    }:
        return "SPLIT_PROTOCOL_FAMILIES"

    if statuses == {"METHOD_CONTEXT_BOUNDARY"}:
        return "METHOD_RECEIVER_REVIEW"

    if statuses and statuses <= {
        "LOCAL_ASSIGNMENT",
        "LOCAL_DEFINITION",
    }:
        related = [item for item in local_analysis if (str(item["primitive"]) == primitive)]

        analysis_statuses = {str(item["analysis_status"]) for item in related}

        if "TRANSITIVE_FACTORY_REVIEW" in analysis_statuses:
            return "TRANSITIVE_FACTORY_REVIEW"

        if analysis_statuses == {"LOCAL_DEFINITION_SEED"}:
            return "LOCAL_DEFINITION_CONTRACT_SEED"

        if analysis_statuses == {"LOCAL_LITERAL_SEED"}:
            return "LOCAL_LITERAL_CONTRACT_SEED"

        return "LOCAL_SOURCE_REVIEW"

    if statuses & {
        "EXTERNAL_DEPENDENCY_BOUNDARY",
        "WILDCARD_IMPORT_BOUNDARY",
    }:
        related_dependencies = [item for item in dependencies if primitive in item["primitives"]]

        if related_dependencies and all(
            bool(item["standard_library"]) for item in related_dependencies
        ):
            return "STDLIB_CONTRACT_SEED"

        if any(str(item["lock_status"]) == "EXACT_PIN_DISCOVERED" for item in related_dependencies):
            return "DEPENDENCY_SOURCE_LOCK_READY"

        if any(
            str(item["lock_status"]) == "CONSTRAINT_DISCOVERED" for item in related_dependencies
        ):
            return "DEPENDENCY_VERSION_RESOLUTION_REQUIRED"

        return "DEPENDENCY_LOCK_REQUIRED"

    return "CLOSURE_REVIEW_REQUIRED"


def build_closure(
    *,
    name_summary_path: Path,
    occurrence_resolution_path: Path,
    contract_queue_path: Path,
    external_root: Path,
    output_dir: Path,
) -> JsonDict:

    name_summary = _load_json(name_summary_path)

    if str(name_summary["cohort_sha256"]) != EXPECTED_COHORT:
        raise ValueError("cohort digest changed")

    resolutions = _load_jsonl(occurrence_resolution_path)

    if len(resolutions) != EXPECTED_OCCURRENCES:
        raise ValueError("binding occurrence count changed")

    contract_entries = _load_json(contract_queue_path)["entries"]

    if len(contract_entries) != EXPECTED_CONTRACTS:
        raise ValueError("contract candidate count changed")

    protocols = _protocol_groups(resolutions)

    dependencies = _dependency_targets(
        resolutions,
        external_root,
    )

    local_targets = _local_analysis(
        resolutions,
        external_root,
    )

    grouped: dict[
        tuple[
            str,
            str,
            str,
        ],
        list[JsonDict],
    ] = defaultdict(list)

    for item in resolutions:
        key = (
            str(item["family_class"]),
            str(item["kind"]),
            str(item["primitive"]),
        )

        grouped[key].append(item)

    queue: list[JsonDict] = []

    for entry in contract_entries:
        key = (
            str(entry["family_class"]),
            str(entry["kind"]),
            str(entry["primitive"]),
        )

        related = grouped.get(
            key,
            [],
        )

        statuses = {str(item["resolution_status"]) for item in related}

        primitive = str(entry["primitive"])

        queue.append(
            {
                "registry_id": str(entry["registry_id"]),
                "family_class": str(entry["family_class"]),
                "kind": str(entry["kind"]),
                "primitive": primitive,
                "candidate_count": int(entry["candidate_count"]),
                "occurrence_count": len(related),
                "resolution_statuses": sorted(statuses),
                "closure_action": _action(
                    primitive,
                    statuses,
                    dependencies,
                    local_targets,
                ),
                "semantic_type": "UNRESOLVED",
                "semantic_contract_status": "MISSING",
                "resolution_status": "UNRESOLVED",
                "certification_claim": False,
            }
        )

    queue.sort(
        key=lambda item: (
            str(item["closure_action"]),
            -int(item["candidate_count"]),
            str(item["primitive"]),
        )
    )

    action_counts = Counter(str(item["closure_action"]) for item in queue)

    dependency_counts = Counter(str(item["lock_status"]) for item in dependencies)

    local_counts = Counter(str(item["analysis_status"]) for item in local_targets)

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "PROTOCOL_DEPENDENCY_CLOSURE",
        "cohort_sha256": EXPECTED_COHORT,
        "binding_occurrences": len(resolutions),
        "contract_candidates": len(queue),
        "protocol_groups": len(protocols),
        "dependency_targets": len(dependencies),
        "local_source_targets": len(local_targets),
        "closure_action_counts": dict(sorted(action_counts.items())),
        "dependency_lock_status_counts": dict(sorted(dependency_counts.items())),
        "local_analysis_status_counts": dict(sorted(local_counts.items())),
        "semantic_types_resolved": 0,
        "semantic_contracts_validated": 0,
        "all_contracts_unresolved": True,
        "certification_claim": False,
        "passed": (len(queue) == EXPECTED_CONTRACTS),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    outputs = {
        "protocols.json": {
            "groups": protocols,
            "certification_claim": False,
        },
        "dependency_manifest.json": {
            "targets": dependencies,
            "certification_claim": False,
        },
        "local_source_analysis.json": {
            "targets": local_targets,
            "certification_claim": False,
        },
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

    (output_dir / "closure_queue.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in queue
        ),
        encoding="utf-8",
    )

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(
            [
                ("# BIZPROOF V0.11 Protocol and Dependency Closure"),
                "",
                (f"- Protocol groups: {len(protocols)}"),
                (f"- Dependency targets: {len(dependencies)}"),
                (f"- Local source targets: {len(local_targets)}"),
                "- Semantic types resolved: 0",
                "- Semantic contracts validated: 0",
                "",
                ("This phase structures evidence for contract authoring only."),
                "",
            ]
        ),
        encoding="utf-8",
    )

    return summary


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--name-summary",
        type=Path,
        default=Path("benchmarks/v0.11/name_resolution/summary.json"),
    )

    parser.add_argument(
        "--occurrence-resolution",
        type=Path,
        default=Path("benchmarks/v0.11/name_resolution/occurrence_resolution.jsonl"),
    )

    parser.add_argument(
        "--contract-queue",
        type=Path,
        default=Path("benchmarks/v0.11/name_resolution/contract_queue.json"),
    )

    parser.add_argument(
        "--external-root",
        type=Path,
        default=Path("external_sources/v0.6"),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/protocol_closure"),
    )

    args = parser.parse_args()

    summary = build_closure(
        name_summary_path=args.name_summary,
        occurrence_resolution_path=args.occurrence_resolution,
        contract_queue_path=args.contract_queue,
        external_root=args.external_root,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 protocol/dependency closure")

    print(
        "Protocol groups:",
        summary["protocol_groups"],
    )

    print(
        "Dependency targets:",
        summary["dependency_targets"],
    )

    print(
        "Local source targets:",
        summary["local_source_targets"],
    )

    print(
        "Actions:",
        summary["closure_action_counts"],
    )

    print(
        "Dependency locks:",
        summary["dependency_lock_status_counts"],
    )

    print("Semantic types resolved: 0")

    print("Semantic contracts validated: 0")

    print("Certification claim: NO")

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
