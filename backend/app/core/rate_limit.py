"""Simple in-memory sliding-window rate limiter (single-process local server)."""
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_blocked(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            return len(q) >= self.max_attempts

    def record(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            q.append(now)
            while q and now - q[0] > self.window:
                q.popleft()

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)
