from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, TypeAlias

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"
EXPECTED_TOTAL = 90

ROUTES = (
    "AUTO_DIRECT_FORMALIZATION",
    "BINDING_DEFINITION",
    "SEMANTIC_SCOPE_REVIEW",
    "STRUCTURAL_REVIEW",
    "EXPLICIT_ADAPTER",
    "CONTROLLED_EXECUTION_REVIEW",
)

SEMANTIC_SCOPE_SHAPES = {
    "PASS_STUB",
    "NONE_RETURN",
    "CONSTANT_RETURN",
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


def _route_candidate(
    assessment: JsonDict,
    probe: JsonDict | None,
) -> JsonDict:
    tier = str(assessment["feasibility"]["feasibility_tier"])

    if tier in {
        "F0_DIRECT_SYMBOLIC",
        "F1_DECLARATIVE_BINDING",
    }:
        if probe is None:
            raise ValueError(f"missing symbolic probe for {assessment['candidate_id']}")

        if probe["probe_status"] != "SYMBOLIC_FRONTEND_READY":
            route = "STRUCTURAL_REVIEW"
            rationale = str(probe["review_reason"])

        elif int(probe["binding_count"]) > 0:
            route = "BINDING_DEFINITION"
            rationale = (
                "The hardened BSIR front-end succeeded but explicit binding obligations remain."
            )

        elif str(probe["semantic_shape"]) in SEMANTIC_SCOPE_SHAPES:
            route = "SEMANTIC_SCOPE_REVIEW"
            rationale = (
                "The function is structurally translatable but its body is a "
                "stub, None-return, or constant default. It must not be counted "
                "as direct business-rule formalization without scope review."
            )

        else:
            route = "AUTO_DIRECT_FORMALIZATION"
            rationale = (
                "The hardened BSIR front-end succeeded with no unresolved "
                "bindings and a non-trivial semantic shape."
            )

    elif tier == "F2_EXPLICIT_ADAPTER":
        route = "EXPLICIT_ADAPTER"
        rationale = (
            "Static feasibility identified structure requiring an explicit "
            "semantic adapter before preservation/equivalence checks."
        )

    elif tier == "F3_SEMANTIC_EXECUTION_REVIEW":
        route = "CONTROLLED_EXECUTION_REVIEW"
        rationale = (
            "Static feasibility identified stateful or hard control-flow "
            "semantics requiring controlled execution review."
        )

    else:
        raise ValueError(f"unknown feasibility tier: {tier}")

    provenance = assessment["provenance"]

    return {
        "candidate_id": str(assessment["candidate_id"]),
        "route": route,
        "rationale": rationale,
        "source_id": str(provenance["source_id"]),
        "adaptation_complexity": str(assessment["stratum"]["adaptation_complexity"]),
        "feasibility_tier": tier,
        "evidence_bucket": str(assessment["evidence_bucket"]),
        "file": str(provenance["file"]),
        "enclosing_class": provenance["enclosing_class"],
        "function": str(provenance["function"]),
        "line_start": int(provenance["line_start"]),
        "line_end": int(provenance["line_end"]),
        "semantic_shape": (str(probe["semantic_shape"]) if probe is not None else None),
        "binding_count": (int(probe["binding_count"]) if probe is not None else None),
        "required_bindings": (probe["required_bindings"] if probe is not None else []),
        "certification_claim": False,
    }


def build_workplan(
    *,
    feasibility_summary_path: Path,
    assessment_path: Path,
    probe_summary_path: Path,
    probe_path: Path,
    output_dir: Path,
) -> JsonDict:
    feasibility_summary = _load_json(feasibility_summary_path)
    probe_summary = _load_json(probe_summary_path)

    if str(feasibility_summary["cohort_sha256"]) != EXPECTED_COHORT_SHA256:
        raise ValueError("feasibility cohort digest changed")

    if str(probe_summary["cohort_sha256"]) != EXPECTED_COHORT_SHA256:
        raise ValueError("probe cohort digest changed")

    assessments = _load_jsonl(assessment_path)
    probes = _load_jsonl(probe_path)

    if len(assessments) != EXPECTED_TOTAL:
        raise ValueError(f"expected {EXPECTED_TOTAL} assessments, got {len(assessments)}")

    probe_map = {str(item["candidate_id"]): item for item in probes}

    if len(probe_map) != len(probes):
        raise ValueError("duplicate candidate_id in probe results")

    work_items = [
        _route_candidate(
            assessment,
            probe_map.get(str(assessment["candidate_id"])),
        )
        for assessment in assessments
    ]

    ids = [str(item["candidate_id"]) for item in work_items]

    if len(ids) != len(set(ids)):
        raise ValueError("duplicate candidate_id in workplan")

    counts = Counter(str(item["route"]) for item in work_items)

    by_source: dict[str, dict[str, int]] = {}

    for source_id in sorted({str(item["source_id"]) for item in work_items}):
        counter = Counter(
            str(item["route"]) for item in work_items if str(item["source_id"]) == source_id
        )
        by_source[source_id] = dict(sorted(counter.items()))

    route_rank = {route: index for index, route in enumerate(ROUTES)}

    queue = sorted(
        work_items,
        key=lambda item: (
            route_rank[str(item["route"])],
            str(item["source_id"]),
            str(item["adaptation_complexity"]),
            str(item["candidate_id"]),
        ),
    )

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "GENERALIZATION_EXECUTION_WORKPLAN_HARDENED",
        "cohort_sha256": EXPECTED_COHORT_SHA256,
        "total_candidates": len(work_items),
        "route_counts": dict(sorted(counts.items())),
        "by_source": by_source,
        "routes": list(ROUTES),
        "semantic_scope_gate": True,
        "certification_claim": False,
        "passed": len(work_items) == EXPECTED_TOTAL,
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "queue.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in queue),
        encoding="utf-8",
    )

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = [
        "# BIZPROOF V0.11 Hardened Execution Workplan",
        "",
        (
            "Every preregistered candidate is routed to its next engineering "
            "action. Structurally trivial default/stub functions are separated "
            "from direct business-rule formalization."
        ),
        "",
        f"- Candidates: {len(work_items)}",
        "",
        "## Route counts",
        "",
    ]

    for route in ROUTES:
        report.append(f"- `{route}`: {counts.get(route, 0)}")

    report.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "Routes are not proof or certification verdicts. A semantic "
                "scope review prevents trivial defaults/stubs from inflating "
                "generalization or certification yield."
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
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/workplan"),
    )

    args = parser.parse_args()

    summary = build_workplan(
        feasibility_summary_path=args.feasibility_summary,
        assessment_path=args.assessment,
        probe_summary_path=args.probe_summary,
        probe_path=args.probe,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 hardened execution workplan")
    print(f"Candidates: {summary['total_candidates']}")
    print(f"Routes: {summary['route_counts']}")
    print("Certification claim: NO")
    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
