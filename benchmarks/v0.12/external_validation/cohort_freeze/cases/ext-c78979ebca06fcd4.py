def get_queryset(self, request):  # pragma: no cover
    return super().get_queryset(request).select_related("owner")
