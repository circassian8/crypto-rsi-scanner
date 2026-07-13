"""Shared provider backoff and sanitized failure receipts for the campaign."""

from __future__ import annotations

import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import market_no_send_campaign_guard, market_no_send_provider
from .market_no_send_io import (
    read_json_object,
    read_regular_bytes,
    safe_existing_namespace_dir,
    write_json_atomic,
)
from .market_no_send_models import MarketNoSendError


LATEST_SHARED_FAILURE_FILENAME = "event_market_no_send_latest_provider_failure.json"
_TELEMETRY_FIELDS = (
    "endpoint_path",
    "request_started_at",
    "request_ended_at",
    "duration_ms",
    "http_status",
    "result_count",
    "retry_count",
    "error_class",
    "cache_behavior",
)


def assess_shared_provider_state(
    artifact_base_dir: Path,
    *,
    checked_at: datetime,
) -> dict[str, Any]:
    """Read cross-namespace backoff without creating or mutating artifacts."""

    now = _utc(checked_at)
    state_dir = market_no_send_campaign_guard.campaign_state_dir(artifact_base_dir)
    try:
        info = state_dir.lstat()
    except FileNotFoundError:
        return {"allowed": True, "reason": None, "disabled_until": None}
    except OSError:
        return _blocked("shared provider state is unreadable")
    if not stat.S_ISDIR(info.st_mode):
        return _blocked("shared provider state is not a directory")
    try:
        safe_existing_namespace_dir(state_dir.parent, state_dir.name)
        allowed, reason = market_no_send_provider.provider_health_allowed(
            state_dir,
            observed_at=now,
        )
        failure = _read_shared_failure(state_dir)
    except (MarketNoSendError, OSError):
        return _blocked("shared provider backoff state is invalid")
    disabled_until = _aware_time(failure.get("disabled_until")) if failure else None
    if failure and failure.get("resolved_at") in (None, ""):
        if disabled_until is None and failure.get("disabled_until") not in (None, ""):
            return _blocked("shared provider failure backoff timestamp is invalid")
        if disabled_until is not None and disabled_until > now:
            return _blocked(
                f"provider is in shared backoff until {disabled_until.isoformat()}",
                disabled_until=disabled_until.isoformat(),
            )
    return {
        "allowed": bool(allowed),
        "reason": reason,
        "disabled_until": disabled_until.isoformat() if disabled_until else None,
        "last_failure_at": failure.get("failed_at") if failure else None,
    }


def record_shared_provider_success(
    reservation: market_no_send_campaign_guard.CampaignReservation,
    *,
    provider: str,
    run_id: str,
    attempted_at: datetime,
    request_telemetry: Mapping[str, Any],
) -> None:
    """Resolve the prior failure receipt and reset shared health after success."""

    reservation.assert_active(reservation.artifact_base_dir)
    state_dir = reservation.state_dir
    _resolve_shared_failure(state_dir, run_id=run_id, resolved_at=attempted_at)
    market_no_send_provider.record_provider_success(
        state_dir,
        provider=provider,
        run_id=run_id,
        observed_at=_utc(attempted_at),
        request_telemetry=request_telemetry,
    )
    reservation.assert_active(reservation.artifact_base_dir)


