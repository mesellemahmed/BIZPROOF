from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_semantic_contract_batch")


def test_decimal_contract() -> None:

    module = _module()

    occurrence = {
        "candidate_id": "candidate",
        "source_id": "django_oscar",
        "file": "src/oscar/apps/offer/abstract_models.py",
        "function": "shipping_discount",
        "primitive": "D",
        "source_expression": "D('0.00')",
        "authoritative_binding": {
            "binding_kind": "EXPLICIT_IMPORT",
            "source": "from decimal import Decimal as D",
            "target_module": "decimal",
            "target_symbol": "Decimal",
        },
    }

    result = module._validate_decimal_contract(
        [
            occurrence,
        ]
    )

    assert result["semantic_contract_status"] == "VALIDATED"

    assert result["semantic_type"] == "decimal.Decimal"

    assert result["runtime_validation"]["exponent"] == -2


def test_local_class_binding_is_resolved(
    tmp_path: Path,
) -> None:

    module = _module()

    root = tmp_path / "source"

    file_path = root / "pkg" / "rule.py"

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path.write_text(
        "class nb_enf:\n    def formula(self):\n        return 1\n",
        encoding="utf-8",
    )

    occurrence = {
        "candidate_id": "candidate",
        "source_id": "source",
        "file": "pkg/rule.py",
        "primitive": "nb_enf",
        "authoritative_binding": {
            "binding_kind": "LOCAL_DEFINITION",
            "line": 1,
            "source": "class nb_enf:",
        },
    }

    result = module._resolve_local_binding(
        occurrence,
        tmp_path,
    )

    assert result["binding_resolution_status"] == "RESOLVED"

    assert result["definition_kind"] == "CLASS"

    assert result["methods"] == [
        "formula",
    ]


def test_src_layout_module_name() -> None:

    module = _module()

    assert (
        module._module_name_from_file("src/oscar/apps/offer/abstract_models.py")
        == "oscar.apps.offer.abstract_models"
    )


def test_traced_local_definition_can_live_outside_candidate_file(
    tmp_path: Path,
) -> None:

    module = _module()

    candidate_file = tmp_path / "openfisca_france" / "model" / "candidate.py"

    definition_file = tmp_path / "openfisca_france" / "model" / "base_ressource.py"

    candidate_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    candidate_file.write_text(
        "def formula():\n    return nb_enf(None, None, 0, 1)\n",
        encoding="utf-8",
    )

    definition_source = (
        "\ndef nb_enf(famille, period, age_min, age_max):\n    return age_max - age_min\n"
    )

    definition_file.write_text(
        definition_source,
        encoding="utf-8",
    )

    import hashlib

    evidence = {
        "candidate_id": "candidate",
        "primitive": "nb_enf",
        "source_id": "openfisca_france",
        "file": "model/base_ressource.py",
        "line": 2,
        "file_sha256": hashlib.sha256(definition_file.read_bytes()).hexdigest(),
        "source": ("def nb_enf(famille, period, age_min, age_max):"),
        "terminal_kind": "LOCAL_DEFINITION",
    }

    occurrence = {
        "candidate_id": "candidate",
        "source_id": "openfisca_france",
        "file": "model/candidate.py",
        "primitive": "nb_enf",
        "authoritative_binding": {
            "binding_kind": "LOCAL_DEFINITION",
            "line": 1,
            "source": "incorrect occurrence-local evidence",
        },
    }

    result = module._resolve_local_binding(
        occurrence,
        tmp_path,
        source_evidence=evidence,
    )

    assert result["binding_resolution_status"] == "RESOLVED"

    assert result["definition_kind"] == "FUNCTION"

    assert result["resolved_definition_file"] == "model/base_ressource.py"

    assert result["candidate_file"] == "model/candidate.py"

    assert result["provenance_basis"] == "PHASE_I_SOURCE_SYMBOL_TRACE"

    assert result["parameters"] == [
        "famille",
        "period",
        "age_min",
        "age_max",
    ]
