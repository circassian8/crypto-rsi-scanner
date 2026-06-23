"""Research-only persistent watchlist for Event Alpha Radar candidates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alerts, event_fade, event_graph

WATCHLIST_SCHEMA_VERSION = "event_watchlist_v1"


class EventWatchlistState(str, Enum):
    RAW_EVIDENCE = "RAW_EVIDENCE"
    HYPOTHESIS = "HYPOTHESIS"
    RADAR = "RADAR"
    WATCHLIST = "WATCHLIST"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    EVENT_PASSED = "EVENT_PASSED"
    ARMED = "ARMED"
    TRIGGERED_FADE = "TRIGGERED_FADE"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


_STATE_RANK = {
    EventWatchlistState.RAW_EVIDENCE.value: 0,
    EventWatchlistState.HYPOTHESIS.value: 1,
    EventWatchlistState.RADAR.value: 2,
    EventWatchlistState.WATCHLIST.value: 3,
    EventWatchlistState.HIGH_PRIORITY.value: 4,
    EventWatchlistState.EVENT_PASSED.value: 5,
    EventWatchlistState.ARMED.value: 6,
    EventWatchlistState.TRIGGERED_FADE.value: 7,
    EventWatchlistState.INVALIDATED.value: -1,
    EventWatchlistState.EXPIRED.value: -1,
}


@dataclass(frozen=True)
class EventWatchlistConfig:
    enabled: bool = False
    state_path: Path | None = None
    expire_hours_after_event: float = 72.0
    max_alert_history: int = 20


@dataclass(frozen=True)
class EventWatchlistEntry:
    schema_version: str
    row_type: str
    key: str
    cluster_id: str | None
    event_id: str
    coin_id: str
    symbol: str
    relationship_type: str
    external_asset: str | None
    event_time: str | None
    state: str
    previous_state: str | None
    first_seen_at: str
    last_seen_at: str
    first_radar_at: str | None = None
    first_watchlisted_at: str | None = None
    first_high_priority_at: str | None = None
    first_event_passed_at: str | None = None
    first_armed_at: str | None = None
    first_triggered_at: str | None = None
    first_invalidated_at: str | None = None
    first_expired_at: str | None = None
    source_count: int = 0
    highest_score: int = 0
    latest_score: int = 0
    latest_tier: str = ""
    latest_event_name: str = ""
    latest_source: str = ""
    latest_playbook_type: str | None = None
    latest_rule_playbook_type: str | None = None
    latest_effective_playbook_type: str | None = None
    latest_llm_adjusted_playbook_type: str | None = None
    latest_playbook_score: int | None = None
    latest_playbook_action: str | None = None
    latest_llm_asset_role: str | None = None
    latest_llm_confidence: float | None = None
    latest_market_snapshot: dict[str, Any] = field(default_factory=dict)
    latest_score_components: dict[str, Any] = field(default_factory=dict)
    alert_history: list[dict[str, Any]] = field(default_factory=list)
    state_changed: bool = False
    escalation: bool = False
    score_jump: int = 0
    source_count_increased: bool = False
    event_time_upgraded: bool = False
    derivatives_crowding_upgraded: bool = False
    cluster_confidence_upgraded: bool = False
    material_change_reasons: tuple[str, ...] = ()
    should_alert: bool = False
    suppressed_reason: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventWatchlistRefreshResult:
    state_path: Path
    observed_at: str
    rows_written: int
    entries: list[EventWatchlistEntry]
    alert_entries: list[EventWatchlistEntry]


@dataclass(frozen=True)
class EventWatchlistReadResult:
    state_path: Path
    rows_read: int
    entries: list[EventWatchlistEntry]
    latest_only: bool


def refresh_watchlist(
    alerts: Iterable[event_alerts.EventAlertCandidate],
    *,
    cfg: EventWatchlistConfig,
    now: datetime | None = None,
) -> EventWatchlistRefreshResult:
    """Append current alert-derived watchlist state and flag escalations."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    observed_iso = observed.isoformat()
    state_path = cfg.state_path or Path("event_watchlist_state.jsonl")
    previous = {entry.key: entry for entry in load_watchlist(state_path).entries}
    entries = [
        _entry_from_alert(alert, previous.get(watchlist_key(alert)), observed, cfg)
        for alert in alerts
    ]
    rows_written = _append_entries(state_path, entries)
    alert_entries = [entry for entry in entries if entry.should_alert]
    return EventWatchlistRefreshResult(
        state_path=state_path,
        observed_at=observed_iso,
        rows_written=rows_written,
        entries=entries,
        alert_entries=alert_entries,
    )


