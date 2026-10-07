def apply_states_filters(sel: Select, start_day: float, end_day: float) -> Select:
    """Filter states by time range.

    Filters states that do not have an old state or new state (added / removed)
    Filters states that are in a continuous domain with a UOM.
    Filters states that do not have matching last_updated_ts and last_changed_ts.
    """
    return (
        sel.filter(
            (States.last_updated_ts > start_day) & (States.last_updated_ts < end_day)
        )
        .outerjoin(OLD_STATE, (States.old_state_id == OLD_STATE.state_id))
        .where(_missing_state_matcher())
        .where(_not_continuous_entity_matcher())
        .where(
            (States.last_updated_ts == States.last_changed_ts)
            | States.last_changed_ts.is_(None)
        )
        .outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
        .outerjoin(StatesMeta, (States.metadata_id == StatesMeta.metadata_id))
    )
