"""Forward-only strict checks for market snapshot unit-health evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import check_registry
from ._utils import Messages, ctx_value
from ...operations import common, market_no_send_features


_ACTIVATION_TIME = datetime(2026, 7, 19, tzinfo=timezone.utc)
_MANIFEST_FILENAME = "event_market_no_send_generation.json"
_SNAPSHOT_FILENAME = "event_market_state_snapshots.jsonl"
_QUALITY_FIELDS = (
    "market_snapshot_unit_validation_contract_version",
    "market_snapshot_unit_validation_status",
    "market_snapshot_unit_warning_row_count",
    "market_snapshot_unit_warning_count",
    "market_snapshot_unit_warning_counts",
)


def apply_checks(ctx: object, blockers: Messages) -> None:
    namespace_dir_value = ctx_value(ctx, "namespace_dir", None)
    if not namespace_dir_value:
        return
    namespace_dir = Path(str(namespace_dir_value)).expanduser()
    manifest = common.read_json(namespace_dir / _MANIFEST_FILENAME)
    if not manifest or manifest.get("row_type") != "event_market_no_send_generation":
        return
    rows = common.read_jsonl(namespace_dir / _SNAPSHOT_FILENAME)
    for error in validate_snapshot_unit_health(manifest, rows):
        blockers.append(
            check_registry.format_check_message(
                "namespace.operator_artifact_coherence",
                error,
            )
        )


def validate_snapshot_unit_health(
    manifest: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """Validate new closed unit-health fields while preserving old evidence."""

    marker = manifest.get("market_snapshot_unit_validation_contract_version")
    if marker is None:
        return (
            ("market_snapshot_unit_validation_contract_missing",)
            if _requires_contract(manifest)
            else ()
        )
    if (
        isinstance(marker, bool)
        or marker
        != market_no_send_features.MARKET_SNAPSHOT_UNIT_VALIDATION_CONTRACT_VERSION
    ):
        return ("market_snapshot_unit_validation_contract_invalid",)

    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    actual = market_no_send_features.market_quality_counts_from_rows(materialized)
    errors: list[str] = []
    expected_snapshot_count = manifest.get("market_snapshot_count")
    if (
        isinstance(expected_snapshot_count, bool)
        or not isinstance(expected_snapshot_count, int)
        or expected_snapshot_count != len(materialized)
    ):
        errors.append("market_snapshot_unit_validation_snapshot_count_mismatch")
    for field in _QUALITY_FIELDS:
        if manifest.get(field) != actual.get(field):
            errors.append(f"market_snapshot_unit_validation_manifest_mismatch:{field}")
    if actual["market_snapshot_unit_warning_row_count"]:
        errors.append(
            "market_snapshot_unit_validation_failed:"
            f"warning_rows={actual['market_snapshot_unit_warning_row_count']},"
            f"warnings={actual['market_snapshot_unit_warning_count']}"
        )
    return tuple(errors)


def _requires_contract(manifest: Mapping[str, Any]) -> bool:
    if (
        manifest.get("status") != "complete"
        or manifest.get("data_acquisition_mode") != "live_provider"
    ):
        return False
    observed = _parse_time(manifest.get("observed_at"))
    return observed is None or observed >= _ACTIVATION_TIME


def _parse_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


__all__ = ("apply_checks", "validate_snapshot_unit_health")
