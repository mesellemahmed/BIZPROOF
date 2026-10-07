    def load(cls, data: Any) -> PdConf:
        # Is it plain service_key value?
        if not data.startswith("{"):
            return cls.model_validate({"service_key": data})

        return super().model_validate_json(data)
