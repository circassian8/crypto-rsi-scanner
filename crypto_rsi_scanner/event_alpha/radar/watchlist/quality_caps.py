"""Event Alpha watchlist quality-cap helpers."""

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
from .models import *  # noqa: F403 - split modules share legacy model names


def quality_cap_watchlist_state(
    requested_state: str | EventWatchlistState | None,
    quality_bundle: Mapping[str, Any] | None,
) -> tuple[str, str | None]:
    """Return the lifecycle state allowed by the final quality verdict.

    This is a research-artifact safety cap, not a scoring model. It prevents
    local-only or insufficient-data rows from surviving as active watchlist
    candidates while preserving deterministic event-fade triggers.
    """
    requested = _state_value(requested_state)
    if requested == EventWatchlistState.TRIGGERED_FADE.value:
        return requested, None
    if requested in {
        EventWatchlistState.INVALIDATED.value,
        EventWatchlistState.EXPIRED.value,
    }:
        return requested, None
    if not _quality_bundle_has_authority(quality_bundle):
        return requested, None
    raw_quality = dict(quality_bundle or {})
    quality = event_alpha_quality_fields.ensure_quality_fields(raw_quality)
    level = str(quality.get("opportunity_level") or "").strip()
    score = _optional_float(quality.get("opportunity_score_final"))
    impact = str(quality.get("impact_path_type") or "").strip()
    evidence = str(quality.get("evidence_specificity") or "").strip()
    source = str(quality.get("source_class") or "").strip()
    role = str(quality.get("candidate_role") or "").strip()
    requested_rank = _state_rank(requested)

    block = _quality_state_block_reason(quality, level=level, score=score, impact=impact, evidence=evidence, source=source, role=role)
    if block:
        if level == "exploratory" and requested_rank >= _STATE_RANK[EventWatchlistState.WATCHLIST.value]:
            return EventWatchlistState.RADAR.value, block
        if requested_rank >= _STATE_RANK[EventWatchlistState.RADAR.value]:
            return EventWatchlistState.QUALITY_BLOCKED.value, block
        return requested, block
    if level == "validated_digest" and requested_rank > _STATE_RANK[EventWatchlistState.RADAR.value]:
        return EventWatchlistState.RADAR.value, "opportunity_level_caps_state:validated_digest"
    if (
        level == "watchlist"
        and requested_rank > _STATE_RANK[EventWatchlistState.WATCHLIST.value]
        and requested not in {
            EventWatchlistState.EVENT_PASSED.value,
            EventWatchlistState.ARMED.value,
        }
    ):
        return EventWatchlistState.WATCHLIST.value, "opportunity_level_caps_state:watchlist"
    return requested, None


def final_state_value(entry: EventWatchlistEntry | Mapping[str, Any]) -> str:
    """Return the quality-capped state for an entry or raw row."""
    if isinstance(entry, Mapping):
        final = _optional_str(entry.get("final_state_after_quality_gate"))
        requested = _optional_str(entry.get("requested_state_before_quality_gate")) or _optional_str(entry.get("state"))
        persisted_final = _state_value(final)
        if persisted_final in {
            EventWatchlistState.TRIGGERED_FADE.value,
            EventWatchlistState.INVALIDATED.value,
            EventWatchlistState.EXPIRED.value,
        }:
            return persisted_final
        components = entry.get("latest_score_components")
        if event_alpha_quality_fields.has_any_quality_field(entry, components_key="latest_score_components"):
            quality = event_alpha_quality_fields.ensure_quality_fields(
                entry,
                components=dict(components if isinstance(components, Mapping) else {}),
            )
            return quality_cap_watchlist_state(requested, quality)[0]
        if final:
            return persisted_final
        return _state_value(requested)
    final = entry.final_state_after_quality_gate
    if final:
        return _state_value(final)
    quality = _quality_bundle_from_entry(entry)
    return quality_cap_watchlist_state(entry.requested_state_before_quality_gate or entry.state, quality)[0]


def requested_state_value(entry: EventWatchlistEntry | Mapping[str, Any]) -> str:
    if isinstance(entry, Mapping):
        return _state_value(entry.get("requested_state_before_quality_gate") or entry.get("state"))
    return _state_value(entry.requested_state_before_quality_gate or entry.state)


