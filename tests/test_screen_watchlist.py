"""Tests for watchlist screening policy (no network)."""

from __future__ import annotations

from core.screen_watchlist import (
    apply_policy_row,
    apply_sector_retreat_downgrade,
    build_theme_index,
    cap_watch_pool_by_theme,
    candidate_row_from_inst,
    detect_sector_retreat,
    load_watchlist_config,
    render_screen_report,
    run_merge_screen_trace,
    trace_has_ai_ranks,
)


def test_load_config_has_policy():
    cfg = load_watchlist_config()
    assert cfg["symbols_flat"]
    assert cfg["policy"]["max_per_theme"] == 2
    assert "BK0427.DC" in cfg["themes"]


def _strong_hints() -> dict:
    return {
        "structure": "higher_highs_higher_lows",
        "price_above_ma20": True,
        "price_above_ma60": True,
        "ma20_slope_daily": 0.05,
        "ma60_slope_daily": 0.03,
        "ma60_slope_weekly": 0.02,
        "vol_ratio_5_20": 1.1,
        "distance_from_52w_high_pct": -10,
        "distance_from_weekly_high_pct": -18,
        "atr14_pct": 0.04,
        "_close": 9.23,
    }


def test_1d_drop_downgrades_watch_pool():
    row = candidate_row_from_inst(
        "601330.SH",
        "绿色动力",
        _strong_hints(),
        pct_1d=-5.14,
    )
    row["action"] = "watch_pool"
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
    row = candidate_row_from_inst(
        "000531.SZ",
        "穗恒运A",
        _strong_hints(),
        pct_1d=1.0,
    )
    row["action"] = "watch_pool"
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


def test_cap_per_theme_uses_safety_rank():
    rows = [
        {"ts_code": "A", "action": "watch_pool", "safety_rank": 90, "theme": "t1"},
        {"ts_code": "B", "action": "watch_pool", "safety_rank": 80, "theme": "t1"},
        {"ts_code": "C", "action": "watch_pool", "safety_rank": 70, "theme": "t1"},
    ]
    cap_watch_pool_by_theme(rows, 2)
    assert sum(1 for r in rows if r["action"] == "watch_pool") == 2
    assert rows[2]["action"] == "wait"


def test_report_forbids_buy_wording():
    text = render_screen_report(
        {
            "meta": {"as_of": "2026-05-20", "run_id": "r1", "trade_date": "20260520"},
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


def test_trace_has_ai_ranks():
    assert not trace_has_ai_ranks({"decisions": {"A.SH": {"screen": {"action": "pending"}}}})
    assert trace_has_ai_ranks({"decisions": {"A.SH": {"screen": {"safety_rank": 55}}}})


def test_run_merge_screen_trace(tmp_path):
    pack = {
        "meta": {"run_id": "t1", "trade_date": "20260520", "as_of": "2026-05-20"},
        "symbols": [
            {
                "ts_code": "600519.SH",
                "name": "茅台",
                "bars": {
                    "daily": [
                        {
                            "id": "b1",
                            "trade_date": "20260520",
                            "close": 100,
                            "pct_chg": 1.0,
                            "high": 101,
                            "low": 99,
                            "open": 100,
                            "vol": 1e6,
                        }
                    ]
                },
                "derived_hints": _strong_hints(),
            }
        ],
        "slots": {
            "quality_gate": {
                "symbols": {"600519.SH": {"tier": "ok", "risk_flags": []}},
            },
            "event_risk": {"symbols": {}},
        },
    }
    trace = {
        "meta": {"playbook": "watchlist-screen", "rules_profile": "watchlist-screen"},
        "decisions": {
            "600519.SH": {
                "facts_used": ["symbol:600519.SH.derived_hints.structure"],
                "screen": {
                    "safety_rank": 88,
                    "action": "watch_pool",
                    "trap_risk": "low",
                    "volume_context": "bottom_accumulation",
                    "rank_rationale": "离周/月前高仍有空间，流动性好",
                },
            }
        },
    }
    pack_path = tmp_path / "screen_pack.json"
    trace_path = tmp_path / "screen_trace.json"
    import json

    pack_path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    trace_path.write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")
    result = run_merge_screen_trace(
        pack_path=pack_path,
        trace_path=trace_path,
        out_dir=tmp_path,
    )
    assert result["watch_pool"]
    assert result["watch_pool"][0]["safety_rank"] == 88
