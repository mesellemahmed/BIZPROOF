from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_name_resolution")


def test_src_layout_module_name() -> None:

    module = _module()

    name, is_package = module._module_name_from_relative("src/oscar/apps/offer/models.py")

    assert name == "oscar.apps.offer.models"

    assert is_package is False


def test_parameter_shadows_wildcard_import() -> None:

    module = _module()

    tree = ast.parse("from openfisca_core.model_api import *\n")

    occurrence = {
        "candidate_id": "candidate",
        "family_class": "OPENFISCA_ENTITY_LOOKUP",
        "kind": "CALL",
        "primitive": "foyer_fiscal",
        "source_id": "openfisca_france",
        "resolved_commit": "commit",
        "file": "openfisca_france/model/rule.py",
        "function": "formula",
        "source_expression": "foyer_fiscal('rfr', period)",
        "context_inferred_type": "NUMERIC",
    }

    result = module._resolve_occurrence(
        occurrence=occurrence,
        skeleton={
            "function_parameters": [
                "foyer_fiscal",
                "period",
            ],
        },
        source_root=Path("."),
        source_tree=tree,
    )

    assert result["resolution_status"] == "FUNCTION_PARAMETER_BOUNDARY"


def test_local_definition_after_wildcard_wins() -> None:

    module = _module()

    tree = ast.parse(
        "from openfisca_core.model_api import *\n\ndef nb_enf(value):\n    return value\n"
    )

    result = module._resolve_module_symbol(
        tree=tree,
        source_root=Path("."),
        module_name="pkg.rule",
        is_package=False,
        symbol="nb_enf",
    )

    assert result["resolution_status"] == "LOCAL_DEFINITION"


def test_wildcard_after_local_binding_is_conservative() -> None:

    module = _module()

    tree = ast.parse("def helper():\n    return 1\n\nfrom thirdparty.api import *\n")

    result = module._resolve_module_symbol(
        tree=tree,
        source_root=Path("."),
        module_name="pkg.rule",
        is_package=False,
        symbol="helper",
    )

    assert result["resolution_status"] == "WILDCARD_IMPORT_BOUNDARY"


def test_parameter_method_call_keeps_receiver() -> None:

    module = _module()

    tree = ast.parse("")

    occurrence = {
        "candidate_id": "candidate",
        "family_class": "EXTERNAL_CALL",
        "kind": "CALL",
        "primitive": "astype",
        "source_id": "openfisca_france",
        "resolved_commit": "commit",
        "file": "openfisca_france/model/rule.py",
        "function": "formula",
        "source_expression": "value.astype(bool)",
        "context_inferred_type": "ANY",
    }

    result = module._resolve_occurrence(
        occurrence=occurrence,
        skeleton={
            "function_parameters": [
                "value",
            ],
        },
        source_root=Path("."),
        source_tree=tree,
    )

    assert result["resolution_status"] == "PARAMETER_METHOD_BOUNDARY"

    assert result["authoritative_binding"]["receiver"] == "value"


def test_builtin_fallback() -> None:

    module = _module()

    result = module._resolve_module_symbol(
        tree=ast.parse(""),
        source_root=Path("."),
        module_name="pkg.rule",
        is_package=False,
        symbol="sum",
    )

    assert result["resolution_status"] == "PYTHON_BUILTIN_BOUNDARY"
