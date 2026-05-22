"""Resolve 东财概念 (BK) members and elect short-term sentiment leaders (连板/涨停高度)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.market_sentiment import _parse_lianban
from core.theme_dc_cache import read_cache, write_cache
from core.theme_graph import load_themes_config

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE_RESOLUTION = _ROOT / "sample" / "theme_resolution.fixture.json"


def _latest_trade_date_from_pack(pack: dict[str, Any]) -> str | None:
    for inst in pack.get("symbols") or []:
        daily = (inst.get("bars") or {}).get("daily") or []
        if daily:
            return str(daily[-1].get("trade_date") or "")
    for idx in pack.get("indices") or []:
        daily = (idx.get("bars") or {}).get("daily") or []
        if daily:
            return str(daily[-1].get("trade_date") or "")
    return None


def _latest_trade_date_pro(pro, max_back: int = 10) -> str | None:
    from core.trade_date_util import resolve_latest_trade_date

    return resolve_latest_trade_date(pro)


def _fetch_dc_member(pro, dc_code: str, trade_date: str) -> list[dict[str, str]]:
    cached = read_cache("dc_member", trade_date, dc_code)
    if cached is not None:
        return cached
    import pandas as pd

    try:
        df = pro.dc_member(trade_date=trade_date, ts_code=dc_code)
    except Exception:
        return []
    rows: list[dict[str, str]] = []
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            con = str(r.get("con_code") or "").strip().upper()
            if con:
                rows.append(
                    {
                        "ts_code": con,
                        "name": str(r.get("name") or "").strip(),
                    }
                )
    write_cache("dc_member", trade_date, rows, dc_code)
    return rows


def _fetch_limit_up_map(pro, trade_date: str) -> dict[str, dict[str, Any]]:
    cached = read_cache("limit_list_u", trade_date)
    if cached is not None:
        return cached
    out: dict[str, dict[str, Any]] = {}
    try:
        import pandas as pd

        df = pro.limit_list_d(trade_date=trade_date, limit_type="U")
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                ts = str(row.get("ts_code") or "").strip().upper()
                if not ts:
                    continue
                pct = float(row.get("pct_chg") or 0)
                out[ts] = {
                    "lianban": _parse_lianban(row),
                    "pct_chg": pct,
                    "limit_up": True,
                    "open_times": int(row.get("open_times") or 0)
                    if pd.notna(row.get("open_times"))
                    else 0,
                }
    except Exception:
        return out
    write_cache("limit_list_u", trade_date, out)
    return out


def _fetch_dc_index_labels(pro, trade_date: str, dc_codes: list[str]) -> dict[str, str]:
    labels: dict[str, str] = {}
    cached = read_cache("dc_index", trade_date)
    if cached is None:
        try:
            df = pro.dc_index(trade_date=trade_date)
            if df is not None and not df.empty:
                cached = {
                    str(r["ts_code"]).strip().upper(): str(r.get("name") or "")
                    for _, r in df.iterrows()
                    if r.get("ts_code")
                }
                write_cache("dc_index", trade_date, cached)
        except Exception:
            cached = {}
    cached = cached or {}
    for code in dc_codes:
        labels[code] = cached.get(code) or code
    return labels


def _spec_leader_score(
    ts_code: str,
    limit_info: dict[str, Any] | None,
    pct: float | None,
) -> tuple[int, int, float]:
    """Higher is better: (连板高度, 当日涨停, 涨幅)."""
    lb = int((limit_info or {}).get("lianban") or 0)
    pct_v = float(pct) if pct is not None else -9999.0
    limit_up = 1 if (limit_info and limit_info.get("limit_up")) or pct_v >= 9.5 else 0
    if lb < 1 and limit_up:
        lb = 1
    return (lb, limit_up, pct_v)


def elect_spec_leader(
    member_codes: list[str],
    limit_map: dict[str, dict[str, Any]],
    pct_map: dict[str, float | None],
) -> tuple[str | None, dict[str, tuple[int, int, float]]]:
    if not member_codes:
        return None, {}
    scores = {
        ts: _spec_leader_score(ts, limit_map.get(ts), pct_map.get(ts)) for ts in member_codes
    }
    leader = max(member_codes, key=lambda t: scores[t])
    return leader, scores


def _load_fixture_resolution() -> dict[str, Any]:
    if not _FIXTURE_RESOLUTION.exists():
        return {}
    with _FIXTURE_RESOLUTION.open(encoding="utf-8") as f:
        return json.load(f)


def _theme_bodies(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return cfg.get("themes") or {}


def resolve_themes(
    *,
    pro: Any | None,
    trade_date: str,
    themes_cfg: dict[str, Any] | None = None,
    universe: list[str] | None = None,
    pct_map: dict[str, float | None] | None = None,
    mode: str = "live",
) -> dict[str, Any]:
    """
    Build theme_resolution:
      theme_index, themes{dc_code: {members, leaders, label}}, leader_codes, trade_date
    """
    cfg = themes_cfg or load_themes_config()
    policy = str(cfg.get("leader_policy") or "spec_lead")
    bodies = _theme_bodies(cfg)
    universe_set = {s.strip().upper() for s in (universe or []) if s}
    pct_map = pct_map or {}

    if mode != "live" or not pro:
        fix = _load_fixture_resolution()
        if fix:
            return fix
        # minimal empty resolution
        return {
            "version": cfg.get("version", "2.0.0"),
            "leader_policy": policy,
            "trade_date": trade_date,
            "theme_index": {},
            "themes": {},
            "leader_codes": [],
            "gaps": ["fixture theme_resolution missing"],
        }

    limit_map = _fetch_limit_up_map(pro, trade_date)
    dc_codes = [k for k in bodies if isinstance(bodies.get(k), dict)]
    labels = _fetch_dc_index_labels(pro, trade_date, dc_codes)

    themes_out: dict[str, Any] = {}
    theme_index: dict[str, dict[str, Any]] = {}
    leader_codes: set[str] = set()
    gaps: list[str] = []

    # priority = yaml key order
    for dc_code in dc_codes:
        body = bodies[dc_code]
        members_raw = _fetch_dc_member(pro, dc_code, trade_date)
        if not members_raw:
            gaps.append(f"dc_member empty: {dc_code}")
            continue
        member_codes = [m["ts_code"] for m in members_raw]
        leader_ts, _scores = elect_spec_leader(member_codes, limit_map, pct_map)
        if not leader_ts:
            continue
        leader_codes.add(leader_ts)
        label = body.get("label") or labels.get(dc_code) or dc_code
        members: list[dict[str, Any]] = []
        for m in members_raw:
            ts = m["ts_code"]
            role = "leader" if ts == leader_ts else "follower"
            members.append(
                {
                    "ts_code": ts,
                    "name": m.get("name") or ts,
                    "role": role,
                    "source": "spec_lead",
                }
            )
            if universe_set and ts not in universe_set:
                continue
            # primary theme: first dc in config order
            if ts not in theme_index:
                theme_index[ts] = {
                    "theme": dc_code,
                    "role": role,
                    "label": label,
                    "name": m.get("name") or ts,
                    "dc_theme_code": dc_code,
                }
        li = limit_map.get(leader_ts) or {}
        lpct = pct_map.get(leader_ts)
        if lpct is None and li:
            lpct = li.get("pct_chg")
        themes_out[dc_code] = {
            "theme_id": dc_code,
            "label": label,
            "members": members,
            "leader_ts_code": leader_ts,
            "leader_lianban": li.get("lianban", 0),
            "leader_pct_chg_1d": lpct,
            "leader_limit_up": bool(li.get("limit_up")),
            "member_count": len(member_codes),
        }

    return {
        "version": cfg.get("version", "2.0.0"),
        "leader_policy": policy,
        "trade_date": trade_date,
        "theme_index": theme_index,
        "themes": themes_out,
        "leader_codes": sorted(leader_codes),
        "gaps": gaps,
    }


def resolve_themes_for_pack(pack: dict[str, Any], pro: Any | None = None) -> dict[str, Any]:
    from core.trade_date_util import resolve_latest_trade_date

    mode = (pack.get("meta") or {}).get("mode", "fixture")
    trade_date = (pack.get("meta") or {}).get("trade_date") or _latest_trade_date_from_pack(pack)
    if not trade_date:
        trade_date = resolve_latest_trade_date(pro, pack=pack)

    from core.theme_graph import _symbol_pct_map

    pct_map = _symbol_pct_map(pack)
    universe = [s["ts_code"] for s in pack.get("symbols", [])]
    return resolve_themes(
        pro=pro if mode == "live" else None,
        trade_date=trade_date,
        universe=universe,
        pct_map=pct_map,
        mode=mode,
    )


def resolve_theme_membership_for_universe(
    pro: Any | None,
    themes_cfg: dict[str, Any],
    universe: list[str],
    *,
    mode: str = "live",
) -> dict[str, Any]:
    from core.trade_date_util import expected_trade_session_date, resolve_latest_trade_date

    trade_date = resolve_latest_trade_date(pro) if pro else expected_trade_session_date()
    return resolve_themes(
        pro=pro if mode == "live" else None,
        trade_date=trade_date,
        themes_cfg=themes_cfg,
        universe=universe,
        pct_map={},
        mode=mode,
    )


def theme_index_theme_only(resolution: dict[str, Any]) -> dict[str, str]:
    return {ts: v["theme"] for ts, v in (resolution.get("theme_index") or {}).items()}
