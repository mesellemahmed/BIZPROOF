from __future__ import annotations

import importlib
from typing import Any


def _module() -> Any:
    return importlib.import_module("bizproof.generalization_workplan")


def _assessment(tier: str) -> dict[str, Any]:
    return {
        "candidate_id": "abc",
        "evidence_bucket": "NONE",
        "stratum": {
            "adaptation_complexity": "LOW",
        },
        "provenance": {
            "source_id": "source",
            "file": "rule.py",
            "enclosing_class": "Rule",
            "function": "check",
            "line_start": 1,
            "line_end": 2,
        },
        "feasibility": {
            "feasibility_tier": tier,
        },
    }


def _probe(
    status: str,
    binding_count: int,
) -> dict[str, Any]:
    return {
        "probe_status": status,
        "review_reason": "review",
        "binding_count": binding_count,
        "required_bindings": [],
    }


def test_f0_ready_without_bindings_is_direct() -> None:
    module = _module()

    item = module._route_candidate(
        _assessment("F0_DIRECT_SYMBOLIC"),
        _probe("SYMBOLIC_FRONTEND_READY", 0),
    )

    assert item["route"] == "AUTO_DIRECT_FORMALIZATION"


def test_f1_ready_routes_to_binding_definition() -> None:
    module = _module()

    item = module._route_candidate(
        _assessment("F1_DECLARATIVE_BINDING"),
        _probe("SYMBOLIC_FRONTEND_READY", 2),
    )

    assert item["route"] == "BINDING_DEFINITION"


def test_probe_review_routes_to_structural_review() -> None:
    module = _module()

    item = module._route_candidate(
        _assessment("F1_DECLARATIVE_BINDING"),
        _probe("STRUCTURAL_REVIEW", 0),
    )

    assert item["route"] == "STRUCTURAL_REVIEW"


def test_f2_routes_to_explicit_adapter() -> None:
    module = _module()

    item = module._route_candidate(
        _assessment("F2_EXPLICIT_ADAPTER"),
        None,
    )

    assert item["route"] == "EXPLICIT_ADAPTER"


def test_f3_routes_to_controlled_execution() -> None:
    module = _module()

    item = module._route_candidate(
        _assessment("F3_SEMANTIC_EXECUTION_REVIEW"),
        None,
    )

    assert item["route"] == "CONTROLLED_EXECUTION_REVIEW"
