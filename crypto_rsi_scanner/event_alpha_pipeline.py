"""Unified research-only Event Alpha Radar pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import (
    event_alerts,
    event_alpha_router,
    event_llm_analyzer,
    event_llm_extractor,
    event_watchlist,
)
from .event_models import EventDiscoveryResult


@dataclass(frozen=True)
class EventAlphaPipelineResult:
    discovery_result: EventDiscoveryResult
    alerts: list[event_alerts.EventAlertCandidate]
    extraction_rows: list[event_llm_extractor.EventLLMExtractionReportRow]
    relationship_rows: list[event_llm_analyzer.EventLLMReportRow]
    watchlist_result: event_watchlist.EventWatchlistRefreshResult | None
    router_result: event_alpha_router.EventAlphaRouterResult | None
    warnings: tuple[str, ...] = ()

    @property
    def raw_events(self) -> int:
        return len(self.discovery_result.raw_events)

    @property
    def extractions(self) -> int:
        return len([row for row in self.extraction_rows if row.extraction is not None])

    @property
    def candidates(self) -> int:
        return len(self.discovery_result.candidates)

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
) -> EventAlphaPipelineResult:
    """Run the research-only Event Alpha pipeline over a discovery result."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    alert_cfg = alert_cfg or event_alerts.EventAlertConfig()
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


def format_event_alpha_pipeline_report(result: EventAlphaPipelineResult) -> str:
    """Format a concise Event Alpha cycle summary."""
    lines = [
        "=" * 76,
        "EVENT ALPHA PIPELINE REPORT (research-only; no trades, paper rows, or live RSI routing)",
        "=" * 76,
        (
            f"raw_events={result.raw_events} · extractions={result.extractions}/{len(result.extraction_rows)} · "
            f"candidates={result.candidates} · alerts={len(result.alerts)}"
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
