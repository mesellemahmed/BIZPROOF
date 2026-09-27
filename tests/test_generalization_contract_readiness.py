from __future__ import annotations

import importlib
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_contract_readiness")


def test_local_source_action() -> None:

    module = _module()

    assert (
        module._action_for_terminals(
            {
                "LOCAL_ASSIGNMENT",
            }
        )
        == "LOCAL_SOURCE_CONTRACT_DRAFT"
    )


def test_parameter_protocol_action() -> None:

    module = _module()

    assert (
        module._action_for_terminals(
            {
                "FUNCTION_PARAMETER_BOUNDARY",
            }
        )
        == "PARAMETER_PROTOCOL_CONTRACT_DRAFT"
    )


def test_external_dependency_action() -> None:

    module = _module()

    assert (
        module._action_for_terminals(
            {
                "EXTERNAL_DEPENDENCY_BOUNDARY",
            }
        )
        == "EXTERNAL_DEPENDENCY_LOCK_REQUIRED"
    )


def test_mixed_trace_requires_review() -> None:

    module = _module()

    assert (
        module._action_for_terminals(
            {
                "FUNCTION_PARAMETER_BOUNDARY",
                "MIXED_TRACE_BOUNDARY",
            }
        )
        == "TRACE_REVIEW_REQUIRED"
    )


def test_external_manifest_grouping() -> None:

    module = _module()

    traces = [
        {
            "candidate_id": "candidate",
            "source_id": "openfisca_france",
            "primitive": "not_",
            "traces": [
                {
                    "steps": [
                        {
                            "step_kind": "EXTERNAL_DEPENDENCY_BOUNDARY",
                            "module": "openfisca_core.model_api",
                            "symbol": "not_",
                        }
                    ]
                }
            ],
        }
    ]

    result = module._external_boundaries(traces)

    assert len(result) == 1

    assert result[0]["package_root"] == "openfisca_core"

    assert result[0]["lock_status"] == "MISSING"
