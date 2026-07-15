"""Exact-namespace materialization for an accepted market calendar snapshot."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from ..artifacts import schema_v1
from ..radar import calendar as unified_calendar
from ..radar import scheduled_catalysts
from .market_no_send_io import (
    read_regular_bytes,
    remove_regular_artifact,
    write_json_atomic,
)
from .market_no_send_models import MarketNoSendError


CALENDAR_PROVIDER_NAME = "decision_radar_calendar_snapshot"


def materialize_market_calendar_snapshot(
    context: Any,
    *,
    calendar_snapshot: Any,
    observed: datetime,
    run_id: str,
    manifest: dict[str, Any],
    safety_counters: Mapping[str, int],
    source_copy_filename: str,
    snapshot_contract_version: int,
) -> tuple[dict[str, Any], ...] | None:
    """Copy and normalize one accepted calendar snapshot into this exact run."""

    if not calendar_snapshot.usable:
        return None
    raw_rows = tuple(dict(row) for row in calendar_snapshot.raw_rows)
    copy_path = context.namespace_dir / source_copy_filename
    write_json_atomic(
        copy_path,
        _calendar_copy_payload(
            context,
            calendar_snapshot=calendar_snapshot,
            observed=observed,
            run_id=run_id,
            raw_rows=raw_rows,
            safety_counters=safety_counters,
            snapshot_contract_version=snapshot_contract_version,
        ),
    )
    copy_bytes = read_regular_bytes(copy_path)
    if copy_bytes is None:
        raise MarketNoSendError("calendar source copy is unavailable")
    scan = _run_scheduled_scan(
        context,
        observed=observed,
        run_id=run_id,
        raw_rows=raw_rows,
    )
    if scan.unlock_count == 0:
        remove_regular_artifact(scan.unlock_path)
        remove_regular_artifact(scan.unlock_report_path)
    metadata = _materialization_metadata(
        manifest,
        copy_path=copy_path,
        copy_bytes=copy_bytes,
        scan=scan,
    )
    manifest["calendar_snapshot"] = metadata
    return raw_rows


def _run_scheduled_scan(
    context: Any,
    *,
    observed: datetime,
    run_id: str,
    raw_rows: tuple[dict[str, Any], ...],
) -> Any:
    return scheduled_catalysts.run_scheduled_catalyst_scan(
        namespace_dir=context.namespace_dir,
        provider_paths={
            "tokenomist": None,
            "messari_unlocks": None,
            "coinmarketcal": None,
        },
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        run_id=run_id,
        observed_at=observed,
        calendar_provider_name=CALENDAR_PROVIDER_NAME,
        calendar_rows=tuple(_calendar_scheduled_row(row) for row in raw_rows),
    )


def canonical_scheduled_calendar_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
    observed_at: datetime | str | None,
) -> tuple[dict[str, Any], ...]:
    """Recompute the exact deterministic scheduled rows without artifact writes."""

    scheduled_rows, _unlock_rows = canonical_calendar_derivation_rows(
        raw_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
        observed_at=observed_at,
    )
    return scheduled_rows


def canonical_calendar_derivation_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
    observed_at: datetime | str | None,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Recompute schema-stamped scheduled and unlock derivations without writes."""

    scheduled, unlocks = scheduled_catalysts.normalize_calendar_catalyst_rows(
        tuple(_calendar_scheduled_row(row) for row in raw_rows),
        provider=CALENDAR_PROVIDER_NAME,
        observed_at=observed_at,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
    )
    return (
        _stamp_rows(
            scheduled,
            filename=scheduled_catalysts.SCHEDULED_CATALYSTS_FILENAME,
        ),
        _stamp_rows(
            unlocks,
            filename=scheduled_catalysts.UNLOCK_CANDIDATES_FILENAME,
        ),
    )


def canonical_unified_calendar_result(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
    observed_at: str | None,
) -> unified_calendar.UnifiedCalendarNormalizationResult:
    """Recompute the exact unified rows and telemetry without artifact writes."""

    return unified_calendar.normalize_unified_calendar_rows_with_telemetry(
        raw_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
        observed_at=observed_at,
    )


