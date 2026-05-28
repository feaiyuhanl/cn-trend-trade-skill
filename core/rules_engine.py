"""Machine-checkable rules from config/rules.yaml (sustainable iteration surface)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from core.observation_verify import verify_step_observations
from core.observations import normalize_observation
from core.pack_facts import build_fact_index
from core.position_calc import holding_pnl_pct
from core.prose_verify import allowed_values_from_facts, find_raw_numbers_in_prose
from core.theme_graph import build_theme_index, load_themes_config

_ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = _ROOT / "config" / "rules.yaml"

CheckFn = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], list[str]]


def load_rules_config() -> dict[str, Any]:
    import yaml

    with RULES_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_profile(pack: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    name = (pack.get("meta") or {}).get("rules_profile") or rules.get("default_profile", "development")
    profiles = rules.get("profiles", {})
    if name not in profiles:
        name = rules.get("default_profile", "development")
    return profiles[name]


def _position_ts_codes(pack: dict[str, Any]) -> set[str]:
    return {p["ts_code"] for p in (pack.get("user_context") or {}).get("positions") or []}


def _check_observation_numbers(pack: dict[str, Any], trace: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    rules = load_rules_config()
    policy = rules.get("observation_policy", {})
    tol = float(profile.get("numeric_tolerance_abs", 0.05))
    msgs: list[str] = []
    for step in trace.get("steps", []):
        msgs.extend(
            verify_step_observations(
                pack,
                step,
                tolerance=tol,
                unverified_marker=policy.get("unverified_marker", "[qualitative]"),
                ignore_patterns=policy.get("ignore_patterns", []),
            )
        )
    return msgs


def _check_decisions_have_evidence(pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]) -> list[str]:
    pack_ids = _pack_bar_ids(pack)
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        ev = dec.get("evidence_ids") or []
        if not ev:
            msgs.append(f"decisions.{ts_code}: evidence_ids required (min 1)")
            continue
        missing = [e for e in ev if e not in pack_ids]
        if missing:
            msgs.append(f"decisions.{ts_code}: unknown evidence_ids {missing}")
    return msgs


def _check_decisions_facts_used(pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]) -> list[str]:
    if "fact_index" not in pack:
        build_fact_index(pack)
    flat = pack["fact_index"]["flat"]
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        used = dec.get("facts_used") or []
        if not used:
            msgs.append(f"decisions.{ts_code}: facts_used required (cite pack.fact_index keys)")
            continue
        for key in used:
            if key not in flat:
                msgs.append(f"decisions.{ts_code}: unknown facts_used key {key!r}")
    return msgs


def _check_holding_pnl(pack: dict[str, Any], trace: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    tol = float(profile.get("numeric_tolerance_abs", 0.05))
    idx = pack.get("fact_index") or build_fact_index(pack)
    holdings = idx.get("holdings", {})
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        hr = dec.get("holding_review")
        if not hr or "vs_cost_pct" not in hr:
            continue
        if ts_code not in holdings:
            msgs.append(f"decisions.{ts_code}.holding_review: vs_cost_pct set but no position in pack")
            continue
        expected = holdings[ts_code]["vs_cost_pct"]
        actual = float(hr["vs_cost_pct"])
        if abs(actual - expected) > tol:
            msgs.append(
                f"decisions.{ts_code}.holding_review.vs_cost_pct={actual} "
                f"!= pack computed {expected} (use position_plan.computed or omit)"
            )
    return msgs


def _check_market_filter_indices(pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]) -> list[str]:
    mf = trace.get("market_filter") or {}
    considered = mf.get("indices_considered") or []
    pack_idx = {i["ts_code"] for i in pack.get("indices", [])}
    missing = [c for c in considered if c not in pack_idx]
    if missing:
        return [f"market_filter.indices_considered not in pack: {missing}"]
    return []


def _check_mf_blocks_new_entry(pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]) -> list[str]:
    mf = trace.get("market_filter") or {}
    if mf.get("allow_new_trend_trade") != "no":
        return []
    held = _position_ts_codes(pack)
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        if ts_code in held:
            continue
        entry = dec.get("entry") or {}
        if entry.get("type") not in ("wait", "none", "not_applicable"):
            msgs.append(
                f"decisions.{ts_code}.entry: allow_new_trend_trade=no requires wait/none, got {entry.get('type')}"
            )
    return msgs


def _check_reduced_note(pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]) -> list[str]:
    mf = trace.get("market_filter") or {}
    if mf.get("allow_new_trend_trade") != "reduced":
        return []
    held = _position_ts_codes(pack)
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        if ts_code in held:
            continue
        entry = dec.get("entry") or {}
        if entry.get("type") == "breakout":
            rat = (entry.get("rationale") or "").lower()
            if not any(w in rat for w in ("reduced", "缩仓", "减仓", "仓位")):
                msgs.append(
                    f"decisions.{ts_code}.entry: reduced regime + breakout needs size note in rationale"
                )
    return msgs


def _check_data_gate_phase(pack: dict[str, Any], trace: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    min_bars = int(profile.get("min_daily_bars_for_phase", 20))
    idx = pack.get("fact_index") or build_fact_index(pack)
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        meta = idx.get("symbols", {}).get(ts_code, {})
        count = meta.get("daily_bar_count", 0)
        if count < min_bars and dec.get("phase") != "unclear":
            msgs.append(
                f"decisions.{ts_code}.phase: daily bars={count} < {min_bars}, must be unclear"
            )
    return msgs


def _check_data_gate_strength(pack: dict[str, Any], trace: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    min_w = int(profile.get("min_weekly_bars_for_strength", 4))
    idx = pack.get("fact_index") or build_fact_index(pack)
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        meta = idx.get("symbols", {}).get(ts_code, {})
        if meta.get("weekly_bar_count", 0) < min_w:
            strength = dec.get("strength") or {}
            if strength.get("weekly") == "strong" or strength.get("monthly") == "strong":
                msgs.append(
                    f"decisions.{ts_code}.strength: insufficient weekly bars for strong W/M"
                )
    return msgs


def _check_unclear_phase_entry(pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]) -> list[str]:
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        if dec.get("phase") != "unclear":
            continue
        action = (dec.get("entry") or {}).get("action")
        if action not in ("wait", "none", "not_applicable"):
            msgs.append(f"decisions.{ts_code}: phase=unclear requires cautious entry action, got {action}")
    return msgs


def _check_discipline_rule_ids(pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]) -> list[str]:
    rules = load_rules_config()
    registry_ids = {r["id"] for r in rules.get("discipline_registry", [])}
    machine_ids = {r["id"] for r in rules.get("machine_rules", [])}
    allowed = registry_ids | machine_ids | {"MF_NO_AGGRESSIVE"}
    msgs: list[str] = []
    for i, item in enumerate(trace.get("discipline_checklist") or []):
        rid = item.get("rule_id")
        if not rid:
            msgs.append(f"discipline_checklist[{i}]: rule_id required")
        elif rid not in allowed and not rid.startswith("CUSTOM_"):
            msgs.append(f"discipline_checklist[{i}]: unknown rule_id {rid!r}")
    return msgs


def _check_observation_kind_consistent(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    flat = (pack.get("fact_index") or build_fact_index(pack))["flat"]
    msgs: list[str] = []
    for step in trace.get("steps", []):
        sn, lens = step.get("step"), step.get("lens")
        for i, raw in enumerate(step.get("observations") or []):
            obs = normalize_observation(raw)
            if obs["kind"] == "fact" and not obs.get("fact_keys"):
                msgs.append(f"step {sn} ({lens}) observations[{i}]: kind=fact requires fact_keys")
            for key in obs.get("fact_keys") or []:
                if key not in flat:
                    msgs.append(f"step {sn} ({lens}) observations[{i}]: unknown fact_key {key!r}")
    return msgs


def _check_framework_no_raw_numbers(
    pack: dict[str, Any], trace: dict[str, Any], profile: dict[str, Any]
) -> list[str]:
    tol = float(profile.get("numeric_tolerance_abs", 0.05))
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        facts = dec.get("facts_used") or []
        allowed = allowed_values_from_facts(pack, facts)
        pp = dec.get("position_plan") or {}
        entry = dec.get("entry") or {}
        for label, block in (
            ("position_plan.framework", pp.get("framework")),
            ("entry.rationale", entry.get("rationale")),
            ("exit_plan", dec.get("exit_plan")),
        ):
            if block is None:
                continue
            msgs.extend(
                find_raw_numbers_in_prose(
                    block,
                    root_label=f"decisions.{ts_code}.{label}",
                    allowed_fact_values=allowed,
                    tolerance=tol,
                )
            )
    return msgs


def _check_steps_match_lenses(pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]) -> list[str]:
    meta = trace.get("meta") or {}
    lenses = meta.get("lenses_applied") or []
    steps = trace.get("steps") or []
    if not lenses:
        return ["meta.lenses_applied: required for step alignment check"]
    if len(steps) != len(lenses):
        return [
            f"steps: count {len(steps)} must equal lenses_applied count {len(lenses)} "
            "(one step per lens)"
        ]
    step_lenses = [s.get("lens") for s in steps]
    if step_lenses != lenses:
        return [f"steps lens order {step_lenses!r} must match lenses_applied {lenses!r}"]
    return []


def _check_discipline_mf_consistent(pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]) -> list[str]:
    mf = trace.get("market_filter") or {}
    allow = mf.get("allow_new_trend_trade")
    for item in trace.get("discipline_checklist") or []:
        if item.get("rule_id") != "MF_NO_AGGRESSIVE":
            continue
        block_errors = _check_mf_blocks_new_entry(pack, trace, {})
        should_pass = len(block_errors) == 0
        if item.get("passed") is True and not should_pass and allow == "no":
            return ["discipline MF_NO_AGGRESSIVE: passed=true but market_filter blocks new entries"]
        if item.get("passed") is False and should_pass:
            return ["discipline MF_NO_AGGRESSIVE: passed=false but entries comply with market_filter"]
    return []


def _pack_bar_ids(pack: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for inst in pack.get("symbols", []) + pack.get("indices", []):
        for tf in ("daily", "weekly", "monthly"):
            for bar in (inst.get("bars", {}).get(tf) or []):
                ids.add(bar["id"])
    return ids


def _entry_types_aggressive(dec: dict[str, Any]) -> bool:
    entry = dec.get("entry") or {}
    return entry.get("type") not in ("wait", "none", "not_applicable") and entry.get(
        "action"
    ) not in ("wait", "none", "not_applicable")


def _check_quality_blocks_entry(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    qg = (pack.get("slots") or {}).get("quality_gate") or {}
    by = qg.get("symbols") or {}
    held = _position_ts_codes(pack)
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        if ts_code in held:
            continue
        rec = by.get(ts_code) or {}
        if rec.get("tier") == "block" and _entry_types_aggressive(dec):
            msgs.append(f"decisions.{ts_code}: quality_gate block, entry must be wait/none")
    return msgs


def _check_event_blocks_entry(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    er = (pack.get("slots") or {}).get("event_risk") or {}
    by = er.get("symbols") or {}
    held = _position_ts_codes(pack)
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        if ts_code in held:
            continue
        rec = by.get(ts_code) or {}
        if rec.get("block_entry") and _entry_types_aggressive(dec):
            msgs.append(f"decisions.{ts_code}: event_risk block, entry must be wait/none")
    return msgs


def _check_leader_retreat_blocks_follower(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    slots = pack.get("slots") or {}
    tc = slots.get("theme_context") or {}
    theme_by_id = {t["theme_id"]: t for t in tc.get("themes") or []}
    resolution = slots.get("theme_resolution")
    idx = tc.get("theme_index") or (resolution or {}).get("theme_index")
    if not idx:
        idx = build_theme_index(load_themes_config().get("themes") or {}, resolution)
    held = _position_ts_codes(pack)
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        if ts_code in held:
            continue
        meta = idx.get(ts_code) or {}
        if meta.get("role") != "follower":
            continue
        th = theme_by_id.get(meta.get("theme", ""))
        if not th:
            continue
        bad = th.get("leader_limit_down") or th.get("lifecycle_stage") == "retreat"
        if bad and _entry_types_aggressive(dec):
            msgs.append(
                f"decisions.{ts_code}: theme {meta.get('theme')} leader weak/retreat, "
                "follower entry must be wait/none"
            )
    return msgs


def _check_sentiment_frozen_blocks_entry(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    sent = pack.get("market_sentiment") or {}
    if sent.get("tier") != "frozen":
        return []
    mf = trace.get("market_filter") or {}
    if mf.get("allow_new_trend_trade") == "yes":
        return ["market_filter.allow_new_trend_trade=yes conflicts with sentiment.tier=frozen"]
    return []


def _check_sentiment_euphoric_breakout_note(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    sent = pack.get("market_sentiment") or {}
    if sent.get("tier") != "euphoric":
        return []
    import yaml
    from pathlib import Path

    cfg_path = Path(__file__).resolve().parent.parent / "config" / "sentiment.yaml"
    th = 0.45
    if cfg_path.exists():
        with cfg_path.open(encoding="utf-8") as f:
            th = float((yaml.safe_load(f) or {}).get("thresholds", {}).get("break_rate_high", 0.45))
    if float(sent.get("break_rate") or 0) < th:
        return []
    held = _position_ts_codes(pack)
    msgs: list[str] = []
    for ts_code, dec in (trace.get("decisions") or {}).items():
        if ts_code in held:
            continue
        entry = dec.get("entry") or {}
        if entry.get("type") == "breakout":
            rat = (entry.get("rationale") or "").lower()
            if not any(w in rat for w in ("缩仓", "减仓", "不追", "破板", "reduced", "wait")):
                msgs.append(
                    f"decisions.{ts_code}.entry: euphoric+high break_rate needs caution in rationale"
                )
    return msgs


def _is_watchlist_screen_trace(trace: dict[str, Any]) -> bool:
    return (trace.get("meta") or {}).get("playbook") == "watchlist-screen"


def _check_screen_safety_rank_range(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    if not _is_watchlist_screen_trace(trace):
        return []
    msgs: list[str] = []
    for ts, dec in (trace.get("decisions") or {}).items():
        sc = (dec or {}).get("screen") or {}
        rank = sc.get("safety_rank")
        if rank is None:
            continue
        try:
            r = int(rank)
        except (TypeError, ValueError):
            msgs.append(f"decisions.{ts}.screen.safety_rank: must be int 0-100")
            continue
        if r < 0 or r > 100:
            msgs.append(f"decisions.{ts}.screen.safety_rank: {r} out of range 0-100")
    return msgs


def _check_screen_trap_high_no_watch_pool(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    if not _is_watchlist_screen_trace(trace):
        return []
    msgs: list[str] = []
    for ts, dec in (trace.get("decisions") or {}).items():
        sc = (dec or {}).get("screen") or {}
        if sc.get("trap_risk") == "high" and sc.get("action") == "watch_pool":
            msgs.append(f"decisions.{ts}.screen: trap_risk=high cannot be watch_pool")
    return msgs


def _check_screen_facts_used_when_ranked(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    if not _is_watchlist_screen_trace(trace):
        return []
    flat = (pack.get("fact_index") or build_fact_index(pack))["flat"]
    msgs: list[str] = []
    for ts, dec in (trace.get("decisions") or {}).items():
        sc = (dec or {}).get("screen") or {}
        if sc.get("safety_rank") is None:
            continue
        used = dec.get("facts_used") or sc.get("facts_used") or []
        if not used:
            msgs.append(f"decisions.{ts}.screen: facts_used required when safety_rank set")
            continue
        for key in used:
            if key not in flat:
                msgs.append(f"decisions.{ts}.screen: unknown facts_used key {key!r}")
    return msgs


def _check_screen_steps_match_lenses(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    if not _is_watchlist_screen_trace(trace):
        return []
    lenses = (trace.get("meta") or {}).get("lenses_applied") or []
    steps = trace.get("steps") or []
    if not lenses:
        return []
    if len(steps) != len(lenses):
        return [f"screen steps: count {len(steps)} must equal lenses_applied {len(lenses)}"]
    step_lenses = [s.get("lens") for s in steps]
    if step_lenses != lenses:
        return [f"screen steps lens order {step_lenses!r} must match lenses_applied {lenses!r}"]
    return []


def _check_screen_watch_pool_observation_plan(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    if not _is_watchlist_screen_trace(trace):
        return []
    msgs: list[str] = []
    for ts, dec in (trace.get("decisions") or {}).items():
        sc = (dec or {}).get("screen") or {}
        if sc.get("action") != "watch_pool":
            continue
        op = sc.get("observation_plan") or {}
        if not op.get("trail_stop_hint"):
            msgs.append(f"decisions.{ts}.screen.observation_plan: trail_stop_hint required for watch_pool")
    return msgs


def _check_screen_quality_block_avoid(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    if not _is_watchlist_screen_trace(trace):
        return []
    qg = (pack.get("slots") or {}).get("quality_gate") or {}
    by_ts = qg.get("symbols") or {}
    msgs: list[str] = []
    for ts, dec in (trace.get("decisions") or {}).items():
        if (by_ts.get(ts) or {}).get("tier") != "block":
            continue
        sc = (dec or {}).get("screen") or {}
        if sc.get("action") not in ("avoid", "pending", None):
            msgs.append(f"decisions.{ts}.screen: quality block requires action=avoid")
    return msgs


def _check_screen_position_gate_watch_pool(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    if not _is_watchlist_screen_trace(trace):
        return []
    from core.position_filter import blocks_watch_pool, load_position_config

    cfg = load_position_config()
    msgs: list[str] = []
    for ts, dec in (trace.get("decisions") or {}).items():
        sc = (dec or {}).get("screen") or {}
        if sc.get("action") != "watch_pool":
            continue
        inst = next((s for s in pack.get("symbols", []) if s["ts_code"] == ts), None)
        h = (inst or {}).get("derived_hints") or {}
        blocked, reason = blocks_watch_pool(
            h,
            struct=str(h.get("structure") or sc.get("structure") or ""),
            above_ma20=h.get("price_above_ma20"),
            cfg=cfg,
        )
        if blocked:
            msgs.append(f"decisions.{ts}.screen: watch_pool blocked by position gate: {reason}")
    return msgs


def _check_trend_top10_quality_block(
    pack: dict[str, Any], trace: dict[str, Any], _profile: dict[str, Any]
) -> list[str]:
    # Validated at result assembly time; trace-only check is no-op
    return []


_CHECK_REGISTRY: dict[str, CheckFn] = {
    "observation_numbers_match_evidence": _check_observation_numbers,
    "decisions_have_evidence": _check_decisions_have_evidence,
    "decisions_facts_used_valid": _check_decisions_facts_used,
    "holding_pnl_matches_pack": _check_holding_pnl,
    "market_filter_indices_in_pack": _check_market_filter_indices,
    "market_filter_blocks_new_entry": _check_mf_blocks_new_entry,
    "reduced_requires_size_note": _check_reduced_note,
    "insufficient_data_forces_unclear_phase": _check_data_gate_phase,
    "insufficient_weekly_limits_strength": _check_data_gate_strength,
    "unclear_phase_cautious_entry": _check_unclear_phase_entry,
    "discipline_has_rule_ids": _check_discipline_rule_ids,
    "discipline_matches_market_filter": _check_discipline_mf_consistent,
    "steps_match_lenses_applied": _check_steps_match_lenses,
    "observation_kind_consistent": _check_observation_kind_consistent,
    "framework_no_raw_numbers": _check_framework_no_raw_numbers,
    "quality_gate_blocks_entry": _check_quality_blocks_entry,
    "event_risk_blocks_entry": _check_event_blocks_entry,
    "leader_retreat_blocks_follower": _check_leader_retreat_blocks_follower,
    "sentiment_frozen_blocks_entry": _check_sentiment_frozen_blocks_entry,
    "sentiment_euphoric_breakout_note": _check_sentiment_euphoric_breakout_note,
    "screen_safety_rank_range": _check_screen_safety_rank_range,
    "screen_trap_high_no_watch_pool": _check_screen_trap_high_no_watch_pool,
    "screen_facts_used_when_ranked": _check_screen_facts_used_when_ranked,
    "screen_quality_block_avoid": _check_screen_quality_block_avoid,
    "screen_steps_match_lenses": _check_screen_steps_match_lenses,
    "screen_watch_pool_observation_plan": _check_screen_watch_pool_observation_plan,
    "screen_position_gate_watch_pool": _check_screen_position_gate_watch_pool,
    "trend_top10_quality_block": _check_trend_top10_quality_block,
}


def run_machine_rules(
    pack: dict[str, Any],
    trace: dict[str, Any],
    *,
    rules_profile: str | None = None,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) from config machine_rules."""
    rules = load_rules_config()
    if rules_profile:
        pack.setdefault("meta", {})["rules_profile"] = rules_profile
    profile = resolve_profile(pack, rules)
    if "fact_index" not in pack:
        from core.pack_facts import attach_fact_index

        attach_fact_index(pack, rules_version=rules.get("version"))

    errors: list[str] = []
    warnings: list[str] = []
    is_screen = _is_watchlist_screen_trace(trace)
    rule_list = (
        rules.get("watchlist_screen_rules", [])
        if is_screen
        else rules.get("machine_rules", [])
    )
    for rule in rule_list:
        check_name = rule.get("check")
        fn = _CHECK_REGISTRY.get(check_name or "")
        if not fn:
            errors.append(f"rules config: unknown check {check_name!r}")
            continue
        msgs = fn(pack, trace, profile)
        prefixed = [f"[{rule['id']}] {m}" for m in msgs]
        if rule.get("severity") == "warn":
            warnings.extend(prefixed)
        else:
            errors.extend(prefixed)
    return errors, warnings
