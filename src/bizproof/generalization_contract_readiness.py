from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypeAlias

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_COHORT_SHA256 = "3144f973a166ebee41a059c538b81ffac5a5d15737982c6d95e59175325ca108"

EXPECTED_CONTRACT_CANDIDATES = 15


LOCAL_TERMINALS = {
    "LOCAL_DEFINITION",
    "LOCAL_ASSIGNMENT",
}

PARAMETER_TERMINALS = {
    "FUNCTION_PARAMETER_BOUNDARY",
}

BUILTIN_TERMINALS = {
    "PYTHON_BUILTIN_BOUNDARY",
}

EXTERNAL_TERMINALS = {
    "EXTERNAL_DEPENDENCY_BOUNDARY",
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

    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = line.strip()

        if not line:
            continue

        value = json.loads(line)

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(f"record {number} in {path} is not an object")

        records.append(value)

    return records


def _action_for_terminals(
    terminals: set[str],
) -> str:

    if terminals and terminals <= LOCAL_TERMINALS:
        return "LOCAL_SOURCE_CONTRACT_DRAFT"

    if terminals and terminals <= PARAMETER_TERMINALS:
        return "PARAMETER_PROTOCOL_CONTRACT_DRAFT"

    if terminals and terminals <= BUILTIN_TERMINALS:
        return "BUILTIN_CONTRACT_DRAFT"

    if terminals and terminals <= EXTERNAL_TERMINALS:
        return "EXTERNAL_DEPENDENCY_LOCK_REQUIRED"

    return "TRACE_REVIEW_REQUIRED"


def _terminal_steps(
    trace_item: JsonDict,
) -> list[JsonDict]:

    steps: list[JsonDict] = []

    for trace in trace_item["traces"]:
        raw_steps = trace.get(
            "steps",
            [],
        )

        if not isinstance(
            raw_steps,
            list,
        ):
            continue

        for step in raw_steps:
            if isinstance(
                step,
                dict,
            ):
                steps.append(step)

    return steps


def _external_boundaries(
    traces: list[JsonDict],
) -> list[JsonDict]:

    grouped: dict[
        tuple[str, str],
        JsonDict,
    ] = {}

    for trace_item in traces:
        for step in _terminal_steps(trace_item):
            if str(step.get("step_kind")) != "EXTERNAL_DEPENDENCY_BOUNDARY":
                continue

            module = str(step.get("module") or "")

            symbol = str(step.get("symbol") or "")

            key = (
                module,
                symbol,
            )

            if key not in grouped:
                grouped[key] = {
                    "module": module,
                    "symbol": symbol,
                    "candidate_ids": set(),
                    "source_ids": set(),
                    "primitives": set(),
                    "occurrences": 0,
                }

            item = grouped[key]

            item["candidate_ids"].add(str(trace_item["candidate_id"]))

            item["source_ids"].add(str(trace_item["source_id"]))

            item["primitives"].add(str(trace_item["primitive"]))

            item["occurrences"] += 1

    result: list[JsonDict] = []

    for item in grouped.values():
        result.append(
            {
                "module": item["module"],
                "package_root": str(item["module"]).split(".")[0],
                "symbol": item["symbol"],
                "candidate_ids": sorted(item["candidate_ids"]),
                "source_ids": sorted(item["source_ids"]),
                "primitives": sorted(item["primitives"]),
                "occurrences": int(item["occurrences"]),
                "lock_status": "MISSING",
                "semantic_contract_status": "MISSING",
                "resolution_status": "UNRESOLVED",
                "certification_claim": False,
            }
        )

    return sorted(
        result,
        key=lambda item: (
            str(item["package_root"]),
            str(item["module"]),
            str(item["symbol"]),
        ),
    )


def _parameter_protocols(
    traces: list[JsonDict],
) -> list[JsonDict]:

    grouped: dict[
        tuple[str, str],
        JsonDict,
    ] = {}

    for trace_item in traces:
        for step in _terminal_steps(trace_item):
            if str(step.get("step_kind")) != "FUNCTION_PARAMETER_BOUNDARY":
                continue

            primitive = str(trace_item["primitive"])

            parameter = str(step.get("parameter") or "")

            key = (
                primitive,
                parameter,
            )

            if key not in grouped:
                grouped[key] = {
                    "primitive": primitive,
                    "parameter": parameter,
                    "candidate_ids": set(),
                    "source_ids": set(),
                    "call_shapes": [],
                    "occurrences": 0,
                }

            item = grouped[key]

            item["candidate_ids"].add(str(trace_item["candidate_id"]))

            item["source_ids"].add(str(trace_item["source_id"]))

            item["occurrences"] += 1

            call_shape = step.get("call_shape")

            if (
                isinstance(
                    call_shape,
                    dict,
                )
                and call_shape not in item["call_shapes"]
            ):
                item["call_shapes"].append(call_shape)

    result: list[JsonDict] = []

    for item in grouped.values():
        result.append(
            {
                "primitive": item["primitive"],
                "parameter": item["parameter"],
                "candidate_ids": sorted(item["candidate_ids"]),
                "source_ids": sorted(item["source_ids"]),
                "call_shapes": item["call_shapes"],
                "occurrences": int(item["occurrences"]),
                "protocol_status": "UNRESOLVED",
                "semantic_contract_status": "MISSING",
                "resolution_status": "UNRESOLVED",
                "certification_claim": False,
            }
        )

    return sorted(
        result,
        key=lambda item: (
            -int(item["occurrences"]),
            str(item["primitive"]),
            str(item["parameter"]),
        ),
    )


def _local_contract_evidence(
    traces: list[JsonDict],
) -> list[JsonDict]:

    records: list[JsonDict] = []

    for trace_item in traces:
        for step in _terminal_steps(trace_item):
            if str(step.get("step_kind")) not in LOCAL_TERMINALS:
                continue

            records.append(
                {
                    "candidate_id": str(trace_item["candidate_id"]),
                    "source_id": str(trace_item["source_id"]),
                    "primitive": str(trace_item["primitive"]),
                    "terminal_kind": str(step["step_kind"]),
                    "file": step.get("file"),
                    "file_sha256": (step.get("file_sha256") or step.get("source_file_sha256")),
                    "line": step.get("line"),
                    "source": step.get("source"),
                    "semantic_type": "UNRESOLVED",
                    "semantic_contract_status": "MISSING",
                    "resolution_status": "UNRESOLVED",
                    "certification_claim": False,
                }
            )

    return records


def build_contract_readiness(
    *,
    symbol_summary_path: Path,
    contract_candidates_path: Path,
    occurrence_traces_path: Path,
    output_dir: Path,
) -> JsonDict:

    symbol_summary = _load_json(symbol_summary_path)

    if str(symbol_summary["cohort_sha256"]) != EXPECTED_COHORT_SHA256:
        raise ValueError("symbol trace cohort digest mismatch")

    contract_data = _load_json(contract_candidates_path)

    contract_candidates = contract_data["entries"]

    if len(contract_candidates) != EXPECTED_CONTRACT_CANDIDATES:
        raise ValueError(f"expected {EXPECTED_CONTRACT_CANDIDATES} contract candidates")

    traces = _load_jsonl(occurrence_traces_path)

    grouped: dict[
        tuple[
            str,
            str,
            str,
        ],
        list[JsonDict],
    ] = defaultdict(list)

    for trace_item in traces:
        key = (
            str(trace_item["family_class"]),
            str(trace_item["kind"]),
            str(trace_item["primitive"]),
        )

        grouped[key].append(trace_item)

    queue: list[JsonDict] = []

    for candidate in contract_candidates:
        key = (
            str(candidate["family_class"]),
            str(candidate["kind"]),
            str(candidate["primitive"]),
        )

        related = grouped.get(
            key,
            [],
        )

        terminals = {str(item["terminal_status"]) for item in related}

        action = _action_for_terminals(terminals)

        queue.append(
            {
                "registry_id": str(candidate["registry_id"]),
                "family_class": str(candidate["family_class"]),
                "kind": str(candidate["kind"]),
                "primitive": str(candidate["primitive"]),
                "candidate_count": int(candidate["candidate_count"]),
                "occurrence_count": int(candidate["occurrence_count"]),
                "terminal_statuses": sorted(terminals),
                "action": action,
                "semantic_type": "UNRESOLVED",
                "semantic_contract_status": "MISSING",
                "resolution_status": "UNRESOLVED",
                "certification_claim": False,
            }
        )

    queue.sort(
        key=lambda item: (
            str(item["action"]),
            -int(item["candidate_count"]),
            -int(item["occurrence_count"]),
            str(item["primitive"]),
        )
    )

    external_manifest = _external_boundaries(traces)

    parameter_protocols = _parameter_protocols(traces)

    local_contracts = _local_contract_evidence(traces)

    action_counts = Counter(str(item["action"]) for item in queue)

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "CONTRACT_READINESS_AND_DEPENDENCY_MANIFEST",
        "cohort_sha256": EXPECTED_COHORT_SHA256,
        "contract_candidates": len(queue),
        "action_counts": dict(sorted(action_counts.items())),
        "external_dependency_targets": len(external_manifest),
        "parameter_protocol_targets": len(parameter_protocols),
        "local_source_evidence_records": len(local_contracts),
        "semantic_types_resolved": 0,
        "semantic_contracts_validated": 0,
        "all_contracts_unresolved": all(
            item["resolution_status"] == "UNRESOLVED" for item in queue
        ),
        "certification_claim": False,
        "passed": (len(queue) == EXPECTED_CONTRACT_CANDIDATES),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_dir / "queue.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                sort_keys=True,
            )
            + "\n"
            for item in queue
        ),
        encoding="utf-8",
    )

    (output_dir / "external_dependencies.json").write_text(
        json.dumps(
            {
                "cohort_sha256": EXPECTED_COHORT_SHA256,
                "targets": external_manifest,
                "certification_claim": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "parameter_protocols.json").write_text(
        json.dumps(
            {
                "cohort_sha256": EXPECTED_COHORT_SHA256,
                "targets": parameter_protocols,
                "certification_claim": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "local_source_contracts.json").write_text(
        json.dumps(
            {
                "cohort_sha256": EXPECTED_COHORT_SHA256,
                "records": local_contracts,
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
        "# BIZPROOF V0.11 Contract Readiness",
        "",
        ("This phase converts source-trace outcomes into explicit contract-authoring actions."),
        "",
        ("No semantic type or semantic contract is resolved by this classification."),
        "",
        (f"- Contract candidates: {len(queue)}"),
        (f"- External dependency targets: {len(external_manifest)}"),
        (f"- Parameter protocol targets: {len(parameter_protocols)}"),
        (f"- Local source evidence records: {len(local_contracts)}"),
        "",
        "## Action counts",
        "",
    ]

    for (
        action_name,
        value,
    ) in sorted(action_counts.items()):
        report.append(f"- `{action_name}`: {value}")

    report.extend(
        [
            "",
            "## Scientific boundary",
            "",
            (
                "Readiness actions are engineering classifications only. "
                "All semantic contracts and semantic types remain unresolved."
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
        "--symbol-summary",
        type=Path,
        default=Path("benchmarks/v0.11/symbol_trace/summary.json"),
    )

    parser.add_argument(
        "--contract-candidates",
        type=Path,
        default=Path("benchmarks/v0.11/symbol_trace/contract_candidates.json"),
    )

    parser.add_argument(
        "--occurrence-traces",
        type=Path,
        default=Path("benchmarks/v0.11/symbol_trace/occurrence_traces.jsonl"),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/contract_readiness"),
    )

    args = parser.parse_args()

    summary = build_contract_readiness(
        symbol_summary_path=args.symbol_summary,
        contract_candidates_path=args.contract_candidates,
        occurrence_traces_path=args.occurrence_traces,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 contract readiness")

    print(
        "Contract candidates:",
        summary["contract_candidates"],
    )

    print(
        "Actions:",
        summary["action_counts"],
    )

    print(
        "External dependency targets:",
        summary["external_dependency_targets"],
    )

    print(
        "Parameter protocol targets:",
        summary["parameter_protocol_targets"],
    )

    print("Semantic contracts validated: 0")

    print("Certification claim: NO")

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
