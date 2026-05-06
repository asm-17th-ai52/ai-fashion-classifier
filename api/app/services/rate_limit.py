"""Simple per-IP fixed-window rate limiter — per spec §8.

Per-IP: 10 req/min default. For production, swap this for Redis INCR with
expiry. The interface (``check`` raises ``RateLimitedError``) is stable.
"""
from __future__ import annotations

import threading
import time
from collections import deque

from app.core.config import settings
from app.core.errors import RateLimitedError


class _IPRateLimiter:
    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.time()
        window_start = now - 60.0
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] < window_start:
                bucket.popleft()
            if len(bucket) >= self.max_per_minute:
                raise RateLimitedError()
            bucket.append(now)


rate_limiter = _IPRateLimiter(settings.rate_limit_per_min)
