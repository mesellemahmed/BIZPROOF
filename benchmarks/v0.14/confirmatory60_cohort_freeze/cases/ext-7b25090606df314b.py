def list_pages(
    request: HttpRequest,
    filters: PageFilterSchema = Query(...),  # ty: ignore[call-non-callable]
    ordering: OrderingSchema = Query(...),  # ty: ignore[call-non-callable]
    search: SearchSchema = Query(...),  # ty: ignore[call-non-callable]
    **kwargs,
):
    pagination_info = cast(
        WagtailLimitOffsetPagination.Input,
        kwargs.get("pagination_info"),
    )
    models = cast(list[type[Model]], filters.type)
    model = models[0] if len(models) == 1 else Page
    field_filter = APIFieldFilterSchema.with_exclude_schemas(
        raw_params=request.GET,
        schemas=(PageFilterSchema, OrderingSchema, SearchSchema),
        base_fields=BASE_PAGE_READ_FIELDS,
    )
    queryset = get_pages_queryset(request, model)
    queryset = filters.filter(queryset, request)
    queryset = field_filter.filter_queryset(queryset)
    queryset = ordering.order_queryset(
        queryset,
        pagination_info,
        base_fields=BASE_PAGE_READ_FIELDS,
    )
    queryset = search.search_queryset(request, queryset)
    return queryset
