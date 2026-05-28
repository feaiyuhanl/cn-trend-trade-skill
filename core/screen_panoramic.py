"""Panoramic watchlist screen reports with evidence chain."""

from __future__ import annotations

import json
from typing import Any


def _fetch_status_lines(pack_meta: dict[str, Any] | None) -> list[str]:
    meta = pack_meta or {}
    fs = meta.get("fetch_status") or {}
    msgs = meta.get("fetch_messages") or []
    lines: list[str] = []
    for key in ("tushare", "breadth", "sentiment", "quality_gate", "event_risk"):
        status = fs.get(key, "—")
        detail = next((m for m in msgs if key in m.lower() or "limit_list" in m), "")
        line = f"- **{key}**：{status}"
        if status in ("skip", "fail") and detail:
            line += f" — {detail}"
        lines.append(line)
    for m in msgs:
        if m and not any(m in ln for ln in lines):
            lines.append(f"- {m}")
    return lines or ["- （无 fetch_status）"]


def _format_theme_line(th: dict[str, Any]) -> str:
    leaders = th.get("leaders") or []
    lead_txt = "、".join(f"{L.get('name')}({L.get('pct_chg_1d', 0):+.1f}%)" for L in leaders[:2])
    inp = th.get("lifecycle_inputs") or {}
    down = inp.get("down_frac", th.get("down_frac", "—"))
    up = inp.get("up_frac", th.get("up_frac", "—"))
    lines = [
        f"- **{th.get('label', th.get('theme_id'))}** · **{th.get('lifecycle_stage')}** · "
        f"median_1d={th.get('median_pct_1d', '—')}% · 龙头：{lead_txt or '—'}",
        f"  - **周期规则**：{th.get('lifecycle_rule', '—')}",
        f"  - **样本统计**：n={th.get('sample_n', '—')} · 下跌占比={down} · 上涨占比={up} · "
        f"allow={th.get('allow_new_trend_trade', '—')}",
    ]
    if th.get("leader_limit_down"):
        lines.append("  - **龙头跌停**：是（退潮/降级参考）")
    return "\n".join(lines)


def _append_symbol_evidence(
    lines: list[str],
    r: dict[str, Any],
    *,
    trace: dict[str, Any],
    flat: dict[str, Any],
    verbose: bool,
) -> None:
    ts = r["ts_code"]
    sc = ((trace.get("decisions") or {}).get(ts) or {}).get("screen") or r
    lines.append(
        f"- **{ts}** {r.get('name', '')} · rank={r.get('safety_rank')} · "
        f"action={r.get('action')} · trap={r.get('trap_risk')} · vol={r.get('volume_context')} · "
        f"收={r.get('latest_close')}"
    )
    if r.get("theme") or r.get("theme_label") or sc.get("theme_id"):
        tl = r.get("theme_label") or sc.get("theme_label") or r.get("theme")
        lc = r.get("theme_lifecycle") or sc.get("theme_lifecycle")
        lcr = r.get("theme_lifecycle_rule") or sc.get("theme_lifecycle_rule")
        role = (r.get("theme_meta") or {}).get("role")
        role_txt = f" · role={role}" if role else ""
        lines.append(f"  - **题材**：{tl}{role_txt} · lifecycle={lc or '—'}")
        if lcr:
            lines.append(f"  - **题材规则**：{lcr}")
    trap_reason = r.get("trap_vol_reason") or sc.get("trap_vol_reason")
    if trap_reason:
        lines.append(f"  - **trap/量能判定**：{trap_reason}")
    action_rule = r.get("action_rule") or sc.get("action_rule")
    if action_rule:
        lines.append(f"  - **action 规则**：{action_rule}")
    note = r.get("note") or sc.get("rank_rationale") or r.get("weekly_position", "")
    if note:
        lines.append(f"  - **摘要**：{note}")
    if r.get("downgrade_reasons"):
        lines.append(f"  - **policy 降级**：{'; '.join(r['downgrade_reasons'])}")
    if r.get("position_band"):
        lines.append(
            f"  - **位置带**：{r.get('position_band')} · "
            f"2年分位={r.get('price_percentile_2y', '—')} · "
            f"52周高={r.get('distance_from_52w_high_pct', '—')}%"
        )
    breakdown = r.get("score_breakdown") or sc.get("score_breakdown") or []
    if breakdown and verbose:
        lines.append("  - **打分拆解**：")
        for item in breakdown:
            d = item.get("delta", 0)
            sign = f"{d:+d}" if isinstance(d, int) else str(d)
            lines.append(
                f"    - {sign} {item.get('reason', '')} → {item.get('score_after', '—')}"
            )
    elif breakdown:
        top = [x for x in breakdown if x.get("delta")][:4]
        tail = breakdown[-1] if breakdown else {}
        parts = [f"{x.get('delta', 0):+d} {x.get('reason', '')}" for x in top if x.get("delta")]
        if tail.get("reason"):
            parts.append(tail["reason"])
        lines.append(f"  - **打分要点**：{'；'.join(parts)}")
    facts = r.get("facts_used") or sc.get("facts_used") or []
    if facts:
        lines.append("  - **facts_used（值）**：")
        for fk in facts[:10]:
            lines.append(f"    - `{fk}` → {flat.get(fk, '—')}")
    op = r.get("observation_plan") or sc.get("observation_plan") or {}
    if op:
        lines.append(f"  - **观察框架**：失效 {op.get('invalid_below', '—')}")


