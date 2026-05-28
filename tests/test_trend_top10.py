"""Tests for trend TOP10 ranking."""

from __future__ import annotations

from core.trend_top10 import build_trend_top10


def _row(ts: str, rank: int, action: str = "wait") -> dict:
    return {
        "ts_code": ts,
        "name": ts,
        "safety_rank": rank,
        "action": action,
        "position_band": "mid_low",
        "structure": "higher_highs_higher_lows",
        "trap_risk": "low",
        "note": "test",
    }


def test_trend_top10_pure_rank():
    ranked = [
        _row("A.SH", 95, "wait"),
        _row("B.SH", 90, "watch_pool"),
        _row("C.SH", 85, "avoid"),
    ]
    pack = {
        "slots": {
            "quality_gate": {
                "symbols": {"C.SH": {"tier": "block", "risk_flags": ["st"]}},
            }
        }
    }
    out = build_trend_top10(
        ranked,
        scope="watchlist",
        top_n=10,
        watchlist_ts={"A.SH", "B.SH"},
        watch_pool_ts={"B.SH"},
        pack=pack,
    )
    assert len(out["stocks"]) == 2
    assert out["stocks"][0]["ts_code"] == "A.SH"
    assert out["stocks"][0]["rank"] == 1
    assert out["stocks"][0]["in_watchlist"] is True
    assert out["stocks"][0]["in_watch_pool"] is False
    assert out["stocks"][1]["in_watch_pool"] is True


def test_trend_top10_symbol_scope():
    ranked = [_row("A.SH", 95), _row("B.SH", 90)]
    out = build_trend_top10(
        ranked,
        scope="mainboard",
        top_n=10,
        symbol_scope={"B.SH"},
    )
    assert len(out["stocks"]) == 1
    assert out["stocks"][0]["ts_code"] == "B.SH"
