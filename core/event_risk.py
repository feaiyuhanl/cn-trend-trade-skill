"""Event risk: reduction announcements, earnings window, forecast loss."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config" / "event_risk.yaml"


def _load_config() -> dict[str, Any]:
    import yaml

    with _CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_date(s: str) -> datetime | None:
    s = str(s).replace("-", "")[:8]
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return datetime.strptime(s, "%Y%m%d")
    except ValueError:
        return None


def _in_earnings_window(pro, ts_code: str, cfg: dict[str, Any]) -> tuple[bool, str]:
    ecfg = cfg.get("earnings") or {}
    before = int(ecfg.get("blackout_days_before", 3))
    after = int(ecfg.get("blackout_days_after", 1))
    today = datetime.now()
    try:
        df = pro.disclosure_date(ts_code=ts_code)
        if df is None or df.empty:
            return False, ""
        for _, row in df.iterrows():
            end = _parse_date(str(row.get("end_date") or row.get("ann_date") or ""))
            if not end:
                continue
            start_win = end - timedelta(days=before)
            end_win = end + timedelta(days=after)
            if start_win <= today <= end_win:
                return True, f"财报窗口 {end.strftime('%Y%m%d')}"
    except Exception:
        pass
    return False, ""


def _has_reduction(pro, ts_code: str, cfg: dict[str, Any]) -> tuple[bool, str]:
    rcfg = cfg.get("reduction") or {}
    days = int(rcfg.get("block_on_ann_within_days", 30))
    keywords = rcfg.get("keywords") or ["减持"]
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    try:
        df = pro.anns(ts_code=ts_code, start_date=cutoff)
        if df is None or df.empty:
            return False, ""
        for _, row in df.iterrows():
            title = str(row.get("title") or "")
            if any(k in title for k in keywords):
                return True, title[:80]
    except Exception:
        pass
    return False, ""


def _forecast_loss(pro, ts_code: str, cfg: dict[str, Any]) -> tuple[bool, str]:
    fcfg = cfg.get("forecast") or {}
    if not fcfg.get("block_on_forecast_loss"):
        return False, ""
    block_types = set(fcfg.get("block_types") or [])
    try:
        df = pro.forecast(ts_code=ts_code)
        if df is None or df.empty:
            return False, ""
        row = df.iloc[0]
        typ = str(row.get("type") or row.get("forecast_type") or "")
        if typ in block_types or any(t in typ for t in block_types):
            return True, f"业绩预告 {typ}"
    except Exception:
        pass
    return False, ""


def evaluate_symbol(ts_code: str, *, pro=None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or _load_config()
    ts = ts_code.strip().upper()
    flags: list[str] = []
    notes: list[str] = []
    block_entry = False

    if pro:
        in_win, note = _in_earnings_window(pro, ts, cfg)
        if in_win:
            flags.append("earnings_window")
            notes.append(note)
            if cfg.get("earnings", {}).get("block_entry_in_window"):
                block_entry = True

        red, rnote = _has_reduction(pro, ts, cfg)
        if red:
            flags.append("reduction")
            notes.append(rnote)
            block_entry = True

        loss, lnote = _forecast_loss(pro, ts, cfg)
        if loss:
            flags.append("forecast_loss")
            notes.append(lnote)
            block_entry = True

    return {
        "ts_code": ts,
        "event_flags": flags,
        "notes": notes,
        "block_entry": block_entry,
    }


def evaluate_symbols(ts_codes: list[str], *, pro=None, pack_mode: str = "live") -> dict[str, Any]:
    cfg = _load_config()
    by_code = {ts.strip().upper(): evaluate_symbol(ts, pro=pro, cfg=cfg) for ts in ts_codes}
    blocked = [t for t, v in by_code.items() if v["block_entry"]]
    return {
        "version": cfg.get("version", "1.0.0"),
        "symbols": by_code,
        "blocked_ts_codes": blocked,
        "mode": pack_mode,
    }


def fixture_event_risk(ts_codes: list[str]) -> dict[str, Any]:
    by_code = {
        ts.strip().upper(): {"ts_code": ts, "event_flags": [], "notes": [], "block_entry": False}
        for ts in ts_codes
    }
    return {"version": "1.0.0", "symbols": by_code, "blocked_ts_codes": [], "mode": "fixture"}
