async def async_setup_entry(
    hass: HomeAssistant,
    entry: NotionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Notion sensors based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            NotionBinarySensor(
                coordinator,
                listener_id,
                sensor.uuid,
                sensor.bridge.id,
                description,
            )
            for listener_id, listener in coordinator.data.listeners.items()
            for description in BINARY_SENSOR_DESCRIPTIONS
            if description.listener_kind.value == listener.definition_id
            and (sensor := coordinator.data.sensors[listener.sensor_id])
        ]
    )
