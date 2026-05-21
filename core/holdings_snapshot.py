"""Snapshot holdings from pack + discipline config on each finalize."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import HOLDINGS_DIR, CONFIG_DIR

DISCIPLINE_FILE = CONFIG_DIR / "my_discipline.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return {}
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def build_holdings_snapshot(
    trace: dict[str, Any], pack: dict[str, Any]
) -> dict[str, Any]:
    meta = trace.get("meta") or {}
    discipline = _load_yaml(DISCIPLINE_FILE)
    session_positions = list((pack.get("user_context") or {}).get("positions") or [])
    config_holdings = list(discipline.get("holdings") or [])

    holdings_review: dict[str, Any] = {}
    for ts_code, dec in (trace.get("decisions") or {}).items():
        hr = dec.get("holding_review")
        if hr:
            holdings_review[ts_code] = hr

    return {
        "run_id": meta.get("run_id"),
        "as_of": meta.get("as_of"),
        "session_mode": meta.get("session_mode"),
        "config_holdings": config_holdings,
        "session_positions": session_positions,
        "holdings_review": holdings_review,
        "portfolio_rules": discipline.get("portfolio"),
        "discipline_rules": discipline.get("rules"),
    }


def save_holdings_snapshot(trace: dict[str, Any], pack: dict[str, Any]) -> Path:
    HOLDINGS_DIR.mkdir(parents=True, exist_ok=True)
    snap = build_holdings_snapshot(trace, pack)
    snap["saved_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    run_id = snap.get("run_id") or datetime.now().strftime("%Y%m%d%H%M%S")
    path = HOLDINGS_DIR / f"{run_id}.json"
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_holdings_snapshots(*, limit: int = 20) -> list[Path]:
    if not HOLDINGS_DIR.exists():
        return []
    files = sorted(HOLDINGS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def load_latest_holdings_snapshot() -> dict[str, Any] | None:
    files = list_holdings_snapshots(limit=1)
    if not files:
        return None
    with files[0].open(encoding="utf-8") as f:
        return json.load(f)
