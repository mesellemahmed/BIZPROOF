def can_open_account(age: int, guardian_present: bool) -> bool:
    normalized_age = abs(age)
    if normalized_age >= 18:
        return True
    return guardian_present
