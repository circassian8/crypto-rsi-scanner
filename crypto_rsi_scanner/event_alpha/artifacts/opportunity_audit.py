"""Decision-path audit reports for Event Alpha research opportunities."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss
import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict
import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs
import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from . import reason_text as event_alpha_reason_text
from . import research_cards as event_research_cards
from .opportunity_audit_matching import (
    _audit_feedback_target,
    _matching_card_paths,
    _target_from_card_path,
)
from .opportunity_audit_values import (
    _as_list_values,
    _asset_list,
    _asset_role_summary,
    _claim_history_value,
    _collect_core_row_values,
    _components,
    _entry_row,
    _float_value,
    _incident_context,
    _list_value,
    _market_age_value,
    _quality_source,
    _role_capabilities_value,
    _row,
    _value,
)


def _first_present(*values: Any, default: Any = None) -> Any:
    return next(
        (value for value in values if value not in (None, "")),
        default,
    )


def format_opportunity_audit(
    target: str,
    *,
    hypotheses: Iterable[Mapping[str, Any] | object] = (),
    core_opportunity_rows: Iterable[Mapping[str, Any] | object] = (),
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry | Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision | Mapping[str, Any]] = (),
    incident_rows: Iterable[Mapping[str, Any]] = (),
    card_paths: Iterable[str | Path] = (),
    feedback_rows: Iterable[Mapping[str, Any] | object] = (),
    profile: str | None = None,
    include_diagnostics: bool = False,
    now: datetime | None = None,
) -> str:
    """Explain one candidate's research-only decision path."""
    clean = str(target or "").strip()
    if not clean:
        return "Event opportunity audit failed: target is required."
    evaluated_at = now or datetime.now(timezone.utc)
    evaluated_at = (
        evaluated_at.astimezone(timezone.utc)
        if evaluated_at.tzinfo is not None
        else evaluated_at.replace(tzinfo=timezone.utc)
    )
    resolved_target = _target_from_card_path(clean, card_paths) or clean
    hypothesis_items = list(hypotheses)
    core_items = list(core_opportunity_rows)
    watchlist_items = list(watchlist_entries)
    alert_items = list(alert_rows)
    decision_items = list(route_decisions)
    incidents = [dict(row) for row in incident_rows if isinstance(row, Mapping)]
    core_view = event_core_opportunity_store.canonical_core_opportunity_view_from_rows(
        resolved_target,
        core_rows=core_items,
        supporting_rows=[*hypothesis_items, *watchlist_items, *alert_items, *decision_items],
        alert_rows=alert_items,
        incident_rows=incidents,
        feedback_rows=feedback_rows,
        card_paths=card_paths,
        profile=profile,
        now=evaluated_at,
    )
    stored_core_opportunities = (
        (core_view.core_opportunity,)
        if core_view.found and core_view.core_opportunity is not None
        else event_core_opportunities.aggregate_core_opportunities(core_items)
    )
    core_opportunities = stored_core_opportunities or event_core_opportunities.aggregate_core_opportunities([
        *decision_items,
        *watchlist_items,
        *alert_items,
        *hypothesis_items,
    ])
    core_match = core_view.core_opportunity if core_view.found else _find_core_match(resolved_target, core_opportunities)
    match = (
        {
            "source": "core_opportunity",
            "row": core_view.canonical_core_row or core_match.primary_row,
            "core_opportunity": core_match,
        }
        if core_match is not None
        else _find_match(resolved_target, hypothesis_items, watchlist_items, alert_items, decision_items, incidents)
    )
    if match is None:
        return _no_match_audit_report(
            clean,
            resolved_target,
            core_items,
            profile=profile,
        )
    row = match["row"]
    resolution_rows = core_items or ([core_match.primary_row] if core_match is not None else [])
    core_resolution = event_core_opportunities.resolve_canonical_core_opportunity_id(row, resolution_rows)
    components = _components(row)
    incident = core_view.incident_row or _incident_context(row, components, incidents)
    upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
    verdict_copy = event_opportunity_verdict.build_verdict_aware_upgrade_downgrade_text(components)
    near_miss = event_near_miss.near_miss_metadata_for_row(row)
    daily_section = _daily_brief_section(row, components, core_match, near_miss)
    card_group = _card_group_for_audit(row, components, core_match, near_miss)
    matching_cards = _matching_card_paths(resolved_target, row, core_match, card_paths)
    if core_view.research_card_path:
        matching_cards = tuple(dict.fromkeys([Path(core_view.research_card_path), *matching_cards]))
    feedback_target = _audit_feedback_target(row, resolved_target, core_match, matching_cards)
    feedback_matches = core_view.feedback_rows
    feedback_status = (
        core_view.feedback_status
        if core_view.found
        else "pending_or_unknown"
    )
    feedback_labels = tuple(
        dict.fromkeys(
            str(item.get("feedback_label"))
            for item in feedback_matches
            if str(item.get("feedback_label") or "")
        )
    )
    return "\n".join(_opportunity_audit_lines(
        clean=clean,
        profile=profile,
        match=match,
        core_resolution=core_resolution,
        row=row,
        components=components,
        core_view=core_view,
        core_match=core_match,
        incident=incident,
        near_miss=near_miss,
        daily_section=daily_section,
        card_group=card_group,
        matching_cards=matching_cards,
        feedback_target=feedback_target,
        feedback_status=feedback_status,
        feedback_labels=feedback_labels,
        verdict_copy=verdict_copy,
        upgrade=upgrade,
        include_diagnostics=include_diagnostics,
    ))


