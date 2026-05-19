from __future__ import annotations

import re

_SUFFIX_RULES = (
    (re.compile(r"^(688\d{3})"), r"\1.SH"),
    (re.compile(r"^(6\d{5})"), r"\1.SH"),
    (re.compile(r"^(0\d{5})"), r"\1.SZ"),
    (re.compile(r"^(3\d{5})"), r"\1.SZ"),
    (re.compile(r"^(8\d{5})"), r"\1.BJ"),
    (re.compile(r"^(4\d{5})"), r"\1.BJ"),
)


def normalize_ts_code(raw: str) -> str:
    s = raw.strip().upper()
    if "." in s:
        return s
    for pat, repl in _SUFFIX_RULES:
        m = pat.match(s)
        if m:
            return pat.sub(repl, m.group(1))
    raise ValueError(f"Cannot infer exchange suffix for: {raw}")


def normalize_symbols(symbols: list[str]) -> list[str]:
    return [normalize_ts_code(x) for x in symbols]
