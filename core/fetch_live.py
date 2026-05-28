from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from core import SKILL_VERSION
from core.config_loader import fetch_lookback, resolve_indices_for_profile
from core.hints import compute_derived_hints
from core.trade_date_util import attach_pack_trade_date_meta, expected_trade_session_date
from core.ts_code import normalize_symbols
from core.tushare_rate_limit import (
    MinuteRateLimiter,
    load_fetch_concurrency_config,
    parallel_map,
)

_ROOT = Path(__file__).resolve().parent.parent
_DAILY_CACHE_DIR = _ROOT / ".trend-trade" / "cache" / "daily_bars"

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
    end_s = expected_trade_session_date()
    end = datetime.strptime(end_s, "%Y%m%d")
    start = end - timedelta(days=int(lookback_daily * 1.6))
    return start.strftime("%Y%m%d"), end_s


def _ak_symbol(ts_code: str) -> str:
    return ts_code.split(".")[0]


def _fetch_daily_akshare(ts_code: str, start: str, end: str, *, is_index: bool) -> pd.DataFrame:
    try:
        import akshare as ak
    except ImportError:
        return pd.DataFrame()
    sym = _ak_symbol(ts_code)
    try:
        if is_index:
            sdf = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
            edf = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
            raw = ak.index_zh_a_hist(
                symbol=sym, period="daily", start_date=sdf, end_date=edf
            )
        else:
            raw = ak.stock_zh_a_hist(
                symbol=sym,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="",
            )
    except Exception as e:
        _FETCH_MESSAGES.append(f"akshare {ts_code}: {e}")
        return pd.DataFrame()
    if raw is None or raw.empty:
        return pd.DataFrame()
    rename = {
        "日期": "trade_date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "vol",
        "成交额": "amount",
        "涨跌幅": "pct_chg",
    }
    df = raw.rename(columns={k: v for k, v in rename.items() if k in raw.columns})
    if "trade_date" not in df.columns:
        return pd.DataFrame()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y%m%d")
    for col in ("open", "high", "low", "close", "pct_chg", "vol", "amount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("trade_date").reset_index(drop=True)


def _merge_daily_supplement(
    ts_df: pd.DataFrame,
    ts_code: str,
    start: str,
    end: str,
    *,
    is_index: bool,
) -> pd.DataFrame:
    """Append missing sessions when Tushare lags (same-day bar via akshare)."""
    if ts_df is None or ts_df.empty:
        ak_df = _fetch_daily_akshare(ts_code, start, end, is_index=is_index)
        if not ak_df.empty:
            _status("akshare_supplement", "ok")
        return ak_df
    latest = str(ts_df["trade_date"].max())
    if latest >= end:
        return ts_df
    next_day = datetime.strptime(latest, "%Y%m%d") + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    ak_start = next_day.strftime("%Y%m%d")
    ak_df = _fetch_daily_akshare(ts_code, ak_start, end, is_index=is_index)
    if ak_df.empty:
        ak_df = _fetch_daily_akshare(ts_code, end, end, is_index=is_index)
    if ak_df.empty:
        _FETCH_MESSAGES.append(
            f"akshare supplement empty for {ts_code} (tushare through {latest}, want {end})"
        )
        return ts_df
    combined = (
        pd.concat([ts_df, ak_df], ignore_index=True)
        .drop_duplicates(subset=["trade_date"], keep="last")
        .sort_values("trade_date")
    )
    _status("akshare_supplement", "ok")
    _FETCH_MESSAGES.append(
        f"akshare supplemented {ts_code}: {latest} -> {combined['trade_date'].max()}"
    )
    return combined


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


def _stock_name(pro, ts_code: str, name_map: dict[str, str] | None = None) -> str:
    ts = ts_code.strip().upper()
    if name_map and ts in name_map:
        return name_map[ts]
    try:
        basic = pro.stock_basic(ts_code=ts, fields="ts_code,name")
        if basic is not None and not basic.empty:
            return str(basic.iloc[0]["name"])
    except Exception:
        pass
    return ts_code


def load_stock_name_map(pro) -> dict[str, str]:
    """Single stock_basic pull (or disk cache via universe_mainboard)."""
    from core.universe_mainboard import fetch_mainboard_stock_basic

    rows = fetch_mainboard_stock_basic(pro)
    if rows:
        return {r["ts_code"]: str(r.get("name") or r["ts_code"]) for r in rows}
    out: dict[str, str] = {}
    try:
        df = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,name",
        )
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                ts = str(row["ts_code"]).strip().upper()
                out[ts] = str(row.get("name") or ts)
    except Exception:
        pass
    return out


