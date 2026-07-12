"""Split implementation for `crypto_rsi_scanner/event_alpha/artifacts/alert_store.py` (snapshots)."""

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
from ...radar.decision_model_surfaces import decision_model_values
from ....event_alpha.notifications import delivery as event_alpha_notification_delivery
from .models import *  # noqa: F403

def _snapshot_from_alert(alert: event_alerts.EventAlertCandidate, observed: datetime) -> dict[str, Any]:
    candidate = alert.discovery_candidate
    fade_candidate = candidate.fade_candidate
    signal = candidate.fade_signal
    market = fade_candidate.market if fade_candidate is not None else None
    entry = None
    if signal is not None:
        entry = signal.entry_reference_price
    if entry is None and market is not None:
        entry = market.price
    cluster_id = event_graph.cluster_id_for_event(candidate.event)
    effective_playbook = alert.effective_playbook_type or alert.playbook_type or candidate.classification.relationship_type
    alert_key = f"{cluster_id}|{candidate.asset.coin_id}|{effective_playbook}"
    observed_iso = observed.isoformat()
    quality = event_alpha_quality_fields.ensure_quality_fields({}, components=alert.score_components)
    requested_route = _route_for_tier_value(alert.tier.value)
    row = {
        "schema_version": ALERT_STORE_SCHEMA_VERSION,
        "row_type": "event_alpha_alert_snapshot",
        "snapshot_id": f"{observed_iso}|{alert_key}",
        "alert_key": alert_key,
        "cluster_id": cluster_id,
        "observed_at": observed_iso,
        "event_id": candidate.event.event_id,
        "event_name": candidate.event.event_name,
        "event_type": candidate.event.event_type,
        "event_time": candidate.event.event_time.isoformat() if candidate.event.event_time else None,
        "external_asset": candidate.event.external_asset,
        "coin_id": candidate.asset.coin_id,
        "symbol": candidate.asset.symbol,
        "asset_coin_id": candidate.asset.coin_id,
        "asset_symbol": candidate.asset.symbol,
        "asset_name": candidate.asset.name,
        "relationship_type": candidate.classification.relationship_type,
        "asset_role": candidate.classification.asset_role,
        "source": candidate.event.source,
        "source_count": len(candidate.event.raw_ids),
        "tier": alert.tier.value,
        "requested_tier_before_quality_gate": alert.tier.value,
        "requested_state_before_quality_gate": None,
        "final_state_after_quality_gate": None,
        "quality_state_block_reason": None,
        "state_quality_capped": False,
        "requested_route_before_quality_gate": requested_route,
        "opportunity_score": alert.opportunity_score,
        "score_before_priors": alert.score_before_priors,
        "score_after_priors": alert.score_after_priors,
        "prior_file": alert.prior_file,
        "prior_version": alert.prior_version,
        "prior_generated_at": alert.prior_generated_at,
        "prior_multipliers_applied": dict(alert.prior_multipliers_applied),
        "score_components": dict(alert.score_components),
        "playbook_type": effective_playbook,
        "rule_playbook_type": alert.rule_playbook_type,
        "effective_playbook_type": effective_playbook,
        "llm_adjusted_playbook_type": alert.llm_adjusted_playbook_type,
        "playbook_score": alert.playbook_score,
        "playbook_action": alert.playbook_action,
        "playbook_hypothesis": alert.playbook_hypothesis,
        "playbook_what_to_verify": list(alert.playbook_what_to_verify),
        "playbook_timing_window": alert.playbook_timing_window,
        "playbook_invalidation": alert.playbook_invalidation,
        "llm_asset_role": alert.llm_asset_role,
        "llm_relationship_type": alert.llm_relationship_type,
        "llm_confidence": alert.llm_confidence,
        "expected_direction": alert.expected_direction,
        "primary_horizon": alert.primary_horizon,
        "success_metric": alert.success_metric,
        "entry_reference_price": entry,
        "market_price": market.price if market else None,
        "return_24h_at_alert": market.return_24h if market else None,
        "return_72h_at_alert": market.return_72h if market else None,
        "return_7d_at_alert": market.return_7d if market else None,
        "volume_zscore_24h": market.volume_zscore_24h if market else None,
        "market_anomaly_bucket": _market_anomaly_bucket(alert.score_components.get("market_move_volume", 0)),
        "incident_id": alert.score_components.get("incident_id"),
        "hypothesis_id": alert.score_components.get("hypothesis_id"),
        "incident_link_status": "linked" if alert.score_components.get("incident_id") else "no_incident",
        "incident_link_reason": (
            None
            if alert.score_components.get("incident_id")
            else alert.score_components.get("incident_link_reason")
            or "no_canonical_incident_for_event_evidence"
        ),
        "incident_relevance_status": alert.score_components.get("incident_relevance_status"),
        "incident_relevance_score": alert.score_components.get("incident_relevance_score"),
        "incident_relevance_reasons": alert.score_components.get("incident_relevance_reasons") or (),
        "incident_relevance_warnings": alert.score_components.get("incident_relevance_warnings") or (),
        "canonical_persistence_reason": alert.score_components.get("canonical_persistence_reason"),
        "incident_canonical_name": alert.score_components.get("incident_canonical_name") or alert.score_components.get("canonical_incident_name"),
        "canonical_incident_name": alert.score_components.get("canonical_incident_name"),
        "incident_event_archetype": alert.score_components.get("incident_event_archetype") or alert.score_components.get("event_archetype"),
        "event_archetype": alert.score_components.get("event_archetype"),
        "incident_primary_subject": alert.score_components.get("incident_primary_subject") or alert.score_components.get("primary_subject"),
        "primary_subject": alert.score_components.get("primary_subject"),
        "incident_affected_ecosystem": alert.score_components.get("incident_affected_ecosystem") or alert.score_components.get("affected_ecosystem"),
        "affected_ecosystem": alert.score_components.get("affected_ecosystem"),
        "incident_cause_status": alert.score_components.get("incident_cause_status") or alert.score_components.get("cause_status"),
        "cause_status": alert.score_components.get("cause_status"),
        "claim_polarities": alert.score_components.get("claim_polarities") or (),
        "claim_history": alert.score_components.get("claim_history") or (),
        "role_confidence": alert.score_components.get("role_confidence"),
        "role_evidence": alert.score_components.get("role_evidence") or (),
        "market_context_source": alert.score_components.get("market_context_source"),
        "market_context_observed_at": alert.score_components.get("market_context_observed_at"),
        "market_context_age_seconds": alert.score_components.get("market_context_age_seconds"),
        "market_context_age_hours": alert.score_components.get("market_context_age_hours"),
        "market_context_stale": alert.score_components.get("market_context_stale"),
        "market_context_freshness_status": alert.score_components.get("market_context_freshness_status"),
        "market_context_freshness_cap_applied": alert.score_components.get("market_context_freshness_cap_applied"),
        "market_context_data_quality": alert.score_components.get("market_context_data_quality"),
        "incident_market_reaction_observed": alert.score_components.get("incident_market_reaction_observed") or alert.score_components.get("market_reaction_observed"),
        "market_reaction_observed": alert.score_components.get("market_reaction_observed") or alert.score_components.get("incident_market_reaction_observed"),
        "market_reaction_confirmed": alert.score_components.get("market_reaction_confirmed"),
        "incident_causal_mechanism_confirmed": alert.score_components.get("incident_causal_mechanism_confirmed") or alert.score_components.get("causal_mechanism_confirmed"),
        "causal_mechanism_confirmed": alert.score_components.get("causal_mechanism_confirmed"),
        "incident_confidence": alert.score_components.get("incident_confidence"),
        **quality,
        "route": requested_route,
        "lane": event_alpha_router.lane_value_for_route_value(requested_route),
        "btc_regime": _btc_regime(candidate),
        "signal_type": signal.signal_type.value if signal else None,
        "fade_state": signal.state.value if signal else None,
        "reason": alert.reason,
        "verify": list(alert.verify),
        "rejected_reason": alert.rejected_reason,
        "delivered_status": None,
        "feedback_status": "pending",
    }
    core_id = alert.score_components.get("core_opportunity_id") or event_core_opportunities.core_opportunity_id_for_row(row)
    row["core_opportunity_id"] = core_id
    row["feedback_target"] = core_id or row["alert_key"]
    row["feedback_target_type"] = "core_opportunity_id" if core_id else "alert_key"
    row.update(decision_model_values(alert.score_components))
    return _with_canonical_quality_route(row)
