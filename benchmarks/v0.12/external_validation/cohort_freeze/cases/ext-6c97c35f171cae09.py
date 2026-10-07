    def have_channel_issues(self) -> bool:
        errors = list(self.channel_set.values_list("last_error", flat=True))

        # It's a problem if a project has no integrations at all
        if len(errors) == 0:
            return True

        # It's a problem if any integration has a logged error
        return any(errors)
