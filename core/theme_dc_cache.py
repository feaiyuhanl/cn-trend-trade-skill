"""Disk cache for Tushare dc_member / limit_list_d (rate-limit friendly)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.paths import DATA_ROOT

CACHE_DIR = DATA_ROOT / "cache"


def _cache_path(kind: str, trade_date: str, key: str = "") -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"_{key}" if key else ""
    return CACHE_DIR / f"{kind}_{trade_date}{suffix}.json"


def read_cache(kind: str, trade_date: str, key: str = "") -> Any | None:
    path = _cache_path(kind, trade_date, key)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_cache(kind: str, trade_date: str, payload: Any, key: str = "") -> Path:
    path = _cache_path(kind, trade_date, key)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return path
