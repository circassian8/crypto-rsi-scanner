"""Immutable exact-response capture for Decision Radar outcome recovery.

Collection remains separately authorized and confirmation-gated.  This module
seals successful public CoinGecko responses and their exact campaign bindings;
it does not apply prices, modify campaign outcomes, or touch baseline history.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Iterator, Mapping, Sequence

from ..outcomes import outcome_eligibility
from . import market_no_send_io, outcome_price_recovery as recovery
from .market_no_send_io import (
    ensure_safe_namespace_dir,
    parse_json_object_bytes,
    read_regular_bytes,
    write_bytes_immutable,
    write_json_atomic,
    write_json_immutable,
)
from .market_no_send_models import MarketNoSendError
from .outcome_price_recovery_capture_source import (
    build_source_binding,
    validate_source_binding,
)
from .outcome_price_recovery_error import OutcomePriceRecoveryError
from .outcome_price_recovery_request import OutcomePriceRecoveryRequest
from .outcome_price_recovery_response import CapturedCoinGeckoResponse


CAPTURE_CONTRACT_VERSION = "decision_radar_outcome_price_recovery_capture_v1"
POINTER_FILENAME = "event_decision_radar_outcome_price_recovery_latest.json"
MANIFEST_FILENAME = "capture_manifest.json"
RECEIPT_FILENAME = "completion_receipt.json"
SOURCE_BINDING_FILENAME = "source_binding.json"
CAPTURE_COMMAND = (
    "CONFIRM=1 make radar-outcome-price-recovery-capture PYTHON=.venv/bin/python"
)
STATUS_COMMAND = (
    "make radar-outcome-price-recovery-status PYTHON=.venv/bin/python"
)
_LOCK_FILENAME = ".radar_outcome_price_recovery.lock"
_NAMESPACE_RE = re.compile(
    r"^radar_outcome_price_recovery_[0-9]{8}t[0-9]{12}z_[0-9a-f]{12}$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_CAPTURE_FILES = recovery.MAX_RECOVERY_REQUESTS * 4 + 3
_MAX_CAPTURE_FILE_BYTES = recovery.MAX_RESPONSE_BYTES + 512 * 1024
_MANIFEST_KEYS = {
    "schema_id",
    "schema_version",
    "status",
    "capture_contract_version",
    "capture_id",
    "artifact_namespace",
    "completed_at",
    "plan_digest",
    "request_count",
    "qualifying_price_count",
    "source_binding_sha256",
    "artifacts",
    "historical_provider_series",
    "point_in_time_collection_at_market_time",
    "baseline_eligible",
    "campaign_outcomes_mutated",
    "protocol_v2_annex_bound",
    "protocol_v2_evidence_eligible",
    "research_only",
    "no_send",
    "orders",
    "trades",
    "paper_trades",
    "normal_rsi_writes",
    "event_alpha_triggered_fade",
    "writes_performed",
}


def capture_outcome_price_recovery(
    *,
    artifact_base_dir: str | Path,
    confirm: bool,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: float = recovery.DEFAULT_TIMEOUT_SECONDS,
    fixture_dir: str | Path | None | object = ...,
    report_builder: recovery.ReportBuilder = (
        recovery.market_observation_campaign.build_campaign_report
    ),
    provider_state_assessor: recovery.ProviderStateAssessor = (
        recovery.market_no_send_campaign_provider.assess_shared_provider_state
    ),
    fetch_exact: recovery.FetchExact | None = None,
    clock: recovery.Clock = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Collect once, revalidate, and seal exact response bytes immutably."""

    collected = recovery.collect_outcome_price_recovery_capture_inputs(
        artifact_base_dir=artifact_base_dir,
        confirm=confirm,
        environ=environ,
        timeout_seconds=timeout_seconds,
        fixture_dir=fixture_dir,
        report_builder=report_builder,
        provider_state_assessor=provider_state_assessor,
        fetch_exact=fetch_exact,
        clock=clock,
    )
    return persist_outcome_price_recovery_capture(
        artifact_base_dir,
        collected=collected,
    )


