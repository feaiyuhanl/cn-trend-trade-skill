from __future__ import annotations

from pathlib import Path

import pytest

from core.enrich_trace import enrich_trace
from core.pack_facts import attach_fact_index
from core.pipeline import finalize_trace
from core.validate import load_json

ROOT = Path(__file__).resolve().parent.parent
FIX_PACK = ROOT / "sample" / "market_pack.sample.json"
FIX_TRACE = ROOT / "sample" / "trade_trace.sample.json"


def test_finalize_writes_reports(tmp_path: Path) -> None:
    pack = load_json(FIX_PACK)
    attach_fact_index(pack)
    trace = load_json(FIX_TRACE)

    trace_path = tmp_path / "trade_trace.json"
    pack_path = tmp_path / "market_pack.json"
    import json

    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")

    code, errs = finalize_trace(trace_path, pack_path, out_dir=tmp_path)
    assert errs == [], errs
    assert code == 0
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "decision-dossier.md").exists()
    assert (tmp_path / "audit-sheet.md").exists()

    enriched = load_json(trace_path)
    assert "resolved" in enriched
    assert enriched["resolved"]["audit"]["facts_used_count"] >= 1


def test_steps_mismatch_fails_finalize(tmp_path: Path) -> None:
    pack = load_json(FIX_PACK)
    attach_fact_index(pack)
    trace = load_json(FIX_TRACE)
    trace["steps"] = trace["steps"][:2]

    trace_path = tmp_path / "trade_trace.json"
    pack_path = tmp_path / "market_pack.json"
    import json

    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")

    code, errs = finalize_trace(trace_path, pack_path, out_dir=tmp_path)
    assert code == 1
    assert any("STEPS_MATCH_LENSES" in e or "lenses_applied" in e for e in errs)
    assert (tmp_path / "validation-errors.md").exists()


def test_enrich_resolves_facts() -> None:
    pack = load_json(FIX_PACK)
    attach_fact_index(pack)
    trace = load_json(FIX_TRACE)
    enrich_trace(trace, pack)
    resolved = trace["resolved"]["decisions"]["600519.SH"]["facts"]
    assert "symbol:600519.SH.latest_close" in resolved
    assert resolved["symbol:600519.SH.latest_close"] == pytest.approx(1688.5)
