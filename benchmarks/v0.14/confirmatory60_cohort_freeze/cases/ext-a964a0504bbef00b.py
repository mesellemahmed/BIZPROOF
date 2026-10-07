def action_past(count):
    return ngettext_lazy(
        "Deleted Project",
        "Deleted Projects",
        count
    )
