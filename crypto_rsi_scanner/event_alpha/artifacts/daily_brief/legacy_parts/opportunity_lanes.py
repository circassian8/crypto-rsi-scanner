"""Opportunity Lanes helpers for legacy daily brief."""

from __future__ import annotations

from .runtime import *

def _core_opportunity_sections(
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
) -> dict[str, list[event_core_opportunities.CoreOpportunity]]:
    """Partition core opportunities into one operator-facing section each."""
    remaining = list(opportunities)
    sections: dict[str, list[event_core_opportunities.CoreOpportunity]] = {}

    def take(
        name: str,
        predicate: Callable[[event_core_opportunities.CoreOpportunity], bool],
    ) -> None:
        selected: list[event_core_opportunities.CoreOpportunity] = []
        rest: list[event_core_opportunities.CoreOpportunity] = []
        for item in remaining:
            if predicate(item):
                selected.append(item)
            else:
                rest.append(item)
        sections[name] = selected
        remaining[:] = rest

    take("strong", lambda item: item.is_high_priority)
    take("watchlist", lambda item: item.is_watchlist)
    take("digest", lambda item: item.is_validated_digest or item.alertable)
    sections["local"] = remaining
    return sections

def _core_opportunity_lane_sections(
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
) -> dict[str, list[event_core_opportunities.CoreOpportunity]]:
    sections: dict[str, list[event_core_opportunities.CoreOpportunity]] = {
        "early": [],
        "confirmed": [],
        "fade": [],
        "risk": [],
        "unconfirmed": [],
        "diagnostics": [],
    }
    for item in opportunities:
        lane = str(item.primary_row.get("opportunity_type") or "").strip().upper()
        if lane == "EARLY_LONG_RESEARCH":
            sections["early"].append(item)
        elif lane == "CONFIRMED_LONG_RESEARCH":
            sections["confirmed"].append(item)
        elif lane == "FADE_SHORT_REVIEW":
            sections["fade"].append(item)
        elif lane == "RISK_ONLY":
            sections["risk"].append(item)
        elif lane == "DIAGNOSTIC":
            sections["diagnostics"].append(item)
        else:
            sections["unconfirmed"].append(item)
    return sections

def _market_freshness_readiness_lines(
    rows: Iterable[Any],
    *,
    requested_profile: str | None,
    limit: int = 8,
) -> list[str]:
    normalized = [_row_mapping(row) for row in rows]
    visible_core = event_core_opportunities.visible_core_opportunities(normalized)
    statuses: dict[str, int] = {}
    capped: list[Mapping[str, Any]] = []
    missing: list[Mapping[str, Any]] = []
    refresh_needed: list[Mapping[str, Any]] = []
    for row in normalized:
        components = _components_for_row(row)
        status = str(
            row.get("market_context_freshness_status")
            or components.get("market_context_freshness_status")
            or "missing"
        )
        statuses[status] = statuses.get(status, 0) + 1
        cap = _truthy(row.get("market_context_freshness_cap_applied") if row.get("market_context_freshness_cap_applied") is not None else components.get("market_context_freshness_cap_applied"))
        if row.get("row_type") == "event_core_opportunity" and status in {"fresh", "fixture_allowed_stale"}:
            cap = False
        if cap or status in {"stale", "unknown", "missing"}:
            refresh_needed.append(row)
        if cap or status == "stale":
            capped.append(row)
        if status in {"missing", "unknown"}:
            missing.append(row)
    profile = str(requested_profile or "").casefold()
    can_refresh = profile not in {"fixture", "quality_validation", "catalyst_frame_e2e", "notify_llm_quality_frame", "catalyst_frame_validation"}
    lines = [
        "- Freshness statuses: " + _format_counts(statuses),
        f"- Fresh market context: {statuses.get('fresh', 0)}",
        f"- Capped by stale/unknown context: {len(capped)}",
        f"- Missing/unknown market context: {len(missing)}",
        f"- Needs targeted market refresh: {len(refresh_needed)}",
        f"- Live profile can perform refresh: {str(can_refresh).lower()}",
    ]
    if visible_core:
        lines.append("- Core opportunity freshness:")
        for item in visible_core[:limit]:
            line = _core_market_freshness_line(item)
            if line:
                lines.append(line)
        if len(visible_core) > limit:
            lines.append(f"  - +{len(visible_core) - limit} more core opportunities in diagnostics")
    else:
        for row in refresh_needed[:limit]:
            components = _components_for_row(row)
            label = _label_for_row(row, components)
            status = row.get("market_context_freshness_status") or components.get("market_context_freshness_status") or "missing"
            source = row.get("market_context_source") or components.get("market_context_source") or "unknown"
            cap = row.get("market_context_freshness_cap_applied")
            if cap is None:
                cap = components.get("market_context_freshness_cap_applied")
            lines.append(
                f"  - {label}: status={status} source={source} age={_market_age_label(row, components)} cap_applied={str(_truthy(cap)).lower()}"
            )
        if len(refresh_needed) > limit:
            lines.append(f"  - +{len(refresh_needed) - limit} more rows need refresh")
    return lines

