def join(self):
    """Wait for reader thread to finish."""
    if self.thread:
        self.thread.join()
