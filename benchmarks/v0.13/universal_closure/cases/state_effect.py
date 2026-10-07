def rule(account, amount: int) -> int:
    account.balance = account.balance + amount
    account.save()
    return account.balance
