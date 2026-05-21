from __future__ import annotations

import json
from pathlib import Path

from core.init_trace import init_trace_from_pack
from core.pack_inspect import dispatch_show_pack, format_holdings
from core.trace_merge import merge_decisions
from core.validate import load_json

ROOT = Path(__file__).resolve().parent.parent
FIX_PACK = ROOT / "sample" / "market_pack.sample.json"


def test_format_holdings_with_positions():
    pack = load_json(FIX_PACK)
    text = format_holdings(pack)
    assert "holdings" in text or "600519" in text or "(none)" in text


def test_show_pack_symbols():
    pack = load_json(FIX_PACK)
    text = dispatch_show_pack(pack, "symbols")
    assert "600519.SH" in text


def test_init_trace_scaffold():
    pack = load_json(FIX_PACK)
    trace = init_trace_from_pack(pack)
    assert trace["meta"]["playbook"] == "full-analysis"
    assert "600519.SH" in trace["decisions"]
    assert trace["decisions"]["600519.SH"]["entry"]["action"] == "wait"


def test_merge_decisions_patch():
    base = {"decisions": {"600519.SH": {"phase": "unclear", "entry": {"action": "wait"}}}}
    patch = {
        "decisions": {"600519.SH": {"phase": "acceleration", "entry": {"action": "hold"}}},
        "steps": [{"step": 1}],
    }
    merged = merge_decisions(base, patch)
    assert merged["decisions"]["600519.SH"]["phase"] == "acceleration"
    assert merged["decisions"]["600519.SH"]["entry"]["action"] == "hold"
    assert len(merged["steps"]) == 1
