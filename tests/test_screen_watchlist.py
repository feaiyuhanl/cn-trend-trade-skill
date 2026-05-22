"""Tests for watchlist screening policy (no network)."""

from __future__ import annotations

from core.screen_watchlist import (
    apply_policy_row,
    apply_sector_retreat_downgrade,
    build_theme_index,
    cap_watch_pool_by_theme,
    detect_sector_retreat,
    load_watchlist_config,
    render_screen_report,
    score_symbol_base,
)


def test_load_config_has_policy():
    cfg = load_watchlist_config()
    assert cfg["symbols_flat"]
    assert cfg["policy"]["max_per_theme"] == 2
    assert "BK0427.DC" in cfg["themes"]


def test_1d_drop_downgrades_watch_pool():
    row = score_symbol_base(
        "601330.SH",
        "绿色动力",
        {
            "structure": "higher_highs_higher_lows",
            "price_above_ma20": True,
            "price_above_ma60": True,
            "ma20_slope_daily": 0.05,
            "ma60_slope_daily": 0.03,
            "ma60_slope_weekly": 0.02,
            "vol_ratio_5_20": 1.1,
            "distance_from_52w_high_pct": -10,
            "atr14_pct": 0.04,
            "_close": 9.23,
        },
        pct_1d=-5.14,
    )
    policy = load_watchlist_config()["policy"]
    row = apply_policy_row(
        row,
        policy=policy,
        theme_id="green_power",
        holdings_ts=set(),
        holding_themes=set(),
    )
    assert row["action"] == "wait"
    assert any("1日跌幅" in r for r in row["downgrade_reasons"])


def test_holding_same_theme_blocks_watch_pool():
    row = score_symbol_base(
        "000531.SZ",
        "穗恒运A",
        {
            "structure": "higher_highs_higher_lows",
            "price_above_ma20": True,
            "price_above_ma60": True,
            "ma20_slope_daily": 0.05,
            "ma60_slope_daily": 0.03,
            "ma60_slope_weekly": 0.02,
            "vol_ratio_5_20": 1.0,
            "distance_from_52w_high_pct": -10,
            "atr14_pct": 0.03,
            "_close": 7.56,
        },
        pct_1d=1.0,
    )
    policy = load_watchlist_config()["policy"]
    row = apply_policy_row(
        row,
        policy=policy,
        theme_id="green_power",
        holdings_ts={"601016.SH", "000591.SZ"},
        holding_themes={"green_power"},
    )
    assert row["action"] == "wait"


def test_sector_retreat_detected():
    theme_index = build_theme_index(
        {"green_power": {"ts_codes": ["A.SH", "B.SH", "C.SH", "D.SH"]}}
    )
    rows = [
        {"ts_code": "A.SH", "pct_chg_1d": -5.0, "theme": "green_power"},
        {"ts_code": "B.SH", "pct_chg_1d": -4.0, "theme": "green_power"},
        {"ts_code": "C.SH", "pct_chg_1d": -3.0, "theme": "green_power"},
        {"ts_code": "D.SH", "pct_chg_1d": -6.0, "theme": "green_power"},
    ]
    policy = {
        "sector_retreat": {
            "min_theme_symbols": 4,
            "min_fraction_down": 0.5,
            "min_median_drop_pct": 2.0,
        }
    }
    info = detect_sector_retreat(rows, theme_index, policy)
    assert info["allow_new_trend_trade"] == "no"
    assert len(info["sector_retreats"]) == 1


def test_sector_retreat_downgrades_pool():
    rows = [
        {
            "ts_code": "A.SH",
            "action": "watch_pool",
            "theme": "green_power",
            "downgrade_reasons": [],
        }
    ]
    apply_sector_retreat_downgrade(
        rows,
        {
            "allow_new_trend_trade": "no",
            "sector_retreats": [{"theme": "green_power"}],
        },
    )
    assert rows[0]["action"] == "wait"


def test_cap_per_theme():
    rows = [
        {"ts_code": "A", "action": "watch_pool", "score": 10, "theme": "t1"},
        {"ts_code": "B", "action": "watch_pool", "score": 9, "theme": "t1"},
        {"ts_code": "C", "action": "watch_pool", "score": 8, "theme": "t1"},
    ]
    cap_watch_pool_by_theme(rows, 2)
    assert sum(1 for r in rows if r["action"] == "watch_pool") == 2


def test_report_forbids_buy_wording():
    text = render_screen_report(
        {
            "meta": {"as_of": "2026-05-20", "run_id": "r1"},
            "market_filter": {"allow_new_trend_trade": "no", "regime_note": ""},
            "watch_pool": [],
            "watch_pullback": [],
            "near_high_trim": [],
            "avoid_count": 0,
            "gaps": [],
        }
    )
    assert "非买入推荐" in text
    assert "观察池" in text
