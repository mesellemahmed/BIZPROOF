from bizproof.generalization_v012_transactional_save_a2 import (
    SaveEffect,
    transaction_aware_model_save,
)


def test_existing_normalization_and_pre_dirty() -> None:
    result = transaction_aware_model_save(
        code="",
        datetime_value=None,
        expires=None,
        organizer_id=None,
        event_organizer_id="ORG",
        pk_before=55,
        pk_after=55,
        status="PAID",
        pending_status="PENDING",
        paid_status="PAID",
        require_approval=False,
        initial_status_paid_or_pending=False,
        deferred_fields=(),
        update_fields={
            "status",
        },
        force_save_with_deferred_fields=False,
        using="DB",
        assigned_code="CODE",
        now_value="NOW",
        assigned_expires="EXPIRES",
        delegated_result="SAVED",
    )

    assert result.code == "CODE"
    assert result.datetime_value == "NOW"
    assert result.expires == "EXPIRES"
    assert result.organizer_id == "ORG"

    assert result.update_fields == frozenset(
        {
            "status",
            "last_modified",
            "code",
            "datetime",
            "expires",
            "organizer",
        }
    )

    assert result.effects[0] == SaveEffect(
        "PRE_SAVE_DIRTY",
        (
            (
                "pk",
                "55",
            ),
            (
                "using",
                "DB",
            ),
        ),
    )


def test_new_order_post_save_dirty() -> None:
    result = transaction_aware_model_save(
        code="C",
        datetime_value="D",
        expires="E",
        organizer_id="O",
        event_organizer_id="O",
        pk_before=None,
        pk_after=101,
        status="OPEN",
        pending_status="PENDING",
        paid_status="PAID",
        require_approval=False,
        initial_status_paid_or_pending=False,
        deferred_fields=(),
        update_fields=None,
        force_save_with_deferred_fields=False,
        using=None,
        assigned_code="CODE",
        now_value="NOW",
        assigned_expires="EXPIRES",
        delegated_result="SAVED",
    )

    assert [effect.kind for effect in result.effects] == [
        "DELEGATED_SAVE",
        "POST_SAVE_DIRTY",
    ]


def test_unsafe_deferred_save() -> None:
    result = transaction_aware_model_save(
        code="C",
        datetime_value="D",
        expires="E",
        organizer_id="O",
        event_organizer_id="O",
        pk_before=55,
        pk_after=55,
        status="PAID",
        pending_status="PENDING",
        paid_status="PAID",
        require_approval=False,
        initial_status_paid_or_pending=False,
        deferred_fields={
            "status",
        },
        update_fields=None,
        force_save_with_deferred_fields=False,
        using=None,
        assigned_code="CODE",
        now_value="NOW",
        assigned_expires="EXPIRES",
        delegated_result="SAVED",
    )

    assert result.unsafe_deferred_save is True

    assert result.effects == ()


def test_deferred_explicit_status_update_is_allowed() -> None:
    result = transaction_aware_model_save(
        code="C",
        datetime_value="D",
        expires="E",
        organizer_id="O",
        event_organizer_id="O",
        pk_before=55,
        pk_after=55,
        status="PAID",
        pending_status="PENDING",
        paid_status="PAID",
        require_approval=False,
        initial_status_paid_or_pending=False,
        deferred_fields={
            "status",
        },
        update_fields={
            "status",
        },
        force_save_with_deferred_fields=False,
        using=None,
        assigned_code="CODE",
        now_value="NOW",
        assigned_expires="EXPIRES",
        delegated_result="SAVED",
    )

    assert result.unsafe_deferred_save is False

    assert [effect.kind for effect in result.effects] == [
        "DELEGATED_SAVE",
    ]
