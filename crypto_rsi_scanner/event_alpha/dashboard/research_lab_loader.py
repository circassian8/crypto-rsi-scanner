"""Bounded, read-only loading for the Decision Radar Research Lab.

Research evidence is deliberately independent of the authoritative dashboard
generation.  The exact seven-file empirical report contract is read once
through one descriptor-anchored directory.  No semantic projection is exposed
until the complete byte bundle validates, so a missing, spliced, oversized, or
unsafe report can never be presented as zero evidence.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Mapping

from ..artifacts.json_lines import loads_no_duplicate_keys
from ..operations import empirical_hardening_supplement, empirical_research_reports
from .research_lab_hardening_projection import (
    ORIGINS,
    ROUTES,
    project_hardening_operator_summary,
)
from .secure_reader import _DashboardNamespaceReadError, open_anchored_namespace


REPORT_FILENAMES = empirical_research_reports.REPORT_FILENAMES
VALIDATION_REPORT = REPORT_FILENAMES[1]
WALK_FORWARD_REPORT = REPORT_FILENAMES[3]
POLICY_REPORT = REPORT_FILENAMES[5]
SUPPLEMENT_FILENAME = empirical_hardening_supplement.SUPPLEMENT_FILENAME
MAX_SUPPLEMENT_BYTES = empirical_hardening_supplement.MAX_SUPPLEMENT_BYTES

_REPORT_FILES = {
    filename: empirical_research_reports.MAX_REPORT_BYTES
    for filename in REPORT_FILENAMES
}
_VALIDATION_SCHEMA = "decision_radar.empirical_validation_report"
_ANALYSIS_SCHEMA = "decision_radar.empirical_replay_analysis"
_PARTITION_ANALYSES_SCHEMA = "decision_radar.empirical_partition_analyses"
_WALK_REPORT_SCHEMA = "decision_radar.empirical_walk_forward_report"
_WALK_SCHEMA = "decision_radar.empirical_walk_forward"
_POLICY_BUNDLE_REPORT_SCHEMA = "decision_radar.empirical_policy_simulation_report"
_POLICY_SIMULATION_SCHEMA = "decision_radar.empirical_policy_simulation"
_ZERO_SIDE_EFFECT_FIELDS = (
    "authorization_mutations",
    "dashboard_authority_mutations",
    "event_alpha_paper_trades",
    "event_alpha_triggered_fade",
    "normal_rsi_writes",
    "normal_rsi_signal_rows_written",
    "orders",
    "paper_trades_created",
    "production_policy_mutations",
    "provider_calls",
    "provider_calls_made_by_report",
    "telegram_sends",
    "trades",
    "trades_created",
    "triggered_fade_created",
    "writes",
)


def load_research_lab_snapshot(research_root: str | Path | None) -> dict[str, Any]:
    """Return one closed Research Lab read model; never raise for bad evidence."""

    if research_root is None:
        return _unavailable_snapshot("research_root_not_configured")
    root = Path(research_root).expanduser()
    records: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    supplement_record = _supplement_record(status="not_configured")
    supplement_payload: bytes | None = None
    try:
        with open_anchored_namespace(root) as reader:
            for filename in REPORT_FILENAMES:
                record, data = _read_report_file(
                    reader,
                    filename,
                    _REPORT_FILES[filename],
                )
                records[filename] = record
                if data is not None:
                    payloads[filename] = data
            supplement_record, supplement_payload = _read_supplement_file(reader)
    except _DashboardNamespaceReadError:
        return _unavailable_snapshot(
            "research_root_unavailable_or_unsafe",
            report_status="unavailable",
        )

    ready_count = sum(record.get("status") == "ready" for record in records.values())
    if ready_count != len(REPORT_FILENAMES):
        warnings = tuple(
            f"{record['filename']}:{record['status']}"
            for record in records.values()
            if record.get("status") != "ready"
        )
        return _snapshot(
            status="partial" if ready_count else "unavailable",
            bundle_status="incomplete",
            reports=records,
            warnings=warnings or ("research_report_bundle_incomplete",),
            hardening_supplement=_supplement_without_valid_reports(
                supplement_record
            ),
        )

    try:
        envelope = empirical_research_reports.validate_report_bundle(payloads)
        parsed = {
            filename: _parse_validated_json(payloads[filename], filename=filename)
            for filename in (VALIDATION_REPORT, WALK_FORWARD_REPORT, POLICY_REPORT)
        }
        projections = {
            "validation": _project_validation(parsed[VALIDATION_REPORT]),
            "walk_forward": _project_walk_forward(parsed[WALK_FORWARD_REPORT]),
            "policy": _project_policy(parsed[POLICY_REPORT]),
            "live": _project_live_binding(envelope.get("live_campaign_report")),
        }
        bundle = _project_bundle(envelope)
    except (KeyError, RuntimeError, TypeError, UnicodeError, ValueError):
        return _snapshot(
            status="unavailable",
            bundle_status="invalid",
            reports=records,
            warnings=("research_report_bundle_invalid",),
            hardening_supplement=_supplement_without_valid_reports(
                supplement_record
            ),
        )
    hardening_supplement = _load_hardening_supplement(
        supplement_record,
        supplement_payload,
        report_payloads=payloads,
        validation_projection=projections["validation"],
    )
    return _snapshot(
        status="ready",
        bundle_status="validated",
        reports=records,
        bundle=bundle,
        projections=projections,
        warnings=(),
        hardening_supplement=hardening_supplement,
    )


def _unavailable_snapshot(
    reason: str,
    *,
    report_status: str = "not_configured",
) -> dict[str, Any]:
    return _snapshot(
        status="unavailable",
        bundle_status="not_configured" if report_status == "not_configured" else "unavailable",
        reports={
            filename: _report_record(filename, status=report_status)
            for filename in REPORT_FILENAMES
        },
        warnings=(reason,),
    )


def _snapshot(
    *,
    status: str,
    bundle_status: str,
    reports: Mapping[str, Mapping[str, Any]],
    warnings: tuple[str, ...],
    bundle: Mapping[str, Any] | None = None,
    projections: Mapping[str, Any] | None = None,
    hardening_supplement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "bundle_status": bundle_status,
        "reports": {filename: dict(reports[filename]) for filename in REPORT_FILENAMES},
        "bundle": dict(bundle or {}),
        "projections": dict(projections or {}),
        "hardening_supplement": dict(
            hardening_supplement
            or _supplement_state(
                _supplement_record(status="not_configured"),
                warnings=("hardening_supplement_not_configured",),
            )
        ),
        "warnings": warnings,
        "research_only": True,
        "auto_apply": False,
        "production_policy_mutations": 0,
        "dashboard_authority_mutations": 0,
        "provider_calls": 0,
        "writes": 0,
    }


def _read_report_file(
    reader: Any,
    filename: str,
    maximum: int,
) -> tuple[dict[str, Any], bytes | None]:
    data, read_error = reader.read_bytes(filename, max_bytes=maximum)
    if read_error == "artifact_missing":
        return _report_record(filename, status="missing"), None
    if read_error == "artifact_too_large":
        return _report_record(filename, status="oversized"), None
    if read_error or data is None:
        return _report_record(filename, status="unsafe_or_unreadable"), None
    if len(data) > maximum:
        return _report_record(filename, status="oversized"), None
    return _report_record(filename, status="ready", data=data), data


def _read_supplement_file(
    reader: Any,
) -> tuple[dict[str, Any], bytes | None]:
    data, read_error = reader.read_bytes(
        SUPPLEMENT_FILENAME,
        max_bytes=MAX_SUPPLEMENT_BYTES,
    )
    if read_error == "artifact_missing":
        return _supplement_record(status="missing"), None
    if read_error == "artifact_too_large":
        return _supplement_record(status="oversized"), None
    if read_error or data is None:
        return _supplement_record(status="unsafe_or_unreadable"), None
    if len(data) > MAX_SUPPLEMENT_BYTES:
        return _supplement_record(status="oversized"), None
    return _supplement_record(status="read", data=data), data


def _supplement_record(
    *,
    status: str,
    data: bytes | None = None,
) -> dict[str, Any]:
    return {
        "filename": SUPPLEMENT_FILENAME,
        "status": status,
        "sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
        "size_bytes": len(data) if data is not None else None,
        "maximum_size_bytes": MAX_SUPPLEMENT_BYTES,
    }


def _supplement_state(
    record: Mapping[str, Any],
    *,
    status: str | None = None,
    projection: Mapping[str, Any] | None = None,
    warnings: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "status": status or str(record.get("status") or "unavailable"),
        "record": dict(record),
        "projection": dict(projection or {}),
        "warnings": warnings,
    }


def _supplement_without_valid_reports(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    observed = str(record.get("status") or "unavailable")
    if observed == "read":
        return _supplement_state(
            record,
            status="suppressed",
            warnings=("hardening_supplement_exact_reports_unavailable",),
        )
    return _supplement_state(
        record,
        warnings=(f"hardening_supplement_{observed}",),
    )


def _load_hardening_supplement(
    record: Mapping[str, Any],
    payload: bytes | None,
    *,
    report_payloads: Mapping[str, bytes],
    validation_projection: Mapping[str, Any],
) -> dict[str, Any]:
    observed = str(record.get("status") or "unavailable")
    if observed != "read" or payload is None:
        return _supplement_state(
            record,
            warnings=(f"hardening_supplement_{observed}",),
        )
    try:
        validated = (
            empirical_hardening_supplement.parse_and_validate_hardening_supplement(
                payload,
                report_payloads=report_payloads,
            )
        )
        projection = project_hardening_operator_summary(
            validated,
            validation_projection=validation_projection,
        )
    except (KeyError, RuntimeError, TypeError, UnicodeError, ValueError):
        invalid_record = {**dict(record), "status": "invalid"}
        return _supplement_state(
            invalid_record,
            status="invalid",
            warnings=("hardening_supplement_invalid",),
        )
    ready_record = {**dict(record), "status": "ready"}
    return _supplement_state(
        ready_record,
        status="ready",
        projection=projection,
    )


def _report_record(
    filename: str,
    *,
    status: str,
    data: bytes | None = None,
) -> dict[str, Any]:
    return {
        "filename": filename,
        "status": status,
        "sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
        "size_bytes": len(data) if data is not None else None,
        "maximum_size_bytes": _REPORT_FILES[filename],
    }


def _parse_validated_json(data: bytes, *, filename: str) -> dict[str, Any]:
    parsed = loads_no_duplicate_keys(data.decode("utf-8"))
    if not isinstance(parsed, Mapping):
        raise ValueError(f"validated_report_not_object:{filename}")
    return dict(parsed)


def _project_bundle(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_id") != "decision_radar.empirical_research_report_bundle":
        raise ValueError("research_report_bundle_schema_invalid")
    report_artifacts = tuple(_strings(value.get("report_artifacts"), 8, 160))
    if report_artifacts != REPORT_FILENAMES:
        raise ValueError("research_report_bundle_inventory_invalid")
    return {
        "schema_id": _text(value.get("schema_id"), 128),
        "schema_version": _count(value.get("schema_version")),
        "bundle_id": _text(value.get("bundle_id"), 128),
        "protocol_version": _text(value.get("protocol_version"), 128),
        "protocol_sha256": _text(value.get("protocol_sha256"), 128),
        "report_artifacts": report_artifacts,
        "report_core_sha256": _bounded_value(value.get("report_core_sha256"), depth=3),
        "recommendation_seal_sha256": _text(value.get("recommendation_seal_sha256"), 128),
        "final_confirmation_sha256": _text(value.get("final_confirmation_sha256"), 128),
        "selection_run": _project_run_binding(value.get("selection_run")),
        "final_test_run": _project_run_binding(value.get("final_test_run")),
        "evidence_lanes": _bounded_value(value.get("evidence_lanes"), depth=4),
        "live_campaign_report": _project_live_binding_metadata(
            value.get("live_campaign_report")
        ),
        "production_contract": _bounded_value(value.get("production_contract"), depth=3),
        "safety": _bounded_value(value.get("safety"), depth=3),
    }


def _project_run_binding(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("research_report_run_binding_missing")
    return {
        "run_fingerprint": _text(value.get("run_fingerprint"), 128),
        "protocol_version": _text(value.get("protocol_version"), 128),
        "protocol_sha256": _text(value.get("protocol_sha256"), 128),
        "input_sha256": _text(value.get("input_sha256"), 128),
        "code_sha256": _text(value.get("code_sha256"), 128),
        "configuration_sha256": _text(value.get("configuration_sha256"), 128),
        "manifest_sha256": _text(value.get("manifest_sha256"), 128),
        "archive_counts": _bounded_value(value.get("archive_counts"), depth=2),
        "immutable": value.get("immutable") is True,
        "research_only": value.get("research_only") is True,
        "auto_apply": value.get("auto_apply") is True,
    }


def _project_validation(value: Mapping[str, Any]) -> dict[str, Any]:
    schema_id = str(value.get("schema_id") or "")
    if schema_id != _VALIDATION_SCHEMA:
        raise ValueError("validation_schema_invalid")
    _require_report_safety(value)
    selection_analyses = [
        _project_analysis(row)
        for row in _analysis_rows(
            value.get("selection_analysis"),
            expected_partitions=("development", "validation"),
        )
    ]
    final_test_analyses = [
        _project_analysis(row)
        for row in _analysis_rows(
            value.get("final_test_analysis"),
            expected_partitions=("final_test",),
        )
    ]
    analyses = selection_analyses + final_test_analyses
    if tuple(row.get("partition") for row in analyses) != (
        "development", "validation", "final_test"
    ):
        raise ValueError("empirical_analysis_partitions_invalid")
    return {
        "schema_id": schema_id,
        "schema_version": _count(value.get("schema_version")),
        "status": _text(value.get("report_status"), 96) or "ready",
        "analyses": analyses,
        "selection_analyses": selection_analyses,
        "final_test_analyses": final_test_analyses,
        "selection_execution": _bounded_value(value.get("selection_execution"), depth=5),
        "final_test_execution": _bounded_value(value.get("final_test_execution"), depth=5),
        "selection_controls": _project_controls(value.get("selection_controls")),
        "final_test_controls": _project_controls(value.get("final_test_controls")),
        "review_evidence": _project_review_evidence(value.get("review_evidence")),
        "conclusions": _bounded_value(value.get("conclusions"), depth=7),
        "final_confirmation": _bounded_value(value.get("final_confirmation"), depth=7),
        "safety": _bounded_value(value.get("safety"), depth=3),
        "research_only": True,
        "auto_apply": False,
        "policy_eligible": False,
    }


def _analysis_rows(
    value: Any,
    *,
    expected_partitions: tuple[str, ...],
) -> list[Mapping[str, Any]]:
    if not isinstance(value, Mapping) or value.get("schema_id") != _PARTITION_ANALYSES_SCHEMA:
        raise ValueError("partition_analyses_schema_invalid")
    partitions = value.get("partitions")
    if not isinstance(partitions, Mapping) or tuple(partitions) != expected_partitions:
        raise ValueError("partition_analyses_inventory_invalid")
    rows: list[Mapping[str, Any]] = []
    for partition in expected_partitions:
        row = partitions.get(partition)
        if not isinstance(row, Mapping) or row.get("schema_id") != _ANALYSIS_SCHEMA:
            raise ValueError("partition_analysis_missing")
        rows.append(row)
    return rows


def _project_analysis(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_id") != _ANALYSIS_SCHEMA:
        raise ValueError("analysis_schema_invalid")
    _require_research_safety(value)
    _require_zero_safety(value.get("safety"))
    return {
        "schema_id": _ANALYSIS_SCHEMA,
        "schema_version": _count(value.get("schema_version")),
        "partition": _text(value.get("partition"), 64),
        "evidence_mode": _text(value.get("evidence_mode"), 64),
        "causal_claim": value.get("causal_claim") is True,
        "return_unit": _text(value.get("return_unit"), 64),
        "episode_count": _count(value.get("episode_count")),
        "matured_episode_count": _count(value.get("matured_episode_count")),
        "directional_return_sample_size": _count(value.get("directional_return_sample_size")),
        "route_cohorts": _cohorts(value.get("route_cohorts"), expected=ROUTES),
        "primary_origin_cohorts": _cohorts(value.get("primary_origin_cohorts"), expected=ORIGINS),
        "score_monotonicity": _monotonicity(value.get("score_monotonicity")),
        "market_regime_cohorts": _cohorts(value.get("market_regime_cohorts")),
        "liquidity_tier_cohorts": _cohorts(value.get("liquidity_tier_cohorts")),
        "data_quality_cohorts": _cohorts(value.get("data_quality_cohorts")),
        "market_catalyst_cohorts": _cohorts(value.get("market_catalyst_cohorts")),
        "cost_sensitivity": _project_costs(value.get("cost_sensitivity")),
        "survivability": _bounded_value(value.get("survivability"), depth=8),
        "operator_burden": _bounded_value(value.get("operator_burden"), depth=7),
        "dimension_analysis": _bounded_value(value.get("dimension_analysis"), depth=6),
        "missed_opportunity_summary": _bounded_value(
            value.get("missed_opportunity_summary"), depth=4
        ),
        "false_positive_and_late_summary": _bounded_value(
            value.get("false_positive_and_late_summary"), depth=4
        ),
        "recommendation": _bounded_value(value.get("recommendation"), depth=5),
        "multiple_comparison_warning": _text(value.get("multiple_comparison_warning"), 1024),
        "analysis_digest": _text(value.get("analysis_digest"), 128),
        "research_only": True,
        "auto_apply": False,
        "policy_eligible": False,
    }


def _cohorts(value: Any, *, expected: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    rows = [row for row in value[:64] if isinstance(row, Mapping)] if isinstance(value, list) else []
    projected = [_project_cohort(row) for row in rows]
    if expected:
        by_name = {row["cohort"]: row for row in projected}
        if set(by_name) != set(expected) or len(projected) != len(expected):
            raise ValueError("closed_cohort_taxonomy_invalid")
        return [by_name[name] for name in expected]
    return projected


def _project_cohort(row: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "mean_directional_return_fraction",
        "median_directional_return_fraction",
        "trimmed_mean_10pct_directional_return_fraction",
        "hit_rate",
        "downside_5pct_fraction",
        "worst_directional_return_fraction",
        "mean_mfe_fraction",
        "mean_mae_fraction",
        "mfe_to_mae_ratio_of_means",
    )
    return {
        "cohort": _text(row.get("cohort"), 128) or "unknown",
        "cohort_type": _text(row.get("cohort_type"), 96),
        "partition": _text(row.get("partition"), 64),
        "evidence_mode": _text(row.get("evidence_mode"), 64),
        "episode_count": _count(row.get("episode_count")),
        "matured_episode_count": _count(row.get("matured_episode_count")),
        "sample_size": _count(row.get("sample_size")),
        "sample_status": _text(row.get("sample_status"), 64),
        "evidence_strength": _text(row.get("evidence_strength"), 64),
        "result_direction": _text(row.get("result_direction"), 64),
        **{field: _number(row.get(field)) for field in fields},
        "uncertainty": _bounded_value(row.get("uncertainty"), depth=2),
    }


def _monotonicity(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in value[:16]:
        if not isinstance(row, Mapping):
            continue
        rows.append({
            "score_field": _text(row.get("score_field"), 96),
            "partition": _text(row.get("partition"), 64),
            "evidence_mode": _text(row.get("evidence_mode"), 64),
            "expected_relationship": _text(row.get("expected_relationship"), 256),
            "comparable_pair_count": _count(row.get("comparable_pair_count")),
            "violation_count": _count(row.get("violation_count")),
            "evaluation_status": _text(row.get("evaluation_status"), 96),
            "not_evaluable_reason": _text(row.get("not_evaluable_reason"), 512),
            "buckets": _cohorts(row.get("buckets")),
        })
    return rows


def _project_costs(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    scenarios = []
    for row in list(value.get("scenarios") or [])[:16]:
        if not isinstance(row, Mapping):
            continue
        scenarios.append({
            "round_trip_cost_bps": _count(row.get("round_trip_cost_bps")),
            "sample_size": _count(row.get("sample_size")),
            "sample_status": _text(row.get("sample_status"), 64),
            "evidence_strength": _text(row.get("evidence_strength"), 64),
            "mean_net_directional_return_fraction": _number(row.get("mean_net_directional_return_fraction")),
            "median_net_directional_return_fraction": _number(row.get("median_net_directional_return_fraction")),
            "net_hit_rate": _number(row.get("net_hit_rate")),
            "mean_survives_assumed_cost": row.get("mean_survives_assumed_cost") if isinstance(row.get("mean_survives_assumed_cost"), bool) else None,
        })
    return {
        "gross_sample_size": _count(value.get("gross_sample_size")),
        "gross_mean_directional_return_fraction": _number(value.get("gross_mean_directional_return_fraction")),
        "break_even_mean_round_trip_cost_bps": _number(value.get("break_even_mean_round_trip_cost_bps")),
        "historical_spread_observed": value.get("historical_spread_observed") is True,
        "cost_basis": _text(value.get("cost_basis"), 256),
        "scenarios": scenarios,
    }


def _project_controls(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("empirical_controls_missing")
    _require_research_safety(value)
    _require_zero_safety(value.get("safety"))
    projected = _bounded_value(value, depth=8)
    if not isinstance(projected, Mapping):
        raise ValueError("empirical_controls_projection_invalid")
    return dict(projected)


def _project_review_evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or tuple(value) != ("final_test", "selection"):
        raise ValueError("review_evidence_inventory_invalid")
    projected: dict[str, Any] = {}
    for key in ("selection", "final_test"):
        row = value.get(key)
        if not isinstance(row, Mapping):
            raise ValueError("review_evidence_missing")
        _require_research_safety(row)
        _require_zero_safety(row.get("safety"))
        projected[key] = _bounded_value(row, depth=7)
    return projected


def _project_walk_forward(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_id") != _WALK_REPORT_SCHEMA:
        raise ValueError("walk_forward_report_schema_invalid")
    _require_report_safety(value)
    candidate = value.get("walk_forward")
    if not isinstance(candidate, Mapping) or candidate.get("schema_id") != _WALK_SCHEMA:
        raise ValueError("walk_forward_schema_invalid")
    _require_research_safety(candidate)
    folds = []
    for row in list(candidate.get("folds") or [])[:64]:
        if not isinstance(row, Mapping):
            continue
        result = row.get("test_result") if isinstance(row.get("test_result"), Mapping) else {}
        folds.append({
            "fold": _count(row.get("fold")),
            "train_start": _text(row.get("train_start"), 64),
            "train_end_exclusive": _text(row.get("train_end_exclusive"), 64),
            "test_start": _text(row.get("test_start"), 64),
            "test_end_exclusive": _text(row.get("test_end_exclusive"), 64),
            "train_episode_count": _count(row.get("train_episode_count")),
            "test_episode_count": _count(row.get("test_episode_count")),
            "train_selected_observation_day_count": _count(
                row.get("train_selected_observation_day_count")
            ),
            "train_idea_active_day_count": _count(row.get("train_idea_active_day_count")),
            "train_outcome_eligible_episode_count": _count(
                row.get("train_outcome_eligible_episode_count")
            ),
            "train_outcome_purged_count": _count(row.get("train_outcome_purged_count")),
            "test_selected_observation_day_count": _count(
                row.get("test_selected_observation_day_count")
            ),
            "test_idea_active_day_count": _count(row.get("test_idea_active_day_count")),
            "test_outcome_eligible_episode_count": _count(
                row.get("test_outcome_eligible_episode_count")
            ),
            "test_outcome_evaluable_episode_count": _count(
                row.get("test_outcome_evaluable_episode_count")
            ),
            "test_outcome_purged_count": _count(row.get("test_outcome_purged_count")),
            "selected_scenario": _text(row.get("selected_scenario"), 96),
            "selection_used_final_test": row.get("selection_used_final_test") is True,
            "test_result": _project_scenario(result),
        })
    return {
        "schema_id": _WALK_SCHEMA,
        "schema_version": _count(candidate.get("schema_version")),
        "status": _text(candidate.get("status"), 96),
        "selection_partitions": _strings(candidate.get("selection_partitions"), 8, 64),
        "final_test_accessed": candidate.get("final_test_accessed") is True,
        "fold_count": _count(candidate.get("fold_count")),
        "nonempty_fold_count": _count(candidate.get("nonempty_fold_count")),
        "minimum_fold_count": _count(candidate.get("minimum_fold_count")),
        "outcome_evaluable_fold_count": _count(candidate.get("outcome_evaluable_fold_count")),
        "selected_observation_day_count": _count(
            candidate.get("selected_observation_day_count")
        ),
        "idea_active_day_count": _count(candidate.get("idea_active_day_count")),
        "observed_day_denominator_basis": _text(
            candidate.get("observed_day_denominator_basis"), 256
        ),
        "selected_observation_days_sha256": _text(
            candidate.get("selected_observation_days_sha256"), 128
        ),
        "outcome_purge_rule": _text(candidate.get("outcome_purge_rule"), 512),
        "partial_test_fold_policy": _text(candidate.get("partial_test_fold_policy"), 512),
        "omitted_partial_test_window": _bounded_value(
            candidate.get("omitted_partial_test_window"), depth=3
        ),
        "folds": folds,
        "conclusion": _bounded_value(value.get("conclusion"), depth=5),
        "final_confirmation": _bounded_value(value.get("final_confirmation"), depth=7),
        "research_only": True,
        "auto_apply": False,
    }


def _project_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    schema_id = str(value.get("schema_id") or "")
    if schema_id != _POLICY_BUNDLE_REPORT_SCHEMA:
        raise ValueError("policy_schema_invalid")
    _require_report_safety(value)
    wrapper = value
    simulation = value.get("selection_simulation")
    if not isinstance(simulation, Mapping):
        raise ValueError("selection_simulation_missing")
    if simulation.get("schema_id") != _POLICY_SIMULATION_SCHEMA:
        raise ValueError("policy_simulation_schema_invalid")
    _require_research_safety(simulation)
    scenarios = [
        _project_scenario(row)
        for row in list(simulation.get("scenarios") or [])[:32]
        if isinstance(row, Mapping)
    ]
    recommendations_source = wrapper.get("recommendations") or simulation.get("recommendations")
    recommendations = [
        {
            "scenario": _text(row.get("scenario"), 96),
            "status": _text(row.get("status"), 64),
            "reason": _text(row.get("reason"), 512),
            "sample_size": _count(row.get("sample_size")),
            "evidence_strength": _text(row.get("evidence_strength"), 96),
            "human_approval_required": row.get("human_approval_required") is True,
            "auto_apply": row.get("auto_apply") is True,
        }
        for row in list(recommendations_source or [])[:32]
        if isinstance(row, Mapping)
    ]
    if any(row["auto_apply"] for row in recommendations):
        raise ValueError("policy_recommendation_auto_apply_invalid")
    return {
        "schema_id": schema_id,
        "schema_version": _count(wrapper.get("schema_version")),
        "status": _text(wrapper.get("status"), 96) or "shadow_only",
        "partitions": _strings(simulation.get("partitions"), 8, 64),
        "episode_representatives": _count(simulation.get("episode_representatives")),
        "selected_observation_day_count": _count(
            simulation.get("selected_observation_day_count")
        ),
        "idea_active_day_count": _count(simulation.get("idea_active_day_count")),
        "observed_day_denominator_basis": _text(
            simulation.get("observed_day_denominator_basis"), 256
        ),
        "selected_observation_days_sha256": _text(
            simulation.get("selected_observation_days_sha256"), 128
        ),
        "scenarios": scenarios,
        "recommendations": recommendations,
        "multiple_comparison_warning": _text(simulation.get("multiple_comparison_warning"), 1024),
        "recommendation_seal": _bounded_value(
            wrapper.get("frozen_recommendation_seal") or wrapper.get("recommendation_seal"),
            depth=7,
        ),
        "final_test_confirmation": _bounded_value(
            wrapper.get("final_test_confirmation"), depth=7
        ),
        "decision_boundary": _bounded_value(wrapper.get("decision_boundary"), depth=4),
        "research_only": True,
        "auto_apply": False,
        "production_policy_mutations": 0,
    }


def _project_scenario(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scenario": _text(row.get("scenario"), 96),
        "episode_count": _count(row.get("episode_count")),
        "visible_episode_count": _count(row.get("visible_episode_count")),
        "matured_visible_episode_count": _count(row.get("matured_visible_episode_count")),
        "route_change_count": _count(row.get("route_change_count")),
        "cooldown_suppressed_count": _count(row.get("cooldown_suppressed_count")),
        "urgent_item_count": _count(row.get("urgent_item_count")),
        "active_day_count": _count(row.get("active_day_count")),
        "idea_active_day_count": _count(row.get("idea_active_day_count")),
        "visible_idea_active_day_count": _count(row.get("visible_idea_active_day_count")),
        "observed_day_count": _count(row.get("observed_day_count")),
        "zero_idea_observed_day_count": _count(row.get("zero_idea_observed_day_count")),
        "ideas_per_active_day": _number(row.get("ideas_per_active_day")),
        "ideas_per_observed_day": _number(row.get("ideas_per_observed_day")),
        "visible_ideas_per_idea_active_day": _number(
            row.get("visible_ideas_per_idea_active_day")
        ),
        "mean_directional_return_fraction": _number(row.get("mean_directional_return_fraction")),
        "median_directional_return_fraction": _number(row.get("median_directional_return_fraction")),
        "hit_rate": _number(row.get("hit_rate")),
        "quick_failure_rate": _number(row.get("quick_failure_rate")),
        "evidence_strength": _text(row.get("evidence_strength"), 96),
        "historical_spread_basis": _text(row.get("historical_spread_basis"), 256),
        "costs_observed": row.get("costs_observed") is True,
        "assumed_cost_sensitivity": _bounded_value(
            row.get("assumed_cost_sensitivity"), depth=5
        ),
        "operator_burden": _bounded_value(row.get("operator_burden"), depth=5),
        "false_positive_summary": _bounded_value(
            row.get("false_positive_summary"), depth=4
        ),
        "missed_opportunity_proxy": _bounded_value(
            row.get("missed_opportunity_proxy"), depth=4
        ),
    }


def _project_live_binding(value: Any) -> dict[str, Any]:
    metadata = _project_live_binding_metadata(value)
    if not isinstance(value, Mapping):
        raise ValueError("live_binding_missing")
    canonical = value.get("canonical_projection")
    if canonical is None:
        return {"available": False, "binding": metadata}
    if not isinstance(canonical, Mapping):
        raise ValueError("live_canonical_projection_invalid")
    _require_research_safety(canonical)
    for field in (
        "authorization_mutations",
        "dashboard_authority_mutations",
        "provider_calls",
        "writes",
    ):
        if canonical.get(field) != 0:
            raise ValueError("live_projection_side_effect_claim_invalid")
    projected = _bounded_value(canonical, depth=7)
    if not isinstance(projected, Mapping):
        raise ValueError("live_projection_invalid")
    return {**dict(projected), "available": True, "binding": metadata}


def _project_live_binding_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("live_binding_missing")
    return {
        "status": _text(value.get("status"), 96),
        "filename": _text(value.get("filename"), 256),
        "sha256": _text(value.get("sha256"), 128),
        "size_bytes": _count(value.get("size_bytes")),
        "schema_id": _text(value.get("schema_id"), 128),
        "canonical_projection_sha256": _text(
            value.get("canonical_projection_sha256"), 128
        ),
        "evidence_pooled_with_replay": value.get("evidence_pooled_with_replay") is True,
    }


def _require_research_safety(value: Mapping[str, Any]) -> None:
    if value.get("research_only") is not True or value.get("auto_apply") is not False:
        raise ValueError("research_safety_invalid")
    if value.get("policy_eligible") is True:
        raise ValueError("policy_eligibility_invalid")
    if value.get("production_policy_mutations") not in (None, 0):
        raise ValueError("production_policy_mutation_invalid")


def _require_report_safety(value: Mapping[str, Any]) -> None:
    safety = value.get("safety")
    if not isinstance(safety, Mapping):
        raise ValueError("report_safety_missing")
    if safety.get("research_only") is not True or safety.get("auto_apply") is not False:
        raise ValueError("report_research_safety_invalid")
    for field in (
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
    ):
        if safety.get(field) != 0:
            raise ValueError("report_side_effect_claim_invalid")


def _require_zero_safety(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("safety_missing")
    for field in _ZERO_SIDE_EFFECT_FIELDS:
        if field in value and value.get(field) != 0:
            raise ValueError("side_effect_claim_invalid")


def _bounded_value(value: Any, *, depth: int = 4) -> Any:
    if depth <= 0:
        return None
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value if not isinstance(value, float) or math.isfinite(value) else None
    if isinstance(value, str):
        return value[:1024]
    if isinstance(value, Mapping):
        return {
            str(key)[:128]: _bounded_value(item, depth=depth - 1)
            for key, item in list(sorted(value.items(), key=lambda pair: str(pair[0])))[:64]
        }
    if isinstance(value, (list, tuple)):
        return [_bounded_value(item, depth=depth - 1) for item in value[:64]]
    return _text(value, 256)


def _strings(value: Any, maximum: int, length: int) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [_text(item, length) for item in value[:maximum]]


def _text(value: Any, maximum: int) -> str:
    return str(value or "")[:maximum]


def _count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


__all__ = (
    "MAX_SUPPLEMENT_BYTES",
    "ORIGINS",
    "POLICY_REPORT",
    "REPORT_FILENAMES",
    "ROUTES",
    "SUPPLEMENT_FILENAME",
    "VALIDATION_REPORT",
    "WALK_FORWARD_REPORT",
    "load_research_lab_snapshot",
)
