from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from core.fetch_live import build_live_pack


def _daily_df(n: int = 60, base: float = 100.0) -> pd.DataFrame:
    from datetime import datetime, timedelta

    rows = []
    start = datetime(2026, 1, 2)
    for i in range(n):
        d = (start + timedelta(days=i)).strftime("%Y%m%d")
        c = base + i * 0.5
        rows.append(
            {
                "trade_date": d,
                "open": c - 1,
                "high": c + 1,
                "low": c - 2,
                "close": c,
                "vol": 1e6,
                "amount": 1e8,
                "pct_chg": 0.5,
            }
        )
    return pd.DataFrame(rows)


@patch("core.fetch_live._get_pro")
@patch("core.fetch_live.resolve_indices_for_profile")
def test_build_live_pack_mock(mock_indices, mock_pro):
    pro = MagicMock()
    mock_pro.return_value = pro
    pro.stock_basic.return_value = pd.DataFrame([{"ts_code": "600519.SH", "name": "贵州茅台"}])
    pro.daily.return_value = _daily_df()
    pro.index_daily.return_value = _daily_df(base=3000)
    pro.limit_list_d.return_value = pd.DataFrame()
    mock_indices.return_value = [
        {"ts_code": "000300.SH", "name": "沪深300", "index_group": "size_segment", "category": "size_segment"}
    ]

    pack = build_live_pack(symbols=["600519.SH"], indices_profile="minimal")
    assert len(pack["symbols"]) == 1
    assert pack["symbols"][0]["ts_code"] == "600519.SH"
    assert pack["meta"]["mode"] == "live"
    assert len(pack["symbols"][0]["bars"]["daily"]) > 0
    assert "derived_hints" in pack["symbols"][0]
