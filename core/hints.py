from __future__ import annotations

from typing import Any

import numpy as np


def _closes(bars: list[dict[str, Any]]) -> np.ndarray:
    if not bars:
        return np.array([])
    return np.array([float(b["close"]) for b in bars], dtype=float)


def _vols(bars: list[dict[str, Any]]) -> np.ndarray:
    if not bars:
        return np.array([])
    return np.array([float(b["vol"] or 0) for b in bars], dtype=float)


def _sma(arr: np.ndarray, n: int) -> float | None:
    if len(arr) < n:
        return None
    return float(np.mean(arr[-n:]))


def _slope(arr: np.ndarray, ma_n: int, lookback: int = 5) -> float | None:
    if len(arr) < ma_n + lookback:
        return None
    ma_now = np.mean(arr[-ma_n:])
    ma_prev = np.mean(arr[-ma_n - lookback : -lookback])
    if ma_prev == 0:
        return None
    return float((ma_now - ma_prev) / ma_prev)


def _atr14(bars: list[dict[str, Any]]) -> float | None:
    if len(bars) < 15:
        return None
    trs = []
    for i in range(1, len(bars)):
        h = float(bars[i]["high"])
        l = float(bars[i]["low"])
        pc = float(bars[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < 14:
        return None
    return float(np.mean(trs[-14:]))


def _structure_label(bars: list[dict[str, Any]], window: int = 20) -> str:
    if len(bars) < window:
        return "insufficient_data"
    seg = bars[-window:]
    highs = [float(b["high"]) for b in seg]
    lows = [float(b["low"]) for b in seg]
    mid = window // 2
    hh = max(highs[mid:]) > max(highs[:mid])
    hl = min(lows[mid:]) > min(lows[:mid])
    lh = max(highs[mid:]) < max(highs[:mid])
    ll = min(lows[mid:]) < min(lows[:mid])
    if hh and hl:
        return "higher_highs_higher_lows"
    if lh and ll:
        return "lower_highs_lower_lows"
    return "range_bound"


def compute_derived_hints(
    daily_bars: list[dict[str, Any]],
    weekly_bars: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Numeric hints only — no buy/sell signals."""
    hints: dict[str, Any] = {}
    closes = _closes(daily_bars)
    vols = _vols(daily_bars)
    if len(closes) == 0:
        return hints

    last_close = float(closes[-1])
    ma20 = _sma(closes, 20)
    ma60 = _sma(closes, 60)

    s20 = _slope(closes, 20)
    s60 = _slope(closes, 60)
    if s20 is not None:
        hints["ma20_slope_daily"] = round(s20, 6)
    if s60 is not None:
        hints["ma60_slope_daily"] = round(s60, 6)

    if ma20 is not None:
        hints["price_above_ma20"] = last_close > ma20
        hints["ma20_value"] = round(ma20, 4)
    if ma60 is not None:
        hints["price_above_ma60"] = last_close > ma60
        hints["ma60_value"] = round(ma60, 4)

    if len(vols) >= 20:
        v5 = float(np.mean(vols[-5:]))
        v20 = float(np.mean(vols[-20:]))
        if v20 > 0:
            hints["vol_ratio_5_20"] = round(v5 / v20, 4)

    atr = _atr14(daily_bars)
    if atr is not None and last_close > 0:
        hints["atr14"] = round(atr, 4)
        hints["atr14_pct"] = round(atr / last_close, 6)

    if len(closes) >= 20:
        high_52w = float(np.max(closes[-min(252, len(closes)) :]))
        if high_52w > 0:
            hints["distance_from_52w_high_pct"] = round((last_close / high_52w - 1) * 100, 4)

    if len(daily_bars) >= 40:
        highs = [float(b["high"]) for b in daily_bars[-60:]]
        sorted_h = sorted(set(round(h, 2) for h in highs), reverse=True)
        hints["resistance_levels"] = sorted_h[:3]

    hints["structure"] = _structure_label(daily_bars)

    if weekly_bars:
        wcloses = _closes(weekly_bars)
        ws60 = _slope(wcloses, 10, 3) if len(wcloses) >= 13 else None
        if ws60 is not None:
            hints["ma60_slope_weekly"] = round(ws60, 6)

    return hints
