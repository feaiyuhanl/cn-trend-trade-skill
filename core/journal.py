from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
JOURNAL_DIR = _ROOT / ".trend-trade" / "journal"


def save_journal(entry: dict[str, Any], *, date: str | None = None) -> Path:
    """Append trade journal entry (review workflow)."""
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    d = date or datetime.now().strftime("%Y%m%d")
    path = JOURNAL_DIR / f"{d}.json"
    records: list[dict[str, Any]] = []
    if path.exists():
        with path.open(encoding="utf-8") as f:
            records = json.load(f)
    if not isinstance(records, list):
        records = [records]
    entry.setdefault("saved_at", datetime.now().astimezone().isoformat(timespec="seconds"))
    records.append(entry)
    with path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return path


def load_journal(date: str) -> list[dict[str, Any]]:
    path = JOURNAL_DIR / f"{date}.json"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def list_journal_dates() -> list[str]:
    if not JOURNAL_DIR.exists():
        return []
    return sorted((p.stem for p in JOURNAL_DIR.glob("*.json")), reverse=True)
