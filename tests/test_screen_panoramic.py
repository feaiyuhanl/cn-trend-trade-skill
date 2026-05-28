"""Tests for panoramic watchlist screen."""

from __future__ import annotations

import json
from pathlib import Path

from core.init_trace import WATCHLIST_SCREEN_LENSES, init_trace_from_pack
from core.screen_ai import fill_screen_trace_from_pack
from core.screen_panoramic import render_screen_panoramic_report

ROOT = Path(__file__).resolve().parent.parent
FIX_PACK = ROOT / "sample" / "market_pack.sample.json"


def test_watchlist_lenses_include_observation_framework():
    assert "watchlist-observation-framework" in WATCHLIST_SCREEN_LENSES
    assert len(WATCHLIST_SCREEN_LENSES) == 4


def test_fill_screen_trace_steps():
    pack = json.loads(FIX_PACK.read_text(encoding="utf-8"))
    trace = init_trace_from_pack(pack, playbook="watchlist-screen")
    trace = fill_screen_trace_from_pack(trace, pack)
    assert len(trace["steps"]) == len(WATCHLIST_SCREEN_LENSES)
    assert trace["steps"][0]["lens"] == "market-sentiment"
    assert trace_has_rank(trace)


def test_panoramic_report_sections():
    pack = json.loads(FIX_PACK.read_text(encoding="utf-8"))
    trace = fill_screen_trace_from_pack(init_trace_from_pack(pack, playbook="watchlist-screen"), pack)
    result = {
        "meta": pack["meta"],
        "market_filter": trace["market_filter"],
        "market_sentiment": pack.get("market_sentiment"),
        "theme_context": (pack.get("slots") or {}).get("theme_context"),
        "watch_pool": [],
        "watch_pullback": [],
        "near_high_trim": [],
        "avoid_count": 0,
        "gaps": trace.get("gaps", []),
    }
    text = render_screen_panoramic_report(
        result, trace=trace, pack_meta=pack["meta"], pack=pack
    )
    assert "全景报告" in text
    assert "## 二、市场情绪" in text
    assert "## 三、题材共振" in text
    assert "## 四、推理链摘要" in text
    assert "非买入推荐" in text
    assert "market-sentiment" in text
    assert len(trace["steps"]) >= 4


def test_assess_symbol_score_breakdown():
    from core.screen_ai import _assess_symbol

    inst = {
        "ts_code": "600519.SH",
        "name": "贵州茅台",
        "derived_hints": {
            "structure": "higher_highs_higher_lows",
            "price_above_ma20": True,
            "price_above_ma60": True,
            "distance_from_weekly_high_pct": -12.0,
            "vol_ratio_5_20": 1.0,
            "amount_ratio_5_20": 1.0,
            "ma20_slope_daily": 0.02,
            "ma20_value": 100.0,
        },
        "bars": {"daily": [{"pct_chg": 1.0}], "weekly": [{"id": "w1"}], "monthly": []},
        "theme_meta": {},
    }
    flat = {
        "symbol:600519.SH.derived_hints.structure": "higher_highs_higher_lows",
        "symbol:600519.SH.derived_hints.price_above_ma20": True,
        "symbol:600519.SH.derived_hints.distance_from_weekly_high_pct": -12.0,
        "symbol:600519.SH.derived_hints.vol_ratio_5_20": 1.0,
        "symbol:600519.SH.derived_hints.amount_ratio_5_20": 1.0,
        "symbol:600519.SH.fundamentals.total_mv_yi": 2000.0,
        "symbol:600519.SH.fundamentals.avg_amount_20d_mn": 500.0,
        "symbol:600519.SH.fundamentals.pe_ttm": 25.0,
        "symbol:600519.SH.quality.tier": "ok",
    }
    sc = _assess_symbol(inst, flat, {})
    assert sc.get("score_breakdown")
    assert sc.get("trap_vol_reason")
    assert sc.get("action_rule")
    assert sc["safety_rank"] >= 0


def trace_has_rank(trace: dict) -> bool:
    for dec in trace.get("decisions", {}).values():
        if (dec.get("screen") or {}).get("safety_rank") is not None:
            return True
    return False
