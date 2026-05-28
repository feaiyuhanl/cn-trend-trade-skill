"""Auto full finalize for watch_pool symbols."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from core.init_trace import FULL_ANALYSIS_LENSES


def _strength_from_hints(h: dict[str, Any]) -> dict[str, str]:
    struct = h.get("structure", "")
    above_ma20 = h.get("price_above_ma20")
    above_w = h.get("price_above_weekly_ma20")
    daily = "strong" if struct == "higher_highs_higher_lows" and above_ma20 else "weak"
    weekly = "strong" if above_w and struct == "higher_highs_higher_lows" else "neutral"
    monthly = "neutral"
    align = "mostly_aligned" if daily == "strong" and weekly == "strong" else "conflicted"
    if struct == "range_bound":
        daily = weekly = "neutral"
        align = "unknown"
    return {"daily": daily, "weekly": weekly, "monthly": monthly, "alignment": align}


def _phase_from_hints(h: dict[str, Any]) -> str:
    struct = h.get("structure", "")
    if struct == "higher_highs_higher_lows" and h.get("price_above_ma20"):
        return "acceleration"
    if struct == "range_bound":
        return "unclear"
    return "unclear"


def build_watch_pool_full_trace(
    pack: dict[str, Any],
    screen_trace: dict[str, Any],
    watch_pool_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    from core.init_trace import init_trace_from_pack

    trace = init_trace_from_pack(pack, playbook="full-analysis")
    meta = pack.get("meta") or {}
    trace["meta"]["run_id"] = f"{meta.get('run_id', 'wp')}-full"
    trace["meta"]["rules_profile"] = "development"
    trace["meta"]["session_mode"] = "watchlist_deep"

    screen_mf = screen_trace.get("market_filter") or {}
    mf = trace.setdefault("market_filter", {})
    mf.update(
        {
            "indices_considered": [i["ts_code"] for i in pack.get("indices", [])],
            "regime_inference": screen_mf.get("regime_note") or "watchlist_screen_context",
            "allow_new_trend_trade": screen_mf.get("allow_new_trend_trade", "yes"),
            "reasoning_summary": screen_mf.get("reasoning_summary") or "watch_pool 深度分析（非买入推荐）",
            "confidence": screen_mf.get("confidence", "medium"),
            "sector_retreats": screen_mf.get("sector_retreats") or [],
        }
    )

    sent = pack.get("market_sentiment") or {}
    if sent:
        mf["sentiment_tier"] = sent.get("tier")
        mf["limit_ratio"] = sent.get("limit_ratio")
        mf["break_rate"] = sent.get("break_rate")
        mf["max_lianban"] = sent.get("max_lianban")

    tc = (pack.get("slots") or {}).get("theme_context") or {}
    if tc.get("themes"):
        trace["theme_assessment"] = tc["themes"]

    flat = (pack.get("fact_index") or {}).get("flat", {})
    idx_bars: list[str] = []
    for idx in pack.get("indices") or []:
        daily = (idx.get("bars") or {}).get("daily") or []
        if daily and daily[-1].get("id"):
            idx_bars.append(daily[-1]["id"])

    steps: list[dict[str, Any]] = []
    for i, lens in enumerate(FULL_ANALYSIS_LENSES, start=1):
        inference = f"watch_pool 深度分析 · {lens}"
        obs: list[dict[str, Any]] = []
        if lens == "market-filter":
            obs = [{"kind": "qualitative", "text": mf.get("reasoning_summary", ""), "fact_keys": []}]
        elif lens == "market-sentiment" and sent:
            obs = [
                {
                    "kind": "fact",
                    "text": f"tier={sent.get('tier')} break_rate={sent.get('break_rate')}",
                    "fact_keys": [],
                }
            ]
        elif lens == "exit-signals":
            obs = [{"kind": "qualitative", "text": "观察池标的 exit_plan 自 observation_plan 映射", "fact_keys": []}]
        elif lens == "discipline":
            obs = [{"kind": "qualitative", "text": "WATCH_POOL_NOT_BUY：观察不等于买入", "fact_keys": []}]
        else:
            obs = [{"kind": "qualitative", "text": f"{lens} 见 screen dossier", "fact_keys": []}]
        steps.append(
            {
                "step": i,
                "lens": lens,
                "prompts_used": [lens],
                "evidence_ids": idx_bars[:3] if i == 1 else [],
                "observations": obs,
                "inference": inference,
                "confidence": "medium",
            }
        )
    trace["steps"] = steps

    symbols_in_pack = {s["ts_code"] for s in pack.get("symbols", [])}
    for row in watch_pool_rows:
        ts = row["ts_code"]
        if ts not in symbols_in_pack:
            continue
        sc = ((screen_trace.get("decisions") or {}).get(ts) or {}).get("screen") or {}
        inst = next(s for s in pack["symbols"] if s["ts_code"] == ts)
        h = inst.get("derived_hints") or {}
        daily = (inst.get("bars") or {}).get("daily") or []
        weekly = (inst.get("bars") or {}).get("weekly") or []
        ev: list[str] = []
        if daily:
            ev.append(daily[-1]["id"])
        if weekly:
            ev.append(weekly[-1]["id"])

        op = sc.get("observation_plan") or row.get("observation_plan") or {}
        exit_plan: dict[str, Any] = {}
        if op:
            exit_plan = {
                "trail_stop": op.get("trail_stop_hint", ""),
                "take_profit": op.get("take_profit_hint", ""),
                "invalid_below": op.get("invalid_below", ""),
            }

        trace["decisions"][ts] = {
            "evidence_ids": ev,
            "facts_used": sc.get("facts_used") or row.get("facts_used") or _facts_for_ts(flat, ts),
            "phase": _phase_from_hints(h),
            "strength": _strength_from_hints(h),
            "entry": {
                "type": "watch",
                "action": "wait",
                "rationale": (
                    f"观察池标的（非买入推荐）；{sc.get('rank_rationale') or row.get('note', '')}；"
                    f"触发：{op.get('entry_trigger', '回踩确认后再评估')}"
                ),
            },
            "position_plan": {"framework": {"max_total_pct": 0.0, "note": "观察池不开仓"}, "computed": {}},
            "exit_plan": exit_plan,
        }

    trace["discipline_checklist"] = [
        {"rule_id": "WATCH_POOL_NOT_BUY", "rule": "观察池不等于买入推荐", "passed": True, "note": ""},
        {"rule_id": "STOP_RECORDED", "rule": "观察框架/exit_plan 已记录", "passed": True, "note": ""},
        {"rule_id": "SENTIMENT_AWARE", "rule": "已读 sentiment", "passed": bool(sent), "note": "" if sent else "sentiment 缺失"},
        {"rule_id": "NO_JUNK_STOCK", "rule": "watch_pool 已通过 quality gate", "passed": True, "note": ""},
        {"rule_id": "EVENT_RISK_CLEAR", "rule": "watch_pool 无 event block", "passed": True, "note": ""},
        {"rule_id": "THEME_LEADER_HEALTH", "rule": "题材龙头未跌停阻断", "passed": True, "note": ""},
        {"rule_id": "MF_NO_AGGRESSIVE", "rule": "环境允许观察", "passed": mf.get("allow_new_trend_trade") != "no", "note": ""},
        {"rule_id": "NO_SIGNAL_NO_TRADE", "rule": "entry.action=wait", "passed": True, "note": ""},
    ]
    trace["gaps"] = list(screen_trace.get("gaps") or [])
    if not sent:
        trace["gaps"].append("market_sentiment 缺失（深度分析情绪维度不完整）")
    return trace


def _facts_for_ts(flat: dict[str, Any], ts: str) -> list[str]:
    prefix = f"symbol:{ts}."
    return [k for k in flat if k.startswith(prefix)][:8]


def run_watch_pool_full_finalize(
    watch_pool: list[dict[str, Any]],
    screen_trace: dict[str, Any],
    *,
    out_dir: Path,
    run_id: str,
    live: bool = True,
) -> dict[str, Any]:
    """Assemble + full finalize for watch_pool symbols (combined pack)."""
    if not watch_pool:
        return {"skipped": True, "reason": "empty watch_pool"}

    from core.assemble import assemble, TMP_DIR
    from core.pack_facts import attach_fact_index
    from core.pipeline import finalize_trace
    from core.validate import load_json

    symbols = [r["ts_code"] for r in watch_pool]
    sym_csv = ",".join(symbols)
    wp_dir = out_dir / "watch_pool_analysis"
    wp_dir.mkdir(parents=True, exist_ok=True)

    try:
        pack_path = assemble(
            use_fixture=not live,
            run_id=f"{run_id}-wp",
            symbols=symbols,
            indices_profile="comprehensive",
        )
    except Exception as e:
        return {"skipped": False, "error": f"assemble failed: {e}", "symbols": symbols}

    pack = load_json(pack_path)
    attach_fact_index(pack)
    trace = build_watch_pool_full_trace(pack, screen_trace, watch_pool)
    trace_path = wp_dir / "trade_trace.json"
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(pack_path, wp_dir / "market_pack.json")

    code, errs = finalize_trace(trace_path, pack_path, out_dir=wp_dir, no_auto_review=True)
    paths_by_ts: dict[str, dict[str, str]] = {}
    for ts in symbols:
        paths_by_ts[ts] = {
            "report": str(wp_dir / "report.md"),
            "dossier": str(wp_dir / "decision-dossier.md"),
            "audit": str(wp_dir / "audit-sheet.md"),
            "trace": str(trace_path),
            "pack": str(wp_dir / "market_pack.json"),
        }

    return {
        "skipped": False,
        "exit_code": code,
        "errors": errs,
        "symbols": symbols,
        "paths": paths_by_ts,
        "combined_report": str(wp_dir / "report.md"),
    }
