from __future__ import annotations

import ast
import importlib
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_semantic_evidence")


def test_explicit_import_evidence() -> None:

    module = _module()

    tree = ast.parse("from package import helper\n")

    evidence = module._module_import_evidence(
        tree,
        "helper",
    )

    assert any(item["evidence_kind"] == "EXPLICIT_IMPORT" for item in evidence)


def test_wildcard_import_evidence() -> None:

    module = _module()

    tree = ast.parse("from package import *\n")

    evidence = module._module_import_evidence(
        tree,
        "helper",
    )

    assert any(item["evidence_kind"] == "WILDCARD_IMPORT" for item in evidence)


def test_global_assignment_evidence() -> None:

    module = _module()

    tree = ast.parse("ZERO_DISCOUNT = 0\n")

    evidence = module._module_definition_evidence(
        tree,
        "ZERO_DISCOUNT",
    )

    assert any(item["evidence_kind"] == "MODULE_ASSIGNMENT" for item in evidence)


def test_parameter_callable_evidence() -> None:

    module = _module()

    tree = ast.parse("x = 1\n")

    obligation = {
        "binding_id": "b",
        "kind": "CALL",
        "primitive": "foyer_fiscal",
        "family_class": "OPENFISCA_ENTITY_LOOKUP",
        "source_expression": "foyer_fiscal('rfr', period)",
        "inferred_type": "NUMERIC",
        "type_requirements": [
            "NUMERIC",
        ],
    }

    skeleton = {
        "function_parameters": [
            "foyer_fiscal",
            "period",
        ],
    }

    result = module._occurrence_evidence(
        obligation=obligation,
        skeleton=skeleton,
        source_tree=tree,
    )

    assert any(
        item["evidence_kind"] == "FUNCTION_PARAMETER_CALLABLE" for item in result["evidence"]
    )


def test_context_type_is_not_semantic_type() -> None:

    module = _module()

    tree = ast.parse("from openfisca_core.model_api import *\n")

    obligation = {
        "binding_id": "n",
        "kind": "CALL",
        "primitive": "not_",
        "family_class": "SEMANTIC_LIBRARY_PRIMITIVE",
        "source_expression": "not_(x)",
        "inferred_type": "NUMERIC",
        "type_requirements": [
            "NUMERIC",
        ],
    }

    result = module._occurrence_evidence(
        obligation=obligation,
        skeleton={
            "function_parameters": [
                "x",
            ],
        },
        source_tree=tree,
    )

    assert result["context_inferred_type"] == "NUMERIC"

    assert result["semantic_type"] == "UNRESOLVED"

    assert result["semantic_contract_required"] is True
