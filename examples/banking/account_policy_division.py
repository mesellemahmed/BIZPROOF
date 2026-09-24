def can_open_account(age: int, guardian_present: bool) -> bool:
    bucket = age // 2
    if bucket >= 9:
        return True
    return guardian_present