def refresh_hypothesis_watchlist(
    hypotheses: Iterable[object],
    *,
    cfg: EventWatchlistConfig,
    now: datetime | None = None,
) -> EventWatchlistRefreshResult:
    """Append research-only impact hypotheses to watchlist state.

    Plain hypotheses are not alertable. A validated hypothesis can move to
    RADAR, but this still only routes as research metadata; it cannot create a
    TRIGGERED_FADE or bypass normal candidate/playbook gates.
    """
    observed = _as_utc(now or datetime.now(timezone.utc))
    observed_iso = observed.isoformat()
    state_path = cfg.state_path or Path("event_watchlist_state.jsonl")
    previous = {entry.key: entry for entry in load_watchlist(state_path).entries}
    entries = [
        _entry_from_hypothesis(hypothesis, previous.get(hypothesis_watchlist_key(hypothesis)), observed, cfg)
        for hypothesis in hypotheses
    ]
    rows_written = _append_entries(state_path, entries)
    alert_entries = [entry for entry in entries if entry.should_alert]
    return EventWatchlistRefreshResult(
        state_path=state_path,
        observed_at=observed_iso,
        rows_written=rows_written,
        entries=entries,
        alert_entries=alert_entries,
    )


def load_watchlist(
    state_path: str | Path,
    *,
    latest_only: bool = True,
) -> EventWatchlistReadResult:
    """Load persisted watchlist entries, tolerating old or malformed rows."""
    path = Path(state_path).expanduser()
    rows = [
        _entry_from_row(row)
        for row in _read_jsonl(path)
        if row.get("row_type") == "event_watchlist_state"
    ]
    entries = [row for row in rows if row is not None]
    rows_read = len(entries)
    if latest_only:
        latest: dict[str, tuple[datetime, int, EventWatchlistEntry]] = {}
        for idx, entry in enumerate(entries):
            observed = _parse_iso(entry.last_seen_at)
            current = latest.get(entry.key)
            if current is None or (observed, idx) >= (current[0], current[1]):
                latest[entry.key] = (observed, idx, entry)
        entries = [value[2] for value in latest.values()]
    return EventWatchlistReadResult(
        state_path=path,
        rows_read=rows_read,
        entries=sorted(entries, key=_entry_sort_key),
        latest_only=latest_only,
    )


def watchlist_key(alert: event_alerts.EventAlertCandidate) -> str:
    candidate = alert.discovery_candidate
    cluster_id = event_graph.cluster_id_for_event(candidate.event)
    playbook = alert.effective_playbook_type or alert.playbook_type or candidate.classification.relationship_type
    parts = (
        cluster_id,
        candidate.asset.coin_id,
        playbook,
    )
    return "|".join(str(part) for part in parts)


def hypothesis_watchlist_key(hypothesis: object) -> str:
    parts = (
        "hypothesis",
        getattr(hypothesis, "event_cluster_id", None) or getattr(hypothesis, "hypothesis_id", "unknown"),
        getattr(hypothesis, "impact_category", "unknown"),
    )
    return "|".join(str(part) for part in parts)


