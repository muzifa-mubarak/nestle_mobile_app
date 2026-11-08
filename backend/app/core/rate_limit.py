import time
from collections import defaultdict, deque

from app.core.errors import AppError


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        self._hits.clear()

    def _trim(self, key: str, window_seconds: int) -> deque[float]:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        return bucket

    def retry_after(self, key: str, window_seconds: int) -> int:
        bucket = self._trim(key, window_seconds)
        if not bucket:
            return 1
        return max(1, int(window_seconds - (time.monotonic() - bucket[0])) + 1)

    def hit(self, key: str, limit: int, window_seconds: int, message: str | None = None) -> None:
        bucket = self._trim(key, window_seconds)
        if len(bucket) >= limit:
            wait = self.retry_after(key, window_seconds)
            error = AppError(429, "RATE_LIMITED", message or "Too many attempts. Please wait and try again.")
            error.retry_after = wait
            raise error
        bucket.append(time.monotonic())


limiter = SlidingWindowLimiter()
