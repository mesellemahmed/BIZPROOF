from __future__ import annotations

import argparse
import ast
import builtins
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypeAlias

from .generalization_semantic_evidence import (
    _load_json,
    _load_jsonl,
    _verify_locked_commits,
)
from .generalization_symbol_trace import (
    _absolute_import_module,
    _trace_symbol,
)

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"

EXPECTED_REGISTRY_ENTRIES = 58
EXPECTED_BINDING_OCCURRENCES = 170
EXPECTED_CONTRACT_CANDIDATES = 15


def _module_name_from_relative(
    path: str,
) -> tuple[str, bool]:

    relative = Path(path)

    parts = list(relative.parts)

    if not parts:
        raise ValueError("empty source path")

    # Common src-layout repositories:
    #
    # src/oscar/...   -> oscar....
    # src/pretix/...  -> pretix....
    if parts and parts[0] == "src":
        parts = parts[1:]

    if not parts:
        raise ValueError("invalid module path")

    if parts[-1] == "__init__.py":
        parts = parts[:-1]
        is_package = True

    else:
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]

        is_package = False

    return (
        ".".join(parts),
        is_package,
    )


def _parse_expression(
    expression: str,
) -> ast.AST | None:

    try:
        return ast.parse(
            expression,
            mode="eval",
        ).body

    except SyntaxError:
        return None


def _leftmost_name(
    node: ast.AST,
) -> str | None:

    current = node

    while True:
        if isinstance(
            current,
            ast.Name,
        ):
            return current.id

        if isinstance(
            current,
            ast.Attribute,
        ):
            current = current.value

            continue

        if isinstance(
            current,
            ast.Subscript,
        ):
            current = current.value

            continue

        if isinstance(
            current,
            ast.Call,
        ):
            current = current.func

            continue

        return None


def _module_binding_events(
    tree: ast.Module,
    *,
    symbol: str,
    module_name: str,
    is_package: bool,
) -> list[JsonDict]:

    events: list[JsonDict] = []

    for node in tree.body:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            if node.name == symbol:
                events.append(
                    {
                        "binding_kind": "LOCAL_DEFINITION",
                        "line": int(node.lineno),
                        "source": ast.unparse(node).splitlines()[0],
                        "definition_type": type(node).__name__,
                    }
                )

        elif isinstance(
            node,
            ast.Assign,
        ):
            names = [
                target.id
                for target in node.targets
                if isinstance(
                    target,
                    ast.Name,
                )
            ]

            if symbol in names:
                events.append(
                    {
                        "binding_kind": "LOCAL_ASSIGNMENT",
                        "line": int(node.lineno),
                        "source": ast.unparse(node),
                    }
                )

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            if (
                isinstance(
                    node.target,
                    ast.Name,
                )
                and node.target.id == symbol
            ):
                events.append(
                    {
                        "binding_kind": "LOCAL_ASSIGNMENT",
                        "line": int(node.lineno),
                        "source": ast.unparse(node),
                    }
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            target_module = _absolute_import_module(
                current_module=module_name,
                current_is_package=is_package,
                imported_module=node.module,
                level=int(node.level),
            )

            for alias in node.names:
                if alias.name == "*":
                    events.append(
                        {
                            "binding_kind": "WILDCARD_IMPORT",
                            "line": int(node.lineno),
                            "source": ast.unparse(node),
                            "target_module": target_module,
                            "target_symbol": symbol,
                        }
                    )

                    continue

                local_name = alias.asname or alias.name

                if local_name == symbol:
                    events.append(
                        {
                            "binding_kind": "EXPLICIT_IMPORT",
                            "line": int(node.lineno),
                            "source": ast.unparse(node),
                            "target_module": target_module,
                            "target_symbol": alias.name,
                        }
                    )

        elif isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]

                if local_name == symbol:
                    events.append(
                        {
                            "binding_kind": "MODULE_IMPORT",
                            "line": int(node.lineno),
                            "source": ast.unparse(node),
                            "target_module": alias.name,
                            "target_symbol": symbol,
                        }
                    )

    return sorted(
        events,
        key=lambda item: int(item["line"]),
    )