def format_watchlist_refresh_result(result: EventWatchlistRefreshResult) -> str:
    rows = [
        "=" * 76,
        "EVENT WATCHLIST REFRESH (research-only; not trade signals)",
        "=" * 76,
        f"state_path: {result.state_path}",
        f"observed_at: {result.observed_at}",
        f"rows_written: {result.rows_written}",
        f"candidates: {len(result.entries)} · alertable escalations: {len(result.alert_entries)}",
        "",
    ]
    if result.alert_entries:
        rows.append("Escalations:")
        for entry in result.alert_entries:
            rows.extend(_entry_lines(entry))
            rows.append("")
    else:
        rows.append("No meaningful state escalations. Duplicate/no-catalyst rows were persisted only as research state.")
    return "\n".join(rows).rstrip()


def format_watchlist_report(result: EventWatchlistReadResult) -> str:
    rows = [
        "=" * 76,
        "EVENT WATCHLIST REPORT (research-only; not trade signals)",
        "=" * 76,
        f"state_path: {result.state_path}",
        f"rows_read: {result.rows_read} · latest_entries: {len(result.entries)}",
    ]
    if not result.entries:
        rows.append("")
        rows.append("No event watchlist state found.")
        return "\n".join(rows)
    counts: dict[str, int] = {}
    for entry in result.entries:
        counts[entry.state] = counts.get(entry.state, 0) + 1
    rows.append("states: " + ", ".join(f"{state}={count}" for state, count in sorted(counts.items())))
    rows.append("")
    for entry in result.entries:
        rows.extend(_entry_lines(entry))
        rows.append("")
    return "\n".join(rows).rstrip()


