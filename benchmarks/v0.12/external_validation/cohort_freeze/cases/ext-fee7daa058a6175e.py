def generate_list_search_parameters(schema_type):
    """Generate list of query parameters for the list resolver based on a filterset."""

    if schema_type in LIST_SEARCH_PARAMS_BY_SCHEMA_TYPE:
        return LIST_SEARCH_PARAMS_BY_SCHEMA_TYPE[schema_type]

    search_params = {
        "limit": graphene.Int(),
        "offset": graphene.Int(),
    }
    if schema_type._meta.filterset_class is not None:
        search_params.update(
            get_filtering_args_from_filterset(
                schema_type._meta.filterset_class,
            )
        )

    LIST_SEARCH_PARAMS_BY_SCHEMA_TYPE[schema_type] = search_params

    return search_params