def _resolve_module_symbol(
    *,
    tree: ast.Module,
    source_root: Path,
    module_name: str,
    is_package: bool,
    symbol: str,
) -> JsonDict:

    events = _module_binding_events(
        tree,
        symbol=symbol,
        module_name=module_name,
        is_package=is_package,
    )

    if not events:
        if symbol in dir(builtins):
            return {
                "resolution_status": "PYTHON_BUILTIN_BOUNDARY",
                "authoritative_binding": None,
                "binding_events": [],
                "trace": None,
            }

        return {
            "resolution_status": "NO_BINDING_EVIDENCE",
            "authoritative_binding": None,
            "binding_events": [],
            "trace": None,
        }

    # Python module execution is ordered.
    # The last relevant module-level binding event
    # is the effective module binding.
    authoritative = events[-1]

    kind = str(authoritative["binding_kind"])

    if kind in {
        "LOCAL_DEFINITION",
        "LOCAL_ASSIGNMENT",
    }:
        return {
            "resolution_status": kind,
            "authoritative_binding": authoritative,
            "binding_events": events,
            "trace": None,
        }

    if kind == "EXPLICIT_IMPORT":
        trace = _trace_symbol(
            source_root=source_root,
            module_name=str(authoritative["target_module"]),
            symbol=str(authoritative["target_symbol"]),
        )

        return {
            "resolution_status": str(trace["terminal_status"]),
            "authoritative_binding": authoritative,
            "binding_events": events,
            "trace": trace,
        }

    if kind == "WILDCARD_IMPORT":
        trace = _trace_symbol(
            source_root=source_root,
            module_name=str(authoritative["target_module"]),
            symbol=str(authoritative["target_symbol"]),
        )

        # Even when the symbol exists in the target
        # module, export through * is not assumed
        # without validating __all__/export behavior.
        return {
            "resolution_status": "WILDCARD_IMPORT_BOUNDARY",
            "authoritative_binding": authoritative,
            "binding_events": events,
            "trace": trace,
        }

    if kind == "MODULE_IMPORT":
        return {
            "resolution_status": "MODULE_IMPORT_BOUNDARY",
            "authoritative_binding": authoritative,
            "binding_events": events,
            "trace": None,
        }

    raise ValueError(f"unknown binding event: {kind}")


def _call_shape(
    node: ast.Call,
) -> JsonDict:

    return {
        "positional_arguments": [ast.unparse(argument) for argument in node.args],
        "keyword_arguments": [
            {
                "name": keyword.arg,
                "value": ast.unparse(keyword.value),
            }
            for keyword in node.keywords
        ],
    }


