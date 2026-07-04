"""Unified research-only Event Alpha Radar pipeline orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ... import (
    event_alerts,
    event_alpha_router,
    event_anomaly_state,
    event_catalyst_frames,
    event_catalyst_frame_validator,
    event_llm_catalyst_frames,
    event_catalyst_search,
    event_evidence_acquisition,
    event_graph,
    event_impact_hypotheses,
    event_llm_analyzer,
    event_llm_extractor,
    event_near_miss,
    event_source_enrichment,
    event_watchlist,
    event_watchlist_enrichment,
    event_watchlist_market,
    event_watchlist_monitor,
)
from ...event_alpha.outcomes import priors as event_alpha_priors
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


def run_event_alpha_pipeline(
    discovery_result: EventDiscoveryResult,
    *,
    alert_cfg: event_alerts.EventAlertConfig | None = None,
    now: datetime | None = None,
    extraction_rows: Iterable[event_llm_extractor.EventLLMExtractionReportRow] = (),
    catalyst_frame_rows: Iterable[event_llm_catalyst_frames.EventLLMCatalystFrameReportRow] = (),
    catalyst_search_result: event_catalyst_search.CatalystSearchRunResult | None = None,
    hypothesis_search_provider: event_catalyst_search.CatalystSearchProvider | None = None,
    hypothesis_search_cfg: event_catalyst_search.EventImpactHypothesisSearchConfig | None = None,
    source_raw_events: Iterable[RawDiscoveredEvent] = (),
    relationship_provider: object | None = None,
    relationship_cfg: event_llm_analyzer.EventLLMConfig | None = None,
    watchlist_cfg: event_watchlist.EventWatchlistConfig | None = None,
    router_cfg: event_alpha_router.EventAlphaRouterConfig | None = None,
    priors_cfg: event_alpha_priors.EventAlphaPriorsConfig | None = None,
    refresh_watchlist: bool = False,
    route: bool = False,
    watchlist_monitor_enabled: bool = False,
    watchlist_monitor_market_rows: Iterable[dict[str, Any]] = (),
    watchlist_monitor_market_source: str = "cycle",
    watchlist_monitor_market_provider: event_watchlist_market.EventWatchlistMarketProvider | None = None,
    watchlist_monitor_targeted_lookup: bool = False,
    watchlist_monitor_max_assets: int = 50,
    watchlist_monitor_market_cache_ttl_seconds: int = 900,
    watchlist_monitor_derivatives_source: str = "cycle",
    watchlist_monitor_supply_source: str = "cycle",
    watchlist_monitor_derivatives_rows: Iterable[dict[str, Any]] = (),
    watchlist_monitor_supply_rows: Iterable[dict[str, Any]] = (),
    watchlist_monitor_enrichment_max_assets: int = 50,
    watchlist_monitor_route_updates: bool = True,
    near_miss_cfg: event_near_miss.EventNearMissConfig | None = None,
    near_miss_market_rows: Iterable[dict[str, Any]] = (),
    near_miss_market_provider: event_watchlist_market.EventWatchlistMarketProvider | None = None,
    near_miss_derivatives_rows: Iterable[dict[str, Any]] = (),
    near_miss_supply_rows: Iterable[dict[str, Any]] = (),
    evidence_acquisition_cfg: event_evidence_acquisition.EvidenceAcquisitionConfig | None = None,
    evidence_acquisition_provider: event_evidence_acquisition.EvidenceSearchProvider | None = None,
    evidence_acquisition_providers_by_hint: dict[str, event_evidence_acquisition.EvidenceSearchProvider | None] | None = None,
    evidence_acquisition_context: dict[str, Any] | None = None,
    extra_warnings: Iterable[str] = (),
) -> EventAlphaPipelineResult:
    """Run the research-only Event Alpha pipeline over a discovery result."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    alert_cfg = alert_cfg or event_alerts.EventAlertConfig()
    warnings: list[str] = list(extra_warnings)
    extraction_rows_list = list(extraction_rows)
    catalyst_frame_rows_list = list(catalyst_frame_rows)
    warnings.extend(_llm_budget_warnings(extraction_rows_list, label="extractor"))
    warnings.extend(_llm_budget_warnings(catalyst_frame_rows_list, label="catalyst_frame"))
    alerts = event_alerts.build_event_alert_candidates(discovery_result, cfg=alert_cfg, now=observed)
    relationship_rows: list[event_llm_analyzer.EventLLMReportRow] = []
    if relationship_provider is not None and relationship_cfg is not None:
        relationship_rows = event_llm_analyzer.analyze_event_candidates(
            discovery_result,
            alerts,
            relationship_provider,
            cfg=relationship_cfg,
        )
        alerts = event_alerts.apply_llm_advisory(
            alerts,
            relationship_rows,
            alert_cfg,
            enabled=relationship_cfg.mode == "advisory",
        )
        warnings.extend(_llm_budget_warnings(relationship_rows, label="relationship"))
    if priors_cfg is not None:
        alerts = event_alpha_priors.apply_priors_to_alerts(alerts, cfg=priors_cfg, alert_cfg=alert_cfg)

    clusters = event_graph.build_event_clusters(discovery_result)
    impact_hypotheses = event_impact_hypotheses.generate_impact_hypotheses(
        discovery_result,
        raw_events=source_raw_events,
        clusters=clusters,
        extraction_rows=extraction_rows_list,
        now=observed,
    )
    if catalyst_search_result is not None:
        validation_raw = tuple(result.raw_event for result in catalyst_search_result.result_events)
        impact_hypotheses = event_impact_hypotheses.validate_hypotheses_with_raw_events(
            impact_hypotheses,
            validation_raw,
        )
    hypothesis_search_result: event_catalyst_search.CatalystSearchRunResult | None = None
    if hypothesis_search_cfg is not None and hypothesis_search_cfg.enabled:
        if hypothesis_search_provider is None:
            warnings.append("hypothesis search skipped: no provider available")
            hypothesis_search_result = event_catalyst_search.CatalystSearchRunResult(
                provider="hypothesis_search",
                warnings=("hypothesis search skipped: no provider available",),
                skip_reasons={"provider_unavailable": 1},
            )
        else:
            hypothesis_search_result = event_catalyst_search.run_hypothesis_search(
                impact_hypotheses,
                hypothesis_search_provider,
                cfg=hypothesis_search_cfg,
                now=observed,
            )
            warnings.extend(f"hypothesis search: {warning}" for warning in hypothesis_search_result.warnings)
            impact_hypotheses = event_impact_hypotheses.attach_hypothesis_search_samples(
                impact_hypotheses,
                hypothesis_search_result,
            )
            discovery_hint_raw = tuple(
                result.raw_event
                for result in hypothesis_search_result.rejected_result_events
                if str(getattr(getattr(result, "query", None), "query_type", "") or "") == "candidate_discovery"
            )
            validation_raw = tuple(result.raw_event for result in hypothesis_search_result.result_events) + discovery_hint_raw
            impact_hypotheses = event_impact_hypotheses.validate_hypotheses_with_raw_events(
                impact_hypotheses,
                validation_raw,
            )

    near_miss_result: event_near_miss.EventNearMissRefreshResult | None = None
    if near_miss_cfg is not None and near_miss_cfg.enabled:
        near_miss_result = event_near_miss.refresh_near_miss_hypotheses(
            impact_hypotheses,
            cfg=near_miss_cfg,
            market_rows=near_miss_market_rows or watchlist_monitor_market_rows,
            targeted_market_provider=near_miss_market_provider,
            derivatives_rows=near_miss_derivatives_rows or watchlist_monitor_derivatives_rows,
            supply_rows=near_miss_supply_rows or watchlist_monitor_supply_rows,
            now=observed,
        )
        impact_hypotheses = near_miss_result.hypotheses
        warnings.extend(f"near miss: {warning}" for warning in near_miss_result.warnings)

    evidence_acquisition_result: event_evidence_acquisition.EventEvidenceAcquisitionRunResult | None = None
    if evidence_acquisition_cfg is not None and evidence_acquisition_cfg.enabled:
        evidence_acquisition_result = event_evidence_acquisition.run_evidence_acquisition(
            impact_hypotheses,
            near_misses=near_miss_result.near_misses if near_miss_result else (),
            provider=evidence_acquisition_provider,
            providers_by_hint=evidence_acquisition_providers_by_hint or {},
            cfg=evidence_acquisition_cfg,
            now=observed,
            run_context=evidence_acquisition_context or {},
        )
        impact_hypotheses = tuple(
            item
            for item in evidence_acquisition_result.hypotheses
            if isinstance(item, event_impact_hypotheses.EventImpactHypothesis)
        )
        warnings.extend(f"evidence acquisition: {warning}" for warning in evidence_acquisition_result.warnings)

    anomaly_lifecycle_result = (
        event_anomaly_state.build_anomaly_lifecycle(
            source_raw_events or discovery_result.raw_events,
            catalyst_search_result,
            alerts,
            now=observed,
        )
        if catalyst_search_result is not None
        else None
    )

    watchlist_result: event_watchlist.EventWatchlistRefreshResult | None = None
    watchlist_read_result: event_watchlist.EventWatchlistReadResult | None = None
    if refresh_watchlist:
        if watchlist_cfg is None or not watchlist_cfg.enabled:
            warnings.append("watchlist refresh skipped: RSI_EVENT_WATCHLIST_ENABLED is not enabled")
        else:
            watchlist_result = event_watchlist.refresh_watchlist(alerts, cfg=watchlist_cfg, now=observed)
            hypothesis_watchlist = event_watchlist.refresh_hypothesis_watchlist(
                impact_hypotheses,
                cfg=watchlist_cfg,
                now=observed,
            )
            watchlist_result = _combine_watchlist_results(watchlist_result, hypothesis_watchlist)

    watchlist_monitor_result: event_watchlist_monitor.EventWatchlistMonitorResult | None = None
    if watchlist_monitor_enabled:
        if watchlist_cfg is None or not watchlist_cfg.enabled:
            warnings.append("watchlist monitor skipped: RSI_EVENT_WATCHLIST_ENABLED is not enabled")
        else:
            state_path = watchlist_cfg.state_path or Path("event_watchlist_state.jsonl")
            watchlist_read_result = event_watchlist.load_watchlist(state_path)
            market_source_result = event_watchlist_market.market_rows_for_watchlist(
                watchlist_read_result,
                source=watchlist_monitor_market_source,
                fixture_rows=watchlist_monitor_market_rows,
                cycle_rows=watchlist_monitor_market_rows,
                discovery_result=discovery_result,
                targeted_lookup=watchlist_monitor_targeted_lookup,
                targeted_provider=watchlist_monitor_market_provider,
                max_assets=watchlist_monitor_max_assets,
                cache_ttl_seconds=watchlist_monitor_market_cache_ttl_seconds,
                now=observed,
            )
            warnings.extend(f"watchlist market: {warning}" for warning in market_source_result.warnings)
            enrichment_result = event_watchlist_enrichment.enrichment_for_watchlist(
                watchlist_read_result,
                derivatives_source=watchlist_monitor_derivatives_source,
                supply_source=watchlist_monitor_supply_source,
                derivatives_rows=watchlist_monitor_derivatives_rows,
                supply_rows=watchlist_monitor_supply_rows,
                max_assets=watchlist_monitor_enrichment_max_assets,
            )
            warnings.extend(f"watchlist enrichment: {warning}" for warning in enrichment_result.warnings)
            watchlist_monitor_result = event_watchlist_monitor.monitor_watchlist(
                watchlist_read_result,
                market_rows=market_source_result.rows,
                derivatives_by_asset=enrichment_result.derivatives,
                supply_by_asset=enrichment_result.supply,
                now=observed,
            )
            watchlist_read_result = event_watchlist_monitor.apply_monitor_updates_to_watchlist(
                watchlist_read_result,
                watchlist_monitor_result,
                route_updates=watchlist_monitor_route_updates,
                score_jump_threshold=(router_cfg.score_jump_threshold if router_cfg else 10),
            )

    router_result: event_alpha_router.EventAlphaRouterResult | None = None
    if route:
        if watchlist_cfg is None:
            warnings.append("router skipped: no watchlist config supplied")
        elif not watchlist_cfg.enabled:
            warnings.append("router skipped: RSI_EVENT_WATCHLIST_ENABLED is not enabled")
        else:
            read_result = watchlist_read_result or event_watchlist.load_watchlist(
                watchlist_cfg.state_path or Path("event_watchlist_state.jsonl")
            )
            router_result = event_alpha_router.route_watchlist(read_result, cfg=router_cfg)

    return EventAlphaPipelineResult(
        discovery_result=discovery_result,
        alerts=alerts,
        catalyst_search_result=catalyst_search_result,
        hypothesis_search_result=hypothesis_search_result,
        anomaly_lifecycle_result=anomaly_lifecycle_result,
        extraction_rows=extraction_rows_list,
        catalyst_frame_rows=catalyst_frame_rows_list,
        relationship_rows=relationship_rows,
        watchlist_result=watchlist_result,
        watchlist_monitor_result=watchlist_monitor_result,
        router_result=router_result,
        near_miss_result=near_miss_result,
        evidence_acquisition_result=evidence_acquisition_result,
        impact_hypotheses=impact_hypotheses,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def run_event_alpha_operating_cycle(
    *,
    load_discovery_result: DiscoveryLoader,
    alert_cfg: event_alerts.EventAlertConfig | None = None,
    now: datetime | None = None,
    with_llm: bool = False,
    extraction_provider: object | None = None,
    extraction_cfg: event_llm_extractor.EventLLMExtractorConfig | None = None,
    catalyst_frame_provider: object | None = None,
    catalyst_frame_cfg: event_llm_catalyst_frames.EventLLMCatalystFrameConfig | None = None,
    catalyst_search_provider: event_catalyst_search.CatalystSearchProvider | None = None,
    catalyst_search_cfg: event_catalyst_search.EventCatalystSearchConfig | None = None,
    hypothesis_search_provider: event_catalyst_search.CatalystSearchProvider | None = None,
    hypothesis_search_cfg: event_catalyst_search.EventImpactHypothesisSearchConfig | None = None,
    source_enrichment_cfg: event_source_enrichment.EventSourceEnrichmentConfig | None = None,
    source_enrichment_fetch_fn: SourceFetchFn | None = None,
    relationship_provider: object | None = None,
    relationship_cfg: event_llm_analyzer.EventLLMConfig | None = None,
    watchlist_cfg: event_watchlist.EventWatchlistConfig | None = None,
    router_cfg: event_alpha_router.EventAlphaRouterConfig | None = None,
    priors_cfg: event_alpha_priors.EventAlphaPriorsConfig | None = None,
    refresh_watchlist: bool = True,
    route: bool = True,
    watchlist_monitor_enabled: bool = False,
    watchlist_monitor_market_rows: Iterable[dict[str, Any]] = (),
    watchlist_monitor_market_source: str = "cycle",
    watchlist_monitor_market_provider: event_watchlist_market.EventWatchlistMarketProvider | None = None,
    watchlist_monitor_targeted_lookup: bool = False,
    watchlist_monitor_max_assets: int = 50,
    watchlist_monitor_market_cache_ttl_seconds: int = 900,
    watchlist_monitor_derivatives_source: str = "cycle",
    watchlist_monitor_supply_source: str = "cycle",
    watchlist_monitor_derivatives_rows: Iterable[dict[str, Any]] = (),
    watchlist_monitor_supply_rows: Iterable[dict[str, Any]] = (),
    watchlist_monitor_enrichment_max_assets: int = 50,
    watchlist_monitor_route_updates: bool = True,
    near_miss_cfg: event_near_miss.EventNearMissConfig | None = None,
    near_miss_market_rows: Iterable[dict[str, Any]] = (),
    near_miss_market_provider: event_watchlist_market.EventWatchlistMarketProvider | None = None,
    near_miss_derivatives_rows: Iterable[dict[str, Any]] = (),
    near_miss_supply_rows: Iterable[dict[str, Any]] = (),
    evidence_acquisition_cfg: event_evidence_acquisition.EvidenceAcquisitionConfig | None = None,
    evidence_acquisition_provider: event_evidence_acquisition.EvidenceSearchProvider | None = None,
    evidence_acquisition_providers_by_hint: dict[str, event_evidence_acquisition.EvidenceSearchProvider | None] | None = None,
    evidence_acquisition_context: dict[str, Any] | None = None,
    send: bool = False,
    send_callback: ResearchAlertSender | None = None,
) -> EventAlphaPipelineResult:
    """Run the coherent Event Alpha research cycle from source loading onward.

    The caller supplies the source/discovery loader so config-specific provider
    wiring can stay in ``scanner.py``. This function owns the cycle ordering:
    optional raw-event extraction, deterministic discovery, alert/playbook
    ranking, optional relationship advisory, watchlist refresh, router
    decisions, and optional research digest callback.
    """
    observed = _as_utc(now or datetime.now(timezone.utc))
    warnings: list[str] = []
    catalyst_search_result: event_catalyst_search.CatalystSearchRunResult | None = None
    extraction_rows: list[event_llm_extractor.EventLLMExtractionReportRow] = []
    catalyst_frame_rows: list[event_llm_catalyst_frames.EventLLMCatalystFrameReportRow] = []
    source_raw_events: tuple[RawDiscoveredEvent, ...] = ()
    llm_transform: RawEventTransform | None = None
    catalyst_frame_transform: RawEventTransform | None = None
    relationship_provider_to_use = None
    relationship_cfg_to_use = None

    if with_llm:
        if extraction_cfg is not None and extraction_provider is not None:
            mode = extraction_cfg.mode.strip().lower()
            if mode == "shadow":
                def _shadow_llm_extractions(
                    raw_events: tuple[RawDiscoveredEvent, ...],
                ) -> tuple[RawDiscoveredEvent, ...]:
                    nonlocal extraction_rows
                    extraction_rows = event_llm_extractor.analyze_raw_events(
                        raw_events,
                        extraction_provider,
                        cfg=extraction_cfg,
                    )
                    return tuple(raw_events)

                llm_transform = _shadow_llm_extractions
            elif mode == "advisory":
                def _enrich_with_llm_extractions(
                    raw_events: tuple[RawDiscoveredEvent, ...],
                ) -> tuple[RawDiscoveredEvent, ...]:
                    nonlocal extraction_rows
                    extraction_rows = event_llm_extractor.analyze_raw_events(
                        raw_events,
                        extraction_provider,
                        cfg=extraction_cfg,
                    )
                    return event_llm_extractor.enrich_raw_events_with_extractions(raw_events, extraction_rows)

                llm_transform = _enrich_with_llm_extractions
            elif mode in {"off", "disabled", "none"}:
                warnings.append("Event LLM extractor skipped: mode is off")
            else:
                warnings.append(
                    f"Event LLM extractor skipped: unsupported mode {extraction_cfg.mode!r}; use shadow or advisory"
                )
        elif extraction_cfg is not None:
            warnings.append("Event LLM extractor skipped: no extraction provider available")

        if catalyst_frame_cfg is not None and catalyst_frame_cfg.enabled:
            if catalyst_frame_provider is None:
                warnings.append("Event LLM catalyst-frame analysis skipped: no provider available")
                provider_name = str(catalyst_frame_cfg.provider or "").strip().lower()
                provider_skip_reason = "missing_api_key" if provider_name == "openai" else "profile_disabled"
                def _mark_missing_llm_catalyst_frames(
                    raw_events: tuple[RawDiscoveredEvent, ...],
                ) -> tuple[RawDiscoveredEvent, ...]:
                    return tuple(
                        _raw_with_catalyst_frame_status(
                            raw,
                            status="missing_required_frame_analysis" if event_llm_catalyst_frames.frame_requirement_for_raw(raw)[0] else "not_required",
                            skip_reason=provider_skip_reason,
                        )
                        for raw in raw_events
                    )

                catalyst_frame_transform = _mark_missing_llm_catalyst_frames
            else:
                def _enrich_with_llm_catalyst_frames(
                    raw_events: tuple[RawDiscoveredEvent, ...],
                ) -> tuple[RawDiscoveredEvent, ...]:
                    nonlocal catalyst_frame_rows
                    catalyst_frame_rows = event_llm_catalyst_frames.analyze_raw_events(
                        raw_events,
                        catalyst_frame_provider,
                        cfg=catalyst_frame_cfg,
                    )
                    enriched: list[RawDiscoveredEvent] = []
                    analyses_by_raw_id = {
                        row.raw_event.raw_id: row.analysis
                        for row in catalyst_frame_rows
                        if row.analysis is not None
                    }
                    row_warnings_by_raw_id = {
                        row.raw_event.raw_id: tuple(row.warnings)
                        for row in catalyst_frame_rows
                    }
                    selected_raw_ids = {row.raw_event.raw_id for row in catalyst_frame_rows}
                    if not selected_raw_ids and any(
                        event_llm_catalyst_frames.frame_requirement_for_raw(raw)[0]
                        for raw in raw_events
                    ):
                        warnings.append("Event LLM catalyst-frame analysis skipped: no required rows selected")
                    for raw in raw_events:
                        required, required_reason = event_llm_catalyst_frames.frame_requirement_for_raw(raw)
                        analysis = analyses_by_raw_id.get(raw.raw_id)
                        if analysis is None:
                            row_warnings = row_warnings_by_raw_id.get(raw.raw_id, ())
                            status = "missing_required_frame_analysis" if required else "not_required"
                            skip_reason = _catalyst_frame_skip_reason(
                                row_warnings,
                                selected=raw.raw_id in selected_raw_ids,
                                required=required,
                            )
                            enriched.append(_raw_with_catalyst_frame_status(
                                raw,
                                status=status,
                                required=required,
                                required_reason=required_reason,
                                skip_reason=skip_reason,
                                warnings=row_warnings,
                            ))
                            continue
                        rule_frames = event_catalyst_frames.build_catalyst_frames((raw,))
                        validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(
                            analysis,
                            (raw,),
                            rule_frames=rule_frames,
                        )
                        status = "unresolved" if validation.resolution == event_catalyst_frame_validator.RESOLUTION_UNRESOLVED else "validated"
                        enriched.append(_raw_with_catalyst_frame_status(
                            event_catalyst_frame_validator.apply_validation_to_raw_event(
                            raw,
                            analysis,
                            validation,
                            ),
                            status=status,
                            required=required,
                            required_reason=required_reason,
                            skip_reason=None,
                            warnings=validation.frame_warnings,
                        ))
                    return tuple(enriched)

                catalyst_frame_transform = _enrich_with_llm_catalyst_frames
        elif catalyst_frame_cfg is not None and not catalyst_frame_cfg.enabled:
            def _mark_disabled_llm_catalyst_frames(
                raw_events: tuple[RawDiscoveredEvent, ...],
            ) -> tuple[RawDiscoveredEvent, ...]:
                return tuple(
                    _raw_with_catalyst_frame_status(
                        raw,
                        status="missing_required_frame_analysis" if event_llm_catalyst_frames.frame_requirement_for_raw(raw)[0] else "not_required",
                        skip_reason="disabled",
                    )
                    for raw in raw_events
                )

            catalyst_frame_transform = _mark_disabled_llm_catalyst_frames
        if relationship_cfg is not None and relationship_provider is not None:
            if relationship_cfg.mode in {"shadow", "advisory"}:
                relationship_provider_to_use = relationship_provider
                relationship_cfg_to_use = relationship_cfg
            else:
                warnings.append(
                    f"Event LLM mode {relationship_cfg.mode!r} is not supported; use shadow or advisory"
                )
        elif relationship_cfg is not None:
            warnings.append("Event LLM relationship analysis skipped: no relationship provider available")

    def _combined_raw_event_transform(
        raw_events: tuple[RawDiscoveredEvent, ...],
    ) -> tuple[RawDiscoveredEvent, ...]:
        nonlocal catalyst_search_result, source_raw_events
        source_raw_events = tuple(raw_events)
        transformed = tuple(raw_events)
        if catalyst_search_cfg is not None and catalyst_search_cfg.enabled:
            if catalyst_search_provider is None:
                warnings.append("catalyst search skipped: no provider available")
                catalyst_search_result = event_catalyst_search.CatalystSearchRunResult(
                    provider=catalyst_search_cfg.provider,
                    warnings=("catalyst search skipped: no provider available",),
                    skip_reasons={"provider_unavailable": 1},
                )
            else:
                catalyst_search_result = event_catalyst_search.run_catalyst_search(
                    transformed,
                    catalyst_search_provider,
                    cfg=catalyst_search_cfg,
                    now=observed,
                )
                warnings.extend(f"catalyst search: {warning}" for warning in catalyst_search_result.warnings)
                transformed = _merge_catalyst_search_events(transformed, catalyst_search_result)
        if source_enrichment_cfg is not None and source_enrichment_cfg.enabled:
            transformed = _enrich_source_events(
                transformed,
                cfg=source_enrichment_cfg,
                fetch_fn=source_enrichment_fetch_fn,
                warnings=warnings,
            )
        if llm_transform is not None:
            transformed = tuple(llm_transform(transformed))
        if catalyst_frame_transform is not None:
            transformed = tuple(catalyst_frame_transform(transformed))
        source_raw_events = tuple(transformed)
        return transformed

    raw_event_transform: RawEventTransform | None = None
    if (
        llm_transform is not None
        or catalyst_frame_transform is not None
        or (catalyst_search_cfg is not None and catalyst_search_cfg.enabled)
        or (source_enrichment_cfg is not None and source_enrichment_cfg.enabled)
    ):
        raw_event_transform = _combined_raw_event_transform

    discovery_result = load_discovery_result(observed, raw_event_transform)
    warnings.extend(str(warning) for warning in getattr(discovery_result, "warnings", ()) or () if str(warning))
    result = run_event_alpha_pipeline(
        discovery_result,
        alert_cfg=alert_cfg,
        now=observed,
        catalyst_search_result=catalyst_search_result,
        hypothesis_search_provider=hypothesis_search_provider,
        hypothesis_search_cfg=hypothesis_search_cfg,
        source_raw_events=source_raw_events,
        extraction_rows=extraction_rows,
        catalyst_frame_rows=catalyst_frame_rows,
        relationship_provider=relationship_provider_to_use,
        relationship_cfg=relationship_cfg_to_use,
        watchlist_cfg=watchlist_cfg,
        router_cfg=router_cfg,
        priors_cfg=priors_cfg,
        refresh_watchlist=refresh_watchlist,
        route=route,
        watchlist_monitor_enabled=watchlist_monitor_enabled,
        watchlist_monitor_market_rows=watchlist_monitor_market_rows,
        watchlist_monitor_market_source=watchlist_monitor_market_source,
        watchlist_monitor_market_provider=watchlist_monitor_market_provider,
        watchlist_monitor_targeted_lookup=watchlist_monitor_targeted_lookup,
        watchlist_monitor_max_assets=watchlist_monitor_max_assets,
        watchlist_monitor_market_cache_ttl_seconds=watchlist_monitor_market_cache_ttl_seconds,
        watchlist_monitor_derivatives_source=watchlist_monitor_derivatives_source,
        watchlist_monitor_supply_source=watchlist_monitor_supply_source,
        watchlist_monitor_derivatives_rows=watchlist_monitor_derivatives_rows,
        watchlist_monitor_supply_rows=watchlist_monitor_supply_rows,
        watchlist_monitor_enrichment_max_assets=watchlist_monitor_enrichment_max_assets,
        watchlist_monitor_route_updates=watchlist_monitor_route_updates,
        near_miss_cfg=near_miss_cfg,
        near_miss_market_rows=near_miss_market_rows or watchlist_monitor_market_rows,
        near_miss_market_provider=near_miss_market_provider,
        near_miss_derivatives_rows=near_miss_derivatives_rows or watchlist_monitor_derivatives_rows,
        near_miss_supply_rows=near_miss_supply_rows or watchlist_monitor_supply_rows,
        evidence_acquisition_cfg=evidence_acquisition_cfg,
        evidence_acquisition_provider=evidence_acquisition_provider,
        evidence_acquisition_providers_by_hint=evidence_acquisition_providers_by_hint,
        evidence_acquisition_context=evidence_acquisition_context,
        extra_warnings=warnings,
    )
    if send:
        if send_callback is None:
            warnings = [*result.warnings, "research send skipped: no send callback supplied"]
            return _with_send_result(
                result,
                EventAlphaSendResult(requested=True, block_reason="no send callback supplied"),
                warnings=warnings,
            )
        if result.router_result is None:
            warnings = [*result.warnings, "research send skipped: no router decisions available"]
            return _with_send_result(
                result,
                EventAlphaSendResult(requested=True, block_reason="no router decisions available"),
                warnings=warnings,
            )
        decisions = result.router_result.alertable_decisions
        if not decisions:
            warnings = [*result.warnings, "research send skipped: no alertable route decisions"]
            return _with_send_result(
                result,
                EventAlphaSendResult(requested=True, block_reason="no alertable route decisions"),
                warnings=warnings,
            )
        try:
            raw_send_result = send_callback(decisions)
            send_result = _normalize_send_result(raw_send_result, decisions)
        except Exception as exc:  # pragma: no cover - defensive fail-soft guard
            warnings = [*result.warnings, f"research send failed: {exc}"]
            return _with_send_result(
                result,
                EventAlphaSendResult(
                    requested=True,
                    attempted=True,
                    success=False,
                    items_attempted=len(decisions),
                    items_delivered=0,
                    block_reason=str(exc),
                ),
                warnings=warnings,
            )
        return _with_send_result(result, send_result)
    return _with_send_result(result, EventAlphaSendResult(requested=False))


def _with_send_result(
    result: EventAlphaPipelineResult,
    send_result: EventAlphaSendResult,
    *,
    warnings: Iterable[str] | None = None,
) -> EventAlphaPipelineResult:
    return replace(
        result,
        warnings=tuple(dict.fromkeys(warnings if warnings is not None else result.warnings)),
        send_requested=send_result.requested,
        send_attempted=send_result.attempted,
        send_success=send_result.success,
        send_items_attempted=send_result.items_attempted,
        send_items_delivered=send_result.items_delivered,
        send_block_reason=send_result.block_reason,
        send_lane_items_attempted=dict(send_result.lane_items_attempted),
        send_lane_items_delivered=dict(send_result.lane_items_delivered),
        send_would_send_items=send_result.would_send_items,
        send_heartbeat_due=send_result.heartbeat_due,
        send_heartbeat_sent=send_result.heartbeat_sent,
        send_cooldown_blocks=dict(send_result.cooldown_blocks),
        notification_scope=send_result.notification_scope,
        notification_scope_value=send_result.notification_scope_value,
        research_review_digest_enabled=send_result.research_review_digest_enabled,
        research_review_digest_candidates=send_result.research_review_digest_candidates,
        research_review_digest_would_send=send_result.research_review_digest_would_send,
        research_review_digest_sent=send_result.research_review_digest_sent,
        research_review_digest_block_reason=send_result.research_review_digest_block_reason,
    )


def _combine_watchlist_results(
    primary: event_watchlist.EventWatchlistRefreshResult,
    secondary: event_watchlist.EventWatchlistRefreshResult,
) -> event_watchlist.EventWatchlistRefreshResult:
    if primary.state_path != secondary.state_path:
        return primary
    return event_watchlist.EventWatchlistRefreshResult(
        state_path=primary.state_path,
        observed_at=primary.observed_at,
        rows_written=primary.rows_written + secondary.rows_written,
        entries=[*primary.entries, *secondary.entries],
        alert_entries=[*primary.alert_entries, *secondary.alert_entries],
    )


def _normalize_send_result(
    raw_result: Any,
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
) -> EventAlphaSendResult:
    if isinstance(raw_result, EventAlphaSendResult):
        return raw_result
    if isinstance(raw_result, bool):
        return EventAlphaSendResult(
            requested=True,
            attempted=True,
            success=raw_result,
            items_attempted=len(decisions),
            items_delivered=len(decisions) if raw_result else 0,
            block_reason=None if raw_result else "send callback returned false",
            would_send_items=len(decisions),
        )
    return EventAlphaSendResult(
        requested=True,
        attempted=True,
        success=True,
        items_attempted=len(decisions),
        items_delivered=len(decisions),
        would_send_items=len(decisions),
    )


def _merge_catalyst_search_events(
    raw_events: tuple[RawDiscoveredEvent, ...],
    search_result: event_catalyst_search.CatalystSearchRunResult | None,
) -> tuple[RawDiscoveredEvent, ...]:
    if search_result is None or not search_result.attached_raw_events:
        return raw_events
    anomaly_ids = {
        raw.raw_id
        for raw in search_result.attached_raw_events
        if raw.raw_json
        and isinstance(raw.raw_json.get("market_anomaly_catalyst_search"), dict)
        and raw.raw_json["market_anomaly_catalyst_search"].get("role") == "parent_anomaly"
    }
    kept = [raw for raw in raw_events if raw.raw_id not in anomaly_ids]
    seen: set[str] = {raw.raw_id for raw in kept}
    for raw in search_result.attached_raw_events:
        if raw.raw_id in seen:
            continue
        kept.append(raw)
        seen.add(raw.raw_id)
    return tuple(kept)


def _enrich_source_events(
    raw_events: tuple[RawDiscoveredEvent, ...],
    *,
    cfg: event_source_enrichment.EventSourceEnrichmentConfig,
    fetch_fn: SourceFetchFn | None,
    warnings: list[str],
) -> tuple[RawDiscoveredEvent, ...]:
    enriched: list[RawDiscoveredEvent] = []
    fetched = 0
    used_cache = 0
    selected = 0
    max_rows = max(0, int(getattr(cfg, "max_rows_per_run", 0) or 0))
    for raw in raw_events:
        if not event_source_enrichment.should_enrich_source(
            raw,
            min_source_confidence=cfg.min_source_confidence,
        ):
            enriched.append(raw)
            continue
        if max_rows and selected >= max_rows:
            enriched.append(raw)
            continue
        selected += 1
        result = event_source_enrichment.enrich_source_text(raw, cfg=cfg, fetch_fn=fetch_fn)
        if result.fetched:
            fetched += 1
        if result.used_cache:
            used_cache += 1
        if result.warning and result.warning not in {"source not selected for enrichment", "source enrichment disabled"}:
            warnings.append(f"source enrichment: {raw.raw_id}: {result.warning}")
        enriched.append(event_source_enrichment.annotate_raw_event_with_enrichment(result))
    if selected:
        warnings.append(f"source enrichment: selected={selected} fetched={fetched} cache_hits={used_cache}")
    if max_rows and selected >= max_rows:
        warnings.append(f"source enrichment: max_rows_per_run={max_rows}")
    return tuple(enriched)


def format_event_alpha_pipeline_report(result: EventAlphaPipelineResult) -> str:
    """Format a concise Event Alpha cycle summary."""
    lines = [
        "=" * 76,
        "EVENT ALPHA PIPELINE REPORT (research-only; no trades, paper rows, or live RSI routing)",
        "=" * 76,
        (
            f"raw_events={result.raw_events} · catalyst_queries={result.catalyst_queries} · "
            f"catalyst_results={result.catalyst_results} · "
            f"anomaly_lifecycle={result.anomaly_lifecycle_entries} · "
            f"extractions={result.extractions}/{len(result.extraction_rows)} · "
            f"extraction_hints_applied={result.extraction_hint_events} · "
            f"catalyst_frames={result.catalyst_frame_analyses}/{len(result.catalyst_frame_rows)} · "
            f"catalyst_frame_validations={result.catalyst_frame_validations_applied} · "
            f"candidates={result.candidates} · clusters={result.clusters} · alerts={len(result.alerts)}"
        ),
        (
            f"impact_hypotheses={len(result.impact_hypotheses)} · "
            f"hypotheses_validated={result.hypotheses_validated} · "
            f"hypothesis_search_queries={result.hypothesis_search_queries} · "
            f"hypothesis_search_results={result.hypothesis_search_results} · "
            f"hypothesis_promotions={result.hypothesis_promotions} · "
            f"near_misses={result.near_misses} · near_miss_upgrades={result.near_miss_upgrades} · "
            f"evidence_acquisition={result.evidence_acquisition_attempted} "
            f"accepted={result.evidence_acquisition_accepted} "
            f"upgraded={result.evidence_acquisition_upgraded}"
        ),
        (
            "hypothesis_search_query_types="
            + (
                _query_type_summary(result.hypothesis_search_result.queries)
                if result.hypothesis_search_result is not None
                else "none"
            )
        ),
        (
            "catalyst_search_skip_reasons="
            + (
                ", ".join(f"{key}={value}" for key, value in sorted(result.catalyst_search_skip_reasons.items()))
                if result.catalyst_search_skip_reasons
                else "none"
            )
        ),
        (
            "hypothesis_search_skip_reasons="
            + (
                ", ".join(f"{key}={value}" for key, value in sorted(result.hypothesis_search_skip_reasons.items()))
                if result.hypothesis_search_skip_reasons
                else "none"
            )
        ),
        (
            f"watchlist_entries={result.watchlist_entries} · "
            f"watchlist_escalations={result.watchlist_escalations} · "
            f"watchlist_monitor_active={result.watchlist_monitor_active_entries} · "
            f"watchlist_monitor_material={result.watchlist_monitor_material_updates} · "
            f"routed={result.routed} · alertable={result.alertable}"
        ),
        (
            f"send_requested={str(result.send_requested).lower()} · "
            f"send_attempted={str(result.send_attempted).lower()} · "
            f"send_success={str(result.send_success).lower()} · "
            f"send_items={result.send_items_delivered}/{result.send_items_attempted}"
            + (f" · send_block={result.send_block_reason}" if result.send_block_reason else "")
        ),
        (
            f"cycle_completed={str(result.cycle_completed).lower()} · "
            f"partial_results={str(result.partial_results).lower()}"
        ),
        (
            f"artifact_writes: hypotheses={result.hypothesis_rows_written} "
            f"success={str(result.hypothesis_write_success).lower()} · "
            f"incidents={result.incident_rows_written} "
            f"success={str(result.incident_write_success).lower()} · "
            f"snapshots={result.snapshot_rows_written} "
            f"success={str(result.snapshot_write_success).lower()}"
        ),
    ]
    if result.warnings:
        lines.append("warnings: " + "; ".join(result.warnings))
    if result.catalyst_search_result is not None:
        lines.append("")
        lines.append(event_catalyst_search.format_catalyst_search_report(result.catalyst_search_result))
    if result.hypothesis_search_result is not None:
        lines.append("")
        lines.append("Impact hypothesis validation search:")
        lines.append(event_catalyst_search.format_catalyst_search_report(result.hypothesis_search_result))
    if result.anomaly_lifecycle_result is not None:
        lines.append("")
        lines.append(event_anomaly_state.format_anomaly_lifecycle_report(result.anomaly_lifecycle_result))
    if result.evidence_acquisition_result is not None and result.evidence_acquisition_result.results:
        lines.append("")
        lines.append("Evidence acquisition execution:")
        lines.append(event_evidence_acquisition.format_acquisition_report(
            event_evidence_acquisition._artifact_row(result_item, context={}, observed_at="")
            for result_item in result.evidence_acquisition_result.results
        ))
    if result.impact_hypotheses:
        lines.append("")
        lines.append(event_impact_hypotheses.format_impact_hypothesis_report(result.impact_hypotheses))
    if result.watchlist_monitor_result is not None:
        lines.append("")
        lines.append(event_watchlist_monitor.format_watchlist_monitor_report(result.watchlist_monitor_result))
    lines.append("")
    lines.append(_tier_summary(result.alerts))
    if result.router_result is not None:
        lines.append(_route_summary(result.router_result))
    if result.watchlist_result is not None and result.watchlist_result.alert_entries:
        lines.append("")
        lines.append("Watchlist escalations:")
        for entry in result.watchlist_result.alert_entries[:10]:
            lines.append(
                f"- {entry.state} {entry.symbol}/{entry.coin_id} "
                f"score={entry.latest_score} playbook={entry.latest_playbook_type or 'unknown'}"
            )
    elif result.watchlist_result is not None and result.watchlist_result.entries:
        lines.append("")
        lines.append("Watchlist sample:")
        for entry in result.watchlist_result.entries[:5]:
            lines.append(
                f"- {entry.state} {entry.symbol}/{entry.coin_id} "
                f"score={entry.latest_score} playbook={entry.latest_playbook_type or 'unknown'}"
            )
    if result.router_result is not None and result.router_result.alertable_decisions:
        lines.append("")
        lines.append("Alertable route decisions:")
        for decision in result.router_result.alertable_decisions[:10]:
            entry = decision.entry
            lines.append(
                f"- {decision.route.value} {entry.symbol}/{entry.coin_id} "
                f"state={entry.state} score={entry.latest_score} reason={decision.reason}"
            )
    return "\n".join(lines).rstrip()


def _tier_summary(alerts: Iterable[event_alerts.EventAlertCandidate]) -> str:
    counts: dict[str, int] = {}
    for alert in alerts:
        counts[alert.tier.value] = counts.get(alert.tier.value, 0) + 1
    if not counts:
        return "alert_tiers: none"
    return "alert_tiers: " + ", ".join(f"{tier}={count}" for tier, count in sorted(counts.items()))


def _route_summary(result: event_alpha_router.EventAlphaRouterResult) -> str:
    counts: dict[str, int] = {}
    for decision in result.decisions:
        counts[decision.route.value] = counts.get(decision.route.value, 0) + 1
    if not counts:
        return "routes: none"
    return "routes: " + ", ".join(f"{route}={count}" for route, count in sorted(counts.items()))


def _query_type_summary(queries: Iterable[object]) -> str:
    counts: dict[str, int] = {}
    for query in queries:
        query_type = str(getattr(query, "query_type", "") or "candidate_validation")
        counts[query_type] = counts.get(query_type, 0) + 1
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _llm_budget_warnings(rows: Iterable[object], *, label: str) -> list[str]:
    skipped = [
        row for row in rows
        if getattr(row, "cache_status", "") == "skipped_budget"
        or any("budget exhausted" in str(warning) for warning in getattr(row, "warnings", ()))
    ]
    if not skipped:
        return []
    return [f"LLM {label} budget exhausted; skipped {len(skipped)} lower-priority row(s)"]


def _catalyst_frame_skip_reason(
    warnings: Iterable[str],
    *,
    selected: bool,
    required: bool,
) -> str:
    text = " ".join(str(item or "") for item in warnings).casefold()
    if "missing openai_api_key" in text or "missing api key" in text:
        return "missing_api_key"
    if "budget" in text and ("exhaust" in text or "skip" in text):
        return "budget_exhausted"
    if "deadline" in text or "timeout" in text or "timed out" in text:
        return "deadline_exceeded"
    if not selected:
        return "no_rows_selected" if required else "not_required"
    if not required:
        return "not_required"
    return "provider_returned_no_analysis"


def _raw_with_catalyst_frame_status(
    raw: RawDiscoveredEvent,
    *,
    status: str,
    required: bool | None = None,
    required_reason: str | None = None,
    skip_reason: str | None = None,
    warnings: Iterable[str] = (),
) -> RawDiscoveredEvent:
    payload = dict(raw.raw_json or {})
    if required is None or required_reason is None:
        detected_required, detected_reason = event_llm_catalyst_frames.frame_requirement_for_raw(raw)
        required = detected_required if required is None else required
        required_reason = required_reason or detected_reason
    payload["catalyst_frame_required"] = bool(required)
    payload["catalyst_frame_required_reason"] = required_reason
    payload["catalyst_frame_status"] = status
    if skip_reason:
        payload["catalyst_frame_skip_reason"] = skip_reason
    if warnings:
        payload["catalyst_frame_warnings"] = list(dict.fromkeys(str(item) for item in warnings if str(item)))
    return replace(raw, raw_json=payload)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
