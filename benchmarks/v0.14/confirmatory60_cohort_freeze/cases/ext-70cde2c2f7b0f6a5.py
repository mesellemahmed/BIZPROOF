    def _filtered_list(self, endpoint, value):
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if self._check_for_int(value):
            return endpoint.get(id=int(value))

        options = self._cache.get_options(endpoint)
        identifier = next(field for field in options['search_fields'] if field in ('name', 'username', 'hostname'))
        if isinstance(value, list):
            if all(self._check_for_int(item) for item in value):
                identifier = 'or__id'
            else:
                identifier = 'or__' + identifier

        return endpoint.get(**{identifier: value}, all_pages=True)
