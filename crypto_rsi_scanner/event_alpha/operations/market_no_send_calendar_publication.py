"""Publication-time validation for the optional market calendar snapshot."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Mapping

from . import market_no_send_calendar
from . import market_no_send_calendar_materialization
from .market_no_send_io import (
    parse_json_object_bytes,
    parse_jsonl_bytes,
    read_regular_bytes,
)
from .market_no_send_models import MarketNoSendError


def validate_optional_calendar_snapshot(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    run_id: str,
    safety_counters: Mapping[str, int],
) -> None:
    """Validate an explicitly configured local snapshot when one was accepted."""

    metadata = manifest.get("calendar_snapshot")
    if metadata is None:
        return  # Read-only compatibility for generations created before v1.
    if not isinstance(metadata, Mapping):
        raise MarketNoSendError("campaign_calendar_snapshot_metadata_invalid")
    status = str(metadata.get("status") or "")
    if status not in market_no_send_calendar.CALENDAR_SNAPSHOT_STATUSES:
        raise MarketNoSendError("campaign_calendar_snapshot_status_invalid")
    configured = metadata.get("configured")
    if configured is not (status != "not_configured"):
        raise MarketNoSendError("campaign_calendar_snapshot_configured_mismatch")
    if any(
        (
            metadata.get("network_call_attempted") is not False,
            metadata.get("provider_call_attempted") is not False,
            metadata.get("provider_authorization_mutated") is not False,
            metadata.get("no_send") is not True,
            metadata.get("research_only") is not True,
            any(
                metadata.get(field) != value
                for field, value in safety_counters.items()
            ),
        )
    ):
        raise MarketNoSendError("campaign_calendar_snapshot_safety_invalid")
    retained_count = _nonnegative_count(
        metadata.get("retained_row_count"), field="retained_row_count"
    )
    source_count = _nonnegative_count(
        metadata.get("source_row_count"), field="source_row_count"
    )
    if source_count < retained_count:
        raise MarketNoSendError("campaign_calendar_snapshot_source_count_mismatch")
    _validate_upstream_coverage(metadata)
    if status == "healthy_empty" and retained_count != 0:
        raise MarketNoSendError("campaign_calendar_snapshot_status_count_mismatch")
    if status == "healthy_nonempty" and retained_count == 0:
        raise MarketNoSendError("campaign_calendar_snapshot_status_count_mismatch")
    if status not in {"healthy_empty", "healthy_nonempty"}:
        if retained_count != 0:
            raise MarketNoSendError("campaign_calendar_snapshot_unusable_rows_present")
        _validate_no_derivation(metadata, namespace_dir=namespace_dir)
        return
    events = _validate_source_copy(
        manifest,
        metadata=metadata,
        namespace_dir=namespace_dir,
        run_id=run_id,
        safety_counters=safety_counters,
    )
    _validate_derivation_chain(
        manifest,
        metadata=metadata,
        namespace_dir=namespace_dir,
        run_id=run_id,
        events=events,
    )


def _nonnegative_count(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MarketNoSendError(f"campaign_calendar_snapshot_{field}_invalid")
    return value


def _validate_upstream_coverage(metadata: Mapping[str, Any]) -> None:
    source_provider = metadata.get("source_provider")
    coverage_fields = (
        metadata.get("snapshot_status"),
        metadata.get("source_coverage"),
        metadata.get("source_coverage_sha256"),
    )
    if source_provider != "official_us_macro":
        if any(value not in (None, "", [], ()) for value in coverage_fields):
            raise MarketNoSendError(
                "campaign_calendar_snapshot_source_coverage_provider_invalid"
            )
        return
    rows = metadata.get("source_coverage")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise MarketNoSendError("campaign_calendar_snapshot_source_coverage_invalid")
    try:
        market_no_send_calendar.validate_official_source_coverage(
            rows,
            snapshot_status=str(metadata.get("snapshot_status") or ""),
            acquisition_mode=_optional_text(
                metadata.get("upstream_acquisition_mode")
            ),
            expected_sha256=str(metadata.get("source_coverage_sha256") or ""),
        )
    except ValueError:
        raise MarketNoSendError(
            "campaign_calendar_snapshot_source_coverage_invalid"
        ) from None


def _validate_no_derivation(
    metadata: Mapping[str, Any],
    *,
    namespace_dir: Path,
) -> None:
    derived_fields = (
        "copy_artifact",
        "scheduled_catalyst_artifact",
        "unlock_candidate_artifact",
        "unified_calendar_artifact",
    )
    if any(metadata.get(field) not in (None, "") for field in derived_fields):
        raise MarketNoSendError("campaign_calendar_snapshot_unusable_derivation_present")
    copy_path = namespace_dir / market_no_send_calendar.CALENDAR_SOURCE_COPY_FILENAME
    if read_regular_bytes(copy_path, missing_ok=True) is not None:
        raise MarketNoSendError("campaign_calendar_snapshot_unusable_copy_present")


def _validate_source_copy(
    manifest: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    namespace_dir: Path,
    run_id: str,
    safety_counters: Mapping[str, int],
) -> list[dict[str, Any]]:
    filename = market_no_send_calendar.CALENDAR_SOURCE_COPY_FILENAME
    if metadata.get("copy_artifact") != filename:
        raise MarketNoSendError("campaign_calendar_snapshot_copy_missing")
    path = namespace_dir / filename
    raw = read_regular_bytes(path)
    payload = parse_json_object_bytes(raw)
    events = payload.get("events")
    if not isinstance(events, list) or any(
        not isinstance(row, Mapping) for row in events
    ):
        raise MarketNoSendError("campaign_calendar_snapshot_rows_invalid")
    safe_events = list(
        market_no_send_calendar.validate_calendar_artifact_rows(events)
    )
    canonical = hashlib.sha256(
        json.dumps(
            safe_events,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    if _source_copy_mismatched(
        manifest,
        metadata=metadata,
        payload=payload,
        safe_events=safe_events,
        raw=raw,
        canonical=canonical,
        run_id=run_id,
        safety_counters=safety_counters,
    ):
        raise MarketNoSendError("campaign_calendar_snapshot_binding_mismatch")
    return safe_events


def _source_copy_mismatched(
    manifest: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    payload: Mapping[str, Any],
    safe_events: list[dict[str, Any]],
    raw: bytes,
    canonical: str,
    run_id: str,
    safety_counters: Mapping[str, int],
) -> bool:
    upstream_source = metadata.get("upstream_source_mode")
    upstream_acquisition = metadata.get("upstream_acquisition_mode")
    source_provider = metadata.get("source_provider")
    source_coverage = metadata.get("source_coverage")
    return any(
        (
            payload.get("row_type") != "event_market_no_send_calendar_source",
            payload.get("contract_version")
            != market_no_send_calendar.CALENDAR_SNAPSHOT_CONTRACT_VERSION,
            payload.get("run_id") != run_id,
            payload.get("profile") != manifest.get("profile"),
            payload.get("artifact_namespace") != manifest.get("artifact_namespace"),
            payload.get("run_mode") != manifest.get("run_mode"),
            payload.get("observed_at") != manifest.get("observed_at"),
            payload.get("status") != metadata.get("status"),
            payload.get("configured") != metadata.get("configured"),
            payload.get("snapshot_observed_at") != metadata.get("snapshot_observed_at"),
            not str(metadata.get("freshness_basis") or "").startswith("container:"),
            upstream_source not in market_no_send_calendar.LIVE_CALENDAR_SOURCE_MODES,
            upstream_acquisition
            not in market_no_send_calendar.LIVE_CALENDAR_ACQUISITION_MODES,
            not isinstance(source_provider, str) or not source_provider,
            payload.get("upstream_source_mode") != upstream_source,
            payload.get("upstream_acquisition_mode") != upstream_acquisition,
            payload.get("source_provider") != source_provider,
            payload.get("snapshot_status") != metadata.get("snapshot_status"),
            payload.get("source_coverage") != source_coverage,
            payload.get("source_coverage_sha256")
            != metadata.get("source_coverage_sha256"),
            payload.get("source_sha256") != metadata.get("source_sha256"),
            payload.get("canonical_rows_sha256") != canonical,
            metadata.get("canonical_rows_sha256") != canonical,
            payload.get("retained_row_count") != len(safe_events),
            metadata.get("retained_row_count") != len(safe_events),
            payload.get("source_row_count") != metadata.get("source_row_count"),
            metadata.get("copy_artifact_sha256")
            != hashlib.sha256(raw).hexdigest(),
            payload.get("no_send") is not True,
            payload.get("research_only") is not True,
            any(
                payload.get(field) != value
                for field, value in safety_counters.items()
            ),
        )
    )


def _validate_derivation_chain(
    manifest: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    namespace_dir: Path,
    run_id: str,
    events: list[dict[str, Any]],
) -> None:
    scheduled_rows = _validate_bound_jsonl(
        metadata,
        namespace_dir=namespace_dir,
        artifact_field="scheduled_catalyst_artifact",
        digest_field="scheduled_catalyst_artifact_sha256",
        count_field="scheduled_catalyst_count",
        expected_filename="event_scheduled_catalysts.jsonl",
        run_id=run_id,
        namespace=manifest.get("artifact_namespace"),
    )
    scheduled_count = len(scheduled_rows)
    retained_count = len(events)
    if scheduled_count != retained_count:
        raise MarketNoSendError("campaign_calendar_scheduled_count_mismatch")
    expected_scheduled, expected_unlocks = (
        market_no_send_calendar_materialization.canonical_calendar_derivation_rows(
            events,
            profile=_optional_text(manifest.get("profile")),
            artifact_namespace=_optional_text(manifest.get("artifact_namespace")),
            run_mode=_optional_text(manifest.get("run_mode")),
            run_id=run_id,
            observed_at=_optional_text(manifest.get("observed_at")),
        )
    )
    if _canonical_rows_sha256(scheduled_rows) != _canonical_rows_sha256(
        expected_scheduled
    ):
        raise MarketNoSendError("campaign_calendar_scheduled_semantics_mismatch")
    _validate_unlock_binding(
        manifest,
        metadata=metadata,
        namespace_dir=namespace_dir,
        run_id=run_id,
        scheduled_count=scheduled_count,
        expected_rows=expected_unlocks,
    )
    unified_rows = _validate_bound_jsonl(
        metadata,
        namespace_dir=namespace_dir,
        artifact_field="unified_calendar_artifact",
        digest_field="unified_calendar_artifact_sha256",
        count_field="unified_calendar_artifact_row_count",
        expected_filename="event_unified_calendar_events.jsonl",
        run_id=run_id,
        namespace=manifest.get("artifact_namespace"),
    )
    unified_count = len(unified_rows)
    expected_unified = (
        market_no_send_calendar_materialization.canonical_unified_calendar_result(
            events,
            profile=_optional_text(manifest.get("profile")),
            artifact_namespace=_optional_text(manifest.get("artifact_namespace")),
            run_mode=_optional_text(manifest.get("run_mode")),
            run_id=run_id,
            observed_at=_optional_text(manifest.get("observed_at")),
        )
    )
    if _canonical_rows_sha256(unified_rows) != _canonical_rows_sha256(
        expected_unified.rows
    ):
        raise MarketNoSendError("campaign_calendar_unified_semantics_mismatch")
    _validate_normalization_counts(
        metadata,
        retained_count=retained_count,
        unified_count=unified_count,
    )
    _validate_expected_normalization(
        metadata,
        telemetry=expected_unified.telemetry.to_dict(),
    )


def _validate_unlock_binding(
    manifest: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    namespace_dir: Path,
    run_id: str,
    scheduled_count: int,
    expected_rows: Sequence[Mapping[str, Any]],
) -> None:
    unlock_count = _nonnegative_count(
        metadata.get("unlock_candidate_count"), field="unlock_candidate_count"
    )
    if unlock_count > scheduled_count:
        raise MarketNoSendError("campaign_calendar_unlock_count_mismatch")
    if unlock_count != len(expected_rows):
        raise MarketNoSendError("campaign_calendar_unlock_count_mismatch")
    if unlock_count == 0:
        _validate_no_unlock_artifacts(metadata, namespace_dir=namespace_dir)
        return
    if metadata.get("unlock_source_status") != "healthy_nonempty":
        raise MarketNoSendError("campaign_calendar_unlock_source_status_mismatch")
    actual_rows = _validate_bound_jsonl(
        metadata,
        namespace_dir=namespace_dir,
        artifact_field="unlock_candidate_artifact",
        digest_field="unlock_candidate_artifact_sha256",
        count_field="unlock_candidate_count",
        expected_filename="event_unlock_candidates.jsonl",
        run_id=run_id,
        namespace=manifest.get("artifact_namespace"),
    )
    if len(actual_rows) != unlock_count:
        raise MarketNoSendError("campaign_calendar_unlock_count_mismatch")
    if _canonical_rows_sha256(actual_rows) != _canonical_rows_sha256(expected_rows):
        raise MarketNoSendError("campaign_calendar_unlock_semantics_mismatch")


def _validate_no_unlock_artifacts(
    metadata: Mapping[str, Any],
    *,
    namespace_dir: Path,
) -> None:
    if metadata.get("unlock_source_status") != "not_configured":
        raise MarketNoSendError("campaign_calendar_unlock_source_status_mismatch")
    if any(
        metadata.get(field) not in (None, "")
        for field in (
            "unlock_candidate_artifact",
            "unlock_candidate_artifact_sha256",
        )
    ):
        raise MarketNoSendError("campaign_calendar_unlock_binding_unexpected")
    for filename in ("event_unlock_candidates.jsonl", "event_unlock_risk_report.md"):
        if read_regular_bytes(namespace_dir / filename, missing_ok=True) is not None:
            raise MarketNoSendError("campaign_calendar_unlock_artifact_unexpected")


def _validate_bound_jsonl(
    metadata: Mapping[str, Any],
    *,
    namespace_dir: Path,
    artifact_field: str,
    digest_field: str,
    count_field: str,
    expected_filename: str,
    run_id: str,
    namespace: Any,
) -> list[dict[str, Any]]:
    if metadata.get(artifact_field) != expected_filename:
        raise MarketNoSendError(f"campaign_calendar_{artifact_field}_invalid")
    path = namespace_dir / expected_filename
    raw = read_regular_bytes(path)
    rows = parse_jsonl_bytes(raw)
    count = _nonnegative_count(metadata.get(count_field), field=count_field)
    if any(
        (
            metadata.get(digest_field) != hashlib.sha256(raw).hexdigest(),
            count != len(rows),
            any(row.get("run_id") != run_id for row in rows),
            any(row.get("artifact_namespace") != namespace for row in rows),
            any(row.get("research_only") is not True for row in rows),
        )
    ):
        raise MarketNoSendError(f"campaign_calendar_{artifact_field}_binding_mismatch")
    return rows


def _canonical_rows_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(
            rows,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _validate_expected_normalization(
    metadata: Mapping[str, Any],
    *,
    telemetry: Mapping[str, Any],
) -> None:
    expected = {
        "normalization_input_count": telemetry.get("input_rows"),
        "normalization_valid_input_count": telemetry.get("accepted_rows"),
        "normalization_output_count": telemetry.get("output_rows"),
        "normalization_duplicate_overwrite_count": telemetry.get(
            "duplicate_overwrite_rows"
        ),
        "normalization_non_mapping_count": telemetry.get("non_mapping_rows"),
        "normalization_rejected_count": telemetry.get("rejected_rows"),
        "normalization_rejected_reason_counts": telemetry.get(
            "rejected_reason_counts"
        ),
        "unified_calendar_count": telemetry.get("output_rows"),
    }
    if any(metadata.get(field) != value for field, value in expected.items()):
        raise MarketNoSendError("campaign_calendar_normalization_semantics_mismatch")


def _validate_normalization_counts(
    metadata: Mapping[str, Any],
    *,
    retained_count: int,
    unified_count: int,
) -> None:
    counts = {
        field: _nonnegative_count(metadata.get(field), field=field)
        for field in (
            "normalization_input_count",
            "normalization_valid_input_count",
            "normalization_output_count",
            "normalization_duplicate_overwrite_count",
            "normalization_non_mapping_count",
            "normalization_rejected_count",
            "unified_calendar_count",
        )
    }
    reasons = metadata.get("normalization_rejected_reason_counts")
    if not isinstance(reasons, Mapping) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in reasons.values()
    ):
        if reasons != {}:
            raise MarketNoSendError("campaign_calendar_normalization_reasons_invalid")
    valid_input = counts["normalization_valid_input_count"]
    rejected = counts["normalization_rejected_count"]
    if any(
        (
            counts["normalization_input_count"] != retained_count,
            counts["normalization_non_mapping_count"] != 0,
            retained_count != valid_input + rejected,
            valid_input
            != counts["normalization_output_count"]
            + counts["normalization_duplicate_overwrite_count"],
            counts["normalization_output_count"] != unified_count,
            counts["unified_calendar_count"] != unified_count,
            rejected != sum(int(value) for value in reasons.values()),
        )
    ):
        raise MarketNoSendError("campaign_calendar_normalization_count_mismatch")
    expected_status = (
        "healthy_nonempty"
        if unified_count
        else "normalization_rejected"
        if rejected
        else "healthy_empty"
    )
    if metadata.get("normalization_status") != expected_status:
        raise MarketNoSendError("campaign_calendar_normalization_status_mismatch")


__all__ = ("validate_optional_calendar_snapshot",)
