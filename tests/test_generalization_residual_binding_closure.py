from __future__ import annotations

from bizproof.generalization_residual_binding_closure import (
    MOBILITY_ID,
    RSA_ID,
    adapt_rsa_tns_turnover_eligibility,
    mutant_rsa_tns_turnover_eligibility,
)


def test_target_ids_are_distinct() -> None:

    assert RSA_ID != MOBILITY_ID


def test_purchase_resale_boundary() -> None:

    assert (
        adapt_rsa_tns_turnover_eligibility(
            100,
            True,
            False,
            False,
            100,
            50,
        )
        == 1
    )

    assert (
        mutant_rsa_tns_turnover_eligibility(
            100,
            True,
            False,
            False,
            100,
            50,
        )
        == 0
    )


def test_service_activity() -> None:

    assert (
        adapt_rsa_tns_turnover_eligibility(
            50,
            False,
            True,
            False,
            100,
            50,
        )
        == 1
    )

    assert (
        adapt_rsa_tns_turnover_eligibility(
            51,
            False,
            False,
            True,
            100,
            50,
        )
        == 0
    )


def test_other_activity() -> None:

    assert (
        adapt_rsa_tns_turnover_eligibility(
            0,
            False,
            False,
            False,
            100,
            50,
        )
        == 0
    )
