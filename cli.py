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
from core.init_trace import init_trace_from_pack  # noqa: E402
from core.pack_inspect import dispatch_show_pack  # noqa: E402
from core.trace_merge import merge_decisions  # noqa: E402
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
from core.screen_watchlist import run_merge_screen_trace, run_screen  # noqa: E402
from core.universe_mainboard import export_mainboard_symbols_yaml  # noqa: E402
from core.watchlist_risk_audit import run_audit as run_watchlist_risk_audit  # noqa: E402
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
            fail_on_stale=not getattr(args, "allow_stale", False),
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


def cmd_audit_watchlist(args: argparse.Namespace) -> int:
    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
    try:
        result = run_watchlist_risk_audit(
            symbols=symbols,
            watchlist_path=Path(args.watchlist) if args.watchlist else None,
            live=not args.fixture,
            out_dir=Path(args.out_dir) if args.out_dir else None,
            archive=not args.no_archive,
        )
    except RuntimeError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    paths = result.get("_paths", {})
    summary = result.get("summary") or {}
    print(f"OK audit {result['meta']['symbols']} as_of={result['meta'].get('as_of')}")
    print(
        f"  block={summary.get('block', 0)} high={summary.get('high', 0)} "
        f"warn={summary.get('warn', 0)} concept={summary.get('concept', 0)}"
    )
    print(f"  json -> {paths.get('json')}")
    print(f"  report -> {paths.get('report')}")
    return 0


def cmd_export_mainboard_universe(args: argparse.Namespace) -> int:
    out = Path(args.export_mainboard_universe)
    try:
        result = export_mainboard_symbols_yaml(out)
    except RuntimeError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    meta = result.get("meta") or {}
    print(f"OK exported {result.get('count')} symbols -> {result.get('path')}")
    print(f"  board_count={meta.get('board_count')} after_liquidity={meta.get('after_liquidity')}")
    clf = meta.get("chronic_loss_filter") or {}
    if clf.get("removed_count") is not None:
        print(f"  chronic_loss removed={clf.get('removed_count')} final={meta.get('final_count')}")
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
            screen_trace_path=Path(args.screen_trace) if getattr(args, "screen_trace", None) else None,
            data_only=getattr(args, "screen_data_only", False),
            universe_mode=getattr(args, "universe_mode", None),
            trend_top_n=getattr(args, "top", None),
            fail_on_stale=not getattr(args, "allow_stale", False),
        )
    except RuntimeError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    paths = result.get("_paths", {})
    print(
        f"OK screened {result['meta']['screened']} "
        f"trade_date={result['meta'].get('trade_date')} as_of={result['meta'].get('as_of')}"
    )
    if result["meta"].get("ranked_by"):
        print(f"  ranked_by: {result['meta']['ranked_by']}")
    elif result.get("gaps"):
        for g in result["gaps"]:
            if "ai_rank" in g or "data_only" in g:
                print(f"  NOTE {g}")
    if result["meta"].get("data_stale"):
        print("  FAIL data_stale: 外部行情未刷新到当日收盘，已中止或结论无效", file=sys.stderr)
        for key in ("data_stale_headline", "data_stale_detail", "data_stale_retry"):
            line = result["meta"].get(key)
            if line:
                print(f"    {line}", file=sys.stderr)
        if not getattr(args, "allow_stale", False):
            return 1
    print(f"  watch_pool: {len(result.get('watch_pool') or [])}")
    trend = result.get("trend_top10") or {}
    if trend.get("stocks"):
        print(f"  trend_top10 ({trend.get('scope')}): {len(trend['stocks'])}")
        for s in trend["stocks"][:3]:
            print(
                f"    #{s.get('rank')} {s.get('ts_code')} rank={s.get('safety_rank')} "
                f"band={s.get('position_band')}"
            )
    print(f"  allow_new_trend_trade: {result.get('market_filter', {}).get('allow_new_trend_trade')}")
    if result.get("screen_pack_path"):
        print(f"  screen_pack -> {result['screen_pack_path']}")
    if result.get("screen_trace_path"):
        print(f"  screen_trace -> {result['screen_trace_path']}")
    for key in ("json", "report", "dossier", "audit", "trend_top10"):
        if paths.get(key):
            print(f"  {key} -> {paths[key]}")
    wp = result.get("watch_pool_full_analysis") or {}
    if wp.get("combined_report"):
        print(f"  watch_pool report -> {wp['combined_report']}")
    if wp.get("errors"):
        print(f"  WARN watch_pool finalize: {len(wp['errors'])} errors", file=sys.stderr)
    return 0


