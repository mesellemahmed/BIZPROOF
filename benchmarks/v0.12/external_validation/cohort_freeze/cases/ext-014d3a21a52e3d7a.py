def declare_config_options(self, declaration: Declaration, key: Key):
    declaration.annotate("expire_api_token plugin")
    key = key.expire_api_token.default_lifetime
    declaration.declare_int(key, 3600)
