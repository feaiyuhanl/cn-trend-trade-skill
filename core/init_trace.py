"""Scaffold trade_trace.json from market_pack (CLI; Agent must not hand-write computed fields)."""

from __future__ import annotations

from typing import Any

from core import SKILL_VERSION

FULL_ANALYSIS_LENSES = [
    "market-filter",
    "market-sentiment",
    "theme-lifecycle",
    "quality-gate",
    "event-risk",
    "trend-strength",
    "trend-phase",
    "entry-signals",
    "position-management",
    "exit-signals",
    "sector-correlation",
    "discipline",
]


def _decision_stub(ts_code: str) -> dict[str, Any]:
    return {
        "evidence_ids": [],
        "facts_used": [],
        "phase": "unclear",
        "strength": {
            "daily": "unknown",
            "weekly": "unknown",
            "monthly": "unknown",
            "alignment": "unknown",
        },
        "entry": {"type": "wait", "action": "wait", "rationale": ""},
        "position_plan": {"framework": {}, "computed": {}},
        "exit_plan": {},
    }


def init_trace_from_pack(
    pack: dict[str, Any],
    *,
    playbook: str = "full-analysis",
    lenses: list[str] | None = None,
) -> dict[str, Any]:
    meta = pack.get("meta") or {}
    ctx = pack.get("user_context") or {}
    applied = lenses if lenses is not None else list(FULL_ANALYSIS_LENSES)
    symbols = [str(s["ts_code"]).strip().upper() for s in pack.get("symbols") or [] if s.get("ts_code")]

    trace: dict[str, Any] = {
        "meta": {
            "run_id": meta.get("run_id"),
            "as_of": meta.get("as_of"),
            "skill_version": SKILL_VERSION,
            "rules_version": None,
            "rules_profile": meta.get("rules_profile"),
            "playbook": playbook,
            "session_mode": ctx.get("session_mode") or meta.get("session_mode") or "mixed",
            "lenses_applied": applied,
        },
        "sources_snapshot": [],
        "steps": [],
        "market_filter": {
            "indices_considered": [],
            "allow_new_trend_trade": "yes",
            "reasoning_summary": "",
            "confidence": "low",
        },
        "theme_assessment": [],
        "decisions": {ts: _decision_stub(ts) for ts in symbols},
        "discipline_checklist": [],
        "gaps": ["trace scaffold from --init-trace; fill steps/decisions then --finalize"],
    }
    return trace
