from __future__ import annotations

from bizproof.generalization_a2_v1_proof import (
    NON_SCALAR_REVIEW,
    SCALAR_TARGETS,
    V1_IDS,
    adapt_basket_discount_success,
    adapt_basket_tax_known,
    adapt_discount_subevent_key,
    adapt_line_tax_known,
)


def test_v1_partition() -> None:

    assert set(SCALAR_TARGETS) | set(NON_SCALAR_REVIEW) == V1_IDS

    assert not (set(SCALAR_TARGETS) & set(NON_SCALAR_REVIEW))


def test_scalar_adapter_key() -> None:

    assert adapt_discount_subevent_key(None) == 0

    assert adapt_discount_subevent_key(7) == 7


def test_scalar_adapter_discount() -> None:

    assert adapt_basket_discount_success(1) is True

    assert adapt_basket_discount_success(0) is False


def test_scalar_adapter_tax() -> None:

    assert adapt_line_tax_known(True) is True

    assert (
        adapt_basket_tax_known(
            False,
            (
                True,
                True,
            ),
        )
        is True
    )

    assert (
        adapt_basket_tax_known(
            True,
            (),
        )
        is False
    )
