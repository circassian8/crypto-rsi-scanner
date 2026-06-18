"""Research-only routing decisions for Event Alpha Radar watchlist rows."""

from __future__ import annotations

import html
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from . import event_playbooks, event_watchlist


class EventAlphaRoute(str, Enum):
    SUPPRESS_DUPLICATE = "SUPPRESS_DUPLICATE"
    STORE_ONLY = "STORE_ONLY"
    LOCAL_REPORT = "LOCAL_REPORT"
    RESEARCH_DIGEST = "RESEARCH_DIGEST"
    HIGH_PRIORITY_RESEARCH = "HIGH_PRIORITY_RESEARCH"
    TRIGGERED_FADE_RESEARCH = "TRIGGERED_FADE_RESEARCH"


@dataclass(frozen=True)
class EventAlphaRouterConfig:
    enabled: bool = False
    include_suppressed: bool = True


@dataclass(frozen=True)
class EventAlphaRouteDecision:
    entry: event_watchlist.EventWatchlistEntry
    route: EventAlphaRoute
    alertable: bool
    reason: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventAlphaRouterResult:
    state_path: Path
    rows_read: int
    decisions: list[EventAlphaRouteDecision]
    enabled: bool

    @property
    def alertable_decisions(self) -> list[EventAlphaRouteDecision]:
        return [decision for decision in self.decisions if decision.alertable]


def route_watchlist(
    read_result: event_watchlist.EventWatchlistReadResult,
    *,
    cfg: EventAlphaRouterConfig | None = None,
) -> EventAlphaRouterResult:
    """Convert latest watchlist state into artifact-only research route decisions."""
    cfg = cfg or EventAlphaRouterConfig()
    decisions = [_route_entry(entry, cfg=cfg) for entry in read_result.entries]
    if not cfg.include_suppressed:
        decisions = [decision for decision in decisions if decision.alertable]
    return EventAlphaRouterResult(
        state_path=read_result.state_path,
        rows_read=read_result.rows_read,
        decisions=sorted(decisions, key=_decision_sort_key),
        enabled=cfg.enabled,
    )


def format_router_report(result: EventAlphaRouterResult) -> str:
    rows = [
        "=" * 76,
        "EVENT ALPHA ROUTER REPORT (research-only; no sends, trades, or paper rows)",
        "=" * 76,
        f"state_path: {result.state_path}",
        f"router_enabled: {str(result.enabled).lower()}",
        f"rows_read: {result.rows_read} · decisions: {len(result.decisions)} · alertable: {len(result.alertable_decisions)}",
    ]
    if not result.enabled:
        rows.append("disabled: set RSI_EVENT_ALPHA_ROUTER_ENABLED=1 for route decisions.")
    if not result.decisions:
        rows.append("")
        rows.append("No watchlist rows to route.")
        return "\n".join(rows)
    counts: dict[str, int] = {}
    for decision in result.decisions:
        counts[decision.route.value] = counts.get(decision.route.value, 0) + 1
    rows.append("routes: " + ", ".join(f"{route}={count}" for route, count in sorted(counts.items())))
    rows.append("")
    for decision in result.decisions:
        entry = decision.entry
        rows.append(
            f"{decision.route.value:<24} score={entry.latest_score:>3} high={entry.highest_score:>3} "
            f"{entry.symbol}/{entry.coin_id}"
        )
        rows.append(f"  event: {entry.latest_event_name}")
        rows.append(
            f"  state: {entry.previous_state or 'new'} -> {entry.state} · "
            f"watchlist_alertable={str(entry.should_alert).lower()}"
        )
        rows.append(
            f"  playbook: {entry.latest_playbook_type or 'unknown'} "
            f"action={entry.latest_playbook_action or 'store_only'}"
        )
        rows.append(f"  route reason: {decision.reason}")
        if entry.latest_llm_asset_role:
            rows.append(
                f"  llm: role={entry.latest_llm_asset_role} "
                f"conf={entry.latest_llm_confidence if entry.latest_llm_confidence is not None else 0.0:.2f}"
            )
        warnings = (*entry.warnings, *decision.warnings)
        if warnings:
            rows.append("  warnings: " + "; ".join(dict.fromkeys(warnings)))
        if entry.suppressed_reason:
            rows.append(f"  watchlist suppressed: {entry.suppressed_reason}")
        rows.append("")
    return "\n".join(rows).rstrip()


