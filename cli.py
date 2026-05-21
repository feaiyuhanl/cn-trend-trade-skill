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
from core.enrich_trace import enrich_trace  # noqa: E402
from core.pipeline import finalize_trace  # noqa: E402
from core.report_render import (  # noqa: E402
    render_audit_sheet,
    render_decision_dossier,
    render_review_report,
    render_trade_report,
)
from core.recommendation_log import (  # noqa: E402
    list_recommendation_dates,
    list_recommendation_runs,
    runs_missing_review,
)
from core.review_brief import build_review_brief  # noqa: E402
from core.rules_engine import load_rules_config  # noqa: E402
from core.screen_watchlist import run_screen  # noqa: E402
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
    if args.enrich and args.pack:
        pack = load_json(Path(args.pack))
        data = enrich_trace(data, pack)
        save_trace(data, path)
        print(f"OK enriched trace -> {path}")
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


def cmd_enrich_trace(args: argparse.Namespace) -> int:
    trace = load_json(Path(args.trace))
    pack = load_json(Path(args.pack))
    enrich_trace(trace, pack)
    out = Path(args.out) if args.out else Path(args.trace)
    save_trace(trace, out)
    print(f"OK enriched -> {out}")
    return 0


def cmd_render_report(args: argparse.Namespace) -> int:
    trace = load_json(Path(args.trace))
    pack = load_json(Path(args.pack)) if args.pack else None
    kind = args.report_kind or "trade"
    if kind == "dossier":
        text = render_decision_dossier(trace, pack)
    elif kind == "audit":
        text = render_audit_sheet(trace, pack)
    elif kind == "review":
        text = render_review_report(trace, pack)
    else:
        text = render_trade_report(trace, pack)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"OK {kind} report -> {out}")
    else:
        print(text)
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    trace_path = Path(args.finalize)
    pack_path = Path(args.pack)
    out_dir = Path(args.out_dir) if args.out_dir else trace_path.parent
    code, errs = finalize_trace(
        trace_path,
        pack_path,
        out_dir=out_dir,
        no_auto_review=getattr(args, "no_auto_review", False),
    )
    if code != 0:
        for e in errs:
            print(f"FAIL {e}", file=sys.stderr)
        print(f"FAIL validation-errors -> {out_dir / 'validation-errors.md'}", file=sys.stderr)
        return 1
    print(f"OK enriched trace -> {trace_path}")
    print(f"OK report -> {out_dir / 'report.md'}")
    print(f"OK decision-dossier -> {out_dir / 'decision-dossier.md'}")
    print(f"OK audit-sheet -> {out_dir / 'audit-sheet.md'}")
    if load_json(Path(args.finalize)).get("review"):
        print(f"OK review-report -> {out_dir / 'review-report.md'}")
    if not getattr(args, "no_auto_review", False):
        print("OK recommendation archived -> .trend-trade/recommendations/")
    return 0


def cmd_screen_watchlist(args: argparse.Namespace) -> int:
    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
    try:
        result = run_screen(
            symbols=symbols,
            watchlist_path=Path(args.watchlist) if args.watchlist else None,
            live=not args.fixture,
            max_symbols=args.max,
            out_dir=Path(args.out_dir) if args.out_dir else None,
        )
    except RuntimeError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    paths = result.get("_paths", {})
    print(f"OK screened {result['meta']['screened']} as_of={result['meta'].get('as_of')}")
    print(f"  watch_pool: {len(result.get('watch_pool') or [])}")
    print(f"  allow_new_trend_trade: {result.get('market_filter', {}).get('allow_new_trend_trade')}")
    print(f"  json -> {paths.get('json')}")
    print(f"  report -> {paths.get('report')}")
    return 0


def cmd_list_rules(_args: argparse.Namespace) -> int:
    rules = load_rules_config()
    print(f"rules version {rules.get('version')} default_profile={rules.get('default_profile')}")
    for r in rules.get("machine_rules", []):
        print(f"  [{r.get('severity')}] {r['id']}: {r.get('description')}")
    return 0


def cmd_save_journal(args: argparse.Namespace) -> int:
    path = Path(args.file)
    data = load_json(path)
    out = save_journal(data, date=args.date)
    print(f"OK journal -> {out}")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    focus = "holdings" if getattr(args, "review_holdings_only", False) else "all"
    text = build_review_brief(
        date=args.review_date,
        days=args.review_days,
        focus=focus,
    )
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"OK review-brief -> {out}")
    else:
        print(text)
    return 0


