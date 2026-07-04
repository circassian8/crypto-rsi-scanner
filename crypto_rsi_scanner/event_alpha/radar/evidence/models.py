"""Evidence acquisition models and constants."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .... import (
    event_evidence_quality,
    event_llm_evidence_planner,
)
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ....event_resolver import clean_text
from ...providers import source_packs as event_source_packs
from ...providers import source_registry as event_source_registry
from .. import catalyst_search as event_catalyst_search
from .. import core_opportunities as event_core_opportunities
from .. import impact_hypotheses as event_impact_hypotheses
from .. import source_enrichment as event_source_enrichment


SCHEMA_VERSION = "event_evidence_acquisition_v1"


PROMOTED_OPPORTUNITY_LEVELS = {"validated_digest", "watchlist", "high_priority"}


UNCONFIRMED_ACQUISITION_STATUSES = {
    "rejected_results_only",
    "no_results",
    "skipped_budget",
    "not_executed",
    "not_configured",
    "provider_unavailable",
    "provider_backoff",
    "skipped_config",
}


class EvidenceAcquisitionStatus(str, Enum):
    PLANNED = "planned"
    EXECUTED = "executed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_BACKOFF = "provider_backoff"
    NO_RESULTS = "no_results"
    ACCEPTED_EVIDENCE_FOUND = "accepted_evidence_found"
    REJECTED_RESULTS_ONLY = "rejected_results_only"
    FAILED_SOFT = "failed_soft"
    SKIPPED_BUDGET = "skipped_budget"
    SKIPPED_CONFIG = "skipped_config"


class EvidenceSearchProvider(Protocol):
    name: str

    def search(
        self,
        queries: Iterable[event_catalyst_search.SearchQuery],
        *,
        max_results_per_query: int,
        now: datetime | None = None,
    ) -> event_catalyst_search.CatalystSearchRunResult:
        ...


@dataclass(frozen=True)
class EvidenceAcquisitionConfig:
    enabled: bool = False
    max_candidates: int = 10
    max_queries: int = 20
    max_results_per_query: int = 5
    timeout_seconds: float = 8.0
    fixture_only: bool = False
    artifact_path: Path | None = None


@dataclass(frozen=True)
class EvidenceAcquisitionRequest:
    acquisition_id: str
    opportunity_id: str
    core_opportunity_id: str | None
    hypothesis_id: str | None
    incident_id: str | None
    symbol: str
    coin_id: str
    event_name: str
    external_asset: str
    source_pack: str
    opportunity_score_before: float
    opportunity_level_before: str
    evidence_quality_before: float | None
    impact_path_validation_before: str | None
    query_plan: tuple[event_llm_evidence_planner.EvidencePlanQuery, ...]
    provider_coverage_status: str = event_source_registry.ProviderCoverageStatus.COMPLETE.value
    row: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class EvidenceAcquisitionQueryResult:
    query: str
    provider_hint: str
    provider_used: str | None
    purpose: str
    status: str
    results_seen: int = 0
    accepted_evidence: tuple[Mapping[str, Any], ...] = ()
    rejected_evidence: tuple[Mapping[str, Any], ...] = ()
    provider_failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence_absence_is_meaningful: bool = False

    def to_metadata(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "provider_hint": self.provider_hint,
            "provider_used": self.provider_used,
            "purpose": self.purpose,
            "status": self.status,
            "results_seen": self.results_seen,
            "accepted_evidence": tuple(dict(item) for item in self.accepted_evidence),
            "rejected_evidence": tuple(dict(item) for item in self.rejected_evidence),
            "provider_failures": self.provider_failures,
            "warnings": self.warnings,
            "evidence_absence_is_meaningful": self.evidence_absence_is_meaningful,
        }


@dataclass(frozen=True)
class EvidenceAcquisitionResult:
    acquisition_id: str
    opportunity_id: str
    core_opportunity_id: str | None
    hypothesis_id: str | None
    incident_id: str | None
    source_pack: str
    status: str
    symbol: str = ""
    coin_id: str = ""
    event_name: str = ""
    external_asset: str = ""
    queries_executed: int = 0
    providers_used: tuple[str, ...] = ()
    provider_failures: tuple[str, ...] = ()
    accepted_evidence: tuple[Mapping[str, Any], ...] = ()
    rejected_evidence: tuple[Mapping[str, Any], ...] = ()
    query_results: tuple[EvidenceAcquisitionQueryResult, ...] = ()
    evidence_quality_before: float | None = None
    evidence_quality_after: float | None = None
    impact_path_validation_before: str | None = None
    impact_path_validation_after: str | None = None
    opportunity_score_before: float = 0.0
    opportunity_score_after: float = 0.0
    opportunity_level_before: str = "local_only"
    opportunity_level_after: str = "local_only"
    acquisition_evidence_status: str = "no_results"
    evidence_quality_delta: float | None = None
    opportunity_score_delta: float = 0.0
    opportunity_level_delta: str = "unchanged"
    evidence_quality_upgraded: bool = False
    impact_path_validation_upgraded: bool = False
    market_confirmation_upgraded: bool = False
    final_upgrade_status: str = "unchanged"
    initial_opportunity_score: float | None = None
    initial_opportunity_level: str | None = None
    post_refresh_opportunity_score: float | None = None
    post_refresh_opportunity_level: str | None = None
    post_refresh_market_confirmation_score: float | None = None
    post_refresh_market_confirmation_level: str | None = None
    post_refresh_evidence_quality_score: float | None = None
    final_opportunity_score: float | None = None
    final_opportunity_level: str | None = None
    final_verdict_source: str = "initial"
    final_verdict_reason: str | None = None
    market_data_freshness: str | None = None
    market_reaction_confirmation: str | None = None
    acquisition_upgrade_status: str = "unchanged"
    acquisition_upgrade_reason: str | None = None
    no_upgrade_reason: str | None = None
    warnings: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return evidence_acquisition_result_metadata(self)


def evidence_acquisition_result_metadata(result: EvidenceAcquisitionResult) -> dict[str, Any]:
    reason_codes = tuple(dict.fromkeys(
        str(code)
        for item in result.accepted_evidence
        for code in item.get("reason_codes", ())
        if str(code)
    ))
    return {
        "evidence_acquisition_id": result.acquisition_id,
        "evidence_acquisition_symbol": result.symbol,
        "evidence_acquisition_coin_id": result.coin_id,
        "evidence_acquisition_event_name": result.event_name,
        "evidence_acquisition_external_asset": result.external_asset,
        "evidence_acquisition_status": result.status,
        "evidence_acquisition_source_pack": result.source_pack,
        "evidence_acquisition_queries_executed": result.queries_executed,
        "evidence_acquisition_providers_used": result.providers_used,
        "evidence_acquisition_provider_failures": result.provider_failures,
        "evidence_acquisition_accepted_count": len(result.accepted_evidence),
        "evidence_acquisition_rejected_count": len(result.rejected_evidence),
        "evidence_acquisition_accepted_evidence": tuple(dict(item) for item in result.accepted_evidence[:5]),
        "evidence_acquisition_rejected_samples": tuple(dict(item) for item in result.rejected_evidence[:5]),
        "accepted_evidence_reason_codes": reason_codes,
        "acquisition_evidence_status": result.acquisition_evidence_status,
        "evidence_acquisition_score_before": result.evidence_quality_before,
        "evidence_acquisition_score_after": result.evidence_quality_after,
        "evidence_quality_delta": result.evidence_quality_delta,
        "evidence_quality_upgraded": result.evidence_quality_upgraded,
        "impact_path_validation_before_acquisition": result.impact_path_validation_before,
        "impact_path_validation_after_acquisition": result.impact_path_validation_after,
        "impact_path_validation_upgraded": result.impact_path_validation_upgraded,
        "market_confirmation_upgraded": result.market_confirmation_upgraded,
        "opportunity_score_before_acquisition": result.opportunity_score_before,
        "opportunity_score_after_acquisition": result.opportunity_score_after,
        "opportunity_score_delta": result.opportunity_score_delta,
        "opportunity_level_before_acquisition": result.opportunity_level_before,
        "opportunity_level_after_acquisition": result.opportunity_level_after,
        "opportunity_level_delta": result.opportunity_level_delta,
        "final_upgrade_status": result.final_upgrade_status,
        "initial_opportunity_score": result.initial_opportunity_score,
        "initial_opportunity_level": result.initial_opportunity_level,
        "post_refresh_opportunity_score": result.post_refresh_opportunity_score,
        "post_refresh_opportunity_level": result.post_refresh_opportunity_level,
        "post_refresh_market_confirmation_score": result.post_refresh_market_confirmation_score,
        "post_refresh_market_confirmation_level": result.post_refresh_market_confirmation_level,
        "post_refresh_evidence_quality_score": result.post_refresh_evidence_quality_score,
        "final_opportunity_score": result.final_opportunity_score,
        "final_opportunity_level": result.final_opportunity_level,
        "final_verdict_source": result.final_verdict_source,
        "final_verdict_reason": result.final_verdict_reason,
        "market_data_freshness": result.market_data_freshness,
        "market_reaction_confirmation": result.market_reaction_confirmation,
        "acquisition_upgrade_status": result.acquisition_upgrade_status,
        "acquisition_upgrade_reason": result.acquisition_upgrade_reason,
        "no_upgrade_reason": result.no_upgrade_reason,
        "evidence_acquisition_warnings": result.warnings,
        "evidence_acquisition_results": _evidence_acquisition_result_summary(result),
    }


def _evidence_acquisition_result_summary(result: EvidenceAcquisitionResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "queries_executed": result.queries_executed,
        "accepted": len(result.accepted_evidence),
        "rejected": len(result.rejected_evidence),
        "providers_used": result.providers_used,
        "upgrade_status": result.acquisition_upgrade_status,
        "final_upgrade_status": result.final_upgrade_status,
        "upgrade_reason": result.acquisition_upgrade_reason,
        "no_upgrade_reason": result.no_upgrade_reason,
    }


@dataclass(frozen=True)
class EventEvidenceAcquisitionRunResult:
    hypotheses: tuple[object, ...]
    results: tuple[EvidenceAcquisitionResult, ...]
    path: Path | None = None
    rows_written: int = 0
    status: str = "complete"
    warnings: tuple[str, ...] = ()

    @property
    def attempted(self) -> int:
        return len(self.results)

    @property
    def accepted(self) -> int:
        return sum(1 for result in self.results if result.accepted_evidence)

    @property
    def rejected_only(self) -> int:
        return sum(
            1
            for result in self.results
            if result.rejected_evidence and not result.accepted_evidence
        )

    @property
    def upgraded(self) -> int:
        return sum(1 for result in self.results if result.acquisition_upgrade_status == "upgraded")
