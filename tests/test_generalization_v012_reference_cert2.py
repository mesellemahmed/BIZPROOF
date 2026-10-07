from datetime import datetime

from bizproof.generalization_v012_reference_cert2 import (
    OfferProjection,
    adapt_get_offers,
    adapt_ticket_download_date,
    mutant_get_offers_semantic,
    mutant_ticket_download_date_semantic,
)
from bizproof.semantic_values_v012 import (
    SemanticReference,
    SemanticSequence,
    SemanticTemporal,
    SequenceKind,
    TemporalKind,
)


class _Subevent:
    def __init__(
        self,
        key: int,
    ) -> None:
        self.key = key


class _Subevents:
    def __init__(
        self,
        values: list[_Subevent],
    ) -> None:
        self.values = values

    def filter(
        self,
        *,
        id__in: list[int],
    ) -> list[_Subevent]:
        wanted = set(id__in)

        return [value for value in self.values if value.key in wanted]


class _Positions:
    def __init__(
        self,
        ids: list[int],
    ) -> None:
        self.ids = ids

    def values_list(
        self,
        field: str,
        *,
        flat: bool,
    ) -> list[int]:
        assert field == "subevent"
        assert flat is True
        return list(self.ids)


class _RelativeDate:
    def __init__(
        self,
        values: dict[
            int,
            datetime,
        ],
    ) -> None:
        self.values = values

    def datetime(
        self,
        target: object,
    ) -> datetime:
        key = target.key
        return self.values[key]


class _Settings:
    def __init__(
        self,
        value: _RelativeDate | None,
    ) -> None:
        self.value = value

    def get(
        self,
        key: str,
        *,
        as_type: object,
    ) -> _RelativeDate | None:
        assert key == "ticket_download_date"
        assert as_type is object
        return self.value


class _Event:
    def __init__(
        self,
        *,
        settings: _Settings,
        has_subevents: bool,
        subevents: _Subevents,
        key: int = 0,
    ) -> None:
        self.settings = settings
        self.has_subevents = has_subevents
        self.subevents = subevents
        self.key = key


def test_ticket_download_date_uses_earliest_subevent() -> None:
    d1 = datetime(
        2026,
        10,
        10,
    )
    d2 = datetime(
        2026,
        10,
        5,
    )

    relative = _RelativeDate(
        {
            1: d1,
            2: d2,
        }
    )

    event = _Event(
        settings=_Settings(relative),
        has_subevents=True,
        subevents=_Subevents(
            [
                _Subevent(1),
                _Subevent(2),
            ]
        ),
    )

    positions = _Positions([1, 2])

    result = adapt_ticket_download_date(
        event,
        positions,
        object,
    )

    assert result == SemanticTemporal(
        kind=TemporalKind.DATETIME,
        iso_value=("2026-10-05T00:00:00"),
    )


def test_ticket_download_date_none_is_preserved() -> None:
    event = _Event(
        settings=_Settings(None),
        has_subevents=False,
        subevents=_Subevents([]),
    )

    assert (
        adapt_ticket_download_date(
            event,
            _Positions([]),
            object,
        )
        is None
    )


def test_ticket_download_mutant_is_refuted() -> None:
    relative = _RelativeDate(
        {
            1: datetime(
                2026,
                10,
                1,
            ),
            2: datetime(
                2026,
                10,
                20,
            ),
        }
    )

    event = _Event(
        settings=_Settings(relative),
        has_subevents=True,
        subevents=_Subevents(
            [
                _Subevent(1),
                _Subevent(2),
            ]
        ),
    )

    positions = _Positions([1, 2])

    assert adapt_ticket_download_date(
        event,
        positions,
        object,
    ) != mutant_ticket_download_date_semantic(
        event,
        positions,
        object,
    )


def test_offer_sequence_is_priority_ordered() -> None:
    result = adapt_get_offers(
        get_site_offers=lambda: [
            OfferProjection(
                10,
                1,
            )
        ],
        get_basket_offers=lambda basket, user: [
            OfferProjection(
                20,
                10,
            )
        ],
        get_user_offers=lambda user: [],
        get_session_offers=lambda request: [
            OfferProjection(
                30,
                5,
            )
        ],
        basket=object(),
    )

    assert result == SemanticSequence(
        kind=SequenceKind.LIST,
        items=(
            SemanticReference(
                type_name="Offer",
                identity=20,
            ),
            SemanticReference(
                type_name="Offer",
                identity=30,
            ),
            SemanticReference(
                type_name="Offer",
                identity=10,
            ),
        ),
    )


def test_offer_mutant_is_refuted() -> None:
    kwargs = {
        "get_site_offers": lambda: [
            OfferProjection(
                1,
                1,
            )
        ],
        "get_basket_offers": lambda basket, user: [
            OfferProjection(
                2,
                10,
            )
        ],
        "get_user_offers": lambda user: [],
        "get_session_offers": lambda request: [],
        "basket": object(),
    }

    assert adapt_get_offers(**kwargs) != mutant_get_offers_semantic(**kwargs)
