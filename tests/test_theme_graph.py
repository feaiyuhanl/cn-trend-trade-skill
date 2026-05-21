from __future__ import annotations

from core.theme_graph import (
    assess_theme,
    build_theme_context,
    build_theme_index,
    leader_codes_for_themes,
    load_themes_config,
    parse_theme_members,
)


def test_parse_theme_members_leader_follower():
    body = {
        "leaders": [{"ts_code": "601991.SH", "name": "大唐发电"}],
        "members": [{"ts_code": "601016.SH", "role": "follower"}],
    }
    rows = parse_theme_members("green_power", body)
    roles = {r["ts_code"]: r["role"] for r in rows}
    assert roles["601991.SH"] == "leader"
    assert roles["601016.SH"] == "follower"


def test_leader_codes_for_green_power():
    themes = load_themes_config().get("themes") or {}
    codes = leader_codes_for_themes(themes, {"green_power"})
    assert "601991.SH" in codes


def test_retreat_when_leader_limit_down():
    themes = load_themes_config().get("themes") or {}
    body = themes["green_power"]
    pack = {
        "symbols": [
            {
                "ts_code": "601991.SH",
                "name": "大唐发电",
                "bars": {"daily": [{"trade_date": "20260520", "pct_chg": -10.0, "close": 3.0}]},
            },
            {
                "ts_code": "601016.SH",
                "name": "节能风电",
                "bars": {"daily": [{"trade_date": "20260520", "pct_chg": -2.0, "close": 4.0}]},
            },
        ]
    }
    ctx = build_theme_context(pack, {"themes": themes})
    gp = next(t for t in ctx["themes"] if t["theme_id"] == "green_power")
    assert gp["lifecycle_stage"] == "retreat"
    assert gp["leader_limit_down"] is True
    assert gp["allow_new_trend_trade"] == "no"


def test_build_theme_index_roles():
    themes = load_themes_config().get("themes") or {}
    idx = build_theme_index(themes)
    assert idx["000591.SZ"]["role"] == "follower"
    assert idx["601991.SH"]["role"] == "leader"