def _materialization_metadata(
    manifest: Mapping[str, Any],
    *,
    copy_path: Any,
    copy_bytes: bytes,
    scan: Any,
) -> dict[str, Any]:
    scheduled_bytes = read_regular_bytes(scan.scheduled_path)
    if scheduled_bytes is None:
        raise MarketNoSendError("calendar scheduled artifact is unavailable")
    metadata = dict(manifest.get("calendar_snapshot") or {})
    metadata.update(
        {
            "copy_artifact": copy_path.name,
            "copy_artifact_sha256": hashlib.sha256(copy_bytes).hexdigest(),
            "scheduled_catalyst_artifact": scan.scheduled_path.name,
            "scheduled_catalyst_artifact_sha256": hashlib.sha256(
                scheduled_bytes
            ).hexdigest(),
            "scheduled_catalyst_count": scan.scheduled_count,
            "unlock_candidate_count": scan.unlock_count,
            "unlock_source_status": (
                "healthy_nonempty" if scan.unlock_count else "not_configured"
            ),
            "normalization_warnings": list(scan.warnings),
        }
    )
    if scan.unlock_count:
        unlock_bytes = read_regular_bytes(scan.unlock_path)
        if unlock_bytes is None:
            raise MarketNoSendError("calendar unlock artifact is unavailable")
        metadata.update(
            {
                "unlock_candidate_artifact": scan.unlock_path.name,
                "unlock_candidate_artifact_sha256": hashlib.sha256(
                    unlock_bytes
                ).hexdigest(),
            }
        )
    return metadata


def _calendar_copy_payload(
    context: Any,
    *,
    calendar_snapshot: Any,
    observed: datetime,
    run_id: str,
    raw_rows: tuple[dict[str, Any], ...],
    safety_counters: Mapping[str, int],
    snapshot_contract_version: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "row_type": "event_market_no_send_calendar_source",
        "contract_version": snapshot_contract_version,
        "profile": context.profile,
        "artifact_namespace": context.artifact_namespace,
        "run_mode": context.run_mode,
        "run_id": run_id,
        "observed_at": observed.isoformat(),
        "snapshot_observed_at": calendar_snapshot.snapshot_observed_at,
        "status": calendar_snapshot.status,
        "configured": calendar_snapshot.configured,
        "source_mode": calendar_snapshot.source_mode,
        "upstream_source_mode": calendar_snapshot.upstream_source_mode,
        "upstream_acquisition_mode": calendar_snapshot.upstream_acquisition_mode,
        "source_provider": calendar_snapshot.source_provider,
        "snapshot_status": calendar_snapshot.snapshot_status,
        "source_coverage": [dict(row) for row in calendar_snapshot.source_coverage],
        "source_coverage_sha256": calendar_snapshot.source_coverage_sha256,
        "source_sha256": calendar_snapshot.source_sha256,
        "canonical_rows_sha256": calendar_snapshot.canonical_rows_sha256,
        "source_row_count": calendar_snapshot.source_row_count,
        "retained_row_count": calendar_snapshot.retained_row_count,
        "events": list(raw_rows),
        "no_send": True,
        "research_only": True,
        **dict(safety_counters),
    }


def _calendar_scheduled_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt the closed calendar shape without changing its unified-calendar row."""

    adapted = dict(row)
    if not adapted.get("event_start_time"):
        adapted["event_start_time"] = _first_nonempty(
            adapted,
            (
                "scheduled_at",
                "event_time",
                "date_event",
                "unlock_time",
                "unlock_date",
                "window_start",
                "window_start_at",
            ),
        )
    if not adapted.get("event_end_time"):
        adapted["event_end_time"] = _first_nonempty(
            adapted,
            ("window_end", "window_end_at", "end_time", "end_date"),
        )
    adapted.setdefault("event_id", adapted.get("calendar_event_id") or adapted.get("id"))
    adapted.setdefault("event_type", adapted.get("event_kind"))
    adapted.setdefault("source_class", "structured_calendar")
    affected = adapted.get("affected_assets")
    if not adapted.get("symbol") and isinstance(affected, Sequence) and not isinstance(
        affected, (str, bytes)
    ):
        _attach_first_affected_asset(adapted, affected)
    return adapted


def _first_nonempty(row: Mapping[str, Any], keys: Sequence[str]) -> Any:
    return next((row.get(key) for key in keys if row.get(key) not in (None, "")), None)


def _attach_first_affected_asset(
    adapted: dict[str, Any],
    affected: Sequence[Any],
) -> None:
    for asset in affected:
        if isinstance(asset, Mapping):
            adapted.setdefault("symbol", asset.get("symbol"))
            adapted.setdefault("coin_id", asset.get("coin_id") or asset.get("id"))
        elif isinstance(asset, str) and re.fullmatch(
            r"[A-Za-z0-9]{2,15}", asset.strip()
        ):
            adapted.setdefault("symbol", asset.strip().upper())
        if adapted.get("symbol") or adapted.get("coin_id"):
            break


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value


def _stamp_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    filename: str,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        _json_ready(schema_v1.stamp_artifact_row(row, path=filename))
        for row in rows
    )


__all__ = (
    "canonical_calendar_derivation_rows",
    "canonical_scheduled_calendar_rows",
    "canonical_unified_calendar_result",
    "materialize_market_calendar_snapshot",
)
