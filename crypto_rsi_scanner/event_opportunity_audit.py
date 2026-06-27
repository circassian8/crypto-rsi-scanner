"""Decision-path audit reports for Event Alpha research opportunities."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Iterable, Mapping

from . import (
    event_core_opportunities,
    event_alpha_quality_fields,
    event_alpha_router,
    event_near_miss,
    event_opportunity_verdict,
    event_watchlist,
)


def format_opportunity_audit(
    target: str,
    *,
    hypotheses: Iterable[Mapping[str, Any] | object] = (),
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry | Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision | Mapping[str, Any]] = (),
    incident_rows: Iterable[Mapping[str, Any]] = (),
    profile: str | None = None,
    include_diagnostics: bool = False,
) -> str:
    """Explain one candidate's research-only decision path."""
    clean = str(target or "").strip()
    if not clean:
        return "Event opportunity audit failed: target is required."
    hypothesis_items = list(hypotheses)
    watchlist_items = list(watchlist_entries)
    alert_items = list(alert_rows)
    decision_items = list(route_decisions)
    incidents = [dict(row) for row in incident_rows if isinstance(row, Mapping)]
    core_opportunities = event_core_opportunities.aggregate_core_opportunities([
        *decision_items,
        *watchlist_items,
        *alert_items,
        *hypothesis_items,
    ])
    core_match = _find_core_match(clean, core_opportunities)
    match = (
        {
            "source": "core_opportunity",
            "row": core_match.primary_row,
            "core_opportunity": core_match,
        }
        if core_match is not None
        else _find_match(clean, hypothesis_items, watchlist_items, alert_items, decision_items, incidents)
    )
    if match is None:
        return "\n".join([
            "=" * 76,
            "EVENT OPPORTUNITY AUDIT (research-only)",
            "=" * 76,
            f"target: {clean}",
            f"profile: {profile or 'default'}",
            "No matching hypothesis, watchlist row, alert snapshot, or route decision found.",
            "No secrets, sends, trades, paper rows, normal RSI rows, or event-fade state were touched.",
        ])
    row = match["row"]
    components = _components(row)
    incident = _incident_context(row, components, incidents)
    upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
    near_miss = event_near_miss.near_miss_metadata_for_row(row)
    daily_section = _daily_brief_section(row, components, core_match, near_miss)
    card_group = _card_group_for_audit(row, components, core_match, near_miss)
    lines = [
        "=" * 76,
        "EVENT OPPORTUNITY AUDIT (research-only)",
        "=" * 76,
        f"target: {clean}",
        f"profile: {profile or 'default'}",
        f"matched_source: {match['source']}",
        f"quality_field_source: {_quality_source(row)}",
        "",
        "## Candidate summary",
        f"- symbol/coin: {_value(row, 'symbol', components.get('validated_symbol'), default='SECTOR')}/{_value(row, 'coin_id', components.get('validated_coin_id'), default='unknown')}",
        f"- event/hypothesis: {_value(row, 'event_id', 'hypothesis_id', default='unknown')}",
        f"- external catalyst: {_value(row, 'external_asset', components.get('external_asset'), default='unknown')}",
        f"- playbook: {_value(row, 'playbook_type', 'latest_playbook_type', components.get('playbook_type'), default='unknown')}",
        f"- state/tier: {_value(row, 'state', default='unknown')} / {_value(row, 'tier', 'latest_tier', default='unknown')}",
        "",
        *(_core_opportunity_lines(core_match, include_diagnostics=include_diagnostics) if core_match is not None else []),
        "## Operator Presentation",
        f"- Daily brief section: {daily_section}",
        f"- Research card group: {card_group}",
        "- Reason: " + _operator_presentation_reason(row, components, core_match, near_miss),
        "",
        "## Evidence chain",
        f"- raw source summary: {_value(row, 'raw_evidence_summary', 'event_name', 'latest_event_name', default='unknown')}",
        f"- source/provider: {_value(row, 'source', 'latest_source', default='unknown')}",
        f"- source count: {_value(row, 'source_count', default='0')}",
        f"- evidence quotes: {_list_value(row.get('evidence_quotes') or components.get('evidence_quotes'))}",
        f"- validation reasons: {_list_value(row.get('validation_reasons') or components.get('validation_reasons'))}",
        f"- external entities: {_asset_list(row.get('external_entities') or components.get('external_entities'))}",
        f"- crypto candidates: {_asset_list(row.get('crypto_candidate_assets') or components.get('crypto_candidate_assets'))}",
        f"- rejected candidates: {_asset_list(row.get('rejected_candidate_assets') or components.get('rejected_candidate_assets'))}",
        "",
        "## Identity decision",
        f"- validated symbol: {components.get('validated_symbol') or row.get('validated_symbol') or row.get('symbol') or 'unknown'}",
        f"- validated coin_id: {components.get('validated_coin_id') or row.get('validated_coin_id') or row.get('coin_id') or 'unknown'}",
        f"- candidate role: {components.get('candidate_role') or row.get('candidate_role') or 'unknown'}",
        f"- identity warnings: {_list_value(row.get('warnings') or components.get('warnings'))}",
        "",
        "## Incident",
        *_incident_lines(incident, row, components),
        "",
        "## Impact path decision",
        f"- impact path: {components.get('impact_path_type') or row.get('impact_path_type') or 'unknown'}",
        f"- strength: {components.get('impact_path_strength') or row.get('impact_path_strength') or 'unknown'}",
        f"- reason: {components.get('impact_path_reason') or row.get('impact_path_reason') or 'unknown'}",
        f"- digest gate: {components.get('digest_eligible_by_impact_path') if components.get('digest_eligible_by_impact_path') is not None else 'unknown'}",
        "",
        "## Evidence quality decision",
        f"- source/evidence: {components.get('source_class') or row.get('source_class') or 'unknown'} / {components.get('evidence_specificity') or row.get('evidence_specificity') or 'unknown'}",
        f"- evidence score: {components.get('evidence_quality_score') or row.get('evidence_quality_score') or 'n/a'}",
        "",
        "## Market confirmation decision",
        f"- market level/score: {components.get('market_confirmation_level') or row.get('market_confirmation_level') or 'unknown'} / {components.get('market_confirmation_score') or row.get('market_confirmation_score') or 'n/a'}",
        f"- market reasons: {_list_value(components.get('market_confirmation_reasons') or row.get('market_confirmation_reasons'))}",
        f"- market missing: {_list_value(components.get('market_confirmation_missing_fields') or row.get('market_confirmation_missing_fields'))}",
        "",
        "## Final opportunity verdict",
        f"- level/score: {components.get('opportunity_level') or row.get('opportunity_level') or 'unknown'} / {components.get('opportunity_score_final') or row.get('opportunity_score_final') or 'n/a'}",
        f"- reasons: {_list_value(components.get('opportunity_verdict_reasons') or row.get('opportunity_verdict_reasons'))}",
        f"- why local-only: {components.get('why_local_only') or row.get('why_local_only') or 'none'}",
        f"- why not watchlist: {components.get('why_not_watchlist') or row.get('why_not_watchlist') or 'none'}",
        "",
        "## Near-miss status",
        *_near_miss_lines(near_miss, row),
        "",
        "## Router decision",
        f"- route: {_value(row, 'route', default=match.get('route') or 'not_routed')}",
        f"- notification lane: {_value(row, 'lane', default=match.get('lane') or 'local_only')}",
        f"- router reason: {_value(row, 'route_reason', 'reason', default=match.get('reason') or 'not routed or stored locally')}",
        "- TRIGGERED_FADE was not created unless the row is already a deterministic proxy_fade/event_fade trigger.",
        "",
        "## Notification and feedback status",
        f"- delivery status: {_value(row, 'delivered_status', 'delivery_state', default='not_delivered_or_unknown')}",
        f"- feedback status: {_value(row, 'feedback_status', default='pending_or_unknown')}",
        f"- feedback label: {_value(row, 'label', 'feedback', default='none')}",
        "",
        "## Missing evidence",
        f"- missing requirements: {_list_value(components.get('missing_requirements') or row.get('missing_requirements'))}",
        "",
        "## What would upgrade this candidate",
        "- " + "; ".join(upgrade.upgrade_requirements[:8]),
        "",
        "## What would downgrade / invalidate this candidate",
        "- " + "; ".join(upgrade.downgrade_warnings[:8]),
        "",
        "## Feedback command",
        f"- make event-feedback-watch PROFILE={profile or 'notify_llm'} FEEDBACK_TARGET='{_audit_feedback_target(row, clean)}'",
        "",
        "No secrets, Telegram sends, trades, paper rows, normal RSI rows, or event-fade state were touched.",
    ]
    return "\n".join(lines)


