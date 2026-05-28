"""Pure trend-score TOP N ranking (independent of watch_pool policy caps)."""

from __future__ import annotations

from typing import Any

from core.merge_screen_trace import sort_key_ranked


def _is_quality_blocked(row: dict[str, Any], pack: dict[str, Any] | None) -> bool:
    ts = row.get("ts_code", "")
    if pack:
        qrec = ((pack.get("slots") or {}).get("quality_gate") or {}).get("symbols", {}).get(ts) or {}
        if qrec.get("tier") == "block":
            return True
    if row.get("action") == "avoid" and row.get("risk_flags"):
        return True
    return False


def build_trend_top10(
    ranked: list[dict[str, Any]],
    *,
    scope: str = "watchlist",
    top_n: int = 10,
    watchlist_ts: set[str] | None = None,
    watch_pool_ts: set[str] | None = None,
    pack: dict[str, Any] | None = None,
    symbol_scope: set[str] | None = None,
) -> dict[str, Any]:
    """Build trend_top10 from safety_rank — quality block only, no theme/sentiment caps."""
    watchlist_ts = watchlist_ts or set()
    watch_pool_ts = watch_pool_ts or set()
    candidates = []
    for row in ranked:
        if row.get("safety_rank") is None:
            continue
        ts = row["ts_code"]
        if symbol_scope is not None and ts not in symbol_scope:
            continue
        if _is_quality_blocked(row, pack):
            continue
        candidates.append(row)

    candidates.sort(key=sort_key_ranked)
    stocks = []
    for i, row in enumerate(candidates[:top_n], start=1):
        stocks.append(
            {
                "rank": i,
                "ts_code": row["ts_code"],
                "name": row.get("name", ""),
                "safety_rank": row.get("safety_rank"),
                "position_band": row.get("position_band", "unknown"),
                "structure": row.get("structure"),
                "distance_from_52w_high_pct": row.get("distance_from_52w_high_pct"),
                "distance_from_weekly_high_pct": row.get("distance_from_weekly_high_pct"),
                "price_percentile_2y": row.get("price_percentile_2y"),
                "trap_risk": row.get("trap_risk"),
                "action": row.get("action"),
                "in_watchlist": row["ts_code"] in watchlist_ts,
                "in_watch_pool": row["ts_code"] in watch_pool_ts,
                "note": row.get("note") or row.get("weekly_position", ""),
                "score_breakdown": row.get("score_breakdown"),
            }
        )
    return {
        "scope": scope,
        "ranked_by": "safety_rank",
        "top_n": top_n,
        "note": "趋势分排行（非买入推荐，不受观察池策略上限/题材熔断限制）",
        "stocks": stocks,
    }
