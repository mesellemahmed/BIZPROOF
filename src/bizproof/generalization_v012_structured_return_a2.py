"""Generic structured-return semantic projections for BIZPROOF V0.12."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class StockRecordProjection:
    """Extensional stock-record observation."""

    price_currency: str
    price: Decimal


@dataclass(frozen=True, slots=True)
class UnavailablePriceProjection:
    """Extensional unavailable-price result."""


@dataclass(frozen=True, slots=True)
class FixedPriceProjection:
    """Extensional fixed-price result."""

    currency: str
    excl_tax: Decimal
    tax: Decimal


def extension_mapping_return(
    *,
    order_position_id: Any,
    external_object_type: Any,
    external_id_field: Any,
    id_value: Any,
    external_link_href: Any,
    external_link_display_name: Any,
    sync_info: Mapping[str, Any],
) -> dict[str, Any]:
    """Model fixed fields followed by Python mapping expansion."""
    result: dict[str, Any] = {
        "position": order_position_id,
        "object_type": external_object_type,
        "external_id_field": external_id_field,
        "id_value": id_value,
        "external_link_href": external_link_href,
        "external_link_display_name": external_link_display_name,
    }

    result.update(sync_info)

    return result


def conditional_localized_string_return(
    *,
    price_includes_tax: bool,
    rate: Any,
    name: Any,
    eu_reverse_charge: bool,
    internal_name: Any,
    translate: Callable[[str], str],
) -> str:
    """Model the frozen localized tax-string projection."""
    if price_includes_tax:
        result = translate("incl. {rate}% {name}").format(
            rate=rate,
            name=name,
        )
    else:
        result = translate("plus {rate}% {name}").format(
            rate=rate,
            name=name,
        )

    if eu_reverse_charge:
        result += " ({})".format(translate("reverse charge enabled"))

    if internal_name:
        return f"{internal_name} ({result})"

    return str(result)


def filtered_sequence_pricing_return(
    *,
    children_stock: Sequence[
        tuple[
            Any,
            StockRecordProjection | None,
        ]
    ],
    rate: Decimal,
    exponent: Decimal,
) -> UnavailablePriceProjection | FixedPriceProjection:
    """Model filtering and first-stockrecord pricing semantics."""
    stockrecords = [item[1] for item in children_stock if item[1] is not None]

    if not stockrecords:
        return UnavailablePriceProjection()

    stockrecord = stockrecords[0]

    tax = (stockrecord.price * rate).quantize(exponent)

    return FixedPriceProjection(
        currency=(stockrecord.price_currency),
        excl_tax=(stockrecord.price),
        tax=tax,
    )
