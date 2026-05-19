"""Market data adapter — delegates to core.fetch_live for live mode."""

from __future__ import annotations

from typing import Any


def apply_live(
    *,
    symbols: list[str],
    indices_profile: str = "comprehensive",
    run_id: str | None = None,
) -> dict[str, Any]:
    from core.fetch_live import build_live_pack

    return build_live_pack(symbols=symbols, indices_profile=indices_profile, run_id=run_id)