def _resolve_occurrence(
    *,
    occurrence: JsonDict,
    skeleton: JsonDict,
    source_root: Path,
    source_tree: ast.Module,
) -> JsonDict:

    primitive = str(occurrence["primitive"])

    binding_kind = str(occurrence["kind"])

    expression = str(occurrence["source_expression"])

    parameters = {str(value) for value in skeleton["function_parameters"]}

    (
        module_name,
        is_package,
    ) = _module_name_from_relative(str(occurrence["file"]))

    parsed = _parse_expression(expression)

    resolution: JsonDict

    # -------------------------------------------------
    # CALL
    # -------------------------------------------------

    if binding_kind == "CALL":
        if not isinstance(
            parsed,
            ast.Call,
        ):
            resolution = {
                "resolution_status": "UNPARSEABLE_CALL",
                "authoritative_binding": None,
                "binding_events": [],
                "trace": None,
            }

        elif isinstance(
            parsed.func,
            ast.Name,
        ):
            callable_name = parsed.func.id

            # Python lexical scope:
            # function parameters shadow module globals.
            if callable_name in parameters:
                resolution = {
                    "resolution_status": "FUNCTION_PARAMETER_BOUNDARY",
                    "authoritative_binding": {
                        "parameter": callable_name,
                        "call_shape": _call_shape(parsed),
                    },
                    "binding_events": [],
                    "trace": None,
                }

            else:
                resolution = _resolve_module_symbol(
                    tree=source_tree,
                    source_root=source_root,
                    module_name=module_name,
                    is_package=is_package,
                    symbol=callable_name,
                )

        elif isinstance(
            parsed.func,
            ast.Attribute,
        ):
            receiver = parsed.func.value

            receiver_source = ast.unparse(receiver)

            receiver_root = _leftmost_name(receiver)

            if receiver_root is not None and receiver_root in parameters:
                status = "PARAMETER_METHOD_BOUNDARY"

            else:
                status = "METHOD_CONTEXT_BOUNDARY"

            resolution = {
                "resolution_status": status,
                "authoritative_binding": {
                    "receiver": receiver_source,
                    "receiver_root": receiver_root,
                    "method": parsed.func.attr,
                    "call_shape": _call_shape(parsed),
                },
                "binding_events": [],
                "trace": None,
            }

        else:
            resolution = {
                "resolution_status": "UNSUPPORTED_CALL_FORM",
                "authoritative_binding": None,
                "binding_events": [],
                "trace": None,
            }

    # -------------------------------------------------
    # GLOBAL NAME
    # -------------------------------------------------

    elif binding_kind == "GLOBAL_NAME":
        if primitive in parameters:
            resolution = {
                "resolution_status": "FUNCTION_PARAMETER_BOUNDARY",
                "authoritative_binding": {
                    "parameter": primitive,
                },
                "binding_events": [],
                "trace": None,
            }

        else:
            resolution = _resolve_module_symbol(
                tree=source_tree,
                source_root=source_root,
                module_name=module_name,
                is_package=is_package,
                symbol=primitive,
            )

    # -------------------------------------------------
    # ATTRIBUTE VALUE
    # -------------------------------------------------

    elif binding_kind == "ATTRIBUTE":
        receiver_root = _leftmost_name(parsed) if parsed is not None else None

        if receiver_root is not None and receiver_root in parameters:
            status = "PARAMETER_ATTRIBUTE_BOUNDARY"

        else:
            status = "ATTRIBUTE_CONTEXT_BOUNDARY"

        resolution = {
            "resolution_status": status,
            "authoritative_binding": {
                "receiver_root": receiver_root,
                "attribute": primitive,
                "expression": expression,
            },
            "binding_events": [],
            "trace": None,
        }

    else:
        resolution = {
            "resolution_status": "UNSUPPORTED_BINDING_KIND",
            "authoritative_binding": None,
            "binding_events": [],
            "trace": None,
        }

    return {
        "candidate_id": str(occurrence["candidate_id"]),
        "family_class": str(occurrence["family_class"]),
        "kind": binding_kind,
        "primitive": primitive,
        "source_id": str(occurrence["source_id"]),
        "resolved_commit": str(occurrence["resolved_commit"]),
        "file": str(occurrence["file"]),
        "function": str(occurrence["function"]),
        "source_expression": expression,
        "context_inferred_type": str(occurrence["context_inferred_type"]),
        "semantic_type": "UNRESOLVED",
        "resolution_status": str(resolution["resolution_status"]),
        "authoritative_binding": resolution["authoritative_binding"],
        "binding_events": resolution["binding_events"],
        "trace": resolution["trace"],
        "certification_claim": False,
    }


def _contract_action(
    statuses: set[str],
) -> str:

    if statuses == {"FUNCTION_PARAMETER_BOUNDARY"}:
        return "PARAMETER_PROTOCOL_DRAFT"

    if statuses == {"PARAMETER_METHOD_BOUNDARY"}:
        return "PARAMETER_METHOD_PROTOCOL_DRAFT"

    if statuses and statuses <= {
        "LOCAL_DEFINITION",
        "LOCAL_ASSIGNMENT",
    }:
        return "LOCAL_SOURCE_CONTRACT_DRAFT"

    if statuses == {"EXTERNAL_DEPENDENCY_BOUNDARY"}:
        return "EXTERNAL_DEPENDENCY_LOCK_REQUIRED"

    if statuses == {"PYTHON_BUILTIN_BOUNDARY"}:
        return "BUILTIN_CONTRACT_DRAFT"

    if statuses == {"METHOD_CONTEXT_BOUNDARY"}:
        return "METHOD_CONTEXT_REVIEW"

    if statuses == {"WILDCARD_IMPORT_BOUNDARY"}:
        return "WILDCARD_EXPORT_REVIEW"

    return "RESOLUTION_REVIEW_REQUIRED"


