    async def user_set_consent_server_notice_sent(
        self, user_id: str, consent_version: str
    ) -> None:
        """Updates the user table to record that we have sent the user a server
        notice about privacy policy consent

        Args:
            user_id: full mxid of the user to update
            consent_version: version of the policy we have notified the user about

        Raises:
            StoreError(404) if user not found
        """

        def f(txn: LoggingTransaction) -> None:
            self.db_pool.simple_update_one_txn(
                txn,
                table="users",
                keyvalues={"name": user_id},
                updatevalues={"consent_server_notice_sent": consent_version},
            )
            self._invalidate_cache_and_stream(txn, self.get_user_by_id, (user_id,))

        await self.db_pool.runInteraction("user_set_consent_server_notice_sent", f)
