"""Placeholder consultation slot — no external API; extensible for news/research feeds."""

from __future__ import annotations

from typing import Any


def apply(pack: dict[str, Any]) -> dict[str, Any]:
    pack.setdefault("slots", {})
    pack["slots"]["consultation"] = {
        "items": [],
        "meta": {
            "adapter_id": "consultation_stub",
            "status": "skip",
            "message": "No consultation provider configured; add adapter in adapters/registry.yaml",
        },
    }
    applied = pack.setdefault("meta", {}).setdefault("adapters_applied", [])
    if "consultation_stub" not in applied:
        applied.append("consultation_stub")
    return pack
