from bizproof.generalization_v012_state_return_a2 import (
    attribute_state_write,
    conditional_status_plus_persistence,
    conditional_string_return,
    discount_sequence_and_cache_invalidation,
    super_mapping_extension,
)


def test_attribute_state_write() -> None:
    assert attribute_state_write(12) == 12


def test_discount_inclusive_branch() -> None:
    result = discount_sequence_and_cache_invalidation(
        pre_discounts=("old",),
        application="new",
        quantity=2,
        offer="offer",
        incl_tax=True,
        pre_incl_cache="INCL",
        pre_excl_cache="EXCL",
    )

    assert result == (
        (
            "old",
            "new",
        ),
        (
            (
                2,
                "offer",
            ),
        ),
        None,
        "EXCL",
    )


def test_discount_exclusive_branch() -> None:
    result = discount_sequence_and_cache_invalidation(
        pre_discounts=(),
        application="new",
        quantity=1,
        offer=None,
        incl_tax=False,
        pre_incl_cache="INCL",
        pre_excl_cache="EXCL",
    )

    assert result == (
        ("new",),
        (
            (
                1,
                None,
            ),
        ),
        "INCL",
        None,
    )


def test_conditional_string_with_description() -> None:
    assert (
        conditional_string_return(
            fee_type_display="Fee",
            description="Desc",
        )
        == "Fee - Desc"
    )


def test_conditional_string_without_description() -> None:
    assert (
        conditional_string_return(
            fee_type_display="Fee",
            description=None,
        )
        == "Fee"
    )


def test_conditional_status_paths() -> None:
    assert conditional_status_plus_persistence(
        old_status="OLD",
        is_suspended=True,
        max_applications=0,
        consumed_status="CONSUMED",
        open_status="OPEN",
        delegated_result="SAVED",
    ) == (
        "OLD",
        "SAVED",
    )

    assert conditional_status_plus_persistence(
        old_status="OLD",
        is_suspended=False,
        max_applications=0,
        consumed_status="CONSUMED",
        open_status="OPEN",
        delegated_result="SAVED",
    ) == (
        "CONSUMED",
        "SAVED",
    )

    assert conditional_status_plus_persistence(
        old_status="OLD",
        is_suspended=False,
        max_applications=2,
        consumed_status="CONSUMED",
        open_status="OPEN",
        delegated_result="SAVED",
    ) == (
        "OPEN",
        "SAVED",
    )


def test_super_mapping_extension_is_pure() -> None:
    base = {
        "base": 1,
    }

    result = super_mapping_extension(
        base,
        "STRATEGY",
    )

    assert base == {
        "base": 1,
    }

    assert result == {
        "base": 1,
        "strategy": "STRATEGY",
    }
