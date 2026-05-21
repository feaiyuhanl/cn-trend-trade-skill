"""Build review context for Agent / CLI from archived recommendations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.holdings_snapshot import load_latest_holdings_snapshot
from core.paths import RECOMMENDATIONS_DIR
from core.recommendation_log import (
    list_recommendation_runs,
    load_archived_trace,
    runs_missing_review,
)
from core.rules_engine import load_rules_config
from core.skill_improvements import (
    assess_trace,
    format_dimensions_markdown,
    load_assessments_for_runs,
)

_ROOT = Path(__file__).resolve().parent.parent


def _load_review_config() -> dict[str, Any]:
    path = _ROOT / "config" / "review.yaml"
    try:
        import yaml
    except ImportError:
        return {}
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _rule_hints_for_run(summary: dict[str, Any]) -> list[str]:
    """Machine-readable hints aligned with config/rules.yaml themes."""
    hints: list[str] = []
    mf = summary.get("market_filter") or {}
    allow = mf.get("allow_new_trend_trade")
    for sym in summary.get("symbols") or []:
        ts = sym.get("ts_code")
        action = sym.get("entry_action") or ""
        phase = sym.get("phase") or ""
        if allow in ("no", "reduced") and action and action not in (
            "wait",
            "none",
            "hold",
            "hold_or_add_on_confirmed_pullback",
        ):
            if "add" in action or "buy" in action or "open" in action:
                hints.append(
                    f"[MF_NO_AGGRESSIVE_NEW_ENTRY] {ts}: 环境 allow={allow} 但 entry_action={action}"
                )
        if phase in ("markup", "distribution") and sym.get("entry_type") == "breakout":
            hints.append(
                f"[TREND_PHASE] {ts}: 阶段 {phase} 仍建议突破追入，核对是否应等回踩"
            )
        hr = sym.get("holding_review_action")
        if hr in ("trim", "exit", "reduce") and sym.get("holding_review_urgency") == "high":
            hints.append(f"[EXIT] {ts}: 持仓复盘建议 {hr}（高优先级），对照实际是否执行")
    return hints


def build_review_brief(
    *,
    date: str | None = None,
    days: int = 10,
    focus: str = "all",
) -> str:
    """
    focus: all | recommendations | holdings
    Returns markdown for Agent review-session playbook.
    """
    cfg = _load_review_config()
    default_days = (cfg.get("auto_review") or {}).get("review_days", 10)
    if days <= 0:
        days = default_days

    lines: list[str] = [
        "# 复盘简报（自动生成，供 Agent 对照趋势规则写 trace.review）",
        "",
        "> 免责声明：个人学习记录，不构成投资建议。",
        "",
    ]

    if focus in ("all", "recommendations"):
        runs = list_recommendation_runs(days=days, date=date)
        gaps = runs_missing_review(days=days)
        lines.append("## 历史推荐记录")
        lines.append("")
        if not runs:
            lines.append("- （尚无归档推荐；请先完成一次 `finalize` 分析）")
        else:
            for r in runs:
                mf = r.get("market_filter") or {}
                rev = "已复盘" if r.get("has_review") else "**待复盘**"
                lines.append(
                    f"- **{r.get('as_of_date')}** `{r.get('run_id')}` "
                    f"· {r.get('playbook')} · {r.get('session_mode')} · {rev}"
                )
                lines.append(f"  - allow_new_trend_trade: {mf.get('allow_new_trend_trade')}")
                for sym in r.get("symbols") or []:
                    lines.append(
                        f"  - `{sym.get('ts_code')}` phase={sym.get('phase')} "
                        f"entry={sym.get('entry_action')} holding={sym.get('holding_review_action') or '—'}"
                    )
                for hint in _rule_hints_for_run(r):
                    lines.append(f"  - {hint}")
        lines.append("")
        if gaps:
            lines.append("### 待补齐复盘")
            for g in gaps:
                lines.append(f"- `{g.get('run_id')}` ({g.get('as_of_date')})")
            lines.append("")

    if focus in ("all", "holdings"):
        snap = load_latest_holdings_snapshot()
        lines.append("## 持仓快照（最近 finalize）")
        lines.append("")
        if not snap:
            lines.append("- （无持仓快照；finalize 时传入 `--positions-file` 或配置 my_discipline.yaml）")
        else:
            lines.append(f"- run_id: `{snap.get('run_id')}` · as_of: {snap.get('as_of')}")
            for h in snap.get("config_holdings") or []:
                lines.append(f"- 配置持仓: `{h.get('ts_code')}` {h.get('name')} theme={h.get('theme')}")
            for p in snap.get("session_positions") or []:
                lines.append(
                    f"- 会话持仓: `{p.get('ts_code')}` cost={p.get('cost')} "
                    f"shares={p.get('shares')} stop={p.get('stop_price')}"
                )
            for ts, hr in (snap.get("holdings_review") or {}).items():
                lines.append(f"- 上次分析 `{ts}`: action={hr.get('action')} urgency={hr.get('urgency')}")
        lines.append("")

    assessments: list[dict[str, Any]] = []
    run_ids = [
        r.get("run_id")
        for r in list_recommendation_runs(days=days, date=date)
        if r.get("run_id")
    ]
    assessments = load_assessments_for_runs(run_ids[:days])
    if not assessments and run_ids:
        trace0 = load_archived_trace(str(run_ids[0]))
        pack_path = RECOMMENDATIONS_DIR / str(run_ids[0]) / "market_pack.json"
        pack0 = None
        if pack_path.exists():
            import json

            with pack_path.open(encoding="utf-8") as f:
                pack0 = json.load(f)
        if trace0:
            assessments = [assess_trace(trace0, pack0)]

    lines.append(format_dimensions_markdown(assessments=assessments or None))
    lines.append("")

    rules = load_rules_config()
    lines.append("## 机检规则提醒（写复盘时对照）")
    lines.append("")
    for r in rules.get("machine_rules") or []:
        if r.get("severity") in ("error", "warn"):
            lines.append(f"- **{r['id']}**: {r.get('description')}")
    lines.append("")

    lines.extend(
        [
            "## Agent 任务（review-session playbook）",
            "",
            "1. 对照上表「计划 vs 用户实际」填写 `trace.review.planned_vs_actual`",
            "2. 评估 `phase_accuracy`（correct / early / late）",
            "3. 列出 `discipline_violations`（含板块退潮加仓、观察池当买入等）",
            "4. 写 `lessons[]` 与 `next_improvements[]`（SKILL 演进方向）",
            "5. `python cli.py --finalize` 生成 `review-report.md`",
            "",
            "### SKILL 八维（配置见 config/skill_improvements.yaml）",
            "",
            "- `MF_PHASE_ENTRY` 大盘过滤与个股阶段 / 开仓一致性",
            "- `SECTOR_THEME_EXPOSURE` 板块退潮与主题暴露",
            "- `THEME_LEADER_LIFECYCLE` 题材生命周期与龙头传导",
            "- `MARKET_SENTIMENT` 市场情绪（涨跌停/破板/连板）",
            "- `EVENT_QUALITY_GATE` 事件风险与质量兜底",
            "- `HOLDING_EXIT_DISCIPLINE` 持仓止损与 exit_plan 纪律",
            "- `WATCH_POOL_BOUNDARY` 观察池 vs 开仓边界",
            "- `EVIDENCE_TRACEABILITY` 证据链与归档可追溯",
            "",
            "将上节「→」建议行写入 `trace.review.next_improvements`（保留维度前缀）。",
            "",
        ]
    )
    return "\n".join(lines)
