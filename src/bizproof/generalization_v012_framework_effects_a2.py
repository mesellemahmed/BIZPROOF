"""V0.12 framework-effect and structured-response semantics."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SemanticEffect:
    """One explicit externally observable dependency interaction."""

    kind: str
    target: str
    arguments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticEffectTrace:
    """Ordered external-effect trace."""

    effects: tuple[SemanticEffect, ...]


@dataclass(frozen=True, slots=True)
class SemanticFrameworkResponse:
    """Framework-independent extensional response observation."""

    response_type: str
    payload_json: str


class EffectRecorder:
    def __init__(self) -> None:
        self.records: list[SemanticEffect] = []

    def record(
        self,
        kind: str,
        target: str,
        *arguments: object,
    ) -> None:
        self.records.append(
            SemanticEffect(
                kind=kind,
                target=target,
                arguments=tuple(repr(value) for value in arguments),
            )
        )

    def freeze(self) -> SemanticEffectTrace:
        return SemanticEffectTrace(effects=tuple(self.records))


class RedisPipeline:
    def __init__(
        self,
        recorder: EffectRecorder,
    ) -> None:
        self.recorder = recorder

    def hdel(
        self,
        key: str,
        member: str,
    ) -> None:
        self.recorder.record(
            "REDIS_HDEL",
            key,
            member,
        )

    def execute(self) -> None:
        self.recorder.record(
            "REDIS_PIPELINE_EXECUTE",
            "redis",
        )


class RedisConnection:
    def __init__(
        self,
        recorder: EffectRecorder,
    ) -> None:
        self.recorder = recorder

    def pipeline(
        self,
    ) -> RedisPipeline:
        self.recorder.record(
            "REDIS_PIPELINE_OPEN",
            "redis",
        )
        return RedisPipeline(self.recorder)


class RedisBackend:
    def __init__(
        self,
        recorder: EffectRecorder,
    ) -> None:
        self.recorder = recorder

    def get_redis_connection(
        self,
        alias: str,
    ) -> RedisConnection:
        self.recorder.record(
            "REDIS_CONNECT",
            alias,
        )
        return RedisConnection(self.recorder)


class AvailabilityHook:
    def __init__(
        self,
        recorder: EffectRecorder,
    ) -> None:
        self.recorder = recorder

    def __call__(
        self,
        *,
        now_dt: object | None = None,
    ) -> None:
        self.recorder.record(
            "AVAILABILITY_REFRESH",
            "quota",
            now_dt,
        )


def raw_rebuild_cache(
    has_redis: bool,
    backend: RedisBackend,
    event_id: object,
    pk: object,
    now_dt: object | None,
    availability: AvailabilityHook,
) -> None:
    if has_redis:
        rc = backend.get_redis_connection("redis")
        p = rc.pipeline()
        p.hdel(
            f"quotas:{event_id}:availabilitycache",
            str(pk),
        )
        p.hdel(
            f"quotas:{event_id}:availabilitycache:nocw",
            str(pk),
        )
        p.hdel(
            f"quotas:{event_id}:availabilitycache:igcl",
            str(pk),
        )
        p.hdel(
            f"quotas:{event_id}:availabilitycache:nocw:igcl",
            str(pk),
        )
        p.execute()
        availability(now_dt=now_dt)


def adapt_rebuild_cache(
    has_redis: bool,
    event_id: object,
    pk: object,
    now_dt: object | None,
) -> SemanticEffectTrace:
    recorder = EffectRecorder()

    raw_rebuild_cache(
        has_redis,
        RedisBackend(recorder),
        event_id,
        pk,
        now_dt,
        AvailabilityHook(recorder),
    )

    return recorder.freeze()


def mutant_rebuild_cache(
    has_redis: bool,
    event_id: object,
    pk: object,
    now_dt: object | None,
) -> SemanticEffectTrace:
    recorder = EffectRecorder()

    if has_redis:
        backend = RedisBackend(recorder)

        rc = backend.get_redis_connection("redis")

        p = rc.pipeline()

        p.hdel(
            f"quotas:{event_id}:availabilitycache",
            str(pk),
        )

        p.hdel(
            f"quotas:{event_id}:availabilitycache:nocw",
            str(pk),
        )

        p.hdel(
            f"quotas:{event_id}:availabilitycache:igcl",
            str(pk),
        )

        # Frozen mutant:
        # omit the fourth invalidation.
        p.execute()

        AvailabilityHook(recorder)(now_dt=now_dt)

    return recorder.freeze()


ResponseConstructor = Callable[
    [dict[str, object]],
    SemanticFrameworkResponse,
]


def canonical_response_constructor(
    payload: dict[str, object],
) -> SemanticFrameworkResponse:
    return SemanticFrameworkResponse(
        response_type="JsonResponse",
        payload_json=json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ),
    )


def raw_json_response(
    rendered_html: str,
    messages_payload: object,
    response_ctor: ResponseConstructor,
) -> SemanticFrameworkResponse:
    basket_html = rendered_html

    return response_ctor(
        {
            "content_html": basket_html,
            "messages": messages_payload,
        }
    )


def adapt_json_response(
    rendered_html: str,
    messages_payload: object,
) -> SemanticFrameworkResponse:
    return raw_json_response(
        rendered_html,
        messages_payload,
        canonical_response_constructor,
    )


def mutant_json_response(
    rendered_html: str,
    messages_payload: object,
) -> SemanticFrameworkResponse:
    basket_html = rendered_html

    return canonical_response_constructor(
        {
            "content": basket_html,
            "messages": messages_payload,
        }
    )