def persist_outcome_price_recovery_capture(
    artifact_base_dir: str | Path,
    *,
    collected: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist one already-validated collection without applying its prices."""

    base = Path(artifact_base_dir).expanduser().absolute()
    readiness, requests, responses, results = _validated_collection(collected)
    source_binding = build_source_binding(base, readiness, requests)
    completed_at = max(_utc(row.received_at) for row in responses)
    capture_id = _capture_id(
        readiness=readiness,
        source_binding=source_binding,
        requests=requests,
        responses=responses,
        results=results,
    )
    namespace = (
        "radar_outcome_price_recovery_"
        f"{completed_at.strftime('%Y%m%dt%H%M%S%fz')}_{capture_id[:12]}"
    )
    if not _NAMESPACE_RE.fullmatch(namespace):
        raise OutcomePriceRecoveryError("recovery_capture_namespace_invalid")
    namespace_dir = base / namespace
    payloads = _capture_payloads(
        capture_id=capture_id,
        source_binding=source_binding,
        requests=requests,
        responses=responses,
        results=results,
    )
    descriptors = [
        {"name": name, "role": role, **_fingerprint(raw)}
        for name, role, raw in payloads
    ]
    manifest = _manifest_values(
        capture_id=capture_id,
        namespace=namespace,
        completed_at=completed_at,
        readiness=readiness,
        results=results,
        source_binding=source_binding,
        descriptors=descriptors,
    )
    manifest_raw = _pretty_bytes(manifest)
    receipt = _receipt_values(
        capture_id=capture_id,
        namespace=namespace,
        completed_at=completed_at,
        manifest_raw=manifest_raw,
        manifest=manifest,
    )
    receipt_raw = _pretty_bytes(receipt)
    pointer = _pointer_values(receipt=receipt, receipt_raw=receipt_raw)

    with _publication_lock(base):
        existing_pointer_raw = read_regular_bytes(
            base / POINTER_FILENAME,
            missing_ok=True,
        )
        if existing_pointer_raw is not None:
            existing_pointer = _parse_pointer(existing_pointer_raw)
            if existing_pointer.get("capture_id") == capture_id:
                return load_latest_outcome_price_recovery_capture(base)
            if _aware(existing_pointer.get("completed_at")) > completed_at:
                raise OutcomePriceRecoveryError(
                    "recovery_capture_pointer_rollback_rejected"
                )
        ensure_safe_namespace_dir(namespace_dir)
        try:
            for name, _role, raw in payloads:
                write_bytes_immutable(namespace_dir / name, raw)
            write_json_immutable(namespace_dir / MANIFEST_FILENAME, manifest)
            write_json_immutable(namespace_dir / RECEIPT_FILENAME, receipt)
        except MarketNoSendError as exc:
            raise OutcomePriceRecoveryError(
                "recovery_capture_immutable_write_failed"
            ) from exc
        validate_outcome_price_recovery_capture(base, namespace=namespace)
        try:
            write_json_atomic(base / POINTER_FILENAME, pointer)
        except MarketNoSendError as exc:
            raise OutcomePriceRecoveryError(
                "recovery_capture_pointer_write_failed"
            ) from exc
        validated = load_latest_outcome_price_recovery_capture(base)
    return validated


def validate_outcome_price_recovery_capture(
    artifact_base_dir: str | Path,
    *,
    namespace: str,
    pointer: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Hold one namespace and rederive every result from its raw response."""

    if not _NAMESPACE_RE.fullmatch(str(namespace or "")):
        raise OutcomePriceRecoveryError("recovery_capture_namespace_invalid")
    base = Path(artifact_base_dir).expanduser().absolute()
    bundle = _read_capture_bundle(base / namespace)
    manifest_raw = bundle.pop(MANIFEST_FILENAME)
    receipt_raw = bundle.pop(RECEIPT_FILENAME)
    manifest = _parse_object(manifest_raw, "recovery_capture_manifest_invalid")
    receipt = _parse_object(receipt_raw, "recovery_capture_receipt_invalid")
    _validate_manifest_receipt(
        namespace=namespace,
        manifest=manifest,
        manifest_raw=manifest_raw,
        receipt=receipt,
        pointer=pointer,
        receipt_raw=receipt_raw,
        artifacts=bundle,
    )
    source_raw = bundle.get(SOURCE_BINDING_FILENAME)
    if source_raw is None:
        raise OutcomePriceRecoveryError("recovery_capture_source_binding_missing")
    source_binding = _parse_object(
        source_raw,
        "recovery_capture_source_binding_invalid",
    )
    validate_source_binding(source_binding)
    requests: list[OutcomePriceRecoveryRequest] = []
    responses: list[CapturedCoinGeckoResponse] = []
    results: list[dict[str, Any]] = []
    request_count = manifest["request_count"]
    for index in range(1, request_count + 1):
        stem = f"request_{index:03d}"
        request_raw = _required_artifact(bundle, f"{stem}.json")
        response_raw = _required_artifact(bundle, f"response_{index:03d}.json")
        metadata_raw = _required_artifact(
            bundle,
            f"response_{index:03d}_metadata.json",
        )
        result_raw = _required_artifact(bundle, f"result_{index:03d}.json")
        request_values = _parse_object(
            request_raw,
            "recovery_capture_request_invalid",
        )
        request = recovery.recovery_request_from_values(request_values)
        metadata = _parse_response_metadata(metadata_raw, request, response_raw)
        if metadata.get("capture_id") != manifest.get("capture_id"):
            raise OutcomePriceRecoveryError(
                "recovery_capture_response_metadata_invalid"
            )
        response = CapturedCoinGeckoResponse(
            request_id=request.request_id,
            provider_base_url=metadata["provider_base_url"],
            http_status=metadata["http_status"],
            requested_at=_aware(metadata["request_started_at"]),
            received_at=_aware(metadata["response_received_at"]),
            body=response_raw,
        )
        derived = recovery.normalize_captured_recovery_response(request, response)
        persisted = _parse_object(
            result_raw,
            "recovery_capture_result_invalid",
        )
        if persisted != derived:
            raise OutcomePriceRecoveryError("recovery_capture_result_drift")
        requests.append(request)
        responses.append(response)
        results.append(derived)
    readiness_stub = {
        "plan_digest": manifest["plan_digest"],
        "campaign_pointer": source_binding["campaign_pointer"],
        "price_history_snapshot": source_binding["price_history_snapshot"],
    }
    derived_id = _capture_id(
        readiness=readiness_stub,
        source_binding=source_binding,
        requests=tuple(requests),
        responses=tuple(responses),
        results=tuple(results),
    )
    completed_at = max(_utc(row.received_at) for row in responses)
    if any((
        derived_id != manifest.get("capture_id"),
        derived_id != receipt.get("capture_id"),
        manifest.get("completed_at") != _iso(completed_at),
        receipt.get("completed_at") != _iso(completed_at),
        manifest.get("qualifying_price_count")
        != sum(row.get("qualifying_price_found") is True for row in results),
        manifest.get("source_binding_sha256") != _sha256(source_raw),
    )):
        raise OutcomePriceRecoveryError("recovery_capture_semantic_drift")
    return {
        "contract_version": CAPTURE_CONTRACT_VERSION,
        "status": "complete",
        "artifact_namespace": namespace,
        "capture_id": derived_id,
        "completed_at": _iso(completed_at),
        "plan_digest": manifest["plan_digest"],
        "request_count": len(requests),
        "qualifying_price_count": sum(
            row.get("qualifying_price_found") is True for row in results
        ),
        "results": results,
        "source_binding": source_binding,
        "manifest_sha256": _sha256(manifest_raw),
        "receipt_sha256": _sha256(receipt_raw),
        "pointer_validated": pointer is not None,
        "historical_provider_series": True,
        "point_in_time_collection_at_market_time": False,
        "baseline_eligible": False,
        "campaign_outcomes_mutated": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        **_safety(writes_performed=False),
    }


def load_latest_outcome_price_recovery_capture(
    artifact_base_dir: str | Path,
) -> dict[str, Any]:
    base = Path(artifact_base_dir).expanduser().absolute()
    try:
        pointer_raw = read_regular_bytes(base / POINTER_FILENAME, missing_ok=True)
    except MarketNoSendError as exc:
        raise OutcomePriceRecoveryError(
            "recovery_capture_pointer_unreadable"
        ) from exc
    if pointer_raw is None:
        raise OutcomePriceRecoveryError("recovery_capture_pointer_missing")
    pointer = validate_outcome_price_recovery_pointer_bytes(pointer_raw)
    namespace = str(pointer.get("artifact_namespace") or "")
    validated = validate_outcome_price_recovery_capture(
        base,
        namespace=namespace,
        pointer=pointer,
    )
    try:
        final_pointer_raw = read_regular_bytes(base / POINTER_FILENAME)
    except MarketNoSendError as exc:
        raise OutcomePriceRecoveryError(
            "recovery_capture_pointer_unreadable"
        ) from exc
    if final_pointer_raw != pointer_raw:
        raise OutcomePriceRecoveryError(
            "recovery_capture_pointer_changed_during_read"
        )
    validated["pointer_sha256"] = _sha256(pointer_raw)
    return validated


def outcome_price_recovery_capture_status(
    artifact_base_dir: str | Path,
) -> dict[str, Any]:
    """Return bounded read-only capture state without a provider call."""

    try:
        return load_latest_outcome_price_recovery_capture(artifact_base_dir)
    except OutcomePriceRecoveryError as exc:
        return {
            "contract_version": CAPTURE_CONTRACT_VERSION,
            "status": "unavailable",
            "reason": exc.reason_code,
            "capture_id": None,
            "request_count": 0,
            "qualifying_price_count": 0,
            "historical_provider_series": False,
            "point_in_time_collection_at_market_time": False,
            "baseline_eligible": False,
            "campaign_outcomes_mutated": False,
            "protocol_v2_annex_bound": False,
            "protocol_v2_evidence_eligible": False,
            "provider_call_attempted": False,
            "next_safe_command": recovery.READINESS_COMMAND,
            **_safety(writes_performed=False),
        }


def validate_outcome_price_recovery_pointer_bytes(raw: bytes) -> dict[str, Any]:
    """Validate the closed latest-pointer bytes without opening a namespace."""

    return _parse_pointer(raw)


def _validated_collection(
    collected: Mapping[str, Any],
) -> tuple[
    dict[str, Any],
    tuple[OutcomePriceRecoveryRequest, ...],
    tuple[CapturedCoinGeckoResponse, ...],
    tuple[dict[str, Any], ...],
]:
    readiness = collected.get("readiness")
    requests = collected.get("requests")
    responses = collected.get("responses")
    results = collected.get("results")
    if (
        not isinstance(readiness, Mapping)
        or readiness.get("ready") is not True
        or not isinstance(requests, tuple)
        or not isinstance(responses, tuple)
        or not isinstance(results, tuple)
        or not requests
        or len(requests) != len(responses)
        or len(requests) != len(results)
        or len(requests) > recovery.MAX_RECOVERY_REQUESTS
        or collected.get("provider_request_count") != len(requests)
        or not all(isinstance(row, OutcomePriceRecoveryRequest) for row in requests)
        or not all(isinstance(row, CapturedCoinGeckoResponse) for row in responses)
        or not all(isinstance(row, Mapping) for row in results)
    ):
        raise OutcomePriceRecoveryError("recovery_capture_collection_invalid")
    for request, response, result in zip(requests, responses, results, strict=True):
        if recovery.normalize_captured_recovery_response(request, response) != dict(result):
            raise OutcomePriceRecoveryError("recovery_capture_collection_drift")
    return (
        dict(readiness),
        requests,
        responses,
        tuple(dict(row) for row in results),
    )


def _capture_payloads(
    *,
    capture_id: str,
    source_binding: Mapping[str, Any],
    requests: Sequence[OutcomePriceRecoveryRequest],
    responses: Sequence[CapturedCoinGeckoResponse],
    results: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str, bytes]]:
    payloads: list[tuple[str, str, bytes]] = [(
        SOURCE_BINDING_FILENAME,
        "campaign_source_binding",
        _pretty_bytes(source_binding),
    )]
    for index, (request, response, result) in enumerate(
        zip(requests, responses, results, strict=True),
        start=1,
    ):
        request_raw = _pretty_bytes(recovery.recovery_request_values(request))
        response_raw = bytes(response.body)
        metadata = {
            "schema_id": "decision_radar.outcome_price_recovery_response_metadata",
            "schema_version": 1,
            "capture_id": capture_id,
            "request_id": request.request_id,
            "provider_base_url": response.provider_base_url,
            "http_status": response.http_status,
            "request_started_at": _iso(_utc(response.requested_at)),
            "response_received_at": _iso(_utc(response.received_at)),
            "raw_response_sha256": _sha256(response_raw),
            "raw_response_size_bytes": len(response_raw),
            "retry_count": 0,
            "redirects_followed": 0,
            "ambient_proxy_used": False,
            "research_only": True,
        }
        payloads.extend((
            (f"request_{index:03d}.json", "exact_request_plan", request_raw),
            (f"response_{index:03d}.json", "accepted_raw_provider_response", response_raw),
            (
                f"response_{index:03d}_metadata.json",
                "provider_response_metadata",
                _pretty_bytes(metadata),
            ),
            (f"result_{index:03d}.json", "rederived_recovery_result", _pretty_bytes(result)),
        ))
    return payloads


