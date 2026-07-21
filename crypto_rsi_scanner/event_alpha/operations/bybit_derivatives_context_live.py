"""Guarded venue-native Bybit derivatives-context collection.

Readiness is no-network/no-write. Collection requires one complete current
execution-quality capture, a separate already-present authorization flag, and
an explicit operator confirmation. The adapter performs four public GETs per
exact instrument without retries and has no credential, private-data, order,
trading, notification, persistence, campaign, or Decision-policy path.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ... import config
from ..dashboard.readiness import resolve_authoritative_dashboard
from .bybit_derivatives_context import (
    ACCOUNT_RATIO_PATH,
    FUNDING_HISTORY_PATH,
    MAX_PLANNED_REQUESTS,
    OPEN_INTEREST_PATH,
    TICKERS_PATH,
    BybitDerivativesContextError,
    build_bybit_derivatives_requests,
    normalize_bybit_derivatives_context,
)
from .bybit_derivatives_context_capture import (
    BybitDerivativesContextCaptureError,
    persist_bybit_derivatives_context_capture,
)
from .bybit_derivatives_context_capture_status import (
    bybit_derivatives_context_capture_status,
)
from .bybit_derivatives_context_set_freshness import (
    MAXIMUM_CONTEXT_AGE_SECONDS,
    SET_FRESHNESS_POLICY,
    _BybitDerivativesContextSetFreshnessError,
    live_summary_freshness_values,
    project_derivatives_context_set_freshness,
)
from .bybit_execution_quality import (
    QUOTE_ASSET,
    BybitEligibleInstrument,
    BybitPublicRequest,
)
from .bybit_execution_quality_capture import (
    BybitCapturedJSONResponse,
    load_latest_bybit_execution_quality_capture,
)
from .bybit_execution_quality_live import (
    BybitExecutionQualityLiveError,
    _fetch_public_json,
    _timeout_seconds_valid,
)
from .bybit_intraday_live import (
    BybitIntradayLiveError,
    _enabled,
    _execution_capture_context,
    _instrument_from_values,
    _payload_and_timing,
)


CONTRACT_VERSION = "crypto_radar_bybit_derivatives_context_live_v3"
LIVE_AUTH_ENV = "RSI_DECISION_RADAR_BYBIT_DERIVATIVES_LIVE"
DEFAULT_TIMEOUT_SECONDS = 10.0
READINESS_COMMAND = "make radar-derivatives-bybit-readiness PYTHON=.venv/bin/python"
COLLECT_COMMAND = (
    "CONFIRM=1 make radar-derivatives-bybit-collect PYTHON=.venv/bin/python"
)
CAPTURE_COMMAND = (
    "CONFIRM=1 make radar-derivatives-bybit-capture PYTHON=.venv/bin/python"
)
STATUS_COMMAND = "make radar-derivatives-bybit-status PYTHON=.venv/bin/python"
READINESS_OUTPUT_JSON = "json"
READINESS_OUTPUT_SUMMARY = "summary"
READINESS_OUTPUT_CHOICES = (READINESS_OUTPUT_JSON, READINESS_OUTPUT_SUMMARY)
READINESS_FULL_JSON_COMMAND = (
    "make -s radar-derivatives-bybit-readiness "
    "RADAR_BYBIT_DERIVATIVES_READINESS_OUTPUT=json PYTHON=.venv/bin/python"
)
AUTHORIZATION_ACTION = (
    f"set_{LIVE_AUTH_ENV}=1_in_local_gitignored_dotenv_then_rerun_readiness"
)
_PATH_LABELS = {
    TICKERS_PATH: "ticker",
    FUNDING_HISTORY_PATH: "funding_history",
    OPEN_INTEREST_PATH: "open_interest",
    ACCOUNT_RATIO_PATH: "account_ratio",
}
_SAFETY = {
    "research_only": True,
    "no_send": True,
    "credentials_read": False,
    "private_data_read": False,
    "orders_available": False,
    "trades_created": 0,
    "paper_trades_created": 0,
    "normal_rsi_signal_rows_written": 0,
    "triggered_fade_created": 0,
    "telegram_sends": 0,
    "writes_performed": False,
}


class _BybitDerivativesContextLiveError(RuntimeError):
    """Closed live-boundary failure without provider payload leakage."""

    def __init__(
        self,
        reason_code: str,
        *,
        provider_status: str | None = None,
        http_status: int | None = None,
        request_count: int = 0,
    ) -> None:
        self.reason_code = _safe_code(reason_code)
        self.provider_status = _safe_code(provider_status) if provider_status else None
        self.http_status = (
            int(http_status)
            if isinstance(http_status, int) and 100 <= http_status <= 599
            else None
        )
        self.request_count = max(0, min(int(request_count), MAX_PLANNED_REQUESTS))
        super().__init__(self.reason_code)


BybitDerivativesContextLiveError = _BybitDerivativesContextLiveError
CaptureLoader = Callable[[str | Path], Mapping[str, object]]
Resolver = Callable[..., Any]
Clock = Callable[[], datetime]
FetchResult = Mapping[str, object] | BybitCapturedJSONResponse
FetchJSON = Callable[[BybitPublicRequest, float], FetchResult]


def _safe_code(value: object) -> str:
    text = str(value or "unknown").strip().casefold()
    cleaned = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in text
    )
    return cleaned[:96] or "unknown"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BybitDerivativesContextLiveError("clock_must_include_timezone")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _execution_prerequisites(
    artifact_base_dir: str | Path,
    *,
    checked_at: datetime,
    capture_loader: CaptureLoader,
    resolver: Resolver,
) -> tuple[dict[str, object] | None, tuple[BybitEligibleInstrument, ...], list[str]]:
    capture, instruments, reasons = _execution_capture_context(
        artifact_base_dir,
        now=checked_at,
        loader=capture_loader,
        resolver=resolver,
    )
    return (
        dict(capture) if isinstance(capture, Mapping) else None,
        tuple(instruments),
        list(reasons),
    )


def build_bybit_derivatives_live_readiness(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
) -> dict[str, object]:
    """Inspect exact prerequisites and authorization without a call or write."""

    checked = _utc(now or datetime.now(timezone.utc))
    env = os.environ if environ is None else environ
    authorized = _enabled(env.get(LIVE_AUTH_ENV))
    capture, instruments, reasons = _execution_prerequisites(
        artifact_base_dir,
        checked_at=checked,
        capture_loader=capture_loader,
        resolver=resolver,
    )
    if not authorized:
        reasons.append("runtime_provider_authorization_absent")
    request_bound = len(instruments) * len(_PATH_LABELS)
    latest_capture = bybit_derivatives_context_capture_status(artifact_base_dir)
    ready = not reasons
    only_auth_missing = reasons == ["runtime_provider_authorization_absent"]
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_derivatives_context_live_readiness",
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "checked_at": _iso(checked),
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "category": "linear",
        "quote_asset": QUOTE_ASSET,
        "context_fields": [
            "ticker_mark_index_basis_current_funding",
            "settled_funding_history",
            "open_interest_1h",
            "long_short_account_ratio_1h",
        ],
        "composite_freshness_policy": "oldest_required_provider_response",
        "derivatives_set_freshness_policy": SET_FRESHNESS_POLICY,
        "maximum_context_age_policy_seconds": MAXIMUM_CONTEXT_AGE_SECONDS,
        "protocol_v2_input_quality_rule": (
            "every_oldest_component_context_clock_must_remain_fresh_at_"
            "full_set_completion"
        ),
        "runtime_authorization_env": LIVE_AUTH_ENV,
        "runtime_provider_authorized": authorized,
        "authorization_mutated": False,
        "source_execution_quality_capture": capture,
        "source_execution_quality_capture_id": (
            capture.get("capture_id") if isinstance(capture, Mapping) else None
        ),
        "eligible_instrument_count": len(instruments),
        "eligible_instruments": [row.to_dict() for row in instruments],
        "maximum_provider_requests_for_current_capture": request_bound,
        "absolute_provider_request_bound": MAX_PLANNED_REQUESTS,
        "provider_call_planned": False,
        "provider_call_attempted": False,
        "artifact_persisted": False,
        "exact_response_capture_contract_implemented": True,
        "immutable_capture_implemented": True,
        "capture_publication_available": True,
        "latest_derivatives_capture_status": latest_capture.get("status"),
        "latest_derivatives_capture": latest_capture,
        "campaign_attached": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_input_quality_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "reasons": list(dict.fromkeys(reasons)),
        "next_safe_command": COLLECT_COMMAND if ready else READINESS_COMMAND,
        "readiness_recheck_command": READINESS_COMMAND,
        "diagnostic_collect_command": COLLECT_COMMAND,
        "immutable_capture_command": CAPTURE_COMMAND,
        "capture_status_command": STATUS_COMMAND,
        "operator_action_required": (
            AUTHORIZATION_ACTION
            if only_auth_missing
            else "resolve_readiness_reasons_then_rerun_readiness"
            if reasons
            else "none"
        ),
        "authorization_action_required": (
            AUTHORIZATION_ACTION if not authorized else "none"
        ),
        "collection_confirmation_required": True,
        "expected_provider_activity": (
            f"collect_exactly_{request_bound}_public_GETs_no_retries"
            if ready
            else "none_readiness_only"
        ),
        "authorization_boundary": (
            f"collection_requires_already_present_{LIVE_AUTH_ENV}=1;"
            "this_command_never_creates_or_mutates_authorization"
        ),
        "rollback_disable_command": f"unset {LIVE_AUTH_ENV}",
        "recorded_403_policy": (
            "fail_closed_no_retry_proxy_VPN_region_bypass_or_alternate_host"
        ),
        **_SAFETY,
    }


def format_bybit_derivatives_readiness_summary(
    payload: Mapping[str, object],
) -> str:
    """Render bounded dependency truth without nested capture/context arrays."""

    status = _readiness_text(payload.get("status"), "status")
    ready = _readiness_bool(payload.get("ready"), "ready")
    reasons = _readiness_text_list(payload.get("reasons"), "reasons", limit=32)
    if status not in {"ready", "blocked"} or ready != (status == "ready"):
        raise BybitDerivativesContextLiveError("readiness_status_mismatch")
    if ready == bool(reasons):
        raise BybitDerivativesContextLiveError("readiness_reasons_mismatch")

    context_fields = _readiness_text_list(
        payload.get("context_fields"), "context_fields", limit=8
    )
    if context_fields != (
        "ticker_mark_index_basis_current_funding",
        "settled_funding_history",
        "open_interest_1h",
        "long_short_account_ratio_1h",
    ):
        raise BybitDerivativesContextLiveError("readiness_context_fields_invalid")
    instrument_count = _readiness_int(
        payload.get("eligible_instrument_count"), "eligible_instrument_count"
    )
    request_bound = _readiness_int(
        payload.get("maximum_provider_requests_for_current_capture"),
        "maximum_provider_requests_for_current_capture",
    )
    absolute_bound = _readiness_int(
        payload.get("absolute_provider_request_bound"),
        "absolute_provider_request_bound",
    )
    if (
        request_bound != instrument_count * len(context_fields)
        or request_bound > absolute_bound
    ):
        raise BybitDerivativesContextLiveError("readiness_request_bound_mismatch")

    safety_bools = {
        key: _readiness_bool(payload.get(key), key)
        for key in (
            "runtime_provider_authorized",
            "provider_call_planned",
            "provider_call_attempted",
            "writes_performed",
            "artifact_persisted",
            "credentials_read",
            "private_data_read",
            "orders_available",
            "context_only",
            "directional_authority",
            "decision_policy_applied",
            "protocol_v2_input_quality_eligible",
            "protocol_v2_evidence_eligible",
        )
    }
    safety_counts = {
        key: _readiness_int(payload.get(key), key)
        for key in (
            "telegram_sends",
            "trades_created",
            "paper_trades_created",
            "normal_rsi_signal_rows_written",
            "triggered_fade_created",
        )
    }
    capture_id = _readiness_optional_text(
        payload.get("source_execution_quality_capture_id"),
        "source_execution_quality_capture_id",
        128,
    )
    lines = (
        "report=decision_radar_bybit_derivatives_readiness",
        f"status={status}",
        f"ready={str(ready).lower()}",
        "checked_at=" + _readiness_text(payload.get("checked_at"), "checked_at"),
        "execution_surface=bybit:usdt_linear_perpetual:USDT",
        f"runtime_provider_authorized={str(safety_bools['runtime_provider_authorized']).lower()}",
        f"source_execution_quality_capture_id={capture_id}",
        f"eligible_instruments={instrument_count}",
        f"context_fields={','.join(context_fields)}",
        f"provider_request_bound={request_bound} (absolute={absolute_bound})",
        "latest_derivatives_capture_status="
        + _readiness_text(
            payload.get("latest_derivatives_capture_status"),
            "latest_derivatives_capture_status",
        ),
        "freshness_policy="
        + _readiness_text(
            payload.get("derivatives_set_freshness_policy"),
            "derivatives_set_freshness_policy",
        ),
        f"reasons={','.join(reasons) if reasons else 'none'}",
        "expected_provider_activity="
        + _readiness_text(
            payload.get("expected_provider_activity"), "expected_provider_activity"
        ),
        "operator_action_required="
        + _readiness_text(
            payload.get("operator_action_required"),
            "operator_action_required",
            512,
        ),
        "next_safe_command="
        + _readiness_text(payload.get("next_safe_command"), "next_safe_command", 512),
        "authorization_boundary="
        + _readiness_text(
            payload.get("authorization_boundary"), "authorization_boundary", 512
        ),
        "rollback_disable_command="
        + _readiness_text(
            payload.get("rollback_disable_command"),
            "rollback_disable_command",
            256,
        ),
        "recorded_403_policy="
        + _readiness_text(payload.get("recorded_403_policy"), "recorded_403_policy"),
        "safety_flags="
        + ",".join(
            f"{key}:{str(value).lower()}" for key, value in safety_bools.items()
            if key != "runtime_provider_authorized"
        ),
        "safety_counts="
        + ",".join(f"{key}:{value}" for key, value in safety_counts.items()),
        f"full_json_command={READINESS_FULL_JSON_COMMAND}",
    )
    return "\n".join(lines)


def _readiness_text(value: object, label: str, limit: int = 256) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text or len(text) > limit or any(ord(character) < 32 for character in text):
        raise BybitDerivativesContextLiveError(f"{label}_invalid")
    return text


def _readiness_optional_text(value: object, label: str, limit: int) -> str:
    return "unavailable" if value is None else _readiness_text(value, label, limit)


def _readiness_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise BybitDerivativesContextLiveError(f"{label}_invalid")
    return value


def _readiness_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise BybitDerivativesContextLiveError(f"{label}_invalid")
    return value


def _readiness_text_list(
    value: object,
    label: str,
    *,
    limit: int,
) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > limit:
        raise BybitDerivativesContextLiveError(f"{label}_invalid")
    return tuple(_readiness_text(item, label, 128) for item in value)


def _revalidate_prerequisites(
    artifact_base_dir: str | Path,
    *,
    expected_capture_id: object,
    expected_instruments: Sequence[BybitEligibleInstrument],
    checked_at: datetime,
    capture_loader: CaptureLoader,
    resolver: Resolver,
) -> None:
    capture, instruments, reasons = _execution_prerequisites(
        artifact_base_dir,
        checked_at=checked_at,
        capture_loader=capture_loader,
        resolver=resolver,
    )
    if (
        reasons
        or capture is None
        or capture.get("capture_id") != expected_capture_id
        or instruments != tuple(expected_instruments)
    ):
        raise BybitDerivativesContextLiveError(
            "derivatives_source_prerequisite_drifted"
        )


def _collect_instrument(
    instrument: BybitEligibleInstrument,
    *,
    instrument_index: int,
    lineage_seed: str,
    fetch: FetchJSON,
    clock: Clock,
    timeout_seconds: float,
) -> tuple[dict[str, object], list[BybitCapturedJSONResponse], list[dict[str, object]]]:
    payloads: dict[str, Mapping[str, object]] = {}
    lineage: dict[str, str] = {}
    captured: list[BybitCapturedJSONResponse] = []
    timing: list[dict[str, object]] = []
    acquired_values: list[datetime] = []
    for request_index, request in enumerate(
        build_bybit_derivatives_requests((instrument,)), start=1
    ):
        label = _PATH_LABELS[request.path]
        fallback_started = _utc(clock())
        try:
            result = fetch(request, timeout_seconds)
        except BybitExecutionQualityLiveError as exc:
            raise BybitDerivativesContextLiveError(
                exc.reason_code,
                provider_status=exc.provider_status,
                http_status=exc.http_status,
                request_count=request_index,
            ) from exc
        except BybitDerivativesContextLiveError:
            raise
        except Exception as exc:
            raise BybitDerivativesContextLiveError(
                getattr(exc, "reason_code", "provider_request_failed"),
                request_count=request_index,
            ) from exc
        fallback_acquired = _utc(clock())
        if isinstance(result, BybitCapturedJSONResponse):
            if result.request != request:
                raise BybitDerivativesContextLiveError(
                    "provider_response_request_mismatch",
                    request_count=request_index,
                )
            captured.append(result)
        try:
            payload, request_started, acquired = _payload_and_timing(
                result,
                fallback_started=fallback_started,
                fallback_acquired=fallback_acquired,
            )
        except BybitIntradayLiveError as exc:
            raise BybitDerivativesContextLiveError(
                exc.reason_code,
                request_count=request_index,
            ) from exc
        lineage_id = (
            f"bybit.derivatives.{lineage_seed}.{instrument_index}.{request_index}"
        )
        payloads[label] = payload
        lineage[label] = lineage_id
        acquired_values.append(acquired)
        timing.append({
            "instrument_id": instrument.instrument_id,
            "source": label,
            "request_lineage_id": lineage_id,
            "request_started_at": _iso(request_started),
            "response_received_at": _iso(acquired),
        })
    snapshot = normalize_bybit_derivatives_context(
        payloads["ticker"],
        payloads["funding_history"],
        payloads["open_interest"],
        payloads["account_ratio"],
        instrument=instrument,
        acquired_at=max(acquired_values),
        request_lineage_ids=lineage,
    )
    return snapshot.to_dict(), captured, timing


def _observation_set_summary(
    *,
    started: datetime,
    completed: datetime,
    readiness: Mapping[str, object],
    capture_id: object,
    instruments: Sequence[BybitEligibleInstrument],
    contexts: list[dict[str, object]],
    request_timing: list[dict[str, object]],
    request_count: int,
    captured_responses: Sequence[BybitCapturedJSONResponse],
) -> dict[str, object]:
    try:
        set_freshness = project_derivatives_context_set_freshness(
            contexts,
            completed_at=completed,
        )
    except _BybitDerivativesContextSetFreshnessError as exc:
        raise BybitDerivativesContextLiveError(exc.reason_code) from exc
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_derivatives_context_observation_set",
        "status": "complete",
        "started_at": _iso(started),
        "completed_at": _iso(completed),
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "category": "linear",
        "quote_asset": QUOTE_ASSET,
        "source_execution_quality_capture_id": capture_id,
        "source_execution_quality_capture": readiness[
            "source_execution_quality_capture"
        ],
        "eligible_instrument_count": len(instruments),
        "eligible_instruments": [row.to_dict() for row in instruments],
        "context_count": len(contexts),
        "contexts": contexts,
        "composite_freshness_policy": "oldest_required_provider_response",
        "request_timing": request_timing,
        **live_summary_freshness_values(set_freshness),
        "provider_call_authorized": True,
        "provider_call_attempted": request_count > 0,
        "provider_request_succeeded": True,
        "provider_request_count": request_count,
        "provider_request_bound": len(instruments) * len(_PATH_LABELS),
        "retries": 0,
        "redirects_followed": 0,
        "exact_response_capture_count": len(captured_responses),
        "exact_response_capture_available": (
            len(captured_responses) == request_count
        ),
        "artifact_persisted": False,
        "immutable_capture_implemented": False,
        "campaign_attached": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_input_quality_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "recorded_403_policy": (
            "fail_closed_no_retry_proxy_VPN_region_bypass_or_alternate_host"
        ),
        **_SAFETY,
    }


def _collect_authoritative_bybit_derivatives(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict[str, object], tuple[BybitCapturedJSONResponse, ...]]:
    clock = now or (lambda: datetime.now(timezone.utc))
    started = _utc(clock())
    if not _timeout_seconds_valid(timeout_seconds):
        raise BybitDerivativesContextLiveError("timeout_seconds_out_of_bounds")
    readiness = build_bybit_derivatives_live_readiness(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=started,
        capture_loader=capture_loader,
        resolver=resolver,
    )
    reasons = readiness["reasons"]
    if isinstance(reasons, list) and reasons:
        raise BybitDerivativesContextLiveError(str(reasons[0]))
    try:
        instruments = tuple(
            _instrument_from_values(row) for row in readiness["eligible_instruments"]
        )
    except BybitIntradayLiveError as exc:
        raise BybitDerivativesContextLiveError(exc.reason_code) from exc
    capture_id = readiness["source_execution_quality_capture_id"]
    fetch = fetch_json or _fetch_public_json
    contexts: list[dict[str, object]] = []
    captured_responses: list[BybitCapturedJSONResponse] = []
    request_timing: list[dict[str, object]] = []
    request_count = 0
    lineage_seed = hashlib.sha256(
        f"{capture_id}|{_iso(started)}".encode("utf-8")
    ).hexdigest()[:24]
    try:
        for instrument_index, instrument in enumerate(instruments, start=1):
            context, captured, timing = _collect_instrument(
                instrument,
                instrument_index=instrument_index,
                lineage_seed=lineage_seed,
                fetch=fetch,
                clock=clock,
                timeout_seconds=timeout_seconds,
            )
            request_count += len(_PATH_LABELS)
            contexts.append(context)
            captured_responses.extend(captured)
            request_timing.extend(timing)
    except BybitDerivativesContextLiveError as exc:
        attempted = request_count + max(1, exc.request_count)
        raise BybitDerivativesContextLiveError(
            exc.reason_code,
            provider_status=exc.provider_status,
            http_status=exc.http_status,
            request_count=attempted,
        ) from exc
    except BybitExecutionQualityLiveError as exc:
        raise BybitDerivativesContextLiveError(
            exc.reason_code,
            provider_status=exc.provider_status,
            http_status=exc.http_status,
            request_count=request_count + 1,
        ) from exc
    except BybitDerivativesContextError as exc:
        raise BybitDerivativesContextLiveError(
            str(exc), request_count=request_count + len(_PATH_LABELS)
        ) from exc
    except Exception as exc:
        raise BybitDerivativesContextLiveError(
            getattr(exc, "reason_code", "provider_request_failed"),
            request_count=request_count + 1,
        ) from exc
    completed = _utc(clock())
    _revalidate_prerequisites(
        artifact_base_dir,
        expected_capture_id=capture_id,
        expected_instruments=instruments,
        checked_at=completed,
        capture_loader=capture_loader,
        resolver=resolver,
    )
    expected = len(instruments) * len(_PATH_LABELS)
    if request_count != expected or len(contexts) != len(instruments):
        raise BybitDerivativesContextLiveError(
            "derivatives_collection_count_mismatch",
            request_count=request_count,
        )
    summary = _observation_set_summary(
        started=started,
        completed=completed,
        readiness=readiness,
        capture_id=capture_id,
        instruments=instruments,
        contexts=contexts,
        request_timing=request_timing,
        request_count=request_count,
        captured_responses=captured_responses,
    )
    return summary, tuple(captured_responses)


def collect_authoritative_bybit_derivatives(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Collect exact venue-native context without persistence or policy use."""

    summary, _responses = _collect_authoritative_bybit_derivatives(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=now,
        capture_loader=capture_loader,
        resolver=resolver,
        fetch_json=fetch_json,
        timeout_seconds=timeout_seconds,
    )
    return summary