def format_routed_telegram_digest(decisions: Iterable[EventAlphaRouteDecision]) -> str:
    """Render router-approved Event Alpha escalations for Telegram."""
    keep = [decision for decision in decisions if decision.alertable]
    lines = [
        "<b>Event Alpha routed research alerts</b>",
        "<i>Research alert only. Not a trade signal, paper trade, or execution.</i>",
    ]
    if not keep:
        lines.append("No router-approved escalations.")
        return "\n".join(lines)
    for decision in keep:
        entry = decision.entry
        lines.append("")
        lines.append(
            f"<b>{_esc(decision.route.value)}</b> score={entry.latest_score} "
            f"<b>{_esc(entry.symbol)}</b>"
        )
        lines.append(_esc(entry.latest_event_name or "unknown event"))
        lines.append(
            f"state={_esc(entry.state)} playbook={_esc(entry.latest_playbook_type or 'unknown')} "
            f"external={_esc(entry.external_asset or 'unknown')}"
        )
        if entry.latest_rule_playbook_type and entry.latest_rule_playbook_type != entry.latest_playbook_type:
            lines.append(f"rule_playbook={_esc(entry.latest_rule_playbook_type)}")
        if entry.latest_llm_asset_role:
            conf = entry.latest_llm_confidence if entry.latest_llm_confidence is not None else 0.0
            lines.append(f"llm={_esc(entry.latest_llm_asset_role)} conf={conf:.2f}")
        lines.append(f"route_reason={_esc(decision.reason)}")
        warnings = tuple(dict.fromkeys((*entry.warnings, *decision.warnings)))
        if warnings:
            lines.append("warnings=" + _esc("; ".join(warnings[:3])))
    return "\n".join(lines)


