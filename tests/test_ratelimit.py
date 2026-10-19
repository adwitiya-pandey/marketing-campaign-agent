"""Tests for sliding window rate limiter backed by SQLite."""

from campaign.ratelimit import RateLimiter
from campaign.store import RunStore


class MockClock:
    """Injected mock clock for deterministically controlling simulated time."""

    def __init__(self, start_ts: float = 1000.0) -> None:
        self.current_ts = start_ts

    def __call__(self) -> float:
        return self.current_ts

    def advance(self, seconds: float) -> None:
        self.current_ts += seconds


def test_rate_limiter_exactly_at_limit(tmp_path):
    db_file = tmp_path / "runs.db"
    store = RunStore(db_file)
    clock = MockClock(1000.0)
    limiter = RateLimiter(max_runs=3, window_s=600, clock=clock, store=store)

    user = "alice_dev"

    # Runs 1, 2, 3 should be permitted
    for i in range(3):
        allowed, wait_s = limiter.check_allowed(user)
        assert allowed is True
        assert wait_s == 0.0
        limiter.record_run(user)
        clock.advance(10.0)  # 10s between runs

    # 4th run exceeds max_runs (3) in window -> rejected
    allowed, wait_s = limiter.check_allowed(user)
    assert allowed is False
    assert wait_s > 0.0


def test_rate_limiter_window_expiry(tmp_path):
    db_file = tmp_path / "runs.db"
    store = RunStore(db_file)
    clock = MockClock(1000.0)
    limiter = RateLimiter(max_runs=2, window_s=300, clock=clock, store=store)

    user = "bob_analyst"

    # Consume 2 runs at t=1000, 1010
    limiter.record_run(user)
    clock.advance(10.0)
    limiter.record_run(user)

    # Immediately blocked
    allowed, wait_s = limiter.check_allowed(user)
    assert allowed is False
    # Oldest run was at 1000; window_s = 300; expires at 1300; current t = 1010; wait = 290s
    assert wait_s == 290.0

    # Advance past the first run's window (e.g. to t=1305)
    clock.advance(295.0)

    # Now first run has expired; 1 active run remains -> allowed
    allowed, wait_s = limiter.check_allowed(user)
    assert allowed is True
    assert wait_s == 0.0


def test_rate_limiter_multiple_users_independent(tmp_path):
    db_file = tmp_path / "runs.db"
    store = RunStore(db_file)
    clock = MockClock(1000.0)
    limiter = RateLimiter(max_runs=2, window_s=600, clock=clock, store=store)

    # User 1 hits limit
    limiter.record_run("user1")
    limiter.record_run("user1")
    assert limiter.check_allowed("user1")[0] is False

    # User 2 is independent and permitted
    assert limiter.check_allowed("user2")[0] is True
    limiter.record_run("user2")
    assert limiter.check_allowed("user2")[0] is True


def test_rate_limiter_restart_persistence(tmp_path):
    db_file = tmp_path / "runs.db"
    clock = MockClock(1000.0)

    # Instance 1: consume limit
    store1 = RunStore(db_file)
    limiter1 = RateLimiter(max_runs=1, window_s=3600, clock=clock, store=store1)
    assert limiter1.check_allowed("charlie")[0] is True
    limiter1.record_run("charlie")
    assert limiter1.check_allowed("charlie")[0] is False

    # Simulate restart by creating completely new store and limiter instances against same file
    store2 = RunStore(db_file)
    limiter2 = RateLimiter(max_runs=1, window_s=3600, clock=clock, store=store2)
    # Must still be blocked!
    allowed, wait_s = limiter2.check_allowed("charlie")
    assert allowed is False
    assert wait_s == 3600.0
