"""Exact latest-attempt receipts for safe Make orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .market_no_send_io import read_json_object, safe_existing_namespace_dir, write_json_atomic
from .market_no_send_models import MarketNoSendError, MarketNoSendGenerationResult


LATEST_ATTEMPT_FILENAME = "event_market_no_send_latest_attempt.json"


def record_attempt(base: Path, namespace: str, result: MarketNoSendGenerationResult) -> Path:
    """Replace the credential-free receipt for the exact CLI run result."""

    path = base / LATEST_ATTEMPT_FILENAME
    write_json_atomic(path, {
        "contract_version": 1,
        "row_type": "event_market_no_send_latest_attempt",
        "artifact_namespace": namespace,
        "status": result.status,
        "observed_at": result.observed_at,
        "run_id": result.run_id,
        "provider_call_attempted": result.provider_call_attempted,
        "provider_request_succeeded": result.provider_request_succeeded,
        "candidate_source_mode": result.candidate_source_mode,
        "no_send": True,
        "research_only": True,
    })
    return path


def exact_generation_status(
    base: Path,
    namespace: str,
    *,
    manifest_filename: str,
) -> dict[str, Any]:
    """Return complete only when the latest CLI receipt matches the manifest."""

    try:
        receipt = read_json_object(base / LATEST_ATTEMPT_FILENAME)
    except MarketNoSendError:
        receipt = {}
    manifest: dict[str, Any] = {}
    if receipt.get("artifact_namespace") == namespace and receipt.get("status") == "complete":
        try:
            namespace_dir = safe_existing_namespace_dir(base, namespace)
            manifest = read_json_object(namespace_dir / manifest_filename)
        except MarketNoSendError:
            manifest = {}
    exact = bool(
        receipt.get("contract_version") == 1
        and receipt.get("row_type") == "event_market_no_send_latest_attempt"
        and receipt.get("artifact_namespace") == namespace
        and receipt.get("status") == "complete"
        and manifest.get("status") == "complete"
        and receipt.get("run_id") == manifest.get("run_id")
        and receipt.get("observed_at") == manifest.get("observed_at")
        and receipt.get("provider_call_attempted") is True
        and receipt.get("provider_request_succeeded") is True
    )
    source = manifest if exact else receipt
    return {
        "artifact_namespace": namespace,
        "status": str(source.get("status") or "not_generated"),
        "complete": exact,
        "exact_latest_attempt": exact,
        "provider_call_attempted": source.get("provider_call_attempted") is True,
        "provider_request_succeeded": source.get("provider_request_succeeded") is True,
        "candidate_source_mode": str(source.get("candidate_source_mode") or "preflight_only"),
        "burn_in_counted": manifest.get("burn_in_counted") is True if exact else False,
    }


__all__ = ("LATEST_ATTEMPT_FILENAME", "exact_generation_status", "record_attempt")
