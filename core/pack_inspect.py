"""Print pack facts to stdout (Agent reads via Shell; no temp scripts)."""

from __future__ import annotations

import json
from typing import Any


def _symbol_name(pack: dict[str, Any], ts_code: str) -> str:
    for inst in pack.get("symbols") or []:
        if inst.get("ts_code") == ts_code:
            return str(inst.get("name") or "")
    return ""


def format_holdings(pack: dict[str, Any]) -> str:
    idx = pack.get("fact_index") or {}
    holdings = idx.get("holdings") or {}
    positions = (pack.get("user_context") or {}).get("positions") or []
    lines = ["# holdings (from market_pack)"]
    if not holdings and not positions:
        lines.append("(none)")
        return "\n".join(lines) + "\n"

    for pos in positions:
        ts = str(pos.get("ts_code", "")).strip().upper()
        h = holdings.get(ts) or {}
        name = _symbol_name(pack, ts)
        lines.append(f"\n## {ts} {name}".rstrip())
        for key in ("cost", "shares", "stop_price", "entry_date", "theme"):
            if pos.get(key) is not None:
                lines.append(f"- {key}: {pos[key]}")
        if h:
            for key in ("latest_close", "vs_cost_pct"):
                if h.get(key) is not None:
                    lines.append(f"- {key}: {h[key]}")
    for ts, h in sorted(holdings.items()):
        if any(str(p.get("ts_code", "")).strip().upper() == ts for p in positions):
            continue
        name = _symbol_name(pack, ts)
        lines.append(f"\n## {ts} {name}".rstrip())
        lines.append(json.dumps(h, ensure_ascii=False, indent=2))
    return "\n".join(lines) + "\n"


def _latest_daily_pct(inst: dict[str, Any]) -> float | None:
    bars = inst.get("bars")
    if isinstance(bars, dict):
        daily = bars.get("daily") or bars.get("D") or []
        if daily and isinstance(daily[0], dict):
            pct = daily[0].get("pct_chg")
            return float(pct) if pct is not None else None
    if isinstance(bars, list):
        for bar in bars:
            if isinstance(bar, dict) and bar.get("timeframe") == "D" and bar.get("pct_chg") is not None:
                return float(bar["pct_chg"])
    return None


def format_symbols(pack: dict[str, Any]) -> str:
    lines = ["# symbols"]
    for inst in pack.get("symbols") or []:
        ts = inst.get("ts_code", "")
        name = inst.get("name", "")
        close = inst.get("latest_close")
        pct = _latest_daily_pct(inst)
        extra = f" close={close}" if close is not None else ""
        if pct is not None:
            extra += f" pct_chg={pct}"
        lines.append(f"- {ts} {name}{extra}")
    return "\n".join(lines) + "\n"


def format_facts(pack: dict[str, Any], *, ts_code: str | None = None, prefix: str | None = None) -> str:
    flat = (pack.get("fact_index") or {}).get("flat") or {}
    lines = ["# fact_index.flat"]
    if not flat:
        lines.append("(empty — run assemble with positions for holdings facts)")
        return "\n".join(lines) + "\n"

    keys = sorted(flat.keys())
    if ts_code:
        ts = ts_code.strip().upper()
        keys = [k for k in keys if f":{ts}" in k or k.startswith(f"symbol:{ts}")]
    if prefix:
        keys = [k for k in keys if k.startswith(prefix)]

    for k in keys[:500]:
        v = flat[k]
        lines.append(f"- {k}: {v}")
    if len(keys) > 500:
        lines.append(f"... ({len(keys) - 500} more keys omitted)")
    return "\n".join(lines) + "\n"


def _fmt_bar_line(bar: dict[str, Any]) -> str:
    td = bar.get("trade_date", "")
    return (
        f"  {td} O={bar.get('open')} H={bar.get('high')} L={bar.get('low')} "
        f"C={bar.get('close')} pct={bar.get('pct_chg')} vol={bar.get('vol')}"
    )


def format_screen_brief(pack: dict[str, Any], *, ts_code: str | None = None) -> str:
    """Per-symbol brief for AI watchlist ranking (objective numbers from pack)."""
    flat = (pack.get("fact_index") or {}).get("flat") or {}
    lines = ["# screen-brief (AI ranking input; numbers from pack only)"]
    symbols = pack.get("symbols") or []
    if ts_code:
        ts = ts_code.strip().upper()
        symbols = [s for s in symbols if str(s.get("ts_code", "")).strip().upper() == ts]

    for inst in symbols:
        ts = str(inst.get("ts_code", "")).strip().upper()
        name = inst.get("name", "")
        lines.append(f"\n## {ts} {name}")
        hints = inst.get("derived_hints") or {}
        hint_keys = sorted(k for k in hints if not k.startswith("_"))
        for k in hint_keys:
            v = hints[k]
            if isinstance(v, (int, float, bool, str)):
                lines.append(f"- derived_hints.{k}: {v}")
            elif isinstance(v, list):
                lines.append(f"- derived_hints.{k}: {v[:5]}")
        for prefix in (f"symbol:{ts}.fundamentals.", f"symbol:{ts}.quality.", f"symbol:{ts}.event."):
            for k in sorted(flat.keys()):
                if k.startswith(prefix):
                    lines.append(f"- {k}: {flat[k]}")
        theme = (inst.get("theme_meta") or {}).get("theme_id") or (inst.get("theme_meta") or {}).get("theme")
        if theme:
            lines.append(f"- theme: {theme}")
            role = (inst.get("theme_meta") or {}).get("role")
            if role:
                lines.append(f"- theme_role: {role}")
        bars = inst.get("bars") or {}
        weekly = bars.get("weekly") or []
        monthly = bars.get("monthly") or []
        if weekly:
            lines.append("- recent_weekly_bars (last 8):")
            for b in weekly[-8:]:
                lines.append(_fmt_bar_line(b))
        if monthly:
            lines.append("- recent_monthly_bars (last 6):")
            for b in monthly[-6:]:
                lines.append(_fmt_bar_line(b))
    return "\n".join(lines) + "\n"


def dispatch_show_pack(pack: dict[str, Any], section: str, *, ts_code: str | None = None) -> str:
    section = (section or "holdings").strip().lower()
    if section in ("holdings", "holding", "positions"):
        return format_holdings(pack)
    if section in ("symbols", "symbol"):
        return format_symbols(pack)
    if section in ("facts", "fact", "flat"):
        return format_facts(pack, ts_code=ts_code)
    if section in ("screen-brief", "screen_brief", "screen"):
        return format_screen_brief(pack, ts_code=ts_code)
    raise ValueError(
        f"Unknown --show-pack section: {section} (use holdings|symbols|facts|screen-brief)"
    )
