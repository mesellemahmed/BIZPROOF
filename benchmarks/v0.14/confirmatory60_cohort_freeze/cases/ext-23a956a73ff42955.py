def gather_analytics():
    if is_run_threshold_reached(getattr(settings, 'AUTOMATION_ANALYTICS_LAST_GATHER', None), settings.AUTOMATION_ANALYTICS_GATHER_INTERVAL):
        analytics.gather()
