def values_list(self, *fields, **kwargs):
    # `values_list()` reaches `Query.set_values()` without going through `values()`, so it needs its own check.
    if not fields:
        fields = self._non_sensitive_field_names() or ()
    else:
        self._check_field_names(fields)
    return super().values_list(*fields, **kwargs)
