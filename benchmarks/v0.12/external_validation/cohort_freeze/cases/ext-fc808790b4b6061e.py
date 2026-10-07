    async def get_current_hosts_in_room_ordered(self, room_id: str) -> tuple[str, ...]:
        """Get current hosts in room based on current state.

        Blocks until we have full state for the given room. This only happens for rooms
        with partial state.

        Returns:
            A list of hosts in the room, sorted by longest in the room first. (aka.
            sorted by join with the lowest depth first).
        """

        await self._partial_state_room_tracker.await_full_state(room_id)

        return await self.stores.main.get_current_hosts_in_room_ordered(room_id)
