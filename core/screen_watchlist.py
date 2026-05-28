"""Watchlist trend screen — policy-driven, not buy recommendations."""

from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_POLICY: dict[str, Any] = {
    "max_symbols_per_run": 145,
    "max_watch_pool_output": 15,
    "max_per_theme": 2,
    "exclude_if_1d_drop_pct": 4.0,
    "exclude_if_below_ma20": True,
    "block_new_if_holding_same_theme": True,
    "sector_retreat": {
        "min_theme_symbols": 4,
        "min_fraction_down": 0.5,
        "min_median_drop_pct": 2.0,
    },
    "batch_size": 25,
    "batch_retry": 2,
    "batch_sleep_sec": 0.8,
    "archive_runs": True,
    "panoramic_report": True,
    "auto_finalize_watch_pool": True,
    "ai_auto_rank": True,
    "fetch_retry": {"max_attempts": 3, "backoff_sec": [65, 90, 120]},
    "forbid_output_words": ["买入推荐", "优先推荐", "优先买入"],
    "universe_mode": "watchlist",
    "trend_top_n": 10,
    "trend_top10_scope": "auto",
    "max_symbols_mainboard_run": 0,
    "bulk_fetch": True,
    "skip_chronic_loss_on_enrich_if_universe_prefiltered": True,
    "skip_missing_leaders_on_bulk_screen": True,
}


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_watchlist_config(watchlist_path: Path | None = None) -> dict[str, Any]:
    path = watchlist_path or (_ROOT / "config" / "watchlist.yaml")
    data = _load_yaml(path)
    policy = {**DEFAULT_POLICY, **(data.get("screening_policy") or {})}
    themes_path = _ROOT / str(policy.get("themes_file") or "config/themes.yaml")
    themes_data = _load_yaml(themes_path)
    holdings_path = _ROOT / str(policy.get("holdings_theme_file") or "config/my_discipline.yaml")
    holdings_data = _load_yaml(holdings_path)
    return {
        "watchlist_path": path,
        "symbols_flat": list(data.get("symbols_flat") or []),
        "policy": policy,
        "themes": themes_data.get("themes") or {},
        "holdings": holdings_data.get("holdings") or [],
    }


def build_theme_index(themes: dict[str, Any]) -> dict[str, str]:
    from core.theme_graph import build_theme_index as _tg_index

    full = _tg_index(themes)
    return {ts: v["theme"] for ts, v in full.items()}


def holding_ts_codes(holdings: list[dict[str, Any]]) -> set[str]:
    return {str(h["ts_code"]).strip().upper() for h in holdings if h.get("ts_code")}


