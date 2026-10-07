"""Generic transaction-aware model-save projection for V0.12."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SaveEffect:
    """One explicit save/transaction observation."""

    kind: str
    payload: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class TransactionSaveProjection:
    """Accepted semantic projection of transaction-aware save."""

    code: Any
    datetime_value: Any
    expires: Any
    organizer_id: Any
    status: Any
    pk_after: Any
    update_fields: frozenset[str] | None
    unsafe_deferred_save: bool
    delegated_result: Any
    effects: tuple[SaveEffect, ...]


def _update_fields_text(
    update_fields: set[str] | None,
) -> str:
    if update_fields is None:
        return "<absent>"

    return ",".join(sorted(update_fields))


def transaction_aware_model_save(
    *,
    code: Any,
    datetime_value: Any,
    expires: Any,
    organizer_id: Any,
    event_organizer_id: Any,
    pk_before: Any,
    pk_after: Any,
    status: Any,
    pending_status: Any,
    paid_status: Any,
    require_approval: bool,
    initial_status_paid_or_pending: bool,
    deferred_fields: Iterable[str],
    update_fields: Iterable[str] | None,
    force_save_with_deferred_fields: bool,
    using: Any,
    assigned_code: Any,
    now_value: Any,
    assigned_expires: Any,
    delegated_result: Any,
) -> TransactionSaveProjection:
    """Model the frozen Order.save projection."""
    fields = None if update_fields is None else set(update_fields)

    if fields is not None:
        fields.add("last_modified")

    if not code:
        code = assigned_code

        if fields is not None:
            fields.add("code")

    if not datetime_value:
        datetime_value = now_value

        if fields is not None:
            fields.add("datetime")

    if not expires:
        expires = assigned_expires

        if fields is not None:
            fields.add("expires")

    if not organizer_id:
        organizer_id = event_organizer_id

        if fields is not None:
            fields.add("organizer")

    is_new = not pk_before

    deferred = set(deferred_fields)

    effects: list[SaveEffect] = []

    safe_status_visibility = "require_approval" not in deferred and "status" not in deferred

    if safe_status_visibility:
        current = (
            status
            in (
                pending_status,
                paid_status,
            )
            and not require_approval
        )

        if current != initial_status_paid_or_pending:
            effects.append(
                SaveEffect(
                    "PRE_SAVE_DIRTY",
                    (
                        (
                            "pk",
                            str(pk_before),
                        ),
                        (
                            "using",
                            str(using),
                        ),
                    ),
                )
            )

    else:
        unsafe = not force_save_with_deferred_fields and (
            not fields or ("require_approval" not in fields and "status" not in fields)
        )

        if unsafe:
            return TransactionSaveProjection(
                code=code,
                datetime_value=datetime_value,
                expires=expires,
                organizer_id=organizer_id,
                status=status,
                pk_after=pk_before,
                update_fields=(None if fields is None else frozenset(fields)),
                unsafe_deferred_save=True,
                delegated_result=None,
                effects=tuple(effects),
            )

    effects.append(
        SaveEffect(
            "DELEGATED_SAVE",
            (
                (
                    "update_fields",
                    _update_fields_text(fields),
                ),
            ),
        )
    )

    if is_new:
        effects.append(
            SaveEffect(
                "POST_SAVE_DIRTY",
                (
                    (
                        "pk",
                        str(pk_after),
                    ),
                    (
                        "using",
                        str(using),
                    ),
                ),
            )
        )

    return TransactionSaveProjection(
        code=code,
        datetime_value=datetime_value,
        expires=expires,
        organizer_id=organizer_id,
        status=status,
        pk_after=pk_after,
        update_fields=(None if fields is None else frozenset(fields)),
        unsafe_deferred_save=False,
        delegated_result=delegated_result,
        effects=tuple(effects),
    )