def state_is_quality_capped(entry: EventWatchlistEntry | Mapping[str, Any]) -> bool:
    if isinstance(entry, Mapping):
        raw = entry.get("state_quality_capped")
        if raw is True:
            return bool(raw)
        return requested_state_value(entry) != final_state_value(entry)
    return bool(entry.state_quality_capped is True or requested_state_value(entry) != final_state_value(entry))


def _quality_bundle_has_authority(quality_bundle: Mapping[str, Any] | None) -> bool:
    if not isinstance(quality_bundle, Mapping) or not quality_bundle:
        return False
    return any(
        key in quality_bundle and not event_alpha_quality_fields.is_missing_quality_value(quality_bundle.get(key))
        for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS
    )


def _quality_bundle_from_entry(entry: EventWatchlistEntry) -> dict[str, Any]:
    row = {
        key: getattr(entry, key, None)
        for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS
        if getattr(entry, key, None) not in (None, "", [], {}, ())
    }
    components = dict(entry.latest_score_components or {})
    if not event_alpha_quality_fields.has_any_quality_field(row, components_key="latest_score_components") and not event_alpha_quality_fields.has_any_quality_field(components):
        return {}
    return {**components, **row}


def _quality_state_block_reason(
    quality: Mapping[str, Any],
    *,
    level: str,
    score: float | None,
    impact: str,
    evidence: str,
    source: str,
    role: str,
) -> str | None:
    text = " ".join(
        str(value or "")
        for value in (
            impact,
            evidence,
            source,
            role,
            quality.get("why_local_only"),
            quality.get("why_not_watchlist"),
            *(quality.get("opportunity_verdict_reasons") or ()),
            *(quality.get("upgrade_requirements") or ()),
            *(quality.get("downgrade_warnings") or ()),
        )
    ).casefold()
    if impact == "insufficient_data":
        return "impact_path_type_insufficient_data"
    if score is not None and score <= 0:
        return "opportunity_score_final_zero"
    if role == "unknown_with_reason":
        return "candidate_role_unknown_with_reason"
    if source == "insufficient_data":
        return "source_class_insufficient_data"
    if evidence == "insufficient_data":
        return "evidence_specificity_insufficient_data"
    if "source_noise" in text:
        return "source_noise_hard_gate"
    if "ticker_collision" in text or "word_collision" in text or "ticker_word_collision" in text:
        return "ticker_collision_hard_gate"
    if level == "local_only":
        return _normalize_quality_state_block_reason(
            str(quality.get("why_local_only") or "opportunity_level_local_only"),
            quality,
        )
    if level == "exploratory":
        return _normalize_quality_state_block_reason(
            str(quality.get("why_not_watchlist") or "opportunity_level_exploratory"),
            quality,
        )
    return None


def _normalize_quality_state_block_reason(reason: str | None, quality: Mapping[str, Any]) -> str | None:
    """Keep block reasons actionable, especially for legacy artifacts."""
    if not reason:
        return None
    value = str(reason)
    normalized = value.strip().casefold()
    if normalized == "strong_market_confirmation":
        impact = str(quality.get("impact_path_type") or "").strip()
        strength = str(quality.get("impact_path_strength") or "").strip()
        role = str(quality.get("candidate_role") or "").strip()
        market_level = str(quality.get("market_confirmation_level") or "").strip()
        market_score = _optional_float(quality.get("market_confirmation_score"))
        market_is_strong = market_level in {"strong", "confirmed"} or (market_score is not None and market_score >= 75)
        weak_context = (
            strength not in {"strong", "medium"}
            or impact in {"generic_cooccurrence_only", "macro_attention_only", "technology_risk", "market_structure_policy", "unknown", ""}
            or role in {"generic_mention", "macro_affected_asset", "unknown_with_reason", ""}
        )
        if market_is_strong and weak_context:
            return "weak_impact_path_despite_market_confirmation"
        if market_is_strong:
            return "impact_path_not_strong_enough"
        return "needs_strong_market_confirmation"
    if normalized == "impact_path":
        return "impact_path_not_strong_enough"
    if normalized == "explained_token_impact_path":
        return "missing_direct_impact_path"
    return value