def _manifest_values(
    *,
    capture_id: str,
    namespace: str,
    completed_at: datetime,
    readiness: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
    source_binding: Mapping[str, Any],
    descriptors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_id": "decision_radar.outcome_price_recovery_capture_manifest",
        "schema_version": 1,
        "status": "complete",
        "capture_contract_version": CAPTURE_CONTRACT_VERSION,
        "capture_id": capture_id,
        "artifact_namespace": namespace,
        "completed_at": _iso(completed_at),
        "plan_digest": readiness["plan_digest"],
        "request_count": len(results),
        "qualifying_price_count": sum(
            row.get("qualifying_price_found") is True for row in results
        ),
        "source_binding_sha256": _sha256(_pretty_bytes(source_binding)),
        "artifacts": list(descriptors),
        "historical_provider_series": True,
        "point_in_time_collection_at_market_time": False,
        "baseline_eligible": False,
        "campaign_outcomes_mutated": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        **_safety(writes_performed=True),
    }


def _receipt_values(
    *,
    capture_id: str,
    namespace: str,
    completed_at: datetime,
    manifest_raw: bytes,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_id": "decision_radar.outcome_price_recovery_completion_receipt",
        "schema_version": 1,
        "status": "complete",
        "capture_contract_version": CAPTURE_CONTRACT_VERSION,
        "capture_id": capture_id,
        "artifact_namespace": namespace,
        "completed_at": _iso(completed_at),
        "plan_digest": manifest["plan_digest"],
        "request_count": manifest["request_count"],
        "qualifying_price_count": manifest["qualifying_price_count"],
        "manifest": {"name": MANIFEST_FILENAME, **_fingerprint(manifest_raw)},
        "research_only": True,
    }


