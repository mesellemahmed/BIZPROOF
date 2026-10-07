def render_rst(entries: list[PermissionEntry]) -> str:
    """Render the full RST document from the list of PermissionEntry objects."""
    rows = "".join(_rst_table_row(e) for e in entries)
    return RST_HEADER + RST_TABLE_HEADER + rows
