from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

BUSINESS_KEYWORDS = (
    "account",
    "amount",
    "availability",
    "benefit",
    "basket",
    "charge",
    "checkout",
    "condition",
    "discount",
    "eligib",
    "fee",
    "fulfil",
    "fulfill",
    "offer",
    "order",
    "payment",
    "price",
    "pricing",
    "quota",
    "refund",
    "shipping",
    "stock",
    "tax",
    "total",
    "voucher",
)

HARD_UNSUPPORTED_NODES = (
    ast.AsyncFunctionDef,
    ast.Await,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Yield,
    ast.YieldFrom,
    ast.Raise,
    ast.Delete,
    ast.Global,
    ast.Nonlocal,
)

ADAPTATION_NODES = (
    ast.Attribute,
    ast.Subscript,
    ast.Call,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Lambda,
)

DIRECT_ALLOWED_EXPR_NODES = (
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.IfExp,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.USub,
    ast.UAdd,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _iter_python_files(
    repo: Path,
    roots: Iterable[str],
    *,
    max_files: int,
) -> list[Path]:
    result: list[Path] = []

    for configured_root in roots:
        candidate = repo / configured_root
        if not candidate.exists():
            continue

        if candidate.is_file() and candidate.suffix == ".py":
            result.append(candidate)
            continue

        if candidate.is_dir():
            for path in sorted(candidate.rglob("*.py")):
                if any(
                    part
                    in {
                        ".git",
                        "__pycache__",
                        "migrations",
                        "vendor",
                        "vendored",
                    }
                    for part in path.parts
                ):
                    continue
                result.append(path)
                if len(result) >= max_files:
                    return result

    return result[:max_files]


EVIDENCE_EXTENSIONS = {
    ".py",
    ".md",
    ".rst",
    ".txt",
    ".yaml",
    ".yml",
}

GENERIC_FUNCTION_NAMES = {
    "formula",
    "calculate",
    "compute",
    "get",
    "set",
    "clean",
    "save",
    "validate",
    "apply",
}


def _looks_like_test_file(path: Path) -> bool:
    lowered_parts = {part.lower() for part in path.parts}
    name = path.name.lower()

    if lowered_parts.intersection(
        {"test", "tests", "testing"},
    ):
        return True

    if name.startswith("test_") and path.suffix.lower() == ".py":
        return True

    if name.endswith("_test.py"):
        return True

    return False


def _iter_evidence_files(
    repo: Path,
    roots: Iterable[str],
    *,
    evidence_kind: str,
) -> list[Path]:
    result: list[Path] = []

    for configured_root in roots:
        candidate = repo / configured_root
        if not candidate.exists():
            continue

        if candidate.is_file():
            candidates = [candidate]
        else:
            candidates = sorted(candidate.rglob("*"))

        for path in candidates:
            if not path.is_file():
                continue
            if path.suffix.lower() not in EVIDENCE_EXTENSIONS:
                continue
            if any(part in {".git", "__pycache__", "migrations"} for part in path.parts):
                continue

            if evidence_kind == "test" and not _looks_like_test_file(path):
                continue

            result.append(path)

            if len(result) >= 5000:
                return result

    return result


def _keyword_matches(text: str) -> list[str]:
    lowered = text.lower()
    return sorted({keyword for keyword in BUSINESS_KEYWORDS if keyword in lowered})


def _business_signals(
    *,
    function_name: str,
    class_name: str | None,
    relative_path: str,
    docstring: str,
) -> JsonDict:
    name_keywords = _keyword_matches(function_name)
    class_keywords = _keyword_matches(class_name or "")
    doc_keywords = _keyword_matches(docstring)
    path_keywords = _keyword_matches(relative_path)

    weighted_score = (
        3 * len(name_keywords)
        + 3 * len(class_keywords)
        + 2 * len(doc_keywords)
        + len(path_keywords)
    )

    if name_keywords or class_keywords or doc_keywords:
        confidence = "STRONG"
    elif path_keywords:
        confidence = "CONTEXTUAL"
    else:
        confidence = "NONE"

    return {
        "weighted_score": weighted_score,
        "confidence": confidence,
        "name_keywords": name_keywords,
        "class_keywords": class_keywords,
        "doc_keywords": doc_keywords,
        "path_keywords": path_keywords,
        "all_keywords": sorted(set(name_keywords + class_keywords + doc_keywords + path_keywords)),
    }


def _exact_text_reference(
    identifier: str,
    text: str,
) -> bool:
    if not identifier:
        return False

    return (
        re.search(
            rf"(?<![A-Za-z0-9_])"
            rf"{re.escape(identifier.lower())}"
            rf"(?![A-Za-z0-9_])",
            text,
        )
        is not None
    )


def _python_symbol_references(text: str) -> set[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()

    symbols: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            symbols.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            symbols.add(node.attr.lower())
        elif isinstance(node, ast.alias):
            if node.asname:
                symbols.add(node.asname.lower())
            symbols.add(node.name.rsplit(".", 1)[-1].lower())

    return symbols


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    return parents


def _enclosing_class_name(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> str | None:
    current = parents.get(node)

    while current is not None:
        if isinstance(current, ast.ClassDef):
            return current.name
        current = parents.get(current)

    return None


def _adaptation_complexity(
    *,
    classification: str,
    reasons: list[str],
    line_start: int,
    line_end: int,
) -> str | None:
    if classification != "ADAPTATION_REQUIRED":
        return None

    span = max(1, line_end - line_start + 1)
    reason_count = len(set(reasons))

    if reason_count <= 2 and span <= 12:
        return "LOW"
    if reason_count <= 4 and span <= 30:
        return "MEDIUM"
    return "HIGH"


def _statement_shape(function: ast.FunctionDef) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    direct_shape = True

    if function.decorator_list:
        direct_shape = False
        reasons.append("decorated_function")

    for node in ast.walk(function):
        if isinstance(node, HARD_UNSUPPORTED_NODES):
            direct_shape = False
            reasons.append(type(node).__name__)

    if any(isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)) for node in function.body):
        direct_shape = False
        reasons.append("local_assignment")

    return direct_shape, sorted(set(reasons))


def _classify(function: ast.FunctionDef) -> tuple[str, list[str]]:
    direct_shape, reasons = _statement_shape(function)

    hard = [
        type(node).__name__
        for node in ast.walk(function)
        if isinstance(node, HARD_UNSUPPORTED_NODES)
    ]
    if hard:
        return "UNSUPPORTED", sorted(set(reasons + hard))

    adaptation: list[str] = []
    for node in ast.walk(function):
        if isinstance(node, ADAPTATION_NODES):
            adaptation.append(type(node).__name__)

    argument_names = {
        arg.arg
        for arg in (
            list(function.args.posonlyargs)
            + list(function.args.args)
            + list(function.args.kwonlyargs)
        )
    }

    if "self" in argument_names or "cls" in argument_names:
        adaptation.append("bound_method")

    if function.args.vararg is not None:
        adaptation.append("varargs")
    if function.args.kwarg is not None:
        adaptation.append("kwargs")

    if adaptation or not direct_shape:
        return "ADAPTATION_REQUIRED", sorted(set(reasons + adaptation))

    for node in ast.walk(function):
        if isinstance(node, ast.expr) and not isinstance(
            node,
            DIRECT_ALLOWED_EXPR_NODES,
        ):
            if isinstance(node, (ast.Return,)):
                continue

    if len(function.body) > 4:
        return "ADAPTATION_REQUIRED", ["complex_statement_shape"]

    return "DIRECT_CANDIDATE", []


def _function_record(
    *,
    source_id: str,
    repo: Path,
    path: Path,
    node: ast.FunctionDef,
    class_name: str | None,
    source_text: str,
    evidence_index: list[tuple[Path, str, str, set[str]]],
) -> JsonDict | None:
    relative = path.relative_to(repo).as_posix()
    docstring = ast.get_docstring(node) or ""

    signals = _business_signals(
        function_name=node.name,
        class_name=class_name,
        relative_path=relative,
        docstring=docstring,
    )
    if signals["confidence"] == "NONE":
        return None

    classification, reasons = _classify(node)

    line_end = getattr(node, "end_lineno", node.lineno)
    segment = ast.get_source_segment(source_text, node) or ""

    test_evidence: list[str] = []
    doc_evidence: list[str] = []
    evidence_modes: Counter[str] = Counter()

    function_name = node.name.lower()
    normalized_class = class_name.lower() if class_name is not None else None

    allow_function_reference = function_name not in GENERIC_FUNCTION_NAMES

    for (
        evidence,
        text,
        evidence_kind,
        python_symbols,
    ) in evidence_index:
        relative_evidence = evidence.relative_to(repo).as_posix()
        modes: set[str] = set()

        if evidence.suffix.lower() == ".py":
            if allow_function_reference and function_name in python_symbols:
                modes.add("EXACT_FUNCTION_SYMBOL")

            if normalized_class is not None and normalized_class in python_symbols:
                modes.add("EXACT_CLASS_SYMBOL")

        else:
            if allow_function_reference and _exact_text_reference(
                function_name,
                text,
            ):
                modes.add("EXACT_FUNCTION_TEXT")

            if normalized_class is not None and _exact_text_reference(
                normalized_class,
                text,
            ):
                modes.add("EXACT_CLASS_TEXT")

        if evidence_kind == "doc":
            if allow_function_reference and _exact_text_reference(
                function_name,
                text,
            ):
                modes.add("EXACT_FUNCTION_TEXT")

            if normalized_class is not None and _exact_text_reference(
                normalized_class,
                text,
            ):
                modes.add("EXACT_CLASS_TEXT")

        if not modes:
            continue

        for mode in modes:
            evidence_modes[f"{evidence_kind}:{mode}"] += 1

        if evidence_kind == "test":
            if len(test_evidence) < 8:
                test_evidence.append(relative_evidence)
        else:
            if len(doc_evidence) < 8:
                doc_evidence.append(relative_evidence)

        if len(test_evidence) >= 8 and len(doc_evidence) >= 8:
            break

    adaptation_complexity = _adaptation_complexity(
        classification=classification,
        reasons=reasons,
        line_start=node.lineno,
        line_end=line_end,
    )

    return {
        "source_id": source_id,
        "file": relative,
        "function": node.name,
        "enclosing_class": class_name,
        "line_start": node.lineno,
        "line_end": line_end,
        "business_score": signals["weighted_score"],
        "business_relevance": signals["confidence"],
        "business_keywords": signals["all_keywords"],
        "business_keyword_sources": {
            "function": signals["name_keywords"],
            "class": signals["class_keywords"],
            "docstring": signals["doc_keywords"],
            "path": signals["path_keywords"],
        },
        "classification": classification,
        "classification_reasons": reasons,
        "adaptation_complexity": adaptation_complexity,
        "parameter_count": (
            len(node.args.posonlyargs) + len(node.args.args) + len(node.args.kwonlyargs)
        ),
        "decorator_count": len(node.decorator_list),
        "docstring_present": bool(docstring.strip()),
        "supporting_test_files": sorted(set(test_evidence)),
        "supporting_doc_files": sorted(set(doc_evidence)),
        "evidence_link_modes": dict(sorted(evidence_modes.items())),
        "evidence_policy": "EXACT_SYMBOL_OR_EXACT_CLASS",
        "function_sha256": _sha256(segment.encode("utf-8")),
        "source_file_sha256": _sha256(path.read_bytes()),
    }


def _scan_source(
    source: JsonDict,
    lock: JsonDict,
    *,
    external_root: Path,
) -> tuple[JsonDict, list[JsonDict]]:
    source_id = str(source["id"])
    repo = external_root / source_id
    if not repo.exists():
        raise FileNotFoundError(f"external source missing: {repo}. Run acquisition first.")

    max_files = int(source.get("max_code_files", 500))
    code_files = _iter_python_files(
        repo,
        [str(item) for item in source.get("code_roots", [])],
        max_files=max_files,
    )
    evidence_index: list[tuple[Path, str, str, set[str]]] = []

    evidence_groups = (
        (
            "test",
            [str(item) for item in source.get("test_roots", [])],
        ),
        (
            "doc",
            [str(item) for item in source.get("doc_roots", [])],
        ),
    )

    for evidence_kind, evidence_roots in evidence_groups:
        evidence_files = _iter_evidence_files(
            repo,
            evidence_roots,
            evidence_kind=evidence_kind,
        )

        for evidence in evidence_files:
            try:
                original_text = evidence.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            except OSError:
                continue

            lowered = original_text.lower()
            python_symbols = (
                _python_symbol_references(original_text)
                if evidence.suffix.lower() == ".py"
                else set()
            )

            evidence_index.append(
                (
                    evidence,
                    lowered,
                    evidence_kind,
                    python_symbols,
                )
            )

    candidates: list[JsonDict] = []
    syntax_errors = 0
    functions_examined = 0

    for path in code_files:
        try:
            source_text = path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
            tree = ast.parse(
                source_text,
                filename=str(path),
            )
        except (OSError, SyntaxError):
            syntax_errors += 1
            continue

        parents = _parent_map(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            functions_examined += 1

            record = _function_record(
                source_id=source_id,
                repo=repo,
                path=path,
                node=node,
                class_name=_enclosing_class_name(
                    node,
                    parents,
                ),
                source_text=source_text,
                evidence_index=evidence_index,
            )
            if record is not None:
                candidates.append(record)

    classification_counts = Counter(str(record["classification"]) for record in candidates)
    relevance_counts = Counter(str(record["business_relevance"]) for record in candidates)
    adaptation_complexity_counts = Counter(
        str(record["adaptation_complexity"])
        for record in candidates
        if record["adaptation_complexity"] is not None
    )
    with_tests = sum(1 for record in candidates if record["supporting_test_files"])
    with_docs = sum(1 for record in candidates if record["supporting_doc_files"])
    with_any_evidence = sum(
        1
        for record in candidates
        if (record["supporting_test_files"] or record["supporting_doc_files"])
    )

    summary = {
        "source_id": source_id,
        "name": source["name"],
        "domain": source["domain"],
        "license": source["license"],
        "resolved_commit": lock["resolved_commit"],
        "code_files_examined": len(code_files),
        "functions_examined": functions_examined,
        "business_candidates": len(candidates),
        "classification_counts": dict(sorted(classification_counts.items())),
        "relevance_counts": dict(sorted(relevance_counts.items())),
        "adaptation_complexity_counts": dict(sorted(adaptation_complexity_counts.items())),
        "candidates_with_test_evidence": with_tests,
        "candidates_with_doc_evidence": with_docs,
        "candidates_with_any_evidence": with_any_evidence,
        "syntax_errors": syntax_errors,
    }
    return summary, candidates


def run_external_audit(
    *,
    sources_path: Path,
    lock_path: Path,
    external_root: Path,
    output_dir: Path,
) -> JsonDict:
    sources_payload = _read_json(sources_path)
    lock_payload = _read_json(lock_path)

    configured = sources_payload.get("sources")
    locked = lock_payload.get("sources")

    if not isinstance(configured, list):
        raise ValueError("sources.json requires a sources list")
    if not isinstance(locked, list):
        raise ValueError("LOCK.json requires a sources list")

    lock_by_id: dict[str, JsonDict] = {}
    for raw in locked:
        if not isinstance(raw, dict):
            continue
        lock_by_id[str(raw["id"])] = raw

    source_summaries: list[JsonDict] = []
    all_candidates: list[JsonDict] = []

    for raw_source in configured:
        if not isinstance(raw_source, dict):
            raise ValueError("invalid configured source")
        source_id = str(raw_source["id"])
        if source_id not in lock_by_id:
            raise ValueError(f"source not locked: {source_id}")

        source_summary, candidates = _scan_source(
            raw_source,
            lock_by_id[source_id],
            external_root=external_root,
        )
        source_summaries.append(source_summary)
        all_candidates.extend(candidates)

    class_counts = Counter(str(item["classification"]) for item in all_candidates)
    relevance_counts = Counter(str(item["business_relevance"]) for item in all_candidates)
    adaptation_complexity_counts = Counter(
        str(item["adaptation_complexity"])
        for item in all_candidates
        if item["adaptation_complexity"] is not None
    )

    business_candidates = len(all_candidates)
    direct = class_counts.get("DIRECT_CANDIDATE", 0)
    adaptation = class_counts.get("ADAPTATION_REQUIRED", 0)
    unsupported = class_counts.get("UNSUPPORTED", 0)

    total_functions = sum(int(item["functions_examined"]) for item in source_summaries)
    total_code_files = sum(int(item["code_files_examined"]) for item in source_summaries)

    summary: JsonDict = {
        "benchmark_version": "0.6.2",
        "sources_checked": len(source_summaries),
        "code_files_examined": total_code_files,
        "functions_examined": total_functions,
        "business_candidates": business_candidates,
        "direct_candidates": direct,
        "adaptation_required": adaptation,
        "unsupported": unsupported,
        "direct_candidate_rate": (direct / business_candidates if business_candidates else 0.0),
        "adaptable_or_direct_rate": (
            (direct + adaptation) / business_candidates if business_candidates else 0.0
        ),
        "sources": source_summaries,
        "classification_counts": dict(sorted(class_counts.items())),
        "relevance_counts": dict(sorted(relevance_counts.items())),
        "adaptation_complexity_counts": dict(sorted(adaptation_complexity_counts.items())),
        "candidates_with_test_evidence": sum(
            1 for item in all_candidates if item["supporting_test_files"]
        ),
        "candidates_with_doc_evidence": sum(
            1 for item in all_candidates if item["supporting_doc_files"]
        ),
        "candidates_with_any_evidence": sum(
            1
            for item in all_candidates
            if (item["supporting_test_files"] or item["supporting_doc_files"])
        ),
        "interpretation": {
            "DIRECT_CANDIDATE": (
                "structurally close to the current BIZPROOF supported subset; "
                "still requires an independently sourced business contract"
            ),
            "ADAPTATION_REQUIRED": (
                "business-relevant external function that requires an explicit "
                "interface or scalar adaptation before formal verification"
            ),
            "UNSUPPORTED": (
                "contains control-flow or language constructs intentionally outside "
                "the current verifier semantics"
            ),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "summary.json"
    candidates_path = output_dir / "candidates.jsonl"

    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    relevance_rank = {
        "STRONG": 0,
        "CONTEXTUAL": 1,
    }
    classification_rank = {
        "DIRECT_CANDIDATE": 0,
        "ADAPTATION_REQUIRED": 1,
        "UNSUPPORTED": 2,
    }
    complexity_rank = {
        "LOW": 0,
        "MEDIUM": 1,
        "HIGH": 2,
        None: 3,
    }

    ranked = sorted(
        all_candidates,
        key=lambda item: (
            relevance_rank.get(
                str(item["business_relevance"]),
                9,
            ),
            classification_rank.get(
                str(item["classification"]),
                9,
            ),
            complexity_rank.get(
                item["adaptation_complexity"],
                9,
            ),
            -int(item["business_score"]),
            -int(bool(item["supporting_test_files"]) + bool(item["supporting_doc_files"])),
            str(item["source_id"]),
            str(item["file"]),
            int(item["line_start"]),
        ),
    )

    with candidates_path.open("w", encoding="utf-8") as handle:
        for item in ranked:
            handle.write(json.dumps(item, sort_keys=True) + "\n")

    return summary


def _print_summary(summary: JsonDict) -> None:
    print("BIZPROOF V0.6 external corpus audit")
    print(f"Sources checked: {summary['sources_checked']}")
    print(f"Code files examined: {summary['code_files_examined']}")
    print(f"Functions examined: {summary['functions_examined']}")
    print(f"Business candidates: {summary['business_candidates']}")
    print(f"Direct candidates: {summary['direct_candidates']}")
    print(f"Adaptation required: {summary['adaptation_required']}")
    print(f"Unsupported: {summary['unsupported']}")
    print(f"Direct candidate rate: {summary['direct_candidate_rate']:.6f}")
    print(f"Direct + adaptable rate: {summary['adaptable_or_direct_rate']:.6f}")

    sources = summary.get("sources", [])
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict):
                continue
            print(
                f"- {source['source_id']}: "
                f"functions={source['functions_examined']} "
                f"business={source['business_candidates']} "
                f"classes={source['classification_counts']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit external business-rule code for BIZPROOF eligibility."
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=Path("benchmarks/v0.6/sources.json"),
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
        default=Path("benchmarks/v0.6/results"),
    )
    args = parser.parse_args()

    summary = run_external_audit(
        sources_path=args.sources,
        lock_path=args.lock,
        external_root=args.external_root,
        output_dir=args.output_dir,
    )
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
