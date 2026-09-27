from __future__ import annotations

import argparse
import importlib
import itertools
import json
from pathlib import Path
from typing import Any, TypeAlias

JsonDict: TypeAlias = dict[str, Any]

EXPECTED_OPENFISCA_CORE_VERSION = "44.0.4"

ALIAS_TARGETS = {
    "not_": "logical_not",
    "min_": "minimum",
    "where": "where",
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


def _normalise(
    value: Any,
) -> Any:

    if hasattr(
        value,
        "tolist",
    ):
        return value.tolist()

    if hasattr(
        value,
        "item",
    ):
        return value.item()

    return value


def _nb_enf_reference(
    ages: list[int],
    autonomy: list[bool],
    age_min: int,
    age_max: int,
) -> int:

    return sum(
        1
        for age, autonomous in zip(
            ages,
            autonomy,
            strict=True,
        )
        if (age >= age_min and age <= age_max and not autonomous)
    )


def _validate_numpy_aliases(
    *,
    phase_n_traces: JsonDict,
    numpy_lock: JsonDict,
) -> list[JsonDict]:

    numpy = importlib.import_module("numpy")

    runtime_version = str(numpy.__version__)

    expected_version = str(numpy_lock["version"])

    if runtime_version != expected_version:
        raise ValueError(f"NumPy runtime/lock mismatch: {runtime_version} != {expected_version}")

    symbols = phase_n_traces["symbols"]

    if not isinstance(
        symbols,
        list,
    ):
        raise ValueError("invalid OpenFisca symbol traces")

    by_symbol = {str(item["symbol"]): item for item in symbols}

    contracts: list[JsonDict] = []

    for (
        local_symbol,
        numpy_symbol,
    ) in ALIAS_TARGETS.items():
        item = by_symbol.get(local_symbol)

        if item is None:
            raise ValueError(f"missing trace for {local_symbol}")

        trace = item["trace"]

        steps = trace.get(
            "steps",
            [],
        )

        import_edges = [
            step
            for step in steps
            if (
                isinstance(
                    step,
                    dict,
                )
                and step.get("step_kind") == "IMPORT_EDGE"
                and step.get("target_module") == "numpy"
                and step.get("target_symbol") == numpy_symbol
            )
        ]

        if len(import_edges) != 1:
            raise ValueError(f"expected exactly one NumPy import edge for {local_symbol}")

        runtime_callable = getattr(
            numpy,
            numpy_symbol,
        )

        runtime_checks: list[JsonDict] = []

        expected: list[Any]

        if local_symbol == "not_":
            values = numpy.array(
                [
                    False,
                    True,
                    0,
                    1,
                    -2,
                ]
            )

            actual = runtime_callable(values)

            expected = [
                True,
                False,
                True,
                False,
                False,
            ]

            actual_value = _normalise(actual)

            if actual_value != expected:
                raise ValueError("logical_not runtime check failed")

            runtime_checks.append(
                {
                    "case": "boolean_and_numeric_truthiness",
                    "actual": actual_value,
                    "expected": expected,
                }
            )

        elif local_symbol == "min_":
            left = numpy.array(
                [
                    3,
                    -1,
                    5,
                ]
            )

            right = numpy.array(
                [
                    2,
                    4,
                    5,
                ]
            )

            actual = runtime_callable(
                left,
                right,
            )

            expected = [
                2,
                -1,
                5,
            ]

            actual_value = _normalise(actual)

            if actual_value != expected:
                raise ValueError("minimum runtime check failed")

            runtime_checks.append(
                {
                    "case": "elementwise_numeric_minimum",
                    "actual": actual_value,
                    "expected": expected,
                }
            )

        elif local_symbol == "where":
            condition = numpy.array(
                [
                    True,
                    False,
                    True,
                ]
            )

            when_true = numpy.array(
                [
                    1,
                    2,
                    3,
                ]
            )

            when_false = numpy.array(
                [
                    9,
                    8,
                    7,
                ]
            )

            actual = runtime_callable(
                condition,
                when_true,
                when_false,
            )

            expected = [
                1,
                8,
                3,
            ]

            actual_value = _normalise(actual)

            if actual_value != expected:
                raise ValueError("where runtime check failed")

            runtime_checks.append(
                {
                    "case": "elementwise_selection",
                    "actual": actual_value,
                    "expected": expected,
                }
            )

        contracts.append(
            {
                "contract_id": (
                    "SC-NP-NOT-001"
                    if local_symbol == "not_"
                    else ("SC-NP-MIN-001" if local_symbol == "min_" else "SC-NP-WHERE-001")
                ),
                "primitive": local_symbol,
                "semantic_definition": (f"Exact source-level alias to numpy.{numpy_symbol}"),
                "openfisca_core_version": EXPECTED_OPENFISCA_CORE_VERSION,
                "numpy_version": runtime_version,
                "numpy_symbol": numpy_symbol,
                "runtime_callable_type": type(runtime_callable).__name__,
                "import_edge": import_edges[0],
                "runtime_checks": runtime_checks,
                "semantic_contract_status": "VALIDATED_DELEGATED_LOCKED_RUNTIME",
                "candidate_certification": False,
                "certification_claim": False,
            }
        )

    return contracts


def _validate_nb_enf(
    *,
    nb_enf_resolution: JsonDict,
    numpy_lock: JsonDict,
) -> JsonDict:

    numpy = importlib.import_module("numpy")

    if str(numpy.__version__) != str(numpy_lock["version"]):
        raise ValueError("NumPy runtime mismatch in nb_enf validation")

    if nb_enf_resolution["definition_kind"] != "FUNCTION":
        raise ValueError("nb_enf is not a function")

    source = str(nb_enf_resolution["definition_source"])

    class Famille:
        ENFANT = "ENFANT"

    class Period:
        def __init__(
            self,
            unit: str,
            size: int,
        ) -> None:

            self.unit = unit
            self.size = size

    class FakeFamily:
        def __init__(
            self,
            ages: list[int],
            autonomy: list[bool],
        ) -> None:

            self._ages = ages
            self._autonomy = autonomy

        def members(
            self,
            variable: str,
            period: Period,
        ) -> Any:

            _ = period

            if variable == "age":
                return numpy.array(
                    self._ages,
                    dtype=int,
                )

            if variable == "autonomie_financiere":
                return numpy.array(
                    self._autonomy,
                    dtype=bool,
                )

            raise KeyError(variable)

        def sum(
            self,
            values: Any,
            *,
            role: str,
        ) -> int:

            if role != Famille.ENFANT:
                raise AssertionError("unexpected role")

            return int(numpy.sum(values))

    namespace: dict[
        str,
        Any,
    ] = {
        "not_": numpy.logical_not,
        "Famille": Famille,
    }

    exec(
        compile(
            source,
            "<locked-nb_enf>",
            "exec",
        ),
        namespace,
    )

    function = namespace.get("nb_enf")

    if not callable(function):
        raise ValueError("compiled nb_enf is not callable")

    child_states = list(
        itertools.product(
            [
                -1,
                0,
                1,
                2,
            ],
            [
                False,
                True,
            ],
        )
    )

    age_min_values = [
        -1,
        0,
        1,
    ]

    age_max_values = [
        0,
        1,
        2,
    ]

    comparisons = 0

    for length in (
        0,
        1,
        2,
    ):
        for children in itertools.product(
            child_states,
            repeat=length,
        ):
            ages = [int(item[0]) for item in children]

            autonomy = [bool(item[1]) for item in children]

            for age_min in age_min_values:
                for age_max in age_max_values:
                    family = FakeFamily(
                        ages,
                        autonomy,
                    )

                    actual = int(
                        function(
                            family,
                            Period(
                                "month",
                                1,
                            ),
                            age_min,
                            age_max,
                        )
                    )

                    expected = _nb_enf_reference(
                        ages,
                        autonomy,
                        age_min,
                        age_max,
                    )

                    if actual != expected:
                        raise ValueError(
                            "nb_enf mismatch: "
                            f"ages={ages}, "
                            f"autonomy={autonomy}, "
                            f"min={age_min}, "
                            f"max={age_max}, "
                            f"actual={actual}, "
                            f"expected={expected}"
                        )

                    comparisons += 1

    assertion_checks = 0

    invalid_periods = [
        Period(
            "year",
            1,
        ),
        Period(
            "month",
            2,
        ),
    ]

    for period in invalid_periods:
        try:
            function(
                FakeFamily(
                    [
                        1,
                    ],
                    [
                        False,
                    ],
                ),
                period,
                0,
                2,
            )

        except AssertionError:
            assertion_checks += 1

        else:
            raise ValueError("nb_enf period precondition did not reject invalid period")

    expected_comparisons = (
        sum(
            len(child_states) ** length
            for length in (
                0,
                1,
                2,
            )
        )
        * len(age_min_values)
        * len(age_max_values)
    )

    if comparisons != expected_comparisons:
        raise ValueError("unexpected nb_enf comparison count")

    return {
        "contract_id": "SC-NB-ENF-001",
        "primitive": "nb_enf",
        "source_file": nb_enf_resolution["resolved_definition_file"],
        "source_line": nb_enf_resolution["resolved_definition_line"],
        "source_sha256": nb_enf_resolution["source_sha256"],
        "definition_sha256": nb_enf_resolution["definition_sha256"],
        "numpy_version": str(numpy.__version__),
        "semantic_definition": (
            "For a monthly period of size 1, "
            "return the number of Famille.ENFANT "
            "members whose age is within "
            "[age_min, age_max] and whose "
            "autonomie_financiere is logically false."
        ),
        "period_precondition": {
            "unit": "month",
            "size": 1,
        },
        "member_queries": [
            "age",
            "autonomie_financiere",
        ],
        "aggregation_role": "Famille.ENFANT",
        "validation_domain": {
            "child_count": [
                0,
                1,
                2,
            ],
            "age_values": [
                -1,
                0,
                1,
                2,
            ],
            "autonomie_financiere": [
                False,
                True,
            ],
            "age_min": age_min_values,
            "age_max": age_max_values,
        },
        "exhaustive_comparisons": comparisons,
        "period_assertion_checks": assertion_checks,
        "semantic_contract_status": "VALIDATED_BOUNDED_EXHAUSTIVE",
        "candidate_certification": False,
        "certification_claim": False,
    }


def build_closure(
    *,
    phase_n_root: Path,
    numpy_lock_path: Path,
    output_dir: Path,
) -> JsonDict:

    phase_n_summary = _load_json(phase_n_root / "summary.json")

    if int(phase_n_summary["semantic_contracts_validated"]) != 1:
        raise ValueError("Phase-N semantic-contract baseline changed")

    if str(phase_n_summary["openfisca_core_version"]) != EXPECTED_OPENFISCA_CORE_VERSION:
        raise ValueError("OpenFisca-Core baseline changed")

    phase_n_traces = _load_json(phase_n_root / "openfisca_core_traces.json")

    nb_enf_resolution = _load_json(phase_n_root / "nb_enf_resolution.json")

    numpy_lock = _load_json(numpy_lock_path)

    if numpy_lock["wheel_hash_verified"] is not True:
        raise ValueError("NumPy wheel hash has not been verified")

    aliases = _validate_numpy_aliases(
        phase_n_traces=phase_n_traces,
        numpy_lock=numpy_lock,
    )

    nb_enf = _validate_nb_enf(
        nb_enf_resolution=nb_enf_resolution,
        numpy_lock=numpy_lock,
    )

    new_contracts = aliases + [
        nb_enf,
    ]

    new_ids = [str(item["contract_id"]) for item in new_contracts]

    expected_ids = {
        "SC-NP-NOT-001",
        "SC-NP-MIN-001",
        "SC-NP-WHERE-001",
        "SC-NB-ENF-001",
    }

    if set(new_ids) != expected_ids:
        raise ValueError("unexpected Phase-O contract IDs")

    summary: JsonDict = {
        "benchmark_version": "0.11.0",
        "phase": "SEMANTIC_CONTRACT_CLOSURE",
        "phase_n_semantic_contracts": 1,
        "new_semantic_contracts_validated": 4,
        "cumulative_semantic_contracts_validated": 5,
        "new_contract_ids": sorted(new_ids),
        "numpy_alias_contracts_validated": len(aliases),
        "numpy_version": str(numpy_lock["version"]),
        "numpy_wheel_sha256": str(numpy_lock["wheel_sha256"]),
        "nb_enf_contract_status": str(nb_enf["semantic_contract_status"]),
        "nb_enf_exhaustive_comparisons": int(nb_enf["exhaustive_comparisons"]),
        "candidate_certifications_issued": 0,
        "terminal_outcomes_assigned": 0,
        "certification_claim": False,
        "passed": (len(aliases) == 3 and int(nb_enf["exhaustive_comparisons"]) > 0),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_dir / "numpy_alias_contracts.json").write_text(
        json.dumps(
            {
                "contracts": aliases,
                "certification_claim": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "nb_enf_contract.json").write_text(
        json.dumps(
            nb_enf,
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

    (output_dir / "REVIEWER_REPORT.md").write_text(
        "\n".join(
            [
                ("# BIZPROOF V0.11 Semantic Contract Closure"),
                "",
                ("- Previous semantic contracts: 1"),
                ("- New semantic contracts: 4"),
                ("- Cumulative semantic contracts: 5"),
                ("- NumPy alias contracts: 3"),
                (
                    "- nb_enf bounded exhaustive contract: "
                    f"{nb_enf['exhaustive_comparisons']} comparisons"
                ),
                ("- Candidate certifications issued: 0"),
                ("- Terminal outcomes assigned: 0"),
                "",
                ("The nb_enf contract is explicitly bounded to its declared exhaustive domain."),
                "",
            ]
        ),
        encoding="utf-8",
    )

    return summary


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--phase-n-root",
        type=Path,
        default=Path("benchmarks/v0.11/semantic_contracts"),
    )

    parser.add_argument(
        "--numpy-lock",
        type=Path,
        default=Path("benchmarks/v0.11/semantic_contract_closure/numpy_lock.json"),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmarks/v0.11/semantic_contract_closure"),
    )

    args = parser.parse_args()

    summary = build_closure(
        phase_n_root=args.phase_n_root,
        numpy_lock_path=args.numpy_lock,
        output_dir=args.output_dir,
    )

    print("BIZPROOF V0.11 semantic contract closure")

    print(
        "New semantic contracts:",
        summary["new_semantic_contracts_validated"],
    )

    print(
        "Cumulative semantic contracts:",
        summary["cumulative_semantic_contracts_validated"],
    )

    print(
        "NumPy alias contracts:",
        summary["numpy_alias_contracts_validated"],
    )

    print(
        "NumPy version:",
        summary["numpy_version"],
    )

    print(
        "nb_enf comparisons:",
        summary["nb_enf_exhaustive_comparisons"],
    )

    print("Candidate certifications issued: 0")

    print("Terminal outcomes assigned: 0")

    print("PASS" if summary["passed"] else "FAIL")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
