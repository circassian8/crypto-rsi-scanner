"""Closed in-memory contract for exact Bybit derivatives response evidence.

This module rederives every normalized context from exact captured public
response bytes and binds the result to its execution-quality source capture.
It deliberately performs no I/O.  Immutable namespace publication is a later,
separate boundary and cannot accept mapping-only diagnostic responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Mapping, Sequence
from urllib.parse import urlencode

from .bybit_derivatives_context import (
    DEFAULT_FRESHNESS_SECONDS,
    MAX_PLANNED_REQUESTS,
    BybitDerivativesContextError,
    build_bybit_derivatives_requests,
    normalize_bybit_derivatives_context,
)
from .bybit_derivatives_context_live import CONTRACT_VERSION as LIVE_CONTRACT_VERSION
from .bybit_execution_quality import (
    PUBLIC_API_BASE,
    BybitEligibleInstrument,
    BybitPublicRequest,
)
from .bybit_execution_quality_capture import (
    CONTRACT_VERSION as EXECUTION_CAPTURE_CONTRACT_VERSION,
    BybitCapturedJSONResponse,
    BybitExecutionQualityCaptureError,
)
from .bybit_execution_quality_capture_models import TRANSPORT_CONTRACT
from .bybit_intraday_live import BybitIntradayLiveError, _instrument_from_values


CONTRACT_VERSION = "crypto_radar_bybit_derivatives_context_capture_v1"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_EXECUTION_NAMESPACE_RE = re.compile(
    r"^radar_bybit_execution_quality_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_LIVE_SUMMARY_KEYS = frozenset(
    {
        "all_context_fresh", "all_context_fresh_at_acquisition",
        "all_context_fresh_at_completion", "artifact_persisted",
        "campaign_attached", "category", "completed_at", "context_count",
        "context_only", "contexts", "contract_version", "credentials_read",
        "decision_policy_applied", "directional_authority",
        "eligible_instrument_count", "eligible_instruments",
        "exact_response_capture_available", "exact_response_capture_count",
        "execution_mode", "immutable_capture_implemented",
        "maximum_context_age_at_completion_seconds",
        "maximum_context_age_policy_seconds", "no_send",
        "normal_rsi_signal_rows_written", "orders_available",
        "paper_trades_created", "private_data_read", "protocol_v2_annex_bound",
        "protocol_v2_evidence_eligible", "protocol_v2_input_quality_eligible",
        "provider_call_attempted", "provider_call_authorized",
        "provider_request_bound", "provider_request_count",
        "provider_request_succeeded", "quote_asset", "recorded_403_policy",
        "redirects_followed", "request_timing", "research_only", "retries",
        "row_type", "source_execution_quality_capture",
        "source_execution_quality_capture_id", "started_at", "status",
        "telegram_sends", "trades_created", "triggered_fade_created",
        "venue_id", "writes_performed",
    }
)
_PATH_LABELS = (
    "ticker",
    "funding_history",
    "open_interest",
    "account_ratio",
)


class BybitDerivativesContextCaptureError(RuntimeError):
    """Raised when exact derivatives evidence violates the closed contract."""


def _canonical_value(value: object) -> object:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return json.loads(raw)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise BybitDerivativesContextCaptureError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitDerivativesContextCaptureError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitDerivativesContextCaptureError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_url(request: BybitPublicRequest) -> str:
    return f"{PUBLIC_API_BASE}{request.path}?{urlencode(request.query)}"


def _request_values(request: BybitPublicRequest) -> dict[str, object]:
    return {
        "method": request.method,
        "path": request.path,
        "query": [[key, value] for key, value in request.query],
        "credentials_required": request.credentials_required,
        "private_data": request.private_data,
        "research_only": request.research_only,
    }


def _source_projection(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise BybitDerivativesContextCaptureError("source_execution_capture_invalid")
    authority = value.get("source_authority")
    authority_keys = {
        "artifact_namespace", "authority_checked_at", "operator_state_sha256",
        "revision", "run_id",
    }
    if (
        value.get("contract_version") != EXECUTION_CAPTURE_CONTRACT_VERSION
        or value.get("status") != "complete"
        or value.get("evidence_authority_eligible") is not True
        or value.get("protocol_v2_input_quality_eligible") is not True
        or value.get("protocol_v2_evidence_eligible") is not False
        or value.get("protocol_v2_annex_bound") is not False
        or value.get("pointer_validated") is not True
        or value.get("research_only") is not True
        or value.get("no_send") is not True
        or any(
            value.get(field) != 0
            for field in (
                "orders", "trades", "paper_trades", "normal_rsi_writes",
                "event_alpha_triggered_fade",
            )
        )
        or not _SHA256_RE.fullmatch(str(value.get("capture_id") or ""))
        or not _EXECUTION_NAMESPACE_RE.fullmatch(
            str(value.get("artifact_namespace") or "")
        )
        or not _SHA256_RE.fullmatch(str(value.get("pointer_sha256") or ""))
        or not isinstance(authority, Mapping)
        or set(authority) != authority_keys
        or not _SHA256_RE.fullmatch(
            str(authority.get("operator_state_sha256") or "")
        )
        or type(authority.get("revision")) is not int
    ):
        raise BybitDerivativesContextCaptureError("source_execution_capture_invalid")
    completed_at = _iso(_utc(value.get("completed_at"), "source_completed_at"))
    _utc(authority.get("authority_checked_at"), "source_authority_checked_at")
    return {
        "contract_version": EXECUTION_CAPTURE_CONTRACT_VERSION,
        "capture_id": value["capture_id"],
        "artifact_namespace": value["artifact_namespace"],
        "completed_at": completed_at,
        "pointer_sha256": value["pointer_sha256"],
        "source_authority": dict(authority),
        "evidence_authority_eligible": True,
        "protocol_v2_input_quality_eligible": True,
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "research_only": True,
        "no_send": True,
    }


def _validate_summary(summary: Mapping[str, object]) -> tuple[datetime, datetime]:
    if (
        set(summary) != _LIVE_SUMMARY_KEYS
        or summary.get("contract_version") != LIVE_CONTRACT_VERSION
        or summary.get("row_type")
        != "decision_radar_bybit_derivatives_context_observation_set"
        or summary.get("status") != "complete"
        or summary.get("venue_id") != "bybit"
        or summary.get("execution_mode") != "perpetual"
        or summary.get("category") != "linear"
        or summary.get("quote_asset") != "USDT"
        or summary.get("provider_call_authorized") is not True
        or summary.get("provider_call_attempted") is not True
        or summary.get("provider_request_succeeded") is not True
        or summary.get("artifact_persisted") is not False
        or summary.get("immutable_capture_implemented") is not False
        or summary.get("campaign_attached") is not False
        or summary.get("context_only") is not True
        or summary.get("directional_authority") is not False
        or summary.get("decision_policy_applied") is not False
        or summary.get("protocol_v2_annex_bound") is not False
        or summary.get("protocol_v2_input_quality_eligible") is not False
        or summary.get("protocol_v2_evidence_eligible") is not False
        or summary.get("research_only") is not True
        or summary.get("no_send") is not True
        or summary.get("credentials_read") is not False
        or summary.get("private_data_read") is not False
        or summary.get("orders_available") is not False
        or summary.get("writes_performed") is not False
        or summary.get("retries") != 0
        or summary.get("redirects_followed") != 0
        or any(
            summary.get(field) != 0
            for field in (
                "trades_created", "paper_trades_created",
                "normal_rsi_signal_rows_written", "triggered_fade_created",
                "telegram_sends",
            )
        )
    ):
        raise BybitDerivativesContextCaptureError("capture_summary_contract_invalid")
    started = _utc(summary.get("started_at"), "capture_started_at")
    completed = _utc(summary.get("completed_at"), "capture_completed_at")
    if completed < started:
        raise BybitDerivativesContextCaptureError("capture_clock_invalid")
    return started, completed


def _response_row(
    response: BybitCapturedJSONResponse,
    *,
    sequence: int,
    raw_name: str,
) -> dict[str, object]:
    started = _utc(response.request_started_at, "request_started_at")
    received = _utc(response.response_received_at, "response_received_at")
    if (
        received < started
        or isinstance(response.duration_ms, bool)
        or not 0 <= response.duration_ms <= 120_000
        or response.transport_contract != TRANSPORT_CONTRACT
        or response.http_status != 200
        or response.content_type.casefold() not in {"application/json", "text/json"}
        or response.response_url != _request_url(response.request)
        or response.request.method != "GET"
        or response.request.credentials_required
        or response.request.private_data
        or not response.request.research_only
        or not response.raw_bytes
        or len(response.raw_bytes) > MAX_RESPONSE_BYTES
    ):
        raise BybitDerivativesContextCaptureError(
            "captured_response_transport_invalid"
        )
    try:
        response.payload()
    except BybitExecutionQualityCaptureError as exc:
        raise BybitDerivativesContextCaptureError(
            "captured_response_json_invalid"
        ) from exc
    return {
        "sequence": sequence,
        "request": _request_values(response.request),
        "request_url": response.response_url,
        "request_started_at": _iso(started),
        "response_received_at": _iso(received),
        "duration_ms": response.duration_ms,
        "http_status": response.http_status,
        "content_type": response.content_type.casefold(),
        "transport_contract": response.transport_contract,
        "raw_artifact": raw_name,
        "sha256": _sha256(response.raw_bytes),
        "size_bytes": len(response.raw_bytes),
    }


def _validated_sets(
    summary: Mapping[str, object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> tuple[list[object], list[object], list[object], dict[str, object]]:
    instruments = summary.get("eligible_instruments")
    contexts = summary.get("contexts")
    timing = summary.get("request_timing")
    if (
        not isinstance(instruments, list)
        or not instruments
        or not isinstance(contexts, list)
        or not isinstance(timing, list)
    ):
        raise BybitDerivativesContextCaptureError("capture_evidence_sets_invalid")
    expected = len(instruments) * len(_PATH_LABELS)
    if (
        expected > MAX_PLANNED_REQUESTS
        or len(responses) != expected
        or any(
            not isinstance(response, BybitCapturedJSONResponse)
            for response in responses
        )
        or len(contexts) != len(instruments)
        or len(timing) != expected
        or summary.get("eligible_instrument_count") != len(instruments)
        or summary.get("context_count") != len(contexts)
        or summary.get("provider_request_count") != expected
        or summary.get("provider_request_bound") != expected
        or summary.get("exact_response_capture_count") != expected
        or summary.get("exact_response_capture_available") is not True
    ):
        raise BybitDerivativesContextCaptureError("capture_count_contract_invalid")
    source = _source_projection(summary.get("source_execution_quality_capture"))
    if source["capture_id"] != summary.get("source_execution_quality_capture_id"):
        raise BybitDerivativesContextCaptureError(
            "source_execution_capture_identity_mismatch"
        )
    canonical_instruments = _canonical_value(instruments)
    source_value = summary.get("source_execution_quality_capture")
    if (
        not isinstance(source_value, Mapping)
        or _canonical_value(source_value.get("eligible_instruments"))
        != canonical_instruments
    ):
        raise BybitDerivativesContextCaptureError(
            "source_execution_instrument_set_mismatch"
        )
    return (
        list(canonical_instruments),
        list(_canonical_value(contexts)),
        list(_canonical_value(timing)),
        source,
    )


def _rederive(
    *,
    instruments: Sequence[object],
    contexts: Sequence[object],
    timing: Sequence[object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[tuple[str, bytes]]]:
    request_rows: list[dict[str, object]] = []
    rebuilt: list[dict[str, object]] = []
    raw_rows: list[tuple[str, bytes]] = []
    cursor = 0
    for instrument_index, instrument_value in enumerate(instruments, start=1):
        try:
            instrument = _instrument_from_values(instrument_value)
        except BybitIntradayLiveError as exc:
            raise BybitDerivativesContextCaptureError(
                "eligible_instrument_schema_invalid"
            ) from exc
        expected_requests = build_bybit_derivatives_requests((instrument,))
        payloads: dict[str, Mapping[str, object]] = {}
        lineage: dict[str, str] = {}
        acquired: list[datetime] = []
        for label, expected_request in zip(_PATH_LABELS, expected_requests, strict=True):
            response = responses[cursor]
            timing_value = timing[cursor]
            if response.request != expected_request or not isinstance(timing_value, Mapping):
                raise BybitDerivativesContextCaptureError(
                    "derivatives_request_order_drift"
                )
            lineage_id = timing_value.get("request_lineage_id")
            expected_timing = {
                "instrument_id": instrument.instrument_id,
                "source": label,
                "request_lineage_id": lineage_id,
                "request_started_at": response.request_started_at,
                "response_received_at": response.response_received_at,
            }
            if _canonical_value(timing_value) != _canonical_value(expected_timing):
                raise BybitDerivativesContextCaptureError("request_timing_drift")
            if not isinstance(lineage_id, str) or not lineage_id:
                raise BybitDerivativesContextCaptureError("request_lineage_invalid")
            raw_name = (
                f"raw_{cursor + 1:03d}_{label}_{instrument.instrument_id}.json"
            )
            request_rows.append(
                _response_row(response, sequence=cursor + 1, raw_name=raw_name)
            )
            raw_rows.append((raw_name, response.raw_bytes))
            payloads[label] = response.payload()
            lineage[label] = lineage_id
            acquired.append(_utc(response.response_received_at, "response_received_at"))
            cursor += 1
        try:
            context = normalize_bybit_derivatives_context(
                payloads["ticker"],
                payloads["funding_history"],
                payloads["open_interest"],
                payloads["account_ratio"],
                instrument=instrument,
                acquired_at=max(acquired),
                request_lineage_ids=lineage,
            ).to_dict()
        except (BybitDerivativesContextError, ValueError) as exc:
            raise BybitDerivativesContextCaptureError(
                "derivatives_response_contract_invalid"
            ) from exc
        if _canonical_value(context) != contexts[instrument_index - 1]:
            raise BybitDerivativesContextCaptureError(
                "derivatives_context_projection_drift"
            )
        rebuilt.append(context)
    return rebuilt, request_rows, raw_rows


def prepare_bybit_derivatives_context_capture(
    summary: Mapping[str, object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> dict[str, object]:
    """Validate and close exact response bytes without writing an artifact."""

    started, completed = _validate_summary(summary)
    instruments, contexts, timing, source = _validated_sets(summary, responses)
    rebuilt, request_rows, raw_rows = _rederive(
        instruments=instruments,
        contexts=contexts,
        timing=timing,
        responses=responses,
    )
    if _utc(source["completed_at"], "source_completed_at") > started:
        raise BybitDerivativesContextCaptureError(
            "source_execution_capture_after_derivatives_start"
        )
    for row in request_rows:
        if (
            _utc(row["request_started_at"], "request_started_at") < started
            or _utc(row["response_received_at"], "response_received_at") > completed
        ):
            raise BybitDerivativesContextCaptureError(
                "captured_response_outside_capture_window"
            )
    ages = [
        max(0.0, (completed - _utc(row["provider_observed_at"], "provider_observed_at")).total_seconds())
        for row in rebuilt
    ]
    acquisition_fresh = all(row.get("freshness_status") == "fresh" for row in rebuilt)
    completion_fresh = acquisition_fresh and all(
        age <= DEFAULT_FRESHNESS_SECONDS for age in ages
    )
    if (
        summary.get("all_context_fresh_at_acquisition") is not acquisition_fresh
        or summary.get("all_context_fresh_at_completion") is not completion_fresh
        or summary.get("all_context_fresh") is not completion_fresh
        or summary.get("maximum_context_age_policy_seconds")
        != DEFAULT_FRESHNESS_SECONDS
        or summary.get("maximum_context_age_at_completion_seconds")
        != round(max(ages, default=0.0), 6)
    ):
        raise BybitDerivativesContextCaptureError(
            "derivatives_freshness_summary_mismatch"
        )
    identity_seed = {
        "completed_at": _iso(completed),
        "source_execution_quality_capture": source,
        "raw_sha256": [_sha256(raw) for _name, raw in raw_rows],
    }
    capture_id = _sha256(_canonical_bytes(identity_seed))
    timestamp = completed.strftime("%Y%m%dt%H%M%S%fz")
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "prepared",
        "capture_id": capture_id,
        "artifact_namespace": (
            f"radar_bybit_derivatives_{timestamp}_{capture_id[:12]}"
        ),
        "started_at": _iso(started),
        "completed_at": _iso(completed),
        "source_execution_quality_capture": source,
        "eligible_instruments": instruments,
        "contexts": rebuilt,
        "request_index": request_rows,
        "raw_artifacts": [
            {"name": name, "sha256": _sha256(raw), "size_bytes": len(raw)}
            for name, raw in raw_rows
        ],
        "request_count": len(request_rows),
        "context_count": len(rebuilt),
        "all_context_fresh": completion_fresh,
        "immutable_capture_persisted": False,
        "protocol_v2_input_quality_eligible": completion_fresh,
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "campaign_attached": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "provider_call_attempted": False,
        "writes_performed": False,
        "research_only": True,
        "no_send": True,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
    }


__all__ = (
    "CONTRACT_VERSION",
    "BybitDerivativesContextCaptureError",
    "prepare_bybit_derivatives_context_capture",
)