def _pointer_values(
    *,
    receipt: Mapping[str, Any],
    receipt_raw: bytes,
) -> dict[str, Any]:
    return {
        "schema_id": "decision_radar.outcome_price_recovery_latest_pointer",
        "schema_version": 1,
        "status": "complete",
        "capture_contract_version": CAPTURE_CONTRACT_VERSION,
        "capture_id": receipt["capture_id"],
        "artifact_namespace": receipt["artifact_namespace"],
        "completed_at": receipt["completed_at"],
        "plan_digest": receipt["plan_digest"],
        "request_count": receipt["request_count"],
        "qualifying_price_count": receipt["qualifying_price_count"],
        "receipt": {"name": RECEIPT_FILENAME, **_fingerprint(receipt_raw)},
        "research_only": True,
    }


def _capture_id(
    *,
    readiness: Mapping[str, Any],
    source_binding: Mapping[str, Any],
    requests: Sequence[OutcomePriceRecoveryRequest],
    responses: Sequence[CapturedCoinGeckoResponse],
    results: Sequence[Mapping[str, Any]],
) -> str:
    seed = {
        "capture_contract_version": CAPTURE_CONTRACT_VERSION,
        "plan_digest": readiness.get("plan_digest"),
        "source_binding_sha256": _sha256(_pretty_bytes(source_binding)),
        "rows": [
            {
                "request": recovery.recovery_request_values(request),
                "provider_base_url": response.provider_base_url,
                "http_status": response.http_status,
                "request_started_at": _iso(_utc(response.requested_at)),
                "response_received_at": _iso(_utc(response.received_at)),
                "raw_response_sha256": _sha256(response.body),
                "result_sha256": _sha256(_pretty_bytes(result)),
            }
            for request, response, result in zip(
                requests,
                responses,
                results,
                strict=True,
            )
        ],
    }
    return _sha256(_canonical_bytes(seed))


