"""Unified research-only Event Alpha Radar pipeline orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import (
    event_alerts,
    event_alpha_router,
    event_alpha_priors,
    event_anomaly_state,
    event_catalyst_search,
    event_graph,
    event_llm_analyzer,
    event_llm_extractor,
    event_watchlist,
    event_watchlist_enrichment,
    event_watchlist_market,
    event_watchlist_monitor,
)
from .event_models import EventDiscoveryResult, RawDiscoveredEvent

RawEventTransform = Callable[[tuple[RawDiscoveredEvent, ...]], Iterable[RawDiscoveredEvent]]
DiscoveryLoader = Callable[[datetime, RawEventTransform | None], EventDiscoveryResult]
ResearchAlertSender = Callable[[list[event_alpha_router.EventAlphaRouteDecision]], Any]


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


@dataclass(frozen=True)
class EventAlphaPipelineResult:
    discovery_result: EventDiscoveryResult
    alerts: list[event_alerts.EventAlertCandidate]
    catalyst_search_result: event_catalyst_search.CatalystSearchRunResult | None
    anomaly_lifecycle_result: event_anomaly_state.EventAnomalyStateResult | None
    extraction_rows: list[event_llm_extractor.EventLLMExtractionReportRow]
    relationship_rows: list[event_llm_analyzer.EventLLMReportRow]
    watchlist_result: event_watchlist.EventWatchlistRefreshResult | None
    watchlist_monitor_result: event_watchlist_monitor.EventWatchlistMonitorResult | None
    router_result: event_alpha_router.EventAlphaRouterResult | None
    warnings: tuple[str, ...] = ()
    cycle_completed: bool = True
    partial_results: bool = False
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
    notification_burn_in: bool = False
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
    def anomaly_lifecycle_entries(self) -> int:
        return len(self.anomaly_lifecycle_result.entries) if self.anomaly_lifecycle_result else 0

    @property
    def extractions(self) -> int:
        return len([row for row in self.extraction_rows if row.extraction is not None])

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

    @property
    def routed(self) -> int:
        return len(self.router_result.decisions) if self.router_result else 0

    @property
    def alertable(self) -> int:
        return len(self.router_result.alertable_decisions) if self.router_result else 0


def run_event_alpha_pipeline(
    discovery_result: EventDiscoveryResult,
    *,
    alert_cfg: event_alerts.EventAlertConfig | None = None,
    now: datetime | None = None,
    extraction_rows: Iterable[event_llm_extractor.EventLLMExtractionReportRow] = (),
    catalyst_search_result: event_catalyst_search.CatalystSearchRunResult | None = None,
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
    extra_warnings: Iterable[str] = (),
) -> EventAlphaPipelineResult:
    """Run the research-only Event Alpha pipeline over a discovery result."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    alert_cfg = alert_cfg or event_alerts.EventAlertConfig()
    warnings: list[str] = list(extra_warnings)
    extraction_rows_list = list(extraction_rows)
    warnings.extend(_llm_budget_warnings(extraction_rows_list, label="extractor"))
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
        anomaly_lifecycle_result=anomaly_lifecycle_result,
        extraction_rows=extraction_rows_list,
        relationship_rows=relationship_rows,
        watchlist_result=watchlist_result,
        watchlist_monitor_result=watchlist_monitor_result,
        router_result=router_result,
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
    catalyst_search_provider: event_catalyst_search.CatalystSearchProvider | None = None,
    catalyst_search_cfg: event_catalyst_search.EventCatalystSearchConfig | None = None,
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
    source_raw_events: tuple[RawDiscoveredEvent, ...] = ()
    llm_transform: RawEventTransform | None = None
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
            else:
                catalyst_search_result = event_catalyst_search.run_catalyst_search(
                    transformed,
                    catalyst_search_provider,
                    cfg=catalyst_search_cfg,
                    now=observed,
                )
                warnings.extend(f"catalyst search: {warning}" for warning in catalyst_search_result.warnings)
                transformed = _merge_catalyst_search_events(transformed, catalyst_search_result)
        if llm_transform is not None:
            transformed = tuple(llm_transform(transformed))
        return transformed

    raw_event_transform: RawEventTransform | None = None
    if llm_transform is not None or (catalyst_search_cfg is not None and catalyst_search_cfg.enabled):
        raw_event_transform = _combined_raw_event_transform

    discovery_result = load_discovery_result(observed, raw_event_transform)
    warnings.extend(str(warning) for warning in getattr(discovery_result, "warnings", ()) or () if str(warning))
    result = run_event_alpha_pipeline(
        discovery_result,
        alert_cfg=alert_cfg,
        now=observed,
        catalyst_search_result=catalyst_search_result,
        source_raw_events=source_raw_events,
        extraction_rows=extraction_rows,
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
            f"candidates={result.candidates} · clusters={result.clusters} · alerts={len(result.alerts)}"
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
    ]
    if result.warnings:
        lines.append("warnings: " + "; ".join(result.warnings))
    if result.catalyst_search_result is not None:
        lines.append("")
        lines.append(event_catalyst_search.format_catalyst_search_report(result.catalyst_search_result))
    if result.anomaly_lifecycle_result is not None:
        lines.append("")
        lines.append(event_anomaly_state.format_anomaly_lifecycle_report(result.anomaly_lifecycle_result))
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


def _llm_budget_warnings(rows: Iterable[object], *, label: str) -> list[str]:
    skipped = [
        row for row in rows
        if getattr(row, "cache_status", "") == "skipped_budget"
        or any("budget exhausted" in str(warning) for warning in getattr(row, "warnings", ()))
    ]
    if not skipped:
        return []
    return [f"LLM {label} budget exhausted; skipped {len(skipped)} lower-priority row(s)"]


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
