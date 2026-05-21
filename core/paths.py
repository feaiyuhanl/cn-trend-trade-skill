"""Repository path constants."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "contracts" / "schemas"
REPORTS_TEMPLATES = ROOT / "engine" / "report" / "templates"
SAMPLE_DIR = ROOT / "sample"
SKILL_DIR = ROOT / "skill"
REFERENCE_DIR = SKILL_DIR / "reference"
ADAPTERS_DIR = ROOT / "adapters"
CONFIG_DIR = ROOT / "config"
DATA_ROOT = ROOT / ".trend-trade"
RECOMMENDATIONS_DIR = DATA_ROOT / "recommendations"
HOLDINGS_DIR = DATA_ROOT / "holdings"
JOURNAL_DIR = DATA_ROOT / "journal"
