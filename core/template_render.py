"""Jinja2 report rendering (P2)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.paths import REPORTS_TEMPLATES


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(REPORTS_TEMPLATES)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(name: str, **context: Any) -> str:
    return _env().get_template(name).render(**context)
