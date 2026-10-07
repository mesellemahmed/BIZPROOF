"""V0.12 generic state/return semantic projections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def attribute_state_write(
    new_value: Any,
) -> Any:
    """Return the post-state of one explicit attribute write."""
    return new_value


def discount_sequence_and_cache_invalidation(
    *,
    pre_discounts: Sequence[Any],
    application: Any,
    quantity: Any,
    offer: Any,
    incl_tax: bool,
    pre_incl_cache: Any,
    pre_excl_cache: Any,
) -> tuple[
    tuple[Any, ...],
    tuple[tuple[Any, Any], ...],
    Any,
    Any,
]:
    """Model discount append, consume effect and cache invalidation."""
    discounts = (
        *tuple(pre_discounts),
        application,
    )

    consume_trace = (
        (
            quantity,
            offer,
        ),
    )

    incl_cache = pre_incl_cache
    excl_cache = pre_excl_cache

    if incl_tax:
        incl_cache = None
    else:
        excl_cache = None

    return (
        discounts,
        consume_trace,
        incl_cache,
        excl_cache,
    )


def conditional_string_return(
    *,
    fee_type_display: str,
    description: str | None,
) -> str:
    """Model the conditional display string."""
    if description:
        return f"{fee_type_display} - {description}"

    return fee_type_display


def conditional_status_plus_persistence(
    *,
    old_status: Any,
    is_suspended: bool,
    max_applications: int,
    consumed_status: Any,
    open_status: Any,
    delegated_result: Any,
) -> tuple[Any, Any]:
    """Model the status transition followed by delegated persistence."""
    status = old_status

    if not is_suspended:
        if max_applications == 0:
            status = consumed_status
        else:
            status = open_status

    return (
        status,
        delegated_result,
    )


def super_mapping_extension(
    base_mapping: Mapping[str, Any],
    strategy: Any,
) -> dict[str, Any]:
    """Extend the delegated mapping with request.strategy."""
    result = dict(base_mapping)

    result["strategy"] = strategy

    return result
