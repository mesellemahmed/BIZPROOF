from __future__ import annotations

import ast
import importlib
from typing import Any


def _module() -> Any:
    return importlib.import_module("bizproof.generalization_feasibility")


def _function(source: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_direct_symbolic_tier() -> None:
    module = _module()
    result = module._classify_function(
        _function("def rule(x, y):\n    value = x + y\n    return value > 0\n")
    )
    assert result["feasibility_tier"] == "F0_DIRECT_SYMBOLIC"


def test_declarative_binding_tier() -> None:
    module = _module()
    result = module._classify_function(
        _function(
            "def rule(entity, period):\n"
            "    value = entity('amount', period)\n"
            "    return value > 0\n"
        )
    )
    assert result["feasibility_tier"] == "F1_DECLARATIVE_BINDING"


def test_explicit_adapter_tier() -> None:
    module = _module()
    result = module._classify_function(_function("def rule(items):\n    return items[0] > 0\n"))
    assert result["feasibility_tier"] == "F2_EXPLICIT_ADAPTER"
    assert "Subscript" in result["adapter_blockers"]


def test_semantic_execution_review_tier() -> None:
    module = _module()
    result = module._classify_function(
        _function("def rule(order):\n    order.save()\n    return True\n")
    )
    assert result["feasibility_tier"] == "F3_SEMANTIC_EXECUTION_REVIEW"
    assert "MutatingCall" in result["hard_blockers"]


def test_weighted_estimates_sum_to_population() -> None:
    module = _module()

    assessments = []

    for (source, complexity), population_size in {
        ("a", "LOW"): 20,
        ("a", "HIGH"): 40,
    }.items():
        for index in range(10):
            tier = "F0_DIRECT_SYMBOLIC" if index < 5 else "F1_DECLARATIVE_BINDING"
            assessments.append(
                {
                    "stratum": {
                        "source_id": source,
                        "adaptation_complexity": complexity,
                        "population_size": population_size,
                    },
                    "feasibility": {
                        "feasibility_tier": tier,
                    },
                }
            )

    original_population = module.EXPECTED_ELIGIBLE_POPULATION
    module.EXPECTED_ELIGIBLE_POPULATION = 60

    try:
        left = module._weighted_estimate(
            assessments,
            "F0_DIRECT_SYMBOLIC",
        )
        right = module._weighted_estimate(
            assessments,
            "F1_DECLARATIVE_BINDING",
        )
    finally:
        module.EXPECTED_ELIGIBLE_POPULATION = original_population

    assert (
        abs(left["estimated_population_count"] + right["estimated_population_count"] - 60.0) < 1e-12
    )
    assert abs(left["estimated_rate"] + right["estimated_rate"] - 1.0) < 1e-12
