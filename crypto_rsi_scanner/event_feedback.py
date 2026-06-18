"""Lightweight research feedback artifacts for Event Alpha Radar."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_watchlist


FEEDBACK_SCHEMA_VERSION = "event_alpha_feedback_v1"


class EventFeedbackLabel(str, Enum):
    USEFUL = "useful"
    JUNK = "junk"
    WATCH = "watch"
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
) -> EventFeedbackRecord:
    """Append one manual research feedback row.

    Feedback is an artifact-only annotation. It does not alter watchlist state,
    alert tiers, paper trades, live DB rows, or event-fade eligibility.
    """
    clean_target = str(target or "").strip()
    if not clean_target:
        raise ValueError("feedback target is required")
    parsed_label = _label(label)
    entry = _find_watchlist_entry(clean_target, list(watchlist_entries))
    if entry is None and parsed_label != EventFeedbackLabel.MISSED:
        raise ValueError(
            f"no unique watchlist row matched {clean_target!r}; use label=missed for uncaptured opportunities"
        )
    marked_at = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    record = _record_from_entry(
        clean_target,
        parsed_label,
        entry=entry,
        marked_at=marked_at,
        marked_by=marked_by,
        notes=notes,
        route=route,
    )
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
        f"label: {record.label}",
        f"symbol/coin: {(record.symbol or 'unknown')}/{record.coin_id or 'unknown'}",
        f"event_id: {record.event_id or 'unmatched'}",
        f"state: {record.state or 'unmatched'} · route: {record.route or 'none'}",
        f"playbook: {record.playbook_type or 'unknown'} · score={record.latest_score if record.latest_score is not None else 0}",
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
            f"state={record.state or 'unmatched'} route={record.route or 'none'}"
        )
        rows.append(f"  target: {record.target} · marked_at: {record.marked_at} · by={record.marked_by}")
        if record.notes:
            rows.append(f"  notes: {record.notes}")
    return "\n".join(rows)


def valid_labels() -> tuple[str, ...]:
    return tuple(label.value for label in EventFeedbackLabel)


def _find_watchlist_entry(
    target: str,
    entries: list[event_watchlist.EventWatchlistEntry],
) -> event_watchlist.EventWatchlistEntry | None:
    target_l = target.strip().lower()
    exact = [
        entry
        for entry in entries
        if target == entry.key or target == entry.event_id
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


def _record_from_entry(
    target: str,
    label: EventFeedbackLabel,
    *,
    entry: event_watchlist.EventWatchlistEntry | None,
    marked_at: str,
    marked_by: str,
    notes: str | None,
    route: str | None,
) -> EventFeedbackRecord:
    if entry is None:
        return EventFeedbackRecord(
            schema_version=FEEDBACK_SCHEMA_VERSION,
            row_type="event_alpha_feedback",
            feedback_id=f"{marked_at}|{target}|{label.value}",
            target=target,
            key=None,
            event_id=None,
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
        )
    return EventFeedbackRecord(
        schema_version=FEEDBACK_SCHEMA_VERSION,
        row_type="event_alpha_feedback",
        feedback_id=f"{marked_at}|{entry.key}|{label.value}",
        target=target,
        key=entry.key,
        event_id=entry.event_id,
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
