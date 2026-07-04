"""Split implementation for `crypto_rsi_scanner/event_alpha/artifacts/alert_store.py` (reconciliation)."""

from __future__ import annotations

import json
import math
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts as event_alpha_outcomes
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
from ....event_alpha.notifications import delivery as event_alpha_notification_delivery
from .models import *  # noqa: F403

def reconcile_alert_snapshots_with_core_store(
    snapshots: Iterable[Mapping[str, Any]],
    core_store_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Apply canonical core final state to alert snapshots when possible."""
    core_rows = [dict(row) for row in core_store_rows if isinstance(row, Mapping)]
    if not core_rows:
        return [dict(row) for row in snapshots if isinstance(row, Mapping)]
    return [_with_core_resolution(dict(row), core_rows) for row in snapshots if isinstance(row, Mapping)]
def reconcile_alert_snapshot_with_core_store(
    snapshot: Mapping[str, Any],
    core_store_row: Mapping[str, Any],
) -> dict[str, Any]:
    """Mirror final operator-facing fields from a canonical CoreOpportunity row."""
    out = dict(snapshot)
    core = dict(core_store_row)
    requested_route = str(out.get("final_route_after_quality_gate") or out.get("route") or "")
    requested_level = str(out.get("final_opportunity_level") or out.get("opportunity_level") or "")
    requested_state = str(out.get("final_state_after_quality_gate") or out.get("state") or "")
    out.setdefault("requested_route_before_core_reconciliation", requested_route)
    out.setdefault("requested_opportunity_level_before_core_reconciliation", requested_level)
    out.setdefault("requested_state_before_core_reconciliation", requested_state)

    final_level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or requested_level or "")
    final_score = _first_present(core, ("final_opportunity_score", "opportunity_score_final"))
    final_route = str(core.get("final_route_after_quality_gate") or core.get("route") or requested_route or "")
    final_state = str(core.get("final_state_after_quality_gate") or core.get("state") or requested_state or "")
    final_tier = _tier_for_final_route(final_route, out.get("requested_tier_before_quality_gate") or out.get("tier"), core)

    mirror_fields = {
        "symbol": core.get("symbol") or core.get("validated_symbol") or out.get("symbol"),
        "coin_id": core.get("coin_id") or core.get("validated_coin_id") or out.get("coin_id"),
        "asset_symbol": core.get("symbol") or core.get("validated_symbol") or out.get("asset_symbol"),
        "asset_coin_id": core.get("coin_id") or core.get("validated_coin_id") or out.get("asset_coin_id"),
        "validated_symbol": core.get("validated_symbol") or core.get("symbol") or out.get("validated_symbol"),
        "validated_coin_id": core.get("validated_coin_id") or core.get("coin_id") or out.get("validated_coin_id"),
        "final_opportunity_level": final_level,
        "opportunity_level": final_level,
        "final_opportunity_score": final_score,
        "opportunity_score_final": final_score,
        "opportunity_score": final_score if final_score is not None else out.get("opportunity_score"),
        "final_route_after_quality_gate": final_route,
        "route": final_route,
        "lane": event_alpha_router.lane_value_for_route_value(final_route),
        "final_state_after_quality_gate": final_state,
        "state": final_state,
        "final_tier_after_quality_gate": final_tier,
        "tier": final_tier,
        "final_verdict_source": core.get("final_verdict_source") or out.get("final_verdict_source"),
        "final_verdict_reason": core.get("final_verdict_reason") or out.get("final_verdict_reason"),
        "evidence_acquisition_status": core.get("evidence_acquisition_status") or out.get("evidence_acquisition_status"),
        "evidence_acquisition_accepted_count": core.get("evidence_acquisition_accepted_count", out.get("evidence_acquisition_accepted_count")),
        "evidence_acquisition_rejected_count": core.get("evidence_acquisition_rejected_count", out.get("evidence_acquisition_rejected_count")),
        "accepted_evidence_count": core.get("accepted_evidence_count", out.get("accepted_evidence_count")),
        "rejected_evidence_count": core.get("rejected_evidence_count", out.get("rejected_evidence_count")),
        "accepted_provider_counts": core.get("accepted_provider_counts") or out.get("accepted_provider_counts"),
        "rejected_provider_counts": core.get("rejected_provider_counts") or out.get("rejected_provider_counts"),
        "accepted_reason_code_counts": core.get("accepted_reason_code_counts") or out.get("accepted_reason_code_counts"),
        "accepted_evidence_reason_codes": core.get("accepted_evidence_reason_codes") or out.get("accepted_evidence_reason_codes"),
        "acquisition_confirmation_status": core.get("acquisition_confirmation_status") or out.get("acquisition_confirmation_status"),
        "acquisition_confirms_candidate": core.get("acquisition_confirms_candidate", out.get("acquisition_confirms_candidate")),
        "acquisition_confirms_impact_path": core.get("acquisition_confirms_impact_path", out.get("acquisition_confirms_impact_path")),
        "source_pack_confirmation_status": core.get("source_pack_confirmation_status") or out.get("source_pack_confirmation_status"),
        "live_confirmation_required": core.get("live_confirmation_required", out.get("live_confirmation_required")),
        "live_confirmation_passed": core.get("live_confirmation_passed", out.get("live_confirmation_passed")),
        "live_confirmation_status": core.get("live_confirmation_status") or out.get("live_confirmation_status"),
        "live_confirmation_reason": core.get("live_confirmation_reason") or out.get("live_confirmation_reason"),
        "live_confirmation_capped": core.get("live_confirmation_capped", out.get("live_confirmation_capped")),
        "live_confirmation_missing_requirements": core.get("live_confirmation_missing_requirements") or out.get("live_confirmation_missing_requirements"),
        "quality_gate_block_reason": (
            core.get("quality_gate_block_reason")
            or core.get("canonical_route_adjustment_reason")
            or out.get("quality_gate_block_reason")
        ),
        "feedback_target": core.get("feedback_target") or core.get("core_opportunity_id") or out.get("feedback_target"),
        "feedback_target_type": core.get("feedback_target_type") or "core_opportunity_id",
        "core_opportunity_id": core.get("core_opportunity_id") or out.get("core_opportunity_id"),
    }
    for key, value in mirror_fields.items():
        if value is not None:
            out[key] = value

    out["alertable_after_quality_gate"] = event_alpha_router.route_value_is_alertable(final_route)
    out["route_alertable"] = out["alertable_after_quality_gate"]
    changed = any(
        str(out.get(key) or "") != str(snapshot.get(key) or "")
        for key in ("final_route_after_quality_gate", "route", "opportunity_level", "final_state_after_quality_gate")
    )
    out["snapshot_core_reconciled"] = True
    out["snapshot_core_reconciliation_reason"] = (
        "canonical_core_final_state_applied" if changed else "canonical_core_aligned"
    )
    out.setdefault("core_resolution_status", "canonical")
    out["snapshot_core_resolution_status"] = SNAPSHOT_CORE_RECONCILED
    out["snapshot_class"] = SNAPSHOT_CLASS_CANONICAL_CORE
    return _with_snapshot_quality_classification(out)
def reconcile_diagnostic_support_snapshot_with_core_store(
    snapshot: Mapping[str, Any],
    core_store_row: Mapping[str, Any],
    *,
    diagnostic_support_for_core_opportunity_id: str | None = None,
) -> dict[str, Any]:
    """Link a diagnostic/support snapshot to a core without inheriting alertability."""
    out = dict(snapshot)
    core = dict(core_store_row)
    requested_route = str(out.get("final_route_after_quality_gate") or out.get("route") or "")
    requested_level = str(out.get("final_opportunity_level") or out.get("opportunity_level") or "")
    requested_state = str(out.get("final_state_after_quality_gate") or out.get("state") or "")
    out.setdefault("requested_route_before_core_reconciliation", requested_route)
    out.setdefault("requested_opportunity_level_before_core_reconciliation", requested_level)
    out.setdefault("requested_state_before_core_reconciliation", requested_state)

    diagnostic_level = requested_level if requested_level in {"local_only", "exploratory", "diagnostic"} else "local_only"
    out["core_opportunity_id"] = core.get("core_opportunity_id") or out.get("core_opportunity_id")
    out["diagnostic_support_for_core_opportunity_id"] = (
        diagnostic_support_for_core_opportunity_id
        or core.get("core_opportunity_id")
        or out.get("diagnostic_support_for_core_opportunity_id")
    )
    out["is_diagnostic_snapshot"] = True
    out["snapshot_class"] = SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
    out["snapshot_core_reconciled"] = False
    out["snapshot_core_resolution_status"] = "diagnostic_support"
    out["snapshot_core_reconciliation_reason"] = "diagnostic_support_not_alertable"
    out["final_route_after_quality_gate"] = event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    out["route"] = event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    out["lane"] = event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY.value
    out["final_tier_after_quality_gate"] = event_alerts.EventAlertTier.STORE_ONLY.value
    out["tier"] = event_alerts.EventAlertTier.STORE_ONLY.value
    out["final_opportunity_level"] = diagnostic_level
    out["opportunity_level"] = diagnostic_level
    out["diagnostic_support_level"] = requested_level or diagnostic_level
    out["alertable_after_quality_gate"] = False
    out["route_alertable"] = False
    out["support_for_core_summary"] = {
        "core_opportunity_id": core.get("core_opportunity_id"),
        "symbol": core.get("symbol") or core.get("validated_symbol"),
        "coin_id": core.get("coin_id") or core.get("validated_coin_id"),
        "final_opportunity_level": core.get("final_opportunity_level") or core.get("opportunity_level"),
        "final_route_after_quality_gate": core.get("final_route_after_quality_gate") or core.get("route"),
        "final_state_after_quality_gate": core.get("final_state_after_quality_gate") or core.get("state"),
        "final_opportunity_score": _first_present(core, ("final_opportunity_score", "opportunity_score_final")),
    }
    out["quality_gate_block_reason"] = out.get("quality_gate_block_reason") or "diagnostic_support_not_alertable"
    out.setdefault("feedback_target", out.get("diagnostic_row_id") or out.get("alert_id") or out.get("alert_key"))
    out["feedback_target_type"] = "diagnostic_support_for_core_opportunity_id"
    return _with_snapshot_quality_classification(out)


def _snapshot_incident_fields(entry: Any, components: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "incident_id": components.get("incident_id"),
        "hypothesis_id": components.get("hypothesis_id") or entry.hypothesis_id or entry.event_id,
        "incident_link_status": components.get("incident_link_status") or entry.incident_link_status or (
            "linked" if components.get("incident_id") or entry.incident_id else "no_incident"
        ),
        "incident_link_reason": (
            components.get("incident_link_reason")
            or entry.incident_link_reason
            or (None if components.get("incident_id") or entry.incident_id else "no_canonical_incident_for_event_evidence")
        ),
        "incident_relevance_status": components.get("incident_relevance_status"),
        "incident_relevance_score": components.get("incident_relevance_score"),
        "incident_relevance_reasons": components.get("incident_relevance_reasons") or (),
        "incident_relevance_warnings": components.get("incident_relevance_warnings") or (),
        "canonical_persistence_reason": components.get("canonical_persistence_reason"),
        "incident_canonical_name": components.get("incident_canonical_name") or components.get("canonical_incident_name") or entry.incident_canonical_name,
        "canonical_incident_name": components.get("canonical_incident_name") or components.get("incident_canonical_name") or entry.incident_canonical_name,
        "incident_event_archetype": components.get("incident_event_archetype") or components.get("event_archetype"),
        "event_archetype": components.get("event_archetype") or components.get("incident_event_archetype"),
        "incident_primary_subject": components.get("incident_primary_subject") or components.get("primary_subject") or entry.incident_primary_subject,
        "primary_subject": components.get("primary_subject") or components.get("incident_primary_subject") or entry.incident_primary_subject,
        "incident_affected_ecosystem": components.get("incident_affected_ecosystem") or components.get("affected_ecosystem") or entry.incident_affected_ecosystem,
        "affected_ecosystem": components.get("affected_ecosystem") or components.get("incident_affected_ecosystem") or entry.incident_affected_ecosystem,
        "incident_cause_status": components.get("incident_cause_status") or components.get("cause_status") or entry.incident_cause_status,
        "cause_status": components.get("cause_status") or components.get("incident_cause_status") or entry.incident_cause_status,
        "claim_polarities": components.get("claim_polarities") or (),
        "claim_history": components.get("claim_history") or (),
        "role_confidence": components.get("role_confidence"),
        "role_evidence": components.get("role_evidence") or (),
        "market_context_source": components.get("market_context_source"),
        "market_context_observed_at": components.get("market_context_observed_at"),
        "market_context_age_seconds": components.get("market_context_age_seconds"),
        "market_context_age_hours": components.get("market_context_age_hours"),
        "market_context_stale": components.get("market_context_stale"),
        "market_context_freshness_status": components.get("market_context_freshness_status"),
        "market_context_freshness_cap_applied": components.get("market_context_freshness_cap_applied"),
        "market_context_data_quality": components.get("market_context_data_quality"),
        "incident_market_reaction_observed": components.get("incident_market_reaction_observed") or components.get("market_reaction_observed") or entry.incident_market_reaction_observed,
        "market_reaction_observed": components.get("market_reaction_observed") or components.get("incident_market_reaction_observed") or entry.incident_market_reaction_observed,
        "market_reaction_confirmed": components.get("market_reaction_confirmed"),
        "incident_causal_mechanism_confirmed": components.get("incident_causal_mechanism_confirmed") or components.get("causal_mechanism_confirmed") or entry.incident_causal_mechanism_confirmed,
        "causal_mechanism_confirmed": components.get("causal_mechanism_confirmed") or components.get("incident_causal_mechanism_confirmed") or entry.incident_causal_mechanism_confirmed,
        "incident_confidence": components.get("incident_confidence"),
    }


def _snapshot_opportunity_quality_fields(components: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "validation_stage": components.get("validation_stage"),
        "impact_path_reason": components.get("impact_path_reason"),
        "impact_path_type": components.get("impact_path_type"),
        "impact_path_strength": components.get("impact_path_strength"),
        "candidate_role": components.get("candidate_role"),
        "evidence_specificity_score": components.get("evidence_specificity_score"),
        "digest_eligible_by_impact_path": components.get("digest_eligible_by_impact_path"),
        "why_digest_ineligible": components.get("why_digest_ineligible"),
        "evidence_quality_score": components.get("evidence_quality_score"),
        "source_class": components.get("source_class"),
        "evidence_specificity": components.get("evidence_specificity"),
        "market_confirmation_score": components.get("market_confirmation_score"),
        "market_confirmation_level": components.get("market_confirmation_level"),
        "opportunity_score_final": components.get("opportunity_score_final"),
        "opportunity_level": components.get("opportunity_level"),
        "opportunity_verdict_reasons": components.get("opportunity_verdict_reasons") or (),
        "why_local_only": components.get("why_local_only"),
        "why_not_watchlist": components.get("why_not_watchlist"),
        "manual_verification_items": components.get("manual_verification_items") or (),
    }


def _snapshot_from_route_decision(
    decision: event_alpha_router.EventAlphaRouteDecision,
    observed: datetime,
) -> dict[str, Any]:
    entry = decision.entry
    components = dict(entry.latest_score_components or {})
    alert_key = str(entry.key)
    observed_iso = observed.isoformat()
    playbook = entry.latest_effective_playbook_type or entry.latest_playbook_type or "unknown"
    validated_asset = components.get("validated_asset") if isinstance(components.get("validated_asset"), Mapping) else {}
    validated_symbol = components.get("validated_symbol") or validated_asset.get("symbol") or entry.symbol
    validated_coin_id = components.get("validated_coin_id") or validated_asset.get("coin_id") or entry.coin_id
    symbol = entry.symbol or validated_symbol
    coin_id = entry.coin_id or validated_coin_id
    warnings = list(entry.warnings)
    if not symbol and not validated_symbol:
        warnings.append("validated_hypothesis_snapshot_missing_identity")
    entry_quality = {
        key: getattr(entry, key, None)
        for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS
        if getattr(entry, key, None) not in (None, "", [], {}, ())
    }
    quality = event_alpha_quality_fields.ensure_quality_fields(entry_quality, components=components)
    final_route = event_alpha_router.final_route_value(decision)
    final_lane = event_alpha_router.final_lane_value(decision)
    alertable_after_quality = event_alpha_router.alertable_after_quality_gate(decision)
    tier = entry.latest_tier if alertable_after_quality else event_alerts.EventAlertTier.STORE_ONLY.value
    core_id = (
        components.get("core_opportunity_id")
        or components.get("aggregated_candidate_id")
        or event_core_opportunities.core_opportunity_id_for_row(entry)
    )
    feedback_target = str(core_id or decision.alert_id or alert_key)
    feedback_target_type = "core_opportunity_id" if core_id else "alert_id"
    row = {
        "schema_version": ALERT_STORE_SCHEMA_VERSION,
        "row_type": "event_alpha_alert_snapshot",
        "snapshot_id": f"{observed_iso}|{alert_key}",
        "alert_key": alert_key,
        "cluster_id": entry.cluster_id,
        "observed_at": observed_iso,
        "event_id": entry.event_id,
        "event_name": entry.latest_event_name,
        "event_type": components.get("event_type") or "impact_hypothesis",
        "event_time": entry.event_time,
        "external_asset": entry.external_asset,
        "coin_id": coin_id,
        "symbol": symbol,
        "asset_coin_id": coin_id,
        "asset_symbol": symbol,
        "asset_name": validated_asset.get("name") if isinstance(validated_asset, Mapping) else None,
        "relationship_type": entry.relationship_type,
        "asset_role": components.get("asset_role"),
        "source": entry.latest_source,
        "source_count": entry.source_count,
        "tier": tier,
        "requested_tier_before_quality_gate": entry.latest_tier,
        "opportunity_score": entry.latest_score,
        "opportunity_score_v2": components.get("opportunity_score_v2"),
        "opportunity_score_components": components.get("opportunity_score_components") or {},
        "score_components": components,
        "playbook_type": playbook,
        "rule_playbook_type": entry.latest_rule_playbook_type,
        "effective_playbook_type": playbook,
        "llm_adjusted_playbook_type": entry.latest_llm_adjusted_playbook_type,
        "playbook_score": entry.latest_playbook_score,
        "playbook_action": entry.latest_playbook_action,
        "llm_asset_role": entry.latest_llm_asset_role,
        "llm_confidence": entry.latest_llm_confidence,
        "expected_direction": components.get("direction_hint") or components.get("expected_direction") or "unknown",
        "primary_horizon": components.get("primary_horizon") or "manual",
        "success_metric": components.get("success_metric") or "manual",
        "market_anomaly_bucket": _market_anomaly_bucket(components.get("market_move_volume", 0)),
        "btc_regime": components.get("btc_regime") or "unknown",
        "signal_type": components.get("signal_type"),
        "fade_state": components.get("fade_state"),
        "state": event_watchlist.final_state_value(entry),
        **_state_cap_context(entry),
        "route": final_route,
        "lane": final_lane,
        "requested_route_before_quality_gate": decision.requested_route_before_quality_gate or decision.route.value,
        "final_route_after_quality_gate": final_route,
        "final_tier_after_quality_gate": _tier_for_final_route(final_route, entry.latest_tier, quality),
        "quality_gate_block_reason": decision.quality_gate_block_reason,
        "alert_id": decision.alert_id,
        "card_id": decision.card_id,
        "core_opportunity_id": core_id,
        "feedback_target": feedback_target,
        "feedback_target_type": feedback_target_type,
        "route_alertable": alertable_after_quality,
        "alertable_after_quality_gate": alertable_after_quality,
        "route_reason": decision.reason,
        "impact_category": components.get("impact_category") or playbook,
        **_snapshot_incident_fields(entry, components),
        **_snapshot_opportunity_quality_fields(components),
        **quality,
        "hypothesis_score": components.get("hypothesis_score") or entry.latest_score,
        "validated_symbol": validated_symbol,
        "validated_coin_id": validated_coin_id,
        "quality_warnings": tuple(dict.fromkeys(warnings)),
        "research_card_path": None,
        "delivered_status": None,
        "feedback_status": "pending",
        "reason": decision.reason,
        "verify": components.get("what_to_verify") or [],
        "rejected_reason": None,
    }
    return _with_snapshot_quality_classification(row)
def _route_context_by_key(router_result: Any | None) -> dict[str, dict[str, Any]]:
    if router_result is None:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for decision in getattr(router_result, "decisions", ()) or ():
        entry = getattr(decision, "entry", None)
        key = str(getattr(entry, "key", "") or "")
        if not key:
            continue
        route = getattr(decision, "route", "")
        final_route = event_alpha_router.final_route_value(decision)
        final_lane = event_alpha_router.final_lane_value(decision)
        alertable_after_quality = event_alpha_router.alertable_after_quality_gate(decision)
        components = getattr(entry, "latest_score_components", None)
        if not isinstance(components, Mapping):
            components = {}
        entry_quality = {
            quality_key: getattr(entry, quality_key, None)
            for quality_key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS
            if getattr(entry, quality_key, None) not in (None, "", [], {}, ())
        }
        quality = event_alpha_quality_fields.ensure_quality_fields(entry_quality, components=components)
        core_id = (
            components.get("core_opportunity_id")
            or components.get("aggregated_candidate_id")
            or event_core_opportunities.core_opportunity_id_for_row(entry)
        )
        out[key] = {
            "alert_id": getattr(decision, "alert_id", f"ea:{key}"),
            "card_id": getattr(decision, "card_id", ""),
            "core_opportunity_id": core_id,
            "feedback_target": core_id or getattr(decision, "alert_id", f"ea:{key}"),
            "feedback_target_type": "core_opportunity_id" if core_id else "alert_id",
            "route": final_route,
            "lane": final_lane,
            "requested_route_before_quality_gate": getattr(decision, "requested_route_before_quality_gate", None)
            or getattr(route, "value", str(route)),
            "final_route_after_quality_gate": final_route,
            "final_tier_after_quality_gate": _tier_for_final_route(
                final_route,
                getattr(entry, "latest_tier", None),
                quality,
            ),
            "quality_gate_block_reason": getattr(decision, "quality_gate_block_reason", None),
            "opportunity_level": getattr(decision, "opportunity_level", None) or quality.get("opportunity_level"),
            "opportunity_score_final": getattr(decision, "opportunity_score_final", None)
            if getattr(decision, "opportunity_score_final", None) is not None
            else quality.get("opportunity_score_final"),
            "route_alertable": alertable_after_quality,
            "alertable_after_quality_gate": alertable_after_quality,
            "route_reason": str(getattr(decision, "reason", "") or ""),
            **_state_cap_context(entry),
        }
    return out
def _route_decisions_for_snapshots(router_result: Any | None) -> tuple[event_alpha_router.EventAlphaRouteDecision, ...]:
    if router_result is None:
        return ()
    out: list[event_alpha_router.EventAlphaRouteDecision] = []
    for decision in getattr(router_result, "decisions", ()) or ():
        requested = getattr(decision, "requested_route_before_quality_gate", None)
        final = getattr(decision, "final_route_after_quality_gate", None)
        if (
            bool(getattr(decision, "alertable", False))
            or bool(getattr(decision, "quality_gate_block_reason", None))
            or (requested and final and requested != final)
        ):
            out.append(decision)
    return tuple(out)
def _with_route_context(row: dict[str, Any], route_context: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    context = route_context.get(str(row.get("alert_key") or ""))
    if not context:
        return _with_snapshot_quality_classification(row)
    out = dict(row)
    if "requested_tier_before_quality_gate" not in out:
        out["requested_tier_before_quality_gate"] = out.get("tier")
    out.update(context)
    if context.get("state") is not None:
        out["state"] = context.get("state")
    if not bool(out.get("alertable_after_quality_gate", out.get("route_alertable"))):
        out["tier"] = event_alerts.EventAlertTier.STORE_ONLY.value
    elif out.get("final_tier_after_quality_gate"):
        out["tier"] = out["final_tier_after_quality_gate"]
    return _with_snapshot_quality_classification(out)
def _with_canonical_quality_route(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    components = out.get("score_components") if isinstance(out.get("score_components"), Mapping) else {}
    requested_route = str(
        out.get("requested_route_before_quality_gate")
        or out.get("route")
        or _route_for_tier_value(out.get("requested_tier_before_quality_gate") or out.get("tier"))
    )
    out["requested_route_before_quality_gate"] = requested_route
    out.setdefault("requested_tier_before_quality_gate", out.get("tier"))
    has_quality = event_alpha_quality_fields.has_any_quality_field(out, components_key="score_components")
    final_route, block = event_alpha_router.quality_gate_route_for_row(
        out,
        components=components,
        requested_route=requested_route,
        require_quality=has_quality,
    )
    final_tier = _tier_for_final_route(final_route, out.get("requested_tier_before_quality_gate") or out.get("tier"), out)
    out["final_route_after_quality_gate"] = final_route
    out["final_tier_after_quality_gate"] = final_tier
    out["quality_gate_block_reason"] = block or out.get("quality_gate_block_reason")
    out["alertable_after_quality_gate"] = event_alpha_router.route_value_is_alertable(final_route)
    out["route_alertable"] = out["alertable_after_quality_gate"]
    out["route"] = final_route
    out["lane"] = event_alpha_router.lane_value_for_route_value(final_route)
    out["tier"] = final_tier
    return _with_snapshot_quality_classification(out)
def _route_for_tier_value(tier: object) -> str:
    value = str(getattr(tier, "value", tier) or "").upper()
    if value == event_alerts.EventAlertTier.TRIGGERED_FADE.value:
        return event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value
    if value == event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH.value:
        return event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    if value in {event_alerts.EventAlertTier.WATCHLIST.value, event_alerts.EventAlertTier.RADAR_DIGEST.value}:
        return event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    return event_alpha_router.EventAlphaRoute.STORE_ONLY.value
def _tier_for_final_route(
    final_route: object,
    requested_tier: object,
    quality: Mapping[str, Any] | None = None,
) -> str:
    route = str(getattr(final_route, "value", final_route) or "").upper()
    requested = str(getattr(requested_tier, "value", requested_tier) or "").upper()
    if route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
        return event_alerts.EventAlertTier.TRIGGERED_FADE.value
    if route == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value:
        return event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH.value
    if route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value:
        if requested in {event_alerts.EventAlertTier.WATCHLIST.value, event_alerts.EventAlertTier.RADAR_DIGEST.value}:
            return requested
        level = str((quality or {}).get("opportunity_level") or "").strip()
        if level == "watchlist":
            return event_alerts.EventAlertTier.WATCHLIST.value
        return event_alerts.EventAlertTier.RADAR_DIGEST.value
    return event_alerts.EventAlertTier.STORE_ONLY.value
def _delivery_context_by_alert_id(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in event_alpha_notification_delivery.latest_rows_by_delivery(rows):
        state = str(row.get("state") or "")
        alert_ids = [part.strip() for part in str(row.get("alert_id") or "").split(",") if part.strip()]
        if not alert_ids:
            continue
        context = {
            "delivered_status": state,
            "delivery_state": state,
            "delivery_id": row.get("delivery_id"),
            "delivery_lane": row.get("lane"),
            "delivery_delivered_at": row.get("delivered_at"),
            "delivery_delivered_count": row.get("delivered_count"),
            "delivery_failed_count": row.get("failed_count"),
        }
        for alert_id in alert_ids:
            out[alert_id] = context
            if alert_id.startswith("ea:"):
                out[alert_id[3:]] = context
            else:
                out[f"ea:{alert_id}"] = context
    return out
def _with_delivery_context(row: dict[str, Any], context: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    ids = [
        str(row.get("alert_id") or ""),
        str(row.get("alert_key") or ""),
        str(row.get("card_id") or ""),
    ]
    for value in ids:
        if value and value in context:
            out = dict(row)
            out.update(context[value])
            return out
    return row
def _card_context_by_card_id(paths: Iterable[str | Path]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for raw in paths:
        path = Path(raw).expanduser()
        if path.name == "index.md":
            continue
        context = {
            "research_card_path": str(path),
        }
        core_id = event_research_cards.card_core_opportunity_id(path)
        feedback_target = event_research_cards.card_feedback_target(path)
        if core_id:
            context["core_opportunity_id"] = core_id
            context.setdefault("feedback_target", core_id)
            context.setdefault("feedback_target_type", "core_opportunity_id")
        if feedback_target:
            context["feedback_target"] = feedback_target
            context.setdefault(
                "feedback_target_type",
                "core_opportunity_id" if feedback_target.startswith("core_") else "card_feedback_target",
            )
        stem = path.stem
        identifiers = {stem, core_id or "", feedback_target or ""}
        if stem.startswith("card_"):
            identifiers.add(stem[5:])
        for identifier in identifiers:
            if identifier:
                out[identifier] = dict(context)
    return out
def _with_card_context(row: dict[str, Any], context: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    for value in (
        str(row.get("card_id") or ""),
        str(row.get("alert_id") or "").replace("ea:", "card_"),
        str(row.get("core_opportunity_id") or ""),
        str(row.get("feedback_target") or ""),
    ):
        if value and value in context:
            out = dict(row)
            card = context[value]
            out["research_card_path"] = card.get("research_card_path")
            if card.get("core_opportunity_id") and not out.get("core_opportunity_id"):
                out["core_opportunity_id"] = card.get("core_opportunity_id")
            if card.get("feedback_target") and not out.get("feedback_target"):
                out["feedback_target"] = card.get("feedback_target")
                out["feedback_target_type"] = card.get("feedback_target_type")
            return out
    return row
def _with_core_resolution(row: dict[str, Any], core_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    core_rows_tuple = tuple(dict(item) for item in core_rows if isinstance(item, Mapping))
    core_by_id = {
        str(item.get("core_opportunity_id") or "").strip(): item
        for item in core_rows_tuple
        if str(item.get("core_opportunity_id") or "").strip()
    }
    out = dict(row)
    if _is_explicit_diagnostic_support_snapshot(out):
        core_id = str(
            out.get("diagnostic_support_for_core_opportunity_id")
            or out.get("core_opportunity_id")
            or ""
        ).strip()
        core_row = core_by_id.get(core_id)
        if core_row:
            out["core_opportunity_id_status"] = "diagnostic_support"
            out["core_resolution_status"] = "diagnostic_support"
            out["canonical_core_resolution_warnings"] = out.get("canonical_core_resolution_warnings") or ()
            out["diagnostic_row_id"] = _diagnostic_row_id(out)
            return reconcile_diagnostic_support_snapshot_with_core_store(
                out,
                core_row,
                diagnostic_support_for_core_opportunity_id=core_id,
            )
        out["diagnostic_row_id"] = _diagnostic_row_id(out)
        out["is_diagnostic_snapshot"] = True
        out["snapshot_class"] = SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        out["snapshot_core_reconciled"] = False
        out["snapshot_core_resolution_status"] = "diagnostic_support"
        out["snapshot_core_reconciliation_reason"] = "diagnostic_support_missing_canonical_core"
        out["alertable_after_quality_gate"] = False
        out["route_alertable"] = False
        out["requested_route_before_core_reconciliation"] = out.get("final_route_after_quality_gate") or out.get("route")
        out["requested_opportunity_level_before_core_reconciliation"] = out.get("final_opportunity_level") or out.get("opportunity_level")
        out["final_route_after_quality_gate"] = event_alpha_router.EventAlphaRoute.STORE_ONLY.value
        out["route"] = event_alpha_router.EventAlphaRoute.STORE_ONLY.value
        out["lane"] = event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY.value
        out["final_tier_after_quality_gate"] = event_alerts.EventAlertTier.STORE_ONLY.value
        out["tier"] = event_alerts.EventAlertTier.STORE_ONLY.value
        out["quality_gate_block_reason"] = out.get("quality_gate_block_reason") or "diagnostic_support_missing_canonical_core"
        out["feedback_target"] = out.get("diagnostic_row_id") or out.get("feedback_target") or out.get("alert_key")
        out["feedback_target_type"] = "diagnostic_support_for_core_opportunity_id"
        return _with_snapshot_quality_classification(out)

    resolution = event_core_opportunities.resolve_canonical_core_opportunity_id(row, core_rows_tuple)
    out["core_opportunity_id_status"] = resolution.resolution_status
    out["core_resolution_status"] = resolution.resolution_status
    out["canonical_core_resolution_warnings"] = resolution.warnings
    if resolution.resolution_status == "canonical":
        out["core_opportunity_id"] = resolution.canonical_core_opportunity_id
        out["is_diagnostic_snapshot"] = False
        out["snapshot_class"] = SNAPSHOT_CLASS_CANONICAL_CORE
        out.pop("diagnostic_support_for_core_opportunity_id", None)
        out.setdefault("feedback_target", resolution.canonical_core_opportunity_id)
        out.setdefault("feedback_target_type", "core_opportunity_id")
        core_row = core_by_id.get(str(resolution.canonical_core_opportunity_id or ""))
        if core_row:
            out = reconcile_alert_snapshot_with_core_store(out, core_row)
    elif resolution.resolution_status == "diagnostic_support":
        out["core_opportunity_id"] = resolution.canonical_core_opportunity_id
        out["diagnostic_support_for_core_opportunity_id"] = resolution.diagnostic_support_for_core_opportunity_id
        out["diagnostic_row_id"] = _diagnostic_row_id(out)
        out["is_diagnostic_snapshot"] = True
        out["snapshot_class"] = SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        core_row = core_by_id.get(str(resolution.canonical_core_opportunity_id or ""))
        if core_row:
            out = reconcile_diagnostic_support_snapshot_with_core_store(
                out,
                core_row,
                diagnostic_support_for_core_opportunity_id=resolution.diagnostic_support_for_core_opportunity_id,
            )
        out["feedback_target"] = out.get("diagnostic_row_id") or out.get("feedback_target") or out.get("alert_key")
        out["feedback_target_type"] = "diagnostic_support_for_core_opportunity_id"
    elif event_core_opportunities.row_is_diagnostic(out):
        out["diagnostic_row_id"] = _diagnostic_row_id(out)
        out["is_diagnostic_snapshot"] = True
        out["snapshot_class"] = SNAPSHOT_CLASS_ORPHAN
        out["diagnostic_support_for_core_opportunity_id"] = None
        out["core_opportunity_id"] = None
        if out.get("feedback_target_type") == "core_opportunity_id":
            out["feedback_target"] = out.get("alert_id") or out.get("alert_key") or out["diagnostic_row_id"]
            out["feedback_target_type"] = "diagnostic_row_id"
    else:
        out["is_diagnostic_snapshot"] = False
        out.setdefault("snapshot_class", SNAPSHOT_CLASS_ORPHAN if resolution.resolution_status == "orphan" else SNAPSHOT_CLASS_EXTERNAL)
        if resolution.canonical_core_opportunity_id:
            out["core_opportunity_id"] = resolution.canonical_core_opportunity_id
            out.setdefault("feedback_target", resolution.canonical_core_opportunity_id)
            out.setdefault("feedback_target_type", "core_opportunity_id")
            out["core_resolution_status"] = SNAPSHOT_MISSING_CORE
            out["snapshot_core_reconciled"] = False
            out["snapshot_core_reconciliation_reason"] = "missing_canonical_core_store_row"
            out["snapshot_class"] = SNAPSHOT_CLASS_ORPHAN
            out["alertable_after_quality_gate"] = False
            out["route_alertable"] = False
            out["requested_route_before_core_reconciliation"] = out.get("final_route_after_quality_gate") or out.get("route")
            out["requested_opportunity_level_before_core_reconciliation"] = out.get("final_opportunity_level") or out.get("opportunity_level")
            out["final_route_after_quality_gate"] = event_alpha_router.EventAlphaRoute.STORE_ONLY.value
            out["route"] = event_alpha_router.EventAlphaRoute.STORE_ONLY.value
            out["lane"] = event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY.value
            out["final_tier_after_quality_gate"] = event_alerts.EventAlertTier.STORE_ONLY.value
            out["tier"] = event_alerts.EventAlertTier.STORE_ONLY.value
            out["quality_gate_block_reason"] = out.get("quality_gate_block_reason") or "missing_core_opportunity_store_row"
    return _with_snapshot_quality_classification(out)
def _sibling_core_store_rows(alert_path: Path) -> list[dict[str, Any]]:
    core_path = alert_path.expanduser().parent / "event_core_opportunities.jsonl"
    if not core_path.exists():
        return []
    return [
        row for row in _read_jsonl(core_path)
        if row.get("row_type") == "event_core_opportunity"
    ]
def _diagnostic_row_id(row: Mapping[str, Any]) -> str:
    for key in ("diagnostic_row_id", "snapshot_id", "alert_id", "alert_key", "event_id", "hypothesis_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    payload = json.dumps(_json_ready(dict(row)), sort_keys=True, separators=(",", ":"))
    return "diagnostic:" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
def _is_diagnostic_support_snapshot(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("snapshot_class") or "") == SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        or str(row.get("core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("snapshot_core_resolution_status") or "") == "diagnostic_support"
        or bool(row.get("is_diagnostic_snapshot"))
    )
def _is_explicit_diagnostic_support_snapshot(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("snapshot_class") or "") == SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        or str(row.get("core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("snapshot_core_resolution_status") or "") == "diagnostic_support"
        or bool(str(row.get("diagnostic_support_for_core_opportunity_id") or "").strip())
    )
