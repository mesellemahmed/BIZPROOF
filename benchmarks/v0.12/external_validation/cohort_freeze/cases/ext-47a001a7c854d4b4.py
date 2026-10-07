def get_override_parameters(self):
    params = super().get_override_parameters()
    # Expose the ?fields, ?omit, and ?brief query parameters supported by NetBoxModelViewSet
    # for all non-bulk GET operations (both list and detail).
    if not self.is_bulk_action and self.method == 'GET':
        params = list(params) + [
            OpenApiParameter(
                name='fields',
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.STR,
                description='Comma-separated list of fields to include in the response. Example: `fields=id,name`.',
            ),
            OpenApiParameter(
                name='omit',
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.STR,
                description='Comma-separated list of fields to exclude from the response. '
                            'Example: `omit=description,tags`.',
            ),
            OpenApiParameter(
                name='brief',
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.BOOL,
                description='Return only brief fields for each object.',
            ),
        ]
    return params
