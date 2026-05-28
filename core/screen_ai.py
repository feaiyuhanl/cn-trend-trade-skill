"""Evidence-backed auto-fill for watchlist screen trace (panoramic mode)."""

from __future__ import annotations

from typing import Any

from core.init_trace import WATCHLIST_SCREEN_LENSES
from core.position_filter import (
    blocks_watch_pool,
    classify_position_band,
    is_near_high,
    load_position_config,
)


def _core_facts(flat: dict[str, Any], ts: str) -> list[str]:
    prefix = f"symbol:{ts}."
    keys: list[str] = []
    for key in (
        "derived_hints.structure",
        "derived_hints.price_above_ma20",
        "derived_hints.distance_from_weekly_high_pct",
        "derived_hints.distance_from_52w_high_pct",
        "derived_hints.price_percentile_2y",
        "derived_hints.vol_ratio_5_20",
        "derived_hints.amount_ratio_5_20",
        "fundamentals.total_mv_yi",
        "fundamentals.avg_amount_20d_mn",
        "fundamentals.pe_ttm",
        "quality.tier",
    ):
        fk = prefix + key
        if fk in flat:
            keys.append(fk)
    return keys


def _add_score(score: int, breakdown: list[dict[str, Any]], delta: int, reason: str) -> int:
    breakdown.append({"delta": delta, "reason": reason, "score_after": score + delta})
    return score + delta


