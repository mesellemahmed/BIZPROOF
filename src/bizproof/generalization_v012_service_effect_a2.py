"""Generic V0.12 service/effect semantic projections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FrameworkEffect:
    """One extensional framework-effect observation."""

    kind: str
    payload: tuple[tuple[str, str], ...] = ()


def cache_backed_service_result(
    *,
    pk: Any,
    count_waitinglist: bool,
    cache: Mapping[Any, Any] | None,
    service_result: Any,
    now_dt: Any,
    allow_cache: bool,
) -> tuple[
    Any,
    dict[Any, Any] | None,
    tuple[FrameworkEffect, ...],
]:
    """Model availability cache/service behavior."""
    post_cache = None if cache is None else dict(cache)

    effects: list[FrameworkEffect] = []

    if post_cache and count_waitinglist is not post_cache.get(
        "_count_waitinglist",
        True,
    ):
        effects.append(FrameworkEffect("CACHE_CLEAR"))

        post_cache.clear()

    if post_cache is not None and pk in post_cache:
        result = post_cache[pk]

        effects.append(
            FrameworkEffect(
                "CACHE_HIT",
                (
                    (
                        "pk",
                        str(pk),
                    ),
                ),
            )
        )

        return (
            result,
            post_cache,
            tuple(effects),
        )

    effects.append(
        FrameworkEffect(
            "SERVICE_QUEUE",
            (
                (
                    "pk",
                    str(pk),
                ),
            ),
        )
    )

    effects.append(
        FrameworkEffect(
            "SERVICE_COMPUTE",
            (
                (
                    "now_dt",
                    str(now_dt),
                ),
                (
                    "allow_cache",
                    str(allow_cache),
                ),
            ),
        )
    )

    if post_cache is not None:
        post_cache[pk] = service_result

        effects.append(
            FrameworkEffect(
                "CACHE_WRITE_RESULT",
                (
                    (
                        "pk",
                        str(pk),
                    ),
                    (
                        "value",
                        str(service_result),
                    ),
                ),
            )
        )

        post_cache["_count_waitinglist"] = count_waitinglist

        effects.append(
            FrameworkEffect(
                "CACHE_WRITE_POLICY",
                (
                    (
                        "value",
                        str(count_waitinglist),
                    ),
                ),
            )
        )

    return (
        service_result,
        post_cache,
        tuple(effects),
    )


def ordered_basket_effect_trace(
    *,
    offers_before: Any,
    product: Any,
    quantity: Any,
    cleaned_options: Any,
    line: Any,
    line_created: bool,
    success_message: str,
    user: Any,
    delegated_result: Any,
) -> tuple[
    Any,
    bool,
    Any,
    tuple[FrameworkEffect, ...],
]:
    """Model the prospectively frozen basket effect trace."""
    effects = (
        FrameworkEffect("APPLIED_OFFERS"),
        FrameworkEffect(
            "ADD_PRODUCT",
            (
                (
                    "product",
                    str(product),
                ),
                (
                    "quantity",
                    str(quantity),
                ),
                (
                    "options",
                    repr(cleaned_options),
                ),
            ),
        ),
        FrameworkEffect(
            "MESSAGE_SUCCESS",
            (
                (
                    "message",
                    success_message,
                ),
                (
                    "extra_tags",
                    "safe noicon",
                ),
            ),
        ),
        FrameworkEffect(
            "OFFER_MESSAGES",
            (
                (
                    "offers_before",
                    repr(offers_before),
                ),
            ),
        ),
        FrameworkEffect(
            "ADD_SIGNAL",
            (
                (
                    "product",
                    str(product),
                ),
                (
                    "user",
                    str(user),
                ),
            ),
        ),
        FrameworkEffect("SUPER_FORM_VALID"),
    )

    return (
        line,
        line_created,
        delegated_result,
        effects,
    )
