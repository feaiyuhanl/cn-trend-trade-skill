"""Quality gate: ST, chronic loss, blacklist — block junk stocks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config" / "quality_gate.yaml"
_BLACKLIST_PATH = _ROOT / "config" / "quality_blacklist.yaml"
_WATCHLIST_RISK_PATH = _ROOT / "config" / "watchlist_risk.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_quality_config() -> dict[str, Any]:
    return _load_yaml(_CONFIG_PATH)


def load_blacklist() -> set[str]:
    data = _load_yaml(_BLACKLIST_PATH)
    return {str(t).strip().upper() for t in (data.get("ts_codes") or [])}


def load_watchlist_risk() -> dict[str, dict[str, Any]]:
    data = _load_yaml(_WATCHLIST_RISK_PATH)
    symbols = data.get("symbols") or {}
    return {str(k).strip().upper(): v for k, v in symbols.items()}


def _is_st_name(name: str, patterns: list[str]) -> bool:
    n = name.upper()
    for p in patterns:
        p = p.replace("*", "")
        if p and p in n:
            return True
    return "ST" in n


def _fetch_basic_map(pro, ts_codes: list[str]) -> dict[str, dict[str, Any]]:
    import pandas as pd

    out: dict[str, dict[str, Any]] = {}
    try:
        df = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,area,industry,list_date",
        )
        if df is None or df.empty:
            return out
        wanted = set(ts_codes)
        for _, row in df.iterrows():
            ts = str(row["ts_code"]).strip().upper()
            if ts in wanted:
                out[ts] = {"name": str(row.get("name") or ""), "industry": str(row.get("industry") or "")}
    except Exception:
        pass
    return out


def _net_profit_from_row(row) -> float | None:
    import pandas as pd

    for key in ("net_profit", "netprofit", "n_income_attr_p", "n_income"):
        v = row.get(key)
        if v is None or (hasattr(pd, "isna") and pd.isna(v)):
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _fetch_fina_loss_years(pro, ts_code: str, years: int = 3) -> int:
    """Count recent periods with net profit < 0."""
    try:
        df = pro.fina_indicator(ts_code=ts_code, limit=years * 4)
        if df is None or df.empty:
            return 0
        neg = 0
        for _, row in df.iterrows():
            np_val = _net_profit_from_row(row)
            if np_val is not None and np_val < 0:
                neg += 1
        return neg
    except Exception:
        return 0


def evaluate_symbol(
    ts_code: str,
    *,
    pro=None,
    basic: dict[str, Any] | None = None,
    cfg: dict[str, Any] | None = None,
    manual_risk: dict[str, Any] | None = None,
    skip_chronic_loss: bool = False,
    rate_limiter=None,
) -> dict[str, Any]:
    cfg = cfg or load_quality_config()
    ts = ts_code.strip().upper()
    blacklist = load_blacklist()
    risk_flags: list[str] = []
    reasons: list[str] = []

    name = (basic or {}).get("name", "")
    tier = "ok"

    if ts in blacklist:
        risk_flags.append("blacklist")
        reasons.append("quality_blacklist")
        tier = "block"

    st_cfg = cfg.get("st") or {}
    if st_cfg.get("block_st") and name and _is_st_name(name, st_cfg.get("name_patterns") or ["ST"]):
        risk_flags.append("st")
        reasons.append("ST/*ST")
        tier = "block"

    if manual_risk:
        for f in manual_risk.get("risk_flags") or []:
            if f not in risk_flags:
                risk_flags.append(str(f))
        if manual_risk.get("note"):
            reasons.append(str(manual_risk["note"]))
        if "st_risk" in risk_flags or "chronic_loss" in risk_flags or "fraud" in risk_flags:
            tier = "block"

    cl_cfg = cfg.get("chronic_loss") or {}
    neg_years = 0
    if pro and cl_cfg.get("block") and not skip_chronic_loss:
        if rate_limiter is not None:
            rate_limiter.wait()
        neg_years = _fetch_fina_loss_years(pro, ts, cl_cfg.get("min_years_negative", 2) + 1)
        if neg_years >= int(cl_cfg.get("min_years_negative", 2)):
            if "chronic_loss" not in risk_flags:
                risk_flags.append("chronic_loss")
            reasons.append(f"近年净利为负期数≥{neg_years}")
            tier = "block"

    if tier == "ok" and risk_flags:
        tier = "warn"

    return {
        "ts_code": ts,
        "name": name,
        "tier": tier,
        "risk_flags": risk_flags,
        "reasons": reasons,
        "neg_profit_periods": neg_years,
        "block_entry": tier == "block",
    }


def evaluate_symbols(
    ts_codes: list[str],
    *,
    pro=None,
    pack_mode: str = "live",
    skip_chronic_loss: bool = False,
    fetch_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_quality_config()
    manual_all = load_watchlist_risk()
    basics: dict[str, dict[str, Any]] = {}
    if pro:
        basics = _fetch_basic_map(pro, ts_codes)

    parallel = bool(pro) and len(ts_codes) > 1
    fetch_cfg = fetch_cfg or {}
    if parallel and fetch_cfg.get("parallel_enabled", True):
        from core.tushare_rate_limit import MinuteRateLimiter, load_fetch_concurrency_config, parallel_map

        fcfg = {**load_fetch_concurrency_config(), **fetch_cfg}
        limiter = MinuteRateLimiter(int(fcfg.get("calls_per_minute") or 450))

        def _eval_one(ts: str) -> dict[str, Any]:
            return evaluate_symbol(
                ts,
                pro=pro,
                basic=basics.get(ts.strip().upper()),
                cfg=cfg,
                manual_risk=manual_all.get(ts.strip().upper()),
                skip_chronic_loss=skip_chronic_loss,
                rate_limiter=limiter,
            )

        by_code = parallel_map(
            [t.strip().upper() for t in ts_codes],
            _eval_one,
            max_workers=int(fcfg.get("max_workers") or 16),
            rate_limiter=None,
        )
        by_code = {k: v for k, v in by_code.items() if v is not None}
    else:
        by_code = {}
        for ts in ts_codes:
            ts = ts.strip().upper()
            by_code[ts] = evaluate_symbol(
                ts,
                pro=pro,
                basic=basics.get(ts),
                cfg=cfg,
                manual_risk=manual_all.get(ts),
                skip_chronic_loss=skip_chronic_loss,
            )

    blocked = [t for t, v in by_code.items() if v["tier"] == "block"]
    return {
        "version": cfg.get("version", "1.0.0"),
        "symbols": by_code,
        "blocked_ts_codes": blocked,
        "mode": pack_mode,
    }
