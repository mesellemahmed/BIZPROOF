from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypeAlias

from .adapter_preservation import _checkout_commit

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"
EXPECTED_SAMPLE_SIZE = 90
EXPECTED_ELIGIBLE_POPULATION = 730

FEASIBILITY_TIERS = (
    "F0_DIRECT_SYMBOLIC",
    "F1_DECLARATIVE_BINDING",
    "F2_EXPLICIT_ADAPTER",
    "F3_SEMANTIC_EXECUTION_REVIEW",
)

HARD_NODE_TYPES = (
    ast.AsyncFor,
    ast.AsyncWith,
    ast.Await,
    ast.Break,
    ast.Continue,
    ast.Delete,
    ast.For,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Match,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.While,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)

ADAPTER_NODE_TYPES = (
    ast.Dict,
    ast.DictComp,
    ast.GeneratorExp,
    ast.JoinedStr,
    ast.Lambda,
    ast.List,
    ast.ListComp,
    ast.NamedExpr,
    ast.Set,
    ast.SetComp,
    ast.Slice,
    ast.Starred,
    ast.Subscript,
    ast.Tuple,
)

ADAPTER_BINOPS = (
    ast.BitAnd,
    ast.BitOr,
    ast.BitXor,
    ast.Div,
    ast.FloorDiv,
    ast.LShift,
    ast.MatMult,
    ast.Mod,
    ast.Pow,
    ast.RShift,
)

ADAPTER_COMPARATORS = (
    ast.In,
    ast.Is,
    ast.IsNot,
    ast.NotIn,
)

MUTATING_CALL_NAMES = {
    "add",
    "append",
    "bulk_create",
    "clear",
    "commit",
    "create",
    "delete",
    "discard",
    "extend",
    "insert",
    "pop",
    "publish",
    "remove",
    "rollback",
    "save",
    "send",
    "set",
    "update",
    "write",
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def _nearest_class(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> str:
    current = parents.get(node)

    while current is not None:
        if isinstance(current, ast.ClassDef):
            return current.name
        current = parents.get(current)

    return ""


def _extract_function(
    *,
    source: str,
    filename: str,
    function_name: str,
    enclosing_class: str,
    line_start: int,
    line_end: int,
) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, str, int]:
    tree = ast.parse(source, filename=filename)

    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    matches: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        if node.name != function_name:
            continue

        if node.lineno != line_start:
            continue

        node_end = int(getattr(node, "end_lineno", node.lineno))
        if node_end != line_end:
            continue

        if _nearest_class(node, parents) != enclosing_class:
            continue

        matches.append(node)

    if len(matches) != 1:
        raise ValueError(
            "expected exactly one function match for "
            f"{filename}:{line_start}-{line_end}:"
            f"{enclosing_class}.{function_name}; found={len(matches)}"
        )

    node = matches[0]

    decorator_lines = [int(decorator.lineno) for decorator in node.decorator_list]
    snippet_start = min([line_start, *decorator_lines])

    lines = source.splitlines(keepends=True)
    snippet = "".join(lines[snippet_start - 1 : line_end])

    return node, snippet, snippet_start


def _call_name(call: ast.Call) -> str:
    try:
        return ast.unparse(call.func)
    except Exception:
        return type(call.func).__name__


def _leaf_call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _assignment_mutates_state(node: ast.AST) -> bool:
    targets: list[ast.AST] = []

    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets.append(node.target)
    elif isinstance(node, ast.AugAssign):
        targets.append(node.target)

    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, (ast.Attribute, ast.Subscript)):
                return True

    return False


def _semantic_nodes(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.AST]:
    result: list[ast.AST] = []

    for statement in node.body:
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            continue

        result.extend(ast.walk(statement))

    return result


