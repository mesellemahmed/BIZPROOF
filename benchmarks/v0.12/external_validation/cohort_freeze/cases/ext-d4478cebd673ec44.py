def async_set_updated_data(self, data: None) -> None:
    """Manually update data and reset to the connected interval."""
    self.update_interval = UPDATE_INTERVAL_CONNECTED
    super().async_set_updated_data(data)
