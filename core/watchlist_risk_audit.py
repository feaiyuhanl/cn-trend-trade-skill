"""Watchlist risk audit: quality_gate + event_risk + concept flags — script output only."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# 续亏/首亏 + 小市值 → 优先剔除
_TIER_A_FORECAST = {"续亏", "首亏"}
_CONCEPT_MV_YI_MAX = 80.0
_CONCEPT_PE_MIN = 120.0


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_watchlist_names(watchlist_path: Path | None = None) -> dict[str, str]:
    path = watchlist_path or (_ROOT / "config" / "watchlist.yaml")
    data = _load_yaml(path)
    return {
        str(s["ts_code"]).strip().upper(): str(s.get("name") or "")
        for s in (data.get("watchlist") or {}).get("stocks") or []
        if s.get("ts_code")
    }


def _latest_trade_date(pro) -> str | None:
    try:
        df = pro.trade_cal(
            exchange="SSE",
            start_date=(datetime.now().replace(year=datetime.now().year - 1)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
            is_open="1",
        )
        if df is None or df.empty:
            return None
        return str(df.iloc[-1]["cal_date"])
    except Exception:
        return None


def _fetch_mv_map(pro, ts_codes: list[str]) -> dict[str, dict[str, Any]]:
    import pandas as pd

    out: dict[str, dict[str, Any]] = {}
    trade_date = _latest_trade_date(pro)
    if not trade_date:
        return out
    wanted = set(ts_codes)
    try:
        df = pro.daily_basic(
            trade_date=trade_date,
            fields="ts_code,total_mv,circ_mv,pe_ttm,pb,turnover_rate",
        )
        if df is None or df.empty:
            return out
        for _, row in df.iterrows():
            ts = str(row["ts_code"]).strip().upper()
            if ts not in wanted:
                continue
            mv_wan = row.get("total_mv")
            mv_yi = None
            if mv_wan is not None and not pd.isna(mv_wan):
                mv_yi = round(float(mv_wan) / 10000.0, 1)
            pe = row.get("pe_ttm")
            try:
                pe_f = round(float(pe), 2) if pe is not None and not pd.isna(pe) else None
            except (TypeError, ValueError):
                pe_f = None
            out[ts] = {
                "total_mv_yi": mv_yi,
                "pe_ttm": pe_f,
                "pb": row.get("pb"),
            }
    except Exception:
        pass
    return out


def _forecast_type(notes: list[str]) -> str:
    for n in notes:
        if "业绩预告" in str(n):
            return str(n).replace("业绩预告", "").strip()
    return ""


def _classify_symbol(
    ts: str,
    *,
    name: str,
    qrec: dict[str, Any],
    erec: dict[str, Any],
    mv: dict[str, Any],
) -> dict[str, Any]:
    flags: list[str] = list(qrec.get("risk_flags") or [])
    event_flags = list(erec.get("event_flags") or [])
    flags.extend(event_flags)
    reasons = list(qrec.get("reasons") or [])
    fc_type = _forecast_type(erec.get("notes") or [])
    mv_yi = mv.get("total_mv_yi")
    pe = mv.get("pe_ttm")

    tier = "ok"
    tags: list[str] = []

    if qrec.get("tier") == "block":
        tier = "block"
        tags.append("质量兜底")
    elif "st" in flags or "ST" in name.upper():
        tier = "block"
        tags.append("ST风险")
    elif fc_type in _TIER_A_FORECAST:
        tier = "high"
        tags.append(f"业绩{fc_type}")
        if mv_yi is not None and mv_yi < _CONCEPT_MV_YI_MAX:
            tags.append("小市值")
    elif erec.get("block_entry") or "forecast_loss" in event_flags:
        tier = "warn"
        tags.append(f"业绩{fc_type}" if fc_type else "业绩预警")
    elif mv_yi is not None and mv_yi < _CONCEPT_MV_YI_MAX:
        if pe is None or (isinstance(pe, (int, float)) and pe > _CONCEPT_PE_MIN):
            tier = "concept"
            tags.append("小市值高估值")

    return {
        "ts_code": ts,
        "name": name,
        "tier": tier,
        "tags": tags,
        "risk_flags": list(dict.fromkeys(flags)),
        "reasons": reasons,
        "event_flags": event_flags,
        "forecast_type": fc_type,
        "total_mv_yi": mv_yi,
        "pe_ttm": pe,
        "qg_tier": qrec.get("tier"),
        "block_entry": bool(qrec.get("block_entry") or erec.get("block_entry")),
    }


def run_audit(
    *,
    symbols: list[str] | None = None,
    watchlist_path: Path | None = None,
    live: bool = True,
    out_dir: Path | None = None,
    archive: bool = True,
) -> dict[str, Any]:
    from core.event_risk import evaluate_symbols as eval_events
    from core.quality_gate import evaluate_symbols as eval_quality
    from core.screen_watchlist import load_watchlist_config

    cfg = load_watchlist_config(watchlist_path)
    ts_codes = [s.strip().upper() for s in (symbols or cfg["symbols_flat"])]
    names = load_watchlist_names(watchlist_path or cfg.get("watchlist_path"))

    pro = None
    pack_mode = "fixture"
    if live:
        import os

        import tushare as ts

        token = os.environ.get("TUSHARE_TOKEN") or os.environ.get("TUSHARE_PRO_TOKEN")
        if not token:
            raise RuntimeError("TUSHARE_TOKEN required for --audit-watchlist (or use --fixture)")
        pro = ts.pro_api(token)
        pack_mode = "live"

    qg = eval_quality(ts_codes, pro=pro, pack_mode=pack_mode)
    ev = eval_events(ts_codes, pro=pro, pack_mode=pack_mode)
    mv_map = _fetch_mv_map(pro, ts_codes) if pro else {}

    rows: list[dict[str, Any]] = []
    for ts in ts_codes:
        qrec = (qg.get("symbols") or {}).get(ts) or {}
        erec = (ev.get("symbols") or {}).get(ts) or {}
        display = qrec.get("name") or names.get(ts, "")
        rows.append(
            _classify_symbol(
                ts,
                name=display,
                qrec=qrec,
                erec=erec,
                mv=mv_map.get(ts) or {},
            )
        )

    by_tier: dict[str, list[dict[str, Any]]] = {
        "block": [],
        "high": [],
        "warn": [],
        "concept": [],
        "ok": [],
    }
    for r in rows:
        by_tier.setdefault(r["tier"], []).append(r)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    result: dict[str, Any] = {
        "meta": {
            "run_id": run_id,
            "as_of": datetime.now().astimezone().isoformat(timespec="seconds"),
            "symbols": len(ts_codes),
            "mode": pack_mode,
        },
        "summary": {
            "block": len(by_tier["block"]),
            "high": len(by_tier["high"]),
            "warn": len(by_tier["warn"]),
            "concept": len(by_tier["concept"]),
            "ok": len(by_tier["ok"]),
        },
        "tiers": by_tier,
        "quality_blocked": qg.get("blocked_ts_codes") or [],
        "event_blocked": ev.get("blocked_ts_codes") or [],
    }

    out = out_dir or (_ROOT / ".trend-trade" / "tmp")
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "watchlist_risk_audit.json"
    report_path = out / "watchlist_risk_report.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_risk_report(result), encoding="utf-8")

    if archive and pack_mode == "live":
        arch = _ROOT / ".trend-trade" / "archive" / run_id
        arch.mkdir(parents=True, exist_ok=True)
        shutil.copy2(json_path, arch / "watchlist_risk_audit.json")
        shutil.copy2(report_path, arch / "watchlist_risk_report.md")

    result["_paths"] = {"json": str(json_path), "report": str(report_path)}
    return result


def _fmt_row(r: dict[str, Any]) -> str:
    parts = [f"**{r['ts_code']}** {r['name']}"]
    if r.get("total_mv_yi") is not None:
        parts.append(f"市值≈{r['total_mv_yi']}亿")
    if r.get("pe_ttm") is not None:
        parts.append(f"PE≈{r['pe_ttm']}")
    if r.get("forecast_type"):
        parts.append(f"预告{r['forecast_type']}")
    if r.get("risk_flags"):
        parts.append(f"风险={','.join(r['risk_flags'])}")
    if r.get("tags"):
        parts.append(f"标签={','.join(r['tags'])}")
    return " · ".join(parts)


def render_risk_report(result: dict[str, Any]) -> str:
    """List-only markdown — safe in Cursor chat (no tables)."""
    meta = result.get("meta") or {}
    summary = result.get("summary") or {}
    tiers = result.get("tiers") or {}

    lines = [
        "# 自选风险审计报告",
        "",
        f"> 数据截至：`{meta.get('as_of', '—')}` · Run：`{meta.get('run_id', '—')}` · "
        f"共 {meta.get('symbols', 0)} 只 · 模式 `{meta.get('mode', '—')}`",
        "",
        "## 摘要",
        "",
        f"- **质量 block（ST/常年亏损/黑名单）**：{summary.get('block', 0)} 只",
        f"- **优先警惕（续亏/首亏+小盘）**：{summary.get('high', 0)} 只",
        f"- **业绩预警（预减等）**：{summary.get('warn', 0)} 只",
        f"- **题材炒作嫌疑（小市值+高估值）**：{summary.get('concept', 0)} 只",
        f"- **暂未命中**：{summary.get('ok', 0)} 只",
        "",
    ]

    sections = [
        ("block", "第一档：质量兜底（禁止新开仓）"),
        ("high", "第二档：优先警惕（续亏/首亏，退市与 ST 风险更高）"),
        ("warn", "第三档：业绩预警（预减/略减等，不宜趋势新开仓）"),
        ("concept", "第四档：题材炒作嫌疑（小市值 + 极高 PE）"),
    ]
    for key, title in sections:
        items = tiers.get(key) or []
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("- （无）")
        else:
            for r in sorted(items, key=lambda x: (x.get("total_mv_yi") or 9999, x["ts_code"])):
                lines.append(f"- {_fmt_row(r)}")
        lines.append("")

    high_names = [r["name"] for r in tiers.get("high") or []][:8]
    if high_names:
        lines.extend(
            [
                "## 建议",
                "",
                f"- 若需精简自选，优先复核：{'、'.join(high_names)}",
                "- 可将确认标的写入 `config/watchlist_risk.yaml` 以便筛选时自动标红",
                "",
            ]
        )

    lines.append("免责声明：见项目 DISCLAIMER.md。")
    return "\n".join(lines)
