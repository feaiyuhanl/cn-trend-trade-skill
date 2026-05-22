from __future__ import annotations

from core.enrich_trace import enrich_trace
from core.pack_facts import attach_fact_index
from core.report_render import render_review_report
from core.validate import load_json

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
FIX_PACK = ROOT / "sample" / "market_pack.sample.json"
FIX_TRACE = ROOT / "sample" / "trade_trace.sample.json"


def test_review_report_renders():
    pack = load_json(FIX_PACK)
    attach_fact_index(pack)
    trace = load_json(FIX_TRACE)
    trace["review"] = {
        "planned_vs_actual": [
            {
                "ts_code": "600519.SH",
                "planned": "hold",
                "actual": "hold",
                "deviation": "none",
            }
        ],
        "phase_accuracy": "correct",
        "discipline_violations": [],
        "lessons": ["reduced 环境下控制加仓"],
        "next_improvements": ["[EVIDENCE_TRACEABILITY] 补齐 breadth 数据"],
        "skill_dimensions": {
            "MF_PHASE_ENTRY": {
                "status": "ok",
                "reflection": "reduced 与 entry 一致",
                "action": "维持",
            }
        },
    }
    enrich_trace(trace, pack)
    text = render_review_report(trace, pack)
    assert "阶段判断准确度" in text
    assert "correct" in text
    assert "reduced" in text
    assert "SKILL 八维自评" in text
    assert "MF_PHASE_ENTRY" in text