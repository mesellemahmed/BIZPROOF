def is_authenticated(self):
    """Checks for a valid authentication."""
    return self.token is not None and utils.is_token_valid(self.token)
