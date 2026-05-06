"""Tier-2 daily budget tracker — per spec §8.

Spec calls for Redis INCR atomic counters with KST midnight reset. For
dev we use an in-memory counter that resets on day rollover (UTC). The
``is_exhausted`` API is what Context Agent should poll via Backend.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from app.core.config import settings


class _Tier2Budget:
    def __init__(self, daily_cap: int, rpm_cap: int) -> None:
        self.daily_cap = daily_cap
        self.rpm_cap = rpm_cap
        self._lock = threading.Lock()
        self._day_key: str = ""
        self._daily_count: int = 0
        self._rpm_window: list[float] = []

    def _refresh_day(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._day_key:
            self._day_key = today
            self._daily_count = 0

    def is_exhausted(self) -> bool:
        with self._lock:
            self._refresh_day()
            return self._daily_count >= self.daily_cap

    def increment(self) -> None:
        import time as _time

        with self._lock:
            self._refresh_day()
            self._daily_count += 1
            now = _time.time()
            self._rpm_window = [t for t in self._rpm_window if t > now - 60]
            self._rpm_window.append(now)

    def snapshot(self) -> dict:
        with self._lock:
            self._refresh_day()
            return {
                "day": self._day_key,
                "daily_count": self._daily_count,
                "daily_cap": self.daily_cap,
                "rpm_count": len(self._rpm_window),
                "rpm_cap": self.rpm_cap,
            }


tier2_budget = _Tier2Budget(
    daily_cap=settings.tier2_daily_budget,
    rpm_cap=settings.tier2_rpm_limit,
)
