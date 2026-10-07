"""Generic rich-framework semantic projections for BIZPROOF V0.12."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class RichEffect:
    """Extensional observation of one framework-side effect."""

    kind: str
    payload: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class RefundSemanticRecord:
    """Framework-independent semantic refund record."""

    state: str
    source: str
    amount: Decimal
    order_ref: str
    payment_ref: str
    execution_date: str
    provider: str
    info: str
    local_id: str
    completed: bool


def signal_gated_set_semantics(
    base_positions: Iterable[Any],
    signal_values: Sequence[Any],
) -> frozenset[Any]:
    """Model Pretix ticket-position plugin gating extensionally."""
    base = frozenset(base_positions)

    if all(value is True for value in signal_values):
        return base

    if any(value is False for value in signal_values):
        return frozenset()

    result = set(base)

    for value in signal_values:
        if isinstance(
            value,
            Iterable,
        ):
            result.intersection_update(value)

    return frozenset(result)


def external_refund_semantics(
    *,
    payment_amount: Decimal,
    explicit_amount: Decimal | None,
    explicit_execution_date: str | None,
    now_value: str,
    provider: str,
    info: str,
    pending_sum: Decimal,
    local_id: str,
    order_ref: str,
    payment_ref: str,
    state: str,
    source: str,
) -> tuple[
    RefundSemanticRecord,
    tuple[RichEffect, ...],
]:
    """Model creation/logging/completion of an external refund."""
    amount = explicit_amount if explicit_amount is not None else payment_amount

    execution_date = explicit_execution_date or now_value

    completed = pending_sum + amount == Decimal("0.00")

    record = RefundSemanticRecord(
        state=state,
        source=source,
        amount=amount,
        order_ref=order_ref,
        payment_ref=payment_ref,
        execution_date=execution_date,
        provider=provider,
        info=info,
        local_id=local_id,
        completed=completed,
    )

    effects = [
        RichEffect(
            "CREATE_REFUND",
            (
                ("state", state),
                ("source", source),
                ("amount", str(amount)),
                ("order", order_ref),
                ("payment", payment_ref),
                (
                    "execution_date",
                    execution_date,
                ),
                ("provider", provider),
                ("info", info),
            ),
        ),
        RichEffect(
            "LOG_ACTION",
            (
                (
                    "action",
                    ("pretix.event.order.refund.created.externally"),
                ),
                ("local_id", local_id),
                ("provider", provider),
            ),
        ),
    ]

    if completed:
        effects.append(
            RichEffect(
                "REFUND_DONE",
                (
                    (
                        "local_id",
                        local_id,
                    ),
                ),
            )
        )

    return (
        record,
        tuple(effects),
    )
