from __future__ import annotations

import time
from typing import Any

import z3

from .expressions import ExpressionError
from .model import BusinessContract, Evidence, InputSpec, Verdict
from .python_symbolic import PythonSymbolicAnalyzer, SymbolicPath, UnsupportedProgram
from .replay import replay_counterexample
from .z3expr import Z3ExpressionCompiler


def _symbol(spec: InputSpec) -> z3.ExprRef:
    if spec.type_name == "int":
        return z3.Int(spec.name)
    if spec.type_name == "bool":
        return z3.Bool(spec.name)
    raise ValueError(f"unsupported input type: {spec.type_name}")


def _domain_constraints(
    contract: BusinessContract,
    symbols: dict[str, z3.ExprRef],
) -> list[z3.BoolRef]:
    """Build explicit domain constraints.

    Python ``int`` inputs are modeled as mathematical Z3 integers.

    When ``minimum`` and/or ``maximum`` are provided, those bounds are
    preserved exactly. When neither bound is supplied, no artificial
    finite bound is introduced.

    This is a backward-compatible extension of the V0.12 bounded-domain
    behavior for the V0.13 generic source-level certifier.
    """
    constraints: list[z3.BoolRef] = []

    for spec in contract.inputs:
        symbol = symbols[spec.name]

        if spec.type_name != "int":
            continue

        if spec.minimum is not None:
            constraints.append(symbol >= spec.minimum)

        if spec.maximum is not None:
            constraints.append(symbol <= spec.maximum)

    return constraints


def _model_value(model: z3.ModelRef, expression: z3.ExprRef) -> Any:
    value = model.eval(expression, model_completion=True)
    if z3.is_true(value):
        return True
    if z3.is_false(value):
        return False
    if z3.is_int_value(value):
        return value.as_long()
    return str(value)


