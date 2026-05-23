from __future__ import annotations

from typing import Any

import numpy as np


def _closes(bars: list[dict[str, Any]]) -> np.ndarray:
    if not bars:
        return np.array([])
    return np.array([float(b["close"]) for b in bars], dtype=float)


def _highs(bars: list[dict[str, Any]]) -> np.ndarray:
    if not bars:
        return np.array([])
    return np.array([float(b["high"]) for b in bars], dtype=float)


def _vols(bars: list[dict[str, Any]]) -> np.ndarray:
    if not bars:
        return np.array([])
    return np.array([float(b["vol"] or 0) for b in bars], dtype=float)


def _amounts(bars: list[dict[str, Any]]) -> np.ndarray:
    if not bars:
        return np.array([])
    out = []
    for b in bars:
        a = b.get("amount")
        out.append(float(a) if a is not None else 0.0)
    return np.array(out, dtype=float)


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


def _distance_from_high_pct(series: np.ndarray, last: float, lookback: int) -> float | None:
    if len(series) < 1 or last <= 0:
        return None
    window = series[-min(lookback, len(series)) :]
    peak = float(np.max(window))
    if peak <= 0:
        return None
    return round((last / peak - 1) * 100, 4)


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


def _up_days_with_expand_vol(daily_bars: list[dict[str, Any]], window: int = 10) -> int | None:
    if len(daily_bars) < window + 1:
        return None
    seg = daily_bars[-window:]
    v20 = _vols(daily_bars)
    if len(v20) < 20:
        return None
    base = float(np.mean(v20[-20:]))
    if base <= 0:
        return None
    count = 0
    for b in seg:
        pct = b.get("pct_chg")
        vol = float(b.get("vol") or 0)
        if pct is not None and float(pct) > 0 and vol / base >= 1.15:
            count += 1
    return count


def compute_derived_hints(
    daily_bars: list[dict[str, Any]],
    weekly_bars: list[dict[str, Any]] | None = None,
    monthly_bars: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Numeric hints only — no buy/sell signals or tier labels."""
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

    amounts = _amounts(daily_bars)
    if len(amounts) >= 20:
        a5 = float(np.mean(amounts[-5:]))
        a20 = float(np.mean(amounts[-20:]))
        if a20 > 0:
            hints["amount_ratio_5_20"] = round(a5 / a20, 4)

    up_exp = _up_days_with_expand_vol(daily_bars)
    if up_exp is not None:
        hints["up_days_vol_expand_10d"] = up_exp

    atr = _atr14(daily_bars)
    if atr is not None and last_close > 0:
        hints["atr14"] = round(atr, 4)
        hints["atr14_pct"] = round(atr / last_close, 6)

    if len(closes) >= 20:
        high_52w = float(np.max(closes[-min(252, len(closes)) :]))
        if high_52w > 0:
            hints["distance_from_52w_high_pct"] = round((last_close / high_52w - 1) * 100, 4)

    if len(daily_bars) >= 40:
        highs_d = [float(b["high"]) for b in daily_bars[-60:]]
        sorted_h = sorted(set(round(h, 2) for h in highs_d), reverse=True)
        hints["resistance_levels"] = sorted_h[:3]

    hints["structure"] = _structure_label(daily_bars)

    if weekly_bars:
        wcloses = _closes(weekly_bars)
        whighs = _highs(weekly_bars)
        if len(wcloses) >= 1:
            hints["weekly_bar_count"] = len(weekly_bars)
            w_last = float(wcloses[-1])
            dist_w = _distance_from_high_pct(whighs, w_last, 52)
            if dist_w is not None:
                hints["distance_from_weekly_high_pct"] = dist_w
            ws10 = _slope(wcloses, 10, 3) if len(wcloses) >= 13 else None
            if ws10 is not None:
                hints["ma10_slope_weekly"] = round(ws10, 6)
            wma20 = _sma(wcloses, 20) if len(wcloses) >= 20 else _sma(wcloses, 10)
            if wma20 is not None:
                hints["price_above_weekly_ma20"] = w_last > wma20

    if monthly_bars:
        mcloses = _closes(monthly_bars)
        mhighs = _highs(monthly_bars)
        if len(mcloses) >= 1:
            hints["monthly_bar_count"] = len(monthly_bars)
            m_last = float(mcloses[-1])
            dist_m = _distance_from_high_pct(mhighs, m_last, 24)
            if dist_m is not None:
                hints["distance_from_monthly_high_pct"] = dist_m
            ms6 = _slope(mcloses, 6, 2) if len(mcloses) >= 8 else None
            if ms6 is not None:
                hints["ma6_slope_monthly"] = round(ms6, 6)

    # Legacy alias
    if weekly_bars and "ma10_slope_weekly" in hints:
        hints["ma60_slope_weekly"] = hints["ma10_slope_weekly"]

    return hints
