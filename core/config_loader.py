from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent


def load_yaml(name: str) -> dict[str, Any]:
    path = _ROOT / "config" / name
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_indices_config() -> dict[str, Any]:
    return load_yaml("indices.yaml")


def resolve_indices_for_profile(profile: str) -> list[dict[str, Any]]:
    """Return flat list of index entries with index_group set."""
    cfg = load_indices_config()
    prof = cfg.get("profiles", {}).get(profile)
    if not prof:
        raise ValueError(f"Unknown indices profile: {profile}")
    groups = prof.get("include_groups") or []
    out: list[dict[str, Any]] = []
    for gid in groups:
        g = cfg.get("groups", {}).get(gid, {})
        if g.get("optional_group") and g.get("optional_group") is True:
            continue
        for item in g.get("indices", []):
            if item.get("source") == "external":
                continue
            entry = dict(item)
            entry["index_group"] = gid
            entry["category"] = gid
            out.append(entry)
    return out


def fetch_lookback() -> dict[str, int]:
    cfg = load_indices_config()
    return dict(cfg.get("fetch", {}).get("lookback_bars", {}))