def _opportunity_audit_lines(
    *,
    clean: str,
    profile: str | None,
    match: Mapping[str, Any],
    core_resolution: event_core_opportunities.CanonicalCoreOpportunityResolution,
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    core_view: event_core_opportunity_store.CanonicalCoreOpportunityView,
    core_match: event_core_opportunities.CoreOpportunity | None,
    incident: Mapping[str, Any] | None,
    near_miss: event_near_miss.EventNearMissCandidate | None,
    daily_section: str,
    card_group: str,
    matching_cards: Iterable[Path],
    feedback_target: str,
    feedback_status: str,
    feedback_labels: Iterable[str],
    verdict_copy: event_opportunity_verdict.VerdictAwareUpgradeDowngradeText,
    upgrade: event_opportunity_verdict.UpgradePathExplanation,
    include_diagnostics: bool,
) -> list[str]:
    return [
        *_opportunity_audit_header_lines(clean, profile, match, core_resolution, row),
        *_candidate_summary_audit_lines(row, components, core_match, include_diagnostics=include_diagnostics),
        *_operator_presentation_audit_lines(row, components, core_match, near_miss, daily_section, card_group, matching_cards, feedback_target),
        *_evidence_chain_audit_lines(row, components),
        *_identity_decision_audit_lines(row, components),
        "## Incident",
        *_incident_lines(incident, row, components),
        "",
        *_impact_and_evidence_quality_audit_lines(row, components),
        "## Source coverage and acquisition plan",
        *_source_acquisition_audit_lines(row, components),
        *_official_exchange_audit_section(row, components),
        "",
        *_market_confirmation_audit_lines(row, components),
        *_opportunity_lane_audit_lines(row, components),
        *_final_verdict_audit_lines(row, components),
        "## Near-miss status",
        *_near_miss_lines(near_miss, row),
        "",
        *_router_and_reconciliation_audit_lines(match, core_view, row, include_diagnostics=include_diagnostics),
        *_notification_feedback_audit_lines(row, feedback_status, feedback_labels),
        *_feedback_evidence_diagnostic_lines(core_view),
        *_upgrade_downgrade_audit_lines(row, components, verdict_copy, upgrade, feedback_target, profile),
        "No secrets, Telegram sends, trades, paper rows, normal RSI rows, or event-fade state were touched.",
    ]


def _opportunity_audit_header_lines(
    clean: str,
    profile: str | None,
    match: Mapping[str, Any],
    core_resolution: event_core_opportunities.CanonicalCoreOpportunityResolution,
    row: Mapping[str, Any],
) -> list[str]:
    return [
        "=" * 76,
        "EVENT OPPORTUNITY AUDIT (research-only)",
        "=" * 76,
        f"target: {clean}",
        f"profile: {profile or 'default'}",
        f"matched_source: {match['source']}",
        f"canonical_core_opportunity_id: {core_resolution.canonical_core_opportunity_id or 'none'}",
        f"input target resolution status: {core_resolution.resolution_status}",
        f"diagnostic_support_for_core_opportunity_id: {core_resolution.diagnostic_support_for_core_opportunity_id or 'none'}",
        f"canonical resolution warnings: {_list_value(core_resolution.warnings) if core_resolution.warnings else 'none'}",
        f"quality_field_source: {_quality_source(row)}",
        "",
    ]


def _candidate_summary_audit_lines(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    core_match: event_core_opportunities.CoreOpportunity | None,
    *,
    include_diagnostics: bool,
) -> list[str]:
    return [
        "## Candidate summary",
        f"- symbol/coin: {_value(row, 'symbol', components.get('validated_symbol'), default='SECTOR')}/{_value(row, 'coin_id', components.get('validated_coin_id'), default='unknown')}",
        f"- event/hypothesis: {_value(row, 'event_id', 'hypothesis_id', default='unknown')}",
        f"- external catalyst: {_value(row, 'external_asset', components.get('external_asset'), default='unknown')}",
        f"- playbook: {_value(row, 'playbook_type', 'latest_playbook_type', components.get('playbook_type'), default='unknown')}",
        f"- state/tier: {_value(row, 'state', default='unknown')} / {_value(row, 'tier', 'latest_tier', default='unknown')}",
        "",
        *(_core_opportunity_lines(core_match, include_diagnostics=include_diagnostics) if core_match is not None else []),
    ]


def _operator_presentation_audit_lines(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    core_match: event_core_opportunities.CoreOpportunity | None,
    near_miss: event_near_miss.EventNearMissCandidate | None,
    daily_section: str,
    card_group: str,
    matching_cards: Iterable[Path],
    feedback_target: str,
) -> list[str]:
    card_paths = tuple(matching_cards)
    return [
        "## Operator Presentation",
        f"- Daily brief section: {daily_section}",
        f"- Research card group: {card_group}",
        f"- Card path: {_list_value(str(path) for path in card_paths) if card_paths else 'none'}",
        f"- Feedback target: {feedback_target}",
        "- Reason: " + _operator_presentation_reason(row, components, core_match, near_miss),
        "",
    ]


def _evidence_chain_audit_lines(row: Mapping[str, Any], components: Mapping[str, Any]) -> list[str]:
    return [
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
    ]


def _identity_decision_audit_lines(row: Mapping[str, Any], components: Mapping[str, Any]) -> list[str]:
    return [
        "## Identity decision",
        f"- validated symbol: {components.get('validated_symbol') or row.get('validated_symbol') or row.get('symbol') or 'unknown'}",
        f"- validated coin_id: {components.get('validated_coin_id') or row.get('validated_coin_id') or row.get('coin_id') or 'unknown'}",
        f"- candidate role: {components.get('candidate_role') or row.get('candidate_role') or 'unknown'}",
        f"- asset kind: {components.get('asset_kind') or row.get('asset_kind') or 'unknown'}",
        f"- role source: {components.get('role_source') or components.get('asset_role_source') or row.get('role_source') or row.get('asset_role_source') or 'unknown'}",
        f"- identity confidence: {components.get('identity_confidence') if components.get('identity_confidence') is not None else row.get('identity_confidence', 'n/a')}",
        f"- identity evidence: {_list_value(components.get('identity_evidence') or row.get('identity_evidence'))}",
        f"- collision risk: {components.get('collision_risk') or row.get('collision_risk') or 'none'}",
        f"- role capabilities: {_role_capabilities_value(components.get('role_capabilities') or row.get('role_capabilities'))}",
        f"- role validation failures: {_list_value(components.get('role_validation_failures') or row.get('role_validation_failures'))}",
        f"- identity warnings: {_list_value(row.get('warnings') or components.get('warnings'))}",
        "",
    ]


