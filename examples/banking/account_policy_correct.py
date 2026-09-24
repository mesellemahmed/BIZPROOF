def can_open_account(age: int, guardian_present: bool) -> bool:
    if age >= 18:
        return True
    return guardian_present
