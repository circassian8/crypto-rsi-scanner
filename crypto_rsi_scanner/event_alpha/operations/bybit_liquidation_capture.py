"""Detached immutable capture for operator-supplied Bybit liquidation transcripts.

The input is an exact, local transcript of WebSocket *application payloads* for
one Bybit USDT-linear perpetual.  This module never opens a socket, reads an
environment variable, calls a provider, publishes a latest pointer, or grants
campaign/dashboard/Protocol-v2 authority.  It preserves the exact transcript
and every decoded application payload, then rederives liquidation events with
the closed normalizer in :mod:`bybit_liquidation_stream`.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping, Sequence

from .bybit_execution_quality import (
    BYBIT_CATEGORY,
    CONTRACT_TYPE,
    EXECUTION_MODE,
    INSTRUMENT_STATUS,
    QUOTE_ASSET,
    VENUE_ID,
)
from .bybit_liquidation_stream import (
    PUBLIC_WEBSOCKET_URL,
    TOPIC_PREFIX,
    BybitLiquidationStreamError,
    normalize_bybit_liquidation_message,
)
from . import bybit_liquidation_capture_io as capture_io


CONTRACT_VERSION = "crypto_radar_bybit_liquidation_capture_v1"
TRANSCRIPT_SCHEMA_ID = "decision_radar.bybit_liquidation_operator_transcript"
APPLICATION_PAYLOAD_SCOPE = "websocket_application_payload_bytes_only"
COVERAGE_STATUS = "observed_messages_only"
SOURCE_FILENAME = "source_transcript.json"
LEDGER_FILENAME = "transcript_ledger.json"
EVENTS_FILENAME = "normalized_liquidation_events.json"
MANIFEST_FILENAME = "capture_manifest.json"
RECEIPT_FILENAME = "capture_completion_receipt.json"
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_PAYLOAD_BYTES = 1_000_000
MAX_MESSAGES = 64
MAX_TOTAL_EVENTS = 1_024
MAX_CAPTURE_DURATION_SECONDS = 3_600
_NAMESPACE_RE = re.compile(
    r"^radar_bybit_liquidation_transcript_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ASSET_RE = re.compile(r"^[A-Z0-9]{2,24}$")
_CANONICAL_ASSET_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_FORBIDDEN_SOURCE_PARTS = frozenset(
    {"fixture", "fixtures", "mock", "mocks", "replay", "replays", "test", "tests"}
)
class BybitLiquidationCaptureError(RuntimeError):
    """Fail-closed local transcript or immutable-bundle error."""


@dataclass(frozen=True)
class _BybitLiquidationInstrumentIdentity:
    """The historical transcript's minimal identity, not an order contract."""

    canonical_asset_id: str
    radar_symbol: str
    liquidity_rank: int
    instrument_id: str
    base_asset: str
    quote_asset: str
    settle_asset: str
    contract_type: str
    status: str
    tick_size: str
    quantity_step: str
    launch_time_ms: int
    delivery_time_ms: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _decimal_occurrence_identity(value: object) -> tuple[int, str, int]:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BybitLiquidationCaptureError("liquidation_data_invalid") from exc
    sign, digits, exponent = parsed.as_tuple()
    while len(digits) > 1 and digits[-1] == 0:
        digits = digits[:-1]
        exponent += 1
    return sign, "".join(str(digit) for digit in digits), exponent


def _pretty_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fingerprint(raw: bytes) -> dict[str, object]:
    return {"sha256": _sha256(raw), "size_bytes": len(raw)}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BybitLiquidationCaptureError("json_duplicate_key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise BybitLiquidationCaptureError("json_non_finite_number")


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise BybitLiquidationCaptureError("json_non_finite_number")
    return parsed


def _parse_object(raw: bytes, *, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_json_float,
        )
    except BybitLiquidationCaptureError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
        RecursionError,
        OverflowError,
    ) as exc:
        raise BybitLiquidationCaptureError(reason) from exc
    if not isinstance(value, Mapping):
        raise BybitLiquidationCaptureError(reason)
    parsed = dict(value)
    try:
        decoded_projection = _canonical_bytes(parsed)
        capture_io.reject_secret_bytes(decoded_projection)
    except capture_io.BybitLiquidationCaptureIOError as exc:
        raise BybitLiquidationCaptureError(str(exc)) from exc
    except (RecursionError, OverflowError, ValueError) as exc:
        raise BybitLiquidationCaptureError(reason) from exc
    return parsed