def render_screen_panoramic_report(
    result: dict[str, Any],
    *,
    trace: dict[str, Any] | None = None,
    pack_meta: dict[str, Any] | None = None,
    pack: dict[str, Any] | None = None,
) -> str:
    meta = result.get("meta") or {}
    mf = result.get("market_filter") or {}
    sent = result.get("market_sentiment") or {}
    tc = result.get("theme_context") or {}
    trace = trace or {}
    mf_trace = trace.get("market_filter") or {}
    flat = ((pack or {}).get("fact_index") or {}).get("flat", {})

    lines = [
        "# 自选趋势观察池 · 全景报告",
        "",
        f"> **非买入推荐** · 行情交易日：`{meta.get('trade_date', '—')}` · "
        f"拉取时间：`{meta.get('as_of', '—')}` · Run：`{meta.get('run_id', '—')}`",
        f"> 排序引擎：`{meta.get('ranked_by', '—')}` · 证据链全文见 `screen-dossier.md`",
        "",
    ]
    if meta.get("data_stale"):
        lines.append("> **警告 · 外部行情尚未就绪**")
        for k in ("data_stale_headline", "data_stale_detail", "data_stale_retry"):
            if meta.get(k):
                lines.append(f"> {meta[k]}")
        lines.append("")

    lines.extend(["## 一、市场环境与大盘过滤", ""])
    lines.append(f"- **allow_new_trend_trade**：{mf.get('allow_new_trend_trade', '—')}")
    lines.append(f"- **confidence**：{mf_trace.get('confidence') or mf.get('confidence', '—')}")
    lines.append(f"- **regime_note**：{mf.get('regime_note') or '—'}")
    lines.append(f"- **reasoning_summary**：{mf_trace.get('reasoning_summary') or mf.get('reasoning_summary') or '—'}")
    lines.append("")

    retreats = mf.get("sector_retreats") or []
    if retreats:
        lines.append("### 板块退潮（自选样本）")
        for r in retreats:
            lines.append(
                f"- 主题 `{r['theme']}`：{r['n']} 只，中位跌幅 {r['median_drop']:.2f}%"
            )
        lines.append("")

    lines.extend(["## 二、市场情绪", ""])
    if sent:
        for k, label in (
            ("tier", "档位"),
            ("limit_up", "涨停"),
            ("limit_down", "跌停"),
            ("limit_ratio", "涨跌停比"),
            ("break_rate", "破板率"),
            ("max_lianban", "最高连板"),
            ("entry_policy", "entry_policy"),
        ):
            if sent.get(k) is not None:
                lines.append(f"- **{label}**：{sent[k]}")
        hot = sent.get("hot_themes") or []
        if hot:
            lines.append("- **热点题材**：" + "；".join(f"{h['theme']}({h.get('limit_up_count', '?')})" for h in hot[:5]))
    else:
        lines.append("- **状态**：未获取（见第六节数据源状态）")
        for g in result.get("gaps") or []:
            if "sentiment" in g.lower() or "market_sentiment" in g.lower():
                lines.append(f"- **缺口**：{g}")
    lines.append("")

    lines.extend(["## 三、题材共振（周期判定 · 可审计）", ""])
    themes = tc.get("themes") or []
    if themes:
        for th in sorted(themes, key=lambda x: -(x.get("strength_rank") or 0))[:8]:
            lines.append(_format_theme_line(th))
    else:
        lines.append("- （theme_context 无主题样本或未 enrich）")
    lines.append("")

    lines.extend(["## 四、推理链摘要（Lens steps）", ""])
    steps = trace.get("steps") or []
    if steps:
        for st in steps:
            lines.append(
                f"- **步骤 {st.get('step')} · {st.get('lens')}**（{st.get('confidence', '?')}）："
                f"{st.get('inference', '')}"
            )
            for obs in st.get("observations") or []:
                kind = obs.get("kind", "?")
                text = obs.get("text", "")
                fkeys = obs.get("fact_keys") or []
                fk = f" [`{', '.join(fkeys[:3])}`]" if fkeys else ""
                lines.append(f"  - [{kind}] {text}{fk}")
    else:
        lines.append("- （screen_trace.steps 为空；请确认 refresh_screen_trace_each_run）")
    lines.append("")

    lines.extend(["## 五、观察池分层（含打分/量能/题材证据）", "", "### watch_pool（仅观察，禁止追涨）", ""])
    for r in result.get("watch_pool") or []:
        _append_symbol_evidence(lines, r, trace=trace, flat=flat, verbose=True)

    lines.extend(["", "### watch_pullback", ""])
    for r in result.get("watch_pullback") or []:
        _append_symbol_evidence(lines, r, trace=trace, flat=flat, verbose=False)

    lines.extend(["", "### near_high_trim（不追涨）", ""])
    for r in result.get("near_high_trim") or []:
        _append_symbol_evidence(lines, r, trace=trace, flat=flat, verbose=False)

    rb = result.get("risk_blocked") or []
    if rb:
        lines.extend(["", "### risk_blocked / avoid（节选前 12）", ""])
        for r in rb[:12]:
            lines.append(
                f"- **{r['ts_code']}** {r.get('name', '')} · action={r.get('action')} · "
                f"flags={r.get('risk_flags') or []}"
            )
        if len(rb) > 12:
            lines.append(f"- … 另有 {len(rb) - 12} 只，见 `screen-dossier.md`")

    wp_finalize = result.get("watch_pool_full_analysis") or {}
    if wp_finalize.get("paths"):
        lines.extend(["", "### watch_pool 深度分析（full finalize）", ""])
        for ts, paths in (wp_finalize.get("paths") or {}).items():
            lines.append(f"- **{ts}**：report → `{paths.get('report', '—')}`")

    lines.extend(["", f"- **avoid 数量**：{result.get('avoid_count', 0)}", ""])

    trend = result.get("trend_top10") or {}
    stocks = trend.get("stocks") or []
    if stocks:
        lines.extend(
            [
                "",
                f"## 五·五、趋势分 TOP{trend.get('top_n', 10)}（{trend.get('scope', '—')} · 非观察池推荐）",
                "",
                f"> {trend.get('note', '')}",
                "",
                "| # | 代码 | 名称 | 分数 | 位置带 | 52周高% | 2年分位 | 在自选 | 在观察池 |",
                "|---|------|------|------|--------|---------|---------|--------|----------|",
            ]
        )
        for s in stocks:
            lines.append(
                f"| {s.get('rank')} | {s.get('ts_code')} | {s.get('name', '')} | "
                f"{s.get('safety_rank')} | {s.get('position_band', '—')} | "
                f"{s.get('distance_from_52w_high_pct', '—')} | "
                f"{s.get('price_percentile_2y', '—')} | "
                f"{'是' if s.get('in_watchlist') else '否'} | "
                f"{'是' if s.get('in_watch_pool') else '否'} |"
            )
        lines.append("")

    lines.extend(["## 六、数据源状态", ""])
    lines.extend(_fetch_status_lines(pack_meta or meta))
    lines.extend(["", "## 七、数据缺口 gaps", ""])
    for g in result.get("gaps") or []:
        lines.append(f"- {g}")
    if trace.get("gaps"):
        for g in trace["gaps"]:
            if g not in (result.get("gaps") or []):
                lines.append(f"- {g}")
    lines.append("")
    lines.append("免责声明：见项目 DISCLAIMER.md。")
    return "\n".join(lines)


