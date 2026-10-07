def _refresh_last_active_date(request: AuthenticatedHttpRequest) -> None:
    """Update last_active_date if it is more than a day old."""

    profile = request.profile
    if profile.last_active_date is None or (now() - profile.last_active_date).days > 0:
        profile.last_active_date = now()
        profile.save()

        # Also modify session to trigger session cookie refresh
        # and push forward its expiry date:
        request.session["last_active"] = profile.last_active_date.timestamp()
