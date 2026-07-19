"""Closed in-memory contract for exact Bybit derivatives response evidence.

This module rederives every normalized context from exact captured public
response bytes and binds the result to its execution-quality source capture.
It deliberately performs no I/O.  Immutable namespace publication is a later,
separate boundary and cannot accept mapping-only diagnostic responses.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import urlencode

from .bybit_derivatives_context import (
    DEFAULT_FRESHNESS_SECONDS,
    MAX_PLANNED_REQUESTS,
    BybitDerivativesContextError,
    build_bybit_derivatives_requests,
    normalize_bybit_derivatives_context,
)
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
from .market_no_send_io import (
    _open_verified_namespace_dir,
    ensure_safe_namespace_dir,
    parse_json_object_bytes,
    read_regular_bytes,
    write_bytes_immutable,
    write_json_atomic,
    write_json_immutable,
)
from .market_no_send_models import MarketNoSendError


CONTRACT_VERSION = "crypto_radar_bybit_derivatives_context_capture_v2"
LIVE_CONTRACT_VERSION = "crypto_radar_bybit_derivatives_context_live_v2"
POINTER_FILENAME = "radar_bybit_derivatives_context_latest.json"
MANIFEST_FILENAME = "capture_manifest.json"
RECEIPT_FILENAME = "capture_completion_receipt.json"
SUMMARY_FILENAME = "capture_input_summary.json"
PROJECTION_FILENAME = "capture_projection.json"
SOURCE_FILENAME = "source_execution_quality_capture.json"
INSTRUMENTS_FILENAME = "eligible_instruments.json"
CONTEXTS_FILENAME = "derivatives_contexts.json"
REQUEST_INDEX_FILENAME = "request_index.json"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_LOCK_FILENAME = ".radar_bybit_derivatives_context.lock"
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_EXECUTION_NAMESPACE_RE = re.compile(
    r"^radar_bybit_execution_quality_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_NAMESPACE_RE = re.compile(
    r"^radar_bybit_derivatives_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_SAFE_RAW_RE = re.compile(
    r"^raw_[0-9]{3}_(?:ticker|funding_history|open_interest|account_ratio)_"
    r"[A-Z0-9]{4,32}\.json$"
)
_LIVE_SUMMARY_KEYS = frozenset(
    {
        "all_context_fresh", "all_context_fresh_at_acquisition",
        "all_context_fresh_at_completion", "artifact_persisted",
        "campaign_attached", "category", "completed_at",
        "composite_freshness_policy", "context_count", "context_only",
        "contexts", "contract_version", "credentials_read",
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
        or summary.get("composite_freshness_policy")
        != "oldest_required_provider_response"
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


def _request_from_values(value: object) -> BybitPublicRequest:
    expected = {
        "credentials_required", "method", "path", "private_data", "query",
        "research_only",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise BybitDerivativesContextCaptureError(
            "captured_request_schema_invalid"
        )
    query = value.get("query")
    if not isinstance(query, list) or not query:
        raise BybitDerivativesContextCaptureError(
            "captured_request_query_invalid"
        )
    pairs: list[tuple[str, str]] = []
    for pair in query:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(item, str) and item for item in pair)
        ):
            raise BybitDerivativesContextCaptureError(
                "captured_request_query_invalid"
            )
        pairs.append((pair[0], pair[1]))
    return BybitPublicRequest(
        method=str(value.get("method") or ""),
        path=str(value.get("path") or ""),
        query=tuple(pairs),
        credentials_required=value.get("credentials_required") is True,
        private_data=value.get("private_data") is True,
        research_only=value.get("research_only") is True,
    )


def _pretty_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _fingerprint(raw: bytes) -> dict[str, object]:
    return {"sha256": _sha256(raw), "size_bytes": len(raw)}


def _raw_rows(
    prepared: Mapping[str, object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> list[tuple[str, bytes]]:
    request_index = prepared.get("request_index")
    if not isinstance(request_index, list) or len(request_index) != len(responses):
        raise BybitDerivativesContextCaptureError("capture_request_index_invalid")
    rows: list[tuple[str, bytes]] = []
    for request_row, response in zip(request_index, responses, strict=True):
        if not isinstance(request_row, Mapping):
            raise BybitDerivativesContextCaptureError(
                "capture_request_index_invalid"
            )
        name = str(request_row.get("raw_artifact") or "")
        if not _SAFE_RAW_RE.fullmatch(name):
            raise BybitDerivativesContextCaptureError(
                "capture_artifact_name_invalid"
            )
        rows.append((name, response.raw_bytes))
    return rows


def _capture_payloads(
    *,
    summary: Mapping[str, object],
    prepared: Mapping[str, object],
    raw_rows: Sequence[tuple[str, bytes]],
) -> list[tuple[str, str, bytes]]:
    capture_id = str(prepared["capture_id"])
    source = {
        "schema_id": "decision_radar.bybit_derivatives_source_execution_capture",
        "schema_version": 1,
        "capture_id": capture_id,
        "source_execution_quality_capture": prepared[
            "source_execution_quality_capture"
        ],
        "research_only": True,
    }
    instruments = {
        "schema_id": "decision_radar.bybit_derivatives_instruments",
        "schema_version": 1,
        "capture_id": capture_id,
        "instrument_count": len(prepared["eligible_instruments"]),
        "instruments": prepared["eligible_instruments"],
        "research_only": True,
    }
    contexts = {
        "schema_id": "decision_radar.bybit_derivatives_contexts",
        "schema_version": 1,
        "capture_id": capture_id,
        "context_count": len(prepared["contexts"]),
        "contexts": prepared["contexts"],
        "all_context_fresh": prepared["all_context_fresh"],
        "research_only": True,
    }
    request_index = {
        "schema_id": "decision_radar.bybit_derivatives_request_index",
        "schema_version": 1,
        "capture_id": capture_id,
        "request_count": len(prepared["request_index"]),
        "requests": prepared["request_index"],
        "retries": 0,
        "redirects_followed": 0,
        "credentials_read": False,
        "private_data_read": False,
        "research_only": True,
    }
    projection = dict(_canonical_value(prepared))
    return [
        (SOURCE_FILENAME, "source_execution_quality_capture", _pretty_bytes(source)),
        (INSTRUMENTS_FILENAME, "eligible_instruments", _pretty_bytes(instruments)),
        (CONTEXTS_FILENAME, "derivatives_contexts", _pretty_bytes(contexts)),
        (REQUEST_INDEX_FILENAME, "request_index", _pretty_bytes(request_index)),
        (SUMMARY_FILENAME, "capture_input_summary", _pretty_bytes(summary)),
        (PROJECTION_FILENAME, "capture_projection", _pretty_bytes(projection)),
        *[
            (name, "accepted_raw_provider_response", raw)
            for name, raw in raw_rows
        ],
    ]


def _publication_objects(
    prepared: Mapping[str, object],
    descriptors: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    source = prepared["source_execution_quality_capture"]
    common = {
        "contract_version": CONTRACT_VERSION,
        "capture_id": prepared["capture_id"],
        "artifact_namespace": prepared["artifact_namespace"],
        "completed_at": prepared["completed_at"],
        "source_execution_quality_capture_id": source["capture_id"],
        "source_execution_quality_pointer_sha256": source["pointer_sha256"],
        "request_count": prepared["request_count"],
        "context_count": prepared["context_count"],
        "all_context_fresh": prepared["all_context_fresh"],
        "protocol_v2_input_quality_eligible": prepared[
            "protocol_v2_input_quality_eligible"
        ],
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "campaign_attached": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "research_only": True,
    }
    manifest = {
        "schema_id": "decision_radar.bybit_derivatives_capture_manifest",
        "schema_version": 1,
        **common,
        "started_at": prepared["started_at"],
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "category": "linear",
        "quote_asset": "USDT",
        "artifacts": list(descriptors),
        "no_send": True,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
    }
    manifest_raw = _pretty_bytes(manifest)
    receipt = {
        "schema_id": "decision_radar.bybit_derivatives_completion_receipt",
        "schema_version": 1,
        "status": "complete",
        **common,
        "manifest": {"name": MANIFEST_FILENAME, **_fingerprint(manifest_raw)},
    }
    receipt_raw = _pretty_bytes(receipt)
    pointer = {
        "schema_id": "decision_radar.bybit_derivatives_latest_pointer",
        "schema_version": 1,
        "status": "complete",
        **common,
        "receipt": {"name": RECEIPT_FILENAME, **_fingerprint(receipt_raw)},
    }
    return manifest, receipt, pointer


@contextmanager
def _publication_lock(base: Path) -> Iterator[None]:
    descriptor: int | None = None
    locked = False
    try:
        with _open_verified_namespace_dir(base) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            flags = (
                os.O_RDWR
                | os.O_CREAT
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0)
            )
            descriptor = os.open(_LOCK_FILENAME, flags, 0o600, dir_fd=namespace_fd)
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                raise BybitDerivativesContextCaptureError("capture_lock_invalid")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            yield
    except BybitDerivativesContextCaptureError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise BybitDerivativesContextCaptureError("capture_lock_unavailable") from exc
    finally:
        if locked and descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        if descriptor is not None:
            os.close(descriptor)


def persist_bybit_derivatives_context_capture(
    artifact_base_dir: str | Path,
    *,
    summary: Mapping[str, object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> dict[str, object]:
    """Seal one exact derivatives response set and publish its latest pointer."""

    base = Path(artifact_base_dir).expanduser().absolute()
    if not base.is_dir():
        raise BybitDerivativesContextCaptureError("artifact_base_unavailable")
    prepared = prepare_bybit_derivatives_context_capture(summary, responses)
    raw_rows = _raw_rows(prepared, responses)
    payloads = _capture_payloads(
        summary=summary,
        prepared=prepared,
        raw_rows=raw_rows,
    )
    descriptors = [
        {"name": name, "role": role, **_fingerprint(raw)}
        for name, role, raw in payloads
    ]
    manifest, receipt, pointer = _publication_objects(prepared, descriptors)
    namespace = str(prepared["artifact_namespace"])
    with _publication_lock(base):
        existing_raw = read_regular_bytes(base / POINTER_FILENAME, missing_ok=True)
        if existing_raw is not None:
            existing = validate_bybit_derivatives_context_pointer_bytes(existing_raw)
            prior = validate_bybit_derivatives_context_capture(
                base,
                namespace=str(existing["artifact_namespace"]),
                pointer=existing,
            )
            if _utc(prior["completed_at"], "prior_completed_at") > _utc(
                prepared["completed_at"], "capture_completed_at"
            ):
                raise BybitDerivativesContextCaptureError(
                    "capture_pointer_rollback_rejected"
                )
        namespace_dir = base / namespace
        try:
            ensure_safe_namespace_dir(namespace_dir)
            for name, _role, raw in payloads:
                write_bytes_immutable(namespace_dir / name, raw)
            write_json_immutable(namespace_dir / MANIFEST_FILENAME, manifest)
            write_json_immutable(namespace_dir / RECEIPT_FILENAME, receipt)
        except MarketNoSendError as exc:
            raise BybitDerivativesContextCaptureError(
                "capture_immutable_write_failed"
            ) from exc
        validate_bybit_derivatives_context_capture(base, namespace=namespace)
        try:
            write_json_atomic(base / POINTER_FILENAME, pointer)
        except MarketNoSendError as exc:
            raise BybitDerivativesContextCaptureError(
                "capture_pointer_write_failed"
            ) from exc
        from .bybit_derivatives_context_capture_status import (
            load_latest_bybit_derivatives_context_capture,
        )

        return load_latest_bybit_derivatives_context_capture(base)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    fields = (
        "st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns",
        "st_ctime_ns",
    )
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _read_regular_bytes_at(directory_fd: int, name: str) -> bytes:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise BybitDerivativesContextCaptureError("capture_artifact_name_invalid")
    descriptor: int | None = None
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise BybitDerivativesContextCaptureError("capture_artifact_unreadable")
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=directory_fd,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_file(before, opened):
            raise BybitDerivativesContextCaptureError("capture_artifact_unreadable")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            raw = handle.read(MAX_RESPONSE_BYTES + 1)
            completed = os.fstat(handle.fileno())
        after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            len(raw) > MAX_RESPONSE_BYTES
            or not _same_file(opened, completed)
            or not _same_file(completed, after)
            or len(raw) != completed.st_size
        ):
            raise BybitDerivativesContextCaptureError("capture_artifact_unreadable")
        return raw
    except BybitDerivativesContextCaptureError:
        raise
    except OSError as exc:
        raise BybitDerivativesContextCaptureError(
            "capture_artifact_unreadable"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _parse_json(raw: bytes) -> dict[str, Any]:
    try:
        return parse_json_object_bytes(raw)
    except MarketNoSendError as exc:
        raise BybitDerivativesContextCaptureError(
            "capture_artifact_invalid_json"
        ) from exc


def validate_bybit_derivatives_context_pointer_bytes(
    raw: bytes,
) -> dict[str, Any]:
    pointer = _parse_json(raw)
    expected = {
        "all_context_fresh", "artifact_namespace", "campaign_attached",
        "capture_id", "completed_at", "context_count", "context_only",
        "contract_version", "decision_policy_applied", "directional_authority",
        "protocol_v2_annex_bound", "protocol_v2_evidence_eligible",
        "protocol_v2_input_quality_eligible", "receipt", "request_count",
        "research_only", "schema_id", "schema_version",
        "source_execution_quality_capture_id",
        "source_execution_quality_pointer_sha256", "status",
    }
    receipt = pointer.get("receipt")
    if (
        set(pointer) != expected
        or pointer.get("schema_id")
        != "decision_radar.bybit_derivatives_latest_pointer"
        or pointer.get("schema_version") != 1
        or pointer.get("contract_version") != CONTRACT_VERSION
        or pointer.get("status") != "complete"
        or not _NAMESPACE_RE.fullmatch(str(pointer.get("artifact_namespace") or ""))
        or not _SHA256_RE.fullmatch(str(pointer.get("capture_id") or ""))
        or not _SHA256_RE.fullmatch(
            str(pointer.get("source_execution_quality_capture_id") or "")
        )
        or not _SHA256_RE.fullmatch(
            str(pointer.get("source_execution_quality_pointer_sha256") or "")
        )
        or type(pointer.get("request_count")) is not int
        or not 1 <= pointer["request_count"] <= MAX_PLANNED_REQUESTS
        or type(pointer.get("context_count")) is not int
        or not 1 <= pointer["context_count"] <= 30
        or pointer["request_count"] != pointer["context_count"] * len(_PATH_LABELS)
        or type(pointer.get("all_context_fresh")) is not bool
        or pointer.get("protocol_v2_input_quality_eligible")
        is not pointer.get("all_context_fresh")
        or pointer.get("protocol_v2_evidence_eligible") is not False
        or pointer.get("protocol_v2_annex_bound") is not False
        or pointer.get("campaign_attached") is not False
        or pointer.get("context_only") is not True
        or pointer.get("directional_authority") is not False
        or pointer.get("decision_policy_applied") is not False
        or pointer.get("research_only") is not True
        or not isinstance(receipt, Mapping)
        or set(receipt) != {"name", "sha256", "size_bytes"}
        or receipt.get("name") != RECEIPT_FILENAME
        or not _SHA256_RE.fullmatch(str(receipt.get("sha256") or ""))
        or type(receipt.get("size_bytes")) is not int
        or not 0 < receipt["size_bytes"] <= MAX_RESPONSE_BYTES
    ):
        raise BybitDerivativesContextCaptureError(
            "capture_pointer_contract_invalid"
        )
    _utc(pointer.get("completed_at"), "pointer_completed_at")
    return pointer


def _read_capture_bundle(
    namespace_dir: Path,
) -> tuple[dict[str, Any], bytes, dict[str, Any], bytes, dict[str, bytes]]:
    required = {
        SOURCE_FILENAME: "source_execution_quality_capture",
        INSTRUMENTS_FILENAME: "eligible_instruments",
        CONTEXTS_FILENAME: "derivatives_contexts",
        REQUEST_INDEX_FILENAME: "request_index",
        SUMMARY_FILENAME: "capture_input_summary",
        PROJECTION_FILENAME: "capture_projection",
    }
    try:
        with _open_verified_namespace_dir(namespace_dir) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            receipt_raw = _read_regular_bytes_at(namespace_fd, RECEIPT_FILENAME)
            manifest_raw = _read_regular_bytes_at(namespace_fd, MANIFEST_FILENAME)
            receipt = _parse_json(receipt_raw)
            manifest = _parse_json(manifest_raw)
            descriptors = manifest.get("artifacts")
            if (
                not isinstance(descriptors, list)
                or not 6 < len(descriptors) <= MAX_PLANNED_REQUESTS + 6
            ):
                raise BybitDerivativesContextCaptureError(
                    "capture_artifact_index_invalid"
                )
            artifacts: dict[str, bytes] = {}
            for descriptor in descriptors:
                if not isinstance(descriptor, Mapping) or set(descriptor) != {
                    "name", "role", "sha256", "size_bytes"
                }:
                    raise BybitDerivativesContextCaptureError(
                        "capture_artifact_index_invalid"
                    )
                name = str(descriptor.get("name") or "")
                role = str(descriptor.get("role") or "")
                expected_role = required.get(name)
                if (
                    name in artifacts
                    or name in {MANIFEST_FILENAME, RECEIPT_FILENAME}
                    or (expected_role is None and not _SAFE_RAW_RE.fullmatch(name))
                    or (expected_role is not None and role != expected_role)
                    or (
                        expected_role is None
                        and role != "accepted_raw_provider_response"
                    )
                ):
                    raise BybitDerivativesContextCaptureError(
                        "capture_artifact_name_invalid"
                    )
                artifact_raw = _read_regular_bytes_at(namespace_fd, name)
                if (
                    descriptor.get("sha256") != _sha256(artifact_raw)
                    or descriptor.get("size_bytes") != len(artifact_raw)
                ):
                    raise BybitDerivativesContextCaptureError(
                        "capture_fingerprint_mismatch"
                    )
                artifacts[name] = artifact_raw
            if set(required) - set(artifacts):
                raise BybitDerivativesContextCaptureError(
                    "capture_required_artifact_missing"
                )
            expected_entries = set(artifacts) | {
                MANIFEST_FILENAME,
                RECEIPT_FILENAME,
            }
            if set(os.listdir(namespace_fd)) != expected_entries:
                raise BybitDerivativesContextCaptureError(
                    "capture_unmanifested_artifact"
                )
    except BybitDerivativesContextCaptureError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise BybitDerivativesContextCaptureError(
            "capture_artifact_unreadable"
        ) from exc
    return receipt, receipt_raw, manifest, manifest_raw, artifacts


def _responses_from_index(
    request_index: Mapping[str, object],
    artifacts: Mapping[str, bytes],
    *,
    capture_id: object,
) -> list[BybitCapturedJSONResponse]:
    rows = request_index.get("requests")
    expected = {
        "capture_id", "credentials_read", "private_data_read",
        "redirects_followed", "request_count", "requests", "research_only",
        "retries", "schema_id", "schema_version",
    }
    if (
        set(request_index) != expected
        or request_index.get("schema_id")
        != "decision_radar.bybit_derivatives_request_index"
        or request_index.get("schema_version") != 1
        or request_index.get("capture_id") != capture_id
        or not isinstance(rows, list)
        or request_index.get("request_count") != len(rows)
        or request_index.get("retries") != 0
        or request_index.get("redirects_followed") != 0
        or request_index.get("credentials_read") is not False
        or request_index.get("private_data_read") is not False
        or request_index.get("research_only") is not True
    ):
        raise BybitDerivativesContextCaptureError("capture_request_index_invalid")
    responses: list[BybitCapturedJSONResponse] = []
    required_keys = {
        "content_type", "duration_ms", "http_status", "raw_artifact", "request",
        "request_started_at", "request_url", "response_received_at", "sequence",
        "sha256", "size_bytes", "transport_contract",
    }
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping) or set(row) != required_keys:
            raise BybitDerivativesContextCaptureError(
                "capture_request_index_invalid"
            )
        raw = artifacts.get(str(row.get("raw_artifact") or ""))
        if (
            row.get("sequence") != index
            or raw is None
            or row.get("sha256") != _sha256(raw)
            or row.get("size_bytes") != len(raw)
            or type(row.get("duration_ms")) is not int
            or row.get("http_status") != 200
        ):
            raise BybitDerivativesContextCaptureError(
                "capture_request_index_invalid"
            )
        responses.append(
            BybitCapturedJSONResponse(
                request=_request_from_values(row.get("request")),
                request_started_at=str(row.get("request_started_at") or ""),
                response_received_at=str(row.get("response_received_at") or ""),
                duration_ms=int(row.get("duration_ms")),
                response_url=str(row.get("request_url") or ""),
                http_status=int(row.get("http_status")),
                content_type=str(row.get("content_type") or ""),
                raw_bytes=raw,
                transport_contract=str(row.get("transport_contract") or ""),
            )
        )
    return responses


def _validate_publication(
    *,
    namespace: str,
    prepared: Mapping[str, object],
    receipt: Mapping[str, object],
    receipt_raw: bytes,
    manifest: Mapping[str, object],
    manifest_raw: bytes,
    pointer: Mapping[str, object] | None,
) -> None:
    expected_manifest, expected_receipt, expected_pointer = _publication_objects(
        prepared,
        manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else [],
    )
    if (
        _canonical_value(manifest) != _canonical_value(expected_manifest)
        or _canonical_value(receipt) != _canonical_value(expected_receipt)
        or receipt.get("artifact_namespace") != namespace
        or receipt.get("manifest")
        != {"name": MANIFEST_FILENAME, **_fingerprint(manifest_raw)}
        or (
            pointer is not None
            and (
                _canonical_value(pointer) != _canonical_value(expected_pointer)
                or pointer.get("receipt")
                != {"name": RECEIPT_FILENAME, **_fingerprint(receipt_raw)}
            )
        )
    ):
        raise BybitDerivativesContextCaptureError(
            "capture_publication_contract_invalid"
        )


def validate_bybit_derivatives_context_capture(
    artifact_base_dir: str | Path,
    *,
    namespace: str,
    pointer: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Hold one namespace, rederive every context, and validate publication."""

    if not _NAMESPACE_RE.fullmatch(namespace):
        raise BybitDerivativesContextCaptureError("capture_namespace_invalid")
    base = Path(artifact_base_dir).expanduser().absolute()
    receipt, receipt_raw, manifest, manifest_raw, artifacts = _read_capture_bundle(
        base / namespace
    )
    summary = _parse_json(artifacts[SUMMARY_FILENAME])
    request_index = _parse_json(artifacts[REQUEST_INDEX_FILENAME])
    capture_id = receipt.get("capture_id")
    responses = _responses_from_index(
        request_index,
        artifacts,
        capture_id=capture_id,
    )
    prepared = prepare_bybit_derivatives_context_capture(summary, responses)
    if (
        prepared.get("capture_id") != capture_id
        or prepared.get("artifact_namespace") != namespace
    ):
        raise BybitDerivativesContextCaptureError("capture_identity_drift")
    source = _parse_json(artifacts[SOURCE_FILENAME])
    instruments = _parse_json(artifacts[INSTRUMENTS_FILENAME])
    contexts = _parse_json(artifacts[CONTEXTS_FILENAME])
    projection = _parse_json(artifacts[PROJECTION_FILENAME])
    if (
        source.get("source_execution_quality_capture")
        != prepared.get("source_execution_quality_capture")
        or instruments.get("instruments") != prepared.get("eligible_instruments")
        or contexts.get("contexts") != prepared.get("contexts")
        or contexts.get("all_context_fresh")
        is not prepared.get("all_context_fresh")
        or _canonical_value(projection) != _canonical_value(prepared)
    ):
        raise BybitDerivativesContextCaptureError("capture_projection_drift")
    _validate_publication(
        namespace=namespace,
        prepared=prepared,
        receipt=receipt,
        receipt_raw=receipt_raw,
        manifest=manifest,
        manifest_raw=manifest_raw,
        pointer=pointer,
    )
    result = dict(prepared)
    result.update(
        {
            "status": "complete",
            "immutable_capture_persisted": True,
            "artifact_persisted": True,
            "pointer_validated": pointer is not None,
            "provider_call_attempted": False,
            "writes_performed": False,
        }
    )
    return result


__all__ = (
    "CONTRACT_VERSION",
    "POINTER_FILENAME",
    "BybitDerivativesContextCaptureError",
    "persist_bybit_derivatives_context_capture",
    "prepare_bybit_derivatives_context_capture",
    "validate_bybit_derivatives_context_capture",
    "validate_bybit_derivatives_context_pointer_bytes",
)
