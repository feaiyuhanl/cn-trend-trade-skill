"""Verify numeric claims in observations against pack evidence."""

from __future__ import annotations

import re
from typing import Any

from core.observations import is_qualitative_observation, normalize_observation
from core.pack_facts import resolve_evidence_numbers

_NUM_RE = re.compile(
    r"(?<![A-Za-z_])=(-?\d+\.?\d*)"
    r"|(?<![A-Za-z_])(-?\d+\.\d+)\s*%?"
    r"|(?<![A-Za-z_])(-?\d+)\s*%"
)


def _extract_numbers(text: str, ignore_patterns: list[str]) -> list[float]:
    nums: list[float] = []
    for m in _NUM_RE.finditer(text):
        raw = m.group(1) or m.group(2) or m.group(3)
        if raw is None:
            continue
        if any(re.fullmatch(p, raw) for p in ignore_patterns):
            continue
        try:
            nums.append(float(raw))
        except ValueError:
            continue
    return nums


def _number_matches_allowed(value: float, allowed: set[float], tol: float) -> bool:
    if not allowed:
        return False
    for a in allowed:
        if abs(value - a) <= tol:
            return True
        if a != 0 and abs((value - a) / a) <= 0.02:
            return True
    return False


def verify_step_observations(
    pack: dict[str, Any],
    step: dict[str, Any],
    *,
    tolerance: float,
    unverified_marker: str,
    ignore_patterns: list[str],
) -> list[str]:
    """Return error messages for numeric mismatches in observations."""
    msgs: list[str] = []
    evidence_ids = step.get("evidence_ids") or []
    allowed = resolve_evidence_numbers(pack, evidence_ids)
    flat = (pack.get("fact_index") or {}).get("flat", {})
    lens = step.get("lens", "?")
    step_n = step.get("step", "?")

    for i, raw_obs in enumerate(step.get("observations") or []):
        obs = normalize_observation(raw_obs)
        kind = obs["kind"]
        text = obs["text"]
        fact_keys = obs.get("fact_keys") or []

        if kind == "qualitative":
            continue
        if unverified_marker in text:
            continue

        if kind == "fact":
            if not fact_keys:
                msgs.append(
                    f"step {step_n} ({lens}) observations[{i}]: kind=fact requires fact_keys"
                )
                continue
            for key in fact_keys:
                if key not in flat:
                    msgs.append(
                        f"step {step_n} ({lens}) observations[{i}]: unknown fact_key {key!r}"
                    )
            for key in fact_keys:
                v = flat.get(key)
                if isinstance(v, (int, float)):
                    allowed.add(float(v))

        nums = _extract_numbers(text, ignore_patterns)
        if not nums:
            continue
        if kind == "fact" and not fact_keys:
            continue
        if not evidence_ids and kind != "fact" and nums:
            msgs.append(
                f"step {step_n} ({lens}) observations[{i}]: numbers present but no evidence_ids"
            )
            continue
        for n in nums:
            if not _number_matches_allowed(n, allowed, tolerance):
                msgs.append(
                    f"step {step_n} ({lens}) observations[{i}]: "
                    f"number {n} not in evidence/fact_keys (tol={tolerance}); "
                    f"use kind=qualitative or {unverified_marker!r}"
                )
    return msgs
