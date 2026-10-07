"""Structured semantic values introduced by BIZPROOF V0.12.

The module deliberately models observable business semantics rather
than arbitrary Python object internals.

It does not alter or reinterpret any V0.11 certification result.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import TypeAlias


class UnsupportedSemanticValue(TypeError):
    """Raised when no explicit V0.12 semantic encoding exists."""


class SequenceKind(StrEnum):
    """Container identity preserved by the semantic projection."""

    LIST = "LIST"
    TUPLE = "TUPLE"


class TemporalKind(StrEnum):
    """Supported temporal observation kinds."""

    DATE = "DATE"
    DATETIME = "DATETIME"


@dataclass(frozen=True, slots=True)
class SemanticReference:
    """Opaque typed identity for a domain object.

    BIZPROOF does not inspect arbitrary framework object state.
    A caller must provide an explicit identity contract.
    """

    type_name: str
    identity: str | int

    def __post_init__(self) -> None:
        if not self.type_name:
            raise ValueError("reference type_name must be non-empty")


@dataclass(frozen=True, slots=True)
class SemanticTemporal:
    """Canonical temporal value."""

    kind: TemporalKind
    iso_value: str


@dataclass(frozen=True, slots=True)
class SemanticRecord:
    """Named structured value with explicit observable fields."""

    type_name: str
    fields: tuple[tuple[str, SemanticValue], ...]

    def __post_init__(self) -> None:
        if not self.type_name:
            raise ValueError("record type_name must be non-empty")

        names = [name for name, _ in self.fields]

        if len(names) != len(set(names)):
            raise ValueError("record field names must be unique")


@dataclass(frozen=True, slots=True)
class SemanticSequence:
    """Finite ordered semantic sequence."""

    kind: SequenceKind
    items: tuple[SemanticValue, ...]


SemanticScalar: TypeAlias = bool | int | str | SemanticReference | SemanticTemporal | None

SemanticValue: TypeAlias = SemanticScalar | SemanticSequence | SemanticRecord

ReferenceEncoder: TypeAlias = Callable[
    [object],
    SemanticReference | None,
]


def normalize_semantic_value(
    value: object,
    *,
    reference_encoder: ReferenceEncoder | None = None,
    max_sequence_length: int = 16,
) -> SemanticValue:
    """Convert an observable result into the V0.12 semantic domain.

    The conversion is intentionally conservative.

    Arbitrary domain objects are rejected unless an explicit
    ``reference_encoder`` supplies a stable typed identity.
    """

    if max_sequence_length < 0:
        raise ValueError("max_sequence_length must be non-negative")

    if value is None:
        return None

    # bool must precede int because bool is an int subclass.
    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        return value

    if isinstance(value, datetime):
        return SemanticTemporal(
            kind=TemporalKind.DATETIME,
            iso_value=value.isoformat(),
        )

    if isinstance(value, date):
        return SemanticTemporal(
            kind=TemporalKind.DATE,
            iso_value=value.isoformat(),
        )

    if isinstance(value, list | tuple):
        if len(value) > max_sequence_length:
            raise UnsupportedSemanticValue(
                f"sequence length exceeds frozen V0.12 bound: {len(value)} > {max_sequence_length}"
            )

        kind = SequenceKind.LIST if isinstance(value, list) else SequenceKind.TUPLE

        return SemanticSequence(
            kind=kind,
            items=tuple(
                normalize_semantic_value(
                    item,
                    reference_encoder=reference_encoder,
                    max_sequence_length=max_sequence_length,
                )
                for item in value
            ),
        )

    if reference_encoder is not None:
        reference = reference_encoder(value)

        if reference is not None:
            return reference

    raise UnsupportedSemanticValue(
        f"no explicit semantic encoding for {type(value).__module__}.{type(value).__qualname__}"
    )


def semantic_equal(
    left: SemanticValue,
    right: SemanticValue,
) -> bool:
    """Extensional equality inside the V0.12 semantic domain."""

    return left == right


def _jsonable(
    value: SemanticValue,
) -> object:
    if value is None:
        return {
            "kind": "NULL",
        }

    if isinstance(value, bool):
        return {
            "kind": "BOOL",
            "value": value,
        }

    if isinstance(value, int):
        return {
            "kind": "INT",
            "value": value,
        }

    if isinstance(value, str):
        return {
            "kind": "TEXT",
            "value": value,
        }

    if isinstance(value, SemanticReference):
        return {
            "kind": "REFERENCE",
            "type_name": value.type_name,
            "identity": value.identity,
        }

    if isinstance(value, SemanticTemporal):
        return {
            "kind": value.kind.value,
            "value": value.iso_value,
        }

    if isinstance(value, SemanticRecord):
        return {
            "kind": "RECORD",
            "type_name": value.type_name,
            "fields": [
                {
                    "name": name,
                    "value": _jsonable(field_value),
                }
                for name, field_value in value.fields
            ],
        }

    if isinstance(value, SemanticSequence):
        return {
            "kind": value.kind.value,
            "items": [_jsonable(item) for item in value.items],
        }

    raise AssertionError(f"unreachable semantic value: {value!r}")


def semantic_fingerprint(
    value: SemanticValue,
) -> str:
    """Stable serialized observation for evidence artifacts."""

    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def semantic_observation(
    value: object,
    *,
    reference_encoder: ReferenceEncoder | None = None,
    max_sequence_length: int = 16,
) -> tuple[SemanticValue, str]:
    """Normalize a runtime result and return its stable evidence form."""

    normalized = normalize_semantic_value(
        value,
        reference_encoder=reference_encoder,
        max_sequence_length=max_sequence_length,
    )

    return (
        normalized,
        semantic_fingerprint(normalized),
    )
