    def __init__(
        self,
        knowledge_base_id: str,
        data_source_id: str,
        ingest_data_kwargs: dict[str, Any] | None = None,
        wait_for_completion: bool = True,
        waiter_delay: int = 60,
        waiter_max_attempts: int = 10,
        deferrable: bool = conf.getboolean("operators", "default_deferrable", fallback=False),
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.knowledge_base_id = knowledge_base_id
        self.data_source_id = data_source_id
        self.ingest_data_kwargs = ingest_data_kwargs or {}

        self.wait_for_completion = wait_for_completion
        self.waiter_delay = waiter_delay
        self.waiter_max_attempts = waiter_max_attempts
        self.deferrable = deferrable
        self.indexing_error_max_attempts = 5
        self.indexing_error_retry_delay = 5
