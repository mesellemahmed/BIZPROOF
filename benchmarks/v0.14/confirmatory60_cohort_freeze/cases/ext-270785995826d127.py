def host_metric_summary_monthly():
    """Run cleanup host metrics summary monthly task each week"""
    if is_run_threshold_reached(getattr(settings, 'HOST_METRIC_SUMMARY_TASK_LAST_TS', None), getattr(settings, 'HOST_METRIC_SUMMARY_TASK_INTERVAL', 7) * 86400):
        logger.info(f"Executing host_metric_summary_monthly, last ran at {getattr(settings, 'HOST_METRIC_SUMMARY_TASK_LAST_TS', '---')}")
        HostMetricSummaryMonthlyTask().execute()
        logger.info("Finished host_metric_summary_monthly")