def _validate_manifest_receipt(
    *,
    namespace: str,
    manifest: Mapping[str, Any],
    manifest_raw: bytes,
    receipt: Mapping[str, Any],
    pointer: Mapping[str, Any] | None,
    receipt_raw: bytes,
    artifacts: Mapping[str, bytes],
) -> None:
    if set(manifest) != _MANIFEST_KEYS or any((
        manifest.get("schema_id")
        != "decision_radar.outcome_price_recovery_capture_manifest",
        manifest.get("schema_version") != 1,
        manifest.get("status") != "complete",
        manifest.get("capture_contract_version") != CAPTURE_CONTRACT_VERSION,
        manifest.get("artifact_namespace") != namespace,
        not _SHA256_RE.fullmatch(str(manifest.get("capture_id") or "")),
        not _SHA256_RE.fullmatch(str(manifest.get("plan_digest") or "")),
        type(manifest.get("request_count")) is not int,
        not 0 < manifest.get("request_count", 0) <= recovery.MAX_RECOVERY_REQUESTS,
        type(manifest.get("qualifying_price_count")) is not int,
        not 0 <= manifest.get("qualifying_price_count", -1)
        <= manifest.get("request_count", 0),
        manifest.get("historical_provider_series") is not True,
        manifest.get("point_in_time_collection_at_market_time") is not False,
        manifest.get("baseline_eligible") is not False,
        manifest.get("campaign_outcomes_mutated") is not False,
        manifest.get("protocol_v2_annex_bound") is not False,
        manifest.get("protocol_v2_evidence_eligible") is not False,
        not _safety_valid(manifest, writes_performed=True),
    )):
        raise OutcomePriceRecoveryError("recovery_capture_manifest_invalid")
    descriptors = manifest.get("artifacts")
    if (
        not isinstance(descriptors, list)
        or len(descriptors) != manifest["request_count"] * 4 + 1
        or len(descriptors) > _MAX_CAPTURE_FILES
    ):
        raise OutcomePriceRecoveryError("recovery_capture_manifest_invalid")
    expected_names: set[str] = set()
    expected_roles = {SOURCE_BINDING_FILENAME: "campaign_source_binding"}
    for index in range(1, manifest["request_count"] + 1):
        expected_roles.update({
            f"request_{index:03d}.json": "exact_request_plan",
            f"response_{index:03d}.json": "accepted_raw_provider_response",
            f"response_{index:03d}_metadata.json": "provider_response_metadata",
            f"result_{index:03d}.json": "rederived_recovery_result",
        })
    for descriptor in descriptors:
        if not isinstance(descriptor, Mapping) or set(descriptor) != {
            "name", "role", "sha256", "size_bytes"
        }:
            raise OutcomePriceRecoveryError("recovery_capture_descriptor_invalid")
        name = descriptor.get("name")
        raw = artifacts.get(str(name))
        if (
            type(name) is not str
            or Path(name).name != name
            or name in expected_names
            or descriptor.get("role") != expected_roles.get(name)
            or raw is None
            or descriptor.get("sha256") != _sha256(raw)
            or descriptor.get("size_bytes") != len(raw)
        ):
            raise OutcomePriceRecoveryError("recovery_capture_descriptor_invalid")
        expected_names.add(name)
    if expected_names != set(artifacts):
        raise OutcomePriceRecoveryError("recovery_capture_inventory_invalid")
    if set(receipt) != {
        "schema_id", "schema_version", "status", "capture_contract_version",
        "capture_id", "artifact_namespace", "completed_at", "plan_digest",
        "request_count", "qualifying_price_count", "manifest", "research_only",
    } or any((
        receipt.get("schema_id")
        != "decision_radar.outcome_price_recovery_completion_receipt",
        receipt.get("schema_version") != 1,
        receipt.get("status") != "complete",
        receipt.get("capture_contract_version") != CAPTURE_CONTRACT_VERSION,
        receipt.get("capture_id") != manifest.get("capture_id"),
        receipt.get("artifact_namespace") != namespace,
        receipt.get("completed_at") != manifest.get("completed_at"),
        receipt.get("plan_digest") != manifest.get("plan_digest"),
        receipt.get("request_count") != manifest.get("request_count"),
        receipt.get("qualifying_price_count")
        != manifest.get("qualifying_price_count"),
        receipt.get("manifest")
        != {"name": MANIFEST_FILENAME, **_fingerprint(manifest_raw)},
        receipt.get("research_only") is not True,
    )):
        raise OutcomePriceRecoveryError("recovery_capture_receipt_invalid")
    if pointer is not None:
        expected_pointer = _pointer_values(receipt=receipt, receipt_raw=receipt_raw)
        if dict(pointer) != expected_pointer:
            raise OutcomePriceRecoveryError("recovery_capture_pointer_drift")


