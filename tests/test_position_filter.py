"""Tests for mid-low position filter."""

from __future__ import annotations

from core.position_filter import (
    apply_position_gate,
    blocks_watch_pool,
    classify_position_band,
    is_near_high,
)
from core.screen_watchlist import candidate_row_from_inst


def _mid_low_hints() -> dict:
    return {
        "structure": "higher_highs_higher_lows",
        "price_above_ma20": True,
        "distance_from_52w_high_pct": -18.0,
        "distance_from_weekly_high_pct": -22.0,
        "distance_from_monthly_high_pct": -25.0,
        "price_percentile_2y": 45.0,
        "_close": 10.0,
    }


def _near_high_hints() -> dict:
    return {
        "structure": "higher_highs_higher_lows",
        "price_above_ma20": True,
        "distance_from_52w_high_pct": -4.0,
        "distance_from_weekly_high_pct": -6.0,
        "distance_from_monthly_high_pct": -6.0,
        "price_percentile_2y": 88.0,
        "_close": 50.0,
    }


def test_classify_mid_low():
    assert classify_position_band(_mid_low_hints()) == "mid_low"


def test_classify_near_high():
    assert classify_position_band(_near_high_hints()) == "near_high"
    assert is_near_high(_near_high_hints()) is True


def test_blocks_watch_pool_near_high():
    blocked, reason = blocks_watch_pool(_near_high_hints(), struct="higher_highs_higher_lows")
    assert blocked is True
    assert "52周" in reason or "分位" in reason or "周前高" in reason


def test_apply_position_gate_downgrades():
    row = candidate_row_from_inst("600000.SH", "Test", _near_high_hints(), pct_1d=1.0)
    row["action"] = "watch_pool"
    row["structure"] = "higher_highs_higher_lows"
    row["price_above_ma20"] = True
    row["distance_from_52w_high_pct"] = -4.0
    row["distance_from_weekly_high_pct"] = -6.0
    row["price_percentile_2y"] = 88.0
    out = apply_position_gate(row)
    assert out["action"] == "watch_pullback"
    assert any("位置过滤" in r for r in out.get("downgrade_reasons") or [])


def test_mid_low_passes_gate():
    blocked, _ = blocks_watch_pool(_mid_low_hints(), struct="higher_highs_higher_lows")
    assert blocked is False
