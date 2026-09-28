from __future__ import annotations

import importlib
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_remaining_cohort_sweep")


def test_semantic_ambiguity_ids_frozen() -> None:

    module = _module()

    assert module.SEMANTIC_AMBIGUITY_IDS == {
        "6c9c5d18966c42d0",
        "aa5b28186fcc7696",
    }


def test_semantic_ambiguity_shapes_frozen() -> None:

    module = _module()

    assert module.ALLOWED_AMBIGUITY_SHAPES == {
        "NONE_RETURN",
        "PASS_STUB",
    }


def test_distribution() -> None:

    module = _module()

    states = [
        {
            "state": "TERMINAL_ASSIGNED",
            "terminal_outcome": "CERTIFIED_A1",
        },
        {
            "state": "TERMINAL_ASSIGNED",
            "terminal_outcome": ("NOT_CERTIFIED_SEMANTIC_AMBIGUITY"),
        },
        {
            "state": "PENDING_UNASSIGNED",
            "terminal_outcome": None,
        },
    ]

    result = module._distribution(states)

    assert result["CERTIFIED_A1"] == 1

    assert result["NOT_CERTIFIED_SEMANTIC_AMBIGUITY"] == 1
