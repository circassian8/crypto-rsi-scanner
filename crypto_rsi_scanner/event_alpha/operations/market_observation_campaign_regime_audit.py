"""Bounded exact-generation audit of causal control-regime input coverage.

The audit reads only already-verified private market-source snapshots attached
to campaign generation rows.  It summarizes what each immutable generation
actually knew at publication time; it never re-enriches history, fills missing
fields, calls a provider, or makes the descriptive regime policy-eligible.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ..radar import market_history as event_market_history
from . import market_no_send_features


SCHEMA_ID = "decision_radar.control_market_regime_generation_audit"
SCHEMA_VERSION = 4
LEGACY_SCHEMA_VERSION = 3
RECENT_CYCLE_LIMIT = 32
RECENT_MEMBERSHIP_WINDOW_SECONDS = 24 * 60 * 60
INTERPRETATION = "descriptive_membership_overlap_not_causal_attribution"
MEMBERSHIP_CLOCK_SCOPE = (
    "prospective_complete_point_in_time_universes_only"
)

_STATUSES = {"empty", "unavailable", "incomplete", "ready"}
_CYCLE_STATUSES = {"ready", "incomplete", "unavailable"}
CADENCE_GAP_AUDIT_SCHEMA_ID = (
    "decision_radar.control_regime_observation_cadence_gap_audit"
)
CADENCE_GAP_AUDIT_SCHEMA_VERSION = 1
CADENCE_GAP_EXAMPLE_LIMIT = 16
CADENCE_GAP_INTERPRETATION = (
    "descriptive_complete_generation_cadence_not_anchor_causation"
)

_AUDIT_KEYS_V3 = {
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
    "membership_clock_scope",
    "precontract_history_used_for_membership_clock",
    "latest_missing_input_anchor_audit",
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
_AUDIT_KEYS = _AUDIT_KEYS_V3 | {"observation_cadence_gap_audit"}
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
    "missing_input_membership_context",
}
_MEMBERSHIP_CONTEXT_KEYS = {
    "canonical_asset_id",
    "membership_start_known",
    "membership_start_basis",
    "continuous_membership_started_at",
    "continuous_membership_age_seconds",
    "within_recent_membership_window",
    "anchor_eligibility_inferred",
}
_ANCHOR_AUDIT_KEYS = {
    "status",
    "reason",
    "generation_observed_at",
    "horizon_hours",
    "retained_history_status",
    "retained_history_artifact",
    "retained_history_sha256",
    "retained_history_size_bytes",
    "retained_history_row_count",
    "retained_history_binding_source",
    "missing_input_count",
    "diagnostics",
    "all_missing_inputs_explained",
    "source_scope",
    "future_endpoint_eligibility_inferred",
    "retained_history_mutated",
    "provider_calls",
    "writes",
    "research_only",
}
_ANCHOR_AUDIT_STATUSES = {
    "observed",
    "not_required",
    "unavailable",
    "inconsistent",
}
_CADENCE_GAP_AUDIT_KEYS = {
    "schema_id",
    "schema_version",
    "status",
    "complete_generation_count",
    "adjacent_interval_count",
    "return_horizon_hours",
    "anchor_tolerance_seconds",
    "within_anchor_tolerance_interval_count",
    "exceeding_anchor_tolerance_interval_count",
    "latest_interval",
    "maximum_interval",
    "gap_example_limit",
    "gap_examples",
    "gap_examples_truncated",
    "source_generation_clock_sha256",
    "source_scope",
    "interpretation",
    "future_endpoint_eligibility_inferred",
    "selection_uses_outcomes",
    "historical_context_backfilled",
    "routing_eligible",
    "decision_policy_eligible",
    "protocol_v2_evidence_eligible",
    "provider_calls",
    "writes",
    "research_only",
}
_CADENCE_INTERVAL_KEYS = {
    "start_artifact_namespace",
    "start_run_id",
    "start_observed_at",
    "end_artifact_namespace",
    "end_run_id",
    "end_observed_at",
    "interval_seconds",
    "exceeds_anchor_tolerance",
    "excess_seconds",
}
_CADENCE_GAP_STATUSES = {
    "empty",
    "insufficient_history",
    "within_anchor_tolerance",
    "gaps_observed",
}


def build_observation_cadence_gap_audit(
    complete_generations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Measure complete-generation clock gaps against the 24h anchor tolerance."""

    clocks: list[dict[str, Any]] = []
    for index, raw in enumerate(complete_generations):
        if not isinstance(raw, Mapping):
            raise ValueError(f"cadence generation {index} is not a mapping")
        namespace = _identity(raw.get("artifact_namespace"))
        run_id = _identity(raw.get("run_id"))
        observed_at = _parse_aware_utc(raw.get("observed_at"))
        if not namespace or not run_id or observed_at is None:
            raise ValueError(f"cadence generation {index} identity is invalid")
        clocks.append({
            "artifact_namespace": namespace,
            "run_id": run_id,
            "observed_at": observed_at,
        })
    clocks.sort(key=lambda row: (
        row["observed_at"],
        row["artifact_namespace"],
        row["run_id"],
    ))
    tolerance_seconds = int(
        event_market_history.return_anchor_tolerance(hours=24).total_seconds()
    )
    intervals = [
        _cadence_interval(start, end, tolerance_seconds=tolerance_seconds)
        for start, end in zip(clocks, clocks[1:])
    ]
    gaps = [row for row in intervals if row["exceeds_anchor_tolerance"]]
    bounded_gaps = gaps[-CADENCE_GAP_EXAMPLE_LIMIT:]
    status = (
        "empty"
        if not clocks
        else "insufficient_history"
        if len(clocks) == 1
        else "gaps_observed"
        if gaps
        else "within_anchor_tolerance"
    )
    source_clock_values = [
        {
            "artifact_namespace": row["artifact_namespace"],
            "run_id": row["run_id"],
            "observed_at": row["observed_at"].isoformat(),
        }
        for row in clocks
    ]
    value = {
        "schema_id": CADENCE_GAP_AUDIT_SCHEMA_ID,
        "schema_version": CADENCE_GAP_AUDIT_SCHEMA_VERSION,
        "status": status,
        "complete_generation_count": len(clocks),
        "adjacent_interval_count": len(intervals),
        "return_horizon_hours": 24,
        "anchor_tolerance_seconds": tolerance_seconds,
        "within_anchor_tolerance_interval_count": len(intervals) - len(gaps),
        "exceeding_anchor_tolerance_interval_count": len(gaps),
        "latest_interval": dict(intervals[-1]) if intervals else None,
        "maximum_interval": (
            dict(max(intervals, key=lambda row: row["interval_seconds"]))
            if intervals
            else None
        ),
        "gap_example_limit": CADENCE_GAP_EXAMPLE_LIMIT,
        "gap_examples": [dict(row) for row in bounded_gaps],
        "gap_examples_truncated": len(gaps) > len(bounded_gaps),
        "source_generation_clock_sha256": _sha256_json(source_clock_values),
        "source_scope": "complete_verified_generation_observation_clocks",
        "interpretation": CADENCE_GAP_INTERPRETATION,
        "future_endpoint_eligibility_inferred": False,
        "selection_uses_outcomes": False,
        "historical_context_backfilled": False,
        "routing_eligible": False,
        "decision_policy_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }
    errors = validate_observation_cadence_gap_audit(value)
    if errors:  # pragma: no cover - builder and validator share the contract
        raise AssertionError("observation cadence gap audit invalid: " + ";".join(errors))
    return value


def validate_observation_cadence_gap_audit(value: object) -> list[str]:
    """Validate the bounded, policy-ineligible generation-clock projection."""

    if not isinstance(value, Mapping):
        return ["cadence_gap_audit_not_mapping"]
    errors: list[str] = []
    if set(value) != _CADENCE_GAP_AUDIT_KEYS:
        errors.append("cadence_gap_audit_keys_invalid")
    if value.get("schema_id") != CADENCE_GAP_AUDIT_SCHEMA_ID:
        errors.append("cadence_gap_schema_id_invalid")
    if value.get("schema_version") != CADENCE_GAP_AUDIT_SCHEMA_VERSION:
        errors.append("cadence_gap_schema_version_invalid")
    complete = value.get("complete_generation_count")
    adjacent = value.get("adjacent_interval_count")
    within = value.get("within_anchor_tolerance_interval_count")
    exceeding = value.get("exceeding_anchor_tolerance_interval_count")
    if any(type(item) is not int or item < 0 for item in (complete, adjacent, within, exceeding)):
        errors.append("cadence_gap_count_invalid")
    else:
        if adjacent != max(0, complete - 1):
            errors.append("cadence_gap_adjacent_count_invalid")
        if within + exceeding != adjacent:
            errors.append("cadence_gap_interval_count_not_closed")
    expected_tolerance = int(
        event_market_history.return_anchor_tolerance(hours=24).total_seconds()
    )
    if (
        value.get("return_horizon_hours") != 24
        or value.get("anchor_tolerance_seconds") != expected_tolerance
    ):
        errors.append("cadence_gap_anchor_policy_invalid")
    if value.get("gap_example_limit") != CADENCE_GAP_EXAMPLE_LIMIT:
        errors.append("cadence_gap_example_limit_invalid")
    latest = value.get("latest_interval")
    maximum = value.get("maximum_interval")
    if type(adjacent) is int and adjacent == 0:
        if latest is not None or maximum is not None:
            errors.append("cadence_gap_empty_intervals_invalid")
    else:
        _validate_cadence_interval(
            latest,
            tolerance_seconds=expected_tolerance,
            label="cadence_gap_latest",
            errors=errors,
        )
        _validate_cadence_interval(
            maximum,
            tolerance_seconds=expected_tolerance,
            label="cadence_gap_maximum",
            errors=errors,
        )
        if (
            isinstance(latest, Mapping)
            and isinstance(maximum, Mapping)
            and _finite_nonnegative(latest.get("interval_seconds"))
            and _finite_nonnegative(maximum.get("interval_seconds"))
            and maximum.get("interval_seconds") < latest.get("interval_seconds")
        ):
            errors.append("cadence_gap_maximum_interval_invalid")
    examples = value.get("gap_examples")
    if not isinstance(examples, list) or len(examples) > CADENCE_GAP_EXAMPLE_LIMIT:
        errors.append("cadence_gap_examples_invalid")
        examples = []
    for index, row in enumerate(examples):
        _validate_cadence_interval(
            row,
            tolerance_seconds=expected_tolerance,
            label=f"cadence_gap_example_{index}",
            errors=errors,
        )
        if isinstance(row, Mapping) and row.get("exceeds_anchor_tolerance") is not True:
            errors.append(f"cadence_gap_example_{index}_not_gap")
    example_times = [
        _parse_aware_utc(row.get("end_observed_at"))
        for row in examples
        if isinstance(row, Mapping)
    ]
    if any(item is None for item in example_times) or example_times != sorted(example_times):
        errors.append("cadence_gap_examples_order_invalid")
    truncated = value.get("gap_examples_truncated")
    if type(truncated) is not bool or type(exceeding) is not int:
        errors.append("cadence_gap_examples_bound_invalid")
    elif truncated:
        if not (exceeding > CADENCE_GAP_EXAMPLE_LIMIT and len(examples) == CADENCE_GAP_EXAMPLE_LIMIT):
            errors.append("cadence_gap_examples_bound_invalid")
    elif len(examples) != exceeding:
        errors.append("cadence_gap_examples_bound_invalid")
    expected_status = (
        "empty"
        if complete == 0
        else "insufficient_history"
        if complete == 1
        else "gaps_observed"
        if type(exceeding) is int and exceeding > 0
        else "within_anchor_tolerance"
    )
    if value.get("status") not in _CADENCE_GAP_STATUSES or value.get("status") != expected_status:
        errors.append("cadence_gap_status_invalid")
    if not _sha256(value.get("source_generation_clock_sha256")):
        errors.append("cadence_gap_source_digest_invalid")
    fixed = {
        "source_scope": "complete_verified_generation_observation_clocks",
        "interpretation": CADENCE_GAP_INTERPRETATION,
        "future_endpoint_eligibility_inferred": False,
        "selection_uses_outcomes": False,
        "historical_context_backfilled": False,
        "routing_eligible": False,
        "decision_policy_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }
    for field, expected in fixed.items():
        if type(value.get(field)) is not type(expected) or value.get(field) != expected:
            errors.append(f"cadence_gap_{field}_invalid")
    if type(exceeding) is int and isinstance(maximum, Mapping):
        if maximum.get("exceeds_anchor_tolerance") is not (exceeding > 0):
            errors.append("cadence_gap_maximum_status_invalid")
    return sorted(set(errors))


def _cadence_interval(
    start: Mapping[str, Any],
    end: Mapping[str, Any],
    *,
    tolerance_seconds: int,
) -> dict[str, Any]:
    interval_seconds = _rounded_seconds(
        (end["observed_at"] - start["observed_at"]).total_seconds()
    )
    exceeds = interval_seconds > tolerance_seconds
    return {
        "start_artifact_namespace": start["artifact_namespace"],
        "start_run_id": start["run_id"],
        "start_observed_at": start["observed_at"].isoformat(),
        "end_artifact_namespace": end["artifact_namespace"],
        "end_run_id": end["run_id"],
        "end_observed_at": end["observed_at"].isoformat(),
        "interval_seconds": interval_seconds,
        "exceeds_anchor_tolerance": exceeds,
        "excess_seconds": _rounded_seconds(
            max(0.0, interval_seconds - tolerance_seconds)
        ),
    }


def _validate_cadence_interval(
    value: object,
    *,
    tolerance_seconds: int,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, Mapping) or set(value) != _CADENCE_INTERVAL_KEYS:
        errors.append(f"{label}_keys_invalid")
        return
    if not all(
        _identity(value.get(field))
        for field in (
            "start_artifact_namespace",
            "start_run_id",
            "end_artifact_namespace",
            "end_run_id",
        )
    ):
        errors.append(f"{label}_identity_invalid")
    start = _parse_aware_utc(value.get("start_observed_at"))
    end = _parse_aware_utc(value.get("end_observed_at"))
    seconds = value.get("interval_seconds")
    excess = value.get("excess_seconds")
    if (
        start is None
        or end is None
        or end < start
        or not _finite_nonnegative(seconds)
        or not _finite_nonnegative(excess)
    ):
        errors.append(f"{label}_clock_invalid")
        return
    expected_seconds = _rounded_seconds((end - start).total_seconds())
    expected_exceeds = expected_seconds > tolerance_seconds
    expected_excess = _rounded_seconds(max(0.0, expected_seconds - tolerance_seconds))
    if (
        seconds != expected_seconds
        or value.get("exceeds_anchor_tolerance") is not expected_exceeds
        or excess != expected_excess
    ):
        errors.append(f"{label}_derivation_invalid")


def _finite_nonnegative(value: object) -> bool:
    return bool(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) >= 0
    )


def _rounded_seconds(value: float) -> float:
    rounded = round(float(value), 6)
    return 0.0 if rounded == 0 else rounded


def build_control_regime_generation_audit(
    generations: Sequence[Mapping[str, Any]],
    *,
    retained_history_snapshot: Mapping[str, Any] | None = None,
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
    latest_complete_source_rows: list[dict[str, Any]] = []

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
        membership_context = [
            _missing_membership_context(
                asset_id,
                entered_at=continuous_entry_times.get(asset_id),
                observed_at=observed_at,
            )
            for asset_id in missing
        ]
        recent_missing = [
            row["canonical_asset_id"]
            for row in membership_context
            if row["within_recent_membership_window"]
        ]
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
            "missing_input_membership_context": membership_context,
        }
        complete_records.append(record)
        latest_complete_source_rows = [dict(row) for row in rows]
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
    latest_anchor_audit = _latest_missing_input_anchor_audit(
        complete_records[-1] if complete_records else None,
        latest_complete_source_rows,
        retained_history_snapshot,
    )
    cadence_gap_audit = build_observation_cadence_gap_audit(complete_records)
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
        "membership_clock_scope": MEMBERSHIP_CLOCK_SCOPE,
        "precontract_history_used_for_membership_clock": False,
        "latest_missing_input_anchor_audit": latest_anchor_audit,
        "observation_cadence_gap_audit": cadence_gap_audit,
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
    version = value.get("schema_version")
    expected_keys = (
        _AUDIT_KEYS
        if version == SCHEMA_VERSION
        else _AUDIT_KEYS_V3
        if version == LEGACY_SCHEMA_VERSION
        else _AUDIT_KEYS
    )
    if set(value) != expected_keys:
        errors.append("audit_keys_invalid")
    if value.get("schema_id") != SCHEMA_ID:
        errors.append("schema_id_invalid")
    if version not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
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
    if value.get("membership_clock_scope") != MEMBERSHIP_CLOCK_SCOPE:
        errors.append("membership_clock_scope_invalid")
    _validate_anchor_audit(
        value.get("latest_missing_input_anchor_audit"),
        latest=value.get("latest_complete_generation"),
        errors=errors,
    )
    if version == SCHEMA_VERSION:
        cadence_audit = value.get("observation_cadence_gap_audit")
        errors.extend(validate_observation_cadence_gap_audit(cadence_audit))
        if (
            isinstance(cadence_audit, Mapping)
            and cadence_audit.get("complete_generation_count")
            != counts.get("complete_universe_generation_count")
        ):
            errors.append("cadence_gap_complete_generation_count_mismatch")
        if (
            isinstance(cadence_audit, Mapping)
            and cadence_audit.get("adjacent_interval_count")
            != counts.get("transition_count")
        ):
            errors.append("cadence_gap_transition_count_mismatch")
        if (
            isinstance(cadence_audit, Mapping)
            and counts.get("complete_universe_generation_count", 0) > 1
            and isinstance(cadence_audit.get("latest_interval"), Mapping)
            and cadence_audit["latest_interval"].get("end_observed_at")
            != value.get("last_complete_observed_at")
        ):
            errors.append("cadence_gap_latest_clock_mismatch")
    fixed = {
        "precontract_history_used_for_membership_clock": False,
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


def _missing_membership_context(
    asset_id: str,
    *,
    entered_at: datetime | None,
    observed_at: datetime,
) -> dict[str, Any]:
    start_known = entered_at is not None
    age_seconds = (
        int((observed_at - entered_at).total_seconds())
        if entered_at is not None
        else None
    )
    return {
        "canonical_asset_id": asset_id,
        "membership_start_known": start_known,
        "membership_start_basis": (
            "observed_entry"
            if start_known
            else "unknown_before_first_complete_generation"
        ),
        "continuous_membership_started_at": (
            entered_at.isoformat() if entered_at is not None else None
        ),
        "continuous_membership_age_seconds": age_seconds,
        "within_recent_membership_window": (
            start_known
            and age_seconds is not None
            and age_seconds < RECENT_MEMBERSHIP_WINDOW_SECONDS
        ),
        "anchor_eligibility_inferred": False,
    }


def _latest_missing_input_anchor_audit(
    latest: Mapping[str, Any] | None,
    latest_source_rows: Sequence[Mapping[str, Any]],
    retained_history_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    snapshot = (
        dict(retained_history_snapshot)
        if isinstance(retained_history_snapshot, Mapping)
        else {}
    )
    history_status = snapshot.get("status")
    history_rows = snapshot.get("rows")
    history_observed = bool(
        history_status in {"observed", "observed_empty"}
        and isinstance(history_rows, (list, tuple))
        and all(isinstance(row, Mapping) for row in history_rows)
    )
    missing = (
        list(latest.get("missing_asset_ids") or ())
        if isinstance(latest, Mapping)
        else []
    )
    status = "unavailable"
    reason = "no_complete_generation"
    diagnostics: list[dict[str, Any]] = []
    if latest is not None and not missing:
        status = "not_required"
        reason = "latest_generation_has_all_inputs"
    elif latest is not None and not history_observed:
        reason = "retained_history_unavailable"
    elif latest is not None:
        endpoints = {
            _identity(row.get("canonical_asset_id")): row
            for row in latest_source_rows
            if isinstance(row, Mapping)
            and _identity(row.get("canonical_asset_id")) in set(missing)
        }
        if set(endpoints) != set(missing):
            reason = "missing_generation_endpoint_row"
        else:
            for asset_id in missing:
                diagnostic = (
                    event_market_history.return_anchor_selection_diagnostic(
                        endpoints[asset_id],
                        list(history_rows),
                        hours=24,
                    )
                )
                diagnostics.append(diagnostic)
            inconsistent = any(
                row.get("status") == "ready" for row in diagnostics
            )
            status = "inconsistent" if inconsistent else "observed"
            reason = (
                "source_missing_but_anchor_replay_ready"
                if inconsistent
                else "anchor_windows_replayed"
            )
    value = {
        "status": status,
        "reason": reason,
        "generation_observed_at": (
            latest.get("observed_at") if isinstance(latest, Mapping) else None
        ),
        "horizon_hours": 24,
        "retained_history_status": (
            history_status if isinstance(history_status, str) else "unavailable"
        ),
        "retained_history_artifact": snapshot.get("artifact"),
        "retained_history_sha256": snapshot.get("sha256"),
        "retained_history_size_bytes": snapshot.get("size_bytes"),
        "retained_history_row_count": _nonnegative_int(
            snapshot.get("row_count")
        ),
        "retained_history_binding_source": snapshot.get("binding_source"),
        "missing_input_count": len(missing),
        "diagnostics": diagnostics,
        "all_missing_inputs_explained": len(diagnostics) == len(missing),
        "source_scope": (
            "latest_generation_endpoints_plus_exact_current_retained_history"
        ),
        "future_endpoint_eligibility_inferred": False,
        "retained_history_mutated": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }
    return value


def _validate_anchor_audit(
    value: object,
    *,
    latest: object,
    errors: list[str],
) -> None:
    if not isinstance(value, Mapping) or set(value) != _ANCHOR_AUDIT_KEYS:
        errors.append("anchor_audit_keys_invalid")
        return
    status = value.get("status")
    diagnostics = value.get("diagnostics")
    missing_count = value.get("missing_input_count")
    latest_mapping = latest if isinstance(latest, Mapping) else None
    if status not in _ANCHOR_AUDIT_STATUSES:
        errors.append("anchor_audit_status_invalid")
    if value.get("reason") not in {
        "no_complete_generation",
        "latest_generation_has_all_inputs",
        "retained_history_unavailable",
        "missing_generation_endpoint_row",
        "anchor_windows_replayed",
        "source_missing_but_anchor_replay_ready",
    }:
        errors.append("anchor_audit_reason_invalid")
    if value.get("horizon_hours") != 24:
        errors.append("anchor_audit_horizon_invalid")
    if type(missing_count) is not int or missing_count < 0:
        errors.append("anchor_audit_missing_count_invalid")
        missing_count = 0
    expected_missing = (
        latest_mapping.get("missing_input_count") if latest_mapping else 0
    )
    if missing_count != expected_missing:
        errors.append("anchor_audit_missing_count_mismatch")
    if latest_mapping is None:
        if value.get("generation_observed_at") is not None:
            errors.append("anchor_audit_generation_time_invalid")
    elif value.get("generation_observed_at") != latest_mapping.get("observed_at"):
        errors.append("anchor_audit_generation_time_mismatch")
    if not isinstance(diagnostics, list) or len(diagnostics) > 256:
        errors.append("anchor_audit_diagnostics_invalid")
        diagnostics = []
    elif not all(
        event_market_history.return_anchor_selection_diagnostic_valid(row)
        for row in diagnostics
    ):
        errors.append("anchor_audit_diagnostic_invalid")
    diagnostic_assets = [
        row.get("canonical_asset_id")
        for row in diagnostics
        if isinstance(row, Mapping)
    ]
    expected_assets = (
        latest_mapping.get("missing_asset_ids") if latest_mapping else []
    )
    if diagnostics and diagnostic_assets != expected_assets:
        errors.append("anchor_audit_assets_mismatch")
    explained = len(diagnostics) == missing_count
    if value.get("all_missing_inputs_explained") is not explained:
        errors.append("anchor_audit_explained_flag_invalid")
    if status in {"observed", "inconsistent"} and not explained:
        errors.append("anchor_audit_observed_incomplete")
    if status == "observed" and any(
        row.get("status") != "unavailable"
        for row in diagnostics
        if isinstance(row, Mapping)
    ):
        errors.append("anchor_audit_observed_status_mismatch")
    if status == "inconsistent" and not any(
        row.get("status") == "ready"
        for row in diagnostics
        if isinstance(row, Mapping)
    ):
        errors.append("anchor_audit_inconsistent_status_mismatch")
    history_status = value.get("retained_history_status")
    history_sha = value.get("retained_history_sha256")
    history_size = value.get("retained_history_size_bytes")
    history_rows = value.get("retained_history_row_count")
    if history_status not in {
        "observed",
        "observed_empty",
        "missing",
        "unavailable",
    }:
        errors.append("anchor_audit_history_status_invalid")
    if type(history_rows) is not int or history_rows < 0:
        errors.append("anchor_audit_history_row_count_invalid")
    if history_status in {"observed", "observed_empty"}:
        if (
            value.get("retained_history_artifact") != "event_market_history.jsonl"
            or value.get("retained_history_binding_source")
            != "campaign_market_history_exact_bytes"
            or not _sha256(history_sha)
            or type(history_size) is not int
            or history_size < 0
            or (history_status == "observed_empty") != (history_rows == 0)
        ):
            errors.append("anchor_audit_history_binding_invalid")
    elif history_sha is not None or history_size is not None:
        errors.append("anchor_audit_unavailable_history_binding_invalid")
    fixed = {
        "source_scope": (
            "latest_generation_endpoints_plus_exact_current_retained_history"
        ),
        "future_endpoint_eligibility_inferred": False,
        "retained_history_mutated": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }
    for field, expected in fixed.items():
        if type(value.get(field)) is not type(expected) or value.get(field) != expected:
            errors.append(f"anchor_audit_{field}_invalid")
    expected_status, expected_reason = (
        ("unavailable", "no_complete_generation")
        if latest_mapping is None
        else ("not_required", "latest_generation_has_all_inputs")
        if missing_count == 0
        else ("unavailable", "retained_history_unavailable")
        if history_status not in {"observed", "observed_empty"}
        else ("unavailable", "missing_generation_endpoint_row")
        if not explained
        else ("inconsistent", "source_missing_but_anchor_replay_ready")
        if any(
            row.get("status") == "ready"
            for row in diagnostics
            if isinstance(row, Mapping)
        )
        else ("observed", "anchor_windows_replayed")
    )
    if status != expected_status or value.get("reason") != expected_reason:
        errors.append("anchor_audit_status_derivation_mismatch")


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
    membership_context = value.get("missing_input_membership_context")
    if not isinstance(membership_context, list) or len(membership_context) > 256:
        errors.append(f"{label}_membership_context_invalid")
        membership_context = []
    else:
        for index, context in enumerate(membership_context):
            _validate_membership_context(
                context,
                observed_at=value.get("observed_at"),
                label=f"{label}_membership_context_{index}",
                errors=errors,
            )
    context_ids = [
        item.get("canonical_asset_id")
        for item in membership_context
        if isinstance(item, Mapping)
    ]
    if isinstance(missing_asset_ids, list) and context_ids != missing_asset_ids:
        errors.append(f"{label}_membership_context_assets_mismatch")
    context_recent_ids = [
        item.get("canonical_asset_id")
        for item in membership_context
        if isinstance(item, Mapping)
        and item.get("within_recent_membership_window") is True
    ]
    if isinstance(recent_asset_ids, list) and context_recent_ids != recent_asset_ids:
        errors.append(f"{label}_membership_context_recent_mismatch")
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


def _validate_membership_context(
    value: object,
    *,
    observed_at: object,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, Mapping) or set(value) != _MEMBERSHIP_CONTEXT_KEYS:
        errors.append(f"{label}_keys_invalid")
        return
    if not _identity(value.get("canonical_asset_id")):
        errors.append(f"{label}_asset_id_invalid")
    start_known = value.get("membership_start_known")
    if type(start_known) is not bool:
        errors.append(f"{label}_start_known_invalid")
        return
    started_at = value.get("continuous_membership_started_at")
    age_seconds = value.get("continuous_membership_age_seconds")
    recent = value.get("within_recent_membership_window")
    if type(recent) is not bool:
        errors.append(f"{label}_recent_flag_invalid")
    if value.get("anchor_eligibility_inferred") is not False:
        errors.append(f"{label}_anchor_eligibility_invalid")
    if start_known:
        start = _parse_aware_utc(started_at)
        observed = _parse_aware_utc(observed_at)
        if value.get("membership_start_basis") != "observed_entry":
            errors.append(f"{label}_start_basis_invalid")
        if start is None or observed is None or start > observed:
            errors.append(f"{label}_started_at_invalid")
            return
        expected_age = int((observed - start).total_seconds())
        if type(age_seconds) is not int or age_seconds != expected_age:
            errors.append(f"{label}_age_invalid")
        expected_recent = expected_age < RECENT_MEMBERSHIP_WINDOW_SECONDS
        if type(recent) is bool and recent != expected_recent:
            errors.append(f"{label}_recent_flag_mismatch")
        return
    if value.get("membership_start_basis") != (
        "unknown_before_first_complete_generation"
    ):
        errors.append(f"{label}_start_basis_invalid")
    if started_at is not None or age_seconds is not None:
        errors.append(f"{label}_unknown_start_values_invalid")
    if recent is not False:
        errors.append(f"{label}_unknown_start_recent_invalid")


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
    "CADENCE_GAP_AUDIT_SCHEMA_ID",
    "CADENCE_GAP_AUDIT_SCHEMA_VERSION",
    "CADENCE_GAP_EXAMPLE_LIMIT",
    "CADENCE_GAP_INTERPRETATION",
    "INTERPRETATION",
    "LEGACY_SCHEMA_VERSION",
    "MEMBERSHIP_CLOCK_SCOPE",
    "RECENT_CYCLE_LIMIT",
    "RECENT_MEMBERSHIP_WINDOW_SECONDS",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_control_regime_generation_audit",
    "build_observation_cadence_gap_audit",
    "validate_control_regime_generation_audit",
    "validate_observation_cadence_gap_audit",
)
