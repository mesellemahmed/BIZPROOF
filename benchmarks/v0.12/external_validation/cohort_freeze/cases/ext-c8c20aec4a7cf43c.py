def resolve_permission_group(info, id):
    return (
        models.Group.objects.using(get_database_connection_name(info.context))
        .filter(id=id)
        .first()
    )
