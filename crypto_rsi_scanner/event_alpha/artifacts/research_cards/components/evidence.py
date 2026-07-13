"""Evidence helpers for research cards."""

from __future__ import annotations

from .runtime import *
from ....radar.decision_model_surfaces import DECISION_MODEL_FIELD_NAMES

_CORE_SCORE_COMPONENT_KEYS = (
    "core_opportunity_id",
    "incident_id",
    "hypothesis_id",
    "validated_symbol",
    "validated_coin_id",
    "candidate_role",
    "primary_impact_path",
    "impact_path_type",
    "relationship_type",
    "impact_category",
    "impact_path_reason",
    "opportunity_level",
    "opportunity_score_final",
    "initial_opportunity_score",
    "initial_opportunity_level",
    "post_refresh_opportunity_score",
    "post_refresh_opportunity_level",
    "post_refresh_market_confirmation_level",
    "post_refresh_market_confirmation_score",
    "post_refresh_evidence_quality_score",
    "final_opportunity_score",
    "final_opportunity_level",
    "final_verdict_source",
    "final_verdict_reason",
    "market_data_freshness",
    "market_reaction_confirmation",
    "market_context_freshness_status",
    "market_context_source",
    "market_context_observed_at",
    "market_context_age_hours",
    "market_context_freshness_cap_applied",
    "market_context_data_quality",
    "market_confirmation_score",
    "market_confirmation_level",
    "market_confirmation_after",
    "market_state_snapshot",
    "source_row_type",
    "integrated_candidate_id",
    "integrated_candidate_family_id",
    "market_state",
    "market_state_class",
    "opportunity_type",
    "opportunity_type_why_now",
    "opportunity_type_evidence",
    "opportunity_type_what_confirms",
    "opportunity_type_what_invalidates",
    "opportunity_type_why_not_alertable",
    "opportunity_type_source_requirements_met",
    "opportunity_type_market_requirements_met",
    "opportunity_type_fade_requirements_met",
    "opportunity_type_source_strength",
    "opportunity_type_warnings",
    "opportunity_type_reason_codes",
    "source_strength",
    "source_requirements_met",
    "market_requirements_met",
    "fade_requirements_met",
    "why_now",
    "what_confirms",
    "what_invalidates",
    "why_not_alertable",
    "reason_codes",
    "warnings",
    "final_route_after_quality_gate",
    "final_tier_after_quality_gate",
    "final_state_after_quality_gate",
    "source_pack",
    "source_packs",
    "source_origin",
    "source_origins",
    "candidate_provenance",
    "market_provenance",
    "market_provenance_schema_version",
    "market_provenance_contract_version",
    "data_acquisition_mode",
    "candidate_source_mode",
    "provider_call_attempted",
    "provider_call_succeeded",
    "live_provider_authorized",
    "request_ledger_sha256",
    "provider_source_artifact_sha256",
    "cache_status",
    "provenance_contract_valid",
    "burn_in_eligible",
    "burn_in_counted",
    "burn_in_reason",
    "feature_basis",
    "data_quality",
    "contract_counted_candidate",
    "provider_generation_id",
    "provider_request_succeeded",
    "provider_source_artifact",
    "request_ledger_path",
    "market_refresh_artifact",
    "source_url",
    "latest_source_url",
    "latest_source_title",
    "official_exchange_event",
    "official_exchange_provider",
    "official_exchange",
    "official_exchange_event_type",
    "official_exchange_title",
    "official_exchange_url",
    "official_exchange_published_at",
    "official_exchange_effective_time",
    "official_exchange_reason_codes",
    "scheduled_catalyst_event",
    "unlock_event",
    "derivatives_state_snapshot",
    "derivatives_snapshot",
    "crowding_class",
    "fade_readiness",
    "crowding_exhaustion_evidence",
    "what_confirms_fade_review",
    "what_invalidates_fade_review",
    "derivatives_warning_codes",
    "integrated_market_confirmation_level",
    "integrated_market_confirmation_score",
    "integrated_market_reaction_confirmation",
    "integrated_market_context_source",
    "integrated_market_freshness_status",
    "evidence_acquisition_source_pack",
    "evidence_acquisition_attempted",
    "evidence_acquisition_status",
    "evidence_acquisition_results",
    "evidence_acquisition_accepted_count",
    "evidence_acquisition_rejected_count",
    "evidence_acquisition_accepted_evidence",
    "evidence_acquisition_rejected_samples",
    "accepted_evidence_reason_codes",
    "rejected_evidence_reason_codes",
    "evidence_acquisition_provider_failures",
    "final_upgrade_status",
    "no_upgrade_reason",
    "source_class",
    "evidence_specificity",
    "evidence_quality_score",
    "evidence_quality_after",
    "quality_state_block_reason",
    "feedback_target",
    "feedback_target_type",
    "main_frame_type",
    "main_frame_role",
    "main_frame_subject",
    "main_frame_actor",
    "main_frame_object",
    "main_frame_evidence_quote",
    "frame_status",
    "selected_main_catalyst_reason",
    "rule_predicted_impact_path",
    "llm_predicted_main_frame_type",
    "frame_rule_disagreement",
    "negated_frame_ids",
    "corrective_frame_ids",
    "frame_summary",
    *DECISION_MODEL_FIELD_NAMES,
)

