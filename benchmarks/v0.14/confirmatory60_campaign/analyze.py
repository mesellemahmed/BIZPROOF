from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

JsonDict = dict[str, Any]


ALLOWED_OUTCOMES = {
    "CERTIFIED_A1",
    "CERTIFIED_A2",
    "UNSUPPORTED",
    "AMBIGUOUS",
    "INFRA_ERROR",
}


def _read_jsonl(
    path: Path,
) -> list[JsonDict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _wilson(
    successes: int,
    total: int,
    z: float,
) -> tuple[float, float]:
    if total <= 0:
        return (
            0.0,
            0.0,
        )

    p = successes / total

    denominator = 1.0 + z * z / total

    center = (p + z * z / (2.0 * total)) / denominator

    half = z * math.sqrt((p * (1.0 - p) / total) + (z * z / (4.0 * total * total))) / denominator

    return (
        max(
            0.0,
            center - half,
        ),
        min(
            1.0,
            center + half,
        ),
    )


def _validate(
    *,
    raw: list[JsonDict],
    case_map: list[JsonDict],
) -> None:
    if len(raw) != 60:
        raise RuntimeError(f"raw_count_mismatch:{len(raw)}")

    if len(case_map) != 60:
        raise RuntimeError(f"case_map_count_mismatch:{len(case_map)}")

    for index, (
        record,
        expected,
    ) in enumerate(
        zip(
            raw,
            case_map,
            strict=True,
        ),
        start=1,
    ):
        if int(record["evaluation_order"]) != index:
            raise RuntimeError("raw_evaluation_order_mismatch")

        for key in (
            "case_id",
            "project",
            "project_commit",
            "stratum",
            "source_sha256",
        ):
            if record.get(key) != expected.get(key):
                raise RuntimeError(f"raw_case_identity_mismatch:{index}:{key}")

        outcome = record.get("scientific_outcome")

        if outcome not in ALLOWED_OUTCOMES:
            raise RuntimeError(f"invalid_raw_outcome:{outcome!r}")


def _group_summary(
    records: list[JsonDict],
    z: float,
) -> JsonDict:
    total = len(records)

    outcomes = Counter(str(record["scientific_outcome"]) for record in records)

    a1 = outcomes["CERTIFIED_A1"]

    a2 = outcomes["CERTIFIED_A2"]

    certified = a1 + a2

    low, high = _wilson(
        certified,
        total,
        z,
    )

    a2_low, a2_high = _wilson(
        a2,
        total,
        z,
    )

    return {
        "total": total,
        "certified_a1": a1,
        "certified_a2": a2,
        "certified_total": certified,
        "unsupported": outcomes["UNSUPPORTED"],
        "ambiguous": outcomes["AMBIGUOUS"],
        "infra_error": outcomes["INFRA_ERROR"],
        "yield": (certified / total if total else 0.0),
        "yield_ci_low": low,
        "yield_ci_high": high,
        "a2_rate": (a2 / total if total else 0.0),
        "a2_ci_low": a2_low,
        "a2_ci_high": a2_high,
    }


def _write_csv(
    path: Path,
    rows: list[JsonDict],
    fields: list[str],
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            lineterminator="\n",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _self_test() -> None:
    z = 1.959963984540054

    zero_low, zero_high = _wilson(
        0,
        60,
        z,
    )

    full_low, full_high = _wilson(
        60,
        60,
        z,
    )

    middle_low, middle_high = _wilson(
        30,
        60,
        z,
    )

    assert zero_low == 0.0
    assert 0.0 < zero_high < 0.1

    assert 0.9 < full_low < 1.0
    assert math.isclose(
        full_high,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-15,
    )

    assert middle_low < 0.5 < middle_high

    print(
        "Wilson 0/60  =",
        zero_low,
        zero_high,
    )

    print(
        "Wilson 60/60 =",
        full_low,
        full_high,
    )

    print(
        "Wilson 30/60 =",
        middle_low,
        middle_high,
    )

    print("analyzer self-test = PASS")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--raw",
        type=Path,
    )

    parser.add_argument(
        "--case-map",
        type=Path,
    )

    parser.add_argument(
        "--plan",
        type=Path,
    )

    parser.add_argument(
        "--completeness",
        type=Path,
    )

    parser.add_argument(
        "--output",
        type=Path,
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return

    for name in (
        "raw",
        "case_map",
        "plan",
        "completeness",
        "output",
    ):
        if (
            getattr(
                args,
                name,
            )
            is None
        ):
            raise SystemExit(f"--{name.replace('_', '-')} is required")

    raw_path: Path = args.raw
    case_map_path: Path = args.case_map
    plan_path: Path = args.plan
    completeness_path: Path = args.completeness
    output: Path = args.output

    completeness = json.loads(completeness_path.read_text(encoding="utf-8"))

    if completeness.get("status") != "RAW_FROZEN":
        raise RuntimeError("analysis_requires_RAW_FROZEN")

    expected_raw_sha = str(completeness["raw_sha256"])

    import hashlib

    actual_raw_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    if actual_raw_sha != expected_raw_sha:
        raise RuntimeError("raw_sha256_mismatch")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    if plan["status"] != "FROZEN_BEFORE_OUTCOMES":
        raise RuntimeError("statistical_plan_not_frozen")

    if plan["denominator"] != 60:
        raise RuntimeError("invalid_plan_denominator")

    z = float(plan["confidence"]["z"])

    raw = _read_jsonl(raw_path)

    case_map = _read_jsonl(case_map_path)

    _validate(
        raw=raw,
        case_map=case_map,
    )

    overall = _group_summary(
        raw,
        z,
    )

    campaign_status = "COMPLETE" if overall["infra_error"] == 0 else "INCOMPLETE_INFRA"

    projects = sorted({str(record["project"]) for record in raw})

    strata = sorted({str(record["stratum"]) for record in raw})

    project_rows: list[JsonDict] = []

    project_yields: list[float] = []

    for project in projects:
        records = [record for record in raw if record["project"] == project]

        summary = _group_summary(
            records,
            z,
        )

        summary["project"] = project

        project_rows.append(summary)

        project_yields.append(float(summary["yield"]))

    stratum_rows: list[JsonDict] = []

    for stratum in strata:
        records = [record for record in raw if record["stratum"] == stratum]

        summary = _group_summary(
            records,
            z,
        )

        summary["stratum"] = stratum

        stratum_rows.append(summary)

    reasons = Counter(
        str(
            record.get(
                "reason_code",
                "NONE",
            )
        )
        for record in raw
        if record["scientific_outcome"]
        not in {
            "CERTIFIED_A1",
            "CERTIFIED_A2",
        }
    )

    formal_obligations = sum(
        int(
            record.get(
                "formal_obligation_count",
                0,
            )
        )
        for record in raw
    )

    a2_obligations = sum(
        int(
            record.get(
                "a2_obligation_count",
                0,
            )
        )
        for record in raw
    )

    hardened_active = sum(bool(record.get("hardened_osss_active")) for record in raw)

    hardened_certified = sum(
        bool(record.get("hardened_osss_active"))
        and record["scientific_outcome"]
        in {
            "CERTIFIED_A1",
            "CERTIFIED_A2",
        }
        for record in raw
    )

    runtime_values = [
        float(record["runtime_seconds"])
        for record in raw
        if isinstance(
            record.get("runtime_seconds"),
            (
                int,
                float,
            ),
        )
    ]

    summary = {
        "schema_version": "BIZPROOF-V0.14-CONFIRMATORY60-ANALYSIS-1",
        "campaign_status": campaign_status,
        "denominator": 60,
        **overall,
        "macro_project_yield": mean(project_yields),
        "formal_obligations": formal_obligations,
        "a2_obligations": a2_obligations,
        "hardened_osss_active": hardened_active,
        "hardened_osss_certified": hardened_certified,
        "runtime_role": "DESCRIPTIVE_ONLY",
        "runtime_observations": len(runtime_values),
        "runtime_mean_seconds": (mean(runtime_values) if runtime_values else None),
        "infra_errors_change_denominator": False,
        "weighted_external_estimate": False,
    }

    output.mkdir(
        parents=True,
        exist_ok=False,
    )

    (output / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    common_fields = [
        "total",
        "certified_a1",
        "certified_a2",
        "certified_total",
        "unsupported",
        "ambiguous",
        "infra_error",
        "yield",
        "yield_ci_low",
        "yield_ci_high",
        "a2_rate",
        "a2_ci_low",
        "a2_ci_high",
    ]

    _write_csv(
        output / "per_project.csv",
        project_rows,
        [
            "project",
            *common_fields,
        ],
    )

    _write_csv(
        output / "per_stratum.csv",
        stratum_rows,
        [
            "stratum",
            *common_fields,
        ],
    )

    _write_csv(
        output / "failure_taxonomy.csv",
        [
            {
                "reason_code": reason,
                "count": count,
            }
            for reason, count in reasons.most_common()
        ],
        [
            "reason_code",
            "count",
        ],
    )

    infra_records = [record for record in raw if record["scientific_outcome"] == "INFRA_ERROR"]

    _write_csv(
        output / "infra_error_cases.csv",
        [
            {
                "evaluation_order": record["evaluation_order"],
                "case_id": record["case_id"],
                "project": record["project"],
                "stratum": record["stratum"],
                "reason_code": record["reason_code"],
                "reason": record["reason"],
            }
            for record in infra_records
        ],
        [
            "evaluation_order",
            "case_id",
            "project",
            "stratum",
            "reason_code",
            "reason",
        ],
    )

    percentage = 100.0 * float(summary["yield"])

    low = 100.0 * float(summary["yield_ci_low"])

    high = 100.0 * float(summary["yield_ci_high"])

    lines = [
        "# BIZPROOF V0.14 — Prospective Confirmatory-60",
        "",
        f"- Campaign status: `{campaign_status}`",
        "- Denominator: `60`",
        (f"- CERTIFIED_A1: `{summary['certified_a1']}`"),
        (f"- CERTIFIED_A2: `{summary['certified_a2']}`"),
        (f"- Certified total: `{summary['certified_total']}/60`"),
        (f"- Certification yield: `{percentage:.3f}%`"),
        (f"- Wilson 95% CI: `{low:.3f}% .. {high:.3f}%`"),
        (f"- Unsupported: `{summary['unsupported']}`"),
        (f"- Ambiguous: `{summary['ambiguous']}`"),
        (f"- Infra error: `{summary['infra_error']}`"),
        (f"- Formal obligations: `{formal_obligations}`"),
        (f"- Hardened OSSS active: `{hardened_active}`"),
        (f"- Hardened OSSS certified: `{hardened_certified}`"),
        "",
        (
            "Infrastructure errors, if any, remain "
            "separate from UNSUPPORTED and do not "
            "change the fixed denominator."
        ),
        "",
        ("Runtime measurements are descriptive only and are not part of the certification claim."),
        "",
    ]

    (output / "RESULTS.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
        newline="\n",
    )

    print("frozen analysis = EXECUTED")


if __name__ == "__main__":
    main()
