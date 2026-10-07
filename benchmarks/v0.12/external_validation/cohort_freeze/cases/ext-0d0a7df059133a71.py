    def delete(self, group_id, role_id):
        """Revoke a role from the group on the system.

        DELETE /system/groups/{group_id}/roles/{role_id}
        """
        ENFORCER.enforce_call(
            action='identity:revoke_system_grant_for_group',
            build_target=functools.partial(
                _build_enforcement_target, allow_non_existing=True
            ),
        )
        PROVIDERS.assignment_api.delete_system_grant_for_group(
            group_id, role_id
        )
        return None, http.client.NO_CONTENT
