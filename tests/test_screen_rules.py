"""Watchlist-screen machine rules."""

from __future__ import annotations

from core.pack_facts import attach_fact_index
from core.rules_engine import run_machine_rules


def _minimal_screen_trace(ts: str, *, rank: int = 70, action: str = "watch_pool", trap: str = "low"):
    return {
        "meta": {"playbook": "watchlist-screen", "rules_profile": "watchlist-screen"},
        "decisions": {
            ts: {
                "facts_used": [f"symbol:{ts}.derived_hints.structure"],
                "screen": {
                    "safety_rank": rank,
                    "action": action,
                    "trap_risk": trap,
                },
            }
        },
    }


def test_screen_trap_high_blocks_watch_pool():
    pack = {
        "meta": {"rules_profile": "watchlist-screen"},
        "symbols": [
            {
                "ts_code": "600519.SH",
                "name": "茅台",
                "bars": {"daily": [], "weekly": [], "monthly": []},
                "derived_hints": {"structure": "higher_highs_higher_lows"},
            }
        ],
        "slots": {"quality_gate": {"symbols": {"600519.SH": {"tier": "ok"}}}},
    }
    attach_fact_index(pack)
    trace = _minimal_screen_trace("600519.SH", action="watch_pool", trap="high")
    errors, _ = run_machine_rules(pack, trace)
    assert any("trap_risk=high" in e for e in errors)


def test_screen_safety_rank_range():
    pack = {
        "meta": {"rules_profile": "watchlist-screen"},
        "symbols": [
            {
                "ts_code": "600519.SH",
                "name": "茅台",
                "bars": {"daily": [], "weekly": [], "monthly": []},
                "derived_hints": {"structure": "range_bound"},
            }
        ],
        "slots": {"quality_gate": {"symbols": {"600519.SH": {"tier": "ok"}}}},
    }
    attach_fact_index(pack)
    trace = _minimal_screen_trace("600519.SH", rank=150)
    errors, _ = run_machine_rules(pack, trace)
    assert any("out of range" in e for e in errors)
