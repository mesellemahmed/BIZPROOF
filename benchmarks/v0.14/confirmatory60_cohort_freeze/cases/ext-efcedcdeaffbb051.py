def locale_names(self):
    event = self._locale_event or getattr(self, "event", None)
    return dict(event.available_content_locales) if event else None
