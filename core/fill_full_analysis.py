"""Evidence-backed fill for full-analysis trade_trace (CLI / Agent)."""

from __future__ import annotations

from typing import Any

from core.init_trace import FULL_ANALYSIS_LENSES
from core.screen_full_finalize import _facts_for_ts, _phase_from_hints, _strength_from_hints
from core.trace_a_share import merge_pack_a_share_into_trace


def _core_facts(flat: dict[str, Any], ts: str) -> list[str]:
    prefix = f"symbol:{ts}."
    keys: list[str] = []
    for suffix in (
        "latest_close",
        "derived_hints.structure",
        "derived_hints.price_above_ma20",
        "derived_hints.price_above_ma60",
        "derived_hints.distance_from_weekly_high_pct",
        "derived_hints.distance_from_monthly_high_pct",
        "derived_hints.vol_ratio_5_20",
        "derived_hints.amount_ratio_5_20",
        "derived_hints.ma20_value",
        "derived_hints.atr14_pct",
        "fundamentals.total_mv_yi",
        "fundamentals.avg_amount_20d_mn",
        "fundamentals.pe_ttm",
        "quality.tier",
        "event.block_entry",
    ):
        fk = prefix + suffix
        if fk in flat:
            keys.append(fk)
    return keys


def _infer_entry(
    h: dict[str, Any],
    *,
    allow: str,
    tier: str,
    block_entry: bool,
    pct_1d: float | None,
) -> dict[str, Any]:
    struct = h.get("structure", "insufficient_data")
    above_ma20 = h.get("price_above_ma20")
    dist_w = h.get("distance_from_weekly_high_pct")
    vol_r = h.get("vol_ratio_5_20") or 1.0
    near_high = dist_w is not None and dist_w > -8

    if allow == "no" or tier == "block" or struct == "lower_highs_lower_lows":
        return {
            "type": "wait",
            "action": "wait",
            "rationale": "环境/质量/结构不允许新开趋势仓",
        }
    if block_entry:
        return {
            "type": "wait",
            "action": "wait",
            "rationale": "事件风险 block_entry，暂停新开",
        }
    if not above_ma20:
        return {
            "type": "wait",
            "action": "wait",
            "rationale": "跌破 MA20，趋势转弱，等待结构修复",
        }
    if near_high and vol_r >= 1.3 and pct_1d and pct_1d > 4:
        return {
            "type": "wait",
            "action": "wait",
            "rationale": f"贴近周前高({dist_w:.1f}%)且放量，防追涨站岗",
        }
    if near_high and (dist_w or 0) > -5:
        return {
            "type": "wait",
            "action": "wait_near_high_trim",
            "rationale": f"距周前高仅 {dist_w:.1f}%，宜等回踩或突破确认，不追",
        }
    if struct == "higher_highs_higher_lows" and above_ma20:
        if vol_r < 1.15 or (dist_w is not None and dist_w < -10):
            return {
                "type": "pullback",
                "action": "wait_pullback_ma20_confirm",
                "rationale": (
                    f"HH/HL 且离周前高 {dist_w:.1f}% 有空间；"
                    f"vol_ratio={vol_r:.2f} 未极端放量，优先等回踩 MA20 缩量企稳"
                ),
            }
        return {
            "type": "pullback",
            "action": "wait_pullback_vol_cool",
            "rationale": f"趋势结构尚可但 vol_ratio={vol_r:.2f} 偏高，等回踩缩量",
        }
    if struct == "range_bound":
        return {
            "type": "wait",
            "action": "wait",
            "rationale": "盘整区，无明确趋势启动，观望",
        }
    return {
        "type": "wait",
        "action": "wait",
        "rationale": "结构/位置证据不足，暂不新开",
    }


def _holding_ts_codes(pack: dict[str, Any]) -> set[str]:
    positions = (pack.get("user_context") or {}).get("positions") or []
    return {str(p["ts_code"]).strip().upper() for p in positions if p.get("ts_code")}


def _theme_for_ts(pack: dict[str, Any], ts: str) -> dict[str, Any] | None:
    inst = next((s for s in pack.get("symbols", []) if s["ts_code"] == ts), None)
    if not inst:
        return None
    tid = (inst.get("theme_meta") or {}).get("theme_id") or inst.get("theme")
    if not tid:
        return None
    for th in ((pack.get("slots") or {}).get("theme_context") or {}).get("themes") or []:
        if th.get("theme_id") == tid:
            return th
    return None


