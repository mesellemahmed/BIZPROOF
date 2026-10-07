def get_is_mfa_enabled(self, user: User) -> bool:
    mfa_adapter = get_mfa_adapter()
    return mfa_adapter.is_mfa_enabled(user)
