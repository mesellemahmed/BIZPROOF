"""V0.12 temporal and ordered-reference A2 projections."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import chain
from typing import Any

from bizproof.semantic_values_v012 import (
    SemanticReference,
    SemanticSequence,
    SemanticTemporal,
    SequenceKind,
    UnsupportedSemanticValue,
    normalize_semantic_value,
)


def raw_ticket_download_date(
    event: Any,
    positions: Any,
    relative_date_wrapper: object,
) -> Any:
    dl_date = event.settings.get(
        "ticket_download_date",
        as_type=relative_date_wrapper,
    )
    if dl_date:
        if event.has_subevents:
            dates = [
                dl_date.datetime(se)
                for se in event.subevents.filter(
                    id__in=positions.values_list(
                        "subevent",
                        flat=True,
                    )
                )
            ]
            dl_date = min(dates) if dates else None
        else:
            dl_date = dl_date.datetime(event)
    return dl_date


def mutant_ticket_download_date(
    event: Any,
    positions: Any,
    relative_date_wrapper: object,
) -> Any:
    dl_date = event.settings.get(
        "ticket_download_date",
        as_type=relative_date_wrapper,
    )
    if dl_date:
        if event.has_subevents:
            dates = [
                dl_date.datetime(se)
                for se in event.subevents.filter(
                    id__in=positions.values_list(
                        "subevent",
                        flat=True,
                    )
                )
            ]
            dl_date = max(dates) if dates else None
        else:
            dl_date = dl_date.datetime(event)
    return dl_date


def adapt_ticket_download_date(
    event: Any,
    positions: Any,
    relative_date_wrapper: object,
) -> SemanticTemporal | None:
    value = raw_ticket_download_date(
        event,
        positions,
        relative_date_wrapper,
    )

    normalized = normalize_semantic_value(value)

    if normalized is None or isinstance(
        normalized,
        SemanticTemporal,
    ):
        return normalized

    raise UnsupportedSemanticValue("ticket_download_date contract requires temporal value or None")


def mutant_ticket_download_date_semantic(
    event: Any,
    positions: Any,
    relative_date_wrapper: object,
) -> SemanticTemporal | None:
    value = mutant_ticket_download_date(
        event,
        positions,
        relative_date_wrapper,
    )

    normalized = normalize_semantic_value(value)

    if normalized is None or isinstance(
        normalized,
        SemanticTemporal,
    ):
        return normalized

    raise UnsupportedSemanticValue("ticket_download_date mutant escaped temporal contract")


@dataclass(frozen=True, slots=True)
class OfferProjection:
    identity: int
    priority: int


SiteOffersProvider = Callable[
    [],
    Iterable[OfferProjection],
]

BasketOffersProvider = Callable[
    [object, object | None],
    Iterable[OfferProjection],
]

UserOffersProvider = Callable[
    [object | None],
    Iterable[OfferProjection],
]

SessionOffersProvider = Callable[
    [object | None],
    Iterable[OfferProjection],
]


def raw_get_offers(
    get_site_offers: SiteOffersProvider,
    get_basket_offers: BasketOffersProvider,
    get_user_offers: UserOffersProvider,
    get_session_offers: SessionOffersProvider,
    basket: object,
    user: object | None = None,
    request: object | None = None,
) -> list[OfferProjection]:
    site_offers = get_site_offers()
    basket_offers = get_basket_offers(
        basket,
        user,
    )
    user_offers = get_user_offers(user)
    session_offers = get_session_offers(request)

    return list(
        sorted(
            chain(
                session_offers,
                basket_offers,
                user_offers,
                site_offers,
            ),
            key=lambda o: o.priority,
            reverse=True,
        )
    )


def mutant_get_offers(
    get_site_offers: SiteOffersProvider,
    get_basket_offers: BasketOffersProvider,
    get_user_offers: UserOffersProvider,
    get_session_offers: SessionOffersProvider,
    basket: object,
    user: object | None = None,
    request: object | None = None,
) -> list[OfferProjection]:
    site_offers = get_site_offers()
    basket_offers = get_basket_offers(
        basket,
        user,
    )
    user_offers = get_user_offers(user)
    session_offers = get_session_offers(request)

    return list(
        sorted(
            chain(
                session_offers,
                basket_offers,
                user_offers,
                site_offers,
            ),
            key=lambda o: o.priority,
            reverse=False,
        )
    )


def _project_offers(
    offers: Iterable[OfferProjection],
) -> SemanticSequence:
    return SemanticSequence(
        kind=SequenceKind.LIST,
        items=tuple(
            SemanticReference(
                type_name="Offer",
                identity=offer.identity,
            )
            for offer in offers
        ),
    )


def adapt_get_offers(
    get_site_offers: SiteOffersProvider,
    get_basket_offers: BasketOffersProvider,
    get_user_offers: UserOffersProvider,
    get_session_offers: SessionOffersProvider,
    basket: object,
    user: object | None = None,
    request: object | None = None,
) -> SemanticSequence:
    return _project_offers(
        raw_get_offers(
            get_site_offers,
            get_basket_offers,
            get_user_offers,
            get_session_offers,
            basket,
            user,
            request,
        )
    )


def mutant_get_offers_semantic(
    get_site_offers: SiteOffersProvider,
    get_basket_offers: BasketOffersProvider,
    get_user_offers: UserOffersProvider,
    get_session_offers: SessionOffersProvider,
    basket: object,
    user: object | None = None,
    request: object | None = None,
) -> SemanticSequence:
    return _project_offers(
        mutant_get_offers(
            get_site_offers,
            get_basket_offers,
            get_user_offers,
            get_session_offers,
            basket,
            user,
            request,
        )
    )
