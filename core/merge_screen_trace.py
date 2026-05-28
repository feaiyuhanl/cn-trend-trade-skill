"""Merge AI screen_trace decisions into watchlist_screen output."""

from __future__ import annotations

from typing import Any


def _screen_decision(trace: dict[str, Any], ts: str) -> dict[str, Any]:
    dec = (trace.get("decisions") or {}).get(ts) or {}
    return dec.get("screen") or {}


def row_from_ai_screen(
    base_row: dict[str, Any],
    screen: dict[str, Any],
) -> dict[str, Any]:
    """Apply AI screen fields onto a candidate row."""
    row = dict(base_row)
    rank = screen.get("safety_rank")
    if rank is not None:
        try:
            row["safety_rank"] = int(rank)
        except (TypeError, ValueError):
            row["safety_rank"] = None
    action = screen.get("action")
    if action and action != "pending":
        row["action"] = str(action)
    row["weekly_position"] = screen.get("weekly_position") or row.get("weekly_position") or ""
    row["volume_context"] = screen.get("volume_context") or row.get("volume_context") or "unclear"
    row["trap_risk"] = screen.get("trap_risk") or row.get("trap_risk") or "unknown"
    row["fundamental_note"] = screen.get("fundamental_note") or row.get("fundamental_note") or ""
    note = screen.get("rank_rationale") or screen.get("note") or ""
    if note:
        row["note"] = str(note)
    facts = screen.get("facts_used") or []
    if facts:
        row["facts_used"] = list(facts)
    op = screen.get("observation_plan")
    if op:
        row["observation_plan"] = op
    for key in (
        "score_breakdown",
        "trap_vol_reason",
        "action_rule",
        "theme_id",
        "theme_label",
        "theme_lifecycle",
        "theme_lifecycle_rule",
        "position_band",
        "price_percentile_2y",
    ):
        if screen.get(key) is not None:
            row[key] = screen[key]
    return row


def merge_trace_into_rows(
    rows: list[dict[str, Any]],
    trace: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for base in rows:
        ts = base["ts_code"]
        screen = _screen_decision(trace, ts)
        if screen.get("safety_rank") is None and screen.get("action", "pending") == "pending":
            out.append(base)
            continue
        out.append(row_from_ai_screen(base, screen))
    return out


def sort_key_ranked(row: dict[str, Any]) -> tuple:
    rank = row.get("safety_rank")
    rank_val = int(rank) if rank is not None else -1
    trap_order = {"low": 0, "medium": 1, "high": 2, "unknown": 3}.get(
        str(row.get("trap_risk") or "unknown"), 3
    )
    return (-rank_val, trap_order, row.get("ts_code", ""))
