def rule(user, enabled: bool) -> bool:
    return user.is_staff and enabled
