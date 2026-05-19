from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.enrich_trace import enrich_trace
from core.pack_facts import attach_fact_index
from core.rules_engine import run_machine_rules
from core.validate import load_json, validate_trace_against_pack

ROOT = Path(__file__).resolve().parent.parent
FIX_PACK = ROOT / "sample" / "market_pack.sample.json"
FIX_TRACE = ROOT / "sample" / "trade_trace.sample.json"


@pytest.fixture
def pack() -> dict:
    data = load_json(FIX_PACK)
    attach_fact_index(data)
    return data


@pytest.fixture
def trace(pack: dict) -> dict:
    data = load_json(FIX_TRACE)
    enrich_trace(data, pack)
    return data


def test_fixture_trace_passes_rules(pack: dict, trace: dict) -> None:
    errs, warns = run_machine_rules(pack, trace)
    assert errs == [], errs
    assert validate_trace_against_pack(trace, pack) == []


def test_bad_observation_number_fails(pack: dict, trace: dict) -> None:
    trace["steps"][0]["observations"][0] = "沪深300 收跌 -99.99%"
    errs, _ = run_machine_rules(pack, trace)
    assert any("FACT_OBSERVATION_NUMBERS" in e for e in errs)


def test_missing_facts_used_fails(pack: dict, trace: dict) -> None:
    trace["decisions"]["600519.SH"]["facts_used"] = []
    errs, _ = run_machine_rules(pack, trace)
    assert any("DECISIONS_FACTS_USED" in e for e in errs)


def test_steps_lens_mismatch_fails(pack: dict, trace: dict) -> None:
    trace["steps"] = trace["steps"][:3]
    errs, _ = run_machine_rules(pack, trace)
    assert any("STEPS_MATCH_LENSES" in e for e in errs)


def test_wrong_holding_pnl_fails(pack: dict, trace: dict) -> None:
    trace["decisions"]["600519.SH"]["holding_review"]["vs_cost_pct"] = 99.0
    errs, _ = run_machine_rules(pack, trace)
    assert any("HOLD_PNL_FROM_PACK" in e for e in errs)
