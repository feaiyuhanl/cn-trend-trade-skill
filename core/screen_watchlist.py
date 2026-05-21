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
    "forbid_output_words": ["买入推荐", "优先推荐", "优先买入"],
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


def score_symbol_base(ts: str, name: str, h: dict[str, Any], *, pct_1d: float | None) -> dict[str, Any]:
    """Score from derived_hints; action is pre-policy label."""
    struct = h.get("structure", "insufficient_data")
    above20 = h.get("price_above_ma20")
    above60 = h.get("price_above_ma60")
    s20 = h.get("ma20_slope_daily") or 0
    s60d = h.get("ma60_slope_daily") or 0
    s60w = h.get("ma60_slope_weekly") or 0
    vol_r = h.get("vol_ratio_5_20") or 1.0
    dist52 = h.get("distance_from_52w_high_pct")
    atr_pct = h.get("atr14_pct") or 0
    close = h.get("_close")

    score = 0
    tags: list[str] = []

    if struct == "higher_highs_higher_lows":
        score += 4
        tags.append("HH/HL")
    elif struct == "range_bound":
        score += 1
        tags.append("盘整")
    elif struct == "lower_highs_lower_lows":
        score -= 4
        tags.append("LH/LL")
    else:
        tags.append("数据不足")

    if above20:
        score += 2
    else:
        tags.append("跌破MA20")
    if above60:
        score += 2
    if s20 > 0:
        score += 2
    if s60d > 0:
        score += 1
    if s60w > 0:
        score += 1
    if 0.85 <= vol_r <= 1.8:
        score += 1
    elif vol_r > 2.2:
        score -= 1
        tags.append("放量过热")
    if dist52 is not None:
        if dist52 > -8:
            score -= 1
            tags.append("近52周高")
        elif -25 <= dist52 <= -8:
            score += 1
    if atr_pct > 0.1:
        score -= 1
        tags.append("高波动")
    if pct_1d is not None and pct_1d <= -4.0:
        score -= 3
        tags.append("1日大跌")
    elif pct_1d is not None and pct_1d <= -2.0:
        score -= 1
        tags.append("1日偏弱")

    if struct == "lower_highs_lower_lows" or not above20:
        phase = "reversal"
    elif struct == "higher_highs_higher_lows" and above20 and s20 > 0:
        if vol_r > 2.0 and dist52 is not None and dist52 > -6:
            phase = "exhaustion"
        elif not above60 or s60w < 0 or (dist52 is not None and dist52 < -18):
            phase = "startup"
        else:
            phase = "acceleration"
    else:
        phase = "unclear"

    if phase == "reversal":
        action = "avoid"
        note = "结构偏弱或跌破 MA20，不符合趋势观察"
    elif phase == "exhaustion":
        action = "wait"
        note = "加速末段或放量过热；仅观察，不追涨"
    elif phase == "startup":
        action = "watch_pullback"
        note = "趋势修复中；仅观察，等回踩 MA20 缩量企稳"
    elif phase == "acceleration":
        if dist52 is not None and dist52 > -5:
            action = "near_high_trim"
            note = "趋势尚可但近前高；观察池内不追涨，等回踩"
        else:
            action = "watch_pool"
            note = "多周期多头结构；列入观察池，突破/回踩确认后再考虑"
    else:
        action = "wait"
        note = "信号不清晰，观望"

    return {
        "ts_code": ts,
        "name": name,
        "score": score,
        "phase": phase,
        "action": action,
        "note": note,
        "tags": tags,
        "latest_close": close,
        "pct_chg_1d": pct_1d,
        "structure": struct,
        "price_above_ma20": above20,
        "vol_ratio_5_20": vol_r,
        "distance_from_52w_high_pct": dist52,
        "ma20_value": h.get("ma20_value"),
        "atr14_pct": atr_pct,
        "theme": None,
        "downgrade_reasons": [],
    }


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
    pools.sort(key=lambda x: (-x["score"], x["ts_code"]))
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
    ts = inst["ts_code"]
    h = dict(inst.get("derived_hints") or {})
    h["_close"] = flat.get(f"symbol:{ts}.latest_close")
    daily = inst.get("bars", {}).get("daily") or []
    pct_1d = float(daily[-1]["pct_chg"]) if daily else None
    return score_symbol_base(ts, inst.get("name", ts), h, pct_1d=pct_1d)


