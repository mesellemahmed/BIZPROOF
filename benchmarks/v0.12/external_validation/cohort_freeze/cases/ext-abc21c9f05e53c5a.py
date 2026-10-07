def copy_and_replace(self, key: StreamKeyType, new_value: Any) -> "StreamToken":
    return attr.evolve(self, **{key.value: new_value})
