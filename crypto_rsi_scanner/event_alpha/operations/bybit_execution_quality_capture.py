"""Immutable evidence bundles for public Bybit execution-quality captures."""

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
    BYBIT_CATEGORY,
    CONTRACT_TYPE,
    INSTRUMENTS_PATH,
    INSTRUMENT_STATUS,
    MAX_RADAR_ASSETS,
    PUBLIC_API_BASE,
    QUOTE_ASSET,
    REQUEST_STRATEGY,
    BybitEligibleInstrument,
    BybitExecutionQualityError,
    BybitPublicRequest,
    build_bybit_instrument_catalog_request,
    build_bybit_orderbook_request,
    normalize_bybit_orderbook,
    select_bybit_usdt_perpetual_instruments,
)
from .bybit_execution_quality_capture_errors import BybitExecutionQualityCaptureError
from .bybit_execution_quality_capture_models import (
    LIVE_SUMMARY_KEYS as _LIVE_SUMMARY_KEYS,
    PERSISTED_SUMMARY_EXTRA_KEYS as _PERSISTED_SUMMARY_EXTRA_KEYS,
    REQUEST_ROW_KEYS as _REQUEST_ROW_KEYS,
    TRANSPORT_CONTRACT,
    BybitCapturedJSONResponse,
    _execution_capture_namespace,
)
from .bybit_execution_quality_set_freshness import (
    _BybitExecutionQualitySetFreshnessError, common_freshness_matches,
    common_freshness_values, live_summary_freshness_matches,
    observation_freshness_contract_valid, observation_freshness_matches,
    observation_freshness_values, prepared_freshness_values,
    prepared_summary_freshness_matches, project_execution_quality_set_freshness,
    exact_response_acquisition_matches, require_exact_response_window,
)
from .bybit_execution_quality_universe import (
    BybitExecutionQualityUniverseError,
    build_capture_universe_values,
    capture_universe_projection_valid,
    require_provider_query_assets,
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


CONTRACT_VERSION = "crypto_radar_bybit_execution_quality_capture_v5"
_LIVE_CONTRACT_VERSION = "crypto_radar_bybit_execution_quality_live_v5"
POINTER_FILENAME = "radar_bybit_execution_quality_latest.json"
MANIFEST_FILENAME = "capture_manifest.json"
RECEIPT_FILENAME = "capture_completion_receipt.json"
SUMMARY_FILENAME = "capture_summary.json"
AUTHORITY_FILENAME = "source_authority.json"
UNIVERSE_FILENAME = "radar_universe.json"
REQUEST_INDEX_FILENAME = "request_index.json"
OBSERVATIONS_FILENAME = "execution_quality_observations.json"
MAX_STANDARD_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_RESPONSES = MAX_RADAR_ASSETS + 1
_LOCK_FILENAME = ".radar_bybit_execution_quality.lock"
_NAMESPACE_RE = re.compile(
    r"^radar_bybit_execution_quality_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_SAFE_RAW_NAME_RE = re.compile(
    r"^(?:raw_001_instrument_catalog|raw_[0-9]{3}_orderbook_[A-Z0-9]{4,32})\.json$"
)


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
        raise BybitExecutionQualityCaptureError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitExecutionQualityCaptureError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitExecutionQualityCaptureError(f"{field}_timezone_missing")
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
        "credentials_required",
        "method",
        "path",
        "private_data",
        "query",
        "research_only",
    }:
        raise BybitExecutionQualityCaptureError("captured_request_schema_invalid")
    query = value.get("query")
    if not isinstance(query, list) or not query:
        raise BybitExecutionQualityCaptureError("captured_request_query_invalid")
    pairs: list[tuple[str, str]] = []
    for pair in query:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(item, str) and item for item in pair)
        ):
            raise BybitExecutionQualityCaptureError(
                "captured_request_query_invalid"
            )
        pairs.append((pair[0], pair[1]))
    request = BybitPublicRequest(
        method=str(value.get("method") or ""),
        path=str(value.get("path") or ""),
        query=tuple(pairs),
        credentials_required=value.get("credentials_required") is True,
        private_data=value.get("private_data") is True,
        research_only=value.get("research_only") is True,
    )
    if _request_values(request) != dict(value):
        raise BybitExecutionQualityCaptureError("captured_request_schema_invalid")
    return request


