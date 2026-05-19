from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.validate import (
    load_json,
    validate_market_pack,
    validate_trace_against_pack,
    validate_trade_trace,
)

ROOT = Path(__file__).resolve().parent.parent
FIX_PACK = ROOT / "fixtures" / "market_pack.sample.json"
FIX_TRACE = ROOT / "fixtures" / "trade_trace.sample.json"


def test_market_pack_fixture_valid():
    pack = load_json(FIX_PACK)
    errs = validate_market_pack(pack)
    assert errs == [], errs


def test_trade_trace_fixture_valid():
    trace = load_json(FIX_TRACE)
    errs = validate_trade_trace(trace)
    assert errs == [], errs


def test_trace_against_pack():
    from core.enrich_trace import enrich_trace
    from core.pack_facts import attach_fact_index

    pack = load_json(FIX_PACK)
    attach_fact_index(pack)
    trace = load_json(FIX_TRACE)
    enrich_trace(trace, pack)
    errs = validate_trace_against_pack(trace, pack)
    assert errs == [], errs


def test_assemble_writes_pack(tmp_path, monkeypatch):
    from core import assemble as asm

    monkeypatch.setattr(asm, "TMP_DIR", tmp_path)
    monkeypatch.setattr(asm, "OUT_PACK", tmp_path / "market_pack.json")
    path = asm.assemble(
        symbols=["600519.SH"],
        session_mode="new_entry",
        positions_file=ROOT / "examples" / "positions_new_entry.json",
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["symbols"]) == 1
    assert data["user_context"]["session_mode"] == "new_entry"
    assert validate_market_pack(data) == []
