"""Research-only lifecycle tracking for market-anomaly catalyst searches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, Mapping

from . import event_alerts, event_catalyst_search
from .event_models import RawDiscoveredEvent


class EventAnomalyLifecycleState(str, Enum):
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    CATALYST_SEARCHED = "CATALYST_SEARCHED"
    CATALYST_FOUND = "CATALYST_FOUND"
    CATALYST_VALIDATED = "CATALYST_VALIDATED"
    PLAYBOOK_ASSIGNED = "PLAYBOOK_ASSIGNED"
    ESCALATED = "ESCALATED"
    EXPIRED_NO_CATALYST = "EXPIRED_NO_CATALYST"


@dataclass(frozen=True)
class EventAnomalyStateEntry:
    anomaly_raw_id: str
    symbol: str
    state: str
    first_anomaly_at: datetime
    first_search_at: datetime | None = None
    first_catalyst_found_at: datetime | None = None
    first_validated_at: datetime | None = None
    search_query_count: int = 0
    search_result_count: int = 0
    rejected_result_count: int = 0
    validated_catalyst_count: int = 0
    assigned_playbook_count: int = 0
    escalated_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventAnomalyStateResult:
    entries: tuple[EventAnomalyStateEntry, ...] = ()

    @property
    def average_hours_to_catalyst_found(self) -> float | None:
        deltas = [
            (entry.first_catalyst_found_at - entry.first_anomaly_at).total_seconds() / 3600.0
            for entry in self.entries
            if entry.first_catalyst_found_at is not None
        ]
        if not deltas:
            return None
        return sum(deltas) / len(deltas)


def build_anomaly_lifecycle(
    raw_events: Iterable[RawDiscoveredEvent],
    catalyst_result: event_catalyst_search.CatalystSearchRunResult | None,
    alerts: Iterable[event_alerts.EventAlertCandidate],
    *,
    now: datetime | None = None,
    expire_hours_no_catalyst: float = 24.0,
) -> EventAnomalyStateResult:
    """Summarize anomaly -> catalyst -> playbook progress for this run."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    anomalies = {
        raw.raw_id: raw
        for raw in raw_events
        if raw.provider == "market_anomaly"
    }
    if catalyst_result is not None:
        for query in catalyst_result.queries:
            anomalies.setdefault(query.anomaly_raw_id, _synthetic_anomaly(query, observed))

    queries_by_anomaly: dict[str, list[event_catalyst_search.SearchQuery]] = {}
    accepted_by_anomaly: dict[str, list[event_catalyst_search.SearchResultEvent]] = {}
    rejected_by_anomaly: dict[str, list[event_catalyst_search.SearchResultEvent]] = {}
    if catalyst_result is not None:
        for query in catalyst_result.queries:
            queries_by_anomaly.setdefault(query.anomaly_raw_id, []).append(query)
        for result in catalyst_result.result_events:
            accepted_by_anomaly.setdefault(result.query.anomaly_raw_id, []).append(result)
        for result in catalyst_result.rejected_result_events:
            rejected_by_anomaly.setdefault(result.query.anomaly_raw_id, []).append(result)

    alerts_by_raw_id: dict[str, list[event_alerts.EventAlertCandidate]] = {}
    for alert in alerts:
        for raw_id in alert.discovery_candidate.event.raw_ids:
            alerts_by_raw_id.setdefault(raw_id, []).append(alert)

    entries: list[EventAnomalyStateEntry] = []
    for raw_id, anomaly in sorted(anomalies.items()):
        queries = queries_by_anomaly.get(raw_id, [])
        accepted = accepted_by_anomaly.get(raw_id, [])
        rejected = rejected_by_anomaly.get(raw_id, [])
        accepted_raw_ids = {result.raw_event.raw_id for result in accepted}
        validated_alerts = [
            alert for raw_result_id in accepted_raw_ids
            for alert in alerts_by_raw_id.get(raw_result_id, [])
            if alert.discovery_candidate.event.source != "market_anomaly"
        ]
        assigned = [
            alert for alert in validated_alerts
            if (alert.effective_playbook_type or alert.playbook_type)
            not in {None, "market_anomaly", "market_anomaly_unknown", "source_noise_control", "ambiguous_control"}
        ]
        escalated = [
            alert for alert in assigned
            if alert.tier in {
                event_alerts.EventAlertTier.WATCHLIST,
                event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH,
                event_alerts.EventAlertTier.TRIGGERED_FADE,
            }
        ]
        first_anomaly_at = _as_utc(anomaly.published_at or anomaly.fetched_at)
        first_found = min((_as_utc(result.raw_event.published_at or result.raw_event.fetched_at) for result in accepted), default=None)
        first_validated = min((alert.discovery_candidate.event.first_seen_time for alert in validated_alerts), default=None)
        state = _entry_state(
            first_anomaly_at=first_anomaly_at,
            searched=bool(queries),
            found=bool(accepted),
            validated=bool(validated_alerts),
            assigned=bool(assigned),
            escalated=bool(escalated),
            now=observed,
            expire_hours_no_catalyst=expire_hours_no_catalyst,
        )
        entries.append(EventAnomalyStateEntry(
            anomaly_raw_id=raw_id,
            symbol=_event_symbol(anomaly),
            state=state.value,
            first_anomaly_at=first_anomaly_at,
            first_search_at=observed if queries else None,
            first_catalyst_found_at=first_found,
            first_validated_at=first_validated,
            search_query_count=len(queries),
            search_result_count=len(accepted),
            rejected_result_count=len(rejected),
            validated_catalyst_count=len(validated_alerts),
            assigned_playbook_count=len(assigned),
            escalated_count=len(escalated),
            warnings=_entry_warnings(state, accepted, rejected, assigned, escalated),
        ))
    return EventAnomalyStateResult(entries=tuple(entries))