def _parse_response_metadata(
    raw: bytes,
    request: OutcomePriceRecoveryRequest,
    response_raw: bytes,
) -> dict[str, Any]:
    value = _parse_object(raw, "recovery_capture_response_metadata_invalid")
    if set(value) != {
        "schema_id", "schema_version", "capture_id", "request_id",
        "provider_base_url", "http_status", "request_started_at",
        "response_received_at", "raw_response_sha256",
        "raw_response_size_bytes", "retry_count", "redirects_followed",
        "ambient_proxy_used", "research_only",
    } or any((
        value.get("schema_id")
        != "decision_radar.outcome_price_recovery_response_metadata",
        value.get("schema_version") != 1,
        not _SHA256_RE.fullmatch(str(value.get("capture_id") or "")),
        value.get("request_id") != request.request_id,
        value.get("provider_base_url")
        not in {recovery.PUBLIC_API_BASE, recovery.PRO_API_BASE},
        value.get("http_status") != 200,
        value.get("raw_response_sha256") != _sha256(response_raw),
        value.get("raw_response_size_bytes") != len(response_raw),
        value.get("retry_count") != 0,
        value.get("redirects_followed") != 0,
        value.get("ambient_proxy_used") is not False,
        value.get("research_only") is not True,
    )):
        raise OutcomePriceRecoveryError(
            "recovery_capture_response_metadata_invalid"
        )
    started = _aware(value.get("request_started_at"))
    received = _aware(value.get("response_received_at"))
    if received < started:
        raise OutcomePriceRecoveryError(
            "recovery_capture_response_metadata_invalid"
        )
    return value


