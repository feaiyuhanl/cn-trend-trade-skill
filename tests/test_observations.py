from __future__ import annotations

from core.observations import normalize_observation, observation_kind
from core.rules_engine import run_machine_rules
from core.validate import load_json, validate_trade_trace

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
FIX_TRACE = ROOT / "fixtures" / "trade_trace.sample.json"


def test_normalize_string_legacy():
    n = normalize_observation("[qualitative] 测试")
    assert n["kind"] == "qualitative"


def test_normalize_structured_fact():
    n = normalize_observation({"kind": "fact", "text": "x=1", "fact_keys": ["a"]})
    assert n["kind"] == "fact"
    assert observation_kind(n) == "fact"


def test_structured_trace_schema_valid():
    trace = load_json(FIX_TRACE)
    assert validate_trade_trace(trace) == []


def test_fact_without_keys_fails_rules():
    from core.enrich_trace import enrich_trace
    from core.pack_facts import attach_fact_index

    pack = load_json(ROOT / "fixtures" / "market_pack.sample.json")
    attach_fact_index(pack)
    trace = load_json(FIX_TRACE)
    enrich_trace(trace, pack)
    trace["steps"][0]["observations"] = [{"kind": "fact", "text": "bad=1", "fact_keys": []}]
    errs, _ = run_machine_rules(pack, trace)
    assert any("OBSERVATION_KIND_CONSISTENT" in e for e in errs)
