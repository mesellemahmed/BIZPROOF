from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypeAlias

from .generalization_candidate_proof import (
    _normalise_cohort_record,
)
from .generalization_protocol_closure import (
    _signature,
)

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT_SIZE = 90
EXPECTED_STRUCTURAL_TARGETS = 11

STRUCTURAL_PRIMITIVES = {
    "famille",
    "foyer_fiscal",
    "has_role",
    "individu",
    "members",
    "menage",
    "sum",
}


def _load_json(
    path: Path,
) -> JsonDict:

    value = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(f"expected JSON object: {path}")

    return value


def _load_jsonl(
    path: Path,
) -> list[JsonDict]:

    records: list[JsonDict] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue

        value = json.loads(raw)

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(f"expected JSON object: {path}")

        records.append(value)

    return records


def _sha256_file(
    path: Path,
) -> str:

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(
    value: str,
) -> str:

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _binding_subject(
    occurrence: JsonDict,
) -> str:

    binding = occurrence.get("authoritative_binding")

    if not isinstance(
        binding,
        dict,
    ):
        return ""

    status = str(occurrence["resolution_status"])

    if status == "FUNCTION_PARAMETER_BOUNDARY":
        return str(binding.get("parameter") or "")

    if status == "PARAMETER_METHOD_BOUNDARY":
        return str(binding.get("receiver_root") or binding.get("receiver") or "")

    return ""


def _probe_status(
    record: JsonDict | None,
) -> str:

    if record is None:
        return "NO_PROBE_RECORD"

    for key in (
        "probe_status",
        "status",
        "symbolic_status",
        "readiness_status",
    ):
        value = record.get(key)

        if value is not None:
            return str(value)

    return "UNKNOWN_PROBE_SCHEMA"


def _workplan_route(
    record: JsonDict | None,
) -> str:

    if record is None:
        return "NO_WORKPLAN_RECORD"

    for key in (
        "route",
        "workplan_route",
        "execution_route",
    ):
        value = record.get(key)

        if value is not None:
            return str(value)

    return "UNKNOWN_WORKPLAN_SCHEMA"


# PHASE-R-HOST-CHECKOUT-VERIFICATION
def _checkout_verification_map(
    path: Path,
) -> dict[str, JsonDict]:

    data = _load_json(path)

    expected_digest = str(data.get("manifest_digest") or "")

    digest_payload = dict(data)

    digest_payload.pop(
        "manifest_digest",
        None,
    )

    canonical = json.dumps(
        digest_payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=True,
    )

    actual_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    if not expected_digest or actual_digest != expected_digest:
        raise ValueError("checkout verification manifest digest mismatch")

    if data.get("generated_by") != "HOST_GIT_PREFLIGHT":
        raise ValueError("checkout verification provenance invalid")

    if data.get("all_passed") is not True:
        raise ValueError("host checkout verification failed")

    records = data.get("records")

    if not isinstance(
        records,
        list,
    ):
        raise ValueError("checkout verification records missing")

    result: dict[
        str,
        JsonDict,
    ] = {}

    for raw in records:
        if not isinstance(
            raw,
            dict,
        ):
            raise ValueError("invalid checkout verification record")

        source_id = str(raw["source_id"])

        expected_commit = str(raw["expected_commit"])

        actual_commit = str(raw["actual_commit"])

        if raw.get("passed") is not True or expected_commit != actual_commit:
            raise ValueError(f"checkout verification record failed: {source_id}")

        if source_id in result:
            raise ValueError(f"duplicate checkout verification: {source_id}")

        result[source_id] = dict(raw)

    if not result:
        raise ValueError("empty checkout verification manifest")

    return result


def _extract_candidate_source(
    *,
    source: str,
    class_name: str | None,
    function_name: str,
) -> tuple[
    ast.FunctionDef,
    str,
]:

    tree = ast.parse(source)

    if class_name:
        classes = [
            node
            for node in tree.body
            if (
                isinstance(
                    node,
                    ast.ClassDef,
                )
                and node.name == class_name
            )
        ]

        if len(classes) != 1:
            raise ValueError(f"candidate class lookup failed: {class_name}")

        functions = [
            node
            for node in classes[0].body
            if (
                isinstance(
                    node,
                    ast.FunctionDef,
                )
                and node.name == function_name
            )
        ]

    else:
        functions = [
            node
            for node in tree.body
            if (
                isinstance(
                    node,
                    ast.FunctionDef,
                )
                and node.name == function_name
            )
        ]

    if len(functions) != 1:
        raise ValueError(f"candidate function lookup failed: {class_name}.{function_name}")

    function = functions[0]

    segment = (
        ast.get_source_segment(
            source,
            function,
        )
        or ""
    )

    if not segment:
        raise ValueError("candidate source extraction failed")

    return (
        function,
        segment,
    )


