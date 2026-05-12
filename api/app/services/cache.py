"""In-process session caches with TTL.

The spec recommends Redis or SQLite for production; for dev we use
threadsafe dicts so the backend has zero-config local runs. Replace
these stores with a Redis client when Redis is provisioned — nothing
else in the codebase depends on the implementation.

Two caches:
- ``session_cache`` — completed ``SessionResponse`` (TTL 24h, spec §4.3).
- ``pending_cache`` — pre-streaming ``SessionState`` after preprocess
  (TTL 5min, spec §5.3). Read once by the SSE handler; deleted when the
  stream completes successfully.
"""
from __future__ import annotations

import threading
import time
from typing import Generic, Optional, TypeVar

from app.core.config import settings
from app.schemas import SessionResponse

T = TypeVar("T")


class _TTLDict(Generic[T]):
    def __init__(self, default_ttl: int) -> None:
        self._store: dict[str, tuple[float, T]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl

    def put(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        expires_at = time.time() + (ttl or self._default_ttl)
        with self._lock:
            self._store[key] = (expires_at, value)

    def get(self, key: str) -> Optional[T]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                del self._store[key]
                return None
            return value

    def pop(self, key: str) -> Optional[T]:
        with self._lock:
            entry = self._store.pop(key, None)
        if entry is None:
            return None
        expires_at, value = entry
        return None if expires_at < time.time() else value

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def purge_expired(self) -> int:
        now = time.time()
        with self._lock:
            stale = [k for k, (exp, _) in self._store.items() if exp < now]
            for k in stale:
                del self._store[k]
        return len(stale)


# Completed analyses keyed by session_id (spec §4.3 — 24h TTL).
session_cache: _TTLDict[SessionResponse] = _TTLDict(settings.session_ttl_seconds)

# Pre-streaming SessionState keyed by session_id (spec §5.3 — short TTL,
# only kept until SSE consumer connects). Untyped here to avoid a circular
# import with orchestration.state; callers pass SessionState instances.
pending_cache: _TTLDict[object] = _TTLDict(default_ttl=300)
