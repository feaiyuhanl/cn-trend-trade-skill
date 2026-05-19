"""Run registered adapters against a market pack."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

_REGISTRY_PATH = Path(__file__).resolve().parent / "registry.yaml"


def load_registry() -> dict[str, Any]:
    import yaml

    with _REGISTRY_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def apply_adapters(pack: dict[str, Any], *, skip: list[str] | None = None) -> dict[str, Any]:
    """Apply optional slot adapters (market fetch is handled in assemble before this)."""
    skip = skip or []
    registry = load_registry()
    for spec in registry.get("adapters", []):
        aid = spec["id"]
        if aid in skip or spec.get("slot") == "market":
            continue
        module_path = spec.get("module")
        if not module_path:
            continue
        mod = importlib.import_module(module_path)
        fn = getattr(mod, "apply", None)
        if fn:
            pack = fn(pack)
    return pack