def _binding_id(
    *,
    candidate_id: str,
    primitive: str,
    resolution_status: str,
    subject: str,
    source_expression: str,
) -> str:

    payload = "|".join(
        (
            candidate_id,
            primitive,
            resolution_status,
            subject,
            source_expression,
        )
    )

    return "DB-" + _sha256_text(payload)[:16]


def _protocol_index(
    groups: list[JsonDict],
) -> dict[
    tuple[
        str,
        str,
        str,
        str,
    ],
    JsonDict,
]:

    result: dict[
        tuple[
            str,
            str,
            str,
            str,
        ],
        JsonDict,
    ] = {}

    for item in groups:
        if item.get("structural_protocol_status") != "VALIDATED":
            continue

        primitive = str(item["primitive"])

        resolution = str(item["resolution_status"])

        subject = str(item["subject"])

        signatures = item.get("signatures")

        if not isinstance(
            signatures,
            dict,
        ):
            raise ValueError("protocol signature mapping missing")

        for signature in signatures:
            key = (
                primitive,
                resolution,
                subject,
                str(signature),
            )

            if key in result:
                raise ValueError(f"duplicate validated protocol key: {key}")

            result[key] = item

    return result


def _source_lock_map(
    lock_path: Path,
) -> dict[str, JsonDict]:

    data = _load_json(lock_path)

    sources = data.get("sources")

    if not isinstance(
        sources,
        list,
    ):
        raise ValueError("invalid V0.6 source lock")

    result: dict[
        str,
        JsonDict,
    ] = {}

    for item in sources:
        if not isinstance(
            item,
            dict,
        ):
            continue

        source_id = str(item["id"])

        result[source_id] = item

    return result


