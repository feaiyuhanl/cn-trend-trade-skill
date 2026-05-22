"""Trade session date helpers (no network)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd

from core.trade_date_util import (
    expected_trade_session_date,
    latest_open_trade_date,
    max_trade_date_from_pack,
    resolve_latest_trade_date,
)


def test_expected_trade_session_after_close_friday():
    # 2026-05-22 is Friday; 15:30 local -> same day
    now = datetime(2026, 5, 22, 15, 30)
    assert expected_trade_session_date(now) == "20260522"


def test_expected_trade_session_before_close():
    now = datetime(2026, 5, 22, 14, 0)
    assert expected_trade_session_date(now) == "20260521"


def test_expected_trade_session_weekend():
    now = datetime(2026, 5, 23, 10, 0)  # Saturday
    assert expected_trade_session_date(now) == "20260522"


def test_latest_open_trade_date_caps_at_expected():
    pro = MagicMock()
    pro.trade_cal.return_value = pd.DataFrame(
        [{"cal_date": "20260520"}, {"cal_date": "20260521"}, {"cal_date": "20260522"}]
    )
    now = datetime(2026, 5, 22, 15, 30)
    assert latest_open_trade_date(pro, end_cap=expected_trade_session_date(now)) == "20260522"


def test_max_trade_date_from_pack():
    pack = {
        "indices": [
            {
                "bars": {
                    "daily": [
                        {"trade_date": "20260521", "pct_chg": -1},
                        {"trade_date": "20260522", "pct_chg": -2},
                    ]
                }
            }
        ],
        "symbols": [],
    }
    assert max_trade_date_from_pack(pack) == "20260522"


def test_resolve_prefers_pack_bars_when_behind_expected():
    pro = MagicMock()
    pro.trade_cal.return_value = pd.DataFrame([{"cal_date": "20260522"}])
    pack = {
        "indices": [{"bars": {"daily": [{"trade_date": "20260521", "pct_chg": -2}]}}],
        "symbols": [],
    }
    assert resolve_latest_trade_date(pro, pack=pack) == "20260521"
