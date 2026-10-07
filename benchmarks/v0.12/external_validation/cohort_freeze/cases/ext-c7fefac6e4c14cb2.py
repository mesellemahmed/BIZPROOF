def get_module_api(self) -> ModuleApi:
    return ModuleApi(self, self.get_auth_handler())
