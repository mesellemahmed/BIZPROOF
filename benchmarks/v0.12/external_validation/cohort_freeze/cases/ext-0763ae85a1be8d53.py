    def capture_was_rejected(self) -> bool:
        """Return whether any capture stage terminally rejected its output."""

        return bool(self._capture_rejection_reasons)
