def give_creator_permissions(user, obj):
    from awx.main.signals import disable_activity_stream

    assignment = RoleDefinition.objects.give_creator_permissions(user, obj)
    if assignment:
        with disable_rbac_sync():
            old_role = get_role_from_object_role(assignment.object_role)
            if old_role is None:
                return
            # The new-side assignment above is already recorded by
            # record_role_assignment_activity_stream. Suppress activity stream for this
            # mirrored write so it isn't recorded a second time.
            with disable_activity_stream():
                old_role.members.add(user)
