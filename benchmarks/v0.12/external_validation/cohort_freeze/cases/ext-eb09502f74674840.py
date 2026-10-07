def execute(self, sql: str, params: dict[str, Any] | None = None):
    with self._get_engine().begin() as conn:
        return conn.execute(sa.text(sql), params)
