from __future__ import annotations

import threading
import time


class RunWatchdog:
    def __init__(
        self,
        timeout_seconds=600,
    ):
        self.timeout_seconds = timeout_seconds
        self.last_progress = time.time()
        self._stop = threading.Event()

    def progress(self):
        self.last_progress = time.time()

    def stale(self):
        return (
            time.time()
            - self.last_progress
            > self.timeout_seconds
        )

    def stop(self):
        self._stop.set()
