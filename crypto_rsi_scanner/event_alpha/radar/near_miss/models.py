"""Event Alpha near-miss models."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping

import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner as event_llm_evidence_planner
import crypto_rsi_scanner.event_alpha.radar.market_confirmation as event_market_confirmation
import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict
import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs
import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry


@dataclass(frozen=True)
class EventNearMissConfig:
    enabled: bool = True
    near_threshold_points: float = 10.0
    digest_threshold: float = 65.0
    watchlist_threshold: float = 78.0
    max_candidates: int = 20
    market_refresh_enabled: bool = False
    max_market_refresh_assets: int = 20
    market_refresh_timeout_seconds: float = 5.0
    stale_after_seconds: float = 6 * 3600
    source_refresh_enabled: bool = False
    max_source_queries: int = 2


@dataclass(frozen=True)
class EventTargetedMarketRefreshQueueItem:
    refresh_id: str
    symbol: str
    coin_id: str
    core_opportunity_id: str | None
    hypothesis_id: str | None
    incident_id: str | None
    reason: str
    current_market_source: str | None
    current_market_age_seconds: float | None
    priority_score: float
    canonical_asset_id: str = ""
    priority_bucket: str = "fresh_candidate"
    candidate_family_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventNearMissCandidate:
    near_miss_id: str
    refresh_id: str | None
    symbol: str
    coin_id: str
    core_opportunity_id: str | None
    hypothesis_id: str | None
    incident_id: str | None
    opportunity_level_before: str
    opportunity_score_before: float
    opportunity_level_after: str | None = None
    opportunity_score_after: float | None = None
    final_route_before: str | None = None
    final_route_after: str | None = None
    missing_evidence: tuple[str, ...] = ()
    recommended_refresh_actions: tuple[str, ...] = ()
    priority_score: float = 0.0
    market_refresh_attempted: bool = False
    market_refresh_success: bool = False
    market_refresh_provider: str | None = None
    market_refresh_error_class: str | None = None
    market_context_source: str | None = None
    market_context_age_seconds: float | None = None
    market_context_data_quality: str | None = None
    market_context_before: Mapping[str, Any] | None = None
    market_context_after: Mapping[str, Any] | None = None
    market_confirmation_before: float | None = None
    market_confirmation_after: float | None = None
    refresh_upgrade_status: str | None = None
    derivatives_refresh_attempted: bool = False
    derivatives_refresh_success: bool = False
    supply_refresh_attempted: bool = False
    supply_refresh_success: bool = False
    derivative_confirmation_reasons: tuple[str, ...] = ()
    supply_confirmation_reasons: tuple[str, ...] = ()
    evidence_refresh_attempted: bool = False
    evidence_refresh_success: bool = False
    evidence_refresh_queries: tuple[str, ...] = ()
    evidence_quality_before: float | None = None
    evidence_quality_after: float | None = None
    source_pack: str | None = None
    provider_coverage_status: str | None = None
    evidence_absence_is_meaningful: bool = False
    source_coverage_gap: str | None = None
    source_quality_prior: float | None = None
    source_confidence_cap: float | None = None
    evidence_acquisition_attempted: bool = False
    evidence_acquisition_plan: Mapping[str, Any] | None = None
    evidence_acquisition_results: Mapping[str, Any] | None = None
    evidence_acquisition_failures: tuple[str, ...] = ()
    upgrade_reason: str | None = None
    no_upgrade_reason: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventNearMissRefreshResult:
    hypotheses: tuple[object, ...]
    near_misses: tuple[EventNearMissCandidate, ...]
    refreshed_count: int = 0
    upgraded_count: int = 0
    warnings: tuple[str, ...] = ()