def _entry_from_alert(
    alert: event_alerts.EventAlertCandidate,
    prior: EventWatchlistEntry | None,
    observed: datetime,
    cfg: EventWatchlistConfig,
) -> EventWatchlistEntry:
    candidate = alert.discovery_candidate
    event = candidate.event
    state = _state_from_alert(alert, observed, cfg)
    previous_state = prior.state if prior else None
    rank = _state_rank(state)
    previous_rank = _state_rank(previous_state)
    state_changed = previous_state is not None and previous_state != state.value
    escalation = previous_state is None and rank >= _STATE_RANK[EventWatchlistState.RADAR.value]
    escalation = escalation or (previous_state is not None and rank > previous_rank)
    material_reasons = _material_change_reasons(alert, prior)
    terminal = state in {EventWatchlistState.INVALIDATED, EventWatchlistState.EXPIRED}
    should_alert = (escalation or bool(material_reasons) or state == EventWatchlistState.TRIGGERED_FADE) and not terminal
    observed_iso = observed.isoformat()
    first_seen = prior.first_seen_at if prior else observed_iso
    history = list(prior.alert_history if prior else [])
    history.append({
        "observed_at": observed_iso,
        "state": state.value,
        "tier": alert.tier.value,
        "score": alert.opportunity_score,
        "rule_playbook_type": alert.rule_playbook_type,
        "effective_playbook_type": alert.effective_playbook_type or alert.playbook_type,
        "material_change_reasons": list(material_reasons),
        "should_alert": should_alert,
    })
    history = history[-max(1, cfg.max_alert_history):]
    warnings = list(prior.warnings if prior else [])
    if alert.rejected_reason:
        warnings.append(alert.rejected_reason)
    warnings = list(dict.fromkeys(warnings))
    entry = EventWatchlistEntry(
        schema_version=WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=watchlist_key(alert),
        cluster_id=event_graph.cluster_id_for_event(event),
        event_id=str(event.event_id),
        coin_id=str(candidate.asset.coin_id),
        symbol=str(candidate.asset.symbol),
        relationship_type=str(candidate.classification.relationship_type),
        external_asset=event.external_asset,
        event_time=event.event_time.isoformat() if event.event_time else None,
        state=state.value,
        previous_state=previous_state,
        first_seen_at=first_seen,
        last_seen_at=observed_iso,
        first_radar_at=_transition_time(prior, "first_radar_at", state, EventWatchlistState.RADAR, observed_iso),
        first_watchlisted_at=_transition_time(
            prior,
            "first_watchlisted_at",
            state,
            EventWatchlistState.WATCHLIST,
            observed_iso,
        ),
        first_high_priority_at=_transition_time(
            prior,
            "first_high_priority_at",
            state,
            EventWatchlistState.HIGH_PRIORITY,
            observed_iso,
        ),
        first_event_passed_at=_transition_time(
            prior,
            "first_event_passed_at",
            state,
            EventWatchlistState.EVENT_PASSED,
            observed_iso,
        ),
        first_armed_at=_transition_time(prior, "first_armed_at", state, EventWatchlistState.ARMED, observed_iso),
        first_triggered_at=_transition_time(
            prior,
            "first_triggered_at",
            state,
            EventWatchlistState.TRIGGERED_FADE,
            observed_iso,
        ),
        first_invalidated_at=_transition_time(
            prior,
            "first_invalidated_at",
            state,
            EventWatchlistState.INVALIDATED,
            observed_iso,
        ),
        first_expired_at=_transition_time(
            prior,
            "first_expired_at",
            state,
            EventWatchlistState.EXPIRED,
            observed_iso,
        ),
        source_count=len(event.raw_ids),
        highest_score=max(prior.highest_score if prior else 0, alert.opportunity_score),
        latest_score=alert.opportunity_score,
        latest_tier=alert.tier.value,
        latest_event_name=event.event_name,
        latest_source=event.source,
        latest_playbook_type=alert.effective_playbook_type or alert.playbook_type,
        latest_rule_playbook_type=alert.rule_playbook_type,
        latest_effective_playbook_type=alert.effective_playbook_type or alert.playbook_type,
        latest_llm_adjusted_playbook_type=alert.llm_adjusted_playbook_type,
        latest_playbook_score=alert.playbook_score,
        latest_playbook_action=alert.playbook_action,
        latest_llm_asset_role=alert.llm_asset_role,
        latest_llm_confidence=alert.llm_confidence,
        latest_market_snapshot=_market_snapshot(alert),
        latest_score_components=dict(alert.score_components),
        alert_history=history,
        state_changed=state_changed,
        escalation=escalation,
        score_jump=_score_jump(alert, prior),
        source_count_increased="new_independent_source" in material_reasons,
        event_time_upgraded="event_time_upgrade" in material_reasons,
        derivatives_crowding_upgraded="derivatives_crowding_upgrade" in material_reasons,
        cluster_confidence_upgraded="cluster_confidence_upgrade" in material_reasons,
        material_change_reasons=material_reasons,
        should_alert=should_alert,
        suppressed_reason=None if should_alert else _suppressed_reason(state, previous_state, state_changed),
        warnings=tuple(warnings),
    )
    return entry


