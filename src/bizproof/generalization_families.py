from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypeAlias

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"
EXPECTED_TOTAL = 90


def _load_json(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[JsonDict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _signature(values: list[str]) -> str:
    return "+".join(sorted(set(values))) or "NONE"


def _family_id(prefix: str, signature: str) -> str:
    digest = hashlib.sha256(f"{prefix}|{signature}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


def build_families(
    *,
    feasibility_summary_path: Path,
    assessment_path: Path,
    probe_summary_path: Path,
    probe_path: Path,
    workplan_summary_path: Path,
    queue_path: Path,
    output_dir: Path,
) -> JsonDict:
    feasibility_summary = _load_json(feasibility_summary_path)
    probe_summary = _load_json(probe_summary_path)
    workplan_summary = _load_json(workplan_summary_path)

    for source_summary in (
        feasibility_summary,
        probe_summary,
        workplan_summary,
    ):
        if str(source_summary["cohort_sha256"]) != EXPECTED_COHORT_SHA256:
            raise ValueError("cohort digest mismatch")

    assessments = _load_jsonl(assessment_path)
    probes = _load_jsonl(probe_path)
    queue = _load_jsonl(queue_path)

    if len(assessments) != EXPECTED_TOTAL:
        raise ValueError("assessment coverage changed")

    if len(queue) != EXPECTED_TOTAL:
        raise ValueError("workplan coverage changed")

    assessment_map = {str(item["candidate_id"]): item for item in assessments}
    probe_map = {str(item["candidate_id"]): item for item in probes}

    binding_groups: dict[tuple[str, str], JsonDict] = {}

    for probe in probes:
        for binding in probe["required_bindings"]:
            key = (
                str(binding["kind"]),
                str(binding["primitive"]),
            )

            if key not in binding_groups:
                binding_groups[key] = {
                    "kind": key[0],
                    "primitive": key[1],
                    "candidate_ids": set(),
                    "source_ids": set(),
                    "examples": set(),
                    "occurrences": 0,
                }

            family = binding_groups[key]
            family["candidate_ids"].add(probe["candidate_id"])
            family["source_ids"].add(probe["source_id"])
            family["examples"].add(binding["source_expression"])
            family["occurrences"] += 1

    binding_families: list[JsonDict] = []

    for (kind, primitive), item in binding_groups.items():
        pattern_class = {
            "GLOBAL_NAME": "GLOBAL_SYMBOL",
            "ATTRIBUTE": "OBJECT_ATTRIBUTE",
            "CALL": "EXTERNAL_CALL",
        }.get(kind, "OTHER")

        signature = f"{kind}:{primitive}"

        binding_families.append(
            {
                "family_id": _family_id(
                    "BIND",
                    signature,
                ),
                "kind": kind,
                "primitive": primitive,
                "pattern_class": pattern_class,
                "resolution_status": "UNRESOLVED",
                "candidate_count": len(item["candidate_ids"]),
                "occurrences": int(item["occurrences"]),
                "candidate_ids": sorted(item["candidate_ids"]),
                "source_ids": sorted(item["source_ids"]),
                "examples": sorted(item["examples"])[:10],
                "certification_claim": False,
            }
        )

    binding_families.sort(
        key=lambda item: (
            -int(item["candidate_count"]),
            -int(item["occurrences"]),
            str(item["kind"]),
            str(item["primitive"]),
        )
    )

    adapter_groups: dict[str, list[str]] = defaultdict(list)
    execution_groups: dict[str, list[str]] = defaultdict(list)
    structural_groups: dict[str, list[str]] = defaultdict(list)
    semantic_scope_groups: dict[str, list[str]] = defaultdict(list)

    for item in queue:
        candidate_id = str(item["candidate_id"])
        route = str(item["route"])

        if route == "EXPLICIT_ADAPTER":
            assessment = assessment_map[candidate_id]
            signature = _signature(
                [str(value) for value in assessment["feasibility"]["adapter_blockers"]]
            )
            adapter_groups[signature].append(candidate_id)

        elif route == "CONTROLLED_EXECUTION_REVIEW":
            assessment = assessment_map[candidate_id]
            signature = _signature(
                [str(value) for value in assessment["feasibility"]["hard_blockers"]]
            )
            execution_groups[signature].append(candidate_id)

        elif route == "STRUCTURAL_REVIEW":
            probe = probe_map[candidate_id]
            signature = str(probe["review_reason"])
            structural_groups[signature].append(candidate_id)

        elif route == "SEMANTIC_SCOPE_REVIEW":
            probe = probe_map[candidate_id]
            signature = str(probe["semantic_shape"])
            semantic_scope_groups[signature].append(candidate_id)

    def serialize_groups(
        prefix: str,
        groups: dict[str, list[str]],
    ) -> list[JsonDict]:
        result: list[JsonDict] = []

        for signature, candidate_ids in groups.items():
            result.append(
                {
                    "family_id": _family_id(
                        prefix,
                        signature,
                    ),
                    "signature": signature,
                    "candidate_count": len(candidate_ids),
                    "candidate_ids": sorted(candidate_ids),
                    "certification_claim": False,
                }
            )

        return sorted(
            result,
            key=lambda item: (
                -int(item["candidate_count"]),
                str(item["signature"]),
            ),
        )

    adapter_families = serialize_groups(
        "ADAPTER",
        adapter_groups,
    )
    execution_families = serialize_groups(
        "EXEC",
        execution_groups,
    )
    structural_families = serialize_groups(
        "STRUCT",
        structural_groups,
    )
    semantic_scope_families = serialize_groups(
        "SCOPE",
        semantic_scope_groups,
    )

    route_counts = Counter(str(item["route"]) for item in queue)

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "GENERALIZATION_FAMILY_CENSUS",
        "cohort_sha256": EXPECTED_COHORT_SHA256,
        "total_candidates": len(queue),
        "route_counts": dict(sorted(route_counts.items())),
        "binding_family_count": len(binding_families),
        "adapter_family_count": len(adapter_families),
        "execution_family_count": len(execution_families),
        "structural_review_family_count": len(structural_families),
        "semantic_scope_family_count": len(semantic_scope_families),
        "certification_claim": False,
        "passed": len(queue) == EXPECTED_TOTAL,
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_dir / "binding_families.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "families": binding_families,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "adapter_families.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "families": adapter_families,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "execution_families.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "families": execution_families,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "review_families.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "structural_review_families": structural_families,
                "semantic_scope_families": semantic_scope_families,
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
        "# BIZPROOF V0.11 Family Census",
        "",
        (
            "This phase groups the frozen 90-candidate cohort into reusable "
            "engineering families without assigning business semantics or "
            "certification verdicts."
        ),
        "",
        f"- Binding families: {len(binding_families)}",
        f"- Adapter blocker families: {len(adapter_families)}",
        f"- Controlled-execution blocker families: {len(execution_families)}",
        f"- Structural-review families: {len(structural_families)}",
        f"- Semantic-scope families: {len(semantic_scope_families)}",
        "",
        "## Interpretation boundary",
        "",
        (
            "Binding family entries remain UNRESOLVED until their business "
            "meaning and source-to-BVC mapping are validated. Family grouping "
            "is an engineering acceleration mechanism, not certification."
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
        "--feasibility-summary",
        type=Path,
        default=Path("benchmarks/v0.11/feasibility/summary.json"),
    )
    parser.add_argument(
        "--assessment",
        type=Path,
        default=Path("benchmarks/v0.11/feasibility/assessment.jsonl"),
    )
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
        default=Path("benchmarks/v0.11/families"),
    )

    args = parser.parse_args()

    summary = build_families(
        feasibility_summary_path=args.feasibility_summary,
        assessment_path=args.assessment,
        probe_summary_path=args.probe_summary,
        probe_path=args.probe,
        workplan_summary_path=args.workplan_summary,
        queue_path=args.queue,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 family census")
    print(f"Binding families: {summary['binding_family_count']}")
    print(f"Adapter families: {summary['adapter_family_count']}")
    print(f"Execution families: {summary['execution_family_count']}")
    print("Certification claim: NO")
    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
