"""Inject script-computed fields into trade_trace (Agent must not hand-write these)."""

from __future__ import annotations

from typing import Any

from core.position_calc import build_position_computed
from core.rules_engine import load_rules_config
from core.trace_a_share import merge_pack_a_share_into_trace
from core.trace_resolve import build_resolved_block, build_sources_snapshot


def enrich_trace(trace: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    rules = load_rules_config()
    trace.setdefault("meta", {})
    trace["meta"]["rules_version"] = rules.get("version", "1.0.0")
    trace["meta"].setdefault("rules_profile", (pack.get("meta") or {}).get("rules_profile"))

    trace["sources_snapshot"] = build_sources_snapshot(pack)
    merge_pack_a_share_into_trace(trace, pack)

    for ts_code, dec in (trace.get("decisions") or {}).items():
        computed = build_position_computed(pack, ts_code)
        pp = dec.setdefault("position_plan", {})
        pp["computed"] = computed
        if ts_code in (pack.get("fact_index") or {}).get("holdings", {}):
            hr = dec.setdefault("holding_review", {})
            if "vs_cost_pct" in computed:
                hr["vs_cost_pct"] = computed["vs_cost_pct"]

    trace["resolved"] = build_resolved_block(pack, trace)
    return trace
