"""Read-only unified-calendar fixture and artifact loaders."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from .models import CalendarValidationError, UnifiedCalendarEvent, normalize_unified_calendar_event


UNIFIED_CALENDAR_FILENAME = "event_unified_calendar_events.jsonl"
UNIFIED_CALENDAR_PREVIEW_FILENAME = "event_unified_calendar_preview.md"


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

    source = Path(path).expanduser()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(payload, Mapping):
        raw_rows = payload.get("events") or payload.get("items") or payload.get("data") or ()
    else:
        raw_rows = payload
    if not isinstance(raw_rows, Iterable) or isinstance(raw_rows, (str, bytes, Mapping)):
        raise ValueError("unified calendar fixture must contain an event list")
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
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
    observed_at: str | None,
) -> tuple[dict[str, Any], ...]:
    """Normalize valid scheduled/unlock rows and deduplicate their event ids."""

    normalized: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
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
        except CalendarValidationError:
            continue
        normalized[str(row["calendar_event_id"])] = row
    return tuple(
        sorted(
            normalized.values(),
            key=lambda row: (
                str(row.get("scheduled_at") or row.get("window_start") or "~"),
                str(row.get("calendar_event_id") or ""),
            ),
        )
    )


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
                f"- kind / importance: {row.get('event_kind') or 'unknown'} / {row.get('importance') or 'unknown'}",
                f"- affected assets: {assets}",
                f"- tracking: {row.get('post_event_tracking_status') or 'unknown'}",
                f"- source: {row.get('source_url') or 'unavailable'}",
                "- notifications sent: 0",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


__all__ = (
    "UNIFIED_CALENDAR_FILENAME", "UNIFIED_CALENDAR_PREVIEW_FILENAME",
    "format_unified_calendar_preview", "load_unified_calendar_artifact",
    "load_unified_calendar_fixture", "normalize_unified_calendar_rows",
    "write_unified_calendar_artifact",
)
