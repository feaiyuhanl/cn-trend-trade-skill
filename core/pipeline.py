"""Pipeline: enrich → validate → render all reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.assemble import save_trace
from core.enrich_trace import enrich_trace
from core.report_render import (
    write_audit_sheet,
    write_decision_dossier,
    write_report,
    write_review_report,
)
from core.validate import (
    load_json,
    validate_trade_trace,
    validate_trace_against_pack,
)


def finalize_trace(
    trace_path: Path,
    pack_path: Path,
    *,
    out_dir: Path | None = None,
) -> tuple[int, list[str]]:
    """Enrich trace, validate, render reports. Returns (exit_code, error_messages)."""
    trace = load_json(trace_path)
    pack = load_json(pack_path)

    enrich_trace(trace, pack)
    save_trace(trace, trace_path)

    errs = validate_trade_trace(trace)
    errs.extend(validate_trace_against_pack(trace, pack))
    if errs:
        out = out_dir or trace_path.parent
        out.mkdir(parents=True, exist_ok=True)
        err_path = out / "validation-errors.md"
        lines = ["# 校验失败", "", "修正 trade_trace 后重新运行 finalize。", ""]
        for e in errs:
            lines.append(f"- {e}")
        err_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1, errs

    target = out_dir or trace_path.parent
    target.mkdir(parents=True, exist_ok=True)
    write_report(trace, pack, target / "report.md")
    write_decision_dossier(trace, pack, target / "decision-dossier.md")
    write_audit_sheet(trace, pack, target / "audit-sheet.md")
    if trace.get("review"):
        write_review_report(trace, pack, target / "review-report.md")
    return 0, []