def _near_miss_lines(
    near_miss: event_near_miss.EventNearMissCandidate | None,
    row: Mapping[str, Any],
) -> list[str]:
    if near_miss is None:
        return ["- status: not close to promotion by current quality gates"]
    lines = [
        "- status: near-miss candidate",
        f"- near_miss_id: {near_miss.near_miss_id}",
        f"- score/level before refresh: {near_miss.opportunity_score_before:.0f} / {near_miss.opportunity_level_before}",
        "- missing evidence: " + (_human_reason_list(near_miss.missing_evidence) or "none"),
        "- recommended refresh: " + (_human_action_list(near_miss.recommended_refresh_actions) or "manual analyst review"),
    ]
    score_components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    before = row.get("opportunity_level_before") or score_components.get("opportunity_level_before")
    after = row.get("opportunity_level_after") or score_components.get("opportunity_level_after")
    if before or after or row.get("market_refresh_attempted") is not None:
        lines.append(
            "- targeted refresh: "
            f"market={str(bool(row.get('market_refresh_attempted'))).lower()}/"
            f"{str(bool(row.get('market_refresh_success'))).lower()} "
            f"verdict={before or near_miss.opportunity_level_before}->{after or row.get('opportunity_level') or near_miss.opportunity_level_before}"
        )
    return lines


