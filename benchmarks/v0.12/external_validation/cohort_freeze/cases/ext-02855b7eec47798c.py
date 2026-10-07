def is_job_active(self, status: str) -> bool:
    life_cycle_state = status.split(":", 1)[0]
    return life_cycle_state in (
        "PENDING",
        "QUEUED",
        "RUNNING",
        "TERMINATING",
        "BLOCKED",
        "WAITING_FOR_RETRY",
    )
