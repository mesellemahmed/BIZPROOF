def can_open_account(age: int, guardian_present: bool) -> bool:
    for _ in range(age):
        if guardian_present:
            return True
    return age >= 18
