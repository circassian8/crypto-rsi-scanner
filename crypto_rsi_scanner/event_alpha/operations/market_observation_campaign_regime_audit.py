"""Bounded exact-generation audit of causal control-regime input coverage.

The audit reads only already-verified private market-source snapshots attached
to campaign generation rows.  It summarizes what each immutable generation
actually knew at publication time; it never re-enriches history, fills missing
fields, calls a provider, or makes the descriptive regime policy-eligible.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from . import market_no_send_features


SCHEMA_ID = "decision_radar.control_market_regime_generation_audit"
SCHEMA_VERSION = 1
RECENT_CYCLE_LIMIT = 32
RECENT_MEMBERSHIP_WINDOW_SECONDS = 24 * 60 * 60
INTERPRETATION = "descriptive_membership_overlap_not_causal_attribution"

_STATUSES = {"empty", "unavailable", "incomplete", "ready"}
_CYCLE_STATUSES = {"ready", "incomplete", "unavailable"}
_AUDIT_KEYS = {
    "schema_id",
    "schema_version",
    "status",
    "input_generation_count",
    "verified_source_generation_count",
    "unverified_source_generation_count",
    "source_row_count",
    "complete_universe_generation_count",
    "ready_generation_count",
    "incomplete_generation_count",
    "complete_but_unavailable_generation_count",
    "unavailable_generation_count",
    "status_counts",
    "transition_count",
    "universe_change_transition_count",
    "entered_asset_event_count",
    "exited_asset_event_count",
    "incomplete_with_recent_entry_count",
    "incomplete_without_recent_entry_count",
    "recent_entry_missing_asset_event_count",
    "recent_membership_window_seconds",
    "missing_asset_generation_counts",
    "missing_asset_distinct_count",
    "missing_asset_counts_truncated",
    "first_complete_observed_at",
    "last_complete_observed_at",
    "first_ready_observed_at",
    "last_ready_observed_at",
    "latest_complete_generation",
    "recent_cycle_limit",
    "recent_cycle_summaries",
    "projection_digest",
    "interpretation",
    "selection_uses_outcomes",
    "historical_context_backfilled",
    "retained_history_mutated",
    "routing_eligible",
    "decision_policy_eligible",
    "protocol_v2_evidence_eligible",
    "provider_calls",
    "writes",
    "research_only",
}
_SUMMARY_KEYS = {
    "artifact_namespace",
    "run_id",
    "observed_at",
    "status",
    "reason",
    "source_artifact_sha256",
    "universe_row_count",
    "universe_expected_count",
    "eligible_input_count",
    "missing_input_count",
    "missing_asset_ids",
    "has_comparable_predecessor",
    "universe_changed_since_previous",
    "entered_asset_ids",
    "exited_asset_ids",
    "recent_entry_missing_asset_ids",
}


def build_control_regime_generation_audit(
    generations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize exact, already-enriched generation inputs without mutation."""

    ordered = sorted(
        (dict(row) for row in generations if isinstance(row, Mapping)),
        key=lambda row: (
            _timestamp_text(row.get("observed_at")) or "",
            _identity(row.get("artifact_namespace")),
            _identity(row.get("run_id")),
        ),
    )
    verified_count = 0
    source_row_count = 0
    status_counts: Counter[str] = Counter()
    missing_asset_counts: Counter[str] = Counter()
    complete_records: list[dict[str, Any]] = []
    previous_assets: set[str] | None = None
    continuous_entry_times: dict[str, datetime | None] = {}
    transition_count = 0
    changed_transition_count = 0
    entered_events = 0
    exited_events = 0
    incomplete_with_recent = 0
    recent_missing_events = 0

    for generation in ordered:
        snapshot = _verified_snapshot(generation)
        if snapshot is None:
            continue
        verified_count += 1
        rows, source_sha = snapshot
        source_row_count += len(rows)
        diagnostic = (
            market_no_send_features
            .point_in_time_control_market_regime_input_diagnostic(rows)
        )
        cycle_status = _cycle_status(diagnostic)
        status_counts[cycle_status] += 1
        if not _complete_universe(diagnostic, rows):
            continue

        observed_at = _parse_aware_utc(diagnostic.get("observed_at"))
        if observed_at is None:
            continue
        assets = {
            asset_id
            for row in rows
            if (asset_id := _identity(row.get("canonical_asset_id")))
        }
        expected = _nonnegative_int(diagnostic.get("universe_expected_count"))
        if len(assets) != expected:
            continue

        comparable = previous_assets is not None
        entered = sorted(assets - previous_assets) if comparable else []
        exited = sorted(previous_assets - assets) if comparable else []
        if comparable:
            transition_count += 1
            if entered or exited:
                changed_transition_count += 1
                entered_events += len(entered)
                exited_events += len(exited)
        for asset_id in exited:
            continuous_entry_times.pop(asset_id, None)
        if previous_assets is None:
            continuous_entry_times = {asset_id: None for asset_id in assets}
        else:
            for asset_id in entered:
                continuous_entry_times[asset_id] = observed_at

        missing = sorted(
            _identity(item.get("canonical_asset_id"))
            for item in diagnostic.get("missing_inputs") or ()
            if isinstance(item, Mapping)
            and _identity(item.get("canonical_asset_id"))
        )
        missing_asset_counts.update(missing)
        recent_missing = sorted(
            asset_id
            for asset_id in missing
            if _within_recent_membership_window(
                continuous_entry_times.get(asset_id),
                observed_at,
            )
        )
        if cycle_status == "incomplete" and recent_missing:
            incomplete_with_recent += 1
        recent_missing_events += len(recent_missing)
        record = {
            "artifact_namespace": _identity(
                generation.get("artifact_namespace")
            ),
            "run_id": _identity(generation.get("run_id")),
            "observed_at": observed_at.isoformat(),
            "status": cycle_status,
            "reason": diagnostic.get("reason"),
            "source_artifact_sha256": source_sha,
            "universe_row_count": _nonnegative_int(
                diagnostic.get("universe_row_count")
            ),
            "universe_expected_count": expected,
            "eligible_input_count": _nonnegative_int(
                diagnostic.get("eligible_input_count")
            ),
            "missing_input_count": _nonnegative_int(
                diagnostic.get("missing_input_count")
            ),
            "missing_asset_ids": missing,
            "has_comparable_predecessor": comparable,
            "universe_changed_since_previous": bool(entered or exited),
            "entered_asset_ids": entered,
            "exited_asset_ids": exited,
            "recent_entry_missing_asset_ids": recent_missing,
        }
        complete_records.append(record)
        previous_assets = assets

    ready_records = [row for row in complete_records if row["status"] == "ready"]
    incomplete_records = [
        row for row in complete_records if row["status"] == "incomplete"
    ]
    complete_unavailable = [
        row for row in complete_records if row["status"] == "unavailable"
    ]
    status = (
        "empty"
        if not ordered
        else "unavailable"
        if not complete_records
        else "ready"
        if complete_records[-1]["status"] == "ready"
        else "incomplete"
    )
    recent_records = complete_records[-RECENT_CYCLE_LIMIT:]
    missing_asset_items = sorted(
        missing_asset_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )
    bounded_missing_asset_items = missing_asset_items[:256]
    value = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "input_generation_count": len(ordered),
        "verified_source_generation_count": verified_count,
        "unverified_source_generation_count": len(ordered) - verified_count,
        "source_row_count": source_row_count,
        "complete_universe_generation_count": len(complete_records),
        "ready_generation_count": len(ready_records),
        "incomplete_generation_count": len(incomplete_records),
        "complete_but_unavailable_generation_count": len(
            complete_unavailable
        ),
        "unavailable_generation_count": status_counts["unavailable"],
        "status_counts": dict(sorted(status_counts.items())),
        "transition_count": transition_count,
        "universe_change_transition_count": changed_transition_count,
        "entered_asset_event_count": entered_events,
        "exited_asset_event_count": exited_events,
        "incomplete_with_recent_entry_count": incomplete_with_recent,
        "incomplete_without_recent_entry_count": (
            len(incomplete_records) - incomplete_with_recent
        ),
        "recent_entry_missing_asset_event_count": recent_missing_events,
        "recent_membership_window_seconds": (
            RECENT_MEMBERSHIP_WINDOW_SECONDS
        ),
        "missing_asset_generation_counts": dict(
            sorted(bounded_missing_asset_items)
        ),
        "missing_asset_distinct_count": len(missing_asset_items),
        "missing_asset_counts_truncated": len(missing_asset_items) > len(
            bounded_missing_asset_items
        ),
        "first_complete_observed_at": (
            complete_records[0]["observed_at"] if complete_records else None
        ),
        "last_complete_observed_at": (
            complete_records[-1]["observed_at"] if complete_records else None
        ),
        "first_ready_observed_at": (
            ready_records[0]["observed_at"] if ready_records else None
        ),
        "last_ready_observed_at": (
            ready_records[-1]["observed_at"] if ready_records else None
        ),
        "latest_complete_generation": (
            dict(complete_records[-1]) if complete_records else None
        ),
        "recent_cycle_limit": RECENT_CYCLE_LIMIT,
        "recent_cycle_summaries": [dict(row) for row in recent_records],
        "projection_digest": _sha256_json(complete_records),
        "interpretation": INTERPRETATION,
        "selection_uses_outcomes": False,
        "historical_context_backfilled": False,
        "retained_history_mutated": False,
        "routing_eligible": False,
        "decision_policy_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }
    errors = validate_control_regime_generation_audit(value)
    if errors:  # pragma: no cover - builder and validator share the contract
        raise AssertionError("control regime generation audit invalid: " + ";".join(errors))
    return value


