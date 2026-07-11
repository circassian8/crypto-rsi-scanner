"""Canonical, explicitly scoped counters for one Event Alpha operator run."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


COUNTER_SCHEMA_VERSION = "event_alpha_run_counters_v1"
COUNTER_FIELDS = (
    "raw_events",
    "candidate_events",
    "research_candidates",
    "source_alert_snapshots",
    "current_generation_core_rows",
    "current_generation_visible_core_rows",
    "cumulative_store_rows",
    "alertable_decisions",
    "strict_alerts",
    "preview_rendered_items",
)


def canonical_run_counters(result: Any | None) -> dict[str, int]:
    """Project legacy/runtime result shapes into one unambiguous counter set."""

    raw_events = _count(_value(result, "raw_events", 0))
    candidate_events = _explicit_count(result, "candidate_events")
    if candidate_events is None:
        candidate_events = _count(_value(result, "candidates", 0))

    research_candidates = _explicit_count(result, "research_candidates")
    if (
        not _value(result, "counter_schema_version")
        and research_candidates == 0
        and _count(_value(result, "alerts", 0)) == candidate_events
        and _count(_value(result, "strict_alerts", 0)) == 0
    ):
        # Pre-counter-schema ledgers used ``alerts`` for the research candidate
        # list while also persisting zero-valued placeholder fields.
        research_candidates = candidate_events
    if research_candidates is None:
        legacy_candidates = _explicit_count(result, "candidates")
        research_candidates = (
            legacy_candidates
            if legacy_candidates is not None
            else _count(_value(result, "alerts", 0))
        )

    source_alert_snapshots = _explicit_count(result, "source_alert_snapshots")
    if source_alert_snapshots is None:
        source_alert_snapshots = _count(_value(result, "snapshot_rows_written", 0))

    current_core = _explicit_count(result, "current_generation_core_rows")
    if current_core is None:
        current_core = _count(_value(result, "core_opportunity_rows_written", 0))
    visible_core = _explicit_count(result, "current_generation_visible_core_rows")
    if visible_core is None:
        visible_core = current_core
    cumulative = _explicit_count(result, "cumulative_store_rows")
    if cumulative is None:
        cumulative = current_core

    alertable = _explicit_count(result, "alertable_decisions")
    if alertable is None:
        alertable = _count(_value(result, "alertable", 0))
    strict_alerts = _explicit_count(result, "strict_alerts")
    if strict_alerts is None:
        strict_alerts_created = _explicit_count(result, "strict_alerts_created")
        if strict_alerts_created is not None:
            strict_alerts = strict_alerts_created
        else:
            legacy_alerts = _count(_value(result, "alerts", 0))
            strict_alerts = legacy_alerts if legacy_alerts != research_candidates else 0
    preview_rendered = _explicit_count(result, "preview_rendered_items")
    if preview_rendered is None:
        preview_rendered = 0

    return {
        "raw_events": raw_events,
        "candidate_events": candidate_events,
        "research_candidates": research_candidates,
        "source_alert_snapshots": source_alert_snapshots,
        "current_generation_core_rows": current_core,
        "current_generation_visible_core_rows": visible_core,
        "cumulative_store_rows": cumulative,
        "alertable_decisions": alertable,
        "strict_alerts": strict_alerts,
        "preview_rendered_items": preview_rendered,
    }


def canonical_send_state(result: Any | None) -> dict[str, Any]:
    """Return factual no-send/burn-in fields without treating failed sends as rehearsal."""

    requested = _value(result, "send_requested", False) is True
    attempted = _value(result, "send_attempted", False) is True
    delivered = _count(_value(result, "send_items_delivered", 0))
    explicit_burn_mode = str(_value(result, "burn_in_mode", "") or "").strip()
    notification_burn_in = (
        _value(result, "notification_burn_in", False) is True
        or "notification_burn_in" in explicit_burn_mode
        or str(_value(result, "run_mode", "") or "") == "notification_burn_in"
        or str(_value(result, "profile", "") or "").startswith("notify_")
    )
    no_send = not attempted
    block_reason = str(_value(result, "send_block_reason", "") or "").strip()
    guard_status = str(_value(result, "send_guard_status", "") or "").strip()
    if not guard_status:
        guard_status = block_reason or ("delivery_attempted" if attempted else "no_delivery_attempted")
    if notification_burn_in and no_send:
        burn_in_mode = "no_send_notification_burn_in"
    elif notification_burn_in:
        burn_in_mode = "notification_burn_in_delivery_attempted"
    else:
        burn_in_mode = "not_notification_burn_in"
    return {
        "burn_in_mode": burn_in_mode,
        "send_guard_status": guard_status,
        "send_requested": requested,
        "send_attempted": attempted,
        "no_send_rehearsal": no_send,
        "send_items_delivered": delivered,
    }


def deprecated_counter_aliases(counters: Mapping[str, int]) -> dict[str, Any]:
    """Keep JSON compatibility aliases with their scopes declared explicitly."""

    return {
        "candidates": int(counters["candidate_events"]),
        "alerts": int(counters["strict_alerts"]),
        "raw_source_candidates": int(counters["candidate_events"]),
        "deprecated_counter_aliases": {
            "candidates": "candidate_events",
            "alerts": "strict_alerts",
            "raw_source_candidates": "candidate_events",
            "snapshot_rows_written": "source_alert_snapshots",
            "core_opportunity_rows_written": "current_generation_core_rows",
        },
    }


def _value(result: Any | None, key: str, default: Any = None) -> Any:
    if isinstance(result, Mapping):
        return result.get(key, default)
    return getattr(result, key, default) if result is not None else default


def _explicit_count(result: Any | None, key: str) -> int | None:
    if isinstance(result, Mapping):
        if key not in result or result.get(key) is None:
            return None
        return _count(result.get(key))
    if result is None or not hasattr(result, key):
        return None
    value = getattr(result, key)
    return None if value is None else _count(value)


def _count(value: Any) -> int:
    if isinstance(value, (list, tuple, set, frozenset)):
        return len(value)
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


__all__ = (
    "COUNTER_FIELDS",
    "COUNTER_SCHEMA_VERSION",
    "canonical_run_counters",
    "canonical_send_state",
    "deprecated_counter_aliases",
)
