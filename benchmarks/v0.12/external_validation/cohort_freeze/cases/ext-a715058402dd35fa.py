def _process_row(row: Row) -> Any:
    return XComModel.deserialize_value(row)
