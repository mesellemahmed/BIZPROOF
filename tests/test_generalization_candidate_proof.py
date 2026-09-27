from __future__ import annotations

import importlib
from typing import Any

import pytest


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_candidate_proof")


def test_constant_decimal_method_shape() -> None:

    module = _module()

    source = (
        "class AbstractBenefit:\n"
        "    def shipping_discount("
        "self, charge, currency=None):\n"
        "        return D('0.00')\n"
    )

    function = module._find_method(
        source,
        class_name="AbstractBenefit",
        function_name="shipping_discount",
    )

    result = module._validate_constant_decimal_method(function)

    assert result["semantic_shape"] == "CONSTANT_DECIMAL_RETURN"

    assert result["literal"] == "0.00"


def test_wrong_decimal_literal_is_rejected() -> None:

    module = _module()

    source = (
        "class AbstractBenefit:\n"
        "    def shipping_discount("
        "self, charge, currency=None):\n"
        "        return D('0.01')\n"
    )

    function = module._find_method(
        source,
        class_name="AbstractBenefit",
        function_name="shipping_discount",
    )

    with pytest.raises(ValueError):
        module._validate_constant_decimal_method(function)


def test_runtime_preservation() -> None:

    module = _module()

    source = "def shipping_discount(self, charge, currency=None):\n    return D('0.00')\n"

    result = module._runtime_preservation(source)

    assert result["comparisons"] == 18

    assert result["adapter_mismatches"] == 0

    assert result["mutant_mismatches"] == 18


def test_symbolic_constant_equivalence() -> None:

    module = _module()

    result = module._symbolic_constant_equivalence()

    assert result["correct_equivalence_proved"] is True

    assert result["mutant_disproved"] is True


def test_frontier_status_closed() -> None:

    module = _module()

    (
        status,
        structural,
        unresolved,
    ) = module._frontier_status(
        {
            "D",
        },
        validated_semantics={
            "D",
        },
        structural_protocols={
            "members",
        },
    )

    assert status == "PRIMITIVE_CONTRACTS_CLOSED"

    assert structural == []
    assert unresolved == []


def test_normalise_serialized_cohort_schema() -> None:

    module = _module()

    raw = {
        "candidate_id": "candidate",
        "source_id": "django_oscar",
        "relative_file": "src/example.py",
        "class_name": "Example",
        "function_name": "rule",
        "adaptation_complexity": "LOW",
        "evidence": "TEST_AND_DOC",
        "start_line": 10,
        "end_line": 12,
    }

    result = module._normalise_cohort_record(raw)

    assert result["source"] == "django_oscar"

    assert result["file"] == "src/example.py"

    assert result["class"] == "Example"

    assert result["function"] == "rule"

    assert result["complexity"] == "LOW"

    assert result["lines"] == [
        10,
        12,
    ]


def test_normalise_compact_cohort_schema() -> None:

    module = _module()

    raw = {
        "candidate_id": "candidate",
        "source": "django_oscar",
        "file": "src/example.py",
        "class": "Example",
        "function": "rule",
        "complexity": "LOW",
        "evidence": "TEST_ONLY",
        "lines": [
            20,
            21,
        ],
    }

    result = module._normalise_cohort_record(raw)

    assert result["source"] == "django_oscar"

    assert result["complexity"] == "LOW"

    assert result["lines"] == [
        20,
        21,
    ]


def test_normalise_nested_candidate_schema() -> None:

    module = _module()

    raw = {
        "candidate_id": "candidate",
        "source_id": "django_oscar",
        "adaptation_complexity": "LOW",
        "candidate": {
            "file": "src/example.py",
            "class": "Example",
            "function": "rule",
            "evidence": "DOC_ONLY",
            "lines": [
                30,
                31,
            ],
        },
    }

    result = module._normalise_cohort_record(raw)

    assert result["candidate_id"] == "candidate"

    assert result["source"] == "django_oscar"

    assert result["file"] == "src/example.py"

    assert result["lines"] == [
        30,
        31,
    ]


def test_normalise_exact_real_frozen_cohort_schema() -> None:

    module = _module()

    raw = {
        "candidate": {
            "adaptation_complexity": "LOW",
            "enclosing_class": "AbstractBenefit",
            "file": "src/oscar/apps/offer/abstract_models.py",
            "function": "shipping_discount",
            "line_end": 820,
            "line_start": 819,
            "source_id": "django_oscar",
        },
        "candidate_id": "aab5348ee173d6e3",
        "evidence_bucket": "TEST_AND_DOC",
        "selection_hash": "hash",
        "selection_rank_within_stratum": 5,
        "stratum": {
            "adaptation_complexity": "LOW",
            "source_id": "django_oscar",
        },
    }

    result = module._normalise_cohort_record(raw)

    assert result["candidate_id"] == "aab5348ee173d6e3"

    assert result["source"] == "django_oscar"

    assert result["file"] == "src/oscar/apps/offer/abstract_models.py"

    assert result["class"] == "AbstractBenefit"

    assert result["function"] == "shipping_discount"

    assert result["complexity"] == "LOW"

    assert result["evidence"] == "TEST_AND_DOC"

    assert result["lines"] == [
        819,
        820,
    ]

    assert result["_cohort_schema"]["nested_candidate"] is True

    assert result["_cohort_schema"]["class_alias"] == "enclosing_class"

    assert result["_cohort_schema"]["evidence_alias"] == "evidence_bucket"
