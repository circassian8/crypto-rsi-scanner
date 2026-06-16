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
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class EventDiscoveryCacheReadResult:
    cache_dir: Path
    snapshots_read: int
    rows: list[dict[str, Any]]
    latest_per_identity: bool


@dataclass(frozen=True)
class EventDiscoveryRunsReadResult:
    cache_dir: Path
    runs_read: int
    rows: list[dict[str, Any]]
    limit: int | None


def write_event_discovery_cache(
    result: EventDiscoveryResult,
    cache_dir: str | Path,
    *,
    observed_at: datetime | None = None,
    diagnostics: Mapping[str, Any] | None = None,
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
    previous_transitions = _latest_transition_state(root / "candidate_snapshots.jsonl")
    sample_rows = event_discovery.event_fade_validation_sample_rows(result, exported_at=observed)
    sample_rows = _apply_transition_timestamps(sample_rows, previous_transitions, observed_iso)
    candidate_rows = (
        _cache_row("candidate_snapshot", row, run_id, observed_iso)
        for row in sample_rows
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
        "diagnostics": _json_ready(diagnostics or {}),
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
        diagnostics=dict(diagnostics or {}),
    )


def load_cached_validation_sample(
    cache_dir: str | Path,
    *,
    latest_per_identity: bool = True,
) -> EventDiscoveryCacheReadResult:
    """Load cached candidate snapshots as validation-sample rows."""
    root = Path(cache_dir).expanduser()
    path = root / "candidate_snapshots.jsonl"
    rows: list[dict[str, Any]] = []
    snapshots_read = 0
    for cache_row in _read_jsonl(path):
        if cache_row.get("row_type") != "candidate_snapshot":
            continue
        snapshots_read += 1
        sample_row = _unwrap_candidate_snapshot(cache_row)
        if sample_row is not None:
            rows.append(sample_row)
    if latest_per_identity:
        rows = _latest_validation_rows(rows)
    return EventDiscoveryCacheReadResult(
        cache_dir=root,
        snapshots_read=snapshots_read,
        rows=rows,
        latest_per_identity=latest_per_identity,
    )


def load_discovery_runs(
    cache_dir: str | Path,
    *,
    limit: int | None = 10,
) -> EventDiscoveryRunsReadResult:
    """Load recent event-discovery cache run rows, newest first."""
    root = Path(cache_dir).expanduser()
    path = root / "discovery_runs.jsonl"
    rows = [row for row in _read_jsonl(path) if row.get("row_type") == "discovery_run"]
    selected = rows[-limit:] if limit and limit > 0 else rows
    selected = list(reversed(selected))
    return EventDiscoveryRunsReadResult(
        cache_dir=root,
        runs_read=len(rows),
        rows=selected,
        limit=limit,
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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


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


def _unwrap_candidate_snapshot(row: Mapping[str, Any]) -> dict[str, Any] | None:
    schema = row.get("payload_schema_version")
    if schema != event_discovery.VALIDATION_SAMPLE_SCHEMA_VERSION:
        return None
    sample = {
        field: row.get(field)
        for field in event_discovery.VALIDATION_SAMPLE_FIELDS
    }
    sample["schema_version"] = schema
    sample["row_type"] = row.get("payload_row_type") or "candidate"
    return sample


def _latest_transition_state(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    state: dict[tuple[str, str, str], tuple[datetime, int, dict[str, Any]]] = {}
    for idx, row in enumerate(_read_jsonl(path)):
        if row.get("row_type") != "candidate_snapshot":
            continue
        sample = _unwrap_candidate_snapshot(row)
        if sample is None:
            continue
        key = _validation_identity(sample)
        if key is None:
            continue
        observed = _parse_iso(sample.get("exported_at") or row.get("observed_at"))
        current = state.get(key)
        if current is None or (observed, idx) >= (current[0], current[1]):
            state[key] = (observed, idx, sample)
    return {key: value[2] for key, value in state.items()}


def _apply_transition_timestamps(
    rows: Iterable[Mapping[str, Any]],
    previous: Mapping[tuple[str, str, str], Mapping[str, Any]],
    observed_iso: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        key = _validation_identity(data)
        prior = previous.get(key) if key is not None else None
        first_seen = _first_nonempty(prior, "first_seen_at") if prior else None
        first_seen = first_seen or observed_iso
        data["first_seen_at"] = first_seen
        data["last_seen_at"] = observed_iso

        if _is_watchlisted(data):
            data["first_watchlisted_at"] = _first_nonempty(prior, "first_watchlisted_at") if prior else None
            data["first_watchlisted_at"] = data["first_watchlisted_at"] or observed_iso
        elif prior and prior.get("first_watchlisted_at"):
            data["first_watchlisted_at"] = prior.get("first_watchlisted_at")

        if _is_armed(data):
            data["first_armed_at"] = _first_nonempty(prior, "first_armed_at") if prior else None
            data["first_armed_at"] = data["first_armed_at"] or observed_iso
        elif prior and prior.get("first_armed_at"):
            data["first_armed_at"] = prior.get("first_armed_at")

        if _is_triggered(data):
            data["first_triggered_at"] = _first_nonempty(prior, "first_triggered_at") if prior else None
            data["first_triggered_at"] = data["first_triggered_at"] or data.get("trigger_observed_at") or observed_iso
        elif prior and prior.get("first_triggered_at"):
            data["first_triggered_at"] = prior.get("first_triggered_at")
        out.append(data)
    return out


def _first_nonempty(row: Mapping[str, Any] | None, field: str) -> Any:
    if not row:
        return None
    value = row.get(field)
    return value if value not in (None, "") else None


def _is_watchlisted(row: Mapping[str, Any]) -> bool:
    return str(row.get("signal_type") or "") in {"WATCHLIST", "ARMED", "SHORT_TRIGGERED"} or str(
        row.get("fade_state") or ""
    ) in {"WATCHLISTED", "PRE_EVENT_HYPE", "BLOWOFF_RISK", "EVENT_PASSED", "ARMED", "TRIGGERED_SHORT"}


def _is_armed(row: Mapping[str, Any]) -> bool:
    return str(row.get("signal_type") or "") in {"ARMED", "SHORT_TRIGGERED"} or str(row.get("fade_state") or "") in {
        "ARMED",
        "TRIGGERED_SHORT",
        "MANAGING_POSITION",
    }


def _is_triggered(row: Mapping[str, Any]) -> bool:
    return str(row.get("signal_type") or "") == "SHORT_TRIGGERED" or str(row.get("fade_state") or "") == "TRIGGERED_SHORT"


def _latest_validation_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str, str], tuple[datetime, int, dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        data = dict(row)
        key = _validation_identity(data)
        if key is None:
            passthrough.append(data)
            continue
        observed = _parse_iso(data.get("exported_at"))
        current = latest.get(key)
        if current is None or (observed, idx) >= (current[0], current[1]):
            latest[key] = (observed, idx, data)
    selected = [value[2] for value in latest.values()]
    selected.extend(passthrough)
    return sorted(
        selected,
        key=lambda row: (
            str(row.get("event_time") or row.get("first_seen_time") or row.get("exported_at") or ""),
            str(row.get("asset_symbol") or ""),
            str(row.get("event_id") or ""),
        ),
    )


def _validation_identity(row: Mapping[str, Any]) -> tuple[str, str, str] | None:
    event_id = row.get("event_id")
    coin_id = row.get("asset_coin_id")
    relationship = row.get("relationship_type")
    if not event_id or not coin_id or not relationship:
        return None
    return (str(event_id), str(coin_id), str(relationship))


def _parse_iso(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


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
