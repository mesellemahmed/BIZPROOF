from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, TypeAlias

from .generalization_candidate_proof import (
    _normalise_cohort_record,
)

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT = 90

SEMANTIC_AMBIGUITY_IDS = {
    "6c9c5d18966c42d0",
    "aa5b28186fcc7696",
}

ALLOWED_AMBIGUITY_SHAPES = {
    "NONE_RETURN",
    "PASS_STUB",
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


def _canonical_digest(
    value: JsonDict,
) -> str:

    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _protocol_ambiguity_definition(
    path: Path,
) -> JsonDict:

    lines = path.read_text(encoding="utf-8").splitlines()

    matches = [
        {
            "line": index + 1,
            "text": line,
        }
        for index, line in enumerate(lines)
        if ("`NOT_CERTIFIED_SEMANTIC_AMBIGUITY`" in line)
    ]

    if len(matches) != 1:
        raise ValueError("semantic ambiguity protocol definition not unique")

    return matches[0]


def _distribution(
    states: list[JsonDict],
) -> JsonDict:

    counter = Counter(
        str(item.get("terminal_outcome"))
        for item in states
        if (item.get("state") == "TERMINAL_ASSIGNED")
    )

    keys = [
        "CERTIFIED_A0",
        "CERTIFIED_A1",
        "CERTIFIED_A2",
        "NOT_CERTIFIED_UNKNOWN",
        "NOT_CERTIFIED_UNSUPPORTED",
        "NOT_CERTIFIED_PROVENANCE",
        "NOT_CERTIFIED_EXECUTION",
        "NOT_CERTIFIED_SEMANTIC_AMBIGUITY",
    ]

    return {
        key: int(
            counter.get(
                key,
                0,
            )
        )
        for key in keys
    }


def build_sweep(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    phase_s_states = _load_jsonl(
        repo_root / ("benchmarks/v0.11/a1_batch_proofs/candidate_terminal_state.jsonl")
    )

    frontier = _load_jsonl(
        repo_root / ("benchmarks/v0.11/candidate_proof_frontier/candidate_frontier.jsonl")
    )

    workplan = _load_jsonl(repo_root / ("benchmarks/v0.11/workplan/queue.jsonl"))

    probes = _load_jsonl(repo_root / ("benchmarks/v0.11/symbolic_probe/probe.jsonl"))

    cohort = [
        _normalise_cohort_record(item)
        for item in _load_jsonl(repo_root / ("benchmarks/v0.11/results/cohort.jsonl"))
    ]

    policy_path = repo_root / ("benchmarks/v0.11/terminal_policy/semantic_ambiguity_policy.json")

    protocol_path = repo_root / "experiments/V0.11_PROTOCOL.md"

    if len(phase_s_states) != EXPECTED_COHORT:
        raise ValueError("Phase-S ledger size changed")

    if len(frontier) != EXPECTED_COHORT:
        raise ValueError("frontier size changed")

    if len(workplan) != EXPECTED_COHORT:
        raise ValueError("workplan size changed")

    if len(cohort) != EXPECTED_COHORT:
        raise ValueError("cohort size changed")

    assigned_before = [item for item in phase_s_states if (item["state"] == "TERMINAL_ASSIGNED")]

    pending_before = [item for item in phase_s_states if (item["state"] == "PENDING_UNASSIGNED")]

    if len(assigned_before) != 12:
        raise ValueError(f"Phase-S assigned count changed: {len(assigned_before)}")

    if len(pending_before) != 78:
        raise ValueError(f"Phase-S pending count changed: {len(pending_before)}")

    frontier_by_id = {str(item["candidate_id"]): item for item in frontier}

    workplan_by_id = {str(item["candidate_id"]): item for item in workplan}

    probe_by_id = {str(item["candidate_id"]): item for item in probes}

    cohort_by_id = {str(item["candidate_id"]): item for item in cohort}

    protocol_definition = _protocol_ambiguity_definition(protocol_path)

    policy_sha256 = _sha256_file(policy_path)

    policy_data = _load_json(policy_path)

    updated_states: list[JsonDict] = []

    ambiguity_records: list[JsonDict] = []

    ambiguity_seen: set[str] = set()

    for old_state in phase_s_states:
        candidate_id = str(old_state["candidate_id"])

        if candidate_id not in SEMANTIC_AMBIGUITY_IDS:
            updated_states.append(dict(old_state))

            continue

        if old_state["state"] != "PENDING_UNASSIGNED":
            raise ValueError("semantic-scope candidate already terminalized: " + candidate_id)

        frontier_item = frontier_by_id[candidate_id]

        workplan_item = workplan_by_id[candidate_id]

        probe_item = probe_by_id[candidate_id]

        candidate = cohort_by_id[candidate_id]

        if frontier_item["frontier_status"] != "NO_CONTRACT_OCCURRENCES":
            raise ValueError("semantic-scope candidate frontier changed")

        if workplan_item["route"] != "SEMANTIC_SCOPE_REVIEW":
            raise ValueError("semantic-scope route changed")

        semantic_shape = str(probe_item["semantic_shape"])

        if semantic_shape not in ALLOWED_AMBIGUITY_SHAPES:
            raise ValueError("unexpected semantic-scope shape: " + semantic_shape)

        required_bindings = probe_item.get(
            "required_bindings",
            [],
        )

        if required_bindings:
            raise ValueError("semantic-scope candidate unexpectedly requires bindings")

        evidence: JsonDict = {
            "schema_version": ("BIZPROOF-V0.11-NEGATIVE-TERMINAL-1"),
            "candidate_id": candidate_id,
            "terminal_outcome": ("NOT_CERTIFIED_SEMANTIC_AMBIGUITY"),
            "source_id": candidate["source"],
            "file": candidate["file"],
            "class": candidate["class"],
            "function": candidate["function"],
            "lines": candidate["lines"],
            "function_sha256": candidate["function_sha256"],
            "frontier_status": frontier_item["frontier_status"],
            "workplan_route": workplan_item["route"],
            "semantic_shape": semantic_shape,
            "required_bindings": required_bindings,
            "reason": (
                "No defensible business-semantic "
                "slice can be fixed for the frozen "
                f"{semantic_shape} function shape."
            ),
            "protocol_definition": protocol_definition,
            "frozen_policy": {
                "path": ("benchmarks/v0.11/terminal_policy/semantic_ambiguity_policy.json"),
                "sha256": policy_sha256,
                "policy": policy_data,
            },
            "certification_claim": False,
            "terminal_outcome_assigned": True,
        }

        evidence["evidence_digest"] = _canonical_digest(dict(evidence))

        evidence_path = output_dir / "evidence" / (candidate_id + ".json")

        evidence_path.write_text(
            json.dumps(
                evidence,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        updated_states.append(
            {
                "candidate_id": candidate_id,
                "state": "TERMINAL_ASSIGNED",
                "terminal_outcome": ("NOT_CERTIFIED_SEMANTIC_AMBIGUITY"),
                "certificate_id": None,
                "negative_evidence": str(evidence_path.relative_to(repo_root)).replace(
                    "\\",
                    "/",
                ),
                "evidence_digest": evidence["evidence_digest"],
            }
        )

        ambiguity_records.append(evidence)

        ambiguity_seen.add(candidate_id)

    if ambiguity_seen != SEMANTIC_AMBIGUITY_IDS:
        raise ValueError("semantic ambiguity candidate set changed")

    assigned_after = [item for item in updated_states if (item["state"] == "TERMINAL_ASSIGNED")]

    pending_after = [item for item in updated_states if (item["state"] == "PENDING_UNASSIGNED")]

    if len(assigned_after) != 14:
        raise ValueError(f"expected 14 terminal outcomes after sweep; found {len(assigned_after)}")

    if len(pending_after) != 76:
        raise ValueError(f"expected 76 pending outcomes after sweep; found {len(pending_after)}")

    pending_ids = {str(item["candidate_id"]) for item in pending_after}

    route_records: list[JsonDict] = []

    for candidate_id in sorted(pending_ids):
        candidate = cohort_by_id[candidate_id]

        frontier_item = frontier_by_id[candidate_id]

        workplan_item = workplan_by_id[candidate_id]

        pending_probe = probe_by_id.get(candidate_id)

        route_records.append(
            {
                "candidate_id": candidate_id,
                "source": candidate["source"],
                "complexity": candidate["complexity"],
                "evidence": candidate["evidence"],
                "class": candidate["class"],
                "function": candidate["function"],
                "frontier_status": frontier_item["frontier_status"],
                "unresolved_primitives": frontier_item.get(
                    "unresolved_primitives_remaining",
                    [],
                ),
                "workplan_route": workplan_item["route"],
                "probe_status": (
                    None if pending_probe is None else pending_probe.get("probe_status")
                ),
                "semantic_shape": (
                    None if pending_probe is None else pending_probe.get("semantic_shape")
                ),
                "binding_count": (
                    None if pending_probe is None else pending_probe.get("binding_count")
                ),
            }
        )

    route_counts = Counter(str(item["workplan_route"]) for item in route_records)

    frontier_counts = Counter(str(item["frontier_status"]) for item in route_records)

    cross_counts = Counter(
        (
            str(item["frontier_status"]),
            str(item["workplan_route"]),
        )
        for item in route_records
    )

    unresolved_primitive_counts: Counter[str] = Counter()

    for item in route_records:
        for primitive in item["unresolved_primitives"]:
            unresolved_primitive_counts[str(primitive)] += 1

    a0_worklist = [
        item
        for item in route_records
        if (
            item["frontier_status"] == "NO_CONTRACT_OCCURRENCES"
            and item["workplan_route"] == "AUTO_DIRECT_FORMALIZATION"
            and item["probe_status"] == "SYMBOLIC_FRONTEND_READY"
            and item["semantic_shape"] == "SUBSTANTIVE_EXPRESSION"
        )
    ]

    a2_worklist = [item for item in route_records if (item["workplan_route"] == "EXPLICIT_ADAPTER")]

    execution_worklist = [
        item for item in route_records if (item["workplan_route"] == "CONTROLLED_EXECUTION_REVIEW")
    ]

    binding_worklist = [
        item for item in route_records if (item["workplan_route"] == "BINDING_DEFINITION")
    ]

    structural_review_worklist = [
        item for item in route_records if (item["workplan_route"] == "STRUCTURAL_REVIEW")
    ]

    def write_jsonl(
        name: str,
        records: list[JsonDict],
    ) -> None:

        (output_dir / name).write_text(
            "".join(
                json.dumps(
                    item,
                    sort_keys=True,
                )
                + "\n"
                for item in records
            ),
            encoding="utf-8",
        )

    write_jsonl(
        "candidate_terminal_state.jsonl",
        updated_states,
    )

    write_jsonl(
        "remaining_candidates.jsonl",
        route_records,
    )

    write_jsonl(
        "a0_worklist.jsonl",
        a0_worklist,
    )

    write_jsonl(
        "a2_worklist.jsonl",
        a2_worklist,
    )

    write_jsonl(
        "controlled_execution_worklist.jsonl",
        execution_worklist,
    )

    write_jsonl(
        "binding_worklist.jsonl",
        binding_worklist,
    )

    write_jsonl(
        "structural_review_worklist.jsonl",
        structural_review_worklist,
    )

    cross_table = {
        f"{frontier_status} | {route}": count
        for (
            frontier_status,
            route,
        ), count in sorted(cross_counts.items())
    }

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "REMAINING_COHORT_SWEEP",
        "cohort_size": EXPECTED_COHORT,
        "terminalized_before": 12,
        "semantic_ambiguity_terminalized": len(ambiguity_records),
        "terminalized_after": len(assigned_after),
        "pending_after": len(pending_after),
        "terminal_distribution": _distribution(updated_states),
        "pending_frontier_counts": dict(sorted(frontier_counts.items())),
        "pending_workplan_route_counts": dict(sorted(route_counts.items())),
        "frontier_route_cross_table": cross_table,
        "unresolved_primitive_candidate_counts": dict(sorted(unresolved_primitive_counts.items())),
        "a0_worklist_size": len(a0_worklist),
        "a2_worklist_size": len(a2_worklist),
        "controlled_execution_worklist_size": len(execution_worklist),
        "binding_worklist_size": len(binding_worklist),
        "structural_review_worklist_size": len(structural_review_worklist),
        "weighted_metrics_ready": False,
        "final_certification_complete": False,
        "passed": True,
    }

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
                ("# BIZPROOF V0.11 Remaining Cohort Sweep"),
                "",
                "- Terminalized before: 12 / 90",
                (f"- Semantic ambiguity outcomes added: {len(ambiguity_records)}"),
                (f"- Terminalized after: {len(assigned_after)} / 90"),
                (f"- Pending after: {len(pending_after)} / 90"),
                "",
                (
                    "The semantic-scope outcomes are "
                    "restricted to frozen NONE_RETURN "
                    "and PASS_STUB candidates with no "
                    "binding obligations."
                ),
                "",
                (
                    "No pending candidate is converted "
                    "to A0/A2/UNKNOWN/UNSUPPORTED by "
                    "classification alone."
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
        default=Path("benchmarks/v0.11/remaining_cohort_sweep"),
    )

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    output_dir = args.output_dir

    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    output_dir = output_dir.resolve()

    summary = build_sweep(
        repo_root=repo_root,
        output_dir=output_dir,
    )

    print("BIZPROOF V0.11 remaining cohort sweep")

    print(
        "Terminalized before:",
        summary["terminalized_before"],
    )

    print(
        "Semantic ambiguity added:",
        summary["semantic_ambiguity_terminalized"],
    )

    print(
        "Terminalized after:",
        summary["terminalized_after"],
        "/90",
    )

    print(
        "Pending:",
        summary["pending_after"],
        "/90",
    )

    print(
        "A0 worklist:",
        summary["a0_worklist_size"],
    )

    print(
        "A2 worklist:",
        summary["a2_worklist_size"],
    )

    print(
        "Controlled execution:",
        summary["controlled_execution_worklist_size"],
    )

    print(
        "Binding worklist:",
        summary["binding_worklist_size"],
    )

    print("PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
