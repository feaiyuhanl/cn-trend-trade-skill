#!/usr/bin/env python3
"""Registered helper: print market_pack holdings/symbols/facts (do not add _tmp_*.py)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.pack_inspect import dispatch_show_pack  # noqa: E402
from core.validate import load_json  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Print market_pack section to stdout")
    p.add_argument("section", choices=["holdings", "symbols", "facts"], nargs="?", default="holdings")
    p.add_argument("--pack", default=".trend-trade/tmp/market_pack.json")
    p.add_argument("--ts-code")
    args = p.parse_args()
    pack = load_json(Path(args.pack))
    print(dispatch_show_pack(pack, args.section, ts_code=args.ts_code), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
