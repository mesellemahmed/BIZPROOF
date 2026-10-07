def __init__(self, calendar, filename, **kwargs):
    kwargs.setdefault("content_type", "text/calendar")
    super().__init__(serialize_calendar(calendar), **kwargs)
    self["Content-Disposition"] = (
        f'attachment; filename="{safe_filename(filename)}.ics"'
    )