def _route_entry(
    entry: event_watchlist.EventWatchlistEntry,
    *,
    cfg: EventAlphaRouterConfig,
) -> EventAlphaRouteDecision:
    playbook = entry.latest_playbook_type or ""
    state = entry.state
    warnings = list(entry.warnings)

    if not cfg.enabled:
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.STORE_ONLY,
            alertable=False,
            reason="Event Alpha router is disabled; retaining watchlist row as research evidence only.",
            warnings=tuple(warnings),
        )

    if _is_raw_or_terminal(state):
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.STORE_ONLY,
            alertable=False,
            reason="Raw, expired, or invalidated watchlist state is stored only.",
            warnings=tuple(warnings),
        )

    if not entry.should_alert:
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.SUPPRESS_DUPLICATE,
            alertable=False,
            reason=entry.suppressed_reason or "No meaningful state escalation since the previous observation.",
            warnings=tuple(warnings),
        )

    if state == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value:
        if playbook == event_playbooks.EventPlaybookType.PROXY_FADE.value:
            return EventAlphaRouteDecision(
                entry=entry,
                route=EventAlphaRoute.TRIGGERED_FADE_RESEARCH,
                alertable=True,
                reason="Proxy-fade playbook reached TRIGGERED_FADE from the deterministic event_fade engine.",
                warnings=tuple(warnings),
            )
        warnings.append("non-proxy playbook cannot route triggered fade")
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.LOCAL_REPORT,
            alertable=False,
            reason="Triggered state is retained for local review because the playbook is not proxy_fade.",
            warnings=tuple(warnings),
        )

    if playbook in {
        event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
        event_playbooks.EventPlaybookType.AMBIGUOUS_CONTROL.value,
        event_playbooks.EventPlaybookType.MARKET_ANOMALY.value,
        event_playbooks.EventPlaybookType.MARKET_ANOMALY_UNKNOWN.value,
    }:
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.STORE_ONLY,
            alertable=False,
            reason="Control/anomaly playbooks are evidence only until catalyst and asset identity are validated.",
            warnings=tuple(warnings),
        )

    if playbook == event_playbooks.EventPlaybookType.INFRASTRUCTURE_MENTION.value:
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.LOCAL_REPORT,
            alertable=False,
            reason="Infrastructure playbooks may be reviewed locally but cannot enter research digest routing.",
            warnings=tuple(warnings),
        )

    if playbook in _NON_FADE_RESEARCH_PLAYBOOKS:
        route = (
            EventAlphaRoute.HIGH_PRIORITY_RESEARCH
            if state in {
                event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
                event_watchlist.EventWatchlistState.ARMED.value,
                event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            }
            else EventAlphaRoute.RESEARCH_DIGEST
        )
        return EventAlphaRouteDecision(
            entry=entry,
            route=route,
            alertable=True,
            reason="Non-fade event playbook produced a research-only state escalation.",
            warnings=tuple(warnings),
        )

    if state in {
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.ARMED.value,
        event_watchlist.EventWatchlistState.EVENT_PASSED.value,
    }:
        route = (
            EventAlphaRoute.HIGH_PRIORITY_RESEARCH
            if playbook == event_playbooks.EventPlaybookType.PROXY_FADE.value
            else EventAlphaRoute.RESEARCH_DIGEST
        )
        return EventAlphaRouteDecision(
            entry=entry,
            route=route,
            alertable=True,
            reason="Proxy candidate escalated to a higher watchlist state.",
            warnings=tuple(warnings),
        )

    if state in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.RADAR.value,
    } and playbook in {
        event_playbooks.EventPlaybookType.PROXY_FADE.value,
        event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
    }:
        return EventAlphaRouteDecision(
            entry=entry,
            route=EventAlphaRoute.RESEARCH_DIGEST,
            alertable=True,
            reason="Proxy candidate produced a meaningful radar/watchlist escalation.",
            warnings=tuple(warnings),
        )

    return EventAlphaRouteDecision(
        entry=entry,
        route=EventAlphaRoute.LOCAL_REPORT,
        alertable=False,
        reason="Unrecognized playbook/state combination is kept in local research output only.",
        warnings=tuple(warnings),
    )


def _is_raw_or_terminal(state: str) -> bool:
    return state in {
        event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        event_watchlist.EventWatchlistState.INVALIDATED.value,
        event_watchlist.EventWatchlistState.EXPIRED.value,
    }


def _decision_sort_key(decision: EventAlphaRouteDecision) -> tuple[int, int, str]:
    rank = {
        EventAlphaRoute.TRIGGERED_FADE_RESEARCH: 0,
        EventAlphaRoute.HIGH_PRIORITY_RESEARCH: 1,
        EventAlphaRoute.RESEARCH_DIGEST: 2,
        EventAlphaRoute.LOCAL_REPORT: 3,
        EventAlphaRoute.SUPPRESS_DUPLICATE: 4,
        EventAlphaRoute.STORE_ONLY: 5,
    }
    entry = decision.entry
    return (rank[decision.route], -entry.highest_score, entry.symbol)


_NON_FADE_RESEARCH_PLAYBOOKS = {
    event_playbooks.EventPlaybookType.DIRECT_EVENT.value,
    event_playbooks.EventPlaybookType.LISTING_VOLATILITY.value,
    event_playbooks.EventPlaybookType.PERP_LISTING_SQUEEZE.value,
    event_playbooks.EventPlaybookType.UNLOCK_SUPPLY_PRESSURE.value,
    event_playbooks.EventPlaybookType.AIRDROP_TGE_SELL_PRESSURE.value,
    event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
    event_playbooks.EventPlaybookType.POLITICAL_MEME_EVENT.value,
    event_playbooks.EventPlaybookType.RWA_PREIPO_PROXY.value,
    event_playbooks.EventPlaybookType.AI_IPO_PROXY.value,
    event_playbooks.EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK.value,
}


def _esc(value: object) -> str:
    return html.escape(str(value), quote=False)
