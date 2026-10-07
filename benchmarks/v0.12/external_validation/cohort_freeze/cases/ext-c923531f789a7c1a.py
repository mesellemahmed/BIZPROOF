def get_request_token_secret(self, client_key, token, request):
    token_ref = PROVIDERS.oauth_api.get_request_token(token)
    return token_ref['request_secret']
