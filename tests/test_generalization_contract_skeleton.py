from __future__ import annotations

import importlib
from typing import Any


def _module() -> Any:
    return importlib.import_module("bizproof.generalization_contract_skeleton")


def test_global_binding_family_class() -> None:
    module = _module()

    binding = {
        "kind": "GLOBAL_NAME",
        "primitive": "ZERO_DISCOUNT",
        "source_expression": "ZERO_DISCOUNT",
    }

    assert module._binding_family_class(binding) == "GLOBAL_CONSTANT"


def test_openfisca_lookup_descriptor() -> None:
    module = _module()

    binding = {
        "kind": "CALL",
        "primitive": "foyer_fiscal",
        "source_expression": "foyer_fiscal('rfr', period)",
    }

    assert module._binding_family_class(binding) == "OPENFISCA_ENTITY_LOOKUP"

    descriptor = module._parse_call_descriptor(binding)

    assert descriptor is not None
    assert descriptor["openfisca_variable_name"] == "rfr"


def test_semantic_library_family_class() -> None:
    module = _module()

    binding = {
        "kind": "CALL",
        "primitive": "not_",
        "source_expression": "not_(x)",
    }

    assert module._binding_family_class(binding) == "SEMANTIC_LIBRARY_PRIMITIVE"


def test_boolean_requirement() -> None:
    module = _module()

    from collections import defaultdict

    values: dict[str, set[str]] = defaultdict(set)

    module._propagate_requirement(
        {
            "op": "not",
            "value": {
                "op": "binding",
                "binding_id": "b",
            },
        },
        module.TYPE_BOOL,
        values,
    )

    normalized = module._normalize_requirements(values["b"])

    assert normalized["inferred_type"] == module.TYPE_BOOL


def test_numeric_requirement() -> None:
    module = _module()

    from collections import defaultdict

    values: dict[str, set[str]] = defaultdict(set)

    module._propagate_requirement(
        {
            "op": "add",
            "left": {
                "op": "binding",
                "binding_id": "b",
            },
            "right": {
                "op": "const",
                "type": "int",
                "value": 1,
            },
        },
        module.TYPE_NUMERIC,
        values,
    )

    normalized = module._normalize_requirements(values["b"])

    assert normalized["inferred_type"] == module.TYPE_NUMERIC


def test_bool_numeric_conflict() -> None:
    module = _module()

    result = module._normalize_requirements(
        {
            module.TYPE_BOOL,
            module.TYPE_NUMERIC,
        }
    )

    assert result["conflict"] is True
    assert result["inferred_type"] == "CONFLICT"
