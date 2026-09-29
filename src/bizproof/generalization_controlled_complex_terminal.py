from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .generalization_controlled_complex_closure import TARGETS
from .generalization_controlled_state_closure import (
    _digest,
    _load_jsonl,
)

JsonDict = dict[str, Any]


CLOSE_UNSUPPORTED = {
    "03e2adf4e4f323b1",
    "63e7979762bf860b",
    "7460029971aad8de",
    "882c5eae0d8fd4ec",
    "8a754dadf1672d0a",
    "a79d9687185720aa",
    "bcb091a940a8d0dd",
}


A2_FOLLOWUP = {
    "1a2de6edb11465fe",
    "3fd2d8b8a76b4834",
}


def _write_jsonl(
    path: Path,
    rows: list[JsonDict],
) -> None:
    path.write_text(
        "".join(
            json.dumps(
                row,
                sort_keys=True,
                default=str,
            )
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _validate_partition() -> None:
    if CLOSE_UNSUPPORTED & A2_FOLLOWUP:
        raise ValueError("W8-E semantic sets overlap")

    if (CLOSE_UNSUPPORTED | A2_FOLLOWUP) != set(TARGETS):
        raise ValueError("W8-E partition must cover exactly 9 targets")


def build_evidence_only(
    *,
    repo_root: Path,
    output_dir: Path,
) -> JsonDict:

    _validate_partition()

    probe_path = (
        repo_root / "benchmarks/v0.11/" / "controlled_complex_closure/" / "execution_probe.jsonl"
    )

    probe = _load_jsonl(probe_path)

    if len(probe) != 9:
        raise ValueError("expected 9 execution records")

    probe_by_id = {str(row["candidate_id"]): row for row in probe}

    if set(probe_by_id) != set(TARGETS):
        raise ValueError("execution probe mismatch")

    negatives: list[JsonDict] = []

    for candidate_id in sorted(CLOSE_UNSUPPORTED):
        manifest = TARGETS[candidate_id]

        execution = probe_by_id[candidate_id]

        if execution["execution_status"] != "ESTABLISHED" or execution["passed"] is not True:
            raise ValueError("execution evidence invalid: " + candidate_id)

        row: JsonDict = {
            "candidate_id": candidate_id,
            "terminal_outcome": "NOT_CERTIFIED_UNSUPPORTED",
            "reason_code": manifest["reason_code"],
            "controlled_execution_status": "ESTABLISHED",
            "execution_cases": execution["cases"],
            "execution_probe_digest": execution["execution_probe_digest"],
            "source": manifest["source"],
            "class": manifest["class"],
            "function": manifest["function"],
            "function_sha256": execution["function_sha256"],
            "interpretation": (
                "Controlled execution is established, "
                "but certification is withheld because "
                "the required mutable framework, object, "
                "service, cache, signal, request, model, "
                "or collection semantics exceed the "
                "frozen V0.11 formal subset."
            ),
            "certification_claim": False,
        }

        row["negative_evidence_digest"] = _digest(dict(row))

        negatives.append(row)

    followup: list[JsonDict] = []

    for candidate_id in sorted(A2_FOLLOWUP):
        manifest = TARGETS[candidate_id]

        execution = probe_by_id[candidate_id]

        if execution["execution_status"] != "ESTABLISHED" or execution["passed"] is not True:
            raise ValueError("execution evidence invalid: " + candidate_id)

        row = {
            "candidate_id": candidate_id,
            "source": manifest["source"],
            "class": manifest["class"],
            "function": manifest["function"],
            "function_sha256": execution["function_sha256"],
            "controlled_execution_status": "ESTABLISHED",
            "execution_cases": execution["cases"],
            "execution_probe_digest": execution["execution_probe_digest"],
            "next_route": "EXPLICIT_ADAPTER_REVIEW",
            "status": "A2_REVIEW_REQUIRED",
            "terminal_outcome": None,
            "certification_claim": False,
        }

        row["followup_digest"] = _digest(dict(row))

        followup.append(row)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    negative_dir = output_dir / "negative_evidence"

    negative_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for row in negatives:
        (negative_dir / (row["candidate_id"] + ".json")).write_text(
            json.dumps(
                row,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    _write_jsonl(
        output_dir / "negative_outcomes.jsonl",
        negatives,
    )

    _write_jsonl(
        output_dir / "a2_followup_worklist.jsonl",
        followup,
    )

    summary: JsonDict = {
        "negative_outcomes": len(negatives),
        "a2_followup": len(followup),
        "negative_candidate_ids": sorted(CLOSE_UNSUPPORTED),
        "a2_candidate_ids": sorted(A2_FOLLOWUP),
        "ledger_modified": False,
        "passed": (len(negatives) == 7 and len(followup) == 2),
    }

    (output_dir / "evidence_only_summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return summary
