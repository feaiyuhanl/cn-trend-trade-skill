"""Build canonical fact_index from market_pack (single source of numeric truth)."""

from __future__ import annotations

from typing import Any

from core.position_calc import holding_pnl_pct


def _latest_bar(bars: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not bars:
        return None
    return max(bars, key=lambda b: b.get("trade_date", ""))


def _instrument_facts(inst: dict[str, Any], prefix: str) -> dict[str, Any]:
    ts = inst["ts_code"]
    flat: dict[str, float | str | bool] = {}
    bars = inst.get("bars", {})
    daily = bars.get("daily") or []
    weekly = bars.get("weekly") or []
    monthly = bars.get("monthly") or []

    for tf, series in (("daily", daily), ("weekly", weekly), ("monthly", monthly)):
        flat[f"{prefix}{ts}.bars.{tf}.count"] = float(len(series))
        lb = _latest_bar(series)
        if lb:
            bid = lb["id"]
            for field in ("open", "high", "low", "close", "pct_chg", "vol"):
                val = lb.get(field)
                if val is not None:
                    flat[f"bar:{bid}:{field}"] = float(val) if isinstance(val, (int, float)) else val
            flat[f"{prefix}{ts}.latest_{tf}_bar_id"] = bid

    hints = inst.get("derived_hints") or {}
    for k, v in hints.items():
        if isinstance(v, (int, float, bool)):
            flat[f"{prefix}{ts}.derived_hints.{k}"] = v
        elif isinstance(v, str):
            flat[f"{prefix}{ts}.derived_hints.{k}"] = v
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, (int, float)):
                    flat[f"{prefix}{ts}.derived_hints.{k}.{i}"] = float(item)

    ld = _latest_bar(daily)
    if ld:
        flat[f"{prefix}{ts}.latest_close"] = float(ld["close"])

    return {
        "ts_code": ts,
        "name": inst.get("name", ""),
        "daily_bar_count": len(daily),
        "weekly_bar_count": len(weekly),
        "monthly_bar_count": len(monthly),
        "flat_keys": [k for k in flat if k.startswith(f"{prefix}{ts}") or k.startswith("bar:")],
    }, flat