def _daily_brief_section(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    core: event_core_opportunities.CoreOpportunity | None,
    near_miss: event_near_miss.EventNearMissCandidate | None,
) -> str:
    if core is not None:
        if core.is_high_priority:
            return "High-Priority Core Opportunities"
        if core.is_watchlist:
            return "Watchlist Core Opportunities"
        if core.is_validated_digest or core.alertable:
            return "Validated Digest Core Opportunities"
    level = str(components.get("opportunity_level") or row.get("opportunity_level") or "").casefold()
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").upper()
    if "HIGH_PRIORITY" in route or level == "high_priority":
        return "High-Priority Core Opportunities"
    if "WATCHLIST" in route or level == "watchlist":
        return "Watchlist Core Opportunities"
    if "RESEARCH_DIGEST" in route or level == "validated_digest":
        return "Validated Digest Core Opportunities"
    if near_miss is not None:
        return "Near-Miss Candidates"
    return "Quality-Capped / Local-Only Candidates"


def _card_group_for_audit(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    core: event_core_opportunities.CoreOpportunity | None,
    near_miss: event_near_miss.EventNearMissCandidate | None,
) -> str:
    text = " ".join(str(value or "") for value in (
        row.get("candidate_role"),
        components.get("candidate_role"),
        row.get("impact_path_type"),
        components.get("impact_path_type"),
        row.get("source_class"),
        components.get("source_class"),
        row.get("latest_effective_playbook_type"),
        row.get("playbook_type"),
    )).casefold()
    if "source_noise" in text or "ticker_word_collision" in text or "generic_cooccurrence_only" in text:
        return "Diagnostic / Source-Noise / Control Cards"
    if core is not None and (core.is_high_priority or core.is_watchlist or core.is_validated_digest or core.alertable):
        return "Core Opportunity Cards"
    if near_miss is not None:
        return "Near-Miss Cards"
    if str(row.get("final_state_after_quality_gate") or row.get("state") or "").upper() == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value:
        return "Local-Only / Quality-Capped Cards"
    return "Local-Only / Quality-Capped Cards"


