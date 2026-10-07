from bizproof.generalization_v012_non_scalar_a2 import (
    adapt_description,
    adapt_get_user_offers,
    adapt_line_price_str,
    adapt_order_position_repr,
    mutant_description,
    mutant_get_user_offers,
    mutant_line_price_str,
    mutant_order_position_repr,
)
from bizproof.semantic_values_v012 import normalize_semantic_value


def test_order_position_projection() -> None:
    result = adapt_order_position_repr(
        7,
        False,
        99,
        "ORDER-1",
    )

    assert result == ("<OrderPosition: item 7, variation 0 for order ORDER-1>")

    assert normalize_semantic_value(result) == result


def test_order_position_mutant_refuted() -> None:
    args = (
        7,
        False,
        99,
        "ORDER-1",
    )

    assert adapt_order_position_repr(*args) != mutant_order_position_repr(*args)


def test_line_price_projection() -> None:
    template = "Line '%(number)s' (quantity %(qty)d) price %(price)s"

    result = adapt_line_price_str(
        template,
        "A",
        2,
        "10.00",
    )

    assert result == ("Line 'A' (quantity 2) price 10.00")

    assert normalize_semantic_value(result) == result


def test_line_price_mutant_refuted() -> None:
    template = "Line '%(number)s' (quantity %(qty)d) price %(price)s"

    assert adapt_line_price_str(
        template,
        "A",
        2,
        "10.00",
    ) != mutant_line_price_str(
        template,
        "A",
        2,
        "10.00",
    )


def test_description_projection() -> None:
    template = "%(value)s on %(range)s"

    result = adapt_description(
        template,
        "25%",
        "Books",
    )

    assert result == "25% on Books"

    assert normalize_semantic_value(result) == result


def test_description_mutant_refuted() -> None:
    template = "%(value)s on %(range)s"

    assert adapt_description(
        template,
        "25%",
        "Books",
    ) != mutant_description(
        template,
        "25%",
        "Books",
    )


def test_user_offers_projection() -> None:
    result = adapt_get_user_offers()

    normalized = normalize_semantic_value(result)

    assert result == []
    assert normalized.items == ()


def test_user_offers_mutant_refuted() -> None:
    assert adapt_get_user_offers() != mutant_get_user_offers()
