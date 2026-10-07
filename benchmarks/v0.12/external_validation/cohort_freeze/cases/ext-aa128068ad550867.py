def resolve_shipping_zone(_root, info: ResolveInfo, *, id, channel=None):
    _, id = from_global_id_or_error(id, ShippingZone)
    instance = (
        models.ShippingZone.objects.using(
            get_database_connection_name(info.context)
        )
        .filter(id=id)
        .first()
    )
    return ChannelContext(node=instance, channel_slug=channel) if instance else None