def _find_entry(key: str, entries: list[event_watchlist.EventWatchlistEntry]) -> event_watchlist.EventWatchlistEntry | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    if clean_key.startswith("card_"):
        clean_key = clean_key[5:]
    key_l = clean_key.lower()
    matches = [
        entry for entry in entries
        if clean_key in {entry.key, entry.event_id}
        or key_l in {entry.symbol.lower(), entry.coin_id.lower()}
    ]
    return matches[0] if matches else None

def _selected_entries(
    entries: list[event_watchlist.EventWatchlistEntry],
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    include_all_alertable: bool,
    selected_tiers: Iterable[str] | None,
) -> list[event_watchlist.EventWatchlistEntry]:
    selected_by_key: dict[str, event_watchlist.EventWatchlistEntry] = {}
    all_by_key = {entry.key: entry for entry in entries}
    alert_row_list = list(alert_rows)
    stored_core_rows = [
        dict(row) for row in alert_row_list
        if isinstance(row, Mapping) and row.get("row_type") == "event_core_opportunity"
    ]
    if stored_core_rows:
        ordered: list[event_watchlist.EventWatchlistEntry] = []
        seen_core: set[str] = set()
        for opportunity in event_core_opportunities.visible_core_opportunities(stored_core_rows):
            if opportunity.core_opportunity_id in seen_core:
                continue
            ordered.append(_entry_from_core_opportunity(opportunity))
            seen_core.add(opportunity.core_opportunity_id)
        for row in stored_core_rows:
            core_id = str(row.get("core_opportunity_id") or "").strip()
            if not core_id or core_id in seen_core:
                continue
            fallback = event_core_opportunities.aggregate_core_opportunities([row])
            if not fallback:
                continue
            ordered.append(_entry_from_core_opportunity(fallback[0]))
            seen_core.add(core_id)
        if ordered:
            return ordered
    states = set(selected_tiers or {
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        "HIGH_PRIORITY_WATCH",
    })
    for entry in entries:
        if (
            event_watchlist.final_state_value(entry) in states
            or entry.latest_tier in states
        ) and (
            not event_watchlist.state_is_quality_capped(entry)
            or event_watchlist.final_state_value(entry) in {
                event_watchlist.EventWatchlistState.WATCHLIST.value,
                event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
                event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
            }
        ):
            selected_by_key[entry.key] = entry
    if include_all_alertable:
        for decision in decisions:
            if event_alpha_router.alertable_after_quality_gate(decision):
                selected_by_key[decision.entry.key] = decision.entry
    core_rows = [*decisions, *entries, *alert_row_list]
    visible_core = event_core_opportunities.visible_core_opportunities(core_rows)
    if visible_core:
        ordered: list[event_watchlist.EventWatchlistEntry] = []
        seen_core: set[str] = set()
        for opportunity in visible_core:
            if opportunity.core_opportunity_id in seen_core:
                continue
            entry = _entry_for_core_opportunity(opportunity, all_by_key)
            if entry is None:
                continue
            selected_by_key.setdefault(entry.key, entry)
            ordered.append(entry)
            seen_core.add(opportunity.core_opportunity_id)
            if len(ordered) >= max(len(visible_core), 1):
                break
        for entry in selected_by_key.values():
            if entry.key not in {item.key for item in ordered} and not event_core_opportunities.row_is_diagnostic(entry):
                ordered.append(entry)
        if ordered:
            return ordered
    if selected_by_key:
        core = event_core_opportunities.aggregate_core_opportunities([*decisions, *selected_by_key.values()])
        if core:
            ordered: list[event_watchlist.EventWatchlistEntry] = []
            for opportunity in core:
                key = str(opportunity.primary_row.get("key") or "")
                entry = selected_by_key.get(key)
                if entry is not None and entry.key not in {item.key for item in ordered}:
                    ordered.append(entry)
            for entry in selected_by_key.values():
                if entry.key not in {item.key for item in ordered} and not event_core_opportunities.row_is_diagnostic(entry):
                    ordered.append(entry)
            return ordered
    return sorted(
        selected_by_key.values(),
        key=lambda entry: (entry.last_seen_at, entry.latest_score, entry.symbol),
        reverse=True,
    )