def _classify_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> JsonDict:
    semantic_nodes = _semantic_nodes(node)

    hard_blockers = sorted(
        {type(item).__name__ for item in semantic_nodes if isinstance(item, HARD_NODE_TYPES)}
    )

    if isinstance(node, ast.AsyncFunctionDef):
        hard_blockers.append("AsyncFunctionDef")
        hard_blockers = sorted(set(hard_blockers))

    adapter_blockers = {
        type(item).__name__ for item in semantic_nodes if isinstance(item, ADAPTER_NODE_TYPES)
    }

    for item in semantic_nodes:
        if isinstance(item, ast.BinOp) and isinstance(
            item.op,
            ADAPTER_BINOPS,
        ):
            adapter_blockers.add(type(item.op).__name__)

        if isinstance(item, ast.Compare):
            for operator in item.ops:
                if isinstance(operator, ADAPTER_COMPARATORS):
                    adapter_blockers.add(type(operator).__name__)

        if isinstance(item, ast.AugAssign):
            adapter_blockers.add("AugAssign")

        if isinstance(item, ast.Call):
            if item.keywords:
                adapter_blockers.add("CallKeywords")

            if any(isinstance(arg, ast.Starred) for arg in item.args):
                adapter_blockers.add("CallStarArgs")

    if node.decorator_list:
        adapter_blockers.add("DecoratorSemantics")

    calls = [_call_name(item) for item in semantic_nodes if isinstance(item, ast.Call)]

    mutating_calls = sorted(
        {
            _call_name(item)
            for item in semantic_nodes
            if isinstance(item, ast.Call) and _leaf_call_name(item) in MUTATING_CALL_NAMES
        }
    )

    state_mutation = any(
        _assignment_mutates_state(item)
        for item in semantic_nodes
        if isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign))
    )

    nested_definitions = [
        item
        for statement in node.body
        for item in ast.walk(statement)
        if isinstance(
            item,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        )
    ]

    if nested_definitions:
        hard_blockers.append("NestedDefinition")
        hard_blockers = sorted(set(hard_blockers))

    if mutating_calls:
        hard_blockers.append("MutatingCall")
        hard_blockers = sorted(set(hard_blockers))

    if state_mutation:
        hard_blockers.append("StateMutation")
        hard_blockers = sorted(set(hard_blockers))

    attributes = sorted(
        {ast.unparse(item) for item in semantic_nodes if isinstance(item, ast.Attribute)}
    )

    call_count = len(calls)
    attribute_count = len(attributes)

    if hard_blockers:
        tier = "F3_SEMANTIC_EXECUTION_REVIEW"
        next_action = (
            "Establish controlled source execution and review stateful/control-flow "
            "semantics before any scalar projection."
        )
    elif adapter_blockers:
        tier = "F2_EXPLICIT_ADAPTER"
        next_action = (
            "Define and validate an explicit scalar semantic adapter, then replay it "
            "against locked source execution before symbolic certification."
        )
    elif call_count > 0 or attribute_count > 0:
        tier = "F1_DECLARATIVE_BINDING"
        next_action = (
            "Attempt symbolic translation with explicit declarative bindings for "
            "external calls and object attributes."
        )
    else:
        tier = "F0_DIRECT_SYMBOLIC"
        next_action = "Attempt direct BVC/symbolic translation without semantic bindings."

    statement_count = sum(1 for item in semantic_nodes if isinstance(item, ast.stmt))

    branch_count = sum(1 for item in semantic_nodes if isinstance(item, (ast.If, ast.IfExp)))

    return {
        "feasibility_tier": tier,
        "hard_blockers": hard_blockers,
        "adapter_blockers": sorted(adapter_blockers),
        "mutating_calls": mutating_calls,
        "state_mutation_detected": state_mutation,
        "call_count": call_count,
        "calls": sorted(set(calls)),
        "attribute_count": attribute_count,
        "attributes": attributes,
        "decorator_count": len(node.decorator_list),
        "decorators": [ast.unparse(decorator) for decorator in node.decorator_list],
        "statement_count": statement_count,
        "branch_count": branch_count,
        "next_action": next_action,
    }


