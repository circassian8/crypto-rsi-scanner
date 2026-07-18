"""Bounded campaign-wide operator actions for the read-only dashboard.

The canonical campaign report is historical context, never current-generation
authority.  This loader admits only a small, pointer-matched, zero-side-effect
projection so the dashboard can expose genuine human work without rescanning
the cumulative artifact tree or inspecting process environment variables.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import hashlib
import math
from pathlib import Path
import re
from typing import Any

from ..artifacts.json_lines import loads_no_duplicate_keys
from .secure_reader import _DashboardNamespaceReadError, open_anchored_namespace


MAX_CAMPAIGN_REPORT_BYTES = 8 * 1024 * 1024
MAX_REVIEW_RECORDS = 64
MAX_OUTCOME_GAPS = 20
CAMPAIGN_REPORT_JSON_FILENAME = "RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.json"

_REPORT_SCHEMA = "decision_radar_live_observation_campaign_report_v2"
_REPORT_ROW_TYPE = "decision_radar_live_observation_campaign_report"
_QUEUE_SCHEMA = "decision_radar.idea_review_timing_queue_summary"
_QUEUE_COMMAND = "make radar-review-timing-queue PYTHON=.venv/bin/python"
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+|\-]{0,199}$")
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,31}$")
_OUTCOME_READINESS_COMMAND = (
    "make radar-outcome-price-recovery-readiness PYTHON=.venv/bin/python"
)
_BYBIT_READINESS_COMMAND = (
    "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python"
)
_BASELINE_FEATURE_GROUPS = (
    "btc_eth_relative",
    "returns_1h",
    "returns_24h",
    "returns_4h",
    "turnover",
    "volatility",
    "volume",
)
_ZERO_REPORT_SAFETY = (
    "normal_rsi_signal_rows_written",
    "paper_trades_created",
    "provider_calls_made_by_report",
    "telegram_sends",
    "trades_created",
    "triggered_fade_created",
)
_ZERO_QUEUE_SAFETY = (
    "authorization_mutations",
    "dashboard_authority_mutations",
    "event_alpha_paper_trades",
    "event_alpha_triggered_fade",
    "normal_rsi_writes",
    "orders",
    "production_policy_mutations",
    "provider_calls",
    "telegram_sends",
    "trades",
)


def load_campaign_operator_actions(
    research_root: str | Path | None,
    *,
    artifact_namespace: str,
    run_id: str,
    revision: int,
) -> dict[str, Any]:
    """Load one safe campaign-action projection without calls or writes."""

    if research_root is None:
        return _unavailable("campaign_report_root_not_configured")
    root = Path(research_root).expanduser()
    try:
        with open_anchored_namespace(root) as reader:
            data, read_error = reader.read_bytes(
                CAMPAIGN_REPORT_JSON_FILENAME,
                max_bytes=MAX_CAMPAIGN_REPORT_BYTES,
            )
    except _DashboardNamespaceReadError:
        return _unavailable("campaign_report_root_unavailable_or_unsafe")
    if read_error == "artifact_missing":
        return _unavailable("campaign_report_missing")
    if read_error == "artifact_too_large":
        return _unavailable("campaign_report_oversized")
    if read_error or data is None:
        return _unavailable("campaign_report_unsafe_or_unreadable")
    try:
        parsed = loads_no_duplicate_keys(data.decode("utf-8"))
        if not isinstance(parsed, Mapping):
            raise ValueError("campaign_report_not_object")
        projection = _project_campaign_actions(
            parsed,
            artifact_namespace=artifact_namespace,
            run_id=run_id,
            revision=revision,
        )
    except (KeyError, TypeError, UnicodeError, ValueError):
        return _unavailable("campaign_report_contract_invalid")
    return {
        **projection,
        "status": "ready",
        "authority": "pointer_matched_campaign_context",
        "report_sha256": hashlib.sha256(data).hexdigest(),
        "report_size_bytes": len(data),
        "maximum_report_size_bytes": MAX_CAMPAIGN_REPORT_BYTES,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }


def _project_campaign_actions(
    report: Mapping[str, Any],
    *,
    artifact_namespace: str,
    run_id: str,
    revision: int,
) -> dict[str, Any]:
    if (
        report.get("schema_id") != _REPORT_SCHEMA
        or report.get("schema_version") != _REPORT_SCHEMA
        or report.get("row_type") != _REPORT_ROW_TYPE
        or report.get("contract_version") != 2
        or report.get("measurement_program")
        != "decision_radar_live_observation_campaign_v2"
    ):
        raise ValueError("campaign_report_identity_invalid")
    _require_report_safety(report.get("safety"))
    generated_at = _timestamp(report.get("generated_at"), "generated_at")
    pointer = _mapping(report.get("pointer"), "pointer")
    if (
        pointer.get("artifact_namespace") != artifact_namespace
        or pointer.get("run_id") != run_id
        or _count(pointer.get("revision"), "pointer_revision") != revision
        or pointer.get("status") != "authoritative"
        or pointer.get("generation_authority_status") != "authoritative"
        or pointer.get("readiness_validation") != "passed"
        or pointer.get("exact_operator_binding") is not True
        or pointer.get("readiness_error") is not None
    ):
        raise ValueError("campaign_report_pointer_mismatch")
    pointer_checked_at = _timestamp(
        pointer.get("authority_checked_at"), "authority_checked_at"
    )
    if generated_at != pointer_checked_at:
        raise ValueError("campaign_report_terminal_clock_mismatch")

    metrics = _project_metrics(report.get("campaign_metrics"))
    review = _project_review_queue(report.get("human_review_queue"))
    outcomes = _project_outcome_gaps(report.get("outcomes"))
    execution = _project_execution_quality(
        report.get("data_quality_limitations"),
        retained_observations=metrics["retained_observation_count"],
        spread_available=metrics["spread_available_count"],
    )
    temporal_baseline = _project_temporal_baseline(
        report.get("baseline_maturity")
    )
    if metrics["review_timing_action_required"] != review["action_required_count"]:
        raise ValueError("campaign_report_review_count_mismatch")
    if metrics["matured_outcomes"] != outcomes["matured_count"]:
        raise ValueError("campaign_report_matured_outcome_count_mismatch")
    if metrics["pending_outcomes"] != outcomes["pending_count"]:
        raise ValueError("campaign_report_pending_outcome_count_mismatch")
    return {
        "report_generated_at": generated_at,
        "campaign_status": _identity(report.get("campaign_status"), "campaign_status"),
        "campaign_metrics": metrics,
        "human_review": review,
        "outcome_recovery": outcomes,
        "execution_quality": execution,
        "temporal_baseline": temporal_baseline,
        "pointer": {
            "artifact_namespace": artifact_namespace,
            "run_id": run_id,
            "revision": revision,
        },
    }


def _project_metrics(value: Any) -> dict[str, int]:
    metrics = _mapping(value, "campaign_metrics")
    projected = {
        name: _count(metrics.get(name), name)
        for name in (
            "real_cycles",
            "real_observations",
            "retained_observation_count",
            "baseline_counted_observation_count",
            "baseline_warm_asset_count",
            "historical_ideas",
            "matured_outcomes",
            "pending_outcomes",
            "review_timing_action_required",
            "spread_available_count",
        )
    }
    if projected["baseline_counted_observation_count"] > projected["retained_observation_count"]:
        raise ValueError("campaign_report_baseline_count_invalid")
    if projected["spread_available_count"] > projected["retained_observation_count"]:
        raise ValueError("campaign_report_spread_count_invalid")
    return projected


def _project_temporal_baseline(value: Any) -> dict[str, Any]:
    maturity = _mapping(value, "baseline_maturity")
    current = _mapping(
        maturity.get("current_universe_maturity"),
        "current_universe_maturity",
    )
    status = _text(current.get("status"), 32)
    if status not in {"cold", "warming", "warm", "incomplete"}:
        raise ValueError("campaign_baseline_status_invalid")
    expected = _count(current.get("expected_asset_count"), "expected_asset_count")
    observed = _count(current.get("observed_asset_count"), "observed_asset_count")
    missing = _count(current.get("missing_asset_count"), "missing_asset_count")
    fully_warm = _count(
        current.get("baseline_warm_asset_count"),
        "baseline_warm_asset_count",
    )
    if observed + missing != expected or fully_warm > observed:
        raise ValueError("campaign_baseline_universe_count_mismatch")
    source_groups = _mapping(
        current.get("baseline_feature_readiness"),
        "baseline_feature_readiness",
    )
    if set(source_groups) != set(_BASELINE_FEATURE_GROUPS):
        raise ValueError("campaign_baseline_feature_groups_invalid")
    groups: dict[str, dict[str, int]] = {}
    for name in _BASELINE_FEATURE_GROUPS:
        details = _mapping(source_groups.get(name), f"baseline_feature_{name}")
        counts = {
            field: _count(details.get(field), f"{name}_{field}")
            for field in (
                "warm_asset_count",
                "warming_asset_count",
                "cold_asset_count",
                "other_asset_count",
                "asset_count",
            )
        }
        progress = {
            field: _count(details.get(field), f"{name}_{field}")
            for field in (
                "minimum_sample_count",
                "maximum_sample_count",
                "required_sample_count",
                "sample_count_deficit_asset_count",
                "minimum_coverage_seconds",
                "maximum_coverage_seconds",
                "required_coverage_seconds",
                "coverage_deficit_asset_count",
            )
        }
        if (
            counts["asset_count"] != observed
            or sum(counts[field] for field in counts if field != "asset_count")
            != counts["asset_count"]
        ):
            raise ValueError("campaign_baseline_feature_count_mismatch")
        _validate_feature_progress(progress, asset_count=counts["asset_count"])
        groups[name] = counts | progress
    return {
        "status": status,
        "expected_asset_count": expected,
        "observed_asset_count": observed,
        "missing_asset_count": missing,
        "fully_warm_asset_count": fully_warm,
        "feature_groups": groups,
    }


def _validate_feature_progress(
    progress: Mapping[str, int],
    *,
    asset_count: int,
) -> None:
    minimum_sample = progress["minimum_sample_count"]
    maximum_sample = progress["maximum_sample_count"]
    required_sample = progress["required_sample_count"]
    sample_deficit = progress["sample_count_deficit_asset_count"]
    minimum_coverage = progress["minimum_coverage_seconds"]
    maximum_coverage = progress["maximum_coverage_seconds"]
    required_coverage = progress["required_coverage_seconds"]
    coverage_deficit = progress["coverage_deficit_asset_count"]
    if (
        minimum_sample > maximum_sample
        or required_sample <= 0
        or sample_deficit > asset_count
        or minimum_coverage > maximum_coverage
        or required_coverage <= 0
        or coverage_deficit > asset_count
    ):
        raise ValueError("campaign_baseline_feature_progress_invalid")
    if (
        (minimum_sample >= required_sample and sample_deficit != 0)
        or (maximum_sample < required_sample and sample_deficit != asset_count)
        or (
            minimum_sample < required_sample <= maximum_sample
            and not 0 < sample_deficit < asset_count
        )
        or (minimum_coverage >= required_coverage and coverage_deficit != 0)
        or (maximum_coverage < required_coverage and coverage_deficit != asset_count)
        or (
            minimum_coverage < required_coverage <= maximum_coverage
            and not 0 < coverage_deficit < asset_count
        )
    ):
        raise ValueError("campaign_baseline_feature_deficit_count_mismatch")


def _project_review_queue(value: Any) -> dict[str, Any]:
    queue = _mapping(value, "human_review_queue")
    if (
        queue.get("schema_id") != _QUEUE_SCHEMA
        or queue.get("schema_version") != 1
        or queue.get("row_type")
        != "decision_radar_idea_review_timing_queue_summary"
        or queue.get("research_only") is not True
        or queue.get("provider_calls") != 0
        or queue.get("writes") != 0
        or queue.get("automatic_policy_effect") != "none"
        or queue.get("dashboard_reads_recorded_as_human_actions") is not False
        or queue.get("commands_require_explicit_confirmation") is not True
        or queue.get("absolute_paths_or_action_commands_embedded") is not False
        or queue.get("operator_queue_command") != _QUEUE_COMMAND
    ):
        raise ValueError("campaign_review_queue_contract_invalid")
    _require_zero_mapping(queue.get("safety"), _ZERO_QUEUE_SAFETY, "queue_safety")
    records = queue.get("records")
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(records, Sequence):
        raise ValueError("campaign_review_records_invalid")
    if len(records) > MAX_REVIEW_RECORDS:
        raise ValueError("campaign_review_records_oversized")
    projected_records = tuple(_project_review_record(row) for row in records)
    counts = {
        name: _count(queue.get(name), name)
        for name in (
            "eligible_idea_count",
            "action_required_count",
            "not_viewed_count",
            "in_review_count",
            "complete_count",
            "skipped_candidate_count",
        )
    }
    if counts["eligible_idea_count"] != len(projected_records):
        raise ValueError("campaign_review_record_count_mismatch")
    if counts["action_required_count"] != counts["not_viewed_count"] + counts["in_review_count"]:
        raise ValueError("campaign_review_action_count_mismatch")
    if counts["eligible_idea_count"] != counts["action_required_count"] + counts["complete_count"]:
        raise ValueError("campaign_review_status_count_mismatch")
    if queue.get("status") not in {"no_eligible_ideas", "action_required", "complete"}:
        raise ValueError("campaign_review_status_invalid")
    return {
        **counts,
        "status": str(queue.get("status")),
        "records": projected_records,
        "next_safe_command": _QUEUE_COMMAND,
        "command_effect": "read_only_queue_preview",
        "dashboard_reads_count_as_review": False,
        "requires_explicit_confirmation_to_record_review": True,
    }


def _project_review_record(value: Any) -> dict[str, Any]:
    row = _mapping(value, "review_record")
    status = _text(row.get("review_status"), 32)
    if status not in {"not_viewed", "in_review", "complete"}:
        raise ValueError("campaign_review_record_status_invalid")
    return {
        "artifact_namespace": _identity(
            row.get("artifact_namespace"), "artifact_namespace"
        ),
        "idea_id": _identity(row.get("idea_id"), "idea_id"),
        "radar_route": _identity(row.get("radar_route"), "radar_route"),
        "review_status": status,
        "idea_available_at": _timestamp(
            row.get("idea_available_at"), "idea_available_at"
        ),
    }


def _project_outcome_gaps(value: Any) -> dict[str, Any]:
    outcomes = _mapping(value, "outcomes")
    due = _count(outcomes.get("due_missing_price"), "due_missing_price")
    details = outcomes.get("due_missing_price_details")
    if isinstance(details, (str, bytes, bytearray)) or not isinstance(details, Sequence):
        raise ValueError("campaign_outcome_gap_details_invalid")
    if len(details) > MAX_OUTCOME_GAPS or len(details) != due:
        raise ValueError("campaign_outcome_gap_count_mismatch")
    symbols: list[str] = []
    for value_row in details:
        row = _mapping(value_row, "outcome_gap")
        if (
            row.get("historical_point_in_time_evidence_required") is not True
            or row.get("interpolation_permitted") is not False
            or row.get("research_only") is not True
            or row.get("automatic_threshold_change_permitted") is not False
        ):
            raise ValueError("campaign_outcome_gap_contract_invalid")
        symbol = _text(row.get("symbol"), 32)
        if symbol and _SYMBOL_RE.fullmatch(symbol) is None:
            raise ValueError("campaign_outcome_gap_symbol_invalid")
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return {
        "due_missing_price_count": due,
        "matured_count": _count(outcomes.get("matured"), "matured"),
        "pending_count": _count(outcomes.get("pending"), "pending"),
        "symbols": tuple(symbols),
        "next_safe_command": _OUTCOME_READINESS_COMMAND,
        "command_effect": "read_only_recovery_readiness",
        "interpolation_permitted": False,
    }


def _project_execution_quality(
    value: Any,
    *,
    retained_observations: int,
    spread_available: int,
) -> dict[str, Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError("campaign_limitations_invalid")
    rows = [
        _mapping(row, "data_quality_limitation")
        for row in value[:32]
        if isinstance(row, Mapping)
        and row.get("category") == "execution_quality_spread"
    ]
    if spread_available == retained_observations and not rows:
        return {
            "status": "observed_complete",
            "venue": "bybit",
            "instrument": "usdt_linear_perpetual",
            "spread_available_count": spread_available,
            "retained_observation_count": retained_observations,
            "next_safe_command": None,
            "command_effect": "none",
            "authorization_created": False,
        }
    if len(rows) != 1:
        raise ValueError("campaign_execution_quality_limitation_missing")
    row = rows[0]
    if (
        row.get("provider_selection")
        != "selected_bybit_usdt_linear_perpetuals"
        or row.get("next_safe_command") != _BYBIT_READINESS_COMMAND
        or row.get("evidence_status")
        != "awaiting_authorized_immutable_capture"
    ):
        raise ValueError("campaign_execution_quality_contract_invalid")
    return {
        "status": "awaiting_authorized_immutable_capture",
        "venue": "bybit",
        "instrument": "usdt_linear_perpetual",
        "spread_available_count": spread_available,
        "retained_observation_count": retained_observations,
        "next_safe_command": _BYBIT_READINESS_COMMAND,
        "command_effect": "static_no_network_readiness",
        "authorization_created": False,
    }


def _require_report_safety(value: Any) -> None:
    safety = _mapping(value, "report_safety")
    if (
        safety.get("research_only") is not True
        or safety.get("no_trade_recommendation") is not True
        or safety.get("provider_authorization_modified") is not False
        or safety.get("automatic_route_changes") is not False
        or safety.get("automatic_threshold_changes") is not False
    ):
        raise ValueError("campaign_report_safety_invalid")
    _require_zero_mapping(safety, _ZERO_REPORT_SAFETY, "report_safety")


def _require_zero_mapping(value: Any, fields: Sequence[str], label: str) -> None:
    row = _mapping(value, label)
    if any(row.get(field) != 0 for field in fields):
        raise ValueError(f"{label}_side_effect_invalid")


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "authority": "campaign_context_unavailable",
        "reason": reason,
        "campaign_metrics": {},
        "human_review": {},
        "outcome_recovery": {},
        "execution_quality": {},
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label}_invalid")
    return value


def _count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}_invalid")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0 or not numeric.is_integer():
        raise ValueError(f"{label}_invalid")
    return int(numeric)


def _text(value: Any, maximum: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > maximum or any(ord(character) < 32 for character in text):
        raise ValueError("campaign_report_text_invalid")
    return text


def _identity(value: Any, label: str) -> str:
    text = _text(value, 200)
    if _IDENTITY_RE.fullmatch(text) is None:
        raise ValueError(f"{label}_invalid")
    return text


def _timestamp(value: Any, label: str) -> str:
    text = _text(value, 64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label}_invalid")
    return parsed.isoformat()


__all__ = (
    "MAX_CAMPAIGN_REPORT_BYTES",
    "load_campaign_operator_actions",
)