def _operator_presentation_reason(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    core: event_core_opportunities.CoreOpportunity | None,
    near_miss: event_near_miss.EventNearMissCandidate | None,
) -> str:
    if core is not None:
        return core.why_opportunity_visible
    if near_miss is not None:
        return "close to promotion but still missing " + (_human_reason_list(near_miss.missing_evidence) or "confirmation")
    level = str(components.get("opportunity_level") or row.get("opportunity_level") or "local_only")
    return f"quality verdict is {level.replace('_', ' ')}; keep as local research evidence"


_HUMAN_REASON_LABELS = {
    "quality_context_missing": "missing enough validated context",
    "needs_direct_token_mechanism": "needs proof that this event directly affects the token",
    "needs_market_confirmation": "no convincing market reaction yet",
    "market_confirmation": "no convincing market reaction yet",
    "cause_unknown_market_dislocation": "token moved, but the cause is unknown",
    "generic_cooccurrence_only": "token and event appeared together, but no impact mechanism was proven",
    "impact_path_type_insufficient_data": "not enough evidence to establish the impact mechanism",
    "impact_path_not_strong_enough": "impact path is not strong enough yet",
    "needs_strong_market_confirmation": "needs stronger price/volume confirmation",
    "blocked_by_low_score": "research score is still too low",
}


def _human_reason_list(values: Iterable[Any]) -> str:
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        out.append(_HUMAN_REASON_LABELS.get(text, text.replace("_", " ")))
    return "; ".join(dict.fromkeys(out))


def _human_action_list(values: Iterable[Any]) -> str:
    mapping = {
        "targeted_market_refresh": "refresh market/volume context",
        "targeted_derivatives_refresh": "check derivatives crowding",
        "targeted_supply_refresh": "check supply pressure",
        "targeted_evidence_refresh": "find independent catalyst evidence",
        "operator_review": "manual analyst review",
    }
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            out.append(mapping.get(text, text.replace("_", " ")))
    return "; ".join(dict.fromkeys(out))


def _find_core_match(
    target: str,
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
) -> event_core_opportunities.CoreOpportunity | None:
    clean = target[3:] if target.startswith("ea:") else target
    clean_l = clean.lower()
    for item in opportunities:
        identifiers = {
            item.core_opportunity_id,
            item.symbol,
            item.coin_id,
            item.incident_id or "",
            item.canonical_incident_name or "",
        }
        identifiers.update(str(value) for value in item.supporting_hypothesis_ids)
        identifiers.update(str(row.get("key") or "") for row in item.supporting_rows)
        identifiers.update(str(row.get("alert_key") or "") for row in item.supporting_rows)
        if clean in identifiers or clean_l in {value.lower() for value in identifiers if value}:
            return item
    return None


def _core_opportunity_lines(
    item: event_core_opportunities.CoreOpportunity,
    *,
    include_diagnostics: bool,
) -> list[str]:
    lines = [
        "## Core Opportunity",
        f"- core_opportunity_id: {item.core_opportunity_id}",
        f"- incident: {item.incident_id or 'unknown'} / {item.canonical_incident_name or 'unknown'}",
        f"- primary impact path: {item.primary_impact_path}",
        f"- final route/state: {item.final_route_after_quality_gate or 'local'} / {item.final_state_after_quality_gate or 'unknown'}",
        f"- opportunity: {item.opportunity_level} score={item.opportunity_score_final:.0f}",
        f"- aggregation reason: {item.why_opportunity_visible}",
        f"- supporting rows hidden from main view: {item.why_other_rows_hidden}",
        f"- supporting hypothesis ids: {_list_value(item.supporting_hypothesis_ids)}",
        f"- supporting categories: {_list_value(item.supporting_categories)}",
        f"- supporting impact paths: {_list_value(item.supporting_impact_paths)}",
    ]
    if item.supporting_evidence_quotes:
        lines.append("- supporting evidence: " + _list_value(item.supporting_evidence_quotes[:4]))
    if item.diagnostic_row_count:
        lines.append(
            f"- hidden diagnostics: {item.diagnostic_row_count} "
            f"(source_noise_controls={item.source_noise_control_count})"
        )
        if include_diagnostics:
            for row in item.diagnostic_rows[:6]:
                lines.append(
                    "  - diagnostic: "
                    f"{row.get('symbol') or row.get('validated_symbol') or 'UNKNOWN'}/"
                    f"{row.get('coin_id') or row.get('validated_coin_id') or 'unknown'} "
                    f"playbook={row.get('latest_effective_playbook_type') or row.get('playbook_type') or 'unknown'} "
                    f"reason={row.get('quality_gate_block_reason') or row.get('suppressed_reason') or row.get('why_local_only') or 'diagnostic'}"
                )
        else:
            lines.append("- diagnostics hidden by default; pass include_diagnostics in local tooling to inspect controls.")
    lines.append("")
    return lines


