"""Tests for watchlist risk audit (no network)."""

from __future__ import annotations

from core.watchlist_risk_audit import (
    _classify_symbol,
    render_risk_report,
    run_audit,
)


def test_classify_high_tier_on_forecast_loss_small_cap():
    row = _classify_symbol(
        "000670.SZ",
        name="盈方微",
        qrec={"tier": "ok", "risk_flags": [], "reasons": [], "block_entry": False},
        erec={
            "event_flags": ["forecast_loss"],
            "notes": ["业绩预告 续亏"],
            "block_entry": True,
        },
        mv={"total_mv_yi": 74.0, "pe_ttm": None},
    )
    assert row["tier"] == "high"
    assert "续亏" in "".join(row["tags"])


def test_render_report_no_markdown_tables():
    result = {
        "meta": {"run_id": "t1", "as_of": "2026-05-21", "symbols": 2, "mode": "fixture"},
        "summary": {"block": 1, "high": 1, "warn": 0, "concept": 0, "ok": 0},
        "tiers": {
            "block": [
                {
                    "ts_code": "600666.SH",
                    "name": "奥瑞德",
                    "tier": "block",
                    "tags": ["ST风险"],
                    "risk_flags": ["st"],
                    "forecast_type": "",
                    "total_mv_yi": 156.0,
                    "pe_ttm": 111.0,
                }
            ],
            "high": [
                {
                    "ts_code": "000670.SZ",
                    "name": "盈方微",
                    "tier": "high",
                    "tags": ["业绩续亏"],
                    "risk_flags": ["forecast_loss"],
                    "forecast_type": "续亏",
                    "total_mv_yi": 74.0,
                    "pe_ttm": None,
                }
            ],
            "warn": [],
            "concept": [],
            "ok": [],
        },
    }
    text = render_risk_report(result)
    assert not any(ln.strip().startswith("|") for ln in text.splitlines())  # no markdown tables
    assert "**000670.SZ**" in text
    assert "第一档" in text
    assert "第二档" in text


def test_run_audit_fixture_writes_files(tmp_path):
    result = run_audit(live=False, out_dir=tmp_path, archive=False)
    assert (tmp_path / "watchlist_risk_report.md").exists()
    assert (tmp_path / "watchlist_risk_audit.json").exists()
    assert result["meta"]["symbols"] > 0
