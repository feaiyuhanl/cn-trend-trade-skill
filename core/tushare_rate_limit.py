"""Thread-safe rate limiter and parallel helpers for Tushare API calls."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, TypeVar

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config" / "fetch_concurrency.yaml"

T = TypeVar("T")
R = TypeVar("R")


def load_fetch_concurrency_config() -> dict[str, Any]:
    import yaml

    defaults: dict[str, Any] = {
        "max_workers": 16,
        "calls_per_minute": 450,
        "parallel_enabled": True,
        "daily_bar_cache": True,
        "bulk_fetch_min_symbols": 50,
    }
    if not _CONFIG_PATH.exists():
        return defaults
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {**defaults, **data}


class MinuteRateLimiter:
    """Smooth spacing of API calls to stay under calls_per_minute."""

    def __init__(self, calls_per_minute: int = 450) -> None:
        cpm = max(int(calls_per_minute), 1)
        self._interval = 60.0 / cpm
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = time.monotonic()
            self._next = max(now, self._next) + self._interval


def parallel_map(
    items: list[T],
    fn: Callable[[T], R],
    *,
    max_workers: int = 16,
    rate_limiter: MinuteRateLimiter | None = None,
) -> dict[T, R | None]:
    """Run fn(item) concurrently; return {item: result_or_None_on_error}."""
    if not items:
        return {}

    def _wrap(item: T) -> R:
        if rate_limiter is not None:
            rate_limiter.wait()
        return fn(item)

    out: dict[T, R | None] = {}
    workers = max(1, min(int(max_workers), len(items)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_wrap, item): item for item in items}
        for fut in as_completed(futures):
            item = futures[fut]
            try:
                out[item] = fut.result()
            except Exception:
                out[item] = None
    return out