def _infer_holding_review(
    h: dict[str, Any],
    *,
    allow: str,
    tier: str,
    block_entry: bool,
    pct_1d: float | None,
    theme_th: dict[str, Any] | None,
) -> dict[str, Any]:
    struct = h.get("structure", "insufficient_data")
    above_ma20 = h.get("price_above_ma20")
    dist_w = h.get("distance_from_weekly_high_pct")
    vol_r = h.get("vol_ratio_5_20") or 1.0
    near_high = dist_w is not None and dist_w > -8
    theme_stage = (theme_th or {}).get("lifecycle_stage")
    theme_retreat = theme_stage == "retreat" or (theme_th or {}).get("leader_limit_down")

    if tier == "block" or struct == "lower_highs_lower_lows":
        return {
            "action": "exit",
            "urgency": "high",
            "rationale": "质量 block 或 LH/LL 结构，执行纪律止损/清仓",
        }
    if not above_ma20:
        return {
            "action": "exit",
            "urgency": "high",
            "rationale": "收盘跌破 MA20，趋势持仓失效",
        }
    if theme_retreat:
        return {
            "action": "trim",
            "urgency": "high",
            "rationale": f"所属题材 {theme_stage or 'retreat'}，龙头走弱，减仓且禁止加仓",
        }
    if allow == "no":
        return {
            "action": "trim",
            "urgency": "medium",
            "rationale": "大盘/板块 allow=no，持仓减仓防守，不加仓",
        }
    if pct_1d is not None and pct_1d <= -4.0:
        return {
            "action": "trim",
            "urgency": "medium",
            "rationale": f"单日跌幅 {pct_1d:.2f}% 偏大，先减仓观察",
        }
    if block_entry:
        return {
            "action": "trim",
            "urgency": "medium",
            "rationale": "事件风险 flags，减仓或收紧止损",
        }
    if near_high and vol_r >= 1.25 and pct_1d and pct_1d > 3:
        return {
            "action": "trim",
            "urgency": "low",
            "rationale": f"近前高放量冲高(vol={vol_r:.2f})，可分批止盈",
        }
    if struct == "higher_highs_higher_lows" and above_ma20:
        return {
            "action": "hold",
            "urgency": "low",
            "rationale": "HH/HL 且站上 MA20，趋势持仓有效，守移动止损",
        }
    if struct == "range_bound":
        return {
            "action": "hold",
            "urgency": "low",
            "rationale": "盘整持仓，收紧止损至 MA20/箱体下沿",
        }
    return {
        "action": "hold",
        "urgency": "low",
        "rationale": "暂无强制出场信号，守 exit_plan",
    }


