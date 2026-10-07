from bizproof.generalization_v012_framework_effects_a2 import (
    SemanticEffect,
    SemanticFrameworkResponse,
    adapt_json_response,
    adapt_rebuild_cache,
    mutant_json_response,
    mutant_rebuild_cache,
)


def test_redis_effect_trace_when_enabled() -> None:
    trace = adapt_rebuild_cache(
        has_redis=True,
        event_id=7,
        pk=11,
        now_dt="NOW",
    )

    assert len(trace.effects) == 8

    assert trace.effects[0] == SemanticEffect(
        kind="REDIS_CONNECT",
        target="redis",
        arguments=(),
    )

    hdel = [effect for effect in trace.effects if effect.kind == "REDIS_HDEL"]

    assert len(hdel) == 4

    assert hdel[-1].target == ("quotas:7:availabilitycache:nocw:igcl")

    assert trace.effects[-1].kind == "AVAILABILITY_REFRESH"


def test_redis_effect_trace_when_disabled() -> None:
    trace = adapt_rebuild_cache(
        has_redis=False,
        event_id=7,
        pk=11,
        now_dt=None,
    )

    assert trace.effects == ()


def test_redis_mutant_is_distinct() -> None:
    assert adapt_rebuild_cache(
        True,
        7,
        11,
        "NOW",
    ) != mutant_rebuild_cache(
        True,
        7,
        11,
        "NOW",
    )


def test_structured_framework_response() -> None:
    result = adapt_json_response(
        "<div>basket</div>",
        {
            "info": "ok",
        },
    )

    assert isinstance(
        result,
        SemanticFrameworkResponse,
    )

    assert result.response_type == "JsonResponse"

    assert '"content_html":' in result.payload_json

    assert '"messages":' in result.payload_json


def test_response_fingerprint_is_deterministic() -> None:
    first = adapt_json_response(
        "x",
        {
            "b": 2,
            "a": 1,
        },
    )

    second = adapt_json_response(
        "x",
        {
            "a": 1,
            "b": 2,
        },
    )

    assert first == second


def test_response_mutant_is_distinct() -> None:
    assert adapt_json_response(
        "HTML",
        {
            "message": "hello",
        },
    ) != mutant_json_response(
        "HTML",
        {
            "message": "hello",
        },
    )
