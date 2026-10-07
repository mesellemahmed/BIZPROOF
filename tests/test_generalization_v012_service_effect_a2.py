from bizproof.generalization_v012_service_effect_a2 import (
    FrameworkEffect,
    cache_backed_service_result,
    ordered_basket_effect_trace,
)


def test_availability_cache_hit() -> None:
    result, cache, trace = cache_backed_service_result(
        pk=1,
        count_waitinglist=True,
        cache={
            1: (
                7,
                8,
            ),
            "_count_waitinglist": True,
        },
        service_result=(
            2,
            17,
        ),
        now_dt=None,
        allow_cache=False,
    )

    assert result == (
        7,
        8,
    )

    assert cache is not None

    assert trace == (
        FrameworkEffect(
            "CACHE_HIT",
            (
                (
                    "pk",
                    "1",
                ),
            ),
        ),
    )


def test_availability_policy_mismatch_clears() -> None:
    result, cache, trace = cache_backed_service_result(
        pk=1,
        count_waitinglist=True,
        cache={
            1: (
                99,
                99,
            ),
            "_count_waitinglist": False,
        },
        service_result=(
            2,
            17,
        ),
        now_dt="NOW",
        allow_cache=True,
    )

    assert result == (
        2,
        17,
    )

    assert cache == {
        1: (
            2,
            17,
        ),
        "_count_waitinglist": True,
    }

    assert trace[0].kind == "CACHE_CLEAR"

    assert trace[1].kind == "SERVICE_QUEUE"

    assert trace[2].kind == "SERVICE_COMPUTE"


def test_availability_without_cache() -> None:
    result, cache, trace = cache_backed_service_result(
        pk=1,
        count_waitinglist=True,
        cache=None,
        service_result=(
            2,
            17,
        ),
        now_dt=None,
        allow_cache=False,
    )

    assert result == (
        2,
        17,
    )

    assert cache is None

    assert [effect.kind for effect in trace] == [
        "SERVICE_QUEUE",
        "SERVICE_COMPUTE",
    ]


def test_ordered_basket_effect_trace() -> None:
    line, created, result, effects = ordered_basket_effect_trace(
        offers_before=("OFFER",),
        product="PRODUCT",
        quantity=2,
        cleaned_options=("OPT",),
        line="LINE",
        line_created=True,
        success_message="SUCCESS",
        user="USER",
        delegated_result="FORM_VALID",
    )

    assert line == "LINE"
    assert created is True
    assert result == "FORM_VALID"

    assert [effect.kind for effect in effects] == [
        "APPLIED_OFFERS",
        "ADD_PRODUCT",
        "MESSAGE_SUCCESS",
        "OFFER_MESSAGES",
        "ADD_SIGNAL",
        "SUPER_FORM_VALID",
    ]
