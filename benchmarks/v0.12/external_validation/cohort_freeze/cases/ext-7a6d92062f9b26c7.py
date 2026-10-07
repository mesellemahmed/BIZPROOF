def _resolve_with_state(
    room_version: RoomVersion,
    unconflicted_state_ids: MutableStateMap[str],
    conflicted_state_ids: StateMap[set[str]],
    auth_event_ids: StateMap[str],
    state_map: dict[str, EventBase],
) -> MutableStateMap[str]:
    conflicted_state = {}
    for key, event_ids in conflicted_state_ids.items():
        events = [state_map[ev_id] for ev_id in event_ids if ev_id in state_map]
        if len(events) > 1:
            conflicted_state[key] = events
        elif len(events) == 1:
            unconflicted_state_ids[key] = events[0].event_id

    auth_events = {
        key: state_map[ev_id]
        for key, ev_id in auth_event_ids.items()
        if ev_id in state_map
    }

    try:
        resolved_state = _resolve_state_events(
            room_version, conflicted_state, auth_events
        )
    except Exception:
        logger.exception("Failed to resolve state")
        raise

    new_state = unconflicted_state_ids
    for key, event in resolved_state.items():
        new_state[key] = event.event_id

    return new_state