def cmd_fill_review_gaps(args: argparse.Namespace) -> int:
    gaps = runs_missing_review(days=args.review_days)
    if not gaps:
        print("OK 无待补齐复盘（近期归档均已含 trace.review 或尚无归档）")
        return 0
    print(f"待补齐复盘 {len(gaps)} 条（最近 {args.review_days} 次归档）：")
    for g in gaps:
        arch = g.get("archive_dir") or g.get("run_id")
        print(f"  {g.get('as_of_date')}\t{g.get('run_id')}\t{arch}")
    print("\n运行: python cli.py --review 获取简报，再按 review-session playbook 写 trace.review 后 finalize")
    return 0


def cmd_list_recommendations(_args: argparse.Namespace) -> int:
    dates = list_recommendation_dates()
    if not dates:
        print("(no archived recommendations)")
        return 0
    for d in dates:
        n = len(list_recommendation_runs(date=d))
        print(f"{d}\t{n} run(s)")
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
    parser.add_argument("--pack", help="与 --validate-trace / --enrich-trace / --render-report 联用")
    parser.add_argument("--enrich", action="store_true", help="validate 前注入 computed 字段")
    parser.add_argument("--enrich-trace", metavar="PATH", help="注入 position_plan.computed 等")
    parser.add_argument("--out", help="--enrich-trace / --render-report 输出路径")
    parser.add_argument("--render-report", metavar="PATH", help="从 trace 渲染报告（禁止新数字）")
    parser.add_argument(
        "--report-kind",
        choices=["trade", "dossier", "audit", "review"],
        default="trade",
        help="配合 --render-report：trade | dossier | audit",
    )
    parser.add_argument(
        "--finalize",
        metavar="TRACE",
        help="enrich + validate + 渲染 report/dossier/audit（需 --pack）",
    )
    parser.add_argument(
        "--out-dir",
        help="配合 --finalize：报告输出目录（默认 trace 同目录）",
    )
    parser.add_argument("--list-rules", action="store_true", help="列出机检规则")
    parser.add_argument(
        "--screen-watchlist",
        action="store_true",
        help="自选趋势观察池筛选（非买入推荐，见 watchlist-screen playbook）",
    )
    parser.add_argument("--watchlist", default="config/watchlist.yaml", help="配合 --screen-watchlist")
    parser.add_argument("--max", type=int, help="配合 --screen-watchlist：最多扫描只数")
    parser.add_argument("--save-journal", metavar="FILE", help="保存复盘日记 JSON 条目")
    parser.add_argument("--journal-date", help="YYYYMMDD，配合 --save-journal")
    parser.add_argument("--list-journal", action="store_true", help="列出日记日期")
    parser.add_argument(
        "--review",
        action="store_true",
        help="生成复盘简报（历史推荐 + 持仓快照 + 规则提示）",
    )
    parser.add_argument("--review-date", type=str, help="复盘日期 YYYYMMDD（与 --review 联用）")
    parser.add_argument(
        "--review-days",
        type=int,
        default=10,
        help="复盘回溯条数/归档次数（默认 10）",
    )
    parser.add_argument(
        "--review-holdings-only",
        action="store_true",
        help="复盘简报仅含持仓部分",
    )
    parser.add_argument(
        "--fill-review-gaps",
        action="store_true",
        help="列出已归档但未写 trace.review 的 run_id",
    )
    parser.add_argument(
        "--no-auto-review",
        action="store_true",
        help="finalize 时不归档推荐、不写持仓快照",
    )
    parser.add_argument(
        "--list-recommendations",
        action="store_true",
        help="按日期列出已归档推荐",
    )
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
    if args.list_recommendations:
        return cmd_list_recommendations(args)
    if args.fill_review_gaps:
        return cmd_fill_review_gaps(args)
    if args.review:
        return cmd_review(args)
    if args.save_journal:
        return cmd_save_journal(
            argparse.Namespace(file=args.save_journal, date=args.journal_date)
        )
    if args.assemble or args.fixture:
        return cmd_assemble(args)
    if args.validate_pack is not None:
        return cmd_validate_pack(argparse.Namespace(path=args.validate_pack))
    if args.validate_trace:
        return cmd_validate_trace(
            argparse.Namespace(
                path=args.validate_trace,
                pack=args.pack,
                enrich=args.enrich,
            )
        )
    if args.enrich_trace:
        if not args.pack:
            print("--enrich-trace requires --pack", file=sys.stderr)
            return 1
        return cmd_enrich_trace(
            argparse.Namespace(trace=args.enrich_trace, pack=args.pack, out=args.out)
        )
    if args.finalize:
        if not args.pack:
            print("--finalize requires --pack", file=sys.stderr)
            return 1
        return cmd_finalize(args)
    if args.render_report:
        return cmd_render_report(
            argparse.Namespace(
                trace=args.render_report,
                pack=args.pack,
                out=args.out,
                report_kind=args.report_kind,
            )
        )
    if args.list_rules:
        return cmd_list_rules(args)
    if args.screen_watchlist:
        return cmd_screen_watchlist(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
