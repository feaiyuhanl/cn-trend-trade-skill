"""Stale data user notices."""

from core.trade_date_util import build_data_stale_notice


def test_stale_notice_external_not_ready():
    n = build_data_stale_notice(
        expected_trade_date="20260522",
        actual_trade_date="20260521",
        fetch_messages=[
            "akshare supplement empty for 600519.SH (tushare through 20260521, want 20260522)"
        ],
    )
    assert n["data_stale_cause"] == "external_not_ready"
    assert "20260522" in n["data_stale_headline"]
    assert "20260521" in n["data_stale_headline"]
    assert "稍后重试" in n["data_stale_retry"]
    assert "外部" in n["data_stale_detail"]


def test_stale_notice_network():
    n = build_data_stale_notice(
        expected_trade_date="20260522",
        actual_trade_date="20260521",
        fetch_messages=[
            "akshare 600519.SH: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))",
            "akshare supplement empty for 600519.SH (tushare through 20260521, want 20260522)",
        ],
    )
    assert n["data_stale_cause"] == "external_or_network"
    assert "网络" in n["data_stale_detail"] or "akshare" in n["data_stale_detail"]
