"""Tests for price percentile hints."""

from __future__ import annotations

from core.hints import compute_derived_hints


def _daily_bars(closes: list[float]) -> list[dict]:
    out = []
    for i, c in enumerate(closes):
        out.append(
            {
                "trade_date": f"20260{(i // 30 + 1):02d}{(i % 30 + 1):02d}",
                "open": c,
                "high": c * 1.02,
                "low": c * 0.98,
                "close": c,
                "pct_chg": 0.5,
                "vol": 1e6,
                "amount": 1e8,
            }
        )
    return out


def test_price_percentile_2y():
    closes = [10.0 + (i % 20) * 0.5 for i in range(260)]
    closes[-1] = 15.0
    hints = compute_derived_hints(_daily_bars(closes))
    assert "price_percentile_2y" in hints
    assert "distance_from_52w_low_pct" in hints
    assert hints["price_percentile_2y"] >= 0
    assert hints["price_percentile_2y"] <= 100
