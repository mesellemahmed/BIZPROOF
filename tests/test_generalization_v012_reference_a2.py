from decimal import Decimal

import pytest

from bizproof.generalization_v012_reference_a2 import (
    adapt_discount_info,
    adapt_product,
    adapt_taxed_price_mul,
    mutant_discount_info,
    mutant_product,
    mutant_taxed_price_mul,
)
from bizproof.semantic_values_v012 import (
    SemanticRecord,
    SemanticReference,
    SemanticSequence,
    SequenceKind,
    semantic_fingerprint,
)


def _identity_round(
    value: Decimal,
) -> Decimal:
    return value


def test_structured_record_fingerprint() -> None:
    record = SemanticRecord(
        type_name="Example",
        fields=(
            ("x", 1),
            ("name", "A"),
        ),
    )

    fingerprint = semantic_fingerprint(record)

    assert '"kind":"RECORD"' in fingerprint
    assert '"type_name":"Example"' in fingerprint


def test_record_rejects_duplicate_fields() -> None:
    with pytest.raises(ValueError):
        SemanticRecord(
            type_name="Example",
            fields=(
                ("x", 1),
                ("x", 2),
            ),
        )


def test_product_reference_projection() -> None:
    assert adapt_product(
        True,
        10,
        20,
    ) == SemanticReference(
        type_name="Product",
        identity=10,
    )

    assert adapt_product(
        False,
        10,
        20,
    ) == SemanticReference(
        type_name="Product",
        identity=20,
    )


def test_product_mutant_is_distinct() -> None:
    assert adapt_product(
        True,
        10,
        20,
    ) != mutant_product(
        True,
        10,
        20,
    )


def test_discount_info_projection() -> None:
    result = adapt_discount_info(
        5,
        100,
        [
            (
                5,
                100,
                900,
                2,
                0,
            ),
            (
                5,
                100,
                901,
                3,
                1,
            ),
        ],
    )

    assert result == SemanticSequence(
        kind=SequenceKind.TUPLE,
        items=(
            5,
            SemanticReference(
                type_name="Item",
                identity=100,
            ),
            5,
            SemanticReference(
                type_name="DiscountRule",
                identity=900,
            ),
        ),
    )


def test_discount_mutant_is_distinct() -> None:
    infos = [
        (
            5,
            100,
            900,
            2,
            0,
        )
    ]

    assert adapt_discount_info(
        5,
        100,
        infos,
    ) != mutant_discount_info(
        5,
        100,
        infos,
    )


def test_taxed_price_projection() -> None:
    result = adapt_taxed_price_mul(
        gross=Decimal("10.00"),
        rate=Decimal("20"),
        name="VAT",
        code="vat",
        other=Decimal("2"),
        round_decimal_fn=_identity_round,
    )

    assert isinstance(
        result,
        SemanticRecord,
    )

    assert result.type_name == "TaxedPrice"

    assert dict(result.fields)["gross"] == "20.00"


def test_taxed_price_mutant_is_distinct() -> None:
    args = {
        "gross": Decimal("10.00"),
        "rate": Decimal("20"),
        "name": "VAT",
        "code": "vat",
        "other": Decimal("2"),
        "round_decimal_fn": _identity_round,
    }

    assert adapt_taxed_price_mul(**args) != mutant_taxed_price_mul(**args)
