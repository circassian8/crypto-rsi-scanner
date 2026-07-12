"""Core opportunity row serialization helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import (
    config,
)
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ...artifacts import paths as event_artifact_paths
from .. import core_opportunities as event_core_opportunities
from ..decision_model_surfaces import decision_model_values
from .. import market_reaction as event_market_reaction
from .. import opportunity_verdict as event_opportunity_verdict
from .models import *  # noqa: F403 - split modules share historical model names


def _row_from_core_opportunity(
    item: event_core_opportunities.CoreOpportunity,
    *,
    generated_at: str,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
    card_path: str | Path | None = None,
) -> dict[str, Any]:
    context = _core_row_serialization_context(
        item,
        generated_at=generated_at,
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        card_path=card_path,
    )
    row: dict[str, Any] = {}
    for section in (
        _core_row_identity_source_fields,
        _core_row_opportunity_market_fields,
        _core_row_frame_evidence_fields,
        _core_row_verdict_fields,
    ):
        row.update(section(context))
    row.update(decision_model_values(*context["all_rows"]))
    if card_path and event_artifact_paths.has_operator_absolute_path(card_path):
        row["card_path_abs_debug"] = str(card_path)
        row["research_card_path_abs_debug"] = str(card_path)
    return _apply_integrated_candidate_truth(
        row,
        primary=context["primary"],
        all_rows=context["all_rows"],
        reaction=context["reaction"],
    )


def _core_row_serialization_context(
    item: event_core_opportunities.CoreOpportunity,
    *,
    generated_at: str,
    run_id: str | None,
    profile: str | None,
    run_mode: str | None,
    artifact_namespace: str | None,
    card_path: str | Path | None,
) -> dict[str, Any]:
    primary = dict(item.primary_row)
    support = [dict(row) for row in item.supporting_rows]
    diagnostics = [dict(row) for row in item.diagnostic_rows]
    all_rows = [primary, *support, *diagnostics]
    context: dict[str, Any] = {
        "item": item,
        "generated_at": generated_at,
        "run_id": run_id,
        "profile": profile,
        "run_mode": run_mode,
        "artifact_namespace": artifact_namespace,
        "card_path": card_path,
        "primary": primary,
        "support": support,
        "diagnostics": diagnostics,
        "all_rows": all_rows,
        "support_ids": _row_ids(support),
        "diagnostic_ids": _row_ids(diagnostics),
        "diagnostic_row_count": max(
            item.diagnostic_row_count,
            _int_or_zero(primary.get("diagnostic_row_count") or primary.get("hidden_diagnostic_count")),
        ),
        "source_noise_control_count": max(
            item.source_noise_control_count,
            _int_or_zero(primary.get("source_noise_control_count")),
        ),
    }
    context.update(_core_row_initial_metrics(item, all_rows))
    context.update(_core_row_acquisition_metrics(item, all_rows, context))
    context.update(_core_row_policy_context(item, primary, all_rows, context))
    context.update(_core_row_event_source_context(all_rows, context))
    return context


def _core_row_initial_metrics(
    item: event_core_opportunities.CoreOpportunity,
    all_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    market_before = _best_float(all_rows, ("market_confirmation_before", "market_confirmation_score_before"))
    market_after = _best_float(all_rows, ("market_confirmation_after", "market_confirmation_score_after", "market_confirmation_score"))
    evidence_before = _best_float(all_rows, ("evidence_quality_before", "evidence_quality_score_before"))
    evidence_after = _best_float(all_rows, ("evidence_quality_after", "evidence_quality_score_after", "evidence_quality_score"))
    source_pack = _best_source_pack(all_rows, item.primary_impact_path)
    source_class = _first_text(all_rows, ("source_class",))
    evidence_specificity = _first_text(all_rows, ("evidence_specificity",))
    evidence_score = evidence_after if evidence_after is not None else _first_float(all_rows, ("evidence_quality_score",))
    market_level = _first_text(all_rows, ("market_confirmation_level", "market_reaction_confirmation", "post_refresh_market_confirmation_level"))
    impact_path_reason = (
        _first_text(all_rows, ("impact_path_reason",))
        or _canonical_impact_path_reason(item.primary_impact_path, source_pack)
    )
    impact_path_strength = (
        _first_text(all_rows, ("impact_path_strength",))
        or _canonical_impact_path_strength(item.opportunity_level, item.primary_impact_path, evidence_score, market_after)
    )
    initial_level = _first_text(all_rows, ("initial_opportunity_level", "opportunity_level_before", "opportunity_level_pre_refresh")) or item.opportunity_level
    initial_score = _first_float(all_rows, ("initial_opportunity_score", "opportunity_score_before", "opportunity_score_pre_refresh"))
    post_level = _first_text(all_rows, ("post_refresh_opportunity_level", "refreshed_opportunity_level", "opportunity_level_after_market_refresh")) or item.opportunity_level
    post_score = _first_float(all_rows, ("post_refresh_opportunity_score", "refreshed_opportunity_score", "opportunity_score_after_market_refresh"))
    market_context = _best_market_context(all_rows)
    derivatives_confirmation = _best_confirmation_context(
        all_rows,
        score_keys=("derivatives_confirmation_score",),
        level_keys=("derivatives_confirmation_level",),
        reasons_keys=("derivatives_confirmation_reasons",),
        freshness_keys=("derivatives_freshness_status",),
    )
    dex_liquidity_confirmation = _best_confirmation_context(
        all_rows,
        score_keys=("dex_liquidity_score",),
        level_keys=("dex_liquidity_level",),
        reasons_keys=("dex_liquidity_reasons",),
        freshness_keys=("dex_freshness_status",),
    )
    protocol_metrics_confirmation = _best_confirmation_context(
        all_rows,
        score_keys=("protocol_metrics_score",),
        level_keys=("protocol_metrics_level",),
        reasons_keys=("protocol_metrics_reasons",),
        freshness_keys=("protocol_metrics_freshness_status",),
    )
    return {
        "market_before": market_before,
        "market_after": market_after,
        "evidence_before": evidence_before,
        "evidence_after": evidence_after,
        "source_pack": source_pack,
        "source_class": source_class,
        "evidence_specificity": evidence_specificity,
        "evidence_score": evidence_score,
        "market_level": market_level,
        "impact_path_reason": impact_path_reason,
        "impact_path_strength": impact_path_strength,
        "initial_level": initial_level,
        "initial_score": initial_score,
        "post_level": post_level,
        "post_score": post_score,
        "market_context": market_context,
        "derivatives_confirmation": derivatives_confirmation,
        "dex_liquidity_confirmation": dex_liquidity_confirmation,
        "protocol_metrics_confirmation": protocol_metrics_confirmation,
    }


def _core_row_acquisition_metrics(
    item: event_core_opportunities.CoreOpportunity,
    all_rows: list[Mapping[str, Any]],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    source_pack = context["source_pack"]
    evidence_before = context["evidence_before"]
    evidence_after = context["evidence_after"]
    evidence_score = context["evidence_score"]
    market_after = context["market_after"]
    market_level = context["market_level"]
    impact_path_reason = context["impact_path_reason"]
    impact_path_strength = context["impact_path_strength"]
    initial_level = context["initial_level"]
    initial_score = context["initial_score"]
    post_level = context["post_level"]
    post_score = context["post_score"]
    market_context = context["market_context"]
    acquisition = _build_core_evidence_acquisition_view(item.core_opportunity_id, all_rows)
    source_pack = acquisition.source_pack or source_pack
    evidence_before = acquisition.evidence_quality_before if acquisition.evidence_quality_before is not None else evidence_before
    evidence_after = acquisition.evidence_quality_after if acquisition.evidence_quality_after is not None else evidence_after
    evidence_score = evidence_after if evidence_after is not None else evidence_score
    if str(market_level or "").casefold() in {"", "unknown", "missing", "none", "insufficient_data"} and market_after is not None:
        market_level = _market_level_from_score(market_after)
    impact_path_reason = impact_path_reason or _canonical_impact_path_reason(item.primary_impact_path, source_pack)
    if str(impact_path_strength or "").casefold() in {"", "unknown", "missing", "none", "insufficient_data"} and str(item.primary_impact_path or "").casefold() not in {"", "unknown", "missing", "none", "insufficient_data", "generic_cooccurrence_only"}:
        impact_path_strength = _canonical_impact_path_strength(item.opportunity_level, item.primary_impact_path, evidence_score, market_after)
    initial_level = acquisition.opportunity_level_before or initial_level
    initial_score = acquisition.opportunity_score_before if acquisition.opportunity_score_before is not None else initial_score
    post_level = acquisition.opportunity_level_after or post_level
    post_score = acquisition.opportunity_score_after if acquisition.opportunity_score_after is not None else post_score
    accepted_source = _accepted_evidence_source_summary(acquisition.accepted_evidence_samples)
    latest_source = _first_real_text(all_rows, ("latest_source", "source", "source_provider", "provider")) or accepted_source.get("provider")
    source_count = _canonical_source_count(all_rows, acquisition)
    market_summary = _canonical_market_summary(
        market_level=market_level,
        market_score=market_after,
        market_context=market_context,
    )
    market_snapshot = _best_market_snapshot(all_rows)
    if not market_snapshot and market_after is not None:
        market_snapshot = {
            "market_confirmation_level": market_level,
            "market_confirmation_score": market_after,
            "market_context_source": market_context.get("market_context_source"),
            "market_context_freshness_status": market_context.get("market_context_freshness_status"),
            "market_context_age_hours": market_context.get("market_context_age_hours"),
            "summary_only": True,
        }
    return {
        "acquisition": acquisition,
        "source_pack": source_pack,
        "evidence_before": evidence_before,
        "evidence_after": evidence_after,
        "evidence_score": evidence_score,
        "market_level": market_level,
        "impact_path_reason": impact_path_reason,
        "impact_path_strength": impact_path_strength,
        "initial_level": initial_level,
        "initial_score": initial_score,
        "post_level": post_level,
        "post_score": post_score,
        "accepted_source": accepted_source,
        "latest_source": latest_source,
        "source_count": source_count,
        "market_summary": market_summary,
        "market_snapshot": market_snapshot,
    }


def _core_row_policy_context(
    item: event_core_opportunities.CoreOpportunity,
    primary: Mapping[str, Any],
    all_rows: list[Mapping[str, Any]],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    profile = context["profile"]
    run_mode = context["run_mode"]
    artifact_namespace = context["artifact_namespace"]
    source_class = context["source_class"]
    evidence_specificity = context["evidence_specificity"]
    evidence_score = context["evidence_score"]
    market_after = context["market_after"]
    market_level = context["market_level"]
    market_context = context["market_context"]
    market_snapshot = context["market_snapshot"]
    source_pack = context["source_pack"]
    acquisition = context["acquisition"]
    accepted_source = context["accepted_source"]
    impact_path_reason = context["impact_path_reason"]
    live_policy_input = {
        **primary,
        "profile": profile or primary.get("profile"),
        "run_mode": run_mode or primary.get("run_mode"),
        "artifact_namespace": artifact_namespace or primary.get("artifact_namespace"),
        "symbol": item.symbol,
        "coin_id": item.coin_id,
        "candidate_role": item.candidate_role,
        "impact_path_type": item.primary_impact_path,
        "primary_impact_path": item.primary_impact_path,
        "opportunity_level": item.opportunity_level,
        "final_opportunity_level": item.opportunity_level,
        "opportunity_score_final": item.opportunity_score_final,
        "final_opportunity_score": item.opportunity_score_final,
        "source_class": source_class,
        "evidence_specificity": evidence_specificity,
        "evidence_quality_score": evidence_score,
        "market_confirmation_score": market_after,
        "market_confirmation_level": market_level,
        "market_context_freshness_status": market_context.get("market_context_freshness_status"),
        "canonical_incident_name": item.canonical_incident_name,
        "incident_canonical_name": item.canonical_incident_name,
        "latest_event_name": _first_text(all_rows, ("latest_event_name", "event_name", "canonical_incident_name")),
        "event_name": _first_text(all_rows, ("event_name", "latest_event_name", "canonical_incident_name")),
        "latest_source_title": accepted_source.get("title") or _first_text(all_rows, ("latest_source_title", "source_title", "title")),
        "source_title": accepted_source.get("title") or _first_text(all_rows, ("source_title", "latest_source_title", "title")),
        "supporting_categories": list(item.supporting_categories),
        "supporting_impact_paths": list(item.supporting_impact_paths),
        "diagnostic_row_count": context["diagnostic_row_count"],
        "source_noise_control_count": context["source_noise_control_count"],
        "playbook_type": item.primary_impact_path,
        "effective_playbook_type": item.primary_impact_path,
        "impact_path_reason": impact_path_reason,
        "evidence_acquisition_status": acquisition.acquisition_status,
        "evidence_acquisition_accepted_count": acquisition.accepted_evidence_count,
        "evidence_acquisition_rejected_count": acquisition.rejected_evidence_count,
        "accepted_evidence_count": acquisition.accepted_evidence_count,
        "rejected_evidence_count": acquisition.rejected_evidence_count,
        "accepted_evidence_reason_codes": list(acquisition.accepted_reason_codes),
        "accepted_provider_counts": dict(acquisition.accepted_provider_counts or {}),
        "rejected_provider_counts": dict(acquisition.rejected_provider_counts or {}),
        "accepted_reason_code_counts": dict(acquisition.accepted_reason_code_counts or {}),
        "source_pack": source_pack,
    }
    live_policy = event_opportunity_verdict.apply_live_confirmation_policy(
        live_policy_input,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        allow_sector_digest=bool(config.EVENT_ALPHA_ALLOW_SECTOR_DIGEST),
        allow_source_only_narrative_digest=bool(config.EVENT_ALPHA_ALLOW_SOURCE_ONLY_NARRATIVE_DIGEST),
    )
    final_level = live_policy.capped_level or item.opportunity_level
    final_score = live_policy.capped_score if live_policy.capped_score is not None else item.opportunity_score_final
    final_state = _canonical_core_state(item, final_level, live_policy)
    final_route, route_adjustment_reason = _canonical_core_route(item, primary, final_level=final_level)
    final_verdict_reason = (
        _first_text(all_rows, ("final_verdict_reason", "quality_gate_block_reason", "route_reason", "opportunity_verdict_reason"))
        or _default_core_verdict_reason(item.opportunity_level)
    )
    if live_policy.required and not live_policy.confirmed and live_policy.reason:
        final_verdict_reason = (
            f"Live confirmation gate capped {item.opportunity_level} to {final_level}: "
            f"{live_policy.reason}."
        )
    if route_adjustment_reason and not (live_policy.required and not live_policy.confirmed):
        final_verdict_reason = _canonical_route_adjusted_verdict_reason(final_level)
    acquisition_confirmation = event_opportunity_verdict.classify_acquisition_confirmation(live_policy_input)
    reaction = event_market_reaction.evaluate_market_reaction({
        **live_policy_input,
        "market_snapshot": market_snapshot,
        "market_confirmation_level": market_level,
        "market_confirmation_score": market_after,
        "market_context_freshness_status": market_context.get("market_context_freshness_status"),
    })
    return {
        "live_policy_input": live_policy_input,
        "live_policy": live_policy,
        "final_level": final_level,
        "final_score": final_score,
        "final_state": final_state,
        "final_route": final_route,
        "route_adjustment_reason": route_adjustment_reason,
        "final_verdict_reason": final_verdict_reason,
        "acquisition_confirmation": acquisition_confirmation,
        "reaction": reaction,
    }


def _core_row_event_source_context(
    all_rows: list[Mapping[str, Any]],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    accepted_source = context["accepted_source"]
    latest_source = context["latest_source"]
    official_event = _first_mapping(all_rows, ("official_exchange_event",))
    scheduled_event = _first_mapping(all_rows, ("scheduled_catalyst_event",))
    unlock_event = _first_mapping(all_rows, ("unlock_event",))
    derivatives_state_snapshot = _first_mapping(all_rows, ("derivatives_state_snapshot", "derivatives_snapshot"))
    crowding_class = _first_text(all_rows, ("crowding_class",))
    fade_readiness = _first_text(all_rows, ("fade_readiness",))
    crowding_exhaustion_evidence = _first_list(all_rows, ("crowding_exhaustion_evidence",))
    what_confirms_fade_review = _first_list(all_rows, ("what_confirms_fade_review",))
    what_invalidates_fade_review = _first_list(all_rows, ("what_invalidates_fade_review",))
    derivatives_warning_codes = list(dict.fromkeys((
        *_first_list(all_rows, ("derivatives_warning_codes",)),
        *_first_list(all_rows, ("warnings",)),
    )))
    latest_source_url = (
        accepted_source.get("source_url")
        or _first_text(all_rows, ("latest_source_url", "source_url", "official_exchange_url"))
        or _mapping_text(official_event, ("source_url", "url"))
        or _mapping_text(scheduled_event, ("source_url", "url"))
        or _mapping_text(unlock_event, ("source_url", "url"))
    )
    latest_source_title = (
        accepted_source.get("title")
        or _first_text(all_rows, ("latest_source_title", "source_title", "title", "event_name"))
        or _mapping_text(official_event, ("title", "event_name"))
        or _mapping_text(scheduled_event, ("title", "event_name"))
        or _mapping_text(unlock_event, ("title", "event_name"))
    )
    latest_source_provider = (
        accepted_source.get("provider")
        or latest_source
        or _mapping_text(official_event, ("provider", "exchange"))
        or _mapping_text(scheduled_event, ("provider", "source_class"))
        or _mapping_text(unlock_event, ("provider", "source_class"))
    )
    return {
        "official_event": official_event,
        "scheduled_event": scheduled_event,
        "unlock_event": unlock_event,
        "derivatives_state_snapshot": derivatives_state_snapshot,
        "crowding_class": crowding_class,
        "fade_readiness": fade_readiness,
        "crowding_exhaustion_evidence": crowding_exhaustion_evidence,
        "what_confirms_fade_review": what_confirms_fade_review,
        "what_invalidates_fade_review": what_invalidates_fade_review,
        "derivatives_warning_codes": derivatives_warning_codes,
        "latest_source_url": latest_source_url,
        "latest_source_title": latest_source_title,
        "latest_source_provider": latest_source_provider,
    }


def _core_row_identity_source_fields(context: Mapping[str, Any]) -> dict[str, Any]:
    item = context["item"]
    all_rows = context["all_rows"]
    primary = context["primary"]
    official_event = context["official_event"]
    scheduled_event = context["scheduled_event"]
    unlock_event = context["unlock_event"]
    return {
        "schema_id": "core_opportunity_v1",
        "schema_version": EVENT_CORE_OPPORTUNITY_STORE_SCHEMA_VERSION,
        "row_type": "event_core_opportunity",
        "run_id": context["run_id"],
        "profile": context["profile"],
        "run_mode": context["run_mode"],
        "artifact_namespace": context["artifact_namespace"],
        "core_opportunity_id": item.core_opportunity_id,
        "symbol": item.symbol,
        "coin_id": item.coin_id,
        "incident_id": item.incident_id,
        "canonical_incident_name": item.canonical_incident_name,
        "candidate_role": item.candidate_role,
        "primary_impact_path": item.primary_impact_path,
        "impact_path_type": item.primary_impact_path,
        "relationship_type": item.primary_impact_path,
        "playbook_type": item.primary_impact_path,
        "effective_playbook_type": item.primary_impact_path,
        "latest_playbook_type": item.primary_impact_path,
        "state": context["final_state"],
        "tier": context["final_route"],
        "latest_tier": context["final_route"],
        "route": context["final_route"],
        "primary_hypothesis_id": _first_text([primary], ("hypothesis_id", "primary_hypothesis_id")),
        "supporting_hypothesis_ids": list(item.supporting_hypothesis_ids),
        "supporting_categories": list(item.supporting_categories),
        "supporting_impact_paths": list(item.supporting_impact_paths),
        "supporting_evidence_quotes": list(item.supporting_evidence_quotes),
        "evidence_quotes": list(item.supporting_evidence_quotes),
        "source_count": context["source_count"],
        "latest_source": context["latest_source"],
        "latest_source_url": context["latest_source_url"],
        "latest_source_title": context["latest_source_title"],
        "source_provider": context["latest_source_provider"],
        "source_url": context["latest_source_url"],
        "official_exchange_event": official_event,
        "official_exchange_provider": _mapping_text(official_event, ("provider",)),
        "official_exchange": _mapping_text(official_event, ("exchange",)),
        "official_exchange_event_type": _mapping_text(official_event, ("event_type",)),
        "official_exchange_title": _mapping_text(official_event, ("title", "event_name")),
        "official_exchange_url": _mapping_text(official_event, ("source_url", "url")),
        "official_exchange_published_at": _mapping_text(official_event, ("published_at",)),
        "official_exchange_effective_time": _mapping_text(official_event, ("effective_time",)),
        "official_exchange_reason_codes": _mapping_list(official_event, ("reason_codes",)),
        "scheduled_catalyst_event": scheduled_event,
        "unlock_event": unlock_event,
        "derivatives_state_snapshot": context["derivatives_state_snapshot"],
        "crowding_class": context["crowding_class"],
        "fade_readiness": context["fade_readiness"],
        "crowding_exhaustion_evidence": context["crowding_exhaustion_evidence"],
        "what_confirms_fade_review": context["what_confirms_fade_review"],
        "what_invalidates_fade_review": context["what_invalidates_fade_review"],
        "derivatives_warning_codes": context["derivatives_warning_codes"],
        "supporting_row_ids": context["support_ids"],
        "diagnostic_row_ids": context["diagnostic_ids"],
        "diagnostic_row_count": context["diagnostic_row_count"],
        "hidden_diagnostic_count": context["diagnostic_row_count"],
        "source_noise_control_count": context["source_noise_control_count"],
        "quality_capped_support_count": item.quality_capped_supporting_rows,
        "initial_opportunity_level": context["initial_level"],
        "initial_opportunity_score": (
            context["initial_score"] if context["initial_score"] is not None else item.opportunity_score_final
        ),
        "market_refresh_attempted": _any_truthy(all_rows, ("market_refresh_attempted", "targeted_market_refresh_attempted")),
        "market_refresh_success": _any_truthy(all_rows, ("market_refresh_success", "targeted_market_refresh_success")),
        "market_refresh_status": _first_text(all_rows, ("market_refresh_status",)),
        "market_refresh_provider": _first_text(all_rows, ("market_refresh_provider",)),
        "market_refresh_observed_at": _first_text(all_rows, ("market_refresh_observed_at",)),
        "market_refresh_artifact": _first_text(all_rows, ("market_refresh_artifact",)),
        "targeted_market_refresh_id": _first_text(all_rows, ("targeted_market_refresh_id",)),
        "targeted_market_refresh_ledger_path": _first_text(all_rows, ("targeted_market_refresh_ledger_path",)),
        "provider_generation_id": _first_text(all_rows, ("provider_generation_id",)),
        "provider_request_succeeded": _any_truthy(all_rows, ("provider_request_succeeded",)),
        "provider_source_artifact": _first_text(all_rows, ("provider_source_artifact",)),
        "request_ledger_path": _first_text(all_rows, ("request_ledger_path",)),
        "candidate_provenance": _first_text(all_rows, ("candidate_provenance",)),
        "candidate_source_mode": _first_text(all_rows, ("candidate_source_mode",)),
        "contract_counted_candidate": _any_truthy(all_rows, ("contract_counted_candidate",)),
    }


def _core_row_opportunity_market_fields(context: Mapping[str, Any]) -> dict[str, Any]:
    all_rows = context["all_rows"]
    reaction = context["reaction"]
    market_context = context["market_context"]
    derivatives_confirmation = context["derivatives_confirmation"]
    dex_liquidity_confirmation = context["dex_liquidity_confirmation"]
    protocol_metrics_confirmation = context["protocol_metrics_confirmation"]
    return {
        "market_snapshot": context["market_snapshot"],
        "latest_market_snapshot": context["market_snapshot"],
        "market_state_snapshot": reaction.market_state_snapshot.to_dict(),
        "market_state": reaction.market_state,
        "market_state_class": reaction.market_state,
        "opportunity_type": reaction.opportunity_type,
        "opportunity_type_why_now": reaction.why_now,
        "opportunity_type_evidence": list(reaction.evidence_summary),
        "opportunity_type_what_confirms": list(reaction.what_confirms),
        "opportunity_type_what_invalidates": list(reaction.what_invalidates),
        "opportunity_type_why_not_alertable": list(reaction.why_not_alertable),
        "opportunity_type_source_requirements_met": reaction.source_requirements_met,
        "opportunity_type_market_requirements_met": reaction.market_requirements_met,
        "opportunity_type_fade_requirements_met": reaction.fade_requirements_met,
        "opportunity_type_source_strength": reaction.source_strength,
        "opportunity_type_warnings": list(reaction.warnings),
        "opportunity_type_reason_codes": list(reaction.reason_codes),
        "source_strength": reaction.source_strength,
        "source_requirements_met": reaction.source_requirements_met,
        "market_requirements_met": reaction.market_requirements_met,
        "fade_requirements_met": reaction.fade_requirements_met,
        "why_now": reaction.why_now,
        "what_confirms": list(reaction.what_confirms),
        "what_invalidates": list(reaction.what_invalidates),
        "why_not_alertable": list(reaction.why_not_alertable),
        "opportunity_type_warnings_compact": list(reaction.warnings),
        "market_context_freshness_status": market_context.get("market_context_freshness_status"),
        "market_context_source": market_context.get("market_context_source"),
        "market_context_observed_at": market_context.get("market_context_observed_at"),
        "market_context_age_hours": market_context.get("market_context_age_hours"),
        "market_context_freshness_cap_applied": bool(market_context.get("market_context_freshness_cap_applied")),
        "market_context_data_quality": market_context.get("market_context_data_quality"),
        "integrated_market_confirmation_level": _first_text(all_rows, ("integrated_market_confirmation_level",)),
        "integrated_market_confirmation_score": _first_float(all_rows, ("integrated_market_confirmation_score",)),
        "integrated_market_reaction_confirmation": _first_text(all_rows, ("integrated_market_reaction_confirmation",)),
        "integrated_market_context_source": _first_text(all_rows, ("integrated_market_context_source",)),
        "integrated_market_freshness_status": _first_text(all_rows, ("integrated_market_freshness_status",)),
        "market_confirmation_score": context["market_after"],
        "market_confirmation_level": context["market_level"],
        "market_confirmation_summary": context["market_summary"],
        "derivatives_confirmation_score": derivatives_confirmation.get("score"),
        "derivatives_confirmation_level": derivatives_confirmation.get("level"),
        "derivatives_confirmation_reasons": list(derivatives_confirmation.get("reasons") or ()),
        "derivatives_freshness_status": derivatives_confirmation.get("freshness_status"),
        "dex_liquidity_score": dex_liquidity_confirmation.get("score"),
        "dex_liquidity_level": dex_liquidity_confirmation.get("level"),
        "dex_liquidity_reasons": list(dex_liquidity_confirmation.get("reasons") or ()),
        "dex_freshness_status": dex_liquidity_confirmation.get("freshness_status"),
        "protocol_metrics_score": protocol_metrics_confirmation.get("score"),
        "protocol_metrics_level": protocol_metrics_confirmation.get("level"),
        "protocol_metrics_reasons": list(protocol_metrics_confirmation.get("reasons") or ()),
        "protocol_metrics_freshness_status": protocol_metrics_confirmation.get("freshness_status"),
        "market_data_freshness": market_context.get("market_context_freshness_status"),
        "market_reaction_confirmation": context["market_level"],
        "market_confirmation_before": context["market_before"],
        "market_confirmation_after": context["market_after"],
    }


def _core_row_frame_evidence_fields(context: Mapping[str, Any]) -> dict[str, Any]:
    all_rows = context["all_rows"]
    acquisition = context["acquisition"]
    source_pack = context["source_pack"]
    return {
        "main_frame_type": _first_text(all_rows, ("main_frame_type",)),
        "main_frame_role": _first_text(all_rows, ("main_frame_role",)),
        "main_frame_subject": _first_text(all_rows, ("main_frame_subject",)),
        "main_frame_actor": _first_text(all_rows, ("main_frame_actor",)),
        "main_frame_object": _first_text(all_rows, ("main_frame_object",)),
        "main_frame_evidence_quote": _first_text(all_rows, ("main_frame_evidence_quote",)),
        "frame_status": _first_text(all_rows, ("frame_status", "catalyst_frame_status")),
        "selected_main_catalyst_reason": _first_text(all_rows, ("selected_main_catalyst_reason",)),
        "rule_predicted_impact_path": _first_text(all_rows, ("rule_predicted_impact_path",)),
        "llm_predicted_main_frame_type": _first_text(all_rows, ("llm_predicted_main_frame_type",)),
        "frame_rule_disagreement": _first_value(all_rows, ("frame_rule_disagreement",)),
        "negated_frame_ids": _first_list(all_rows, ("negated_frame_ids",)),
        "corrective_frame_ids": _first_list(all_rows, ("corrective_frame_ids",)),
        "frame_summary": _first_list(all_rows, ("frame_summary",)),
        "evidence_acquisition_attempted": acquisition.acquisition_attempted or _any_truthy(all_rows, ("evidence_acquisition_attempted", "source_acquisition_attempted")),
        "evidence_acquisition_status": acquisition.acquisition_status or _first_text(all_rows, ("evidence_acquisition_status", "acquisition_status", "source_acquisition_status")),
        "evidence_acquisition_source_pack": source_pack,
        "source_pack": source_pack,
        "evidence_acquisition_accepted_count": acquisition.accepted_evidence_count,
        "evidence_acquisition_rejected_count": acquisition.rejected_evidence_count,
        "accepted_evidence_count": acquisition.accepted_evidence_count,
        "rejected_evidence_count": acquisition.rejected_evidence_count,
        "accepted_provider_counts": dict(acquisition.accepted_provider_counts or {}),
        "rejected_provider_counts": dict(acquisition.rejected_provider_counts or {}),
        "accepted_reason_code_counts": dict(acquisition.accepted_reason_code_counts or {}),
        "evidence_acquisition_accepted_evidence": list(acquisition.accepted_evidence_samples),
        "evidence_acquisition_rejected_samples": list(acquisition.rejected_evidence_samples),
        "accepted_evidence_reason_codes": list(acquisition.accepted_reason_codes),
        "rejected_evidence_reason_codes": list(acquisition.rejected_reason_codes),
        "evidence_acquisition_provider_failures": list(acquisition.provider_failures),
        "evidence_acquisition_results": {
            **acquisition.to_metadata(),
            "acquisition_evidence_status": _first_text(all_rows, ("acquisition_evidence_status",)),
        },
        "final_upgrade_status": acquisition.final_upgrade_status or _first_text(all_rows, ("final_upgrade_status", "acquisition_upgrade_status")),
        "no_upgrade_reason": acquisition.no_upgrade_reason or _first_text(all_rows, ("no_upgrade_reason",)),
    }


def _core_row_verdict_fields(context: Mapping[str, Any]) -> dict[str, Any]:
    item = context["item"]
    final_level = context["final_level"]
    live_policy = context["live_policy"]
    acquisition_confirmation = context["acquisition_confirmation"]
    card_path = context["card_path"]
    return {
        "source_class": context["source_class"],
        "evidence_specificity": context["evidence_specificity"],
        "evidence_quality_score": context["evidence_score"],
        "evidence_quality_before": context["evidence_before"],
        "evidence_quality_after": context["evidence_after"],
        "impact_path_strength": context["impact_path_strength"],
        "impact_path_reason": context["impact_path_reason"],
        "digest_eligible_by_impact_path": final_level in {"validated_digest", "watchlist", "high_priority"},
        "manual_verification_items": _canonical_manual_verification_items(
            item,
            context["source_pack"],
            final_level=final_level,
            live_policy=live_policy,
        ),
        "upgrade_requirements": _canonical_upgrade_requirements(final_level, live_policy=live_policy),
        "downgrade_warnings": _canonical_downgrade_warnings(item.primary_impact_path, final_level),
        "post_refresh_opportunity_level": context["post_level"],
        "post_refresh_opportunity_score": (
            context["post_score"] if context["post_score"] is not None else item.opportunity_score_final
        ),
        "requested_opportunity_level_before_live_confirmation": item.opportunity_level,
        "requested_opportunity_score_before_live_confirmation": item.opportunity_score_final,
        "requested_route_before_live_confirmation": item.final_route_after_quality_gate,
        "requested_state_before_live_confirmation": item.final_state_after_quality_gate,
        "final_opportunity_level": final_level,
        "final_opportunity_score": context["final_score"],
        "opportunity_level": final_level,
        "opportunity_score_final": context["final_score"],
        "final_state_after_quality_gate": context["final_state"],
        "final_route_after_quality_gate": context["final_route"],
        "final_tier_after_quality_gate": context["final_route"],
        "canonical_route_adjustment_reason": context["route_adjustment_reason"],
        "live_confirmation_required": live_policy.required,
        "live_confirmation_passed": live_policy.confirmed,
        "live_confirmation_status": live_policy.status,
        "live_confirmation_reason": live_policy.reason,
        "live_confirmation_capped": bool(live_policy.capped_level),
        "live_confirmation_original_level": item.opportunity_level,
        "live_confirmation_capped_level": live_policy.capped_level,
        "live_confirmation_missing_requirements": list(live_policy.missing_requirements),
        "acquisition_confirms_candidate": acquisition_confirmation.confirms_candidate,
        "acquisition_confirms_impact_path": acquisition_confirmation.confirms_impact_path,
        "acquisition_confirmation_status": acquisition_confirmation.status,
        "acquisition_confirmation_reason": acquisition_confirmation.reason,
        "source_pack_confirmation_status": acquisition_confirmation.status,
        "final_verdict_source": (
            _first_text(context["all_rows"], ("final_verdict_source", "opportunity_verdict_source", "verdict_source"))
            or "core_opportunity_merge"
        ),
        "final_verdict_reason": context["final_verdict_reason"],
        "why_opportunity_visible": item.why_opportunity_visible,
        "why_other_rows_hidden": item.why_other_rows_hidden,
        "card_path": event_artifact_paths.artifact_display_path(card_path) if card_path else None,
        "research_card_path": event_artifact_paths.artifact_display_path(card_path) if card_path else None,
        "feedback_target": item.core_opportunity_id,
        "feedback_target_type": "core_opportunity_id",
        "generated_at": context["generated_at"],
    }


def _row_with_score_components(row: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in ("score_components", "latest_score_components"):
        value = row.get(key)
        if isinstance(value, Mapping):
            merged.update(dict(value))
    merged.update(dict(row))
    return merged


def _merge_count_maps(values: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if not isinstance(value, Mapping):
            continue
        for key, raw in value.items():
            text = str(key or "").strip()
            if not text:
                continue
            try:
                number = int(raw or 0)
            except (TypeError, ValueError):
                continue
            counts[text] = counts.get(text, 0) + max(0, number)
    return counts


def _row_has_acquisition_metadata(row: Mapping[str, Any]) -> bool:
    if str(row.get("row_type") or "") == "event_evidence_acquisition":
        return True
    return any(
        key in row and row.get(key) not in (None, "", [], {}, ())
        for key in (
            "evidence_acquisition_attempted",
            "source_acquisition_attempted",
            "evidence_acquisition_status",
            "acquisition_status",
            "source_acquisition_status",
            "evidence_acquisition_results",
            "evidence_acquisition_accepted_evidence",
            "accepted_evidence",
            "evidence_acquisition_rejected_samples",
            "rejected_evidence_samples",
            "provider_failures",
            "evidence_acquisition_provider_failures",
        )
    )


def _is_diagnostic_acquisition_row(row: Mapping[str, Any], core_opportunity_id: str) -> bool:
    status = str(row.get("core_opportunity_id_status") or "").strip()
    if status == "diagnostic_support":
        return True
    diagnostic_target = str(row.get("diagnostic_support_for_core_opportunity_id") or "").strip()
    if diagnostic_target and diagnostic_target == core_opportunity_id:
        return True
    return bool(row.get("is_diagnostic_snapshot"))


def _acquisition_row_matches_core(row: Mapping[str, Any], identifiers: set[str]) -> bool:
    explicit = str(row.get("core_opportunity_id") or "").strip()
    if explicit:
        return explicit in identifiers
    return _row_matches_identifiers(row, identifiers)


def _evidence_samples(row: Mapping[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for key in keys:
        value = row.get(key)
        if value in (None, "", [], {}, ()):
            nested = row.get("evidence_acquisition_results")
            value = nested.get(key) if isinstance(nested, Mapping) else value
        for sample in _as_sequence(value):
            if isinstance(sample, Mapping):
                samples.append(dict(sample))
            elif str(sample or "").strip():
                samples.append({"title": str(sample).strip()})
    return samples


def _unique_evidence_samples(samples: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sample in samples:
        normalized = dict(sample)
        key = "|".join(str(normalized.get(field) or "").strip() for field in ("source_url", "title", "quote", "evidence_quote"))
        if not key.strip("|"):
            key = json.dumps(_json_ready(normalized), sort_keys=True, separators=(",", ":"))
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _query_provider_failures(row: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    for query in _as_sequence(row.get("queries")):
        if isinstance(query, Mapping):
            failures.extend(str(item) for item in _as_sequence(query.get("provider_failures")) if str(item or "").strip())
    return failures


def _nested_result_value(row: Mapping[str, Any], key: str) -> Any:
    nested = row.get("evidence_acquisition_results")
    if isinstance(nested, Mapping):
        return nested.get(key)
    return None


def _best_acquisition_status(
    rows: Iterable[Mapping[str, Any]],
    *,
    accepted_count: int,
    rejected_count: int,
) -> str:
    if accepted_count > 0:
        return "accepted_evidence_found"
    if rejected_count > 0:
        return "rejected_results_only"
    statuses = [
        str(_first_text([row], ("evidence_acquisition_status", "acquisition_status", "source_acquisition_status", "status")) or "").strip()
        for row in rows
    ]
    statuses = [status for status in statuses if status]
    if not statuses:
        return "not_executed"
    rank = {
        "accepted_evidence_found": 7,
        "executed": 6,
        "rejected_results_only": 5,
        "no_results": 4,
        "provider_backoff": 3,
        "provider_unavailable": 3,
        "failed_soft": 2,
        "skipped_budget": 1,
        "skipped_config": 1,
        "planned": 0,
        "not_executed": 0,
    }
    return sorted(statuses, key=lambda status: rank.get(status, 0), reverse=True)[0]


def _unique_strings(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _as_sequence(value: Any) -> list[Any]:
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return list(value)
    return [value]


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
