"""Assess archived/full traces against the five SKILL evolution dimensions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from core.paths import CONFIG_DIR, RECOMMENDATIONS_DIR

DimensionStatus = Literal["ok", "warn", "gap", "na"]

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = CONFIG_DIR / "skill_improvements.yaml"

# Stable IDs (also used as next_improvements prefix)
MF_PHASE_ENTRY = "MF_PHASE_ENTRY"
SECTOR_THEME_EXPOSURE = "SECTOR_THEME_EXPOSURE"
HOLDING_EXIT_DISCIPLINE = "HOLDING_EXIT_DISCIPLINE"
WATCH_POOL_BOUNDARY = "WATCH_POOL_BOUNDARY"
EVIDENCE_TRACEABILITY = "EVIDENCE_TRACEABILITY"
THEME_LEADER_LIFECYCLE = "THEME_LEADER_LIFECYCLE"
MARKET_SENTIMENT = "MARKET_SENTIMENT"
EVENT_QUALITY_GATE = "EVENT_QUALITY_GATE"

ALL_DIMENSION_IDS = (
    MF_PHASE_ENTRY,
    SECTOR_THEME_EXPOSURE,
    THEME_LEADER_LIFECYCLE,
    MARKET_SENTIMENT,
    EVENT_QUALITY_GATE,
    HOLDING_EXIT_DISCIPLINE,
    WATCH_POOL_BOUNDARY,
    EVIDENCE_TRACEABILITY,
)

_CAUTIOUS_ENTRY = frozenset(
    {"wait", "none", "not_applicable", "hold", "hold_or_add_on_confirmed_pullback"}
)
_AGGRESSIVE_TOKENS = ("buy", "open", "chase", "breakout_chase", "full_size")


def load_dimensions_config() -> list[dict[str, Any]]:
    try:
        import yaml
    except ImportError:
        return []
    if not _CONFIG_PATH.exists():
        return []
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return list(data.get("dimensions") or [])


def _theme_map() -> dict[str, str]:
    try:
        import yaml
    except ImportError:
        return {}
    path = CONFIG_DIR / "themes.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out: dict[str, str] = {}
    for theme_id, block in (data.get("themes") or {}).items():
        for code in block.get("ts_codes") or []:
            ts = str(code).split("#")[0].strip()
            if ts:
                out[ts] = theme_id
    return out


def _discipline_map(trace: dict[str, Any]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for item in trace.get("discipline_checklist") or []:
        rid = item.get("rule_id") or item.get("rule")
        if rid:
            out[str(rid)] = bool(item.get("passed") if "passed" in item else item.get("checked"))
    return out


def _held_ts_codes(pack: dict[str, Any] | None) -> set[str]:
    if not pack:
        return set()
    return {
        p["ts_code"]
        for p in (pack.get("user_context") or {}).get("positions") or []
        if p.get("ts_code")
    }


def _evidence_stats(trace: dict[str, Any]) -> dict[str, Any]:
    total_obs = 0
    fact_obs = 0
    with_fact_keys = 0
    for step in trace.get("steps") or []:
        for obs in step.get("observations") or []:
            total_obs += 1
            if isinstance(obs, dict):
                if obs.get("kind") == "fact":
                    fact_obs += 1
                    if obs.get("fact_keys"):
                        with_fact_keys += 1
            elif isinstance(obs, str) and "fact_keys" not in obs:
                pass
    facts_used = 0
    for dec in (trace.get("decisions") or {}).values():
        facts_used += len(dec.get("facts_used") or [])
    resolved = trace.get("resolved") or {}
    audit = resolved.get("audit") or {}
    return {
        "total_observations": total_obs,
        "fact_observations": fact_obs,
        "fact_with_keys": with_fact_keys,
        "facts_used_count": facts_used,
        "unknown_facts_used": len(audit.get("unknown_facts_used") or []),
        "gaps_count": len(trace.get("gaps") or []),
    }


def assess_mf_phase_entry(
    trace: dict[str, Any], pack: dict[str, Any] | None
) -> dict[str, Any]:
    findings: list[str] = []
    mf = trace.get("market_filter") or {}
    allow = mf.get("allow_new_trend_trade")
    held = _held_ts_codes(pack)

    for ts, dec in (trace.get("decisions") or {}).items():
        entry = dec.get("entry") or {}
        action = (entry.get("action") or "").lower()
        phase = dec.get("phase") or ""
        etype = (entry.get("type") or "").lower()
        if ts in held:
            continue
        if allow == "no" and action and action not in _CAUTIOUS_ENTRY:
            if any(t in action for t in _AGGRESSIVE_TOKENS):
                findings.append(f"{ts}: allow=no 但 entry.action={entry.get('action')}")
        if allow == "reduced" and etype == "breakout" and "缩" not in (entry.get("rationale") or ""):
            findings.append(f"{ts}: reduced 环境 breakout 未在 rationale 说明缩仓")
        if phase == "unclear" and action and action not in (
            "wait",
            "none",
            "not_applicable",
        ):
            findings.append(f"{ts}: phase=unclear 但 entry.action={entry.get('action')}")
        if phase in ("distribution", "decline") and etype == "breakout":
            findings.append(f"{ts}: 阶段 {phase} 仍建议突破追入")

    status: DimensionStatus = "ok" if not findings else "warn"
    if allow == "no" and any("allow=no" in f for f in findings):
        status = "gap"
    return {
        "id": MF_PHASE_ENTRY,
        "status": status,
        "findings": findings,
        "metrics": {"allow_new_trend_trade": allow},
    }


def assess_sector_theme(
    trace: dict[str, Any], pack: dict[str, Any] | None
) -> dict[str, Any]:
    findings: list[str] = []
    mf = trace.get("market_filter") or {}
    retreats = mf.get("sector_retreats") or []
    discipline = _discipline_map(trace)
    theme_map = _theme_map()

    if retreats and discipline.get("NO_CHASE_ON_RED_DAY") is False:
        findings.append("存在 sector_retreats 但 NO_CHASE_ON_RED_DAY 未通过")
    if retreats and discipline.get("SECTOR_CORRELATION_CAP") is False:
        findings.append("板块退潮但 SECTOR_CORRELATION_CAP 未通过")

    held_by_theme: dict[str, list[str]] = {}
    for ts in _held_ts_codes(pack):
        th = theme_map.get(ts, "unknown")
        held_by_theme.setdefault(th, []).append(ts)

    allow = mf.get("allow_new_trend_trade")
    for theme, codes in held_by_theme.items():
        if len(codes) >= 2 and allow in ("yes", "reduced"):
            for ts, dec in (trace.get("decisions") or {}).items():
                if ts in codes or theme_map.get(ts) != theme:
                    continue
                action = (dec.get("entry") or {}).get("action") or ""
                if action and action not in _CAUTIOUS_ENTRY and "add" in action.lower():
                    findings.append(f"{ts}: 同主题 {theme} 已持仓 {len(codes)} 只仍建议加仓")

    if not retreats and trace.get("meta", {}).get("playbook") != "watchlist-screen":
        findings.append("trace 未记录 sector_retreats（复盘时建议补记）")

    status: DimensionStatus = "ok"
    if findings:
        status = "gap" if any("退潮" in f for f in findings) else "warn"
    return {
        "id": SECTOR_THEME_EXPOSURE,
        "status": status,
        "findings": findings,
        "metrics": {
            "sector_retreats": len(retreats),
            "themes_held": {k: len(v) for k, v in held_by_theme.items()},
        },
    }


def assess_holding_exit(
    trace: dict[str, Any], pack: dict[str, Any] | None
) -> dict[str, Any]:
    findings: list[str] = []
    positions = (pack.get("user_context") or {}).get("positions") if pack else []
    pos_by_ts = {p["ts_code"]: p for p in positions if p.get("ts_code")}

    if not pos_by_ts:
        return {
            "id": HOLDING_EXIT_DISCIPLINE,
            "status": "na",
            "findings": ["本次无会话持仓，跳过"],
            "metrics": {},
        }

    discipline = _discipline_map(trace)
    if discipline.get("STOP_RECORDED") is False:
        findings.append("discipline STOP_RECORDED 未通过")

    for ts, pos in pos_by_ts.items():
        dec = (trace.get("decisions") or {}).get(ts) or {}
        if not pos.get("stop_price") and not (dec.get("exit_plan") or {}).get("primary_trigger"):
            findings.append(f"{ts}: 无 stop_price 且无 exit_plan.primary_trigger")
        hr = dec.get("holding_review") or {}
        if hr.get("urgency") == "high" and hr.get("action") in ("trim", "exit", "reduce"):
            findings.append(
                f"{ts}: 分析建议 {hr.get('action')}（高优先级），复盘须对照是否执行"
            )

    status: DimensionStatus = "ok" if not findings else "warn"
    if any("无 stop" in f for f in findings):
        status = "gap"
    return {
        "id": HOLDING_EXIT_DISCIPLINE,
        "status": status,
        "findings": findings,
        "metrics": {"positions": len(pos_by_ts)},
    }


def assess_watch_pool_boundary(trace: dict[str, Any], pack: dict[str, Any] | None) -> dict[str, Any]:
    findings: list[str] = []
    discipline = _discipline_map(trace)
    meta = trace.get("meta") or {}
    forbid_words = ["买入推荐", "优先推荐", "优先买入"]

    if discipline.get("WATCH_POOL_NOT_BUY") is False:
        findings.append("WATCH_POOL_NOT_BUY discipline 未通过")

    blob = str(trace.get("decisions", {})) + str(trace.get("steps", []))
    for w in forbid_words:
        if w in blob:
            findings.append(f"trace 文案含禁止词「{w}」")

    if meta.get("playbook") == "watchlist-screen":
        for ts, dec in (trace.get("decisions") or {}).items():
            action = (dec.get("entry") or {}).get("action") or ""
            if action and action not in _CAUTIOUS_ENTRY and "watch" not in action.lower():
                findings.append(f"{ts}: 观察池筛选 run 出现激进 entry.action={action}")

    status: DimensionStatus = "ok" if not findings else "warn"
    if any("禁止词" in f for f in findings):
        status = "gap"
    return {
        "id": WATCH_POOL_BOUNDARY,
        "status": status,
        "findings": findings,
        "metrics": {"playbook": meta.get("playbook")},
    }


def assess_evidence_traceability(
    trace: dict[str, Any], pack: dict[str, Any] | None
) -> dict[str, Any]:
    findings: list[str] = []
    stats = _evidence_stats(trace)
    meta = trace.get("meta") or {}

    lenses = meta.get("lenses_applied") or []
    steps = trace.get("steps") or []
    if len(steps) != len(lenses):
        findings.append(f"steps({len(steps)}) 与 lenses_applied({len(lenses)}) 数量不一致")

    coverage = 1.0
    if stats["fact_observations"] > 0:
        coverage = stats["fact_with_keys"] / stats["fact_observations"]
        if coverage < 0.8:
            findings.append(
                f"fact 观测 fact_keys 覆盖率 {coverage:.0%}（目标≥80%）"
            )
    if stats["unknown_facts_used"] > 0:
        findings.append(f"unknown_facts_used: {stats['unknown_facts_used']} 项")
    if stats["gaps_count"] > 0:
        findings.append(f"trace.gaps 仍有 {stats['gaps_count']} 项未闭合")

    run_id = meta.get("run_id")
    archived = bool(run_id and (RECOMMENDATIONS_DIR / str(run_id)).exists())
    if not archived:
        findings.append("本 run 尚未归档至 .trend-trade/recommendations/（finalize 后自动写入）")

    status: DimensionStatus = "ok" if not findings else "warn"
    if stats["unknown_facts_used"] or (
        stats["fact_observations"] > 0 and coverage < 0.5
    ):
        status = "gap"
    return {
        "id": EVIDENCE_TRACEABILITY,
        "status": status,
        "findings": findings,
        "metrics": {**stats, "archived": archived},
    }


def assess_theme_leader_lifecycle(
    trace: dict[str, Any], pack: dict[str, Any] | None
) -> dict[str, Any]:
    findings: list[str] = []
    tc = ((pack or {}).get("slots") or {}).get("theme_context") or {}
    if not tc.get("themes") and pack:
        findings.append("pack 无 theme_context（assemble enrich 未运行？）")
    for th in tc.get("themes") or []:
        if th.get("leader_limit_down"):
            findings.append(f"主题 {th.get('theme_id')} 龙头跌停")
    status: DimensionStatus = "ok" if not findings else "warn"
    if any("龙头跌停" in f for f in findings):
        status = "gap"
    return {"id": THEME_LEADER_LIFECYCLE, "status": status, "findings": findings}


def assess_market_sentiment_dim(
    trace: dict[str, Any], pack: dict[str, Any] | None
) -> dict[str, Any]:
    findings: list[str] = []
    sent = (pack or {}).get("market_sentiment") or {}
    mf = trace.get("market_filter") or {}
    if not sent and pack:
        findings.append("pack 无 market_sentiment")
    if sent.get("tier") == "frozen" and mf.get("allow_new_trend_trade") == "yes":
        findings.append("sentiment frozen 与 allow=yes 冲突")
    status: DimensionStatus = "ok" if not findings else "warn"
    if any("冲突" in f for f in findings):
        status = "gap"
    return {"id": MARKET_SENTIMENT, "status": status, "findings": findings}


def assess_event_quality_gate(
    trace: dict[str, Any], pack: dict[str, Any] | None
) -> dict[str, Any]:
    findings: list[str] = []
    qg = ((pack or {}).get("slots") or {}).get("quality_gate") or {}
    er = ((pack or {}).get("slots") or {}).get("event_risk") or {}
    for ts, rec in (qg.get("symbols") or {}).items():
        if rec.get("tier") == "block":
            dec = (trace.get("decisions") or {}).get(ts, {})
            entry = dec.get("entry") or {}
            if entry.get("type") not in ("wait", "none", "not_applicable"):
                findings.append(f"{ts}: quality block 但 entry 非 wait")
    for ts, rec in (er.get("symbols") or {}).items():
        if rec.get("block_entry"):
            dec = (trace.get("decisions") or {}).get(ts, {})
            entry = dec.get("entry") or {}
            if entry.get("type") not in ("wait", "none", "not_applicable"):
                findings.append(f"{ts}: event block 但 entry 非 wait")
    status: DimensionStatus = "ok" if not findings else "gap"
    return {"id": EVENT_QUALITY_GATE, "status": status, "findings": findings}


_ASSESSORS = {
    MF_PHASE_ENTRY: assess_mf_phase_entry,
    SECTOR_THEME_EXPOSURE: assess_sector_theme,
    THEME_LEADER_LIFECYCLE: assess_theme_leader_lifecycle,
    MARKET_SENTIMENT: assess_market_sentiment_dim,
    EVENT_QUALITY_GATE: assess_event_quality_gate,
    HOLDING_EXIT_DISCIPLINE: assess_holding_exit,
    WATCH_POOL_BOUNDARY: assess_watch_pool_boundary,
    EVIDENCE_TRACEABILITY: assess_evidence_traceability,
}


def assess_trace(trace: dict[str, Any], pack: dict[str, Any] | None = None) -> dict[str, Any]:
    """Full dimension assessment for one trace (+ optional pack)."""
    dimensions: list[dict[str, Any]] = []
    for dim_id in ALL_DIMENSION_IDS:
        fn = _ASSESSORS[dim_id]
        dimensions.append(fn(trace, pack))

    status_rank = {"gap": 3, "warn": 2, "ok": 1, "na": 0}
    worst = max((status_rank.get(d["status"], 0) for d in dimensions), default=0)
    overall = {3: "gap", 2: "warn", 1: "ok", 0: "na"}[worst]

    config_dims = {d["id"]: d for d in load_dimensions_config()}
    for d in dimensions:
        cfg = config_dims.get(d["id"], {})
        d["title"] = cfg.get("title", d["id"])
        d["review_questions"] = cfg.get("review_questions") or []
        d["suggested_improvements"] = _suggestions_for_dimension(d)

    return {
        "run_id": (trace.get("meta") or {}).get("run_id"),
        "as_of": (trace.get("meta") or {}).get("as_of"),
        "overall_status": overall,
        "dimensions": dimensions,
    }


def _suggestions_for_dimension(dim: dict[str, Any]) -> list[str]:
    """Actionable next_improvements lines prefixed with dimension id."""
    dim_id = dim["id"]
    status = dim["status"]
    if status == "ok":
        return [f"[{dim_id}] 维持当前做法，继续观察跨 run 一致性"]
    prefix = f"[{dim_id}]"
    out: list[str] = []
    for f in dim.get("findings") or []:
        out.append(f"{prefix} 修复：{f}")
    if not out:
        out.append(f"{prefix} 对照 review_questions 人工复盘后补充改进项")
    return out[:3]


def aggregate_dimension_trends(
    assessments: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Count status per dimension across multiple runs."""
    trends: dict[str, dict[str, Any]] = {}
    for a in assessments:
        for d in a.get("dimensions") or []:
            did = d["id"]
            trends.setdefault(did, {"ok": 0, "warn": 0, "gap": 0, "na": 0, "title": d.get("title", did)})
            st = d.get("status", "na")
            if st in trends[did]:
                trends[did][st] += 1
    return trends


