def rule(
    user,
    values: tuple[int, int, int],
) -> tuple[bool, int]:
    accepted = all(
        value > 0
        for value in values
    )

    if accepted:
        user.accepted = True
        user.save()

    return (
        accepted,
        user.code,
    )
