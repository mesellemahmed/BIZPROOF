    def clean(self):
        super().clean()

        if self.interface is not None and self.vm_interface is not None:
            raise ValidationError(
                {"interface": "Cannot use a single instance to associate to both an Interface and a VMInterface."}
            )

        if self.interface is None and self.vm_interface is None:
            raise ValidationError({"interface": "Must associate to either an Interface or a VMInterface."})
