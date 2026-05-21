#!/usr/bin/env python3
"""CLI wrapper: watchlist risk audit. See skill/playbooks/watchlist-risk-audit.md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.watchlist_risk_audit import run_audit  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="自选风险审计")
    p.add_argument("--fixture", action="store_true", help="无 Tushare，仅结构")
    p.add_argument("--watchlist", default="config/watchlist.yaml")
    p.add_argument("--out-dir", default=".trend-trade/tmp")
    p.add_argument("--no-archive", action="store_true")
    args = p.parse_args()
    try:
        result = run_audit(
            watchlist_path=Path(args.watchlist),
            live=not args.fixture,
            out_dir=Path(args.out_dir),
            archive=not args.no_archive,
        )
    except RuntimeError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    paths = result.get("_paths", {})
    print(f"OK -> {paths.get('report')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
