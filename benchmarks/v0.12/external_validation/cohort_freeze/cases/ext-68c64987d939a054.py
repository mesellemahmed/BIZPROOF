def to_dict(self) -> FlipDict:
    return {
        "timestamp": self.created.replace(microsecond=0).isoformat(),
        "up": 1 if self.new_status == "up" else 0,
    }
