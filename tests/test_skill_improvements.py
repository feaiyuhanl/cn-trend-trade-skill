from __future__ import annotations

from pathlib import Path

import pytest

from core.pack_facts import attach_fact_index
from core.skill_improvements import (
    ALL_DIMENSION_IDS,
    MF_PHASE_ENTRY,
    assess_trace,
    format_dimensions_markdown,
    load_dimensions_config,
)
from core.validate import load_json

ROOT = Path(__file__).resolve().parent.parent
FIX_PACK = ROOT / "sample" / "market_pack.sample.json"
FIX_TRACE = ROOT / "sample" / "trade_trace.sample.json"


def test_load_dimensions_config_has_eight() -> None:
    dims = load_dimensions_config()
    assert len(dims) == 8
    ids = {d["id"] for d in dims}
    assert ids == set(ALL_DIMENSION_IDS)


def test_assess_sample_trace() -> None:
    trace = load_json(FIX_TRACE)
    pack = load_json(FIX_PACK)
    attach_fact_index(pack)
    result = assess_trace(trace, pack)
    assert result["overall_status"] in ("ok", "warn", "gap", "na")
    assert len(result["dimensions"]) == 8
    ids = {d["id"] for d in result["dimensions"]}
    assert MF_PHASE_ENTRY in ids


def test_format_dimensions_markdown() -> None:
    trace = load_json(FIX_TRACE)
    pack = load_json(FIX_PACK)
    attach_fact_index(pack)
    assessment = assess_trace(trace, pack)
    text = format_dimensions_markdown(single=assessment)
    assert "SKILL 八维演进评估" in text
    assert "MF_PHASE_ENTRY" in text


def test_mf_phase_flags_reduced_breakout_without_note() -> None:
    trace = load_json(FIX_TRACE)
    pack = load_json(FIX_PACK)
    trace["decisions"]["300750.SZ"]["phase"] = "acceleration"
    trace["decisions"]["300750.SZ"]["entry"] = {
        "type": "breakout",
        "action": "open_on_breakout",
        "rationale": "突破买入",
    }
    result = assess_trace(trace, pack)
    mf_dim = next(d for d in result["dimensions"] if d["id"] == MF_PHASE_ENTRY)
    assert mf_dim["status"] in ("warn", "gap")
    assert any("reduced" in f.lower() or "缩" in f for f in mf_dim.get("findings") or [])