def _unknown(
    contract: BusinessContract,
    started: float,
    *,
    reason_code: str,
    reason: str,
    timeout_ms: int,
    extra_metadata: dict[str, Any] | None = None,
) -> Evidence:
    metadata: dict[str, Any] = {
        "runtime_seconds": time.perf_counter() - started,
        "timeout_ms": timeout_ms,
        "z3_version": z3.get_version_string(),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return Evidence(
        verdict=Verdict.UNKNOWN,
        contract_id=contract.contract_id,
        backend="z3",
        reason_code=reason_code,
        reason=reason,
        metadata=metadata,
    )


def _check_precondition_satisfiable(
    domain_constraints: list[z3.BoolRef],
    precondition: z3.BoolRef,
    timeout_ms: int,
) -> tuple[z3.CheckSatResult, str | None]:
    solver = z3.Solver()
    solver.set(timeout=timeout_ms)
    solver.add(*domain_constraints)
    solver.add(precondition)
    result = solver.check()
    return result, solver.reason_unknown() if result == z3.unknown else None


def _check_path_coverage(
    domain_constraints: list[z3.BoolRef],
    precondition: z3.BoolRef,
    paths: list[SymbolicPath],
    timeout_ms: int,
) -> tuple[z3.CheckSatResult, z3.ModelRef | None, str | None]:
    solver = z3.Solver()
    solver.set(timeout=timeout_ms)
    solver.add(*domain_constraints)
    solver.add(precondition)
    solver.add(z3.Not(z3.Or(*[path.condition for path in paths])))
    result = solver.check()
    if result == z3.sat:
        return result, solver.model(), None
    if result == z3.unknown:
        return result, None, solver.reason_unknown()
    return result, None, None


def verify_with_z3(
    contract: BusinessContract,
    *,
    timeout_ms: int = 10_000,
) -> Evidence:
    started = time.perf_counter()
    symbols = {spec.name: _symbol(spec) for spec in contract.inputs}

    try:
        compiler = Z3ExpressionCompiler(symbols)
        precondition = compiler.compile_boolean_text(contract.precondition)
        domain_constraints = _domain_constraints(contract, symbols)

        pre_result, pre_reason = _check_precondition_satisfiable(
            domain_constraints,
            precondition,
            timeout_ms,
        )
        if pre_result == z3.unsat:
            return _unknown(
                contract,
                started,
                reason_code="unsatisfiable_precondition",
                reason="precondition admits no values in the declared input domain",
                timeout_ms=timeout_ms,
            )
        if pre_result == z3.unknown:
            return _unknown(
                contract,
                started,
                reason_code="precondition_solver_unknown",
                reason=f"solver returned unknown: {pre_reason}",
                timeout_ms=timeout_ms,
            )

        analyzer = PythonSymbolicAnalyzer(contract.target.source, contract.target.function)
        paths = analyzer.extract_paths(symbols)

        coverage_result, coverage_model, coverage_reason = _check_path_coverage(
            domain_constraints,
            precondition,
            paths,
            timeout_ms,
        )
        if coverage_result == z3.sat:
            witness = (
                {
                    spec.name: _model_value(coverage_model, symbols[spec.name])
                    for spec in contract.inputs
                }
                if coverage_model is not None
                else None
            )
            return _unknown(
                contract,
                started,
                reason_code="incomplete_symbolic_path_coverage",
                reason="symbolic paths do not cover the entire admissible business domain",
                timeout_ms=timeout_ms,
                extra_metadata={"coverage_witness": witness},
            )
        if coverage_result == z3.unknown:
            return _unknown(
                contract,
                started,
                reason_code="path_coverage_solver_unknown",
                reason=f"solver returned unknown while checking path coverage: {coverage_reason}",
                timeout_ms=timeout_ms,
            )

        for index, path in enumerate(paths):
            post_symbols = dict(symbols)
            post_symbols["result"] = path.result
            postcondition = Z3ExpressionCompiler(post_symbols).compile_boolean_text(
                contract.postcondition
            )

            solver = z3.Solver()
            solver.set(timeout=timeout_ms)
            solver.add(*domain_constraints)
            solver.add(precondition)
            solver.add(path.condition)
            solver.add(z3.Not(postcondition))

            result = solver.check()

            if result == z3.sat:
                model = solver.model()
                counterexample = {
                    spec.name: _model_value(model, symbols[spec.name]) for spec in contract.inputs
                }
                symbolic_observed = _model_value(model, path.result)
                replay = replay_counterexample(contract, counterexample)

                if not replay.valid:
                    return _unknown(
                        contract,
                        started,
                        reason_code=replay.reason_code or "counterexample_replay_failed",
                        reason=replay.reason or "counterexample replay failed",
                        timeout_ms=timeout_ms,
                        extra_metadata={
                            "path_index": index,
                            "path_count": len(paths),
                            "candidate_counterexample": counterexample,
                            "symbolic_observed_result": symbolic_observed,
                            "concrete_observed_result": replay.observed_result,
                        },
                    )

                if replay.observed_result != symbolic_observed:
                    return _unknown(
                        contract,
                        started,
                        reason_code="symbolic_concrete_result_mismatch",
                        reason="symbolic and concrete execution produced different results",
                        timeout_ms=timeout_ms,
                        extra_metadata={
                            "path_index": index,
                            "path_count": len(paths),
                            "candidate_counterexample": counterexample,
                            "symbolic_observed_result": symbolic_observed,
                            "concrete_observed_result": replay.observed_result,
                        },
                    )

                return Evidence(
                    verdict=Verdict.DISPROVED,
                    contract_id=contract.contract_id,
                    backend="z3",
                    counterexample=counterexample,
                    observed_result=replay.observed_result,
                    postcondition_satisfied=False,
                    replay_validated=True,
                    metadata={
                        "path_index": index,
                        "path_count": len(paths),
                        "runtime_seconds": time.perf_counter() - started,
                        "timeout_ms": timeout_ms,
                        "z3_version": z3.get_version_string(),
                    },
                )

            if result == z3.unknown:
                return _unknown(
                    contract,
                    started,
                    reason_code="verification_solver_unknown",
                    reason=f"solver returned unknown: {solver.reason_unknown()}",
                    timeout_ms=timeout_ms,
                    extra_metadata={
                        "path_index": index,
                        "path_count": len(paths),
                    },
                )

    except (ExpressionError, UnsupportedProgram, ValueError, z3.Z3Exception) as exc:
        return _unknown(
            contract,
            started,
            reason_code="unsupported_or_invalid_semantics",
            reason=str(exc),
            timeout_ms=timeout_ms,
        )
    except (OSError, SyntaxError) as exc:
        return _unknown(
            contract,
            started,
            reason_code="target_source_error",
            reason=str(exc),
            timeout_ms=timeout_ms,
        )

    return Evidence(
        verdict=Verdict.PROVED,
        contract_id=contract.contract_id,
        backend="z3",
        metadata={
            "path_count": len(paths),
            "runtime_seconds": time.perf_counter() - started,
            "timeout_ms": timeout_ms,
            "z3_version": z3.get_version_string(),
        },
    )
