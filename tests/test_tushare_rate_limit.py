"""Tests for tushare rate limiter and parallel map."""

from __future__ import annotations

import threading
import time

from core.tushare_rate_limit import MinuteRateLimiter, parallel_map


def test_minute_rate_limiter_spacing():
    lim = MinuteRateLimiter(calls_per_minute=600)
    t0 = time.monotonic()
    lim.wait()
    lim.wait()
    lim.wait()
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.08


def test_parallel_map_collects_results():
    lock = threading.Lock()
    seen: list[int] = []

    def fn(x: int) -> int:
        with lock:
            seen.append(x)
        return x * 2

    out = parallel_map([1, 2, 3, 4], fn, max_workers=4, rate_limiter=None)
    assert out[1] == 2
    assert out[4] == 8
    assert len(seen) == 4