def _core_market_freshness_line(item: event_core_opportunities.CoreOpportunity) -> str:
    rows = [item.primary_row, *item.supporting_rows]
    row_infos: list[tuple[str, str, str, bool, bool]] = []
    for row in rows:
        components = _components_for_row(row)
        status = str(row.get("market_context_freshness_status") or components.get("market_context_freshness_status") or "missing")
        source = str(row.get("market_context_source") or components.get("market_context_source") or "unknown")
        age = _market_age_label(row, components)
        cap_raw = row.get("market_context_freshness_cap_applied")
        if cap_raw is None:
            cap_raw = components.get("market_context_freshness_cap_applied")
        refresh_attempted = _truthy(row.get("market_refresh_attempted") or components.get("market_refresh_attempted"))
        row_infos.append((status, source, age, _truthy(cap_raw), refresh_attempted))
    if not row_infos:
        row_infos.append(("missing", "unknown", "unknown", False, False))
    status_rank = {"fresh": 0, "fixture_allowed_stale": 1, "stale": 2, "unknown": 3, "missing": 4}
    core_components = _components_for_row(item.primary_row)
    core_status = str(item.primary_row.get("market_context_freshness_status") or core_components.get("market_context_freshness_status") or "")
    core_source = str(item.primary_row.get("market_context_source") or core_components.get("market_context_source") or "")
    core_age = _market_age_label(item.primary_row, core_components)
    if not core_status:
        best = sorted(row_infos, key=lambda item_info: status_rank.get(item_info[0], 5))[0]
        core_status, core_source, core_age = best[0], best[1], best[2]
    if core_status in {"fresh", "fixture_allowed_stale"} and core_source.casefold() in {"", "missing", "unknown"}:
        core_source = "canonical_core_store"
    if core_status in {"fresh", "fixture_allowed_stale"} and core_age.casefold() in {"", "unknown", "missing"}:
        core_age = "n/a"
    support_infos = row_infos[1:] if len(row_infos) > 1 else ()
    support_gaps = sum(1 for status, _, _, cap, _ in support_infos if cap or status in {"stale", "unknown", "missing"})
    core_refresh_needed = core_status in {"", "stale", "unknown", "missing"}
    support_refresh_needed = 0 if core_status in {"fresh", "fixture_allowed_stale"} else support_gaps
    refresh_attempted = any(info[4] for info in row_infos)
    derivatives_line = _confirmation_status_line(
        item.primary_row,
        core_components,
        level_key="derivatives_confirmation_level",
        score_key="derivatives_confirmation_score",
        freshness_key="derivatives_freshness_status",
    )
    dex_line = _confirmation_status_line(
        item.primary_row,
        core_components,
        level_key="dex_liquidity_level",
        score_key="dex_liquidity_score",
        freshness_key="dex_freshness_status",
    )
    protocol_line = _confirmation_status_line(
        item.primary_row,
        core_components,
        level_key="protocol_metrics_level",
        score_key="protocol_metrics_score",
        freshness_key="protocol_metrics_freshness_status",
    )
    return (
        f"  - {item.core_opportunity_id} {item.symbol}/{item.coin_id}: "
        f"core_market_freshness_status={core_status or 'missing'} "
        f"core_market_context_source={core_source or 'unknown'} "
        f"core_market_context_age={core_age} "
        f"refresh_attempted={str(refresh_attempted).lower()} "
        f"derivatives={derivatives_line} "
        f"dex_liquidity={dex_line} "
        f"protocol_metrics={protocol_line} "
        f"core_market_refresh_needed={str(core_refresh_needed).lower()} "
        f"support_rows_stale_or_missing_count={support_gaps} "
        f"support_rows_needing_refresh_count={support_refresh_needed}"
    )

def _confirmation_status_line(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    *,
    level_key: str,
    score_key: str,
    freshness_key: str,
) -> str:
    level = row.get(level_key) or components.get(level_key) or "none"
    score = row.get(score_key) if row.get(score_key) is not None else components.get(score_key)
    freshness = row.get(freshness_key) or components.get(freshness_key) or "missing"
    score_text = "n/a" if score in (None, "") else str(score)
    return f"{level}/{score_text}/{freshness}"

