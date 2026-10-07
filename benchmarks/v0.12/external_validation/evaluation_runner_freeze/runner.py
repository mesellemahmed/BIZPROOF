from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path("benchmarks/v0.12/external_validation")

COHORT = ROOT / "cohort_freeze"

PROTOCOL = ROOT / "evaluation_protocol_freeze"

RUNNER = ROOT / "evaluation_runner_freeze"


def load_json(
    path: Path,
) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cases() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (COHORT / "selected_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify_case_bytes(
    row: dict[str, Any],
) -> None:
    path = COHORT / row["frozen_source_file"]

    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    if digest != row["source_sha256"]:
        raise RuntimeError(f"source hash mismatch: {row['case_id']}")


def verify_preflight() -> None:
    protocol = load_json(PROTOCOL / "protocol.json")

    order = load_json(PROTOCOL / "evaluation_order.json")

    assessment = load_json(RUNNER / "backend_assessment.json")

    cases = load_cases()

    if len(cases) != 120:
        raise RuntimeError("expected 120 frozen cases")

    if order["case_count"] != 120:
        raise RuntimeError("evaluation order is not 120")

    if protocol["primary_endpoints"]["certification_yield"]["denominator"] != 120:
        raise RuntimeError("primary denominator changed")

    if protocol["execution"]["case_substitution"] is not False:
        raise RuntimeError("case substitution unexpectedly enabled")

    for row in cases:
        verify_case_bytes(row)

    print("cases               = 120 / 120")

    print("source hashes       = 120 / 120 PASS")

    print("order               = FROZEN")

    print("denominator         = 120")

    print(
        "generic certifier   =",
        ("AVAILABLE" if assessment["generic_source_level_certifier_available"] else "NOT FOUND"),
    )

    print("external outcomes   = NONE")


def inspect() -> None:
    assessment = load_json(RUNNER / "backend_assessment.json")

    inventory = load_json(RUNNER / "backend_inventory.json")

    print(
        json.dumps(
            {
                "assessment": assessment,
                "inventory": inventory,
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "command",
        choices=[
            "preflight",
            "inspect",
        ],
    )

    args = parser.parse_args()

    if args.command == "preflight":
        verify_preflight()
        return

    if args.command == "inspect":
        inspect()
        return

    raise RuntimeError("unsupported command")


if __name__ == "__main__":
    main()
