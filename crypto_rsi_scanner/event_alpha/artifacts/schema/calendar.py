"""Unified calendar schema specification and semantic checks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

SCHEMA_IDS = ("unified_calendar_event_v1",)


def schema_specs(
    schema_factory: Callable[..., Any],
    *,
    operation_safety: tuple[str, ...],
    common_lineage: tuple[str, ...],
) -> dict[str, Any]:
    safety = tuple(dict.fromkeys((
        "research_only", "created_alert", "notification_send_enabled", "execution_enabled",
        "paper_trading_enabled", "normal_rsi_routing_enabled", *operation_safety,
    )))
    return {
        "unified_calendar_event_v1": schema_factory(
            "unified_calendar_event_v1",
            required=(
                "row_type", "calendar_event_id", "title", "event_kind", "time_certainty",
                "importance", "affected_assets", "source", "source_url", "reminder_windows",
                "post_event_tracking_status", "research_only",
            ),
            optional=(
                "schema_id", "schema_version", "scheduled_at", "window_start", "window_end",
                "observed_at", "created_alert", "notification_send_enabled", "execution_enabled",
                "paper_trading_enabled", "normal_rsi_routing_enabled", *operation_safety,
            ),
            types={
                "row_type": "str", "calendar_event_id": "str", "title": "str",
                "event_kind": "str", "time_certainty": "str", "importance": "str",
                "affected_assets": "list", "source": "str", "source_url": "str",
                "reminder_windows": "list", "post_event_tracking_status": "str",
                "research_only": "bool",
            },
            enums={
                "event_kind": (
                    "central_bank", "inflation", "employment", "macro_release", "crypto_unlock",
                    "exchange", "project", "protocol", "regulatory",
                ),
                "time_certainty": ("exact", "window", "estimated", "unknown"),
                "importance": ("low", "medium", "high", "critical"),
                "post_event_tracking_status": (
                    "upcoming", "active_window", "changed", "completed", "canceled",
                    "needs_confirmation",
                ),
            },
            safety=safety,
            timestamps=("scheduled_at", "window_start", "window_end", "observed_at"),
            lineage=common_lineage,
        )
    }


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    certainty = str(row.get("time_certainty") or "")
    scheduled = _timestamp(row.get("scheduled_at"))
    window_start = _timestamp(row.get("window_start"))
    window_end = _timestamp(row.get("window_end"))
    if certainty == "exact" and scheduled is None:
        errors.append("calendar_exact_missing_scheduled_at")
    if certainty == "window" and (window_start is None or window_end is None):
        errors.append("calendar_window_missing_bounds")
    if window_start is not None and window_end is not None and window_end < window_start:
        errors.append("calendar_window_end_before_start")
    parsed_url = urlsplit(str(row.get("source_url") or "").strip())
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        errors.append("calendar_source_url_not_http")
    return errors


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


__all__ = ("SCHEMA_IDS", "schema_specs", "validate_contract")