def _row_mapping(row: Any) -> Mapping[str, Any]:
    if isinstance(row, event_watchlist.EventWatchlistEntry):
        data = dict(getattr(row, "__dict__", {}) or {})
        data.setdefault("latest_score_components", dict(row.latest_score_components or {}))
        return data
    if isinstance(row, Mapping):
        return row
    return dict(getattr(row, "__dict__", {}) or {})

def _components_for_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("latest_score_components", "score_components", "_components"):
        value = row.get(key)
        if isinstance(value, Mapping):
            return value
    return {}

def _label_for_row(row: Mapping[str, Any], components: Mapping[str, Any]) -> str:
    symbol = row.get("symbol") or row.get("validated_symbol") or components.get("validated_symbol") or "UNKNOWN"
    coin = row.get("coin_id") or row.get("validated_coin_id") or components.get("validated_coin_id") or "unknown"
    return f"{symbol}/{coin}"

def _market_age_label(row: Mapping[str, Any], components: Mapping[str, Any]) -> str:
    value = row.get("market_context_age_hours")
    if value is None:
        value = components.get("market_context_age_hours")
    try:
        hours = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "unknown"
    if hours < 1:
        return f"{hours * 60:.0f}m"
    return f"{hours:.1f}h"

def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)

def _card_paths_for_daily_brief(paths: Iterable[Path], *, include_diagnostics: bool) -> list[Path]:
    cards = [Path(path) for path in paths]
    if include_diagnostics:
        return cards
    hidden_terms = (
        "source_noise_control",
        "ambiguous_control",
        "quality_blocked",
        "local_only",
        "store_only",
        "diagnostic",
    )
    return [
        path for path in cards
        if not any(term in path.name.casefold() for term in hidden_terms)
    ]

def _brief_core_opportunities(
    rows: Iterable[event_core_opportunities.CoreOpportunity],
    *,
    section: str,
    limit: int,
) -> str:
    if section == "strong":
        selected = [item for item in rows if item.is_high_priority or item.is_watchlist]
    elif section == "digest":
        selected = [item for item in rows if item.is_validated_digest and not (item.is_high_priority or item.is_watchlist)]
    else:
        selected = list(rows)
    labels = []
    for item in selected[:limit]:
        labels.append(
            f"{item.symbol}/{item.coin_id}"
            f"(core={item.core_opportunity_id},level={item.opportunity_level},"
            f"route={item.final_route_after_quality_gate or 'local'},"
            f"state={item.final_state_after_quality_gate or 'unknown'},"
            f"score={item.opportunity_score_final:.0f},"
            f"path={item.primary_impact_path},role={item.candidate_role},"
            f"support={len(item.supporting_rows)},diagnostics={item.diagnostic_row_count})"
        )
    return "; ".join(labels)

def _brief_entries(rows: Iterable[event_watchlist.EventWatchlistEntry]) -> str:
    labels: list[str] = []
    seen: set[tuple[str, str]] = set()
    for entry in rows:
        key = _entry_family_key(entry)
        if key in seen:
            continue
        seen.add(key)
        components = entry.latest_score_components or {}
        labels.append(
            f"{entry.symbol}/{entry.coin_id}"
            f"({components.get('impact_category') or entry.latest_playbook_type or 'unknown'},"
            f"score={entry.latest_score},v2={_float(components.get('opportunity_score_v2')):.0f},"
            f"path={components.get('impact_path_type') or 'unknown'},main={components.get('main_frame_type') or 'unknown'})"
        )
    return "; ".join(labels)

