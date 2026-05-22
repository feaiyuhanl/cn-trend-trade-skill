"""Theme graph: leaders, followers, lifecycle stage, sector strength rank."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_THEMES_PATH = _ROOT / "config" / "themes.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_themes_config(path: Path | None = None) -> dict[str, Any]:
    return _load_yaml(path or _THEMES_PATH)


def parse_theme_members(theme_id: str, body: dict[str, Any]) -> list[dict[str, Any]]:
    """Legacy v1: leaders/members in yaml. v2 themes have no static members."""
    out: list[dict[str, Any]] = []
    leaders = body.get("leaders") or []
    for ld in leaders:
        if isinstance(ld, str):
            out.append({"ts_code": ld.strip().upper(), "name": "", "role": "leader"})
        else:
            out.append(
                {
                    "ts_code": str(ld["ts_code"]).strip().upper(),
                    "name": ld.get("name", ""),
                    "role": "leader",
                }
            )
    members = body.get("members") or body.get("ts_codes") or []
    for m in members:
        if isinstance(m, str):
            ts = m.split("#")[0].strip().upper()
            out.append({"ts_code": ts, "name": "", "role": "follower"})
        else:
            out.append(
                {
                    "ts_code": str(m["ts_code"]).strip().upper(),
                    "name": m.get("name", ""),
                    "role": m.get("role") or "follower",
                }
            )
    seen: dict[str, dict[str, Any]] = {}
    for row in out:
        ts = row["ts_code"]
        if ts not in seen or row["role"] == "leader":
            seen[ts] = row
    return list(seen.values())


def build_theme_index(
    themes: dict[str, Any],
    resolution: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """ts_code -> {theme, role, label}. Prefer runtime theme_resolution."""
    if resolution and resolution.get("theme_index"):
        return dict(resolution["theme_index"])
    idx: dict[str, dict[str, Any]] = {}
    for theme_id, body in (themes or {}).items():
        if not isinstance(body, dict):
            continue
        label = body.get("label", theme_id)
        for row in parse_theme_members(theme_id, body):
            ts = row["ts_code"]
            idx[ts] = {
                "theme": theme_id,
                "role": row["role"],
                "label": label,
                "name": row.get("name", ""),
            }
    return idx


def leader_codes_for_themes(
    themes: dict[str, Any],
    theme_ids: set[str],
    resolution: dict[str, Any] | None = None,
) -> list[str]:
    if resolution:
        codes: list[str] = []
        for tid in theme_ids:
            tdata = (resolution.get("themes") or {}).get(tid) or {}
            leader = tdata.get("leader_ts_code")
            if leader:
                codes.append(str(leader).strip().upper())
        return sorted(set(codes))
    codes = []
    for tid in theme_ids:
        body = themes.get(tid) or {}
        for row in parse_theme_members(tid, body):
            if row["role"] == "leader":
                codes.append(row["ts_code"])
    return sorted(set(codes))


def _symbol_pct_map(pack: dict[str, Any]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for inst in pack.get("symbols", []):
        ts = inst["ts_code"]
        daily = (inst.get("bars") or {}).get("daily") or []
        if daily:
            out[ts] = float(daily[-1].get("pct_chg") or 0)
        else:
            out[ts] = None
    return out


def _is_limit_down(pct: float | None, ts_code: str) -> bool:
    if pct is None:
        return False
    lim = -19.8 if ts_code.startswith("300") or ts_code.startswith("688") else -9.8
    return pct <= lim


def _infer_lifecycle(
    *,
    down_frac: float,
    median_pct: float,
    leader_pct: float | None,
    leader_limit_down: bool,
    up_frac: float,
) -> str:
    if leader_limit_down or (leader_pct is not None and leader_pct <= -7) or (
        down_frac >= 0.5 and median_pct <= -2
    ):
        return "retreat"
    if up_frac >= 0.6 and leader_pct is not None and leader_pct > 0:
        return "consensus"
    if leader_pct is not None and leader_pct > 1 and up_frac < 0.45:
        return "divergence"
    if leader_pct is not None and leader_pct > 0 and up_frac >= 0.4:
        return "ferment"
    if leader_pct is not None and leader_pct > 3:
        return "new"
    return "divergence"


def assess_theme_from_members(
    theme_id: str,
    label: str,
    members: list[dict[str, Any]],
    pct_map: dict[str, float | None],
) -> dict[str, Any]:
    leader_rows = [m for m in members if m.get("role") == "leader"]
    follower_rows = [m for m in members if m.get("role") != "leader"]

    leader_stats: list[dict[str, Any]] = []
    for ld in leader_rows:
        ts = ld["ts_code"]
        pct = pct_map.get(ts)
        leader_stats.append(
            {
                "ts_code": ts,
                "name": ld.get("name") or ts,
                "pct_chg_1d": pct,
                "limit_down": _is_limit_down(pct, ts),
                "lianban": ld.get("lianban"),
                "leader_source": ld.get("source", "spec_lead"),
            }
        )

    sample_pcts: list[float] = []
    for m in members:
        p = pct_map.get(m["ts_code"])
        if p is not None:
            sample_pcts.append(p)

    down = [p for p in sample_pcts if p < 0]
    up = [p for p in sample_pcts if p > 0]
    down_frac = len(down) / len(sample_pcts) if sample_pcts else 0.0
    up_frac = len(up) / len(sample_pcts) if sample_pcts else 0.0
    median_pct = 0.0
    if sample_pcts:
        s = sorted(sample_pcts)
        median_pct = s[len(s) // 2]

    leader_pct = leader_stats[0]["pct_chg_1d"] if leader_stats else None
    leader_limit_down = any(x["limit_down"] for x in leader_stats)

    stage = _infer_lifecycle(
        down_frac=down_frac,
        median_pct=median_pct,
        leader_pct=leader_pct,
        leader_limit_down=leader_limit_down,
        up_frac=up_frac,
    )

    strength_score = median_pct
    allow = "yes"
    if stage == "retreat" or leader_limit_down:
        allow = "no"
    elif stage in ("divergence", "consensus") and leader_pct is not None and leader_pct < -3:
        allow = "reduced"

    return {
        "theme_id": theme_id,
        "label": label,
        "lifecycle_stage": stage,
        "allow_new_trend_trade": allow,
        "leaders": leader_stats,
        "sample_n": len(sample_pcts),
        "down_frac": round(down_frac, 4),
        "up_frac": round(up_frac, 4),
        "median_pct_1d": round(median_pct, 4),
        "strength_score": round(strength_score, 4),
        "leader_limit_down": leader_limit_down,
        "follower_count": len(follower_rows),
    }


def assess_theme(
    theme_id: str,
    body: dict[str, Any],
    pack: dict[str, Any],
    pct_map: dict[str, float | None],
) -> dict[str, Any]:
    members = parse_theme_members(theme_id, body)
    return assess_theme_from_members(theme_id, body.get("label", theme_id), members, pct_map)


def build_theme_context(pack: dict[str, Any], themes_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = themes_cfg or load_themes_config()
    themes = cfg.get("themes") or {}
    pct_map = _symbol_pct_map(pack)
    resolution = (pack.get("slots") or {}).get("theme_resolution")
    theme_index = build_theme_index(themes, resolution)

    assessments: list[dict[str, Any]] = []
    if resolution and resolution.get("themes"):
        for theme_id, tdata in resolution["themes"].items():
            members = tdata.get("members") or []
            if not any(m["ts_code"] in pct_map for m in members):
                continue
            for m in members:
                if m.get("role") == "leader":
                    m.setdefault("lianban", tdata.get("leader_lianban"))
                    m.setdefault("source", "spec_lead")
            assessments.append(
                assess_theme_from_members(
                    theme_id,
                    tdata.get("label", theme_id),
                    members,
                    pct_map,
                )
            )
    else:
        for theme_id, body in themes.items():
            if not isinstance(body, dict):
                continue
            member_codes = [m["ts_code"] for m in parse_theme_members(theme_id, body)]
            if not any(c in pct_map for c in member_codes):
                continue
            assessments.append(assess_theme(theme_id, body, pack, pct_map))

    assessments.sort(key=lambda x: -x["strength_score"])
    for i, a in enumerate(assessments):
        a["strength_rank"] = i + 1

    leader_blocks = [
        a["theme_id"]
        for a in assessments
        if a.get("leader_limit_down") or a.get("allow_new_trend_trade") == "no"
    ]

    return {
        "version": cfg.get("version", "2.0.0"),
        "leader_policy": cfg.get("leader_policy", "spec_lead"),
        "theme_index": {ts: v for ts, v in theme_index.items()},
        "themes": assessments,
        "sector_retreats": [
            {
                "theme": a["theme_id"],
                "label": a["label"],
                "median_drop": a["median_pct_1d"],
                "lifecycle_stage": a["lifecycle_stage"],
                "leader_limit_down": a["leader_limit_down"],
            }
            for a in assessments
            if a["lifecycle_stage"] == "retreat"
        ],
        "leader_block_themes": leader_blocks,
    }


def theme_for_symbol(
    ts_code: str,
    themes: dict[str, Any] | None = None,
    resolution: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    idx = build_theme_index((themes or load_themes_config()).get("themes") or {}, resolution)
    return idx.get(ts_code.strip().upper())