def build_name_resolution(
    *,
    contract_skeletons_path: Path,
    occurrence_evidence_path: Path,
    semantic_registry_path: Path,
    previous_traces_path: Path,
    lock_path: Path,
    external_root: Path,
    output_dir: Path,
) -> JsonDict:

    skeletons = _load_jsonl(contract_skeletons_path)

    occurrences = _load_jsonl(occurrence_evidence_path)

    semantic_registry = _load_json(semantic_registry_path)

    previous_traces = _load_jsonl(previous_traces_path)

    registry_entries = semantic_registry["entries"]

    if len(registry_entries) != EXPECTED_REGISTRY_ENTRIES:
        raise ValueError("registry entry count changed")

    if len(occurrences) != EXPECTED_BINDING_OCCURRENCES:
        raise ValueError("binding occurrence count changed")

    verified_commits = _verify_locked_commits(
        lock_path=lock_path,
        external_root=external_root,
    )

    skeleton_map = {str(item["candidate_id"]): item for item in skeletons}

    source_cache: dict[
        tuple[
            str,
            str,
        ],
        ast.Module,
    ] = {}

    resolutions: list[JsonDict] = []

    for occurrence in occurrences:
        candidate_id = str(occurrence["candidate_id"])

        source_id = str(occurrence["source_id"])

        relative_file = str(occurrence["file"])

        if str(occurrence["resolved_commit"]) != verified_commits[source_id]:
            raise ValueError(f"commit mismatch for {source_id}")

        skeleton = skeleton_map.get(candidate_id)

        if skeleton is None:
            raise ValueError(f"missing contract skeleton for {candidate_id}")

        cache_key = (
            source_id,
            relative_file,
        )

        if cache_key not in source_cache:
            source_path = external_root / source_id / relative_file

            if not source_path.is_file():
                raise ValueError(f"source file missing: {source_path}")

            source_cache[cache_key] = ast.parse(
                source_path.read_text(encoding="utf-8"),
                filename=str(source_path),
            )

        resolutions.append(
            _resolve_occurrence(
                occurrence=occurrence,
                skeleton=skeleton,
                source_root=external_root / source_id,
                source_tree=source_cache[cache_key],
            )
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
        registry_key = (
            str(item["family_class"]),
            str(item["kind"]),
            str(item["primitive"]),
        )

        grouped[registry_key].append(item)

    contract_queue: list[JsonDict] = []

    for registry_entry in registry_entries:
        if not registry_entry["semantic_contract_required"]:
            continue

        registry_key = (
            str(registry_entry["family_class"]),
            str(registry_entry["kind"]),
            str(registry_entry["primitive"]),
        )

        related = grouped.get(
            registry_key,
            [],
        )

        status_counts = Counter(str(item["resolution_status"]) for item in related)

        statuses = set(status_counts)

        contract_queue.append(
            {
                "registry_id": str(registry_entry["registry_id"]),
                "family_class": str(registry_entry["family_class"]),
                "kind": str(registry_entry["kind"]),
                "primitive": str(registry_entry["primitive"]),
                "candidate_count": int(registry_entry["candidate_count"]),
                "occurrence_count": len(related),
                "resolution_status_counts": dict(sorted(status_counts.items())),
                "action": _contract_action(statuses),
                "semantic_type": "UNRESOLVED",
                "semantic_contract_status": "MISSING",
                "resolution_status": "UNRESOLVED",
                "certification_claim": False,
            }
        )

    if len(contract_queue) != EXPECTED_CONTRACT_CANDIDATES:
        raise ValueError("semantic contract candidate count changed")

    contract_queue.sort(
        key=lambda item: (
            str(item["action"]),
            -int(item["candidate_count"]),
            -int(item["occurrence_count"]),
            str(item["primitive"]),
        )
    )

    resolution_counts = Counter(str(item["resolution_status"]) for item in resolutions)

    action_counts = Counter(str(item["action"]) for item in contract_queue)

    previous_mixed = sum(
        1 for item in previous_traces if (str(item["terminal_status"]) == "MIXED_TRACE_BOUNDARY")
    )

    review_statuses = {
        "NO_BINDING_EVIDENCE",
        "UNPARSEABLE_CALL",
        "UNSUPPORTED_CALL_FORM",
        "UNSUPPORTED_BINDING_KIND",
    }

    current_unresolved = sum(
        1 for item in resolutions if (str(item["resolution_status"]) in review_statuses)
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "PYTHON_NAME_RESOLUTION_HARDENING",
        "cohort_sha256": EXPECTED_COHORT_SHA256,
        "registry_entries": len(registry_entries),
        "binding_occurrences": len(resolutions),
        "semantic_contract_candidates": len(contract_queue),
        "resolution_status_counts": dict(sorted(resolution_counts.items())),
        "contract_action_counts": dict(sorted(action_counts.items())),
        "previous_mixed_trace_occurrences": previous_mixed,
        "current_unresolved_occurrences": current_unresolved,
        "mixed_trace_status_eliminated": all(
            str(item["resolution_status"]) != "MIXED_TRACE_BOUNDARY" for item in resolutions
        ),
        "semantic_types_resolved": 0,
        "semantic_contracts_validated": 0,
        "all_semantic_types_unresolved": all(
            item["semantic_type"] == "UNRESOLVED" for item in resolutions
        ),
        "certification_claim": False,
        "passed": (
            len(registry_entries) == EXPECTED_REGISTRY_ENTRIES
            and len(resolutions) == EXPECTED_BINDING_OCCURRENCES
            and len(contract_queue) == EXPECTED_CONTRACT_CANDIDATES
        ),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_dir / "occurrence_resolution.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in resolutions
        ),
        encoding="utf-8",
    )

    (output_dir / "contract_queue.json").write_text(
        json.dumps(
            {
                "benchmark_version": "0.11.0",
                "phase": "HARDENED_CONTRACT_QUEUE",
                "cohort_sha256": EXPECTED_COHORT_SHA256,
                "entries": contract_queue,
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
        "# BIZPROOF V0.11 Python Name Resolution Hardening",
        "",
        (
            "This phase applies Python name-resolution precedence before "
            "interpreting source/import evidence."
        ),
        "",
        (
            "Function parameters shadow module globals, method calls retain "
            "their receiver context, and the last relevant module-level "
            "binding event is treated as authoritative."
        ),
        "",
        (f"- Binding occurrences: {len(resolutions)}"),
        (f"- Previous MIXED_TRACE occurrences: {previous_mixed}"),
        (f"- Current unresolved occurrences: {current_unresolved}"),
        "- Semantic types resolved: 0",
        "- Semantic contracts validated: 0",
        "",
        "## Scientific boundary",
        "",
        (
            "Name resolution improves provenance precision only. It does "
            "not transform source structure into a semantic contract or "
            "certification result."
        ),
        "",
    ]

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    return summary


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--contract-skeletons",
        type=Path,
        default=Path("benchmarks/v0.11/contracts/contract_skeletons.jsonl"),
    )

    parser.add_argument(
        "--occurrence-evidence",
        type=Path,
        default=Path("benchmarks/v0.11/semantic_evidence/occurrence_evidence.jsonl"),
    )

    parser.add_argument(
        "--semantic-registry",
        type=Path,
        default=Path("benchmarks/v0.11/semantic_evidence/semantic_registry.json"),
    )

    parser.add_argument(
        "--previous-traces",
        type=Path,
        default=Path("benchmarks/v0.11/symbol_trace/occurrence_traces.jsonl"),
    )

    parser.add_argument(
        "--lock",
        type=Path,
        default=Path("benchmarks/v0.6/LOCK.json"),
    )

    parser.add_argument(
        "--external-root",
        type=Path,
        default=Path("external_sources/v0.6"),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/name_resolution"),
    )

    args = parser.parse_args()

    summary = build_name_resolution(
        contract_skeletons_path=args.contract_skeletons,
        occurrence_evidence_path=args.occurrence_evidence,
        semantic_registry_path=args.semantic_registry,
        previous_traces_path=args.previous_traces,
        lock_path=args.lock,
        external_root=args.external_root,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 Python name-resolution hardening")

    print(
        "Binding occurrences:",
        summary["binding_occurrences"],
    )

    print(
        "Resolution statuses:",
        summary["resolution_status_counts"],
    )

    print(
        "Contract actions:",
        summary["contract_action_counts"],
    )

    print(
        "Previous mixed traces:",
        summary["previous_mixed_trace_occurrences"],
    )

    print(
        "Current unresolved:",
        summary["current_unresolved_occurrences"],
    )

    print("Semantic types resolved: 0")

    print("Certification claim: NO")

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