def _impact_and_evidence_quality_audit_lines(row: Mapping[str, Any], components: Mapping[str, Any]) -> list[str]:
    return [
        "## Impact path decision",
        f"- impact path: {components.get('impact_path_type') or row.get('impact_path_type') or components.get('primary_impact_path') or row.get('primary_impact_path') or 'unknown'}",
        f"- strength: {components.get('impact_path_strength') or row.get('impact_path_strength') or 'unknown'}",
        f"- reason: {components.get('impact_path_reason') or row.get('impact_path_reason') or 'unknown'}",
        f"- digest gate: {components.get('digest_eligible_by_impact_path') if components.get('digest_eligible_by_impact_path') is not None else 'unknown'}",
        "",
        "## Evidence quality decision",
        f"- source/evidence: {components.get('source_class') or row.get('source_class') or 'unknown'} / {components.get('evidence_specificity') or row.get('evidence_specificity') or 'unknown'}",
        f"- evidence score: {_first_present(components.get('evidence_quality_score'), row.get('evidence_quality_score'), default='n/a')}",
        "",
    ]


def _market_confirmation_audit_lines(row: Mapping[str, Any], components: Mapping[str, Any]) -> list[str]:
    return [
        "## Market confirmation decision",
        f"- market level/score: {components.get('market_confirmation_level') or row.get('market_confirmation_level') or 'unknown'} / {_first_present(components.get('market_confirmation_score'), row.get('market_confirmation_score'), default='n/a')}",
        f"- market freshness: {components.get('market_context_freshness_status') or row.get('market_context_freshness_status') or 'unknown'} "
        f"age={_market_age_value(components, row)} "
        f"cap_applied={components.get('market_context_freshness_cap_applied') if components.get('market_context_freshness_cap_applied') is not None else row.get('market_context_freshness_cap_applied')}",
        f"- market reasons: {_list_value(components.get('market_confirmation_reasons') or row.get('market_confirmation_reasons'))}",
        f"- market missing: {_list_value(components.get('market_confirmation_missing_fields') or row.get('market_confirmation_missing_fields'))}",
        f"- derivatives confirmation: {components.get('derivatives_confirmation_level') or row.get('derivatives_confirmation_level') or 'unknown'} / "
        f"{_first_present(components.get('derivatives_confirmation_score'), row.get('derivatives_confirmation_score'), default='n/a')} "
        f"freshness={components.get('derivatives_freshness_status') or row.get('derivatives_freshness_status') or 'unknown'}",
        f"- DEX liquidity confirmation: {components.get('dex_liquidity_level') or row.get('dex_liquidity_level') or 'unknown'} / "
        f"{_first_present(components.get('dex_liquidity_score'), row.get('dex_liquidity_score'), default='n/a')} "
        f"freshness={components.get('dex_freshness_status') or row.get('dex_freshness_status') or 'unknown'}",
        f"- protocol metrics confirmation: {components.get('protocol_metrics_level') or row.get('protocol_metrics_level') or 'unknown'} / "
        f"{_first_present(components.get('protocol_metrics_score'), row.get('protocol_metrics_score'), default='n/a')} "
        f"freshness={components.get('protocol_metrics_freshness_status') or row.get('protocol_metrics_freshness_status') or 'unknown'}",
        "",
    ]


def _opportunity_lane_audit_lines(row: Mapping[str, Any], components: Mapping[str, Any]) -> list[str]:
    return [
        "## Opportunity lane decision",
        f"- opportunity type: {components.get('opportunity_type') or row.get('opportunity_type') or 'unknown'}",
        f"- market state: {components.get('market_state_class') or row.get('market_state_class') or components.get('market_state') or row.get('market_state') or 'unknown'}",
        f"- source strength: {components.get('source_strength') or row.get('source_strength') or components.get('opportunity_type_source_strength') or row.get('opportunity_type_source_strength') or 'unknown'}",
        f"- requirements: source={components.get('source_requirements_met') if components.get('source_requirements_met') is not None else row.get('source_requirements_met', row.get('opportunity_type_source_requirements_met', 'unknown'))} "
        f"market={components.get('market_requirements_met') if components.get('market_requirements_met') is not None else row.get('market_requirements_met', row.get('opportunity_type_market_requirements_met', 'unknown'))} "
        f"fade={components.get('fade_requirements_met') if components.get('fade_requirements_met') is not None else row.get('fade_requirements_met', row.get('opportunity_type_fade_requirements_met', 'unknown'))}",
        f"- why now: {components.get('why_now') or row.get('why_now') or components.get('opportunity_type_why_now') or row.get('opportunity_type_why_now') or 'unknown'}",
        f"- what confirms: {_list_value(components.get('what_confirms') or row.get('what_confirms') or components.get('opportunity_type_what_confirms') or row.get('opportunity_type_what_confirms'))}",
        f"- what invalidates: {_list_value(components.get('what_invalidates') or row.get('what_invalidates') or components.get('opportunity_type_what_invalidates') or row.get('opportunity_type_what_invalidates'))}",
        f"- why not alertable: {_list_value(components.get('why_not_alertable') or row.get('why_not_alertable') or components.get('opportunity_type_why_not_alertable') or row.get('opportunity_type_why_not_alertable'))}",
        "",
    ]


