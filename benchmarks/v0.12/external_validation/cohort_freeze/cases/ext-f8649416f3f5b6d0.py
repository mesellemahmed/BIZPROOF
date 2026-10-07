async def _internal_update_data(self) -> Activity | None:
    """Retrieve latest activity."""
    if self._last_valid_update is None:
        now = dt_util.utcnow()
        startdate = now - timedelta(days=14)
        activities = await self._client.get_activities_in_period(
            startdate.date(), now.date()
        )
    else:
        activities = await self._client.get_activities_since(
            self._last_valid_update
        )

    today = dt_util.now().date()
    for activity in activities:
        if activity.date == today:
            self._previous_data = activity
            self._last_valid_update = activity.modified
            return activity
    if self._previous_data and self._previous_data.date == today:
        return self._previous_data
    return None
