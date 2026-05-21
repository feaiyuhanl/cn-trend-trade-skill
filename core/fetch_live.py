from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from core import SKILL_VERSION
from core.config_loader import fetch_lookback, resolve_indices_for_profile
from core.hints import compute_derived_hints
from core.ts_code import normalize_symbols

_FETCH_STATUS: dict[str, str] = {}
_FETCH_MESSAGES: list[str] = []


def _status(key: str, value: str, msg: str = "") -> None:
    _FETCH_STATUS[key] = value
    if msg:
        _FETCH_MESSAGES.append(msg)


def _get_pro():
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        return None
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api()


def _end_start_dates(lookback_daily: int) -> tuple[str, str]:
    end = datetime.now()
    if end.hour < 16:
        end = end - timedelta(days=1)
    while end.weekday() >= 5:
        end = end - timedelta(days=1)
    start = end - timedelta(days=int(lookback_daily * 1.6))
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def _df_to_bars(df: pd.DataFrame, ts_code: str, tf: str, source_id: str = "tushare") -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    bars: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        td = str(row["trade_date"])
        if len(td) == 8 and "-" not in td:
            pass
        else:
            td = pd.Timestamp(row["trade_date"]).strftime("%Y%m%d")
        bars.append(
            {
                "id": f"bar_{ts_code.replace('.', '_')}_{tf[0]}_{td}",
                "trade_date": td,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "pct_chg": float(row.get("pct_chg") or 0),
                "vol": float(row["vol"]) if pd.notna(row.get("vol")) else None,
                "amount": float(row["amount"]) if pd.notna(row.get("amount")) else None,
                "source_id": source_id,
            }
        )
    return bars


def _fetch_daily(pro, ts_code: str, start: str, end: str, *, is_index: bool) -> pd.DataFrame:
    if is_index:
        df = pro.index_daily(ts_code=ts_code, start_date=start, end_date=end)
    else:
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.sort_values("trade_date")
    return df


def _resample_bars(daily_df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame()
    d = daily_df.copy()
    d["dt"] = pd.to_datetime(d["trade_date"], format="%Y%m%d")
    d = d.set_index("dt").sort_index()
    agg_cols = {c: c for c in ("open", "high", "low", "close", "vol", "amount") if c in d.columns}
    ohlc = d.resample(rule).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "vol": "sum",
            **({"amount": "sum"} if "amount" in d.columns else {}),
        }
    )
    ohlc = ohlc.dropna(subset=["close"])
    if ohlc.empty:
        return pd.DataFrame()
    ohlc["pct_chg"] = ohlc["close"].pct_change() * 100
    ohlc["trade_date"] = ohlc.index.strftime("%Y%m%d")
    return ohlc.reset_index(drop=True)


def _stock_name(pro, ts_code: str) -> str:
    try:
        basic = pro.stock_basic(ts_code=ts_code, fields="ts_code,name")
        if basic is not None and not basic.empty:
            return str(basic.iloc[0]["name"])
    except Exception:
        pass
    return ts_code


def _index_name(entry: dict[str, Any]) -> str:
    return str(entry.get("name") or entry["ts_code"])


def _fetch_instrument(
    pro,
    ts_code: str,
    *,
    asset_type: str,
    name: str,
    index_group: str | None = None,
    category: str | None = None,
    lookback: dict[str, int],
) -> dict[str, Any] | None:
    is_index = asset_type == "index"
    start, end = _end_start_dates(lookback.get("daily", 120))
    try:
        daily_df = _fetch_daily(pro, ts_code, start, end, is_index=is_index)
    except Exception as e:
        _FETCH_MESSAGES.append(f"{ts_code} daily fail: {e}")
        return None
    if daily_df.empty:
        return None

    daily_bars = _df_to_bars(daily_df, ts_code, "daily")
    weekly_df = _resample_bars(daily_df, "W-FRI")
    try:
        monthly_df = _resample_bars(daily_df, "ME")
    except ValueError:
        monthly_df = _resample_bars(daily_df, "M")
    w_look = lookback.get("weekly", 52)
    m_look = lookback.get("monthly", 24)
    weekly_bars = _df_to_bars(weekly_df, ts_code, "weekly")[-w_look:]
    monthly_bars = _df_to_bars(monthly_df, ts_code, "monthly")[-m_look:]
    daily_bars = daily_bars[-lookback.get("daily", 120) :]

    hints = compute_derived_hints(daily_bars, weekly_bars)
    inst: dict[str, Any] = {
        "ts_code": ts_code,
        "name": name,
        "asset_type": asset_type,
        "bars": {"daily": daily_bars, "weekly": weekly_bars, "monthly": monthly_bars},
        "derived_hints": hints,
    }
    if index_group:
        inst["index_group"] = index_group
    if category:
        inst["category"] = category
    return inst


