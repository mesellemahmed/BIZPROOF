from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any, TypeAlias

JsonDict: TypeAlias = dict[str, Any]

TARGET_SYMBOLS = {
    "_reviewer_report",
    "_sha256_file",
}

DISCOVERY_KEYWORDS = (
    "certif",
    "equival",
    "preserv",
    "symbolic",
    "z3",
    "counterexample",
    "replay",
    "evidence",
)


def _sha256(
    path: Path,
) -> str:

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _call_name(
    node: ast.Call,
) -> str | None:

    function = node.func

    if isinstance(
        function,
        ast.Name,
    ):
        return function.id

    if isinstance(
        function,
        ast.Attribute,
    ):
        return function.attr

    return None


def _source_block(
    lines: list[str],
    node: ast.AST,
) -> str:

    start = getattr(
        node,
        "lineno",
        None,
    )

    end = getattr(
        node,
        "end_lineno",
        None,
    )

    if not isinstance(
        start,
        int,
    ) or not isinstance(
        end,
        int,
    ):
        return ""

    return "\n".join(lines[start - 1 : end])


def _function_parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:

    result = {
        argument.arg
        for argument in (
            list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
        )
    }

    if node.args.vararg:
        result.add(node.args.vararg.arg)

    if node.args.kwarg:
        result.add(node.args.kwarg.arg)

    return result