def record_shared_provider_failure(
    reservation: market_no_send_campaign_guard.CampaignReservation,
    *,
    artifact_namespace: str,
    provider: str,
    run_id: str,
    attempted_at: datetime,
    error: BaseException,
    request_telemetry: Mapping[str, Any],
) -> None:
    """Persist cross-namespace health plus one allowlisted latest failure row."""

    try:
        reservation.assert_active(reservation.artifact_base_dir)
    except MarketNoSendError:
        return
    state_dir = reservation.state_dir
    attempted = _utc(attempted_at)
    market_no_send_provider.record_provider_failure(
        state_dir,
        provider=provider,
        run_id=run_id,
        observed_at=attempted,
        error=error,
        request_telemetry=request_telemetry,
    )
    health = read_json_object(state_dir / market_no_send_provider.PROVIDER_HEALTH_FILENAME)
    providers = health.get("providers")
    row = (
        providers.get(market_no_send_provider.PROVIDER_HEALTH_KEY)
        if isinstance(providers, Mapping)
        else None
    )
    if not isinstance(row, Mapping):
        raise MarketNoSendError("shared provider failure health row is missing")
    error_class = str(row.get("last_error_class") or "provider_error")[:80]
    telemetry = _sanitized_telemetry(
        request_telemetry,
        attempted_at=attempted,
        error_class=error_class,
    )
    write_json_atomic(state_dir / LATEST_SHARED_FAILURE_FILENAME, {
        "contract_version": 1,
        "row_type": "decision_radar_shared_provider_failure",
        "artifact_namespace": str(artifact_namespace),
        "provider": str(provider),
        "run_id": str(run_id),
        "failed_at": attempted.isoformat(),
        "disabled_until": row.get("disabled_until"),
        "error_class": error_class,
        "request": telemetry,
        "resolved_at": None,
        "resolution_run_id": None,
        "no_send": True,
        "research_only": True,
    })
    reservation.assert_active(reservation.artifact_base_dir)


def _read_shared_failure(state_dir: Path) -> dict[str, Any]:
    path = state_dir / LATEST_SHARED_FAILURE_FILENAME
    if read_regular_bytes(path, missing_ok=True) is None:
        return {}
    payload = read_json_object(path)
    if (
        payload.get("contract_version") != 1
        or payload.get("row_type") != "decision_radar_shared_provider_failure"
        or _aware_time(payload.get("failed_at")) is None
        or not isinstance(payload.get("request"), Mapping)
        or set(payload.get("request", {})) - set(_TELEMETRY_FIELDS)
    ):
        raise MarketNoSendError("shared provider failure receipt is invalid")
    resolved = payload.get("resolved_at")
    if resolved not in (None, "") and _aware_time(resolved) is None:
        raise MarketNoSendError("shared provider failure resolution clock is invalid")
    return payload


def _resolve_shared_failure(
    state_dir: Path,
    *,
    run_id: str,
    resolved_at: datetime,
) -> None:
    payload = _read_shared_failure(state_dir)
    if not payload:
        return
    payload.update({
        "resolved_at": _utc(resolved_at).isoformat(),
        "resolution_run_id": str(run_id),
    })
    write_json_atomic(state_dir / LATEST_SHARED_FAILURE_FILENAME, payload)


def _sanitized_telemetry(
    value: Mapping[str, Any],
    *,
    attempted_at: datetime,
    error_class: str,
) -> dict[str, Any]:
    started = _aware_time(value.get("request_started_at")) or attempted_at
    ended = _aware_time(value.get("request_ended_at")) or attempted_at
    return {
        "endpoint_path": "/coins/markets",
        "request_started_at": _utc(started).isoformat(),
        "request_ended_at": _utc(ended).isoformat(),
        "duration_ms": _nonnegative_int(value.get("duration_ms")),
        "http_status": _http_status(value.get("http_status")),
        "result_count": _nonnegative_int(value.get("result_count")),
        "retry_count": _nonnegative_int(value.get("retry_count")),
        "error_class": error_class,
        "cache_behavior": (
            value.get("cache_behavior")
            if value.get("cache_behavior") in {"network", "cache_hit", "cache_miss"}
            else "network"
        ),
    }


def _nonnegative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _http_status(value: object) -> int | None:
    try:
        status = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return status if status is not None and 100 <= status <= 599 else None


def _blocked(reason: str, *, disabled_until: str | None = None) -> dict[str, Any]:
    return {
        "allowed": False,
        "reason": reason,
        "disabled_until": disabled_until,
        "last_failure_at": None,
    }


def _aware_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _utc(parsed) if parsed.tzinfo is not None else None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise MarketNoSendError("shared provider state clock must be timezone-aware")
    return value.astimezone(timezone.utc)


__all__ = (
    "LATEST_SHARED_FAILURE_FILENAME",
    "assess_shared_provider_state",
    "record_shared_provider_failure",
    "record_shared_provider_success",
)