def _entry_for_core_opportunity(
    opportunity: event_core_opportunities.CoreOpportunity,
    entries_by_key: Mapping[str, event_watchlist.EventWatchlistEntry],
) -> event_watchlist.EventWatchlistEntry | None:
    for key in event_core_opportunities.row_key_candidates_for_opportunity(opportunity):
        entry = entries_by_key.get(key)
        if entry is not None and _entry_matches_core_identity(entry, opportunity):
            return entry
    symbol = opportunity.symbol.upper()
    coin = opportunity.coin_id.casefold()
    for entry in entries_by_key.values():
        if (
            (symbol and entry.symbol.upper() == symbol)
            or (coin and entry.coin_id.casefold() == coin)
        ) and _entry_matches_core_identity(entry, opportunity):
            return entry
    return _entry_from_core_opportunity(opportunity)

def _entry_matches_core_identity(
    entry: event_watchlist.EventWatchlistEntry,
    opportunity: event_core_opportunities.CoreOpportunity,
) -> bool:
    symbol_match = bool(opportunity.symbol and entry.symbol.upper() == opportunity.symbol.upper())
    coin_match = bool(opportunity.coin_id and entry.coin_id.casefold() == opportunity.coin_id.casefold())
    if not (symbol_match or coin_match):
        return False
    if opportunity.supporting_hypothesis_ids:
        entry_hypothesis_ids = {
            str(value or "")
            for value in (
                entry.hypothesis_id,
                entry.latest_score_components.get("hypothesis_id") if isinstance(entry.latest_score_components, Mapping) else None,
            )
            if str(value or "")
        }
        if not entry_hypothesis_ids.intersection(opportunity.supporting_hypothesis_ids):
            return False
    if event_core_opportunities.row_is_diagnostic(entry):
        return opportunity.primary_impact_path in {
            "generic_cooccurrence_only",
            "insufficient_data",
            "source_noise_control",
        } or opportunity.candidate_role in {"unknown", "unknown_with_reason", "source_noise"}
    return True