def _verify_external_commits(
    *,
    lock_path: Path,
    external_root: Path,
) -> dict[str, str]:
    lock = _load_json(lock_path)
    raw_sources = lock.get("sources")

    if not isinstance(raw_sources, list):
        raise ValueError("LOCK sources must be a list")

    verified: dict[str, str] = {}

    for item in raw_sources:
        if not isinstance(item, dict):
            continue

        source_id = str(item["id"])
        expected = str(item["resolved_commit"])
        actual = _checkout_commit(external_root / source_id)

        if actual != expected:
            raise ValueError(
                f"external checkout mismatch for {source_id}: expected={expected}, actual={actual}"
            )

        verified[source_id] = actual

    return verified


def _weighted_estimate(
    assessments: list[JsonDict],
    tier: str,
) -> JsonDict:
    strata: dict[tuple[str, str], list[JsonDict]] = defaultdict(list)

    for item in assessments:
        stratum = item["stratum"]
        key = (
            str(stratum["source_id"]),
            str(stratum["adaptation_complexity"]),
        )
        strata[key].append(item)

    estimated_total = 0.0
    variance_total = 0.0

    for items in strata.values():
        first = items[0]["stratum"]
        population_size = int(first["population_size"])
        sample_size = len(items)

        if sample_size <= 0:
            raise ValueError("empty stratum")

        successes = sum(1 for item in items if item["feasibility"]["feasibility_tier"] == tier)

        sample_rate = successes / sample_size
        estimated_total += population_size * sample_rate

        if sample_size > 1:
            sample_variance = (
                successes * (sample_size - successes) / (sample_size * (sample_size - 1))
            )
        else:
            sample_variance = 0.0

        sampling_fraction = sample_size / population_size
        variance_total += (
            (population_size**2) * (1.0 - sampling_fraction) * sample_variance / sample_size
        )

    estimated_rate = estimated_total / EXPECTED_ELIGIBLE_POPULATION
    standard_error = math.sqrt(max(variance_total, 0.0)) / EXPECTED_ELIGIBLE_POPULATION

    margin = 1.96 * standard_error

    return {
        "estimated_population_count": estimated_total,
        "estimated_rate": estimated_rate,
        "approx_standard_error": standard_error,
        "approx_ci95_low": max(0.0, estimated_rate - margin),
        "approx_ci95_high": min(1.0, estimated_rate + margin),
        "ci_interpretation": (
            "Approximate design-based interval under the preregistered "
            "hash-as-uniform stratified sampling assumption."
        ),
    }


