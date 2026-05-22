"""Unified A-share trade session date (YYYYMMDD).

Wall-clock `as_of` is when the pack was built; `trade_date` is the latest daily bar
session used for pct_chg / MA / theme / sentiment. Before 15:05 local time on a
trading day, expect the previous session.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

# A-share cash session closes 15:00; allow a few minutes for bar publication
SESSION_CLOSE_HOUR = 15
SESSION_DATA_READY_MINUTE = 5


def expected_trade_session_date(now: datetime | None = None) -> str:
    """Latest session whose daily bar we should use (weekends roll back)."""
    now = now or datetime.now()
    if now.hour < SESSION_CLOSE_HOUR or (
        now.hour == SESSION_CLOSE_HOUR and now.minute < SESSION_DATA_READY_MINUTE
    ):
        now = now - timedelta(days=1)
    while now.weekday() >= 5:
        now = now - timedelta(days=1)
    return now.strftime("%Y%m%d")


def latest_open_trade_date(pro, *, end_cap: str | None = None) -> str | None:
    """Last SSE open day from Tushare trade_cal, capped at expected session."""
    end = end_cap or expected_trade_session_date()
    try:
        end_dt = datetime.strptime(end, "%Y%m%d")
        start = (end_dt - timedelta(days=400)).strftime("%Y%m%d")
        df = pro.trade_cal(
            exchange="SSE",
            start_date=start,
            end_date=end,
            is_open="1",
        )
        if df is None or df.empty:
            return None
        return str(df.iloc[-1]["cal_date"])
    except Exception:
        return None


def _probe_limit_list_trade_date(pro, start: str, max_back: int = 10) -> str | None:
    """Fallback when trade_cal unavailable; try expected session first."""
    end_dt = datetime.strptime(start, "%Y%m%d")
    for _ in range(max_back):
        while end_dt.weekday() >= 5:
            end_dt -= timedelta(days=1)
        d = end_dt.strftime("%Y%m%d")
        try:
            up = pro.limit_list_d(trade_date=d, limit_type="U")
            if up is not None and not up.empty:
                return d
        except Exception:
            pass
        end_dt -= timedelta(days=1)
    return None


def resolve_latest_trade_date(
    pro=None,
    *,
    pack: dict[str, Any] | None = None,
) -> str:
    """Authoritative YYYYMMDD for theme/sentiment/limit_list enrichment.

    When pack bars exist, they win over trade_cal so pct_chg/MA/theme stay aligned.
    """
    expected = expected_trade_session_date()
    from_pack = max_trade_date_from_pack(pack) if pack else None
    if from_pack:
        return from_pack
    if pro is not None:
        cal = latest_open_trade_date(pro, end_cap=expected)
        if cal:
            return cal
        probed = _probe_limit_list_trade_date(pro, expected)
        if probed:
            return probed
    return expected


def max_trade_date_from_pack(pack: dict[str, Any]) -> str | None:
    """Max trade_date across indices and symbols daily bars."""
    best = ""
    for key in ("indices", "symbols"):
        for inst in pack.get(key) or []:
            daily = (inst.get("bars") or {}).get("daily") or []
            if not daily:
                continue
            td = str(daily[-1].get("trade_date") or "")
            if len(td) == 8 and td > best:
                best = td
    return best or None


def build_data_stale_notice(
    *,
    expected_trade_date: str,
    actual_trade_date: str,
    fetch_messages: list[str] | None = None,
) -> dict[str, str]:
    """Human-readable stale-data explanation (external lag vs transient errors)."""
    msgs = fetch_messages or []
    ak_errors = [m for m in msgs if m.lower().startswith("akshare ") and ":" in m]
    ak_empty = [m for m in msgs if "akshare supplement empty" in m]
    has_network = any(
        tok in " ".join(ak_errors).lower()
        for tok in ("connection", "timeout", "remote", "disconnected", "reset")
    )

    if has_network and ak_empty:
        cause = "external_or_network"
        cause_zh = (
            "外部行情源尚未放出当日收盘 K 线，和/或 akshare 补数请求失败（网络中断）。"
            "这不是分析逻辑用错交易日，而是数据源侧尚未就绪。"
        )
    elif ak_empty or ak_errors:
        cause = "external_not_ready"
        cause_zh = (
            "当日 A 股已收盘，但 Tushare 日线常晚于收盘入库；程序已尝试用 akshare 补当日 K 线，"
            "仍未拿到收盘价。属于外部数据刷新滞后，不是选股规则算错。"
        )
    else:
        cause = "external_not_ready"
        cause_zh = (
            "当日 A 股已收盘，但拉取到的 K 线仍停留在上一交易日。"
            "属于外部行情数据尚未更新到本程序，不是交易日判断错误。"
        )

    retry = (
        "请稍后重试：建议首次在 15:30–17:00 再跑；若仍滞后，可 18:00 后或次日开盘前再跑 "
        "`python cli.py --screen-watchlist` / `--assemble`。"
    )
    headline = (
        f"行情滞后：应使用交易日 {expected_trade_date}，当前 K 线仅到 {actual_trade_date}。"
    )
    return {
        "data_stale_cause": cause,
        "data_stale_headline": headline,
        "data_stale_detail": cause_zh,
        "data_stale_retry": retry,
        "data_stale_notice": f"{headline} {cause_zh} {retry}",
    }


def attach_pack_trade_date_meta(pack: dict[str, Any], *, pro=None) -> None:
    """Set meta.trade_date / expected_trade_date / data_stale on pack."""
    meta = pack.setdefault("meta", {})
    expected = expected_trade_session_date()
    data_td = max_trade_date_from_pack(pack) or resolve_latest_trade_date(pro, pack=pack)
    meta["expected_trade_date"] = expected
    meta["trade_date"] = data_td
    stale = bool(data_td and data_td < expected)
    meta["data_stale"] = stale
    if stale:
        notice = build_data_stale_notice(
            expected_trade_date=expected,
            actual_trade_date=data_td,
            fetch_messages=list(meta.get("fetch_messages") or []),
        )
        meta.update(notice)
