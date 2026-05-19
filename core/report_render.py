"""Render reports from trace via Jinja2 templates — no new numbers invented."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.report_context import (
    build_audit_context,
    build_dossier_context,
    build_review_context,
    build_trade_context,
)
from core.template_render import render_template


def render_trade_report(trace: dict[str, Any], pack: dict[str, Any] | None = None) -> str:
    return render_template("trade-report.md.j2", **build_trade_context(trace, pack))


def render_decision_dossier(trace: dict[str, Any], pack: dict[str, Any] | None = None) -> str:
    return render_template("decision-dossier.md.j2", **build_dossier_context(trace, pack))


def render_audit_sheet(trace: dict[str, Any], pack: dict[str, Any] | None = None) -> str:
    return render_template("audit-sheet.md.j2", **build_audit_context(trace, pack))


def render_review_report(trace: dict[str, Any], pack: dict[str, Any] | None = None) -> str:
    if not trace.get("review"):
        raise ValueError("trace.review is required for review report")
    return render_template("review-report.md.j2", **build_review_context(trace, pack))


def write_report(trace: dict[str, Any], pack: dict[str, Any] | None, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_trade_report(trace, pack), encoding="utf-8")
    return path


def write_decision_dossier(trace: dict[str, Any], pack: dict[str, Any] | None, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_decision_dossier(trace, pack), encoding="utf-8")
    return path


def write_audit_sheet(trace: dict[str, Any], pack: dict[str, Any] | None, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_audit_sheet(trace, pack), encoding="utf-8")
    return path


def write_review_report(trace: dict[str, Any], pack: dict[str, Any] | None, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_review_report(trace, pack), encoding="utf-8")
    return path