def _entry_from_hypothesis(
    hypothesis: object,
    prior: EventWatchlistEntry | None,
    observed: datetime,
    cfg: EventWatchlistConfig,
) -> EventWatchlistEntry:
    status = str(getattr(hypothesis, "status", "") or "")
    validated = status == "validated"
    state = EventWatchlistState.RADAR if validated else EventWatchlistState.HYPOTHESIS
    previous_state = prior.state if prior else None
    rank = _state_rank(state)
    previous_rank = _state_rank(previous_state)
    state_changed = previous_state is not None and previous_state != state.value
    escalation = bool(validated and (previous_state is None or rank > previous_rank))
    observed_iso = observed.isoformat()
    first_seen = prior.first_seen_at if prior else observed_iso
    confidence = _optional_float(getattr(hypothesis, "confidence", None)) or 0.0
    score = max(0, min(100, int(round(confidence * 100))))
    symbols = tuple(str(value) for value in getattr(hypothesis, "candidate_symbols", ()) or ())
    coin_ids = tuple(str(value) for value in getattr(hypothesis, "candidate_coin_ids", ()) or ())
    category = str(getattr(hypothesis, "impact_category", "") or "impact_hypothesis")
    scope = str(getattr(hypothesis, "hypothesis_scope", "") or "sector")
    token_level = validated and scope == "token"
    symbol = symbols[0] if token_level and symbols else "SECTOR"
    coin_id = coin_ids[0] if token_level and coin_ids else category
    playbook = str(getattr(hypothesis, "playbook_hint", "") or "impact_hypothesis")
    event_name = f"{getattr(hypothesis, 'external_asset', None) or category} {scope} impact hypothesis"
    reasons = ("hypothesis_validated",) if validated else ()
    history = list(prior.alert_history if prior else [])
    history.append({
        "observed_at": observed_iso,
        "state": state.value,
        "tier": "RADAR_DIGEST" if validated else "STORE_ONLY",
        "score": score,
        "effective_playbook_type": playbook,
        "material_change_reasons": list(reasons),
        "should_alert": escalation,
    })
    history = history[-max(1, cfg.max_alert_history):]
    warnings = tuple(dict.fromkeys(
        str(value)
        for value in (
            *(prior.warnings if prior else ()),
            *tuple(getattr(hypothesis, "warnings", ()) or ()),
            *tuple(getattr(hypothesis, "rejection_reasons", ()) or ()),
        )
        if str(value)
    ))
    return EventWatchlistEntry(
        schema_version=WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=hypothesis_watchlist_key(hypothesis),
        cluster_id=_optional_str(getattr(hypothesis, "event_cluster_id", None)),
        event_id=str(getattr(hypothesis, "hypothesis_id", "") or hypothesis_watchlist_key(hypothesis)),
        coin_id=coin_id,
        symbol=symbol,
        relationship_type="impact_hypothesis",
        external_asset=_optional_str(getattr(hypothesis, "external_asset", None)),
        event_time=None,
        state=state.value,
        previous_state=previous_state,
        first_seen_at=first_seen,
        last_seen_at=observed_iso,
        first_radar_at=_transition_time(prior, "first_radar_at", state, EventWatchlistState.RADAR, observed_iso),
        first_watchlisted_at=prior.first_watchlisted_at if prior else None,
        first_high_priority_at=prior.first_high_priority_at if prior else None,
        first_event_passed_at=prior.first_event_passed_at if prior else None,
        first_armed_at=prior.first_armed_at if prior else None,
        first_triggered_at=prior.first_triggered_at if prior else None,
        first_invalidated_at=prior.first_invalidated_at if prior else None,
        first_expired_at=prior.first_expired_at if prior else None,
        source_count=len(tuple(getattr(hypothesis, "source_raw_ids", ()) or ())),
        highest_score=max(prior.highest_score if prior else 0, score),
        latest_score=score,
        latest_tier="RADAR_DIGEST" if validated else "STORE_ONLY",
        latest_event_name=event_name,
        latest_source="impact_hypothesis",
        latest_playbook_type=playbook,
        latest_rule_playbook_type=playbook,
        latest_effective_playbook_type=playbook,
        latest_playbook_score=score,
        latest_playbook_action="radar_digest" if validated else "store_only",
        latest_market_snapshot={},
        latest_score_components={
            "hypothesis_confidence": score,
            "hypothesis_scope": scope,
            "candidate_symbol_count": len(symbols),
            "candidate_symbols": list(symbols[:12]),
            "candidate_coin_ids": list(coin_ids[:12]),
            "validation_evidence": 100 if validated else 0,
        },
        alert_history=history,
        state_changed=state_changed,
        escalation=escalation,
        score_jump=score - int(prior.latest_score if prior else score),
        material_change_reasons=reasons,
        should_alert=escalation,
        suppressed_reason=None if escalation else (
            "validated hypothesis promoted to RADAR" if validated else "impact hypothesis awaiting asset validation"
        ),
        warnings=warnings,
    )


