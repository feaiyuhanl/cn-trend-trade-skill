"""Attach A-share context slots after base market pack is built."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.event_risk import evaluate_symbols as eval_events
from core.event_risk import fixture_event_risk
from core.market_sentiment import (
    fetch_market_sentiment,
    fixture_sentiment,
    merge_into_breadth,
)
from core.quality_gate import evaluate_symbol, evaluate_symbols as eval_quality
from core.quality_gate import load_watchlist_risk
from core.theme_graph import (
    build_theme_context,
    build_theme_index,
    leader_codes_for_themes,
    load_themes_config,
    theme_for_symbol,
)
from core.ts_code import normalize_symbols

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE_ENRICH = _ROOT / "sample" / "a_share_enrich.fixture.json"


def _get_pro():
    import os

    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        return None
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api()


def _themes_for_symbols(ts_codes: list[str]) -> set[str]:
    cfg = load_themes_config()
    idx = build_theme_index(cfg.get("themes") or {})
    themes: set[str] = set()
    for ts in ts_codes:
        m = idx.get(ts.strip().upper())
        if m:
            themes.add(m["theme"])
    return themes


def _fetch_missing_leaders(pack: dict[str, Any], pro) -> None:
    """Append leader instruments not yet in pack.symbols (live only)."""
    if not pro:
        return
    from core.fetch_live import _fetch_instrument, fetch_lookback

    ts_codes = [s["ts_code"] for s in pack.get("symbols", [])]
    themes = _themes_for_symbols(ts_codes)
    leaders = leader_codes_for_themes(load_themes_config().get("themes") or {}, themes)
    have = {s["ts_code"] for s in pack.get("symbols", [])}
    missing = [c for c in leaders if c not in have]
    if not missing:
        return
    lookback = fetch_lookback()
    for ts_code in missing:
        try:
            inst = _fetch_instrument(pro, ts_code, asset_type="stock", name=ts_code, lookback=lookback)
            if inst:
                pack.setdefault("symbols", []).append(inst)
        except Exception:
            pack.setdefault("meta", {}).setdefault("fetch_messages", []).append(
                f"leader fetch skip {ts_code}"
            )


def _load_fixture_enrich() -> dict[str, Any]:
    import json

    if not _FIXTURE_ENRICH.exists():
        return {}
    with _FIXTURE_ENRICH.open(encoding="utf-8") as f:
        return json.load(f)


def enrich_a_share_context(pack: dict[str, Any]) -> dict[str, Any]:
    """
    Populate pack.market_sentiment and pack.slots:
      theme_context, quality_gate, event_risk
    """
    mode = (pack.get("meta") or {}).get("mode", "fixture")
    symbols = [s["ts_code"] for s in pack.get("symbols", [])]
    pro = _get_pro() if mode == "live" else None

    if mode == "live" and pro:
        _fetch_missing_leaders(pack, pro)
        symbols = [s["ts_code"] for s in pack.get("symbols", [])]

    pack.setdefault("slots", {})

    # Theme lifecycle
    pack["slots"]["theme_context"] = build_theme_context(pack)

    # Sentiment
    if mode == "live" and pro:
        sent = fetch_market_sentiment(pro)
        if sent:
            pack["market_sentiment"] = sent
            merge_into_breadth(pack, sent)
            pack.setdefault("meta", {}).setdefault("fetch_status", {})["sentiment"] = "ok"
        else:
            pack.setdefault("meta", {}).setdefault("fetch_status", {})["sentiment"] = "skip"
    else:
        fix = _load_fixture_enrich()
        pack["market_sentiment"] = fix.get("market_sentiment") or fixture_sentiment()
        merge_into_breadth(pack, pack["market_sentiment"])
        if fix.get("slots"):
            for k, v in fix["slots"].items():
                if k != "theme_context":
                    pack["slots"][k] = v

    # Quality + events per symbol
    if mode == "live" and pro:
        pack["slots"]["quality_gate"] = eval_quality(symbols, pro=pro, pack_mode="live")
        pack["slots"]["event_risk"] = eval_events(symbols, pro=pro, pack_mode="live")
        pack.setdefault("meta", {}).setdefault("fetch_status", {})["quality_gate"] = "ok"
        pack.setdefault("meta", {}).setdefault("fetch_status", {})["event_risk"] = "ok"
    else:
        fix = _load_fixture_enrich()
        qg = fix.get("slots", {}).get("quality_gate")
        er = fix.get("slots", {}).get("event_risk")
        if not qg:
            basics = {s["ts_code"]: {"name": s.get("name", "")} for s in pack.get("symbols", [])}
            manual_all = load_watchlist_risk()
            by_code = {
                ts: evaluate_symbol(ts, pro=None, basic=basics.get(ts, {}), manual_risk=manual_all.get(ts))
                for ts in symbols
            }
            pack["slots"]["quality_gate"] = {
                "version": "1.0.0",
                "symbols": by_code,
                "blocked_ts_codes": [t for t, v in by_code.items() if v["tier"] == "block"],
                "mode": "fixture",
            }
        else:
            pack["slots"]["quality_gate"] = qg
        pack["slots"]["event_risk"] = er or fixture_event_risk(symbols)

    # Merge sector_retreats into trace-friendly market_filter hint on pack
    tc = pack["slots"]["theme_context"]
    mf_hint = {
        "sector_retreats": tc.get("sector_retreats") or [],
        "leader_block_themes": tc.get("leader_block_themes") or [],
    }
    pack.setdefault("slots", {})["market_filter_hints"] = mf_hint

    # Per-symbol role tags on instruments
    themes = load_themes_config().get("themes") or {}
    for inst in pack.get("symbols", []):
        meta = theme_for_symbol(inst["ts_code"], {"themes": themes})
        if meta:
            inst["theme_meta"] = meta

    return pack


def extra_symbols_for_assemble(symbols: list[str]) -> list[str]:
    """Leaders to include in assemble symbol list."""
    norm = normalize_symbols(symbols)
    themes = _themes_for_symbols(norm)
    leaders = leader_codes_for_themes(load_themes_config().get("themes") or {}, themes)
    return normalize_symbols(norm + leaders)