def _daily_cache_path(ts_code: str, end: str) -> Path:
    safe = ts_code.replace(".", "_")
    return _DAILY_CACHE_DIR / f"{safe}_{end}.json"


def _load_daily_cache(ts_code: str, end: str) -> pd.DataFrame | None:
    path = _daily_cache_path(ts_code, end)
    if not path.exists():
        return None
    try:
        import json

        rows = json.loads(path.read_text(encoding="utf-8"))
        if not rows:
            return None
        df = pd.DataFrame(rows)
        if df.empty:
            return None
        latest = str(df["trade_date"].max())
        if latest < end:
            # Stale cache written before Tushare/akshare had the expected session bar.
            return None
        return df
    except Exception:
        return None


def _save_daily_cache(ts_code: str, end: str, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    latest = str(df["trade_date"].max())
    if latest < end:
        return
    _DAILY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    import json

    rows = df.where(pd.notna(df), None).to_dict(orient="records")
    _daily_cache_path(ts_code, end).write_text(
        json.dumps(rows, ensure_ascii=False),
        encoding="utf-8",
    )


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
    rate_limiter: MinuteRateLimiter | None = None,
    use_daily_cache: bool = False,
) -> dict[str, Any] | None:
    is_index = asset_type == "index"
    start, end = _end_start_dates(lookback.get("daily", 120))
    daily_df: pd.DataFrame | None = None
    if use_daily_cache and not is_index:
        daily_df = _load_daily_cache(ts_code, end)
    try:
        if daily_df is None or daily_df.empty:
            if rate_limiter is not None:
                rate_limiter.wait()
            daily_df = _fetch_daily(pro, ts_code, start, end, is_index=is_index)
            if use_daily_cache and not is_index and daily_df is not None and not daily_df.empty:
                _save_daily_cache(ts_code, end, daily_df)
        daily_df = _merge_daily_supplement(
            daily_df, ts_code, start, end, is_index=is_index
        )
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

    hints = compute_derived_hints(daily_bars, weekly_bars, monthly_bars)
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
        end = expected_trade_session_date()
        end_dt = datetime.strptime(end, "%Y%m%d")
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
            end_dt = end_dt - timedelta(days=1)
            while end_dt.weekday() >= 5:
                end_dt -= timedelta(days=1)
            end = end_dt.strftime("%Y%m%d")
    except Exception as e:
        _FETCH_MESSAGES.append(f"breadth skip: {e}")
    return None


def preflight_fresh_session(
    *,
    probe_symbols: list[str] | None = None,
    min_symbol_ratio: float | None = None,
    fail_on_stale: bool = True,
) -> dict[str, Any]:
    """Fast probe (indices + 1–2 liquid stocks, no disk cache) before bulk screen."""
    from core.trade_date_util import DEFAULT_MIN_SYMBOL_SESSION_RATIO, assert_pack_session_fresh

    syms = probe_symbols or ["600519.SH", "000001.SZ"]
    ratio = (
        float(min_symbol_ratio)
        if min_symbol_ratio is not None
        else DEFAULT_MIN_SYMBOL_SESSION_RATIO
    )
    pack = build_live_pack(
        symbols=syms,
        indices_profile="minimal",
        enrich=False,
        fetch_breadth=False,
        fetch_indices=True,
        fetch_cfg={"daily_bar_cache": False, "parallel_enabled": len(syms) > 1},
        fail_on_stale=False,
        min_symbol_session_ratio=ratio,
    )
    if fail_on_stale:
        assert_pack_session_fresh(pack, fail_on_stale=True, min_symbol_ratio=ratio)
    return pack.get("meta") or {}