def _material_change_reasons(
    alert: event_alerts.EventAlertCandidate,
    prior: EventWatchlistEntry | None,
) -> tuple[str, ...]:
    if prior is None:
        return ()
    reasons: list[str] = []
    score_jump = _score_jump(alert, prior)
    if score_jump >= 10:
        reasons.append("score_jump")
    current_sources = int(alert.score_components.get("independent_source_count") or len(alert.discovery_candidate.event.raw_ids))
    previous_sources = int(prior.latest_score_components.get("independent_source_count") or prior.source_count or 0)
    if current_sources > previous_sources:
        reasons.append("new_independent_source")
    current_time = int(alert.score_components.get("event_time_consensus") or alert.score_components.get("event_time_quality") or 0)
    previous_time = int(
        prior.latest_score_components.get("event_time_consensus")
        or prior.latest_score_components.get("event_time_quality")
        or 0
    )
    if current_time >= 75 and current_time > previous_time:
        reasons.append("event_time_upgrade")
    current_derivatives = int(alert.score_components.get("derivatives_crowding") or 0)
    previous_derivatives = int(prior.latest_score_components.get("derivatives_crowding") or 0)
    if current_derivatives >= 50 and (previous_derivatives < 50 or current_derivatives - previous_derivatives >= 20):
        reasons.append("derivatives_crowding_upgrade")
    current_cluster = int(alert.score_components.get("cluster_confidence") or 0)
    previous_cluster = int(prior.latest_score_components.get("cluster_confidence") or 0)
    if current_cluster >= 65 and (previous_cluster < 65 or current_cluster - previous_cluster >= 15):
        reasons.append("cluster_confidence_upgrade")
    return tuple(dict.fromkeys(reasons))


def _score_jump(alert: event_alerts.EventAlertCandidate, prior: EventWatchlistEntry | None) -> int:
    if prior is None:
        return 0
    return int(alert.opportunity_score) - int(prior.latest_score or 0)


def _state_from_alert(
    alert: event_alerts.EventAlertCandidate,
    now: datetime,
    cfg: EventWatchlistConfig,
) -> EventWatchlistState:
    signal = alert.discovery_candidate.fade_signal
    signal_type = signal.signal_type if signal else event_fade.FadeSignalType.NO_TRADE
    fade_state = signal.state if signal else None
    if signal_type == event_fade.FadeSignalType.INVALIDATED or fade_state == event_fade.FadeState.INVALIDATED:
        return EventWatchlistState.INVALIDATED
    if alert.tier == event_alerts.EventAlertTier.STORE_ONLY:
        return EventWatchlistState.EXPIRED if _is_expired(alert, now, cfg) else EventWatchlistState.RAW_EVIDENCE
    if signal_type == event_fade.FadeSignalType.SHORT_TRIGGERED:
        return EventWatchlistState.TRIGGERED_FADE
    if _is_expired(alert, now, cfg):
        return EventWatchlistState.EXPIRED
    if signal_type == event_fade.FadeSignalType.ARMED or fade_state == event_fade.FadeState.ARMED:
        return EventWatchlistState.ARMED
    if fade_state == event_fade.FadeState.EVENT_PASSED or _event_has_passed(alert, now):
        return EventWatchlistState.EVENT_PASSED
    if alert.tier == event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH:
        return EventWatchlistState.HIGH_PRIORITY
    if alert.tier == event_alerts.EventAlertTier.WATCHLIST:
        return EventWatchlistState.WATCHLIST
    if alert.tier == event_alerts.EventAlertTier.RADAR_DIGEST:
        return EventWatchlistState.RADAR
    return EventWatchlistState.RAW_EVIDENCE


def _transition_time(
    prior: EventWatchlistEntry | None,
    field: str,
    state: EventWatchlistState,
    threshold: EventWatchlistState,
    observed_iso: str,
) -> str | None:
    previous = getattr(prior, field) if prior else None
    if previous:
        return previous
    if threshold in {EventWatchlistState.INVALIDATED, EventWatchlistState.EXPIRED}:
        return observed_iso if state == threshold else None
    if state == threshold or _state_rank(state.value) >= _state_rank(threshold.value):
        return observed_iso
    return None


