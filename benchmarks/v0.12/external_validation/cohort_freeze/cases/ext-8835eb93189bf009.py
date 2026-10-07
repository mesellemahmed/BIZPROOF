    def clean(self):
        """
        Validate the model for GenericForeignKey fields to ensure that the content type and object ID exist.
        """
        super().clean()
        self._coerce_nullable_unique_chars()

        for field in self._meta.get_fields():
            if isinstance(field, GenericForeignKey):
                ct_value = getattr(self, field.ct_field, None)
                fk_value = getattr(self, field.fk_field, None)

                if ct_value is None and fk_value is not None:
                    raise ValidationError({
                        field.ct_field: "This field cannot be null.",
                    })
                if fk_value is None and ct_value is not None:
                    raise ValidationError({
                        field.fk_field: "This field cannot be null.",
                    })

                if ct_value and fk_value:
                    klass = getattr(self, field.ct_field).model_class()
                    try:
                        obj = klass.objects.get(pk=fk_value)
                    except ObjectDoesNotExist:
                        raise ValidationError({
                            field.fk_field: f"Related object not found using the provided value: {fk_value}."
                        })

                    # update the GFK field value
                    setattr(self, field.name, obj)
