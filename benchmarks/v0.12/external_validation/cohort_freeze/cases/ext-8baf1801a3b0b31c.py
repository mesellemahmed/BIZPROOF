    def clean(self):
        super().clean()

        # Both ports must belong to the same device
        if self.front_port.device_id != self.rear_port.device_id:
            raise ValidationError({
                "rear_port": _("Rear port ({rear_port}) must belong to the same device").format(
                    rear_port=self.rear_port
                )
            })