def _entry_from_core_opportunity(
    opportunity: event_core_opportunities.CoreOpportunity,
) -> event_watchlist.EventWatchlistEntry:
    row = opportunity.primary_row
    observed = _first_text(row, "last_seen_at", "observed_at", "updated_at", "created_at") or datetime.now(timezone.utc).isoformat()
    final_state = (
        opportunity.final_state_after_quality_gate
        or _first_text(row, "final_state_after_quality_gate", "state")
        or event_watchlist.EventWatchlistState.RADAR.value
    )
    components = _core_score_components(opportunity)
    latest_score = int(round(_float_value(opportunity.opportunity_score_final) or _float_value(row.get("latest_score")) or _float_value(row.get("score")) or 0.0))
    return event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_card_synthetic",
        key=_first_text(row, "key", "alert_key", "watchlist_key") or opportunity.core_opportunity_id,
        cluster_id=_first_text(row, "cluster_id") or opportunity.incident_id,
        event_id=_first_text(row, "event_id", "hypothesis_id", "alert_id") or opportunity.core_opportunity_id,
        coin_id=opportunity.coin_id or _first_text(row, "coin_id", "validated_coin_id") or "unknown",
        symbol=opportunity.symbol or _first_text(row, "symbol", "validated_symbol") or "UNKNOWN",
        relationship_type=opportunity.primary_impact_path or _first_text(row, "relationship_type", "effective_playbook_type") or "event_alpha",
        external_asset=_first_text(row, "external_asset", "external_catalyst", "external_asset_name") or opportunity.canonical_incident_name,
        event_time=_first_text(row, "event_time"),
        state=final_state,
        previous_state=_first_text(row, "previous_state"),
        first_seen_at=_first_text(row, "first_seen_at") or observed,
        last_seen_at=observed,
        incident_id=opportunity.incident_id or _first_text(row, "incident_id"),
        hypothesis_id=_first_text(row, "hypothesis_id"),
        incident_canonical_name=opportunity.canonical_incident_name or _first_text(row, "incident_canonical_name"),
        requested_state_before_quality_gate=_first_text(row, "requested_state_before_quality_gate", "state"),
        final_state_after_quality_gate=final_state,
        quality_state_block_reason=_first_text(row, "quality_state_block_reason"),
        state_quality_capped=_bool_value(row.get("state_quality_capped")),
        source_count=int(_float_value(row.get("source_count")) or 0),
        highest_score=latest_score,
        latest_score=latest_score,
        latest_tier=_first_text(row, "latest_tier", "tier", "final_tier_after_quality_gate", "final_route_after_quality_gate", "route") or "",
        latest_event_name=_first_text(row, "latest_event_name", "event_name", "canonical_incident_name") or opportunity.canonical_incident_name,
        latest_source=_first_text(row, "latest_source", "source", "provider"),
        latest_playbook_type=_first_text(row, "effective_playbook_type", "playbook_type", "primary_impact_path") or opportunity.primary_impact_path,
        latest_rule_playbook_type=_first_text(row, "rule_playbook_type"),
        latest_effective_playbook_type=_first_text(row, "effective_playbook_type", "playbook_type", "primary_impact_path") or opportunity.primary_impact_path,
        latest_playbook_score=latest_score,
        latest_playbook_action=_first_text(row, "playbook_action"),
        latest_market_snapshot=_mapping_value(row.get("latest_market_snapshot")) or _mapping_value(row.get("market_snapshot")) or {},
        latest_score_components=components,
        impact_path_type=opportunity.primary_impact_path or _first_text(row, "impact_path_type"),
        impact_path_strength=_first_text(row, "impact_path_strength"),
        candidate_role=opportunity.candidate_role or _first_text(row, "candidate_role"),
        evidence_quality_score=_float_value(row.get("evidence_quality_score")),
        source_class=_first_text(row, "source_class"),
        evidence_specificity=_first_text(row, "evidence_specificity"),
        market_confirmation_score=_float_value(row.get("market_confirmation_score")),
        market_confirmation_level=_first_text(row, "market_confirmation_level"),
        market_context_freshness_status=_first_text(row, "market_context_freshness_status"),
        market_context_age_hours=row.get("market_context_age_hours"),
        market_context_stale=row.get("market_context_stale") if isinstance(row.get("market_context_stale"), bool) else None,
        market_context_freshness_cap_applied=row.get("market_context_freshness_cap_applied") if isinstance(row.get("market_context_freshness_cap_applied"), bool) else None,
        opportunity_score_final=_float_value(opportunity.opportunity_score_final) or _float_value(row.get("opportunity_score_final")),
        opportunity_level=opportunity.opportunity_level or _first_text(row, "opportunity_level"),
        opportunity_verdict_reasons=_list_value(row.get("opportunity_verdict_reasons")),
        why_local_only=_first_text(row, "why_local_only"),
        why_not_watchlist=_first_text(row, "why_not_watchlist"),
        manual_verification_items=_list_value(row.get("manual_verification_items")),
        upgrade_requirements=_list_value(row.get("upgrade_requirements")),
        downgrade_warnings=_list_value(row.get("downgrade_warnings")),
        should_alert=_bool_value(row.get("should_alert")),
        suppressed_reason=_first_text(row, "suppressed_reason"),
        warnings=tuple(_list_value(row.get("warnings"))),
    )