def validate_control_regime_generation_audit(value: object) -> list[str]:
    """Validate the closed bounded audit projection."""

    if not isinstance(value, Mapping):
        return ["audit_not_mapping"]
    errors: list[str] = []
    if set(value) != _AUDIT_KEYS:
        errors.append("audit_keys_invalid")
    if value.get("schema_id") != SCHEMA_ID:
        errors.append("schema_id_invalid")
    if value.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if value.get("status") not in _STATUSES:
        errors.append("status_invalid")
    counts = {
        field: value.get(field)
        for field in (
            "input_generation_count",
            "verified_source_generation_count",
            "unverified_source_generation_count",
            "source_row_count",
            "complete_universe_generation_count",
            "ready_generation_count",
            "incomplete_generation_count",
            "complete_but_unavailable_generation_count",
            "unavailable_generation_count",
            "transition_count",
            "universe_change_transition_count",
            "entered_asset_event_count",
            "exited_asset_event_count",
            "incomplete_with_recent_entry_count",
            "incomplete_without_recent_entry_count",
            "recent_entry_missing_asset_event_count",
        )
    }
    if any(type(item) is not int or item < 0 for item in counts.values()):
        errors.append("count_invalid")
    else:
        if counts["input_generation_count"] != (
            counts["verified_source_generation_count"]
            + counts["unverified_source_generation_count"]
        ):
            errors.append("source_generation_count_not_closed")
        if counts["complete_universe_generation_count"] != (
            counts["ready_generation_count"]
            + counts["incomplete_generation_count"]
            + counts["complete_but_unavailable_generation_count"]
        ):
            errors.append("complete_generation_count_not_closed")
        if counts["incomplete_generation_count"] != (
            counts["incomplete_with_recent_entry_count"]
            + counts["incomplete_without_recent_entry_count"]
        ):
            errors.append("incomplete_generation_count_not_closed")
        maximum_transitions = max(
            0, counts["complete_universe_generation_count"] - 1
        )
        if counts["transition_count"] != maximum_transitions:
            errors.append("transition_count_invalid")
        if counts["universe_change_transition_count"] > counts["transition_count"]:
            errors.append("universe_change_count_invalid")

    status_counts = value.get("status_counts")
    if not _count_mapping(status_counts, allowed=_CYCLE_STATUSES):
        errors.append("status_counts_invalid")
    elif sum(status_counts.values()) != counts.get(
        "verified_source_generation_count", -1
    ):
        errors.append("status_counts_not_closed")
    elif status_counts.get("unavailable", 0) != counts.get(
        "unavailable_generation_count"
    ):
        errors.append("unavailable_generation_count_mismatch")

    missing_counts = value.get("missing_asset_generation_counts")
    if not _count_mapping(missing_counts, bounded_keys=True):
        errors.append("missing_asset_generation_counts_invalid")
        missing_counts = {}
    missing_distinct = value.get("missing_asset_distinct_count")
    missing_truncated = value.get("missing_asset_counts_truncated")
    if not (
        type(missing_distinct) is int
        and missing_distinct >= len(missing_counts)
        and type(missing_truncated) is bool
        and missing_truncated == (missing_distinct > len(missing_counts))
    ):
        errors.append("missing_asset_count_bound_invalid")
    if value.get("recent_membership_window_seconds") != (
        RECENT_MEMBERSHIP_WINDOW_SECONDS
    ):
        errors.append("recent_membership_window_seconds_invalid")
    if value.get("recent_cycle_limit") != RECENT_CYCLE_LIMIT:
        errors.append("recent_cycle_limit_invalid")
    summaries = value.get("recent_cycle_summaries")
    if not isinstance(summaries, list) or len(summaries) > RECENT_CYCLE_LIMIT:
        errors.append("recent_cycle_summaries_invalid")
        summaries = []
    for index, summary in enumerate(summaries):
        _validate_summary(summary, label=f"summary_{index}", errors=errors)
    latest = value.get("latest_complete_generation")
    if counts.get("complete_universe_generation_count", 0) == 0:
        if latest is not None or summaries:
            errors.append("empty_latest_generation_invalid")
    else:
        _validate_summary(latest, label="latest", errors=errors)
        if not summaries or latest != summaries[-1]:
            errors.append("latest_generation_mismatch")
    expected_status = (
        "empty"
        if counts.get("input_generation_count") == 0
        else "unavailable"
        if counts.get("complete_universe_generation_count") == 0
        else "ready"
        if isinstance(latest, Mapping) and latest.get("status") == "ready"
        else "incomplete"
    )
    if value.get("status") != expected_status:
        errors.append("status_derivation_mismatch")
    complete_times = (
        value.get("first_complete_observed_at"),
        value.get("last_complete_observed_at"),
    )
    ready_times = (
        value.get("first_ready_observed_at"),
        value.get("last_ready_observed_at"),
    )
    if counts.get("complete_universe_generation_count", 0):
        if any(_parse_aware_utc(item) is None for item in complete_times):
            errors.append("complete_observed_at_invalid")
    elif any(item is not None for item in complete_times):
        errors.append("complete_observed_at_must_be_none")
    if counts.get("ready_generation_count", 0):
        if any(_parse_aware_utc(item) is None for item in ready_times):
            errors.append("ready_observed_at_invalid")
    elif any(item is not None for item in ready_times):
        errors.append("ready_observed_at_must_be_none")
    if not _sha256(value.get("projection_digest")):
        errors.append("projection_digest_invalid")
    if value.get("interpretation") != INTERPRETATION:
        errors.append("interpretation_invalid")
    fixed = {
        "selection_uses_outcomes": False,
        "historical_context_backfilled": False,
        "retained_history_mutated": False,
        "routing_eligible": False,
        "decision_policy_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }
    for field, expected in fixed.items():
        if not (
            type(value.get(field)) is type(expected)
            and value.get(field) == expected
        ):
            errors.append(f"{field}_invalid")
    return sorted(set(errors))


def _verified_snapshot(
    generation: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str] | None:
    rows = generation.get("_market_source_snapshot_rows")
    digest = generation.get("_market_source_snapshot_sha256")
    if not (
        generation.get("_market_source_snapshot_verified") is True
        and isinstance(rows, (list, tuple))
        and all(isinstance(row, Mapping) for row in rows)
        and _sha256(digest)
        and generation.get("_market_source_snapshot_row_count") == len(rows)
    ):
        return None
    return [dict(row) for row in rows], str(digest)


def _cycle_status(diagnostic: Mapping[str, Any]) -> str:
    status = diagnostic.get("status")
    return status if status in _CYCLE_STATUSES else "unavailable"


def _complete_universe(
    diagnostic: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> bool:
    expected = diagnostic.get("universe_expected_count")
    replayed = diagnostic.get("replayed_control_market_regime")
    return bool(
        type(expected) is int
        and expected > 0
        and len(rows) == expected
        and isinstance(replayed, Mapping)
        and replayed.get("reason") != "current_cycle_context_invalid"
        and all(row.get("point_in_time_universe_member") is True for row in rows)
    )


def _within_recent_membership_window(
    entered_at: datetime | None,
    observed_at: datetime,
) -> bool:
    if entered_at is None:
        return False
    seconds = (observed_at - entered_at).total_seconds()
    return 0 <= seconds < RECENT_MEMBERSHIP_WINDOW_SECONDS


def _validate_summary(
    value: object,
    *,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, Mapping) or set(value) != _SUMMARY_KEYS:
        errors.append(f"{label}_keys_invalid")
        return
    if not _identity(value.get("artifact_namespace")):
        errors.append(f"{label}_namespace_invalid")
    if not _identity(value.get("run_id")):
        errors.append(f"{label}_run_id_invalid")
    if _parse_aware_utc(value.get("observed_at")) is None:
        errors.append(f"{label}_observed_at_invalid")
    if value.get("status") not in _CYCLE_STATUSES:
        errors.append(f"{label}_status_invalid")
    if value.get("reason") is not None and not _identity(value.get("reason")):
        errors.append(f"{label}_reason_invalid")
    if not _sha256(value.get("source_artifact_sha256")):
        errors.append(f"{label}_source_digest_invalid")
    for field in (
        "universe_row_count",
        "universe_expected_count",
        "eligible_input_count",
        "missing_input_count",
    ):
        if type(value.get(field)) is not int or value.get(field) < 0:
            errors.append(f"{label}_{field}_invalid")
    if all(
        type(value.get(field)) is int and value.get(field) >= 0
        for field in (
            "universe_row_count",
            "eligible_input_count",
            "missing_input_count",
        )
    ) and value.get("eligible_input_count") + value.get(
        "missing_input_count"
    ) != value.get("universe_row_count"):
        errors.append(f"{label}_input_count_not_closed")
    for field in (
        "missing_asset_ids",
        "entered_asset_ids",
        "exited_asset_ids",
        "recent_entry_missing_asset_ids",
    ):
        items = value.get(field)
        if not isinstance(items, list) or not all(
            isinstance(item, str) for item in items
        ):
            errors.append(f"{label}_{field}_invalid")
            continue
        if not (
            items == sorted(set(items))
            and len(items) <= 256
            and all(_identity(item) == item for item in items)
        ):
            errors.append(f"{label}_{field}_invalid")
    missing_asset_ids = value.get("missing_asset_ids")
    recent_asset_ids = value.get("recent_entry_missing_asset_ids")
    if (
        isinstance(missing_asset_ids, list)
        and type(value.get("missing_input_count")) is int
        and len(missing_asset_ids) != value.get("missing_input_count")
    ):
        errors.append(f"{label}_missing_asset_count_mismatch")
    if (
        isinstance(missing_asset_ids, list)
        and isinstance(recent_asset_ids, list)
        and all(isinstance(item, str) for item in (*missing_asset_ids, *recent_asset_ids))
        and not set(recent_asset_ids).issubset(missing_asset_ids)
    ):
        errors.append(f"{label}_recent_missing_not_subset")
    if type(value.get("has_comparable_predecessor")) is not bool:
        errors.append(f"{label}_predecessor_flag_invalid")
    if type(value.get("universe_changed_since_previous")) is not bool:
        errors.append(f"{label}_change_flag_invalid")
    elif value.get("universe_changed_since_previous") != bool(
        value.get("entered_asset_ids") or value.get("exited_asset_ids")
    ):
        errors.append(f"{label}_change_flag_mismatch")
    if not value.get("has_comparable_predecessor") and any((
        value.get("universe_changed_since_previous"),
        value.get("entered_asset_ids"),
        value.get("exited_asset_ids"),
        value.get("recent_entry_missing_asset_ids"),
    )):
        errors.append(f"{label}_first_cycle_transition_invalid")


def _count_mapping(
    value: object,
    *,
    allowed: set[str] | None = None,
    bounded_keys: bool = False,
) -> bool:
    return (
        isinstance(value, Mapping)
        and len(value) <= 256
        and all(
            isinstance(key, str)
            and (not bounded_keys or _identity(key) == key)
            and (allowed is None or key in allowed)
            and type(count) is int
            and count >= 0
            for key, count in value.items()
        )
    )


def _nonnegative_int(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _identity(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return text if 0 < len(text) <= 256 else ""


def _timestamp_text(value: object) -> str:
    parsed = _parse_aware_utc(value)
    return parsed.isoformat() if parsed is not None else ""


def _parse_aware_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _sha256(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = (
    "INTERPRETATION",
    "RECENT_CYCLE_LIMIT",
    "RECENT_MEMBERSHIP_WINDOW_SECONDS",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_control_regime_generation_audit",
    "validate_control_regime_generation_audit",
)
