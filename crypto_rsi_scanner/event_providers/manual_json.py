"""Manual JSON event provider for offline event-discovery research."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..event_core.models import RawDiscoveredEvent

log = logging.getLogger(__name__)


def parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"invalid datetime {value!r}") from exc
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    raise ValueError(f"invalid datetime {value!r}")


def content_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ManualJsonEventProvider:
    name = "manual_json"

    def __init__(self, path: str | Path | None, *, required: bool = False) -> None:
        self.path = Path(path).expanduser() if path else None
        self.required = required

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        if self.path is None or not self.path.exists():
            if self.required:
                raise FileNotFoundError(f"manual event fixture not found: {self.path}")
            log.warning("Manual event fixture missing: %s", self.path)
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise ValueError(f"invalid manual event fixture {self.path}: {exc}") from exc
            log.warning("Manual event fixture load failed: %s", exc)
            return []
        if isinstance(raw, Mapping):
            raw = raw.get("raw_events", raw.get("events", raw))
        if not isinstance(raw, list):
            if self.required:
                raise ValueError("manual event fixture must be a list")
            log.warning("Manual event fixture must be a list: %s", self.path)
            return []

        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        out: list[RawDiscoveredEvent] = []
        for idx, item in enumerate(raw):
            if not isinstance(item, Mapping):
                if self.required:
                    raise ValueError("manual event fixture entries must be objects")
                log.warning("Skipping non-object manual event fixture entry at index %s", idx)
                continue
            try:
                fetched_at = parse_datetime(item.get("fetched_at")) or datetime.now(timezone.utc)
                published_at = parse_datetime(item.get("published_at"))
            except ValueError as exc:
                if self.required:
                    raise
                log.warning("Skipping manual event with invalid datetime: %s", exc)
                continue
            reference_time = published_at or fetched_at
            if reference_time < start_utc or reference_time > end_utc:
                continue
            title = str(item.get("title") or "")
            raw_id = str(item.get("raw_id") or f"{self.name}:{content_hash(item)[:16]}")
            out.append(RawDiscoveredEvent(
                raw_id=raw_id,
                provider=str(item.get("provider") or self.name),
                fetched_at=fetched_at,
                published_at=published_at,
                source_url=item.get("source_url"),
                title=title,
                body=item.get("body"),
                raw_json=dict(item),
                source_confidence=float(item.get("source_confidence") or 0.5),
                content_hash=content_hash(item),
            ))
        return out


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