def _final_verdict_audit_lines(row: Mapping[str, Any], components: Mapping[str, Any]) -> list[str]:
    return [
        "## Final opportunity verdict",
        f"- level/score: {components.get('final_opportunity_level') or row.get('final_opportunity_level') or components.get('opportunity_level') or row.get('opportunity_level') or 'unknown'} / {_first_present(components.get('final_opportunity_score'), row.get('final_opportunity_score'), components.get('opportunity_score_final'), row.get('opportunity_score_final'), default='n/a')}",
        f"- source/reason: {components.get('final_verdict_source') or row.get('final_verdict_source') or 'initial'} / {components.get('final_verdict_reason') or row.get('final_verdict_reason') or 'none'}",
        f"- reasons: {_list_value(components.get('opportunity_verdict_reasons') or row.get('opportunity_verdict_reasons'))}",
        f"- why local-only: {_human_reason_value(components.get('why_local_only') or row.get('why_local_only')) or 'none'}",
        f"- why not watchlist: {_human_reason_value(components.get('why_not_watchlist') or row.get('why_not_watchlist')) or 'none'}",
        "",
    ]


def _router_and_reconciliation_audit_lines(
    match: Mapping[str, Any],
    core_view: event_core_opportunity_store.CanonicalCoreOpportunityView,
    row: Mapping[str, Any],
    *,
    include_diagnostics: bool,
) -> list[str]:
    return [
        "## Router decision",
        f"- route: {_value(row, 'route', default=match.get('route') or 'not_routed')}",
        f"- notification lane: {_value(row, 'lane', default=match.get('lane') or 'local_only')}",
        f"- router reason: {_value(row, 'route_reason', 'reason', default=match.get('reason') or 'not routed or stored locally')}",
        "- TRIGGERED_FADE was not created unless the row is already a deterministic proxy_fade/event_fade trigger.",
        "",
        "## Alert snapshot / core reconciliation",
        *_snapshot_core_reconciliation_lines(core_view, row, include_diagnostics=include_diagnostics),
        "",
    ]


def _notification_feedback_audit_lines(
    row: Mapping[str, Any],
    feedback_status: str,
    feedback_labels: Iterable[str],
) -> list[str]:
    labels = tuple(feedback_labels)
    return [
        "## Notification and feedback status",
        f"- delivery status: {_value(row, 'delivered_status', 'delivery_state', default='not_delivered_or_unknown')}",
        f"- feedback status: {feedback_status}",
        f"- feedback label: {_list_value(labels) if labels else 'none'}",
        f"- outcome status: {_value(row, 'outcome_status', default='pending_or_unknown')}",
        "",
    ]


def _feedback_evidence_diagnostic_lines(
    core_view: event_core_opportunity_store.CanonicalCoreOpportunityView,
) -> list[str]:
    reason_counts = core_view.feedback_exclusion_reason_counts
    reasons = (
        "; ".join(
            f"{reason}={count}"
            for reason, count in sorted(reason_counts.items())
        )
        if reason_counts
        else "none"
    )
    return [
        "## Feedback evidence diagnostics",
        f"- feedback rows supplied: {core_view.feedback_rows_supplied}",
        f"- eligible exact-Core feedback rows: {core_view.feedback_rows_eligible}",
        f"- eligible feedback rows matched to this Core: {core_view.feedback_rows_matched_to_core}",
        f"- eligible feedback rows for other Core opportunities: {core_view.feedback_rows_eligible_other_core}",
        f"- excluded feedback rows: {core_view.feedback_rows_excluded}",
        f"- aggregate exclusion reasons: {reasons}",
        "- Excluded feedback is aggregate diagnostics only and never supplies audit status or labels.",
        "",
    ]


def _upgrade_downgrade_audit_lines(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    verdict_copy: event_opportunity_verdict.VerdictAwareUpgradeDowngradeText,
    upgrade: event_opportunity_verdict.UpgradePathExplanation,
    feedback_target: str,
    profile: str | None,
) -> list[str]:
    promoted = _is_promoted_audit_row(components, row)
    return [
        "## Missing evidence",
        f"- missing requirements: {_audit_missing_evidence_text(components, row, verdict_copy)}",
        "",
        "## What would upgrade this candidate",
        "- " + (
            verdict_copy.upgrade_text
            if promoted
            else (event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.upgrade_requirements, limit=8) or verdict_copy.upgrade_text)
        ),
        "",
        "## What would downgrade / invalidate this candidate",
        "- " + (
            verdict_copy.downgrade_text
            if promoted
            else (event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.downgrade_warnings, limit=8) or verdict_copy.downgrade_text)
        ),
        "",
        "## Feedback command",
        f"- make event-feedback-watch PROFILE={profile or 'notify_llm'} FEEDBACK_TARGET='{feedback_target}'",
        "",
    ]


