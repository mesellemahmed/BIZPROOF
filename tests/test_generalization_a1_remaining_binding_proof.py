from __future__ import annotations

import ast

import pytest
import z3

from bizproof.generalization_a1_batch_proof import (
    ProofUnsupported,
)
from bizproof.generalization_a1_remaining_binding_proof import (
    BindingAwareSourceCompiler,
    _validate_binding_semantics,
)


def test_declared_attribute_is_binding() -> None:

    expression = "TypesScolarite.enseignement_superieur"

    variable = z3.Real("enum_value")

    compiler = BindingAwareSourceCompiler({expression: variable})

    node = ast.parse(
        expression,
        mode="eval",
    ).body

    result = compiler.expression(node)

    assert z3.eq(
        result,
        variable,
    )

    assert expression in (compiler.used_bindings)


def test_declared_global_name_is_binding() -> None:

    variable = z3.Real("zero_discount")

    compiler = BindingAwareSourceCompiler({"ZERO_DISCOUNT": variable})

    node = ast.parse(
        "ZERO_DISCOUNT",
        mode="eval",
    ).body

    result = compiler.expression(node)

    assert z3.eq(
        result,
        variable,
    )


def test_declared_period_call_is_binding() -> None:

    expression = "periods.period('2021-10')"

    variable = z3.Real("period_value")

    compiler = BindingAwareSourceCompiler({expression: variable})

    node = ast.parse(
        expression,
        mode="eval",
    ).body

    result = compiler.expression(node)

    assert z3.eq(
        result,
        variable,
    )


def test_undeclared_attribute_remains_unsupported() -> None:

    compiler = BindingAwareSourceCompiler({})

    node = ast.parse(
        "TypesScolarite.enseignement_superieur",
        mode="eval",
    ).body

    with pytest.raises(ProofUnsupported):
        compiler.expression(node)


def test_validated_not_contract_is_accepted() -> None:

    required = [
        {
            "kind": "CALL",
            "primitive": "not_",
        }
    ]

    contracts = {
        "not_": "SC-NP-NOT-001",
    }

    result = _validate_binding_semantics(
        required,
        contracts,
    )

    assert result == {
        "not_": "SC-NP-NOT-001",
    }


def test_unvalidated_astype_is_rejected() -> None:

    required = [
        {
            "kind": "CALL",
            "primitive": "astype",
        }
    ]

    with pytest.raises(ProofUnsupported):
        _validate_binding_semantics(
            required,
            {},
        )
