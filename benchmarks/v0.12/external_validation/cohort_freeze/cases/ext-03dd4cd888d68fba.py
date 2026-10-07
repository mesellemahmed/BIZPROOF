async def _async_get_trigger_platform(
    hass: HomeAssistant, trigger_key: str
) -> tuple[str, TriggerProtocol]:
    platform_and_sub_type = trigger_key.split(".")
    platform = platform_and_sub_type[0]
    # Only apply aliases for old-style triggers (no sub_type).
    # New-style triggers (e.g. "event.received") use the integration domain directly.
    if len(platform_and_sub_type) == 1:
        platform = _PLATFORM_ALIASES.get(platform, platform)

    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise probatio.Invalid(f"Invalid trigger '{trigger_key}' specified") from None
    try:
        platform_module = await integration.async_get_platform("trigger")
    except ImportError:
        raise probatio.Invalid(
            f"Integration '{platform}' does not provide trigger support"
        ) from None

    # Ensure triggers are registered so descriptions can be loaded
    await _register_trigger_platform(hass, platform, platform_module)

    return platform, platform_module
