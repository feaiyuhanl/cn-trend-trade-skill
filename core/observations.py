"""Normalize and classify trace observations (string legacy + structured)."""

from __future__ import annotations

from typing import Any, Literal

ObservationKind = Literal["fact", "qualitative", "mixed"]

_LEGACY_QUALITATIVE_PREFIX = "[qualitative]"


def normalize_observation(obs: Any) -> dict[str, Any]:
    """Return a structured observation dict."""
    if isinstance(obs, str):
        text = obs.strip()
        if text.startswith(_LEGACY_QUALITATIVE_PREFIX):
            return {"kind": "qualitative", "text": text, "fact_keys": []}
        return {"kind": "mixed", "text": text, "fact_keys": []}

    if isinstance(obs, dict):
        kind = obs.get("kind", "mixed")
        if kind not in ("fact", "qualitative", "mixed"):
            kind = "mixed"
        return {
            "kind": kind,
            "text": str(obs.get("text", "")),
            "fact_keys": list(obs.get("fact_keys") or []),
        }

    return {"kind": "mixed", "text": str(obs), "fact_keys": []}


def observation_text(obs: Any) -> str:
    return normalize_observation(obs)["text"]


def observation_kind(obs: Any) -> ObservationKind:
    return normalize_observation(obs)["kind"]  # type: ignore[return-value]


def is_qualitative_observation(obs: Any) -> bool:
    n = normalize_observation(obs)
    return n["kind"] == "qualitative" or _LEGACY_QUALITATIVE_PREFIX in n["text"]
