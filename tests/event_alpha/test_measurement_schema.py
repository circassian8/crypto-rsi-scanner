"""Schema truth checks for the Event Alpha current-window dashboard."""

from __future__ import annotations

import json
from copy import deepcopy

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1


def _payload() -> dict[str, object]:
    return {
        "row_type": "event_alpha_burn_in_measurement_dashboard",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "live_burn_in_no_send",
        "evidence_scope": "active_burn_in_no_candidate_evidence",
        "auto_apply_thresholds": False,
        "generated_at": "2026-07-12T04:00:00+00:00",
        "window_days": 30,
        "low_sample_warning": True,
        "included_namespace_count": 1,
        "real_burn_in_candidate_count": 0,
        "non_burn_in_candidate_count": 0,
        "feedback_rows_eligible": 0,
        "outcome_rows_eligible": 0,
        "near_miss_count": 0,
        "quality_capped_count": 0,
        "research_only": True,
        "no_send_rehearsal": True,
        "current_window_interpretation": {
            "source": "selected_filtered_namespaces",
            "window_days": 30,
            "window_start": "2026-06-12T04:00:00+00:00",
            "window_end": "2026-07-12T04:00:00+00:00",
            "included_namespace_count": 1,
            "real_burn_in_candidate_count": 0,
            "non_burn_in_candidate_count": 0,
            "feedback_rows_eligible": 0,
            "outcome_rows_eligible": 0,
            "near_miss_count": 0,
            "quality_capped_count": 0,
            "interpretation": "insufficient exact current-window evidence for threshold changes",
        },
    }


def test_measurement_dashboard_schema_declares_current_and_deprecated_surfaces(tmp_path):
    schema = schema_v1.get_schema("event_alpha_burn_in_measurement_dashboard_v1")
    assert "current_window_interpretation" in schema.optional_fields
    assert schema.field_types["current_window_interpretation"] == "dict"
    assert schema.field_types["window_days"] == "int"
    assert schema.field_types["low_sample_warning"] == "bool"
    assert "first_real_run_interpretation" in schema.deprecated_fields
    payload = _payload()
    assert schema_v1.validate_row_against_schema(payload, schema) == []

    stale_path = tmp_path / "event_alpha_burn_in_measurement_dashboard.json"
    stale_path.write_text(
        json.dumps(
            {**payload, "first_real_run_interpretation": {"real_candidates": 59}},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    validation = schema_v1.validate_artifact_file(stale_path)
    assert validation["errors"] == []
    assert validation["deprecated_field_usage"] == 1


def test_measurement_dashboard_schema_rejects_shape_and_authority_drift():
    schema = schema_v1.get_schema("event_alpha_burn_in_measurement_dashboard_v1")
    invalid_type = {**_payload(), "current_window_interpretation": "stale prose"}
    assert "invalid_type:current_window_interpretation:dict" in schema_v1.validate_row_against_schema(
        invalid_type,
        schema,
    )

    missing_bound = deepcopy(_payload())
    missing_bound["current_window_interpretation"].pop("window_end")
    errors = schema_v1.validate_row_against_schema(missing_bound, schema)
    assert "measurement_current_window_missing_field" in errors

    extra = deepcopy(_payload())
    extra["current_window_interpretation"]["historical_rollup"] = 59
    assert "measurement_current_window_unknown_field" in schema_v1.validate_row_against_schema(
        extra,
        schema,
    )

    drifted_count = {**_payload(), "near_miss_count": 1}
    assert "measurement_current_window_authority_mismatch:near_miss_count" in schema_v1.validate_row_against_schema(
        drifted_count,
        schema,
    )

    missing_warning = _payload()
    missing_warning.pop("low_sample_warning")
    assert "measurement_current_window_invalid_low_sample_warning" in schema_v1.validate_row_against_schema(
        missing_warning,
        schema,
    )


def test_measurement_dashboard_schema_rejects_clock_source_and_interpretation_drift():
    schema = schema_v1.get_schema("event_alpha_burn_in_measurement_dashboard_v1")
    wrong_source = deepcopy(_payload())
    wrong_source["current_window_interpretation"]["source"] = "historical_rollup"
    assert "measurement_current_window_invalid_source" in schema_v1.validate_row_against_schema(
        wrong_source,
        schema,
    )

    wrong_end = deepcopy(_payload())
    wrong_end["current_window_interpretation"]["window_end"] = "2026-07-11T04:00:00+00:00"
    errors = schema_v1.validate_row_against_schema(wrong_end, schema)
    assert "measurement_current_window_end_mismatch" in errors
    assert "measurement_current_window_start_mismatch" in errors

    naive_start = deepcopy(_payload())
    naive_start["current_window_interpretation"]["window_start"] = "2026-06-12T04:00:00"
    assert "measurement_current_window_invalid_timestamp:window_start" in schema_v1.validate_row_against_schema(
        naive_start,
        schema,
    )

    wrong_branch = deepcopy(_payload())
    wrong_branch["current_window_interpretation"]["interpretation"] = (
        "descriptive current-window evidence; thresholds remain review-only"
    )
    assert "measurement_current_window_interpretation_mismatch" in schema_v1.validate_row_against_schema(
        wrong_branch,
        schema,
    )
