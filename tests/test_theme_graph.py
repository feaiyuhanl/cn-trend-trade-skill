from __future__ import annotations

from core.theme_graph import (
    assess_theme_from_members,
    build_theme_context,
    build_theme_index,
    leader_codes_for_themes,
    parse_theme_members,
)


def test_parse_theme_members_legacy():
    body = {
        "leaders": [{"ts_code": "601991.SH", "name": "大唐发电"}],
        "members": [{"ts_code": "601016.SH", "role": "follower"}],
    }
    rows = parse_theme_members("green_power", body)
    roles = {r["ts_code"]: r["role"] for r in rows}
    assert roles["601991.SH"] == "leader"
    assert roles["601016.SH"] == "follower"


def test_leader_codes_from_resolution():
    resolution = {
        "themes": {
            "BK0427.DC": {"leader_ts_code": "600578.SH"},
        }
    }
    codes = leader_codes_for_themes({}, {"BK0427.DC"}, resolution)
    assert codes == ["600578.SH"]


def test_retreat_when_leader_limit_down():
    pack = {
        "symbols": [
            {
                "ts_code": "600578.SH",
                "name": "京能电力",
                "bars": {"daily": [{"trade_date": "20260520", "pct_chg": -10.0, "close": 3.0}]},
            },
            {
                "ts_code": "601016.SH",
                "name": "节能风电",
                "bars": {"daily": [{"trade_date": "20260520", "pct_chg": -2.0, "close": 4.0}]},
            },
        ],
        "slots": {
            "theme_resolution": {
                "version": "2.0.0",
                "theme_index": {
                    "600578.SH": {"theme": "BK0427.DC", "role": "leader", "label": "风电"},
                    "601016.SH": {"theme": "BK0427.DC", "role": "follower", "label": "风电"},
                },
                "themes": {
                    "BK0427.DC": {
                        "label": "风电",
                        "members": [
                            {"ts_code": "600578.SH", "name": "京能电力", "role": "leader"},
                            {"ts_code": "601016.SH", "name": "节能风电", "role": "follower"},
                        ],
                    }
                },
            }
        },
    }
    ctx = build_theme_context(pack)
    gp = next(t for t in ctx["themes"] if t["theme_id"] == "BK0427.DC")
    assert gp["lifecycle_stage"] == "retreat"
    assert gp["leader_limit_down"] is True
    assert gp["allow_new_trend_trade"] == "no"


def test_build_theme_index_from_resolution():
    resolution = {
        "theme_index": {
            "601016.SH": {"theme": "BK0427.DC", "role": "follower", "label": "风电"},
        }
    }
    idx = build_theme_index({}, resolution)
    assert idx["601016.SH"]["theme"] == "BK0427.DC"


def test_assess_theme_from_members_roles():
    members = [
        {"ts_code": "L.SH", "role": "leader", "name": "龙头"},
        {"ts_code": "F.SH", "role": "follower", "name": "跟风"},
    ]
    pct_map = {"L.SH": 5.0, "F.SH": -1.0}
    a = assess_theme_from_members("BK0001.DC", "测试", members, pct_map)
    assert a["leaders"][0]["ts_code"] == "L.SH"
    assert a["follower_count"] == 1
