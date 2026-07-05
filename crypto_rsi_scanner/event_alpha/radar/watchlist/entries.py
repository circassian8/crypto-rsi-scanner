"""Event Alpha watchlist entry conversion helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import event_fade
import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
from .models import *  # noqa: F403 - split modules share historical model names


def _entry_from_alert(
    alert: event_alerts.EventAlertCandidate,
    prior: EventWatchlistEntry | None,
    observed: datetime,
    cfg: EventWatchlistConfig,
) -> EventWatchlistEntry:
    candidate = alert.discovery_candidate
    event = candidate.event
    requested_state = _state_from_alert(alert, observed, cfg)
    quality = event_alpha_quality_fields.ensure_quality_fields({}, components=alert.score_components)
    score_components = {
        **dict(alert.score_components),
        **quality,
        "source_raw_ids": list(event.raw_ids),
        "source_event_ids": [event.event_id],
    }
    final_state, quality_state_block = quality_cap_watchlist_state(requested_state, score_components)
    state = EventWatchlistState(final_state)
    previous_state = prior.state if prior else None
    rank = _state_rank(state)
    previous_rank = _state_rank(previous_state)
    state_changed = previous_state is not None and previous_state != state.value
    escalation = previous_state is None and rank >= _STATE_RANK[EventWatchlistState.RADAR.value]
    escalation = escalation or (previous_state is not None and rank > previous_rank)
    material_reasons = _material_change_reasons(alert, prior)
    state_quality_capped = bool(quality_state_block and state.value != requested_state.value)
    if prior and prior.state_quality_capped and not state_quality_capped and _state_rank(requested_state) >= _STATE_RANK[EventWatchlistState.WATCHLIST.value]:
        material_reasons = tuple(dict.fromkeys((*material_reasons, "quality_state_upgraded")))
    terminal = state in {EventWatchlistState.INVALIDATED, EventWatchlistState.EXPIRED, EventWatchlistState.QUALITY_BLOCKED}
    should_alert = (
        escalation
        or bool(material_reasons)
        or state == EventWatchlistState.TRIGGERED_FADE
    ) and not terminal and not state_quality_capped
    observed_iso = observed.isoformat()
    first_seen = prior.first_seen_at if prior else observed_iso
    history = list(prior.alert_history if prior else [])
    history.append({
        "observed_at": observed_iso,
        "state": state.value,
        "requested_state_before_quality_gate": requested_state.value,
        "final_state_after_quality_gate": state.value,
        "quality_state_block_reason": quality_state_block,
        "state_quality_capped": state_quality_capped,
        "tier": alert.tier.value,
        "score": alert.opportunity_score,
        "rule_playbook_type": alert.rule_playbook_type,
        "effective_playbook_type": alert.effective_playbook_type or alert.playbook_type,
        "material_change_reasons": list(material_reasons),
        "should_alert": should_alert,
    })
    history = history[-max(1, cfg.max_alert_history):]
    warnings = list(prior.warnings if prior else [])
    if alert.rejected_reason:
        warnings.append(alert.rejected_reason)
    if quality_state_block:
        warnings.append(f"quality_state_blocked:{quality_state_block}")
    warnings = list(dict.fromkeys(warnings))
    entry = EventWatchlistEntry(
        schema_version=WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=watchlist_key(alert),
        cluster_id=event_graph.cluster_id_for_event(event),
        event_id=str(event.event_id),
        coin_id=str(candidate.asset.coin_id),
        symbol=str(candidate.asset.symbol),
        relationship_type=str(candidate.classification.relationship_type),
        external_asset=event.external_asset,
        event_time=event.event_time.isoformat() if event.event_time else None,
        state=state.value,
        previous_state=previous_state,
        first_seen_at=first_seen,
        last_seen_at=observed_iso,
        **_alert_incident_entry_fields(alert.score_components),
        requested_state_before_quality_gate=requested_state.value,
        final_state_after_quality_gate=state.value,
        quality_state_block_reason=quality_state_block,
        state_quality_capped=state_quality_capped,
        **_alert_transition_entry_fields(prior, state, observed_iso),
        source_count=len(event.raw_ids),
        highest_score=max(prior.highest_score if prior else 0, alert.opportunity_score),
        latest_score=alert.opportunity_score,
        latest_tier=alert.tier.value,
        latest_event_name=event.event_name,
        latest_source=event.source,
        latest_playbook_type=alert.effective_playbook_type or alert.playbook_type,
        latest_rule_playbook_type=alert.rule_playbook_type,
        latest_effective_playbook_type=alert.effective_playbook_type or alert.playbook_type,
        latest_llm_adjusted_playbook_type=alert.llm_adjusted_playbook_type,
        latest_playbook_score=alert.playbook_score,
        latest_playbook_action=alert.playbook_action,
        latest_llm_asset_role=alert.llm_asset_role,
        latest_llm_confidence=alert.llm_confidence,
        latest_market_snapshot=_market_snapshot(alert),
        latest_score_components=score_components,
        impact_path_type=_optional_str(quality.get("impact_path_type")),
        impact_path_strength=_optional_str(quality.get("impact_path_strength")),
        candidate_role=_optional_str(quality.get("candidate_role")),
        evidence_quality_score=_optional_float(quality.get("evidence_quality_score")),
        source_class=_optional_str(quality.get("source_class")),
        evidence_specificity=_optional_str(quality.get("evidence_specificity")),
        market_confirmation_score=_optional_float(quality.get("market_confirmation_score")),
        market_confirmation_level=_optional_str(quality.get("market_confirmation_level")),
        market_context_freshness_status=_optional_str(quality.get("market_context_freshness_status")),
        market_context_age_hours=quality.get("market_context_age_hours"),
        market_context_stale=_optional_bool(quality.get("market_context_stale")),
        market_context_freshness_cap_applied=_optional_bool(quality.get("market_context_freshness_cap_applied")),
        opportunity_score_final=_optional_float(quality.get("opportunity_score_final")),
        opportunity_level=_optional_str(quality.get("opportunity_level")),
        opportunity_verdict_reasons=list(quality.get("opportunity_verdict_reasons") or []),
        why_local_only=_optional_str(quality.get("why_local_only")),
        why_not_watchlist=_optional_str(quality.get("why_not_watchlist")),
        manual_verification_items=list(quality.get("manual_verification_items") or []),
        upgrade_requirements=list(quality.get("upgrade_requirements") or []),
        downgrade_warnings=list(quality.get("downgrade_warnings") or []),
        alert_history=history,
        state_changed=state_changed,
        escalation=escalation,
        score_jump=_score_jump(alert, prior),
        source_count_increased="new_independent_source" in material_reasons,
        event_time_upgraded="event_time_upgrade" in material_reasons,
        derivatives_crowding_upgraded="derivatives_crowding_upgrade" in material_reasons,
        cluster_confidence_upgraded="cluster_confidence_upgrade" in material_reasons,
        material_change_reasons=material_reasons,
        should_alert=should_alert,
        suppressed_reason=None if should_alert else _suppressed_reason(state, previous_state, state_changed),
        warnings=tuple(warnings),
    )
    return entry


def _alert_incident_entry_fields(score_components: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "incident_id": _optional_str(score_components.get("incident_id")),
        "hypothesis_id": _optional_str(score_components.get("hypothesis_id")),
        "incident_canonical_name": _optional_str(
            score_components.get("incident_canonical_name")
            or score_components.get("canonical_incident_name")
        ),
        "incident_primary_subject": _optional_str(
            score_components.get("incident_primary_subject")
            or score_components.get("primary_subject")
        ),
        "incident_affected_ecosystem": _optional_str(
            score_components.get("incident_affected_ecosystem")
            or score_components.get("affected_ecosystem")
        ),
        "incident_cause_status": _optional_str(
            score_components.get("incident_cause_status")
            or score_components.get("cause_status")
        ),
        "incident_market_reaction_observed": _optional_bool(
            score_components.get("incident_market_reaction_observed")
            if "incident_market_reaction_observed" in score_components
            else score_components.get("market_reaction_observed")
        ),
        "incident_causal_mechanism_confirmed": _optional_bool(
            score_components.get("incident_causal_mechanism_confirmed")
            if "incident_causal_mechanism_confirmed" in score_components
            else score_components.get("causal_mechanism_confirmed")
        ),
    }


def _alert_transition_entry_fields(
    prior: EventWatchlistEntry | None,
    state: EventWatchlistState,
    observed_iso: str,
) -> dict[str, str | None]:
    return {
        "first_radar_at": _transition_time(prior, "first_radar_at", state, EventWatchlistState.RADAR, observed_iso),
        "first_watchlisted_at": _transition_time(
            prior,
            "first_watchlisted_at",
            state,
            EventWatchlistState.WATCHLIST,
            observed_iso,
        ),
        "first_high_priority_at": _transition_time(
            prior,
            "first_high_priority_at",
            state,
            EventWatchlistState.HIGH_PRIORITY,
            observed_iso,
        ),
        "first_event_passed_at": _transition_time(
            prior,
            "first_event_passed_at",
            state,
            EventWatchlistState.EVENT_PASSED,
            observed_iso,
        ),
        "first_armed_at": _transition_time(prior, "first_armed_at", state, EventWatchlistState.ARMED, observed_iso),
        "first_triggered_at": _transition_time(
            prior,
            "first_triggered_at",
            state,
            EventWatchlistState.TRIGGERED_FADE,
            observed_iso,
        ),
        "first_invalidated_at": _transition_time(
            prior,
            "first_invalidated_at",
            state,
            EventWatchlistState.INVALIDATED,
            observed_iso,
        ),
        "first_expired_at": _transition_time(
            prior,
            "first_expired_at",
            state,
            EventWatchlistState.EXPIRED,
            observed_iso,
        ),
    }


def _quality_entry_fields(quality: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "impact_path_type": _optional_str(quality.get("impact_path_type")),
        "impact_path_strength": _optional_str(quality.get("impact_path_strength")),
        "candidate_role": _optional_str(quality.get("candidate_role")),
        "evidence_quality_score": _optional_float(quality.get("evidence_quality_score")),
        "source_class": _optional_str(quality.get("source_class")),
        "evidence_specificity": _optional_str(quality.get("evidence_specificity")),
        "market_confirmation_score": _optional_float(quality.get("market_confirmation_score")),
        "market_confirmation_level": _optional_str(quality.get("market_confirmation_level")),
        "market_context_freshness_status": _optional_str(quality.get("market_context_freshness_status")),
        "market_context_age_hours": quality.get("market_context_age_hours"),
        "market_context_stale": _optional_bool(quality.get("market_context_stale")),
        "market_context_freshness_cap_applied": _optional_bool(quality.get("market_context_freshness_cap_applied")),
        "opportunity_score_final": _optional_float(quality.get("opportunity_score_final")),
        "opportunity_level": _optional_str(quality.get("opportunity_level")),
        "opportunity_verdict_reasons": list(quality.get("opportunity_verdict_reasons") or []),
        "why_local_only": _optional_str(quality.get("why_local_only")),
        "why_not_watchlist": _optional_str(quality.get("why_not_watchlist")),
        "manual_verification_items": list(quality.get("manual_verification_items") or []),
        "upgrade_requirements": list(quality.get("upgrade_requirements") or []),
        "downgrade_warnings": list(quality.get("downgrade_warnings") or []),
    }


def _hypothesis_incident_context(hypothesis: object) -> dict[str, Any]:
    incident_market_observed = _optional_bool(getattr(hypothesis, "incident_market_reaction_observed", None))
    if incident_market_observed is None:
        incident_market_observed = _optional_bool(getattr(hypothesis, "market_reaction_confirmed", None))
    incident_causal = _optional_bool(getattr(hypothesis, "incident_causal_mechanism_confirmed", None))
    if incident_causal is None:
        incident_causal = _optional_bool(getattr(hypothesis, "causal_mechanism_confirmed", None))
    incident_id = _optional_str(getattr(hypothesis, "incident_id", None))
    incident_link_status = _optional_str(getattr(hypothesis, "incident_link_status", None)) or (
        "linked" if incident_id else "no_incident"
    )
    return {
        "incident_id": incident_id,
        "hypothesis_id": _optional_str(getattr(hypothesis, "hypothesis_id", None)),
        "incident_canonical_name": _optional_str(
            getattr(hypothesis, "incident_canonical_name", None)
            or getattr(hypothesis, "canonical_incident_name", None)
        ),
        "incident_event_archetype": _optional_str(
            getattr(hypothesis, "incident_event_archetype", None)
            or getattr(hypothesis, "event_archetype", None)
        ),
        "incident_primary_subject": _optional_str(
            getattr(hypothesis, "incident_primary_subject", None)
            or getattr(hypothesis, "primary_subject", None)
        ),
        "incident_affected_ecosystem": _optional_str(
            getattr(hypothesis, "incident_affected_ecosystem", None)
            or getattr(hypothesis, "affected_ecosystem", None)
        ),
        "incident_cause_status": _optional_str(
            getattr(hypothesis, "incident_cause_status", None)
            or getattr(hypothesis, "cause_status", None)
        ),
        "incident_market_observed": incident_market_observed,
        "incident_causal": incident_causal,
        "incident_link_status": incident_link_status,
        "incident_link_reason": _optional_str(getattr(hypothesis, "incident_link_reason", None)) or (
            None if incident_link_status == "linked" else "no_canonical_incident_for_event_evidence"
        ),
        "incident_relevance_status": _optional_str(getattr(hypothesis, "incident_relevance_status", None)),
        "incident_relevance_score": _optional_float(getattr(hypothesis, "incident_relevance_score", None)),
        "incident_relevance_reasons": list(getattr(hypothesis, "incident_relevance_reasons", ()) or ())[:8],
        "incident_relevance_warnings": list(getattr(hypothesis, "incident_relevance_warnings", ()) or ())[:8],
        "canonical_persistence_reason": _optional_str(getattr(hypothesis, "canonical_persistence_reason", None)),
    }


def _hypothesis_incident_entry_fields(incident: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "incident_id": incident["incident_id"],
        "hypothesis_id": incident["hypothesis_id"],
        "incident_canonical_name": incident["incident_canonical_name"],
        "incident_primary_subject": incident["incident_primary_subject"],
        "incident_affected_ecosystem": incident["incident_affected_ecosystem"],
        "incident_cause_status": incident["incident_cause_status"],
        "incident_market_reaction_observed": incident["incident_market_observed"],
        "incident_causal_mechanism_confirmed": incident["incident_causal"],
        "incident_link_status": incident["incident_link_status"],
        "incident_link_reason": incident["incident_link_reason"],
    }


def _hypothesis_quality_components(hypothesis: object) -> dict[str, Any]:
    return {
        "impact_path_type": _optional_str(getattr(hypothesis, "impact_path_type", None)),
        "impact_path_strength": _optional_str(getattr(hypothesis, "impact_path_strength", None)),
        "candidate_role": _optional_str(getattr(hypothesis, "candidate_role", None)),
        "evidence_quality_score": _optional_float(getattr(hypothesis, "evidence_quality_score", None)),
        "source_class": _optional_str(getattr(hypothesis, "source_class", None)),
        "evidence_specificity": _optional_str(getattr(hypothesis, "evidence_specificity", None)),
        "market_confirmation_score": _optional_float(getattr(hypothesis, "market_confirmation_score", None)),
        "market_confirmation_level": _optional_str(getattr(hypothesis, "market_confirmation_level", None)),
        "market_context_observed_at": _optional_str(getattr(hypothesis, "market_context_observed_at", None)),
        "market_context_age_hours": _optional_float(getattr(hypothesis, "market_context_age_hours", None)),
        "market_context_stale": getattr(hypothesis, "market_context_stale", None),
        "market_context_freshness_status": _optional_str(getattr(hypothesis, "market_context_freshness_status", None)),
        "market_context_freshness_cap_applied": getattr(hypothesis, "market_context_freshness_cap_applied", None),
        "opportunity_score_final": _optional_float(getattr(hypothesis, "opportunity_score_final", None)),
        "opportunity_level": _optional_str(getattr(hypothesis, "opportunity_level", None)),
        "opportunity_verdict_reasons": list(getattr(hypothesis, "opportunity_verdict_reasons", ()) or ())[:8],
        "why_local_only": _optional_str(getattr(hypothesis, "why_local_only", None)),
        "why_not_watchlist": _optional_str(getattr(hypothesis, "why_not_watchlist", None)),
        "manual_verification_items": list(getattr(hypothesis, "manual_verification_items", ()) or ())[:8],
    }


def _hypothesis_latest_score_components(
    hypothesis: object,
    *,
    incident: Mapping[str, Any],
    score: int,
    playbook: str,
    category: str,
    validation_stage: str,
    scope: str,
    symbols: tuple[str, ...],
    coin_ids: tuple[str, ...],
    symbol: str,
    coin_id: str,
    validated: bool,
    validated_asset: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "run_id": _optional_str(getattr(hypothesis, "run_id", None)),
        "profile": _optional_str(getattr(hypothesis, "profile", None)),
        "run_mode": _optional_str(getattr(hypothesis, "run_mode", None)),
        "artifact_namespace": _optional_str(getattr(hypothesis, "artifact_namespace", None)),
        "hypothesis_id": str(incident["hypothesis_id"] or ""),
        "aggregated_candidate_id": _optional_str(getattr(hypothesis, "aggregated_candidate_id", None)),
        "supporting_hypothesis_count": getattr(hypothesis, "supporting_hypothesis_count", None),
        "supporting_hypothesis_ids": list(getattr(hypothesis, "supporting_hypothesis_ids", ()) or ())[:12],
        "supporting_categories": list(getattr(hypothesis, "supporting_categories", ()) or ())[:12],
        "supporting_impact_paths": list(getattr(hypothesis, "supporting_impact_paths", ()) or ())[:12],
        "supporting_evidence_quotes": list(getattr(hypothesis, "supporting_evidence_quotes", ()) or ())[:8],
        "source_raw_ids": list(getattr(hypothesis, "source_raw_ids", ()) or ())[:24],
        "source_event_ids": list(getattr(hypothesis, "source_event_ids", ()) or ())[:24],
        "impact_category": category,
        "validation_stage": validation_stage or "unknown",
        "impact_path_reason": _optional_str(getattr(hypothesis, "impact_path_reason", None)),
        "impact_path_type": _optional_str(getattr(hypothesis, "impact_path_type", None)),
        "impact_path_strength": _optional_str(getattr(hypothesis, "impact_path_strength", None)),
        "candidate_role": _optional_str(getattr(hypothesis, "candidate_role", None)),
        "evidence_specificity_score": _optional_float(getattr(hypothesis, "evidence_specificity_score", None)),
        "required_evidence_met": getattr(hypothesis, "required_evidence_met", None),
        "market_confirmation_required": getattr(hypothesis, "market_confirmation_required", None),
        "digest_eligible_by_impact_path": getattr(hypothesis, "digest_eligible_by_impact_path", None),
        "why_digest_ineligible": _optional_str(getattr(hypothesis, "why_digest_ineligible", None)),
        "opportunity_score_v2": _optional_float(getattr(hypothesis, "opportunity_score_v2", None)),
        "opportunity_score_components": dict(getattr(hypothesis, "opportunity_score_components", {}) or {}),
        "evidence_quality_score": _optional_float(getattr(hypothesis, "evidence_quality_score", None)),
        "source_class": _optional_str(getattr(hypothesis, "source_class", None)),
        "evidence_specificity": _optional_str(getattr(hypothesis, "evidence_specificity", None)),
        "evidence_quality_reasons": list(getattr(hypothesis, "evidence_quality_reasons", ()) or ())[:8],
        "market_confirmation_score": _optional_float(getattr(hypothesis, "market_confirmation_score", None)),
        "market_confirmation_level": _optional_str(getattr(hypothesis, "market_confirmation_level", None)),
        "market_confirmation_reasons": list(getattr(hypothesis, "market_confirmation_reasons", ()) or ())[:8],
        "market_confirmation_warnings": list(getattr(hypothesis, "market_confirmation_warnings", ()) or ())[:8],
        "market_confirmation_missing_fields": list(getattr(hypothesis, "market_confirmation_missing_fields", ()) or ())[:8],
        "market_confirmation_summary": _optional_str(getattr(hypothesis, "market_confirmation_summary", None)),
        "market_context_source": _optional_str(getattr(hypothesis, "market_context_source", None)),
        "market_context_timestamp": _optional_str(getattr(hypothesis, "market_context_timestamp", None)),
        "market_context_observed_at": _optional_str(getattr(hypothesis, "market_context_observed_at", None)),
        "market_context_age_seconds": _optional_float(getattr(hypothesis, "market_context_age_seconds", None)),
        "market_context_age_hours": _optional_float(getattr(hypothesis, "market_context_age_hours", None)),
        "market_context_stale": getattr(hypothesis, "market_context_stale", None),
        "market_context_freshness_status": _optional_str(getattr(hypothesis, "market_context_freshness_status", None)),
        "market_context_freshness_cap_applied": getattr(hypothesis, "market_context_freshness_cap_applied", None),
        "market_context_data_quality": _optional_str(getattr(hypothesis, "market_context_data_quality", None)),
        "market_context_snapshot": dict(getattr(hypothesis, "market_context_snapshot", {}) or {}),
        "market_reaction_confirmed": getattr(hypothesis, "market_reaction_confirmed", None),
        "causal_mechanism_confirmed": getattr(hypothesis, "causal_mechanism_confirmed", None),
        "incident_confidence": _optional_float(getattr(hypothesis, "incident_confidence", None)),
        "incident_id": incident["incident_id"],
        "incident_canonical_name": incident["incident_canonical_name"],
        "canonical_incident_name": incident["incident_canonical_name"],
        "incident_event_archetype": incident["incident_event_archetype"],
        "event_archetype": incident["incident_event_archetype"],
        "incident_primary_subject": incident["incident_primary_subject"],
        "primary_subject": incident["incident_primary_subject"],
        "affected_entity": _optional_str(getattr(hypothesis, "affected_entity", None)),
        "incident_affected_ecosystem": incident["incident_affected_ecosystem"],
        "affected_ecosystem": incident["incident_affected_ecosystem"],
        "role_confidence": _optional_float(getattr(hypothesis, "role_confidence", None)),
        "role_evidence": list(getattr(hypothesis, "role_evidence", ()) or ())[:8],
        "incident_cause_status": incident["incident_cause_status"],
        "cause_status": incident["incident_cause_status"],
        "incident_link_status": incident["incident_link_status"],
        "incident_link_reason": incident["incident_link_reason"],
        "incident_relevance_status": incident["incident_relevance_status"],
        "incident_relevance_score": incident["incident_relevance_score"],
        "incident_relevance_reasons": incident["incident_relevance_reasons"],
        "incident_relevance_warnings": incident["incident_relevance_warnings"],
        "canonical_persistence_reason": incident["canonical_persistence_reason"],
        "claim_polarities": list(getattr(hypothesis, "claim_polarities", ()) or ())[:8],
        "claim_history": list(getattr(hypothesis, "claim_history", ()) or ())[:8],
        "independent_source_domains": list(getattr(hypothesis, "independent_source_domains", ()) or ())[:8],
        "conflicting_claims": list(getattr(hypothesis, "conflicting_claims", ()) or ())[:8],
        "incident_market_reaction_observed": incident["incident_market_observed"],
        "market_reaction_observed": incident["incident_market_observed"],
        "incident_causal_mechanism_confirmed": incident["incident_causal"],
        "opportunity_score_final": _optional_float(getattr(hypothesis, "opportunity_score_final", None)),
        "opportunity_level": _optional_str(getattr(hypothesis, "opportunity_level", None)),
        "opportunity_verdict_reasons": list(getattr(hypothesis, "opportunity_verdict_reasons", ()) or ())[:8],
        "missing_requirements": list(getattr(hypothesis, "missing_requirements", ()) or ())[:8],
        "manual_verification_items": list(getattr(hypothesis, "manual_verification_items", ()) or ())[:8],
        "upgrade_requirements": list(getattr(hypothesis, "upgrade_requirements", ()) or ())[:8],
        "downgrade_warnings": list(getattr(hypothesis, "downgrade_warnings", ()) or ())[:8],
        "why_local_only": _optional_str(getattr(hypothesis, "why_local_only", None)),
        "why_not_watchlist": _optional_str(getattr(hypothesis, "why_not_watchlist", None)),
        "frame_required": bool(getattr(hypothesis, "frame_required", False)),
        "frame_status": _optional_str(getattr(hypothesis, "frame_status", None)),
        "frame_required_reason": _optional_str(getattr(hypothesis, "frame_required_reason", None)),
        "frame_gate_reason": _optional_str(getattr(hypothesis, "frame_gate_reason", None)),
        "route_block_reason": _optional_str(getattr(hypothesis, "route_block_reason", None)),
        "primary_impact_path": _optional_str(getattr(hypothesis, "primary_impact_path", None)),
        "asset_role_source": _optional_str(getattr(hypothesis, "asset_role_source", None)),
        "asset_kind": _optional_str(getattr(hypothesis, "asset_kind", None)),
        "role_source": _optional_str(getattr(hypothesis, "role_source", None)),
        "identity_confidence": _optional_float(getattr(hypothesis, "identity_confidence", None)),
        "identity_evidence": list(getattr(hypothesis, "identity_evidence", ()) or ())[:8],
        "collision_risk": _optional_str(getattr(hypothesis, "collision_risk", None)),
        "role_validation_failures": list(getattr(hypothesis, "role_validation_failures", ()) or ())[:8],
        "role_validation_warnings": list(getattr(hypothesis, "role_validation_warnings", ()) or ())[:8],
        "role_capabilities": dict(getattr(hypothesis, "role_capabilities", {}) or {}),
        "hypothesis_score": score,
        "score": score,
        "playbook_type": playbook,
        "effective_playbook_type": playbook,
        "direction_hint": str(getattr(hypothesis, "direction_hint", "") or "unknown"),
        "external_asset": _optional_str(getattr(hypothesis, "external_asset", None)),
        "candidate_sectors": list(getattr(hypothesis, "candidate_sectors", ()) or ()),
        "hypothesis_confidence": score,
        "hypothesis_scope": scope,
        "candidate_symbol_count": len(symbols),
        "candidate_symbols": list(symbols[:12]),
        "candidate_coin_ids": list(coin_ids[:12]),
        "validated_symbol": symbol if symbol != "SECTOR" else None,
        "validated_coin_id": coin_id if symbol != "SECTOR" else None,
        "validated_asset": validated_asset,
        "route_eligibility": "validated_hypothesis_digest_candidate" if validated and symbol != "SECTOR" else "local_only",
        "why_not_promoted": list(getattr(hypothesis, "why_not_promoted", ()) or ())[:10],
        "validation_evidence": 100 if validated else 0,
        "validation_reasons": list(getattr(hypothesis, "validation_reasons", ()) or ())[:8],
        "evidence_quotes": list(getattr(hypothesis, "evidence_quotes", ()) or ())[:8],
        "external_entities": list(getattr(hypothesis, "external_entities", ()) or ())[:8],
        "crypto_candidate_assets": list(getattr(hypothesis, "crypto_candidate_assets", ()) or ())[:12],
        "rejected_candidate_assets": list(getattr(hypothesis, "rejected_candidate_assets", ()) or ())[:8],
        **dict(getattr(hypothesis, "score_components", {}) or {}),
    }


def _hypothesis_entry_warnings(
    hypothesis: object,
    prior: EventWatchlistEntry | None,
    *,
    asset_warnings: tuple[str, ...],
    incident_id: str | None,
    incident_link_status: str,
    quality_state_block: str | None,
) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        str(value)
        for value in (
            *(prior.warnings if prior else ()),
            *tuple(getattr(hypothesis, "warnings", ()) or ()),
            *tuple(getattr(hypothesis, "rejection_reasons", ()) or ()),
            *asset_warnings,
            *((
                "missing_incident_id_for_hypothesis_watchlist_key",
            ) if not incident_id and incident_link_status != "no_incident" else ()),
            *(("quality_state_blocked:" + quality_state_block,) if quality_state_block else ()),
        )
        if str(value)
    ))


def _hypothesis_suppressed_reason(
    requested_state: EventWatchlistState,
    state: EventWatchlistState,
    *,
    validated: bool,
    state_quality_capped: bool,
    quality_state_block: str | None,
) -> str | None:
    if state_quality_capped:
        return f"quality state gate capped {requested_state.value} to {state.value}: {quality_state_block}"
    if validated:
        return f"validated hypothesis retained at {state.value}"
    return "impact hypothesis awaiting validation"


def _hypothesis_transition_entry_fields(
    prior: EventWatchlistEntry | None,
    state: EventWatchlistState,
    observed_iso: str,
) -> dict[str, str | None]:
    return {
        "first_radar_at": _transition_time(prior, "first_radar_at", state, EventWatchlistState.RADAR, observed_iso),
        "first_watchlisted_at": _transition_time(prior, "first_watchlisted_at", state, EventWatchlistState.WATCHLIST, observed_iso),
        "first_high_priority_at": _transition_time(prior, "first_high_priority_at", state, EventWatchlistState.HIGH_PRIORITY, observed_iso),
        "first_event_passed_at": prior.first_event_passed_at if prior else None,
        "first_armed_at": prior.first_armed_at if prior else None,
        "first_triggered_at": prior.first_triggered_at if prior else None,
        "first_invalidated_at": prior.first_invalidated_at if prior else None,
        "first_expired_at": prior.first_expired_at if prior else None,
    }


def _entry_from_hypothesis(
    hypothesis: object,
    prior: EventWatchlistEntry | None,
    observed: datetime,
    cfg: EventWatchlistConfig,
) -> EventWatchlistEntry:
    status = str(getattr(hypothesis, "status", "") or "")
    validation_stage = str(getattr(hypothesis, "validation_stage", "") or "")
    promotable_stage = validation_stage in {
        "catalyst_link_validated",
        "impact_path_validated",
        "market_confirmed",
        "promoted_to_radar",
    }
    validated = status == "validated" and promotable_stage
    observed_iso = observed.isoformat()
    first_seen = prior.first_seen_at if prior else observed_iso
    hypothesis_score = _optional_float(getattr(hypothesis, "hypothesis_score", None))
    confidence = _optional_float(getattr(hypothesis, "confidence", None)) or 0.0
    score = max(0, min(100, int(round(hypothesis_score if hypothesis_score is not None else confidence * 100))))
    symbols = tuple(str(value) for value in getattr(hypothesis, "candidate_symbols", ()) or ())
    coin_ids = tuple(str(value) for value in getattr(hypothesis, "candidate_coin_ids", ()) or ())
    category = str(getattr(hypothesis, "impact_category", "") or "impact_hypothesis")
    scope = str(getattr(hypothesis, "hypothesis_scope", "") or "sector")
    symbol, coin_id, asset_warnings, validated_asset = _hypothesis_watchlist_asset(
        hypothesis,
        candidate_symbols=symbols,
        candidate_coin_ids=coin_ids,
        category=category,
        token_level=validated and scope == "token",
    )
    playbook = str(getattr(hypothesis, "playbook_hint", "") or "impact_hypothesis")
    incident = _hypothesis_incident_context(hypothesis)
    incident_id = incident["incident_id"]
    hypothesis_id = incident["hypothesis_id"]
    incident_link_status = incident["incident_link_status"]
    requested_state = _state_from_hypothesis(hypothesis, validated=validated, token_level=symbol != "SECTOR")
    hypothesis_quality_components = _hypothesis_quality_components(hypothesis)
    hypothesis_quality = event_alpha_quality_fields.ensure_quality_fields(
        {},
        components=hypothesis_quality_components,
    )
    hypothesis_quality_components = {**hypothesis_quality_components, **hypothesis_quality}
    final_state, quality_state_block = quality_cap_watchlist_state(
        requested_state,
        hypothesis_quality_components,
    )
    state = EventWatchlistState(final_state)
    previous_state = prior.state if prior else None
    rank = _state_rank(state)
    previous_rank = _state_rank(previous_state)
    state_changed = previous_state is not None and previous_state != state.value
    state_quality_capped = bool(quality_state_block and state.value != requested_state.value)
    escalation = bool(validated and (previous_state is None or rank > previous_rank) and not state_quality_capped)
    event_name = f"{getattr(hypothesis, 'external_asset', None) or category} {scope} impact hypothesis"
    reasons = _hypothesis_material_change_reasons(hypothesis, prior, state, validated=validated)
    if prior and prior.state_quality_capped and not state_quality_capped and _state_rank(requested_state) >= _STATE_RANK[EventWatchlistState.WATCHLIST.value]:
        reasons = tuple(dict.fromkeys((*reasons, "quality_state_upgraded")))
    history = list(prior.alert_history if prior else [])
    history.append({
        "observed_at": observed_iso,
        "state": state.value,
        "requested_state_before_quality_gate": requested_state.value,
        "final_state_after_quality_gate": state.value,
        "quality_state_block_reason": quality_state_block,
        "state_quality_capped": state_quality_capped,
        "tier": _tier_for_hypothesis_state(state, validated=validated),
        "score": score,
        "effective_playbook_type": playbook,
        "material_change_reasons": list(reasons),
        "should_alert": escalation,
    })
    history = history[-max(1, cfg.max_alert_history):]
    warnings = _hypothesis_entry_warnings(
        hypothesis,
        prior,
        asset_warnings=asset_warnings,
        incident_id=incident_id,
        incident_link_status=incident_link_status,
        quality_state_block=quality_state_block,
    )
    return EventWatchlistEntry(
        schema_version=WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=hypothesis_watchlist_key(hypothesis),
        cluster_id=_optional_str(getattr(hypothesis, "event_cluster_id", None)),
        event_id=str(hypothesis_id or hypothesis_watchlist_key(hypothesis)),
        coin_id=coin_id,
        symbol=symbol,
        relationship_type="impact_hypothesis",
        external_asset=_optional_str(getattr(hypothesis, "external_asset", None)),
        event_time=None,
        state=state.value,
        previous_state=previous_state,
        first_seen_at=first_seen,
        last_seen_at=observed_iso,
        **_hypothesis_incident_entry_fields(incident),
        requested_state_before_quality_gate=requested_state.value,
        final_state_after_quality_gate=state.value,
        quality_state_block_reason=quality_state_block,
        state_quality_capped=state_quality_capped,
        **_hypothesis_transition_entry_fields(prior, state, observed_iso),
        source_count=len(tuple(getattr(hypothesis, "source_raw_ids", ()) or ())),
        highest_score=max(prior.highest_score if prior else 0, score),
        latest_score=score,
        latest_tier=_tier_for_hypothesis_state(state, validated=validated),
        latest_event_name=event_name,
        latest_source="impact_hypothesis",
        latest_playbook_type=playbook,
        latest_rule_playbook_type=playbook,
        latest_effective_playbook_type=playbook,
        latest_playbook_score=score,
        latest_playbook_action=_action_for_hypothesis_state(state, validated=validated),
        latest_market_snapshot=dict(getattr(hypothesis, "market_context_snapshot", {}) or {}),
        latest_score_components=_hypothesis_latest_score_components(
            hypothesis,
            incident=incident,
            score=score,
            playbook=playbook,
            category=category,
            validation_stage=validation_stage,
            scope=scope,
            symbols=symbols,
            coin_ids=coin_ids,
            symbol=symbol,
            coin_id=coin_id,
            validated=validated,
            validated_asset=validated_asset,
        ),
        **_quality_entry_fields(hypothesis_quality),
        alert_history=history,
        state_changed=state_changed,
        escalation=escalation,
        score_jump=score - int(prior.latest_score if prior else score),
        material_change_reasons=reasons,
        should_alert=escalation and not state_quality_capped,
        suppressed_reason=None if escalation and not state_quality_capped else _hypothesis_suppressed_reason(
            requested_state,
            state,
            validated=validated,
            state_quality_capped=state_quality_capped,
            quality_state_block=quality_state_block,
        ),
        warnings=warnings,
    )


def _row_entry_quality_state(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
) -> tuple[str, str, str, dict[str, Any], dict[str, Any], str, bool, str | None]:
    requested_state = _state_value(row.get("requested_state_before_quality_gate") or row.get("state"))
    first_seen = str(row.get("first_seen_at") or row.get("last_seen_at") or "")
    last_seen = str(row.get("last_seen_at") or first_seen)
    has_quality = event_alpha_quality_fields.has_any_quality_field(row, components_key="latest_score_components")
    quality = event_alpha_quality_fields.ensure_quality_fields(row, components=components)
    raw_quality = {**dict(components), **quality} if has_quality else dict(components)
    computed_final, computed_block = (
        quality_cap_watchlist_state(requested_state, raw_quality)
        if has_quality
        else (requested_state, None)
    )
    persisted_final = _state_value(row.get("final_state_after_quality_gate"))
    if persisted_final in {
        EventWatchlistState.TRIGGERED_FADE.value,
        EventWatchlistState.INVALIDATED.value,
        EventWatchlistState.EXPIRED.value,
    }:
        final_state = persisted_final
    elif has_quality:
        final_state = computed_final
    elif row.get("final_state_after_quality_gate"):
        final_state = persisted_final
    else:
        final_state = requested_state
    state_quality_capped = bool(row.get("state_quality_capped")) if not has_quality else requested_state != final_state
    quality_state_block = _normalize_quality_state_block_reason(
        _optional_str(row.get("quality_state_block_reason")) or computed_block,
        quality,
    )
    return requested_state, first_seen, last_seen, raw_quality, quality, final_state, state_quality_capped, quality_state_block


def _entry_from_row(row: Mapping[str, Any]) -> EventWatchlistEntry | None:
    try:
        key = str(row.get("key") or "")
        event_id = str(row.get("event_id") or "")
        coin_id = str(row.get("coin_id") or "")
        symbol = str(row.get("symbol") or "")
        relationship_type = str(row.get("relationship_type") or "")
        if not key or not event_id or not coin_id or not relationship_type:
            return None
        components = dict(row.get("latest_score_components") or {})
        (
            requested_state,
            first_seen,
            last_seen,
            raw_quality,
            quality,
            final_state,
            state_quality_capped,
            quality_state_block,
        ) = _row_entry_quality_state(row, components)
        return EventWatchlistEntry(
            schema_version=str(row.get("schema_version") or WATCHLIST_SCHEMA_VERSION),
            row_type="event_watchlist_state",
            key=key,
            cluster_id=_optional_str(row.get("cluster_id")),
            event_id=event_id,
            coin_id=coin_id,
            symbol=symbol,
            relationship_type=relationship_type,
            external_asset=_optional_str(row.get("external_asset")),
            event_time=_optional_str(row.get("event_time")),
            state=final_state,
            previous_state=_optional_str(row.get("previous_state")),
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            incident_id=_optional_str(row.get("incident_id") or components.get("incident_id")),
            hypothesis_id=_optional_str(row.get("hypothesis_id") or components.get("hypothesis_id")),
            incident_canonical_name=_optional_str(
                row.get("incident_canonical_name")
                or row.get("canonical_incident_name")
                or components.get("incident_canonical_name")
                or components.get("canonical_incident_name")
            ),
            incident_primary_subject=_optional_str(
                row.get("incident_primary_subject")
                or row.get("primary_subject")
                or components.get("incident_primary_subject")
                or components.get("primary_subject")
            ),
            incident_affected_ecosystem=_optional_str(
                row.get("incident_affected_ecosystem")
                or row.get("affected_ecosystem")
                or components.get("incident_affected_ecosystem")
                or components.get("affected_ecosystem")
            ),
            incident_cause_status=_optional_str(
                row.get("incident_cause_status")
                or row.get("cause_status")
                or components.get("incident_cause_status")
                or components.get("cause_status")
            ),
            incident_market_reaction_observed=_optional_bool(
                row.get("incident_market_reaction_observed")
                if "incident_market_reaction_observed" in row
                else components.get("incident_market_reaction_observed")
                if "incident_market_reaction_observed" in components
                else row.get("market_reaction_observed")
                if "market_reaction_observed" in row
                else components.get("market_reaction_observed")
            ),
            incident_causal_mechanism_confirmed=_optional_bool(
                row.get("incident_causal_mechanism_confirmed")
                if "incident_causal_mechanism_confirmed" in row
                else components.get("incident_causal_mechanism_confirmed")
                if "incident_causal_mechanism_confirmed" in components
                else row.get("causal_mechanism_confirmed")
                if "causal_mechanism_confirmed" in row
                else components.get("causal_mechanism_confirmed")
            ),
            incident_link_status=_optional_str(row.get("incident_link_status") or components.get("incident_link_status")),
            incident_link_reason=_optional_str(row.get("incident_link_reason") or components.get("incident_link_reason")),
            requested_state_before_quality_gate=requested_state,
            final_state_after_quality_gate=final_state,
            quality_state_block_reason=quality_state_block,
            state_quality_capped=state_quality_capped,
            first_radar_at=_optional_str(row.get("first_radar_at")),
            first_watchlisted_at=_optional_str(row.get("first_watchlisted_at")),
            first_high_priority_at=_optional_str(row.get("first_high_priority_at")),
            first_event_passed_at=_optional_str(row.get("first_event_passed_at")),
            first_armed_at=_optional_str(row.get("first_armed_at")),
            first_triggered_at=_optional_str(row.get("first_triggered_at")),
            first_invalidated_at=_optional_str(row.get("first_invalidated_at")),
            first_expired_at=_optional_str(row.get("first_expired_at")),
            source_count=int(row.get("source_count") or 0),
            highest_score=int(row.get("highest_score") or row.get("latest_score") or 0),
            latest_score=int(row.get("latest_score") or 0),
            latest_tier=str(row.get("latest_tier") or ""),
            latest_event_name=str(row.get("latest_event_name") or ""),
            latest_source=str(row.get("latest_source") or ""),
            latest_playbook_type=_optional_str(row.get("latest_playbook_type")),
            latest_rule_playbook_type=_optional_str(row.get("latest_rule_playbook_type")),
            latest_effective_playbook_type=_optional_str(row.get("latest_effective_playbook_type"))
            or _optional_str(row.get("latest_playbook_type")),
            latest_llm_adjusted_playbook_type=_optional_str(row.get("latest_llm_adjusted_playbook_type")),
            latest_playbook_score=_optional_int(row.get("latest_playbook_score")),
            latest_playbook_action=_optional_str(row.get("latest_playbook_action")),
            latest_llm_asset_role=_optional_str(row.get("latest_llm_asset_role")),
            latest_llm_confidence=_optional_float(row.get("latest_llm_confidence")),
            latest_market_snapshot=dict(row.get("latest_market_snapshot") or {}),
            latest_score_components=raw_quality,
            impact_path_type=_optional_str(quality.get("impact_path_type")),
            impact_path_strength=_optional_str(quality.get("impact_path_strength")),
            candidate_role=_optional_str(quality.get("candidate_role")),
            evidence_quality_score=_optional_float(quality.get("evidence_quality_score")),
            source_class=_optional_str(quality.get("source_class")),
            evidence_specificity=_optional_str(quality.get("evidence_specificity")),
            market_confirmation_score=_optional_float(quality.get("market_confirmation_score")),
            market_confirmation_level=_optional_str(quality.get("market_confirmation_level")),
            market_context_freshness_status=_optional_str(quality.get("market_context_freshness_status")),
            market_context_age_hours=quality.get("market_context_age_hours"),
            market_context_stale=_optional_bool(quality.get("market_context_stale")),
            market_context_freshness_cap_applied=_optional_bool(quality.get("market_context_freshness_cap_applied")),
            opportunity_score_final=_optional_float(quality.get("opportunity_score_final")),
            opportunity_level=_optional_str(quality.get("opportunity_level")),
            opportunity_verdict_reasons=list(quality.get("opportunity_verdict_reasons") or []),
            why_local_only=_optional_str(quality.get("why_local_only")),
            why_not_watchlist=_optional_str(quality.get("why_not_watchlist")),
            manual_verification_items=list(quality.get("manual_verification_items") or []),
            upgrade_requirements=list(quality.get("upgrade_requirements") or []),
            downgrade_warnings=list(quality.get("downgrade_warnings") or []),
            alert_history=list(row.get("alert_history") or []),
            state_changed=bool(row.get("state_changed")),
            escalation=bool(row.get("escalation")),
            score_jump=int(row.get("score_jump") or 0),
            source_count_increased=bool(row.get("source_count_increased")),
            event_time_upgraded=bool(row.get("event_time_upgraded")),
            derivatives_crowding_upgraded=bool(row.get("derivatives_crowding_upgraded")),
            cluster_confidence_upgraded=bool(row.get("cluster_confidence_upgraded")),
            material_change_reasons=tuple(str(value) for value in row.get("material_change_reasons") or ()),
            should_alert=bool(row.get("should_alert")),
            suppressed_reason=_optional_str(row.get("suppressed_reason")),
            warnings=tuple(str(value) for value in row.get("warnings") or ()),
        )
    except (TypeError, ValueError):
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows
