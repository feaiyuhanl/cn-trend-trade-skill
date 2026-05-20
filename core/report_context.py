"""Build Jinja contexts for report templates."""

from __future__ import annotations

import json
import re
from typing import Any

from core.observations import normalize_observation

_FACT_KEY_RE = re.compile(r"symbol:[^.]+\.(?:SZ|SH)\.(.+)")


def fact_short_key(key: str) -> str:
    m = _FACT_KEY_RE.match(key)
    return m.group(1) if m else key


def strength_line(strength: dict[str, Any]) -> str:
    return (
        f"D={strength.get('daily', '?')} / W={strength.get('weekly', '?')} / "
        f"M={strength.get('monthly', '?')} ({strength.get('alignment', '?')})"
    )


def observation_display(obs: Any) -> dict[str, str]:
    n = normalize_observation(obs)
    icons = {"fact": "📊", "qualitative": "💭", "mixed": "👁"}
    return {
        "icon": icons.get(n["kind"], "👁"),
        "kind": n["kind"],
        "text": n["text"],
    }


def symbol_names(pack: dict[str, Any] | None) -> dict[str, str]:
    if not pack:
        return {}
    return {s["ts_code"]: s.get("name", "") for s in pack.get("symbols", [])}


def build_trade_context(trace: dict[str, Any], pack: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = trace.get("meta", {})
    resolved = trace.get("resolved") or {}
    dec_resolved = resolved.get("decisions") or {}
    symbols = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        entry = dec.get("entry") or {}
        pp = dec.get("position_plan") or {}
        facts = (dec_resolved.get(ts_code) or {}).get("facts") or {}
        symbols.append(
            {
                "ts_code": ts_code,
                "name": symbol_names(pack).get(ts_code, ""),
                "phase": dec.get("phase", ""),
                "strength_line": strength_line(dec.get("strength") or {}),
                "entry_type": entry.get("type", ""),
                "entry_action": entry.get("action", ""),
                "entry_rationale": entry.get("rationale", ""),
                "facts_rows": [
                    {"key": k, "short_key": fact_short_key(k), "value": v}
                    for k, v in sorted(facts.items())
                ],
                "computed": pp.get("computed") or {},
                "framework": pp.get("framework") or {},
                "exit_plan": dec.get("exit_plan") or {},
                "holding_review": dec.get("holding_review") or {},
                "computed_json": json.dumps(pp.get("computed") or {}, ensure_ascii=False),
                "framework_json": json.dumps(pp.get("framework") or {}, ensure_ascii=False),
                "exit_json": json.dumps(dec.get("exit_plan") or {}, ensure_ascii=False),
                "holding_json": json.dumps(dec.get("holding_review") or {}, ensure_ascii=False),
            }
        )
    return {
        "meta": meta,
        "symbols_summary": ", ".join(trace.get("decisions", {}).keys()),
        "market_filter": trace.get("market_filter") or {},
        "symbols": symbols,
        "discipline": trace.get("discipline_checklist") or [],
        "gaps": trace.get("gaps") or [],
        "steps": trace.get("steps") or [],
        "sources": trace.get("sources_snapshot") or [],
    }


def build_dossier_context(trace: dict[str, Any], pack: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = trace.get("resolved") or {}
    step_resolved = {s.get("step"): s for s in (resolved.get("steps") or [])}
    steps = []
    for step in trace.get("steps", []):
        sn = step.get("step")
        sr = step_resolved.get(sn) or {}
        steps.append(
            {
                "step": sn,
                "lens": step.get("lens"),
                "observations": [observation_display(o) for o in step.get("observations") or []],
                "bars": sr.get("bars") or [],
                "inference": step.get("inference", ""),
                "confidence": step.get("confidence", ""),
            }
        )
    dec_resolved = resolved.get("decisions") or {}
    symbols = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        dr = dec_resolved.get(ts_code) or {}
        entry = dec.get("entry") or {}
        symbols.append(
            {
                "ts_code": ts_code,
                "name": symbol_names(pack).get(ts_code, ""),
                "phase": dec.get("phase", ""),
                "strength_line": strength_line(dec.get("strength") or {}),
                "entry_type": entry.get("type", ""),
                "entry_action": entry.get("action", ""),
                "rationale": entry.get("rationale", ""),
                "facts_rows": [{"key": k, "value": v} for k, v in sorted((dr.get("facts") or {}).items())],
                "bars": dr.get("bars") or [],
            }
        )
    return {
        "meta": trace.get("meta", {}),
        "steps": steps,
        "symbols": symbols,
        "market_filter": trace.get("market_filter") or {},
    }


def build_audit_context(trace: dict[str, Any], pack: dict[str, Any] | None = None) -> dict[str, Any]:
    audit = (trace.get("resolved") or {}).get("audit") or {}
    flat = (pack or {}).get("fact_index", {}).get("flat", {})
    dec_resolved = (trace.get("resolved") or {}).get("decisions") or {}
    symbols = []
    for ts_code in (trace.get("decisions") or {}):
        facts = (dec_resolved.get(ts_code) or {}).get("facts") or {}
        symbols.append(
            {
                "ts_code": ts_code,
                "facts_rows": [{"key": k, "value": v} for k, v in sorted(facts.items())],
            }
        )
    unused = audit.get("unused_relevant_facts") or []
    return {
        "meta": trace.get("meta", {}),
        "symbols": symbols,
        "unused_rows": [{"key": k, "value": flat.get(k, "—")} for k in unused],
        "unknown_keys": audit.get("unknown_facts_used") or [],
        "sources": trace.get("sources_snapshot") or [],
    }


def build_review_context(trace: dict[str, Any], pack: dict[str, Any] | None = None) -> dict[str, Any]:
    review = trace.get("review") or {}
    names = symbol_names(pack)
    rows = []
    for row in review.get("planned_vs_actual") or []:
        ts = row.get("ts_code", "")
        rows.append({**row, "name": names.get(ts, "")})
    return {
        "meta": trace.get("meta", {}),
        "review": review,
        "rows": rows,
        "violations": review.get("discipline_violations") or [],
        "lessons": review.get("lessons") or [],
        "improvements": review.get("next_improvements") or review.get("improvements") or [],
    }
