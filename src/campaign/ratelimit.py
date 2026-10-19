"""Sliding window per-user rate limiter backed by SQLite."""

from __future__ import annotations

import time
from collections.abc import Callable

from campaign.config import get_settings
from campaign.store import RunStore


class RateLimiter:
    """Sliding-window per-user rate limiter backed by SQLite rate_events table."""

    def __init__(
        self,
        max_runs: int | None = None,
        window_s: int | None = None,
        clock: Callable[[], float] = time.time,
        store: RunStore | None = None,
    ) -> None:
        settings = get_settings()
        self.max_runs = max_runs if max_runs is not None else settings.rate_limit_runs
        self.window_s = window_s if window_s is not None else settings.rate_limit_window_s
        self.clock = clock
        self.store = store if store is not None else RunStore()

    def check_allowed(self, user_id: str) -> tuple[bool, float]:
        """Check if user has remaining run allowance in rolling window.

        Returns:
            (True, 0.0) if allowed.
            (False, wait_seconds) if rate limit reached.
        """
        now = self.clock()
        window_start = now - self.window_s

        # Periodically clean expired events
        self.store.clean_old_rate_events(window_start)

        active_count = self.store.count_rate_events(user_id, window_start)
        if active_count < self.max_runs:
            return True, 0.0

        oldest_ts = self.store.get_oldest_rate_event_ts(user_id, window_start)
        if oldest_ts is None:
            wait_s = float(self.window_s)
        else:
            wait_s = max(1.0, (oldest_ts + self.window_s) - now)

        return False, round(wait_s, 1)

    def record_run(self, user_id: str) -> None:
        """Record a successful run consumption."""
        self.store.record_rate_event(user_id, self.clock())