def _core_score_components(opportunity: event_core_opportunities.CoreOpportunity) -> dict[str, Any]:
    row = opportunity.primary_row
    components: dict[str, Any] = {}
    for key in ("latest_score_components", "score_components"):
        value = row.get(key)
        if isinstance(value, Mapping):
            components.update(value)
    for key in _CORE_SCORE_COMPONENT_KEYS:
        value = row.get(key)
        if value not in (None, "", [], {}, ()):
            components[key] = value
    components.setdefault("core_opportunity_id", opportunity.core_opportunity_id)
    components.setdefault("feedback_target", opportunity.core_opportunity_id)
    components.setdefault("feedback_target_type", "core_opportunity_id")
    components.setdefault("incident_id", opportunity.incident_id)
    components.setdefault("validated_symbol", opportunity.symbol)
    components.setdefault("validated_coin_id", opportunity.coin_id)
    components.setdefault("candidate_role", opportunity.candidate_role)
    components.setdefault("impact_path_type", opportunity.primary_impact_path)
    if opportunity.primary_impact_path and str(components.get("impact_path_type") or "").casefold() in {
        "",
        "unknown",
        "insufficient_data",
        "generic_cooccurrence_only",
    }:
        components["impact_path_type"] = opportunity.primary_impact_path
    components.setdefault("relationship_type", opportunity.primary_impact_path)
    components.setdefault("opportunity_level", opportunity.opportunity_level)
    components.setdefault("opportunity_score_final", opportunity.opportunity_score_final)
    if components.get("final_opportunity_level") not in (None, ""):
        components["opportunity_level"] = components.get("final_opportunity_level")
    if components.get("final_opportunity_score") not in (None, ""):
        components["opportunity_score_final"] = components.get("final_opportunity_score")
    components.setdefault("final_route_after_quality_gate", opportunity.final_route_after_quality_gate)
    components.setdefault("final_state_after_quality_gate", opportunity.final_state_after_quality_gate)
    return components

def _first_text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}, ()):
            return str(value)
    return None

def _mapping_value(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None

def _list_value(value: object) -> list[str]:
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return [str(item) for item in value if str(item or "")]
    return [str(value)]

def _display_list_value(value: object, *, limit: int = 6) -> str:
    items = _list_value(value)
    if not items:
        return "none"
    return "; ".join(items[:limit])

def _role_capabilities_line(value: object) -> str:
    if not isinstance(value, Mapping):
        return "unknown"
    enabled = [str(key) for key, child in sorted(value.items()) if bool(child)]
    return ", ".join(enabled) if enabled else "none"

def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)

def _card_filename(entry: event_watchlist.EventWatchlistEntry) -> str:
    base = event_alpha_router.card_id_for_entry(entry)
    return _slug(base)[:180] + ".md"

def _find_alert(key: str, rows: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    matches: list[Mapping[str, Any]] = []
    for row in rows:
        values = {
            str(row.get("alert_key") or ""),
            str(row.get("alert_id") or ""),
            str(row.get("card_id") or ""),
            str(row.get("snapshot_id") or ""),
            str(row.get("core_opportunity_id") or ""),
            str(row.get("event_id") or ""),
            str(row.get("hypothesis_id") or ""),
            str(row.get("incident_id") or ""),
            str(row.get("asset_symbol") or ""),
            str(row.get("asset_coin_id") or ""),
        }
        if clean_key in values or key_l in {value.lower() for value in values}:
            matches.append(row)
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda row: (
            str(row.get("row_type") or "") == "event_core_opportunity",
            bool(row.get("final_route_after_quality_gate")),
            _float_value(row.get("opportunity_score_final") or row.get("final_opportunity_score")) or 0.0,
        ),
        reverse=True,
    )[0]

def _find_decision(
    key: str,
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
) -> event_alpha_router.EventAlphaRouteDecision | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    for decision in decisions:
        entry = decision.entry
        if clean_key in {entry.key, entry.event_id, decision.alert_id, decision.card_id} or key_l in {
            entry.symbol.lower(),
            entry.coin_id.lower(),
        }:
            return decision
    return None

