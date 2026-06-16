"""Research-only JSONL cache for event-discovery evidence.

This cache preserves point-in-time event-discovery artifacts for validation
work. It never writes live scanner storage, routes notifications, opens paper
trades, or implies execution.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_discovery
from .event_models import EventDiscoveryResult

CACHE_SCHEMA_VERSION = "event_discovery_cache_v1"


@dataclass(frozen=True)
class EventDiscoveryCacheWriteResult:
    cache_dir: Path
    run_id: str
    observed_at: str
    raw_events_written: int
    normalized_events_written: int
    event_asset_links_written: int
    classifications_written: int
    candidate_snapshots_written: int
    runs_written: int


def write_event_discovery_cache(
    result: EventDiscoveryResult,
    cache_dir: str | Path,
    *,
    observed_at: datetime | None = None,
) -> EventDiscoveryCacheWriteResult:
    """Write discovery evidence to a local observational JSONL cache."""
    observed = _as_utc(observed_at or datetime.now(timezone.utc))
    observed_iso = observed.isoformat()
    run_id = observed.strftime("%Y%m%dT%H%M%S.%fZ")
    root = Path(cache_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)

    raw_written = _append_unique_jsonl(
        root / "raw_events.jsonl",
        (_cache_row("raw_event", asdict(raw), run_id, observed_iso) for raw in result.raw_events),
        key_fields=("provider", "raw_id", "content_hash"),
    )
    normalized_written = _append_unique_jsonl(
        root / "normalized_events.jsonl",
        (
            _cache_row("normalized_event", asdict(event), run_id, observed_iso)
            for event in result.normalized_events
        ),
        key_fields=("event_id", "raw_ids"),
    )
    links_written = _append_unique_jsonl(
        root / "event_asset_links.jsonl",
        (_cache_row("event_asset_link", asdict(link), run_id, observed_iso) for link in result.links),
        key_fields=("event_id", "coin_id", "match_reason"),
    )
    classifications_written = _append_unique_jsonl(
        root / "classifications.jsonl",
        (
            _cache_row("event_classification", asdict(classification), run_id, observed_iso)
            for classification in result.classifications
        ),
        key_fields=("event_id", "coin_id", "classifier_version", "relationship_type"),
    )
    candidate_rows = (
        _cache_row("candidate_snapshot", row, run_id, observed_iso)
        for row in event_discovery.event_fade_validation_sample_rows(result, exported_at=observed)
    )
    candidate_written = _append_jsonl(root / "candidate_snapshots.jsonl", candidate_rows)
    run_written = _append_jsonl(root / "discovery_runs.jsonl", [{
        "schema_version": CACHE_SCHEMA_VERSION,
        "row_type": "discovery_run",
        "run_id": run_id,
        "observed_at": observed_iso,
        "raw_events": len(result.raw_events),
        "normalized_events": len(result.normalized_events),
        "event_asset_links": len(result.links),
        "classifications": len(result.classifications),
        "candidate_snapshots": len(result.candidates),
        "raw_events_written": raw_written,
        "normalized_events_written": normalized_written,
        "event_asset_links_written": links_written,
        "classifications_written": classifications_written,
        "candidate_snapshots_written": candidate_written,
    }])
    return EventDiscoveryCacheWriteResult(
        cache_dir=root,
        run_id=run_id,
        observed_at=observed_iso,
        raw_events_written=raw_written,
        normalized_events_written=normalized_written,
        event_asset_links_written=links_written,
        classifications_written=classifications_written,
        candidate_snapshots_written=candidate_written,
        runs_written=run_written,
    )


def _cache_row(row_type: str, payload: Mapping[str, Any], run_id: str, observed_at: str) -> dict[str, Any]:
    data = dict(payload)
    payload_schema = data.pop("schema_version", None)
    payload_row_type = data.pop("row_type", None)
    if payload_schema is not None:
        data["payload_schema_version"] = payload_schema
    if payload_row_type is not None:
        data["payload_row_type"] = payload_row_type
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "row_type": row_type,
        "run_id": run_id,
        "observed_at": observed_at,
        **data,
    }


def _append_unique_jsonl(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    key_fields: tuple[str, ...],
) -> int:
    existing = _existing_keys(path, key_fields)
    new_rows: list[Mapping[str, Any]] = []
    for row in rows:
        key = _row_key(row, key_fields)
        if key in existing:
            continue
        existing.add(key)
        new_rows.append(row)
    return _append_jsonl(path, new_rows)


def _append_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    data = list(rows)
    if not data:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in data:
            fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    return len(data)


def _existing_keys(path: Path, key_fields: tuple[str, ...]) -> set[tuple[str, ...]]:
    if not path.exists():
        return set()
    keys: set[tuple[str, ...]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        keys.add(_row_key(row, key_fields))
    return keys


def _row_key(row: Mapping[str, Any], key_fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_key_part(row.get(field)) for field in key_fields)


def _key_part(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return json.dumps([_json_ready(part) for part in value], sort_keys=True, separators=(",", ":"))
    if isinstance(value, Mapping):
        return json.dumps(_json_ready(value), sort_keys=True, separators=(",", ":"))
    return "" if value is None else str(value)


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(child) for child in value]
    return value


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
