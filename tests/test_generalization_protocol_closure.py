from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_protocol_closure")


def test_function_protocol_signature() -> None:

    module = _module()

    signature = module._signature("foyer_fiscal('rfr', period)")

    assert signature.startswith("FUNCTION")

    assert "CONST_STR" in signature

    assert "NAME" in signature


def test_method_protocol_signature() -> None:

    module = _module()

    signature = module._signature("famille.members('ENF')")

    assert signature.startswith("METHOD:NAME")


def test_decimal_is_python_stdlib() -> None:

    assert "decimal" in sys.stdlib_module_names


def test_dependency_constraint_discovery(
    tmp_path: Path,
) -> None:

    module = _module()

    (tmp_path / "pyproject.toml").write_text(
        'openfisca-core = ">=43,<44"\n',
        encoding="utf-8",
    )

    evidence = module._manifest_evidence(
        tmp_path,
        "openfisca_core",
    )

    assert len(evidence) == 1

    assert evidence[0]["exact_pin_detected"] is False


def test_foyer_fiscal_split_action() -> None:

    module = _module()

    action = module._action(
        "foyer_fiscal",
        {
            "FUNCTION_PARAMETER_BOUNDARY",
            "PARAMETER_METHOD_BOUNDARY",
        },
        [],
        [],
    )

    assert action == "SPLIT_PROTOCOL_FAMILIES"


def test_local_definition_seed_survives_missing_body_rediscovery(
    tmp_path: Path,
) -> None:

    module = _module()

    resolutions = [
        {
            "candidate_id": "candidate",
            "source_id": "openfisca_france",
            "primitive": "nb_enf",
            "resolution_status": "LOCAL_DEFINITION",
            "file": "missing/source.py",
            "authoritative_binding": {
                "line": 123,
                "source": "def nb_enf(value):",
            },
        }
    ]

    result = module._local_analysis(
        resolutions,
        tmp_path,
    )

    assert len(result) == 1

    assert result[0]["resolution_status"] == "LOCAL_DEFINITION"

    assert result[0]["analysis_status"] == "LOCAL_DEFINITION_SEED"