def format_anomaly_lifecycle_report(result: EventAnomalyStateResult | None) -> str:
    rows = [
        "=" * 76,
        "EVENT ANOMALY LIFECYCLE REPORT (research-only; no alerts or trades)",
        "=" * 76,
    ]
    if result is None:
        rows.append("No anomaly lifecycle was built.")
        return "\n".join(rows)
    rows.append(f"anomalies={len(result.entries)}")
    counts: dict[str, int] = {}
    for entry in result.entries:
        counts[entry.state] = counts.get(entry.state, 0) + 1
    if counts:
        rows.append("states: " + ", ".join(f"{state}={count}" for state, count in sorted(counts.items())))
    avg = result.average_hours_to_catalyst_found
    if avg is not None:
        rows.append(f"avg_hours_anomaly_to_catalyst_found={avg:.2f}")
    if not result.entries:
        return "\n".join(rows)
    rows.append("")
    for entry in result.entries[:30]:
        rows.append(
            f"{entry.state:<22} {entry.symbol or 'UNKNOWN'} {entry.anomaly_raw_id} "
            f"queries={entry.search_query_count} results={entry.search_result_count} "
            f"validated={entry.validated_catalyst_count} escalated={entry.escalated_count}"
        )
        if entry.warnings:
            rows.append("  warnings: " + "; ".join(entry.warnings))
    return "\n".join(rows).rstrip()


def _entry_state(
    *,
    first_anomaly_at: datetime,
    searched: bool,
    found: bool,
    validated: bool,
    assigned: bool,
    escalated: bool,
    now: datetime,
    expire_hours_no_catalyst: float,
) -> EventAnomalyLifecycleState:
    if escalated:
        return EventAnomalyLifecycleState.ESCALATED
    if assigned:
        return EventAnomalyLifecycleState.PLAYBOOK_ASSIGNED
    if validated:
        return EventAnomalyLifecycleState.CATALYST_VALIDATED
    if found:
        return EventAnomalyLifecycleState.CATALYST_FOUND
    if searched:
        if now - first_anomaly_at >= timedelta(hours=max(0.0, expire_hours_no_catalyst)):
            return EventAnomalyLifecycleState.EXPIRED_NO_CATALYST
        return EventAnomalyLifecycleState.CATALYST_SEARCHED
    return EventAnomalyLifecycleState.ANOMALY_DETECTED


def _entry_warnings(
    state: EventAnomalyLifecycleState,
    accepted: Iterable[event_catalyst_search.SearchResultEvent],
    rejected: Iterable[event_catalyst_search.SearchResultEvent],
    assigned: Iterable[event_alerts.EventAlertCandidate],
    escalated: Iterable[event_alerts.EventAlertCandidate],
) -> tuple[str, ...]:
    warnings: list[str] = []
    if state == EventAnomalyLifecycleState.EXPIRED_NO_CATALYST:
        warnings.append("no validated catalyst found before expiry")
    if not tuple(accepted) and tuple(rejected):
        warnings.append("search results were rejected by quality scoring")
    if tuple(escalated):
        if any(alert.tier == event_alerts.EventAlertTier.TRIGGERED_FADE for alert in escalated):
            warnings.append("triggered fade must be proxy_fade from event_fade.py")
    elif tuple(assigned):
        warnings.append("playbook assigned without state escalation")
    return tuple(dict.fromkeys(warnings))


def _synthetic_anomaly(query: event_catalyst_search.SearchQuery, observed: datetime) -> RawDiscoveredEvent:
    return RawDiscoveredEvent(
        raw_id=query.anomaly_raw_id,
        provider="market_anomaly",
        fetched_at=observed,
        published_at=observed,
        source_url=None,
        title=f"{query.symbol} market anomaly",
        body=None,
        raw_json={"market": {"symbol": query.symbol}, "anomaly": {"score": 0}},
        source_confidence=0.0,
        content_hash=query.anomaly_raw_id,
    )


def _event_symbol(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
    asset = payload.get("asset") if isinstance(payload.get("asset"), Mapping) else {}
    for value in (market.get("symbol"), asset.get("symbol"), payload.get("symbol")):
        symbol = str(value or "").strip().upper()
        if symbol:
            return symbol
    return raw.title.split(" ", 1)[0].strip("():,").upper() if raw.title else ""


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