def candidate_row_from_inst(
    ts: str,
    name: str,
    h: dict[str, Any],
    *,
    pct_1d: float | None,
    flat: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Objective snapshot for AI ranking — action/safety_rank filled by Agent via screen_trace."""
    struct = h.get("structure", "insufficient_data")
    tags: list[str] = []
    if struct == "higher_highs_higher_lows":
        tags.append("HH/HL")
    elif struct == "range_bound":
        tags.append("盘整")
    elif struct == "lower_highs_lower_lows":
        tags.append("LH/LL")
    else:
        tags.append("数据不足")

    flat = flat or {}
    prefix = f"symbol:{ts}."
    fundamentals = {
        k.replace(prefix + "fundamentals.", ""): flat[k]
        for k in flat
        if k.startswith(prefix + "fundamentals.")
    }

    return {
        "ts_code": ts,
        "name": name,
        "safety_rank": None,
        "score": None,
        "phase": "pending_ai",
        "action": "pending",
        "note": "待 AI 综合 safety_rank（见 watchlist-screen playbook）",
        "tags": tags,
        "latest_close": h.get("_close"),
        "pct_chg_1d": pct_1d,
        "structure": struct,
        "price_above_ma20": h.get("price_above_ma20"),
        "vol_ratio_5_20": h.get("vol_ratio_5_20"),
        "amount_ratio_5_20": h.get("amount_ratio_5_20"),
        "distance_from_52w_high_pct": h.get("distance_from_52w_high_pct"),
        "distance_from_weekly_high_pct": h.get("distance_from_weekly_high_pct"),
        "distance_from_monthly_high_pct": h.get("distance_from_monthly_high_pct"),
        "distance_from_52w_low_pct": h.get("distance_from_52w_low_pct"),
        "price_percentile_2y": h.get("price_percentile_2y"),
        "position_band": h.get("position_band"),
        "ma20_value": h.get("ma20_value"),
        "atr14_pct": h.get("atr14_pct"),
        "fundamentals": fundamentals,
        "weekly_position": "",
        "volume_context": "unclear",
        "trap_risk": "unknown",
        "fundamental_note": "",
        "facts_used": [],
        "theme": None,
        "downgrade_reasons": [],
        "ai_eligible": True,
    }


def score_symbol_base(ts: str, name: str, h: dict[str, Any], *, pct_1d: float | None) -> dict[str, Any]:
    """Backward-compatible alias for tests; production ranking uses AI safety_rank."""
    return candidate_row_from_inst(ts, name, h, pct_1d=pct_1d)


def apply_policy_row(
    row: dict[str, Any],
    *,
    policy: dict[str, Any],
    theme_id: str | None,
    holdings_ts: set[str],
    holding_themes: set[str] | None = None,
) -> dict[str, Any]:
    row = dict(row)
    row["theme"] = theme_id
    reasons: list[str] = list(row.get("downgrade_reasons") or [])

    drop_thr = float(policy.get("exclude_if_1d_drop_pct") or 4.0)
    pct = row.get("pct_chg_1d")
    if pct is not None and pct <= -drop_thr and row["action"] in ("watch_pool", "near_high_trim"):
        row["action"] = "wait"
        reasons.append(f"1日跌幅{pct:.2f}%超阈值")
    if policy.get("exclude_if_below_ma20") and not row.get("price_above_ma20"):
        if row["action"] in ("watch_pool", "near_high_trim", "watch_pullback"):
            row["action"] = "avoid"
            reasons.append("跌破MA20")
    if policy.get("block_new_if_holding_same_theme") and theme_id and row["ts_code"] in holdings_ts:
        pass  # same symbol is holding — handled below
    if row["ts_code"] in holdings_ts:
        row["action"] = "holding"
        reasons.append("已有持仓，仅风控跟踪")
    elif (
        policy.get("block_new_if_holding_same_theme")
        and theme_id
        and theme_id in (holding_themes or set())
        and row["action"] == "watch_pool"
    ):
        row["action"] = "wait"
        reasons.append("与持仓同主题，不新增观察升级为可开仓")

    row["downgrade_reasons"] = reasons
    return row


def apply_pack_gates(row: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    """Quality / event / theme leader / sentiment gates from pack.slots."""
    row = dict(row)
    reasons: list[str] = list(row.get("downgrade_reasons") or [])
    ts = row["ts_code"]
    slots = pack.get("slots") or {}

    qrec = (slots.get("quality_gate") or {}).get("symbols", {}).get(ts) or {}
    if qrec.get("tier") == "block":
        row["action"] = "avoid"
        reasons.append("质量兜底:" + ",".join(qrec.get("risk_flags") or qrec.get("reasons") or ["block"]))
        row["risk_flags"] = qrec.get("risk_flags") or []

    erec = (slots.get("event_risk") or {}).get("symbols", {}).get(ts) or {}
    if erec.get("block_entry"):
        if row["action"] in ("watch_pool", "near_high_trim", "watch_pullback"):
            row["action"] = "wait"
        reasons.append("事件风险:" + ",".join(erec.get("event_flags") or []))

    tid = row.get("theme")
    for th in (slots.get("theme_context") or {}).get("themes") or []:
        if th.get("theme_id") != tid:
            continue
        if th.get("leader_limit_down") or th.get("lifecycle_stage") == "retreat":
            if row.get("theme_meta", {}).get("role") == "follower" and row["action"] in (
                "watch_pool",
                "near_high_trim",
            ):
                row["action"] = "wait"
                reasons.append("龙头走弱/题材退潮")
        break

    sent = pack.get("market_sentiment") or {}
    if sent.get("tier") == "frozen" and row["action"] in ("watch_pool", "near_high_trim"):
        row["action"] = "wait"
        reasons.append("市场情绪冰点")
    if sent.get("tier") == "euphoric" and sent.get("break_rate", 0) >= 0.45:
        if row["action"] == "watch_pool":
            row["action"] = "wait"
            reasons.append("亢奋期破板率高，不追涨")

    row["downgrade_reasons"] = reasons
    return row


def detect_sector_retreat(
    rows: list[dict[str, Any]],
    theme_index: dict[str, str],
    policy: dict[str, Any],
) -> dict[str, Any]:
    cfg = policy.get("sector_retreat") or {}
    min_n = int(cfg.get("min_theme_symbols") or 4)
    frac = float(cfg.get("min_fraction_down") or 0.5)
    med_drop = float(cfg.get("min_median_drop_pct") or 2.0)

    by_theme: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        tid = theme_index.get(r["ts_code"]) or r.get("theme")
        if not tid:
            continue
        by_theme.setdefault(tid, []).append(r)

    retreats: list[dict[str, Any]] = []
    for tid, items in by_theme.items():
        if len(items) < min_n:
            continue
        pcts = [x["pct_chg_1d"] for x in items if x.get("pct_chg_1d") is not None]
        if len(pcts) < min_n:
            continue
        down = [p for p in pcts if p < 0]
        if len(down) / len(pcts) < frac:
            continue
        down_sorted = sorted(down)
        median = down_sorted[len(down_sorted) // 2]
        if abs(median) < med_drop:
            continue
        retreats.append({"theme": tid, "median_drop": median, "n": len(items), "down_frac": len(down) / len(pcts)})

    allow = "yes" if not retreats else "reduced"
    if retreats:
        allow = "no"
    return {"sector_retreats": retreats, "allow_new_trend_trade": allow}


def apply_sector_retreat_downgrade(rows: list[dict[str, Any]], retreat_info: dict[str, Any]) -> None:
    if retreat_info.get("allow_new_trend_trade") != "no":
        return
    retreat_themes = {x["theme"] for x in retreat_info.get("sector_retreats") or []}
    for r in rows:
        if r.get("theme") in retreat_themes and r["action"] in ("watch_pool", "near_high_trim"):
            r["action"] = "wait"
            r.setdefault("downgrade_reasons", []).append("板块退潮熔断")


def cap_watch_pool_by_theme(rows: list[dict[str, Any]], max_per_theme: int) -> None:
    pools = [r for r in rows if r["action"] == "watch_pool"]
    pools.sort(key=lambda x: (-(x.get("safety_rank") or -1), x["ts_code"]))
    kept: dict[str, int] = {}
    keep_ts: set[str] = set()
    for r in pools:
        tid = r.get("theme") or "_none"
        if kept.get(tid, 0) >= max_per_theme:
            continue
        kept[tid] = kept.get(tid, 0) + 1
        keep_ts.add(r["ts_code"])
    for r in rows:
        if r["action"] == "watch_pool" and r["ts_code"] not in keep_ts:
            r["action"] = "wait"
            r.setdefault("downgrade_reasons", []).append("同主题观察池上限")


def instrument_row_from_pack(inst: dict[str, Any], flat: dict[str, Any]) -> dict[str, Any]:
    from core.position_filter import classify_position_band

    ts = inst["ts_code"]
    h = dict(inst.get("derived_hints") or {})
    band = classify_position_band(h)
    h["position_band"] = band
    h["_close"] = flat.get(f"symbol:{ts}.latest_close")
    daily = inst.get("bars", {}).get("daily") or []
    pct_1d = float(daily[-1]["pct_chg"]) if daily else None
    row = candidate_row_from_inst(ts, inst.get("name", ts), h, pct_1d=pct_1d, flat=flat)
    row["position_band"] = band
    return row


def _merge_slot_symbols(target: dict[str, Any], source: dict[str, Any]) -> None:
    for ts, rec in (source.get("symbols") or {}).items():
        target.setdefault("symbols", {})[ts] = rec


def merge_batch_into_pack(accum: dict[str, Any] | None, pack: dict[str, Any]) -> dict[str, Any]:
    """Merge one batch live pack into a universe pack (all symbols for AI)."""
    if accum is None:
        accum = {
            "meta": dict(pack.get("meta") or {}),
            "symbols": [],
            "indices": list(pack.get("indices") or []),
            "slots": {},
            "market_sentiment": pack.get("market_sentiment"),
        }
    by_ts = {s["ts_code"]: s for s in accum.get("symbols", [])}
    for inst in pack.get("symbols", []):
        by_ts[inst["ts_code"]] = inst
    accum["symbols"] = list(by_ts.values())
    accum["meta"] = dict(pack.get("meta") or accum.get("meta") or {})
    if pack.get("market_sentiment"):
        accum["market_sentiment"] = pack["market_sentiment"]
    slots = accum.setdefault("slots", {})
    for key in ("quality_gate", "event_risk", "fundamentals", "theme_context", "theme_resolution"):
        src = (pack.get("slots") or {}).get(key)
        if not src:
            continue
        if key not in slots:
            slots[key] = src
            continue
        if isinstance(src.get("symbols"), dict):
            tgt = slots.setdefault(key, {"symbols": {}})
            _merge_slot_symbols(tgt, src)
        elif key in ("theme_context", "theme_resolution"):
            slots[key] = src
    return accum


def finalize_ranked_rows(
    rows: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
    retreat_info: dict[str, Any],
) -> list[dict[str, Any]]:
    from core.merge_screen_trace import sort_key_ranked

    apply_sector_retreat_downgrade(rows, retreat_info)
    cap_watch_pool_by_theme(rows, int(policy.get("max_per_theme") or 2))
    return sorted(rows, key=sort_key_ranked)


def trace_has_ai_ranks(trace: dict[str, Any]) -> bool:
    for _ts, dec in (trace.get("decisions") or {}).items():
        sc = (dec or {}).get("screen") or {}
        if sc.get("safety_rank") is not None:
            return True
    return False


def rows_from_merged_pack(
    pack: dict[str, Any],
    theme_index: dict[str, str],
) -> list[dict[str, Any]]:
    flat = (pack.get("fact_index") or {}).get("flat", {})
    rows: list[dict[str, Any]] = []
    for inst in pack.get("symbols", []):
        row = instrument_row_from_pack(inst, flat)
        row["theme"] = theme_index.get(row["ts_code"])
        row["theme_meta"] = inst.get("theme_meta") or {}
        rows.append(row)
    return rows


def apply_post_ai_gates(
    rows: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
    theme_index: dict[str, str],
    holdings_ts: set[str],
    holding_themes: set[str] | None,
    pack: dict[str, Any],
    apply_position: bool = True,
) -> None:
    from core.position_filter import apply_position_gate

    for i, row in enumerate(rows):
        if row.get("action") == "pending":
            continue
        tid = theme_index.get(row["ts_code"]) or row.get("theme")
        row["theme"] = tid
        row = apply_policy_row(
            row,
            policy=policy,
            theme_id=tid,
            holdings_ts=holdings_ts,
            holding_themes=holding_themes,
        )
        row = apply_pack_gates(row, pack)
        if apply_position:
            row = apply_position_gate(row)
        rows[i] = row


def resolve_universe_symbols(
    *,
    policy: dict[str, Any],
    watchlist_symbols: list[str],
    live: bool,
    max_symbols: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Resolve symbol list from universe_mode: watchlist | mainboard | both."""
    mode = str(policy.get("universe_mode") or "watchlist").lower()
    universe_meta: dict[str, Any] = {"universe_mode": mode}
    wl = [str(s).strip().upper() for s in watchlist_symbols if s]
    wl_set = set(wl)

    if mode == "watchlist":
        symbols = list(wl)
    elif mode in ("mainboard", "both"):
        if not live:
            universe_meta["mainboard_skipped"] = "fixture/offline mode — mainboard requires --live"
            symbols = list(wl) if mode == "both" else []
        else:
            try:
                from core.pack_enrich import _get_pro
                from core.universe_mainboard import fetch_mainboard_universe

                pro = _get_pro()
                mb = fetch_mainboard_universe(pro)
                mb_syms = list(mb.get("ts_codes") or [])
                universe_meta["mainboard"] = mb.get("meta") or {}
                universe_meta["mainboard"]["final_ts_codes"] = mb_syms
                if mode == "mainboard":
                    symbols = mb_syms
                else:
                    mb_cap = int(policy.get("max_symbols_mainboard_run") or 0)
                    mb_extra = [s for s in mb_syms if s not in wl_set]
                    if mb_cap > 0:
                        mb_extra = mb_extra[:mb_cap]
                    symbols = list(dict.fromkeys(wl + mb_extra))
                    universe_meta["mainboard_extra_count"] = len(mb_extra)
            except Exception as e:
                universe_meta["mainboard_error"] = str(e)
                symbols = list(wl)
    else:
        symbols = list(wl)
        universe_meta["universe_mode"] = "watchlist"

    if max_symbols is not None:
        symbols = symbols[:max_symbols]
    elif mode == "watchlist" and policy.get("max_symbols_per_run"):
        symbols = symbols[: int(policy["max_symbols_per_run"])]

    universe_meta["symbols_resolved"] = len(symbols)
    universe_meta["watchlist_count"] = len(wl_set)
    return symbols, universe_meta


def _attach_trend_top10(
    result: dict[str, Any],
    ranked: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
    watchlist_symbols: list[str],
    pack: dict[str, Any] | None,
    universe_meta: dict[str, Any],
) -> None:
    from core.trend_top10 import build_trend_top10

    mode = str(universe_meta.get("universe_mode") or policy.get("universe_mode") or "watchlist").lower()
    top_n = int(policy.get("trend_top_n") or 10)
    scope_cfg = str(policy.get("trend_top10_scope") or "auto").lower()
    if scope_cfg == "auto":
        scope = "mainboard" if mode in ("mainboard", "both") else "watchlist"
    else:
        scope = scope_cfg

    wl_set = {str(s).strip().upper() for s in watchlist_symbols}
    wp_ts = {r["ts_code"] for r in result.get("watch_pool") or []}
    mb_ts: set[str] | None = None
    if scope == "mainboard" and mode in ("mainboard", "both"):
        mb_meta = universe_meta.get("mainboard") or {}
        mb_list = mb_meta.get("final_ts_codes")
        if mb_list:
            mb_ts = set(mb_list)
        elif mode == "mainboard":
            mb_ts = {r["ts_code"] for r in ranked}

    trend = build_trend_top10(
        ranked,
        scope=scope,
        top_n=top_n,
        watchlist_ts=wl_set,
        watch_pool_ts=wp_ts,
        pack=pack,
        symbol_scope=mb_ts,
    )
    result["trend_top10"] = trend


def _meta_stale_fields(pack: dict[str, Any] | None) -> dict[str, str]:
    meta = (pack or {}).get("meta") or {}
    out: dict[str, str] = {}
    for k in (
        "expected_trade_date",
        "data_stale_headline",
        "data_stale_detail",
        "data_stale_retry",
        "data_stale_notice",
    ):
        if meta.get(k):
            out[k] = str(meta[k])
    return out


def _fetch_cfg_from_policy(policy: dict[str, Any]) -> dict[str, Any]:
    from core.tushare_rate_limit import load_fetch_concurrency_config

    cfg = load_fetch_concurrency_config()
    override = policy.get("fetch_concurrency") or {}
    return {**cfg, **override}


def _enrich_merged_pack_once(
    merged_pack: dict[str, Any],
    policy: dict[str, Any],
    *,
    universe_meta: dict[str, Any] | None = None,
) -> None:
    from core.pack_enrich import enrich_a_share_context

    fetch_retry = policy.get("fetch_retry") or {}
    fetch_cfg = _fetch_cfg_from_policy(policy)
    skip_cl = False
    if policy.get("skip_chronic_loss_on_enrich_if_universe_prefiltered"):
        mb = (universe_meta or {}).get("mainboard") or {}
        clf = mb.get("chronic_loss_filter") or {}
        skip_cl = clf.get("after_chronic_loss") is not None and not clf.get("skipped")
    skip_leaders = bool(policy.get("skip_missing_leaders_on_bulk_screen")) and len(
        merged_pack.get("symbols") or []
    ) >= int(fetch_cfg.get("bulk_fetch_min_symbols") or 50)
    enrich_a_share_context(
        merged_pack,
        fetch_retry=fetch_retry,
        fetch_cfg=fetch_cfg,
        skip_chronic_loss=skip_cl,
        skip_missing_leaders=skip_leaders,
    )


def _write_panoramic_outputs(
    result: dict[str, Any],
    *,
    out: Path,
    trace: dict[str, Any] | None,
    pack: dict[str, Any] | None,
    policy: dict[str, Any],
    run_id: str,
    live: bool,
) -> None:
    from core.screen_panoramic import (
        render_screen_audit_sheet,
        render_screen_dossier,
        render_screen_panoramic_report,
    )

    pack_meta = (pack or {}).get("meta") or result.get("meta")
    panoramic = policy.get("panoramic_report", True)
    if panoramic and trace and pack:
        report_path = out / "screen_report.md"
        report_path.write_text(
            render_screen_panoramic_report(
                result, trace=trace, pack_meta=pack_meta, pack=pack
            ),
            encoding="utf-8",
        )
        dossier_path = out / "screen-dossier.md"
        dossier_path.write_text(render_screen_dossier(result, trace=trace, pack=pack), encoding="utf-8")
        audit_path = out / "screen-audit-sheet.md"
        audit_path.write_text(render_screen_audit_sheet(result, pack=pack), encoding="utf-8")
        result["_paths"]["report"] = str(report_path)
        result["_paths"]["dossier"] = str(dossier_path)
        result["_paths"]["audit"] = str(audit_path)
    else:
        report_path = out / "screen_report.md"
        report_path.write_text(render_screen_report(result), encoding="utf-8")
        result["_paths"]["report"] = str(report_path)

    if policy.get("auto_finalize_watch_pool") and result.get("watch_pool") and trace:
        from core.screen_full_finalize import run_watch_pool_full_finalize

        wp_result = run_watch_pool_full_finalize(
            result["watch_pool"],
            trace,
            out_dir=out,
            run_id=run_id,
            live=live,
        )
        result["watch_pool_full_analysis"] = wp_result
        if wp_result.get("errors"):
            result.setdefault("gaps", []).append(
                f"watch_pool_full_finalize: {len(wp_result['errors'])} validation errors"
            )


def _maybe_auto_rank_trace(
    trace: dict[str, Any],
    pack: dict[str, Any],
    policy: dict[str, Any],
    trace_path: Path,
) -> dict[str, Any]:
    if not policy.get("ai_auto_rank", True):
        return trace
    from core.screen_ai import fill_screen_trace_from_pack

    trace = fill_screen_trace_from_pack(trace, pack)
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    return trace


def run_merge_screen_trace(
    *,
    pack_path: Path,
    trace_path: Path,
    watchlist_path: Path | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Apply patched screen_trace to cached screen_pack (no network)."""
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    from core.pack_facts import attach_fact_index

    attach_fact_index(pack)
    cfg = load_watchlist_config(watchlist_path)
    policy = cfg["policy"]
    theme_index = build_theme_index(cfg["themes"])
    holdings_ts = holding_ts_codes(cfg["holdings"])
    holding_themes = {theme_index.get(ts) for ts in holdings_ts} - {None}

    from core.merge_screen_trace import merge_trace_into_rows

    rows = rows_from_merged_pack(pack, theme_index)
    rows = merge_trace_into_rows(rows, trace)
    for row in rows:
        ts = row["ts_code"]
        sc = ((trace.get("decisions") or {}).get(ts) or {}).get("screen") or {}
        if sc.get("observation_plan"):
            row["observation_plan"] = sc["observation_plan"]
    apply_post_ai_gates(
        rows,
        policy=policy,
        theme_index=theme_index,
        holdings_ts=holdings_ts,
        holding_themes=holding_themes,
        pack=pack,
    )
    retreat_info = detect_sector_retreat(rows, theme_index, policy)
    ranked = finalize_ranked_rows(rows, policy=policy, retreat_info=retreat_info)

    meta = pack.get("meta") or {}
    stale_extra = _meta_stale_fields(pack)
    max_out = int(policy.get("max_watch_pool_output") or 15)
    watchlist_symbols = list(cfg["symbols_flat"])
    universe_meta = {"universe_mode": policy.get("universe_mode") or "watchlist"}
    result: dict[str, Any] = {
        "meta": {
            "run_id": meta.get("run_id") or datetime.now().strftime("%Y%m%d-%H%M%S"),
            "as_of": meta.get("as_of"),
            "trade_date": meta.get("trade_date"),
            "data_stale": bool(meta.get("data_stale")),
            "fetch_status": meta.get("fetch_status") or {},
            "fetch_messages": meta.get("fetch_messages") or [],
            **stale_extra,
            "output_label": policy.get("output_label") or "watch_pool_only",
            "screened": len(ranked),
            "ranked_by": "ai_safety_rank",
            "policy_version": cfg["watchlist_path"].name,
            "universe_mode": universe_meta.get("universe_mode"),
        },
        "market_filter": {
            "regime_note": "",
            "allow_new_trend_trade": retreat_info.get("allow_new_trend_trade", "yes"),
            "sector_retreats": retreat_info.get("sector_retreats") or [],
        },
        "watch_pool": [r for r in ranked if r["action"] == "watch_pool"][:max_out],
        "watch_pullback": [r for r in ranked if r["action"] == "watch_pullback"][:max_out],
        "near_high_trim": [r for r in ranked if r["action"] == "near_high_trim"][:max_out],
        "avoid_count": sum(1 for r in ranked if r["action"] == "avoid"),
        "gaps": ["ranked_by_rule_engine_safety_rank"],
        "all_ranked": ranked,
        "screen_pack_path": str(pack_path),
        "screen_trace_path": str(trace_path),
    }
    _attach_trend_top10(
        result,
        ranked,
        policy=policy,
        watchlist_symbols=watchlist_symbols,
        pack=pack,
        universe_meta=universe_meta,
    )
    if pack.get("market_sentiment"):
        result["market_sentiment"] = pack["market_sentiment"]
    tc = (pack.get("slots") or {}).get("theme_context")
    if tc:
        result["theme_context"] = tc

    out = out_dir or (_ROOT / ".trend-trade" / "tmp")
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "watchlist_screen.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["_paths"] = {"json": str(json_path)}
    if result.get("trend_top10"):
        top_path = out / "trend_top10.json"
        top_path.write_text(json.dumps(result["trend_top10"], ensure_ascii=False, indent=2), encoding="utf-8")
        result["_paths"]["trend_top10"] = str(top_path)
    _write_panoramic_outputs(
        result,
        out=out,
        trace=trace,
        pack=pack,
        policy=policy,
        run_id=result["meta"]["run_id"],
        live=(pack.get("meta") or {}).get("mode") == "live",
    )
    if policy.get("archive_runs"):
        run_id = result["meta"]["run_id"]
        arch = _ROOT / ".trend-trade" / "archive" / run_id
        arch.mkdir(parents=True, exist_ok=True)
        shutil.copy2(json_path, arch / "watchlist_screen.json")
        top_p = out / "trend_top10.json"
        if top_p.exists():
            shutil.copy2(top_p, arch / "trend_top10.json")
        for name in ("screen_report.md", "screen-dossier.md", "screen-audit-sheet.md"):
            p = out / name
            if p.exists():
                shutil.copy2(p, arch / name)
        wp_dir = out / "watch_pool_analysis"
        if wp_dir.exists():
            arch_wp = arch / "watch_pool_analysis"
            if arch_wp.exists():
                shutil.rmtree(arch_wp)
            shutil.copytree(wp_dir, arch_wp)
    return result


def run_screen(
    *,
    symbols: list[str] | None = None,
    watchlist_path: Path | None = None,
    live: bool = True,
    max_symbols: int | None = None,
    out_dir: Path | None = None,
    screen_trace_path: Path | None = None,
    data_only: bool = False,
    universe_mode: str | None = None,
    trend_top_n: int | None = None,
    fail_on_stale: bool | None = None,
) -> dict[str, Any]:
    from core.fetch_live import build_live_pack, preflight_fresh_session
    from core.pack_facts import attach_fact_index

    cfg = load_watchlist_config(watchlist_path)
    policy = cfg["policy"]
    if universe_mode:
        policy = {**policy, "universe_mode": universe_mode}
    if trend_top_n is not None:
        policy = {**policy, "trend_top_n": trend_top_n}
    watchlist_symbols = list(cfg["symbols_flat"])
    if symbols is not None:
        symbols = [str(s).strip().upper() for s in symbols if s]
        if max_symbols is not None:
            symbols = symbols[:max_symbols]
        universe_meta: dict[str, Any] = {
            "universe_mode": "cli_override",
            "symbols_resolved": len(symbols),
        }
    else:
        symbols, universe_meta = resolve_universe_symbols(
            policy=policy,
            watchlist_symbols=watchlist_symbols,
            live=live,
            max_symbols=max_symbols,
        )

    theme_resolution: dict[str, Any] | None = None
    if live:
        from core.theme_leader_resolver import resolve_theme_membership_for_universe

        pro = None
        try:
            from core.pack_enrich import _get_pro

            pro = _get_pro()
        except Exception:
            pro = None
        if pro:
            theme_resolution = resolve_theme_membership_for_universe(
                pro,
                {"themes": cfg["themes"], "version": "2.0.0", "leader_policy": "spec_lead"},
                symbols,
                mode="live",
            )
    if theme_resolution:
        from core.theme_graph import build_theme_index as _build_full_index

        theme_index = {
            ts: v["theme"]
            for ts, v in _build_full_index(cfg["themes"], theme_resolution).items()
        }
    else:
        theme_index = build_theme_index(cfg["themes"])
    holdings_ts = holding_ts_codes(cfg["holdings"])
    # themes of current holdings
    holding_themes = {theme_index.get(ts) for ts in holdings_ts} - {None}

    batch_size = int(policy.get("batch_size") or 25)
    retries = int(policy.get("batch_retry") or 2)
    sleep_sec = float(policy.get("batch_sleep_sec") or 0.8)
    fetch_cfg = _fetch_cfg_from_policy(policy)
    bulk_min = int(fetch_cfg.get("bulk_fetch_min_symbols") or 50)
    use_bulk = bool(policy.get("bulk_fetch", True)) and live and len(symbols) >= bulk_min
    min_sym_ratio = float(policy.get("min_symbol_session_ratio") or 0.95)
    require_fresh = live and (
        fail_on_stale
        if fail_on_stale is not None
        else bool(policy.get("require_fresh_session", True))
    )

    if require_fresh:
        preflight_fresh_session(min_symbol_ratio=min_sym_ratio, fail_on_stale=True)

    all_rows: list[dict[str, Any]] = []
    gaps: list[str] = []
    market_note = ""
    as_of = ""
    trade_date = ""
    data_stale = False
    stale_notice: dict[str, str] = {}
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    failed_batches: list[str] = []
    merged_pack: dict[str, Any] | None = None

    if use_bulk:
        pack = None
        last_err = ""
        for attempt in range(retries + 1):
            try:
                pack = build_live_pack(
                    symbols=symbols,
                    indices_profile="minimal",
                    run_id=run_id,
                    enrich=False,
                    fetch_breadth=False,
                    fetch_indices=True,
                    fetch_cfg=fetch_cfg,
                )
                break
            except Exception as e:
                last_err = str(e)
                time.sleep(1.5)
        if pack is None:
            failed_batches.append(f"bulk:{symbols[0]}..{symbols[-1]}: {last_err}")
        else:
            merged_pack = pack
            attach_fact_index(pack)
            meta_pack = pack.get("meta") or {}
            as_of = meta_pack.get("as_of") or as_of
            trade_date = meta_pack.get("trade_date") or trade_date
            if meta_pack.get("data_stale"):
                data_stale = True
            if pack.get("indices"):
                parts = []
                for idx in pack["indices"]:
                    bars = idx.get("bars", {}).get("daily") or []
                    if bars:
                        parts.append(f"{idx.get('name')} {bars[-1].get('pct_chg', 0):+.2f}%")
                market_note = "；".join(parts[:4])
            flat = (pack.get("fact_index") or {}).get("flat", {})
            for inst in pack.get("symbols", []):
                row = instrument_row_from_pack(inst, flat)
                tid = theme_index.get(row["ts_code"])
                meta = inst.get("theme_meta") or {}
                row["theme"] = tid
                row["theme_meta"] = meta
                all_rows.append(row)
    else:
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            pack = None
            last_err = ""
            for attempt in range(retries + 1):
                try:
                    if live:
                        pack = build_live_pack(
                            symbols=batch,
                            indices_profile="minimal",
                            run_id=run_id,
                            enrich=False,
                            fetch_breadth=False,
                            fetch_indices=(i == 0),
                            fetch_cfg=fetch_cfg,
                        )
                    else:
                        raise RuntimeError("fixture screen not in run_screen; use tests with candidate_row_from_inst")
                    break
                except Exception as e:
                    last_err = str(e)
                    time.sleep(1.5)
            if pack is None:
                failed_batches.append(f"{batch[0]}..{batch[-1]}: {last_err}")
                continue

            merged_pack = merge_batch_into_pack(merged_pack, pack)
            attach_fact_index(pack)
            meta_pack = pack.get("meta") or {}
            as_of = meta_pack.get("as_of") or as_of
            trade_date = meta_pack.get("trade_date") or trade_date
            if meta_pack.get("data_stale"):
                data_stale = True
            if i == 0 and pack.get("indices"):
                parts = []
                for idx in pack["indices"]:
                    bars = idx.get("bars", {}).get("daily") or []
                    if bars:
                        parts.append(f"{idx.get('name')} {bars[-1].get('pct_chg', 0):+.2f}%")
                market_note = "；".join(parts[:4])

            flat = (pack.get("fact_index") or {}).get("flat", {})
            for inst in pack.get("symbols", []):
                row = instrument_row_from_pack(inst, flat)
                tid = theme_index.get(row["ts_code"])
                meta = inst.get("theme_meta") or {}
                row["theme"] = tid
                row["theme_meta"] = meta
                all_rows.append(row)
            time.sleep(sleep_sec)

    out = out_dir or (_ROOT / ".trend-trade" / "tmp")
    out.mkdir(parents=True, exist_ok=True)

    if merged_pack:
        from core.pack_facts import attach_fact_index as _attach
        from core.trade_date_util import attach_pack_trade_date_meta

        if live:
            try:
                from core.pack_enrich import _get_pro

                pro = _get_pro()
            except Exception:
                pro = None
            from core.trade_date_util import assert_pack_session_fresh

            assert_pack_session_fresh(
                merged_pack,
                fail_on_stale=require_fresh,
                min_symbol_ratio=min_sym_ratio,
            )
            stale_notice = _meta_stale_fields(merged_pack)
            _enrich_merged_pack_once(merged_pack, policy, universe_meta=universe_meta)
        _attach(merged_pack)
        pack_path = out / "screen_pack.json"
        pack_path.write_text(json.dumps(merged_pack, ensure_ascii=False, indent=2), encoding="utf-8")
        from core.init_trace import init_trace_from_pack

        trace_path = out / "screen_trace.json"
        refresh_trace = policy.get("refresh_screen_trace_each_run", True)
        if refresh_trace or not trace_path.exists() or policy.get("reset_screen_trace"):
            trace = init_trace_from_pack(merged_pack, playbook="watchlist-screen")
            trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")

    trace_file = screen_trace_path or (out / "screen_trace.json")
    screen_trace: dict[str, Any] | None = None
    if trace_file.exists():
        screen_trace = json.loads(trace_file.read_text(encoding="utf-8"))
    elif merged_pack and not data_only:
        from core.init_trace import init_trace_from_pack

        screen_trace = init_trace_from_pack(merged_pack, playbook="watchlist-screen")
        trace_file.write_text(json.dumps(screen_trace, ensure_ascii=False, indent=2), encoding="utf-8")

    if merged_pack and screen_trace and policy.get("ai_auto_rank", True) and not data_only:
        screen_trace = _maybe_auto_rank_trace(screen_trace, merged_pack, policy, trace_file)

    if screen_trace and trace_has_ai_ranks(screen_trace) and not data_only:
        from core.merge_screen_trace import merge_trace_into_rows

        all_rows = merge_trace_into_rows(all_rows, screen_trace)
        for row in all_rows:
            ts = row["ts_code"]
            sc = ((screen_trace.get("decisions") or {}).get(ts) or {}).get("screen") or {}
            if sc.get("observation_plan"):
                row["observation_plan"] = sc["observation_plan"]
            for key in (
                "score_breakdown",
                "trap_vol_reason",
                "action_rule",
                "theme_id",
                "theme_label",
                "theme_lifecycle",
                "theme_lifecycle_rule",
                "position_band",
                "price_percentile_2y",
            ):
                if sc.get(key) is not None:
                    row[key] = sc[key]
        if merged_pack:
            apply_post_ai_gates(
                all_rows,
                policy=policy,
                theme_index=theme_index,
                holdings_ts=holdings_ts,
                holding_themes=holding_themes,
                pack=merged_pack,
            )
        gaps.append("ranked_by_rule_engine_safety_rank")
    elif data_only:
        gaps.append("data_only: patch screen_trace.json then --merge-screen-trace")
    elif screen_trace and not trace_has_ai_ranks(screen_trace):
        gaps.append(
            "ai_rank_pending: fill decisions[].screen.safety_rank for ALL symbols, then --merge-screen-trace"
        )
    else:
        gaps.append(
            "ai_rank_pending: fill decisions[].screen for ALL symbols, then --merge-screen-trace"
        )

    retreat_info = detect_sector_retreat(all_rows, theme_index, policy)
    has_ranks = screen_trace is not None and trace_has_ai_ranks(screen_trace) and not data_only
    ranked = finalize_ranked_rows(all_rows, policy=policy, retreat_info=retreat_info) if has_ranks else all_rows
    max_out = int(policy.get("max_watch_pool_output") or 15)
    watch_pool = [r for r in ranked if r["action"] == "watch_pool"][:max_out]
    watch_pullback = [r for r in ranked if r["action"] == "watch_pullback"][:max_out]
    near_high = [r for r in ranked if r["action"] == "near_high_trim"][:max_out]
    avoid_n = sum(1 for r in ranked if r["action"] == "avoid")

    result: dict[str, Any] = {
        "meta": {
            "run_id": run_id,
            "as_of": as_of,
            "trade_date": trade_date,
            "data_stale": data_stale,
            "expected_trade_date": stale_notice.get("expected_trade_date") or trade_date,
            "fetch_status": (merged_pack.get("meta") or {}).get("fetch_status") if merged_pack else {},
            "fetch_messages": (merged_pack.get("meta") or {}).get("fetch_messages") if merged_pack else [],
            **(
                {k: stale_notice[k] for k in ("data_stale_headline", "data_stale_detail", "data_stale_retry", "data_stale_notice") if k in stale_notice}
            ),
            "output_label": policy.get("output_label") or "watch_pool_only",
            "screened": len(ranked),
            "symbols_requested": len(symbols),
            "ranked_by": "ai_safety_rank" if has_ranks else None,
            "policy_version": cfg["watchlist_path"].name,
            "universe_mode": universe_meta.get("universe_mode"),
            "universe_meta": universe_meta,
        },
        "market_filter": {
            "regime_note": market_note,
            "allow_new_trend_trade": retreat_info.get("allow_new_trend_trade", "yes"),
            "sector_retreats": retreat_info.get("sector_retreats") or [],
        },
        "watch_pool": watch_pool,
        "watch_pullback": watch_pullback,
        "near_high_trim": near_high,
        "avoid_count": avoid_n,
        "gaps": gaps
        + (
            [
                stale_notice.get("data_stale_notice")
                or "data_stale: 行情 K 线落后于当日收盘日，外部数据尚未刷新，请稍后重跑"
            ]
            if data_stale
            else []
        )
        + ([f"failed_batches: {len(failed_batches)}"] if failed_batches else []),
        "failed_batches": failed_batches,
        "all_ranked": ranked,
        "holdings_ts": sorted(holdings_ts),
    }
    if merged_pack:
        result["screen_pack_path"] = str(out / "screen_pack.json")
        result["screen_trace_path"] = str(out / "screen_trace.json")
        if has_ranks:
            _attach_trend_top10(
                result,
                ranked,
                policy=policy,
                watchlist_symbols=watchlist_symbols,
                pack=merged_pack,
                universe_meta=universe_meta,
            )
        if merged_pack.get("market_sentiment"):
            result["market_sentiment"] = merged_pack["market_sentiment"]
        tc = (merged_pack.get("slots") or {}).get("theme_context")
        if tc:
            result["theme_context"] = tc
        if theme_resolution:
            result["theme_resolution"] = theme_resolution
    result["risk_blocked"] = [
        {
            "ts_code": r["ts_code"],
            "name": r.get("name"),
            "risk_flags": r.get("risk_flags") or [],
            "action": r["action"],
        }
        for r in ranked
        if r.get("risk_flags") or r["action"] == "avoid"
    ]

    json_path = out / "watchlist_screen.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["_paths"] = {"json": str(json_path)}
    if result.get("trend_top10"):
        top_path = out / "trend_top10.json"
        top_path.write_text(json.dumps(result["trend_top10"], ensure_ascii=False, indent=2), encoding="utf-8")
        result["_paths"]["trend_top10"] = str(top_path)
    _write_panoramic_outputs(
        result,
        out=out,
        trace=screen_trace,
        pack=merged_pack,
        policy=policy,
        run_id=run_id,
        live=live,
    )

    if policy.get("archive_runs"):
        arch = _ROOT / ".trend-trade" / "archive" / run_id
        arch.mkdir(parents=True, exist_ok=True)
        shutil.copy2(json_path, arch / "watchlist_screen.json")
        top_p = out / "trend_top10.json"
        if top_p.exists():
            shutil.copy2(top_p, arch / "trend_top10.json")
        for name in ("screen_report.md", "screen-dossier.md", "screen-audit-sheet.md"):
            p = out / name
            if p.exists():
                shutil.copy2(p, arch / name)
        wp_dir = out / "watch_pool_analysis"
        if wp_dir.exists():
            arch_wp = arch / "watch_pool_analysis"
            if arch_wp.exists():
                shutil.rmtree(arch_wp)
            shutil.copytree(wp_dir, arch_wp)

    return result


def render_screen_report(result: dict[str, Any]) -> str:
    meta = result.get("meta") or {}
    mf = result.get("market_filter") or {}
    lines = [
        "# 自选趋势观察池报告",
        "",
        f"> **非买入推荐** · 行情交易日：`{meta.get('trade_date', '—')}` · "
        f"拉取时间：`{meta.get('as_of', '—')}` · Run：`{meta.get('run_id', '—')}`",
        "",
    ]
    if meta.get("data_stale"):
        lines.append("> **警告 · 外部行情尚未就绪（非程序用错交易日）**")
        if meta.get("data_stale_headline"):
            lines.append(f"> {meta['data_stale_headline']}")
        if meta.get("data_stale_detail"):
            lines.append(f"> {meta['data_stale_detail']}")
        if meta.get("data_stale_retry"):
            lines.append(f"> {meta['data_stale_retry']}")
        lines.append("")
    lines.extend(
        [
            "## 市场环境",
            "",
            f"- **allow_new_trend_trade**：{mf.get('allow_new_trend_trade', '—')}",
            f"- **摘要**：{mf.get('regime_note') or '—'}",
            "",
        ]
    )
    retreats = mf.get("sector_retreats") or []
    if retreats:
        lines.append("### 板块退潮")
        for r in retreats:
            lines.append(
                f"- 主题 `{r['theme']}`：{r['n']} 只样本，中位跌幅 {r['median_drop']:.2f}%"
            )
        lines.append("")
    lines.extend(["## 观察池 watch_pool（仅观察，禁止追涨）", ""])
    for r in result.get("watch_pool") or []:
        rank = r.get("safety_rank")
        lines.append(
            f"- **{r['ts_code']}** {r['name']} · safety_rank={rank} · trap={r.get('trap_risk')} · "
            f"vol_ctx={r.get('volume_context')} · 收={r.get('latest_close')} · {r.get('note')}"
        )
        if r.get("risk_flags"):
            lines.append(f"  - **风险**：{', '.join(r['risk_flags'])}")
        if r.get("downgrade_reasons"):
            lines.append(f"  - 降级：{'; '.join(r['downgrade_reasons'])}")
    lines.extend(["", "## 回踩观察 watch_pullback", ""])
    for r in result.get("watch_pullback") or []:
        lines.append(f"- **{r['ts_code']}** {r['name']} · {r.get('note')}")
    lines.extend(["", "## 近前高 near_high_trim（不追涨）", ""])
    for r in result.get("near_high_trim") or []:
        lines.append(f"- **{r['ts_code']}** {r['name']} · {r.get('note')}")
    risk_blocked = [
        r for r in (result.get("risk_blocked") or []) if r.get("risk_flags")
    ]
    if risk_blocked:
        lines.extend(["", "## 风险标的（quality / event）", ""])
        for r in risk_blocked[:30]:
            flags = ", ".join(r.get("risk_flags") or [])
            lines.append(f"- **{r['ts_code']}** {r.get('name', '')} · {flags} · action={r.get('action')}")
        if len(risk_blocked) > 30:
            lines.append(f"- … 另有 {len(risk_blocked) - 30} 只，见 watchlist_screen.json")
    lines.extend(["", f"- **avoid 数量**：{result.get('avoid_count', 0)}", ""])

    trend = result.get("trend_top10") or {}
    stocks = trend.get("stocks") or []
    if stocks:
        lines.extend(
            [
                "",
                f"## 趋势分 TOP{ trend.get('top_n', 10) }（{trend.get('scope', '—')} · 非观察池推荐）",
                "",
                f"> {trend.get('note', '')}",
                "",
                "| # | 代码 | 名称 | 分数 | 位置带 | 在自选 | 在观察池 |",
                "|---|------|------|------|--------|--------|----------|",
            ]
        )
        for s in stocks:
            lines.append(
                f"| {s.get('rank')} | {s.get('ts_code')} | {s.get('name', '')} | "
                f"{s.get('safety_rank')} | {s.get('position_band', '—')} | "
                f"{'是' if s.get('in_watchlist') else '否'} | "
                f"{'是' if s.get('in_watch_pool') else '否'} |"
            )

    lines.extend(["", "## 数据缺口 gaps", ""])
    for g in result.get("gaps") or []:
        lines.append(f"- {g}")
    lines.append("")
    lines.append("免责声明：见项目 DISCLAIMER.md。")
    return "\n".join(lines)