def _render_dossier_symbol_block(
    lines: list[str],
    r: dict[str, Any],
    *,
    trace: dict[str, Any],
    flat: dict[str, Any],
) -> None:
    ts = r["ts_code"]
    sc = ((trace.get("decisions") or {}).get(ts) or {}).get("screen") or {}
    lines.append(f"### {ts} {r.get('name', '')}")
    lines.append(
        f"- action={r.get('action')} safety_rank={r.get('safety_rank')} "
        f"trap={r.get('trap_risk')} vol={r.get('volume_context')}"
    )
    if r.get("downgrade_reasons"):
        lines.append(f"- policy_downgrade: {'; '.join(r['downgrade_reasons'])}")
    if sc.get("trap_vol_reason") or r.get("trap_vol_reason"):
        lines.append(f"- trap_vol_reason: {r.get('trap_vol_reason') or sc.get('trap_vol_reason')}")
    if sc.get("action_rule") or r.get("action_rule"):
        lines.append(f"- action_rule: {r.get('action_rule') or sc.get('action_rule')}")
    if r.get("theme_lifecycle_rule") or sc.get("theme_lifecycle_rule"):
        lines.append(
            f"- theme: {r.get('theme_label') or r.get('theme')} "
            f"lifecycle={r.get('theme_lifecycle') or sc.get('theme_lifecycle')}"
        )
        lines.append(f"- theme_lifecycle_rule: {r.get('theme_lifecycle_rule') or sc.get('theme_lifecycle_rule')}")
    lines.append(f"- rank_rationale: {sc.get('rank_rationale') or r.get('note', '')}")
    breakdown = r.get("score_breakdown") or sc.get("score_breakdown") or []
    if breakdown:
        lines.append("- score_breakdown:")
        for item in breakdown:
            d = item.get("delta", 0)
            sign = f"{d:+d}" if isinstance(d, int) else str(d)
            lines.append(f"  - {sign} {item.get('reason', '')} → {item.get('score_after', '—')}")
    facts = r.get("facts_used") or sc.get("facts_used") or []
    for fk in facts:
        lines.append(f"- `{fk}` → {flat.get(fk, '—')}")
    op = sc.get("observation_plan") or r.get("observation_plan") or {}
    if op:
        lines.append(f"- observation_plan: {json.dumps(op, ensure_ascii=False)}")
    lines.append("")


