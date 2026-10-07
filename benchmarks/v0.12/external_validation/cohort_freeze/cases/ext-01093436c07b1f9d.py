def get_status_color(self):
    return JobStatusChoices.colors.get(self.status)
