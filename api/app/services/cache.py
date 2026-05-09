"""In-process session cache with TTL.

The spec recommends Redis or SQLite for production; for dev we use a
threadsafe dict so the backend has zero-config local runs. Replace this
module's two functions with a Redis client when Redis is provisioned —
nothing else in the codebase depends on the implementation.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from app.core.config import settings
from app.schemas import SessionResponse


class _SessionCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, SessionResponse]] = {}
        self._lock = threading.Lock()

    def put(self, session_id: str, value: SessionResponse, ttl: Optional[int] = None) -> None:
        ttl = ttl or settings.session_ttl_seconds
        expires_at = time.time() + ttl
        with self._lock:
            self._store[session_id] = (expires_at, value)

    def get(self, session_id: str) -> Optional[SessionResponse]:
        with self._lock:
            entry = self._store.get(session_id)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                del self._store[session_id]
                return None
            return value

    def purge_expired(self) -> int:
        now = time.time()
        with self._lock:
            stale = [k for k, (exp, _) in self._store.items() if exp < now]
            for k in stale:
                del self._store[k]
        return len(stale)


session_cache = _SessionCache()
