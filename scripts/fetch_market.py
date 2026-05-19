#!/usr/bin/env python3
"""CLI wrapper: live fetch market pack (requires TUSHARE_TOKEN)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.assemble import OUT_PACK, assemble  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch market_pack via tushare")
    p.add_argument("--symbols", required=True, help="600519.SH,300750.SZ")
    p.add_argument("--indices-profile", default="comprehensive")
    p.add_argument("--session-mode", choices=["new_entry", "holdings_review", "mixed"])
    p.add_argument("--positions-file")
    args = p.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",")]
    path = assemble(
        use_fixture=False,
        symbols=symbols,
        session_mode=args.session_mode,
        positions_file=Path(args.positions_file) if args.positions_file else None,
        indices_profile=args.indices_profile,
    )
    print(f"OK {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
