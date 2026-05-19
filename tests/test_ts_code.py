from core.ts_code import normalize_ts_code


def test_normalize_with_suffix():
    assert normalize_ts_code("600519.SH") == "600519.SH"


def test_normalize_sh():
    assert normalize_ts_code("600519") == "600519.SH"


def test_normalize_sz():
    assert normalize_ts_code("300750") == "300750.SZ"
