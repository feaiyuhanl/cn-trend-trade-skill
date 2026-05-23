"""Fetch per-symbol fundamentals (market cap, valuation) for pack enrichment."""

from __future__ import annotations

from typing import Any


def _latest_trade_date(pro) -> str | None:
    from core.trade_date_util import latest_open_trade_date

    return latest_open_trade_date(pro)


def fetch_fundamentals_map(pro, ts_codes: list[str]) -> dict[str, dict[str, Any]]:
    """Return ts_code -> {total_mv_yi, circ_mv_yi, pe_ttm, pb, turnover_rate}."""
    import pandas as pd

    out: dict[str, dict[str, Any]] = {}
    if not pro or not ts_codes:
        return out
    trade_date = _latest_trade_date(pro)
    if not trade_date:
        return out
    wanted = {str(t).strip().upper() for t in ts_codes}
    try:
        df = pro.daily_basic(
            trade_date=trade_date,
            fields="ts_code,total_mv,circ_mv,pe_ttm,pb,turnover_rate",
        )
        if df is None or df.empty:
            return out
        for _, row in df.iterrows():
            ts = str(row["ts_code"]).strip().upper()
            if ts not in wanted:
                continue
            mv_wan = row.get("total_mv")
            mv_yi = None
            if mv_wan is not None and not pd.isna(mv_wan):
                mv_yi = round(float(mv_wan) / 10000.0, 2)
            circ_wan = row.get("circ_mv")
            circ_yi = None
            if circ_wan is not None and not pd.isna(circ_wan):
                circ_yi = round(float(circ_wan) / 10000.0, 2)
            pe = row.get("pe_ttm")
            try:
                pe_f = round(float(pe), 2) if pe is not None and not pd.isna(pe) else None
            except (TypeError, ValueError):
                pe_f = None
            pb = row.get("pb")
            try:
                pb_f = round(float(pb), 2) if pb is not None and not pd.isna(pb) else None
            except (TypeError, ValueError):
                pb_f = None
            tr = row.get("turnover_rate")
            try:
                tr_f = round(float(tr), 4) if tr is not None and not pd.isna(tr) else None
            except (TypeError, ValueError):
                tr_f = None
            out[ts] = {
                "total_mv_yi": mv_yi,
                "circ_mv_yi": circ_yi,
                "pe_ttm": pe_f,
                "pb": pb_f,
                "turnover_rate": tr_f,
                "trade_date": trade_date,
            }
    except Exception:
        pass
    return out


def avg_amount_mn_from_daily(daily_bars: list[dict[str, Any]], n: int = 20) -> float | None:
    """Mean daily amount (万元) over last n bars; Tushare amount unit preserved."""
    if len(daily_bars) < n:
        return None
    amounts = []
    for b in daily_bars[-n:]:
        a = b.get("amount")
        if a is not None:
            try:
                amounts.append(float(a))
            except (TypeError, ValueError):
                pass
    if not amounts:
        return None
    return round(sum(amounts) / len(amounts) / 10000.0, 2)


def build_fundamentals_slot(
    symbols: list[str],
    *,
    pro=None,
    pack_symbols: list[dict[str, Any]] | None = None,
    mode: str = "live",
) -> dict[str, Any]:
    """Slot for pack.slots.fundamentals — objective numbers only."""
    by_code: dict[str, dict[str, Any]] = {}
    mv_map = fetch_fundamentals_map(pro, symbols) if pro and mode == "live" else {}
    inst_by_ts = {str(s["ts_code"]).strip().upper(): s for s in (pack_symbols or [])}
    for ts in symbols:
        ts = str(ts).strip().upper()
        rec: dict[str, Any] = dict(mv_map.get(ts) or {})
        inst = inst_by_ts.get(ts)
        if inst:
            daily = (inst.get("bars") or {}).get("daily") or []
            avg_amt = avg_amount_mn_from_daily(daily)
            if avg_amt is not None:
                rec["avg_amount_20d_mn"] = avg_amt
        by_code[ts] = rec
    return {
        "version": "1.0.0",
        "mode": mode,
        "symbols": by_code,
    }
