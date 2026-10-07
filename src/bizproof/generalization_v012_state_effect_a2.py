"""Generic state/effect semantic projections for BIZPROOF V0.12."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StateEffect:
    """One ordered observable effect."""

    kind: str
    payload: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ZeroDiscountProjection:
    """Extensional zero-discount result."""


@dataclass(frozen=True, slots=True)
class BasketDiscountProjection:
    """Extensional successful basket-discount result."""

    discount: Any


def deferred_field_gated_reset_effect(
    *,
    deferred_fields: Collection[str],
) -> tuple[StateEffect, ...]:
    """Model constructor delegation followed by conditional reset."""
    effects = [StateEffect("SUPER_INIT")]

    if not deferred_fields:
        effects.append(StateEffect("TRANSACTION_KEY_RESET"))

    return tuple(effects)


def conditional_discount_consume_effect(
    *,
    line_tuples: Sequence[tuple[Any, Any]],
    first_line_quantity_with_offer_discount: int | None,
    offer: Any,
    basket: Any,
) -> tuple[
    ZeroDiscountProjection | BasketDiscountProjection,
    tuple[StateEffect, ...],
]:
    """Model the frozen conditional discount/effect projection."""
    effects = [StateEffect("GET_APPLICABLE_LINES")]

    if not line_tuples:
        return (
            ZeroDiscountProjection(),
            tuple(effects),
        )

    discount, line = line_tuples[0]

    if first_line_quantity_with_offer_discount is None:
        raise ValueError("quantity observation is required when an applicable line exists")

    effects.append(
        StateEffect(
            "QUANTITY_WITH_OFFER_DISCOUNT",
            (
                str(line),
                str(offer),
            ),
        )
    )

    if first_line_quantity_with_offer_discount == 0:
        effects.append(
            StateEffect(
                "APPLY_DISCOUNT",
                (
                    str(line),
                    str(discount),
                    "1",
                    str(offer),
                ),
            )
        )

        affected_lines = [
            (
                line,
                discount,
                1,
            )
        ]

        effects.append(
            StateEffect(
                "CONSUME_ITEMS",
                (
                    str(offer),
                    str(basket),
                    repr(affected_lines),
                ),
            )
        )

        return (
            BasketDiscountProjection(discount),
            tuple(effects),
        )

    return (
        ZeroDiscountProjection(),
        tuple(effects),
    )
