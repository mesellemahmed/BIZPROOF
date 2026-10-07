def tags_list(self) -> list[str]:
    return [t.strip() for t in self.tags.split(" ") if t.strip()]