def _find_match(
    target: str,
    hypotheses: Iterable[Mapping[str, Any] | object],
    entries: Iterable[event_watchlist.EventWatchlistEntry | Mapping[str, Any]],
    alerts: Iterable[Mapping[str, Any]],
    decisions: Iterable[event_alpha_router.EventAlphaRouteDecision | Mapping[str, Any]],
    incidents: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any] | None:
    clean = target[3:] if target.startswith("ea:") else target
    for decision in decisions:
        if isinstance(decision, event_alpha_router.EventAlphaRouteDecision):
            if target in {
                decision.alert_id,
                decision.card_id,
                "ea:" + decision.entry.key,
                decision.entry.key,
                decision.entry.event_id,
                decision.entry.symbol,
                decision.entry.coin_id,
            } or clean in {decision.entry.symbol, decision.entry.coin_id}:
                return {
                    "source": "route_decision",
                    "row": _entry_row(decision.entry),
                    "route": decision.route.value,
                    "lane": decision.lane.value,
                    "reason": decision.reason,
                }
        else:
            row = dict(decision)
            if _row_matches(row, clean, target):
                return {"source": "route_decision", "row": row}
    for entry in entries:
        row = _entry_row(entry)
        if _row_matches(row, clean, target):
            return {"source": "watchlist", "row": row}
    for row in alerts:
        row = dict(row)
        if _row_matches(row, clean, target):
            return {"source": "alert_snapshot", "row": row}
    for item in hypotheses:
        row = _row(item)
        if _row_matches(row, clean, target):
            return {"source": "impact_hypothesis", "row": row}
    for incident in incidents:
        row = dict(incident)
        if _row_matches(row, clean, target):
            return {"source": "incident", "row": row}
    return None


def _row_matches(row: Mapping[str, Any], clean: str, original: str) -> bool:
    keys = {
        row.get("alert_id"),
        row.get("alert_key"),
        row.get("card_id"),
        row.get("key"),
        row.get("event_id"),
        row.get("hypothesis_id"),
        row.get("incident_id"),
        row.get("canonical_name"),
        row.get("symbol"),
        row.get("coin_id"),
        row.get("validated_symbol"),
        row.get("validated_coin_id"),
    }
    components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    keys.update({
        components.get("validated_symbol"),
        components.get("validated_coin_id"),
    })
    text_keys = {str(value) for value in keys if value not in (None, "")}
    return clean in text_keys or original in text_keys or ("ea:" + clean) in text_keys


def _entry_row(entry: event_watchlist.EventWatchlistEntry | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(entry, Mapping):
        return dict(entry)
    row = asdict(entry)
    row["alert_id"] = event_alpha_router.alert_id_for_entry(entry)
    row["card_id"] = event_alpha_router.card_id_for_entry(entry)
    return row


def _row(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}) or {})


def _components(row: Mapping[str, Any]) -> dict[str, Any]:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    if not components and isinstance(row.get("score_components"), Mapping):
        components = row.get("score_components")
    out = dict(components)
    for key, value in row.items():
        if key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS:
            if value not in (None, "", [], {}):
                out[key] = value
        elif key not in out and value not in (None, "", [], {}):
            out[key] = value
    return event_alpha_quality_fields.ensure_quality_fields(out)


