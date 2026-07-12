"""Schema contract tests for the feedback-progress operating artifact."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.namespace import status as namespace_status
from crypto_rsi_scanner.event_alpha.operations import feedback_progress


def _payload() -> dict[str, object]:
    return {
        "schema_version": "event_alpha_feedback_progress_v1",
        "row_type": "event_alpha_feedback_progress",
        "generated_at": "2026-07-12T12:00:00+00:00",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "live_burn_in_no_send",
        "namespace_dir": "event_fade_cache/live_burn_in_no_send",
        "window_days": 7,
        "labels_today": 1,
        "labels_this_week": 2,
        "labels_total": 2,
        "unlabeled_review_items": 1,
        "feedback_rows_supplied": 3,
        "feedback_rows_eligible": 2,
        "feedback_rows_excluded": 1,
        "feedback_exclusion_reason_counts": {"legacy_feedback_contract": 1},
        "labels_by_type": {"junk": 1, "useful": 1},
        "labels_by_opportunity_type": {"EARLY_LONG_RESEARCH": 2},
        "labels_by_source_pack": {"official_exchange": 2},
        "labels_by_provider": {"bybit_announcements": 2},
        "labels_by_candidate_family": {"core:a": 1, "core:b": 1},
        "label_coverage_pct": 50.0,
        "stale_unresolved_feedback_targets": ["core:b"],
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
    }


def test_feedback_progress_schema_registers_and_validates_file(tmp_path):
    schema = schema_v1.get_schema("event_alpha_feedback_progress_v1")
    payload = _payload()

    assert schema_v1.infer_schema_id_for_file("event_alpha_feedback_progress.json") == schema.schema_id
    assert schema_v1.schema_for_row(payload) == schema
    assert schema_v1.validate_row_against_schema(payload, schema) == []

    path = tmp_path / "event_alpha_feedback_progress.json"
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    validation = schema_v1.validate_artifact_file(path)
    assert validation["schema_id"] == schema.schema_id
    assert validation["rows_read"] == 1
    assert validation["rows_validated"] == 1
    assert validation["errors"] == []


def test_feedback_progress_producer_output_matches_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(
        feedback_progress.common,
        "repo_root_from_module",
        lambda: tmp_path,
    )
    payload = feedback_progress.build_feedback_progress(
        profile="live_burn_in_no_send",
        base_dir=tmp_path,
        days=7,
        now=datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc),
    )

    assert schema_v1.validate_row_against_schema(
        payload,
        "event_alpha_feedback_progress_v1",
    ) == []
    validation = schema_v1.validate_artifact_file(
        tmp_path / "live_burn_in_no_send" / "event_alpha_feedback_progress.json"
    )
    assert validation["rows_validated"] == 1
    assert validation["errors"] == []


def test_feedback_progress_schema_rejects_denominator_clock_and_safety_drift():
    invalid = deepcopy(_payload())
    invalid.update(
        {
            "generated_at": "2026-07-12T12:00:00",
            "labels_today": 3,
            "labels_total": 3,
            "feedback_rows_supplied": 4,
            "label_coverage_pct": 101.0,
            "stale_unresolved_feedback_targets": ["core:b", "core:b"],
            "no_send_rehearsal": False,
            "normal_rsi_signal_rows_written": 1,
        }
    )

    errors = schema_v1.validate_row_against_schema(
        invalid,
        "event_alpha_feedback_progress_v1",
    )
    assert "feedback_progress_generated_at_invalid" in errors
    assert "feedback_progress_denominator_mismatch" in errors
    assert "feedback_progress_labels_total_mismatch" in errors
    assert "feedback_progress_window_count_mismatch" in errors
    assert "feedback_progress_breakdown_total_mismatch:labels_by_type" in errors
    assert "feedback_progress_label_coverage_invalid" in errors
    assert "feedback_progress_stale_targets_invalid" in errors
    assert "feedback_progress_not_no_send" in errors
    assert "unsafe_side_effect_count:normal_rsi_signal_rows_written" in errors


def test_feedback_progress_schema_rejects_invalid_counter_and_reason_maps():
    invalid = deepcopy(_payload())
    invalid["window_days"] = 0
    invalid["labels_today"] = True
    invalid["labels_by_provider"] = {"bybit_announcements": -1}
    invalid["feedback_exclusion_reason_counts"] = {"": 1}

    errors = schema_v1.validate_row_against_schema(
        invalid,
        "event_alpha_feedback_progress_v1",
    )
    assert "feedback_progress_window_days_invalid" in errors
    assert "invalid_type:labels_today:int" in errors
    assert "feedback_progress_counter_invalid:labels_today" in errors
    assert "feedback_progress_breakdown_invalid:labels_by_provider" in errors
    assert "feedback_progress_exclusion_reasons_invalid" in errors


def test_feedback_progress_refuses_archived_output_namespace(tmp_path):
    namespace_dir = tmp_path / "archived_burn_in"
    marker = namespace_status.write_namespace_status(
        namespace_dir,
        {
            "namespace": namespace_dir.name,
            "status": namespace_status.STATUS_ARCHIVED,
            "safe_for_send_readiness": False,
        },
        now=datetime(2026, 7, 12, 11, 0, tzinfo=timezone.utc),
    )
    marker_before = marker.read_bytes()

    with pytest.raises(ValueError, match="output namespace is immutable"):
        feedback_progress.build_feedback_progress(
            profile="live_burn_in_no_send",
            artifact_namespace=namespace_dir.name,
            base_dir=tmp_path,
            now=datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc),
        )

    assert marker.read_bytes() == marker_before
    assert not (namespace_dir / feedback_progress.PROGRESS_JSON).exists()
    assert not (namespace_dir / feedback_progress.PROGRESS_MD).exists()
