def filter_device(self, queryset, name, value):
    if not value:
        return queryset
    return queryset.filter(**{f"{name}__in": value})
