from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = _ROOT / "schemas"


def _load_schema(name: str) -> dict:
    with (SCHEMA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(_load_schema(name))


def validate_market_pack(data: dict[str, Any]) -> list[str]:
    v = _validator("market_pack.schema.json")
    errors = sorted(v.iter_errors(data), key=lambda e: list(e.path))
    return [f"{list(e.path)}: {e.message}" for e in errors]


def validate_trade_trace(data: dict[str, Any]) -> list[str]:
    v = _validator("trade_trace.schema.json")
    errors = sorted(v.iter_errors(data), key=lambda e: list(e.path))
    msgs = [f"{list(e.path)}: {e.message}" for e in errors]
    if not errors:
        msgs.extend(_trace_semantic_checks(data))
    return msgs


def _trace_semantic_checks(data: dict[str, Any]) -> list[str]:
    msgs: list[str] = []
    decisions = data.get("decisions", {})
    if not decisions:
        msgs.append("decisions: at least one symbol decision required")
    for ts_code, dec in decisions.items():
        if dec.get("phase") == "unclear" and dec.get("entry", {}).get("action") not in (
            "wait",
            "none",
            "not_applicable",
        ):
            msgs.append(
                f"decisions.{ts_code}: phase=unclear should pair with cautious entry action"
            )
    return msgs


def _collect_pack_bar_ids(pack: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for inst in pack.get("symbols", []) + pack.get("indices", []):
        bars = inst.get("bars", {})
        for tf in ("daily", "weekly", "monthly"):
            for bar in bars.get(tf, []):
                ids.add(bar["id"])
    for b in pack.get("market_breadth") or []:
        ids.add(b["id"])
    return ids


def validate_trace_against_pack(trace: dict[str, Any], pack: dict[str, Any]) -> list[str]:
    msgs: list[str] = []
    pack_ids = _collect_pack_bar_ids(pack)
    pack_symbols = {s["ts_code"] for s in pack.get("symbols", [])}
    for step in trace.get("steps", []):
        missing = [e for e in step.get("evidence_ids", []) if e not in pack_ids]
        if missing:
            msgs.append(f"step {step.get('step')}: unknown evidence_ids {missing}")
    for ts_code in trace.get("decisions", {}):
        if ts_code not in pack_symbols:
            msgs.append(f"decisions.{ts_code}: not in pack symbols")
    if trace.get("meta", {}).get("run_id") != pack.get("meta", {}).get("run_id"):
        msgs.append("meta.run_id mismatch between trace and pack")
    return msgs


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)
