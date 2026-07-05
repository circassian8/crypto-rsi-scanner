"""Lightweight research feedback artifacts for Event Alpha Radar."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist


FEEDBACK_SCHEMA_VERSION = "event_alpha_feedback_v1"


class EventFeedbackLabel(str, Enum):
    USEFUL = "useful"
    JUNK = "junk"
    WATCH = "watch"
    FALSE_POSITIVE = "false_positive"
    LATE = "late"
    SOURCE_NOISE = "source_noise"
    NEEDS_CONFIRMATION = "needs_confirmation"
    DUPLICATE = "duplicate"
    PROMISING_SOURCE_TYPE = "promising_source_type"
    MISSED = "missed"
    TRADED_ELSEWHERE = "traded_elsewhere"
    IGNORED = "ignored"


@dataclass(frozen=True)
class EventFeedbackConfig:
    path: Path


@dataclass(frozen=True)
class EventFeedbackRecord:
    schema_version: str
    row_type: str
    feedback_id: str
    target: str
    key: str | None
    event_id: str | None
    incident_id: str | None
    coin_id: str | None
    symbol: str | None
    relationship_type: str | None
    external_asset: str | None
    event_time: str | None
    label: str
    marked_at: str
    marked_by: str
    notes: str | None = None
    source: str = "manual_cli"
    state: str | None = None
    route: str | None = None
    playbook_type: str | None = None
    latest_score: int | None = None
    watchlist_last_seen_at: str | None = None
    source_class: str | None = None
    source_domain: str | None = None
    evidence_specificity: str | None = None
    impact_path_type: str | None = None
    candidate_role: str | None = None
    opportunity_level: str | None = None
    market_confirmation_level: str | None = None
    source_pack: str | None = None
    source_provider: str | None = None
    accepted_evidence_reason_codes: tuple[str, ...] = ()
    feedback_target: str | None = None
    feedback_target_type: str | None = None
    core_opportunity_id: str | None = None
    card_path: str | None = None
    run_id: str | None = None
    profile: str | None = None
    artifact_namespace: str | None = None
    hypothesis_id: str | None = None
    watchlist_key: str | None = None
    final_route_after_quality_gate: str | None = None
    lane: str | None = None
    market_context_freshness_status: str | None = None
    catalyst_frame_status: str | None = None
    main_frame_type: str | None = None
    source_provider_domain: str | None = None
    provider_coverage_status: str | None = None
    source_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class EventFeedbackReadResult:
    path: Path
    rows_read: int
    records: list[EventFeedbackRecord]


def mark_feedback(
    target: str,
    label: str | EventFeedbackLabel,
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    cfg: EventFeedbackConfig,
    marked_by: str = "human",
    notes: str | None = None,
    route: str | None = None,
    now: datetime | None = None,
    allow_unmatched: bool = False,
    context_rows: Iterable[Mapping[str, Any] | object] = (),
    card_paths: Iterable[str | Path] = (),
) -> EventFeedbackRecord:
    """Append one manual research feedback row.

    Feedback is an artifact-only annotation. It does not alter watchlist state,
    alert tiers, paper trades, live DB rows, or event-fade eligibility.
    """
    clean_target = str(target or "").strip()
    if not clean_target:
        raise ValueError("feedback target is required")
    parsed_label = _label(label)
    entries = list(watchlist_entries)
    rows = [_row_dict(row) for row in context_rows]
    cards = tuple(Path(path) for path in card_paths)
    entry = _find_watchlist_entry(clean_target, entries)
    context_row, matched_card_path = _find_context_row(clean_target, rows, cards, entry=entry)
    if entry is None and context_row is None and parsed_label != EventFeedbackLabel.MISSED and not allow_unmatched:
        raise ValueError(
            f"no unique watchlist row matched {clean_target!r}; use label=missed for uncaptured opportunities"
        )
    if entry is None and context_row is None and parsed_label != EventFeedbackLabel.MISSED and allow_unmatched:
        notes = "; ".join(
            value
            for value in (
                "warning: no watchlist row matched this manual feedback target",
                notes,
            )
            if value
        )
    marked_at = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    if context_row is not None and entry is None:
        record = _record_from_context_row(
            clean_target,
            parsed_label,
            row=context_row,
            marked_at=marked_at,
            marked_by=marked_by,
            notes=notes,
            route=route,
            card_path=matched_card_path,
        )
    else:
        record = _record_from_entry(
            clean_target,
            parsed_label,
            entry=entry,
            marked_at=marked_at,
            marked_by=marked_by,
            notes=notes,
            route=route,
            context_row=context_row,
            card_path=matched_card_path,
        )
    if entry is None and context_row is None and allow_unmatched and parsed_label != EventFeedbackLabel.MISSED:
        record = EventFeedbackRecord(**{**record.__dict__, "source": "manual_cli_unmatched"})
    _append_record(cfg.path, record)
    return record


def load_feedback(path: str | Path) -> EventFeedbackReadResult:
    records = [
        record
        for record in (_record_from_row(row) for row in _read_jsonl(Path(path).expanduser()))
        if record is not None
    ]
    return EventFeedbackReadResult(path=Path(path).expanduser(), rows_read=len(records), records=records)


def format_feedback_record(record: EventFeedbackRecord, *, path: Path | None = None) -> str:
    rows = [
        "=" * 76,
        "EVENT ALPHA FEEDBACK MARKED (research artifact only)",
        "=" * 76,
    ]
    if path is not None:
        rows.append(f"path: {path}")
    rows.extend([
        f"target: {record.target}",
        f"feedback_target: {record.feedback_target or record.target} ({record.feedback_target_type or 'legacy'})",
        f"core_opportunity_id: {record.core_opportunity_id or 'none'}",
        f"card_path: {record.card_path or 'none'}",
        f"label: {record.label}",
        f"symbol/coin: {(record.symbol or 'unknown')}/{record.coin_id or 'unknown'}",
        f"event_id: {record.event_id or 'unmatched'}",
        f"incident_id: {record.incident_id or 'unmatched'}",
        f"hypothesis_id: {record.hypothesis_id or 'unmatched'}",
        f"profile/namespace: {record.profile or 'unknown'}/{record.artifact_namespace or 'unknown'}",
        f"state: {record.state or 'unmatched'} · route: {record.route or 'none'}",
        f"final_route: {record.final_route_after_quality_gate or record.route or 'none'} · lane: {record.lane or 'unknown'}",
        f"playbook: {record.playbook_type or 'unknown'} · score={record.latest_score if record.latest_score is not None else 0}",
        f"quality: impact={record.impact_path_type or 'unknown'} role={record.candidate_role or 'unknown'} "
        f"level={record.opportunity_level or 'unknown'} source_pack={record.source_pack or 'unknown'}",
        f"marked_by: {record.marked_by} · marked_at: {record.marked_at}",
    ])
    if record.notes:
        rows.append(f"notes: {record.notes}")
    rows.append("No live signal, paper-trade, Telegram, or event-fade state was changed.")
    return "\n".join(rows)


def format_feedback_report(read_result: EventFeedbackReadResult) -> str:
    rows = [
        "=" * 76,
        "EVENT ALPHA FEEDBACK REPORT (research artifact only)",
        "=" * 76,
        f"path: {read_result.path}",
        f"rows_read: {read_result.rows_read}",
    ]
    if not read_result.records:
        rows.append("")
        rows.append("No feedback rows found.")
        return "\n".join(rows)
    counts: dict[str, int] = {}
    for record in read_result.records:
        counts[record.label] = counts.get(record.label, 0) + 1
    rows.append("labels: " + ", ".join(f"{label}={count}" for label, count in sorted(counts.items())))
    rows.append("")
    for record in sorted(read_result.records, key=lambda item: item.marked_at, reverse=True):
        rows.append(
            f"{record.label:<18} {record.symbol or record.target}/{record.coin_id or 'unmatched'} "
            f"state={record.state or 'unmatched'} route={record.final_route_after_quality_gate or record.route or 'none'} "
            f"impact={record.impact_path_type or 'unknown'} source_pack={record.source_pack or 'unknown'}"
        )
        rows.append(
            f"  target: {record.feedback_target or record.target} "
            f"({record.feedback_target_type or 'legacy'}) · core={record.core_opportunity_id or 'none'} "
            f"· marked_at: {record.marked_at} · by={record.marked_by}"
        )
        if record.notes:
            rows.append(f"  notes: {record.notes}")
    return "\n".join(rows)


def valid_labels() -> tuple[str, ...]:
    return tuple(label.value for label in EventFeedbackLabel)


def _find_watchlist_entry(
    target: str,
    entries: list[event_watchlist.EventWatchlistEntry],
) -> event_watchlist.EventWatchlistEntry | None:
    clean_target = target[3:] if str(target).startswith("ea:") else target
    target_l = clean_target.strip().lower()
    exact = [
        entry
        for entry in entries
        if clean_target in _entry_feedback_identifiers(entry)
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(f"feedback target {target!r} matched multiple exact watchlist rows")
    loose = [
        entry
        for entry in entries
        if target_l in {entry.symbol.lower(), entry.coin_id.lower()}
    ]
    if len(loose) == 1:
        return loose[0]
    if len(loose) > 1:
        raise ValueError(f"feedback target {target!r} matched multiple watchlist rows; use the full key")
    return None


def _entry_feedback_identifiers(entry: event_watchlist.EventWatchlistEntry) -> set[str]:
    components = dict(entry.latest_score_components or {})
    identifiers = {
        entry.key,
        entry.event_id,
        entry.symbol,
        entry.coin_id,
        event_alpha_router.alert_id_for_entry(entry),
        event_alpha_router.card_id_for_entry(entry),
        str(entry.hypothesis_id or ""),
        str(entry.incident_id or ""),
        str(components.get("hypothesis_id") or ""),
        str(components.get("incident_id") or ""),
        str(components.get("core_opportunity_id") or ""),
    }
    core_id = event_core_opportunities.core_opportunity_id_for_row(entry)
    if core_id:
        identifiers.add(core_id)
    return {item for item in identifiers if item}


def _find_context_row(
    target: str,
    rows: Iterable[Mapping[str, Any]],
    card_paths: Iterable[Path],
    *,
    entry: event_watchlist.EventWatchlistEntry | None,
) -> tuple[dict[str, Any] | None, Path | None]:
    clean_target = target[3:] if str(target).startswith("ea:") else target
    target_l = clean_target.strip().lower()
    row_list = [dict(row) for row in rows if isinstance(row, Mapping)]
    card_target = _card_target_for(clean_target, card_paths)
    if card_target is not None:
        clean_target = card_target[0]
        target_l = clean_target.lower()
    if entry is not None:
        entry_ids = _entry_feedback_identifiers(entry)
        candidates = [
            row for row in row_list
            if entry_ids & _context_identifiers(row)
        ]
        if candidates:
            return _richest_context_row(candidates), card_target[1] if card_target else _card_path_for_row(candidates[0], card_paths)
    exact = [
        row for row in row_list
        if clean_target in _context_identifiers(row)
    ]
    if len(exact) == 1:
        return exact[0], card_target[1] if card_target else _card_path_for_row(exact[0], card_paths)
    if len(exact) > 1:
        return _richest_context_row(exact), card_target[1] if card_target else _card_path_for_row(exact[0], card_paths)
    loose = [
        row for row in row_list
        if target_l in {
            str(_row_value(row, "symbol", "asset_symbol", "validated_symbol") or "").lower(),
            str(_row_value(row, "coin_id", "asset_coin_id", "validated_coin_id") or "").lower(),
        }
    ]
    if len(loose) == 1:
        return loose[0], card_target[1] if card_target else _card_path_for_row(loose[0], card_paths)
    return None, card_target[1] if card_target else None


def _context_identifiers(row: Mapping[str, Any]) -> set[str]:
    components = _components(row)
    identifiers = {
        _row_value(row, "feedback_target", components=components),
        _row_value(row, "core_opportunity_id", components=components),
        _row_value(row, "alert_id", components=components),
        _row_value(row, "card_id", components=components),
        _row_value(row, "alert_key", components=components),
        _row_value(row, "key", components=components),
        _row_value(row, "watchlist_key", components=components),
        _row_value(row, "hypothesis_id", "primary_hypothesis_id", components=components),
        _row_value(row, "incident_id", components=components),
        _row_value(row, "symbol", "asset_symbol", "validated_symbol", components=components),
        _row_value(row, "coin_id", "asset_coin_id", "validated_coin_id", components=components),
        _row_value(row, "card_path", "research_card_path", components=components),
    }
    out = {str(item).strip() for item in identifiers if str(item or "").strip()}
    for item in tuple(out):
        if item.startswith("ea:"):
            out.add(item[3:])
        else:
            out.add(f"ea:{item}")
    return out


def _card_target_for(target: str, card_paths: Iterable[Path]) -> tuple[str, Path] | None:
    target_path = Path(target).expanduser()
    for path in card_paths:
        p = Path(path).expanduser()
        if str(p) == str(target_path) or p.name == target:
            feedback_target = event_research_cards.card_feedback_target(p)
            core_id = event_research_cards.card_core_opportunity_id(p)
            return (feedback_target or core_id or str(p), p)
    return None


def _card_path_for_row(row: Mapping[str, Any], card_paths: Iterable[Path]) -> Path | None:
    ids = _context_identifiers(row)
    embedded = _row_value(row, "card_path", "research_card_path")
    if embedded:
        return Path(str(embedded)).expanduser()
    for path in card_paths:
        p = Path(path).expanduser()
        feedback_target = event_research_cards.card_feedback_target(p)
        core_id = event_research_cards.card_core_opportunity_id(p)
        if (feedback_target and feedback_target in ids) or (core_id and core_id in ids):
            return p
    return None


def _richest_context_row(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return max((dict(row) for row in rows), key=_context_richness_score)


def _context_richness_score(row: Mapping[str, Any]) -> int:
    fields = (
        "core_opportunity_id",
        "feedback_target",
        "card_path",
        "research_card_path",
        "run_id",
        "profile",
        "artifact_namespace",
        "impact_path_type",
        "source_pack",
        "market_confirmation_level",
        "market_context_freshness_status",
        "main_frame_type",
        "final_route_after_quality_gate",
    )
    components = _components(row)
    return sum(1 for field in fields if _row_value(row, field, components=components) not in (None, "", [], {}, ()))


def _row_dict(row: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    return dict(getattr(row, "__dict__", {}) or {})


def _components(row: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("score_components", "latest_score_components", "opportunity_score_components"):
        value = row.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _row_value(row: Mapping[str, Any], *keys: str, components: Mapping[str, Any] | None = None) -> Any:
    comp = components if components is not None else _components(row)
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}, ()):
            return value
        value = comp.get(key) if isinstance(comp, Mapping) else None
        if value not in (None, "", [], {}, ()):
            return value
    return None


def _source_metadata(row: Mapping[str, Any], *, components: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "source",
        "source_provider",
        "source_domain",
        "source_url",
        "source_class",
        "source_pack",
        "source_confidence",
        "provider_coverage_status",
        "source_coverage_gap_reason",
    )
    metadata: dict[str, Any] = {}
    for key in keys:
        value = row.get(key)
        if value in (None, "", [], {}, ()):
            value = components.get(key)
        if value not in (None, "", [], {}, ()):
            metadata[key] = value
    return metadata


def _record_from_entry(
    target: str,
    label: EventFeedbackLabel,
    *,
    entry: event_watchlist.EventWatchlistEntry | None,
    marked_at: str,
    marked_by: str,
    notes: str | None,
    route: str | None,
    context_row: Mapping[str, Any] | None = None,
    card_path: str | Path | None = None,
) -> EventFeedbackRecord:
    if entry is None:
        return EventFeedbackRecord(
            schema_version=FEEDBACK_SCHEMA_VERSION,
            row_type="event_alpha_feedback",
            feedback_id=f"{marked_at}|{target}|{label.value}",
            target=target,
            key=None,
            event_id=None,
            incident_id=None,
            coin_id=None,
            symbol=None,
            relationship_type=None,
            external_asset=None,
            event_time=None,
            label=label.value,
            marked_at=marked_at,
            marked_by=str(marked_by or "human"),
            notes=_optional_str(notes),
            route=route,
            feedback_target=target,
            feedback_target_type="manual_target",
            card_path=str(card_path) if card_path else None,
        )
    components = dict(entry.latest_score_components or {})
    row = dict(context_row or {})
    row_components = _components(row)
    core_id = (
        _row_value(row, "core_opportunity_id", "feedback_target", components=row_components)
        or components.get("core_opportunity_id")
        or event_core_opportunities.core_opportunity_id_for_row(entry)
    )
    source_meta = _source_metadata(row, components=components)
    return EventFeedbackRecord(
        schema_version=FEEDBACK_SCHEMA_VERSION,
        row_type="event_alpha_feedback",
        feedback_id=f"{marked_at}|{entry.key}|{label.value}",
        target=target,
        key=entry.key,
        event_id=entry.event_id,
        incident_id=_optional_str(entry.incident_id or components.get("incident_id")),
        coin_id=entry.coin_id,
        symbol=entry.symbol,
        relationship_type=entry.relationship_type,
        external_asset=entry.external_asset,
        event_time=entry.event_time,
        label=label.value,
        marked_at=marked_at,
        marked_by=str(marked_by or "human"),
        notes=_optional_str(notes),
        route=route,
        state=entry.state,
        playbook_type=entry.latest_playbook_type,
        latest_score=entry.latest_score,
        watchlist_last_seen_at=entry.last_seen_at,
        source_class=_optional_str(components.get("source_class") or _row_value(row, "source_class", components=row_components)),
        source_domain=_optional_str(components.get("source_domain") or _row_value(row, "source_domain", components=row_components)),
        evidence_specificity=_optional_str(components.get("evidence_specificity") or _row_value(row, "evidence_specificity", components=row_components)),
        impact_path_type=_optional_str(components.get("impact_path_type") or _row_value(row, "impact_path_type", "primary_impact_path", components=row_components)),
        candidate_role=_optional_str(components.get("candidate_role") or _row_value(row, "candidate_role", components=row_components)),
        opportunity_level=_optional_str(components.get("opportunity_level") or _row_value(row, "opportunity_level", "final_opportunity_level", components=row_components)),
        market_confirmation_level=_optional_str(components.get("market_confirmation_level") or _row_value(row, "market_confirmation_level", components=row_components)),
        source_pack=_optional_str(
            components.get("evidence_acquisition_source_pack")
            or components.get("source_pack")
            or _row_value(row, "source_pack", "evidence_acquisition_source_pack", components=row_components)
        ),
        source_provider=_optional_str(
            components.get("source_provider")
            or _first_text(components.get("evidence_acquisition_providers_used"))
            or entry.latest_source
        ),
        accepted_evidence_reason_codes=_text_tuple(components.get("accepted_evidence_reason_codes")),
        feedback_target=_optional_str(_row_value(row, "feedback_target", components=row_components) or core_id or target),
        feedback_target_type=_optional_str(_row_value(row, "feedback_target_type", components=row_components) or ("core_opportunity_id" if core_id else "watchlist_key")),
        core_opportunity_id=_optional_str(core_id),
        card_path=str(card_path) if card_path else _optional_str(_row_value(row, "card_path", "research_card_path", components=row_components)),
        run_id=_optional_str(_row_value(row, "run_id", components=row_components) or components.get("run_id")),
        profile=_optional_str(_row_value(row, "profile", components=row_components) or components.get("profile")),
        artifact_namespace=_optional_str(_row_value(row, "artifact_namespace", components=row_components) or components.get("artifact_namespace")),
        hypothesis_id=_optional_str(entry.hypothesis_id or components.get("hypothesis_id") or _row_value(row, "hypothesis_id", components=row_components)),
        watchlist_key=entry.key,
        final_route_after_quality_gate=_optional_str(_row_value(row, "final_route_after_quality_gate", components=row_components) or route),
        lane=_optional_str(_row_value(row, "lane", components=row_components)),
        market_context_freshness_status=_optional_str(entry.market_context_freshness_status or components.get("market_context_freshness_status") or _row_value(row, "market_context_freshness_status", components=row_components)),
        catalyst_frame_status=_optional_str(components.get("catalyst_frame_status") or components.get("frame_status") or _row_value(row, "catalyst_frame_status", "frame_status", components=row_components)),
        main_frame_type=_optional_str(components.get("main_frame_type") or _row_value(row, "main_frame_type", components=row_components)),
        source_provider_domain=_optional_str(components.get("source_domain") or _row_value(row, "source_domain", "source_provider_domain", components=row_components)),
        provider_coverage_status=_optional_str(components.get("provider_coverage_status") or _row_value(row, "provider_coverage_status", "source_coverage_status", components=row_components)),
        source_metadata=source_meta or None,
    )


def _record_from_context_row(
    target: str,
    label: EventFeedbackLabel,
    *,
    row: Mapping[str, Any],
    marked_at: str,
    marked_by: str,
    notes: str | None,
    route: str | None,
    card_path: str | Path | None,
) -> EventFeedbackRecord:
    components = _components(row)
    core_id = _row_value(row, "core_opportunity_id", "feedback_target", components=components)
    feedback_target = _row_value(row, "feedback_target", components=components) or core_id or target
    feedback_target_type = _row_value(row, "feedback_target_type", components=components)
    route_value = route or _row_value(row, "final_route_after_quality_gate", "route", "tier", components=components)
    source_meta = _source_metadata(row, components=components)
    return EventFeedbackRecord(
        schema_version=FEEDBACK_SCHEMA_VERSION,
        row_type="event_alpha_feedback",
        feedback_id=f"{marked_at}|{feedback_target}|{label.value}",
        target=target,
        key=_optional_str(_row_value(row, "key", "alert_key", "watchlist_key", components=components)),
        event_id=_optional_str(_row_value(row, "event_id", components=components)),
        incident_id=_optional_str(_row_value(row, "incident_id", components=components)),
        coin_id=_optional_str(_row_value(row, "coin_id", "asset_coin_id", "validated_coin_id", components=components)),
        symbol=_optional_str(_row_value(row, "symbol", "asset_symbol", "validated_symbol", components=components)),
        relationship_type=_optional_str(_row_value(row, "relationship_type", "impact_path_type", components=components)),
        external_asset=_optional_str(_row_value(row, "external_asset", components=components)),
        event_time=_optional_str(_row_value(row, "event_time", components=components)),
        label=label.value,
        marked_at=marked_at,
        marked_by=str(marked_by or "human"),
        notes=_optional_str(notes),
        route=_optional_str(route_value),
        state=_optional_str(_row_value(row, "final_state_after_quality_gate", "state", components=components)),
        playbook_type=_optional_str(_row_value(row, "effective_playbook_type", "playbook_type", "latest_playbook_type", components=components)),
        latest_score=_optional_int(_row_value(row, "opportunity_score_final", "latest_score", "opportunity_score", components=components)),
        watchlist_last_seen_at=_optional_str(_row_value(row, "last_seen_at", "observed_at", components=components)),
        source_class=_optional_str(_row_value(row, "source_class", components=components)),
        source_domain=_optional_str(_row_value(row, "source_domain", components=components)),
        evidence_specificity=_optional_str(_row_value(row, "evidence_specificity", components=components)),
        impact_path_type=_optional_str(_row_value(row, "impact_path_type", "primary_impact_path", components=components)),
        candidate_role=_optional_str(_row_value(row, "candidate_role", components=components)),
        opportunity_level=_optional_str(_row_value(row, "opportunity_level", "final_opportunity_level", components=components)),
        market_confirmation_level=_optional_str(_row_value(row, "market_confirmation_level", components=components)),
        source_pack=_optional_str(_row_value(row, "source_pack", "evidence_acquisition_source_pack", components=components)),
        source_provider=_optional_str(_row_value(row, "source_provider", "latest_source", "source", components=components)),
        accepted_evidence_reason_codes=_text_tuple(_row_value(row, "accepted_evidence_reason_codes", components=components)),
        feedback_target=_optional_str(feedback_target),
        feedback_target_type=_optional_str(feedback_target_type or ("core_opportunity_id" if core_id else "artifact_row")),
        core_opportunity_id=_optional_str(core_id),
        card_path=str(card_path) if card_path else _optional_str(_row_value(row, "card_path", "research_card_path", components=components)),
        run_id=_optional_str(_row_value(row, "run_id", components=components)),
        profile=_optional_str(_row_value(row, "profile", components=components)),
        artifact_namespace=_optional_str(_row_value(row, "artifact_namespace", components=components)),
        hypothesis_id=_optional_str(_row_value(row, "hypothesis_id", "primary_hypothesis_id", components=components)),
        watchlist_key=_optional_str(_row_value(row, "watchlist_key", "key", "alert_key", components=components)),
        final_route_after_quality_gate=_optional_str(_row_value(row, "final_route_after_quality_gate", components=components) or route_value),
        lane=_optional_str(_row_value(row, "lane", components=components)),
        market_context_freshness_status=_optional_str(_row_value(row, "market_context_freshness_status", components=components)),
        catalyst_frame_status=_optional_str(_row_value(row, "catalyst_frame_status", "frame_status", components=components)),
        main_frame_type=_optional_str(_row_value(row, "main_frame_type", components=components)),
        source_provider_domain=_optional_str(_row_value(row, "source_provider_domain", "source_domain", components=components)),
        provider_coverage_status=_optional_str(_row_value(row, "provider_coverage_status", "source_coverage_status", components=components)),
        source_metadata=source_meta or None,
    )


def _append_record(path: Path, record: EventFeedbackRecord) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_json_ready(asdict(record)), sort_keys=True, separators=(",", ":")))
        fh.write("\n")


def _record_from_row(row: Mapping[str, Any]) -> EventFeedbackRecord | None:
    if row.get("row_type") != "event_alpha_feedback":
        return None
    try:
        label = _label(str(row.get("label") or ""))
        marked_at = str(row.get("marked_at") or "")
        target = str(row.get("target") or row.get("key") or "")
        if not marked_at or not target:
            return None
        return EventFeedbackRecord(
            schema_version=str(row.get("schema_version") or FEEDBACK_SCHEMA_VERSION),
            row_type="event_alpha_feedback",
            feedback_id=str(row.get("feedback_id") or f"{marked_at}|{target}|{label.value}"),
            target=target,
            key=_optional_str(row.get("key")),
            event_id=_optional_str(row.get("event_id")),
            incident_id=_optional_str(row.get("incident_id")),
            coin_id=_optional_str(row.get("coin_id")),
            symbol=_optional_str(row.get("symbol")),
            relationship_type=_optional_str(row.get("relationship_type")),
            external_asset=_optional_str(row.get("external_asset")),
            event_time=_optional_str(row.get("event_time")),
            label=label.value,
            marked_at=marked_at,
            marked_by=str(row.get("marked_by") or "human"),
            notes=_optional_str(row.get("notes")),
            source=str(row.get("source") or "manual_cli"),
            state=_optional_str(row.get("state")),
            route=_optional_str(row.get("route")),
            playbook_type=_optional_str(row.get("playbook_type")),
            latest_score=_optional_int(row.get("latest_score")),
            watchlist_last_seen_at=_optional_str(row.get("watchlist_last_seen_at")),
            source_class=_optional_str(row.get("source_class")),
            source_domain=_optional_str(row.get("source_domain")),
            evidence_specificity=_optional_str(row.get("evidence_specificity")),
            impact_path_type=_optional_str(row.get("impact_path_type")),
            candidate_role=_optional_str(row.get("candidate_role")),
            opportunity_level=_optional_str(row.get("opportunity_level")),
            market_confirmation_level=_optional_str(row.get("market_confirmation_level")),
            source_pack=_optional_str(row.get("source_pack")),
            source_provider=_optional_str(row.get("source_provider")),
            accepted_evidence_reason_codes=_text_tuple(row.get("accepted_evidence_reason_codes")),
            feedback_target=_optional_str(row.get("feedback_target")),
            feedback_target_type=_optional_str(row.get("feedback_target_type")),
            core_opportunity_id=_optional_str(row.get("core_opportunity_id")),
            card_path=_optional_str(row.get("card_path")),
            run_id=_optional_str(row.get("run_id")),
            profile=_optional_str(row.get("profile")),
            artifact_namespace=_optional_str(row.get("artifact_namespace")),
            hypothesis_id=_optional_str(row.get("hypothesis_id")),
            watchlist_key=_optional_str(row.get("watchlist_key")),
            final_route_after_quality_gate=_optional_str(row.get("final_route_after_quality_gate")),
            lane=_optional_str(row.get("lane")),
            market_context_freshness_status=_optional_str(row.get("market_context_freshness_status")),
            catalyst_frame_status=_optional_str(row.get("catalyst_frame_status")),
            main_frame_type=_optional_str(row.get("main_frame_type")),
            source_provider_domain=_optional_str(row.get("source_provider_domain")),
            provider_coverage_status=_optional_str(row.get("provider_coverage_status")),
            source_metadata=dict(row.get("source_metadata")) if isinstance(row.get("source_metadata"), Mapping) else None,
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


def _label(value: str | EventFeedbackLabel) -> EventFeedbackLabel:
    if isinstance(value, EventFeedbackLabel):
        return value
    try:
        return EventFeedbackLabel(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"feedback label must be one of: {', '.join(valid_labels())}") from exc


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _first_text(value: Any) -> str | None:
    for item in _text_tuple(value):
        return item
    return None


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, (str, bytes)):
        text = str(value).strip()
        return (text,) if text else ()
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return tuple(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
    text = str(value).strip()
    return (text,) if text else ()


def _optional_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


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
