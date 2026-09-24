from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .expressions import ExpressionError, evaluate_boolean_expression
from .loader import TargetLoadError, load_function
from .model import BusinessContract


@dataclass(frozen=True)
class ReplayResult:
    valid: bool
    observed_result: Any | None = None
    postcondition_satisfied: bool | None = None
    reason_code: str | None = None
    reason: str | None = None


def replay_counterexample(
    contract: BusinessContract,
    inputs: dict[str, Any],
) -> ReplayResult:
    try:
        if not evaluate_boolean_expression(contract.precondition, inputs):
            return ReplayResult(
                valid=False,
                reason_code="replay_precondition_false",
                reason="symbolic counterexample does not satisfy the concrete precondition",
            )

        target = load_function(contract.target.source, contract.target.function)
        observed_result = target(**inputs)

        post_values = dict(inputs)
        post_values["result"] = observed_result
        postcondition_satisfied = evaluate_boolean_expression(
            contract.postcondition,
            post_values,
        )

        if postcondition_satisfied:
            return ReplayResult(
                valid=False,
                observed_result=observed_result,
                postcondition_satisfied=True,
                reason_code="replay_postcondition_true",
                reason="symbolic counterexample does not violate the concrete postcondition",
            )

        return ReplayResult(
            valid=True,
            observed_result=observed_result,
            postcondition_satisfied=False,
        )
    except TargetLoadError as exc:
        return ReplayResult(
            valid=False,
            reason_code="replay_target_load_error",
            reason=str(exc),
        )
    except ExpressionError as exc:
        return ReplayResult(
            valid=False,
            reason_code="replay_expression_error",
            reason=str(exc),
        )
    except Exception as exc:
        return ReplayResult(
            valid=False,
            reason_code="replay_target_execution_error",
            reason=f"target raised {type(exc).__name__}: {exc}",
        )
