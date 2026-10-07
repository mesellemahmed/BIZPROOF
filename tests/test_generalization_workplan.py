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
    *,
    status: str = "SYMBOLIC_FRONTEND_READY",
    binding_count: int = 0,
    semantic_shape: str = "SUBSTANTIVE_EXPRESSION",
) -> dict[str, Any]:
    return {
        "probe_status": status,
        "review_reason": "review",
        "binding_count": binding_count,
        "required_bindings": [],
        "semantic_shape": semantic_shape,
    }


def test_substantive_f0_without_bindings_is_direct() -> None:
    module = _module()

    item = module._route_candidate(
        _assessment("F0_DIRECT_SYMBOLIC"),
        _probe(),
    )

    assert item["route"] == "AUTO_DIRECT_FORMALIZATION"


def test_free_binding_routes_to_binding_definition() -> None:
    module = _module()

    item = module._route_candidate(
        _assessment("F0_DIRECT_SYMBOLIC"),
        _probe(binding_count=1),
    )

    assert item["route"] == "BINDING_DEFINITION"


def test_stub_routes_to_semantic_scope_review() -> None:
    module = _module()

    item = module._route_candidate(
        _assessment("F0_DIRECT_SYMBOLIC"),
        _probe(semantic_shape="PASS_STUB"),
    )

    assert item["route"] == "SEMANTIC_SCOPE_REVIEW"


def test_none_return_routes_to_semantic_scope_review() -> None:
    module = _module()

    item = module._route_candidate(
        _assessment("F0_DIRECT_SYMBOLIC"),
        _probe(semantic_shape="NONE_RETURN"),
    )

    assert item["route"] == "SEMANTIC_SCOPE_REVIEW"


def test_structural_failure_routes_to_review() -> None:
    module = _module()

    item = module._route_candidate(
        _assessment("F1_DECLARATIVE_BINDING"),
        _probe(status="STRUCTURAL_REVIEW"),
    )

    assert item["route"] == "STRUCTURAL_REVIEW"


def test_f2_and_f3_routes_are_preserved() -> None:
    module = _module()

    f2 = module._route_candidate(
        _assessment("F2_EXPLICIT_ADAPTER"),
        None,
    )
    f3 = module._route_candidate(
        _assessment("F3_SEMANTIC_EXECUTION_REVIEW"),
        None,
    )

    assert f2["route"] == "EXPLICIT_ADAPTER"
    assert f3["route"] == "CONTROLLED_EXECUTION_REVIEW"
