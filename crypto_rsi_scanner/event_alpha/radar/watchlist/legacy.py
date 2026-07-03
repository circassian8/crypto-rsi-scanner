"""Research-only persistent watchlist for Event Alpha Radar candidates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import event_alerts, event_alpha_quality_fields, event_fade, event_graph

WATCHLIST_SCHEMA_VERSION = "event_watchlist_v1"


class EventWatchlistState(str, Enum):
    RAW_EVIDENCE = "RAW_EVIDENCE"
    HYPOTHESIS = "HYPOTHESIS"
    QUALITY_BLOCKED = "QUALITY_BLOCKED"
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
    EventWatchlistState.QUALITY_BLOCKED.value: 1,
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
    incident_id: str | None = None
    hypothesis_id: str | None = None
    incident_canonical_name: str | None = None
    incident_primary_subject: str | None = None
    incident_affected_ecosystem: str | None = None
    incident_cause_status: str | None = None
    incident_market_reaction_observed: bool | None = None
    incident_causal_mechanism_confirmed: bool | None = None
    incident_link_status: str | None = None
    incident_link_reason: str | None = None
    requested_state_before_quality_gate: str | None = None
    final_state_after_quality_gate: str | None = None
    quality_state_block_reason: str | None = None
    state_quality_capped: bool = False
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
    impact_path_type: str | None = None
    impact_path_strength: str | None = None
    candidate_role: str | None = None
    evidence_quality_score: float | None = None
    source_class: str | None = None
    evidence_specificity: str | None = None
    market_confirmation_score: float | None = None
    market_confirmation_level: str | None = None
    market_context_freshness_status: str | None = None
    market_context_age_hours: float | str | None = None
    market_context_stale: bool | None = None
    market_context_freshness_cap_applied: bool | None = None
    opportunity_score_final: float | None = None
    opportunity_level: str | None = None
    opportunity_verdict_reasons: list[str] = field(default_factory=list)
    why_local_only: str | None = None
    why_not_watchlist: str | None = None
    manual_verification_items: list[str] = field(default_factory=list)
    upgrade_requirements: list[str] = field(default_factory=list)
    downgrade_warnings: list[str] = field(default_factory=list)
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
    incident_id = _optional_str(getattr(hypothesis, "incident_id", None))
    if incident_id:
        return "|".join((
            "hypothesis",
            incident_id,
            _hypothesis_key_asset_identity(hypothesis),
            _optional_str(getattr(hypothesis, "candidate_role", None)) or "unknown_role",
            _optional_str(getattr(hypothesis, "impact_path_type", None)) or "unknown_path",
        ))
    parts = (
        "hypothesis",
        getattr(hypothesis, "event_cluster_id", None) or getattr(hypothesis, "hypothesis_id", "unknown"),
        getattr(hypothesis, "impact_category", "unknown"),
    )
    return "|".join(str(part) for part in parts)


def _hypothesis_key_asset_identity(hypothesis: object) -> str:
    asset = _direct_validated_hypothesis_asset(hypothesis)
    if not asset:
        asset = _first_validated_asset(getattr(hypothesis, "crypto_candidate_assets", ()) or ())
    if not asset:
        asset = _first_validated_asset(getattr(hypothesis, "validated_candidate_assets", ()) or ())
    symbol = str(asset.get("symbol") or "").strip().upper() if asset else ""
    coin_id = str(asset.get("coin_id") or "").strip() if asset else ""
    if coin_id:
        return coin_id
    if symbol:
        return symbol
    sectors = tuple(str(value) for value in getattr(hypothesis, "candidate_sectors", ()) or () if str(value))
    if sectors:
        return "sector:" + ",".join(sectors[:4])
    return "sector:" + str(getattr(hypothesis, "impact_category", "") or "unknown")


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


def quality_cap_watchlist_state(
    requested_state: str | EventWatchlistState | None,
    quality_bundle: Mapping[str, Any] | None,
) -> tuple[str, str | None]:
    """Return the lifecycle state allowed by the final quality verdict.

    This is a research-artifact safety cap, not a scoring model. It prevents
    local-only or insufficient-data rows from surviving as active watchlist
    candidates while preserving deterministic event-fade triggers.
    """
    requested = _state_value(requested_state)
    if requested == EventWatchlistState.TRIGGERED_FADE.value:
        return requested, None
    if requested in {
        EventWatchlistState.INVALIDATED.value,
        EventWatchlistState.EXPIRED.value,
    }:
        return requested, None
    if not _quality_bundle_has_authority(quality_bundle):
        return requested, None
    raw_quality = dict(quality_bundle or {})
    quality = event_alpha_quality_fields.ensure_quality_fields(raw_quality)
    level = str(quality.get("opportunity_level") or "").strip()
    score = _optional_float(quality.get("opportunity_score_final"))
    impact = str(quality.get("impact_path_type") or "").strip()
    evidence = str(quality.get("evidence_specificity") or "").strip()
    source = str(quality.get("source_class") or "").strip()
    role = str(quality.get("candidate_role") or "").strip()
    requested_rank = _state_rank(requested)

    block = _quality_state_block_reason(quality, level=level, score=score, impact=impact, evidence=evidence, source=source, role=role)
    if block:
        if level == "exploratory" and requested_rank >= _STATE_RANK[EventWatchlistState.WATCHLIST.value]:
            return EventWatchlistState.RADAR.value, block
        if requested_rank >= _STATE_RANK[EventWatchlistState.RADAR.value]:
            return EventWatchlistState.QUALITY_BLOCKED.value, block
        return requested, block
    if level == "validated_digest" and requested_rank > _STATE_RANK[EventWatchlistState.RADAR.value]:
        return EventWatchlistState.RADAR.value, "opportunity_level_caps_state:validated_digest"
    if (
        level == "watchlist"
        and requested_rank > _STATE_RANK[EventWatchlistState.WATCHLIST.value]
        and requested not in {
            EventWatchlistState.EVENT_PASSED.value,
            EventWatchlistState.ARMED.value,
        }
    ):
        return EventWatchlistState.WATCHLIST.value, "opportunity_level_caps_state:watchlist"
    return requested, None


def final_state_value(entry: EventWatchlistEntry | Mapping[str, Any]) -> str:
    """Return the quality-capped state for an entry or raw row."""
    if isinstance(entry, Mapping):
        final = _optional_str(entry.get("final_state_after_quality_gate"))
        requested = _optional_str(entry.get("requested_state_before_quality_gate")) or _optional_str(entry.get("state"))
        persisted_final = _state_value(final)
        if persisted_final in {
            EventWatchlistState.TRIGGERED_FADE.value,
            EventWatchlistState.INVALIDATED.value,
            EventWatchlistState.EXPIRED.value,
        }:
            return persisted_final
        components = entry.get("latest_score_components")
        if event_alpha_quality_fields.has_any_quality_field(entry, components_key="latest_score_components"):
            quality = event_alpha_quality_fields.ensure_quality_fields(
                entry,
                components=dict(components if isinstance(components, Mapping) else {}),
            )
            return quality_cap_watchlist_state(requested, quality)[0]
        if final:
            return persisted_final
        return _state_value(requested)
    final = entry.final_state_after_quality_gate
    if final:
        return _state_value(final)
    quality = _quality_bundle_from_entry(entry)
    return quality_cap_watchlist_state(entry.requested_state_before_quality_gate or entry.state, quality)[0]


def requested_state_value(entry: EventWatchlistEntry | Mapping[str, Any]) -> str:
    if isinstance(entry, Mapping):
        return _state_value(entry.get("requested_state_before_quality_gate") or entry.get("state"))
    return _state_value(entry.requested_state_before_quality_gate or entry.state)


def state_is_quality_capped(entry: EventWatchlistEntry | Mapping[str, Any]) -> bool:
    if isinstance(entry, Mapping):
        raw = entry.get("state_quality_capped")
        if raw is True:
            return bool(raw)
        return requested_state_value(entry) != final_state_value(entry)
    return bool(entry.state_quality_capped is True or requested_state_value(entry) != final_state_value(entry))


def _entry_from_alert(
    alert: event_alerts.EventAlertCandidate,
    prior: EventWatchlistEntry | None,
    observed: datetime,
    cfg: EventWatchlistConfig,
) -> EventWatchlistEntry:
    candidate = alert.discovery_candidate
    event = candidate.event
    requested_state = _state_from_alert(alert, observed, cfg)
    quality = event_alpha_quality_fields.ensure_quality_fields({}, components=alert.score_components)
    score_components = {
        **dict(alert.score_components),
        **quality,
        "source_raw_ids": list(event.raw_ids),
        "source_event_ids": [event.event_id],
    }
    final_state, quality_state_block = quality_cap_watchlist_state(requested_state, score_components)
    state = EventWatchlistState(final_state)
    previous_state = prior.state if prior else None
    rank = _state_rank(state)
    previous_rank = _state_rank(previous_state)
    state_changed = previous_state is not None and previous_state != state.value
    escalation = previous_state is None and rank >= _STATE_RANK[EventWatchlistState.RADAR.value]
    escalation = escalation or (previous_state is not None and rank > previous_rank)
    material_reasons = _material_change_reasons(alert, prior)
    state_quality_capped = bool(quality_state_block and state.value != requested_state.value)
    if prior and prior.state_quality_capped and not state_quality_capped and _state_rank(requested_state) >= _STATE_RANK[EventWatchlistState.WATCHLIST.value]:
        material_reasons = tuple(dict.fromkeys((*material_reasons, "quality_state_upgraded")))
    terminal = state in {EventWatchlistState.INVALIDATED, EventWatchlistState.EXPIRED, EventWatchlistState.QUALITY_BLOCKED}
    should_alert = (
        escalation
        or bool(material_reasons)
        or state == EventWatchlistState.TRIGGERED_FADE
    ) and not terminal and not state_quality_capped
    observed_iso = observed.isoformat()
    first_seen = prior.first_seen_at if prior else observed_iso
    history = list(prior.alert_history if prior else [])
    history.append({
        "observed_at": observed_iso,
        "state": state.value,
        "requested_state_before_quality_gate": requested_state.value,
        "final_state_after_quality_gate": state.value,
        "quality_state_block_reason": quality_state_block,
        "state_quality_capped": state_quality_capped,
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
    if quality_state_block:
        warnings.append(f"quality_state_blocked:{quality_state_block}")
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
        incident_id=_optional_str(alert.score_components.get("incident_id")),
        hypothesis_id=_optional_str(alert.score_components.get("hypothesis_id")),
        incident_canonical_name=_optional_str(
            alert.score_components.get("incident_canonical_name")
            or alert.score_components.get("canonical_incident_name")
        ),
        incident_primary_subject=_optional_str(
            alert.score_components.get("incident_primary_subject")
            or alert.score_components.get("primary_subject")
        ),
        incident_affected_ecosystem=_optional_str(
            alert.score_components.get("incident_affected_ecosystem")
            or alert.score_components.get("affected_ecosystem")
        ),
        incident_cause_status=_optional_str(
            alert.score_components.get("incident_cause_status")
            or alert.score_components.get("cause_status")
        ),
        incident_market_reaction_observed=_optional_bool(
            alert.score_components.get("incident_market_reaction_observed")
            if "incident_market_reaction_observed" in alert.score_components
            else alert.score_components.get("market_reaction_observed")
        ),
        incident_causal_mechanism_confirmed=_optional_bool(
            alert.score_components.get("incident_causal_mechanism_confirmed")
            if "incident_causal_mechanism_confirmed" in alert.score_components
            else alert.score_components.get("causal_mechanism_confirmed")
        ),
        requested_state_before_quality_gate=requested_state.value,
        final_state_after_quality_gate=state.value,
        quality_state_block_reason=quality_state_block,
        state_quality_capped=state_quality_capped,
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
        latest_score_components=score_components,
        impact_path_type=_optional_str(quality.get("impact_path_type")),
        impact_path_strength=_optional_str(quality.get("impact_path_strength")),
        candidate_role=_optional_str(quality.get("candidate_role")),
        evidence_quality_score=_optional_float(quality.get("evidence_quality_score")),
        source_class=_optional_str(quality.get("source_class")),
        evidence_specificity=_optional_str(quality.get("evidence_specificity")),
        market_confirmation_score=_optional_float(quality.get("market_confirmation_score")),
        market_confirmation_level=_optional_str(quality.get("market_confirmation_level")),
        market_context_freshness_status=_optional_str(quality.get("market_context_freshness_status")),
        market_context_age_hours=quality.get("market_context_age_hours"),
        market_context_stale=_optional_bool(quality.get("market_context_stale")),
        market_context_freshness_cap_applied=_optional_bool(quality.get("market_context_freshness_cap_applied")),
        opportunity_score_final=_optional_float(quality.get("opportunity_score_final")),
        opportunity_level=_optional_str(quality.get("opportunity_level")),
        opportunity_verdict_reasons=list(quality.get("opportunity_verdict_reasons") or []),
        why_local_only=_optional_str(quality.get("why_local_only")),
        why_not_watchlist=_optional_str(quality.get("why_not_watchlist")),
        manual_verification_items=list(quality.get("manual_verification_items") or []),
        upgrade_requirements=list(quality.get("upgrade_requirements") or []),
        downgrade_warnings=list(quality.get("downgrade_warnings") or []),
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
    validation_stage = str(getattr(hypothesis, "validation_stage", "") or "")
    promotable_stage = validation_stage in {
        "catalyst_link_validated",
        "impact_path_validated",
        "market_confirmed",
        "promoted_to_radar",
    }
    validated = status == "validated" and promotable_stage
    observed_iso = observed.isoformat()
    first_seen = prior.first_seen_at if prior else observed_iso
    hypothesis_score = _optional_float(getattr(hypothesis, "hypothesis_score", None))
    confidence = _optional_float(getattr(hypothesis, "confidence", None)) or 0.0
    score = max(0, min(100, int(round(hypothesis_score if hypothesis_score is not None else confidence * 100))))
    symbols = tuple(str(value) for value in getattr(hypothesis, "candidate_symbols", ()) or ())
    coin_ids = tuple(str(value) for value in getattr(hypothesis, "candidate_coin_ids", ()) or ())
    category = str(getattr(hypothesis, "impact_category", "") or "impact_hypothesis")
    scope = str(getattr(hypothesis, "hypothesis_scope", "") or "sector")
    symbol, coin_id, asset_warnings, validated_asset = _hypothesis_watchlist_asset(
        hypothesis,
        candidate_symbols=symbols,
        candidate_coin_ids=coin_ids,
        category=category,
        token_level=validated and scope == "token",
    )
    playbook = str(getattr(hypothesis, "playbook_hint", "") or "impact_hypothesis")
    incident_id = _optional_str(getattr(hypothesis, "incident_id", None))
    hypothesis_id = _optional_str(getattr(hypothesis, "hypothesis_id", None))
    incident_canonical_name = _optional_str(
        getattr(hypothesis, "incident_canonical_name", None)
        or getattr(hypothesis, "canonical_incident_name", None)
    )
    incident_event_archetype = _optional_str(
        getattr(hypothesis, "incident_event_archetype", None)
        or getattr(hypothesis, "event_archetype", None)
    )
    incident_primary_subject = _optional_str(
        getattr(hypothesis, "incident_primary_subject", None)
        or getattr(hypothesis, "primary_subject", None)
    )
    incident_affected_ecosystem = _optional_str(
        getattr(hypothesis, "incident_affected_ecosystem", None)
        or getattr(hypothesis, "affected_ecosystem", None)
    )
    incident_cause_status = _optional_str(
        getattr(hypothesis, "incident_cause_status", None)
        or getattr(hypothesis, "cause_status", None)
    )
    incident_market_observed = _optional_bool(getattr(hypothesis, "incident_market_reaction_observed", None))
    if incident_market_observed is None:
        incident_market_observed = _optional_bool(getattr(hypothesis, "market_reaction_confirmed", None))
    incident_causal = _optional_bool(getattr(hypothesis, "incident_causal_mechanism_confirmed", None))
    if incident_causal is None:
        incident_causal = _optional_bool(getattr(hypothesis, "causal_mechanism_confirmed", None))
    incident_link_status = _optional_str(getattr(hypothesis, "incident_link_status", None)) or (
        "linked" if incident_id else "no_incident"
    )
    incident_link_reason = _optional_str(getattr(hypothesis, "incident_link_reason", None)) or (
        None if incident_link_status == "linked" else "no_canonical_incident_for_event_evidence"
    )
    incident_relevance_status = _optional_str(getattr(hypothesis, "incident_relevance_status", None))
    incident_relevance_score = _optional_float(getattr(hypothesis, "incident_relevance_score", None))
    incident_relevance_reasons = list(getattr(hypothesis, "incident_relevance_reasons", ()) or ())[:8]
    incident_relevance_warnings = list(getattr(hypothesis, "incident_relevance_warnings", ()) or ())[:8]
    canonical_persistence_reason = _optional_str(getattr(hypothesis, "canonical_persistence_reason", None))
    requested_state = _state_from_hypothesis(hypothesis, validated=validated, token_level=symbol != "SECTOR")
    hypothesis_quality_components = {
        "impact_path_type": _optional_str(getattr(hypothesis, "impact_path_type", None)),
        "impact_path_strength": _optional_str(getattr(hypothesis, "impact_path_strength", None)),
        "candidate_role": _optional_str(getattr(hypothesis, "candidate_role", None)),
        "evidence_quality_score": _optional_float(getattr(hypothesis, "evidence_quality_score", None)),
        "source_class": _optional_str(getattr(hypothesis, "source_class", None)),
        "evidence_specificity": _optional_str(getattr(hypothesis, "evidence_specificity", None)),
        "market_confirmation_score": _optional_float(getattr(hypothesis, "market_confirmation_score", None)),
        "market_confirmation_level": _optional_str(getattr(hypothesis, "market_confirmation_level", None)),
        "market_context_observed_at": _optional_str(getattr(hypothesis, "market_context_observed_at", None)),
        "market_context_age_hours": _optional_float(getattr(hypothesis, "market_context_age_hours", None)),
        "market_context_stale": getattr(hypothesis, "market_context_stale", None),
        "market_context_freshness_status": _optional_str(getattr(hypothesis, "market_context_freshness_status", None)),
        "market_context_freshness_cap_applied": getattr(hypothesis, "market_context_freshness_cap_applied", None),
        "opportunity_score_final": _optional_float(getattr(hypothesis, "opportunity_score_final", None)),
        "opportunity_level": _optional_str(getattr(hypothesis, "opportunity_level", None)),
        "opportunity_verdict_reasons": list(getattr(hypothesis, "opportunity_verdict_reasons", ()) or ())[:8],
        "why_local_only": _optional_str(getattr(hypothesis, "why_local_only", None)),
        "why_not_watchlist": _optional_str(getattr(hypothesis, "why_not_watchlist", None)),
        "manual_verification_items": list(getattr(hypothesis, "manual_verification_items", ()) or ())[:8],
    }
    hypothesis_quality = event_alpha_quality_fields.ensure_quality_fields(
        {},
        components=hypothesis_quality_components,
    )
    hypothesis_quality_components = {**hypothesis_quality_components, **hypothesis_quality}
    final_state, quality_state_block = quality_cap_watchlist_state(
        requested_state,
        hypothesis_quality_components,
    )
    state = EventWatchlistState(final_state)
    previous_state = prior.state if prior else None
    rank = _state_rank(state)
    previous_rank = _state_rank(previous_state)
    state_changed = previous_state is not None and previous_state != state.value
    state_quality_capped = bool(quality_state_block and state.value != requested_state.value)
    escalation = bool(validated and (previous_state is None or rank > previous_rank) and not state_quality_capped)
    event_name = f"{getattr(hypothesis, 'external_asset', None) or category} {scope} impact hypothesis"
    reasons = _hypothesis_material_change_reasons(hypothesis, prior, state, validated=validated)
    if prior and prior.state_quality_capped and not state_quality_capped and _state_rank(requested_state) >= _STATE_RANK[EventWatchlistState.WATCHLIST.value]:
        reasons = tuple(dict.fromkeys((*reasons, "quality_state_upgraded")))
    history = list(prior.alert_history if prior else [])
    history.append({
        "observed_at": observed_iso,
        "state": state.value,
        "requested_state_before_quality_gate": requested_state.value,
        "final_state_after_quality_gate": state.value,
        "quality_state_block_reason": quality_state_block,
        "state_quality_capped": state_quality_capped,
        "tier": _tier_for_hypothesis_state(state, validated=validated),
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
            *asset_warnings,
            *((
                "missing_incident_id_for_hypothesis_watchlist_key",
            ) if not incident_id and incident_link_status != "no_incident" else ()),
            *(("quality_state_blocked:" + quality_state_block,) if quality_state_block else ()),
        )
        if str(value)
    ))
    return EventWatchlistEntry(
        schema_version=WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=hypothesis_watchlist_key(hypothesis),
        cluster_id=_optional_str(getattr(hypothesis, "event_cluster_id", None)),
        event_id=str(hypothesis_id or hypothesis_watchlist_key(hypothesis)),
        coin_id=coin_id,
        symbol=symbol,
        relationship_type="impact_hypothesis",
        external_asset=_optional_str(getattr(hypothesis, "external_asset", None)),
        event_time=None,
        state=state.value,
        previous_state=previous_state,
        first_seen_at=first_seen,
        last_seen_at=observed_iso,
        incident_id=incident_id,
        hypothesis_id=hypothesis_id,
        incident_canonical_name=incident_canonical_name,
        incident_primary_subject=incident_primary_subject,
        incident_affected_ecosystem=incident_affected_ecosystem,
        incident_cause_status=incident_cause_status,
        incident_market_reaction_observed=incident_market_observed,
        incident_causal_mechanism_confirmed=incident_causal,
        incident_link_status=incident_link_status,
        incident_link_reason=incident_link_reason,
        requested_state_before_quality_gate=requested_state.value,
        final_state_after_quality_gate=state.value,
        quality_state_block_reason=quality_state_block,
        state_quality_capped=state_quality_capped,
        first_radar_at=_transition_time(prior, "first_radar_at", state, EventWatchlistState.RADAR, observed_iso),
        first_watchlisted_at=_transition_time(prior, "first_watchlisted_at", state, EventWatchlistState.WATCHLIST, observed_iso),
        first_high_priority_at=_transition_time(prior, "first_high_priority_at", state, EventWatchlistState.HIGH_PRIORITY, observed_iso),
        first_event_passed_at=prior.first_event_passed_at if prior else None,
        first_armed_at=prior.first_armed_at if prior else None,
        first_triggered_at=prior.first_triggered_at if prior else None,
        first_invalidated_at=prior.first_invalidated_at if prior else None,
        first_expired_at=prior.first_expired_at if prior else None,
        source_count=len(tuple(getattr(hypothesis, "source_raw_ids", ()) or ())),
        highest_score=max(prior.highest_score if prior else 0, score),
        latest_score=score,
        latest_tier=_tier_for_hypothesis_state(state, validated=validated),
        latest_event_name=event_name,
        latest_source="impact_hypothesis",
        latest_playbook_type=playbook,
        latest_rule_playbook_type=playbook,
        latest_effective_playbook_type=playbook,
        latest_playbook_score=score,
        latest_playbook_action=_action_for_hypothesis_state(state, validated=validated),
        latest_market_snapshot=dict(getattr(hypothesis, "market_context_snapshot", {}) or {}),
        latest_score_components={
            "run_id": _optional_str(getattr(hypothesis, "run_id", None)),
            "profile": _optional_str(getattr(hypothesis, "profile", None)),
            "run_mode": _optional_str(getattr(hypothesis, "run_mode", None)),
            "artifact_namespace": _optional_str(getattr(hypothesis, "artifact_namespace", None)),
            "hypothesis_id": str(hypothesis_id or ""),
            "aggregated_candidate_id": _optional_str(getattr(hypothesis, "aggregated_candidate_id", None)),
            "supporting_hypothesis_count": getattr(hypothesis, "supporting_hypothesis_count", None),
            "supporting_hypothesis_ids": list(getattr(hypothesis, "supporting_hypothesis_ids", ()) or ())[:12],
            "supporting_categories": list(getattr(hypothesis, "supporting_categories", ()) or ())[:12],
            "supporting_impact_paths": list(getattr(hypothesis, "supporting_impact_paths", ()) or ())[:12],
            "supporting_evidence_quotes": list(getattr(hypothesis, "supporting_evidence_quotes", ()) or ())[:8],
            "source_raw_ids": list(getattr(hypothesis, "source_raw_ids", ()) or ())[:24],
            "source_event_ids": list(getattr(hypothesis, "source_event_ids", ()) or ())[:24],
            "impact_category": category,
            "validation_stage": validation_stage or "unknown",
            "impact_path_reason": _optional_str(getattr(hypothesis, "impact_path_reason", None)),
            "impact_path_type": _optional_str(getattr(hypothesis, "impact_path_type", None)),
            "impact_path_strength": _optional_str(getattr(hypothesis, "impact_path_strength", None)),
            "candidate_role": _optional_str(getattr(hypothesis, "candidate_role", None)),
            "evidence_specificity_score": _optional_float(getattr(hypothesis, "evidence_specificity_score", None)),
            "required_evidence_met": getattr(hypothesis, "required_evidence_met", None),
            "market_confirmation_required": getattr(hypothesis, "market_confirmation_required", None),
            "digest_eligible_by_impact_path": getattr(hypothesis, "digest_eligible_by_impact_path", None),
            "why_digest_ineligible": _optional_str(getattr(hypothesis, "why_digest_ineligible", None)),
            "opportunity_score_v2": _optional_float(getattr(hypothesis, "opportunity_score_v2", None)),
            "opportunity_score_components": dict(getattr(hypothesis, "opportunity_score_components", {}) or {}),
            "evidence_quality_score": _optional_float(getattr(hypothesis, "evidence_quality_score", None)),
            "source_class": _optional_str(getattr(hypothesis, "source_class", None)),
            "evidence_specificity": _optional_str(getattr(hypothesis, "evidence_specificity", None)),
            "evidence_quality_reasons": list(getattr(hypothesis, "evidence_quality_reasons", ()) or ())[:8],
            "market_confirmation_score": _optional_float(getattr(hypothesis, "market_confirmation_score", None)),
            "market_confirmation_level": _optional_str(getattr(hypothesis, "market_confirmation_level", None)),
            "market_confirmation_reasons": list(getattr(hypothesis, "market_confirmation_reasons", ()) or ())[:8],
            "market_confirmation_warnings": list(getattr(hypothesis, "market_confirmation_warnings", ()) or ())[:8],
            "market_confirmation_missing_fields": list(getattr(hypothesis, "market_confirmation_missing_fields", ()) or ())[:8],
            "market_confirmation_summary": _optional_str(getattr(hypothesis, "market_confirmation_summary", None)),
            "market_context_source": _optional_str(getattr(hypothesis, "market_context_source", None)),
            "market_context_timestamp": _optional_str(getattr(hypothesis, "market_context_timestamp", None)),
            "market_context_observed_at": _optional_str(getattr(hypothesis, "market_context_observed_at", None)),
            "market_context_age_seconds": _optional_float(getattr(hypothesis, "market_context_age_seconds", None)),
            "market_context_age_hours": _optional_float(getattr(hypothesis, "market_context_age_hours", None)),
            "market_context_stale": getattr(hypothesis, "market_context_stale", None),
            "market_context_freshness_status": _optional_str(getattr(hypothesis, "market_context_freshness_status", None)),
            "market_context_freshness_cap_applied": getattr(hypothesis, "market_context_freshness_cap_applied", None),
            "market_context_data_quality": _optional_str(getattr(hypothesis, "market_context_data_quality", None)),
            "market_context_snapshot": dict(getattr(hypothesis, "market_context_snapshot", {}) or {}),
            "market_reaction_confirmed": getattr(hypothesis, "market_reaction_confirmed", None),
            "causal_mechanism_confirmed": getattr(hypothesis, "causal_mechanism_confirmed", None),
            "incident_confidence": _optional_float(getattr(hypothesis, "incident_confidence", None)),
            "incident_id": incident_id,
            "incident_canonical_name": incident_canonical_name,
            "canonical_incident_name": incident_canonical_name,
            "incident_event_archetype": incident_event_archetype,
            "event_archetype": incident_event_archetype,
            "incident_primary_subject": incident_primary_subject,
            "primary_subject": incident_primary_subject,
            "affected_entity": _optional_str(getattr(hypothesis, "affected_entity", None)),
            "incident_affected_ecosystem": incident_affected_ecosystem,
            "affected_ecosystem": incident_affected_ecosystem,
            "role_confidence": _optional_float(getattr(hypothesis, "role_confidence", None)),
            "role_evidence": list(getattr(hypothesis, "role_evidence", ()) or ())[:8],
            "incident_cause_status": incident_cause_status,
            "cause_status": incident_cause_status,
            "incident_link_status": incident_link_status,
            "incident_link_reason": incident_link_reason,
            "incident_relevance_status": incident_relevance_status,
            "incident_relevance_score": incident_relevance_score,
            "incident_relevance_reasons": incident_relevance_reasons,
            "incident_relevance_warnings": incident_relevance_warnings,
            "canonical_persistence_reason": canonical_persistence_reason,
            "claim_polarities": list(getattr(hypothesis, "claim_polarities", ()) or ())[:8],
            "claim_history": list(getattr(hypothesis, "claim_history", ()) or ())[:8],
            "independent_source_domains": list(getattr(hypothesis, "independent_source_domains", ()) or ())[:8],
            "conflicting_claims": list(getattr(hypothesis, "conflicting_claims", ()) or ())[:8],
            "incident_market_reaction_observed": incident_market_observed,
            "market_reaction_observed": incident_market_observed,
            "incident_causal_mechanism_confirmed": incident_causal,
            "opportunity_score_final": _optional_float(getattr(hypothesis, "opportunity_score_final", None)),
            "opportunity_level": _optional_str(getattr(hypothesis, "opportunity_level", None)),
            "opportunity_verdict_reasons": list(getattr(hypothesis, "opportunity_verdict_reasons", ()) or ())[:8],
            "missing_requirements": list(getattr(hypothesis, "missing_requirements", ()) or ())[:8],
            "manual_verification_items": list(getattr(hypothesis, "manual_verification_items", ()) or ())[:8],
            "upgrade_requirements": list(getattr(hypothesis, "upgrade_requirements", ()) or ())[:8],
            "downgrade_warnings": list(getattr(hypothesis, "downgrade_warnings", ()) or ())[:8],
            "why_local_only": _optional_str(getattr(hypothesis, "why_local_only", None)),
            "why_not_watchlist": _optional_str(getattr(hypothesis, "why_not_watchlist", None)),
            "frame_required": bool(getattr(hypothesis, "frame_required", False)),
            "frame_status": _optional_str(getattr(hypothesis, "frame_status", None)),
            "frame_required_reason": _optional_str(getattr(hypothesis, "frame_required_reason", None)),
            "frame_gate_reason": _optional_str(getattr(hypothesis, "frame_gate_reason", None)),
            "route_block_reason": _optional_str(getattr(hypothesis, "route_block_reason", None)),
            "primary_impact_path": _optional_str(getattr(hypothesis, "primary_impact_path", None)),
            "asset_role_source": _optional_str(getattr(hypothesis, "asset_role_source", None)),
            "asset_kind": _optional_str(getattr(hypothesis, "asset_kind", None)),
            "role_source": _optional_str(getattr(hypothesis, "role_source", None)),
            "identity_confidence": _optional_float(getattr(hypothesis, "identity_confidence", None)),
            "identity_evidence": list(getattr(hypothesis, "identity_evidence", ()) or ())[:8],
            "collision_risk": _optional_str(getattr(hypothesis, "collision_risk", None)),
            "role_validation_failures": list(getattr(hypothesis, "role_validation_failures", ()) or ())[:8],
            "role_validation_warnings": list(getattr(hypothesis, "role_validation_warnings", ()) or ())[:8],
            "role_capabilities": dict(getattr(hypothesis, "role_capabilities", {}) or {}),
            "hypothesis_score": score,
            "score": score,
            "playbook_type": playbook,
            "effective_playbook_type": playbook,
            "direction_hint": str(getattr(hypothesis, "direction_hint", "") or "unknown"),
            "external_asset": _optional_str(getattr(hypothesis, "external_asset", None)),
            "candidate_sectors": list(getattr(hypothesis, "candidate_sectors", ()) or ()),
            "hypothesis_confidence": score,
            "hypothesis_scope": scope,
            "candidate_symbol_count": len(symbols),
            "candidate_symbols": list(symbols[:12]),
            "candidate_coin_ids": list(coin_ids[:12]),
            "validated_symbol": symbol if symbol != "SECTOR" else None,
            "validated_coin_id": coin_id if symbol != "SECTOR" else None,
            "validated_asset": validated_asset,
            "route_eligibility": "validated_hypothesis_digest_candidate" if validated and symbol != "SECTOR" else "local_only",
            "why_not_promoted": list(getattr(hypothesis, "why_not_promoted", ()) or ())[:10],
            "validation_evidence": 100 if validated else 0,
            "validation_reasons": list(getattr(hypothesis, "validation_reasons", ()) or ())[:8],
            "evidence_quotes": list(getattr(hypothesis, "evidence_quotes", ()) or ())[:8],
            "external_entities": list(getattr(hypothesis, "external_entities", ()) or ())[:8],
            "crypto_candidate_assets": list(getattr(hypothesis, "crypto_candidate_assets", ()) or ())[:12],
            "rejected_candidate_assets": list(getattr(hypothesis, "rejected_candidate_assets", ()) or ())[:8],
            **dict(getattr(hypothesis, "score_components", {}) or {}),
        },
        impact_path_type=_optional_str(hypothesis_quality.get("impact_path_type")),
        impact_path_strength=_optional_str(hypothesis_quality.get("impact_path_strength")),
        candidate_role=_optional_str(hypothesis_quality.get("candidate_role")),
        evidence_quality_score=_optional_float(hypothesis_quality.get("evidence_quality_score")),
        source_class=_optional_str(hypothesis_quality.get("source_class")),
        evidence_specificity=_optional_str(hypothesis_quality.get("evidence_specificity")),
        market_confirmation_score=_optional_float(hypothesis_quality.get("market_confirmation_score")),
        market_confirmation_level=_optional_str(hypothesis_quality.get("market_confirmation_level")),
        market_context_freshness_status=_optional_str(hypothesis_quality.get("market_context_freshness_status")),
        market_context_age_hours=hypothesis_quality.get("market_context_age_hours"),
        market_context_stale=_optional_bool(hypothesis_quality.get("market_context_stale")),
        market_context_freshness_cap_applied=_optional_bool(hypothesis_quality.get("market_context_freshness_cap_applied")),
        opportunity_score_final=_optional_float(hypothesis_quality.get("opportunity_score_final")),
        opportunity_level=_optional_str(hypothesis_quality.get("opportunity_level")),
        opportunity_verdict_reasons=list(hypothesis_quality.get("opportunity_verdict_reasons") or []),
        why_local_only=_optional_str(hypothesis_quality.get("why_local_only")),
        why_not_watchlist=_optional_str(hypothesis_quality.get("why_not_watchlist")),
        manual_verification_items=list(hypothesis_quality.get("manual_verification_items") or []),
        upgrade_requirements=list(hypothesis_quality.get("upgrade_requirements") or []),
        downgrade_warnings=list(hypothesis_quality.get("downgrade_warnings") or []),
        alert_history=history,
        state_changed=state_changed,
        escalation=escalation,
        score_jump=score - int(prior.latest_score if prior else score),
        material_change_reasons=reasons,
        should_alert=escalation and not state_quality_capped,
        suppressed_reason=None if escalation and not state_quality_capped else (
            f"quality state gate capped {requested_state.value} to {state.value}: {quality_state_block}"
            if state_quality_capped
            else
            f"validated hypothesis retained at {state.value}" if validated else "impact hypothesis awaiting validation"
        ),
        warnings=warnings,
    )


def _state_from_hypothesis(
    hypothesis: object,
    *,
    validated: bool,
    token_level: bool,
) -> EventWatchlistState:
    if not validated:
        return EventWatchlistState.HYPOTHESIS
    if not token_level:
        return EventWatchlistState.RADAR
    level = str(getattr(hypothesis, "opportunity_level", "") or "")
    market_level = str(getattr(hypothesis, "market_confirmation_level", "") or "")
    score = _optional_float(getattr(hypothesis, "opportunity_score_final", None))
    if score is None:
        score = _optional_float(getattr(hypothesis, "hypothesis_score", None)) or 0.0
    evidence = _optional_float(getattr(hypothesis, "evidence_quality_score", None)) or 0.0
    timing = _score_component_float(hypothesis, "timing_event_window", "event_clarity")
    derivatives = _score_component_float(hypothesis, "derivatives_crowding")
    if level == "high_priority" or score >= 88 or (market_level == "strong" and (timing >= 70 or derivatives >= 50)):
        return EventWatchlistState.HIGH_PRIORITY
    if level == "watchlist" or score >= 78 or (market_level in {"moderate", "strong"} and evidence >= 60):
        return EventWatchlistState.WATCHLIST
    return EventWatchlistState.RADAR


def _hypothesis_material_change_reasons(
    hypothesis: object,
    prior: EventWatchlistEntry | None,
    state: EventWatchlistState,
    *,
    validated: bool,
) -> tuple[str, ...]:
    if not validated:
        return ()
    reasons: list[str] = ["impact_path_confirmed"]
    if prior is None:
        reasons.append("initial_validated_hypothesis")
    components = prior.latest_score_components if prior else {}
    market = str(getattr(hypothesis, "market_confirmation_level", "") or "")
    previous_market = str(components.get("market_confirmation_level") or "")
    if market in {"moderate", "strong"} and market != previous_market:
        reasons.append("market_confirmation_upgraded")
    evidence = _optional_float(getattr(hypothesis, "evidence_quality_score", None)) or 0.0
    previous_evidence = _optional_float(components.get("evidence_quality_score")) or 0.0
    if evidence >= 65 and evidence > previous_evidence:
        reasons.append("evidence_quality_upgraded")
    level = str(getattr(hypothesis, "opportunity_level", "") or "")
    previous_level = str(components.get("opportunity_level") or "")
    if level in {"validated_digest", "watchlist", "high_priority"} and level != previous_level:
        reasons.append("opportunity_score_upgraded")
    current_sources = _item_count(getattr(hypothesis, "independent_source_domains", None)) or _item_count(getattr(hypothesis, "source_raw_ids", None))
    previous_sources = _item_count(components.get("independent_source_domains")) or _item_count(components.get("source_raw_ids"))
    if current_sources > previous_sources:
        reasons.append("independent_source_confirmation")
        reasons.append("incident_new_independent_source")
    current_cause = _optional_str(getattr(hypothesis, "cause_status", None)) or ""
    previous_cause = _optional_str(components.get("cause_status")) or ""
    if current_cause and current_cause != previous_cause:
        reasons.append("cause_status_changed")
        reasons.append("incident_cause_status_changed")
        if current_cause == "confirmed":
            reasons.append("claim_confirmed")
            reasons.append("incident_claim_confirmed")
        elif current_cause == "ruled_out":
            reasons.append("claim_ruled_out")
            reasons.append("incident_claim_ruled_out")
    current_conflicts = _item_count(getattr(hypothesis, "conflicting_claims", None))
    previous_conflicts = _item_count(components.get("conflicting_claims"))
    if current_conflicts > previous_conflicts:
        reasons.append("incident_conflicting_claim_added")
    current_market = bool(getattr(hypothesis, "market_reaction_confirmed", False))
    previous_market = bool(components.get("market_reaction_confirmed"))
    if current_market and not previous_market:
        reasons.append("incident_market_reaction_confirmed")
    current_causal = bool(getattr(hypothesis, "causal_mechanism_confirmed", False))
    previous_causal = bool(components.get("causal_mechanism_confirmed"))
    if current_causal and not previous_causal:
        reasons.append("incident_causal_mechanism_confirmed")
    current_incident_confidence = _optional_float(getattr(hypothesis, "incident_confidence", None)) or 0.0
    previous_incident_confidence = _optional_float(components.get("incident_confidence")) or 0.0
    if current_incident_confidence and abs(current_incident_confidence - previous_incident_confidence) >= 10:
        reasons.append("incident_confidence_changed")
    current_role = _optional_str(getattr(hypothesis, "candidate_role", None)) or ""
    previous_role = _optional_str(components.get("candidate_role")) or ""
    if current_role and previous_role and current_role != previous_role:
        reasons.append("affected_asset_role_changed")
        reasons.append("incident_asset_role_changed")
    if state == EventWatchlistState.RADAR and market in {"", "none", "weak"}:
        reasons.append("market_reaction_absent_downgrade")
    warnings = tuple(str(value).lower() for value in (
        *tuple(getattr(hypothesis, "warnings", ()) or ()),
        *tuple(getattr(hypothesis, "why_not_promoted", ()) or ()),
    ))
    if any("stale" in warning for warning in warnings):
        reasons.append("event_stale_downgrade")
    return tuple(dict.fromkeys(reasons))


def _tier_for_hypothesis_state(state: EventWatchlistState, *, validated: bool) -> str:
    if not validated:
        return "STORE_ONLY"
    if state == EventWatchlistState.HIGH_PRIORITY:
        return "HIGH_PRIORITY_WATCH"
    if state == EventWatchlistState.WATCHLIST:
        return "WATCHLIST"
    if state == EventWatchlistState.RADAR:
        return "RADAR_DIGEST"
    return "STORE_ONLY"


def _action_for_hypothesis_state(state: EventWatchlistState, *, validated: bool) -> str:
    if not validated:
        return "store_only"
    if state == EventWatchlistState.HIGH_PRIORITY:
        return "high_priority_watch"
    if state == EventWatchlistState.WATCHLIST:
        return "watchlist"
    if state == EventWatchlistState.RADAR:
        return "radar_digest"
    return "store_only"


def _score_component_float(hypothesis: object, *keys: str) -> float:
    components = getattr(hypothesis, "score_components", {}) or {}
    if not isinstance(components, Mapping):
        return 0.0
    for key in keys:
        value = _optional_float(components.get(key))
        if value is not None:
            return value
    return 0.0


def _hypothesis_watchlist_asset(
    hypothesis: object,
    *,
    candidate_symbols: tuple[str, ...],
    candidate_coin_ids: tuple[str, ...],
    category: str,
    token_level: bool,
) -> tuple[str, str, tuple[str, ...], dict[str, Any]]:
    """Return the validated token identity for a promoted hypothesis.

    Candidate taxonomy order is intentionally not identity evidence. A validated
    hypothesis without a validated token identity stays at SECTOR level.
    """
    if not token_level:
        return "SECTOR", category, (), {}

    warnings: list[str] = []
    asset = _direct_validated_hypothesis_asset(hypothesis)
    if not asset:
        asset = _first_validated_asset(getattr(hypothesis, "crypto_candidate_assets", ()) or ())
    if not asset:
        asset = _first_validated_asset(getattr(hypothesis, "validated_candidate_assets", ()) or ())
    if not asset:
        asset = _first_resolver_validated_asset(getattr(hypothesis, "validated_candidate_assets", ()) or ())

    symbol = str(asset.get("symbol") or "").strip().upper() if asset else ""
    coin_id = str(asset.get("coin_id") or "").strip() if asset else ""
    if symbol and not coin_id:
        coin_id = _coin_id_for_symbol(symbol, candidate_symbols, candidate_coin_ids)
    if not symbol and coin_id:
        symbol = _symbol_for_coin_id(coin_id, candidate_symbols, candidate_coin_ids)

    if not symbol and not coin_id:
        warnings.append("validated_hypothesis_missing_validated_asset")
        return "SECTOR", category, tuple(warnings), {}

    if candidate_symbols and symbol and candidate_symbols[0].upper() != symbol.upper():
        warnings.append(
            "validated_asset_mismatch_candidate_order:"
            f"first_candidate={candidate_symbols[0].upper()} validated={symbol.upper()}"
        )
    normalized = {str(key): value for key, value in dict(asset).items()} if asset else {}
    normalized["symbol"] = symbol
    normalized["coin_id"] = coin_id or category
    return symbol or "SECTOR", coin_id or category, tuple(warnings), normalized


def _direct_validated_hypothesis_asset(hypothesis: object) -> dict[str, Any]:
    symbol = str(getattr(hypothesis, "validated_symbol", "") or "").strip().upper()
    coin_id = str(getattr(hypothesis, "validated_coin_id", "") or "").strip()
    if not symbol and not coin_id:
        return {}
    return {
        "source": "validated_hypothesis_fields",
        "symbol": symbol,
        "coin_id": coin_id,
        "validated": True,
    }


def _first_validated_asset(rows: Iterable[object]) -> dict[str, Any]:
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if not bool(row.get("validated")):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or "").strip()
        if symbol or coin_id:
            data = dict(row)
            data["symbol"] = symbol
            data["coin_id"] = coin_id
            return data
    return {}


def _first_resolver_validated_asset(rows: Iterable[object]) -> dict[str, Any]:
    resolver_sources = {"deterministic_resolver", "resolver", "hypothesis_search", "candidate_validation_search"}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        source = str(row.get("source") or "")
        reason = str(row.get("reason") or "")
        if source not in resolver_sources and "identity_match" not in reason and "validated" not in reason:
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or "").strip()
        if symbol or coin_id:
            data = dict(row)
            data["symbol"] = symbol
            data["coin_id"] = coin_id
            data["validated"] = True
            return data
    return {}


def _coin_id_for_symbol(symbol: str, symbols: tuple[str, ...], coin_ids: tuple[str, ...]) -> str:
    for idx, candidate in enumerate(symbols):
        if candidate.upper() == symbol.upper() and idx < len(coin_ids):
            return str(coin_ids[idx] or "")
    return ""


def _symbol_for_coin_id(coin_id: str, symbols: tuple[str, ...], coin_ids: tuple[str, ...]) -> str:
    for idx, candidate in enumerate(coin_ids):
        if str(candidate) == coin_id and idx < len(symbols):
            return str(symbols[idx] or "").upper()
    return ""


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
    if state == EventWatchlistState.QUALITY_BLOCKED:
        return "quality verdict capped lifecycle state; local-only research evidence"
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
    data = [_entry_with_persistence_quality_cap(entry) for entry in entries]
    if not data:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for entry in data:
            fh.write(json.dumps(_json_ready(asdict(entry)), sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    return len(data)


def _entry_with_persistence_quality_cap(entry: EventWatchlistEntry) -> EventWatchlistEntry:
    """Ensure hand-built entries cannot bypass lifecycle quality caps."""
    requested = requested_state_value(entry)
    quality = _quality_bundle_from_entry(entry)
    final_state, block_reason = quality_cap_watchlist_state(requested, quality)
    if final_state in {
        EventWatchlistState.TRIGGERED_FADE.value,
        EventWatchlistState.INVALIDATED.value,
        EventWatchlistState.EXPIRED.value,
    }:
        return entry
    capped = requested != final_state
    if (
        entry.state == final_state
        and entry.final_state_after_quality_gate == final_state
        and bool(entry.state_quality_capped) == capped
        and (entry.quality_state_block_reason or block_reason) == entry.quality_state_block_reason
    ):
        return entry
    warnings = tuple(dict.fromkeys((
        *entry.warnings,
        *(("quality_state_blocked:" + str(block_reason),) if block_reason else ()),
    )))
    return replace(
        entry,
        state=final_state,
        requested_state_before_quality_gate=requested,
        final_state_after_quality_gate=final_state,
        state_quality_capped=capped,
        quality_state_block_reason=block_reason,
        should_alert=entry.should_alert and not capped,
        suppressed_reason=entry.suppressed_reason
        or (
            f"quality state gate capped {requested} to {final_state}: {block_reason}"
            if capped
            else None
        ),
        warnings=warnings,
    )


def _entry_from_row(row: Mapping[str, Any]) -> EventWatchlistEntry | None:
    try:
        key = str(row.get("key") or "")
        event_id = str(row.get("event_id") or "")
        coin_id = str(row.get("coin_id") or "")
        symbol = str(row.get("symbol") or "")
        relationship_type = str(row.get("relationship_type") or "")
        if not key or not event_id or not coin_id or not relationship_type:
            return None
        requested_state = _state_value(row.get("requested_state_before_quality_gate") or row.get("state"))
        first_seen = str(row.get("first_seen_at") or row.get("last_seen_at") or "")
        last_seen = str(row.get("last_seen_at") or first_seen)
        components = dict(row.get("latest_score_components") or {})
        has_quality = event_alpha_quality_fields.has_any_quality_field(row, components_key="latest_score_components")
        quality = event_alpha_quality_fields.ensure_quality_fields(row, components=components)
        raw_quality = {**components, **quality} if has_quality else components
        computed_final, computed_block = (
            quality_cap_watchlist_state(requested_state, raw_quality)
            if has_quality
            else (requested_state, None)
        )
        persisted_final = _state_value(row.get("final_state_after_quality_gate"))
        if persisted_final in {
            EventWatchlistState.TRIGGERED_FADE.value,
            EventWatchlistState.INVALIDATED.value,
            EventWatchlistState.EXPIRED.value,
        }:
            final_state = persisted_final
        elif has_quality:
            final_state = computed_final
        elif row.get("final_state_after_quality_gate"):
            final_state = persisted_final
        else:
            final_state = requested_state
        state_quality_capped = bool(row.get("state_quality_capped")) if not has_quality else requested_state != final_state
        quality_state_block = _normalize_quality_state_block_reason(
            _optional_str(row.get("quality_state_block_reason")) or computed_block,
            quality,
        )
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
            state=final_state,
            previous_state=_optional_str(row.get("previous_state")),
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            incident_id=_optional_str(row.get("incident_id") or components.get("incident_id")),
            hypothesis_id=_optional_str(row.get("hypothesis_id") or components.get("hypothesis_id")),
            incident_canonical_name=_optional_str(
                row.get("incident_canonical_name")
                or row.get("canonical_incident_name")
                or components.get("incident_canonical_name")
                or components.get("canonical_incident_name")
            ),
            incident_primary_subject=_optional_str(
                row.get("incident_primary_subject")
                or row.get("primary_subject")
                or components.get("incident_primary_subject")
                or components.get("primary_subject")
            ),
            incident_affected_ecosystem=_optional_str(
                row.get("incident_affected_ecosystem")
                or row.get("affected_ecosystem")
                or components.get("incident_affected_ecosystem")
                or components.get("affected_ecosystem")
            ),
            incident_cause_status=_optional_str(
                row.get("incident_cause_status")
                or row.get("cause_status")
                or components.get("incident_cause_status")
                or components.get("cause_status")
            ),
            incident_market_reaction_observed=_optional_bool(
                row.get("incident_market_reaction_observed")
                if "incident_market_reaction_observed" in row
                else components.get("incident_market_reaction_observed")
                if "incident_market_reaction_observed" in components
                else row.get("market_reaction_observed")
                if "market_reaction_observed" in row
                else components.get("market_reaction_observed")
            ),
            incident_causal_mechanism_confirmed=_optional_bool(
                row.get("incident_causal_mechanism_confirmed")
                if "incident_causal_mechanism_confirmed" in row
                else components.get("incident_causal_mechanism_confirmed")
                if "incident_causal_mechanism_confirmed" in components
                else row.get("causal_mechanism_confirmed")
                if "causal_mechanism_confirmed" in row
                else components.get("causal_mechanism_confirmed")
            ),
            incident_link_status=_optional_str(row.get("incident_link_status") or components.get("incident_link_status")),
            incident_link_reason=_optional_str(row.get("incident_link_reason") or components.get("incident_link_reason")),
            requested_state_before_quality_gate=requested_state,
            final_state_after_quality_gate=final_state,
            quality_state_block_reason=quality_state_block,
            state_quality_capped=state_quality_capped,
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
            latest_score_components=raw_quality,
            impact_path_type=_optional_str(quality.get("impact_path_type")),
            impact_path_strength=_optional_str(quality.get("impact_path_strength")),
            candidate_role=_optional_str(quality.get("candidate_role")),
            evidence_quality_score=_optional_float(quality.get("evidence_quality_score")),
            source_class=_optional_str(quality.get("source_class")),
            evidence_specificity=_optional_str(quality.get("evidence_specificity")),
            market_confirmation_score=_optional_float(quality.get("market_confirmation_score")),
            market_confirmation_level=_optional_str(quality.get("market_confirmation_level")),
            market_context_freshness_status=_optional_str(quality.get("market_context_freshness_status")),
            market_context_age_hours=quality.get("market_context_age_hours"),
            market_context_stale=_optional_bool(quality.get("market_context_stale")),
            market_context_freshness_cap_applied=_optional_bool(quality.get("market_context_freshness_cap_applied")),
            opportunity_score_final=_optional_float(quality.get("opportunity_score_final")),
            opportunity_level=_optional_str(quality.get("opportunity_level")),
            opportunity_verdict_reasons=list(quality.get("opportunity_verdict_reasons") or []),
            why_local_only=_optional_str(quality.get("why_local_only")),
            why_not_watchlist=_optional_str(quality.get("why_not_watchlist")),
            manual_verification_items=list(quality.get("manual_verification_items") or []),
            upgrade_requirements=list(quality.get("upgrade_requirements") or []),
            downgrade_warnings=list(quality.get("downgrade_warnings") or []),
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
    transition = (
        f"  transition: {entry.previous_state or 'new'} -> {entry.state}"
        + (
            f" · quality-capped from {entry.requested_state_before_quality_gate}: {entry.quality_state_block_reason}"
            if entry.state_quality_capped
            else " · alertable escalation"
            if entry.should_alert and not entry.material_change_reasons
            else f" · alertable material change: {', '.join(entry.material_change_reasons)}"
            if entry.should_alert
            else f" · suppressed: {entry.suppressed_reason}"
        )
    )
    return [
        f"{entry.state:<16} score={entry.latest_score:>3} high={entry.highest_score:>3} "
        f"{entry.symbol}/{entry.coin_id}",
        f"  event: {entry.latest_event_name}",
        f"  cluster: {entry.cluster_id or 'legacy'}",
        f"  external: {entry.external_asset or 'unknown'} · relationship: {entry.relationship_type}",
        f"  first_seen: {entry.first_seen_at} · last_seen: {entry.last_seen_at}",
        f"  tier: {entry.latest_tier or 'unknown'} · source_count: {entry.source_count} · source: {entry.latest_source}",
        playbook_line,
        transition,
    ]


def _entry_sort_key(entry: EventWatchlistEntry) -> tuple[int, int, str]:
    return (-_state_rank(entry.state), -entry.highest_score, entry.symbol)


def _state_rank(state: str | EventWatchlistState | None) -> int:
    if isinstance(state, EventWatchlistState):
        state = state.value
    return _STATE_RANK.get(str(state or ""), -1)


def _state_value(state: str | EventWatchlistState | None) -> str:
    value = state.value if isinstance(state, EventWatchlistState) else str(state or "")
    return value if value in _STATE_RANK else EventWatchlistState.RAW_EVIDENCE.value


def _quality_bundle_has_authority(quality_bundle: Mapping[str, Any] | None) -> bool:
    if not isinstance(quality_bundle, Mapping) or not quality_bundle:
        return False
    return any(
        key in quality_bundle and not event_alpha_quality_fields.is_missing_quality_value(quality_bundle.get(key))
        for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS
    )


def _quality_bundle_from_entry(entry: EventWatchlistEntry) -> dict[str, Any]:
    row = {
        key: getattr(entry, key, None)
        for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS
        if getattr(entry, key, None) not in (None, "", [], {}, ())
    }
    components = dict(entry.latest_score_components or {})
    if not event_alpha_quality_fields.has_any_quality_field(row, components_key="latest_score_components") and not event_alpha_quality_fields.has_any_quality_field(components):
        return {}
    return {**components, **row}


def _quality_state_block_reason(
    quality: Mapping[str, Any],
    *,
    level: str,
    score: float | None,
    impact: str,
    evidence: str,
    source: str,
    role: str,
) -> str | None:
    text = " ".join(
        str(value or "")
        for value in (
            impact,
            evidence,
            source,
            role,
            quality.get("why_local_only"),
            quality.get("why_not_watchlist"),
            *(quality.get("opportunity_verdict_reasons") or ()),
            *(quality.get("upgrade_requirements") or ()),
            *(quality.get("downgrade_warnings") or ()),
        )
    ).casefold()
    if impact == "insufficient_data":
        return "impact_path_type_insufficient_data"
    if score is not None and score <= 0:
        return "opportunity_score_final_zero"
    if role == "unknown_with_reason":
        return "candidate_role_unknown_with_reason"
    if source == "insufficient_data":
        return "source_class_insufficient_data"
    if evidence == "insufficient_data":
        return "evidence_specificity_insufficient_data"
    if "source_noise" in text:
        return "source_noise_hard_gate"
    if "ticker_collision" in text or "word_collision" in text or "ticker_word_collision" in text:
        return "ticker_collision_hard_gate"
    if level == "local_only":
        return _normalize_quality_state_block_reason(
            str(quality.get("why_local_only") or "opportunity_level_local_only"),
            quality,
        )
    if level == "exploratory":
        return _normalize_quality_state_block_reason(
            str(quality.get("why_not_watchlist") or "opportunity_level_exploratory"),
            quality,
        )
    return None


def _normalize_quality_state_block_reason(reason: str | None, quality: Mapping[str, Any]) -> str | None:
    """Keep block reasons actionable, especially for legacy artifacts."""
    if not reason:
        return None
    value = str(reason)
    normalized = value.strip().casefold()
    if normalized == "strong_market_confirmation":
        impact = str(quality.get("impact_path_type") or "").strip()
        strength = str(quality.get("impact_path_strength") or "").strip()
        role = str(quality.get("candidate_role") or "").strip()
        market_level = str(quality.get("market_confirmation_level") or "").strip()
        market_score = _optional_float(quality.get("market_confirmation_score"))
        market_is_strong = market_level in {"strong", "confirmed"} or (market_score is not None and market_score >= 75)
        weak_context = (
            strength not in {"strong", "medium"}
            or impact in {"generic_cooccurrence_only", "macro_attention_only", "technology_risk", "market_structure_policy", "unknown", ""}
            or role in {"generic_mention", "macro_affected_asset", "unknown_with_reason", ""}
        )
        if market_is_strong and weak_context:
            return "weak_impact_path_despite_market_confirmation"
        if market_is_strong:
            return "impact_path_not_strong_enough"
        return "needs_strong_market_confirmation"
    if normalized == "impact_path":
        return "impact_path_not_strong_enough"
    if normalized == "explained_token_impact_path":
        return "missing_direct_impact_path"
    return value


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


def _optional_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _item_count(value: Any) -> int:
    if value in (None, "", [], (), {}):
        return 0
    if isinstance(value, str):
        return 1
    if isinstance(value, Mapping):
        return len(value)
    try:
        return len(value)
    except TypeError:
        return 1


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
