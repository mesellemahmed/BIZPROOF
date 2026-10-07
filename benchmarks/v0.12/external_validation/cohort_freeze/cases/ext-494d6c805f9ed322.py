def sms_limit(to: list[str], ctx: dict[str, Any]) -> None:
    send(make_message("sms-limit", to, ctx))
