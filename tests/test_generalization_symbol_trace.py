from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_symbol_trace")


def test_local_reexport_trace(
    tmp_path: Path,
) -> None:

    module = _module()

    package = tmp_path / "pkg"

    package.mkdir()

    (package / "__init__.py").write_text(
        "from .base import helper\n",
        encoding="utf-8",
    )

    (package / "base.py").write_text(
        "def helper(value):\n    return value\n",
        encoding="utf-8",
    )

    result = module._trace_symbol(
        source_root=tmp_path,
        module_name="pkg",
        symbol="helper",
    )

    assert result["terminal_status"] == "LOCAL_DEFINITION"


def test_external_dependency_boundary(
    tmp_path: Path,
) -> None:

    module = _module()

    result = module._trace_symbol(
        source_root=tmp_path,
        module_name="thirdparty.api",
        symbol="helper",
    )

    assert result["terminal_status"] == "EXTERNAL_DEPENDENCY_BOUNDARY"


def test_local_assignment_trace(
    tmp_path: Path,
) -> None:

    module = _module()

    package = tmp_path / "pkg"

    package.mkdir()

    (package / "constants.py").write_text(
        "ZERO = 0\n",
        encoding="utf-8",
    )

    result = module._trace_symbol(
        source_root=tmp_path,
        module_name="pkg.constants",
        symbol="ZERO",
    )

    assert result["terminal_status"] == "LOCAL_ASSIGNMENT"


def test_function_parameter_boundary() -> None:

    module = _module()

    occurrence = {
        "candidate_id": "candidate",
        "family_class": "OPENFISCA_ENTITY_LOOKUP",
        "kind": "CALL",
        "primitive": "foyer_fiscal",
        "source_id": "openfisca_france",
        "resolved_commit": "commit",
        "file": "rule.py",
        "function": "formula",
        "source_expression": "foyer_fiscal('rfr', period)",
        "context_inferred_type": "NUMERIC",
        "evidence": [
            {
                "evidence_kind": "FUNCTION_PARAMETER_CALLABLE",
                "parameter": "foyer_fiscal",
            }
        ],
    }

    result = module._trace_occurrence(
        occurrence=occurrence,
        source_root=Path("."),
    )

    assert result["terminal_status"] == "FUNCTION_PARAMETER_BOUNDARY"

    assert result["semantic_type"] == "UNRESOLVED"


def test_no_semantic_resolution_from_trace(
    tmp_path: Path,
) -> None:

    module = _module()

    package = tmp_path / "pkg"

    package.mkdir()

    (package / "base.py").write_text(
        "def not_(value):\n    return not value\n",
        encoding="utf-8",
    )

    trace = module._trace_symbol(
        source_root=tmp_path,
        module_name="pkg.base",
        symbol="not_",
    )

    assert trace["terminal_status"] == "LOCAL_DEFINITION"
