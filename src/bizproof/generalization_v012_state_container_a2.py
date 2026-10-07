"""Generic V0.12 state/container semantic projections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any


def mapping_state_write(
    pre_state: Mapping[str, Any],
    key: str,
    value: Any,
) -> dict[str, Any]:
    """Return the mapping post-state after one explicit write."""
    post = dict(pre_state)
    post[key] = value
    return post


def object_state_plus_effect_trace(
    open_status: Any,
) -> tuple[Any, tuple[str, ...]]:
    """Model an OPEN assignment followed by persistence."""
    return (
        open_status,
        ("save",),
    )


def operation_sequence_append(
    pre_operations: Sequence[Any],
    operation: Any,
) -> tuple[Any, ...]:
    """Append one semantic operation to an ordered sequence."""
    return (
        *tuple(pre_operations),
        operation,
    )


def session_mapping_sequence_mutation(
    pre_state: Mapping[str, Any],
    *,
    generated_id: str,
    provider_identifier: str,
    multi_use_supported: bool,
    min_value_text: str | None,
    max_value_text: str | None,
    info_data: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Model the payment-session update extensionally."""
    post = dict(pre_state)

    payments = list(
        post.get(
            "payments",
            [],
        )
    )

    payments.append(
        {
            "id": generated_id,
            "provider": provider_identifier,
            "multi_use_supported": multi_use_supported,
            "min_value": min_value_text,
            "max_value": max_value_text,
            "info_data": (dict(info_data) if info_data else {}),
        }
    )

    post["payments"] = payments

    post["payments_postpone"] = False

    return post


def multi_state_plus_operation_append(
    *,
    old_totaldiff: Decimal,
    taxed_gross: Decimal,
    fee_value: Decimal,
    pre_operations: Sequence[Any],
    operation: Any,
) -> tuple[
    Decimal,
    bool,
    tuple[Any, ...],
]:
    """Model the state affected by change_fee."""
    delta = taxed_gross - fee_value

    return (
        old_totaldiff + delta,
        True,
        (
            *tuple(pre_operations),
            operation,
        ),
    )


def conditional_sequence_return(
    *,
    order_text: str | None,
    variation_present: bool,
    variation_text: str | None,
    item_text: str | None,
) -> tuple[str, ...]:
    """Build the ordered non-scalar observation."""
    result: list[str] = []

    if order_text:
        result.append(order_text)

    if variation_present and variation_text:
        result.append(variation_text)

    if item_text:
        result.append(item_text)

    return tuple(result)
