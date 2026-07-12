"""Read-only unified-calendar fixture and artifact loaders."""

from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .models import (
    CalendarValidationError,
    UnifiedCalendarEvent,
    normalize_unified_calendar_event,
)
from .normalization import (
    CALENDAR_DEDUPE_POLICY,
    CALENDAR_NORMALIZATION_CONTRACT_VERSION,
    UnifiedCalendarNormalizationTelemetry,
)


UNIFIED_CALENDAR_FILENAME = "event_unified_calendar_events.jsonl"
UNIFIED_CALENDAR_PREVIEW_FILENAME = "event_unified_calendar_preview.md"


class _DuplicateFixtureJsonKey(ValueError):
    """Internal marker for ambiguous fixture JSON objects."""


@dataclass(frozen=True)
class UnifiedCalendarNormalizationResult:
    """Normalized rows plus their deterministic payload-free telemetry."""

    rows: tuple[dict[str, Any], ...]
    telemetry: UnifiedCalendarNormalizationTelemetry

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple):
            raise ValueError("calendar normalization rows must be a tuple")
        if len(self.rows) != self.telemetry.output_rows:
            raise ValueError("calendar normalization output row invariant failed")


def load_unified_calendar_fixture_raw_rows(path: str | Path) -> tuple[Any, ...]:
    """Load raw rows from the first present events/items/data fixture key."""

    source = Path(path).expanduser()
    try:
        payload = json.loads(
            source.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
    except _DuplicateFixtureJsonKey:
        raise ValueError("unified calendar fixture contains duplicate JSON object keys") from None
    if isinstance(payload, Mapping):
        raw_rows: Any = ()
        selected = False
        for key in ("events", "items", "data"):
            if key in payload:
                raw_rows = payload.get(key)
                selected = True
                break
        if not selected and payload:
            raise ValueError("unified calendar fixture object must contain events, items, or data")
    else:
        raw_rows = payload
    if not isinstance(raw_rows, Iterable) or isinstance(raw_rows, (str, bytes, Mapping)):
        raise ValueError("unified calendar fixture must contain an event list")
    return tuple(raw_rows)


def load_unified_calendar_fixture(
    path: str | Path,
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
    observed_at: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Load and normalize one checked fixture without writing artifacts."""

    raw_rows = load_unified_calendar_fixture_raw_rows(path)
    return tuple(
        normalize_unified_calendar_event(
            row,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            observed_at=observed_at,
        ).to_dict()
        for row in raw_rows
        if isinstance(row, Mapping)
    )


def load_unified_calendar_fixture_with_telemetry(
    path: str | Path,
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
    observed_at: str | None = None,
) -> UnifiedCalendarNormalizationResult:
    """Load raw fixture rows and normalize them once with truthful telemetry."""

    return normalize_unified_calendar_rows_with_telemetry(
        load_unified_calendar_fixture_raw_rows(path),
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
        observed_at=observed_at,
    )


def load_unified_calendar_artifact(
    path: str | Path,
    *,
    run_id: str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Load validated local JSONL rows, optionally scoped to exact identity."""

    source = Path(path).expanduser()
    if not source.exists():
        return ()
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        parsed = json.loads(line)
        if not isinstance(parsed, Mapping):
            raise ValueError(f"calendar artifact line {line_number} is not an object")
        if str(parsed.get("row_type") or "") != "event_unified_calendar_event":
            continue
        event = UnifiedCalendarEvent.from_mapping(parsed)
        row = event.to_dict()
        if run_id is not None and str(row.get("run_id") or "") != str(run_id):
            continue
        if profile is not None and str(row.get("profile") or "") != str(profile):
            continue
        if artifact_namespace is not None and str(row.get("artifact_namespace") or "") != str(artifact_namespace):
            continue
        rows.append(row)
    return tuple(rows)


def normalize_unified_calendar_rows(
    rows: Iterable[Any],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
    observed_at: str | None,
) -> tuple[dict[str, Any], ...]:
    """Normalize valid scheduled/unlock rows and deduplicate their event ids."""

    return normalize_unified_calendar_rows_with_telemetry(
        rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
        observed_at=observed_at,
    ).rows


def normalize_unified_calendar_rows_with_telemetry(
    rows: Iterable[Any],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
    observed_at: str | None,
) -> UnifiedCalendarNormalizationResult:
    """Normalize raw rows exactly once and return payload-free diagnostics."""

    normalized: dict[str, dict[str, Any]] = {}
    input_rows = 0
    accepted_rows = 0
    duplicate_overwrite_rows = 0
    non_mapping_rows = 0
    rejected_rows = 0
    rejected_reason_counts: Counter[str] = Counter()
    for raw in rows:
        input_rows += 1
        if not isinstance(raw, Mapping):
            non_mapping_rows += 1
            continue
        try:
            row = normalize_unified_calendar_event(
                raw,
                profile=profile,
                artifact_namespace=artifact_namespace,
                run_mode=run_mode,
                run_id=run_id,
                observed_at=observed_at,
            ).to_dict()
        except CalendarValidationError as exc:
            rejected_rows += 1
            rejected_reason_counts[exc.code.value] += 1
            continue
        accepted_rows += 1
        event_id = str(row["calendar_event_id"])
        if event_id in normalized:
            duplicate_overwrite_rows += 1
        normalized[event_id] = row
    output_rows = tuple(
        sorted(
            normalized.values(),
            key=lambda row: (
                str(row.get("scheduled_at") or row.get("window_start") or "~"),
                str(row.get("calendar_event_id") or ""),
            ),
        )
    )
    telemetry = UnifiedCalendarNormalizationTelemetry(
        contract_version=CALENDAR_NORMALIZATION_CONTRACT_VERSION,
        dedupe_policy=CALENDAR_DEDUPE_POLICY,
        input_rows=input_rows,
        accepted_rows=accepted_rows,
        output_rows=len(output_rows),
        duplicate_overwrite_rows=duplicate_overwrite_rows,
        non_mapping_rows=non_mapping_rows,
        rejected_rows=rejected_rows,
        rejected_reason_counts=dict(sorted(rejected_reason_counts.items())),
    )
    return UnifiedCalendarNormalizationResult(rows=output_rows, telemetry=telemetry)


def write_unified_calendar_artifact(
    path: str | Path,
    rows: Iterable[Mapping[str, Any]],
) -> Path:
    """Atomically replace one research-only unified calendar JSONL artifact."""

    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    materialized = tuple(dict(row) for row in rows if isinstance(row, Mapping))
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            for row in materialized:
                handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def format_unified_calendar_preview(rows: Iterable[Mapping[str, Any]]) -> str:
    """Render a no-send operator preview for fixture or current calendar rows."""

    materialized = tuple(dict(row) for row in rows if isinstance(row, Mapping))
    lines = [
        "# Unified Radar Calendar Preview",
        "",
        "Research-only / no-send preview. Not a trade instruction.",
        f"rows: {len(materialized)}",
        "",
    ]
    for row in materialized:
        when = row.get("scheduled_at") or (
            f"{row.get('window_start') or 'unknown'} .. {row.get('window_end') or 'unknown'}"
        )
        assets = ", ".join(str(item) for item in row.get("affected_assets") or ()) or "market-wide"
        lines.extend(
            (
                f"## {row.get('title') or 'Untitled event'}",
                f"- when: {when} ({row.get('time_certainty') or 'unknown'})",
                f"- timezone: {row.get('timezone') or 'UTC'}",
                f"- kind / importance: {row.get('event_kind') or 'unknown'} / {row.get('importance') or 'unknown'}",
                (
                    "- forecast / previous / actual / surprise: "
                    f"{_calendar_value(row.get('forecast_value'))} / "
                    f"{_calendar_value(row.get('previous_value'))} / "
                    f"{_calendar_value(row.get('actual_value'))} / "
                    f"{_calendar_value(row.get('surprise_value'))}"
                ),
                (
                    "- impact window: "
                    f"-{row.get('impact_window_before') or '24h'} / +{row.get('impact_window_after') or '4h'}"
                ),
                f"- affected assets: {assets}",
                f"- tracking: {row.get('post_event_tracking_status') or 'unknown'}",
                f"- source: {row.get('source_url') or 'unavailable'}",
                "- notifications sent: 0",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _calendar_value(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):g}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)


def _json_object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in pairs:
        if key in parsed:
            raise _DuplicateFixtureJsonKey
        parsed[key] = value
    return parsed


__all__ = (
    "CALENDAR_DEDUPE_POLICY", "CALENDAR_NORMALIZATION_CONTRACT_VERSION",
    "UNIFIED_CALENDAR_FILENAME", "UNIFIED_CALENDAR_PREVIEW_FILENAME",
    "UnifiedCalendarNormalizationResult", "UnifiedCalendarNormalizationTelemetry",
    "format_unified_calendar_preview", "load_unified_calendar_artifact",
    "load_unified_calendar_fixture", "load_unified_calendar_fixture_raw_rows",
    "load_unified_calendar_fixture_with_telemetry", "normalize_unified_calendar_rows",
    "normalize_unified_calendar_rows_with_telemetry",
    "write_unified_calendar_artifact",
)
