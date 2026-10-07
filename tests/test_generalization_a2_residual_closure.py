from __future__ import annotations

from bizproof.generalization_a2_residual_closure import (
    COMPLEX_SCALAR_PENDING,
    ORIGINAL_A2_REMAINDER,
    SCALAR_PROJECTION_TARGETS,
    UNSUPPORTED_IDS,
    adapt_basket_quantity_permission,
    adapt_stock_purchase_permission,
)


def test_residual_partition() -> None:

    assert len(ORIGINAL_A2_REMAINDER) == 21

    assert len(SCALAR_PROJECTION_TARGETS) == 2

    assert len(UNSUPPORTED_IDS) == 17

    assert len(COMPLEX_SCALAR_PENDING) == 2

    assert not (set(SCALAR_PROJECTION_TARGETS) & UNSUPPORTED_IDS)

    assert not (UNSUPPORTED_IDS & COMPLEX_SCALAR_PENDING)


def test_stock_permission_projection() -> None:

    assert (
        adapt_stock_purchase_permission(
            5,
            5,
        )
        is True
    )

    assert (
        adapt_stock_purchase_permission(
            5,
            6,
        )
        is False
    )

    assert (
        adapt_stock_purchase_permission(
            0,
            0,
        )
        is False
    )


def test_basket_quantity_projection() -> None:

    assert (
        adapt_basket_quantity_permission(
            False,
            False,
            False,
            None,
            100,
        )
        is True
    )

    assert (
        adapt_basket_quantity_permission(
            True,
            True,
            False,
            None,
            1,
        )
        is False
    )

    assert (
        adapt_basket_quantity_permission(
            True,
            True,
            True,
            5,
            6,
        )
        is False
    )

    assert (
        adapt_basket_quantity_permission(
            True,
            True,
            True,
            5,
            5,
        )
        is True
    )
