    def perform_mutation(cls, _root, info: ResolveInfo, /, **data):
        instance = cls.get_instance(info, **data)

        if instance:
            meta_instance = get_valid_metadata_instance(instance)
            metadata_list = data.pop("input")

            cls.create_metadata_from_graphql_input(
                metadata_list, error_field_name="input"
            )

            items = {data.key: data.value for data in metadata_list}
            update_private_metadata(meta_instance, items)

        return cls.success_response(instance)
