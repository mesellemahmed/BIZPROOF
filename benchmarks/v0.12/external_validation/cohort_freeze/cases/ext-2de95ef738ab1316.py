def build_guest_token_audit_payload(
    issuer_user_id: Optional[int],
    source_ip: Optional[str],
    body: dict[str, Any],
    token: str,
    header_name: str = "X-GuestToken",
    header_budget_bytes: object = None,
) -> dict[str, Any]:
    """Build security-relevant metadata for a guest-token issuance event.

    Captures who issued the token, from where, what it grants, and a hash of
    the issued token (never the raw token) so a later investigation into a
    misissued or over-scoped token can be scoped from the audit log.
    """
    resources = body.get("resources") or []
    rls = body.get("rls") or []
    token_bytes = len(token.encode("utf-8"))
    # HTTP/1-style accounting: name + colon-space + value + CRLF.
    header_bytes = token_bytes + len(header_name.encode("utf-8")) + 4
    # Match JavaScript's positive safe-integer budget, without coercing settings.
    # Invalid deployment values must not turn successful issuance into an error.
    budget = (
        int(header_budget_bytes)
        if isinstance(header_budget_bytes, (int, float))
        and not isinstance(header_budget_bytes, bool)
        and 0 < header_budget_bytes <= 2**53 - 1
        and int(header_budget_bytes) == header_budget_bytes
        else None
    )
    return {
        "token_bytes": token_bytes,
        "header_bytes": header_bytes,
        "header_budget_bytes": budget,
        "header_budget_exceeded": budget is not None and header_bytes > budget,
        "issuer_user_id": issuer_user_id,
        "source_ip": source_ip,
        "resources": [
            f"{resource.get('type')}:{resource.get('id')}" for resource in resources
        ],
        "datasets": body.get("datasets"),
        # RLS clauses can carry data values; record only the datasets in scope
        # and the rule count, not the clause text.
        "rls_datasets": [rule.get("dataset") for rule in rls],
        "rls_rule_count": len(rls),
        # Hash, not the raw token, so the log can be correlated without
        # becoming a credential store.
        "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
    }
