from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypeAlias

from .generalization_semantic_evidence import (
    _load_json,
    _load_jsonl,
    _verify_locked_commits,
)

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"

EXPECTED_REGISTRY_ENTRIES = 58
EXPECTED_BINDING_OCCURRENCES = 170
EXPECTED_CONTRACT_CANDIDATES = 15


def _sha256_bytes(
    value: bytes,
) -> str:

    return hashlib.sha256(value).hexdigest()


def _module_file(
    source_root: Path,
    module_name: str,
) -> Path | None:

    parts = [part for part in module_name.split(".") if part]

    if not parts:
        return None

    relative = Path(*parts)

    candidates = [
        source_root / relative.with_suffix(".py"),
        source_root / relative / "__init__.py",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def _absolute_import_module(
    *,
    current_module: str,
    current_is_package: bool,
    imported_module: str | None,
    level: int,
) -> str:

    if level == 0:
        return imported_module or ""

    current_parts = [part for part in current_module.split(".") if part]

    if not current_is_package:
        current_parts = current_parts[:-1]

    climb = max(
        level - 1,
        0,
    )

    if climb > len(current_parts):
        return imported_module or ""

    base = current_parts[: len(current_parts) - climb]

    if imported_module:
        base.extend(imported_module.split("."))

    return ".".join(base)


def _parse_module(
    path: Path,
) -> tuple[
    ast.Module,
    str,
]:

    raw = path.read_bytes()

    tree = ast.parse(
        raw.decode("utf-8"),
        filename=str(path),
    )

    return (
        tree,
        _sha256_bytes(raw),
    )


def _symbol_matches(
    tree: ast.Module,
    symbol: str,
) -> list[JsonDict]:

    matches: list[JsonDict] = []

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
                matches.append(
                    {
                        "match_kind": "DEFINITION",
                        "definition_type": type(node).__name__,
                        "line": int(node.lineno),
                        "source": ast.unparse(node).splitlines()[0],
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
                matches.append(
                    {
                        "match_kind": "ASSIGNMENT",
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
                matches.append(
                    {
                        "match_kind": "ASSIGNMENT",
                        "line": int(node.lineno),
                        "source": ast.unparse(node),
                    }
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            for alias in node.names:
                if alias.name == "*":
                    matches.append(
                        {
                            "match_kind": "WILDCARD_IMPORT",
                            "module": node.module,
                            "level": int(node.level),
                            "line": int(node.lineno),
                            "source": ast.unparse(node),
                        }
                    )

                    continue

                local_name = alias.asname or alias.name

                if local_name == symbol:
                    matches.append(
                        {
                            "match_kind": "IMPORT_FROM",
                            "module": node.module,
                            "level": int(node.level),
                            "imported_name": alias.name,
                            "line": int(node.lineno),
                            "source": ast.unparse(node),
                        }
                    )

        elif isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]

                if local_name == symbol:
                    matches.append(
                        {
                            "match_kind": "IMPORT_MODULE",
                            "module": alias.name,
                            "line": int(node.lineno),
                            "source": ast.unparse(node),
                        }
                    )

    return matches


def _trace_symbol(
    *,
    source_root: Path,
    module_name: str,
    symbol: str,
    max_depth: int = 8,
) -> JsonDict:

    visited: set[
        tuple[
            str,
            str,
        ]
    ] = set()

    steps: list[JsonDict] = []

    def trace(
        current_module: str,
        current_symbol: str,
        depth: int,
    ) -> str:

        visit_key = (
            current_module,
            current_symbol,
        )

        if visit_key in visited:
            steps.append(
                {
                    "step_kind": "TRACE_CYCLE",
                    "module": current_module,
                    "symbol": current_symbol,
                }
            )

            return "AMBIGUOUS_OR_UNRESOLVED"

        if depth > max_depth:
            steps.append(
                {
                    "step_kind": "MAX_DEPTH",
                    "module": current_module,
                    "symbol": current_symbol,
                }
            )

            return "AMBIGUOUS_OR_UNRESOLVED"

        visited.add(visit_key)

        module_path = _module_file(
            source_root,
            current_module,
        )

        if module_path is None:
            steps.append(
                {
                    "step_kind": "EXTERNAL_DEPENDENCY_BOUNDARY",
                    "module": current_module,
                    "symbol": current_symbol,
                }
            )

            return "EXTERNAL_DEPENDENCY_BOUNDARY"

        tree, file_sha = _parse_module(module_path)

        relative_file = str(module_path.relative_to(source_root)).replace(
            "\\",
            "/",
        )

        current_is_package = module_path.name == "__init__.py"

        matches = _symbol_matches(
            tree,
            current_symbol,
        )

        direct = [
            match
            for match in matches
            if match["match_kind"]
            in {
                "DEFINITION",
                "ASSIGNMENT",
            }
        ]

        if len(direct) > 1:
            steps.append(
                {
                    "step_kind": "AMBIGUOUS_LOCAL_SYMBOL",
                    "module": current_module,
                    "symbol": current_symbol,
                    "file": relative_file,
                    "file_sha256": file_sha,
                    "matches": direct,
                }
            )

            return "AMBIGUOUS_OR_UNRESOLVED"

        if len(direct) == 1:
            match = direct[0]

            terminal = (
                "LOCAL_DEFINITION" if match["match_kind"] == "DEFINITION" else "LOCAL_ASSIGNMENT"
            )

            steps.append(
                {
                    "step_kind": terminal,
                    "module": current_module,
                    "symbol": current_symbol,
                    "file": relative_file,
                    "file_sha256": file_sha,
                    "line": match["line"],
                    "source": match["source"],
                    "definition_type": match.get("definition_type"),
                }
            )

            return terminal

        explicit_imports = [match for match in matches if match["match_kind"] == "IMPORT_FROM"]

        if len(explicit_imports) > 1:
            steps.append(
                {
                    "step_kind": "AMBIGUOUS_IMPORT",
                    "module": current_module,
                    "symbol": current_symbol,
                    "file": relative_file,
                    "file_sha256": file_sha,
                    "matches": explicit_imports,
                }
            )

            return "AMBIGUOUS_OR_UNRESOLVED"

        if len(explicit_imports) == 1:
            match = explicit_imports[0]

            target_module = _absolute_import_module(
                current_module=current_module,
                current_is_package=current_is_package,
                imported_module=match.get("module"),
                level=int(match["level"]),
            )

            target_symbol = str(match["imported_name"])

            steps.append(
                {
                    "step_kind": "IMPORT_EDGE",
                    "module": current_module,
                    "symbol": current_symbol,
                    "file": relative_file,
                    "file_sha256": file_sha,
                    "line": match["line"],
                    "source": match["source"],
                    "target_module": target_module,
                    "target_symbol": target_symbol,
                }
            )

            return trace(
                target_module,
                target_symbol,
                depth + 1,
            )

        module_imports = [match for match in matches if match["match_kind"] == "IMPORT_MODULE"]

        if module_imports:
            steps.append(
                {
                    "step_kind": "MODULE_IMPORT_BOUNDARY",
                    "module": current_module,
                    "symbol": current_symbol,
                    "file": relative_file,
                    "file_sha256": file_sha,
                    "matches": module_imports,
                }
            )

            return "MODULE_IMPORT_BOUNDARY"

        wildcard_imports = [match for match in matches if match["match_kind"] == "WILDCARD_IMPORT"]

        if len(wildcard_imports) > 1:
            steps.append(
                {
                    "step_kind": "AMBIGUOUS_WILDCARD_IMPORT",
                    "module": current_module,
                    "symbol": current_symbol,
                    "file": relative_file,
                    "file_sha256": file_sha,
                    "matches": wildcard_imports,
                }
            )

            return "AMBIGUOUS_OR_UNRESOLVED"

        if len(wildcard_imports) == 1:
            match = wildcard_imports[0]

            target_module = _absolute_import_module(
                current_module=current_module,
                current_is_package=current_is_package,
                imported_module=match.get("module"),
                level=int(match["level"]),
            )

            steps.append(
                {
                    "step_kind": "WILDCARD_IMPORT_EDGE",
                    "module": current_module,
                    "symbol": current_symbol,
                    "file": relative_file,
                    "file_sha256": file_sha,
                    "line": match["line"],
                    "source": match["source"],
                    "target_module": target_module,
                    "target_symbol": current_symbol,
                }
            )

            return trace(
                target_module,
                current_symbol,
                depth + 1,
            )

        steps.append(
            {
                "step_kind": "UNRESOLVED_SYMBOL",
                "module": current_module,
                "symbol": current_symbol,
                "file": relative_file,
                "file_sha256": file_sha,
            }
        )

        return "AMBIGUOUS_OR_UNRESOLVED"

    terminal_status = trace(
        module_name,
        symbol,
        0,
    )

    return {
        "initial_module": module_name,
        "initial_symbol": symbol,
        "terminal_status": terminal_status,
        "steps": steps,
    }


def _call_shape(
    expression: str,
) -> JsonDict | None:

    try:
        node = ast.parse(
            expression,
            mode="eval",
        ).body

    except SyntaxError:
        return None

    if not isinstance(
        node,
        ast.Call,
    ):
        return None

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


def _trace_occurrence(
    *,
    occurrence: JsonDict,
    source_root: Path,
) -> JsonDict:

    traces: list[JsonDict] = []

    for evidence_item in occurrence["evidence"]:
        evidence_kind = str(evidence_item["evidence_kind"])

        if evidence_kind == "EXPLICIT_IMPORT":
            traces.append(
                _trace_symbol(
                    source_root=source_root,
                    module_name=str(evidence_item["module"]),
                    symbol=str(evidence_item["imported_name"]),
                )
            )

        elif evidence_kind == "WILDCARD_IMPORT":
            traces.append(
                _trace_symbol(
                    source_root=source_root,
                    module_name=str(evidence_item["module"]),
                    symbol=str(occurrence["primitive"]),
                )
            )

        elif evidence_kind in {
            "MODULE_ASSIGNMENT",
            "MODULE_DEFINITION",
        }:
            terminal_status = (
                "LOCAL_ASSIGNMENT" if evidence_kind == "MODULE_ASSIGNMENT" else "LOCAL_DEFINITION"
            )

            traces.append(
                {
                    "initial_module": None,
                    "initial_symbol": str(occurrence["primitive"]),
                    "terminal_status": terminal_status,
                    "steps": [
                        {
                            "step_kind": terminal_status,
                            "file": occurrence["file"],
                            "source_file_sha256": occurrence["source_file_sha256"],
                            "line": evidence_item.get("line"),
                            "source": evidence_item.get("source"),
                        }
                    ],
                }
            )

        elif evidence_kind in {
            "FUNCTION_PARAMETER_CALLABLE",
            "FUNCTION_PARAMETER_VALUE",
        }:
            traces.append(
                {
                    "initial_module": None,
                    "initial_symbol": str(occurrence["primitive"]),
                    "terminal_status": "FUNCTION_PARAMETER_BOUNDARY",
                    "steps": [
                        {
                            "step_kind": "FUNCTION_PARAMETER_BOUNDARY",
                            "parameter": evidence_item["parameter"],
                            "call_shape": _call_shape(str(occurrence["source_expression"])),
                        }
                    ],
                }
            )

        elif evidence_kind == "PYTHON_BUILTIN":
            traces.append(
                {
                    "initial_module": "builtins",
                    "initial_symbol": str(occurrence["primitive"]),
                    "terminal_status": "PYTHON_BUILTIN_BOUNDARY",
                    "steps": [
                        {
                            "step_kind": "PYTHON_BUILTIN_BOUNDARY",
                            "primitive": occurrence["primitive"],
                        }
                    ],
                }
            )

        elif evidence_kind == "MODULE_IMPORT":
            traces.append(
                {
                    "initial_module": str(evidence_item["module"]),
                    "initial_symbol": str(occurrence["primitive"]),
                    "terminal_status": "MODULE_IMPORT_BOUNDARY",
                    "steps": [
                        {
                            "step_kind": "MODULE_IMPORT_BOUNDARY",
                            "module": evidence_item["module"],
                            "source": evidence_item.get("source"),
                        }
                    ],
                }
            )

        elif evidence_kind == "PARAMETER_ATTRIBUTE_ACCESS":
            traces.append(
                {
                    "initial_module": None,
                    "initial_symbol": str(occurrence["primitive"]),
                    "terminal_status": "ATTRIBUTE_PARAMETER_BOUNDARY",
                    "steps": [
                        {
                            "step_kind": "ATTRIBUTE_PARAMETER_BOUNDARY",
                            "parameter": evidence_item["parameter"],
                            "attribute": evidence_item["attribute"],
                        }
                    ],
                }
            )

        elif evidence_kind == "ATTRIBUTE_ROOT_CONTEXT":
            traces.append(
                {
                    "initial_module": None,
                    "initial_symbol": str(occurrence["primitive"]),
                    "terminal_status": "ATTRIBUTE_CONTEXT_BOUNDARY",
                    "steps": [
                        {
                            "step_kind": "ATTRIBUTE_CONTEXT_BOUNDARY",
                            "root": evidence_item["root"],
                            "attribute": evidence_item["attribute"],
                        }
                    ],
                }
            )

    if not traces:
        terminal_status = "NO_TRACE_EVIDENCE"

    else:
        terminal_statuses = {str(trace_item["terminal_status"]) for trace_item in traces}

        if len(terminal_statuses) == 1:
            terminal_status = next(iter(terminal_statuses))

        else:
            terminal_status = "MIXED_TRACE_BOUNDARY"

    return {
        "candidate_id": occurrence["candidate_id"],
        "family_class": occurrence["family_class"],
        "kind": occurrence["kind"],
        "primitive": occurrence["primitive"],
        "source_id": occurrence["source_id"],
        "resolved_commit": occurrence["resolved_commit"],
        "file": occurrence["file"],
        "function": occurrence["function"],
        "source_expression": occurrence["source_expression"],
        "context_inferred_type": occurrence["context_inferred_type"],
        "semantic_type": "UNRESOLVED",
        "terminal_status": terminal_status,
        "traces": traces,
        "certification_claim": False,
    }


def build_symbol_traces(
    *,
    semantic_summary_path: Path,
    occurrence_evidence_path: Path,
    semantic_registry_path: Path,
    lock_path: Path,
    external_root: Path,
    output_dir: Path,
) -> JsonDict:

    semantic_summary = _load_json(semantic_summary_path)

    if str(semantic_summary["cohort_sha256"]) != EXPECTED_COHORT_SHA256:
        raise ValueError("semantic evidence cohort digest changed")

    occurrences = _load_jsonl(occurrence_evidence_path)

    semantic_registry = _load_json(semantic_registry_path)

    registry_entries = semantic_registry["entries"]

    if len(registry_entries) != EXPECTED_REGISTRY_ENTRIES:
        raise ValueError("registry entry count changed")

    if len(occurrences) != EXPECTED_BINDING_OCCURRENCES:
        raise ValueError("binding occurrence count changed")

    verified_commits = _verify_locked_commits(
        lock_path=lock_path,
        external_root=external_root,
    )

    occurrence_traces: list[JsonDict] = []

    for occurrence in occurrences:
        source_id = str(occurrence["source_id"])

        if str(occurrence["resolved_commit"]) != verified_commits[source_id]:
            raise ValueError(f"commit mismatch for {source_id}")

        occurrence_traces.append(
            _trace_occurrence(
                occurrence=occurrence,
                source_root=external_root / source_id,
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

    for trace_item in occurrence_traces:
        registry_key = (
            str(trace_item["family_class"]),
            str(trace_item["kind"]),
            str(trace_item["primitive"]),
        )

        grouped[registry_key].append(trace_item)

    contract_candidates: list[JsonDict] = []

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

        terminal_counts = Counter(str(item["terminal_status"]) for item in related)

        unresolved_statuses = {
            "AMBIGUOUS_OR_UNRESOLVED",
            "MIXED_TRACE_BOUNDARY",
            "NO_TRACE_EVIDENCE",
        }

        trace_complete = not any(
            status_name in unresolved_statuses for status_name in terminal_counts
        )

        if trace_complete:
            trace_readiness = "TRACE_COMPLETE"

        else:
            trace_readiness = "TRACE_REVIEW"

        terminal_names = set(terminal_counts)

        if terminal_names == {"FUNCTION_PARAMETER_BOUNDARY"}:
            next_action = "SPECIFY_PARAMETER_CALL_PROTOCOL"

        elif "EXTERNAL_DEPENDENCY_BOUNDARY" in terminal_names:
            next_action = "LOCK_EXTERNAL_DEPENDENCY_OR_AUTHOR_CONTRACT"

        elif terminal_names <= {
            "LOCAL_DEFINITION",
            "LOCAL_ASSIGNMENT",
        }:
            next_action = "AUTHOR_CONTRACT_FROM_LOCAL_SOURCE"

        elif terminal_names == {"PYTHON_BUILTIN_BOUNDARY"}:
            next_action = "AUTHOR_BUILTIN_CONTRACT"

        else:
            next_action = "MANUAL_TRACE_REVIEW"

        contract_candidates.append(
            {
                "registry_id": registry_entry["registry_id"],
                "family_class": registry_entry["family_class"],
                "kind": registry_entry["kind"],
                "primitive": registry_entry["primitive"],
                "candidate_count": registry_entry["candidate_count"],
                "occurrence_count": len(related),
                "contextual_types": registry_entry["contextual_types"],
                "terminal_status_counts": dict(sorted(terminal_counts.items())),
                "trace_readiness": trace_readiness,
                "semantic_type": "UNRESOLVED",
                "semantic_contract_status": "MISSING",
                "resolution_status": "UNRESOLVED",
                "next_action": next_action,
                "certification_claim": False,
            }
        )

    if len(contract_candidates) != EXPECTED_CONTRACT_CANDIDATES:
        raise ValueError("semantic contract candidate count changed")

    contract_candidates.sort(
        key=lambda item: (
            0 if item["trace_readiness"] == "TRACE_COMPLETE" else 1,
            -int(item["candidate_count"]),
            -int(item["occurrence_count"]),
            str(item["primitive"]),
        )
    )

    terminal_counts = Counter(str(item["terminal_status"]) for item in occurrence_traces)

    step_counts = Counter(
        str(step["step_kind"])
        for trace_item in occurrence_traces
        for trace in trace_item["traces"]
        for step in trace["steps"]
    )

    readiness_counts = Counter(str(item["trace_readiness"]) for item in contract_candidates)

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "SYMBOL_DEFINITION_TRACE",
        "cohort_sha256": EXPECTED_COHORT_SHA256,
        "registry_entries": len(registry_entries),
        "binding_occurrences": len(occurrence_traces),
        "semantic_contract_candidates": len(contract_candidates),
        "terminal_status_counts": dict(sorted(terminal_counts.items())),
        "trace_step_counts": dict(sorted(step_counts.items())),
        "contract_trace_readiness": dict(sorted(readiness_counts.items())),
        "semantic_types_resolved": 0,
        "all_semantic_types_unresolved": True,
        "certification_claim": False,
        "passed": (
            len(registry_entries) == EXPECTED_REGISTRY_ENTRIES
            and len(occurrence_traces) == EXPECTED_BINDING_OCCURRENCES
            and len(contract_candidates) == EXPECTED_CONTRACT_CANDIDATES
        ),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_dir / "occurrence_traces.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in occurrence_traces
        ),
        encoding="utf-8",
    )

    (output_dir / "contract_candidates.json").write_text(
        json.dumps(
            {
                "benchmark_version": "0.11.0",
                "phase": "SOURCE_BACKED_CONTRACT_CANDIDATES",
                "cohort_sha256": EXPECTED_COHORT_SHA256,
                "entries": contract_candidates,
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
        "# BIZPROOF V0.11 Symbol Definition Trace",
        "",
        (
            "Phase H recursively follows symbol definitions and imports "
            "inside the locked external-source snapshots."
        ),
        "",
        (
            "External dependencies, callable parameters, builtins and "
            "attribute boundaries are recorded explicitly."
        ),
        "",
        (f"- Registry entries: {len(registry_entries)}"),
        (f"- Binding occurrences: {len(occurrence_traces)}"),
        (f"- Semantic-contract candidates: {len(contract_candidates)}"),
        "- Semantic types resolved: 0",
        "",
        "## Trace readiness",
        "",
    ]

    for (
        readiness_name,
        value,
    ) in sorted(readiness_counts.items()):
        report.append(f"- `{readiness_name}`: {value}")

    report.extend(
        [
            "",
            "## Scientific boundary",
            "",
            (
                "A successfully traced symbol establishes provenance, "
                "not semantic equivalence or certification."
            ),
            "",
            ("All semantic types and semantic contracts remain explicitly unresolved."),
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
        "--semantic-summary",
        type=Path,
        default=Path("benchmarks/v0.11/semantic_evidence/summary.json"),
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
        default=Path("benchmarks/v0.11/symbol_trace"),
    )

    args = parser.parse_args()

    summary = build_symbol_traces(
        semantic_summary_path=args.semantic_summary,
        occurrence_evidence_path=args.occurrence_evidence,
        semantic_registry_path=args.semantic_registry,
        lock_path=args.lock,
        external_root=args.external_root,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 symbol definition trace")

    print(
        "Registry entries:",
        summary["registry_entries"],
    )

    print(
        "Binding occurrences:",
        summary["binding_occurrences"],
    )

    print(
        "Contract candidates:",
        summary["semantic_contract_candidates"],
    )

    print(
        "Terminal statuses:",
        summary["terminal_status_counts"],
    )

    print(
        "Trace readiness:",
        summary["contract_trace_readiness"],
    )

    print("Semantic types resolved: 0")

    print("Certification claim: NO")

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
