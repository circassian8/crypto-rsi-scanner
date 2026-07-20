"""Immutable exact-response bundles for Bybit direct 1h/4h captures."""

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

from .bybit_execution_quality import (
    MAX_RADAR_ASSETS,
    PUBLIC_API_BASE,
    BybitEligibleInstrument,
    BybitExecutionQualityError,
    BybitPublicRequest,
    bybit_eligible_instrument_from_values,
)
from .bybit_execution_quality_capture import BybitCapturedJSONResponse
from .bybit_execution_quality_capture_errors import (
    BybitExecutionQualityCaptureError,
)
from .bybit_execution_quality_capture_models import TRANSPORT_CONTRACT
from .bybit_intraday import (
    INTERVAL_SECONDS,
    BybitIntradayError,
    build_bybit_kline_request,
    normalize_bybit_completed_kline,
)
from .bybit_intraday_set_freshness import (
    BAR_RECENCY_POLICY,
    FRESHNESS_POLICY,
    MAXIMUM_PROVIDER_AGE_SECONDS,
    _BybitIntradaySetFreshnessError,
    common_freshness_values,
    freshness_contract_valid,
    live_summary_freshness_matches,
    live_summary_freshness_values,
    project_intraday_set_freshness,
    require_exact_response_window,
)
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


CONTRACT_VERSION = "crypto_radar_bybit_intraday_capture_v4"
LIVE_CONTRACT_VERSION = "crypto_radar_bybit_intraday_live_v4"
EXECUTION_CAPTURE_CONTRACT_VERSION = (
    "crypto_radar_bybit_execution_quality_capture_v5"
)
POINTER_FILENAME = "radar_bybit_intraday_latest.json"
MANIFEST_FILENAME = "capture_manifest.json"
RECEIPT_FILENAME = "capture_completion_receipt.json"
SUMMARY_FILENAME = "capture_summary.json"
SOURCE_FILENAME = "source_execution_quality_capture.json"
INSTRUMENTS_FILENAME = "eligible_instruments.json"
REQUEST_INDEX_FILENAME = "request_index.json"
BARS_FILENAME = "intraday_bars.json"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_RESPONSES = MAX_RADAR_ASSETS * len(INTERVAL_SECONDS)
_LOCK_FILENAME = ".radar_bybit_intraday.lock"
_NAMESPACE_RE = re.compile(
    r"^radar_bybit_intraday_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_EXECUTION_NAMESPACE_RE = re.compile(
    r"^radar_bybit_execution_quality_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_SAFE_RAW_RE = re.compile(
    r"^raw_[0-9]{3}_kline_(?:60|240)_[A-Z0-9]{4,32}\.json$"
)
_LIVE_SUMMARY_KEYS = frozenset(
    {
        "all_bars_fresh", "all_bars_fresh_at_acquisition",
        "all_bars_fresh_at_completion", "artifact_persisted",
        "bar_count", "bar_recency_policy", "bars", "campaign_attached",
        "completed_at", "contract_version",
        "credentials_read", "eligible_instrument_count", "eligible_instruments",
        "execution_mode", "intervals", "no_send", "normal_rsi_signal_rows_written",
        "orders_available", "paper_trades_created", "private_data_read",
        "intraday_set_freshness_policy",
        "maximum_provider_response_age_at_completion_seconds",
        "maximum_provider_response_age_policy_seconds",
        "minimum_bar_recency_remaining_at_completion_seconds",
        "protocol_v2_evidence_eligible", "provider_call_attempted",
        "provider_call_authorized", "provider_request_bound",
        "provider_request_count", "provider_request_succeeded", "quote_asset",
        "recorded_403_policy", "redirects_followed", "research_only", "retries",
        "row_type", "source_execution_quality_capture",
        "source_execution_quality_capture_id", "started_at", "status",
        "telegram_sends", "trades_created", "triggered_fade_created", "venue_id",
        "writes_performed",
    }
)
_PERSISTED_EXTRA_KEYS = frozenset(
    {
        "artifact_namespace",
        "capture_contract_version",
        "capture_id",
        "protocol_v2_annex_bound",
        "protocol_v2_input_quality_eligible",
    }
)


class _BybitIntradayCaptureError(RuntimeError):
    """Closed immutable-capture validation or publication failure."""


BybitIntradayCaptureError = _BybitIntradayCaptureError


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _pretty_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _canonical_value(value: object) -> object:
    return json.loads(_canonical_bytes(value))


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fingerprint(raw: bytes) -> dict[str, object]:
    return {"sha256": _sha256(raw), "size_bytes": len(raw)}


def _utc_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BybitIntradayCaptureError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitIntradayCaptureError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitIntradayCaptureError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_datetime(value: object, field: str) -> datetime:
    return datetime.fromisoformat(_utc_text(value, field).replace("Z", "+00:00"))


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