def build_closure(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    frontier_path = repo_root / (
        "benchmarks/v0.11/candidate_proof_frontier/candidate_frontier.jsonl"
    )

    cohort_path = repo_root / "benchmarks/v0.11/results/cohort.jsonl"

    occurrences_path = repo_root / ("benchmarks/v0.11/name_resolution/occurrence_resolution.jsonl")

    protocol_path = repo_root / ("benchmarks/v0.11/semantic_contracts/protocol_contracts.json")

    probe_path = repo_root / ("benchmarks/v0.11/symbolic_probe/probe.jsonl")

    workplan_path = repo_root / ("benchmarks/v0.11/workplan/queue.jsonl")

    terminal_summary_path = repo_root / ("benchmarks/v0.11/terminal_certification/summary.json")

    lock_candidates = [
        repo_root / "benchmarks/v0.6/LOCK.json",
        repo_root / "external_sources/v0.6/LOCK.json",
    ]

    lock_path = next(
        (path for path in lock_candidates if path.is_file()),
        None,
    )

    if lock_path is None:
        raise ValueError("V0.6 source lock missing")

    frontier = _load_jsonl(frontier_path)

    if len(frontier) != EXPECTED_COHORT_SIZE:
        raise ValueError("frontier size changed")

    targets = [
        item
        for item in frontier
        if (item.get("frontier_status") == "STRUCTURAL_PROTOCOL_SEMANTICS_REMAIN")
    ]

    if len(targets) != EXPECTED_STRUCTURAL_TARGETS:
        raise ValueError(
            "expected exactly "
            f"{EXPECTED_STRUCTURAL_TARGETS} "
            "structural-only candidates; "
            f"found {len(targets)}"
        )

    cohort = [_normalise_cohort_record(item) for item in _load_jsonl(cohort_path)]

    cohort_by_id = {str(item["candidate_id"]): item for item in cohort}

    occurrences = _load_jsonl(occurrences_path)

    occurrences_by_candidate: dict[
        str,
        list[JsonDict],
    ] = defaultdict(list)

    for item in occurrences:
        occurrences_by_candidate[str(item["candidate_id"])].append(item)

    protocol_data = _load_json(protocol_path)

    raw_groups = protocol_data.get("groups")

    if not isinstance(
        raw_groups,
        list,
    ):
        raise ValueError("protocol group list missing")

    protocol_groups = [
        item
        for item in raw_groups
        if isinstance(
            item,
            dict,
        )
    ]

    protocol_lookup = _protocol_index(protocol_groups)

    probe_records = _load_jsonl(probe_path)

    probe_by_id = {str(item["candidate_id"]): item for item in probe_records}

    workplan_records = _load_jsonl(workplan_path)

    workplan_by_id = {str(item["candidate_id"]): item for item in workplan_records}

    source_locks = _source_lock_map(lock_path)

    checkout_verification = _checkout_verification_map(output_dir / "checkout_verification.json")

    terminal_summary = _load_json(terminal_summary_path)

    if terminal_summary.get("terminal_outcomes_assigned") != 1:
        raise ValueError("Phase-Q terminal baseline changed")

    if terminal_summary.get("first_terminal_outcome") != "CERTIFIED_A2":
        raise ValueError("Phase-Q A2 baseline changed")

    manifests: list[JsonDict] = []

    statuses: list[JsonDict] = []

    source_slices: list[JsonDict] = []

    total_structural_occurrences = 0
    total_bindings = 0

    for frontier_item in sorted(
        targets,
        key=lambda item: str(item["candidate_id"]),
    ):
        candidate_id = str(frontier_item["candidate_id"])

        candidate = cohort_by_id.get(candidate_id)

        if candidate is None:
            raise ValueError("candidate missing from frozen cohort: " + candidate_id)

        structural_remaining = set(
            str(value)
            for value in frontier_item.get(
                "structural_semantics_remaining",
                [],
            )
        )

        unresolved_remaining = set(
            str(value)
            for value in frontier_item.get(
                "unresolved_primitives_remaining",
                [],
            )
        )

        if unresolved_remaining:
            raise ValueError(
                "structural-only candidate unexpectedly "
                "has non-structural unresolved primitives: "
                f"{candidate_id}: "
                f"{sorted(unresolved_remaining)}"
            )

        if not structural_remaining:
            raise ValueError(
                "structural-only candidate has empty structural frontier: " + candidate_id
            )

        if not structural_remaining.issubset(STRUCTURAL_PRIMITIVES):
            raise ValueError(
                f"unexpected structural primitive: {candidate_id}: {sorted(structural_remaining)}"
            )

        candidate_occurrences = occurrences_by_candidate.get(
            candidate_id,
            [],
        )

        structural_occurrences = [
            item
            for item in candidate_occurrences
            if (str(item.get("primitive")) in structural_remaining)
        ]

        observed_primitives = {str(item["primitive"]) for item in structural_occurrences}

        if observed_primitives != structural_remaining:
            raise ValueError(
                "structural frontier/occurrence mismatch: "
                f"{candidate_id}; "
                f"frontier={sorted(structural_remaining)}; "
                f"occurrences={sorted(observed_primitives)}"
            )

        total_structural_occurrences += len(structural_occurrences)

        bindings: list[JsonDict] = []

        for occurrence in sorted(
            structural_occurrences,
            key=lambda item: (
                str(item["primitive"]),
                str(item["source_expression"]),
            ),
        ):
            primitive = str(occurrence["primitive"])

            resolution = str(occurrence["resolution_status"])

            subject = _binding_subject(occurrence)

            expression = str(occurrence["source_expression"])

            signature = _signature(expression)

            protocol_key = (
                primitive,
                resolution,
                subject,
                signature,
            )

            protocol_group = protocol_lookup.get(protocol_key)

            if protocol_group is None:
                raise ValueError(
                    "validated protocol not found for "
                    f"{candidate_id}: {protocol_key}; "
                    f"expression={expression}"
                )

            binding_id = _binding_id(
                candidate_id=candidate_id,
                primitive=primitive,
                resolution_status=resolution,
                subject=subject,
                source_expression=expression,
            )

            bindings.append(
                {
                    "binding_id": binding_id,
                    "candidate_id": candidate_id,
                    "primitive": primitive,
                    "resolution_status": resolution,
                    "subject": subject,
                    "source_expression": expression,
                    "protocol_signature": signature,
                    "protocol_status": "VALIDATED",
                    "binding_semantics": ("DECLARATIVE_SOURCE_TO_BVC_INPUT"),
                    "value_semantics": ("EXTERNAL_INPUT_VALUE_NOT_REINTERPRETED"),
                    "certification_claim": False,
                }
            )

        total_bindings += len(bindings)

        source_id = str(candidate["source"])

        source_file = str(candidate["file"])

        source_path = repo_root / "external_sources/v0.6" / source_id / source_file

        if not source_path.is_file():
            raise ValueError("locked source missing: " + str(source_path))

        actual_file_sha = _sha256_file(source_path)

        expected_file_sha = str(candidate.get("source_file_sha256") or "")

        if actual_file_sha != expected_file_sha:
            raise ValueError("source file SHA mismatch: " + candidate_id)

        lock_record = source_locks.get(source_id)

        if lock_record is None:
            raise ValueError("source lock missing: " + source_id)

        locked_commit = str(lock_record["resolved_commit"])

        verification_record = checkout_verification.get(source_id)

        if verification_record is None:
            raise ValueError(f"host checkout verification missing: {source_id}")

        if (
            verification_record["passed"] is not True
            or verification_record["expected_commit"] != locked_commit
            or verification_record["actual_commit"] != locked_commit
        ):
            raise ValueError(f"locked checkout verification mismatch: {source_id}")

        source_text = source_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        class_name_value = candidate.get("class")

        class_name = None if class_name_value is None else str(class_name_value)

        (
            function_node,
            function_source,
        ) = _extract_candidate_source(
            source=source_text,
            class_name=class_name,
            function_name=str(candidate["function"]),
        )

        actual_function_sha = _sha256_text(function_source)

        expected_function_sha = str(candidate.get("function_sha256") or "")

        if actual_function_sha != expected_function_sha:
            raise ValueError("function SHA mismatch: " + candidate_id)

        expected_lines = [int(value) for value in candidate["lines"]]

        actual_lines = [
            int(function_node.lineno),
            int(function_node.end_lineno or function_node.lineno),
        ]

        if actual_lines != expected_lines:
            raise ValueError(
                f"function line mismatch: {candidate_id}: {actual_lines} != {expected_lines}"
            )

        probe_record = probe_by_id.get(candidate_id)

        workplan_record = workplan_by_id.get(candidate_id)

        probe_status = _probe_status(probe_record)

        workplan_route = _workplan_route(workplan_record)

        binding_coverage_ready = len(bindings) == len(structural_occurrences) and bool(bindings)

        symbolic_ready = probe_status == "SYMBOLIC_FRONTEND_READY"

        route_ready = workplan_route == "BINDING_DEFINITION"

        a1_ready = binding_coverage_ready and symbolic_ready and route_ready

        if a1_ready:
            final_status = "A1_PROOF_READY"

        elif not symbolic_ready:
            final_status = "DECLARATIVE_BINDINGS_CLOSED_SYMBOLIC_FRONTEND_NOT_READY"

        elif not route_ready:
            final_status = "DECLARATIVE_BINDINGS_CLOSED_WORKPLAN_ROUTE_NOT_A1"

        else:
            final_status = "DECLARATIVE_BINDING_REVIEW_REQUIRED"

        manifest_digest = _sha256_text(
            json.dumps(
                bindings,
                sort_keys=True,
                separators=(
                    ",",
                    ":",
                ),
            )
        )

        manifests.append(
            {
                "candidate_id": candidate_id,
                "source": source_id,
                "class": class_name,
                "function": candidate["function"],
                "bindings": bindings,
                "binding_count": len(bindings),
                "binding_manifest_sha256": manifest_digest,
                "certification_claim": False,
            }
        )

        source_slices.append(
            {
                "candidate_id": candidate_id,
                "source_id": source_id,
                "resolved_commit": locked_commit,
                "file": source_file,
                "source_file_sha256": actual_file_sha,
                "class": class_name,
                "function": candidate["function"],
                "lines": actual_lines,
                "function_sha256": actual_function_sha,
                "source_slice": function_source,
            }
        )

        statuses.append(
            {
                "candidate_id": candidate_id,
                "source": source_id,
                "class": class_name,
                "function": candidate["function"],
                "complexity": candidate["complexity"],
                "evidence": candidate["evidence"],
                "structural_primitives": sorted(structural_remaining),
                "structural_occurrences": len(structural_occurrences),
                "bindings_closed": len(bindings),
                "binding_coverage_ready": binding_coverage_ready,
                "symbolic_probe_status": probe_status,
                "workplan_route": workplan_route,
                "a1_proof_ready": a1_ready,
                "status": final_status,
                "terminal_outcome_assigned": False,
                "certification_claim": False,
            }
        )

    if len(manifests) != EXPECTED_STRUCTURAL_TARGETS:
        raise ValueError("structural manifest count changed")

    if len(statuses) != EXPECTED_STRUCTURAL_TARGETS:
        raise ValueError("structural status count changed")

    if not all(item["binding_coverage_ready"] is True for item in statuses):
        raise ValueError(
            "not all structural protocol occurrences received validated declarative bindings"
        )

    a1_ready_records = [item for item in statuses if (item["a1_proof_ready"] is True)]

    status_counts = Counter(str(item["status"]) for item in statuses)

    probe_counts = Counter(str(item["symbolic_probe_status"]) for item in statuses)

    route_counts = Counter(str(item["workplan_route"]) for item in statuses)

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": ("STRUCTURAL_DECLARATIVE_BINDING_CLOSURE"),
        "cohort_size": EXPECTED_COHORT_SIZE,
        "structural_candidates_targeted": len(statuses),
        "structural_candidates_binding_closed": sum(
            1 for item in statuses if (item["binding_coverage_ready"] is True)
        ),
        "structural_occurrences_bound": total_structural_occurrences,
        "declarative_bindings_created": total_bindings,
        "a1_proof_ready_candidates": len(a1_ready_records),
        "a1_proof_ready_candidate_ids": [item["candidate_id"] for item in a1_ready_records],
        "status_counts": dict(sorted(status_counts.items())),
        "symbolic_probe_counts": dict(sorted(probe_counts.items())),
        "workplan_route_counts": dict(sorted(route_counts.items())),
        "terminal_outcomes_assigned_before": 1,
        "terminal_outcomes_assigned_this_phase": 0,
        "terminal_outcomes_pending": 89,
        "certification_claim": False,
        "passed": (
            len(statuses) == EXPECTED_STRUCTURAL_TARGETS
            and total_bindings == total_structural_occurrences
            and all(item["binding_coverage_ready"] is True for item in statuses)
        ),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_dir / "binding_manifests.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in manifests
        ),
        encoding="utf-8",
    )

    (output_dir / "candidate_status.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in statuses
        ),
        encoding="utf-8",
    )

    (output_dir / "a1_proof_worklist.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in a1_ready_records
        ),
        encoding="utf-8",
    )

    (output_dir / "source_slices.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in source_slices
        ),
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

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(
            [
                ("# BIZPROOF V0.11 Structural Declarative Binding Closure"),
                "",
                (f"- Structural-only candidates: {len(statuses)}"),
                (f"- Structural occurrences bound: {total_structural_occurrences}"),
                (f"- Declarative bindings created: {total_bindings}"),
                (
                    "- Binding coverage: "
                    f"{sum(1 for item in statuses if item['binding_coverage_ready'])}"
                    f"/{len(statuses)}"
                ),
                (f"- A1 proof-ready candidates: {len(a1_ready_records)}"),
                ("- Terminal outcomes assigned in this phase: 0"),
                "",
                (
                    "A declarative binding maps an "
                    "observed source lookup to a BVC "
                    "input. It does not reinterpret the "
                    "external variable's business value."
                ),
                "",
                (
                    "Only candidates already marked "
                    "`SYMBOLIC_FRONTEND_READY` and routed "
                    "through `BINDING_DEFINITION` are "
                    "promoted to `A1_PROOF_READY`."
                ),
                "",
            ]
        ),
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
        default=Path("benchmarks/v0.11/declarative_binding_closure"),
    )

    args = parser.parse_args()

    summary = build_closure(
        repo_root=args.repo_root.resolve(),
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 structural declarative binding closure")

    print(
        "Structural candidates:",
        summary["structural_candidates_targeted"],
    )

    print(
        "Binding-closed:",
        summary["structural_candidates_binding_closed"],
    )

    print(
        "Structural occurrences:",
        summary["structural_occurrences_bound"],
    )

    print(
        "Declarative bindings:",
        summary["declarative_bindings_created"],
    )

    print(
        "A1 proof-ready:",
        summary["a1_proof_ready_candidates"],
    )

    print("Terminal outcomes assigned: 0")

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
