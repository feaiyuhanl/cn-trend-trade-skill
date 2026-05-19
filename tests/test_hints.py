from core.hints import compute_derived_hints


def _bar(i: int, close: float, vol: float = 1e6) -> dict:
    return {
        "id": f"b{i}",
        "trade_date": f"202601{i:02d}",
        "open": close - 1,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "pct_chg": 0.5,
        "vol": vol,
        "amount": None,
        "source_id": "test",
    }


def test_hints_uptrend():
    bars = [_bar(i, 100 + i * 2, vol=1e6 + i * 1e4) for i in range(1, 61)]
    h = compute_derived_hints(bars)
    assert h.get("price_above_ma20") is True
    assert h.get("structure") == "higher_highs_higher_lows"
    assert "vol_ratio_5_20" in h
