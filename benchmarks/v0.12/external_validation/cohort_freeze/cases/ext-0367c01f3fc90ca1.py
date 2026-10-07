async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TelegramBotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform."""
    async_add_entities([TelegramBotEventEntity(config_entry)])