def _assess_symbol(inst: dict[str, Any], flat: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    ts = inst["ts_code"]
    h = inst.get("derived_hints") or {}
    pos_cfg = load_position_config()
    daily = (inst.get("bars") or {}).get("daily") or []
    weekly = (inst.get("bars") or {}).get("weekly") or []
    monthly = (inst.get("bars") or {}).get("monthly") or []
    pct_1d = float(daily[-1]["pct_chg"]) if daily else None

    qg = (slots.get("quality_gate") or {}).get("symbols") or {}
    er = (slots.get("event_risk") or {}).get("symbols") or {}
    tier = flat.get(f"symbol:{ts}.quality.tier") or (qg.get(ts) or {}).get("tier", "ok")
    block_entry = flat.get(f"symbol:{ts}.event.block_entry") or (er.get(ts) or {}).get("block_entry")

    struct = h.get("structure", "insufficient_data")
    above_ma20 = h.get("price_above_ma20")
    above_ma60 = h.get("price_above_ma60")
    dist_w = h.get("distance_from_weekly_high_pct")
    dist_m = h.get("distance_from_monthly_high_pct")
    dist_52 = h.get("distance_from_52w_high_pct")
    pct_2y = h.get("price_percentile_2y")
    vol_r = h.get("vol_ratio_5_20") or 1.0
    amt_r = h.get("amount_ratio_5_20") or 1.0
    ma20_slope = h.get("ma20_slope_daily") or 0
    ma20_val = h.get("ma20_value")
    mv = flat.get(f"symbol:{ts}.fundamentals.total_mv_yi") or 0
    amt = flat.get(f"symbol:{ts}.fundamentals.avg_amount_20d_mn") or 0
    pe = flat.get(f"symbol:{ts}.fundamentals.pe_ttm")
    facts_used = _core_facts(flat, ts)
    position_band = classify_position_band(h, pos_cfg)

    near_high = is_near_high(h, pos_cfg)
    thr = pos_cfg.get("thresholds") or {}
    far_from_high = (dist_w is not None and dist_w < float(thr.get("far_from_high_weekly_pct", -20))) or (
        dist_m is not None and dist_m < float(thr.get("far_from_high_weekly_pct", -20))
    )

    trap = "medium"
    vol_ctx = "unclear"
    trap_rule = ""

    if struct == "lower_highs_lower_lows" or (above_ma20 is False and above_ma60 is False):
        trap = "high"
        vol_ctx = "distribution" if vol_r > 1.2 else "unclear"
        trap_rule = "LH/LL 或 MA20/MA60 下方 → trap=high"
    elif near_high and vol_r > 1.3 and struct != "higher_highs_higher_lows":
        trap = "high"
        vol_ctx = "top_chase"
        trap_rule = f"近前高(dist_w>{-8}%) 且 vol_ratio={vol_r:.2f}>1.3 且非 HH/HL → trap=high"
    elif near_high and vol_r > 1.2:
        trap = "medium"
        vol_ctx = "top_chase" if pct_1d and pct_1d > 3 else "distribution"
        trap_rule = f"近前高 + vol_ratio={vol_r:.2f}>1.2 → trap=medium, vol={vol_ctx}"
    elif struct == "higher_highs_higher_lows" and far_from_high and vol_r >= 1.0:
        trap = "low"
        vol_ctx = "bottom_accumulation" if amt_r > 1.1 else "healthy_pullback"
        trap_rule = f"HH/HL 离前高远 + vol_ratio={vol_r:.2f}≥1 → trap=low, vol={vol_ctx}"
    elif struct == "higher_highs_higher_lows" and above_ma20:
        trap = "low" if not near_high else "medium"
        vol_ctx = "healthy_pullback" if not near_high else "top_chase"
        trap_rule = f"HH/HL 站上 MA20, near_high={near_high} → trap={trap}, vol={vol_ctx}"
    elif struct == "range_bound":
        trap = "medium"
        vol_ctx = "unclear"
        trap_rule = "盘整区 → trap=medium"
    else:
        trap_rule = "默认 → trap=medium"

    wp: list[str] = []
    if dist_w is not None:
        wp.append(f"距周前高{dist_w:.1f}%")
    if dist_m is not None:
        wp.append(f"距月前高{dist_m:.1f}%")
    if dist_52 is not None:
        wp.append(f"距52周高{dist_52:.1f}%")
    if pct_2y is not None:
        wp.append(f"2年分位{pct_2y:.0f}%")
    wp.append(f"位置带={position_band}")
    if struct == "higher_highs_higher_lows":
        wp.append("HH/HL结构")
    elif struct == "lower_highs_lower_lows":
        wp.append("LH/LL走弱")
    elif struct == "range_bound":
        wp.append("盘整区")
    weekly_pos = "；".join(wp) if wp else "数据有限"

    breakdown: list[dict[str, Any]] = []
    score = 50
    breakdown.append({"delta": 0, "reason": "基准分 50", "score_after": 50})

    if struct == "higher_highs_higher_lows":
        score = _add_score(score, breakdown, 12, "结构 HH/HL +12")
    elif struct == "range_bound":
        score = _add_score(score, breakdown, 2, "盘整区 +2")
    else:
        score = _add_score(score, breakdown, -10, f"结构 {struct} -10")

    if above_ma20:
        score = _add_score(score, breakdown, 8, "站上 MA20 +8")
    else:
        score = _add_score(score, breakdown, -12, "跌破 MA20 -12")
    if above_ma60:
        score = _add_score(score, breakdown, 5, "站上 MA60 +5")
    if ma20_slope > 0:
        d = min(8, int(ma20_slope * 40))
        score = _add_score(score, breakdown, d, f"MA20 斜率 {ma20_slope:.3f} +{d}")
    if dist_w is not None:
        if dist_w < float(thr.get("far_from_high_weekly_pct", -20)):
            score = _add_score(score, breakdown, 8, f"距周前高 {dist_w:.1f}% 空间充足 +8")
        elif dist_w > float(thr.get("near_high_weekly_pct", -12)):
            score = _add_score(score, breakdown, -10, f"距周前高 {dist_w:.1f}% 过近 -10")
        elif dist_w > float(thr.get("far_from_high_weekly_pct", -20)):
            score = _add_score(score, breakdown, -5, f"距周前高 {dist_w:.1f}% 偏近 -5")
    if dist_52 is not None:
        if dist_52 > float(thr.get("near_high_52w_pct", -8)):
            score = _add_score(score, breakdown, -15, f"距52周高 {dist_52:.1f}% 过近 -15")
    band_cfg = pos_cfg.get("mid_low_band") or {}
    if position_band == "mid_low" and struct == "higher_highs_higher_lows":
        bonus = int(band_cfg.get("prefer_mid_low_bonus") or 10)
        score = _add_score(score, breakdown, bonus, f"中低位修复区 +{bonus}")
    elif position_band == "near_high":
        score = _add_score(score, breakdown, -8, "位置带 near_high -8")
    elif position_band == "mid_high":
        score = _add_score(score, breakdown, -5, "位置带 mid_high -5")
    if vol_r >= 1.2 and struct == "higher_highs_higher_lows" and not near_high:
        score = _add_score(score, breakdown, 5, f"放量未近高 vol_ratio={vol_r:.2f} +5")
    elif vol_r >= 1.5 and near_high:
        score = _add_score(score, breakdown, -8, f"近高放量 vol_ratio={vol_r:.2f} -8")
    if mv >= 200:
        score = _add_score(score, breakdown, 6, f"市值 {mv:.0f}亿 +6")
    elif mv >= 80:
        score = _add_score(score, breakdown, 3, f"市值 {mv:.0f}亿 +3")
    elif mv < 30:
        score = _add_score(score, breakdown, -5, f"市值 {mv:.0f}亿 偏小 -5")
    if amt >= 300:
        score = _add_score(score, breakdown, 5, f"20d均额 {amt:.0f}mn +5")
    elif amt >= 100:
        score = _add_score(score, breakdown, 2, f"20d均额 {amt:.0f}mn +2")
    elif amt < 30:
        score = _add_score(score, breakdown, -4, f"20d均额 {amt:.0f}mn 偏低 -4")
    if pe is not None:
        if pe < 0 or pe > 150:
            score = _add_score(score, breakdown, -8, f"PE {pe:.0f} 极端 -8")
        elif pe > 80:
            score = _add_score(score, breakdown, -4, f"PE {pe:.0f} 偏高 -4")
    if tier == "block":
        score = min(score, 5)
        breakdown.append({"delta": 0, "reason": "quality tier=block → 分数封顶 5", "score_after": score})
    elif tier == "warn":
        score = _add_score(score, breakdown, -10, "quality tier=warn -10")
    if block_entry:
        score = _add_score(score, breakdown, -15, "event block_entry -15")
    if trap == "high":
        score = _add_score(score, breakdown, -12, "trap=high -12")
    elif trap == "low":
        score = _add_score(score, breakdown, 5, "trap=low +5")
    score = max(0, min(100, int(score)))
    breakdown.append({"delta": 0, "reason": f"裁剪至 [0,100] → safety_rank={score}", "score_after": score})

    action = "avoid"
    action_rule = ""
    if tier == "block":
        action = "avoid"
        action_rule = "quality tier=block → avoid"
    elif trap == "high":
        action = "wait"
        action_rule = "trap=high → wait"
    elif not above_ma20:
        action = "avoid"
        action_rule = "跌破 MA20 → avoid"
    elif near_high and (dist_w or 0) > float(thr.get("near_high_52w_pct", -8)) and pct_1d and pct_1d > 5:
        action = "near_high_trim"
        action_rule = f"近前高且日涨 {pct_1d:.1f}%>5% → near_high_trim"
    elif struct == "lower_highs_lower_lows":
        action = "avoid"
        action_rule = "LH/LL → avoid"
    elif score >= 62 and trap == "low" and above_ma20:
        pos_block, pos_reason = blocks_watch_pool(
            h, struct=struct, above_ma20=above_ma20, cfg=pos_cfg
        )
        if pos_block:
            action = "watch_pullback"
            action_rule = f"score={score}≥62 但位置过滤:{pos_reason} → watch_pullback"
        else:
            action = "watch_pool"
            action_rule = f"score={score}≥62 且 trap=low 且 MA20 上且中低位 → watch_pool"
    elif score >= 55 and trap in ("low", "medium") and above_ma20:
        action = "watch_pullback"
        action_rule = f"score={score}≥55 且 trap∈{{low,medium}} → watch_pullback"
    elif score >= 48 and above_ma20:
        action = "wait"
        action_rule = f"score={score}≥48 → wait"
    else:
        action_rule = f"score={score} 未达观察阈值 → avoid"

    if block_entry and action in ("watch_pool", "near_high_trim", "watch_pullback"):
        action = "wait"
        action_rule += "；event block_entry 降级 wait"

    fund_note = f"市值{mv:.0f}亿" if mv else "市值—"
    if pe is not None:
        fund_note += f" PE{pe:.0f}"
    fund_note += f" 20d均额{amt:.0f}mn"
    if block_entry:
        fund_note += " 有事件风险"

    rationale = f"{weekly_pos}；trap={trap} vol={vol_ctx}"
    if struct == "higher_highs_higher_lows" and above_ma20 and not near_high:
        rationale += "；趋势结构尚可且离前高仍有空间"
    elif near_high:
        rationale += "；贴近前高需防站岗"
    elif not above_ma20:
        rationale += "；跌破MA20趋势转弱"

    theme_id = (inst.get("theme_meta") or {}).get("theme_id") or inst.get("theme")
    theme_label = (inst.get("theme_meta") or {}).get("theme_label")
    theme_lifecycle = None
    theme_lifecycle_rule = None
    if theme_id:
        for th in (slots.get("theme_context") or {}).get("themes") or []:
            if th.get("theme_id") == theme_id:
                theme_lifecycle = th.get("lifecycle_stage")
                theme_lifecycle_rule = th.get("lifecycle_rule")
                theme_label = theme_label or th.get("label")
                break
        tid_key = f"theme:{theme_id}.lifecycle_stage"
        if tid_key in flat:
            facts_used.append(tid_key)

    ev_ids: list[str] = []
    if weekly:
        ev_ids.append(weekly[-1].get("id", ""))
    if monthly:
        ev_ids.append(monthly[-1].get("id", ""))
    ev_ids = [x for x in ev_ids if x]

    observation_plan: dict[str, Any] = {}
    if action in ("watch_pool", "watch_pullback"):
        ma_ref = f"MA20({ma20_val:.2f})" if ma20_val else "MA20"
        observation_plan = {
            "framework": "observation_only",
            "invalid_below": ma_ref,
            "trail_stop_hint": f"观察失效：收盘跌破 {ma_ref} 或周结构转 LH/LL",
            "take_profit_hint": "前高/阻力区分批减仓，不追涨",
            "entry_trigger": "缩量回踩 MA20 企稳后再评估（非买入推荐）",
            "rationale": rationale,
            "facts_used": list(facts_used),
        }

    return {
        "safety_rank": score,
        "action": action,
        "weekly_position": weekly_pos,
        "volume_context": vol_ctx,
        "trap_risk": trap,
        "fundamental_note": fund_note,
        "rank_rationale": rationale,
        "position_band": position_band,
        "price_percentile_2y": pct_2y,
        "facts_used": facts_used,
        "observation_plan": observation_plan,
        "evidence_ids": ev_ids,
        "score_breakdown": breakdown,
        "trap_vol_reason": trap_rule,
        "action_rule": action_rule,
        "theme_id": theme_id,
        "theme_label": theme_label,
        "theme_lifecycle": theme_lifecycle,
        "theme_lifecycle_rule": theme_lifecycle_rule,
    }


def _build_screen_steps(pack: dict[str, Any], trace: dict[str, Any]) -> list[dict[str, Any]]:
    sent = pack.get("market_sentiment") or {}
    tc = (pack.get("slots") or {}).get("theme_context") or {}
    themes = tc.get("themes") or []
    mf = trace.get("market_filter") or {}
    flat = (pack.get("fact_index") or {}).get("flat", {})

    idx_evidence: list[str] = []
    idx_obs: list[dict[str, Any]] = []
    for idx in pack.get("indices") or []:
        daily = (idx.get("bars") or {}).get("daily") or []
        if not daily:
            continue
        bar = daily[-1]
        bid = bar.get("id")
        if bid:
            idx_evidence.append(bid)
        pct = bar.get("pct_chg")
        if pct is not None:
            idx_obs.append(
                {
                    "kind": "fact",
                    "text": f"{idx.get('name', idx.get('ts_code'))} 日线 {pct:+.2f}%",
                    "fact_keys": [f"bar:{bid}:pct_chg"] if bid else [],
                }
            )

    sent_obs: list[dict[str, Any]] = []
    if sent:
        for key, label in (
            ("tier", "情绪档位"),
            ("limit_ratio", "涨跌停比"),
            ("break_rate", "破板率"),
            ("max_lianban", "最高连板"),
        ):
            val = sent.get(key)
            if val is not None:
                fk = f"market_sentiment.{key}"
                sent_obs.append({"kind": "fact", "text": f"{label}={val}", "fact_keys": [fk] if fk in flat else []})
        hot = sent.get("hot_themes") or []
        if hot:
            sent_obs.append(
                {
                    "kind": "qualitative",
                    "text": f"热点题材：{', '.join(h['theme'] for h in hot[:3])}",
                    "fact_keys": [],
                }
            )
    else:
        fs = (pack.get("meta") or {}).get("fetch_status") or {}
        msgs = (pack.get("meta") or {}).get("fetch_messages") or []
        reason = next((m for m in msgs if "market_sentiment" in m or "limit_list" in m), "")
        sent_obs.append(
            {
                "kind": "qualitative",
                "text": f"market_sentiment 缺失（fetch_status.sentiment={fs.get('sentiment', '?')}）{reason}",
                "fact_keys": [],
            }
        )

    theme_obs: list[dict[str, Any]] = []
    for th in sorted(themes, key=lambda x: -(x.get("strength_rank") or 0))[:8]:
        inp = th.get("lifecycle_inputs") or {}
        theme_obs.append(
            {
                "kind": "qualitative",
                "text": (
                    f"{th.get('label', th.get('theme_id'))} → {th.get('lifecycle_stage')} "
                    f"（{th.get('lifecycle_rule', '—')}）"
                    f" | down={inp.get('down_frac', th.get('down_frac'))} "
                    f"up={inp.get('up_frac', th.get('up_frac'))} "
                    f"median={th.get('median_pct_1d', '—')}% "
                    f"n={th.get('sample_n', '—')}"
                ),
                "fact_keys": [f"theme:{th.get('theme_id')}.lifecycle_stage"]
                if f"theme:{th.get('theme_id')}.lifecycle_stage" in flat
                else [],
            }
        )
    if not theme_obs:
        theme_obs.append({"kind": "qualitative", "text": "theme_context 无活跃主题样本", "fact_keys": []})

    ranked_n = sum(
        1
        for _ts, dec in (trace.get("decisions") or {}).items()
        if (dec.get("screen") or {}).get("safety_rank") is not None
    )

    step4_obs = (idx_obs[:4] or [{"kind": "qualitative", "text": "指数数据见 pack.indices", "fact_keys": []}]) + theme_obs
    return [
        {
            "step": 1,
            "lens": "market-sentiment",
            "prompts_used": ["涨跌停比", "破板率", "连板热度", "entry_policy"],
            "evidence_ids": [],
            "observations": sent_obs,
            "inference": (
                f"情绪 tier={sent.get('tier', '缺失')}；"
                f"allow_new_trend_trade={mf.get('allow_new_trend_trade', 'yes')}"
            ),
            "confidence": "medium" if sent else "low",
        },
        {
            "step": 2,
            "lens": "watchlist-relative-position",
            "prompts_used": ["周/月相对位置", "trap_risk", "volume_context"],
            "evidence_ids": [],
            "observations": [
                {
                    "kind": "qualitative",
                    "text": f"全自选 {ranked_n} 只：trap/vol 规则见 decisions[].screen.trap_vol_reason",
                    "fact_keys": [],
                }
            ],
            "inference": "相对位置与站岗风险已写入各标的 screen.weekly_position / trap_risk / trap_vol_reason",
            "confidence": "medium",
        },
        {
            "step": 3,
            "lens": "watchlist-safety-rank",
            "prompts_used": ["safety_rank", "action", "score_breakdown"],
            "evidence_ids": [],
            "observations": [
                {
                    "kind": "qualitative",
                    "text": f"已排序 {ranked_n} 只；打分拆解见 score_breakdown；policy 熔断见 downgrade_reasons",
                    "fact_keys": [],
                }
            ],
            "inference": "safety_rank 由规则加减分 → action；脚本 gate 后输出 watch_pool",
            "confidence": "medium",
        },
        {
            "step": 4,
            "lens": "watchlist-observation-framework",
            "prompts_used": ["观察失效位", "止盈框架", "非买入推荐"],
            "evidence_ids": idx_evidence[:4],
            "observations": step4_obs,
            "inference": "watch_pool 标的已填 observation_plan（观察止损/止盈框架，非开仓指令）",
            "confidence": "medium",
        },
    ]


def fill_screen_trace_from_pack(trace: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    """Rank all symbols and populate steps / market_filter from pack evidence."""
    from core.pack_facts import attach_fact_index
    from core.trace_a_share import merge_pack_a_share_into_trace

    attach_fact_index(pack)
    flat = pack["fact_index"]["flat"]
    slots = pack.get("slots") or {}

    for inst in pack.get("symbols", []):
        ts = inst["ts_code"]
        if ts not in trace.get("decisions", {}):
            continue
        sc = _assess_symbol(inst, flat, slots)
        dec = trace["decisions"][ts]
        dec["screen"] = {k: v for k, v in sc.items() if k != "evidence_ids"}
        dec["facts_used"] = sc["facts_used"]
        dec["evidence_ids"] = sc["evidence_ids"]

    merge_pack_a_share_into_trace(trace, pack)

    mf = trace.setdefault("market_filter", {})
    parts = []
    for idx in pack.get("indices") or []:
        daily = (idx.get("bars") or {}).get("daily") or []
        if daily:
            parts.append(f"{idx.get('name')} {daily[-1].get('pct_chg', 0):+.2f}%")
    mf["regime_note"] = "；".join(parts[:4]) if parts else mf.get("regime_note", "")
    mf["indices_considered"] = [i["ts_code"] for i in pack.get("indices") or []]
    sent = pack.get("market_sentiment") or {}
    if sent:
        mf["reasoning_summary"] = (
            f"情绪 tier={sent.get('tier')} limit_ratio={sent.get('limit_ratio')} "
            f"break_rate={sent.get('break_rate')}"
        )
        mf["confidence"] = "medium"
    else:
        mf["reasoning_summary"] = mf.get("reasoning_summary") or "market_sentiment 缺失，情绪维度未纳入"
        mf["confidence"] = "low"

    trace["steps"] = _build_screen_steps(pack, trace)
    trace["meta"]["lenses_applied"] = list(WATCHLIST_SCREEN_LENSES)
    pmeta = pack.get("meta") or {}
    trace["meta"]["run_id"] = pmeta.get("run_id") or trace["meta"].get("run_id")
    trace["meta"]["as_of"] = pmeta.get("as_of") or trace["meta"].get("as_of")

    gaps: list[str] = list(trace.get("gaps") or [])
    gaps = [g for g in gaps if "scaffold" not in g and "ai_rank_pending" not in g]
    gaps.append("ranked_by_rule_engine_safety_rank")
    trace["gaps"] = gaps
    return trace