def _reviewer_report(summary: JsonDict) -> str:
    lines = [
        "# BIZPROOF V0.11 Static Generalization Feasibility Census",
        "",
        "## Scope",
        "",
        (
            "This phase is a static feasibility assessment over the preregistered "
            "90-candidate cohort. Feasibility tiers are routing decisions for the "
            "next validation stage; they are NOT proof verdicts and are NOT "
            "certification outcomes."
        ),
        "",
        "## Cohort integrity",
        "",
        f"- Cohort SHA-256: `{summary['cohort_sha256']}`",
        f"- Candidates assessed: {summary['assessed_candidates']}",
        f"- Source mismatches: {summary['source_mismatches']}",
        f"- Extraction failures: {summary['extraction_failures']}",
        "",
        "## Unweighted cohort counts",
        "",
    ]

    for tier in FEASIBILITY_TIERS:
        lines.append(f"- `{tier}`: {summary['feasibility_counts'].get(tier, 0)}")

    lines.extend(
        [
            "",
            "## Weighted eligible-population estimates",
            "",
        ]
    )

    weighted = summary["weighted_estimates"]

    for tier in FEASIBILITY_TIERS:
        item = weighted[tier]
        lines.append(
            "- "
            f"`{tier}`: estimated rate {item['estimated_rate']:.4f}, "
            f"approx. 95% CI "
            f"[{item['approx_ci95_low']:.4f}, "
            f"{item['approx_ci95_high']:.4f}]"
        )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "`F0`–`F3` describe the amount of semantic machinery expected "
                "before attempting V0.7/V0.8/V0.9 obligations. They must not be "
                "reported as CERTIFIED, PROVED, or DISPROVED."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def run_feasibility(
    *,
    cohort_path: Path,
    cohort_summary_path: Path,
    lock_path: Path,
    external_root: Path,
    output_dir: Path,
    expected_cohort_sha256: str = EXPECTED_COHORT_SHA256,
) -> JsonDict:
    cohort_summary = _load_json(cohort_summary_path)

    if str(cohort_summary["cohort_sha256"]) != expected_cohort_sha256:
        raise ValueError(f"cohort summary digest changed: {cohort_summary['cohort_sha256']}")

    cohort = _load_jsonl(cohort_path)

    if len(cohort) != EXPECTED_SAMPLE_SIZE:
        raise ValueError(f"expected {EXPECTED_SAMPLE_SIZE} cohort members, got {len(cohort)}")

    ids = [str(item["candidate_id"]) for item in cohort]
    actual_cohort_digest = _sha256_bytes("\n".join(ids).encode("utf-8"))

    if actual_cohort_digest != expected_cohort_sha256:
        raise ValueError(f"cohort digest changed: {actual_cohort_digest}")

    if len(ids) != len(set(ids)):
        raise ValueError("duplicate candidate_id in cohort")

    verified_commits = _verify_external_commits(
        lock_path=lock_path,
        external_root=external_root,
    )

    assessments: list[JsonDict] = []
    source_mismatches = 0
    extraction_failures = 0

    for item in cohort:
        candidate = item["candidate"]
        source_id = str(candidate["source_id"])

        if source_id not in verified_commits:
            raise ValueError(f"source not locked: {source_id}")

        source_path = external_root / source_id / str(candidate["file"])

        if not source_path.is_file():
            raise ValueError(f"source file missing: {source_path}")

        raw = source_path.read_bytes()
        actual_file_sha = _sha256_bytes(raw)
        expected_file_sha = str(candidate["source_file_sha256"])

        if actual_file_sha != expected_file_sha:
            source_mismatches += 1
            raise ValueError(f"source SHA mismatch for {item['candidate_id']}: {actual_file_sha}")

        source = raw.decode("utf-8")

        try:
            node, snippet, snippet_start = _extract_function(
                source=source,
                filename=str(source_path),
                function_name=str(candidate["function"]),
                enclosing_class=str(candidate["enclosing_class"] or ""),
                line_start=int(candidate["line_start"]),
                line_end=int(candidate["line_end"]),
            )
        except Exception:
            extraction_failures += 1
            raise

        feasibility = _classify_function(node)

        assessment: JsonDict = {
            "candidate_id": str(item["candidate_id"]),
            "selection_hash": str(item["selection_hash"]),
            "stratum": item["stratum"],
            "evidence_bucket": str(item["evidence_bucket"]),
            "provenance": {
                "source_id": source_id,
                "resolved_commit": verified_commits[source_id],
                "file": str(candidate["file"]),
                "source_file_sha256": actual_file_sha,
                "function": str(candidate["function"]),
                "enclosing_class": candidate["enclosing_class"],
                "line_start": int(candidate["line_start"]),
                "line_end": int(candidate["line_end"]),
                "snippet_line_start": snippet_start,
                "snippet_sha256": _sha256_bytes(snippet.encode("utf-8")),
            },
            "v0.6_classification": {
                "adaptation_complexity": str(candidate["adaptation_complexity"]),
                "classification_reasons": candidate["classification_reasons"],
                "business_score": int(candidate["business_score"]),
            },
            "feasibility": feasibility,
        }

        assessments.append(assessment)

    feasibility_counts = Counter(
        str(item["feasibility"]["feasibility_tier"]) for item in assessments
    )

    by_source: dict[str, dict[str, int]] = {}
    by_complexity: dict[str, dict[str, int]] = {}

    for source_id in sorted({str(item["stratum"]["source_id"]) for item in assessments}):
        counter = Counter(
            str(item["feasibility"]["feasibility_tier"])
            for item in assessments
            if str(item["stratum"]["source_id"]) == source_id
        )
        by_source[source_id] = dict(sorted(counter.items()))

    for complexity in sorted(
        {str(item["stratum"]["adaptation_complexity"]) for item in assessments}
    ):
        counter = Counter(
            str(item["feasibility"]["feasibility_tier"])
            for item in assessments
            if str(item["stratum"]["adaptation_complexity"]) == complexity
        )
        by_complexity[complexity] = dict(sorted(counter.items()))

    weighted_estimates = {tier: _weighted_estimate(assessments, tier) for tier in FEASIBILITY_TIERS}

    weighted_rate_sum = sum(float(item["estimated_rate"]) for item in weighted_estimates.values())

    if not math.isclose(weighted_rate_sum, 1.0, abs_tol=1e-12):
        raise ValueError(f"weighted feasibility rates do not sum to 1: {weighted_rate_sum}")

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "STATIC_GENERALIZATION_FEASIBILITY",
        "cohort_sha256": actual_cohort_digest,
        "assessed_candidates": len(assessments),
        "source_mismatches": source_mismatches,
        "extraction_failures": extraction_failures,
        "feasibility_counts": dict(sorted(feasibility_counts.items())),
        "by_source": by_source,
        "by_complexity": by_complexity,
        "weighted_estimates": weighted_estimates,
        "weighted_rate_sum": weighted_rate_sum,
        "certification_claim": False,
        "passed": (
            len(assessments) == EXPECTED_SAMPLE_SIZE
            and source_mismatches == 0
            and extraction_failures == 0
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "assessment.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in assessments),
        encoding="utf-8",
    )

    queue = sorted(
        assessments,
        key=lambda item: (
            FEASIBILITY_TIERS.index(str(item["feasibility"]["feasibility_tier"])),
            str(item["stratum"]["source_id"]),
            str(item["stratum"]["adaptation_complexity"]),
            str(item["candidate_id"]),
        ),
    )

    (output_dir / "next_actions.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "candidate_id": item["candidate_id"],
                    "feasibility_tier": item["feasibility"]["feasibility_tier"],
                    "next_action": item["feasibility"]["next_action"],
                    "hard_blockers": item["feasibility"]["hard_blockers"],
                    "adapter_blockers": item["feasibility"]["adapter_blockers"],
                    "source_id": item["stratum"]["source_id"],
                    "adaptation_complexity": item["stratum"]["adaptation_complexity"],
                    "file": item["provenance"]["file"],
                    "function": item["provenance"]["function"],
                    "enclosing_class": item["provenance"]["enclosing_class"],
                },
                sort_keys=True,
            )
            + "\n"
            for item in queue
        ),
        encoding="utf-8",
    )

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    (output_dir / "REVIEWER_REPORT.md").write_text(
        _reviewer_report(summary),
        encoding="utf-8",
    )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--cohort",
        type=Path,
        default=Path("benchmarks/v0.11/results/cohort.jsonl"),
    )
    parser.add_argument(
        "--cohort-summary",
        type=Path,
        default=Path("benchmarks/v0.11/results/summary.json"),
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
        default=Path("benchmarks/v0.11/feasibility"),
    )

    args = parser.parse_args()

    summary = run_feasibility(
        cohort_path=args.cohort,
        cohort_summary_path=args.cohort_summary,
        lock_path=args.lock,
        external_root=args.external_root,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 static generalization feasibility")
    print(f"Candidates assessed: {summary['assessed_candidates']}")
    print(f"Source mismatches: {summary['source_mismatches']}")
    print(f"Extraction failures: {summary['extraction_failures']}")
    print(f"Feasibility counts: {summary['feasibility_counts']}")
    print(f"Weighted rate sum: {summary['weighted_rate_sum']:.12f}")
    print("Certification claim: NO")
    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
