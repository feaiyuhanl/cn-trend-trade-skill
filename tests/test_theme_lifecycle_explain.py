"""Tests for theme lifecycle explain (no network)."""

from __future__ import annotations

from core.theme_graph import explain_lifecycle_stage


def test_explain_retreat_leader_limit_down():
    out = explain_lifecycle_stage(
        down_frac=0.2,
        median_pct=1.0,
        leader_pct=5.0,
        leader_limit_down=True,
        up_frac=0.8,
    )
    assert out["lifecycle_stage"] == "retreat"
    assert "龙头跌停" in out["lifecycle_rule"]


def test_explain_consensus():
    out = explain_lifecycle_stage(
        down_frac=0.1,
        median_pct=2.0,
        leader_pct=3.0,
        leader_limit_down=False,
        up_frac=0.7,
    )
    assert out["lifecycle_stage"] == "consensus"
    assert "consensus" in out["lifecycle_rule"]
