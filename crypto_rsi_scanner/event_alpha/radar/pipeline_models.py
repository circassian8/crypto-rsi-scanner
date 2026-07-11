"""Data models for the Event Alpha Radar pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor
import crypto_rsi_scanner.event_alpha.radar.anomaly_state as event_anomaly_state
import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, RawDiscoveredEvent

RawEventTransform = Callable[[tuple[RawDiscoveredEvent, ...]], Iterable[RawDiscoveredEvent]]
DiscoveryLoader = Callable[[datetime, RawEventTransform | None], EventDiscoveryResult]
ResearchAlertSender = Callable[[list[event_alpha_router.EventAlphaRouteDecision]], Any]
SourceFetchFn = Callable[[str, float], str | bytes]


@dataclass(frozen=True)
class EventAlphaSendResult:
    requested: bool = False
    attempted: bool = False
    success: bool = False
    items_attempted: int = 0
    items_delivered: int = 0
    block_reason: str | None = None
    lane_items_attempted: dict[str, int] = field(default_factory=dict)
    lane_items_delivered: dict[str, int] = field(default_factory=dict)
    would_send_items: int = 0
    heartbeat_due: bool = False
    heartbeat_sent: bool = False
    cooldown_blocks: dict[str, str] = field(default_factory=dict)
    notification_scope: str | None = None
    notification_scope_value: str | None = None
    delivery_records_written: int = 0
    deliveries_delivered: int = 0
    deliveries_partial_delivered: int = 0
    deliveries_failed: int = 0
    deliveries_skipped_duplicate: int = 0
    deliveries_skipped_in_flight: int = 0
    deliveries_blocked: int = 0
    research_review_digest_enabled: bool = False
    research_review_digest_candidates: int = 0
    research_review_digest_would_send: int = 0
    research_review_digest_sent: int = 0
    research_review_digest_block_reason: str | None = None
    preview_rendered_items: int = 0


@dataclass(frozen=True)
class _PipelineCoreFields:
    discovery_result: EventDiscoveryResult
    alerts: list[event_alerts.EventAlertCandidate]
    catalyst_search_result: event_catalyst_search.CatalystSearchRunResult | None
    hypothesis_search_result: event_catalyst_search.CatalystSearchRunResult | None
    anomaly_lifecycle_result: event_anomaly_state.EventAnomalyStateResult | None
    extraction_rows: list[event_llm_extractor.EventLLMExtractionReportRow]
    catalyst_frame_rows: list[event_llm_catalyst_frames.EventLLMCatalystFrameReportRow]
    relationship_rows: list[event_llm_analyzer.EventLLMReportRow]
    watchlist_result: event_watchlist.EventWatchlistRefreshResult | None
    watchlist_monitor_result: event_watchlist_monitor.EventWatchlistMonitorResult | None
    router_result: event_alpha_router.EventAlphaRouterResult | None
    near_miss_result: event_near_miss.EventNearMissRefreshResult | None = None
    evidence_acquisition_result: event_evidence_acquisition.EventEvidenceAcquisitionRunResult | None = None
    impact_hypotheses: tuple[event_impact_hypotheses.EventImpactHypothesis, ...] = ()
    warnings: tuple[str, ...] = ()
    clock_status: dict[str, Any] = field(default_factory=dict)
    cycle_completed: bool = True
    partial_results: bool = False


@dataclass(frozen=True)
class _PipelineSendFields:
    send_requested: bool = False
    send_attempted: bool = False
    send_success: bool = False
    send_items_attempted: int = 0
    send_items_delivered: int = 0
    send_block_reason: str | None = None
    send_lane_items_attempted: dict[str, int] = field(default_factory=dict)
    send_lane_items_delivered: dict[str, int] = field(default_factory=dict)
    send_would_send_items: int = 0
    send_heartbeat_due: bool = False
    send_heartbeat_sent: bool = False
    send_cooldown_blocks: dict[str, str] = field(default_factory=dict)
    notification_scope: str | None = None
    notification_scope_value: str | None = None
    notification_lock_acquired: bool = False
    notification_skipped_due_to_active_lock: bool = False
    notification_stale_lock_recovered: bool = False
    notification_delivery_records_written: int = 0
    notification_deliveries_delivered: int = 0
    notification_deliveries_partial_delivered: int = 0
    notification_deliveries_failed: int = 0
    notification_deliveries_skipped_duplicate: int = 0
    notification_deliveries_skipped_in_flight: int = 0
    notification_deliveries_blocked: int = 0
    research_review_digest_enabled: bool = False
    research_review_digest_candidates: int = 0
    research_review_digest_would_send: int = 0
    research_review_digest_sent: int = 0
    research_review_digest_block_reason: str | None = None
    notification_burn_in: bool = False


@dataclass(frozen=True)
class _PipelineArtifactWriteFields:
    research_card_paths: tuple[Path, ...] = ()
    run_id: str | None = None
    profile: str | None = None
    run_mode: str | None = None
    artifact_namespace: str | None = None
    run_ledger_path: str | None = None
    alert_store_path: str | None = None
    watchlist_state_path: str | None = None
    research_cards_dir: str | None = None
    snapshot_write_attempted: bool = False
    snapshot_write_success: bool = False
    snapshot_rows_written: int = 0
    snapshot_write_block_reason: str | None = None
    candidate_events: int | None = None
    research_candidates: int | None = None
    source_alert_snapshots: int | None = None
    alertable_decisions: int | None = None
    strict_alerts: int | None = None
    hypothesis_store_path: str | None = None
    hypothesis_write_attempted: bool = False
    hypothesis_write_success: bool = False
    hypothesis_rows_written: int = 0
    hypothesis_write_block_reason: str | None = None
    incident_store_path: str | None = None
    incident_write_attempted: bool = False
    incident_write_success: bool = False
    incident_rows_written: int = 0
    incident_write_block_reason: str | None = None
    core_opportunity_store_path: str | None = None
    core_opportunity_write_attempted: bool = False
    core_opportunity_write_success: bool = False
    core_opportunity_rows_written: int = 0
    core_opportunity_write_block_reason: str | None = None
    current_generation_core_rows: int | None = None
    current_generation_visible_core_rows: int | None = None
    cumulative_store_rows: int | None = None
    preview_rendered_items: int | None = None


@dataclass(frozen=True)
class _PipelineCryptoPanicFields:
    cryptopanic_configured: bool = False
    cryptopanic_attempted: bool = False
    cryptopanic_requests_used: int = 0
    cryptopanic_request_cache_hits: int = 0
    cryptopanic_request_cache_misses: int = 0
    cryptopanic_requests_deduped: int = 0
    cryptopanic_invalid_currency_requests_skipped: int = 0
    cryptopanic_results: int = 0
    cryptopanic_accepted_evidence: int = 0
    cryptopanic_rejected_evidence: int = 0
    cryptopanic_raw_provider_status: str = "not_observed"
    cryptopanic_provider_status: str = "not_observed"
    cryptopanic_effective_provider_status: str = "not_observed"
    cryptopanic_successful_requests: int = 0
    cryptopanic_failed_requests: int = 0
    cryptopanic_stale_backoff_reconciled_after_success: bool = False
    cryptopanic_skip_reason: str | None = None


@dataclass(frozen=True)
class _PipelineAlertPhase:
    alerts: list[event_alerts.EventAlertCandidate]
    relationship_rows: list[event_llm_analyzer.EventLLMReportRow]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _PipelineHypothesisPhase:
    impact_hypotheses: tuple[event_impact_hypotheses.EventImpactHypothesis, ...]
    hypothesis_search_result: event_catalyst_search.CatalystSearchRunResult | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _PipelineNearMissPhase:
    impact_hypotheses: tuple[event_impact_hypotheses.EventImpactHypothesis, ...]
    near_miss_result: event_near_miss.EventNearMissRefreshResult | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _PipelineEvidencePhase:
    impact_hypotheses: tuple[event_impact_hypotheses.EventImpactHypothesis, ...]
    evidence_acquisition_result: event_evidence_acquisition.EventEvidenceAcquisitionRunResult | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _PipelineWatchlistRoutePhase:
    watchlist_result: event_watchlist.EventWatchlistRefreshResult | None = None
    watchlist_monitor_result: event_watchlist_monitor.EventWatchlistMonitorResult | None = None
    router_result: event_alpha_router.EventAlphaRouterResult | None = None
    warnings: tuple[str, ...] = ()


@dataclass
class _OperatingCycleContext:
    observed: datetime
    warnings: list[str] = field(default_factory=list)
    catalyst_search_result: event_catalyst_search.CatalystSearchRunResult | None = None
    extraction_rows: list[event_llm_extractor.EventLLMExtractionReportRow] = field(default_factory=list)
    catalyst_frame_rows: list[event_llm_catalyst_frames.EventLLMCatalystFrameReportRow] = field(default_factory=list)
    source_raw_events: tuple[RawDiscoveredEvent, ...] = ()
    llm_transform: RawEventTransform | None = None
    catalyst_frame_transform: RawEventTransform | None = None
    relationship_provider: object | None = None
    relationship_cfg: event_llm_analyzer.EventLLMConfig | None = None


class _PipelineDiscoveryProperties:
    @property
    def raw_events(self) -> int:
        return len(self.discovery_result.raw_events)

    @property
    def catalyst_queries(self) -> int:
        return len(self.catalyst_search_result.queries) if self.catalyst_search_result else 0

    @property
    def catalyst_results(self) -> int:
        return len(self.catalyst_search_result.result_events) if self.catalyst_search_result else 0

    @property
    def catalyst_search_skip_reasons(self) -> dict[str, int]:
        if self.catalyst_search_result is None:
            return {}
        return {
            str(key): int(value)
            for key, value in (self.catalyst_search_result.skip_reasons or {}).items()
            if str(key)
        }

    @property
    def hypothesis_search_skip_reasons(self) -> dict[str, int]:
        if self.hypothesis_search_result is None:
            return {}
        return {
            str(key): int(value)
            for key, value in (self.hypothesis_search_result.skip_reasons or {}).items()
            if str(key)
        }

    @property
    def anomaly_lifecycle_entries(self) -> int:
        return len(self.anomaly_lifecycle_result.entries) if self.anomaly_lifecycle_result else 0

    @property
    def extractions(self) -> int:
        return len([row for row in self.extraction_rows if row.extraction is not None])

    @property
    def catalyst_frame_analyses(self) -> int:
        return len([row for row in self.catalyst_frame_rows if row.analysis is not None])

    @property
    def catalyst_frame_validations_applied(self) -> int:
        return len([
            raw for raw in self.discovery_result.raw_events
            if raw.raw_json and raw.raw_json.get("llm_catalyst_frame_validation")
        ])

    @property
    def extraction_hint_events(self) -> int:
        return len([
            raw for raw in self.discovery_result.raw_events
            if raw.raw_json and raw.raw_json.get("llm_extraction")
        ])

    @property
    def candidates(self) -> int:
        return len(self.discovery_result.candidates)

    @property
    def clusters(self) -> int:
        return len(event_graph.build_event_clusters(self.discovery_result))


class _PipelineHypothesisWatchlistProperties:
    @property
    def hypotheses_validated(self) -> int:
        return len([
            item for item in self.impact_hypotheses
            if item.status == event_impact_hypotheses.HypothesisStatus.VALIDATED.value
        ])

    @property
    def hypothesis_search_queries(self) -> int:
        if self.hypothesis_search_result is not None:
            return len(self.hypothesis_search_result.queries)
        return len({query for item in self.impact_hypotheses for query in item.search_queries})

    @property
    def hypothesis_search_results(self) -> int:
        if self.hypothesis_search_result is not None:
            return len(self.hypothesis_search_result.result_events)
        return len([
            item for item in self.impact_hypotheses
            if item.status in {
                event_impact_hypotheses.HypothesisStatus.VALIDATION_EVIDENCE_FOUND.value,
                event_impact_hypotheses.HypothesisStatus.VALIDATED.value,
            }
        ])

    @property
    def hypothesis_promotions(self) -> int:
        if self.watchlist_result is None:
            return 0
        return len([
            entry for entry in self.watchlist_result.entries
            if entry.relationship_type == "impact_hypothesis"
            and entry.state == event_watchlist.EventWatchlistState.RADAR.value
        ])

    @property
    def watchlist_entries(self) -> int:
        return len(self.watchlist_result.entries) if self.watchlist_result else 0

    @property
    def watchlist_escalations(self) -> int:
        return len(self.watchlist_result.alert_entries) if self.watchlist_result else 0

    @property
    def watchlist_monitor_material_updates(self) -> int:
        if self.watchlist_monitor_result is None:
            return 0
        return len([row for row in self.watchlist_monitor_result.rows if row.material_update])

    @property
    def watchlist_monitor_active_entries(self) -> int:
        return self.watchlist_monitor_result.active_entries if self.watchlist_monitor_result else 0


class _PipelineRoutingEvidenceProperties:
    @property
    def routed(self) -> int:
        return len(self.router_result.decisions) if self.router_result else 0

    @property
    def alertable(self) -> int:
        return len(self.router_result.alertable_decisions) if self.router_result else 0

    @property
    def near_misses(self) -> int:
        return len(self.near_miss_result.near_misses) if self.near_miss_result else 0

    @property
    def near_miss_upgrades(self) -> int:
        return self.near_miss_result.upgraded_count if self.near_miss_result else 0

    @property
    def evidence_acquisition_attempted(self) -> int:
        return self.evidence_acquisition_result.attempted if self.evidence_acquisition_result else 0

    @property
    def evidence_acquisition_accepted(self) -> int:
        return self.evidence_acquisition_result.accepted if self.evidence_acquisition_result else 0

    @property
    def evidence_acquisition_rejected_only(self) -> int:
        return self.evidence_acquisition_result.rejected_only if self.evidence_acquisition_result else 0

    @property
    def evidence_acquisition_upgraded(self) -> int:
        return self.evidence_acquisition_result.upgraded if self.evidence_acquisition_result else 0


@dataclass(frozen=True)
class EventAlphaPipelineResult(
    _PipelineRoutingEvidenceProperties,
    _PipelineHypothesisWatchlistProperties,
    _PipelineDiscoveryProperties,
    _PipelineCryptoPanicFields,
    _PipelineArtifactWriteFields,
    _PipelineSendFields,
    _PipelineCoreFields,
):
    """Compatibility aggregate for Event Alpha pipeline outputs."""
