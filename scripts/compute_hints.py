#!/usr/bin/env python3
"""Recompute derived_hints on an existing market_pack.json (offline refresh)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.hints import compute_derived_hints  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("pack", nargs="?", default=".trend-trade/tmp/market_pack.json")
    args = p.parse_args()
    path = Path(args.pack)
    with path.open(encoding="utf-8") as f:
        pack = json.load(f)
    for key in ("symbols", "indices"):
        for inst in pack.get(key, []):
            bars = inst.get("bars", {})
            inst["derived_hints"] = compute_derived_hints(
                bars.get("daily", []),
                bars.get("weekly", []),
                bars.get("monthly", []),
            )
    with path.open("w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)
    print(f"OK hints refreshed -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
