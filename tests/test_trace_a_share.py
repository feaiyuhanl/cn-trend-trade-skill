from __future__ import annotations

from core.enrich_trace import enrich_trace
from core.trace_a_share import merge_pack_a_share_into_trace
from core.validate import load_json

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


def test_merge_pack_sentiment_into_trace() -> None:
    pack = load_json(ROOT / "sample" / "market_pack.sample.json")
    trace = {"market_filter": {"allow_new_trend_trade": "yes"}, "gaps": []}
    merge_pack_a_share_into_trace(trace, pack)
    assert trace["market_filter"].get("sentiment_tier") == "normal"
    assert "sector_retreats" in trace["market_filter"]


def test_enrich_trace_merges_a_share() -> None:
    pack = load_json(ROOT / "sample" / "market_pack.sample.json")
    trace = load_json(ROOT / "sample" / "trade_trace.sample.json")
    enrich_trace(trace, pack)
    assert trace["market_filter"].get("sentiment_tier") == "normal"