def cmd_merge_screen_trace(args: argparse.Namespace) -> int:
    pack_path = Path(args.pack)
    trace_path = Path(args.merge_screen_trace)
    if not pack_path.exists():
        print(f"FAIL pack not found: {pack_path}", file=sys.stderr)
        return 1
    if not trace_path.exists():
        print(f"FAIL trace not found: {trace_path}", file=sys.stderr)
        return 1
    try:
        result = run_merge_screen_trace(
            pack_path=pack_path,
            trace_path=trace_path,
            watchlist_path=Path(args.watchlist) if args.watchlist else None,
            out_dir=Path(args.out_dir) if args.out_dir else None,
        )
    except Exception as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    paths = result.get("_paths", {})
    print(f"OK merged AI ranks for {result['meta']['screened']} symbols")
    print(f"  watch_pool: {len(result.get('watch_pool') or [])}")
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


def cmd_show_pack(args: argparse.Namespace) -> int:
    pack = load_json(Path(args.pack))
    try:
        text = dispatch_show_pack(pack, args.show_pack, ts_code=args.ts_code)
    except ValueError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    print(text, end="" if text.endswith("\n") else "\n")
    return 0


def cmd_init_trace(args: argparse.Namespace) -> int:
    pack = load_json(Path(args.pack))
    if args.from_sample:
        trace = load_json(_ROOT / "sample" / "trade_trace.sample.json")
        trace.setdefault("meta", {})["run_id"] = (pack.get("meta") or {}).get("run_id")
        trace["meta"]["session_mode"] = (pack.get("user_context") or {}).get(
            "session_mode"
        ) or trace["meta"].get("session_mode")
    else:
        trace = init_trace_from_pack(pack, playbook=args.playbook or "full-analysis")
    if getattr(args, "auto_fill", False) and (args.playbook or "full-analysis") != "watchlist-screen":
        from core.fill_full_analysis import fill_full_analysis_trace_from_pack

        trace = fill_full_analysis_trace_from_pack(trace, pack)
    out = Path(args.out) if args.out else OUT_TRACE
    save_trace(trace, out)
    print(f"OK trade_trace scaffold -> {out}")
    print(f"  symbols: {len(trace.get('decisions') or {})}")
    print(f"  lenses: {len(trace.get('meta', {}).get('lenses_applied') or [])}")
    if getattr(args, "auto_fill", False):
        print(f"  steps: {len(trace.get('steps') or [])}")
    return 0


def cmd_fill_analysis_trace(args: argparse.Namespace) -> int:
    trace_path = Path(args.fill_analysis_trace)
    pack_path = Path(args.pack)
    if not pack_path.exists():
        print(f"FAIL pack not found: {pack_path}", file=sys.stderr)
        return 1
    trace = load_json(trace_path)
    pack = load_json(pack_path)
    from core.fill_full_analysis import fill_full_analysis_trace_from_pack

    trace = fill_full_analysis_trace_from_pack(trace, pack)
    out = Path(args.out) if args.out else trace_path
    save_trace(trace, out)
    print(f"OK filled full-analysis trace -> {out}")
    print(f"  steps: {len(trace.get('steps') or [])}")
    return 0


def _load_patch_json(path: str | None) -> dict:
    if path in (None, "-"):
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("patch must be a JSON object")
    return data