def render_screen_dossier(
    result: dict[str, Any],
    *,
    trace: dict[str, Any],
    pack: dict[str, Any],
) -> str:
    flat = (pack.get("fact_index") or {}).get("flat", {})
    lines = [
        "# 自选观察池 · 证据链 dossier",
        "",
        f"> Run `{result.get('meta', {}).get('run_id', '—')}` · trade_date `{result.get('meta', {}).get('trade_date', '—')}`",
        "> 全量标的按 action 分层；打分/量能/题材规则见各节",
        "",
        "## Lens 步骤（完整 observations）",
        "",
    ]
    for st in trace.get("steps") or []:
        lines.append(f"### Step {st.get('step')} · {st.get('lens')}")
        lines.append(f"- inference: {st.get('inference', '')}")
        lines.append(f"- evidence_ids: {st.get('evidence_ids') or []}")
        for obs in st.get("observations") or []:
            lines.append(f"- [{obs.get('kind')}] {obs.get('text')}")
            if obs.get("fact_keys"):
                for fk in obs["fact_keys"]:
                    val = flat.get(fk, "—")
                    lines.append(f"  - `{fk}` → {val}")
        lines.append("")

    tc = result.get("theme_context") or (pack.get("slots") or {}).get("theme_context") or {}
    themes = tc.get("themes") or []
    if themes:
        lines.extend(["## 题材周期证据（theme_context）", ""])
        for th in sorted(themes, key=lambda x: -(x.get("strength_rank") or 0)):
            lines.append(_format_theme_line(th))
        lines.append("")

    all_rows = result.get("all_ranked") or []
    tiers: list[tuple[str, list[dict[str, Any]]]] = [
        ("watch_pool", result.get("watch_pool") or []),
        ("watch_pullback", result.get("watch_pullback") or []),
        ("near_high_trim", result.get("near_high_trim") or []),
    ]
    if all_rows:
        seen = {r["ts_code"] for r in result.get("watch_pool", []) + result.get("watch_pullback", []) + result.get("near_high_trim", [])}
        other = [r for r in all_rows if r["ts_code"] not in seen and r.get("action") in ("wait", "avoid", "holding")]
        tiers.append(("wait_avoid_holding", other))

    for title, rows in tiers:
        if not rows:
            continue
        lines.append(f"## {title}（{len(rows)} 只）")
        lines.append("")
        for r in rows:
            _render_dossier_symbol_block(lines, r, trace=trace, flat=flat)

    return "\n".join(lines)


def render_screen_audit_sheet(result: dict[str, Any], *, pack: dict[str, Any]) -> str:
    from core.trace_resolve import build_sources_snapshot

    meta = pack.get("meta") or {}
    snap = build_sources_snapshot(pack)
    lines = [
        "# 自选观察池 · 事实审计",
        "",
        "## fetch_status",
        "",
    ]
    lines.extend(_fetch_status_lines(meta))
    lines.extend(["", "## sources_snapshot", ""])
    for s in snap:
        lines.append(f"- **{s.get('id')}**: {s.get('status')} — {s.get('message', '')}")
    lines.extend(["", "## screened vs requested", ""])
    m = result.get("meta") or {}
    lines.append(f"- screened: {m.get('screened')} / requested: {m.get('symbols_requested', m.get('screened'))}")
    lines.append(f"- ranked_by: {m.get('ranked_by', '—')}")
    lines.append("- evidence_fields: score_breakdown, trap_vol_reason, action_rule, theme_lifecycle_rule")
    return "\n".join(lines)