def _state_cap_context(entry: event_watchlist.EventWatchlistEntry) -> dict[str, Any]:
    requested = event_watchlist.requested_state_value(entry)
    final = event_watchlist.final_state_value(entry)
    quality = {
        key: getattr(entry, key, None)
        for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS
        if getattr(entry, key, None) not in (None, "", [], {}, ())
    }
    if not quality:
        quality = dict(entry.latest_score_components or {})
    _, computed_block = event_watchlist.quality_cap_watchlist_state(requested, quality)
    capped = event_watchlist.state_is_quality_capped(entry)
    return {
        "state": final,
        "requested_state_before_quality_gate": requested,
        "final_state_after_quality_gate": final,
        "quality_state_block_reason": entry.quality_state_block_reason or computed_block,
        "state_quality_capped": capped,
    }
def classify_alert_snapshot(row: Mapping[str, Any]) -> str:
    """Classify snapshot route/quality consistency for reports and migrations."""
    components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    has_quality = event_alpha_quality_fields.has_any_quality_field(row, components_key="score_components")
    final_present = bool(row.get("final_route_after_quality_gate"))
    final_route, block = event_alpha_router.quality_gate_route_for_row(
        row,
        components=components,
        require_quality=has_quality,
    )
    persisted_final = str(row.get("final_route_after_quality_gate") or "")
    persisted_route = str(row.get("route") or "")
    persisted_alertable = bool(row.get("route_alertable")) or event_alpha_router.route_value_is_alertable(persisted_route)
    final_alertable = event_alpha_router.route_value_is_alertable(final_route)
    persisted_final_alertable = event_alpha_router.route_value_is_alertable(persisted_final)
    if not final_present:
        if persisted_alertable and not final_alertable:
            return SNAPSHOT_LEGACY_CONFLICT
        return SNAPSHOT_STALE_PRE_QUALITY_GATE if has_quality else SNAPSHOT_MISSING_FINAL_ROUTE
    if (persisted_alertable or persisted_final_alertable) and not final_alertable:
        return SNAPSHOT_LEGACY_CONFLICT
    if persisted_final and persisted_final != final_route and persisted_final_alertable:
        return SNAPSHOT_LEGACY_CONFLICT
    if bool(row.get("state_quality_capped")):
        return SNAPSHOT_QUALITY_GATED_LOCAL
    if block and not final_alertable:
        return SNAPSHOT_QUALITY_GATED_LOCAL
    return SNAPSHOT_CURRENT_CLEAN
def _with_snapshot_quality_classification(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["snapshot_quality_classification"] = classify_alert_snapshot(out)
    return out