def _direct_parameter_subscripts(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[JsonDict]:

    parameters = _function_parameters(node)

    results: list[JsonDict] = []

    for child in ast.walk(node):
        if not isinstance(
            child,
            ast.Subscript,
        ):
            continue

        value = child.value

        if not isinstance(
            value,
            ast.Name,
        ):
            continue

        if value.id not in parameters:
            continue

        results.append(
            {
                "parameter": value.id,
                "line": int(child.lineno),
                "expression": ast.unparse(child),
            }
        )

    return results


def _context(
    lines: list[str],
    line_number: int,
    radius: int = 5,
) -> str:

    start = max(
        line_number - radius - 1,
        0,
    )

    end = min(
        line_number + radius,
        len(lines),
    )

    rendered = []

    for index in range(
        start,
        end,
    ):
        rendered.append(f"{index + 1:04d}: " + lines[index])

    return "\n".join(rendered)


def _scan_python_file(
    *,
    path: Path,
    repo_root: Path,
) -> JsonDict:

    text = path.read_text(encoding="utf-8")

    lines = text.splitlines()

    tree = ast.parse(
        text,
        filename=str(path),
    )

    relative = str(path.relative_to(repo_root)).replace(
        "\\",
        "/",
    )

    functions: list[JsonDict] = []

    callsites: list[JsonDict] = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            lowered = node.name.lower()

            interesting = node.name in TARGET_SYMBOLS or any(
                keyword in lowered for keyword in DISCOVERY_KEYWORDS
            )

            if interesting:
                functions.append(
                    {
                        "name": node.name,
                        "line": int(node.lineno),
                        "end_line": int(node.end_lineno or node.lineno),
                        "parameters": sorted(_function_parameters(node)),
                        "direct_parameter_subscripts": (_direct_parameter_subscripts(node)),
                        "source": _source_block(
                            lines,
                            node,
                        ),
                    }
                )

        elif isinstance(
            node,
            ast.Call,
        ):
            name = _call_name(node)

            if name not in TARGET_SYMBOLS:
                continue

            callsites.append(
                {
                    "symbol": name,
                    "line": int(node.lineno),
                    "expression": ast.unparse(node),
                    "context": _context(
                        lines,
                        int(node.lineno),
                    ),
                }
            )

    return {
        "file": relative,
        "sha256": _sha256(path),
        "functions": sorted(
            functions,
            key=lambda item: (
                int(item["line"]),
                str(item["name"]),
            ),
        ),
        "callsites": sorted(
            callsites,
            key=lambda item: int(item["line"]),
        ),
    }


def build_audit(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    source_root = repo_root / "src" / "bizproof"

    tests_root = repo_root / "tests"

    if not source_root.is_dir():
        raise ValueError("src/bizproof missing")

    source_records: list[JsonDict] = []

    for path in sorted(source_root.rglob("*.py")):
        record = _scan_python_file(
            path=path,
            repo_root=repo_root,
        )

        if record["functions"] or record["callsites"]:
            source_records.append(record)

    definitions: dict[
        str,
        list[JsonDict],
    ] = {symbol: [] for symbol in TARGET_SYMBOLS}

    callsites: dict[
        str,
        list[JsonDict],
    ] = {symbol: [] for symbol in TARGET_SYMBOLS}

    discovered_functions: list[JsonDict] = []

    relevant_source_files: set[str] = set()

    for record in source_records:
        file_name = str(record["file"])

        for function in record["functions"]:
            enriched = {
                "file": file_name,
                **function,
            }

            discovered_functions.append(enriched)

            relevant_source_files.add(file_name)

            if function["name"] in TARGET_SYMBOLS:
                definitions[str(function["name"])].append(enriched)

        for callsite in record["callsites"]:
            enriched = {
                "file": file_name,
                **callsite,
            }

            callsites[str(callsite["symbol"])].append(enriched)

            relevant_source_files.add(file_name)

    relevant_tests: list[JsonDict] = []

    search_tokens = {
        "_reviewer_report",
        "_sha256_file",
        "certif",
        "equival",
        "preserv",
        "symbolic",
        "counterexample",
        "replay",
    }

    if tests_root.is_dir():
        for path in sorted(tests_root.rglob("*.py")):
            text = path.read_text(encoding="utf-8")

            lowered = text.lower()

            matched = sorted(token for token in search_tokens if (token.lower() in lowered))

            if not matched:
                continue

            relative = str(path.relative_to(repo_root)).replace(
                "\\",
                "/",
            )

            relevant_tests.append(
                {
                    "file": relative,
                    "sha256": _sha256(path),
                    "matched_tokens": matched,
                }
            )

    reviewer_subscripts = []

    for definition in definitions["_reviewer_report"]:
        for item in definition["direct_parameter_subscripts"]:
            reviewer_subscripts.append(
                {
                    "file": definition["file"],
                    **item,
                }
            )

    summary: JsonDict = {
        "phase": "CERTIFICATION_ENGINE_SAFETY_AUDIT",
        "target_definition_counts": {
            symbol: len(definitions[symbol]) for symbol in sorted(TARGET_SYMBOLS)
        },
        "target_callsite_counts": {
            symbol: len(callsites[symbol]) for symbol in sorted(TARGET_SYMBOLS)
        },
        "discovered_function_count": len(discovered_functions),
        "relevant_source_file_count": len(relevant_source_files),
        "relevant_test_file_count": len(relevant_tests),
        "reviewer_report_direct_parameter_subscripts": len(reviewer_subscripts),
        "reviewer_report_negative_path_review_required": bool(reviewer_subscripts),
        "sha256_missing_path_review_required": bool(callsites["_sha256_file"]),
        "semantic_contracts_validated": 0,
        "certification_claim": False,
        "passed": (
            len(definitions["_reviewer_report"]) >= 1 and len(definitions["_sha256_file"]) >= 1
        ),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
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

    (output_dir / "target_definitions.json").write_text(
        json.dumps(
            definitions,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "target_callsites.json").write_text(
        json.dumps(
            callsites,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "discovered_functions.json").write_text(
        json.dumps(
            discovered_functions,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "relevant_tests.json").write_text(
        json.dumps(
            relevant_tests,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "review_findings.json").write_text(
        json.dumps(
            {
                "reviewer_report_direct_parameter_subscripts": reviewer_subscripts,
                "sha256_callsites": callsites["_sha256_file"],
                "certification_claim": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_files = sorted(relevant_source_files | {str(item["file"]) for item in relevant_tests})

    (output_dir / "pack_manifest.json").write_text(
        json.dumps(
            {
                "files": manifest_files,
                "additional_files": [
                    "run.sh",
                    "pyproject.toml",
                    "VALIDATION.json",
                ],
                "benchmark_directories": [
                    "benchmarks/v0.9",
                    "benchmarks/v0.10",
                ],
                "certification_claim": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    report = [
        "# BIZPROOF V0.11 Certification Engine Safety Audit",
        "",
        (
            "This phase inventories the exact proof/certification "
            "implementation before V0.11 semantic contracts reuse it."
        ),
        "",
        (
            f"- `_reviewer_report` definitions: "
            f"{summary['target_definition_counts']['_reviewer_report']}"
        ),
        (f"- `_sha256_file` definitions: {summary['target_definition_counts']['_sha256_file']}"),
        (f"- `_sha256_file` callsites: {summary['target_callsite_counts']['_sha256_file']}"),
        (f"- discovered proof-related functions: {summary['discovered_function_count']}"),
        (f"- relevant tests: {summary['relevant_test_file_count']}"),
        "",
        "## `_reviewer_report`",
        "",
    ]

    for definition in definitions["_reviewer_report"]:
        report.extend(
            [
                (f"File: `{definition['file']}` line {definition['line']}"),
                "",
                "```python",
                str(definition["source"]),
                "```",
                "",
            ]
        )

    report.extend(
        [
            "## `_sha256_file`",
            "",
        ]
    )

    for definition in definitions["_sha256_file"]:
        report.extend(
            [
                (f"File: `{definition['file']}` line {definition['line']}"),
                "",
                "```python",
                str(definition["source"]),
                "```",
                "",
            ]
        )

    report.extend(
        [
            "## `_sha256_file` callsites",
            "",
        ]
    )

    for callsite in callsites["_sha256_file"]:
        report.extend(
            [
                (f"File: `{callsite['file']}` line {callsite['line']}"),
                "",
                "```text",
                str(callsite["context"]),
                "```",
                "",
            ]
        )

    report.extend(
        [
            "## Scientific boundary",
            "",
            (
                "This is an implementation audit only. "
                "No V0.11 semantic contract or certification "
                "verdict is created."
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
        "--repo-root",
        type=Path,
        default=Path("."),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/certification_gate"),
    )

    args = parser.parse_args()

    summary = build_audit(
        repo_root=args.repo_root.resolve(),
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 certification-engine safety audit")

    print(
        "Target definitions:",
        summary["target_definition_counts"],
    )

    print(
        "Target callsites:",
        summary["target_callsite_counts"],
    )

    print(
        "Proof-related functions:",
        summary["discovered_function_count"],
    )

    print(
        "Relevant tests:",
        summary["relevant_test_file_count"],
    )

    print(
        "Reviewer direct parameter subscripts:",
        summary["reviewer_report_direct_parameter_subscripts"],
    )

    print("Certification claim: NO")

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
