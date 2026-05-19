"""Deterministic position / holding math (Agent must not hand-compute these)."""

from __future__ import annotations

from typing import Any


def holding_pnl_pct(cost: float, latest_close: float) -> float:
    if cost == 0:
        return 0.0
    return (latest_close - cost) / cost * 100.0


def initial_shares_from_risk(
    *,
    total_equity: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_price: float,
) -> int | None:
    risk_amount = total_equity * risk_per_trade_pct / 100.0
    per_share_risk = entry_price - stop_price
    if per_share_risk <= 0:
        return None
    return int(risk_amount / per_share_risk)


def stop_from_atr(entry_price: float, atr14: float, multiplier: float = 2.0) -> float:
    return round(entry_price - atr14 * multiplier, 4)


def build_position_computed(
    pack: dict[str, Any], ts_code: str, *, atr_multiplier: float = 2.0
) -> dict[str, Any]:
    """Framework numbers for position_plan.computed — Agent fills framework only."""
    flat = (pack.get("fact_index") or {}).get("flat", {})
    ctx = pack.get("user_context") or {}
    portfolio = ctx.get("portfolio") or {}
    out: dict[str, Any] = {"ts_code": ts_code}

    close = flat.get(f"symbol:{ts_code}.latest_close")
    atr = flat.get(f"symbol:{ts_code}.derived_hints.atr14")
    if close is not None and atr is not None:
        out["stop_atr2"] = stop_from_atr(float(close), float(atr), atr_multiplier)

    equity = portfolio.get("total_equity")
    risk_pct = portfolio.get("risk_per_trade_pct")
    positions = ctx.get("positions") or []
    pos = next((p for p in positions if p["ts_code"] == ts_code), None)
    stop_price = pos.get("stop_price") if pos else out.get("stop_atr2")
    if equity and risk_pct and close and stop_price:
        shares = initial_shares_from_risk(
            total_equity=float(equity),
            risk_per_trade_pct=float(risk_pct),
            entry_price=float(close),
            stop_price=float(stop_price),
        )
        if shares is not None:
            out["suggested_shares_risk_based"] = shares

    hold_key = f"holding:{ts_code}:vs_cost_pct"
    if hold_key in flat:
        out["vs_cost_pct"] = flat[hold_key]

    return out