def format_dimensions_markdown(
    *,
    assessments: list[dict[str, Any]] | None = None,
    single: dict[str, Any] | None = None,
) -> str:
    """Markdown section for review brief / report."""
    lines = ["## SKILL 八维演进评估", ""]
    config_dims = {d["id"]: d for d in load_dimensions_config()}

    if single:
        assessments = [single]

    if not assessments:
        lines.append("- （无评估数据；先 finalize 或提供 trace）")
        return "\n".join(lines)

    if len(assessments) > 1:
        trends = aggregate_dimension_trends(assessments)
        lines.append("### 跨 run 趋势（近期归档）")
        lines.append("")
        for did in ALL_DIMENSION_IDS:
            t = trends.get(did, {})
            title = t.get("title") or config_dims.get(did, {}).get("title", did)
            lines.append(
                f"- **{title}** (`{did}`): "
                f"ok={t.get('ok', 0)} warn={t.get('warn', 0)} gap={t.get('gap', 0)}"
            )
        lines.append("")

    target = assessments[0] if len(assessments) == 1 else assessments[0]
    lines.append(f"### 最近一次 · `{target.get('run_id')}` · overall={target.get('overall_status')}")
    lines.append("")
    for d in target.get("dimensions") or []:
        icon = {"ok": "✓", "warn": "!", "gap": "✗", "na": "—"}.get(d["status"], "?")
        lines.append(f"- {icon} **{d.get('title', d['id'])}** · `{d['status']}`")
        for f in d.get("findings") or []:
            lines.append(f"  - {f}")
        for q in (d.get("review_questions") or [])[:2]:
            lines.append(f"  - ？{q}")
        for s in d.get("suggested_improvements") or []:
            lines.append(f"  - → {s}")
    lines.append("")
    lines.append("### 写入 trace.review.next_improvements")
    lines.append("")
    lines.append("从各维 `suggested_improvements` 选取 3–5 条；Agent 可合并同类项。")
    lines.append("")
    for d in target.get("dimensions") or []:
        if d["status"] != "ok":
            for s in d.get("suggested_improvements") or []:
                lines.append(f"- {s}")
    return "\n".join(lines)


def save_assessment(assessment: dict[str, Any], run_id: str) -> Path:
    import json

    arch = RECOMMENDATIONS_DIR / run_id
    arch.mkdir(parents=True, exist_ok=True)
    path = arch / "skill_assessment.json"
    path.write_text(json.dumps(assessment, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_assessments_for_runs(run_ids: list[str]) -> list[dict[str, Any]]:
    import json

    out: list[dict[str, Any]] = []
    for rid in run_ids:
        p = RECOMMENDATIONS_DIR / rid / "skill_assessment.json"
        if p.exists():
            with p.open(encoding="utf-8") as f:
                out.append(json.load(f))
    return out