def _read_capture_bundle(namespace_dir: Path) -> dict[str, bytes]:
    try:
        with market_no_send_io._open_verified_namespace_dir(  # noqa: SLF001
            namespace_dir
        ) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            names = os.listdir(namespace_fd)
            if (
                not names
                or len(names) > _MAX_CAPTURE_FILES
                or len(names) != len(set(names))
            ):
                raise OutcomePriceRecoveryError("recovery_capture_inventory_invalid")
            out = {
                name: _read_leaf(namespace_fd, name)
                for name in sorted(names)
            }
    except OutcomePriceRecoveryError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise OutcomePriceRecoveryError("recovery_capture_namespace_unreadable") from exc
    if MANIFEST_FILENAME not in out or RECEIPT_FILENAME not in out:
        raise OutcomePriceRecoveryError("recovery_capture_inventory_invalid")
    return out


def _read_leaf(directory_fd: int, name: str) -> bytes:
    if type(name) is not str or Path(name).name != name or name in {".", ".."}:
        raise OutcomePriceRecoveryError("recovery_capture_artifact_name_invalid")
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(name, flags, dir_fd=directory_fd)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise OutcomePriceRecoveryError("recovery_capture_artifact_invalid")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, _MAX_CAPTURE_FILE_BYTES + 1 - size),
            )
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > _MAX_CAPTURE_FILE_BYTES:
                raise OutcomePriceRecoveryError("recovery_capture_artifact_oversize")
        after = os.fstat(descriptor)
        named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not _same_snapshot(before, after) or not _same_snapshot(after, named):
            raise OutcomePriceRecoveryError("recovery_capture_artifact_changed")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


@contextmanager
def _publication_lock(base: Path) -> Iterator[None]:
    descriptor: int | None = None
    locked = False
    try:
        with market_no_send_io._open_verified_namespace_dir(  # noqa: SLF001
            base
        ) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(_LOCK_FILENAME, flags, 0o600, dir_fd=namespace_fd)
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                raise OutcomePriceRecoveryError("recovery_capture_lock_invalid")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            yield
    except OutcomePriceRecoveryError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise OutcomePriceRecoveryError("recovery_capture_lock_unavailable") from exc
    finally:
        if locked and descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        if descriptor is not None:
            os.close(descriptor)