def _request_from_values(value: object) -> BybitPublicRequest:
    if not isinstance(value, Mapping) or set(value) != {
        "credentials_required", "method", "path", "private_data", "query",
        "research_only",
    }:
        raise BybitIntradayCaptureError("captured_request_schema_invalid")
    query = value.get("query")
    if not isinstance(query, list) or not query:
        raise BybitIntradayCaptureError("captured_request_query_invalid")
    pairs: list[tuple[str, str]] = []
    for pair in query:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(item, str) and item for item in pair)
        ):
            raise BybitIntradayCaptureError("captured_request_query_invalid")
        pairs.append((pair[0], pair[1]))
    return BybitPublicRequest(
        method=str(value.get("method") or ""),
        path=str(value.get("path") or ""),
        query=tuple(pairs),
        credentials_required=value.get("credentials_required") is True,
        private_data=value.get("private_data") is True,
        research_only=value.get("research_only") is True,
    )


def _instrument_from_values(value: object) -> BybitEligibleInstrument:
    try:
        return bybit_eligible_instrument_from_values(value)
    except BybitExecutionQualityError as exc:
        raise BybitIntradayCaptureError("eligible_instrument_schema_invalid") from exc


def _source_capture_projection(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise BybitIntradayCaptureError("source_execution_capture_invalid")
    source = value.get("source_authority")
    required = {
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
        or not isinstance(source, Mapping)
        or set(source) != required
        or not _SHA256_RE.fullmatch(str(source.get("operator_state_sha256") or ""))
        or type(source.get("revision")) is not int
    ):
        raise BybitIntradayCaptureError("source_execution_capture_invalid")
    _utc_text(value.get("completed_at"), "source_execution_capture_completed_at")
    _utc_text(source.get("authority_checked_at"), "source_authority_checked_at")
    return {
        "contract_version": EXECUTION_CAPTURE_CONTRACT_VERSION,
        "capture_id": value["capture_id"],
        "artifact_namespace": value["artifact_namespace"],
        "completed_at": value["completed_at"],
        "pointer_sha256": value["pointer_sha256"],
        "source_authority": dict(source),
        "evidence_authority_eligible": True,
        "protocol_v2_input_quality_eligible": True,
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "research_only": True,
        "no_send": True,
    }


def _response_values(
    response: BybitCapturedJSONResponse,
    *,
    index: int,
    raw_filename: str,
) -> dict[str, object]:
    started = _utc_datetime(response.request_started_at, "request_started_at")
    received = _utc_datetime(response.response_received_at, "response_received_at")
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
        raise BybitIntradayCaptureError("captured_response_transport_invalid")
    try:
        response.payload()
    except BybitExecutionQualityCaptureError as exc:
        raise BybitIntradayCaptureError("captured_response_json_invalid") from exc
    return {
        "sequence": index,
        "request": _request_values(response.request),
        "request_url": response.response_url,
        "request_started_at": _utc_text(
            response.request_started_at, "request_started_at"
        ),
        "response_received_at": _utc_text(
            response.response_received_at, "response_received_at"
        ),
        "duration_ms": response.duration_ms,
        "http_status": response.http_status,
        "content_type": response.content_type.casefold(),
        "transport_contract": response.transport_contract,
        "raw_artifact": raw_filename,
        **_fingerprint(response.raw_bytes),
    }


def _validate_live_summary(summary: Mapping[str, object]) -> tuple[str, str]:
    if (
        set(summary) != _LIVE_SUMMARY_KEYS
        or summary.get("contract_version") != LIVE_CONTRACT_VERSION
        or summary.get("row_type")
        != "decision_radar_bybit_intraday_observation_set"
        or summary.get("status") != "complete"
        or summary.get("venue_id") != "bybit"
        or summary.get("execution_mode") != "perpetual"
        or summary.get("quote_asset") != "USDT"
        or summary.get("intervals") != ["1h", "4h"]
        or summary.get("provider_call_authorized") is not True
        or summary.get("provider_call_attempted") is not True
        or summary.get("provider_request_succeeded") is not True
        or summary.get("artifact_persisted") is not False
        or summary.get("campaign_attached") is not False
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
        raise BybitIntradayCaptureError("capture_summary_contract_invalid")
    started = _utc_text(summary.get("started_at"), "capture_started_at")
    completed = _utc_text(summary.get("completed_at"), "capture_completed_at")
    if _utc_datetime(completed, "capture_completed_at") < _utc_datetime(
        started, "capture_started_at"
    ):
        raise BybitIntradayCaptureError("capture_clock_invalid")
    return started, completed


def _validate_evidence_sets(
    summary: Mapping[str, object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> tuple[list[object], list[object], dict[str, object]]:
    instrument_values = summary.get("eligible_instruments")
    bars = summary.get("bars")
    if (
        not isinstance(instrument_values, list)
        or not 0 < len(instrument_values) <= MAX_RADAR_ASSETS
        or not isinstance(bars, list)
    ):
        raise BybitIntradayCaptureError("capture_evidence_sets_invalid")
    expected_count = len(instrument_values) * len(INTERVAL_SECONDS)
    if (
        len(responses) != expected_count
        or len(responses) > MAX_RESPONSES
        or len(bars) != expected_count
        or summary.get("eligible_instrument_count") != len(instrument_values)
        or summary.get("bar_count") != len(bars)
        or summary.get("provider_request_count") != len(responses)
        or summary.get("provider_request_bound") != expected_count
        or type(summary.get("all_bars_fresh")) is not bool
    ):
        raise BybitIntradayCaptureError("capture_count_contract_invalid")
    source_value = summary.get("source_execution_quality_capture")
    source = _source_capture_projection(source_value)
    if source["capture_id"] != summary.get("source_execution_quality_capture_id"):
        raise BybitIntradayCaptureError("source_execution_capture_identity_mismatch")
    canonical_instruments = _canonical_value(instrument_values)
    canonical_bars = _canonical_value(bars)
    if not isinstance(canonical_instruments, list) or not isinstance(canonical_bars, list):
        raise BybitIntradayCaptureError("capture_evidence_sets_invalid")
    if (
        not isinstance(source_value, Mapping)
        or _canonical_value(source_value.get("eligible_instruments"))
        != canonical_instruments
    ):
        raise BybitIntradayCaptureError("source_execution_instrument_set_mismatch")
    return canonical_instruments, canonical_bars, source


def _reconstruct_responses(
    *,
    started_at: str,
    instruments: Sequence[object],
    bars: Sequence[object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> tuple[list[dict[str, object]], list[tuple[str, bytes]]]:
    request_rows: list[dict[str, object]] = []
    raw_rows: list[tuple[str, bytes]] = []
    cursor = 0
    for instrument_value in instruments:
        instrument = _instrument_from_values(instrument_value)
        for interval in INTERVAL_SECONDS:
            response = responses[cursor]
            expected = build_bybit_kline_request(
                instrument,
                interval=interval,
                as_of=started_at,
            )
            if response.request != expected:
                raise BybitIntradayCaptureError("kline_request_order_drift")
            raw_name = (
                f"raw_{cursor + 1:03d}_kline_{interval}_{instrument.instrument_id}.json"
            )
            request_rows.append(
                _response_values(response, index=cursor + 1, raw_filename=raw_name)
            )
            raw_rows.append((raw_name, response.raw_bytes))
            expected_bar = bars[cursor]
            if not isinstance(expected_bar, Mapping):
                raise BybitIntradayCaptureError("intraday_bar_schema_invalid")
            try:
                reconstructed = normalize_bybit_completed_kline(
                    response.payload(),
                    instrument=instrument,
                    request=response.request,
                    request_started_at=response.request_started_at,
                    acquired_at=response.response_received_at,
                    request_lineage_id=str(expected_bar.get("request_lineage_id") or ""),
                ).to_dict()
            except (BybitIntradayError, ValueError) as exc:
                raise BybitIntradayCaptureError("kline_response_contract_invalid") from exc
            if _canonical_value(reconstructed) != expected_bar:
                raise BybitIntradayCaptureError("intraday_bar_projection_drift")
            cursor += 1
    return request_rows, raw_rows


def _validate_capture_inputs(
    summary: Mapping[str, object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> dict[str, object]:
    started, completed = _validate_live_summary(summary)
    instruments, bars, source = _validate_evidence_sets(summary, responses)
    request_rows, raw_rows = _reconstruct_responses(
        started_at=started,
        instruments=instruments,
        bars=bars,
        responses=responses,
    )
    if _utc_datetime(source["completed_at"], "source_capture_completed_at") > (
        _utc_datetime(started, "capture_started_at")
    ):
        raise BybitIntradayCaptureError("source_execution_capture_after_intraday_start")
    try:
        require_exact_response_window(
            responses,
            started_at=_utc_datetime(started, "capture_started_at"),
            completed_at=_utc_datetime(completed, "capture_completed_at"),
        )
        freshness = project_intraday_set_freshness(
            bars,
            completed_at=_utc_datetime(completed, "capture_completed_at"),
        )
    except _BybitIntradaySetFreshnessError as exc:
        raise BybitIntradayCaptureError(exc.reason_code) from exc
    if not live_summary_freshness_matches(summary, freshness):
        raise BybitIntradayCaptureError("intraday_freshness_summary_mismatch")
    freshness_values = live_summary_freshness_values(freshness)
    return {
        "started_at": started,
        "completed_at": completed,
        "source_execution_quality_capture": source,
        "eligible_instruments": instruments,
        "bars": bars,
        "request_rows": request_rows,
        "raw_rows": raw_rows,
        **freshness_values,
        "protocol_v2_input_quality_eligible": freshness.fresh_at_completion,
    }


def _capture_namespace(prepared: Mapping[str, object]) -> tuple[str, str]:
    completed = _utc_datetime(prepared["completed_at"], "capture_completed_at")
    source = prepared["source_execution_quality_capture"]
    seed = _canonical_bytes(
        {
            "completed_at": prepared["completed_at"],
            "source_execution_quality_capture": source,
            "raw_sha256": [_sha256(raw) for _name, raw in prepared["raw_rows"]],
        }
    )
    capture_id = _sha256(seed)
    timestamp = completed.strftime("%Y%m%dt%H%M%S%fz")
    return f"radar_bybit_intraday_{timestamp}_{capture_id[:12]}", capture_id


@contextmanager
def _publication_lock(base: Path) -> Iterator[None]:
    descriptor: int | None = None
    locked = False
    try:
        with _open_verified_namespace_dir(base) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(_LOCK_FILENAME, flags, 0o600, dir_fd=namespace_fd)
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                raise BybitIntradayCaptureError("capture_lock_invalid")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            yield
    except BybitIntradayCaptureError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise BybitIntradayCaptureError("capture_lock_unavailable") from exc
    finally:
        if locked and descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        if descriptor is not None:
            os.close(descriptor)


def _artifact_descriptor(name: str, role: str, raw: bytes) -> dict[str, object]:
    return {"name": name, "role": role, **_fingerprint(raw)}


def _capture_payloads(
    summary: Mapping[str, object],
    prepared: Mapping[str, object],
    *,
    namespace: str,
    capture_id: str,
) -> list[tuple[str, str, bytes]]:
    source = {
        "schema_id": "decision_radar.bybit_intraday_source_execution_capture",
        "schema_version": 1,
        "capture_id": capture_id,
        "source_execution_quality_capture": prepared[
            "source_execution_quality_capture"
        ],
        "research_only": True,
    }
    instruments = {
        "schema_id": "decision_radar.bybit_intraday_instruments",
        "schema_version": 1,
        "capture_id": capture_id,
        "instrument_count": len(prepared["eligible_instruments"]),
        "instruments": prepared["eligible_instruments"],
        "research_only": True,
    }
    bars = {
        "schema_id": "decision_radar.bybit_intraday_bars",
        "schema_version": 1,
        "capture_id": capture_id,
        "bar_count": len(prepared["bars"]),
        "bars": prepared["bars"],
        **common_freshness_values(prepared),
        "research_only": True,
    }
    request_index = {
        "schema_id": "decision_radar.bybit_intraday_request_index",
        "schema_version": 1,
        "capture_id": capture_id,
        "request_count": len(prepared["request_rows"]),
        "requests": prepared["request_rows"],
        "retries": 0,
        "redirects_followed": 0,
        "credentials_read": False,
        "private_data_read": False,
        "research_only": True,
    }
    persisted = dict(_canonical_value(dict(summary)))
    persisted.update(
        {
            "capture_contract_version": CONTRACT_VERSION,
            "capture_id": capture_id,
            "artifact_namespace": namespace,
            "artifact_persisted": True,
            "writes_performed": True,
            "protocol_v2_input_quality_eligible": prepared[
                "protocol_v2_input_quality_eligible"
            ],
            "protocol_v2_annex_bound": False,
        }
    )
    payloads = [
        (SOURCE_FILENAME, "source_execution_quality_capture", _pretty_bytes(source)),
        (INSTRUMENTS_FILENAME, "eligible_instruments", _pretty_bytes(instruments)),
        (BARS_FILENAME, "intraday_bars", _pretty_bytes(bars)),
        (REQUEST_INDEX_FILENAME, "request_index", _pretty_bytes(request_index)),
        (SUMMARY_FILENAME, "capture_summary", _pretty_bytes(persisted)),
    ]
    payloads.extend(
        (name, "accepted_raw_provider_response", raw)
        for name, raw in prepared["raw_rows"]
    )
    return payloads


def _publication_values(
    prepared: Mapping[str, object],
    *,
    namespace: str,
    capture_id: str,
    descriptors: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    source = prepared["source_execution_quality_capture"]
    common = {
        "contract_version": CONTRACT_VERSION,
        "capture_id": capture_id,
        "artifact_namespace": namespace,
        "completed_at": prepared["completed_at"],
        "source_execution_quality_capture_id": source["capture_id"],
        "source_execution_quality_pointer_sha256": source["pointer_sha256"],
        "request_count": len(prepared["request_rows"]),
        "bar_count": len(prepared["bars"]),
        **common_freshness_values(prepared),
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "campaign_attached": False,
        "research_only": True,
    }
    manifest = {
        "schema_id": "decision_radar.bybit_intraday_capture_manifest",
        "schema_version": 1,
        **common,
        "started_at": prepared["started_at"],
        "venue_id": "bybit",
        "execution_mode": "perpetual",
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
        "schema_id": "decision_radar.bybit_intraday_completion_receipt",
        "schema_version": 1,
        "status": "complete",
        **common,
        "manifest": {"name": MANIFEST_FILENAME, **_fingerprint(manifest_raw)},
    }
    receipt_raw = _pretty_bytes(receipt)
    pointer = {
        "schema_id": "decision_radar.bybit_intraday_latest_pointer",
        "schema_version": 1,
        "status": "complete",
        **common,
        "receipt": {"name": RECEIPT_FILENAME, **_fingerprint(receipt_raw)},
    }
    return manifest, receipt, pointer


def persist_bybit_intraday_capture(
    artifact_base_dir: str | Path,
    *,
    summary: Mapping[str, object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> dict[str, object]:
    """Seal and point to one fully rederived direct-bar capture."""

    base = Path(artifact_base_dir).expanduser().absolute()
    if not base.is_dir():
        raise BybitIntradayCaptureError("artifact_base_unavailable")
    prepared = _validate_capture_inputs(summary, responses)
    namespace, capture_id = _capture_namespace(prepared)
    payloads = _capture_payloads(
        summary,
        prepared,
        namespace=namespace,
        capture_id=capture_id,
    )
    descriptors = [
        _artifact_descriptor(name, role, raw) for name, role, raw in payloads
    ]
    manifest, receipt, pointer = _publication_values(
        prepared,
        namespace=namespace,
        capture_id=capture_id,
        descriptors=descriptors,
    )
    with _publication_lock(base):
        existing_raw = read_regular_bytes(base / POINTER_FILENAME, missing_ok=True)
        if existing_raw is not None:
            existing = validate_bybit_intraday_pointer_bytes(existing_raw)
            prior = validate_bybit_intraday_capture(
                base,
                namespace=str(existing["artifact_namespace"]),
                pointer=existing,
            )
            if _utc_datetime(prior["completed_at"], "prior_completed_at") > (
                _utc_datetime(prepared["completed_at"], "capture_completed_at")
            ):
                raise BybitIntradayCaptureError("capture_pointer_rollback_rejected")
        namespace_dir = base / namespace
        ensure_safe_namespace_dir(namespace_dir)
        try:
            for name, _role, raw in payloads:
                write_bytes_immutable(namespace_dir / name, raw)
            write_json_immutable(namespace_dir / MANIFEST_FILENAME, manifest)
            write_json_immutable(namespace_dir / RECEIPT_FILENAME, receipt)
        except MarketNoSendError as exc:
            raise BybitIntradayCaptureError("capture_immutable_write_failed") from exc
        validate_bybit_intraday_capture(base, namespace=namespace)
        try:
            write_json_atomic(base / POINTER_FILENAME, pointer)
        except MarketNoSendError as exc:
            raise BybitIntradayCaptureError("capture_pointer_write_failed") from exc
        return load_latest_bybit_intraday_capture(base)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev, left.st_ino, left.st_mode, left.st_nlink, left.st_size,
        left.st_mtime_ns, left.st_ctime_ns,
    ) == (
        right.st_dev, right.st_ino, right.st_mode, right.st_nlink, right.st_size,
        right.st_mtime_ns, right.st_ctime_ns,
    )


def _read_regular_bytes_at(directory_fd: int, name: str) -> bytes:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise BybitIntradayCaptureError("capture_artifact_name_invalid")
    descriptor: int | None = None
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise BybitIntradayCaptureError("capture_artifact_unreadable")
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=directory_fd,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_file(before, opened):
            raise BybitIntradayCaptureError("capture_artifact_unreadable")
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
            raise BybitIntradayCaptureError("capture_artifact_unreadable")
        return raw
    except BybitIntradayCaptureError:
        raise
    except OSError as exc:
        raise BybitIntradayCaptureError("capture_artifact_unreadable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _parse_json(raw: bytes) -> dict[str, Any]:
    try:
        return parse_json_object_bytes(raw)
    except MarketNoSendError as exc:
        raise BybitIntradayCaptureError("capture_artifact_invalid_json") from exc


def validate_bybit_intraday_pointer_bytes(raw: bytes) -> dict[str, Any]:
    pointer = _parse_json(raw)
    expected = {
        "all_bars_fresh", "all_bars_fresh_at_acquisition",
        "all_bars_fresh_at_completion", "artifact_namespace", "bar_count",
        "bar_recency_policy", "campaign_attached", "capture_id",
        "completed_at", "contract_version", "intraday_set_freshness_policy",
        "maximum_provider_response_age_at_completion_seconds",
        "maximum_provider_response_age_policy_seconds",
        "minimum_bar_recency_remaining_at_completion_seconds",
        "protocol_v2_annex_bound", "protocol_v2_evidence_eligible",
        "protocol_v2_input_quality_eligible", "receipt", "request_count",
        "research_only", "schema_id", "schema_version",
        "source_execution_quality_capture_id",
        "source_execution_quality_pointer_sha256", "status",
    }
    receipt = pointer.get("receipt")
    if (
        set(pointer) != expected
        or pointer.get("schema_id") != "decision_radar.bybit_intraday_latest_pointer"
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
        or not 1 <= pointer["request_count"] <= MAX_RESPONSES
        or pointer.get("bar_count") != pointer.get("request_count")
        or not freshness_contract_valid(pointer)
        or pointer.get("protocol_v2_evidence_eligible") is not False
        or pointer.get("protocol_v2_annex_bound") is not False
        or pointer.get("campaign_attached") is not False
        or pointer.get("research_only") is not True
        or not isinstance(receipt, Mapping)
        or set(receipt) != {"name", "sha256", "size_bytes"}
        or receipt.get("name") != RECEIPT_FILENAME
        or not _SHA256_RE.fullmatch(str(receipt.get("sha256") or ""))
        or type(receipt.get("size_bytes")) is not int
        or not 0 < receipt["size_bytes"] <= MAX_RESPONSE_BYTES
    ):
        raise BybitIntradayCaptureError("capture_pointer_contract_invalid")
    _utc_text(pointer.get("completed_at"), "pointer_completed_at")
    return pointer


def _read_capture_bundle(
    namespace_dir: Path,
) -> tuple[dict[str, Any], bytes, dict[str, Any], bytes, dict[str, bytes], dict[str, str]]:
    required = {
        SOURCE_FILENAME: "source_execution_quality_capture",
        INSTRUMENTS_FILENAME: "eligible_instruments",
        BARS_FILENAME: "intraday_bars",
        REQUEST_INDEX_FILENAME: "request_index",
        SUMMARY_FILENAME: "capture_summary",
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
                or not 5 < len(descriptors) <= MAX_RESPONSES + 5
            ):
                raise BybitIntradayCaptureError("capture_artifact_index_invalid")
            artifacts: dict[str, bytes] = {}
            roles: dict[str, str] = {}
            for descriptor in descriptors:
                if not isinstance(descriptor, Mapping) or set(descriptor) != {
                    "name", "role", "sha256", "size_bytes"
                }:
                    raise BybitIntradayCaptureError("capture_artifact_index_invalid")
                name = str(descriptor.get("name") or "")
                role = str(descriptor.get("role") or "")
                expected_role = required.get(name)
                if (
                    name in artifacts
                    or name in {MANIFEST_FILENAME, RECEIPT_FILENAME}
                    or (expected_role is None and not _SAFE_RAW_RE.fullmatch(name))
                    or (expected_role is not None and role != expected_role)
                    or (expected_role is None and role != "accepted_raw_provider_response")
                ):
                    raise BybitIntradayCaptureError("capture_artifact_name_invalid")
                raw = _read_regular_bytes_at(namespace_fd, name)
                if (
                    descriptor.get("sha256") != _sha256(raw)
                    or descriptor.get("size_bytes") != len(raw)
                ):
                    raise BybitIntradayCaptureError("capture_fingerprint_mismatch")
                artifacts[name] = raw
                roles[name] = role
            if set(required) - set(artifacts):
                raise BybitIntradayCaptureError("capture_required_artifact_missing")
            expected_entries = set(artifacts) | {
                MANIFEST_FILENAME,
                RECEIPT_FILENAME,
            }
            try:
                actual_entries = set(os.listdir(namespace_fd))
            except OSError as exc:
                raise BybitIntradayCaptureError("capture_artifact_unreadable") from exc
            if (
                len(actual_entries) > MAX_RESPONSES + 7
                or actual_entries != expected_entries
            ):
                raise BybitIntradayCaptureError("capture_unmanifested_artifact")
    except BybitIntradayCaptureError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise BybitIntradayCaptureError("capture_artifact_unreadable") from exc
    return receipt, receipt_raw, manifest, manifest_raw, artifacts, roles


def _validate_common(
    namespace: str,
    value: Mapping[str, object],
    *,
    schema_id: str,
    capture_id: object,
) -> None:
    if (
        value.get("schema_id") != schema_id
        or value.get("schema_version") != 1
        or value.get("contract_version") != CONTRACT_VERSION
        or value.get("capture_id") != capture_id
        or value.get("artifact_namespace") != namespace
        or value.get("protocol_v2_evidence_eligible") is not False
        or value.get("protocol_v2_annex_bound") is not False
        or value.get("campaign_attached") is not False
        or value.get("research_only") is not True
    ):
        raise BybitIntradayCaptureError("capture_publication_contract_invalid")


def _source_summary_from_persisted(value: Mapping[str, object]) -> dict[str, object]:
    if (
        set(value) != _LIVE_SUMMARY_KEYS | _PERSISTED_EXTRA_KEYS
        or value.get("capture_contract_version") != CONTRACT_VERSION
        or not _SHA256_RE.fullmatch(str(value.get("capture_id") or ""))
        or not _NAMESPACE_RE.fullmatch(str(value.get("artifact_namespace") or ""))
        or value.get("artifact_persisted") is not True
        or value.get("writes_performed") is not True
        or type(value.get("protocol_v2_input_quality_eligible")) is not bool
        or value.get("protocol_v2_annex_bound") is not False
    ):
        raise BybitIntradayCaptureError("persisted_summary_contract_invalid")
    source = {key: value[key] for key in _LIVE_SUMMARY_KEYS}
    source.update({"artifact_persisted": False, "writes_performed": False})
    return source


def _responses_from_index(
    request_index: Mapping[str, object],
    artifacts: Mapping[str, bytes],
    *,
    capture_id: object,
) -> list[BybitCapturedJSONResponse]:
    rows = request_index.get("requests")
    if (
        set(request_index)
        != {
            "capture_id", "credentials_read", "private_data_read",
            "redirects_followed", "request_count", "requests",
            "research_only", "retries", "schema_id", "schema_version",
        }
        or request_index.get("schema_id")
        != "decision_radar.bybit_intraday_request_index"
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
        raise BybitIntradayCaptureError("capture_request_index_invalid")
    responses: list[BybitCapturedJSONResponse] = []
    required_keys = {
        "content_type", "duration_ms", "http_status", "raw_artifact", "request",
        "request_started_at", "request_url", "response_received_at", "sequence",
        "sha256", "size_bytes", "transport_contract",
    }
    for index, row in enumerate(rows, start=1):
        if (
            not isinstance(row, Mapping)
            or set(row) != required_keys
            or type(row.get("duration_ms")) is not int
            or type(row.get("http_status")) is not int
            or row.get("http_status") != 200
            or not isinstance(row.get("request_started_at"), str)
            or not isinstance(row.get("response_received_at"), str)
            or not isinstance(row.get("request_url"), str)
            or not isinstance(row.get("content_type"), str)
            or not isinstance(row.get("transport_contract"), str)
            or not _SHA256_RE.fullmatch(str(row.get("sha256") or ""))
            or type(row.get("size_bytes")) is not int
            or not 0 < row["size_bytes"] <= MAX_RESPONSE_BYTES
        ):
            raise BybitIntradayCaptureError("capture_request_index_invalid")
        raw_name = str(row.get("raw_artifact") or "")
        raw = artifacts.get(raw_name)
        if (
            row.get("sequence") != index
            or raw is None
            or row.get("sha256") != _sha256(raw)
            or row.get("size_bytes") != len(raw)
        ):
            raise BybitIntradayCaptureError("capture_request_index_invalid")
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


def validate_bybit_intraday_capture(
    artifact_base_dir: str | Path,
    *,
    namespace: str,
    pointer: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate one immutable namespace and rederive every bar from raw bytes."""

    from .bybit_intraday_capture_validation import (
        _validate_projection_objects,
        _validate_publication_objects,
        _validated_capture_result,
    )

    if not _NAMESPACE_RE.fullmatch(namespace):
        raise BybitIntradayCaptureError("capture_namespace_invalid")
    base = Path(artifact_base_dir).expanduser().absolute()
    receipt, receipt_raw, manifest, manifest_raw, artifacts, _roles = (
        _read_capture_bundle(base / namespace)
    )
    capture_id = receipt.get("capture_id")
    _validate_publication_objects(
        namespace=namespace,
        capture_id=capture_id,
        receipt=receipt,
        receipt_raw=receipt_raw,
        manifest=manifest,
        manifest_raw=manifest_raw,
        pointer=pointer,
    )
    summary = _parse_json(artifacts[SUMMARY_FILENAME])
    request_index = _parse_json(artifacts[REQUEST_INDEX_FILENAME])
    responses = _responses_from_index(
        request_index,
        artifacts,
        capture_id=capture_id,
    )
    source_summary = _source_summary_from_persisted(summary)
    prepared = _validate_capture_inputs(source_summary, responses)
    derived_namespace, derived_capture_id = _capture_namespace(prepared)
    if derived_namespace != namespace or derived_capture_id != capture_id:
        raise BybitIntradayCaptureError("capture_identity_drift")
    source = _parse_json(artifacts[SOURCE_FILENAME])
    instruments = _parse_json(artifacts[INSTRUMENTS_FILENAME])
    bars = _parse_json(artifacts[BARS_FILENAME])
    _validate_projection_objects(
        capture_id=capture_id,
        artifacts=artifacts,
        responses=responses,
        source=source,
        instruments=instruments,
        bars=bars,
        prepared=prepared,
    )
    common_fields = (
        "completed_at", "source_execution_quality_capture_id",
        "source_execution_quality_pointer_sha256", "request_count", "bar_count",
        "all_bars_fresh", "all_bars_fresh_at_acquisition",
        "all_bars_fresh_at_completion", "intraday_set_freshness_policy",
        "maximum_provider_response_age_at_completion_seconds",
        "maximum_provider_response_age_policy_seconds",
        "minimum_bar_recency_remaining_at_completion_seconds",
        "bar_recency_policy", "protocol_v2_input_quality_eligible",
    )
    if any(receipt.get(key) != manifest.get(key) for key in common_fields) or (
        pointer is not None
        and any(pointer.get(key) != receipt.get(key) for key in common_fields)
    ):
        raise BybitIntradayCaptureError("capture_cross_artifact_drift")
    return _validated_capture_result(
        namespace=namespace,
        capture_id=capture_id,
        prepared=prepared,
        request_count=len(responses),
        pointer_validated=pointer is not None,
    )


def load_latest_bybit_intraday_capture(
    artifact_base_dir: str | Path,
) -> dict[str, object]:
    base = Path(artifact_base_dir).expanduser().absolute()
    try:
        raw = read_regular_bytes(base / POINTER_FILENAME, missing_ok=True)
    except MarketNoSendError as exc:
        raise BybitIntradayCaptureError("capture_pointer_unreadable") from exc
    if raw is None:
        raise BybitIntradayCaptureError("capture_pointer_missing")
    pointer = validate_bybit_intraday_pointer_bytes(raw)
    validated = validate_bybit_intraday_capture(
        base,
        namespace=str(pointer["artifact_namespace"]),
        pointer=pointer,
    )
    try:
        final_raw = read_regular_bytes(base / POINTER_FILENAME)
    except MarketNoSendError as exc:
        raise BybitIntradayCaptureError("capture_pointer_unreadable") from exc
    if final_raw != raw:
        raise BybitIntradayCaptureError("capture_pointer_changed_during_read")
    validated["pointer_sha256"] = _sha256(raw)
    return validated


def bybit_intraday_capture_status(
    artifact_base_dir: str | Path,
) -> dict[str, object]:
    try:
        return load_latest_bybit_intraday_capture(artifact_base_dir)
    except BybitIntradayCaptureError as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "unavailable",
            "reason": str(exc),
            "source_execution_quality_capture": None,
            "eligible_instruments": [],
            "bars": [],
            "request_count": 0,
            "bar_count": 0,
            "all_bars_fresh": False,
            "all_bars_fresh_at_acquisition": False,
            "all_bars_fresh_at_completion": False,
            "intraday_set_freshness_policy": FRESHNESS_POLICY,
            "maximum_provider_response_age_at_completion_seconds": None,
            "maximum_provider_response_age_policy_seconds": (
                MAXIMUM_PROVIDER_AGE_SECONDS
            ),
            "minimum_bar_recency_remaining_at_completion_seconds": None,
            "bar_recency_policy": BAR_RECENCY_POLICY,
            "protocol_v2_input_quality_eligible": False,
            "protocol_v2_evidence_eligible": False,
            "protocol_v2_annex_bound": False,
            "campaign_attached": False,
            "provider_call_attempted": False,
            "writes_performed": False,
            "research_only": True,
            "no_send": True,
            "orders": 0,
            "trades": 0,
            "paper_trades": 0,
            "normal_rsi_writes": 0,
            "event_alpha_triggered_fade": 0,
            "pointer_sha256": None,
        }


__all__ = (
    "CONTRACT_VERSION",
    "POINTER_FILENAME",
    "BybitIntradayCaptureError",
    "bybit_intraday_capture_status",
    "load_latest_bybit_intraday_capture",
    "persist_bybit_intraday_capture",
    "validate_bybit_intraday_capture",
    "validate_bybit_intraday_pointer_bytes",
)