def build_live_pack(
    *,
    symbols: list[str],
    indices_profile: str = "comprehensive",
    run_id: str | None = None,
    enrich: bool = True,
    fetch_breadth: bool = True,
    fetch_indices: bool = True,
    fetch_cfg: dict[str, Any] | None = None,
    fail_on_stale: bool = False,
    min_symbol_session_ratio: float | None = None,
) -> dict[str, Any]:
    global _FETCH_STATUS, _FETCH_MESSAGES
    _FETCH_STATUS = {}
    _FETCH_MESSAGES = []

    pro = _get_pro()
    if pro is None:
        raise RuntimeError("TUSHARE_TOKEN not set; use --fixture or export TUSHARE_TOKEN")

    _status("tushare", "ok")
    cfg = {**load_fetch_concurrency_config(), **(fetch_cfg or {})}
    symbols_norm = normalize_symbols(symbols)
    lookback = fetch_lookback()
    name_map = load_stock_name_map(pro) if symbols_norm else {}
    use_parallel = bool(cfg.get("parallel_enabled", True)) and len(symbols_norm) > 1
    use_cache = bool(cfg.get("daily_bar_cache", True))
    limiter = MinuteRateLimiter(int(cfg.get("calls_per_minute") or 450))

    symbol_instruments: list[dict[str, Any]] = []
    if use_parallel:
        def _worker(ts_code: str) -> dict[str, Any] | None:
            return _fetch_instrument(
                pro,
                ts_code,
                asset_type="stock",
                name=name_map.get(ts_code, ts_code),
                lookback=lookback,
                rate_limiter=limiter,
                use_daily_cache=use_cache,
            )

        fetched = parallel_map(
            symbols_norm,
            _worker,
            max_workers=int(cfg.get("max_workers") or 16),
            rate_limiter=None,
        )
        for ts_code in symbols_norm:
            inst = fetched.get(ts_code)
            if inst:
                symbol_instruments.append(inst)
            else:
                _FETCH_MESSAGES.append(f"skip stock (no data): {ts_code}")
    else:
        for ts_code in symbols_norm:
            name = name_map.get(ts_code) or _stock_name(pro, ts_code, name_map)
            inst = _fetch_instrument(
                pro,
                ts_code,
                asset_type="stock",
                name=name,
                lookback=lookback,
                rate_limiter=limiter,
                use_daily_cache=use_cache,
            )
            if inst:
                symbol_instruments.append(inst)
            else:
                _FETCH_MESSAGES.append(f"skip stock (no data): {ts_code}")

    if not symbol_instruments:
        raise RuntimeError(f"No stock data fetched for: {symbols_norm}")

    index_instruments: list[dict[str, Any]] = []
    if fetch_indices:
        index_entries = resolve_indices_for_profile(indices_profile)
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
                    rate_limiter=limiter,
                    use_daily_cache=False,
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

    breadth = _fetch_breadth(pro) if fetch_breadth else None
    if fetch_breadth:
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

    if enrich:
        enrich_a_share_context(pack, fetch_cfg=cfg)
    from core.trade_date_util import DEFAULT_MIN_SYMBOL_SESSION_RATIO, assert_pack_session_fresh

    ratio = (
        float(min_symbol_session_ratio)
        if min_symbol_session_ratio is not None
        else DEFAULT_MIN_SYMBOL_SESSION_RATIO
    )
    assert_pack_session_fresh(pack, fail_on_stale=fail_on_stale, min_symbol_ratio=ratio)
    return pack
