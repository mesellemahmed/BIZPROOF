from __future__ import annotations

import importlib
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_semantic_contract_closure")


def test_nb_enf_reference() -> None:

    module = _module()

    assert (
        module._nb_enf_reference(
            [
                0,
                1,
                2,
                3,
            ],
            [
                False,
                True,
                False,
                False,
            ],
            0,
            2,
        )
        == 2
    )


def test_nb_enf_reference_empty() -> None:

    module = _module()

    assert (
        module._nb_enf_reference(
            [],
            [],
            0,
            2,
        )
        == 0
    )


def test_alias_targets_are_frozen() -> None:

    module = _module()

    assert module.ALIAS_TARGETS == {
        "not_": "logical_not",
        "min_": "minimum",
        "where": "where",
    }
