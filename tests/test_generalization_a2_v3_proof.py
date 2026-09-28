from __future__ import annotations

from decimal import Decimal

from bizproof.generalization_a2_v3_proof import (
    REVIEW_TARGETS,
    SCALAR_TARGETS,
    V3_IDS,
    adapt_completed_payment_sum,
    adapt_event_permission,
    adapt_net_stock_level,
    adapt_pending_order_sum,
    adapt_product_quantity,
)


def test_v3_partition() -> None:

    assert set(SCALAR_TARGETS) | set(REVIEW_TARGETS) == V3_IDS

    assert not (set(SCALAR_TARGETS) & set(REVIEW_TARGETS))


def test_completed_payment_sum() -> None:

    assert adapt_completed_payment_sum(
        Decimal("10.00"),
        Decimal("4.00"),
    ) == Decimal("6.00")

    assert adapt_completed_payment_sum(
        None,
        None,
    ) == Decimal("0.00")


def test_pending_sum() -> None:

    assert adapt_pending_order_sum(
        Decimal("10.00"),
        False,
        Decimal("3.00"),
        Decimal("1.00"),
    ) == Decimal("8.00")

    assert adapt_pending_order_sum(
        Decimal("10.00"),
        True,
        Decimal("3.00"),
        Decimal("1.00"),
    ) == Decimal("-2.00")


def test_product_quantity() -> None:

    assert (
        adapt_product_quantity(
            False,
            7,
        )
        == 0
    )

    assert (
        adapt_product_quantity(
            True,
            7,
        )
        == 7
    )

    assert (
        adapt_product_quantity(
            True,
            None,
        )
        == 0
    )


def test_net_stock_level() -> None:

    assert (
        adapt_net_stock_level(
            None,
            4,
        )
        == 0
    )

    assert (
        adapt_net_stock_level(
            10,
            None,
        )
        == 10
    )

    assert (
        adapt_net_stock_level(
            10,
            3,
        )
        == 7
    )


def test_event_permission() -> None:

    permissions = frozenset(
        {
            "read",
        }
    )

    assert (
        adapt_event_permission(
            True,
            True,
            False,
            permissions,
            "read",
        )
        is True
    )

    assert (
        adapt_event_permission(
            False,
            False,
            True,
            permissions,
            (
                "write",
                "read",
            ),
        )
        is True
    )

    assert (
        adapt_event_permission(
            False,
            False,
            False,
            permissions,
            "read",
        )
        is False
    )