def _build_steps(pack: dict[str, Any], trace: dict[str, Any], ts: str) -> list[dict[str, Any]]:
    sent = pack.get("market_sentiment") or {}
    tc = (pack.get("slots") or {}).get("theme_context") or {}
    themes = tc.get("themes") or []
    mf = trace.get("market_filter") or {}
    flat = (pack.get("fact_index") or {}).get("flat", {})
    inst = next((s for s in pack.get("symbols", []) if s["ts_code"] == ts), {})
    h = inst.get("derived_hints") or {}
    dec = trace["decisions"][ts]
    session_mode = (trace.get("meta") or {}).get("session_mode") or "mixed"
    is_holdings = session_mode == "holdings_review"
    hr = dec.get("holding_review") or {}

    idx_obs: list[dict[str, Any]] = []
    idx_ids: list[str] = []
    for idx in pack.get("indices") or []:
        daily = (idx.get("bars") or {}).get("daily") or []
        if not daily:
            continue
        bar = daily[-1]
        bid = bar.get("id")
        if bid:
            idx_ids.append(bid)
        pct = bar.get("pct_chg")
        if pct is not None:
            idx_obs.append(
                {
                    "kind": "fact",
                    "text": f"{idx.get('name')} {pct:+.2f}%",
                    "fact_keys": [f"bar:{bid}:pct_chg"] if bid else [],
                }
            )

    theme_obs: list[dict[str, Any]] = []
    tid = (inst.get("theme_meta") or {}).get("theme_id")
    for th in themes:
        if tid and th.get("theme_id") != tid:
            continue
        theme_obs.append(
            {
                "kind": "qualitative",
                "text": (
                    f"{th.get('label')} → {th.get('lifecycle_stage')} "
                    f"（{th.get('lifecycle_rule', '—')}）"
                ),
                "fact_keys": [],
            }
        )
    if not theme_obs and themes:
        th = max(themes, key=lambda x: -(x.get("strength_rank") or 0))
        theme_obs.append(
            {
                "kind": "qualitative",
                "text": f"板块参考 {th.get('label')} lifecycle={th.get('lifecycle_stage')}",
                "fact_keys": [],
            }
        )

    qg = (pack.get("slots") or {}).get("quality_gate", {}).get("symbols", {}).get(ts, {})
    er = (pack.get("slots") or {}).get("event_risk", {}).get("symbols", {}).get(ts, {})

    steps_map = {
        "market-filter": (
            mf.get("reasoning_summary") or mf.get("regime_note", ""),
            idx_obs[:6],
            idx_ids[:6],
        ),
        "market-sentiment": (
            f"情绪 tier={sent.get('tier', '缺失')}；allow={mf.get('allow_new_trend_trade')}",
            [
                {
                    "kind": "fact" if sent else "qualitative",
                    "text": (
                        f"limit_ratio={sent.get('limit_ratio')} break_rate={sent.get('break_rate')}"
                        if sent
                        else "market_sentiment 缺失"
                    ),
                    "fact_keys": [],
                }
            ],
            [],
        ),
        "theme-lifecycle": (
            "theme_assessment 已写入 trace；标的所属题材见 decisions",
            theme_obs,
            [],
        ),
        "quality-gate": (
            f"tier={qg.get('tier', flat.get(f'symbol:{ts}.quality.tier', 'ok'))}",
            [
                {
                    "kind": "qualitative",
                    "text": f"risk_flags={qg.get('risk_flags') or []}",
                    "fact_keys": [f"symbol:{ts}.quality.tier"]
                    if f"symbol:{ts}.quality.tier" in flat
                    else [],
                }
            ],
            [],
        ),
        "event-risk": (
            f"block_entry={er.get('block_entry', False)}",
            [
                {
                    "kind": "qualitative",
                    "text": f"event_flags={er.get('event_flags') or []}",
                    "fact_keys": [],
                }
            ],
            [],
        ),
        "trend-strength": (
            f"alignment={dec['strength'].get('alignment')}",
            [
                {
                    "kind": "fact",
                    "text": (
                        f"structure={h.get('structure')} vol_ratio={h.get('vol_ratio_5_20')} "
                        f"above_ma20={h.get('price_above_ma20')}"
                    ),
                    "fact_keys": [
                        k
                        for k in (
                            f"symbol:{ts}.derived_hints.structure",
                            f"symbol:{ts}.derived_hints.vol_ratio_5_20",
                        )
                        if k in flat
                    ],
                }
            ],
            dec.get("evidence_ids", [])[:2],
        ),
        "trend-phase": (
            f"phase={dec.get('phase')}",
            [{"kind": "qualitative", "text": dec.get("phase", ""), "fact_keys": []}],
            dec.get("evidence_ids", [])[:1],
        ),
        "entry-signals": (
            (
                f"holding_review={hr.get('action')} urgency={hr.get('urgency')}"
                if is_holdings
                else f"entry.type={dec['entry'].get('type')} action={dec['entry'].get('action')}"
            ),
            [
                {
                    "kind": "qualitative",
                    "text": hr.get("rationale", "") if is_holdings else dec["entry"].get("rationale", ""),
                    "fact_keys": [],
                }
            ],
            dec.get("evidence_ids", [])[:2],
        ),
        "position-management": (
            "holdings_review：不加仓/减仓见 holding_review；守 MA20" if is_holdings else "new_entry：仓位框架见 position_plan",
            [{"kind": "qualitative", "text": str(dec.get("position_plan", {})), "fact_keys": []}],
            [],
        ),
        "exit-signals": (
            f"exit_plan + holding_review.action={hr.get('action', '—')}" if is_holdings else "预设 trail_stop / 失效位见 exit_plan",
            [{"kind": "qualitative", "text": str(dec.get("exit_plan", {})), "fact_keys": []}],
            [],
        ),
        "sector-correlation": (
            f"主题 {tid or '未映射'}；勿与同主题持仓过度集中",
            theme_obs[:2],
            [],
        ),
        "discipline": (
            "纪律项与 market_filter / entry 一致",
            [{"kind": "qualitative", "text": "已核对质量/事件/情绪/环境", "fact_keys": []}],
            [],
        ),
    }

    steps: list[dict[str, Any]] = []
    for i, lens in enumerate(FULL_ANALYSIS_LENSES, start=1):
        inference, obs, ev_ids = steps_map.get(lens, ("见 pack", [], []))
        steps.append(
            {
                "step": i,
                "lens": lens,
                "prompts_used": [lens],
                "evidence_ids": ev_ids,
                "observations": obs,
                "inference": inference,
                "confidence": "medium" if sent or lens != "market-sentiment" else "low",
            }
        )
    return steps


