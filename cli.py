#!/usr/bin/env python3
"""CLI for cn-trend-trade-skill: assemble market pack, validate schemas, journal."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.assemble import OUT_PACK, OUT_TRACE, assemble, copy_fixture_trace, save_trace  # noqa: E402
from core.journal import list_journal_dates, load_journal, save_journal  # noqa: E402
from core.validate import (  # noqa: E402
    load_json,
    validate_market_pack,
    validate_trace_against_pack,
    validate_trade_trace,
)

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def cmd_assemble(args: argparse.Namespace) -> int:
    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
    positions_file = Path(args.positions_file) if args.positions_file else None
    use_fixture = not args.live
    try:
        path = assemble(
            use_fixture=use_fixture,
            run_id=args.run_id,
            symbols=symbols,
            session_mode=args.session_mode,
            positions_file=positions_file,
            portfolio_equity=args.equity,
            risk_pct=args.risk_pct,
            indices_profile=args.indices_profile,
        )
    except (ValueError, RuntimeError) as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    print(f"OK market_pack -> {path}")
    if args.copy_trace:
        tp = copy_fixture_trace()
        print(f"OK trade_trace (sample) -> {tp}")
    return 0


def cmd_validate_pack(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    errs = validate_market_pack(data)
    if errs:
        for e in errs:
            print(f"FAIL {e}", file=sys.stderr)
        return 1
    print(f"OK market_pack {path}")
    return 0


def cmd_validate_trace(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    errs = validate_trade_trace(data)
    if args.pack:
        pack = load_json(Path(args.pack))
        errs.extend(validate_trace_against_pack(data, pack))
    if errs:
        for e in errs:
            print(f"FAIL {e}", file=sys.stderr)
        return 1
    print(f"OK trade_trace {path}")
    return 0


def cmd_save_journal(args: argparse.Namespace) -> int:
    path = Path(args.file)
    data = load_json(path)
    out = save_journal(data, date=args.date)
    print(f"OK journal -> {out}")
    return 0


def cmd_list_journal(_args: argparse.Namespace) -> int:
    dates = list_journal_dates()
    if not dates:
        print("(no journal files)")
        return 0
    for d in dates:
        n = len(load_journal(d))
        print(f"{d}\t{n} entries")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    sources_path = _ROOT / "config" / "sources.yaml"
    indices_path = _ROOT / "config" / "indices.yaml"
    if yaml is None:
        print("Install PyYAML: pip install -r requirements.txt", file=sys.stderr)
        return 1
    with sources_path.open(encoding="utf-8") as f:
        src = yaml.safe_load(f)
    print(f"cn-trend-trade-skill sources (version {src.get('version')}):")
    for s in src.get("sources", []):
        env = ",".join(s.get("env") or []) or "-"
        opt = "optional" if s.get("optional") else "required"
        print(f"  - {s['id']}: {s['name']} [{opt}] env={env}")
    token = "set" if __import__("os").environ.get("TUSHARE_TOKEN") else "unset"
    print(f"\nTUSHARE_TOKEN: {token}")
    with indices_path.open(encoding="utf-8") as f:
        idx = yaml.safe_load(f)
    print(f"\nindices profiles: {', '.join(idx.get('profiles', {}).keys())}")
    for gid, g in idx.get("groups", {}).items():
        n = len(g.get("indices", []))
        print(f"  - {gid} ({g.get('label')}): {n} indices")
    return 0


def cmd_list_indices(args: argparse.Namespace) -> int:
    if yaml is None:
        print("Install PyYAML: pip install -r requirements.txt", file=sys.stderr)
        return 1
    with (_ROOT / "config" / "indices.yaml").open(encoding="utf-8") as f:
        idx = yaml.safe_load(f)
    profile = args.profile or "comprehensive"
    prof = idx.get("profiles", {}).get(profile, {})
    groups = prof.get("include_groups") or []
    print(f"profile={profile} groups={groups}")
    for gid in groups:
        g = idx.get("groups", {}).get(gid, {})
        for item in g.get("indices", []):
            opt = " optional" if item.get("optional") else ""
            print(f"  {item['ts_code']}\t{item['name']}{opt}\t[{gid}]")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="cn-trend-trade-skill：行情包、推理链、复盘日记")
    parser.add_argument("--assemble", action="store_true", help="生成 market_pack.json")
    parser.add_argument("--live", action="store_true", help="Tushare 实盘（需 TUSHARE_TOKEN + --symbols）")
    parser.add_argument("--fixture", action="store_true", help="fixture 数据（默认）")
    parser.add_argument("--symbols", help="逗号分隔 ts_code")
    parser.add_argument("--session-mode", choices=["new_entry", "holdings_review", "mixed"])
    parser.add_argument("--positions-file", help="持仓 JSON")
    parser.add_argument("--equity", type=float, help="账户总权益")
    parser.add_argument("--risk-pct", type=float, help="单笔风险 %")
    parser.add_argument("--indices-profile", default="comprehensive")
    parser.add_argument("--run-id", help="覆盖 run_id")
    parser.add_argument("--copy-trace", action="store_true", help="复制 sample trace")
    parser.add_argument("--validate-pack", nargs="?", const=str(OUT_PACK), metavar="PATH")
    parser.add_argument("--validate-trace", metavar="PATH")
    parser.add_argument("--pack", help="与 --validate-trace 联用")
    parser.add_argument("--save-journal", metavar="FILE", help="保存复盘日记 JSON 条目")
    parser.add_argument("--journal-date", help="YYYYMMDD，配合 --save-journal")
    parser.add_argument("--list-journal", action="store_true", help="列出日记日期")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--list-indices", action="store_true")
    parser.add_argument("--profile", help="配合 --list-indices")
    args = parser.parse_args()

    if args.status:
        return cmd_status(args)
    if args.list_indices:
        return cmd_list_indices(args)
    if args.list_journal:
        return cmd_list_journal(args)
    if args.save_journal:
        return cmd_save_journal(
            argparse.Namespace(file=args.save_journal, date=args.journal_date)
        )
    if args.assemble or args.fixture:
        return cmd_assemble(args)
    if args.validate_pack is not None:
        return cmd_validate_pack(argparse.Namespace(path=args.validate_pack))
    if args.validate_trace:
        return cmd_validate_trace(argparse.Namespace(path=args.validate_trace, pack=args.pack))

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
