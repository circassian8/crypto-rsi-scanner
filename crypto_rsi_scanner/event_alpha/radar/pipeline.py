"""Unified research-only Event Alpha Radar pipeline orchestration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.anomaly_state as event_anomaly_state
import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames
import crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator as event_catalyst_frame_validator
import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss
import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
import crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment as event_watchlist_enrichment
import crypto_rsi_scanner.event_alpha.radar.watchlist_market as event_watchlist_market
import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor
from ...event_alpha.outcomes import priors as event_alpha_priors
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, RawDiscoveredEvent

from .pipeline_models import (
    DiscoveryLoader,
    EventAlphaPipelineResult,
    EventAlphaSendResult,
    RawEventTransform,
    ResearchAlertSender,
    SourceFetchFn,
    _OperatingCycleContext,
    _PipelineAlertPhase,
    _PipelineEvidencePhase,
    _PipelineHypothesisPhase,
    _PipelineNearMissPhase,
    _PipelineWatchlistRoutePhase,
)

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

    alert_phase = _pipeline_alert_phase(
        discovery_result,
        alert_cfg=alert_cfg,
        observed=observed,
        relationship_provider=relationship_provider,
        relationship_cfg=relationship_cfg,
        priors_cfg=priors_cfg,
    )
    warnings.extend(alert_phase.warnings)

    hypothesis_phase = _pipeline_hypothesis_phase(
        discovery_result,
        extraction_rows_list=extraction_rows_list,
        raw_events=source_raw_events,
        catalyst_search_result=catalyst_search_result,
        hypothesis_search_provider=hypothesis_search_provider,
        hypothesis_search_cfg=hypothesis_search_cfg,
        observed=observed,
    )
    impact_hypotheses = hypothesis_phase.impact_hypotheses
    warnings.extend(hypothesis_phase.warnings)

    near_miss_phase = _pipeline_near_miss_phase(
        impact_hypotheses,
        near_miss_cfg=near_miss_cfg,
        near_miss_market_rows=near_miss_market_rows or watchlist_monitor_market_rows,
        near_miss_market_provider=near_miss_market_provider,
        near_miss_derivatives_rows=near_miss_derivatives_rows or watchlist_monitor_derivatives_rows,
        near_miss_supply_rows=near_miss_supply_rows or watchlist_monitor_supply_rows,
        observed=observed,
    )
    impact_hypotheses = near_miss_phase.impact_hypotheses
    warnings.extend(near_miss_phase.warnings)

    evidence_phase = _pipeline_evidence_phase(
        impact_hypotheses,
        near_miss_result=near_miss_phase.near_miss_result,
        evidence_acquisition_cfg=evidence_acquisition_cfg,
        evidence_acquisition_provider=evidence_acquisition_provider,
        evidence_acquisition_providers_by_hint=evidence_acquisition_providers_by_hint,
        evidence_acquisition_context=evidence_acquisition_context,
        observed=observed,
    )
    impact_hypotheses = evidence_phase.impact_hypotheses
    warnings.extend(evidence_phase.warnings)

    anomaly_lifecycle_result = (
        event_anomaly_state.build_anomaly_lifecycle(
            source_raw_events or discovery_result.raw_events,
            catalyst_search_result,
            alert_phase.alerts,
            now=observed,
        )
        if catalyst_search_result is not None
        else None
    )
    watchlist_phase = _pipeline_watchlist_route_phase(
        discovery_result,
        alerts=alert_phase.alerts,
        impact_hypotheses=impact_hypotheses,
        watchlist_cfg=watchlist_cfg,
        router_cfg=router_cfg,
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
        observed=observed,
    )
    warnings.extend(watchlist_phase.warnings)

    return EventAlphaPipelineResult(
        discovery_result=discovery_result,
        alerts=alert_phase.alerts,
        catalyst_search_result=catalyst_search_result,
        hypothesis_search_result=hypothesis_phase.hypothesis_search_result,
        anomaly_lifecycle_result=anomaly_lifecycle_result,
        extraction_rows=extraction_rows_list,
        catalyst_frame_rows=catalyst_frame_rows_list,
        relationship_rows=alert_phase.relationship_rows,
        watchlist_result=watchlist_phase.watchlist_result,
        watchlist_monitor_result=watchlist_phase.watchlist_monitor_result,
        router_result=watchlist_phase.router_result,
        near_miss_result=near_miss_phase.near_miss_result,
        evidence_acquisition_result=evidence_phase.evidence_acquisition_result,
        impact_hypotheses=impact_hypotheses,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _pipeline_alert_phase(
    discovery_result: EventDiscoveryResult,
    *,
    alert_cfg: event_alerts.EventAlertConfig,
    observed: datetime,
    relationship_provider: object | None,
    relationship_cfg: event_llm_analyzer.EventLLMConfig | None,
    priors_cfg: event_alpha_priors.EventAlphaPriorsConfig | None,
) -> _PipelineAlertPhase:
    warnings: list[str] = []
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
    return _PipelineAlertPhase(
        alerts=alerts,
        relationship_rows=relationship_rows,
        warnings=tuple(warnings),
    )


def _pipeline_hypothesis_phase(
    discovery_result: EventDiscoveryResult,
    *,
    extraction_rows_list: list[event_llm_extractor.EventLLMExtractionReportRow],
    raw_events: Iterable[RawDiscoveredEvent],
    catalyst_search_result: event_catalyst_search.CatalystSearchRunResult | None,
    hypothesis_search_provider: event_catalyst_search.CatalystSearchProvider | None,
    hypothesis_search_cfg: event_catalyst_search.EventImpactHypothesisSearchConfig | None,
    observed: datetime,
) -> _PipelineHypothesisPhase:
    warnings: list[str] = []
    clusters = event_graph.build_event_clusters(discovery_result)
    impact_hypotheses = event_impact_hypotheses.generate_impact_hypotheses(
        discovery_result,
        raw_events=raw_events,
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
    return _PipelineHypothesisPhase(
        impact_hypotheses=impact_hypotheses,
        hypothesis_search_result=hypothesis_search_result,
        warnings=tuple(warnings),
    )


def _pipeline_near_miss_phase(
    impact_hypotheses: tuple[event_impact_hypotheses.EventImpactHypothesis, ...],
    *,
    near_miss_cfg: event_near_miss.EventNearMissConfig | None,
    near_miss_market_rows: Iterable[dict[str, Any]],
    near_miss_market_provider: event_watchlist_market.EventWatchlistMarketProvider | None,
    near_miss_derivatives_rows: Iterable[dict[str, Any]],
    near_miss_supply_rows: Iterable[dict[str, Any]],
    observed: datetime,
) -> _PipelineNearMissPhase:
    if near_miss_cfg is None or not near_miss_cfg.enabled:
        return _PipelineNearMissPhase(impact_hypotheses=impact_hypotheses)
    near_miss_result = event_near_miss.refresh_near_miss_hypotheses(
        impact_hypotheses,
        cfg=near_miss_cfg,
        market_rows=near_miss_market_rows,
        targeted_market_provider=near_miss_market_provider,
        derivatives_rows=near_miss_derivatives_rows,
        supply_rows=near_miss_supply_rows,
        now=observed,
    )
    return _PipelineNearMissPhase(
        impact_hypotheses=near_miss_result.hypotheses,
        near_miss_result=near_miss_result,
        warnings=tuple(f"near miss: {warning}" for warning in near_miss_result.warnings),
    )


def _pipeline_evidence_phase(
    impact_hypotheses: tuple[event_impact_hypotheses.EventImpactHypothesis, ...],
    *,
    near_miss_result: event_near_miss.EventNearMissRefreshResult | None,
    evidence_acquisition_cfg: event_evidence_acquisition.EvidenceAcquisitionConfig | None,
    evidence_acquisition_provider: event_evidence_acquisition.EvidenceSearchProvider | None,
    evidence_acquisition_providers_by_hint: dict[str, event_evidence_acquisition.EvidenceSearchProvider | None] | None,
    evidence_acquisition_context: dict[str, Any] | None,
    observed: datetime,
) -> _PipelineEvidencePhase:
    if evidence_acquisition_cfg is None or not evidence_acquisition_cfg.enabled:
        return _PipelineEvidencePhase(impact_hypotheses=impact_hypotheses)
    evidence_acquisition_result = event_evidence_acquisition.run_evidence_acquisition(
        impact_hypotheses,
        near_misses=near_miss_result.near_misses if near_miss_result else (),
        provider=evidence_acquisition_provider,
        providers_by_hint=evidence_acquisition_providers_by_hint or {},
        cfg=evidence_acquisition_cfg,
        now=observed,
        run_context=evidence_acquisition_context or {},
    )
    return _PipelineEvidencePhase(
        impact_hypotheses=tuple(
            item
            for item in evidence_acquisition_result.hypotheses
            if isinstance(item, event_impact_hypotheses.EventImpactHypothesis)
        ),
        evidence_acquisition_result=evidence_acquisition_result,
        warnings=tuple(f"evidence acquisition: {warning}" for warning in evidence_acquisition_result.warnings),
    )


def _pipeline_watchlist_route_phase(
    discovery_result: EventDiscoveryResult,
    *,
    alerts: list[event_alerts.EventAlertCandidate],
    impact_hypotheses: tuple[event_impact_hypotheses.EventImpactHypothesis, ...],
    watchlist_cfg: event_watchlist.EventWatchlistConfig | None,
    router_cfg: event_alpha_router.EventAlphaRouterConfig | None,
    refresh_watchlist: bool,
    route: bool,
    watchlist_monitor_enabled: bool,
    watchlist_monitor_market_rows: Iterable[dict[str, Any]],
    watchlist_monitor_market_source: str,
    watchlist_monitor_market_provider: event_watchlist_market.EventWatchlistMarketProvider | None,
    watchlist_monitor_targeted_lookup: bool,
    watchlist_monitor_max_assets: int,
    watchlist_monitor_market_cache_ttl_seconds: int,
    watchlist_monitor_derivatives_source: str,
    watchlist_monitor_supply_source: str,
    watchlist_monitor_derivatives_rows: Iterable[dict[str, Any]],
    watchlist_monitor_supply_rows: Iterable[dict[str, Any]],
    watchlist_monitor_enrichment_max_assets: int,
    watchlist_monitor_route_updates: bool,
    observed: datetime,
) -> _PipelineWatchlistRoutePhase:
    warnings: list[str] = []
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
    return _PipelineWatchlistRoutePhase(
        watchlist_result=watchlist_result,
        watchlist_monitor_result=watchlist_monitor_result,
        router_result=router_result,
        warnings=tuple(warnings),
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
    context = _build_operating_cycle_context(
        observed=observed,
        with_llm=with_llm,
        extraction_provider=extraction_provider,
        extraction_cfg=extraction_cfg,
        catalyst_frame_provider=catalyst_frame_provider,
        catalyst_frame_cfg=catalyst_frame_cfg,
        relationship_provider=relationship_provider,
        relationship_cfg=relationship_cfg,
    )
    raw_event_transform = _operating_cycle_raw_event_transform(
        context,
        catalyst_search_provider=catalyst_search_provider,
        catalyst_search_cfg=catalyst_search_cfg,
        source_enrichment_cfg=source_enrichment_cfg,
        source_enrichment_fetch_fn=source_enrichment_fetch_fn,
    )

    discovery_result = load_discovery_result(observed, raw_event_transform)
    context.warnings.extend(str(warning) for warning in getattr(discovery_result, "warnings", ()) or () if str(warning))
    result = run_event_alpha_pipeline(
        discovery_result,
        alert_cfg=alert_cfg,
        now=observed,
        catalyst_search_result=context.catalyst_search_result,
        hypothesis_search_provider=hypothesis_search_provider,
        hypothesis_search_cfg=hypothesis_search_cfg,
        source_raw_events=context.source_raw_events,
        extraction_rows=context.extraction_rows,
        catalyst_frame_rows=context.catalyst_frame_rows,
        relationship_provider=context.relationship_provider,
        relationship_cfg=context.relationship_cfg,
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
        extra_warnings=context.warnings,
    )
    return _apply_operating_cycle_send(result, send=send, send_callback=send_callback)


def _build_operating_cycle_context(
    *,
    observed: datetime,
    with_llm: bool,
    extraction_provider: object | None,
    extraction_cfg: event_llm_extractor.EventLLMExtractorConfig | None,
    catalyst_frame_provider: object | None,
    catalyst_frame_cfg: event_llm_catalyst_frames.EventLLMCatalystFrameConfig | None,
    relationship_provider: object | None,
    relationship_cfg: event_llm_analyzer.EventLLMConfig | None,
) -> _OperatingCycleContext:
    context = _OperatingCycleContext(observed=observed)
    if not with_llm:
        return context
    context.llm_transform = _operating_cycle_extraction_transform(
        context,
        extraction_provider=extraction_provider,
        extraction_cfg=extraction_cfg,
    )
    context.catalyst_frame_transform = _operating_cycle_catalyst_frame_transform(
        context,
        catalyst_frame_provider=catalyst_frame_provider,
        catalyst_frame_cfg=catalyst_frame_cfg,
    )
    _set_operating_cycle_relationship_inputs(
        context,
        relationship_provider=relationship_provider,
        relationship_cfg=relationship_cfg,
    )
    return context


def _operating_cycle_extraction_transform(
    context: _OperatingCycleContext,
    *,
    extraction_provider: object | None,
    extraction_cfg: event_llm_extractor.EventLLMExtractorConfig | None,
) -> RawEventTransform | None:
    if extraction_cfg is None:
        return None
    if extraction_provider is None:
        context.warnings.append("Event LLM extractor skipped: no extraction provider available")
        return None
    mode = extraction_cfg.mode.strip().lower()
    if mode == "shadow":
        def _shadow_llm_extractions(raw_events: tuple[RawDiscoveredEvent, ...]) -> tuple[RawDiscoveredEvent, ...]:
            context.extraction_rows = event_llm_extractor.analyze_raw_events(
                raw_events,
                extraction_provider,
                cfg=extraction_cfg,
            )
            return tuple(raw_events)

        return _shadow_llm_extractions
    if mode == "advisory":
        def _enrich_with_llm_extractions(raw_events: tuple[RawDiscoveredEvent, ...]) -> tuple[RawDiscoveredEvent, ...]:
            context.extraction_rows = event_llm_extractor.analyze_raw_events(
                raw_events,
                extraction_provider,
                cfg=extraction_cfg,
            )
            return event_llm_extractor.enrich_raw_events_with_extractions(raw_events, context.extraction_rows)

        return _enrich_with_llm_extractions
    if mode in {"off", "disabled", "none"}:
        context.warnings.append("Event LLM extractor skipped: mode is off")
    else:
        context.warnings.append(
            f"Event LLM extractor skipped: unsupported mode {extraction_cfg.mode!r}; use shadow or advisory"
        )
    return None


def _operating_cycle_catalyst_frame_transform(
    context: _OperatingCycleContext,
    *,
    catalyst_frame_provider: object | None,
    catalyst_frame_cfg: event_llm_catalyst_frames.EventLLMCatalystFrameConfig | None,
) -> RawEventTransform | None:
    if catalyst_frame_cfg is None:
        return None
    if not catalyst_frame_cfg.enabled:
        return _operating_cycle_catalyst_frame_marker(skip_reason="disabled")
    if catalyst_frame_provider is None:
        context.warnings.append("Event LLM catalyst-frame analysis skipped: no provider available")
        provider_name = str(catalyst_frame_cfg.provider or "").strip().lower()
        provider_skip_reason = "missing_api_key" if provider_name == "openai" else "profile_disabled"
        return _operating_cycle_catalyst_frame_marker(skip_reason=provider_skip_reason)
    return _operating_cycle_catalyst_frame_enrichment(
        context,
        catalyst_frame_provider=catalyst_frame_provider,
        catalyst_frame_cfg=catalyst_frame_cfg,
    )


def _operating_cycle_catalyst_frame_marker(*, skip_reason: str) -> RawEventTransform:
    def _mark_llm_catalyst_frames(raw_events: tuple[RawDiscoveredEvent, ...]) -> tuple[RawDiscoveredEvent, ...]:
        return tuple(
            _raw_with_catalyst_frame_status(
                raw,
                status="missing_required_frame_analysis"
                if event_llm_catalyst_frames.frame_requirement_for_raw(raw)[0]
                else "not_required",
                skip_reason=skip_reason,
            )
            for raw in raw_events
        )

    return _mark_llm_catalyst_frames


def _operating_cycle_catalyst_frame_enrichment(
    context: _OperatingCycleContext,
    *,
    catalyst_frame_provider: object,
    catalyst_frame_cfg: event_llm_catalyst_frames.EventLLMCatalystFrameConfig,
) -> RawEventTransform:
    def _enrich_with_llm_catalyst_frames(
        raw_events: tuple[RawDiscoveredEvent, ...],
    ) -> tuple[RawDiscoveredEvent, ...]:
        context.catalyst_frame_rows = event_llm_catalyst_frames.analyze_raw_events(
            raw_events,
            catalyst_frame_provider,
            cfg=catalyst_frame_cfg,
        )
        selected_raw_ids = {row.raw_event.raw_id for row in context.catalyst_frame_rows}
        if not selected_raw_ids and any(
            event_llm_catalyst_frames.frame_requirement_for_raw(raw)[0]
            for raw in raw_events
        ):
            context.warnings.append("Event LLM catalyst-frame analysis skipped: no required rows selected")
        return _operating_cycle_apply_catalyst_frame_rows(context, raw_events, selected_raw_ids=selected_raw_ids)

    return _enrich_with_llm_catalyst_frames


def _operating_cycle_apply_catalyst_frame_rows(
    context: _OperatingCycleContext,
    raw_events: tuple[RawDiscoveredEvent, ...],
    *,
    selected_raw_ids: set[str],
) -> tuple[RawDiscoveredEvent, ...]:
    analyses_by_raw_id = {
        row.raw_event.raw_id: row.analysis
        for row in context.catalyst_frame_rows
        if row.analysis is not None
    }
    row_warnings_by_raw_id = {
        row.raw_event.raw_id: tuple(row.warnings)
        for row in context.catalyst_frame_rows
    }
    enriched: list[RawDiscoveredEvent] = []
    for raw in raw_events:
        required, required_reason = event_llm_catalyst_frames.frame_requirement_for_raw(raw)
        analysis = analyses_by_raw_id.get(raw.raw_id)
        if analysis is None:
            row_warnings = row_warnings_by_raw_id.get(raw.raw_id, ())
            skip_reason = _catalyst_frame_skip_reason(
                row_warnings,
                selected=raw.raw_id in selected_raw_ids,
                required=required,
            )
            enriched.append(_raw_with_catalyst_frame_status(
                raw,
                status="missing_required_frame_analysis" if required else "not_required",
                required=required,
                required_reason=required_reason,
                skip_reason=skip_reason,
                warnings=row_warnings,
            ))
            continue
        enriched.append(_operating_cycle_validated_catalyst_frame_raw(
            raw,
            analysis=analysis,
            required=required,
            required_reason=required_reason,
        ))
    return tuple(enriched)


def _operating_cycle_validated_catalyst_frame_raw(
    raw: RawDiscoveredEvent,
    *,
    analysis: event_llm_catalyst_frames.EventLLMCatalystFrameAnalysis,
    required: bool,
    required_reason: str | None,
) -> RawDiscoveredEvent:
    rule_frames = event_catalyst_frames.build_catalyst_frames((raw,))
    validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(
        analysis,
        (raw,),
        rule_frames=rule_frames,
    )
    if (
        validation.source_raw_id != raw.raw_id
        or not validation.source_binding_schema_version
        or not validation.analysis_sha256
    ):
        return _raw_with_catalyst_frame_status(
            raw,
            status="unresolved",
            required=required,
            required_reason=required_reason,
            skip_reason="catalyst_frame_source_binding_invalid",
            warnings=validation.frame_warnings,
        )
    status = (
        "unresolved"
        if validation.resolution == event_catalyst_frame_validator.RESOLUTION_UNRESOLVED
        else "validated"
    )
    return _raw_with_catalyst_frame_status(
        event_catalyst_frame_validator.apply_validation_to_raw_event(raw, analysis, validation),
        status=status,
        required=required,
        required_reason=required_reason,
        skip_reason=None,
        warnings=validation.frame_warnings,
    )


def _set_operating_cycle_relationship_inputs(
    context: _OperatingCycleContext,
    *,
    relationship_provider: object | None,
    relationship_cfg: event_llm_analyzer.EventLLMConfig | None,
) -> None:
    if relationship_cfg is not None and relationship_provider is not None:
        if relationship_cfg.mode in {"shadow", "advisory"}:
            context.relationship_provider = relationship_provider
            context.relationship_cfg = relationship_cfg
        else:
            context.warnings.append(
                f"Event LLM mode {relationship_cfg.mode!r} is not supported; use shadow or advisory"
            )
    elif relationship_cfg is not None:
        context.warnings.append("Event LLM relationship analysis skipped: no relationship provider available")


def _operating_cycle_raw_event_transform(
    context: _OperatingCycleContext,
    *,
    catalyst_search_provider: event_catalyst_search.CatalystSearchProvider | None,
    catalyst_search_cfg: event_catalyst_search.EventCatalystSearchConfig | None,
    source_enrichment_cfg: event_source_enrichment.EventSourceEnrichmentConfig | None,
    source_enrichment_fetch_fn: SourceFetchFn | None,
) -> RawEventTransform | None:
    enabled = (
        context.llm_transform is not None
        or context.catalyst_frame_transform is not None
        or (catalyst_search_cfg is not None and catalyst_search_cfg.enabled)
        or (source_enrichment_cfg is not None and source_enrichment_cfg.enabled)
    )
    if not enabled:
        return None

    def _combined_raw_event_transform(raw_events: tuple[RawDiscoveredEvent, ...]) -> tuple[RawDiscoveredEvent, ...]:
        context.source_raw_events = tuple(raw_events)
        transformed = _operating_cycle_catalyst_search_events(
            context,
            tuple(raw_events),
            catalyst_search_provider=catalyst_search_provider,
            catalyst_search_cfg=catalyst_search_cfg,
        )
        transformed = _operating_cycle_source_enrichment_events(
            transformed,
            source_enrichment_cfg=source_enrichment_cfg,
            source_enrichment_fetch_fn=source_enrichment_fetch_fn,
            warnings=context.warnings,
        )
        if context.llm_transform is not None:
            transformed = tuple(context.llm_transform(transformed))
        if context.catalyst_frame_transform is not None:
            transformed = tuple(context.catalyst_frame_transform(transformed))
        context.source_raw_events = tuple(transformed)
        return transformed

    return _combined_raw_event_transform


def _operating_cycle_catalyst_search_events(
    context: _OperatingCycleContext,
    raw_events: tuple[RawDiscoveredEvent, ...],
    *,
    catalyst_search_provider: event_catalyst_search.CatalystSearchProvider | None,
    catalyst_search_cfg: event_catalyst_search.EventCatalystSearchConfig | None,
) -> tuple[RawDiscoveredEvent, ...]:
    if catalyst_search_cfg is None or not catalyst_search_cfg.enabled:
        return tuple(raw_events)
    if catalyst_search_provider is None:
        context.warnings.append("catalyst search skipped: no provider available")
        context.catalyst_search_result = event_catalyst_search.CatalystSearchRunResult(
            provider=catalyst_search_cfg.provider,
            warnings=("catalyst search skipped: no provider available",),
            skip_reasons={"provider_unavailable": 1},
        )
        return tuple(raw_events)
    context.catalyst_search_result = event_catalyst_search.run_catalyst_search(
        raw_events,
        catalyst_search_provider,
        cfg=catalyst_search_cfg,
        now=context.observed,
    )
    context.warnings.extend(f"catalyst search: {warning}" for warning in context.catalyst_search_result.warnings)
    return _merge_catalyst_search_events(raw_events, context.catalyst_search_result)


def _operating_cycle_source_enrichment_events(
    raw_events: tuple[RawDiscoveredEvent, ...],
    *,
    source_enrichment_cfg: event_source_enrichment.EventSourceEnrichmentConfig | None,
    source_enrichment_fetch_fn: SourceFetchFn | None,
    warnings: list[str],
) -> tuple[RawDiscoveredEvent, ...]:
    if source_enrichment_cfg is None or not source_enrichment_cfg.enabled:
        return tuple(raw_events)
    return _enrich_source_events(
        raw_events,
        cfg=source_enrichment_cfg,
        fetch_fn=source_enrichment_fetch_fn,
        warnings=warnings,
    )


def _apply_operating_cycle_send(
    result: EventAlphaPipelineResult,
    *,
    send: bool,
    send_callback: ResearchAlertSender | None,
) -> EventAlphaPipelineResult:
    if not send:
        return _with_send_result(result, EventAlphaSendResult(requested=False))
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
    from .pipeline_report import format_event_alpha_pipeline_report as _format_report

    return _format_report(result)


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
