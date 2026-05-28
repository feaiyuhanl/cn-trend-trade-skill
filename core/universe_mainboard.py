"""Mainboard (主板) universe fetch and quality/liquidity prefilter."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config" / "universe_mainboard.yaml"
_CACHE_PATH = _ROOT / ".trend-trade" / "cache" / "stock_basic_mainboard.json"


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_universe_config() -> dict[str, Any]:
    return _load_yaml(_CONFIG_PATH)


def _is_mainboard_ts_code(ts_code: str, cfg: dict[str, Any]) -> bool:
    ts = ts_code.strip().upper()
    if ts.endswith(".BJ"):
        return False
    if ".BJ" in (cfg.get("board_filter") or {}).get("exclude_exchanges", []):
        if ts.endswith(".BJ"):
            return False
    code = ts.split(".")[0]
    prefixes = (cfg.get("board_filter") or {}).get("include_prefixes") or []
    if not any(code.startswith(p) for p in prefixes):
        return False
    if code.startswith("688") or code.startswith("300"):
        return False
    return True


def _is_st_name(name: str) -> bool:
    n = (name or "").upper()
    return "ST" in n


def _list_days_ok(list_date: str, min_days: int) -> bool:
    if not list_date or len(str(list_date)) < 8:
        return True
    try:
        ld = datetime.strptime(str(list_date)[:8], "%Y%m%d")
        return (datetime.now() - ld).days >= min_days
    except ValueError:
        return True


def _filter_mainboard_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cfg = load_universe_config()
    bf = cfg.get("board_filter") or {}
    min_list = int(bf.get("min_list_days") or 0)
    qcfg = cfg.get("quality_prefilter") or {}
    from core.quality_gate import load_blacklist, load_watchlist_risk

    blacklist = load_blacklist()
    manual = load_watchlist_risk()
    out: list[dict[str, Any]] = []
    for row in rows:
        ts = str(row["ts_code"]).strip().upper()
        name = str(row.get("name") or "")
        if not _is_mainboard_ts_code(ts, cfg):
            continue
        if qcfg.get("block_st", True) and _is_st_name(name):
            continue
        if not _list_days_ok(str(row.get("list_date") or ""), min_list):
            continue
        if qcfg.get("block_blacklist", True) and ts in blacklist:
            continue
        risk = manual.get(ts) or {}
        flags = set(risk.get("risk_flags") or [])
        if qcfg.get("block_fraud_flags", True) and ("fraud" in flags or "st_risk" in flags):
            continue
        out.append(
            {
                "ts_code": ts,
                "name": name,
                "industry": str(row.get("industry") or ""),
                "list_date": str(row.get("list_date") or ""),
            }
        )
    return out


def _load_stock_basic_cache() -> list[dict[str, Any]] | None:
    if not _CACHE_PATH.exists():
        return None
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        rows = data.get("rows") if isinstance(data, dict) else data
        return rows if isinstance(rows, list) and rows else None
    except Exception:
        return None


def _save_stock_basic_cache(rows: list[dict[str, Any]]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cached_at": datetime.now().isoformat(), "rows": rows}
    _CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_mainboard_stock_basic(pro) -> list[dict[str, Any]]:
    """All listed mainboard symbols from stock_basic (with retry + disk cache)."""
    raw_rows: list[dict[str, Any]] = []
    last_err = ""
    for attempt in range(3):
        try:
            df = pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,symbol,name,area,industry,list_date,market",
            )
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    raw_rows.append(
                        {
                            "ts_code": str(row["ts_code"]).strip().upper(),
                            "name": str(row.get("name") or ""),
                            "industry": str(row.get("industry") or ""),
                            "list_date": str(row.get("list_date") or ""),
                        }
                    )
                break
            last_err = "stock_basic empty"
        except Exception as e:
            last_err = str(e)
        if attempt < 2:
            time.sleep(30 * (attempt + 1))

    if raw_rows:
        out = _filter_mainboard_rows(raw_rows)
        if out:
            _save_stock_basic_cache(raw_rows)
        return out

    cached = _load_stock_basic_cache()
    if cached:
        return _filter_mainboard_rows(cached)

    # Fallback: build universe from daily_basic when stock_basic is rate-limited
    try:
        from core.trade_date_util import latest_open_trade_date

        td = latest_open_trade_date(pro)
        if td:
            df = pro.daily_basic(trade_date=td, fields="ts_code")
            if df is not None and not df.empty:
                raw_rows = [
                    {"ts_code": str(row["ts_code"]).strip().upper(), "name": "", "industry": "", "list_date": ""}
                    for _, row in df.iterrows()
                ]
                out = _filter_mainboard_rows(raw_rows)
                if out:
                    return out
    except Exception:
        pass
    return []


def _liquidity_amount_mn(row) -> float:
    """Daily turnover in 万元.

    Tushare daily_basic no longer ships ``amount``; estimate from circ_mv (万元)
    × turnover_rate (%). Legacy ``amount`` on daily bars is 千元 → /10 for 万元.
    """
    import pandas as pd

    def _f(key: str) -> float | None:
        v = row.get(key)
        if v is None or (hasattr(pd, "isna") and pd.isna(v)):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    amt = _f("amount")
    if amt is not None and amt > 0:
        # daily.amount 千元; daily_basic.amount (if ever returned) is also 千元
        return amt / 10.0
    circ = _f("circ_mv")
    tr = _f("turnover_rate")
    if circ is not None and tr is not None and circ > 0 and tr > 0:
        return circ * tr / 100.0
    return 0.0


def apply_liquidity_prefilter(
    pro,
    candidates: list[dict[str, Any]],
    *,
    cfg: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Filter and cap by daily_basic amount; return ts_code list + meta."""
    cfg = cfg or load_universe_config()
    liq = cfg.get("liquidity_prefilter") or {}
    min_amt = float(liq.get("min_amount_mn") or 0)
    max_c_raw = liq.get("max_candidates")
    max_c = int(max_c_raw) if max_c_raw is not None else 500
    meta: dict[str, Any] = {
        "candidates_before_liquidity": len(candidates),
        "min_amount_mn": min_amt,
        "max_candidates": max_c,
    }
    if not candidates or not pro:
        cap = len(candidates) if max_c <= 0 else min(len(candidates), max_c)
        return [c["ts_code"] for c in candidates[:cap]], meta

    from core.trade_date_util import latest_open_trade_date

    trade_date = latest_open_trade_date(pro)
    meta["trade_date"] = trade_date
    wanted = {c["ts_code"] for c in candidates}
    scored: list[tuple[str, float]] = []
    df = None
    for attempt in range(3):
        try:
            df = pro.daily_basic(
                trade_date=trade_date,
                fields="ts_code,circ_mv,turnover_rate,total_mv",
            )
            if df is not None and not df.empty:
                break
        except Exception as e:
            meta["liquidity_error"] = str(e)
        if attempt < 2:
            time.sleep(20 * (attempt + 1))
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            ts = str(row["ts_code"]).strip().upper()
            if ts not in wanted:
                continue
            amt = _liquidity_amount_mn(row)
            if min_amt > 0 and amt < min_amt:
                continue
            scored.append((ts, amt))
    elif min_amt <= 0:
        cap = len(candidates) if max_c <= 0 else min(len(candidates), max_c)
        return [c["ts_code"] for c in candidates[:cap]], meta
    else:
        meta["liquidity_fallback"] = "daily_basic empty — cap without liquidity sort"
        cap = len(candidates) if max_c <= 0 else min(len(candidates), max_c)
        return [c["ts_code"] for c in candidates[:cap]], meta

    scored.sort(key=lambda x: -x[1])
    meta["after_liquidity"] = len(scored)
    if max_c <= 0:
        return [ts for ts, _ in scored], meta
    return [ts for ts, _ in scored[:max_c]], meta


