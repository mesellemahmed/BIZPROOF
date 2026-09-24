from __future__ import annotations

import itertools
import time
from collections.abc import Iterable
from typing import Any

from .expressions import ExpressionError, evaluate_boolean_expression
from .loader import TargetLoadError, load_function
from .model import BusinessContract, Evidence, InputSpec, Verdict


class EnumerationLimitError(RuntimeError):
    pass


def _domain(spec: InputSpec) -> Iterable[Any]:
    if spec.type_name == "bool":
        return (False, True)
    if spec.type_name == "int":
        assert spec.minimum is not None
        assert spec.maximum is not None
        return range(spec.minimum, spec.maximum + 1)
    raise ValueError(f"unsupported input type: {spec.type_name}")


def verify_by_enumeration(
    contract: BusinessContract,
    *,
    max_cases: int = 100_000,
) -> Evidence:
    started = time.perf_counter()

    try:
        target = load_function(contract.target.source, contract.target.function)
    except TargetLoadError as exc:
        return Evidence(
            verdict=Verdict.UNKNOWN,
            contract_id=contract.contract_id,
            backend="enum",
            reason_code="target_load_error",
            reason=str(exc),
        )

    domains = [_domain(spec) for spec in contract.inputs]
    checked = 0
    admissible = 0

    try:
        for combination in itertools.product(*domains):
            checked += 1
            if checked > max_cases:
                raise EnumerationLimitError(f"enumeration exceeded max_cases={max_cases}")

            values = {
                spec.name: value for spec, value in zip(contract.inputs, combination, strict=True)
            }

            if not evaluate_boolean_expression(contract.precondition, values):
                continue

            admissible += 1

            try:
                result = target(**values)
            except Exception as exc:
                elapsed = time.perf_counter() - started
                return Evidence(
                    verdict=Verdict.UNKNOWN,
                    contract_id=contract.contract_id,
                    backend="enum",
                    reason_code="target_execution_error",
                    reason=f"target raised {type(exc).__name__}: {exc}",
                    metadata={
                        "checked_cases": checked,
                        "admissible_cases": admissible,
                        "runtime_seconds": elapsed,
                        "witness_input": values,
                    },
                )

            post_values = dict(values)
            post_values["result"] = result
            postcondition_satisfied = evaluate_boolean_expression(
                contract.postcondition,
                post_values,
            )

            if not postcondition_satisfied:
                elapsed = time.perf_counter() - started
                return Evidence(
                    verdict=Verdict.DISPROVED,
                    contract_id=contract.contract_id,
                    backend="enum",
                    counterexample=values,
                    observed_result=result,
                    postcondition_satisfied=False,
                    replay_validated=True,
                    metadata={
                        "checked_cases": checked,
                        "admissible_cases": admissible,
                        "runtime_seconds": elapsed,
                    },
                )

    except (ExpressionError, EnumerationLimitError, ValueError) as exc:
        elapsed = time.perf_counter() - started
        return Evidence(
            verdict=Verdict.UNKNOWN,
            contract_id=contract.contract_id,
            backend="enum",
            reason_code="enumeration_error",
            reason=str(exc),
            metadata={
                "checked_cases": checked,
                "admissible_cases": admissible,
                "runtime_seconds": elapsed,
            },
        )

    elapsed = time.perf_counter() - started
    if admissible == 0:
        return Evidence(
            verdict=Verdict.UNKNOWN,
            contract_id=contract.contract_id,
            backend="enum",
            reason_code="unsatisfiable_precondition",
            reason="precondition admits no values in the declared input domain",
            metadata={
                "checked_cases": checked,
                "admissible_cases": admissible,
                "runtime_seconds": elapsed,
            },
        )

    return Evidence(
        verdict=Verdict.PROVED,
        contract_id=contract.contract_id,
        backend="enum",
        metadata={
            "checked_cases": checked,
            "admissible_cases": admissible,
            "runtime_seconds": elapsed,
        },
    )
