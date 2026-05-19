from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import SKILL_VERSION
from core.pack_facts import attach_fact_index
from core.rules_engine import load_rules_config

_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PACK = _ROOT / "sample" / "market_pack.sample.json"
TMP_DIR = _ROOT / ".trend-trade" / "tmp"
OUT_PACK = TMP_DIR / "market_pack.json"
OUT_TRACE = TMP_DIR / "trade_trace.json"


def _load_user_context(
    *,
    session_mode: str | None,
    positions_file: Path | None,
    portfolio_equity: float | None,
    risk_pct: float | None,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "session_mode": session_mode or "mixed",
        "positions": [],
        "portfolio": {},
        "user_notes": "",
    }
    if positions_file and positions_file.exists():
        with positions_file.open(encoding="utf-8") as f:
            file_ctx = json.load(f)
        ctx.update(
            {
                k: v
                for k, v in file_ctx.items()
                if k in ("session_mode", "positions", "portfolio", "user_notes")
            }
        )
    if portfolio_equity is not None:
        ctx.setdefault("portfolio", {})["total_equity"] = portfolio_equity
    if risk_pct is not None:
        ctx.setdefault("portfolio", {})["risk_per_trade_pct"] = risk_pct
    if session_mode:
        ctx["session_mode"] = session_mode
    return ctx


def _filter_symbols(pack: dict[str, Any], symbols: list[str] | None) -> dict[str, Any]:
    if not symbols:
        return pack
    from core.ts_code import normalize_symbols

    wanted = set(normalize_symbols(symbols))
    pack["symbols"] = [s for s in pack["symbols"] if s["ts_code"] in wanted]
    if not pack["symbols"]:
        raise ValueError(f"No data for symbols: {sorted(wanted)}")
    pack["meta"]["symbols_requested"] = sorted(wanted)
    return pack


def assemble(
    *,
    use_fixture: bool = True,
    run_id: str | None = None,
    symbols: list[str] | None = None,
    session_mode: str | None = None,
    positions_file: Path | None = None,
    portfolio_equity: float | None = None,
    risk_pct: float | None = None,
    indices_profile: str = "comprehensive",
) -> Path:
    """Build market_pack.json from fixture or tushare live fetch."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if use_fixture:
        with FIXTURE_PACK.open(encoding="utf-8") as f:
            pack = json.load(f)
        pack = _filter_symbols(pack, symbols)
    else:
        if not symbols:
            raise ValueError("--live requires --symbols (comma-separated ts_code)")
        from adapters.tushare_market import apply_live

        pack = apply_live(
            symbols=symbols,
            indices_profile=indices_profile,
            run_id=run_id,
        )

    pack["user_context"] = _load_user_context(
        session_mode=session_mode,
        positions_file=positions_file,
        portfolio_equity=portfolio_equity,
        risk_pct=risk_pct,
    )
    pack["meta"]["indices_profile"] = indices_profile
    if run_id:
        pack["meta"]["run_id"] = run_id
    pack["meta"]["skill_version"] = SKILL_VERSION
    pack["meta"]["as_of"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    mode = pack["meta"].get("mode", "fixture")
    pack["meta"]["rules_profile"] = "production" if mode == "live" else "development"
    from adapters.runner import apply_adapters

    pack = apply_adapters(pack)
    rules = load_rules_config()
    attach_fact_index(pack, rules_version=rules.get("version"))

    with OUT_PACK.open("w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)
    return OUT_PACK


def copy_fixture_trace() -> Path:
    src = _ROOT / "sample" / "trade_trace.sample.json"
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, OUT_TRACE)
    return OUT_TRACE


def save_trace(trace: dict[str, Any], path: Path | None = None) -> Path:
    out = path or OUT_TRACE
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)
    return out