def _suppressed_reason(
    state: EventWatchlistState,
    previous_state: str | None,
    state_changed: bool,
) -> str:
    if state == EventWatchlistState.RAW_EVIDENCE:
        return "raw/store-only evidence, no alertable watchlist state"
    if state in {EventWatchlistState.INVALIDATED, EventWatchlistState.EXPIRED}:
        return "terminal non-alert state"
    if previous_state is None:
        return "first state below alert threshold"
    if not state_changed:
        return "duplicate state, no escalation"
    return "state changed without rank escalation"


def _market_snapshot(alert: event_alerts.EventAlertCandidate) -> dict[str, Any]:
    fade_candidate = alert.discovery_candidate.fade_candidate
    if fade_candidate is None:
        return {}
    market = fade_candidate.market
    return {
        key: value
        for key, value in _json_ready(asdict(market)).items()
        if value not in (None, "", [], {})
    }


def _is_expired(
    alert: event_alerts.EventAlertCandidate,
    now: datetime,
    cfg: EventWatchlistConfig,
) -> bool:
    event_time = alert.discovery_candidate.event.event_time
    if event_time is None:
        return False
    if alert.tier == event_alerts.EventAlertTier.TRIGGERED_FADE:
        return False
    cutoff = _as_utc(event_time) + timedelta(hours=max(0.0, cfg.expire_hours_after_event))
    return now > cutoff


def _event_has_passed(alert: event_alerts.EventAlertCandidate, now: datetime) -> bool:
    event_time = alert.discovery_candidate.event.event_time
    return event_time is not None and now >= _as_utc(event_time)