def _snapshot_core_reconciliation_lines(
    core_view: event_core_opportunity_store.CanonicalCoreOpportunityView,
    row: Mapping[str, Any],
    *,
    include_diagnostics: bool = False,
) -> list[str]:
    snapshots = list(core_view.alert_snapshot_rows)
    if not snapshots and str(row.get("row_type") or "") == "event_alpha_alert_snapshot":
        snapshots = [dict(row)]
    core_route = core_view.final_route_after_quality_gate or row.get("final_route_after_quality_gate") or row.get("route") or "unknown"
    core_level = core_view.opportunity_level or row.get("final_opportunity_level") or row.get("opportunity_level") or "unknown"
    if not snapshots:
        return [
            f"- snapshot found: false",
            f"- canonical core final route/level: {core_route} / {core_level}",
            "- alertable after reconciliation: false",
        ]
    snap = _primary_snapshot_for_audit(snapshots)
    final_route = str(snap.get("final_route_after_quality_gate") or snap.get("route") or "")
    requested = str(snap.get("requested_route_before_core_reconciliation") or snap.get("requested_route_before_quality_gate") or "")
    status = str(snap.get("snapshot_core_resolution_status") or snap.get("core_resolution_status") or snap.get("core_opportunity_id_status") or "unknown")
    lines = [
        "- snapshot found: true",
        f"- primary snapshot class: {snap.get('snapshot_class') or 'unknown'}",
        f"- snapshot route before reconciliation: {requested or 'unknown'}",
        f"- snapshot route after reconciliation: {final_route or 'unknown'}",
        f"- canonical core final route/level: {core_route} / {core_level}",
        f"- reconciliation status: {status}",
        f"- reconciliation reason: {snap.get('snapshot_core_reconciliation_reason') or 'none'}",
        f"- alertable after reconciliation: {str(event_alpha_router.route_value_is_alertable(final_route)).lower()}",
    ]
    diagnostics = [item for item in snapshots if _snapshot_is_diagnostic(item)]
    if diagnostics:
        if include_diagnostics:
            lines.append("### Diagnostic/support snapshots")
            for diag in diagnostics[:8]:
                lines.append(
                    "- diagnostic snapshot: "
                    f"alert_id={diag.get('alert_id') or diag.get('snapshot_id') or 'unknown'} "
                    f"class={diag.get('snapshot_class') or 'unknown'} "
                    f"route={diag.get('final_route_after_quality_gate') or diag.get('route') or 'unknown'} "
                    f"status={diag.get('snapshot_core_resolution_status') or diag.get('core_resolution_status') or 'unknown'} "
                    f"alertable={str(event_alpha_router.route_value_is_alertable(str(diag.get('final_route_after_quality_gate') or diag.get('route') or ''))).lower()}"
                )
        else:
            lines.append(f"- diagnostic/support snapshots hidden: {len(diagnostics)}")
    return lines


def _primary_snapshot_for_audit(snapshots: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(row) for row in snapshots if isinstance(row, Mapping)]
    if not rows:
        return {}

    def rank(row: Mapping[str, Any]) -> tuple[int, int, str]:
        diagnostic = _snapshot_is_diagnostic(row)
        snapshot_class = str(row.get("snapshot_class") or "")
        status = str(row.get("snapshot_core_resolution_status") or row.get("core_resolution_status") or "")
        canonical = (
            snapshot_class == "canonical_core_snapshot"
            or status in {"canonical", "core_reconciled"}
            or bool(row.get("snapshot_core_reconciled"))
        ) and not diagnostic
        alertable = event_alpha_router.route_value_is_alertable(
            str(row.get("final_route_after_quality_gate") or row.get("route") or "")
        )
        return (3 if canonical else 0, 1 if alertable and not diagnostic else 0, str(row.get("observed_at") or row.get("snapshot_id") or ""))

    return max(rows, key=rank)


