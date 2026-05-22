from __future__ import annotations

from core.theme_leader_resolver import elect_spec_leader


def test_elect_spec_leader_by_lianban():
    members = ["A.SH", "B.SH", "C.SH"]
    limit_map = {
        "A.SH": {"lianban": 1, "limit_up": True, "pct_chg": 10.0},
        "B.SH": {"lianban": 3, "limit_up": True, "pct_chg": 10.0},
        "C.SH": {"lianban": 0, "limit_up": False, "pct_chg": 2.0},
    }
    pct_map = {"A.SH": 10.0, "B.SH": 10.0, "C.SH": 2.0}
    leader, scores = elect_spec_leader(members, limit_map, pct_map)
    assert leader == "B.SH"
    assert scores["B.SH"][0] == 3


def test_elect_spec_leader_by_pct_when_no_limit():
    members = ["A.SH", "B.SH"]
    limit_map = {}
    pct_map = {"A.SH": 5.0, "B.SH": 8.0}
    leader, _ = elect_spec_leader(members, limit_map, pct_map)
    assert leader == "B.SH"