def _market_confirmation_by_playbook(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    counts: dict[str, dict[str, int]] = {}
    for decision in rows:
        entry = decision.entry
        if entry.relationship_type != "impact_hypothesis":
            continue
        components = entry.latest_score_components or {}
        playbook = str(entry.latest_effective_playbook_type or entry.latest_playbook_type or "unknown")
        level = str(components.get("market_confirmation_level") or "unknown")
        counts.setdefault(playbook, {})[level] = counts.setdefault(playbook, {}).get(level, 0) + 1
    if not counts:
        return "none"
    parts: list[str] = []
    for playbook, levels in sorted(counts.items()):
        parts.append(playbook + "[" + ",".join(f"{key}={value}" for key, value in sorted(levels.items())) + "]")
    return "; ".join(parts)

def _quality_decision_counts(rows: Iterable[event_alpha_router.EventAlphaRouteDecision], key: str) -> str:
    counts: dict[str, int] = {}
    for decision in rows:
        if decision.entry.relationship_type != "impact_hypothesis":
            continue
        components = decision.entry.latest_score_components or {}
        value = str(components.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return _format_counts(counts)

def _quality_gate_downgrades(
    rows: Iterable[event_alpha_router.EventAlphaRouteDecision],
) -> list[event_alpha_router.EventAlphaRouteDecision]:
    return [
        decision for decision in rows
        if decision.quality_gate_block_reason
        or (
            decision.requested_route_before_quality_gate
            and decision.final_route_after_quality_gate
            and decision.requested_route_before_quality_gate != decision.final_route_after_quality_gate
        )
    ]

def _blocked_route_attempts_line(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels: list[str] = []
    for decision in rows:
        labels.append(
            f"{decision.entry.symbol}/{decision.entry.coin_id}:"
            f"{decision.requested_route_before_quality_gate or 'unknown'}->"
            f"{decision.final_route_after_quality_gate or decision.route.value}"
        )
        if len(labels) >= 5:
            break
    return "; ".join(labels)

def _quality_gate_reason_counts(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    counts: dict[str, int] = {}
    for decision in rows:
        reason = str(decision.quality_gate_block_reason or "route_capped")
        counts[reason] = counts.get(reason, 0) + 1
    return _format_counts(counts)

def _legacy_quality_conflicts(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    out = []
    for row in rows:
        classification = str(
            row.get("snapshot_quality_classification")
            or event_alpha_alert_store.classify_alert_snapshot(row)
        )
        if classification in event_alpha_alert_store.LEGACY_CONFLICT_CLASSIFICATIONS:
            out.append(row)
    return out

def _legacy_quality_conflict_lines(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    items = list(rows)
    if not items:
        return ["- none"]
    lines: list[str] = []
    for row in items:
        label = row.get("symbol") or row.get("validated_symbol") or row.get("coin_id") or row.get("alert_key") or "candidate"
        classification = str(row.get("snapshot_quality_classification") or event_alpha_alert_store.classify_alert_snapshot(row))
        lines.append(
            f"- {label}: classification={classification} "
            f"legacy_route={row.get('route') or 'unknown'} "
            f"final={row.get('final_route_after_quality_gate') or 'missing'} "
            f"level={row.get('opportunity_level') or 'unknown'} "
            f"score={row.get('opportunity_score_final') if row.get('opportunity_score_final') is not None else 'n/a'}"
        )
    return lines

def _candidate_discovery_funnel_line(rows: Iterable[Mapping[str, Any]]) -> str:
    generated = executed = raw_terms = candidate_like = accepted = rejected = validated = promoted = 0
    for row in rows:
        generated += len(row.get("generated_queries") or [])
        executed += len(row.get("executed_queries") or [])
        crypto = row.get("crypto_candidate_assets") or []
        rejects = row.get("rejected_candidate_assets") or []
        raw_terms += len(crypto) + len(rejects)
        candidate_like += sum(1 for item in [*crypto, *rejects] if isinstance(item, Mapping) and _candidate_like_term(item))
        accepted += sum(1 for item in crypto if isinstance(item, Mapping) and bool(item.get("accepted", item.get("validated", False))))
        rejected += len(rejects)
        if str(row.get("validation_stage") or "") in {"catalyst_link_validated", "impact_path_validated", "market_confirmed", "promoted_to_radar"}:
            validated += 1
        if str(row.get("opportunity_level") or "") in {"validated_digest", "watchlist", "high_priority"}:
            promoted += 1
    if not any((generated, executed, raw_terms, candidate_like, accepted, rejected, validated, promoted)):
        return "none"
    resolver_attempted = accepted + rejected
    return (
        f"generated={generated}, executed={executed}, raw_terms_extracted={raw_terms}, "
        f"candidate_like_terms={candidate_like}, resolver_accepted_candidates={accepted}, "
        f"resolver_attempted={resolver_attempted}, resolver_rejected_terms={rejected}, "
        f"context_validated_candidates={validated}, "
        f"promoted_candidates={promoted}"
    )

__all__ = (
    '_core_opportunity_sections',
    '_core_opportunity_lane_sections',
    '_market_freshness_readiness_lines',
    '_core_market_freshness_line',
    '_confirmation_status_line',
    '_row_mapping',
    '_components_for_row',
    '_label_for_row',
    '_market_age_label',
    '_truthy',
    '_card_paths_for_daily_brief',
    '_brief_core_opportunities',
    '_brief_entries',
    '_market_confirmation_by_playbook',
    '_quality_decision_counts',
    '_quality_gate_downgrades',
    '_blocked_route_attempts_line',
    '_quality_gate_reason_counts',
    '_legacy_quality_conflicts',
    '_legacy_quality_conflict_lines',
    '_candidate_discovery_funnel_line',
)
