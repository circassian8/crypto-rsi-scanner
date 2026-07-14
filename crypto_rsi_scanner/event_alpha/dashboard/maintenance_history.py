"""Closed, allowlisted projection of non-authoritative Daily Operations telemetry."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping


SERVICE_FILENAME = "event_radar_daily_operations_service.json"
STATE_FILENAME = "event_radar_daily_operations_state.json"
CYCLE_LEDGER_FILENAME = "event_radar_daily_operations_cycles.jsonl"
DASHBOARD_MAINTENANCE_CYCLE_LIMIT = 128

_SAFE_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_SAFETY_COUNTER_FIELDS = (
    "telegram_sends",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_signal_rows_written",
    "triggered_fade_created",
)

ReadObject = Callable[[Path], tuple[Mapping[str, Any], str | None, str | None]]
ReadJsonl = Callable[
    [Path, int],
    tuple[
        tuple[dict[str, Any], ...],
        str | None,
        str | None,
        dict[str, Any],
    ],
]


def load_maintenance_history(
    *,
    now: datetime,
    read_object: ReadObject,
    read_jsonl: ReadJsonl,
) -> dict[str, Any]:
    """Read and project maintenance artifacts through caller-owned safe readers."""

    service, service_digest, service_error = read_object(Path(SERVICE_FILENAME))
    if service_digest:
        service = _project_service(service)
        if not service and service_error is None:
            service_error = "invalid_contract"
    elif service_error in {None, "unreadable"}:
        service = _default_service()
        service_error = None

    state, state_digest, state_error = read_object(Path(STATE_FILENAME))
    state = _project_state(state)
    if state_digest and not state and state_error is None:
        state_error = "invalid_contract"

    raw_cycles, cycles_digest, cycles_error, cycle_stats = read_jsonl(
        Path(CYCLE_LEDGER_FILENAME),
        DASHBOARD_MAINTENANCE_CYCLE_LIMIT,
    )
    cycles, rejected_cycles = _project_cycles(raw_cycles)
    cycle_stats = _bounded_stats(
        int(cycle_stats["source_row_count"]),
        len(cycles),
        DASHBOARD_MAINTENANCE_CYCLE_LIMIT,
    )
    if rejected_cycles:
        cycles_error = cycles_error or "invalid_contract_rows"

    metadata = {
        SERVICE_FILENAME: _metadata(
            now,
            service_digest,
            service_error,
            source_row_count=1 if service_digest else 0,
            returned_row_count=1 if service_digest and service else 0,
            truncated=False,
            defaulted=service_digest is None and service_error is None,
        ),
        STATE_FILENAME: _metadata(
            now,
            state_digest,
            state_error,
            source_row_count=1 if state_digest else 0,
            returned_row_count=1 if state else 0,
            truncated=False,
        ),
        CYCLE_LEDGER_FILENAME: _metadata(
            now,
            cycles_digest,
            cycles_error,
            rejected_row_count=rejected_cycles,
            **cycle_stats,
        ),
    }
    return {
        "maintenance_service": service,
        "maintenance_state": state,
        "maintenance_cycles": cycles,
        "maintenance_metadata": metadata,
    }


def _project_service(row: Mapping[str, Any]) -> dict[str, Any]:
    interval = row.get("interval_seconds")
    if (
        row.get("contract_version") != 1
        or row.get("row_type") != "decision_radar_daily_operations_service"
        or row.get("prepared") is not True
        or row.get("research_only") is not True
        or row.get("no_send") is not True
        or row.get("operation") not in {"install", "uninstall"}
        or not _required_aware_timestamps(row, ("updated_at",))
        or not _boolean_fields(
            row,
            (
                "operation_ok",
                "operation_changed",
                "enabled",
                "installed",
                "loaded",
                "running",
                "healthy",
            ),
        )
        or not _required_safe_tokens(
            row,
            ("operation", "reason", "scheduler_reason"),
        )
        or not _optional_nonnegative_int(row.get("scheduler_last_exit_code"))
        or not _optional_nonnegative_int(row.get("scheduler_runs"))
        or not _safe_service_label(row.get("scheduler_label"))
        or isinstance(interval, bool)
        or not isinstance(interval, int)
        or not 60 <= interval <= 604_800
        or not _zero_safety_counters(row)
    ):
        return {}
    fields = (
        "contract_version",
        "row_type",
        "updated_at",
        "prepared",
        "operation",
        "operation_ok",
        "operation_changed",
        "enabled",
        "installed",
        "loaded",
        "running",
        "healthy",
        "reason",
        "scheduler_reason",
        "scheduler_last_exit_code",
        "scheduler_runs",
        "scheduler_label",
        "interval_seconds",
        *_SAFETY_COUNTER_FIELDS,
        "no_send",
        "research_only",
    )
    return {field: row.get(field) for field in fields}


def _project_state(row: Mapping[str, Any]) -> dict[str, Any]:
    if (
        row.get("contract_version") != 1
        or row.get("row_type") != "decision_radar_daily_operations_state"
        or row.get("research_only") is not True
        or row.get("no_send") is not True
        or row.get("last_cycle_status")
        not in {"skipped", "blocked", "succeeded", "failed"}
        or not _required_safe_tokens(
            row,
            ("last_cycle_id", "last_cycle_status", "last_cycle_reason"),
        )
        or not _optional_safe_namespace(row.get("last_cycle_namespace"))
        or not _optional_safe_namespace(row.get("last_successful_namespace"))
        or not _required_aware_timestamps(
            row,
            ("updated_at", "last_readiness_check"),
        )
        or not _optional_aware_timestamps(
            row,
            (
                "last_attempted_observation",
                "last_successful_publication",
                "next_eligible_observation_at",
            ),
        )
        or not _boolean_fields(
            row,
            (
                "live_provider_authorized",
                "provider_call_attempted",
                "pointer_published",
                "dashboard_restarted",
                "scheduler_enabled",
                "scheduler_loaded",
                "scheduler_healthy",
            ),
        )
        or not _required_safe_tokens(row, ("scheduler_reason",))
        or not _optional_nonnegative_int(row.get("scheduler_last_exit_code"))
        or not _optional_nonnegative_int(row.get("scheduler_runs"))
        or not _optional_boolean(row.get("pointer_invalidated"))
        or not _zero_safety_counters(row)
    ):
        return {}
    fields = (
        "contract_version",
        "row_type",
        "updated_at",
        "last_cycle_id",
        "last_cycle_status",
        "last_cycle_reason",
        "last_cycle_namespace",
        "last_readiness_check",
        "last_attempted_observation",
        "last_successful_publication",
        "last_successful_namespace",
        "next_eligible_observation_at",
        "live_provider_authorized",
        "provider_call_attempted",
        "pointer_published",
        "dashboard_restarted",
        "pointer_invalidated",
        "scheduler_enabled",
        "scheduler_loaded",
        "scheduler_healthy",
        "scheduler_reason",
        "scheduler_last_exit_code",
        "scheduler_runs",
        *_SAFETY_COUNTER_FIELDS,
        "no_send",
        "research_only",
    )
    projected = {field: row.get(field) for field in fields}
    projected["pointer_invalidated"] = row.get("pointer_invalidated") is True
    return projected


def _project_cycles(
    rows: tuple[dict[str, Any], ...],
) -> tuple[tuple[dict[str, Any], ...], int]:
    projected: list[dict[str, Any]] = []
    rejected = 0
    for row in rows:
        value = _project_cycle(row)
        if value:
            projected.append(value)
        else:
            rejected += 1
    return tuple(projected), rejected


def _project_cycle(row: Mapping[str, Any]) -> dict[str, Any]:
    if (
        row.get("contract_version") != 1
        or row.get("row_type") != "decision_radar_daily_operations_cycle"
        or row.get("research_only") is not True
        or row.get("no_send") is not True
        or row.get("status")
        not in {"attempted", "skipped", "blocked", "succeeded", "failed"}
        or not _required_safe_tokens(row, ("cycle_id", "status", "reason"))
        or not _optional_safe_namespace(row.get("artifact_namespace"), required=True)
        or not _required_aware_timestamps(row, ("recorded_at",))
        or not _boolean_fields(
            row,
            (
                "provider_call_attempted",
                "provider_request_succeeded",
                "pointer_published",
                "dashboard_restarted",
                "pointer_rolled_back",
            ),
        )
        or not _optional_boolean(row.get("pointer_invalidated"))
        or not _zero_safety_counters(row)
    ):
        return {}
    fields = (
        "contract_version",
        "row_type",
        "cycle_id",
        "recorded_at",
        "artifact_namespace",
        "status",
        "reason",
        "provider_call_attempted",
        "provider_request_succeeded",
        "pointer_published",
        "dashboard_restarted",
        "pointer_rolled_back",
        "pointer_invalidated",
        *_SAFETY_COUNTER_FIELDS,
        "no_send",
        "research_only",
    )
    projected = {field: row.get(field) for field in fields}
    projected["pointer_invalidated"] = row.get("pointer_invalidated") is True
    return projected


def _default_service() -> dict[str, Any]:
    return {
        "contract_version": 1,
        "row_type": "decision_radar_daily_operations_service",
        "updated_at": None,
        "prepared": True,
        "operation": None,
        "operation_ok": None,
        "operation_changed": None,
        "enabled": False,
        "installed": False,
        "loaded": False,
        "running": False,
        "healthy": True,
        "reason": "not_installed",
        "scheduler_reason": "service_not_installed",
        "scheduler_last_exit_code": None,
        "scheduler_runs": None,
        "scheduler_label": "com.nasrenkaraf.crypto-radar-daily-operations",
        "interval_seconds": None,
        **{field: 0 for field in _SAFETY_COUNTER_FIELDS},
        "no_send": True,
        "research_only": True,
    }


def _required_safe_tokens(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return all(
        bool(_SAFE_TOKEN_RE.fullmatch(str(row.get(field) or "").strip()))
        for field in fields
    )


def _optional_safe_namespace(value: object, *, required: bool = False) -> bool:
    namespace = str(value or "").strip()
    if not namespace:
        return not required
    return (
        namespace not in {".", ".."}
        and len(namespace) <= 160
        and bool(_SAFE_NAMESPACE_RE.fullmatch(namespace))
    )


def _safe_service_label(value: object) -> bool:
    label = str(value or "").strip()
    return (
        0 < len(label) <= 160
        and all(character.isalnum() or character in "_.-" for character in label)
    )


def _boolean_fields(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return all(isinstance(row.get(field), bool) for field in fields)


def _optional_boolean(value: object) -> bool:
    return value is None or isinstance(value, bool)


def _optional_nonnegative_int(value: object) -> bool:
    return value is None or (
        not isinstance(value, bool) and isinstance(value, int) and value >= 0
    )


def _zero_safety_counters(row: Mapping[str, Any]) -> bool:
    return all(
        not isinstance(row.get(field), bool)
        and isinstance(row.get(field), int)
        and row.get(field) == 0
        for field in _SAFETY_COUNTER_FIELDS
    )


def _required_aware_timestamps(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return all(_aware_timestamp(row.get(field)) is not None for field in fields)


def _optional_aware_timestamps(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    return all(
        row.get(field) in (None, "") or _aware_timestamp(row.get(field)) is not None
        for field in fields
    )


def _aware_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _bounded_stats(source_count: int, returned_count: int, limit: int) -> dict[str, Any]:
    return {
        "source_row_count": source_count,
        "returned_row_count": returned_count,
        "row_limit": limit,
        "truncated": source_count > returned_count,
    }


def _metadata(
    now: datetime,
    digest: str | None,
    error: str | None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "authority": "maintenance_telemetry_non_authoritative",
        "read_at": now.isoformat() if digest else None,
        "sha256": digest,
        "error": error,
        **extra,
    }


__all__ = (
    "CYCLE_LEDGER_FILENAME",
    "DASHBOARD_MAINTENANCE_CYCLE_LIMIT",
    "SERVICE_FILENAME",
    "STATE_FILENAME",
    "load_maintenance_history",
)
