"""Mid-low historical position filter (新大陆模式) — config-driven gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config" / "position_filter.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_position_config() -> dict[str, Any]:
    return _load_yaml(_CONFIG_PATH)


def _thresholds(cfg: dict[str, Any]) -> dict[str, float]:
    t = cfg.get("thresholds") or {}
    return {
        "near_high_weekly_pct": float(t.get("near_high_weekly_pct", -12)),
        "near_high_monthly_pct": float(t.get("near_high_monthly_pct", -12)),
        "near_high_52w_pct": float(t.get("near_high_52w_pct", -8)),
        "far_from_high_weekly_pct": float(t.get("far_from_high_weekly_pct", -20)),
    }


def is_near_high(hints: dict[str, Any], cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_position_config()
    thr = _thresholds(cfg)
    dist_w = hints.get("distance_from_weekly_high_pct")
    dist_m = hints.get("distance_from_monthly_high_pct")
    dist_52 = hints.get("distance_from_52w_high_pct")
    if dist_w is not None and dist_w > thr["near_high_weekly_pct"]:
        return True
    if dist_m is not None and dist_m > thr["near_high_monthly_pct"]:
        return True
    if dist_52 is not None and dist_52 > thr["near_high_52w_pct"]:
        return True
    return False


def classify_position_band(hints: dict[str, Any], cfg: dict[str, Any] | None = None) -> str:
    """Return mid_low | mid_high | near_high | below_base | unknown."""
    cfg = cfg or load_position_config()
    band = cfg.get("mid_low_band") or {}
    pct = hints.get("price_percentile_2y")
    dist_52 = hints.get("distance_from_52w_high_pct")
    dist_w = hints.get("distance_from_weekly_high_pct")

    if pct is not None and pct < float(band.get("min_percentile_2y", 25)):
        return "below_base"
    if is_near_high(hints, cfg):
        return "near_high"
    if pct is not None:
        lo = float(band.get("min_percentile_2y", 25))
        hi = float(band.get("max_percentile_2y", 60))
        if lo <= pct <= hi:
            if dist_52 is not None and dist_52 <= float(band.get("max_52w_high_proximity_pct", -10)):
                if dist_w is not None and dist_w <= float(band.get("min_weekly_high_distance_pct", -15)):
                    return "mid_low"
    if pct is not None and pct > float(band.get("max_percentile_2y", 60)):
        return "mid_high"
    if dist_w is not None and dist_w < _thresholds(cfg)["far_from_high_weekly_pct"]:
        return "mid_low"
    return "unknown"


def blocks_watch_pool(
    hints: dict[str, Any],
    *,
    struct: str = "",
    above_ma20: bool | None = None,
    cfg: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Return (blocked, reason) for watch_pool entry."""
    cfg = cfg or load_position_config()
    gate = cfg.get("watch_pool_gate") or {}
    band_cfg = cfg.get("mid_low_band") or {}

    pct = hints.get("price_percentile_2y")
    dist_52 = hints.get("distance_from_52w_high_pct")
    dist_w = hints.get("distance_from_weekly_high_pct")

    if pct is not None and pct > float(gate.get("reject_if_percentile_2y_above", 65)):
        return True, f"2年区间分位 {pct:.0f}% 偏高(>{gate.get('reject_if_percentile_2y_above', 65)}%)"
    if dist_52 is not None and dist_52 > float(gate.get("reject_if_52w_high_within_pct", -8)):
        return True, f"距52周高 {dist_52:.1f}% 过近(>{gate.get('reject_if_52w_high_within_pct', -8)}%)"
    if dist_w is not None and dist_w > float(gate.get("reject_if_weekly_high_within_pct", -12)):
        return True, f"距周前高 {dist_w:.1f}% 过近(>{gate.get('reject_if_weekly_high_within_pct', -12)}%)"

    if band_cfg.get("require_hh_hl") and struct and struct != "higher_highs_higher_lows":
        return True, f"结构 {struct} 非 HH/HL"
    if band_cfg.get("require_above_ma20") and above_ma20 is False:
        return True, "未站上 MA20"

    return False, ""


def apply_position_gate(row: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Downgrade watch_pool when position gate fails."""
    cfg = cfg or load_position_config()
    row = dict(row)
    if row.get("action") != "watch_pool":
        return row

    hints = {
        "distance_from_52w_high_pct": row.get("distance_from_52w_high_pct"),
        "distance_from_weekly_high_pct": row.get("distance_from_weekly_high_pct"),
        "distance_from_monthly_high_pct": row.get("distance_from_monthly_high_pct"),
        "price_percentile_2y": row.get("price_percentile_2y"),
        "distance_from_52w_low_pct": row.get("distance_from_52w_low_pct"),
    }
    blocked, reason = blocks_watch_pool(
        hints,
        struct=str(row.get("structure") or ""),
        above_ma20=row.get("price_above_ma20"),
        cfg=cfg,
    )
    if blocked:
        downgrade = str((cfg.get("watch_pool_gate") or {}).get("downgrade_to") or "watch_pullback")
        row["action"] = downgrade
        reasons = list(row.get("downgrade_reasons") or [])
        reasons.append(f"位置过滤:{reason}")
        row["downgrade_reasons"] = reasons
    return row
