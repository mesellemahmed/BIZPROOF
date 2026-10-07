from decimal import Decimal

from bizproof.generalization_v012_structured_return_a2 import (
    FixedPriceProjection,
    StockRecordProjection,
    UnavailablePriceProjection,
    conditional_localized_string_return,
    extension_mapping_return,
    filtered_sequence_pricing_return,
)


def test_extension_mapping_preserves_extra_fields() -> None:
    result = extension_mapping_return(
        order_position_id="P",
        external_object_type="TYPE",
        external_id_field="FIELD",
        id_value="ID",
        external_link_href="HREF",
        external_link_display_name="DISPLAY",
        sync_info={
            "extra": 7,
        },
    )

    assert result["extra"] == 7


def test_extension_mapping_sync_info_has_final_precedence() -> None:
    result = extension_mapping_return(
        order_position_id="ORIGINAL",
        external_object_type="TYPE",
        external_id_field="FIELD",
        id_value="ID",
        external_link_href="HREF",
        external_link_display_name="DISPLAY",
        sync_info={
            "position": "OVERRIDE",
        },
    )

    assert result["position"] == "OVERRIDE"


def test_conditional_localized_string() -> None:
    def translate(value: str) -> str:
        return value

    assert (
        conditional_localized_string_return(
            price_includes_tax=True,
            rate=19,
            name="VAT",
            eu_reverse_charge=False,
            internal_name=None,
            translate=translate,
        )
        == "incl. 19% VAT"
    )

    assert conditional_localized_string_return(
        price_includes_tax=False,
        rate=19,
        name="VAT",
        eu_reverse_charge=True,
        internal_name="INTERNAL",
        translate=translate,
    ) == ("INTERNAL (plus 19% VAT (reverse charge enabled))")


def test_filtered_sequence_unavailable() -> None:
    result = filtered_sequence_pricing_return(
        children_stock=[
            (
                "CHILD",
                None,
            )
        ],
        rate=Decimal("0.20"),
        exponent=Decimal("0.01"),
    )

    assert result == (UnavailablePriceProjection())


def test_filtered_sequence_uses_first_non_null_record() -> None:
    first = StockRecordProjection(
        price_currency="USD",
        price=Decimal("10.00"),
    )

    second = StockRecordProjection(
        price_currency="EUR",
        price=Decimal("20.00"),
    )

    result = filtered_sequence_pricing_return(
        children_stock=[
            (
                "NONE",
                None,
            ),
            (
                "FIRST",
                first,
            ),
            (
                "SECOND",
                second,
            ),
        ],
        rate=Decimal("0.20"),
        exponent=Decimal("0.01"),
    )

    assert result == (
        FixedPriceProjection(
            currency="USD",
            excl_tax=Decimal("10.00"),
            tax=Decimal("2.00"),
        )
    )
