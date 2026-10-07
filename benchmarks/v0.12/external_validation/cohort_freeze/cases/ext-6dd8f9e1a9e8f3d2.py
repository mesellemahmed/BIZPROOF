async def async_media_previous_track(self) -> None:
    """Send previous channel command."""
    await async_device_command(self._device.send_key(RemoteKey.CH_DOWN))
