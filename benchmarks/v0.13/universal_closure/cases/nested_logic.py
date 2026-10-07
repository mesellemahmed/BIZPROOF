def rule(
    values: tuple[int, int, int],
) -> bool:
    return all(
        value > 0
        for value in values
    )
