    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Version major.minor
        self.major_minor = ".".join(cms_version.split(".")[:2])

        # Configure formatting
        self.HEADING = lambda text: "\n" + self.style.SQL_FIELD(text)
        self.COMMAND = self.style.HTTP_SUCCESS