def _utc_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BybitLiquidationCaptureError(f"{field}_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitLiquidationCaptureError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitLiquidationCaptureError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_datetime(value: object, field: str) -> datetime:
    return datetime.fromisoformat(_utc_text(value, field).replace("Z", "+00:00"))


def _instrument_from_values(value: object) -> _BybitLiquidationInstrumentIdentity:
    expected = {
        "base_asset",
        "canonical_asset_id",
        "contract_type",
        "delivery_time_ms",
        "instrument_id",
        "launch_time_ms",
        "liquidity_rank",
        "quantity_step",
        "quote_asset",
        "radar_symbol",
        "settle_asset",
        "status",
        "tick_size",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise BybitLiquidationCaptureError("instrument_schema_invalid")
    string_fields = expected - {
        "delivery_time_ms",
        "launch_time_ms",
        "liquidity_rank",
    }
    if any(not isinstance(value.get(field), str) for field in string_fields) or any(
        type(value.get(field)) is not int
        for field in ("delivery_time_ms", "launch_time_ms", "liquidity_rank")
    ):
        raise BybitLiquidationCaptureError("instrument_schema_invalid")
    try:
        instrument = _BybitLiquidationInstrumentIdentity(**dict(value))
    except (TypeError, ValueError) as exc:
        raise BybitLiquidationCaptureError("instrument_schema_invalid") from exc
    if (
        not _CANONICAL_ASSET_RE.fullmatch(instrument.canonical_asset_id)
        or not _ASSET_RE.fullmatch(instrument.base_asset)
        or instrument.radar_symbol != instrument.base_asset
        or instrument.instrument_id != f"{instrument.base_asset}{QUOTE_ASSET}"
        or instrument.quote_asset != QUOTE_ASSET
        or instrument.settle_asset != QUOTE_ASSET
        or instrument.contract_type != CONTRACT_TYPE
        or instrument.status != INSTRUMENT_STATUS
        or not 1 <= instrument.liquidity_rank <= 100
        or not 0 < instrument.launch_time_ms <= 32_503_680_000_000
        or instrument.delivery_time_ms != 0
    ):
        raise BybitLiquidationCaptureError("instrument_identity_invalid")
    for field in ("tick_size", "quantity_step"):
        try:
            number = float(getattr(instrument, field))
        except ValueError as exc:
            raise BybitLiquidationCaptureError("instrument_numeric_invalid") from exc
        if not math.isfinite(number) or number <= 0:
            raise BybitLiquidationCaptureError("instrument_numeric_invalid")
    return instrument


def _decode_base64(value: object) -> bytes:
    if not isinstance(value, str) or not value or len(value) > (MAX_PAYLOAD_BYTES * 2):
        raise BybitLiquidationCaptureError("application_payload_base64_invalid")
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise BybitLiquidationCaptureError("application_payload_base64_invalid") from exc
    if (
        not raw
        or len(raw) > MAX_PAYLOAD_BYTES
        or base64.b64encode(raw).decode("ascii") != value
    ):
        raise BybitLiquidationCaptureError("application_payload_base64_invalid")
    return raw


def _message_object(payload: bytes) -> dict[str, Any]:
    try:
        capture_io.reject_secret_bytes(payload)
    except capture_io.BybitLiquidationCaptureIOError as exc:
        raise BybitLiquidationCaptureError(str(exc)) from exc
    value = _parse_object(payload, reason="application_payload_json_invalid")
    if str(value.get("op") or "").casefold() == "auth":
        raise BybitLiquidationCaptureError("secret_or_auth_material_rejected")
    return value


def _subscribe_values(payload: bytes, *, topic: str) -> str | None:
    value = _message_object(payload)
    allowed = ({"args", "op"}, {"args", "op", "req_id"})
    request_id = value.get("req_id")
    if (
        set(value) not in allowed
        or value.get("op") != "subscribe"
        or value.get("args") != [topic]
        or (
            request_id is not None
            and (
                not isinstance(request_id, str)
                or not _TOKEN_RE.fullmatch(request_id)
            )
        )
    ):
        raise BybitLiquidationCaptureError("subscribe_payload_invalid")
    return request_id


def _ack_values(payload: bytes, *, request_id: str | None) -> None:
    value = _message_object(payload)
    required = {"conn_id", "op", "ret_msg", "success"}
    ack_request_id = value.get("req_id")
    if (
        frozenset(value) not in {frozenset(required), frozenset(required | {"req_id"})}
        or value.get("success") is not True
        or value.get("op") != "subscribe"
        or value.get("ret_msg") not in {"", "subscribe"}
        or not isinstance(value.get("conn_id"), str)
        or not _TOKEN_RE.fullmatch(value["conn_id"])
        or ("req_id" in value and not isinstance(ack_request_id, str))
        or (
            request_id is not None
            and ack_request_id != request_id
        )
        or (
            request_id is None
            and ack_request_id not in {None, ""}
        )
    ):
        raise BybitLiquidationCaptureError("subscribe_ack_invalid")


def _prepare_messages(
    messages: object,
    *,
    instrument: BybitEligibleInstrument,
    started: datetime,
    completed: datetime,
    lineage: str,
    capture_mode: str,
) -> tuple[str, list[dict[str, object]], list[dict[str, object]]]:
    if not isinstance(messages, list) or not 3 <= len(messages) <= MAX_MESSAGES:
        raise BybitLiquidationCaptureError("transcript_message_count_invalid")
    payload_rows: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    topic = f"{TOPIC_PREFIX}{instrument.instrument_id}"
    previous = started
    request_id: str | None = None
    data_payload_hashes: set[str] = set()
    canonical_event_occurrences: set[str] = set()
    previous_provider_message_at: datetime | None = None
    for sequence, message in enumerate(messages, start=1):
        if not isinstance(message, Mapping) or set(message) != {
            "direction",
            "observed_at",
            "payload_base64",
            "sequence",
        }:
            raise BybitLiquidationCaptureError("transcript_message_schema_invalid")
        if type(message.get("sequence")) is not int or message.get("sequence") != sequence:
            raise BybitLiquidationCaptureError("transcript_message_order_invalid")
        observed = _utc_datetime(message.get("observed_at"), "message_observed_at")
        if observed < previous or observed > completed:
            raise BybitLiquidationCaptureError("transcript_message_clock_invalid")
        previous = observed
        payload = _decode_base64(message.get("payload_base64"))
        if sequence == 1:
            if message.get("direction") != "client_to_server":
                raise BybitLiquidationCaptureError("subscribe_direction_invalid")
            request_id = _subscribe_values(payload, topic=topic)
            role = "client_subscribe"
        elif sequence == 2:
            if message.get("direction") != "server_to_client":
                raise BybitLiquidationCaptureError("subscribe_ack_direction_invalid")
            _ack_values(payload, request_id=request_id)
            role = "server_subscribe_ack"
        else:
            if message.get("direction") != "server_to_client":
                raise BybitLiquidationCaptureError("liquidation_data_direction_invalid")
            payload_sha = _sha256(payload)
            if payload_sha in data_payload_hashes:
                raise BybitLiquidationCaptureError("duplicate_data_payload_rejected")
            data_payload_hashes.add(payload_sha)
            message_value = _message_object(payload)
            try:
                normalized = normalize_bybit_liquidation_message(
                    payload,
                    instrument=instrument,
                    received_at=observed,
                    source_lineage_id=f"{lineage}.message{sequence:03d}",
                )
            except BybitLiquidationStreamError as exc:
                raise BybitLiquidationCaptureError(
                    f"liquidation_data_invalid:{exc}"
                ) from exc
            provider_rows = message_value.get("data")
            if not isinstance(provider_rows, list):
                raise BybitLiquidationCaptureError("liquidation_data_invalid")
            message_event_occurrences: set[str] = set()
            for provider_row, event in zip(provider_rows, normalized, strict=True):
                occurrence = _sha256(
                    _canonical_bytes(
                        {
                            "topic": event.topic,
                            "ts": event.message_emitted_at,
                            "T": event.liquidation_observed_at,
                            "s": event.instrument_id,
                            "S": event.provider_side,
                            "v": _decimal_occurrence_identity(provider_row.get("v")),
                            "p": _decimal_occurrence_identity(provider_row.get("p")),
                        }
                    )
                )
                if (
                    occurrence in message_event_occurrences
                    or occurrence in canonical_event_occurrences
                ):
                    raise BybitLiquidationCaptureError(
                        "duplicate_provider_occurrence_rejected"
                    )
                message_event_occurrences.add(occurrence)
            canonical_event_occurrences.update(message_event_occurrences)
            provider_message_at = _utc_datetime(
                normalized[0].message_emitted_at,
                "provider_message_emitted_at",
            )
            if (
                previous_provider_message_at is not None
                and provider_message_at < previous_provider_message_at
            ):
                raise BybitLiquidationCaptureError(
                    "provider_message_clock_regression"
                )
            previous_provider_message_at = provider_message_at
            if len(events) + len(normalized) > MAX_TOTAL_EVENTS:
                raise BybitLiquidationCaptureError("total_event_bound_exceeded")
            for event in normalized:
                event_value = event.to_dict()
                operator_supplied = capture_mode == "operator_import"
                event_value.update(
                    {
                        "canonical_identity_status": (
                            "operator_attested_unverified"
                            if operator_supplied
                            else "synthetic_unverified"
                        ),
                        "canonical_identity_verified": False,
                        "canonical_identity_attestation": (
                            "operator_supplied_transcript_only"
                            if operator_supplied
                            else "synthetic_smoke_only"
                        ),
                        "economic_dedupe_authority": False,
                    }
                )
                events.append(event_value)
            role = "server_liquidation_data"
        payload_rows.append(
            {
                "sequence": sequence,
                "direction": message["direction"],
                "observed_at": _utc_text(message["observed_at"], "message_observed_at"),
                "role": role,
                "artifact": f"application_payload_{sequence:03d}.bin",
                "payload": payload,
            }
        )
    if not events:
        raise BybitLiquidationCaptureError("liquidation_events_missing")
    return topic, payload_rows, events


def _prepare_transcript(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_SOURCE_BYTES:
        raise BybitLiquidationCaptureError("source_transcript_bytes_invalid")
    try:
        capture_io.reject_secret_bytes(raw)
    except capture_io.BybitLiquidationCaptureIOError as exc:
        raise BybitLiquidationCaptureError(str(exc)) from exc
    transcript = _parse_object(raw, reason="source_transcript_json_invalid")
    expected = {
        "application_payload_scope",
        "capture_completed_at",
        "capture_mode",
        "capture_started_at",
        "category",
        "contract_version",
        "coverage_complete",
        "coverage_status",
        "execution_mode",
        "instrument",
        "messages",
        "public_websocket_url",
        "research_only",
        "schema_id",
        "schema_version",
        "source_lineage_id",
        "stream_continuity_claimed",
        "silent_intervals_observed_as_zero_liquidations",
        "tls_claims_included",
        "transport_claims_included",
        "venue_id",
        "websocket_framing_claims_included",
    }
    if (
        set(transcript) != expected
        or transcript.get("schema_id") != TRANSCRIPT_SCHEMA_ID
        or type(transcript.get("schema_version")) is not int
        or transcript.get("schema_version") != 1
        or transcript.get("contract_version") != CONTRACT_VERSION
        or transcript.get("venue_id") != VENUE_ID
        or transcript.get("execution_mode") != EXECUTION_MODE
        or transcript.get("category") != BYBIT_CATEGORY
        or transcript.get("public_websocket_url") != PUBLIC_WEBSOCKET_URL
        or transcript.get("application_payload_scope") != APPLICATION_PAYLOAD_SCOPE
        or transcript.get("transport_claims_included") is not False
        or transcript.get("tls_claims_included") is not False
        or transcript.get("websocket_framing_claims_included") is not False
        or transcript.get("stream_continuity_claimed") is not False
        or transcript.get("silent_intervals_observed_as_zero_liquidations") is not False
        or transcript.get("coverage_status") != COVERAGE_STATUS
        or transcript.get("coverage_complete") is not False
        or transcript.get("research_only") is not True
        or transcript.get("capture_mode") not in {
            "operator_import",
            "synthetic_smoke",
        }
    ):
        raise BybitLiquidationCaptureError("source_transcript_contract_invalid")
    lineage = transcript.get("source_lineage_id")
    if (
        not isinstance(lineage, str)
        or len(lineage) > 100
        or not _TOKEN_RE.fullmatch(lineage)
    ):
        raise BybitLiquidationCaptureError("source_lineage_id_invalid")
    lineage_parts = {
        part
        for part in re.split(r"[._:-]+", lineage.casefold())
        if part
    }
    if lineage_parts & _FORBIDDEN_SOURCE_PARTS:
        raise BybitLiquidationCaptureError("operator_source_lineage_rejected")
    instrument = _instrument_from_values(transcript.get("instrument"))
    started = _utc_datetime(transcript.get("capture_started_at"), "capture_started_at")
    completed = _utc_datetime(
        transcript.get("capture_completed_at"), "capture_completed_at"
    )
    if completed < started or (
        completed - started
    ).total_seconds() > MAX_CAPTURE_DURATION_SECONDS:
        raise BybitLiquidationCaptureError("capture_clock_invalid")
    try:
        launched_at = datetime.fromtimestamp(
            instrument.launch_time_ms / 1000,
            tz=timezone.utc,
        )
    except (OSError, OverflowError, ValueError) as exc:
        raise BybitLiquidationCaptureError("instrument_numeric_invalid") from exc
    if launched_at > started:
        raise BybitLiquidationCaptureError("instrument_clock_invalid")
    topic, payload_rows, events = _prepare_messages(
        transcript.get("messages"),
        instrument=instrument,
        started=started,
        completed=completed,
        lineage=lineage,
        capture_mode=str(transcript["capture_mode"]),
    )
    source_sha = _sha256(raw)
    timestamp = completed.strftime("%Y%m%dt%H%M%S%fz")
    return {
        "source_raw": raw,
        "source_sha256": source_sha,
        "capture_id": source_sha,
        "namespace": (
            f"radar_bybit_liquidation_transcript_{timestamp}_{source_sha[:12]}"
        ),
        "started_at": _utc_text(transcript["capture_started_at"], "capture_started_at"),
        "completed_at": _utc_text(
            transcript["capture_completed_at"], "capture_completed_at"
        ),
        "instrument": instrument,
        "topic": topic,
        "source_lineage_id": lineage,
        "capture_mode": transcript["capture_mode"],
        "payload_rows": payload_rows,
        "events": events,
    }


def _closed_truth(capture_mode: str | None) -> dict[str, object]:
    operator_supplied = capture_mode == "operator_import"
    source_authority = (
        "operator_attested_unverified_application_payloads"
        if operator_supplied
        else "synthetic_smoke_unverified_application_payloads"
        if capture_mode == "synthetic_smoke"
        else "unavailable"
    )
    return {
        "source_authority": source_authority,
        "transport_scope": "application_payloads_only",
        "transport_captured_by_project": False,
        "provider_connection_verified_by_project": False,
        "websocket_frame_bytes_preserved": False,
        "tls_upgrade_evidence_included": False,
        "input_authority": False,
        "pointer_authority": False,
        "campaign_authority": False,
        "dashboard_authority": False,
        "policy_authority": False,
        "directional_authority": False,
        "protocol_v2_authority": False,
        "evidence_authority_eligible": False,
        "protocol_v2_input_quality_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "protocol_v2_annex_bound": False,
        "dashboard_authority_eligible": False,
        "campaign_attached": False,
        "operator_supplied": operator_supplied if capture_mode else None,
        "genuine_capture": False,
        "project_transport_capture": False,
        "project_websocket_listener": False,
        "latest_pointer_published": False,
        "context_only": True,
        "decision_policy_applied": False,
        "provider_calls_by_radar": 0,
        "websocket_connections_by_radar": 0,
        "provider_authorization_reads_by_radar": 0,
        "credential_reads_by_radar": 0,
        "environment_reads_by_radar": 0,
        "no_send": True,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "research_only": True,
    }


def _common(prepared: Mapping[str, object]) -> dict[str, object]:
    instrument = prepared["instrument"]
    if not isinstance(instrument, _BybitLiquidationInstrumentIdentity):
        raise BybitLiquidationCaptureError("prepared_instrument_invalid")
    operator_supplied = prepared.get("capture_mode") == "operator_import"
    return {
        "contract_version": CONTRACT_VERSION,
        "capture_id": prepared["capture_id"],
        "artifact_namespace": prepared["namespace"],
        "capture_started_at": prepared["started_at"],
        "capture_completed_at": prepared["completed_at"],
        "capture_mode": prepared["capture_mode"],
        "venue_id": VENUE_ID,
        "execution_mode": EXECUTION_MODE,
        "category": BYBIT_CATEGORY,
        "instrument_id": instrument.instrument_id,
        "canonical_asset_id": instrument.canonical_asset_id,
        "canonical_identity_status": (
            "operator_attested_unverified"
            if operator_supplied
            else "synthetic_unverified"
        ),
        "canonical_identity_verified": False,
        "canonical_identity_attestation": (
            "operator_supplied_transcript_only"
            if operator_supplied
            else "synthetic_smoke_only"
        ),
        "topic": prepared["topic"],
        "application_payload_scope": APPLICATION_PAYLOAD_SCOPE,
        "coverage_status": COVERAGE_STATUS,
        "coverage_complete": False,
        "transport_claims_included": False,
        "tls_claims_included": False,
        "websocket_framing_claims_included": False,
        "stream_continuity_claimed": False,
        "silent_intervals_observed_as_zero_liquidations": False,
        "economic_dedupe_authority": False,
        "duplicate_occurrence_policy": (
            "reject_canonical_provider_occurrence_within_or_across_data_messages"
        ),
        "message_count": len(prepared["payload_rows"]),
        "data_message_count": len(prepared["payload_rows"]) - 2,
        "event_count": len(prepared["events"]),
        **_closed_truth(str(prepared["capture_mode"])),
    }


def _capture_payloads(prepared: Mapping[str, object]) -> list[tuple[str, str, bytes]]:
    common = _common(prepared)
    ledger_rows: list[dict[str, object]] = []
    payloads: list[tuple[str, str, bytes]] = [
        (
            SOURCE_FILENAME,
            "exact_source_transcript",
            prepared["source_raw"],
        )
    ]
    for row in prepared["payload_rows"]:
        payload = row["payload"]
        if not isinstance(payload, bytes):
            raise BybitLiquidationCaptureError("prepared_payload_invalid")
        ledger_rows.append(
            {
                "sequence": row["sequence"],
                "direction": row["direction"],
                "observed_at": row["observed_at"],
                "role": row["role"],
                "artifact": row["artifact"],
                **_fingerprint(payload),
            }
        )
        payloads.append((str(row["artifact"]), str(row["role"]), payload))
    ledger = {
        "schema_id": "decision_radar.bybit_liquidation_transcript_ledger",
        "schema_version": 1,
        **common,
        "source_lineage_id": prepared["source_lineage_id"],
        "source_transcript": {
            "name": SOURCE_FILENAME,
            **_fingerprint(prepared["source_raw"]),
        },
        "payloads": ledger_rows,
    }
    event_values = {
        "schema_id": "decision_radar.bybit_liquidation_normalized_events",
        "schema_version": 1,
        **common,
        "events": prepared["events"],
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
    }
    ledger_raw = _pretty_bytes(ledger)
    events_raw = _pretty_bytes(event_values)
    if len(ledger_raw) > MAX_SOURCE_BYTES or len(events_raw) > MAX_SOURCE_BYTES:
        raise BybitLiquidationCaptureError("derived_artifact_size_bound_exceeded")
    payloads.extend(
        (
            (LEDGER_FILENAME, "transcript_ledger", ledger_raw),
            (EVENTS_FILENAME, "normalized_liquidation_events", events_raw),
        )
    )
    return payloads


def _artifact_descriptor(name: str, role: str, raw: bytes) -> dict[str, object]:
    return {"name": name, "role": role, **_fingerprint(raw)}


def _publication_values(
    prepared: Mapping[str, object],
    descriptors: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    common = _common(prepared)
    manifest = {
        "schema_id": "decision_radar.bybit_liquidation_capture_manifest",
        "schema_version": 1,
        **common,
        "artifacts": [dict(row) for row in descriptors],
    }
    manifest_raw = _pretty_bytes(manifest)
    if len(manifest_raw) > MAX_SOURCE_BYTES:
        raise BybitLiquidationCaptureError("derived_artifact_size_bound_exceeded")
    receipt = {
        "schema_id": "decision_radar.bybit_liquidation_completion_receipt",
        "schema_version": 1,
        "status": "complete",
        **common,
        "manifest": {"name": MANIFEST_FILENAME, **_fingerprint(manifest_raw)},
    }
    if len(_pretty_bytes(receipt)) > MAX_SOURCE_BYTES:
        raise BybitLiquidationCaptureError("derived_artifact_size_bound_exceeded")
    return manifest, receipt


def _read_operator_source(
    path: str | Path, forbidden_ancestor: capture_io._AnchoredCaptureBase | None = None
) -> tuple[Path, bytes]:
    try:
        source, raw = capture_io.read_operator_file(
            path,
            maximum_bytes=MAX_SOURCE_BYTES,
            forbidden_ancestor=forbidden_ancestor,
        )
    except capture_io.BybitLiquidationCaptureIOError as exc:
        raise BybitLiquidationCaptureError(str(exc)) from exc
    return source, raw


def _safe_result(
    prepared: Mapping[str, object], *, persisted: bool, writes: bool
) -> dict[str, object]:
    common = _common(prepared)
    return {
        **common,
        "status": "complete",
        "source_transcript_sha256": prepared["source_sha256"],
        "artifact_persisted": persisted,
        "writes_performed": writes,
    }


def _validate_loaded_capture(
    namespace: str,
    artifacts: Mapping[str, bytes],
    roles: Mapping[str, str],
    manifest_raw: bytes,
    receipt_raw: bytes,
) -> dict[str, object]:
    source_raw = artifacts.get(SOURCE_FILENAME)
    if source_raw is None:
        raise BybitLiquidationCaptureError("source_transcript_missing")
    prepared = _prepare_transcript(source_raw)
    if prepared["namespace"] != namespace:
        raise BybitLiquidationCaptureError("capture_identity_drift")
    expected_payloads = _capture_payloads(prepared)
    if set(artifacts) != {name for name, _role, _raw in expected_payloads}:
        raise BybitLiquidationCaptureError("capture_artifact_set_drift")
    for name, role, raw in expected_payloads:
        if artifacts.get(name) != raw or roles.get(name) != role:
            raise BybitLiquidationCaptureError("capture_projection_drift")
    descriptors = [
        _artifact_descriptor(name, role, raw) for name, role, raw in expected_payloads
    ]
    expected_manifest, expected_receipt = _publication_values(prepared, descriptors)
    if manifest_raw != _pretty_bytes(expected_manifest):
        raise BybitLiquidationCaptureError("capture_manifest_drift")
    if receipt_raw != _pretty_bytes(expected_receipt):
        raise BybitLiquidationCaptureError("capture_receipt_drift")
    return _safe_result(prepared, persisted=True, writes=False)


def _validate_bybit_liquidation_capture_at(
    anchored: capture_io._AnchoredCaptureBase, *, namespace: str
) -> dict[str, object]:
    if not _NAMESPACE_RE.fullmatch(str(namespace or "")):
        raise BybitLiquidationCaptureError("capture_namespace_invalid")
    artifacts: dict[str, bytes] = {}
    try:
        with capture_io.open_namespace_at(anchored, namespace) as namespace_fd:
            manifest_raw = capture_io.read_regular_at(
                namespace_fd, MANIFEST_FILENAME, maximum_bytes=MAX_SOURCE_BYTES
            )
            receipt_raw = capture_io.read_regular_at(
                namespace_fd, RECEIPT_FILENAME, maximum_bytes=MAX_SOURCE_BYTES
            )
            manifest = _parse_object(manifest_raw, reason="capture_manifest_invalid")
            receipt = _parse_object(receipt_raw, reason="capture_receipt_invalid")
            descriptors = manifest.get("artifacts")
            if not isinstance(descriptors, list) or not 6 <= len(descriptors) <= MAX_MESSAGES + 3:
                raise BybitLiquidationCaptureError("capture_artifact_index_invalid")
            roles: dict[str, str] = {}
            for descriptor in descriptors:
                if not isinstance(descriptor, Mapping) or set(descriptor) != {
                    "name",
                    "role",
                    "sha256",
                    "size_bytes",
                }:
                    raise BybitLiquidationCaptureError("capture_artifact_index_invalid")
                name = descriptor.get("name")
                role = descriptor.get("role")
                if (
                    not isinstance(name, str)
                    or not isinstance(role, str)
                    or name in artifacts
                    or name in {MANIFEST_FILENAME, RECEIPT_FILENAME}
                    or not _SHA256_RE.fullmatch(str(descriptor.get("sha256") or ""))
                    or type(descriptor.get("size_bytes")) is not int
                    or descriptor["size_bytes"] <= 0
                ):
                    raise BybitLiquidationCaptureError("capture_artifact_index_invalid")
                maximum = (
                    MAX_PAYLOAD_BYTES
                    if name.startswith("application_payload_")
                    else MAX_SOURCE_BYTES
                )
                raw = capture_io.read_regular_at(
                    namespace_fd,
                    name,
                    maximum_bytes=maximum,
                )
                if (
                    descriptor.get("sha256") != _sha256(raw)
                    or descriptor.get("size_bytes") != len(raw)
                ):
                    raise BybitLiquidationCaptureError("capture_fingerprint_mismatch")
                artifacts[name] = raw
                roles[name] = role
            expected_entries = set(artifacts) | {MANIFEST_FILENAME, RECEIPT_FILENAME}
            actual_entries = capture_io.bounded_entry_names(
                namespace_fd,
                maximum=MAX_MESSAGES + 5,
            )
            if set(actual_entries) != expected_entries:
                raise BybitLiquidationCaptureError("capture_unmanifested_artifact")
            return _validate_loaded_capture(
                namespace,
                artifacts,
                roles,
                manifest_raw,
                receipt_raw,
            )
    except BybitLiquidationCaptureError:
        raise
    except (capture_io.BybitLiquidationCaptureIOError, OSError) as exc:
        raise BybitLiquidationCaptureError("capture_artifact_unreadable") from exc


def validate_bybit_liquidation_capture(
    artifact_base_dir: str | Path, *, namespace: str
) -> dict[str, object]:
    """Hold one anchored base and rederive every persisted byte."""

    try:
        with capture_io.hold_anchored_base(artifact_base_dir, exclusive=False) as anchored:
            return _validate_bybit_liquidation_capture_at(
                anchored, namespace=namespace
            )
    except BybitLiquidationCaptureError:
        raise
    except (capture_io.BybitLiquidationCaptureIOError, OSError) as exc:
        raise BybitLiquidationCaptureError("capture_artifact_unreadable") from exc


def validate_local_transcript(transcript_path: str | Path) -> dict[str, object]:
    """Validate and rederive one operator source without writing artifacts."""

    _source, raw = _read_operator_source(transcript_path)
    prepared = _prepare_transcript(raw)
    if prepared.get("capture_mode") != "operator_import":
        raise BybitLiquidationCaptureError("synthetic_source_not_operator_import")
    return _safe_result(prepared, persisted=False, writes=False)


def _persist_prepared_capture(
    anchored: capture_io._AnchoredCaptureBase, prepared: Mapping[str, object]
) -> dict[str, object]:
    namespace = str(prepared["namespace"])
    payloads = _capture_payloads(prepared)
    descriptors = [_artifact_descriptor(name, role, raw) for name, role, raw in payloads]
    manifest, receipt = _publication_values(prepared, descriptors)
    files = [(name, raw) for name, _role, raw in payloads]
    files.extend(
        (
            (MANIFEST_FILENAME, _pretty_bytes(manifest)),
            (RECEIPT_FILENAME, _pretty_bytes(receipt)),
        )
    )
    try:
        created = capture_io.publish_bundle_atomically(
            anchored,
            namespace=namespace,
            files=files,
        )
    except capture_io.BybitLiquidationCaptureIOError as exc:
        raise BybitLiquidationCaptureError(str(exc)) from exc
    result = _validate_bybit_liquidation_capture_at(anchored, namespace=namespace)
    if (
        result.get("capture_id") != prepared["capture_id"]
        or result.get("source_transcript_sha256") != prepared["source_sha256"]
    ):
        raise BybitLiquidationCaptureError("capture_identity_collision")
    result["writes_performed"] = created
    result["idempotent_reuse"] = not created
    return result


def import_bybit_liquidation_transcript(
    artifact_base_dir: str | Path,
    *,
    transcript_path: str | Path,
    confirm: bool,
) -> dict[str, object]:
    """Confirm, validate, and immutably seal one local operator transcript."""

    if confirm is not True:
        raise BybitLiquidationCaptureError("explicit_confirmation_required")
    try:
        with capture_io.hold_anchored_base(
            artifact_base_dir, exclusive=True
        ) as anchored:
            source, source_raw = _read_operator_source(transcript_path, anchored)
            if source == anchored.path or anchored.path in source.parents:
                raise BybitLiquidationCaptureError(
                    "source_transcript_inside_artifact_base"
                )
            prepared = _prepare_transcript(source_raw)
            if prepared.get("capture_mode") != "operator_import":
                raise BybitLiquidationCaptureError(
                    "synthetic_source_not_operator_import"
                )
            return _persist_prepared_capture(anchored, prepared)
    except BybitLiquidationCaptureError:
        raise
    except capture_io.BybitLiquidationCaptureIOError as exc:
        raise BybitLiquidationCaptureError(str(exc)) from exc


def bybit_liquidation_capture_status(
    artifact_base_dir: str | Path,
    *,
    namespace: str | None,
) -> dict[str, object]:
    """Validate only an exact named namespace; never guess or scan for latest."""

    if not namespace:
        return _unavailable("capture_namespace_required")
    try:
        return validate_bybit_liquidation_capture(
            artifact_base_dir,
            namespace=namespace,
        )
    except BybitLiquidationCaptureError as exc:
        return _unavailable(str(exc))


def _unavailable(reason: str) -> dict[str, object]:
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "unavailable",
        "reason": reason,
        "capture_mode": None,
        "coverage_status": COVERAGE_STATUS,
        "coverage_complete": False,
        **_closed_truth(None),
        "writes_performed": False,
    }


def _smoke_transcript() -> bytes:
    instrument = _BybitLiquidationInstrumentIdentity(
        canonical_asset_id="bitcoin",
        radar_symbol="BTC",
        liquidity_rank=1,
        instrument_id="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        settle_asset="USDT",
        contract_type="LinearPerpetual",
        status="Trading",
        tick_size="0.10",
        quantity_step="0.001",
        launch_time_ms=1588118400000,
        delivery_time_ms=0,
    )
    payloads = [
        b'{"req_id":"radar-local-001","op":"subscribe","args":["allLiquidation.BTCUSDT"]}',
        (
            b'{"success":true,"ret_msg":"subscribe",'
            b'"conn_id":"local-connection-001","req_id":"radar-local-001",'
            b'"op":"subscribe"}'
        ),
        (
            b'{"topic":"allLiquidation.BTCUSDT","type":"snapshot",'
            b'"ts":1784360640000,"data":[{"T":1784360639500,'
            b'"s":"BTCUSDT","S":"Buy","v":"0.5","p":"120000"}]}'
        ),
    ]
    transcript = {
        "schema_id": TRANSCRIPT_SCHEMA_ID,
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "venue_id": VENUE_ID,
        "execution_mode": EXECUTION_MODE,
        "category": BYBIT_CATEGORY,
        "public_websocket_url": PUBLIC_WEBSOCKET_URL,
        "instrument": instrument.to_dict(),
        "capture_started_at": "2026-07-18T07:43:59Z",
        "capture_completed_at": "2026-07-18T07:44:00.300Z",
        "capture_mode": "synthetic_smoke",
        "source_lineage_id": "operator.bybit.liquidation.btcusdt",
        "application_payload_scope": APPLICATION_PAYLOAD_SCOPE,
        "transport_claims_included": False,
        "tls_claims_included": False,
        "websocket_framing_claims_included": False,
        "stream_continuity_claimed": False,
        "silent_intervals_observed_as_zero_liquidations": False,
        "coverage_status": COVERAGE_STATUS,
        "coverage_complete": False,
        "messages": [
            {
                "sequence": index,
                "direction": "client_to_server" if index == 1 else "server_to_client",
                "observed_at": (
                    "2026-07-18T07:43:59.100Z"
                    if index == 1
                    else "2026-07-18T07:43:59.150Z"
                    if index == 2
                    else "2026-07-18T07:44:00.250Z"
                ),
                "payload_base64": base64.b64encode(payload).decode("ascii"),
            }
            for index, payload in enumerate(payloads, start=1)
        ],
        "research_only": True,
    }
    return _pretty_bytes(transcript)


def run_capture_smoke() -> dict[str, object]:
    """Seal, validate, and discard synthetic application payloads offline."""

    with tempfile.TemporaryDirectory(
        prefix="radar_bybit_liquidation_",
        dir="/tmp",
    ) as root_text:
        root = Path(root_text).resolve(strict=True)
        artifact_base = root / "artifacts"
        source_dir = root / "operator_inputs"
        artifact_base.mkdir()
        source_dir.mkdir()
        source = source_dir / "transcript.json"
        source.write_bytes(_smoke_transcript())
        _canonical_source, source_raw = _read_operator_source(source)
        prepared = _prepare_transcript(source_raw)
        if prepared.get("capture_mode") != "synthetic_smoke":
            raise BybitLiquidationCaptureError("capture_smoke_mode_invalid")
        with capture_io.hold_anchored_base(
            artifact_base, exclusive=True
        ) as anchored:
            first = _persist_prepared_capture(anchored, prepared)
            second = _persist_prepared_capture(anchored, prepared)
            validated = _validate_bybit_liquidation_capture_at(
                anchored, namespace=str(first["artifact_namespace"])
            )
        disposable_artifact_write_count = len(
            list((artifact_base / str(first["artifact_namespace"])).iterdir())
        )
        if (
            first["capture_id"] != second["capture_id"]
            or first["capture_id"] != validated["capture_id"]
            or second.get("idempotent_reuse") is not True
        ):
            raise BybitLiquidationCaptureError("capture_smoke_idempotence_failed")
        result = dict(validated)
    result.update(
        {
            "status": "ok",
            "smoke_namespace_retained": False,
            "artifact_persisted": False,
            "disposable_artifact_write_count": disposable_artifact_write_count,
            "idempotence_validated": True,
            "writes_performed": True,
        }
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate or immutably import detached Bybit liquidation payloads."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("capture-smoke")
    validate = subparsers.add_parser("validate-local")
    validate.add_argument("--input", required=True)
    import_local = subparsers.add_parser("import-local")
    import_local.add_argument("--artifact-base", required=True)
    import_local.add_argument("--input", required=True)
    import_local.add_argument("--confirm", action="store_true")
    status = subparsers.add_parser("status")
    status.add_argument("--artifact-base", required=True)
    status.add_argument("--namespace")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "capture-smoke":
            result = run_capture_smoke()
        elif args.command == "validate-local":
            result = validate_local_transcript(args.input)
        elif args.command == "import-local":
            result = import_bybit_liquidation_transcript(
                args.artifact_base,
                transcript_path=args.input,
                confirm=args.confirm,
            )
        else:
            result = bybit_liquidation_capture_status(
                args.artifact_base,
                namespace=args.namespace,
            )
    except BybitLiquidationCaptureError as exc:
        print(json.dumps(_unavailable(str(exc)), indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


__all__ = (
    "APPLICATION_PAYLOAD_SCOPE",
    "CONTRACT_VERSION",
    "COVERAGE_STATUS",
    "BybitLiquidationCaptureError",
    "bybit_liquidation_capture_status",
    "import_bybit_liquidation_transcript",
    "run_capture_smoke",
    "validate_local_transcript",
    "validate_bybit_liquidation_capture",
)


if __name__ == "__main__":
    raise SystemExit(main())
