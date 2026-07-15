"""Event Alpha watchlist refresh and state helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import event_fade
import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
from crypto_rsi_scanner.event_alpha.radar.source_independence import validated_source_independence_container
from .models import *  # noqa: F403 - split modules share historical model names


def _validated_corroboration_count(value: object) -> int | None:
    if isinstance(value, Mapping):
        container = value
    else:
        container = {
            key: getattr(value, key, None)
            for key in (
                "source_independence",
                "source_independence_status",
                "source_independence_errors",
                "independent_source_count",
                "independent_corroboration_count",
                "source_content_cluster_count",
            )
        }
    contract = validated_source_independence_container(container)
    if not contract:
        return None
    raw = contract.get("independent_corroboration_count")
    return int(raw) if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0 else None


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
    current_sources = _validated_corroboration_count(hypothesis)
    previous_sources = _validated_corroboration_count(components)
    if current_sources is not None and previous_sources is not None and current_sources > previous_sources:
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
    current_sources = _validated_corroboration_count(alert.score_components)
    previous_sources = _validated_corroboration_count(prior.latest_score_components)
    if current_sources is not None and previous_sources is not None and current_sources > previous_sources:
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
