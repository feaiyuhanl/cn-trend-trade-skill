#!/usr/bin/env python3
"""CLI wrapper: screen watchlist (policy-driven watch pool only)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.screen_watchlist import load_watchlist_config, run_screen  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Screen watchlist for trend watch_pool (not buy list)")
    p.add_argument("--watchlist", default="config/watchlist.yaml", help="watchlist yaml path")
    p.add_argument("--max", type=int, help="max symbols to screen")
    p.add_argument("--symbols", help="comma-separated ts_code override")
    p.add_argument("--out-dir", default=".trend-trade/tmp")
    p.add_argument("--fixture", action="store_true", help="reserved; live only for now")
    args = p.parse_args()

    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    try:
        result = run_screen(
            symbols=symbols,
            watchlist_path=Path(args.watchlist),
            live=not args.fixture,
            max_symbols=args.max,
            out_dir=Path(args.out_dir),
        )
    except RuntimeError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1

    paths = result.get("_paths", {})
    print(f"OK screened {result['meta']['screened']} as_of={result['meta'].get('as_of')}")
    print(f"  watch_pool: {len(result.get('watch_pool') or [])}")
    print(f"  allow: {result.get('market_filter', {}).get('allow_new_trend_trade')}")
    print(f"  -> {paths.get('json')}")
    print(f"  -> {paths.get('report')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
