def assemble(
    cls,
    user_id,
    methods,
    system,
    project_id,
    domain_id,
    expires_at,
    audit_ids,
    trust_id,
    federated_group_ids,
    identity_provider_id,
    protocol_id,
    access_token_id,
    app_cred_id,
    thumbprint,
):
    b_user_id = cls.attempt_convert_uuid_hex_to_bytes(user_id)
    methods = auth_plugins.convert_method_list_to_integer(methods)
    b_project_id = cls.attempt_convert_uuid_hex_to_bytes(project_id)
    b_domain_id = cls.attempt_convert_uuid_hex_to_bytes(domain_id)
    expires_at_int = cls._convert_time_string_to_float(expires_at)
    b_audit_ids = list(map(cls.random_urlsafe_str_to_bytes, audit_ids))
    b_thumbprint = (False, thumbprint)
    return (
        b_user_id,
        methods,
        b_project_id,
        b_domain_id,
        expires_at_int,
        b_audit_ids,
        b_thumbprint,
    )