def _eligible_from_values(value: Mapping[str, object]) -> BybitEligibleInstrument:
    try:
        return BybitEligibleInstrument(
            canonical_asset_id=str(value["canonical_asset_id"]),
            radar_symbol=str(value["radar_symbol"]),
            liquidity_rank=int(value["liquidity_rank"]),
            instrument_id=str(value["instrument_id"]),
            base_asset=str(value["base_asset"]),
            quote_asset=str(value["quote_asset"]),
            settle_asset=str(value["settle_asset"]),
            contract_type=str(value["contract_type"]),
            status=str(value["status"]),
            tick_size=str(value["tick_size"]),
            quantity_step=str(value["quantity_step"]),
            minimum_order_quantity=str(value["minimum_order_quantity"]),
            maximum_limit_order_quantity=str(
                value["maximum_limit_order_quantity"]
            ),
            maximum_market_order_quantity=str(
                value["maximum_market_order_quantity"]
            ),
            minimum_notional_value_usdt=str(
                value["minimum_notional_value_usdt"]
            ),
            launch_time_ms=int(value["launch_time_ms"]),
            delivery_time_ms=int(value["delivery_time_ms"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BybitExecutionQualityCaptureError(
            "eligible_instrument_schema_invalid"
        ) from exc


def _response_values(
    response: BybitCapturedJSONResponse,
    *,
    index: int,
    raw_filename: str,
) -> dict[str, object]:
    started = _utc_datetime(response.request_started_at, "request_started_at")
    received = _utc_datetime(response.response_received_at, "response_received_at")
    if received < started or isinstance(response.duration_ms, bool):
        raise BybitExecutionQualityCaptureError("captured_response_timing_invalid")
    if response.duration_ms < 0 or response.duration_ms > 120_000:
        raise BybitExecutionQualityCaptureError("captured_response_duration_invalid")
    response_limit = (
        MAX_RESPONSE_BYTES
        if response.request.path == INSTRUMENTS_PATH
        else MAX_STANDARD_RESPONSE_BYTES
    )
    if (
        response.transport_contract != TRANSPORT_CONTRACT
        or response.http_status != 200
        or response.content_type.casefold() not in {"application/json", "text/json"}
        or response.response_url != _request_url(response.request)
        or response.request.method != "GET"
        or response.request.credentials_required
        or response.request.private_data
        or not response.request.research_only
        or not response.raw_bytes
        or len(response.raw_bytes) > response_limit
    ):
        raise BybitExecutionQualityCaptureError(
            "captured_response_transport_contract_invalid"
        )
    response.payload()
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


def _validated_summary_components(
    summary: Mapping[str, object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> tuple[
    str,
    str,
    dict[str, object],
    list[object],
    list[object],
    list[object],
    list[object],
    list[object],
]:
    if (
        set(summary) != _LIVE_SUMMARY_KEYS
        or summary.get("contract_version") != _LIVE_CONTRACT_VERSION
        or summary.get("row_type")
        != "decision_radar_bybit_execution_quality_observation_set"
        or summary.get("status") != "complete"
        or summary.get("venue_id") != "bybit"
        or summary.get("execution_mode") != "perpetual"
        or summary.get("category") != BYBIT_CATEGORY
        or summary.get("quote_asset") != QUOTE_ASSET
        or summary.get("source_base_url") != PUBLIC_API_BASE
        or summary.get("instrument_contract") != CONTRACT_TYPE
        or summary.get("instrument_status") != INSTRUMENT_STATUS
        or summary.get("provider_call_authorized") is not True
        or summary.get("provider_call_attempted") is not True
        or summary.get("provider_request_succeeded") is not True
        or summary.get("provider_request_strategy") != REQUEST_STRATEGY
        or summary.get("instrument_catalog_request_count") != 1
        or summary.get("research_only") is not True
        or summary.get("no_send") is not True
        or summary.get("orders_available") is not False
        or summary.get("credentials_read") is not False
        or summary.get("private_data_read") is not False
        or summary.get("artifact_persisted") is not False
        or summary.get("campaign_attached") is not False
        or summary.get("evidence_authority_eligible") is not False
        or summary.get("protocol_v2_evidence_eligible") is not False
        or summary.get("writes_performed") is not False
        or any(
            summary.get(field) != 0
            for field in (
                "normal_rsi_signal_rows_written",
                "paper_trades_created",
                "telegram_sends",
                "trades_created",
                "triggered_fade_created",
            )
        )
        or summary.get("retries") != 0
        or summary.get("redirects_followed") != 0
    ):
        raise BybitExecutionQualityCaptureError("capture_summary_contract_invalid")
    started_at = _utc_text(summary.get("started_at"), "capture_started_at")
    completed_at = _utc_text(summary.get("completed_at"), "capture_completed_at")
    if _utc_datetime(completed_at, "capture_completed_at") < _utc_datetime(
        started_at, "capture_started_at"
    ):
        raise BybitExecutionQualityCaptureError("capture_clock_invalid")
    source_authority = summary.get("source_authority")
    radar_assets = summary.get("radar_assets")
    provider_query_assets = summary.get("provider_query_assets")
    preflight_excluded_assets = summary.get("preflight_excluded_assets")
    eligible_values = summary.get("eligible_instruments")
    snapshot_values = summary.get("execution_quality_snapshots")
    if (
        not isinstance(source_authority, Mapping)
        or not isinstance(radar_assets, list)
        or not 0 < len(radar_assets) <= 30
        or not isinstance(provider_query_assets, list)
        or not provider_query_assets
        or not isinstance(preflight_excluded_assets, list)
        or not isinstance(eligible_values, list)
        or not eligible_values
        or not isinstance(snapshot_values, list)
    ):
        raise BybitExecutionQualityCaptureError("capture_evidence_sets_invalid")
    authority_keys = {
        "artifact_namespace",
        "authority_checked_at",
        "operator_state_sha256",
        "revision",
        "run_id",
    }
    if set(source_authority) != authority_keys:
        raise BybitExecutionQualityCaptureError("source_authority_schema_invalid")
    if (
        not isinstance(source_authority.get("artifact_namespace"), str)
        or not isinstance(source_authority.get("run_id"), str)
        or type(source_authority.get("revision")) is not int
        or not _SHA256_RE.fullmatch(
            str(source_authority.get("operator_state_sha256") or "")
        )
    ):
        raise BybitExecutionQualityCaptureError("source_authority_identity_invalid")
    _utc_text(source_authority.get("authority_checked_at"), "authority_checked_at")
    try:
        expected_query_assets, expected_excluded_assets = (
            require_provider_query_assets(radar_assets)  # type: ignore[arg-type]
        )
    except BybitExecutionQualityUniverseError as exc:
        raise BybitExecutionQualityCaptureError(exc.reason_code) from exc
    if (
        len(responses) > MAX_RESPONSES
        or summary.get("provider_request_count") != len(responses)
        or summary.get("requested_radar_asset_count") != len(radar_assets)
        or summary.get("provider_query_asset_count") != len(provider_query_assets)
        or summary.get("preflight_excluded_asset_count")
        != len(preflight_excluded_assets)
        or summary.get("eligible_instrument_count") != len(eligible_values)
        or summary.get("execution_quality_snapshot_count") != len(snapshot_values)
        or summary.get("orderbook_request_count") != len(snapshot_values)
        or len(snapshot_values) != len(eligible_values)
        or len(responses) != 1 + len(eligible_values)
        or summary.get("provider_request_bound") != len(provider_query_assets) + 1
        or provider_query_assets != list(expected_query_assets)
        or preflight_excluded_assets != list(expected_excluded_assets)
    ):
        raise BybitExecutionQualityCaptureError("capture_count_contract_invalid")

    radar_assets = _canonical_value(radar_assets)
    provider_query_assets = _canonical_value(provider_query_assets)
    preflight_excluded_assets = _canonical_value(preflight_excluded_assets)
    eligible_values = _canonical_value(eligible_values)
    snapshot_values = _canonical_value(snapshot_values)
    if (
        not isinstance(radar_assets, list)
        or not isinstance(provider_query_assets, list)
        or not isinstance(preflight_excluded_assets, list)
        or not isinstance(eligible_values, list)
        or not isinstance(snapshot_values, list)
    ):
        raise BybitExecutionQualityCaptureError("capture_evidence_sets_invalid")
    return (
        started_at,
        completed_at,
        dict(source_authority),
        radar_assets,
        provider_query_assets,
        preflight_excluded_assets,
        eligible_values,
        snapshot_values,
    )


def _validate_capture_inputs(
    summary: Mapping[str, object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> dict[str, object]:
    (
        started_at,
        completed_at,
        source_authority,
        radar_assets,
        provider_query_assets,
        preflight_excluded_assets,
        eligible_values,
        snapshot_values,
    ) = _validated_summary_components(summary, responses)

    try:
        require_exact_response_window(
            responses,
            started_at=_utc_datetime(started_at, "capture_started_at"),
            completed_at=_utc_datetime(completed_at, "capture_completed_at"),
        )
    except _BybitExecutionQualitySetFreshnessError as exc:
        raise BybitExecutionQualityCaptureError(exc.reason_code) from exc

    request_rows: list[dict[str, object]] = []
    raw_rows: list[tuple[str, bytes]] = []
    catalog_request = build_bybit_instrument_catalog_request()
    catalog_response = responses[0]
    if catalog_response.request != catalog_request:
        raise BybitExecutionQualityCaptureError("instrument_request_order_drift")
    catalog_filename = "raw_001_instrument_catalog.json"
    request_rows.append(
        _response_values(
            catalog_response,
            index=1,
            raw_filename=catalog_filename,
        )
    )
    raw_rows.append((catalog_filename, catalog_response.raw_bytes))
    try:
        selected = list(
            select_bybit_usdt_perpetual_instruments(
                provider_query_assets,  # type: ignore[arg-type]
                catalog_response.payload(),
            )
        )
    except BybitExecutionQualityError as exc:
        raise BybitExecutionQualityCaptureError(
            "instrument_response_contract_invalid"
        ) from exc

    selected_values = _canonical_value([row.to_dict() for row in selected])
    if selected_values != eligible_values:
        raise BybitExecutionQualityCaptureError("eligible_instrument_projection_drift")

    reconstructed_snapshots: list[dict[str, object]] = []
    for offset, (instrument, expected_snapshot) in enumerate(
        zip(selected, snapshot_values, strict=True),
        start=2,
    ):
        if not isinstance(expected_snapshot, Mapping):
            raise BybitExecutionQualityCaptureError(
                "execution_quality_snapshot_schema_invalid"
            )
        response = responses[offset - 1]
        expected = build_bybit_orderbook_request(instrument)
        if response.request != expected:
            raise BybitExecutionQualityCaptureError("orderbook_request_order_drift")
        if not exact_response_acquisition_matches(expected_snapshot, response):
            raise BybitExecutionQualityCaptureError(
                "snapshot_acquisition_response_clock_mismatch"
            )
        raw_filename = f"raw_{offset:03d}_orderbook_{instrument.instrument_id}.json"
        request_rows.append(
            _response_values(response, index=offset, raw_filename=raw_filename)
        )
        raw_rows.append((raw_filename, response.raw_bytes))
        try:
            reconstructed = normalize_bybit_orderbook(
                response.payload(),
                instrument=instrument,
                acquired_at=str(expected_snapshot.get("acquired_at") or ""),
                request_lineage_id=str(
                    expected_snapshot.get("request_lineage_id") or ""
                ),
            ).to_dict()
        except BybitExecutionQualityError as exc:
            raise BybitExecutionQualityCaptureError(
                "orderbook_response_contract_invalid"
            ) from exc
        reconstructed_snapshots.append(reconstructed)
    if _canonical_value(reconstructed_snapshots) != snapshot_values:
        raise BybitExecutionQualityCaptureError(
            "execution_quality_snapshot_projection_drift"
        )

    try:
        freshness = project_execution_quality_set_freshness(
            snapshot_values,  # type: ignore[arg-type]
            completed_at=_utc_datetime(completed_at, "capture_completed_at"),
        )
    except _BybitExecutionQualitySetFreshnessError as exc:
        raise BybitExecutionQualityCaptureError(exc.reason_code) from exc
    if not live_summary_freshness_matches(summary, freshness):
        raise BybitExecutionQualityCaptureError(
            "execution_quality_freshness_summary_mismatch"
        )
    return {
        "started_at": started_at,
        "completed_at": completed_at,
        "source_authority": source_authority,
        "radar_assets": radar_assets,
        "provider_query_assets": provider_query_assets,
        "preflight_excluded_assets": preflight_excluded_assets,
        "eligible_instruments": eligible_values,
        "execution_quality_snapshots": snapshot_values,
        "request_rows": request_rows,
        "raw_rows": raw_rows,
        **prepared_freshness_values(freshness),
        "evidence_authority_eligible": True,
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
    }


def _source_summary_from_persisted(
    value: Mapping[str, object],
) -> dict[str, object]:
    if (
        set(value) != _LIVE_SUMMARY_KEYS | _PERSISTED_SUMMARY_EXTRA_KEYS
        or value.get("capture_contract_version") != CONTRACT_VERSION
        or not _SHA256_RE.fullmatch(str(value.get("capture_id") or ""))
        or not _NAMESPACE_RE.fullmatch(str(value.get("artifact_namespace") or ""))
        or value.get("artifact_persisted") is not True
        or value.get("campaign_attached") is not False
        or value.get("evidence_authority_eligible") is not True
        or value.get("protocol_v2_evidence_eligible") is not False
        or type(value.get("protocol_v2_input_quality_eligible")) is not bool
        or value.get("protocol_v2_annex_bound") is not False
        or value.get("writes_performed") is not True
    ):
        raise BybitExecutionQualityCaptureError(
            "capture_persisted_summary_contract_invalid"
        )
    source = {key: value[key] for key in _LIVE_SUMMARY_KEYS}
    source.update(
        {
            "artifact_persisted": False,
            "campaign_attached": False,
            "evidence_authority_eligible": False,
            "protocol_v2_evidence_eligible": False,
            "writes_performed": False,
        }
    )
    return source


def _artifact_descriptor(name: str, role: str, raw: bytes) -> dict[str, object]:
    return {"name": name, "role": role, **_fingerprint(raw)}


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
                raise BybitExecutionQualityCaptureError("capture_lock_invalid")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            yield
    except BybitExecutionQualityCaptureError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise BybitExecutionQualityCaptureError("capture_lock_unavailable") from exc
    finally:
        if locked and descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        if descriptor is not None:
            os.close(descriptor)


def _capture_file_payloads(
    summary: Mapping[str, object],
    prepared: Mapping[str, object],
    *,
    namespace: str,
    capture_id: str,
) -> list[tuple[str, str, bytes]]:
    source_values = {
        "schema_id": "decision_radar.bybit_execution_quality_source_authority",
        "schema_version": 1,
        "capture_id": capture_id,
        **prepared["source_authority"],
        "research_only": True,
    }
    universe_values = build_capture_universe_values(
        capture_id=capture_id,
        radar_assets=prepared["radar_assets"],
        provider_query_assets=prepared["provider_query_assets"],
        preflight_excluded_assets=prepared["preflight_excluded_assets"],
    )
    observation_values = {
        "schema_id": "decision_radar.bybit_execution_quality_observations",
        "schema_version": 2,
        "capture_id": capture_id,
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "notional_currency": QUOTE_ASSET,
        "observation_count": len(prepared["execution_quality_snapshots"]),
        "observations": prepared["execution_quality_snapshots"],
        **observation_freshness_values(prepared),
        "research_only": True,
    }
    request_values = {
        "schema_id": "decision_radar.bybit_execution_quality_request_index",
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
    persisted_summary = dict(_canonical_value(dict(summary)))
    persisted_summary.update(
        {
            "capture_contract_version": CONTRACT_VERSION,
            "capture_id": capture_id,
            "artifact_namespace": namespace,
            "artifact_persisted": True,
            "campaign_attached": False,
            "evidence_authority_eligible": True,
            "protocol_v2_evidence_eligible": False,
            "protocol_v2_input_quality_eligible": prepared[
                "protocol_v2_input_quality_eligible"
            ],
            "protocol_v2_annex_bound": False,
            "writes_performed": True,
        }
    )
    payloads = [
        (AUTHORITY_FILENAME, "source_authority", _pretty_bytes(source_values)),
        (UNIVERSE_FILENAME, "radar_universe", _pretty_bytes(universe_values)),
        (SUMMARY_FILENAME, "capture_summary", _pretty_bytes(persisted_summary)),
        (REQUEST_INDEX_FILENAME, "request_index", _pretty_bytes(request_values)),
        (
            OBSERVATIONS_FILENAME,
            "execution_quality_observations",
            _pretty_bytes(observation_values),
        ),
    ]
    payloads.extend(
        (name, "accepted_raw_provider_response", raw)
        for name, raw in prepared["raw_rows"]
    )
    return payloads


def _capture_publication_values(
    prepared: Mapping[str, object],
    *,
    namespace: str,
    capture_id: str,
    descriptors: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    common = {
        "contract_version": CONTRACT_VERSION,
        "capture_id": capture_id,
        "artifact_namespace": namespace,
        "completed_at": prepared["completed_at"],
        "source_authority": prepared["source_authority"],
        "request_count": len(prepared["request_rows"]),
        "observation_count": len(prepared["execution_quality_snapshots"]),
        "evidence_authority_eligible": True,
        "protocol_v2_evidence_eligible": False,
        **common_freshness_values(prepared),
        "protocol_v2_annex_bound": False,
        "campaign_attached": False,
        "research_only": True,
    }
    manifest = {
        "schema_id": "decision_radar.bybit_execution_quality_capture_manifest",
        "schema_version": 2,
        **common,
        "started_at": prepared["started_at"],
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "quote_asset": QUOTE_ASSET,
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
        "schema_id": "decision_radar.bybit_execution_quality_completion_receipt",
        "schema_version": 2,
        "status": "complete",
        **common,
        "manifest": {"name": MANIFEST_FILENAME, **_fingerprint(manifest_raw)},
    }
    receipt_raw = _pretty_bytes(receipt)
    pointer = {
        "schema_id": "decision_radar.bybit_execution_quality_latest_pointer",
        "schema_version": 2,
        "status": "complete",
        **common,
        "receipt": {"name": RECEIPT_FILENAME, **_fingerprint(receipt_raw)},
    }
    return manifest, receipt, pointer


def persist_bybit_execution_quality_capture(
    artifact_base_dir: str | Path,
    *,
    summary: Mapping[str, object],
    responses: Sequence[BybitCapturedJSONResponse],
) -> dict[str, object]:
    """Seal and point to one complete exact-response capture."""

    base = Path(artifact_base_dir).expanduser().absolute()
    prepared = _validate_capture_inputs(summary, responses)
    namespace, capture_id = _execution_capture_namespace(prepared)
    namespace_dir = base / namespace
    if not _NAMESPACE_RE.fullmatch(namespace):
        raise BybitExecutionQualityCaptureError("capture_namespace_invalid")

    file_payloads = _capture_file_payloads(
        summary, prepared, namespace=namespace, capture_id=capture_id
    )
    descriptors = [
        _artifact_descriptor(name, role, raw) for name, role, raw in file_payloads
    ]
    manifest, receipt, pointer = _capture_publication_values(
        prepared,
        namespace=namespace,
        capture_id=capture_id,
        descriptors=descriptors,
    )

    with _publication_lock(base):
        existing_raw = read_regular_bytes(base / POINTER_FILENAME, missing_ok=True)
        if existing_raw is not None:
            existing = validate_bybit_execution_quality_pointer_bytes(existing_raw)
            existing_namespace = str(existing.get("artifact_namespace") or "")
            validated_existing = validate_bybit_execution_quality_capture(
                base,
                namespace=existing_namespace,
                pointer=existing,
            )
            if _utc_datetime(
                validated_existing.get("completed_at"), "existing_completed_at"
            ) > _utc_datetime(prepared["completed_at"], "capture_completed_at"):
                raise BybitExecutionQualityCaptureError("capture_pointer_rollback_rejected")
        ensure_safe_namespace_dir(namespace_dir)
        try:
            for name, _role, raw in file_payloads:
                write_bytes_immutable(namespace_dir / name, raw)
            write_json_immutable(namespace_dir / MANIFEST_FILENAME, manifest)
            write_json_immutable(namespace_dir / RECEIPT_FILENAME, receipt)
        except MarketNoSendError as exc:
            raise BybitExecutionQualityCaptureError("capture_immutable_write_failed") from exc
        validate_bybit_execution_quality_capture(base, namespace=namespace)
        try:
            write_json_atomic(base / POINTER_FILENAME, pointer)
        except MarketNoSendError as exc:
            raise BybitExecutionQualityCaptureError("capture_pointer_write_failed") from exc
        validated = load_latest_bybit_execution_quality_capture(base)
    return validated


def _parse_artifact_json(raw: bytes) -> dict[str, Any]:
    from .bybit_execution_quality_capture_validation import parse_artifact_json

    return parse_artifact_json(raw)


def validate_bybit_execution_quality_pointer_bytes(raw: bytes) -> dict[str, Any]:
    """Parse the closed latest-pointer schema without reading its namespace."""

    from .bybit_execution_quality_capture_validation import (
        validate_capture_pointer_bytes,
    )

    return validate_capture_pointer_bytes(raw)


def _validate_capture_contracts(
    namespace: str,
    *,
    receipt: Mapping[str, object],
    receipt_raw: bytes,
    manifest: Mapping[str, object],
    manifest_raw: bytes,
    pointer: Mapping[str, object] | None = None,
) -> Mapping[str, object] | None:
    from .bybit_execution_quality_capture_validation import (
        validate_capture_contracts,
    )

    return validate_capture_contracts(
        namespace,
        receipt=receipt,
        receipt_raw=receipt_raw,
        manifest=manifest,
        manifest_raw=manifest_raw,
        pointer=pointer,
    )


def _capture_projections(
    artifacts: Mapping[str, bytes],
    roles: Mapping[str, str],
    *,
    capture_id: object,
) -> dict[str, object]:
    summary = _parse_artifact_json(artifacts[SUMMARY_FILENAME])
    request_index = _parse_artifact_json(artifacts[REQUEST_INDEX_FILENAME])
    observations = _parse_artifact_json(artifacts[OBSERVATIONS_FILENAME])
    universe = _parse_artifact_json(artifacts[UNIVERSE_FILENAME])
    authority = _parse_artifact_json(artifacts[AUTHORITY_FILENAME])
    if (
        set(authority)
        != {
            "artifact_namespace",
            "authority_checked_at",
            "capture_id",
            "operator_state_sha256",
            "research_only",
            "revision",
            "run_id",
            "schema_id",
            "schema_version",
        }
        or authority.get("schema_id")
        != "decision_radar.bybit_execution_quality_source_authority"
        or authority.get("schema_version") != 1
        or authority.get("capture_id") != capture_id
        or authority.get("research_only") is not True
        or not capture_universe_projection_valid(
            universe,
            capture_id=capture_id,
        )
        or set(observations)
        != {
            "all_fresh",
            "all_fresh_at_acquisition",
            "all_fresh_at_completion",
            "capture_id",
            "execution_mode",
            "freshness_policy",
            "maximum_age_at_completion_seconds",
            "maximum_age_policy_seconds",
            "notional_currency",
            "observation_count",
            "observations",
            "research_only",
            "schema_id",
            "schema_version",
            "venue_id",
        }
        or observations.get("schema_id")
        != "decision_radar.bybit_execution_quality_observations"
        or observations.get("schema_version") != 2
        or observations.get("capture_id") != capture_id
        or observations.get("venue_id") != "bybit"
        or observations.get("execution_mode") != "perpetual"
        or observations.get("notional_currency") != QUOTE_ASSET
        or not observation_freshness_contract_valid(observations)
        or observations.get("research_only") is not True
        or set(request_index)
        != {
            "capture_id",
            "credentials_read",
            "private_data_read",
            "redirects_followed",
            "request_count",
            "requests",
            "research_only",
            "retries",
            "schema_id",
            "schema_version",
        }
        or request_index.get("schema_id")
        != "decision_radar.bybit_execution_quality_request_index"
        or request_index.get("schema_version") != 1
        or request_index.get("capture_id") != capture_id
        or request_index.get("research_only") is not True
    ):
        raise BybitExecutionQualityCaptureError(
            "capture_projection_contract_invalid"
        )
    request_rows = request_index.get("requests")
    if (
        not isinstance(request_rows, list)
        or request_index.get("request_count") != len(request_rows)
        or request_index.get("retries") != 0
        or request_index.get("redirects_followed") != 0
        or request_index.get("credentials_read") is not False
        or request_index.get("private_data_read") is not False
    ):
        raise BybitExecutionQualityCaptureError("capture_request_index_invalid")
    responses: list[BybitCapturedJSONResponse] = []
    for index, row in enumerate(request_rows, start=1):
        if (
            not isinstance(row, Mapping)
            or set(row) != _REQUEST_ROW_KEYS
            or row.get("sequence") != index
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
            raise BybitExecutionQualityCaptureError("capture_request_index_invalid")
        raw_name = str(row.get("raw_artifact") or "")
        if raw_name not in artifacts or roles.get(raw_name) != "accepted_raw_provider_response":
            raise BybitExecutionQualityCaptureError("capture_raw_response_missing")
        responses.append(
            BybitCapturedJSONResponse(
                request=_request_from_values(row.get("request")),
                request_started_at=row["request_started_at"],
                response_received_at=row["response_received_at"],
                duration_ms=row["duration_ms"],
                response_url=row["request_url"],
                http_status=row["http_status"],
                content_type=row["content_type"],
                raw_bytes=artifacts[raw_name],
                transport_contract=row["transport_contract"],
            )
        )
    return {
        "summary": summary,
        "request_rows": request_rows,
        "responses": responses,
        "observations": observations,
        "universe": universe,
        "authority": authority,
    }


def _validate_capture_semantics(
    namespace: str,
    *,
    receipt: Mapping[str, object],
    manifest: Mapping[str, object],
    pointer: Mapping[str, object] | None,
    artifacts: Mapping[str, bytes],
    projections: Mapping[str, object],
) -> dict[str, object]:
    summary = projections["summary"]
    request_rows = projections["request_rows"]
    responses = projections["responses"]
    observations = projections["observations"]
    universe = projections["universe"]
    authority = projections["authority"]
    capture_id = receipt.get("capture_id")
    if (
        not isinstance(summary, Mapping)
        or not isinstance(request_rows, list)
        or not isinstance(responses, list)
        or not isinstance(observations, Mapping)
        or not isinstance(universe, Mapping)
        or not isinstance(authority, Mapping)
    ):
        raise BybitExecutionQualityCaptureError("capture_projection_contract_invalid")
    source_summary = _source_summary_from_persisted(summary)
    prepared = _validate_capture_inputs(source_summary, responses)
    derived_namespace, derived_capture_id = _execution_capture_namespace(prepared)
    if (
        derived_namespace != namespace
        or derived_capture_id != capture_id
        or len(artifacts) != len(responses) + 5
        or prepared["request_rows"] != request_rows
        or summary.get("capture_id") != capture_id
        or summary.get("artifact_namespace") != namespace
        or not prepared_summary_freshness_matches(summary, prepared)
        or universe.get("asset_count") != len(prepared["radar_assets"])
        or universe.get("assets") != prepared["radar_assets"]
        or universe.get("provider_query_asset_count")
        != len(prepared["provider_query_assets"])
        or universe.get("provider_query_assets")
        != prepared["provider_query_assets"]
        or universe.get("preflight_excluded_asset_count")
        != len(prepared["preflight_excluded_assets"])
        or universe.get("preflight_excluded_assets")
        != prepared["preflight_excluded_assets"]
        or observations.get("observation_count")
        != len(prepared["execution_quality_snapshots"])
        or observations.get("observations")
        != prepared["execution_quality_snapshots"]
        or not observation_freshness_matches(observations, prepared)
        or authority.get("capture_id") != receipt.get("capture_id")
        or {
            key: authority.get(key)
            for key in (
                "artifact_namespace",
                "authority_checked_at",
                "operator_state_sha256",
                "revision",
                "run_id",
            )
        }
        != prepared["source_authority"]
        or manifest.get("capture_id") != derived_capture_id
        or manifest.get("started_at") != prepared["started_at"]
        or manifest.get("completed_at") != prepared["completed_at"]
        or manifest.get("venue_id") != "bybit"
        or manifest.get("execution_mode") != "perpetual"
        or manifest.get("quote_asset") != QUOTE_ASSET
        or manifest.get("source_authority") != prepared["source_authority"]
        or manifest.get("request_count") != len(responses)
        or manifest.get("observation_count")
        != len(prepared["execution_quality_snapshots"])
        or manifest.get("protocol_v2_evidence_eligible")
        is not prepared["protocol_v2_evidence_eligible"]
        or not common_freshness_matches(manifest, prepared)
        or manifest.get("protocol_v2_annex_bound") is not False
        or receipt.get("capture_id") != derived_capture_id
        or receipt.get("completed_at") != prepared["completed_at"]
        or receipt.get("request_count") != len(responses)
        or receipt.get("observation_count")
        != len(prepared["execution_quality_snapshots"])
        or receipt.get("source_authority") != prepared["source_authority"]
        or receipt.get("protocol_v2_evidence_eligible")
        is not prepared["protocol_v2_evidence_eligible"]
        or not common_freshness_matches(receipt, prepared)
        or (
            pointer is not None
            and (
                pointer.get("request_count") != len(responses)
                or pointer.get("completed_at") != prepared["completed_at"]
                or pointer.get("observation_count")
                != len(prepared["execution_quality_snapshots"])
                or pointer.get("source_authority") != prepared["source_authority"]
                or pointer.get("protocol_v2_evidence_eligible")
                is not prepared["protocol_v2_evidence_eligible"]
                or not common_freshness_matches(pointer, prepared)
            )
        )
    ):
        raise BybitExecutionQualityCaptureError("capture_semantic_drift")
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "complete",
        "capture_id": receipt["capture_id"],
        "artifact_namespace": namespace,
        "completed_at": receipt["completed_at"],
        "source_authority": prepared["source_authority"],
        "eligible_instruments": prepared["eligible_instruments"],
        "request_count": len(responses),
        "observation_count": len(prepared["execution_quality_snapshots"]),
        "evidence_authority_eligible": True,
        "protocol_v2_evidence_eligible": prepared[
            "protocol_v2_evidence_eligible"
        ],
        **common_freshness_values(prepared),
        "protocol_v2_annex_bound": False,
        "campaign_attached": False,
        "pointer_validated": pointer is not None,
        "research_only": True,
        "no_send": True,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
    }


def validate_bybit_execution_quality_capture(
    artifact_base_dir: str | Path,
    *,
    namespace: str,
    pointer: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate one immutable capture and rederive projections from raw bytes."""

    from .bybit_execution_quality_capture_validation import read_capture_bundle

    if not _NAMESPACE_RE.fullmatch(namespace):
        raise BybitExecutionQualityCaptureError("capture_namespace_invalid")
    base = Path(artifact_base_dir).expanduser().absolute()
    (
        receipt,
        receipt_raw,
        manifest,
        manifest_raw,
        artifacts,
        roles,
    ) = read_capture_bundle(base / namespace)
    validated_pointer = _validate_capture_contracts(
        namespace,
        receipt=receipt,
        receipt_raw=receipt_raw,
        manifest=manifest,
        manifest_raw=manifest_raw,
        pointer=pointer,
    )
    projections = _capture_projections(
        artifacts,
        roles,
        capture_id=receipt.get("capture_id"),
    )
    return _validate_capture_semantics(
        namespace,
        receipt=receipt,
        manifest=manifest,
        pointer=validated_pointer,
        artifacts=artifacts,
        projections=projections,
    )


def load_latest_bybit_execution_quality_capture(
    artifact_base_dir: str | Path,
) -> dict[str, object]:
    base = Path(artifact_base_dir).expanduser().absolute()
    try:
        raw = read_regular_bytes(base / POINTER_FILENAME, missing_ok=True)
    except MarketNoSendError as exc:
        raise BybitExecutionQualityCaptureError("capture_pointer_unreadable") from exc
    if raw is None:
        raise BybitExecutionQualityCaptureError("capture_pointer_missing")
    pointer = validate_bybit_execution_quality_pointer_bytes(raw)
    namespace = str(pointer.get("artifact_namespace") or "")
    validated = validate_bybit_execution_quality_capture(
        base, namespace=namespace, pointer=pointer
    )
    try:
        final_raw = read_regular_bytes(base / POINTER_FILENAME)
    except MarketNoSendError as exc:
        raise BybitExecutionQualityCaptureError("capture_pointer_unreadable") from exc
    if final_raw != raw:
        raise BybitExecutionQualityCaptureError("capture_pointer_changed_during_read")
    validated["pointer_sha256"] = _sha256(raw)
    return validated


def bybit_execution_quality_capture_status(
    artifact_base_dir: str | Path,
) -> dict[str, object]:
    try:
        return load_latest_bybit_execution_quality_capture(artifact_base_dir)
    except BybitExecutionQualityCaptureError as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "unavailable",
            "reason": str(exc),
            "evidence_authority_eligible": False,
            "protocol_v2_evidence_eligible": False,
            "protocol_v2_input_quality_eligible": False,
            "protocol_v2_annex_bound": False,
            "campaign_attached": False,
            "eligible_instruments": [],
            "provider_call_attempted": False,
            "writes_performed": False,
            "research_only": True,
            "no_send": True,
            "orders": 0,
            "trades": 0,
            "paper_trades": 0,
            "pointer_sha256": None,
            "normal_rsi_writes": 0,
            "event_alpha_triggered_fade": 0,
        }


__all__ = (
    "CONTRACT_VERSION",
    "POINTER_FILENAME",
    "TRANSPORT_CONTRACT",
    "BybitCapturedJSONResponse",
    "BybitExecutionQualityCaptureError",
    "bybit_execution_quality_capture_status",
    "load_latest_bybit_execution_quality_capture",
    "persist_bybit_execution_quality_capture",
    "validate_bybit_execution_quality_pointer_bytes",
    "validate_bybit_execution_quality_capture",
)