def run_screen(
    *,
    symbols: list[str] | None = None,
    watchlist_path: Path | None = None,
    live: bool = True,
    max_symbols: int | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    from core.fetch_live import build_live_pack
    from core.pack_facts import attach_fact_index

    cfg = load_watchlist_config(watchlist_path)
    policy = cfg["policy"]
    symbols = symbols or cfg["symbols_flat"]
    if max_symbols is not None:
        symbols = symbols[:max_symbols]
    elif policy.get("max_symbols_per_run"):
        symbols = symbols[: int(policy["max_symbols_per_run"])]

    theme_index = build_theme_index(cfg["themes"])
    holdings_ts = holding_ts_codes(cfg["holdings"])
    # themes of current holdings
    holding_themes = {theme_index.get(ts) for ts in holdings_ts} - {None}

    batch_size = int(policy.get("batch_size") or 25)
    retries = int(policy.get("batch_retry") or 2)
    sleep_sec = float(policy.get("batch_sleep_sec") or 0.8)

    all_rows: list[dict[str, Any]] = []
    gaps: list[str] = []
    market_note = ""
    as_of = ""
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    failed_batches: list[str] = []
    last_pack: dict[str, Any] | None = None

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        pack = None
        last_err = ""
        for attempt in range(retries + 1):
            try:
                if live:
                    pack = build_live_pack(symbols=batch, indices_profile="minimal", run_id=run_id)
                else:
                    raise RuntimeError("fixture screen not in run_screen; use tests with score_symbol_base")
                break
            except Exception as e:
                last_err = str(e)
                time.sleep(1.5)
        if pack is None:
            failed_batches.append(f"{batch[0]}..{batch[-1]}: {last_err}")
            continue

        last_pack = pack
        attach_fact_index(pack)
        as_of = (pack.get("meta") or {}).get("as_of") or as_of
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
            meta = (inst.get("theme_meta") or {})
            row = apply_policy_row(
                row,
                policy=policy,
                theme_id=tid,
                holdings_ts=holdings_ts,
                holding_themes=holding_themes,
            )
            row["theme_meta"] = meta
            row = apply_pack_gates(row, pack)
            all_rows.append(row)
        time.sleep(sleep_sec)

    retreat_info = detect_sector_retreat(all_rows, theme_index, policy)
    apply_sector_retreat_downgrade(all_rows, retreat_info)
    cap_watch_pool_by_theme(all_rows, int(policy.get("max_per_theme") or 2))

    ranked = sorted(all_rows, key=lambda r: (-r["score"], r["ts_code"]))
    max_out = int(policy.get("max_watch_pool_output") or 15)
    watch_pool = [r for r in ranked if r["action"] == "watch_pool"][:max_out]
    watch_pullback = [r for r in ranked if r["action"] == "watch_pullback"][:max_out]
    near_high = [r for r in ranked if r["action"] == "near_high_trim"][:max_out]
    avoid_n = sum(1 for r in ranked if r["action"] == "avoid")

    result: dict[str, Any] = {
        "meta": {
            "run_id": run_id,
            "as_of": as_of,
            "output_label": policy.get("output_label") or "watch_pool_only",
            "screened": len(ranked),
            "symbols_requested": len(symbols),
            "policy_version": cfg["watchlist_path"].name,
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
        "gaps": gaps + ([f"failed_batches: {len(failed_batches)}"] if failed_batches else []),
        "failed_batches": failed_batches,
        "all_ranked": ranked,
        "holdings_ts": sorted(holdings_ts),
    }
    if last_pack:
        if last_pack.get("market_sentiment"):
            result["market_sentiment"] = last_pack["market_sentiment"]
        tc = (last_pack.get("slots") or {}).get("theme_context")
        if tc:
            result["theme_context"] = tc
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

    out = out_dir or (_ROOT / ".trend-trade" / "tmp")
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "watchlist_screen.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = out / "screen_report.md"
    report_path.write_text(render_screen_report(result), encoding="utf-8")

    if policy.get("archive_runs"):
        arch = _ROOT / ".trend-trade" / "archive" / run_id
        arch.mkdir(parents=True, exist_ok=True)
        shutil.copy2(json_path, arch / "watchlist_screen.json")
        shutil.copy2(report_path, arch / "screen_report.md")

    result["_paths"] = {"json": str(json_path), "report": str(report_path)}
    return result


def render_screen_report(result: dict[str, Any]) -> str:
    meta = result.get("meta") or {}
    mf = result.get("market_filter") or {}
    lines = [
        "# 自选趋势观察池报告",
        "",
        f"> **非买入推荐** · 数据截至：`{meta.get('as_of', '—')}` · Run：`{meta.get('run_id', '—')}`",
        "",
        "## 市场环境",
        "",
        f"- **allow_new_trend_trade**：{mf.get('allow_new_trend_trade', '—')}",
        f"- **摘要**：{mf.get('regime_note') or '—'}",
        "",
    ]
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
        lines.append(
            f"- **{r['ts_code']}** {r['name']} · 分={r['score']} · 阶段={r['phase']} · "
            f"收={r.get('latest_close')} · MA20={r.get('ma20_value')} · {r.get('note')}"
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
    lines.extend(
        [
            "",
            f"- **avoid 数量**：{result.get('avoid_count', 0)}",
            "",
            "## 数据缺口 gaps",
            "",
        ]
    )
    for g in result.get("gaps") or []:
        lines.append(f"- {g}")
    lines.append("")
    lines.append("免责声明：见项目 DISCLAIMER.md。")
    return "\n".join(lines)