def capture_authoritative_bybit_derivatives(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Collect once and seal exact derivatives bytes as immutable evidence."""

    summary, responses = _collect_authoritative_bybit_derivatives(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=now,
        capture_loader=capture_loader,
        resolver=resolver,
        fetch_json=fetch_json,
        timeout_seconds=timeout_seconds,
    )
    request_count = int(summary["provider_request_count"])
    if len(responses) != request_count:
        raise BybitDerivativesContextLiveError(
            "exact_provider_response_capture_unavailable",
            request_count=request_count,
        )
    try:
        return persist_bybit_derivatives_context_capture(
            artifact_base_dir,
            summary=summary,
            responses=responses,
        )
    except BybitDerivativesContextCaptureError as exc:
        raise BybitDerivativesContextLiveError(
            f"capture_{exc}",
            request_count=request_count,
        ) from exc


def _failure_payload(exc: BybitDerivativesContextLiveError) -> dict[str, object]:
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_derivatives_context_live_failure",
        "status": "blocked",
        "reason": exc.reason_code,
        "provider_status": exc.provider_status,
        "http_status": exc.http_status,
        "provider_request_count": exc.request_count,
        "provider_request_succeeded": False,
        "artifact_persisted": False,
        "campaign_attached": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_input_quality_eligible": False,
        "protocol_v2_evidence_eligible": False,
        **_SAFETY,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("readiness", "collect", "capture", "status"):
        command = commands.add_parser(name)
        command.add_argument(
            "--artifact-base",
            type=Path,
            default=Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR),
        )
    for name in ("collect", "capture"):
        commands.choices[name].add_argument(
            "--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS
        )
        commands.choices[name].add_argument("--confirm", action="store_true")
    commands.choices["readiness"].add_argument(
        "--output",
        choices=READINESS_OUTPUT_CHOICES,
        default=READINESS_OUTPUT_JSON,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "readiness":
        payload = build_bybit_derivatives_live_readiness(
            artifact_base_dir=args.artifact_base
        )
        if args.output == READINESS_OUTPUT_SUMMARY:
            print(format_bybit_derivatives_readiness_summary(payload))
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command == "status":
        payload = bybit_derivatives_context_capture_status(args.artifact_base)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if not args.confirm:
        payload = _failure_payload(
            BybitDerivativesContextLiveError(
                "explicit_collection_confirmation_required"
            )
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    try:
        operation = (
            capture_authoritative_bybit_derivatives
            if args.command == "capture"
            else collect_authoritative_bybit_derivatives
        )
        payload = operation(
            artifact_base_dir=args.artifact_base,
            timeout_seconds=args.timeout_seconds,
        )
    except BybitDerivativesContextLiveError as exc:
        print(json.dumps(_failure_payload(exc), indent=2, sort_keys=True))
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


__all__ = (
    "AUTHORIZATION_ACTION",
    "CAPTURE_COMMAND",
    "COLLECT_COMMAND",
    "CONTRACT_VERSION",
    "LIVE_AUTH_ENV",
    "MAX_PLANNED_REQUESTS",
    "READINESS_COMMAND",
    "READINESS_FULL_JSON_COMMAND",
    "STATUS_COMMAND",
    "BybitDerivativesContextLiveError",
    "_collect_authoritative_bybit_derivatives",
    "build_bybit_derivatives_live_readiness",
    "format_bybit_derivatives_readiness_summary",
    "capture_authoritative_bybit_derivatives",
    "collect_authoritative_bybit_derivatives",
    "main",
)


if __name__ == "__main__":
    raise SystemExit(main())
