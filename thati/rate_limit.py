"""In-memory per-key sliding-window rate limiter."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def configure(self, max_requests: int, window_seconds: float) -> None:
        with self._lock:
            self.max_requests = max_requests
            self.window_seconds = window_seconds

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            window_start = now - self.window_seconds
            recent = [stamp for stamp in self._hits[key] if stamp > window_start]
            if len(recent) >= self.max_requests:
                self._hits[key] = recent
                return False
            recent.append(now)
            self._hits[key] = recent
            return True


analyze_limiter = SlidingWindowLimiter(max_requests=30, window_seconds=60.0)
