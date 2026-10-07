def rule(user, values):
    accepted = all(value > 0 for value in values)

    if accepted:
        user.accepted = True
        user.save()

    return (accepted, user.code)
