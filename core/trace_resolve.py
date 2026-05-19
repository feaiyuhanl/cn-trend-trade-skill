"""Resolve pack facts and bars for trace enrichment and audit reports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.pack_facts import attach_fact_index, build_fact_index

_STATUS_MAP = {
    "ok": "ok",
    "success": "ok",
    "fail": "fail",
    "error": "fail",
    "skip": "skip",
    "not_configured": "not_configured",
    "unset": "not_configured",
}


def _bar_index(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for inst in pack.get("symbols", []) + pack.get("indices", []):
        for tf in ("daily", "weekly", "monthly"):
            for bar in (inst.get("bars", {}).get(tf) or []):
                index[bar["id"]] = {
                    **bar,
                    "ts_code": inst["ts_code"],
                    "timeframe": tf,
                }
    for b in pack.get("market_breadth") or []:
        if isinstance(b, dict) and b.get("id"):
            index[b["id"]] = b
    return index


def resolve_bars(pack: dict[str, Any], evidence_ids: list[str]) -> list[dict[str, Any]]:
    bars = _bar_index(pack)
    out: list[dict[str, Any]] = []
    for eid in evidence_ids:
        bar = bars.get(eid)
        if not bar:
            out.append({"id": eid, "missing": True})
            continue
        out.append(
            {
                "id": eid,
                "ts_code": bar.get("ts_code"),
                "timeframe": bar.get("timeframe"),
                "trade_date": bar.get("trade_date"),
                "open": bar.get("open"),
                "high": bar.get("high"),
                "low": bar.get("low"),
                "close": bar.get("close"),
                "pct_chg": bar.get("pct_chg"),
                "vol": bar.get("vol"),
            }
        )
    return out


def resolve_facts(pack: dict[str, Any], fact_keys: list[str]) -> dict[str, Any]:
    if "fact_index" not in pack:
        attach_fact_index(pack)
    flat = pack["fact_index"]["flat"]
    resolved: dict[str, Any] = {}
    for key in fact_keys:
        if key in flat:
            resolved[key] = flat[key]
        else:
            resolved[key] = None
    return resolved


def build_sources_snapshot(pack: dict[str, Any]) -> list[dict[str, Any]]:
    meta = pack.get("meta") or {}
    fetch_status = meta.get("fetch_status") or {}
    mode = meta.get("mode", "unknown")
    if not fetch_status:
        return [
            {
                "id": "assemble",
                "status": "ok",
                "items": len(pack.get("symbols", [])),
                "message": f"mode={mode}",
            }
        ]
    out: list[dict[str, Any]] = []
    for sid, raw in fetch_status.items():
        status = _STATUS_MAP.get(str(raw).lower(), "skip")
        out.append(
            {
                "id": sid,
                "status": status,
                "message": f"fetch_status={raw}; pack_mode={mode}",
            }
        )
    return out


def collect_facts_used(trace: dict[str, Any]) -> set[str]:
    used: set[str] = set()
    for dec in (trace.get("decisions") or {}).values():
        used.update(dec.get("facts_used") or [])
    return used


def build_audit(pack: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    if "fact_index" not in pack:
        attach_fact_index(pack)
    flat = pack["fact_index"]["flat"]
    used = collect_facts_used(trace)
    symbols = set((trace.get("decisions") or {}).keys())

    def _relevant(key: str) -> bool:
        if key.startswith("holding:"):
            return any(key.startswith(f"holding:{s}:") for s in symbols)
        if key.startswith("symbol:"):
            return any(key.startswith(f"symbol:{s}.") for s in symbols)
        return False

    relevant = {k: flat[k] for k in flat if _relevant(k)}
    unused = sorted(k for k in relevant if k not in used)
    missing = sorted(k for k in used if k not in flat)

    return {
        "facts_used_count": len(used),
        "facts_used": sorted(used),
        "unused_relevant_facts": unused,
        "unknown_facts_used": missing,
    }


def build_resolved_block(pack: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    decisions_out: dict[str, Any] = {}
    for ts_code, dec in (trace.get("decisions") or {}).items():
        decisions_out[ts_code] = {
            "facts": resolve_facts(pack, dec.get("facts_used") or []),
            "bars": resolve_bars(pack, dec.get("evidence_ids") or []),
        }

    steps_out: list[dict[str, Any]] = []
    for step in trace.get("steps", []):
        steps_out.append(
            {
                "step": step.get("step"),
                "lens": step.get("lens"),
                "bars": resolve_bars(pack, step.get("evidence_ids") or []),
            }
        )

    return {
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "decisions": decisions_out,
        "steps": steps_out,
        "audit": build_audit(pack, trace),
    }