def _find_cluster(
    key: str,
    clusters: list[event_graph.EventCluster],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> event_graph.EventCluster | None:
    key_l = key.lower()
    identifiers = {
        key,
        key_l,
        str(getattr(entry, "cluster_id", "") or ""),
        str(getattr(entry, "event_id", "") or ""),
        str(alert.get("cluster_id") or "") if alert else "",
        str(alert.get("event_id") or "") if alert else "",
    }
    identifiers_l = {item.lower() for item in identifiers if item}
    for cluster in clusters:
        if cluster.cluster_id in identifiers or cluster.cluster_id.lower() in identifiers_l:
            return cluster
        if any(str(event_id).lower() in identifiers_l for event_id in cluster.event_ids):
            return cluster
        for link in cluster.asset_links:
            if key_l in {link.symbol.lower(), link.coin_id.lower()}:
                return cluster
    return None

def _find_monitor_row(
    key: str,
    rows: list[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any] | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    identifiers = {
        clean_key,
        key_l,
        str(getattr(entry, "key", "") or ""),
        str(getattr(entry, "symbol", "") or ""),
        str(getattr(entry, "coin_id", "") or ""),
        str(alert.get("alert_key") or "") if alert else "",
        str(alert.get("asset_symbol") or "") if alert else "",
        str(alert.get("asset_coin_id") or "") if alert else "",
    }
    identifiers_l = {item.lower() for item in identifiers if item}
    for row in rows:
        values = {
            str(_monitor_value(row, "key") or ""),
            str(_monitor_value(row, "symbol") or ""),
            str(_monitor_value(row, "coin_id") or ""),
        }
        if clean_key in values or key_l in {value.lower() for value in values} or identifiers_l & {
            value.lower() for value in values if value
        }:
            return row
    return None

def _matching_rows(
    key: str,
    rows: list[Mapping[str, Any]],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    del key, entry
    if not isinstance(alert, Mapping):
        return []
    exact_identity = event_feedback_eligibility.canonical_feedback_join_identity(alert)
    if exact_identity is None:
        return []
    return [
        row
        for row in rows
        if row.get("calibration_eligible") is True
        and event_feedback_eligibility.canonical_feedback_join_identity(row)
        == exact_identity
    ]

def _find_outcome(
    key: str,
    rows: list[Mapping[str, Any]],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    del entry
    exact_core = _exact_core_context(alert)
    exact_candidate = (
        event_outcome_eligibility.canonical_join_identity(alert)
        if isinstance(alert, Mapping)
        else None
    )
    matches: list[Mapping[str, Any]] = []
    if exact_candidate is not None:
        matches = [
            row
            for row in rows
            if event_outcome_eligibility.canonical_join_identity(row) == exact_candidate
        ]
    elif exact_core is not None:
        matches = [row for row in rows if _exact_core_context(row) == exact_core]
    else:
        clean_key = str(key or "").strip()
        if clean_key:
            matches = [
                row
                for row in rows
                if row.get("candidate_id") == clean_key
                or row.get("core_opportunity_id") == clean_key
            ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        reasons = sorted({
            str(reason)
            for row in matches
            for reason in row.get("calibration_ineligible_reasons") or ()
            if str(reason)
        }) or ["ambiguous_outcome_identity"]
        first = matches[0]
        return {
            "candidate_id": first.get("candidate_id"),
            "core_opportunity_id": first.get("core_opportunity_id"),
            "outcome_status": "excluded",
            "calibration_eligible": False,
            "calibration_ineligible_reasons": reasons,
        }
    return None


def _exact_core_context(row: Mapping[str, Any] | None) -> tuple[str, str, str, str] | None:
    if not isinstance(row, Mapping):
        return None
    values = tuple(
        row.get(field)
        for field in ("core_opportunity_id", "run_id", "profile", "artifact_namespace")
    )
    if not all(type(value) is str and value and value == value.strip() for value in values):
        return None
    return values  # type: ignore[return-value]

def _value(entry: Any | None, alert: Mapping[str, Any] | None, entry_field: str, alert_field: str) -> Any:
    if entry is not None and entry_field:
        value = getattr(entry, entry_field, None)
        if value not in (None, ""):
            return value
    if alert is not None:
        value = alert.get(alert_field)
        if value not in (None, ""):
            return value
        if entry_field:
            value = alert.get(entry_field)
            if value not in (None, ""):
                return value
    return None

def _canonical_card_alert(
    opportunity: event_core_opportunities.CoreOpportunity,
    alert: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = dict(alert or {})
    primary = dict(opportunity.primary_row or {})
    for key, value in primary.items():
        row.setdefault(key, value)
    row.update({
        "core_opportunity_id": opportunity.core_opportunity_id,
        "symbol": opportunity.symbol,
        "coin_id": opportunity.coin_id,
        "asset_symbol": opportunity.symbol,
        "asset_coin_id": opportunity.coin_id,
        "event_name": opportunity.canonical_incident_name or row.get("event_name") or row.get("latest_event_name"),
        "canonical_incident_name": opportunity.canonical_incident_name,
        "candidate_role": opportunity.candidate_role,
        "primary_impact_path": opportunity.primary_impact_path,
        "impact_path_type": opportunity.primary_impact_path,
        "relationship_type": opportunity.primary_impact_path,
        "playbook_type": row.get("playbook_type") or row.get("effective_playbook_type") or opportunity.primary_impact_path,
        "effective_playbook_type": row.get("effective_playbook_type") or row.get("playbook_type") or opportunity.primary_impact_path,
        "state": opportunity.final_state_after_quality_gate,
        "tier": opportunity.final_route_after_quality_gate,
        "latest_tier": opportunity.final_route_after_quality_gate,
        "route": opportunity.final_route_after_quality_gate,
        "final_route_after_quality_gate": opportunity.final_route_after_quality_gate,
        "final_tier_after_quality_gate": row.get("final_tier_after_quality_gate") or opportunity.final_route_after_quality_gate,
        "final_state_after_quality_gate": opportunity.final_state_after_quality_gate,
        "opportunity_level": opportunity.opportunity_level,
        "opportunity_score_final": opportunity.opportunity_score_final,
        "final_opportunity_level": row.get("final_opportunity_level") or opportunity.opportunity_level,
        "final_opportunity_score": row.get("final_opportunity_score") or opportunity.opportunity_score_final,
        "feedback_target": row.get("feedback_target") or opportunity.core_opportunity_id,
        "feedback_target_type": row.get("feedback_target_type") or "core_opportunity_id",
    })
    components = _core_score_components(opportunity)
    existing = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    row["score_components"] = {**dict(existing), **components}
    return row

def _cluster_lines(cluster: event_graph.EventCluster | None) -> list[str]:
    if cluster is None:
        return ["- No cluster graph data found in local artifacts."]
    accepted = [link for link in cluster.asset_links if link.accepted]
    rejected = [link for link in cluster.asset_links if not link.accepted]
    providers = sorted({evidence.source for evidence in cluster.evidence if evidence.source})
    origins = sorted({
        _origin(url)
        for evidence in cluster.evidence
        for url in evidence.source_urls
        if url
    })
    lines = [
        f"- Cluster ID: {cluster.cluster_id}",
        f"- Cluster confidence: {cluster.cluster_confidence}",
        f"- Independent sources: {cluster.independent_source_count}",
        f"- Event-time consensus: {cluster.event_time_consensus}",
        f"- Source providers: {', '.join(providers) if providers else 'unknown'}",
        f"- Source origins: {', '.join(origins) if origins else 'unknown'}",
    ]
    accepted_by_kind: dict[str, list[str]] = {}
    for link in accepted:
        accepted_by_kind.setdefault(link.accepted_kind, []).append(f"{link.symbol}/{link.coin_id}")
    if accepted_by_kind:
        lines.append(
            "- Accepted links by kind: "
            + "; ".join(
                f"{kind}={', '.join(values)}"
                for kind, values in sorted(accepted_by_kind.items())
            )
        )
    else:
        lines.append("- Accepted links by kind: none")
    if rejected:
        lines.append(
            "- Rejected/noise links: "
            + "; ".join(
                f"{link.symbol}/{link.coin_id}:{link.rejected_reason or 'rejected'}"
                for link in rejected[:8]
            )
        )
    else:
        lines.append("- Rejected/noise links: none")
    if cluster.source_urls:
        lines.append("- Top evidence URLs: " + "; ".join(cluster.source_urls[:5]))
    if cluster.warnings:
        lines.append("- Cluster warnings: " + "; ".join(cluster.warnings))
    return lines

def _origin(url: str) -> str:
    parsed = urlparse(str(url))
    return parsed.netloc or parsed.path or "unknown"

def _card_components(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> dict[str, Any]:
    components = dict(entry.latest_score_components if entry else {})
    if alert:
        alert_components = alert.get("score_components") if isinstance(alert.get("score_components"), Mapping) else {}
        latest = alert.get("latest_score_components") if isinstance(alert.get("latest_score_components"), Mapping) else {}
        components.update(dict(alert_components or {}))
        components.update(dict(latest or {}))
        components.update({key: value for key, value in alert.items() if value not in (None, "", [], {}, ())})
    if entry is not None:
        for key, value in {
            "latest_source": entry.latest_source,
            "source_count": entry.source_count,
            "symbol": entry.symbol,
            "coin_id": entry.coin_id,
            "impact_path_type": entry.impact_path_type,
            "impact_path_strength": entry.impact_path_strength,
            "candidate_role": entry.candidate_role,
            "market_confirmation_level": entry.market_confirmation_level,
            "market_confirmation_score": entry.market_confirmation_score,
            "market_context_freshness_status": entry.market_context_freshness_status,
            "market_context_age_hours": entry.market_context_age_hours,
            "opportunity_level": entry.opportunity_level,
            "opportunity_score_final": entry.opportunity_score_final,
        }.items():
            if value not in (None, "", [], {}, ()) and key not in components:
                components[key] = value
    return components

def _accepted_evidence_samples(components: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = components.get("evidence_acquisition_accepted_evidence") or components.get("accepted_evidence")
    if isinstance(raw, Mapping):
        return [raw]
    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
        return [item for item in raw if isinstance(item, Mapping)]
    return []

def _first_accepted_evidence_sample(components: Mapping[str, Any]) -> Mapping[str, Any]:
    samples = _accepted_evidence_samples(components)
    return samples[0] if samples else {}

def _int_value(value: object) -> int | None:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

def _is_promoted_components(components: Mapping[str, Any]) -> bool:
    level = str(components.get("final_opportunity_level") or components.get("opportunity_level") or "").casefold()
    route = str(components.get("final_route_after_quality_gate") or components.get("route") or "").upper()
    return level in {"validated_digest", "watchlist", "high_priority"} or event_alpha_router.route_value_is_alertable(route)

def _canonical_reason_from_components(components: Mapping[str, Any]) -> str | None:
    path = str(components.get("impact_path_type") or components.get("primary_impact_path") or "").strip()
    pack = str(components.get("source_pack") or components.get("evidence_acquisition_source_pack") or "").strip()
    if path in {"proxy_attention", "proxy_exposure", "venue_value_capture"} or pack == "proxy_preipo_rwa_pack":
        return "venue_value_capture"
    if path == "strategic_investment_or_valuation" or pack == "strategic_investment_pack":
        return "strategic_investment"
    if path == "market_dislocation_unknown":
        return "cause_unknown_market_dislocation"
    return path or None

def _canonical_strength_from_components(components: Mapping[str, Any]) -> str | None:
    level = str(components.get("final_opportunity_level") or components.get("opportunity_level") or "").casefold()
    path = str(components.get("impact_path_type") or components.get("primary_impact_path") or "").casefold()
    if path in {"", "insufficient_data", "generic_cooccurrence_only"}:
        return None
    if level in {"high_priority", "watchlist"}:
        return "strong"
    if level == "validated_digest":
        return "medium"
    return None

def _canonical_market_summary_from_components(components: Mapping[str, Any]) -> str | None:
    level = components.get("market_confirmation_level") or components.get("market_reaction_confirmation")
    score = components.get("market_confirmation_score")
    freshness = components.get("market_data_freshness") or components.get("market_context_freshness_status")
    source = components.get("market_context_source")
    if not any(value not in (None, "", [], {}, ()) for value in (level, score, freshness, source)):
        return None
    parts = []
    if level or score is not None:
        parts.append(f"{level or 'not available'} / {score if score is not None else 'n/a'}")
    if freshness or source:
        parts.append(f"freshness={freshness or 'not available'} source={source or 'not available'}")
    return "; ".join(parts)

__all__ = (
    '_find_entry',
    '_selected_entries',
    '_entry_for_core_opportunity',
    '_entry_matches_core_identity',
    '_entry_from_core_opportunity',
    '_core_score_components',
    '_first_text',
    '_mapping_value',
    '_list_value',
    '_display_list_value',
    '_role_capabilities_line',
    '_bool_value',
    '_card_filename',
    '_find_alert',
    '_find_decision',
    '_find_cluster',
    '_find_monitor_row',
    '_matching_rows',
    '_find_outcome',
    '_exact_core_context',
    '_value',
    '_canonical_card_alert',
    '_cluster_lines',
    '_origin',
    '_card_components',
    '_accepted_evidence_samples',
    '_first_accepted_evidence_sample',
    '_int_value',
    '_is_promoted_components',
    '_canonical_reason_from_components',
    '_canonical_strength_from_components',
    '_canonical_market_summary_from_components',
)
