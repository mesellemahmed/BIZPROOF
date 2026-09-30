from __future__ import annotations

import argparse
import csv
import importlib
import json
import tempfile
import time
from collections import Counter
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from hypothesis import Phase, find, settings
from hypothesis import strategies as st
from hypothesis.errors import NoSuchExample

from .baseline_comparison import _run_crosshair

ROOT = Path("benchmarks/v0.11/paper_baselines")

COMPATIBILITY = ROOT / "type_compatibility.jsonl"

FREEZE = ROOT / "baseline_freeze.json"


JsonDict = dict[
    str,
    Any,
]


def _load_jsonl(
    path: Path,
) -> list[JsonDict]:

    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _module_name(
    raw_path: str,
) -> str:

    normalized = raw_path.replace(
        "\\",
        "/",
    )

    path = Path(normalized)

    parts = list(path.with_suffix("").parts)

    if "src" not in parts:
        raise ValueError("adapter path is outside src: " + raw_path)

    index = parts.index("src")

    module_parts = parts[index + 1 :]

    return ".".join(module_parts)


def _function_pair(
    row: JsonDict,
) -> tuple[
    Callable[..., Any],
    Callable[..., Any],
    str,
    str,
    str,
]:

    adapter_defs = row["adapter_definitions"]

    mutant_defs = row["mutant_definitions"]

    if not (
        isinstance(
            adapter_defs,
            list,
        )
        and adapter_defs
        and isinstance(
            mutant_defs,
            list,
        )
        and mutant_defs
    ):
        raise ValueError("missing function definitions")

    adapter_def = adapter_defs[0]
    mutant_def = mutant_defs[0]

    adapter_path = str(adapter_def["path"])

    mutant_path = str(mutant_def["path"])

    adapter_module = _module_name(adapter_path)

    mutant_module = _module_name(mutant_path)

    adapter_name = str(row["adapter_names"][0])

    mutant_name = str(row["mutant_names"][0])

    a_module = importlib.import_module(adapter_module)

    m_module = importlib.import_module(mutant_module)

    adapter = getattr(
        a_module,
        adapter_name,
    )

    mutant = getattr(
        m_module,
        mutant_name,
    )

    return (
        adapter,
        mutant,
        adapter_module,
        adapter_name,
        mutant_name,
    )


