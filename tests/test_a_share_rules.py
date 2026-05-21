from __future__ import annotations

from core.rules_engine import run_machine_rules


def _pack_follower_retreat():
    return {
        "meta": {"rules_profile": "development"},
        "symbols": [{"ts_code": "601016.SH", "name": "节能风电", "bars": {"daily": [], "weekly": [], "monthly": []}}],
        "indices": [],
        "user_context": {"session_mode": "new_entry", "positions": []},
        "slots": {
            "theme_context": {
                "themes": [
                    {
                        "theme_id": "green_power",
                        "lifecycle_stage": "retreat",
                        "leader_limit_down": True,
                    }
                ]
            },
            "quality_gate": {
                "symbols": {
                    "601016.SH": {"tier": "ok", "block_entry": False},
                }
            },
            "event_risk": {"symbols": {"601016.SH": {"block_entry": False}}},
        },
        "fact_index": {"flat": {}, "symbols": {}, "indices": {}, "holdings": {}},
    }


def test_leader_retreat_blocks_follower_entry():
    pack = _pack_follower_retreat()
    trace = {
        "market_filter": {"allow_new_trend_trade": "reduced"},
        "decisions": {
            "601016.SH": {
                "phase": "acceleration",
                "entry": {"type": "breakout", "action": "add"},
                "evidence_ids": [],
                "facts_used": [],
            }
        },
        "discipline_checklist": [],
        "steps": [],
        "meta": {"lenses_applied": []},
    }
    errs, _ = run_machine_rules(pack, trace)
    assert any("LEADER_RETREAT" in e for e in errs)


def test_quality_block_entry():
    pack = {
        "meta": {"rules_profile": "development"},
        "symbols": [{"ts_code": "000670.SZ", "bars": {"daily": [], "weekly": [], "monthly": []}}],
        "indices": [],
        "user_context": {"session_mode": "new_entry", "positions": []},
        "slots": {
            "quality_gate": {
                "symbols": {
                    "000670.SZ": {"tier": "block", "block_entry": True, "risk_flags": ["chronic_loss"]},
                }
            },
            "event_risk": {"symbols": {"000670.SZ": {"block_entry": False}}},
        },
        "fact_index": {"flat": {}, "symbols": {}, "indices": {}, "holdings": {}},
    }
    trace = {
        "decisions": {
            "000670.SZ": {
                "phase": "startup",
                "entry": {"type": "breakout", "action": "add"},
                "evidence_ids": ["x"],
                "facts_used": ["y"],
            }
        },
        "discipline_checklist": [],
        "steps": [],
        "meta": {"lenses_applied": []},
    }
    errs, _ = run_machine_rules(pack, trace)
    assert any("QUALITY_GATE" in e for e in errs)
