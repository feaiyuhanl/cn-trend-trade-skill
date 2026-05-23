from core.hints import compute_derived_hints


def _bar(i: int, close: float, vol: float = 1e6, high: float | None = None) -> dict:
    h = high if high is not None else close + 2
    return {
        "id": f"b{i}",
        "trade_date": f"202601{i:02d}",
        "open": close - 1,
        "high": h,
        "low": close - 2,
        "close": close,
        "pct_chg": 0.5,
        "vol": vol,
        "amount": vol * close,
        "source_id": "test",
    }


def test_hints_uptrend():
    bars = [_bar(i, 100 + i * 2, vol=1e6 + i * 1e4) for i in range(1, 61)]
    h = compute_derived_hints(bars)
    assert h.get("price_above_ma20") is True
    assert h.get("structure") == "higher_highs_higher_lows"
    assert "vol_ratio_5_20" in h


def test_hints_weekly_monthly_distance():
    daily = [_bar(i, 50 + i * 0.5) for i in range(1, 121)]
    weekly = [_bar(i, 40 + i * 2, high=45 + i * 2) for i in range(1, 53)]
    monthly = [_bar(i, 30 + i * 5, high=35 + i * 5) for i in range(1, 25)]
    h = compute_derived_hints(daily, weekly, monthly)
    assert "distance_from_weekly_high_pct" in h
    assert "distance_from_monthly_high_pct" in h
    assert h["distance_from_weekly_high_pct"] < 0
    assert "amount_ratio_5_20" in h
