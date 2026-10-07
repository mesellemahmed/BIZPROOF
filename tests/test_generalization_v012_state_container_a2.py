from decimal import Decimal

from bizproof.generalization_v012_state_container_a2 import (
    conditional_sequence_return,
    mapping_state_write,
    multi_state_plus_operation_append,
    object_state_plus_effect_trace,
    operation_sequence_append,
    session_mapping_sequence_mutation,
)


def test_mapping_state_write_is_pure() -> None:
    pre = {
        "existing": "E",
    }

    post = mapping_state_write(
        pre,
        "color",
        "FIELD",
    )

    assert pre == {
        "existing": "E",
    }

    assert post == {
        "existing": "E",
        "color": "FIELD",
    }


def test_object_state_plus_effect_trace() -> None:
    assert object_state_plus_effect_trace("OPEN") == (
        "OPEN",
        ("save",),
    )


def test_operation_sequence_append() -> None:
    assert operation_sequence_append(
        ("old",),
        "new",
    ) == (
        "old",
        "new",
    )


def test_session_mapping_sequence_mutation() -> None:
    post = session_mapping_sequence_mutation(
        {
            "payments": [
                {
                    "id": "old",
                }
            ],
            "payments_postpone": True,
        },
        generated_id="U1",
        provider_identifier="provider",
        multi_use_supported=True,
        min_value_text="1.25",
        max_value_text=None,
        info_data={
            "x": 1,
        },
    )

    assert len(post["payments"]) == 2

    assert post["payments"][1]["id"] == "U1"

    assert post["payments_postpone"] is False


def test_multi_state_plus_operation_append() -> None:
    result = multi_state_plus_operation_append(
        old_totaldiff=Decimal("3.00"),
        taxed_gross=Decimal("12.00"),
        fee_value=Decimal("8.00"),
        pre_operations=("seed",),
        operation="fee-op",
    )

    assert result == (
        Decimal("7.00"),
        True,
        (
            "seed",
            "fee-op",
        ),
    )


def test_conditional_sequence_return_order() -> None:
    assert conditional_sequence_return(
        order_text="ORDER",
        variation_present=True,
        variation_text="VAR",
        item_text="ITEM",
    ) == (
        "ORDER",
        "VAR",
        "ITEM",
    )


def test_conditional_sequence_return_optional_paths() -> None:
    assert conditional_sequence_return(
        order_text=None,
        variation_present=False,
        variation_text="VAR",
        item_text="ITEM",
    ) == ("ITEM",)
