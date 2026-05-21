"""Persist each finalized analysis run for later review."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import RECOMMENDATIONS_DIR

INDEX_FILE = RECOMMENDATIONS_DIR / "index.json"


def _as_of_date(trace: dict[str, Any]) -> str:
    raw = (trace.get("meta") or {}).get("as_of") or ""
    digits = "".join(c for c in raw if c.isdigit())
    return digits[:8] if len(digits) >= 8 else datetime.now().strftime("%Y%m%d")


def extract_recommendation_summary(
    trace: dict[str, Any], pack: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Compact per-run record for index and review brief."""
    meta = trace.get("meta") or {}
    mf = trace.get("market_filter") or {}
    names: dict[str, str] = {}
    if pack:
        for sym in (pack.get("symbols") or []):
            if isinstance(sym, dict) and sym.get("ts_code"):
                names[sym["ts_code"]] = sym.get("name") or ""

    symbols: list[dict[str, Any]] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        entry = dec.get("entry") or {}
        hr = dec.get("holding_review") or {}
        exit_p = dec.get("exit_plan") or {}
        symbols.append(
            {
                "ts_code": ts_code,
                "name": names.get(ts_code) or dec.get("name") or "",
                "phase": dec.get("phase"),
                "entry_type": entry.get("type"),
                "entry_action": entry.get("action"),
                "entry_rationale": (entry.get("rationale") or "")[:200],
                "holding_review_action": hr.get("action"),
                "holding_review_urgency": hr.get("urgency"),
                "exit_trigger": exit_p.get("primary_trigger"),
            }
        )

    positions = []
    if pack:
        positions = list((pack.get("user_context") or {}).get("positions") or [])

    return {
        "run_id": meta.get("run_id"),
        "as_of": meta.get("as_of"),
        "as_of_date": _as_of_date(trace),
        "playbook": meta.get("playbook"),
        "session_mode": meta.get("session_mode"),
        "skill_version": meta.get("skill_version"),
        "rules_version": meta.get("rules_version"),
        "has_review": bool(trace.get("review")),
        "market_filter": {
            "allow_new_trend_trade": mf.get("allow_new_trend_trade"),
            "regime_note": (mf.get("regime_note") or "")[:300],
        },
        "symbols": symbols,
        "positions_count": len(positions),
        "discipline_checked": sum(
            1 for d in (trace.get("discipline_checklist") or []) if d.get("checked")
        ),
        "discipline_total": len(trace.get("discipline_checklist") or []),
    }


def _load_index() -> dict[str, Any]:
    if not INDEX_FILE.exists():
        return {"version": "1.0.0", "runs": []}
    with INDEX_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"version": "1.0.0", "runs": []}
    data.setdefault("runs", [])
    return data


def _save_index(data: dict[str, Any]) -> None:
    RECOMMENDATIONS_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _upsert_index_entry(summary: dict[str, Any], archive_dir: Path) -> None:
    idx = _load_index()
    runs: list[dict[str, Any]] = idx["runs"]
    run_id = summary.get("run_id")
    entry = {**summary, "archive_dir": str(archive_dir.relative_to(RECOMMENDATIONS_DIR.parent))}
    runs = [r for r in runs if r.get("run_id") != run_id]
    runs.append(entry)
    runs.sort(key=lambda r: (r.get("as_of_date") or "", r.get("run_id") or ""), reverse=True)
    idx["runs"] = runs
    idx["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _save_index(idx)


def archive_finalize_run(
    trace: dict[str, Any],
    pack: dict[str, Any],
    *,
    out_dir: Path,
    trace_path: Path | None = None,
    pack_path: Path | None = None,
    skip: bool = False,
) -> Path | None:
    """Copy artifacts + write summary.json; update index."""
    if skip:
        return None

    meta = trace.get("meta") or {}
    run_id = meta.get("run_id") or f"run-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    arch = RECOMMENDATIONS_DIR / run_id
    arch.mkdir(parents=True, exist_ok=True)

    summary = extract_recommendation_summary(trace, pack)
    summary["archived_at"] = datetime.now().astimezone().isoformat(timespec="seconds")

    tp = trace_path if trace_path and trace_path.exists() else out_dir / "trade_trace.json"
    pp = pack_path if pack_path and pack_path.exists() else out_dir / "market_pack.json"
    if tp.exists():
        shutil.copy2(tp, arch / "trade_trace.json")
    if pp.exists():
        shutil.copy2(pp, arch / "market_pack.json")

    for report in ("report.md", "decision-dossier.md", "audit-sheet.md", "review-report.md"):
        src = out_dir / report
        if src.exists():
            shutil.copy2(src, arch / report)

    (arch / "recommendation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _upsert_index_entry(summary, arch)
    return arch


def list_recommendation_runs(*, days: int | None = None, date: str | None = None) -> list[dict[str, Any]]:
    idx = _load_index()
    runs = list(idx.get("runs") or [])
    if date:
        runs = [r for r in runs if r.get("as_of_date") == date]
    if days is not None and days > 0:
        runs = runs[:days]
    return runs


def load_archived_trace(run_id: str) -> dict[str, Any] | None:
    path = RECOMMENDATIONS_DIR / run_id / "trade_trace.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def runs_missing_review(*, days: int = 10) -> list[dict[str, Any]]:
    """Runs archived without trace.review (gaps to fill)."""
    return [r for r in list_recommendation_runs(days=days) if not r.get("has_review")]


def list_recommendation_dates() -> list[str]:
    dates = sorted({r.get("as_of_date") for r in _load_index().get("runs") or [] if r.get("as_of_date")})
    return dates
