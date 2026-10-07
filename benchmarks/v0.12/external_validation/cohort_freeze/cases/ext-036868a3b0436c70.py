def get_cache_key_failed_ip(ip: str) -> str:
    return f"login:fail:ip:{ip}"
