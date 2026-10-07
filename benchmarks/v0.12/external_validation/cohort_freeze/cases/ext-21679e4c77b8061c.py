    def store_search_entries_txn(
        self, txn: LoggingTransaction, entries: Iterable[SearchEntry]
    ) -> None:
        """Add entries to the search table

        Args:
            txn:
            entries: entries to be added to the table
        """
        if not self.hs.config.server.enable_search:
            return
        if isinstance(self.database_engine, PostgresEngine):
            sql = """
            INSERT INTO event_search
            (event_id, room_id, key, vector, stream_ordering, origin_server_ts)
            VALUES (?,?,?,to_tsvector('english', ?),?,?)
            """

            args1 = [
                (
                    entry.event_id,
                    entry.room_id,
                    entry.key,
                    _clean_value_for_search(entry.value),
                    entry.stream_ordering,
                    entry.origin_server_ts,
                )
                for entry in entries
            ]

            txn.execute_batch(sql, args1)

        elif isinstance(self.database_engine, Sqlite3Engine):
            self.db_pool.simple_insert_many_txn(
                txn,
                table="event_search",
                keys=("event_id", "room_id", "key", "value"),
                values=[
                    (
                        entry.event_id,
                        entry.room_id,
                        entry.key,
                        _clean_value_for_search(entry.value),
                    )
                    for entry in entries
                ],
            )

        else:
            # This should be unreachable.
            raise Exception("Unrecognized database engine")