def build_fact_index(pack: dict[str, Any]) -> dict[str, Any]:
    """Attach-ready fact_index: flat lookup + per-symbol data quality."""
    flat: dict[str, float | str | bool] = {}
    symbols_meta: dict[str, Any] = {}
    indices_meta: dict[str, Any] = {}
    holdings: dict[str, Any] = {}

    for inst in pack.get("symbols", []):
        meta, inst_flat = _instrument_facts(inst, "symbol:")
        flat.update(inst_flat)
        symbols_meta[inst["ts_code"]] = meta

    for inst in pack.get("indices", []):
        meta, inst_flat = _instrument_facts(inst, "index:")
        flat.update(inst_flat)
        indices_meta[inst["ts_code"]] = meta

    positions = (pack.get("user_context") or {}).get("positions") or []
    for pos in positions:
        ts = pos["ts_code"]
        close_key = f"symbol:{ts}.latest_close"
        close = flat.get(close_key)
        if close is None or pos.get("cost") is None:
            continue
        pnl = holding_pnl_pct(float(pos["cost"]), float(close))
        key = f"holding:{ts}:vs_cost_pct"
        flat[key] = round(pnl, 4)
        holdings[ts] = {
            "vs_cost_pct": round(pnl, 4),
            "cost": float(pos["cost"]),
            "shares": pos.get("shares"),
            "stop_price": pos.get("stop_price"),
            "latest_close": float(close),
        }

    # A-share context slots → flat keys for Agent fact_keys
    sent = pack.get("market_sentiment") or {}
    if sent:
        for k in (
            "limit_up",
            "limit_down",
            "limit_ratio",
            "break_rate",
            "max_lianban",
            "lianban_count",
        ):
            v = sent.get(k)
            if isinstance(v, (int, float)):
                flat[f"sentiment.{k}"] = float(v)
        if sent.get("tier"):
            flat["sentiment.tier"] = str(sent["tier"])

    slots = pack.get("slots") or {}
    tc = slots.get("theme_context") or {}
    for th in tc.get("themes") or []:
        tid = th.get("theme_id", "")
        flat[f"theme:{tid}.lifecycle_stage"] = str(th.get("lifecycle_stage", ""))
        flat[f"theme:{tid}.strength_rank"] = float(th.get("strength_rank") or 0)
        flat[f"theme:{tid}.median_pct_1d"] = float(th.get("median_pct_1d") or 0)
        if th.get("leader_limit_down"):
            flat[f"theme:{tid}.leader_limit_down"] = True
        for ld in th.get("leaders") or []:
            lts = ld.get("ts_code", "")
            if ld.get("pct_chg_1d") is not None:
                flat[f"symbol:{lts}.leader_pct_chg_1d"] = float(ld["pct_chg_1d"])

    qg = slots.get("quality_gate") or {}
    for ts, rec in (qg.get("symbols") or {}).items():
        flat[f"symbol:{ts}.quality.tier"] = str(rec.get("tier", "ok"))
        if rec.get("block_entry"):
            flat[f"symbol:{ts}.quality.block_entry"] = True
        for i, flag in enumerate(rec.get("risk_flags") or []):
            flat[f"symbol:{ts}.quality.risk_flags.{i}"] = str(flag)

    er = slots.get("event_risk") or {}
    for ts, rec in (er.get("symbols") or {}).items():
        if rec.get("block_entry"):
            flat[f"symbol:{ts}.event.block_entry"] = True
        for i, flag in enumerate(rec.get("event_flags") or []):
            flat[f"symbol:{ts}.event.flags.{i}"] = str(flag)

    fund = slots.get("fundamentals") or {}
    for ts, rec in (fund.get("symbols") or {}).items():
        for key in ("total_mv_yi", "circ_mv_yi", "pe_ttm", "pb", "turnover_rate", "avg_amount_20d_mn"):
            v = rec.get(key)
            if isinstance(v, (int, float)):
                flat[f"symbol:{ts}.fundamentals.{key}"] = float(v)

    return {
        "version": "1",
        "rules_version": None,
        "flat": flat,
        "symbols": symbols_meta,
        "indices": indices_meta,
        "holdings": holdings,
    }


def attach_fact_index(pack: dict[str, Any], *, rules_version: str | None = None) -> dict[str, Any]:
    idx = build_fact_index(pack)
    if rules_version:
        idx["rules_version"] = rules_version
    pack["fact_index"] = idx
    return pack


def resolve_evidence_numbers(
    pack: dict[str, Any], evidence_ids: list[str]
) -> set[float]:
    """Numbers allowed in observations for given evidence bar ids (+ linked hints)."""
    allowed: set[float] = set()
    idx = pack.get("fact_index") or build_fact_index(pack)
    flat = idx["flat"]

    for eid in evidence_ids:
        prefix = f"bar:{eid}:"
        for k, v in flat.items():
            if k.startswith(prefix) and isinstance(v, (int, float)):
                allowed.add(float(v))
        for inst in pack.get("symbols", []) + pack.get("indices", []):
            for tf in ("daily", "weekly", "monthly"):
                for bar in (inst.get("bars", {}).get(tf) or []):
                    if bar.get("id") != eid:
                        continue
                    ts_prefix = (
                        "symbol:" if inst in pack.get("symbols", []) else "index:"
                    )
                    ts = inst["ts_code"]
                    for hk, hv in (inst.get("derived_hints") or {}).items():
                        if isinstance(hv, (int, float)):
                            allowed.add(float(hv))
                        elif isinstance(hv, list):
                            for item in hv:
                                if isinstance(item, (int, float)):
                                    allowed.add(float(item))
                    for k, v in flat.items():
                        if k.startswith(f"{ts_prefix}{ts}.derived_hints."):
                            if isinstance(v, (int, float)):
                                allowed.add(float(v))

    return allowed
