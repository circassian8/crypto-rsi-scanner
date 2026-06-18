"""Unified research-only Event Alpha Radar pipeline orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import (
    event_alerts,
    event_alpha_router,
    event_graph,
    event_llm_analyzer,
    event_llm_extractor,
    event_watchlist,
)
from .event_models import EventDiscoveryResult, RawDiscoveredEvent

RawEventTransform = Callable[[tuple[RawDiscoveredEvent, ...]], Iterable[RawDiscoveredEvent]]
DiscoveryLoader = Callable[[datetime, RawEventTransform | None], EventDiscoveryResult]
ResearchAlertSender = Callable[[list[event_alerts.EventAlertCandidate]], Any]


@dataclass(frozen=True)
class EventAlphaPipelineResult:
    discovery_result: EventDiscoveryResult
    alerts: list[event_alerts.EventAlertCandidate]
    extraction_rows: list[event_llm_extractor.EventLLMExtractionReportRow]
    relationship_rows: list[event_llm_analyzer.EventLLMReportRow]
    watchlist_result: event_watchlist.EventWatchlistRefreshResult | None
    router_result: event_alpha_router.EventAlphaRouterResult | None
    warnings: tuple[str, ...] = ()
    send_attempted: bool = False

    @property
    def raw_events(self) -> int:
        return len(self.discovery_result.raw_events)

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
    relationship_provider: object | None = None,
    relationship_cfg: event_llm_analyzer.EventLLMConfig | None = None,
    watchlist_cfg: event_watchlist.EventWatchlistConfig | None = None,
    router_cfg: event_alpha_router.EventAlphaRouterConfig | None = None,
    refresh_watchlist: bool = False,
    route: bool = False,
    extra_warnings: Iterable[str] = (),
) -> EventAlphaPipelineResult:
    """Run the research-only Event Alpha pipeline over a discovery result."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    alert_cfg = alert_cfg or event_alerts.EventAlertConfig()
    warnings: list[str] = list(extra_warnings)
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

    watchlist_result: event_watchlist.EventWatchlistRefreshResult | None = None
    if refresh_watchlist:
        if watchlist_cfg is None or not watchlist_cfg.enabled:
            warnings.append("watchlist refresh skipped: RSI_EVENT_WATCHLIST_ENABLED is not enabled")
        else:
            watchlist_result = event_watchlist.refresh_watchlist(alerts, cfg=watchlist_cfg, now=observed)

    router_result: event_alpha_router.EventAlphaRouterResult | None = None
    if route:
        if watchlist_cfg is None:
            warnings.append("router skipped: no watchlist config supplied")
        elif not watchlist_cfg.enabled:
            warnings.append("router skipped: RSI_EVENT_WATCHLIST_ENABLED is not enabled")
        else:
            read_result = event_watchlist.load_watchlist(
                watchlist_cfg.state_path or Path("event_watchlist_state.jsonl")
            )
            router_result = event_alpha_router.route_watchlist(read_result, cfg=router_cfg)

    return EventAlphaPipelineResult(
        discovery_result=discovery_result,
        alerts=alerts,
        extraction_rows=list(extraction_rows),
        relationship_rows=relationship_rows,
        watchlist_result=watchlist_result,
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
    relationship_provider: object | None = None,
    relationship_cfg: event_llm_analyzer.EventLLMConfig | None = None,
    watchlist_cfg: event_watchlist.EventWatchlistConfig | None = None,
    router_cfg: event_alpha_router.EventAlphaRouterConfig | None = None,
    refresh_watchlist: bool = True,
    route: bool = True,
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
    extraction_rows: list[event_llm_extractor.EventLLMExtractionReportRow] = []
    raw_event_transform: RawEventTransform | None = None
    relationship_provider_to_use = None
    relationship_cfg_to_use = None

    if with_llm:
        if extraction_cfg is not None and extraction_provider is not None:
            if extraction_cfg.mode == "shadow":
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

                raw_event_transform = _enrich_with_llm_extractions
            else:
                warnings.append(
                    "Event LLM extractor skipped: RSI_EVENT_LLM_EXTRACTOR_MODE must be shadow for this cycle"
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

    discovery_result = load_discovery_result(observed, raw_event_transform)
    result = run_event_alpha_pipeline(
        discovery_result,
        alert_cfg=alert_cfg,
        now=observed,
        extraction_rows=extraction_rows,
        relationship_provider=relationship_provider_to_use,
        relationship_cfg=relationship_cfg_to_use,
        watchlist_cfg=watchlist_cfg,
        router_cfg=router_cfg,
        refresh_watchlist=refresh_watchlist,
        route=route,
        extra_warnings=warnings,
    )
    if send:
        if send_callback is None:
            warnings = [*result.warnings, "research send skipped: no send callback supplied"]
            return EventAlphaPipelineResult(
                discovery_result=result.discovery_result,
                alerts=result.alerts,
                extraction_rows=result.extraction_rows,
                relationship_rows=result.relationship_rows,
                watchlist_result=result.watchlist_result,
                router_result=result.router_result,
                warnings=tuple(dict.fromkeys(warnings)),
                send_attempted=False,
            )
        try:
            send_callback(result.alerts)
        except Exception as exc:  # pragma: no cover - defensive fail-soft guard
            warnings = [*result.warnings, f"research send failed: {exc}"]
            return EventAlphaPipelineResult(
                discovery_result=result.discovery_result,
                alerts=result.alerts,
                extraction_rows=result.extraction_rows,
                relationship_rows=result.relationship_rows,
                watchlist_result=result.watchlist_result,
                router_result=result.router_result,
                warnings=tuple(dict.fromkeys(warnings)),
                send_attempted=True,
            )
        return EventAlphaPipelineResult(
            discovery_result=result.discovery_result,
            alerts=result.alerts,
            extraction_rows=result.extraction_rows,
            relationship_rows=result.relationship_rows,
            watchlist_result=result.watchlist_result,
            router_result=result.router_result,
            warnings=result.warnings,
            send_attempted=True,
        )
    return result


def format_event_alpha_pipeline_report(result: EventAlphaPipelineResult) -> str:
    """Format a concise Event Alpha cycle summary."""
    lines = [
        "=" * 76,
        "EVENT ALPHA PIPELINE REPORT (research-only; no trades, paper rows, or live RSI routing)",
        "=" * 76,
        (
            f"raw_events={result.raw_events} · extractions={result.extractions}/{len(result.extraction_rows)} · "
            f"extraction_hints_applied={result.extraction_hint_events} · "
            f"candidates={result.candidates} · clusters={result.clusters} · alerts={len(result.alerts)}"
        ),
        (
            f"watchlist_entries={result.watchlist_entries} · "
            f"watchlist_escalations={result.watchlist_escalations} · "
            f"routed={result.routed} · alertable={result.alertable}"
        ),
    ]
    if result.warnings:
        lines.append("warnings: " + "; ".join(result.warnings))
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


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
