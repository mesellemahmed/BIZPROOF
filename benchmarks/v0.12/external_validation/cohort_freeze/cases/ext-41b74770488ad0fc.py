def __init__(self, *args, help_text='', **kwargs):
    if not help_text:
        help_text = mark_safe(
            _(
                "Specify one or more individual numbers or numeric ranges separated by commas. Example: {example}"
            ).format(example="<code>1-5,10,20-30</code>")
        )
    super().__init__(*args, help_text=help_text, **kwargs)
