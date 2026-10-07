    def delete(self, user_id, access_token_id):
        """Delete specific access token.

        DELETE /v3/users/{user_id}/OS-OAUTH1/access_tokens/{access_token_id}
        """
        ENFORCER.enforce_call(
            action='identity:ec2_delete_credential',
            build_target=_build_enforcer_target_data_owner_and_user_id_match,
        )
        _block_delegated_token(self.oslo_context, self.auth_context['token'])
        access_token = PROVIDERS.oauth_api.get_access_token(access_token_id)
        reason = (
            'Invalidating the token cache because an access token for '
            'consumer {consumer_id} has been deleted. Authorization for '
            'users with OAuth tokens will be recalculated and enforced '
            'accordingly the next time they authenticate or validate a '
            'token.'.format(consumer_id=access_token['consumer_id'])
        )
        notifications.invalidate_token_cache_notification(reason)
        PROVIDERS.oauth_api.delete_access_token(
            user_id, access_token_id, initiator=self.audit_initiator
        )
        return None, http.client.NO_CONTENT
