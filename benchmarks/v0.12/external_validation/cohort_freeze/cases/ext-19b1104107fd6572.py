def perform_heartbeat(job: Job, heartbeat_callback: Callable[..., None], only_if_necessary: bool) -> None:
    """
    Perform heartbeat for the Job passed to it,optionally checking if it is necessary.

    :param job: job to perform heartbeat for
    :param heartbeat_callback: callback to run by the heartbeat
    :param only_if_necessary: only heartbeat if it is necessary (i.e. if there are things to run for
        triggerer for example)
    """
    seconds_remaining: float = 0.0
    if job.latest_heartbeat and job.heartrate:
        seconds_remaining = job.heartrate - (timezone.utcnow() - job.latest_heartbeat).total_seconds()
    if seconds_remaining > 0 and only_if_necessary:
        return
    job.heartbeat(heartbeat_callback=heartbeat_callback)
