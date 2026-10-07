def transaction_cancelation_requested(
    self, transaction_data: "TransactionActionData", previous_value: Any
) -> None:
    self._request_transaction_action(
        transaction_data,
        WebhookEventSyncType.TRANSACTION_CANCELATION_REQUESTED,
    )
    return previous_value