def _fetch_breadth(pro) -> list[dict[str, Any]] | None:
    """Optional: limit up/down counts for latest trade date."""
    try:
        end = datetime.now().strftime("%Y%m%d")
        for _ in range(10):
            up = pro.limit_list_d(trade_date=end, limit_type="U")
            down = pro.limit_list_d(trade_date=end, limit_type="D")
            if (up is not None and not up.empty) or (down is not None and not down.empty):
                return [
                    {
                        "id": f"breadth_{end}",
                        "trade_date": end,
                        "advance": None,
                        "decline": None,
                        "limit_up": int(len(up)) if up is not None else None,
                        "limit_down": int(len(down)) if down is not None else None,
                        "source_id": "tushare",
                    }
                ]
            end_dt = datetime.strptime(end, "%Y%m%d") - timedelta(days=1)
            while end_dt.weekday() >= 5:
                end_dt -= timedelta(days=1)
            end = end_dt.strftime("%Y%m%d")
    except Exception as e:
        _FETCH_MESSAGES.append(f"breadth skip: {e}")
    return None


def build_live_pack(
    *,
    symbols: list[str],
    indices_profile: str = "comprehensive",
    run_id: str | None = None,
) -> dict[str, Any]:
    global _FETCH_STATUS, _FETCH_MESSAGES
    _FETCH_STATUS = {}
    _FETCH_MESSAGES = []

    pro = _get_pro()
    if pro is None:
        raise RuntimeError("TUSHARE_TOKEN not set; use --fixture or export TUSHARE_TOKEN")

    _status("tushare", "ok")
    symbols_norm = normalize_symbols(symbols)
    lookback = fetch_lookback()
    symbol_instruments: list[dict[str, Any]] = []
    for ts_code in symbols_norm:
        name = _stock_name(pro, ts_code)
        inst = _fetch_instrument(
            pro, ts_code, asset_type="stock", name=name, lookback=lookback
        )
        if inst:
            symbol_instruments.append(inst)
        else:
            _FETCH_MESSAGES.append(f"skip stock (no data): {ts_code}")

    if not symbol_instruments:
        raise RuntimeError(f"No stock data fetched for: {symbols_norm}")

    index_entries = resolve_indices_for_profile(indices_profile)
    index_instruments: list[dict[str, Any]] = []
    for entry in index_entries:
        ts_code = entry["ts_code"]
        optional = bool(entry.get("optional"))
        try:
            inst = _fetch_instrument(
                pro,
                ts_code,
                asset_type="index",
                name=_index_name(entry),
                index_group=entry.get("index_group"),
                category=entry.get("category"),
                lookback=lookback,
            )
            if inst:
                index_instruments.append(inst)
            elif not optional:
                _FETCH_MESSAGES.append(f"required index missing: {ts_code}")
        except Exception as e:
            if optional:
                _FETCH_MESSAGES.append(f"optional index skip {ts_code}: {e}")
            else:
                _FETCH_MESSAGES.append(f"index fail {ts_code}: {e}")

    breadth = _fetch_breadth(pro)
    if breadth:
        _status("breadth", "ok")
    else:
        _status("breadth", "skip", "limit_list_d unavailable or empty")

    rid = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    pack: dict[str, Any] = {
        "meta": {
            "run_id": rid,
            "as_of": datetime.now().astimezone().isoformat(timespec="seconds"),
            "fetch_status": dict(_FETCH_STATUS),
            "skill_version": SKILL_VERSION,
            "mode": "live",
            "symbols_requested": symbols_norm,
            "indices_profile": indices_profile,
            "fetch_messages": _FETCH_MESSAGES[:20],
        },
        "symbols": symbol_instruments,
        "indices": index_instruments,
        "user_context": {
            "session_mode": "mixed",
            "positions": [],
            "portfolio": {},
            "user_notes": "",
        },
        "market_breadth": breadth,
    }
    from core.pack_enrich import enrich_a_share_context

    enrich_a_share_context(pack)
    return pack
