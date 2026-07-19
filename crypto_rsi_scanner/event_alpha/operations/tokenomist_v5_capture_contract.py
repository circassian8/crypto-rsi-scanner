"""Pure contract derivation for the fixture-only Tokenomist v5 capture.

This provider-specific module owns bounded JSON validation and deterministic
artifact payload construction.  It performs no filesystem, environment, or
network I/O; descriptor anchoring and immutable publication remain in
``tokenomist_v5_capture``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Mapping

from ...event_providers import tokenomist_v5
from . import common
from .market_no_send_io import parse_json_object_bytes
from .market_no_send_models import MarketNoSendError


CONTRACT_VERSION = "decision_radar_tokenomist_v5_capture_v1"
CAPTURE_MODE_FIXTURE = "offline_fixture"
CAPTURE_MODE_LIVE = "live_provider_http"
CAPTURE_MODES = frozenset({CAPTURE_MODE_FIXTURE})
SOURCE_FILENAME = "exact_fixture_capture.json"
LEDGER_FILENAME = "request_ledger.json"
SNAPSHOT_FILENAME = "normalized_snapshot.json"
MANIFEST_FILENAME = "capture_manifest.json"
RECEIPT_FILENAME = "capture_completion_receipt.json"
MAX_SOURCE_BYTES = 4_000_000
MAX_ARTIFACT_BYTES = 8_000_000
DEFAULT_MAX_BUNDLE_BYTES = 24_000_000
_MAX_JSON_DEPTH = 32
_MAX_JSON_NODES = 20_000


class TokenomistV5CaptureError(ValueError):
    """Raised when fixture capture preparation or validation fails closed."""


@dataclass(frozen=True)
class _PreparedCapture:
    namespace: str
    capture_id: str
    completed_at: str
    payloads: tuple[tuple[str, bytes], ...]
    summary: Mapping[str, object]


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_digest(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _sha256(raw)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _pretty_bytes(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(dict(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _fingerprint(raw: bytes) -> dict[str, object]:
    return {"sha256": _sha256(raw), "size_bytes": len(raw)}


def _artifact(name: str, role: str, raw: bytes) -> dict[str, object]:
    return {"name": name, "role": role, **_fingerprint(raw)}


def _aware_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise TokenomistV5CaptureError(f"{field}_invalid")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise TokenomistV5CaptureError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TokenomistV5CaptureError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _secret_text_rejected(text: str) -> bool:
    return any(
        pattern.search(text)
        for pattern in (
            common.OPENAI_KEY_RE,
            common.PROVIDER_TOKEN_VALUE_RE,
            common.TELEGRAM_BOT_TOKEN_VALUE_RE,
        )
    ) or "-----BEGIN PRIVATE KEY-----" in text.upper() or any(
        row.get("status") == "blocker"
        for row in common.classify_secret_hits_in_text(text)
    )


def _validate_json_tree(value: object) -> None:
    stack: list[tuple[object, int]] = [(value, 1)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > _MAX_JSON_NODES:
            raise TokenomistV5CaptureError("capture_json_node_bound_exceeded")
        if depth > _MAX_JSON_DEPTH:
            raise TokenomistV5CaptureError("capture_json_depth_bound_exceeded")
        if isinstance(current, float) and not math.isfinite(current):
            raise TokenomistV5CaptureError("capture_json_nonfinite_rejected")
        if isinstance(current, str) and "\x00" in current:
            raise TokenomistV5CaptureError("capture_nul_rejected")
        if isinstance(current, Mapping):
            for key, item in current.items():
                if isinstance(key, str) and "\x00" in key:
                    raise TokenomistV5CaptureError("capture_nul_rejected")
                stack.append((item, depth + 1))
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def _parse_source(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_SOURCE_BYTES:
        raise TokenomistV5CaptureError("capture_source_bytes_invalid")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TokenomistV5CaptureError("capture_source_utf8_invalid") from exc
    if "\x00" in text:
        raise TokenomistV5CaptureError("capture_nul_rejected")
    if _secret_text_rejected(text):
        raise TokenomistV5CaptureError("capture_secret_or_auth_material_rejected")
    try:
        source = parse_json_object_bytes(raw)
        _validate_json_tree(source)
        decoded = json.dumps(source, ensure_ascii=False, separators=(",", ":"))
        if "\x00" in decoded:
            raise TokenomistV5CaptureError("capture_nul_rejected")
        if _secret_text_rejected(decoded):
            raise TokenomistV5CaptureError(
                "capture_secret_or_auth_material_rejected"
            )
        rows = tokenomist_v5.normalize_tokenomist_v5_fixture_capture(source)
    except TokenomistV5CaptureError:
        raise
    except RecursionError as exc:
        raise TokenomistV5CaptureError("capture_json_depth_bound_exceeded") from exc
    except (MarketNoSendError, ValueError) as exc:
        raise TokenomistV5CaptureError("capture_response_contract_invalid") from exc
    if source.get("capture_mode") != "fixture" or source.get("fixture_synthetic") is not True:
        raise TokenomistV5CaptureError("capture_source_not_synthetic_fixture")
    request = source.get("request")
    response = source.get("response")
    if not isinstance(request, Mapping) or not isinstance(response, Mapping):
        raise TokenomistV5CaptureError("capture_request_response_invalid")
    request_digest = _canonical_digest(request)
    response_digest = _canonical_digest(response)
    semantic_capture_digest = _canonical_digest(source)
    event_ids = [str(row.get("event_id") or "") for row in rows]
    if any(not value for value in event_ids) or len(set(event_ids)) != len(event_ids):
        raise TokenomistV5CaptureError("capture_duplicate_event_identity")
    for row in rows:
        if (
            row.get("request_identity_sha256") != request_digest
            or row.get("provider_response_sha256") != response_digest
            or row.get("fixture_capture_sha256") != semantic_capture_digest
        ):
            raise TokenomistV5CaptureError("capture_normalizer_identity_drift")
    return {"source": source, "rows": list(rows)}


def _parse_artifact_object(raw: bytes, *, artifact: str) -> dict[str, Any]:
    """Parse one derived artifact with the same bounded, secret-safe rules."""

    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_ARTIFACT_BYTES:
        raise TokenomistV5CaptureError(f"capture_{artifact}_invalid")
    try:
        text = raw.decode("utf-8")
        if "\x00" in text:
            raise TokenomistV5CaptureError("capture_nul_rejected")
        if _secret_text_rejected(text):
            raise TokenomistV5CaptureError(
                "capture_secret_or_auth_material_rejected"
            )
        value = parse_json_object_bytes(raw)
        _validate_json_tree(value)
        decoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if "\x00" in decoded:
            raise TokenomistV5CaptureError("capture_nul_rejected")
        if _secret_text_rejected(decoded):
            raise TokenomistV5CaptureError(
                "capture_secret_or_auth_material_rejected"
            )
        return value
    except TokenomistV5CaptureError:
        raise
    except (
        MarketNoSendError,
        RecursionError,
        OverflowError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise TokenomistV5CaptureError(f"capture_{artifact}_invalid") from exc


def _common_values(
    *,
    namespace: str,
    capture_id: str,
    completed_at: str,
    coverage_status: str,
    result_status: str,
    event_count: int,
) -> dict[str, object]:
    return {
        "contract_version": CONTRACT_VERSION,
        "artifact_namespace": namespace,
        "capture_id": capture_id,
        "capture_mode": CAPTURE_MODE_FIXTURE,
        "provider": "tokenomist",
        "provider_api_version": "v5",
        "source_class": "structured_unlock",
        "completed_at": completed_at,
        "coverage_status": coverage_status,
        "coverage_complete": coverage_status == "complete",
        "result_status": result_status,
        "accepted_unlock_event_count": event_count,
        "fixture_synthetic": True,
        "exact_source_bytes_retained": True,
        "transport_captured_by_project": False,
        "live_transport_implemented": False,
        "runtime_provider_authorized_at_capture": False,
        "provider_subscription_authorized_at_capture": False,
        "provider_calls_recorded": 0,
        "credentials_read": 0,
        "environment_reads": 0,
        "retention_policy_status": "synthetic_fixture_disposable_only",
        "genuine_provider_bytes_retention_approved": False,
        "genuine_provider_bytes_export_approved": False,
        "latest_pointer_published": False,
        "input_quality_eligible": False,
        "source_authority_eligible": False,
        "campaign_attached": False,
        "dashboard_authority_eligible": False,
        "decision_policy_applied": False,
        "directional_authority": False,
        "context_only": True,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "safe_for_send_readiness": False,
        "research_only": True,
        "no_send": True,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "telegram_sends": 0,
    }


def _bundle_payloads(
    *,
    source_bytes: bytes,
    ledger: Mapping[str, object],
    ledger_raw: bytes,
    snapshot_raw: bytes,
    common_values: Mapping[str, object],
) -> tuple[tuple[str, bytes], ...]:
    descriptors = [
        _artifact(SOURCE_FILENAME, "exact_synthetic_fixture_capture_bytes", source_bytes),
        _artifact(LEDGER_FILENAME, "exact_fixture_request_identity_ledger", ledger_raw),
        _artifact(
            SNAPSHOT_FILENAME,
            "deterministic_normalized_unlock_snapshot",
            snapshot_raw,
        ),
    ]
    manifest = {
        "schema_id": "decision_radar.tokenomist_v5_capture_manifest",
        "schema_version": 1,
        "status": ledger["status"],
        **common_values,
        "artifacts": descriptors,
    }
    manifest_raw = _pretty_bytes(manifest)
    receipt = {
        "schema_id": "decision_radar.tokenomist_v5_completion_receipt",
        "schema_version": 1,
        "status": ledger["status"],
        **common_values,
        "manifest": {"name": MANIFEST_FILENAME, **_fingerprint(manifest_raw)},
    }
    return (
        (SOURCE_FILENAME, source_bytes),
        (LEDGER_FILENAME, ledger_raw),
        (SNAPSHOT_FILENAME, snapshot_raw),
        (MANIFEST_FILENAME, manifest_raw),
        (RECEIPT_FILENAME, _pretty_bytes(receipt)),
    )


def prepare_capture(
    source_bytes: bytes,
    *,
    capture_mode: str,
    maximum_bundle_bytes: int = DEFAULT_MAX_BUNDLE_BYTES,
) -> _PreparedCapture:
    """Derive the complete immutable fixture bundle without filesystem I/O."""

    if capture_mode == CAPTURE_MODE_LIVE:
        raise TokenomistV5CaptureError("live_transport_not_implemented")
    if capture_mode not in CAPTURE_MODES:
        raise TokenomistV5CaptureError("capture_mode_invalid")
    parsed = _parse_source(source_bytes)
    source = parsed["source"]
    rows = parsed["rows"]
    request = source["request"]
    response = source["response"]
    metadata = response["metadata"]
    acquired = _aware_utc(source["acquired_at"], "capture_acquired_at")
    query_at = _aware_utc(metadata["queryDate"], "capture_query_at")
    if query_at > acquired:
        raise TokenomistV5CaptureError("capture_query_after_acquisition")
    total_pages = metadata["totalPages"]
    coverage_status = "complete" if total_pages in {0, 1} else "partial_page"
    result_status = (
        "healthy_empty"
        if coverage_status == "complete" and metadata["total"] == 0
        else "observed"
        if coverage_status == "complete"
        else "partial"
    )
    request_digest = _canonical_digest(request)
    response_digest = _canonical_digest(response)
    source_fingerprint = _fingerprint(source_bytes)
    snapshot = {
        "schema_id": "decision_radar.tokenomist_v5_normalized_snapshot",
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "capture_mode": CAPTURE_MODE_FIXTURE,
        "provider": "tokenomist",
        "provider_api_version": "v5",
        "source_class": "structured_unlock",
        "acquired_at": _iso(acquired),
        "provider_query_at": _iso(query_at),
        "request_identity_sha256": request_digest,
        "provider_response_sha256": response_digest,
        "exact_source": {"name": SOURCE_FILENAME, **source_fingerprint},
        "provider_page": metadata["page"],
        "provider_page_size": metadata["pageSize"],
        "provider_total_pages": total_pages,
        "provider_total_rows": metadata["total"],
        "coverage_status": coverage_status,
        "coverage_complete": coverage_status == "complete",
        "result_status": result_status,
        "accepted_unlock_event_count": len(rows),
        "unlock_events": rows,
        "query_date_is_publication_time": False,
        "first_public_at_status": "unavailable",
        "research_only": True,
        "fixture_synthetic": True,
        "campaign_attached": False,
        "dashboard_authority_eligible": False,
        "directional_authority": False,
        "protocol_v2_evidence_eligible": False,
    }
    snapshot_raw = _pretty_bytes(snapshot)
    identity_input = {
        "contract_version": CONTRACT_VERSION,
        "capture_mode": capture_mode,
        "source_sha256": source_fingerprint["sha256"],
        "source_size_bytes": source_fingerprint["size_bytes"],
        "request_identity_sha256": request_digest,
        "response_identity_sha256": response_digest,
        "snapshot_sha256": _sha256(snapshot_raw),
    }
    capture_id = _sha256(_canonical_bytes(identity_input))
    completed_at = _iso(acquired)
    stamp = acquired.strftime("%Y%m%dt%H%M%S%fz")
    namespace = f"radar_tokenomist_v5_{stamp}_{capture_id[:12]}"
    ledger = {
        "schema_id": "decision_radar.tokenomist_v5_request_ledger",
        "schema_version": 1,
        "status": "complete" if coverage_status == "complete" else "partial",
        "contract_version": CONTRACT_VERSION,
        "artifact_namespace": namespace,
        "capture_id": capture_id,
        "capture_mode": CAPTURE_MODE_FIXTURE,
        "provider": "tokenomist",
        "provider_api_version": "v5",
        "method": request["method"],
        "host": request["host"],
        "path": request["path"],
        "request": request,
        "request_identity_sha256": request_digest,
        "provider_response_sha256": response_digest,
        "source_artifact": {"name": SOURCE_FILENAME, **source_fingerprint},
        "capture_acquired_at": completed_at,
        "provider_query_at": _iso(query_at),
        "provider_page": metadata["page"],
        "provider_page_size": metadata["pageSize"],
        "provider_total_pages": total_pages,
        "provider_total_rows": metadata["total"],
        "coverage_status": coverage_status,
        "provider_call_performed": False,
        "transport_captured_by_project": False,
        "redirects_observed": None,
        "retries_observed": None,
        "credentials_read": False,
        "environment_read": False,
    }
    ledger_raw = _pretty_bytes(ledger)
    common_values = _common_values(
        namespace=namespace,
        capture_id=capture_id,
        completed_at=completed_at,
        coverage_status=coverage_status,
        result_status=result_status,
        event_count=len(rows),
    )
    payloads = _bundle_payloads(
        source_bytes=source_bytes,
        ledger=ledger,
        ledger_raw=ledger_raw,
        snapshot_raw=snapshot_raw,
        common_values=common_values,
    )
    if sum(len(raw) for _name, raw in payloads) > maximum_bundle_bytes:
        raise TokenomistV5CaptureError("capture_bundle_size_bound_exceeded")
    return _PreparedCapture(
        namespace=namespace,
        capture_id=capture_id,
        completed_at=completed_at,
        payloads=payloads,
        summary={
            "status": ledger["status"],
            **common_values,
            "artifact_count": len(payloads),
            "writes_performed": False,
        },
    )


__all__ = (
    "CAPTURE_MODE_FIXTURE",
    "CAPTURE_MODE_LIVE",
    "CONTRACT_VERSION",
    "TokenomistV5CaptureError",
    "prepare_capture",
)
