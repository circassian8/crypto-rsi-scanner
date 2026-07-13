"""Focused manifest helpers for one guarded market/no-send generation."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import market_no_send_publication
from ..radar.calendar import UNIFIED_CALENDAR_FILENAME
from .market_no_send_io import (
    parse_jsonl_bytes,
    read_regular_bytes,
    write_json_atomic,
)
from .market_no_send_models import MarketNoSendReadiness


def start_generation_manifest(
    *,
    context: Any,
    observed: datetime,
    data_mode: str,
    provider_name: str,
    readiness: MarketNoSendReadiness,
    top_n: int,
    fetch_limit: int,
    contract_version: int,
    safety_counters: Mapping[str, int],
    run_id: str,
    raw_row_count: int,
    selected_row_count: int,
    request_cache_filename: str,
    request_cache_sha256: str,
    request_ledger_filename: str,
    request_ledger_sha256: str,
    provenance: Mapping[str, Any],
    history_filename: str,
    history_sha256: str,
    campaign_counted: bool,
    calendar_snapshot: Mapping[str, Any],
    manifest_filename: str,
) -> tuple[Path, dict[str, Any]]:
    """Write the initial fail-closed building manifest."""

    manifest_path = context.namespace_dir / manifest_filename
    manifest = market_no_send_publication.base_manifest(
        context=context,
        observed=observed,
        data_mode=data_mode,
        provider=provider_name,
        authorized=readiness.live_provider_authorized,
        fixture_mode=readiness.fixture_mode,
        top_n=top_n,
        fetch_limit=fetch_limit,
        status="building",
        contract_version=contract_version,
        safety_counters=safety_counters,
    )
    manifest.update(
        {
            "run_id": run_id,
            "provider_call_attempted": True,
            "provider_request_succeeded": True,
            "raw_market_row_count": raw_row_count,
            "selected_market_row_count": selected_row_count,
            "request_cache_artifact": request_cache_filename,
            "request_cache_sha256": request_cache_sha256,
            "request_ledger_artifact": request_ledger_filename,
            "request_ledger_sha256": request_ledger_sha256,
            "market_provenance": dict(provenance),
            "market_history_artifact": history_filename,
            "market_history_sha256": history_sha256,
            "contract_counted_status": "pending" if campaign_counted else "not_counted",
            "calendar_snapshot": dict(calendar_snapshot),
        }
    )
    write_json_atomic(manifest_path, manifest)
    return manifest_path, manifest


def mark_generation_failed(
    manifest_path: Path,
    manifest: dict[str, Any],
    exc: Exception,
) -> None:
    """Close a partially built generation without counting it."""

    manifest.update(
        {
            "status": "failed",
            "contract_counted_status": "not_counted",
            "failure_class": type(exc).__name__,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_json_atomic(manifest_path, manifest)


def calendar_completion_metadata(
    metadata: Mapping[str, Any],
    *,
    namespace_dir: Path,
    unified_calendar_rows: int,
    normalization: Mapping[str, Any],
) -> dict[str, Any]:
    """Close the calendar normalization counts without changing source status."""

    result = dict(metadata)
    result.update(
        {
            "unified_calendar_count": int(unified_calendar_rows or 0),
            "normalization_input_count": int(normalization.get("input_rows") or 0),
            "normalization_valid_input_count": int(
                normalization.get("accepted_rows") or 0
            ),
            "normalization_output_count": int(
                normalization.get("output_rows") or 0
            ),
            "normalization_duplicate_overwrite_count": int(
                normalization.get("duplicate_overwrite_rows") or 0
            ),
            "normalization_non_mapping_count": int(
                normalization.get("non_mapping_rows") or 0
            ),
            "normalization_rejected_count": int(
                normalization.get("rejected_rows") or 0
            ),
            "normalization_rejected_reason_counts": dict(
                normalization.get("rejected_reason_counts") or {}
            ),
        }
    )
    if result.get("status") in {"healthy_empty", "healthy_nonempty"}:
        result["normalization_status"] = _calendar_normalization_status(result)
        _bind_unified_calendar_artifact(result, namespace_dir=namespace_dir)
    return result


def _bind_unified_calendar_artifact(
    metadata: dict[str, Any],
    *,
    namespace_dir: Path,
) -> None:
    path = namespace_dir / UNIFIED_CALENDAR_FILENAME
    raw = read_regular_bytes(path)
    if raw is None:
        raise ValueError("unified calendar artifact is unavailable")
    metadata.update(
        {
            "unified_calendar_artifact": path.name,
            "unified_calendar_artifact_sha256": hashlib.sha256(raw).hexdigest(),
            "unified_calendar_artifact_row_count": len(parse_jsonl_bytes(raw)),
        }
    )


def _calendar_normalization_status(metadata: Mapping[str, Any]) -> str:
    if int(metadata.get("unified_calendar_count") or 0):
        return "healthy_nonempty"
    if int(metadata.get("normalization_rejected_count") or 0):
        return "normalization_rejected"
    return "healthy_empty"


__all__ = (
    "calendar_completion_metadata",
    "mark_generation_failed",
    "start_generation_manifest",
)
