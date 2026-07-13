"""Safe provider-health state for the bounded CoinGecko no-send pilot."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .market_no_send_io import read_json_object, read_regular_bytes, write_json_atomic
from .market_no_send_models import (
    MarketNoSendError,
    MarketProviderBackoff,
    MarketProviderFetchResult,
    MarketProviderRequestError,
    MarketProviderResponse,
)


PROVIDER_HEALTH_FILENAME = "event_provider_health.json"
PROVIDER_HEALTH_KEY = "market_universe:market_no_send"
PROVIDER_SERVICE = "market_universe"
PROVIDER_ROLE = "market_no_send"
_BACKOFF = timedelta(minutes=30)
_MAX_FAILURES = 3
MarketRowsProvider = Callable[[int], Sequence[Mapping[str, Any]]]
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


def require_approved_live_adapter(*, data_mode: str, injected: bool) -> None:
    """Prevent an arbitrary callable from asserting real CoinGecko lineage."""

    if data_mode == "live" and injected:
        raise MarketNoSendError(
            "an injected provider cannot claim live CoinGecko provenance; "
            "use mock mode for injected rows"
        )


def fetch_approved_live_rows(
    namespace_dir: Path,
    *,
    fetch: MarketRowsProvider,
    fetch_limit: int,
    provider: str,
    run_id: str,
    observed_at: datetime,
    attempted_at: datetime | None = None,
) -> MarketProviderFetchResult:
    health_at = _utc(attempted_at or datetime.now(timezone.utc))
    allowed, reason = provider_health_allowed(
        namespace_dir,
        observed_at=health_at,
    )
    if not allowed:
        raise MarketProviderBackoff(reason or "market provider is in backoff")
    started_at = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()
    try:
        response = fetch(fetch_limit)
        if isinstance(response, MarketProviderResponse):
            rows = response.rows
            supplied_telemetry = response.telemetry
        else:
            rows = response
            supplied_telemetry = {}
    except Exception as exc:
        telemetry = _request_telemetry(
            getattr(exc, "request_telemetry", {}),
            started_at=started_at,
            started_monotonic=started_monotonic,
            result_count=0,
            error_class=getattr(exc, "error_class", None) or type(exc).__name__,
        )
        record_provider_failure(
            namespace_dir,
            provider=provider,
            run_id=run_id,
            observed_at=health_at,
            error=exc,
            request_telemetry=telemetry,
        )
        if isinstance(exc, MarketProviderRequestError):
            raise
        raise MarketProviderRequestError(type(exc).__name__, telemetry) from exc
    materialized = tuple(row for row in rows if isinstance(row, Mapping))
    telemetry = _request_telemetry(
        supplied_telemetry,
        started_at=started_at,
        started_monotonic=started_monotonic,
        result_count=len(materialized),
        error_class=None,
    )
    record_provider_success(
        namespace_dir,
        provider=provider,
        run_id=run_id,
        observed_at=health_at,
        request_telemetry=telemetry,
    )
    return MarketProviderFetchResult(materialized, telemetry)


def provider_health_allowed(
    namespace_dir: Path,
    *,
    observed_at: datetime,
) -> tuple[bool, str | None]:
    payload = _load_health(namespace_dir)
    providers = payload.get("providers")
    providers = providers if isinstance(providers, Mapping) else {}
    row = providers.get(PROVIDER_HEALTH_KEY)
    if not isinstance(row, Mapping):
        return True, None
    disabled_until = _aware_time(row.get("disabled_until"))
    if row.get("disabled_until") not in (None, "") and disabled_until is None:
        return False, "provider health backoff timestamp is invalid"
    if disabled_until is not None and disabled_until > observed_at.astimezone(timezone.utc):
        return False, f"provider is in backoff until {disabled_until.isoformat()}"
    return True, None


def record_provider_success(
    namespace_dir: Path,
    *,
    provider: str,
    run_id: str,
    observed_at: datetime,
    request_telemetry: Mapping[str, Any] | None = None,
) -> Path:
    payload, providers, row = _health_update_context(namespace_dir)
    row.update({
        "provider": provider,
        "provider_key": PROVIDER_HEALTH_KEY,
        "provider_service": PROVIDER_SERVICE,
        "provider_role": PROVIDER_ROLE,
        "provider_kind": "market_data",
        "last_success_at": _utc(observed_at).isoformat(),
        "consecutive_failures": 0,
        "disabled_until": None,
        "last_error_class": None,
        "run_id": run_id,
        "request_http_status": (request_telemetry or {}).get("http_status"),
        "request_result_count": (request_telemetry or {}).get("result_count"),
        "request_retry_count": (request_telemetry or {}).get("retry_count"),
        "no_send": True,
        "research_only": True,
    })
    providers[PROVIDER_HEALTH_KEY] = row
    return _write_health(namespace_dir, payload, providers)


def record_provider_failure(
    namespace_dir: Path,
    *,
    provider: str,
    run_id: str,
    observed_at: datetime,
    error: BaseException,
    request_telemetry: Mapping[str, Any] | None = None,
) -> Path:
    payload, providers, row = _health_update_context(namespace_dir)
    failures = int(row.get("consecutive_failures") or 0) + 1
    error_class, immediate_backoff = _safe_error_class(
        error,
        request_telemetry=request_telemetry,
    )
    disabled_until = (
        _utc(observed_at) + _BACKOFF
        if immediate_backoff or failures >= _MAX_FAILURES
        else None
    )
    row.update({
        "provider": provider,
        "provider_key": PROVIDER_HEALTH_KEY,
        "provider_service": PROVIDER_SERVICE,
        "provider_role": PROVIDER_ROLE,
        "provider_kind": "market_data",
        "last_failure_at": _utc(observed_at).isoformat(),
        "consecutive_failures": failures,
        "disabled_until": disabled_until.isoformat() if disabled_until else None,
        "last_error_class": error_class,
        "run_id": run_id,
        "request_http_status": (request_telemetry or {}).get("http_status"),
        "request_result_count": (request_telemetry or {}).get("result_count"),
        "request_retry_count": (request_telemetry or {}).get("retry_count"),
        "no_send": True,
        "research_only": True,
    })
    providers[PROVIDER_HEALTH_KEY] = row
    return _write_health(namespace_dir, payload, providers)


def _health_update_context(
    namespace_dir: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    payload = _load_health(namespace_dir)
    raw = payload.get("providers")
    providers = {
        str(key): dict(value)
        for key, value in (raw.items() if isinstance(raw, Mapping) else ())
        if isinstance(value, Mapping)
    }
    return payload, providers, dict(providers.get(PROVIDER_HEALTH_KEY) or {})


def _load_health(namespace_dir: Path) -> dict[str, Any]:
    path = namespace_dir / PROVIDER_HEALTH_FILENAME
    if read_regular_bytes(path, missing_ok=True) is None:
        return {"schema_version": "event_provider_health_v1", "providers": {}}
    payload = read_json_object(path)
    if payload.get("schema_version") != "event_provider_health_v1":
        raise MarketNoSendError("market provider health schema is invalid")
    if not isinstance(payload.get("providers"), Mapping):
        raise MarketNoSendError("market provider health rows are invalid")
    return payload


def _write_health(
    namespace_dir: Path,
    payload: Mapping[str, Any],
    providers: Mapping[str, Mapping[str, Any]],
) -> Path:
    path = namespace_dir / PROVIDER_HEALTH_FILENAME
    write_json_atomic(path, {
        **dict(payload),
        "schema_version": "event_provider_health_v1",
        "providers": {key: dict(value) for key, value in sorted(providers.items())},
    })
    return path


def _safe_error_class(
    error: BaseException,
    *,
    request_telemetry: Mapping[str, Any] | None = None,
) -> tuple[str, bool]:
    status = getattr(error, "status", None) or (request_telemetry or {}).get("http_status")
    if status == 429:
        return "rate_limited", True
    if status == 403:
        return "forbidden", True
    declared = getattr(error, "error_class", None)
    name = str(declared or type(error).__name__)
    safe_name = "".join(
        character for character in name[:80]
        if character.isalnum() or character in {"_", "-", "."}
    ) or "provider_error"
    try:
        retries_exhausted = int((request_telemetry or {}).get("retry_count") or 0) > 0
    except (TypeError, ValueError):
        retries_exhausted = False
    return safe_name, (
        retries_exhausted
        or safe_name.casefold() in {"rate_limited", "forbidden"}
    )


def _request_telemetry(
    supplied: Mapping[str, Any] | object,
    *,
    started_at: datetime,
    started_monotonic: float,
    result_count: int,
    error_class: str | None,
) -> dict[str, Any]:
    values = _sanitize_telemetry(supplied)
    ended_at = datetime.now(timezone.utc)
    values.setdefault("endpoint_path", "/coins/markets")
    values.setdefault("request_started_at", started_at.isoformat())
    values.setdefault("request_ended_at", ended_at.isoformat())
    values.setdefault("duration_ms", max(0, int(round((time.monotonic() - started_monotonic) * 1000))))
    values.setdefault("http_status", 200 if error_class is None else None)
    values["result_count"] = max(0, int(result_count))
    values.setdefault("retry_count", 0)
    values["error_class"] = error_class
    values.setdefault("cache_behavior", "network")
    return values


def _sanitize_telemetry(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {key: value.get(key) for key in _TELEMETRY_FIELDS if key in value}


def _aware_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _utc(parsed) if parsed.tzinfo is not None else None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise MarketNoSendError("market provider health clock must be timezone-aware")
    return value.astimezone(timezone.utc)


__all__ = (
    "MarketProviderBackoff",
    "MarketProviderFetchResult",
    "MarketProviderRequestError",
    "MarketProviderResponse",
    "PROVIDER_HEALTH_FILENAME",
    "fetch_approved_live_rows",
    "provider_health_allowed",
    "record_provider_failure",
    "record_provider_success",
    "require_approved_live_adapter",
)
