"""Repository path constants (P3 layout)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "contracts" / "schemas"
if not SCHEMA_DIR.is_dir():
    SCHEMA_DIR = ROOT / "schemas"
REPORTS_TEMPLATES = ROOT / "reports" / "templates"
SKILL_DIR = ROOT / "skill"
ADAPTERS_DIR = ROOT / "adapters"