def _parse_pointer(raw: bytes) -> dict[str, Any]:
    value = _parse_object(raw, "recovery_capture_pointer_invalid")
    if set(value) != {
        "schema_id", "schema_version", "status", "capture_contract_version",
        "capture_id", "artifact_namespace", "completed_at", "plan_digest",
        "request_count", "qualifying_price_count", "receipt", "research_only",
    } or any((
        value.get("schema_id")
        != "decision_radar.outcome_price_recovery_latest_pointer",
        value.get("schema_version") != 1,
        value.get("status") != "complete",
        value.get("capture_contract_version") != CAPTURE_CONTRACT_VERSION,
        not _SHA256_RE.fullmatch(str(value.get("capture_id") or "")),
        not _NAMESPACE_RE.fullmatch(str(value.get("artifact_namespace") or "")),
        not _SHA256_RE.fullmatch(str(value.get("plan_digest") or "")),
        type(value.get("request_count")) is not int,
        not 0 < value.get("request_count", 0) <= recovery.MAX_RECOVERY_REQUESTS,
        type(value.get("qualifying_price_count")) is not int,
        not _fingerprint_valid(value.get("receipt"), expected_name=RECEIPT_FILENAME),
        value.get("research_only") is not True,
    )):
        raise OutcomePriceRecoveryError("recovery_capture_pointer_invalid")
    _aware(value.get("completed_at"))
    return value


def _parse_object(raw: bytes, reason: str) -> dict[str, Any]:
    try:
        return parse_json_object_bytes(raw)
    except (MarketNoSendError, ValueError) as exc:
        raise OutcomePriceRecoveryError(reason) from exc


def _required_artifact(artifacts: Mapping[str, bytes], name: str) -> bytes:
    raw = artifacts.get(name)
    if raw is None:
        raise OutcomePriceRecoveryError("recovery_capture_artifact_missing")
    return raw


def _fingerprint(raw: bytes) -> dict[str, Any]:
    return {"sha256": _sha256(raw), "size_bytes": len(raw)}


def _fingerprint_valid(value: object, *, expected_name: str | None = None) -> bool:
    if not isinstance(value, Mapping):
        return False
    expected = {"sha256", "size_bytes"}
    if expected_name is not None:
        expected.add("name")
    return (
        set(value) == expected
        and (expected_name is None or value.get("name") == expected_name)
        and _SHA256_RE.fullmatch(str(value.get("sha256") or "")) is not None
        and type(value.get("size_bytes")) is int
        and 0 < value.get("size_bytes", 0) <= _MAX_CAPTURE_FILE_BYTES
    )


def _pretty_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _aware(value: object) -> datetime:
    parsed = outcome_eligibility.parse_aware_time(value)
    if parsed is None:
        raise OutcomePriceRecoveryError("recovery_capture_clock_invalid")
    return parsed.astimezone(timezone.utc)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OutcomePriceRecoveryError("recovery_capture_clock_invalid")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        left.st_mode,
        left.st_size,
        left.st_mtime_ns,
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_mode,
        right.st_size,
        right.st_mtime_ns,
    )


def _safety(*, writes_performed: bool) -> dict[str, Any]:
    return {
        "research_only": True,
        "no_send": True,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "writes_performed": writes_performed,
    }


def _safety_valid(value: Mapping[str, Any], *, writes_performed: bool) -> bool:
    return all((
        value.get("research_only") is True,
        value.get("no_send") is True,
        value.get("orders") == 0,
        value.get("trades") == 0,
        value.get("paper_trades") == 0,
        value.get("normal_rsi_writes") == 0,
        value.get("event_alpha_triggered_fade") == 0,
        value.get("writes_performed") is writes_performed,
    ))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "status"))
    parser.add_argument("--artifact-base", default="event_fade_cache")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=recovery.DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--confirm", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "status":
            result = outcome_price_recovery_capture_status(args.artifact_base)
        else:
            result = capture_outcome_price_recovery(
                artifact_base_dir=args.artifact_base,
                confirm=args.confirm,
                timeout_seconds=args.timeout_seconds,
            )
    except OutcomePriceRecoveryError as exc:
        result = {
            "status": "blocked",
            "reason": exc.reason_code,
            "provider_request_count": exc.request_count,
            **_safety(writes_performed=False),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if args.command == "status" or result.get("status") == "complete" else 2


if __name__ == "__main__":
    sys.exit(main())


__all__ = (
    "CAPTURE_COMMAND",
    "CAPTURE_CONTRACT_VERSION",
    "POINTER_FILENAME",
    "STATUS_COMMAND",
    "capture_outcome_price_recovery",
    "load_latest_outcome_price_recovery_capture",
    "outcome_price_recovery_capture_status",
    "persist_outcome_price_recovery_capture",
    "validate_outcome_price_recovery_pointer_bytes",
    "validate_outcome_price_recovery_capture",
)
