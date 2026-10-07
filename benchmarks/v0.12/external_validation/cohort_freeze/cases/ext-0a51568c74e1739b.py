def hvac_action(self) -> HVACAction | None:
    """Return the current hvac action."""
    action = HVAC_ACTIONS.get(self.device.operation_status.mode)
    if action == HVACAction.OFF and self.hvac_mode != HVACMode.OFF:
        action = HVACAction.IDLE
    return action
