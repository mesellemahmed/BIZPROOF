def rule(values) -> bool:
    return all(value > 0 for value in values)
