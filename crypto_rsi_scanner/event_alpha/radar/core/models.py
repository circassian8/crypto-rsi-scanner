"""Core opportunity store models."""

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
from .. import market_reaction as event_market_reaction
from .. import opportunity_verdict as event_opportunity_verdict


EVENT_CORE_OPPORTUNITY_STORE_SCHEMA_VERSION = "event_core_opportunity_store_v1"


@dataclass(frozen=True)
class EventCoreOpportunityStoreConfig:
    path: Path


@dataclass(frozen=True)
class EventCoreOpportunityStoreWriteResult:
    path: Path
    attempted: bool
    success: bool
    rows_written: int = 0
    block_reason: str | None = None


@dataclass(frozen=True)
class EventCoreOpportunityStoreReadResult:
    path: Path
    rows_read: int
    rows: list[dict[str, Any]]
    total_rows_read: int = 0
    latest_run_id: str | None = None
    latest_run_rows_available: int = 0
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventCoreOpportunityCardLinkUpdateResult:
    path: Path
    attempted: bool
    success: bool
    rows_updated: int = 0
    block_reason: str | None = None


@dataclass(frozen=True)
class EventCoreOpportunityStoreNormalizeResult:
    path: Path
    attempted: bool
    success: bool
    rows_read: int = 0
    rows_written: int = 0
    rows_updated: int = 0
    block_reason: str | None = None


@dataclass(frozen=True)
class CanonicalCoreOpportunityView:
    """Single read model for one operator-facing Event Alpha opportunity."""

    profile: str | None
    artifact_namespace: str | None
    requested_core_opportunity_id: str
    core_opportunity_id: str | None
    found: bool
    canonical_core_row: dict[str, Any] | None = None
    core_opportunity: event_core_opportunities.CoreOpportunity | None = None
    supporting_rows: tuple[dict[str, Any], ...] = ()
    diagnostic_rows: tuple[dict[str, Any], ...] = ()
    evidence_acquisition_rows: tuple[dict[str, Any], ...] = ()
    market_refresh_rows: tuple[dict[str, Any], ...] = ()
    research_card_path: str | None = None
    alert_snapshot_rows: tuple[dict[str, Any], ...] = ()
    incident_row: dict[str, Any] | None = None
    incident_rows: tuple[dict[str, Any], ...] = ()
    feedback_target: str | None = None
    feedback_status: str = "pending_or_unknown"
    feedback_rows: tuple[dict[str, Any], ...] = ()
    feedback_rows_supplied: int = 0
    feedback_rows_eligible: int = 0
    feedback_rows_matched_to_core: int = 0
    feedback_rows_eligible_other_core: int = 0
    feedback_rows_excluded: int = 0
    feedback_exclusion_reason_counts: Mapping[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def symbol(self) -> str | None:
        return _first_text([self.canonical_core_row or {}], ("symbol", "validated_symbol"))

    @property
    def coin_id(self) -> str | None:
        return _first_text([self.canonical_core_row or {}], ("coin_id", "validated_coin_id"))

    @property
    def opportunity_level(self) -> str | None:
        return _first_text([self.canonical_core_row or {}], ("final_opportunity_level", "opportunity_level"))

    @property
    def final_route_after_quality_gate(self) -> str | None:
        return _first_text([self.canonical_core_row or {}], ("final_route_after_quality_gate", "route"))

    @property
    def final_state_after_quality_gate(self) -> str | None:
        return _first_text([self.canonical_core_row or {}], ("final_state_after_quality_gate", "state"))


@dataclass(frozen=True)
class CoreEvidenceAcquisitionView:
    """Canonical source-acquisition read model for one core opportunity."""

    core_opportunity_id: str
    acquisition_attempted: bool = False
    acquisition_status: str = "not_executed"
    source_pack: str | None = None
    accepted_evidence_count: int = 0
    rejected_evidence_count: int = 0
    accepted_reason_codes: tuple[str, ...] = ()
    rejected_reason_codes: tuple[str, ...] = ()
    accepted_provider_counts: Mapping[str, int] | None = None
    rejected_provider_counts: Mapping[str, int] | None = None
    accepted_reason_code_counts: Mapping[str, int] | None = None
    accepted_evidence_samples: tuple[dict[str, Any], ...] = ()
    rejected_evidence_samples: tuple[dict[str, Any], ...] = ()
    source_update_count: int = 0
    independent_source_count: int = 0
    independent_corroboration_count: int = 0
    source_content_cluster_count: int = 0
    source_independence: Mapping[str, Any] = field(default_factory=dict)
    source_independence_status: str = "unassessed"
    source_independence_errors: tuple[str, ...] = ()
    provider_failures: tuple[str, ...] = ()
    evidence_quality_before: float | None = None
    evidence_quality_after: float | None = None
    opportunity_score_before: float | None = None
    opportunity_score_after: float | None = None
    opportunity_level_before: str | None = None
    opportunity_level_after: str | None = None
    final_upgrade_status: str | None = None
    no_upgrade_reason: str | None = None
    diagnostic_rows: tuple[dict[str, Any], ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "status": self.acquisition_status,
            "source_pack": self.source_pack,
            "accepted": self.accepted_evidence_count,
            "rejected": self.rejected_evidence_count,
            "accepted_reason_codes": self.accepted_reason_codes,
            "rejected_reason_codes": self.rejected_reason_codes,
            "accepted_provider_counts": dict(self.accepted_provider_counts or {}),
            "rejected_provider_counts": dict(self.rejected_provider_counts or {}),
            "accepted_reason_code_counts": dict(self.accepted_reason_code_counts or {}),
            "source_update_count": self.source_update_count,
            "independent_source_count": self.independent_source_count,
            "independent_corroboration_count": self.independent_corroboration_count,
            "source_content_cluster_count": self.source_content_cluster_count,
            "source_independence": dict(self.source_independence),
            "source_independence_status": self.source_independence_status,
            "source_independence_errors": self.source_independence_errors,
            "provider_failures": self.provider_failures,
            "evidence_quality_before": self.evidence_quality_before,
            "evidence_quality_after": self.evidence_quality_after,
            "opportunity_score_before": self.opportunity_score_before,
            "opportunity_score_after": self.opportunity_score_after,
            "opportunity_level_before": self.opportunity_level_before,
            "opportunity_level_after": self.opportunity_level_after,
            "final_upgrade_status": self.final_upgrade_status,
            "no_upgrade_reason": self.no_upgrade_reason,
        }
