def resolve_private_metafield(
    root: ModelWithMetadata | BaseContext[ModelWithMetadata],
    info: ResolveInfo,
    *,
    key: str,
) -> str | None:
    instance = _get_metadata_instance(root)
    check_private_metadata_privilege(instance, info)
    return instance.private_metadata.get(key)
