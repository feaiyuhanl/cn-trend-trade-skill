"""Detect raw numbers in qualitative Agent prose fields."""

from __future__ import annotations

from typing import Any

from core.observations import _LEGACY_QUALITATIVE_PREFIX
from core.observation_verify import _extract_numbers

_IGNORE = [r"^20\d{6}$"]


def _walk_strings(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, str):
        out.append((prefix, obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.extend(_walk_strings(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_walk_strings(v, f"{prefix}[{i}]"))
    return out


def find_raw_numbers_in_prose(
    obj: Any,
    *,
    root_label: str,
    allowed_fact_values: set[float],
    tolerance: float,
) -> list[str]:
    """Numbers in prose must match allowed fact values (from facts_used)."""
    msgs: list[str] = []
    for path, text in _walk_strings(obj):
        if _LEGACY_QUALITATIVE_PREFIX in text:
            continue
        nums = _extract_numbers(text, _IGNORE)
        for n in nums:
            if not allowed_fact_values:
                msgs.append(f"{root_label}{path}: number {n} without facts_used to verify")
                continue
            matched = any(abs(n - a) <= tolerance for a in allowed_fact_values)
            if not matched:
                msgs.append(f"{root_label}{path}: number {n} not in facts_used values")
    return msgs


def allowed_values_from_facts(pack: dict[str, Any], fact_keys: list[str]) -> set[float]:
    flat = (pack.get("fact_index") or {}).get("flat", {})
    allowed: set[float] = set()
    for key in fact_keys:
        v = flat.get(key)
        if isinstance(v, (int, float)):
            allowed.add(float(v))
    return allowed
