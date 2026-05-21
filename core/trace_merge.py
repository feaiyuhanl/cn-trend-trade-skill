"""Deep-merge JSON patch into trade_trace (CLI stdin/file; no Agent Write tool)."""

from __future__ import annotations

from typing import Any


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, val in patch.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def merge_decisions(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    decisions = dict(base.get("decisions") or {})
    for ts, dec_patch in (patch.get("decisions") or {}).items():
        ts = str(ts).strip().upper()
        cur = dict(decisions.get(ts) or {})
        if isinstance(dec_patch, dict):
            cur = deep_merge(cur, dec_patch)
        decisions[ts] = cur
    base = dict(base)
    base["decisions"] = decisions
    rest = {k: v for k, v in patch.items() if k != "decisions"}
    return deep_merge(base, rest) if rest else base
