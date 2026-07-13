"""Core opportunity verdict merge and canonical field helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ...artifacts import paths as event_artifact_paths
from .. import core_opportunities as event_core_opportunities
from ..decision_model_surfaces import DECISION_MODEL_FIELD_NAMES, decision_model_values
from .. import market_reaction as event_market_reaction
from .. import opportunity_verdict as event_opportunity_verdict
from .models import *  # noqa: F403 - split modules share historical model names


_INTEGRATED_SCALAR_TRUTH_FIELDS = (
    "symbol",
    "validated_symbol",
    "coin_id",
    "validated_coin_id",
    "opportunity_type",
    "market_state_class",
    "market_state",
    "final_opportunity_level",
    "opportunity_level",
    "route",
    "tier",
    "latest_tier",
    "final_route_after_quality_gate",
    "final_tier_after_quality_gate",
    "state",
    "final_state_after_quality_gate",
    "score",
    "opportunity_score_final",
    "final_opportunity_score",
    "source_strength",
    "candidate_role",
    "asset_role",
    "source_requirements_met",
    "market_requirements_met",
    "fade_requirements_met",
    "risk_requirements_met",
    "canonical_asset_id",
    "asset_registry_symbol",
    "asset_registry_coin_id",
    "asset_registry_name",
    "asset_registry_liquidity_tier",
    "asset_registry_source",
    "instrument_resolver_status",
    "instrument_resolver_confidence",
    "instrument_resolver_match_reason",
    "instrument_identity_trusted",
    "is_tradable_asset",
    "is_theme_or_sector",
    "is_quote_asset",
    "quote_asset_excluded",
    "base_asset_excluded",
    "diagnostics_reason",
    "integrated_market_confirmation_level",
    "integrated_market_confirmation_score",
    "integrated_market_reaction_confirmation",
    "integrated_market_context_source",
    "integrated_market_freshness_status",
    "crowding_class",
    "fade_readiness",
    "why_now",
    "source_origin",
    "source_origins",
    "source_pack",
    "source_packs",
    "source_url",
    "latest_source_url",
    "latest_source_title",
    "source_class",
    "supporting_evidence_quotes",
    "research_only",
    *DECISION_MODEL_FIELD_NAMES,
)

_INTEGRATED_SEQUENCE_TRUTH_FIELDS = (
    ("what_confirms", "what_confirms"),
    ("what_invalidates", "what_invalidates"),
    ("why_not_alertable", "why_not_alertable"),
    ("reason_codes", "reason_codes"),
    ("warnings", "warnings"),
    ("crowding_exhaustion_evidence", "crowding_exhaustion_evidence"),
    ("what_confirms_fade_review", "what_confirms_fade_review"),
    ("what_invalidates_fade_review", "what_invalidates_fade_review"),
    ("derivatives_warning_codes", "derivatives_warning_codes"),
    ("instrument_resolver_warnings", "instrument_resolver_warnings"),
    ("asset_registry_venues", "asset_registry_venues"),
    ("asset_registry_spot_symbols", "asset_registry_spot_symbols"),
    ("asset_registry_perp_symbols", "asset_registry_perp_symbols"),
    ("asset_registry_coinalyze_symbols", "asset_registry_coinalyze_symbols"),
    ("asset_registry_bybit_symbols", "asset_registry_bybit_symbols"),
    ("asset_registry_binance_symbols", "asset_registry_binance_symbols"),
    ("nearby_calendar_events", "nearby_calendar_events"),
    ("calendar_events", "calendar_events"),
    ("unified_calendar_context", "unified_calendar_context"),
    ("rsi_adjustment_reason_codes", "rsi_adjustment_reason_codes"),
)

_INTEGRATED_MAPPING_TRUTH_FIELDS = (
    "market_state_snapshot",
    "latest_market_snapshot",
    "market_snapshot",
    "official_exchange_event",
    "unified_calendar_event",
    "calendar_event",
    "scheduled_catalyst_event",
    "unlock_event",
    "derivatives_state_snapshot",
    "derivatives_snapshot",
    "rsi_context",
    "rsi_context_adjustment",
    "rsi_context_safety",
)


def merge_core_opportunity_verdict(
    initial: Mapping[str, Any] | None,
    market_refresh: Mapping[str, Any] | None = None,
    evidence_acquisition: Mapping[str, Any] | None = None,
    support_rows: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return the deterministic final state from compatible candidate rows.

    Higher-quality final core rows win over stale supporting rows. Diagnostics
    are retained as support metadata by the aggregator and cannot downgrade the
    canonical visible opportunity.
    """
    rows: list[Mapping[str, Any]] = []
    for row in (initial, market_refresh, evidence_acquisition):
        if isinstance(row, Mapping) and row:
            rows.append(row)
    rows.extend(row for row in support_rows if isinstance(row, Mapping) and row)
    opportunities = event_core_opportunities.aggregate_core_opportunities(rows)
    if not opportunities:
        return {}
    item = opportunities[0]
    return _row_from_core_opportunity(
        item,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _canonical_core_route(
    item: event_core_opportunities.CoreOpportunity,
    primary: Mapping[str, Any],
    *,
    final_level: str | None = None,
) -> tuple[str, str | None]:
    current = str(item.final_route_after_quality_gate or "").strip()
    level = str(final_level or item.opportunity_level or "").strip()
    if current == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
        return current, None
    if level not in {
        event_opportunity_verdict.OpportunityLevel.VALIDATED_DIGEST.value,
        event_opportunity_verdict.OpportunityLevel.WATCHLIST.value,
        event_opportunity_verdict.OpportunityLevel.HIGH_PRIORITY.value,
    } and current in {
        event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
    }:
        return (
            event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            f"core_route_capped_by_live_confirmation:{level}",
        )
    if current in {
        event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
    }:
        return current, None
    if _core_route_quality_blocked(primary):
        return current or event_alpha_router.EventAlphaRoute.STORE_ONLY.value, None
    if level == event_opportunity_verdict.OpportunityLevel.HIGH_PRIORITY.value:
        return (
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            f"core_route_derived_from_opportunity_level:{level}",
        )
    if level in {
        event_opportunity_verdict.OpportunityLevel.WATCHLIST.value,
        event_opportunity_verdict.OpportunityLevel.VALIDATED_DIGEST.value,
    }:
        return (
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            f"core_route_derived_from_opportunity_level:{level}",
        )
    return current or event_alpha_router.EventAlphaRoute.STORE_ONLY.value, None


def _canonical_core_state(
    item: event_core_opportunities.CoreOpportunity,
    final_level: str,
    live_policy: event_opportunity_verdict.LiveConfirmationVerdict,
) -> str:
    current = str(item.final_state_after_quality_gate or item.primary_row.get("state") or "").strip()
    if current == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
        return current
    if not live_policy.capped_level:
        return current
    if final_level == event_opportunity_verdict.OpportunityLevel.LOCAL_ONLY.value:
        return event_watchlist.EventWatchlistState.RAW_EVIDENCE.value
    return event_watchlist.EventWatchlistState.RADAR.value


def _apply_integrated_candidate_truth(
    row: dict[str, Any],
    *,
    primary: Mapping[str, Any],
    all_rows: Iterable[Mapping[str, Any]],
    reaction: event_market_reaction.MarketReactionResult,
) -> dict[str, Any]:
    """Preserve already-classified integrated radar candidates at rest.

    Integrated radar candidates are the post-sidecar policy surface. The core
    store may add stricter quality/live-confirmation caps, but it must not
    recompute a generic market-reaction lane and silently upgrade capped rows.
    """
    materialized_rows = tuple(row for row in all_rows if isinstance(row, Mapping))
    integrated = _first_integrated_candidate(primary, materialized_rows)
    if integrated is None:
        return row
    core_duplicate_suppressed = str(row.get("final_route_after_quality_gate") or "").upper() == (
        event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value
    )
    row["source_row_type"] = "event_integrated_radar_candidate"
    row["integrated_candidate_id"] = integrated.get("candidate_id")
    row["integrated_candidate_family_id"] = integrated.get("candidate_family_id")
    row["generic_recomputed_opportunity_type"] = reaction.opportunity_type
    row["generic_recomputed_market_state_class"] = reaction.market_state
    for key in _INTEGRATED_SCALAR_TRUTH_FIELDS:
        value = integrated.get(key)
        if value not in (None, "", [], {}, ()):
            row[key] = value
    for src_key, dst_key in _INTEGRATED_SEQUENCE_TRUTH_FIELDS:
        value = integrated.get(src_key)
        if value not in (None, "", [], {}, ()):
            row[dst_key] = list(value) if isinstance(value, (list, tuple, set)) else [value]
    row["opportunity_type_why_now"] = integrated.get("why_now") or row.get("opportunity_type_why_now")
    row["opportunity_type_what_confirms"] = list(integrated.get("what_confirms") or row.get("opportunity_type_what_confirms") or ())
    row["opportunity_type_what_invalidates"] = list(integrated.get("what_invalidates") or row.get("opportunity_type_what_invalidates") or ())
    row["opportunity_type_why_not_alertable"] = list(integrated.get("why_not_alertable") or row.get("opportunity_type_why_not_alertable") or ())
    row["opportunity_type_reason_codes"] = list(integrated.get("reason_codes") or row.get("opportunity_type_reason_codes") or ())
    row["opportunity_type_warnings"] = list(integrated.get("warnings") or row.get("opportunity_type_warnings") or ())
    for key in _INTEGRATED_MAPPING_TRUTH_FIELDS:
        value = integrated.get(key)
        if isinstance(value, Mapping) and value:
            row[key] = dict(value)
    official = row.get("official_exchange_event") if isinstance(row.get("official_exchange_event"), Mapping) else {}
    if official:
        row["official_exchange_provider"] = _mapping_text(official, ("provider",)) or row.get("official_exchange_provider")
        row["official_exchange"] = _mapping_text(official, ("exchange",)) or row.get("official_exchange")
        row["official_exchange_event_type"] = _mapping_text(official, ("event_type",)) or row.get("official_exchange_event_type")
        row["official_exchange_title"] = _mapping_text(official, ("title", "event_name")) or row.get("official_exchange_title")
        row["official_exchange_url"] = _mapping_text(official, ("source_url", "url")) or row.get("official_exchange_url")
        row["official_exchange_published_at"] = _mapping_text(official, ("published_at",)) or row.get("official_exchange_published_at")
        row["official_exchange_effective_time"] = _mapping_text(official, ("effective_time",)) or row.get("official_exchange_effective_time")
        row["official_exchange_reason_codes"] = _mapping_list(official, ("reason_codes",)) or row.get("official_exchange_reason_codes")
        row["latest_source_url"] = row.get("latest_source_url") or row.get("official_exchange_url")
        row["source_url"] = row.get("source_url") or row.get("official_exchange_url")
        row["latest_source_title"] = row.get("latest_source_title") or row.get("official_exchange_title")
    if _opportunity_rank_value(str(row.get("opportunity_type") or "")) > _opportunity_rank_value(str(integrated.get("opportunity_type") or "")):
        row["integrated_core_silent_upgrade"] = True
    if core_duplicate_suppressed:
        row["final_route_after_quality_gate"] = event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value
        row["duplicate_suppressed"] = True
    # The integrated candidate owns the Decision v2 evaluation for this idea
    # generation.  Core serialization is a projection/copy boundary, not a
    # second scoring boundary: re-evaluating here can lose calendar or RSI
    # evidence that is not part of the generic Core merge context and silently
    # change routes or scores.  A malformed explicit authority therefore fails
    # closed instead of borrowing partial context from supporting rows.
    canonical_decision = decision_model_values(integrated)
    if canonical_decision:
        row["decision_projection"] = dict(canonical_decision)
        for field in DECISION_MODEL_FIELD_NAMES:
            if field in canonical_decision:
                row[field] = canonical_decision[field]
        row["decision_projection_source"] = "integrated_candidate"
        row["decision_projection_drift_detected"] = False
    elif any(
        integrated.get(field) not in (None, "")
        for field in ("decision_model_version", "decision_model_enabled")
    ):
        for field in DECISION_MODEL_FIELD_NAMES:
            row.pop(field, None)
        row["decision_projection_source"] = "invalid_integrated_candidate"
        row["decision_projection_drift_detected"] = True
    return row


def _first_integrated_candidate(
    primary: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    if (
        str(primary.get("row_type") or "") == "event_integrated_radar_candidate"
        or str(primary.get("source_row_type") or "") == "event_integrated_radar_candidate"
    ):
        return primary
    for row in rows:
        if (
            str(row.get("row_type") or "") == "event_integrated_radar_candidate"
            or str(row.get("source_row_type") or "") == "event_integrated_radar_candidate"
        ):
            return row
    return None


def _opportunity_rank_value(value: str) -> int:
    return {
        "DIAGNOSTIC": 0,
        "UNCONFIRMED_RESEARCH": 1,
        "RISK_ONLY": 2,
        "EARLY_LONG_RESEARCH": 3,
        "CONFIRMED_LONG_RESEARCH": 4,
        "FADE_SHORT_REVIEW": 5,
    }.get(str(value or "").upper(), -1)


def _core_route_quality_blocked(primary: Mapping[str, Any]) -> bool:
    route, block = event_alpha_router.quality_gate_route_for_row(primary, require_quality=True)
    if block:
        return True
    if route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value:
        return False
    if _truthy(primary.get("state_quality_capped")):
        return True
    return False


def _default_core_verdict_reason(level: str | None) -> str:
    level_text = str(level or "unknown").strip() or "unknown"
    return f"Core opportunity verdict reached {level_text}."


def _canonical_route_adjusted_verdict_reason(level: str | None) -> str:
    level_text = str(level or "unknown").strip() or "unknown"
    return (
        f"Core opportunity verdict reached {level_text}; "
        "final route derived from canonical opportunity level."
    )


def _accepted_evidence_source_summary(samples: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    for sample in samples:
        if not isinstance(sample, Mapping):
            continue
        provider = _text_or_none(sample.get("provider")) or _text_or_none(sample.get("provider_hint"))
        title = _text_or_none(sample.get("title"))
        source_url = _text_or_none(sample.get("source_url"))
        if provider or title or source_url:
            return {"provider": provider, "title": title, "source_url": source_url}
    return {}


def _first_mapping(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> dict[str, Any] | None:
    for row in rows:
        for key in keys:
            value = row.get(key)
            if isinstance(value, Mapping) and value:
                return dict(value)
    return None


def _mapping_text(row: Mapping[str, Any] | None, keys: tuple[str, ...]) -> str | None:
    if not isinstance(row, Mapping):
        return None
    for key in keys:
        value = _text_or_none(row.get(key))
        if value:
            return value
    return None


def _mapping_list(row: Mapping[str, Any] | None, keys: tuple[str, ...]) -> list[str]:
    if not isinstance(row, Mapping):
        return []
    out: list[str] = []
    for key in keys:
        raw = row.get(key)
        if isinstance(raw, str):
            if raw:
                out.append(raw)
        elif isinstance(raw, Mapping):
            out.extend(str(value) for value in raw.values() if str(value or ""))
        elif isinstance(raw, Iterable):
            out.extend(str(item) for item in raw if str(item or ""))
    return list(dict.fromkeys(out))


def _canonical_source_count(
    rows: Iterable[Mapping[str, Any]],
    acquisition: CoreEvidenceAcquisitionView,
) -> int:
    counts = [
        _float_or_none(_first_value(rows, ("source_count", "independent_source_count", "source_update_count"))),
        float(acquisition.accepted_evidence_count) if acquisition.accepted_evidence_count else None,
    ]
    count = max((int(value) for value in counts if value is not None), default=0)
    return count


def _first_real_text(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> str | None:
    text = _first_text(rows, keys)
    return None if _is_filler_text(text) else text


def _is_filler_text(value: Any) -> bool:
    return str(value or "").strip().casefold() in {
        "",
        "unknown",
        "missing",
        "none",
        "not available",
        "n/a",
        "insufficient_data",
        "impact_hypothesis",
        "watchlist",
        "alert_snapshot",
        "core_opportunity",
    }


def _canonical_impact_path_reason(primary_path: str | None, source_pack: str | None) -> str | None:
    path = str(primary_path or "").strip()
    pack = str(source_pack or "").strip()
    if path in {"proxy_attention", "proxy_exposure", "venue_value_capture"} or pack == "proxy_preipo_rwa_pack":
        return "venue_value_capture"
    if path in {"strategic_investment_or_valuation", "acquisition_or_stake"} or pack == "strategic_investment_pack":
        return "strategic_investment"
    if path == "exploit_security_event":
        return "exploit_security_event"
    if path == "listing_liquidity_event":
        return "listing_liquidity_event"
    if path == "market_dislocation_unknown":
        return "cause_unknown_market_dislocation"
    return path or None


def _canonical_impact_path_strength(
    level: str | None,
    primary_path: str | None,
    evidence_score: float | None,
    market_score: float | None,
) -> str | None:
    path = str(primary_path or "").strip()
    lvl = str(level or "").strip()
    if path in {"insufficient_data", "generic_cooccurrence_only", ""}:
        return "none" if path else None
    if lvl in {"high_priority", "watchlist"}:
        return "strong"
    if lvl == "validated_digest":
        return "medium"
    if (evidence_score or 0.0) >= 75 and (market_score or 0.0) >= 50:
        return "medium"
    return "weak"


def _canonical_market_summary(
    *,
    market_level: str | None,
    market_score: float | None,
    market_context: Mapping[str, Any],
) -> str | None:
    if not market_level and market_score is None and not market_context:
        return None
    parts = []
    if market_level:
        score_text = f" / {market_score:.0f}" if market_score is not None else ""
        parts.append(f"{market_level}{score_text}")
    freshness = market_context.get("market_context_freshness_status")
    source = market_context.get("market_context_source")
    age = market_context.get("market_context_age_hours")
    if freshness or source:
        age_text = ""
        if isinstance(age, (int, float)):
            age_text = f"; age={age:.1f}h" if age >= 1 else f"; age={age * 60:.0f}m"
        parts.append(f"freshness={freshness or 'not available'} source={source or 'not available'}{age_text}")
    return "; ".join(parts) if parts else None


def _market_level_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 75:
        return "strong"
    if score >= 50:
        return "moderate"
    if score > 0:
        return "weak"
    return "none"


def _best_market_snapshot(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    for row in rows:
        for source in (
            row.get("latest_market_snapshot"),
            row.get("market_snapshot"),
            row.get("market_context"),
        ):
            if isinstance(source, Mapping) and source:
                return dict(source)
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        if isinstance(components, Mapping):
            for source in (
                components.get("latest_market_snapshot"),
                components.get("market_snapshot"),
                components.get("market_context"),
            ):
                if isinstance(source, Mapping) and source:
                    return dict(source)
    return {}


def _canonical_manual_verification_items(
    item: event_core_opportunities.CoreOpportunity,
    source_pack: str | None,
    *,
    final_level: str | None = None,
    live_policy: event_opportunity_verdict.LiveConfirmationVerdict | None = None,
) -> list[str]:
    if live_policy and live_policy.required and not live_policy.confirmed:
        return list(live_policy.manual_verification_items)
    level = final_level or item.opportunity_level
    if level == "high_priority":
        return [
            "verify independent source corroboration",
            "verify exposure/value-capture claim remains valid",
            "verify liquidity and market confirmation are still fresh",
        ]
    if level == "watchlist":
        return ["verify second source, market confirmation, derivatives/liquidity, and catalyst timing"]
    if level == "validated_digest":
        return ["verify market reaction, official/second-source confirmation, and source-pack coverage"]
    if str(source_pack or "") == "market_anomaly_pack":
        return ["find causal catalyst evidence and confirm the move is not purely mechanical"]
    return ["validate catalyst, token identity, impact path, and market confirmation"]


def _canonical_upgrade_requirements(
    level: str | None,
    *,
    live_policy: event_opportunity_verdict.LiveConfirmationVerdict | None = None,
) -> list[str]:
    if live_policy and live_policy.required and not live_policy.confirmed:
        return list(live_policy.missing_requirements)
    if level == "high_priority":
        return ["sustained_fresh_market_confirmation", "stronger_source_corroboration", "derivatives_or_liquidity_support"]
    if level == "watchlist":
        return ["fresh_stronger_market_confirmation", "second_independent_source", "derivatives_or_liquidity_support"]
    if level == "validated_digest":
        return ["fresh_price_volume_reaction", "official_or_second_source_confirmation", "derivatives_or_supply_confirmation"]
    return ["validated_catalyst", "direct_token_mechanism", "identity_validation", "market_confirmation"]


def _canonical_downgrade_warnings(primary_path: str | None, level: str | None) -> list[str]:
    if level in {"high_priority", "watchlist", "validated_digest"}:
        if str(primary_path or "") in {"proxy_attention", "proxy_exposure", "venue_value_capture"}:
            return ["source_correction_or_denial", "exposure_value_capture_invalid", "market_confirmation_fades", "liquidity_drifts_lower", "catalyst_stale"]
        if str(primary_path or "") == "strategic_investment_or_valuation":
            return ["deal_denied_or_corrected", "token_value_capture_invalid", "market_reaction_absent", "market_context_stale"]
        return ["source_correction_or_denial", "impact_path_invalid", "market_confirmation_fades", "liquidity_drifts_lower"]
    return ["source_noise", "weak_cooccurrence_only", "market_move_without_catalyst"]
