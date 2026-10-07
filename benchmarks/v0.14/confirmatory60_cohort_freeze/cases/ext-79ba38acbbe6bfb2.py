def _get_notify_alert_extra_conditions(self, alarm_type=None):
    base = super()._get_notify_alert_extra_conditions(alarm_type)
    if alarm_type == 'email':
        return SQL("%s AND event.google_id IS NULL", base)
    return base
