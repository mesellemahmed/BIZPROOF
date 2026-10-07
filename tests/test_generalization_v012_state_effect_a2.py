from bizproof.generalization_v012_state_effect_a2 import (
    BasketDiscountProjection,
    StateEffect,
    ZeroDiscountProjection,
    conditional_discount_consume_effect,
    deferred_field_gated_reset_effect,
)


def test_reset_when_no_fields_deferred() -> None:
    assert deferred_field_gated_reset_effect(deferred_fields=set()) == (
        StateEffect("SUPER_INIT"),
        StateEffect("TRANSACTION_KEY_RESET"),
    )


def test_no_reset_when_fields_deferred() -> None:
    assert deferred_field_gated_reset_effect(deferred_fields={"field"}) == (
        StateEffect("SUPER_INIT"),
    )


def test_discount_no_applicable_lines() -> None:
    result, effects = conditional_discount_consume_effect(
        line_tuples=[],
        first_line_quantity_with_offer_discount=None,
        offer="OFFER",
        basket="BASKET",
    )

    assert result == (ZeroDiscountProjection())

    assert effects == (StateEffect("GET_APPLICABLE_LINES"),)


def test_discount_successful_effect_order() -> None:
    result, effects = conditional_discount_consume_effect(
        line_tuples=[
            (
                "10",
                "LINE",
            )
        ],
        first_line_quantity_with_offer_discount=0,
        offer="OFFER",
        basket="BASKET",
    )

    assert result == (BasketDiscountProjection("10"))

    assert [effect.kind for effect in effects] == [
        "GET_APPLICABLE_LINES",
        "QUANTITY_WITH_OFFER_DISCOUNT",
        "APPLY_DISCOUNT",
        "CONSUME_ITEMS",
    ]


def test_discount_already_discounted() -> None:
    result, effects = conditional_discount_consume_effect(
        line_tuples=[
            (
                "10",
                "LINE",
            )
        ],
        first_line_quantity_with_offer_discount=1,
        offer="OFFER",
        basket="BASKET",
    )

    assert result == (ZeroDiscountProjection())

    assert [effect.kind for effect in effects] == [
        "GET_APPLICABLE_LINES",
        "QUANTITY_WITH_OFFER_DISCOUNT",
    ]