def _snapshot_is_diagnostic(row: Mapping[str, Any]) -> bool:
    return (
        bool(row.get("is_diagnostic_snapshot"))
        or str(row.get("snapshot_class") or "") == "diagnostic_support_snapshot"
        or str(row.get("core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("snapshot_core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("core_opportunity_id_status") or "") == "diagnostic_support"
        or event_core_opportunities.row_is_diagnostic(row)
    )


def _no_match_audit_report(
    clean: str,
    resolved_target: str,
    core_store_rows: Iterable[Mapping[str, Any] | object],
    *,
    profile: str | None,
) -> str:
    core_resolution = event_core_opportunities.resolve_canonical_core_opportunity_id(
        {"core_opportunity_id": resolved_target},
        core_store_rows,
    )
    return "\n".join([
        "=" * 76,
        "EVENT OPPORTUNITY AUDIT (research-only)",
        "=" * 76,
        f"target: {clean}",
        f"profile: {profile or 'default'}",
        "matched_source: none",
        f"canonical_core_opportunity_id: {core_resolution.canonical_core_opportunity_id or 'none'}",
        f"input target resolution status: {core_resolution.resolution_status}",
        f"diagnostic_support_for_core_opportunity_id: {core_resolution.diagnostic_support_for_core_opportunity_id or 'none'}",
        f"canonical resolution warnings: {_list_value(core_resolution.warnings) if core_resolution.warnings else 'none'}",
        "No matching hypothesis, watchlist row, alert snapshot, or route decision found.",
        "No secrets, sends, trades, paper rows, normal RSI rows, or event-fade state were touched.",
    ])


def _near_miss_lines(
    near_miss: event_near_miss.EventNearMissCandidate | None,
    row: Mapping[str, Any],
) -> list[str]:
    if near_miss is None:
        if row.get("market_refresh_attempted") is not None:
            score_components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
            before = row.get("opportunity_level_before_refresh") or row.get("opportunity_level_before") or score_components.get("opportunity_level_before_refresh") or score_components.get("opportunity_level_before") or "unknown"
            after = row.get("opportunity_level_after_refresh") or row.get("opportunity_level_after") or score_components.get("opportunity_level_after_refresh") or score_components.get("opportunity_level_after") or row.get("opportunity_level") or "unknown"
            market_before = row.get("market_confirmation_before_refresh") or row.get("market_confirmation_before") or score_components.get("market_confirmation_before_refresh") or score_components.get("market_confirmation_before")
            market_after = row.get("market_confirmation_after_refresh") or row.get("market_confirmation_after") or score_components.get("market_confirmation_after_refresh") or score_components.get("market_confirmation_after") or row.get("market_confirmation_score")
            provider = row.get("market_refresh_provider") or score_components.get("market_refresh_provider") or row.get("market_context_source") or score_components.get("market_context_source")
            status = row.get("refresh_upgrade_status") or score_components.get("refresh_upgrade_status") or row.get("upgrade_reason") or score_components.get("upgrade_reason") or row.get("no_upgrade_reason") or score_components.get("no_upgrade_reason")
            return [
                "- status: targeted refresh previously applied",
                "- targeted refresh: "
                f"market={str(bool(row.get('market_refresh_attempted'))).lower()}/"
                f"{str(bool(row.get('market_refresh_success'))).lower()} "
                f"provider={provider or 'unknown'} "
                f"verdict={before}->{after} "
                f"market_confirmation={market_before if market_before is not None else 'n/a'}->{market_after if market_after is not None else 'n/a'} "
                f"status={status or 'pending'}",
            ]
        return ["- status: not close to promotion by current quality gates"]
    lines = [
        "- status: near-miss candidate",
        f"- near_miss_id: {near_miss.near_miss_id}",
        f"- score/level before refresh: {near_miss.opportunity_score_before:.0f} / {near_miss.opportunity_level_before}",
        "- missing evidence: " + (_human_reason_list(near_miss.missing_evidence) or "none"),
        "- recommended refresh: " + (_human_action_list(near_miss.recommended_refresh_actions) or "manual analyst review"),
    ]
    score_components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    before = row.get("opportunity_level_before_refresh") or row.get("opportunity_level_before") or score_components.get("opportunity_level_before_refresh") or score_components.get("opportunity_level_before")
    after = row.get("opportunity_level_after_refresh") or row.get("opportunity_level_after") or score_components.get("opportunity_level_after_refresh") or score_components.get("opportunity_level_after")
    score_before = row.get("opportunity_score_before_refresh") or row.get("opportunity_score_before") or score_components.get("opportunity_score_before_refresh") or score_components.get("opportunity_score_before")
    score_after = row.get("opportunity_score_after_refresh") or row.get("opportunity_score_after") or score_components.get("opportunity_score_after_refresh") or score_components.get("opportunity_score_after")
    market_before = row.get("market_confirmation_before_refresh") or row.get("market_confirmation_before") or score_components.get("market_confirmation_before_refresh") or score_components.get("market_confirmation_before")
    market_after = row.get("market_confirmation_after_refresh") or row.get("market_confirmation_after") or score_components.get("market_confirmation_after_refresh") or score_components.get("market_confirmation_after")
    provider = row.get("market_refresh_provider") or score_components.get("market_refresh_provider") or row.get("market_context_source") or score_components.get("market_context_source")
    status = row.get("refresh_upgrade_status") or score_components.get("refresh_upgrade_status") or row.get("upgrade_reason") or score_components.get("upgrade_reason") or row.get("no_upgrade_reason") or score_components.get("no_upgrade_reason")
    if before or after or row.get("market_refresh_attempted") is not None:
        lines.append(
            "- targeted refresh: "
            f"market={str(bool(row.get('market_refresh_attempted'))).lower()}/"
            f"{str(bool(row.get('market_refresh_success'))).lower()} "
            f"provider={provider or 'unknown'} "
            f"verdict={before or near_miss.opportunity_level_before}->{after or row.get('opportunity_level') or near_miss.opportunity_level_before} "
            f"score={score_before if score_before is not None else near_miss.opportunity_score_before}"
            f"->{score_after if score_after is not None else _first_present(row.get('opportunity_score_final'), default='n/a')} "
            f"market_confirmation={market_before if market_before is not None else 'n/a'}->{market_after if market_after is not None else 'n/a'} "
            f"status={status or 'pending'}"
        )
    return lines


def _source_acquisition_audit_lines(row: Mapping[str, Any], components: Mapping[str, Any]) -> list[str]:
    merged = {**dict(components or {}), **dict(row or {})}
    pack_name = str(merged.get("source_pack") or "")
    if not pack_name:
        impact_for_pack = str(merged.get("impact_path_type") or merged.get("primary_impact_path") or "")
        if impact_for_pack.casefold() in {"proxy_attention", "proxy_exposure"}:
            impact_for_pack = "venue_value_capture"
        pack = event_source_packs.source_pack_for_playbook(
            str(merged.get("playbook_type") or merged.get("latest_effective_playbook_type") or ""),
            impact_path_type=impact_for_pack,
            impact_category=str(merged.get("impact_category") or ""),
        )
        pack_name = pack.name
    else:
        pack = event_source_packs.get_source_pack(pack_name)
    assessment = event_source_registry.assess_source(
        merged,
        symbol=str(merged.get("validated_symbol") or merged.get("symbol") or ""),
        coin_id=str(merged.get("validated_coin_id") or merged.get("coin_id") or ""),
        provider_coverage_status=merged.get("provider_coverage_status"),
    )
    plan = merged.get("evidence_acquisition_plan") if isinstance(merged.get("evidence_acquisition_plan"), Mapping) else {}
    needed = plan.get("evidence_needed") if isinstance(plan, Mapping) else merged.get("evidence_needed")
    queries = plan.get("evidence_query_plan") if isinstance(plan, Mapping) else merged.get("evidence_query_plan")
    failures = merged.get("evidence_acquisition_failures") or assessment.warnings
    acquisition = merged.get("evidence_acquisition_results") if isinstance(merged.get("evidence_acquisition_results"), Mapping) else {}
    accepted_reasons = merged.get("accepted_evidence_reason_codes") or ()
    accepted_evidence = merged.get("evidence_acquisition_accepted_evidence") or ()
    contract = event_source_registry.source_contract_metadata(
        merged,
        evidence_rows=tuple(item for item in accepted_evidence if isinstance(item, Mapping)),
        assessment=assessment,
    )
    if isinstance(needed, str):
        needed = [needed]
    if isinstance(failures, str):
        failures = [failures]
    query_count = len(queries or ()) if isinstance(queries, Iterable) and not isinstance(queries, (str, bytes, Mapping)) else 0
    return [
        f"- source pack: {pack_name}",
        f"- source mission: {assessment.source_mission}",
        f"- provider coverage: {merged.get('provider_coverage_status') or assessment.provider_coverage_status}",
        f"- evidence absence meaningful: {str(bool(merged.get('evidence_absence_is_meaningful', assessment.evidence_absence_is_meaningful))).lower()}",
        f"- source quality prior/cap: {_first_present(merged.get('source_quality_prior'), assessment.source_quality_prior)}/{_first_present(merged.get('source_confidence_cap'), assessment.confidence_cap)}",
        f"- source can prove: {_source_contract_text(contract.get('source_can_prove'))}",
        f"- source cannot prove: {_source_contract_text(contract.get('source_cannot_prove'))}",
        f"- relevant playbooks: {_source_contract_text(contract.get('source_useful_playbooks'))}",
        f"- evidence needed: {'; '.join(str(item) for item in list(needed or pack.minimum_evidence)[:5])}",
        f"- planned query count: {query_count}",
        (
            f"- execution result: status={acquisition.get('status') or merged.get('evidence_acquisition_status') or 'not_executed'} "
            f"evidence={merged.get('acquisition_evidence_status') or acquisition.get('acquisition_evidence_status') or 'unknown'} "
            f"accepted={acquisition.get('accepted', merged.get('evidence_acquisition_accepted_count', 0))} "
            f"rejected={acquisition.get('rejected', merged.get('evidence_acquisition_rejected_count', 0))} "
            f"final={acquisition.get('final_upgrade_status') or merged.get('final_upgrade_status') or merged.get('acquisition_upgrade_status') or 'unchanged'}"
        ),
        (
            f"- final post-refresh verdict: {merged.get('final_opportunity_level') or merged.get('opportunity_level') or 'unknown'} "
            f"/ {_first_present(merged.get('final_opportunity_score'), merged.get('opportunity_score_final'), default='n/a')} "
            f"source={merged.get('final_verdict_source') or 'initial'} "
            f"reason={merged.get('final_verdict_reason') or 'none'}"
        ),
        f"- accepted reason codes: {'; '.join(str(item) for item in list(accepted_reasons or ())[:5]) if accepted_reasons else 'none'}",
        f"- accepted evidence samples: {'; '.join(_accepted_evidence_sample_text(item) for item in list(accepted_evidence or ())[:2]) if accepted_evidence else 'none'}",
        f"- article/source quality: {_source_enrichment_summary(accepted_evidence)}",
        f"- provider gaps/failures: {'; '.join(str(item) for item in list(failures or ())[:5]) if failures else 'none'}",
        f"- validation criteria: {'; '.join(pack.validation_requirements[:5])}",
    ]


def _official_exchange_audit_section(row: Mapping[str, Any], components: Mapping[str, Any]) -> list[str]:
    merged = {**dict(components or {}), **dict(row or {})}
    source_pack = str(merged.get("source_pack") or "")
    source_class = str(merged.get("source_class") or "")
    if (
        source_class != "official_exchange"
        and not source_pack.startswith("official_exchange")
        and not source_pack.startswith("official_perp")
    ):
        return []
    lines = [
        "",
        "## Official exchange evidence",
        f"- exchange: {merged.get('exchange') or 'unknown'}",
        f"- event type: {merged.get('event_type') or 'unknown'}",
        f"- source pack: {source_pack or 'unknown'}",
        f"- identity: {merged.get('validated_symbol') or merged.get('symbol') or 'unknown'}/{merged.get('validated_coin_id') or merged.get('coin_id') or 'unresolved'}",
        f"- pairs: {_list_value(merged.get('pairs') or merged.get('announcement_pairs'))}",
        f"- contracts: {_list_value(merged.get('contracts') or merged.get('announcement_contracts'))}",
        f"- reason codes: {_list_value(merged.get('reason_codes') or merged.get('accepted_evidence_reason_codes'))}",
        f"- timing: published={merged.get('published_at') or 'unknown'} effective={merged.get('effective_time') or 'unknown'}",
        f"- official source: {merged.get('source_url') or 'unknown'}",
    ]
    return lines


def _source_contract_text(values: object, *, limit: int = 5) -> str:
    if values in (None, "", [], {}, ()):
        return "none"
    if isinstance(values, str):
        items = [part.strip() for part in values.replace(";", ",").split(",") if part.strip()]
    elif isinstance(values, Mapping):
        items = [str(value) for value in values.values() if str(value)]
    elif isinstance(values, Iterable):
        items = [str(value) for value in values if str(value)]
    else:
        items = [str(values)]
    items = list(dict.fromkeys(items))
    if not items:
        return "none"
    shown = [_human_contract_value(item) for item in items[:limit]]
    suffix = f"; +{len(items) - limit} more" if len(items) > limit else ""
    return "; ".join(shown) + suffix


def _accepted_evidence_sample_text(item: object) -> str:
    if not isinstance(item, Mapping):
        return str(item)[:160]
    title = str(item.get("title") or item.get("source_url") or "evidence")[:120]
    details: list[str] = []
    tags = item.get("currency_tags")
    if tags:
        if isinstance(tags, str):
            tag_text = tags
        elif isinstance(tags, Iterable) and not isinstance(tags, (bytes, bytearray, Mapping)):
            tag_text = ",".join(str(tag) for tag in list(tags)[:4] if str(tag))
        else:
            tag_text = str(tags)
        if tag_text:
            details.append(f"tags={tag_text}")
    if item.get("cryptopanic_currency_tag_match"):
        details.append("tag_match=true")
    exchange = item.get("exchange")
    if exchange:
        details.append(f"exchange={exchange}")
    pairs = item.get("announcement_pairs")
    if pairs:
        pair_text = pairs if isinstance(pairs, str) else ",".join(str(pair) for pair in list(pairs)[:4] if str(pair))
        if pair_text:
            details.append(f"pairs={pair_text}")
    contracts = item.get("announcement_contracts")
    if contracts:
        contract_text = contracts if isinstance(contracts, str) else ",".join(str(contract) for contract in list(contracts)[:4] if str(contract))
        if contract_text:
            details.append(f"contracts={contract_text}")
    event_time = item.get("structured_event_time")
    if event_time:
        details.append(f"event_time={event_time}")
    category = item.get("calendar_event_category")
    if category:
        details.append(f"category={category}")
    unlock_pct = item.get("unlock_pct_circulating")
    if unlock_pct not in (None, ""):
        details.append(f"unlock_pct={unlock_pct}")
    materiality = item.get("unlock_materiality")
    if materiality:
        details.append(f"materiality={materiality}")
    enrichment = item.get("source_enrichment") if isinstance(item.get("source_enrichment"), Mapping) else {}
    quality_status = enrichment.get("article_quality_status")
    if quality_status:
        details.append(f"article={quality_status}")
    return title + (f" ({'; '.join(details)})" if details else "")


def _source_enrichment_summary(items: object) -> str:
    if not isinstance(items, Iterable) or isinstance(items, (str, bytes, Mapping)):
        return "not available"
    parts: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        enrichment = item.get("source_enrichment") if isinstance(item.get("source_enrichment"), Mapping) else {}
        status = enrichment.get("article_quality_status")
        cleaner = enrichment.get("cleaner_version")
        ratio = enrichment.get("boilerplate_ratio")
        triage = enrichment.get("source_triage_decision")
        warnings = enrichment.get("warnings") or ()
        if status:
            detail = f"{status}"
            if cleaner:
                detail += f" cleaner={cleaner}"
            if ratio not in (None, ""):
                detail += f" boilerplate={ratio}"
            if triage:
                detail += f" triage={triage}"
            if warnings:
                detail += " warnings=" + ",".join(str(warning) for warning in list(warnings)[:3])
            parts.append(detail)
    return "; ".join(parts[:3]) if parts else "not available"


def _human_contract_value(value: object) -> str:
    return str(value).replace("_", " ")


def _is_promoted_audit_row(components: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    level = str(
        components.get("final_opportunity_level")
        or row.get("final_opportunity_level")
        or components.get("opportunity_level")
        or row.get("opportunity_level")
        or ""
    ).casefold()
    route = str(
        components.get("final_route_after_quality_gate")
        or row.get("final_route_after_quality_gate")
        or row.get("route")
        or ""
    ).upper()
    return level in {"validated_digest", "watchlist", "high_priority"} or event_alpha_router.route_value_is_alertable(route)


def _audit_missing_evidence_text(
    components: Mapping[str, Any],
    row: Mapping[str, Any],
    verdict_copy: event_opportunity_verdict.VerdictAwareUpgradeDowngradeText,
) -> str:
    raw = components.get("missing_requirements") or row.get("missing_requirements") or ()
    values = []
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, Iterable) and not isinstance(raw, Mapping):
        values = [str(item) for item in raw if str(item or "")]
    if _is_promoted_audit_row(components, row):
        values = [
            value for value in values
            if not event_alpha_reason_text.reason_code_is_passed_gate_blocker(value)
        ]
    text = _list_value(values)
    return text if text and text != "none" else verdict_copy.missing_evidence_text


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


def _human_reason_list(values: Iterable[Any]) -> str:
    return event_alpha_reason_text.humanize_event_alpha_reasons(values, limit=8)


def _human_reason_value(value: Any) -> str:
    if value in (None, "", [], ()):
        return ""
    if isinstance(value, str):
        return event_alpha_reason_text.humanize_event_alpha_reason(value)
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return _human_reason_list(value)
    return event_alpha_reason_text.humanize_event_alpha_reason(value)


def _human_action_list(values: Iterable[Any]) -> str:
    return event_alpha_reason_text.humanize_event_alpha_actions(values, limit=8)


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
            str(item.primary_row.get("alert_id") or ""),
            str(item.primary_row.get("card_id") or ""),
            str(item.primary_row.get("snapshot_id") or ""),
        }
        identifiers.update(str(value) for value in item.supporting_hypothesis_ids)
        identifiers.update(str(row.get("key") or "") for row in item.supporting_rows)
        identifiers.update(str(row.get("alert_key") or "") for row in item.supporting_rows)
        identifiers.update(str(row.get("alert_id") or "") for row in item.supporting_rows)
        identifiers.update(str(row.get("card_id") or "") for row in item.supporting_rows)
        identifiers.update(str(row.get("snapshot_id") or "") for row in item.supporting_rows)
        identifiers.update(str(row.get("core_opportunity_id") or "") for row in item.supporting_rows)
        identifiers.update(_as_list_values(item.primary_row.get("supporting_row_ids")))
        identifiers.update(_as_list_values(item.primary_row.get("diagnostic_row_ids")))
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
        f"- watchlist keys: {_list_value(_collect_core_row_values(item.supporting_rows, 'key'))}",
        f"- alert ids: {_list_value(_collect_core_row_values(item.supporting_rows, 'alert_id'))}",
        f"- snapshot ids: {_list_value(_collect_core_row_values(item.supporting_rows, 'snapshot_id'))}",
        f"- card ids/paths: {_list_value(_collect_core_row_values(item.supporting_rows, 'card_id', 'research_card_path'))}",
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
        row.get("snapshot_id"),
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
        f"score={_first_present(source.get('incident_relevance_score'), components.get('incident_relevance_score'), default='n/a')}",
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
        f"- source updates: {_first_present(source.get('source_update_count'), len(source.get('source_raw_ids') or []) if source.get('source_raw_ids') is not None else None, default='unknown')} "
        f"(independent={source.get('independent_source_count') if type(source.get('independent_source_count')) is int else 'legacy-unassessed'}; "
        f"corroborations={source.get('independent_corroboration_count') if type(source.get('independent_corroboration_count')) is int else 'legacy-unassessed'})",
        f"- market reaction vs causal mechanism: observed={str(bool(reaction_observed)).lower()} "
        f"confirmed={str(bool(reaction_confirmed)).lower()} "
        f"causal={str(bool(causal)).lower()} "
        f"source={source.get('market_context_source') or components.get('market_context_source') or 'none'}",
        f"- linked assets and roles: {_asset_list(linked_assets) if linked_assets else _asset_role_summary(row, components)}",
    ]
