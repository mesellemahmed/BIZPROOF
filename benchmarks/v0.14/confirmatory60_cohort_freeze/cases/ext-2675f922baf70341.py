def _recursive_escape(self, o, esc=conditional_escape):
    if isinstance(o, dict):
        return type(o)((esc(k), self._recursive_escape(v)) for (k, v) in dict.items(o))
    if isinstance(o, (list, tuple)):
        return type(o)(self._recursive_escape(v) for v in o)
    if isinstance(o, bool):
        return o
    try:
        return type(o)(esc(o))
    except (ValueError, TypeError):
        return self.default(o)
