from datetime import date, datetime

import pytest

from bizproof.semantic_values_v012 import (
    SemanticReference,
    SemanticSequence,
    SemanticTemporal,
    SequenceKind,
    TemporalKind,
    UnsupportedSemanticValue,
    normalize_semantic_value,
    semantic_equal,
    semantic_fingerprint,
    semantic_observation,
)


class _DomainObject:
    def __init__(self, pk: int) -> None:
        self.pk = pk


def _reference_encoder(
    value: object,
) -> SemanticReference | None:
    if isinstance(value, _DomainObject):
        return SemanticReference(
            type_name="DomainObject",
            identity=value.pk,
        )

    return None


def test_text_value_is_first_class_semantic_value() -> None:
    assert normalize_semantic_value("vip") == "vip"

    assert semantic_equal(
        normalize_semantic_value("vip"),
        normalize_semantic_value("vip"),
    )

    assert not semantic_equal(
        normalize_semantic_value("vip"),
        normalize_semantic_value("standard"),
    )


def test_list_semantics_preserve_order() -> None:
    observed = normalize_semantic_value(["a", "b", "c"])

    assert observed == SemanticSequence(
        kind=SequenceKind.LIST,
        items=("a", "b", "c"),
    )

    assert not semantic_equal(
        observed,
        normalize_semantic_value(["c", "b", "a"]),
    )


def test_tuple_and_list_remain_distinct() -> None:
    as_list = normalize_semantic_value([1, 2])

    as_tuple = normalize_semantic_value((1, 2))

    assert as_list == SemanticSequence(
        kind=SequenceKind.LIST,
        items=(1, 2),
    )

    assert as_tuple == SemanticSequence(
        kind=SequenceKind.TUPLE,
        items=(1, 2),
    )

    assert not semantic_equal(
        as_list,
        as_tuple,
    )


def test_list_of_domain_objects_uses_explicit_identity_contract() -> None:
    observed = normalize_semantic_value(
        [
            _DomainObject(10),
            _DomainObject(20),
        ],
        reference_encoder=_reference_encoder,
    )

    assert observed == SemanticSequence(
        kind=SequenceKind.LIST,
        items=(
            SemanticReference(
                type_name="DomainObject",
                identity=10,
            ),
            SemanticReference(
                type_name="DomainObject",
                identity=20,
            ),
        ),
    )


def test_domain_object_without_identity_contract_is_rejected() -> None:
    with pytest.raises(UnsupportedSemanticValue):
        normalize_semantic_value(_DomainObject(10))


def test_single_domain_object_reference() -> None:
    observed = normalize_semantic_value(
        _DomainObject(42),
        reference_encoder=_reference_encoder,
    )

    assert observed == SemanticReference(
        type_name="DomainObject",
        identity=42,
    )


def test_optional_none_is_explicit() -> None:
    assert normalize_semantic_value(None) is None


def test_date_value_is_canonical() -> None:
    observed = normalize_semantic_value(
        date(
            2026,
            9,
            30,
        )
    )

    assert observed == SemanticTemporal(
        kind=TemporalKind.DATE,
        iso_value="2026-09-30",
    )


def test_datetime_value_is_canonical() -> None:
    observed = normalize_semantic_value(
        datetime(
            2026,
            9,
            30,
            12,
            30,
            15,
        )
    )

    assert observed == SemanticTemporal(
        kind=TemporalKind.DATETIME,
        iso_value="2026-09-30T12:30:15",
    )


def test_sequence_bound_is_explicit() -> None:
    with pytest.raises(UnsupportedSemanticValue):
        normalize_semantic_value(
            [1, 2, 3],
            max_sequence_length=2,
        )


def test_negative_sequence_bound_is_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_semantic_value(
            [],
            max_sequence_length=-1,
        )


def test_nested_semantic_values_are_supported() -> None:
    observed = normalize_semantic_value(
        [
            ("x", 1),
            ("y", 2),
        ]
    )

    assert observed == SemanticSequence(
        kind=SequenceKind.LIST,
        items=(
            SemanticSequence(
                kind=SequenceKind.TUPLE,
                items=("x", 1),
            ),
            SemanticSequence(
                kind=SequenceKind.TUPLE,
                items=("y", 2),
            ),
        ),
    )


def test_fingerprint_is_stable_and_type_sensitive() -> None:
    list_value = normalize_semantic_value(["x", "y"])

    tuple_value = normalize_semantic_value(("x", "y"))

    assert semantic_fingerprint(list_value) == (
        '{"items":[{"kind":"TEXT","value":"x"},{"kind":"TEXT","value":"y"}],"kind":"LIST"}'
    )

    assert semantic_fingerprint(list_value) != semantic_fingerprint(tuple_value)


def test_semantic_observation_returns_value_and_evidence() -> None:
    value, evidence = semantic_observation("accepted")

    assert value == "accepted"

    assert evidence == ('{"kind":"TEXT","value":"accepted"}')
