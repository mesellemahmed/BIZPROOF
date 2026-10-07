from decimal import Decimal

from bizproof.generalization_v012_rich_framework_a2 import (
    RichEffect,
    external_refund_semantics,
    signal_gated_set_semantics,
)


def test_signal_all_true_returns_base() -> None:
    assert signal_gated_set_semantics(
        ("A", "B"),
        (True, True),
    ) == frozenset(
        {
            "A",
            "B",
        }
    )


def test_signal_false_vetoes() -> None:
    assert (
        signal_gated_set_semantics(
            ("A", "B"),
            (
                {
                    "A",
                },
                False,
            ),
        )
        == frozenset()
    )


def test_signal_intersection() -> None:
    assert signal_gated_set_semantics(
        (
            "A",
            "B",
            "C",
        ),
        (
            {
                "A",
                "B",
            },
            {
                "B",
                "C",
            },
        ),
    ) == frozenset(
        {
            "B",
        }
    )


def test_signal_empty_response_matches_all_true_identity() -> None:
    assert signal_gated_set_semantics(
        ("A", "B"),
        (),
    ) == frozenset(
        {
            "A",
            "B",
        }
    )


def test_refund_completed_effect_trace() -> None:
    record, effects = external_refund_semantics(
        payment_amount=Decimal("10.00"),
        explicit_amount=None,
        explicit_execution_date=None,
        now_value="NOW",
        provider="provider",
        info="{}",
        pending_sum=Decimal("-10.00"),
        local_id="R1",
        order_ref="ORDER",
        payment_ref="PAYMENT",
        state="EXTERNAL_STATE",
        source="EXTERNAL_SOURCE",
    )

    assert record.completed is True

    assert [effect.kind for effect in effects] == [
        "CREATE_REFUND",
        "LOG_ACTION",
        "REFUND_DONE",
    ]


def test_refund_incomplete_has_no_done_effect() -> None:
    record, effects = external_refund_semantics(
        payment_amount=Decimal("10.00"),
        explicit_amount=Decimal("3.00"),
        explicit_execution_date="DATE",
        now_value="NOW",
        provider="provider",
        info='{"x":1}',
        pending_sum=Decimal("5.00"),
        local_id="R1",
        order_ref="ORDER",
        payment_ref="PAYMENT",
        state="EXTERNAL_STATE",
        source="EXTERNAL_SOURCE",
    )

    assert record.completed is False

    assert (
        RichEffect(
            "REFUND_DONE",
            (
                (
                    "local_id",
                    "R1",
                ),
            ),
        )
        not in effects
    )
