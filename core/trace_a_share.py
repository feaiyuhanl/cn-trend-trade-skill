"""Merge pack A-share slots into trace (script-side, Agent 勿手编)."""

from __future__ import annotations

from typing import Any


def merge_pack_a_share_into_trace(trace: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    """Sync market_filter / theme_assessment / gaps from enrich output."""
    mf = trace.setdefault("market_filter", {})
    slots = pack.get("slots") or {}
    tc = slots.get("theme_context") or {}

    retreats = tc.get("sector_retreats") or (slots.get("market_filter_hints") or {}).get(
        "sector_retreats"
    )
    mf["sector_retreats"] = retreats if retreats is not None else mf.get("sector_retreats", [])

    sent = pack.get("market_sentiment") or {}
    if sent:
        mf["sentiment_tier"] = sent.get("tier")
        mf["limit_ratio"] = sent.get("limit_ratio")
        mf["break_rate"] = sent.get("break_rate")
        mf["max_lianban"] = sent.get("max_lianban")
        ep = sent.get("entry_policy")
        if ep in ("no", "reduced", "yes") and not trace.get("_mf_allow_locked"):
            cur = mf.get("allow_new_trend_trade")
            if ep == "no":
                mf["allow_new_trend_trade"] = "no"
            elif ep == "reduced" and cur in (None, "", "yes"):
                mf["allow_new_trend_trade"] = "reduced"

    if tc.get("themes"):
        trace["theme_assessment"] = tc["themes"]

    gaps: list[str] = list(trace.get("gaps") or [])
    fs = (pack.get("meta") or {}).get("fetch_status") or {}
    for key in ("sentiment", "quality_gate", "event_risk"):
        if fs.get(key) == "skip" and f"pack.{key} skipped" not in " ".join(gaps):
            gaps.append(f"pack.{key} skipped（live 权限或 API 不可用）")
    if not sent and "market_sentiment 缺失" not in " ".join(gaps):
        gaps.append("market_sentiment 缺失；assemble 须运行 enrich")
    trace["gaps"] = gaps
    return trace
