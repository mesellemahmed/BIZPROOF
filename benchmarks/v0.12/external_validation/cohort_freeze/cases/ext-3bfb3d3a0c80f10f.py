def async_reconcile_missing_address_issue(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Create or clear the repair from the entry's stored data alone.

    The issue is not persistent and unload deletes it, so paths that cannot
    consult the cloud's fresh device list — setup before the cloud is
    reached, a reload whose unload failed — reconcile it from the cached
    credentials and stored addresses instead.
    """
    addresses: dict[str, str] = entry.data.get(CONF_ADDRESSES, {})
    credentials: dict[str, dict[str, str]] = entry.data.get(CONF_CREDENTIALS, {})
    if any(
        dr.format_mac(cred["mac"]) not in addresses
        for cred in credentials.values()
        if has_full_credentials(cred)
    ):
        async_create_missing_address_issue(hass, entry.entry_id)
    else:
        ir.async_delete_issue(hass, DOMAIN, f"missing_address_{entry.entry_id}")
