from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.pack_facts import attach_fact_index
from core.pipeline import finalize_trace
from core.recommendation_log import (
    INDEX_FILE,
    archive_finalize_run,
    extract_recommendation_summary,
    list_recommendation_runs,
    runs_missing_review,
)
from core.validate import load_json

ROOT = Path(__file__).resolve().parent.parent
FIX_PACK = ROOT / "sample" / "market_pack.sample.json"
FIX_TRACE = ROOT / "sample" / "trade_trace.sample.json"


@pytest.fixture(autouse=True)
def isolated_recommendations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rec = tmp_path / "recommendations"
    rec.mkdir()
    monkeypatch.setattr("core.recommendation_log.RECOMMENDATIONS_DIR", rec)
    monkeypatch.setattr("core.recommendation_log.INDEX_FILE", rec / "index.json")


def test_extract_summary_has_symbols() -> None:
    trace = load_json(FIX_TRACE)
    pack = load_json(FIX_PACK)
    s = extract_recommendation_summary(trace, pack)
    assert s["run_id"] == "20260519-trend-demo"
    assert len(s["symbols"]) >= 2
    assert s["has_review"] is False


def test_archive_and_index(tmp_path: Path) -> None:
    pack = load_json(FIX_PACK)
    attach_fact_index(pack)
    trace = load_json(FIX_TRACE)
    trace_path = tmp_path / "trade_trace.json"
    pack_path = tmp_path / "market_pack.json"
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")

    code, errs = finalize_trace(trace_path, pack_path, out_dir=tmp_path, no_auto_review=True)
    assert code == 0 and not errs

    arch = archive_finalize_run(trace, pack, out_dir=tmp_path, trace_path=trace_path, pack_path=pack_path)
    assert arch is not None
    assert (arch / "recommendation_summary.json").exists()
    assert INDEX_FILE.exists()

    runs = list_recommendation_runs(days=5)
    assert any(r["run_id"] == "20260519-trend-demo" for r in runs)
    gaps = runs_missing_review(days=5)
    assert any(g["run_id"] == "20260519-trend-demo" for g in gaps)
