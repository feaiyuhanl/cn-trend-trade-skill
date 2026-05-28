"""Pack session freshness (index + symbol coverage)."""

from __future__ import annotations

import pytest

from core.trade_date_util import (
    DataStaleError,
    assess_pack_data_session,
    assert_pack_session_fresh,
    attach_pack_trade_date_meta,
)


def _pack(*, index_td: str, symbol_tds: list[str]) -> dict:
    return {
        "indices": [
            {
                "bars": {
                    "daily": [
                        {"trade_date": index_td, "pct_chg": 0.1},
                    ]
                }
            }
        ],
        "symbols": [
            {
                "bars": {
                    "daily": [
                        {"trade_date": td, "pct_chg": 0.0},
                    ]
                }
            }
            for td in symbol_tds
        ],
    }


def test_stale_when_index_behind_expected():
    pack = _pack(index_td="20260526", symbol_tds=["20260526"] * 10)
    a = assess_pack_data_session(pack, expected="20260527", min_symbol_ratio=0.95)
    assert a["data_stale"] is True
    assert any("指数" in r for r in a["data_stale_reasons"])


def test_stale_when_symbols_lag_even_if_index_fresh():
    """Global max(bar) would hide this; coverage check must catch it."""
    pack = _pack(index_td="20260527", symbol_tds=["20260526"] * 10)
    a = assess_pack_data_session(pack, expected="20260527", min_symbol_ratio=0.95)
    assert a["data_stale"] is True
    assert any("个股" in r for r in a["data_stale_reasons"])


def test_fresh_when_index_and_symbols_match():
    pack = _pack(index_td="20260527", symbol_tds=["20260527"] * 20)
    a = assess_pack_data_session(pack, expected="20260527", min_symbol_ratio=0.95)
    assert a["data_stale"] is False
    assert a["trade_date"] == "20260527"


def test_assert_pack_session_fresh_raises():
    pack = _pack(index_td="20260526", symbol_tds=["20260526"])
    with pytest.raises(DataStaleError):
        assert_pack_session_fresh(
            pack,
            fail_on_stale=True,
            min_symbol_ratio=0.95,
        )
    meta = pack["meta"]
    assert meta["expected_trade_date"]
    assert meta["data_stale"] is True
