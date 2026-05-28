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

WATCHLIST_SCREEN_LENSES = [
    "market-sentiment",
    "watchlist-relative-position",
    "watchlist-safety-rank",
    "watchlist-observation-framework",
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


def _screen_decision_stub(ts_code: str) -> dict[str, Any]:
    return {
        "evidence_ids": [],
        "facts_used": [],
        "screen": {
            "safety_rank": None,
            "action": "pending",
            "weekly_position": "",
            "volume_context": "unclear",
            "trap_risk": "unknown",
            "fundamental_note": "",
            "rank_rationale": "",
            "observation_plan": {},
        },
    }


def init_trace_from_pack(
    pack: dict[str, Any],
    *,
    playbook: str = "full-analysis",
    lenses: list[str] | None = None,
) -> dict[str, Any]:
    meta = pack.get("meta") or {}
    ctx = pack.get("user_context") or {}
    is_screen = playbook == "watchlist-screen"
    if lenses is not None:
        applied = lenses
    elif is_screen:
        applied = list(WATCHLIST_SCREEN_LENSES)
    else:
        applied = list(FULL_ANALYSIS_LENSES)
    symbols = [str(s["ts_code"]).strip().upper() for s in pack.get("symbols") or [] if s.get("ts_code")]
    stub_fn = _screen_decision_stub if is_screen else _decision_stub
    gap_msg = (
        "screen trace scaffold: fill decisions[].screen via --patch-trace, then --merge-screen-trace"
        if is_screen
        else "trace scaffold from --init-trace; fill steps/decisions then --finalize"
    )

    trace: dict[str, Any] = {
        "meta": {
            "run_id": meta.get("run_id"),
            "as_of": meta.get("as_of"),
            "skill_version": SKILL_VERSION,
            "rules_version": None,
            "rules_profile": "watchlist-screen" if is_screen else meta.get("rules_profile"),
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
        "decisions": {ts: stub_fn(ts) for ts in symbols},
        "discipline_checklist": [],
        "gaps": [gap_msg],
    }
    return trace
