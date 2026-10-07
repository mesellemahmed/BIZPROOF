def sign_bounce_id(s: str) -> str:
    return ShortHexTimestampSigner(sep=".").sign(s)
