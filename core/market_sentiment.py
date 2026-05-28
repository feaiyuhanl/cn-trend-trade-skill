"""Market sentiment: limit up/down ratio, break rate, lianban, hot themes."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_SENTIMENT_PATH = _ROOT / "config" / "sentiment.yaml"


def _load_config() -> dict[str, Any]:
    import yaml

    with _SENTIMENT_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _latest_trade_date(pro, max_back: int = 10) -> str | None:
    from core.trade_date_util import resolve_latest_trade_date

    return resolve_latest_trade_date(pro)


def _parse_lianban(row: Any) -> int:
    """连板数：优先 limit_times / up_stat 字段。"""
    for col in ("limit_times", "up_stat", "nums"):
        if col in row.index:
            val = row[col]
            if val is None or (isinstance(val, float) and val != val):
                continue
            s = str(val)
            digits = "".join(c if c.isdigit() else " " for c in s).split()
            if digits:
                try:
                    return int(float(digits[0]))
                except ValueError:
                    pass
            if "板" in s:
                for part in s.replace("天", "").split():
                    if part.isdigit():
                        return int(part)
    return 1


def fetch_market_sentiment(pro, *, trade_date: str | None = None) -> dict[str, Any] | None:
    """Build market_sentiment from Tushare limit_list_d (+ stock_basic industry)."""
    import pandas as pd

    trade_date = trade_date or _latest_trade_date(pro)
    if not trade_date:
        return None

    try:
        up_df = pro.limit_list_d(trade_date=trade_date, limit_type="U")
        down_df = pro.limit_list_d(trade_date=trade_date, limit_type="D")
    except Exception:
        return None

    up_df = up_df if up_df is not None else pd.DataFrame()
    down_df = down_df if down_df is not None else pd.DataFrame()

    limit_up = int(len(up_df))
    limit_down = int(len(down_df))
    limit_ratio = round(limit_up / max(limit_down, 1), 4)

    broken = 0
    lianban_list: list[dict[str, Any]] = []
    theme_counts: dict[str, int] = {}

    if not up_df.empty:
        basics = {}
        try:
            bdf = pro.stock_basic(exchange="", list_status="L", fields="ts_code,industry,name")
            if bdf is not None and not bdf.empty:
                for _, r in bdf.iterrows():
                    basics[str(r["ts_code"])] = {
                        "industry": str(r.get("industry") or "未知"),
                        "name": str(r.get("name") or ""),
                    }
        except Exception:
            pass

        for _, row in up_df.iterrows():
            ts = str(row.get("ts_code", ""))
            pct = float(row.get("pct_chg") or 0)
            open_times = int(row.get("open_times") or 0) if pd.notna(row.get("open_times")) else 0
            # 破板近似：曾开板次数>0 或 收盘涨幅明显低于涨停
            if open_times > 0 or pct < 9.5:
                broken += 1
            lb = _parse_lianban(row)
            if lb >= 2:
                ind = basics.get(ts, {}).get("industry", "未知")
                theme_counts[ind] = theme_counts.get(ind, 0) + 1
                lianban_list.append(
                    {
                        "ts_code": ts,
                        "name": basics.get(ts, {}).get("name", ts),
                        "lianban": lb,
                        "industry": ind,
                        "pct_chg": pct,
                    }
                )

    break_rate = round(broken / max(limit_up, 1), 4)
    lianban_list.sort(key=lambda x: -x["lianban"])
    max_lianban = max((x["lianban"] for x in lianban_list), default=0)
    hot_themes = sorted(
        [{"theme": k, "limit_up_count": v} for k, v in theme_counts.items()],
        key=lambda x: -x["limit_up_count"],
    )[:8]

    cfg = _load_config()
    th = cfg.get("thresholds") or {}
    tier = "normal"
    if limit_down >= th.get("limit_down_frozen_min", 80) or limit_ratio < th.get("limit_ratio_frozen", 0.35):
        tier = "frozen"
    elif limit_ratio > th.get("limit_ratio_euphoric", 3) or max_lianban >= th.get("max_lianban_euphoric", 5):
        tier = "euphoric"
    if break_rate >= th.get("break_rate_high", 0.45) and tier == "normal":
        tier = "euphoric"

    entry_policy = (cfg.get("entry_policy") or {}).get(tier, "yes")

    return {
        "id": f"sentiment_{trade_date}",
        "trade_date": trade_date,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "limit_ratio": limit_ratio,
        "break_rate": break_rate,
        "broken_count": broken,
        "max_lianban": max_lianban,
        "lianban_count": len(lianban_list),
        "lianban_stocks": lianban_list[:20],
        "hot_themes": hot_themes,
        "tier": tier,
        "entry_policy": entry_policy,
        "source_id": "tushare",
    }


def fetch_market_sentiment_with_retry(
    pro,
    *,
    max_attempts: int = 3,
    backoff_sec: tuple[float, ...] | list[float] = (65.0, 90.0, 120.0),
) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch sentiment with backoff on rate-limit / transient errors."""
    import time

    last_err = ""
    attempts = max(1, int(max_attempts))
    delays = list(backoff_sec) if backoff_sec else [65.0]
    for attempt in range(attempts):
        sent = fetch_market_sentiment(pro)
        if sent:
            return sent, None
        last_err = "limit_list_d 返回空或接口不可用"
        if attempt + 1 < attempts:
            wait = delays[min(attempt, len(delays) - 1)]
            time.sleep(wait)
    return None, (
        f"market_sentiment 获取失败（已重试 {attempts} 次）：{last_err}。"
        "常见原因：Tushare limit_list_d 频率超限(1次/分钟)或当日涨跌停列表未更新"
    )


def merge_into_breadth(pack: dict[str, Any], sentiment: dict[str, Any] | None) -> None:
    """Keep market_breadth backward-compatible."""
    if not sentiment:
        return
    pack["market_breadth"] = [
        {
            "id": sentiment["id"].replace("sentiment", "breadth"),
            "trade_date": sentiment["trade_date"],
            "advance": None,
            "decline": None,
            "limit_up": sentiment.get("limit_up"),
            "limit_down": sentiment.get("limit_down"),
            "source_id": sentiment.get("source_id", "tushare"),
        }
    ]


def fixture_sentiment() -> dict[str, Any]:
    return {
        "id": "sentiment_fixture",
        "trade_date": "20260519",
        "limit_up": 42,
        "limit_down": 18,
        "limit_ratio": 2.33,
        "break_rate": 0.28,
        "broken_count": 12,
        "max_lianban": 4,
        "lianban_count": 6,
        "lianban_stocks": [],
        "hot_themes": [{"theme": "电力设备", "limit_up_count": 5}],
        "tier": "normal",
        "entry_policy": "yes",
        "source_id": "fixture",
    }
