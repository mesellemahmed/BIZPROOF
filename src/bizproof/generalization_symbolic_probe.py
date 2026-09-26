from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, TypeAlias

from .adapter_preservation import _checkout_commit
from .generalization_feasibility import _extract_function

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"
EXPECTED_ATTEMPTED = 40
ATTEMPTED_TIERS = {
    "F0_DIRECT_SYMBOLIC",
    "F1_DECLARATIVE_BINDING",
}

READY = "SYMBOLIC_FRONTEND_READY"
REVIEW = "STRUCTURAL_REVIEW"


class UnsupportedStructure(ValueError):
    pass


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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _call_leaf(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return type(node.func).__name__


def _attribute_leaf(node: ast.Attribute) -> str:
    return node.attr


class IRBuilder:
    def __init__(self) -> None:
        self.bindings: dict[str, JsonDict] = {}
        self.environment: dict[str, JsonDict] = {}

    def _binding(
        self,
        *,
        kind: str,
        expression: ast.AST,
        primitive: str,
    ) -> JsonDict:
        source = ast.unparse(expression)
        key = _sha256_bytes(f"{kind}|{source}".encode())[:16]

        if key not in self.bindings:
            self.bindings[key] = {
                "binding_id": key,
                "kind": kind,
                "source_expression": source,
                "primitive": primitive,
            }

        return {
            "op": "binding",
            "binding_id": key,
        }

    def expression(self, node: ast.AST) -> JsonDict:
        if isinstance(node, ast.Constant):
            value = node.value

            if value is None:
                type_name = "none"
            elif isinstance(value, bool):
                type_name = "bool"
            elif isinstance(value, int):
                type_name = "int"
            elif isinstance(value, float):
                type_name = "float"
            elif isinstance(value, str):
                type_name = "str"
            else:
                raise UnsupportedStructure(f"unsupported constant type: {type(value).__name__}")

            return {
                "op": "const",
                "type": type_name,
                "value": value,
            }

        if isinstance(node, ast.Name):
            if node.id in self.environment:
                return self.environment[node.id]

            return {
                "op": "input",
                "name": node.id,
            }

        if isinstance(node, ast.Attribute):
            return self._binding(
                kind="ATTRIBUTE",
                expression=node,
                primitive=_attribute_leaf(node),
            )

        if isinstance(node, ast.Call):
            return self._binding(
                kind="CALL",
                expression=node,
                primitive=_call_leaf(node),
            )

        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                operator_name = "not"
            elif isinstance(node.op, ast.USub):
                operator_name = "neg"
            elif isinstance(node.op, ast.UAdd):
                operator_name = "pos"
            else:
                raise UnsupportedStructure(f"unsupported unary operator: {type(node.op).__name__}")

            return {
                "op": operator_name,
                "value": self.expression(node.operand),
            }

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                name = "and"
            elif isinstance(node.op, ast.Or):
                name = "or"
            else:
                raise UnsupportedStructure(
                    f"unsupported boolean operator: {type(node.op).__name__}"
                )

            return {
                "op": name,
                "values": [self.expression(value) for value in node.values],
            }

        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Add):
                binary_operator_name = "add"
            elif isinstance(node.op, ast.Sub):
                binary_operator_name = "sub"
            elif isinstance(node.op, ast.Mult):
                binary_operator_name = "mul"
            else:
                raise UnsupportedStructure(f"unsupported binary operator: {type(node.op).__name__}")

            return {
                "op": binary_operator_name,
                "left": self.expression(node.left),
                "right": self.expression(node.right),
            }

        if isinstance(node, ast.Compare):
            comparison_names: list[str] = []

            for comparison_operator in node.ops:
                if isinstance(comparison_operator, ast.Eq):
                    comparison_names.append("eq")
                elif isinstance(comparison_operator, ast.NotEq):
                    comparison_names.append("ne")
                elif isinstance(comparison_operator, ast.Lt):
                    comparison_names.append("lt")
                elif isinstance(comparison_operator, ast.LtE):
                    comparison_names.append("le")
                elif isinstance(comparison_operator, ast.Gt):
                    comparison_names.append("gt")
                elif isinstance(comparison_operator, ast.GtE):
                    comparison_names.append("ge")
                else:
                    raise UnsupportedStructure(
                        f"unsupported comparison operator: {type(comparison_operator).__name__}"
                    )

            return {
                "op": "compare",
                "left": self.expression(node.left),
                "operators": comparison_names,
                "comparators": [self.expression(value) for value in node.comparators],
            }

        if isinstance(node, ast.IfExp):
            return {
                "op": "ite",
                "condition": self.expression(node.test),
                "then": self.expression(node.body),
                "else": self.expression(node.orelse),
            }

        raise UnsupportedStructure(f"unsupported expression: {type(node).__name__}")

    def _simple_assignment(
        self,
        target: ast.AST,
        value: ast.AST,
    ) -> None:
        if not isinstance(target, ast.Name):
            raise UnsupportedStructure(f"unsupported assignment target: {type(target).__name__}")

        self.environment[target.id] = self.expression(value)

    def function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> JsonDict:
        if isinstance(node, ast.AsyncFunctionDef):
            raise UnsupportedStructure("async function")

        statements = list(node.body)

        if (
            statements
            and isinstance(statements[0], ast.Expr)
            and isinstance(statements[0].value, ast.Constant)
            and isinstance(statements[0].value.value, str)
        ):
            statements = statements[1:]

        if not statements:
            raise UnsupportedStructure("empty function body")

        return_ir: JsonDict | None = None

        for index, statement in enumerate(statements):
            if isinstance(statement, ast.Assign):
                if len(statement.targets) != 1:
                    raise UnsupportedStructure("multiple assignment targets")

                self._simple_assignment(
                    statement.targets[0],
                    statement.value,
                )
                continue

            if isinstance(statement, ast.AnnAssign):
                if statement.value is None:
                    raise UnsupportedStructure("annotation without assigned value")

                self._simple_assignment(
                    statement.target,
                    statement.value,
                )
                continue

            if isinstance(statement, ast.Return):
                if index != len(statements) - 1:
                    raise UnsupportedStructure("return before end of function body")

                if statement.value is None:
                    return_ir = {
                        "op": "const",
                        "type": "none",
                        "value": None,
                    }
                else:
                    return_ir = self.expression(statement.value)
                continue

            if isinstance(statement, ast.Pass):
                if len(statements) != 1:
                    raise UnsupportedStructure("pass mixed with executable statements")

                return_ir = {
                    "op": "const",
                    "type": "none",
                    "value": None,
                }
                continue

            if isinstance(statement, ast.If):
                raise UnsupportedStructure("statement-level If requires branch-state normalization")

            raise UnsupportedStructure(f"unsupported statement: {type(statement).__name__}")

        if return_ir is None:
            raise UnsupportedStructure("no explicit or implicit terminal return")

        return {
            "ir_version": "BSIR-SKELETON-0.11",
            "return": return_ir,
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


def _binding_catalog(
    probes: list[JsonDict],
) -> list[JsonDict]:
    grouped: dict[tuple[str, str], JsonDict] = {}

    for probe in probes:
        for binding in probe["required_bindings"]:
            key = (
                str(binding["kind"]),
                str(binding["primitive"]),
            )

            if key not in grouped:
                grouped[key] = {
                    "kind": key[0],
                    "primitive": key[1],
                    "occurrences": 0,
                    "candidate_ids": set(),
                    "source_ids": set(),
                    "examples": set(),
                }

            item = grouped[key]
            item["occurrences"] += 1
            item["candidate_ids"].add(probe["candidate_id"])
            item["source_ids"].add(probe["source_id"])
            item["examples"].add(binding["source_expression"])

    result: list[JsonDict] = []

    for item in grouped.values():
        result.append(
            {
                "kind": item["kind"],
                "primitive": item["primitive"],
                "occurrences": int(item["occurrences"]),
                "candidate_count": len(item["candidate_ids"]),
                "candidate_ids": sorted(item["candidate_ids"]),
                "source_ids": sorted(item["source_ids"]),
                "examples": sorted(item["examples"])[:10],
            }
        )

    return sorted(
        result,
        key=lambda item: (
            -int(item["candidate_count"]),
            -int(item["occurrences"]),
            str(item["kind"]),
            str(item["primitive"]),
        ),
    )


def run_probe(
    *,
    assessment_path: Path,
    cohort_summary_path: Path,
    lock_path: Path,
    external_root: Path,
    output_dir: Path,
) -> JsonDict:
    cohort_summary = _load_json(cohort_summary_path)

    if str(cohort_summary["cohort_sha256"]) != EXPECTED_COHORT_SHA256:
        raise ValueError(f"cohort digest changed: {cohort_summary['cohort_sha256']}")

    assessments = _load_jsonl(assessment_path)

    attempted = [
        item
        for item in assessments
        if str(item["feasibility"]["feasibility_tier"]) in ATTEMPTED_TIERS
    ]

    if len(attempted) != EXPECTED_ATTEMPTED:
        raise ValueError(f"expected {EXPECTED_ATTEMPTED} F0/F1 candidates, got {len(attempted)}")

    verified_commits = _verify_external_commits(
        lock_path=lock_path,
        external_root=external_root,
    )

    probes: list[JsonDict] = []
    source_mismatches = 0
    extraction_failures = 0

    for assessment in attempted:
        provenance = assessment["provenance"]
        source_id = str(provenance["source_id"])

        source_path = external_root / source_id / str(provenance["file"])

        if not source_path.is_file():
            raise ValueError(f"source file missing: {source_path}")

        raw = source_path.read_bytes()
        actual_sha = _sha256_bytes(raw)

        if actual_sha != str(provenance["source_file_sha256"]):
            source_mismatches += 1
            raise ValueError(f"source SHA mismatch for {assessment['candidate_id']}")

        source = raw.decode("utf-8")

        try:
            node, snippet, snippet_start = _extract_function(
                source=source,
                filename=str(source_path),
                function_name=str(provenance["function"]),
                enclosing_class=str(provenance["enclosing_class"] or ""),
                line_start=int(provenance["line_start"]),
                line_end=int(provenance["line_end"]),
            )
        except Exception:
            extraction_failures += 1
            raise

        builder = IRBuilder()

        status = READY
        reason: str | None = None
        ir: JsonDict | None = None

        try:
            ir = builder.function(node)
        except UnsupportedStructure as exc:
            status = REVIEW
            reason = str(exc)

        required_bindings = sorted(
            builder.bindings.values(),
            key=lambda item: (
                str(item["kind"]),
                str(item["primitive"]),
                str(item["source_expression"]),
            ),
        )

        probes.append(
            {
                "candidate_id": str(assessment["candidate_id"]),
                "source_id": source_id,
                "adaptation_complexity": str(assessment["stratum"]["adaptation_complexity"]),
                "feasibility_tier": str(assessment["feasibility"]["feasibility_tier"]),
                "probe_status": status,
                "review_reason": reason,
                "resolved_commit": verified_commits[source_id],
                "file": str(provenance["file"]),
                "enclosing_class": provenance["enclosing_class"],
                "function": str(provenance["function"]),
                "line_start": int(provenance["line_start"]),
                "line_end": int(provenance["line_end"]),
                "snippet_line_start": snippet_start,
                "snippet_sha256": _sha256_bytes(snippet.encode("utf-8")),
                "ir": ir,
                "ir_sha256": (_json_digest(ir) if ir is not None else None),
                "required_bindings": required_bindings,
                "binding_count": len(required_bindings),
                "certification_claim": False,
            }
        )

    counts = Counter(str(item["probe_status"]) for item in probes)

    by_original_tier: dict[str, dict[str, int]] = {}

    for tier in sorted(ATTEMPTED_TIERS):
        counter = Counter(
            str(item["probe_status"]) for item in probes if str(item["feasibility_tier"]) == tier
        )
        by_original_tier[tier] = dict(sorted(counter.items()))

    ready = [item for item in probes if item["probe_status"] == READY]

    binding_counts = Counter(int(item["binding_count"]) for item in ready)

    catalog = _binding_catalog(probes)

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "SYMBOLIC_FRONTEND_PROBE",
        "cohort_sha256": EXPECTED_COHORT_SHA256,
        "attempted_candidates": len(probes),
        "source_mismatches": source_mismatches,
        "extraction_failures": extraction_failures,
        "probe_counts": dict(sorted(counts.items())),
        "by_original_feasibility_tier": by_original_tier,
        "ready_binding_count_distribution": {
            str(key): value for key, value in sorted(binding_counts.items())
        },
        "binding_primitives": len(catalog),
        "binding_occurrences": sum(int(item["occurrences"]) for item in catalog),
        "certification_claim": False,
        "passed": (
            len(probes) == EXPECTED_ATTEMPTED
            and source_mismatches == 0
            and extraction_failures == 0
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "probe.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in probes),
        encoding="utf-8",
    )

    (output_dir / "binding_catalog.json").write_text(
        json.dumps(
            {
                "benchmark_version": "0.11.0",
                "phase": "SYMBOLIC_BINDING_CATALOG",
                "certification_claim": False,
                "bindings": catalog,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_lines = [
        "# BIZPROOF V0.11 Symbolic Front-End Probe",
        "",
        (
            "This phase tests structural translation into a conservative "
            "BSIR skeleton for the preregistered F0/F1 candidates."
        ),
        "",
        (
            "A `SYMBOLIC_FRONTEND_READY` result is NOT a proof and is NOT "
            "a certification verdict. It only means the selected function "
            "can be represented by the current structural front-end while "
            "leaving external calls/attributes as explicit binding obligations."
        ),
        "",
        f"- Attempted candidates: {len(probes)}",
        f"- Ready: {counts.get(READY, 0)}",
        f"- Structural review: {counts.get(REVIEW, 0)}",
        f"- Source mismatches: {source_mismatches}",
        f"- Extraction failures: {extraction_failures}",
        f"- Distinct binding primitives: {len(catalog)}",
        "",
        "## Most recurrent binding primitives",
        "",
    ]

    for item in catalog[:20]:
        report_lines.append(
            "- "
            f"`{item['kind']}:{item['primitive']}` — "
            f"{item['candidate_count']} candidates / "
            f"{item['occurrences']} occurrences"
        )

    report_lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "The generated IR and binding catalog are engineering evidence "
                "for subsequent contract/domain construction. No candidate is "
                "reported as PROVED, DISPROVED, or CERTIFIED in this phase."
            ),
            "",
        ]
    )

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--assessment",
        type=Path,
        default=Path("benchmarks/v0.11/feasibility/assessment.jsonl"),
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
        default=Path("benchmarks/v0.11/symbolic_probe"),
    )

    args = parser.parse_args()

    summary = run_probe(
        assessment_path=args.assessment,
        cohort_summary_path=args.cohort_summary,
        lock_path=args.lock,
        external_root=args.external_root,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 symbolic front-end probe")
    print(f"Attempted candidates: {summary['attempted_candidates']}")
    print(f"Probe counts: {summary['probe_counts']}")
    print(f"Binding primitives: {summary['binding_primitives']}")
    print(f"Binding occurrences: {summary['binding_occurrences']}")
    print("Certification claim: NO")
    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
