    def get_writable_class(self, serializer, bulk=False):
        """
        Given a FooSerializer instance, look up or construct a [Bulk]WritableFooSerializer class if necessary.

        If no [Bulk]WritableFooSerializer class is needed, returns None instead.
        """
        properties = {}
        # Does this serializer have any fields of certain special types?
        # These are the field types that are asymmetric between request (write) and response (read); if any such fields
        # are present, we should generate a distinct WritableFooSerializer to reflect that asymmetry in the schema.
        fields = {} if hasattr(serializer, "child") else serializer.fields
        for child_name, child in fields.items():
            # Don't consider read_only fields (since we're planning specifically for the writable serializer).
            if child.read_only:
                continue

            if isinstance(child, (ChoiceField, WritableNestedSerializer)):
                properties[child_name] = None
            elif isinstance(child, ManyRelatedField) and isinstance(child.child_relation, SerializedPKRelatedField):
                properties[child_name] = None

        if bulk:
            # The "id" field is always different in bulk serializers
            properties["id"] = None

        if not properties:
            # There's nothing about this serializer that requires a special WritableSerializer class to be defined.
            return None

        # Have we already created a [Bulk]WritableFooSerializer class or do we need to do so now?
        writable_name = "Writable" + type(serializer).__name__
        if bulk:
            writable_name = f"Bulk{writable_name}"
        if writable_name not in self.writable_serializers:
            # We need to create a new class to use
            # If the original serializer class has a Meta, make sure we set Meta.ref_name appropriately
            meta_class = getattr(type(serializer), "Meta", None)
            if meta_class:
                ref_name = "Writable" + self.get_serializer_ref_name(serializer)
                if bulk:
                    ref_name = f"Bulk{ref_name}"
                writable_meta = type("Meta", (meta_class,), {"ref_name": ref_name})
                properties["Meta"] = writable_meta

            # Define and cache a new [Bulk]WritableFooSerializer class
            if bulk:

                def get_fields(self):
                    """For Nautobot's bulk_update/partial_update/delete APIs, the `id` field is mandatory."""
                    new_fields = {}
                    for name, field in type(serializer)().get_fields().items():
                        if name == "id":
                            field.read_only = False
                            field.required = True
                        new_fields[name] = field
                    return new_fields

                properties["get_fields"] = get_fields

            self.writable_serializers[writable_name] = type(writable_name, (type(serializer),), properties)

        writable_class = self.writable_serializers[writable_name]
        return writable_class