def _append_entries(path: Path, entries: Iterable[EventWatchlistEntry]) -> int:
    data = list(entries)
    if not data:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for entry in data:
            fh.write(json.dumps(_json_ready(asdict(entry)), sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    return len(data)


def _entry_from_row(row: Mapping[str, Any]) -> EventWatchlistEntry | None:
    try:
        key = str(row.get("key") or "")
        event_id = str(row.get("event_id") or "")
        coin_id = str(row.get("coin_id") or "")
        symbol = str(row.get("symbol") or "")
        relationship_type = str(row.get("relationship_type") or "")
        if not key or not event_id or not coin_id or not relationship_type:
            return None
        state = str(row.get("state") or EventWatchlistState.RAW_EVIDENCE.value)
        if state not in _STATE_RANK:
            state = EventWatchlistState.RAW_EVIDENCE.value
        first_seen = str(row.get("first_seen_at") or row.get("last_seen_at") or "")
        last_seen = str(row.get("last_seen_at") or first_seen)
        return EventWatchlistEntry(
            schema_version=str(row.get("schema_version") or WATCHLIST_SCHEMA_VERSION),
            row_type="event_watchlist_state",
            key=key,
            cluster_id=_optional_str(row.get("cluster_id")),
            event_id=event_id,
            coin_id=coin_id,
            symbol=symbol,
            relationship_type=relationship_type,
            external_asset=_optional_str(row.get("external_asset")),
            event_time=_optional_str(row.get("event_time")),
            state=state,
            previous_state=_optional_str(row.get("previous_state")),
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            first_radar_at=_optional_str(row.get("first_radar_at")),
            first_watchlisted_at=_optional_str(row.get("first_watchlisted_at")),
            first_high_priority_at=_optional_str(row.get("first_high_priority_at")),
            first_event_passed_at=_optional_str(row.get("first_event_passed_at")),
            first_armed_at=_optional_str(row.get("first_armed_at")),
            first_triggered_at=_optional_str(row.get("first_triggered_at")),
            first_invalidated_at=_optional_str(row.get("first_invalidated_at")),
            first_expired_at=_optional_str(row.get("first_expired_at")),
            source_count=int(row.get("source_count") or 0),
            highest_score=int(row.get("highest_score") or row.get("latest_score") or 0),
            latest_score=int(row.get("latest_score") or 0),
            latest_tier=str(row.get("latest_tier") or ""),
            latest_event_name=str(row.get("latest_event_name") or ""),
            latest_source=str(row.get("latest_source") or ""),
            latest_playbook_type=_optional_str(row.get("latest_playbook_type")),
            latest_rule_playbook_type=_optional_str(row.get("latest_rule_playbook_type")),
            latest_effective_playbook_type=_optional_str(row.get("latest_effective_playbook_type"))
            or _optional_str(row.get("latest_playbook_type")),
            latest_llm_adjusted_playbook_type=_optional_str(row.get("latest_llm_adjusted_playbook_type")),
            latest_playbook_score=_optional_int(row.get("latest_playbook_score")),
            latest_playbook_action=_optional_str(row.get("latest_playbook_action")),
            latest_llm_asset_role=_optional_str(row.get("latest_llm_asset_role")),
            latest_llm_confidence=_optional_float(row.get("latest_llm_confidence")),
            latest_market_snapshot=dict(row.get("latest_market_snapshot") or {}),
            latest_score_components=dict(row.get("latest_score_components") or {}),
            alert_history=list(row.get("alert_history") or []),
            state_changed=bool(row.get("state_changed")),
            escalation=bool(row.get("escalation")),
            score_jump=int(row.get("score_jump") or 0),
            source_count_increased=bool(row.get("source_count_increased")),
            event_time_upgraded=bool(row.get("event_time_upgraded")),
            derivatives_crowding_upgraded=bool(row.get("derivatives_crowding_upgraded")),
            cluster_confidence_upgraded=bool(row.get("cluster_confidence_upgraded")),
            material_change_reasons=tuple(str(value) for value in row.get("material_change_reasons") or ()),
            should_alert=bool(row.get("should_alert")),
            suppressed_reason=_optional_str(row.get("suppressed_reason")),
            warnings=tuple(str(value) for value in row.get("warnings") or ()),
        )
    except (TypeError, ValueError):
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _entry_lines(entry: EventWatchlistEntry) -> list[str]:
    effective = entry.latest_effective_playbook_type or entry.latest_playbook_type or "unknown"
    rule = entry.latest_rule_playbook_type
    playbook_line = (
        f"  playbook: {effective} "
        f"score={entry.latest_playbook_score if entry.latest_playbook_score is not None else 0} "
        f"action={entry.latest_playbook_action or 'store_only'}"
    )
    if rule and rule != effective:
        playbook_line += f" · rule={rule}"
    return [
        f"{entry.state:<16} score={entry.latest_score:>3} high={entry.highest_score:>3} "
        f"{entry.symbol}/{entry.coin_id}",
        f"  event: {entry.latest_event_name}",
        f"  cluster: {entry.cluster_id or 'legacy'}",
        f"  external: {entry.external_asset or 'unknown'} · relationship: {entry.relationship_type}",
        f"  first_seen: {entry.first_seen_at} · last_seen: {entry.last_seen_at}",
        f"  tier: {entry.latest_tier or 'unknown'} · source_count: {entry.source_count} · source: {entry.latest_source}",
        playbook_line,
        f"  transition: {entry.previous_state or 'new'} -> {entry.state}"
        + (
            " · alertable escalation"
            if entry.should_alert and not entry.material_change_reasons
            else f" · alertable material change: {', '.join(entry.material_change_reasons)}"
            if entry.should_alert
            else f" · suppressed: {entry.suppressed_reason}"
        ),
    ]


def _entry_sort_key(entry: EventWatchlistEntry) -> tuple[int, int, str]:
    return (-_state_rank(entry.state), -entry.highest_score, entry.symbol)


def _state_rank(state: str | EventWatchlistState | None) -> int:
    if isinstance(state, EventWatchlistState):
        state = state.value
    return _STATE_RANK.get(str(state or ""), -1)


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _optional_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_iso(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(child) for child in value]
    return value


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