def _strategy_for_annotation(
    annotation: str | None,
) -> st.SearchStrategy[Any]:

    if annotation is None:
        return st.integers(
            min_value=-100,
            max_value=100,
        )

    if annotation == "int":
        return st.integers(
            min_value=-100,
            max_value=100,
        )

    if annotation == "bool":
        return st.booleans()

    if annotation == "int | None":
        return st.one_of(
            st.none(),
            st.integers(
                min_value=-100,
                max_value=100,
            ),
        )

    if annotation == "bool | None":
        return st.one_of(
            st.none(),
            st.booleans(),
        )

    if annotation == ("tuple[bool, ...]"):
        return st.lists(
            st.booleans(),
            min_size=0,
            max_size=3,
        ).map(tuple)

    if annotation == ("tuple[int, ...]"):
        return st.lists(
            st.integers(
                min_value=-10,
                max_value=10,
            ),
            min_size=0,
            max_size=3,
        ).map(tuple)

    if annotation == ("tuple[int, int, int, int, int, int]"):
        return st.tuples(
            *[
                st.integers(
                    min_value=-10,
                    max_value=10,
                )
                for _ in range(6)
            ]
        )

    if annotation == "Decimal":
        return st.decimals(
            min_value=Decimal("-1000.00"),
            max_value=Decimal("1000.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )

    if annotation == "Decimal | None":
        return st.one_of(
            st.none(),
            st.decimals(
                min_value=Decimal("-1000.00"),
                max_value=Decimal("1000.00"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            ),
        )

    raise ValueError("unsupported primary annotation: " + annotation)


def _arguments(
    row: JsonDict,
) -> list[
    tuple[
        str,
        str | None,
    ]
]:

    definitions = row["adapter_definitions"]

    raw_args = definitions[0]["args"]

    result: list[
        tuple[
            str,
            str | None,
        ]
    ] = []

    for raw in raw_args:
        annotation = raw.get("annotation")

        result.append(
            (
                str(raw["name"]),
                (str(annotation) if annotation is not None else None),
            )
        )

    return result


def _strategy(
    row: JsonDict,
) -> st.SearchStrategy[
    dict[
        str,
        Any,
    ]
]:

    fields = {name: _strategy_for_annotation(annotation) for name, annotation in _arguments(row)}

    return st.fixed_dictionaries(fields)


def _safe_difference(
    adapter: Callable[..., Any],
    mutant: Callable[..., Any],
    values: dict[str, Any],
) -> bool:

    try:
        correct = adapter(**values)

    except Exception:
        # Outside the executable domain
        # of the frozen projection.
        return False

    try:
        altered = mutant(**values)

    except Exception:
        return True

    return bool(correct != altered)


def _jsonable(
    value: Any,
) -> Any:

    if isinstance(
        value,
        Decimal,
    ):
        return str(value)

    if isinstance(
        value,
        tuple,
    ):
        return [_jsonable(item) for item in value]

    if isinstance(
        value,
        frozenset,
    ):
        return sorted(str(item) for item in value)

    if isinstance(
        value,
        dict,
    ):
        return {str(key): _jsonable(child) for key, child in value.items()}

    if isinstance(
        value,
        list,
    ):
        return [_jsonable(child) for child in value]

    return value


def _run_hypothesis(
    row: JsonDict,
    *,
    budget: int,
) -> tuple[
    bool | None,
    dict[str, Any] | None,
    float,
    str | None,
]:

    adapter, mutant, _, _, _ = _function_pair(row)

    strategy = _strategy(row)

    config = settings(
        max_examples=budget,
        derandomize=True,
        database=None,
        deadline=None,
        phases=(
            Phase.generate,
            Phase.shrink,
        ),
    )

    started = time.perf_counter()

    try:
        witness = find(
            strategy,
            lambda values: _safe_difference(
                adapter,
                mutant,
                values,
            ),
            settings=config,
        )

        return (
            True,
            _jsonable(dict(witness)),
            time.perf_counter() - started,
            None,
        )

    except NoSuchExample:
        return (
            False,
            None,
            time.perf_counter() - started,
            None,
        )

    except Exception as exc:
        return (
            None,
            None,
            time.perf_counter() - started,
            (type(exc).__name__ + ": " + str(exc)),
        )


def _crosshair_preconditions(
    name: str,
    annotation: str | None,
) -> list[str]:

    if annotation is None:
        return [f"    assert -100 <= {name} <= 100"]

    if annotation == "int":
        return [f"    assert -100 <= {name} <= 100"]

    if annotation == "bool":
        return []

    if annotation == "int | None":
        return [
            f"    if {name} is not None:",
            f"        assert -100 <= {name} <= 100",
        ]

    if annotation == "bool | None":
        return []

    if annotation == "tuple[bool, ...]":
        return [f"    assert len({name}) <= 3"]

    if annotation == "tuple[int, ...]":
        return [
            f"    assert len({name}) <= 3",
            f"    for item in {name}:",
            "        assert -10 <= item <= 10",
        ]

    if annotation == ("tuple[int, int, int, int, int, int]"):
        checks: list[str] = []

        for index in range(6):
            checks.append(f"    assert -10 <= {name}[{index}] <= 10")

        return checks

    if annotation == "Decimal":
        return [(f"    assert Decimal('-1000.00') <= {name} <= Decimal('1000.00')")]

    if annotation == "Decimal | None":
        return [
            f"    if {name} is not None:",
            (f"        assert Decimal('-1000.00') <= {name} <= Decimal('1000.00')"),
        ]

    raise ValueError("unsupported CrossHair annotation: " + str(annotation))


def _crosshair_source(
    row: JsonDict,
    path: Path,
) -> None:

    (
        _,
        _,
        module_name,
        adapter_name,
        mutant_name,
    ) = _function_pair(row)

    args = _arguments(row)

    signature = ", ".join(
        (name if annotation is None else (name + ": " + annotation)) for name, annotation in args
    )

    call = ", ".join(name for name, _ in args)

    lines = [
        "from decimal import Decimal",
        (f"from {module_name} import {adapter_name}, {mutant_name}"),
        "",
        (f"def check_mutant({signature}) -> None:" if signature else "def check_mutant() -> None:"),
    ]

    preconditions: list[str] = []

    for name, annotation in args:
        preconditions.extend(
            _crosshair_preconditions(
                name,
                annotation,
            )
        )

    if preconditions:
        lines.extend(preconditions)

    adapter_call = f"{adapter_name}({call})" if call else f"{adapter_name}()"

    mutant_call = f"{mutant_name}({call})" if call else f"{mutant_name}()"

    lines.extend(
        [
            ("    observed = " + adapter_call),
            ("    altered = " + mutant_call),
            "    assert observed == altered",
            "",
        ]
    )

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _summary_for_budget(
    rows: list[JsonDict],
    *,
    tool: str,
    budget: str,
) -> JsonDict:

    selected = [row for row in rows if row["tool"] == tool and str(row["budget"]) == budget]

    detected = sum(row["detected"] is True for row in selected)

    missed = sum(row["detected"] is False for row in selected)

    unknown = sum(row["detected"] is None for row in selected)

    return {
        "cases": len(selected),
        "detected": detected,
        "missed": missed,
        "unknown_or_error": unknown,
        "detection_rate_over_all": (detected / len(selected) if selected else 0.0),
        "detection_rate_when_conclusive": (
            detected / (detected + missed) if (detected + missed) else 0.0
        ),
        "runtime_seconds": round(
            sum(float(row["runtime_seconds"]) for row in selected),
            6,
        ),
    }


def run(
    output: Path,
    details: Path,
) -> JsonDict:

    compatibility = _load_jsonl(COMPATIBILITY)

    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))

    primary_ids = set(freeze["primary_candidate_ids"])

    primary = [row for row in compatibility if row["candidate_id"] in primary_ids]

    expected_primary = int(freeze["primary_total"])
    if len(primary) != expected_primary:
        raise ValueError(
            f"primary candidate count mismatch: expected {expected_primary}, got {len(primary)}"
        )

    if not all(bool(row["correct_unsat"]) and bool(row["mutant_sat"]) for row in primary):
        raise ValueError("frozen BIZPROOF evidence incomplete")

    hypothesis_budgets = [int(value) for value in freeze["hypothesis_budgets"]]

    crosshair_budgets = [float(value) for value in freeze["crosshair_per_condition_budgets"]]

    result_rows: list[JsonDict] = []

    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="bizproof-v011-paper-") as raw_tmp:
        tmp = Path(raw_tmp)

        for row in primary:
            cid = str(row["candidate_id"])

            for budget in hypothesis_budgets:
                (
                    detected,
                    witness,
                    runtime,
                    error,
                ) = _run_hypothesis(
                    row,
                    budget=budget,
                )

                result_rows.append(
                    {
                        "candidate_id": cid,
                        "type_class": row["type_class"],
                        "tool": "hypothesis",
                        "budget": budget,
                        "detected": detected,
                        "runtime_seconds": round(
                            runtime,
                            6,
                        ),
                        "witness": witness,
                        "error": error,
                    }
                )

            crosshair_file = tmp / (cid + "_crosshair.py")

            _crosshair_source(
                row,
                crosshair_file,
            )

            for crosshair_budget in crosshair_budgets:
                (
                    detected,
                    runtime,
                    error,
                ) = _run_crosshair(
                    crosshair_file,
                    per_condition_timeout=crosshair_budget,
                    process_timeout=8.0,
                )

                result_rows.append(
                    {
                        "candidate_id": cid,
                        "type_class": row["type_class"],
                        "tool": "crosshair",
                        "crosshair_budget": crosshair_budget,
                        "detected": detected,
                        "runtime_seconds": round(
                            runtime,
                            6,
                        ),
                        "witness": None,
                        "error": error,
                    }
                )

    hypothesis_summary = {
        str(budget): _summary_for_budget(
            result_rows,
            tool="hypothesis",
            budget=str(budget),
        )
        for budget in hypothesis_budgets
    }

    crosshair_summary = {
        str(budget): _summary_for_budget(
            result_rows,
            tool="crosshair",
            budget=str(budget),
        )
        for budget in crosshair_budgets
    }

    type_counts = Counter(str(row["type_class"]) for row in primary)

    summary: JsonDict = {
        "schema_version": "BIZPROOF-V0.11-A2-MATCHED-BASELINE-1",
        "benchmark_scope": ("Frozen CERTIFIED_A2 projection mutation sensitivity."),
        "source_level_certification_comparison": False,
        "primary_candidates": len(primary),
        "candidate_ids": sorted(primary_ids),
        "type_distribution": dict(sorted(type_counts.items())),
        "bizproof_frozen": {
            "correct_equivalences_proved": len(primary),
            "mutants_disproved": len(primary),
            "mutant_detection_rate": 1.0,
            "evidence_source": ("Frozen V0.11 A2 symbolic certificates."),
        },
        "hypothesis_by_budget": hypothesis_summary,
        "crosshair_by_budget": crosshair_summary,
        "interpretation": {
            "bizproof": (
                "Formal source-equivalence and mutant-disproof evidence from frozen V0.11."
            ),
            "hypothesis": ("No counterexample within budget is inconclusive."),
            "crosshair": (
                "No reported counterexample "
                "within budget is inconclusive; "
                "timeouts/errors are separate."
            ),
            "runtime": (
                "Runtime values are descriptive "
                "only because the tools provide "
                "different guarantee levels."
            ),
        },
        "wall_runtime_seconds": round(
            time.perf_counter() - started,
            6,
        ),
    }

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    details.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "candidate_id",
        "type_class",
        "tool",
        "budget",
        "detected",
        "runtime_seconds",
        "witness",
        "error",
    ]

    with details.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )

        writer.writeheader()

        for row in result_rows:
            serialized = dict(row)

            serialized["witness"] = (
                json.dumps(
                    row["witness"],
                    sort_keys=True,
                )
                if row["witness"] is not None
                else ""
            )

            serialized["error"] = row["error"] or ""

            writer.writerow(serialized)

    return summary


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--details",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    summary = run(
        args.output,
        args.details,
    )

    print("Matched A2 baseline")

    print(
        "Primary candidates:",
        summary["primary_candidates"],
    )

    print()

    print("BIZPROOF frozen:")

    print(
        "  mutants disproved:",
        summary["bizproof_frozen"]["mutants_disproved"],
        "/",
        summary["primary_candidates"],
    )

    print()

    print("Hypothesis:")

    for budget, result in summary["hypothesis_by_budget"].items():
        print(
            "  budget=",
            budget,
            " detected=",
            result["detected"],
            "/",
            result["cases"],
            " unknown=",
            result["unknown_or_error"],
            sep="",
        )

    print()

    print("CrossHair:")

    for budget, result in summary["crosshair_by_budget"].items():
        print(
            "  budget=",
            budget,
            " detected=",
            result["detected"],
            "/",
            result["cases"],
            " unknown=",
            result["unknown_or_error"],
            sep="",
        )

    print()

    print("MATCHED BASELINE EXECUTION: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
