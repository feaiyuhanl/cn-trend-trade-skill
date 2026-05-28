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

# Bulk screen: require this fraction of symbols to have the expected session bar
DEFAULT_MIN_SYMBOL_SESSION_RATIO = 0.95


class DataStaleError(RuntimeError):
    """Raised when live data is behind expected_trade_session_date (fail-fast)."""


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


def _last_bar_trade_date(inst: dict[str, Any]) -> str | None:
    daily = (inst.get("bars") or {}).get("daily") or []
    if not daily:
        return None
    td = str(daily[-1].get("trade_date") or "")
    return td if len(td) == 8 else None


def max_trade_date_from_pack(pack: dict[str, Any]) -> str | None:
    """Max trade_date across indices and symbols daily bars."""
    best = ""
    for key in ("indices", "symbols"):
        for inst in pack.get(key) or []:
            td = _last_bar_trade_date(inst)
            if td and td > best:
                best = td
    return best or None


def max_trade_date_from_indices(pack: dict[str, Any]) -> str | None:
    best = ""
    for inst in pack.get("indices") or []:
        td = _last_bar_trade_date(inst)
        if td and td > best:
            best = td
    return best or None


def symbol_session_coverage(
    pack: dict[str, Any],
    *,
    expected: str | None = None,
) -> tuple[int, int, float]:
    """Count symbols whose last daily bar is on or after expected session."""
    expected = expected or expected_trade_session_date()
    fresh = 0
    total = 0
    for inst in pack.get("symbols") or []:
        td = _last_bar_trade_date(inst)
        if not td:
            continue
        total += 1
        if td >= expected:
            fresh += 1
    ratio = (fresh / total) if total else 1.0
    return fresh, total, ratio


def assess_pack_data_session(
    pack: dict[str, Any],
    *,
    expected: str | None = None,
    min_symbol_ratio: float = DEFAULT_MIN_SYMBOL_SESSION_RATIO,
) -> dict[str, Any]:
    """Decide if pack bars match the session we should be trading on.

    Stale when benchmark indices OR enough individual symbols lag expected session.
    Using only global max(bar dates) would mark fresh when indices updated but
    thousands of stocks are still on the previous day (common with disk cache).
    """
    expected = expected or expected_trade_session_date()
    index_td = max_trade_date_from_indices(pack) or ""
    fresh, total, ratio = symbol_session_coverage(pack, expected=expected)
    pack_max = max_trade_date_from_pack(pack) or ""

    reasons: list[str] = []
    if not index_td or index_td < expected:
        reasons.append(
            f"大盘指数 K 线仅到 {index_td or '无'}，应使用 {expected}"
        )
    if total and ratio < min_symbol_ratio:
        reasons.append(
            f"个股仅 {fresh}/{total} 只含 {expected} 日线"
            f"（需 ≥{min_symbol_ratio:.0%}）"
        )

    stale = bool(reasons)
    # Authoritative session for regime / MA: index bar date when present
    trade_date = index_td or pack_max or expected

    return {
        "expected_trade_date": expected,
        "trade_date": trade_date,
        "index_trade_date": index_td or None,
        "pack_max_trade_date": pack_max or None,
        "symbol_fresh_count": fresh,
        "symbol_total": total,
        "symbol_fresh_ratio": round(ratio, 4),
        "min_symbol_session_ratio": min_symbol_ratio,
        "data_stale": stale,
        "data_stale_reasons": reasons,
    }


def build_data_stale_notice(
    *,
    expected_trade_date: str,
    actual_trade_date: str,
    fetch_messages: list[str] | None = None,
    stale_reasons: list[str] | None = None,
    symbol_fresh_ratio: float | None = None,
    symbol_fresh_count: int | None = None,
    symbol_total: int | None = None,
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
        "勿使用 `--allow-stale` 强行继续（仅调试）。"
    )
    headline = (
        f"行情滞后：应使用交易日 {expected_trade_date}，"
        f"指数/有效 K 线仅到 {actual_trade_date}。"
    )
    if stale_reasons:
        headline += " " + "；".join(stale_reasons)
    elif symbol_fresh_ratio is not None and symbol_total:
        headline += (
            f" 个股含当日 K 线：{symbol_fresh_count}/{symbol_total}"
            f"（{symbol_fresh_ratio:.1%}）。"
        )
    return {
        "data_stale_cause": cause,
        "data_stale_headline": headline,
        "data_stale_detail": cause_zh,
        "data_stale_retry": retry,
        "data_stale_notice": f"{headline} {cause_zh} {retry}",
    }


def attach_pack_trade_date_meta(
    pack: dict[str, Any],
    *,
    pro=None,
    min_symbol_ratio: float = DEFAULT_MIN_SYMBOL_SESSION_RATIO,
) -> None:
    """Set meta.trade_date / expected_trade_date / data_stale on pack."""
    meta = pack.setdefault("meta", {})
    assessment = assess_pack_data_session(pack, min_symbol_ratio=min_symbol_ratio)
    meta.update(assessment)
    if assessment["data_stale"]:
        notice = build_data_stale_notice(
            expected_trade_date=assessment["expected_trade_date"],
            actual_trade_date=str(assessment["trade_date"]),
            fetch_messages=list(meta.get("fetch_messages") or []),
            stale_reasons=list(assessment.get("data_stale_reasons") or []),
            symbol_fresh_ratio=assessment.get("symbol_fresh_ratio"),
            symbol_fresh_count=assessment.get("symbol_fresh_count"),
            symbol_total=assessment.get("symbol_total"),
        )
        meta.update(notice)


def assert_pack_session_fresh(
    pack: dict[str, Any],
    *,
    fail_on_stale: bool = True,
    min_symbol_ratio: float = DEFAULT_MIN_SYMBOL_SESSION_RATIO,
) -> None:
    """Re-check freshness and abort live runs when data lags expected session."""
    attach_pack_trade_date_meta(pack, min_symbol_ratio=min_symbol_ratio)
    if not fail_on_stale:
        return
    meta = pack.get("meta") or {}
    if meta.get("data_stale"):
        raise DataStaleError(
            meta.get("data_stale_notice")
            or (
                f"行情未刷新到 {meta.get('expected_trade_date')}，"
                f"当前仅 {meta.get('trade_date')}；已中止，请稍后重试。"
            )
        )
