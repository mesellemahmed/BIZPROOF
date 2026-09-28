from __future__ import annotations

from bizproof.generalization_a2_v2_proof import (
    COMPLEX_SCALAR_REVIEW,
    NON_SCALAR_REVIEW,
    SCALAR_TARGETS,
    V2_IDS,
    adapt_housing_tax_exemption,
    adapt_locapass_student_contract,
    adapt_special_allowance,
)


def test_v2_partition() -> None:

    combined = set(SCALAR_TARGETS) | set(COMPLEX_SCALAR_REVIEW) | set(NON_SCALAR_REVIEW)

    assert combined == V2_IDS


def test_locapass_adapter() -> None:

    assert (
        adapt_locapass_student_contract(
            (
                1,
                1,
                1,
                0,
                0,
                0,
            )
        )
        is True
    )

    assert (
        adapt_locapass_student_contract(
            (
                1,
                1,
                0,
                0,
                0,
                0,
            )
        )
        is False
    )


def test_special_allowance_adapter() -> None:

    assert (
        adapt_special_allowance(
            70,
            False,
            0,
            False,
            100,
            0,
            80,
            0,
        )
        == 80
    )

    assert (
        adapt_special_allowance(
            70,
            False,
            70,
            False,
            100,
            0,
            80,
            0,
        )
        == 100
    )


def test_housing_tax_adapter() -> None:

    assert (
        adapt_housing_tax_exemption(
            70,
            50,
            False,
            0,
            0,
            0,
            0,
            True,
            60,
        )
        == 1
    )

    assert (
        adapt_housing_tax_exemption(
            70,
            50,
            False,
            0,
            0,
            0,
            0,
            False,
            60,
        )
        == 0
    )
