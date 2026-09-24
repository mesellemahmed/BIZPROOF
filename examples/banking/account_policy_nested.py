def can_open_account(age: int, guardian_present: bool) -> bool:
    eligible = False
    if age >= 18:
        eligible = True
    else:
        if guardian_present:
            eligible = True
    return eligible
