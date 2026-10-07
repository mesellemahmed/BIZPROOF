"""V0.12 reference and structured-value A2 projections."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal

from bizproof.semantic_values_v012 import (
    SemanticRecord,
    SemanticReference,
    SemanticSequence,
    SequenceKind,
)

RoundDecimal = Callable[[Decimal], Decimal]


@dataclass(frozen=True, slots=True)
class TaxedPriceProjection:
    gross: Decimal
    net: Decimal
    tax: Decimal
    rate: Decimal
    name: str
    code: str


def raw_taxed_price_mul(
    gross: Decimal,
    rate: Decimal,
    name: str,
    code: str,
    other: Decimal,
    round_decimal_fn: RoundDecimal,
) -> TaxedPriceProjection:
    newgross = gross * other
    newnet = round_decimal_fn(newgross - (newgross * (1 - 100 / (100 + rate)))).quantize(
        Decimal("10") ** gross.as_tuple().exponent  # type: ignore[operator]
    )

    return TaxedPriceProjection(
        gross=newgross,
        net=newnet,
        tax=newgross - newnet,
        rate=rate,
        name=name,
        code=code,
    )


def project_taxed_price(
    value: TaxedPriceProjection,
) -> SemanticRecord:
    return SemanticRecord(
        type_name="TaxedPrice",
        fields=(
            (
                "gross",
                format(value.gross, "f"),
            ),
            (
                "net",
                format(value.net, "f"),
            ),
            (
                "tax",
                format(value.tax, "f"),
            ),
            (
                "rate",
                format(value.rate, "f"),
            ),
            ("name", value.name),
            ("code", value.code),
        ),
    )


def adapt_taxed_price_mul(
    gross: Decimal,
    rate: Decimal,
    name: str,
    code: str,
    other: Decimal,
    round_decimal_fn: RoundDecimal,
) -> SemanticRecord:
    return project_taxed_price(
        raw_taxed_price_mul(
            gross,
            rate,
            name,
            code,
            other,
            round_decimal_fn,
        )
    )


def mutant_taxed_price_mul(
    gross: Decimal,
    rate: Decimal,
    name: str,
    code: str,
    other: Decimal,
    round_decimal_fn: RoundDecimal,
) -> SemanticRecord:
    raw = raw_taxed_price_mul(
        gross,
        rate,
        name,
        code,
        other,
        round_decimal_fn,
    )

    return SemanticRecord(
        type_name="TaxedPrice",
        fields=(
            (
                "gross",
                format(raw.gross, "f"),
            ),
            (
                "net",
                format(raw.net, "f"),
            ),
            (
                "tax",
                format(raw.tax, "f"),
            ),
            (
                "rate",
                format(raw.rate, "f"),
            ),
            ("name", raw.code),
            ("code", raw.name),
        ),
    )


InfoTuple = tuple[
    int,
    int,
    int,
    int,
    int,
]


def raw_discount_info(
    subevent_id: int,
    item_id: int,
    infos_for_item: Iterable[InfoTuple],
) -> tuple[int, int, int, int]:
    infos_for_item = list(infos_for_item)

    return (
        subevent_id,
        item_id,
        sum(
            max_count
            for (
                subevent_id,
                item_id,
                discount_rule_id,
                max_count,
                i,
            ) in infos_for_item
        ),
        next(
            discount_rule_id
            for (
                subevent_id,
                item_id,
                discount_rule_id,
                max_count,
                i,
            ) in infos_for_item
        ),
    )


def adapt_discount_info(
    subevent_id: int,
    item_id: int,
    infos_for_item: Iterable[InfoTuple],
) -> SemanticSequence:
    (
        result_subevent_id,
        result_item_id,
        max_count,
        discount_rule_id,
    ) = raw_discount_info(
        subevent_id,
        item_id,
        infos_for_item,
    )

    return SemanticSequence(
        kind=SequenceKind.TUPLE,
        items=(
            result_subevent_id,
            SemanticReference(
                type_name="Item",
                identity=result_item_id,
            ),
            max_count,
            SemanticReference(
                type_name="DiscountRule",
                identity=discount_rule_id,
            ),
        ),
    )


def mutant_discount_info(
    subevent_id: int,
    item_id: int,
    infos_for_item: Iterable[InfoTuple],
) -> SemanticSequence:
    (
        result_subevent_id,
        result_item_id,
        max_count,
        discount_rule_id,
    ) = raw_discount_info(
        subevent_id,
        item_id,
        infos_for_item,
    )

    return SemanticSequence(
        kind=SequenceKind.TUPLE,
        items=(
            result_subevent_id,
            SemanticReference(
                type_name="Item",
                identity=result_item_id,
            ),
            max_count + 1,
            SemanticReference(
                type_name="DiscountRule",
                identity=discount_rule_id,
            ),
        ),
    )


def raw_product(
    child_present: bool,
    child_product_id: int,
    parent_product_id: int,
) -> int:
    return child_product_id if child_present else parent_product_id


def adapt_product(
    child_present: bool,
    child_product_id: int,
    parent_product_id: int,
) -> SemanticReference:
    return SemanticReference(
        type_name="Product",
        identity=raw_product(
            child_present,
            child_product_id,
            parent_product_id,
        ),
    )


def mutant_product(
    child_present: bool,
    child_product_id: int,
    parent_product_id: int,
) -> SemanticReference:
    return SemanticReference(
        type_name="Product",
        identity=(parent_product_id if child_present else child_product_id),
    )
