def migrate_2_1_to_2_2(data: dict[str, Any]) -> None:
    """Migrate from schema 2.1 to schema 2.2."""
    if b_sensors := data.get("entities", {}).get(Platform.BINARY_SENSOR):
        for b_sensor in b_sensors.values():
            # "respond_to_read" was never used for binary_sensor and is not valid
            #  in the new schema. It was set as default in Store schema v1 and v2.1
            b_sensor["knx"].pop(CONF_RESPOND_TO_READ, None)