def apply_chronic_loss_prefilter(
    pro,
    ts_codes: list[str],
    *,
    cfg: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Remove tier=block symbols (chronic loss, ST re-check, blacklist)."""
    cfg = cfg or load_universe_config()
    qcfg = cfg.get("quality_prefilter") or {}
    meta: dict[str, Any] = {"before": len(ts_codes)}
    if not qcfg.get("block_chronic_loss") or not ts_codes or not pro:
        meta["skipped"] = True
        return list(ts_codes), meta

    from core.quality_gate import evaluate_symbols

    fetch_cfg = {}
    try:
        from core.tushare_rate_limit import load_fetch_concurrency_config

        fetch_cfg = load_fetch_concurrency_config()
    except Exception:
        pass
    qg = evaluate_symbols(ts_codes, pro=pro, fetch_cfg=fetch_cfg)
    kept: list[str] = []
    removed: list[dict[str, Any]] = []
    for ts in ts_codes:
        rec = (qg.get("symbols") or {}).get(ts) or {}
        if rec.get("tier") == "block":
            removed.append(
                {
                    "ts_code": ts,
                    "name": rec.get("name") or "",
                    "risk_flags": rec.get("risk_flags") or [],
                    "reasons": rec.get("reasons") or [],
                }
            )
        else:
            kept.append(ts)
    meta["after_chronic_loss"] = len(kept)
    meta["removed_count"] = len(removed)
    meta["removed_sample"] = removed[:30]
    return kept, meta


def fetch_mainboard_universe(pro) -> dict[str, Any]:
    """Full pipeline: board filter → optional liquidity → chronic loss."""
    cfg = load_universe_config()
    basic = fetch_mainboard_stock_basic(pro)
    liq = cfg.get("liquidity_prefilter") or {}
    min_amt = float(liq.get("min_amount_mn") or 0)
    max_c = int(liq.get("max_candidates") or 0)

    if min_amt <= 0 and max_c <= 0:
        ts_list = [c["ts_code"] for c in basic]
        liq_meta = {
            "liquidity_skipped": "full_universe_after_board_st_filter",
            "after_liquidity": len(ts_list),
            "min_amount_mn": min_amt,
            "max_candidates": max_c,
        }
    else:
        ts_list, liq_meta = apply_liquidity_prefilter(pro, basic, cfg=cfg)
    cl_meta: dict[str, Any] = {}
    if ts_list and pro:
        ts_list, cl_meta = apply_chronic_loss_prefilter(pro, ts_list)
    return {
        "ts_codes": ts_list,
        "meta": {
            "source": "mainboard",
            "board_count": len(basic),
            **liq_meta,
            **({"chronic_loss_filter": cl_meta} if cl_meta else {}),
            "final_count": len(ts_list),
            "final_ts_codes": ts_list,
        },
    }


def export_mainboard_symbols_yaml(out_path: Path | None = None) -> dict[str, Any]:
    """Fetch mainboard universe and write config/mainboard_symbols.yaml snapshot."""
    from core.pack_enrich import _get_pro

    out_path = out_path or (_ROOT / "config" / "mainboard_symbols.yaml")
    cfg = load_universe_config()
    pro = _get_pro()
    universe = fetch_mainboard_universe(pro)
    ts_codes = list(universe.get("ts_codes") or [])
    meta = dict(universe.get("meta") or {})

    name_map: dict[str, str] = {}
    basic_rows = fetch_mainboard_stock_basic(pro)
    for row in basic_rows:
        name_map[row["ts_code"]] = row.get("name") or ""

    payload: dict[str, Any] = {
        "version": cfg.get("version") or "1.0.0",
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "source": "tushare mainboard universe export",
        "filters_applied": {
            "board": "沪市+深市主板（600/601/603/605/000/001/002/003）",
            "block_st": bool((cfg.get("quality_prefilter") or {}).get("block_st")),
            "block_blacklist": bool((cfg.get("quality_prefilter") or {}).get("block_blacklist")),
            "block_fraud_flags": bool((cfg.get("quality_prefilter") or {}).get("block_fraud_flags")),
            "block_chronic_loss": bool((cfg.get("quality_prefilter") or {}).get("block_chronic_loss")),
            "min_list_days": (cfg.get("board_filter") or {}).get("min_list_days"),
            "min_amount_mn": (cfg.get("liquidity_prefilter") or {}).get("min_amount_mn"),
            "max_candidates": (cfg.get("liquidity_prefilter") or {}).get("max_candidates"),
        },
        "universe_meta": meta,
        "symbols_flat": ts_codes,
        "symbols_detail": [
            {"ts_code": ts, "name": name_map.get(ts, "")} for ts in ts_codes
        ],
    }
    import yaml

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        yaml.dump(payload, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return {"path": str(out_path), "count": len(ts_codes), "meta": meta}
