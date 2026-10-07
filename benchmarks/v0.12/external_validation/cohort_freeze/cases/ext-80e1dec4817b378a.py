def get_tracking_url(cls, cursor: Cursor) -> str | None:
    with contextlib.suppress(AttributeError):
        if cursor.last_query_id:
            # pylint: disable=protected-access, line-too-long
            return f"{cursor._protocol}://{cursor._host}:{cursor._port}/ui/query.html?{cursor.last_query_id}"
    return None