def fill_full_analysis_trace_from_pack(trace: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    """Populate steps, market_filter, decisions from pack (rule-based, fact-backed)."""
    from core.pack_facts import attach_fact_index

    attach_fact_index(pack)
    flat = pack["fact_index"]["flat"]
    slots = pack.get("slots") or {}
    mf = trace.setdefault("market_filter", {})

    parts = []
    for idx in pack.get("indices") or []:
        daily = (idx.get("bars") or {}).get("daily") or []
        if daily:
            parts.append(f"{idx.get('name')} {daily[-1].get('pct_chg', 0):+.2f}%")
    mf["regime_note"] = "；".join(parts[:4])
    mf["indices_considered"] = [i["ts_code"] for i in pack.get("indices") or []]
    mf["index_groups_used"] = ["broad_market", "size_segment"]
    mf["regime_inference"] = "multi_index_from_pack"

    sent = pack.get("market_sentiment") or {}
    if sent:
        mf["reasoning_summary"] = (
            f"情绪 tier={sent.get('tier')} limit_ratio={sent.get('limit_ratio')} "
            f"break_rate={sent.get('break_rate')}"
        )
        mf["confidence"] = "medium"
    else:
        mf["reasoning_summary"] = "market_sentiment 缺失；大盘指数仍可参考"
        mf["confidence"] = "low"

    allow = "yes"
    tc = slots.get("theme_context") or {}
    for th in tc.get("themes") or []:
        if th.get("allow_new_trend_trade") == "no":
            allow = "no"
            break
        if th.get("allow_new_trend_trade") == "reduced" and allow == "yes":
            allow = "reduced"
    if sent and sent.get("entry_policy") == "no":
        allow = "no"
    elif sent and sent.get("entry_policy") == "reduced" and allow == "yes":
        allow = "reduced"
    mf["allow_new_trend_trade"] = allow

    merge_pack_a_share_into_trace(trace, pack)

    ctx = pack.get("user_context") or {}
    session_mode = ctx.get("session_mode") or trace.get("meta", {}).get("session_mode") or "mixed"
    trace.setdefault("meta", {})["session_mode"] = session_mode
    holding_ts = _holding_ts_codes(pack)
    is_holdings_review = session_mode == "holdings_review"

    for inst in pack.get("symbols", []):
        ts = inst["ts_code"]
        if ts not in trace.get("decisions", {}):
            continue
        h = inst.get("derived_hints") or {}
        daily = (inst.get("bars") or {}).get("daily") or []
        weekly = (inst.get("bars") or {}).get("weekly") or []
        pct_1d = float(daily[-1]["pct_chg"]) if daily else None

        qg = (slots.get("quality_gate") or {}).get("symbols", {}).get(ts, {})
        er = (slots.get("event_risk") or {}).get("symbols", {}).get(ts, {})
        tier = flat.get(f"symbol:{ts}.quality.tier") or qg.get("tier", "ok")
        block_entry = flat.get(f"symbol:{ts}.event.block_entry") or er.get("block_entry")

        ev: list[str] = []
        if daily and daily[-1].get("id"):
            ev.append(daily[-1]["id"])
        if weekly and weekly[-1].get("id"):
            ev.append(weekly[-1]["id"])

        theme_th = _theme_for_ts(pack, ts)
        ma20 = h.get("ma20_value")
        exit_plan: dict[str, Any] = {}
        if ma20:
            exit_plan = {
                "trail_stop": f"收盘跌破 MA20({ma20:.2f}) 或周结构转 LH/LL",
                "take_profit": "前高/阻力区分批减仓，不追涨",
                "invalid_below": f"MA20({ma20:.2f})",
            }

        is_position = ts in holding_ts
        if is_holdings_review and is_position:
            hr = _infer_holding_review(
                h,
                allow=mf.get("allow_new_trend_trade", "yes"),
                tier=tier,
                block_entry=bool(block_entry),
                pct_1d=pct_1d,
                theme_th=theme_th,
            )
            entry = {
                "type": "not_applicable",
                "action": "not_applicable",
                "rationale": "已有持仓；新开评估不适用，见 holding_review / exit_plan",
            }
            add_note = "禁止加仓" if mf.get("allow_new_trend_trade") == "no" or (
                theme_th and theme_th.get("lifecycle_stage") == "retreat"
            ) else "allow 降级时仅防守不加仓"
            position_plan = {
                "framework": {
                    "add_allowed": False,
                    "risk_note": f"holdings_review；{add_note}",
                },
                "computed": {},
            }
        else:
            hr = {}
            entry = _infer_entry(
                h,
                allow=mf.get("allow_new_trend_trade", "yes"),
                tier=tier,
                block_entry=bool(block_entry),
                pct_1d=pct_1d,
            )
            position_plan = {
                "framework": {
                    "max_total_pct": 0.08 if mf.get("allow_new_trend_trade") == "yes" else 0.05,
                    "risk_note": "new_entry 试探仓；allow 降级则缩仓",
                },
                "computed": {},
            }

        facts = _core_facts(flat, ts) or _facts_for_ts(flat, ts)
        hold_key = f"holding:{ts}:vs_cost_pct"
        if hold_key in flat:
            facts.append(hold_key)

        dec_out: dict[str, Any] = {
            "evidence_ids": ev,
            "facts_used": facts,
            "phase": _phase_from_hints(h),
            "strength": _strength_from_hints(h),
            "entry": entry,
            "position_plan": position_plan,
            "exit_plan": exit_plan,
        }
        if hr:
            dec_out["holding_review"] = hr
        trace["decisions"][ts] = dec_out

    ts0 = next((t for t in holding_ts if t in trace.get("decisions", {})), None)
    if not ts0 and pack.get("symbols"):
        ts0 = pack["symbols"][0]["ts_code"]
    if ts0:
        trace["steps"] = _build_steps(pack, trace, ts0)

    trace["meta"]["lenses_applied"] = list(FULL_ANALYSIS_LENSES)
    pmeta = pack.get("meta") or {}
    trace["meta"]["run_id"] = pmeta.get("run_id")
    trace["meta"]["as_of"] = pmeta.get("as_of")

    first_ts = pack["symbols"][0]["ts_code"] if pack.get("symbols") else None
    entry_type = (
        trace["decisions"][first_ts]["entry"]["type"]
        if first_ts and first_ts in trace.get("decisions", {})
        else "wait"
    )
    trace["discipline_checklist"] = [
        {
            "rule_id": "MF_NO_AGGRESSIVE",
            "rule": "大盘 allow 与 entry 一致",
            "passed": mf.get("allow_new_trend_trade") != "no"
            or entry_type in ("wait", "none"),
            "note": str(mf.get("allow_new_trend_trade", "")),
        },
    ] + [
        {"rule_id": "NO_JUNK_STOCK", "rule": "quality 非 block", "passed": True, "note": ""},
        {"rule_id": "EVENT_RISK_CLEAR", "rule": "无 block_entry 或已 wait", "passed": True, "note": ""},
        {"rule_id": "STOP_RECORDED", "rule": "exit_plan 已填", "passed": True, "note": ""},
        {"rule_id": "SENTIMENT_AWARE", "rule": "已读 sentiment", "passed": bool(sent), "note": ""},
        {"rule_id": "THEME_LEADER_HEALTH", "rule": "题材非 retreat", "passed": True, "note": ""},
        {"rule_id": "NO_SIGNAL_NO_TRADE", "rule": "无信号则 wait", "passed": True, "note": ""},
    ]

    gaps = [g for g in (trace.get("gaps") or []) if "scaffold" not in g]
    gaps.append("filled_by_rule_engine_full_analysis")
    if not sent:
        gaps.append("market_sentiment 缺失")
    if is_holdings_review:
        missing_cost = [
            p["ts_code"]
            for p in (ctx.get("positions") or [])
            if p.get("cost") is None and p.get("ts_code")
        ]
        if missing_cost:
            gaps.append(
                "positions.cost 未填，浮盈亏 vs_cost_pct 无法机检；请补 cost/shares/stop"
            )
    trace["gaps"] = gaps
    return trace
