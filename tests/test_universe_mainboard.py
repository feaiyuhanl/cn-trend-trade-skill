"""Tests for mainboard universe filter (no network)."""

from __future__ import annotations

from core.universe_mainboard import (
    _is_mainboard_ts_code,
    _liquidity_amount_mn,
    fetch_mainboard_stock_basic,
    load_universe_config,
)


def test_load_universe_config():
    cfg = load_universe_config()
    assert cfg.get("board_filter", {}).get("include_prefixes")


def test_mainboard_ts_code_filter():
    cfg = load_universe_config()
    assert _is_mainboard_ts_code("600519.SH", cfg) is True
    assert _is_mainboard_ts_code("000001.SZ", cfg) is True
    assert _is_mainboard_ts_code("002281.SZ", cfg) is True
    assert _is_mainboard_ts_code("688981.SH", cfg) is False
    assert _is_mainboard_ts_code("300750.SZ", cfg) is False
    assert _is_mainboard_ts_code("430047.BJ", cfg) is False


def test_liquidity_amount_mn_from_circ_mv():
    row = {"circ_mv": 100000.0, "turnover_rate": 2.5}
    assert _liquidity_amount_mn(row) == 2500.0


def test_liquidity_amount_mn_from_daily_amount():
    row = {"amount": 2808158.177}
    assert abs(_liquidity_amount_mn(row) - 280815.8177) < 0.01


def test_fetch_mainboard_stock_basic_mock():
    import pandas as pd

    class FakePro:
        def stock_basic(self, **kwargs):
            return pd.DataFrame(
                [
                    {"ts_code": "600519.SH", "name": "贵州茅台", "list_date": "20010827"},
                    {"ts_code": "688981.SH", "name": "中芯国际", "list_date": "20200716"},
                    {"ts_code": "002001.SZ", "name": "*ST测试", "list_date": "20100101"},
                    {"ts_code": "000001.SZ", "name": "平安银行", "list_date": "19910403"},
                ]
            )

    rows = fetch_mainboard_stock_basic(FakePro())
    codes = {r["ts_code"] for r in rows}
    assert "600519.SH" in codes
    assert "000001.SZ" in codes
    assert "688981.SH" not in codes
    assert not any("ST" in r["name"] for r in rows)


def test_chronic_loss_prefilter_mock():
    from core.universe_mainboard import apply_chronic_loss_prefilter

    class FakePro:
        pass

    kept, meta = apply_chronic_loss_prefilter(
        FakePro(),
        ["600519.SH", "000001.SZ"],
        cfg={"quality_prefilter": {"block_chronic_loss": False}},
    )
    assert kept == ["600519.SH", "000001.SZ"]
    assert meta.get("skipped") is True


def test_liquidity_no_cap_when_max_candidates_zero():
    from core.universe_mainboard import apply_liquidity_prefilter

    class FakePro:
        pass

    cands = [{"ts_code": f"60000{i}.SH", "name": f"n{i}"} for i in range(5)]
    out, meta = apply_liquidity_prefilter(
        FakePro(),
        cands,
        cfg={"liquidity_prefilter": {"min_amount_mn": 0, "max_candidates": 0}},
    )
    assert len(out) == 5
    assert meta.get("max_candidates") == 0