def cmd_patch_trace(args: argparse.Namespace) -> int:
    trace_path = Path(args.patch_trace)
    trace = load_json(trace_path)
    try:
        patch = _load_patch_json(args.patch)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    merged = merge_decisions(trace, patch)
    save_trace(merged, trace_path)
    print(f"OK patched trace -> {trace_path}")
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
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="允许使用滞后交易日 K 线继续（默认 live 在 data_stale 时失败退出）",
    )
    parser.add_argument("--fixture", action="store_true", help="fixture 数据（默认）")
    parser.add_argument("--symbols", help="逗号分隔 ts_code")
    parser.add_argument("--session-mode", choices=["new_entry", "holdings_review", "mixed"])
    parser.add_argument("--positions-file", help="持仓 JSON")
    parser.add_argument("--equity", type=float, help="账户总权益")
    parser.add_argument("--risk-pct", type=float, help="单笔风险 %")
    parser.add_argument("--indices-profile", default="comprehensive")
    parser.add_argument("--run-id", help="覆盖 run_id")
    parser.add_argument("--copy-trace", action="store_true", help="复制 sample trace")
    parser.add_argument(
        "--show-pack",
        metavar="SECTION",
        help="打印 pack 摘要：holdings | symbols | facts（需 --pack）",
    )
    parser.add_argument("--ts-code", help="配合 --show-pack facts：过滤单标的")
    parser.add_argument(
        "--init-trace",
        action="store_true",
        help="从 market_pack 生成 trade_trace 骨架（需 --pack）",
    )
    parser.add_argument(
        "--from-sample",
        action="store_true",
        help="配合 --init-trace：以 sample trace 为模板并覆盖 run_id",
    )
    parser.add_argument("--playbook", help="配合 --init-trace：playbook 名")
    parser.add_argument(
        "--auto-fill",
        action="store_true",
        help="配合 --init-trace：full-analysis 时自动填充 steps/decisions（规则引擎）",
    )
    parser.add_argument(
        "--fill-analysis-trace",
        metavar="TRACE",
        help="将已存在的 trace 用 pack 填充 full-analysis 证据链（需 --pack）",
    )
    parser.add_argument(
        "--patch-trace",
        metavar="TRACE",
        help="深度合并 JSON patch 到 trace（--patch FILE 或 - 表示 stdin）",
    )
    parser.add_argument(
        "--patch",
        help="配合 --patch-trace：patch JSON 文件路径，- 为 stdin",
    )
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
        "--export-mainboard-universe",
        nargs="?",
        const="config/mainboard_symbols.yaml",
        metavar="OUT",
        help="导出主板 universe 快照（去 ST/连续亏损/黑名单 + 流动性预筛）",
    )
    parser.add_argument(
        "--screen-watchlist",
        action="store_true",
        help="自选趋势观察池筛选（非买入推荐，见 watchlist-screen playbook）",
    )
    parser.add_argument("--watchlist", default="config/watchlist.yaml", help="配合 --screen-watchlist / --audit-watchlist")
    parser.add_argument("--max", type=int, help="配合 --screen-watchlist：最多扫描只数")
    parser.add_argument(
        "--universe-mode",
        choices=["watchlist", "mainboard", "both"],
        help="配合 --screen-watchlist：扫描范围（默认见 watchlist.yaml screening_policy.universe_mode）",
    )
    parser.add_argument(
        "--top",
        type=int,
        help="配合 --screen-watchlist：趋势分 TOP N 排行（默认 10）",
    )
    parser.add_argument(
        "--screen-data-only",
        action="store_true",
        help="配合 --screen-watchlist：仅拉 pack + screen_trace 骨架，不合并 AI 排序",
    )
    parser.add_argument(
        "--screen-trace",
        help="配合 --screen-watchlist：指定已 patch 的 screen_trace.json",
    )
    parser.add_argument(
        "--merge-screen-trace",
        metavar="TRACE",
        help="将 AI patch 后的 screen_trace 合并进观察池报告（需 --pack screen_pack.json）",
    )
    parser.add_argument(
        "--audit-watchlist",
        action="store_true",
        help="自选风险审计（垃圾股/ST/业绩预警/题材嫌疑，见 watchlist-risk-audit playbook）",
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="配合 --audit-watchlist：不复制到 .trend-trade/archive/",
    )
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
    if args.export_mainboard_universe:
        return cmd_export_mainboard_universe(args)
    if args.screen_watchlist:
        return cmd_screen_watchlist(args)
    if args.merge_screen_trace:
        if not args.pack:
            print("--merge-screen-trace requires --pack (screen_pack.json)", file=sys.stderr)
            return 1
        return cmd_merge_screen_trace(args)
    if args.audit_watchlist:
        return cmd_audit_watchlist(args)
    if args.show_pack:
        if not args.pack:
            print("--show-pack requires --pack", file=sys.stderr)
            return 1
        return cmd_show_pack(args)
    if args.fill_analysis_trace:
        if not args.pack:
            print("--fill-analysis-trace requires --pack", file=sys.stderr)
            return 1
        return cmd_fill_analysis_trace(args)
    if args.init_trace:
        if not args.pack:
            print("--init-trace requires --pack", file=sys.stderr)
            return 1
        return cmd_init_trace(args)
    if args.patch_trace:
        if not args.patch:
            print("--patch-trace requires --patch FILE (or - for stdin)", file=sys.stderr)
            return 1
        return cmd_patch_trace(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
