    def clean(self):
        super().clean()

        if self.can_add and self.grant_on == ACCESS_PAGE:
            # this is a misconfiguration - user can add/move page to current
            # page, but after he does this, he will not have permissions to
            # access this page anymore, so avoid this.
            message = _("Add page permission requires also access to children, "
                        "or descendants, otherwise added page can't be changed "
                        "by its creator.")
            raise ValidationError(message)
