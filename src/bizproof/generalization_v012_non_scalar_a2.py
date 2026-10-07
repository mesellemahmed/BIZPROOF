# ruff: noqa: UP031
"""V0.12 A2 projections for previously unsupported non-scalar returns."""

from __future__ import annotations


def adapt_order_position_repr(
    item_id: int,
    variation_present: bool,
    variation_id: int,
    order_id: object,
) -> str:
    return "<OrderPosition: item %d, variation %d for order %s>" % (
        item_id,
        variation_id if variation_present else 0,
        order_id,
    )


def mutant_order_position_repr(
    item_id: int,
    variation_present: bool,
    variation_id: int,
    order_id: object,
) -> str:
    return "<OrderPosition: item %d, variation %d for order %s>" % (
        item_id,
        variation_id if variation_present else 1,
        order_id,
    )


def adapt_line_price_str(
    translated_template: str,
    line: object,
    quantity: int,
    price_incl_tax: object,
) -> str:
    return translated_template % {
        "number": line,
        "qty": quantity,
        "price": price_incl_tax,
    }


def mutant_line_price_str(
    translated_template: str,
    line: object,
    quantity: int,
    price_incl_tax: object,
) -> str:
    return translated_template % {
        "number": line,
        "qty": quantity + 1,
        "price": price_incl_tax,
    }


def adapt_description(
    description_template: str,
    value: object,
    range_anchor_value: object,
) -> str:
    return description_template % {
        "value": value,
        "range": range_anchor_value,
    }


def mutant_description(
    description_template: str,
    value: object,
    range_anchor_value: object,
) -> str:
    return description_template % {
        "value": range_anchor_value,
        "range": value,
    }


def adapt_get_user_offers() -> list[object]:
    return []


def mutant_get_user_offers() -> list[object]:
    return ["unexpected"]