def _incident_context(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    incidents: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    incident_id = str(row.get("incident_id") or components.get("incident_id") or "")
    if not incident_id:
        return row if str(row.get("row_type") or "") == "event_incident" else None
    for incident in incidents:
        if str(incident.get("incident_id") or "") == incident_id:
            return incident
    return row if row.get("incident_id") else None


def _incident_lines(
    incident: Mapping[str, Any] | None,
    row: Mapping[str, Any],
    components: Mapping[str, Any],
) -> list[str]:
    source = incident or row
    incident_id = source.get("incident_id") or components.get("incident_id")
    if not incident_id:
        return ["- incident link: no_incident"]
    claim_history = source.get("claim_history") or components.get("claim_history") or ()
    linked_assets = source.get("linked_assets") or components.get("linked_assets") or ()
    reaction_confirmed = source.get("market_reaction_confirmed")
    if reaction_confirmed is None:
        reaction_confirmed = components.get("market_reaction_confirmed")
    reaction_observed = source.get("market_reaction_observed")
    if reaction_observed is None:
        reaction_observed = components.get("market_reaction_observed")
    if reaction_observed is None:
        reaction_observed = reaction_confirmed
    causal = source.get("causal_mechanism_confirmed")
    if causal is None:
        causal = components.get("causal_mechanism_confirmed")
    return [
        f"- incident_id: {incident_id}",
        f"- canonical name: {source.get('canonical_name') or source.get('canonical_incident_name') or components.get('canonical_incident_name') or 'unknown'}",
        f"- relevance: {source.get('incident_relevance_status') or components.get('incident_relevance_status') or 'unknown'} "
        f"score={source.get('incident_relevance_score') or components.get('incident_relevance_score') or 'n/a'}",
        f"- persistence reason: {source.get('canonical_persistence_reason') or components.get('canonical_persistence_reason') or 'unknown'}",
        f"- relevance reasons: {_list_value(source.get('incident_relevance_reasons') or components.get('incident_relevance_reasons'))}",
        (
            "- link quality: "
            f"raw={source.get('raw_link_count') or components.get('raw_link_count') or 0}, "
            f"qualified={source.get('qualified_link_count') or components.get('qualified_link_count') or 0}, "
            f"weak={source.get('weak_link_count') or components.get('weak_link_count') or 0}, "
            f"quality_blocked={source.get('quality_blocked_link_count') or components.get('quality_blocked_link_count') or 0}, "
            f"unknown_role={source.get('unknown_role_link_count') or components.get('unknown_role_link_count') or 0}"
        ),
        "- link quality reasons: "
        + _list_value(source.get("link_quality_reasons") or components.get("link_quality_reasons")),
        "- weak-link explanation: "
        + (
            "this candidate qualified the incident"
            if int(source.get("qualified_link_count") or components.get("qualified_link_count") or 0) > 0
            else "weak or quality-blocked links do not make an incident active"
        ),
        f"- primary subject: {source.get('primary_subject') or components.get('primary_subject') or 'unknown'}",
        f"- main catalyst frame: {source.get('main_frame_type') or components.get('main_frame_type') or 'unknown'} "
        f"({source.get('main_frame_role') or components.get('main_frame_role') or 'unknown'})",
        f"- frame status: {source.get('frame_status') or components.get('frame_status') or 'unknown'}",
        f"- main catalyst subject/actor/object: "
        f"{source.get('main_frame_subject') or components.get('main_frame_subject') or 'unknown'} / "
        f"{source.get('main_frame_actor') or components.get('main_frame_actor') or 'unknown'} / "
        f"{source.get('main_frame_object') or components.get('main_frame_object') or 'unknown'}",
        f"- main catalyst evidence: {source.get('main_frame_evidence_quote') or components.get('main_frame_evidence_quote') or 'none'}",
        f"- selected main catalyst reason: {source.get('selected_main_catalyst_reason') or components.get('selected_main_catalyst_reason') or 'unknown'}",
        f"- rule vs LLM frame: rule={source.get('rule_predicted_impact_path') or components.get('rule_predicted_impact_path') or 'unknown'} "
        f"llm={source.get('llm_predicted_main_frame_type') or components.get('llm_predicted_main_frame_type') or 'unknown'} "
        f"disagreement={source.get('frame_rule_disagreement') if source.get('frame_rule_disagreement') is not None else components.get('frame_rule_disagreement', 'unknown')} "
        f"resolution={source.get('disagreement_resolution') or components.get('disagreement_resolution') or 'unknown'}",
        f"- background context: {source.get('background_context_summary') or components.get('background_context_summary') or 'none'}",
        f"- negated/corrective frame count: "
        f"{len(source.get('negated_frame_ids') or components.get('negated_frame_ids') or []) + len(source.get('corrective_frame_ids') or components.get('corrective_frame_ids') or [])}",
        f"- rejected/background impact paths: {_list_value(source.get('rejected_impact_paths') or components.get('rejected_impact_paths'))}",
        f"- affected ecosystem: {source.get('affected_ecosystem') or components.get('affected_ecosystem') or 'unknown'}",
        f"- current cause status: {source.get('current_cause_status') or source.get('cause_status') or components.get('cause_status') or 'unknown'}",
        f"- claim history: {_claim_history_value(claim_history)}",
        f"- conflicting claims: {_list_value(source.get('conflicting_claims') or components.get('conflicting_claims'))}",
        f"- source updates: {source.get('source_update_count') or len(source.get('source_raw_ids') or []) or 'unknown'} "
        f"(independent={source.get('independent_source_count') or len(source.get('independent_source_domains') or []) or 'unknown'})",
        f"- market reaction vs causal mechanism: observed={str(bool(reaction_observed)).lower()} "
        f"confirmed={str(bool(reaction_confirmed)).lower()} "
        f"causal={str(bool(causal)).lower()} "
        f"source={source.get('market_context_source') or components.get('market_context_source') or 'none'}",
        f"- linked assets and roles: {_asset_list(linked_assets) if linked_assets else _asset_role_summary(row, components)}",
    ]


def _claim_history_value(value: Any) -> str:
    if not value:
        return "none"
    labels: list[str] = []
    for item in list(value)[:4]:
        if isinstance(item, Mapping):
            labels.append(
                f"{item.get('claim_type') or 'claim'}:"
                f"{item.get('polarity') or 'unknown'}/"
                f"{item.get('cause_status') or 'unknown'}"
            )
        else:
            labels.append(str(item))
    return "; ".join(labels) or "none"


def _asset_role_summary(row: Mapping[str, Any], components: Mapping[str, Any]) -> str:
    symbol = components.get("validated_symbol") or row.get("validated_symbol") or row.get("symbol")
    coin_id = components.get("validated_coin_id") or row.get("validated_coin_id") or row.get("coin_id")
    role = components.get("candidate_role") or row.get("candidate_role") or "unknown"
    if symbol or coin_id:
        return f"{symbol or coin_id}({role})"
    return "none"


def _quality_source(row: Mapping[str, Any]) -> str:
    source = event_alpha_quality_fields.quality_source(row, components_key="latest_score_components")
    if source == "nested_score_components":
        return "nested_score_components"
    if source in {"partial_quality_fields", "recomputed"}:
        return "recomputed" if source == "recomputed" else "partial_top_level_recomputed"
    return source


def _value(row: Mapping[str, Any], *keys: Any, default: str = "unknown") -> str:
    for key in keys:
        if isinstance(key, str):
            value = row.get(key)
        else:
            value = key
        if value not in (None, "", [], {}):
            return str(value)
    return default


def _list_value(value: Any) -> str:
    if value in (None, "", [], ()):
        return "none"
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return ", ".join(f"{key}={child}" for key, child in list(value.items())[:6])
    return "; ".join(str(item) for item in list(value)[:6])


def _asset_list(value: Any) -> str:
    if not value:
        return "none"
    if isinstance(value, Mapping):
        value = [value]
    rows = []
    for item in list(value)[:6]:
        if isinstance(item, Mapping):
            rows.append(
                f"{item.get('symbol') or item.get('coin_id') or item.get('name') or 'asset'}"
                f"({item.get('rejection_reason') or item.get('identity_reason') or item.get('source') or 'candidate'})"
            )
        else:
            rows.append(str(item))
    return "; ".join(rows)


def _audit_feedback_target(row: Mapping[str, Any], fallback: str) -> str:
    return str(row.get("alert_id") or row.get("key") or row.get("hypothesis_id") or fallback)
