"""Focused pytest checks for Event Alpha schema v1."""

from __future__ import annotations

import json
from copy import deepcopy

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.artifacts.schema import calendar as calendar_schema
from crypto_rsi_scanner.event_alpha.doctor import check_registry, schema_doctor


def _operator_state_schema_row(artifacts):
    return {
        "row_type": "event_alpha_operator_state",
        "run_id": "run-fingerprint",
        "profile": "fixture",
        "artifact_namespace": "fingerprint",
        "revision": 1,
        "manifest_status": "complete",
        "artifacts": artifacts,
        "doctor": {"status": "stale", "authoritative": False},
        "research_only": True,
        "no_send_rehearsal": True,
        "sent": False,
        "send_requested": False,
        "send_attempted": False,
        "send_success": False,
        "send_items_delivered": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
    }


def _current_artifact_fingerprint(kind, *, item_count=1):
    return {
        "status": "current",
        "fingerprint_contract_version": 1,
        "fingerprint_kind": kind,
        "sha256": "a" * 64,
        "size_bytes": 42,
        "item_count": item_count,
    }


def _valid_calendar_normalization():
    return {
        "contract_version": 1,
        "dedupe_policy": "last_valid_row_wins",
        "input_rows": 7,
        "accepted_rows": 5,
        "output_rows": 4,
        "duplicate_overwrite_rows": 1,
        "non_mapping_rows": 1,
        "rejected_rows": 1,
        "rejected_reason_counts": {"missing_title": 1},
    }


def _calendar_run_row():
    return {
        "row_type": "event_alpha_run",
        "run_id": "calendar-normalization-run",
        "profile": "fixture",
        "unified_calendar_rows": 4,
        "unified_calendar_normalization": _valid_calendar_normalization(),
    }


def test_run_ledger_calendar_normalization_schema_accepts_v1_and_legacy_rows():
    schema = schema_v1.get_schema("run_ledger_v1")
    assert "unified_calendar_normalization" in schema.optional_fields
    assert schema.field_types["unified_calendar_normalization"] == "dict"
    assert schema_v1.validate_row_against_schema(_calendar_run_row(), schema) == []
    assert schema_v1.validate_row_against_schema(
        {
            "row_type": "event_alpha_run",
            "run_id": "legacy-calendar-run",
            "profile": "fixture",
            "unified_calendar_rows": 2,
        },
        schema,
    ) == []


def test_run_ledger_calendar_normalization_schema_rejects_shape_and_contract_tampering():
    missing = _calendar_run_row()
    missing["unified_calendar_normalization"].pop("accepted_rows")
    errors = schema_v1.validate_row_against_schema(missing, "run_ledger_v1")
    assert "calendar_normalization_missing_field:accepted_rows" in errors

    extra = _calendar_run_row()
    extra["unified_calendar_normalization"]["raw_payload"] = "SECRET"
    errors = schema_v1.validate_row_against_schema(extra, "run_ledger_v1")
    assert "calendar_normalization_unknown_field" in errors
    assert "SECRET" not in " ".join(errors)

    for field_name, value, expected_error in (
        ("contract_version", True, "calendar_normalization_contract_version_invalid"),
        ("contract_version", 2, "calendar_normalization_contract_version_invalid"),
        ("dedupe_policy", "first_row_wins", "calendar_normalization_dedupe_policy_invalid"),
        ("input_rows", True, "calendar_normalization_counter_invalid:input_rows"),
        ("output_rows", -1, "calendar_normalization_counter_invalid:output_rows"),
    ):
        tampered = _calendar_run_row()
        tampered["unified_calendar_normalization"][field_name] = value
        assert expected_error in schema_v1.validate_row_against_schema(
            tampered,
            "run_ledger_v1",
        )


def test_run_ledger_calendar_normalization_schema_rejects_reason_and_counter_tampering():
    for reason_counts, expected_error in (
        ({"not_a_registered_reason": 1}, "calendar_normalization_rejected_reason_unknown"),
        ({"missing_title": 0}, "calendar_normalization_rejected_reason_count_invalid"),
        ({"missing_title": True}, "calendar_normalization_rejected_reason_count_invalid"),
    ):
        tampered = _calendar_run_row()
        tampered["unified_calendar_normalization"]["rejected_reason_counts"] = reason_counts
        assert expected_error in schema_v1.validate_row_against_schema(
            tampered,
            "run_ledger_v1",
        )

    input_mismatch = _calendar_run_row()
    input_mismatch["unified_calendar_normalization"]["input_rows"] = 8
    assert "calendar_normalization_input_counter_mismatch" in schema_v1.validate_row_against_schema(
        input_mismatch,
        "run_ledger_v1",
    )

    accepted_mismatch = _calendar_run_row()
    accepted_mismatch["unified_calendar_normalization"]["duplicate_overwrite_rows"] = 0
    assert "calendar_normalization_accepted_counter_mismatch" in schema_v1.validate_row_against_schema(
        accepted_mismatch,
        "run_ledger_v1",
    )

    rejected_mismatch = _calendar_run_row()
    rejected_mismatch["unified_calendar_normalization"]["rejected_reason_counts"] = {
        "missing_title": 2
    }
    assert "calendar_normalization_rejected_counter_mismatch" in schema_v1.validate_row_against_schema(
        rejected_mismatch,
        "run_ledger_v1",
    )

    output_mismatch = _calendar_run_row()
    output_mismatch["unified_calendar_rows"] = 5
    assert "calendar_normalization_output_rows_mismatch" in schema_v1.validate_row_against_schema(
        output_mismatch,
        "run_ledger_v1",
    )


def test_calendar_normalization_schema_constants_match_the_producer_contract():
    from crypto_rsi_scanner.event_alpha.radar import calendar as calendar_producer

    assert (
        calendar_schema.CALENDAR_NORMALIZATION_CONTRACT_VERSION
        == calendar_producer.CALENDAR_NORMALIZATION_CONTRACT_VERSION
    )
    assert (
        calendar_schema.CALENDAR_NORMALIZATION_DEDUPE_POLICY
        == calendar_producer.CALENDAR_DEDUPE_POLICY
    )
    assert (
        calendar_schema.CALENDAR_NORMALIZATION_REJECTION_CODES
        == calendar_producer.CALENDAR_REJECTION_CODES
    )


def test_run_ledger_writer_rejects_calendar_telemetry_before_secret_bearing_data_is_written(
    tmp_path,
):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from crypto_rsi_scanner.event_alpha.artifacts import run_ledger

    ledger_path = tmp_path / "event_alpha_runs.jsonl"
    malformed = _valid_calendar_normalization()
    malformed["dedupe_policy"] = "SECRET_BAD_POLICY"
    malformed["raw_payload"] = "SECRET"
    result = SimpleNamespace(
        run_id="malformed-calendar-run",
        profile="fixture",
        unified_calendar_rows=4,
        unified_calendar_normalization=malformed,
    )
    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)

    try:
        run_ledger.append_run_record(
            result,
            cfg=run_ledger.EventAlphaRunLedgerConfig(path=ledger_path),
            profile="fixture",
            started_at=now,
            finished_at=now,
            with_llm=False,
            send_requested=False,
        )
    except ValueError as exc:
        assert str(exc) == "invalid unified calendar normalization telemetry"
    else:
        raise AssertionError("malformed calendar telemetry was accepted")

    ledger_bytes = ledger_path.read_bytes() if ledger_path.exists() else b""
    assert b"SECRET" not in ledger_bytes
    assert ledger_bytes == b""

    class SecretLeakingValue:
        def __eq__(self, other):
            raise RuntimeError("SECRET")

        def __ne__(self, other):
            raise RuntimeError("SECRET")

    hostile = _valid_calendar_normalization()
    hostile["dedupe_policy"] = SecretLeakingValue()
    result.unified_calendar_normalization = hostile
    try:
        run_ledger.append_run_record(
            result,
            cfg=run_ledger.EventAlphaRunLedgerConfig(path=ledger_path),
            profile="fixture",
            started_at=now,
            finished_at=now,
            with_llm=False,
            send_requested=False,
        )
    except ValueError as exc:
        assert str(exc) == "invalid unified calendar normalization telemetry"
        assert "SECRET" not in str(exc)
    else:
        raise AssertionError("hostile calendar telemetry was accepted")
    assert not ledger_path.exists()


def test_operator_state_schema_keeps_fingerprintless_and_sha_only_legacy_entries_readable():
    state = _operator_state_schema_row(
        {
            "core_opportunities": {"status": "current", "path": "event_core_opportunities.jsonl"},
            "unified_calendar": {
                "status": "current",
                "path": "event_unified_calendar_events.jsonl",
                "count": 2,
                "sha256": "b" * 64,
            },
            "daily_brief": {
                "status": "stale",
                "fingerprint_contract_version": "legacy-invalid-but-not-current",
            },
        }
    )

    assert schema_v1.validate_row_against_schema(state, "operator_state_v1") == []


def test_operator_state_schema_rejects_malformed_sha_only_and_stray_run_row_digest():
    malformed_sha = _operator_state_schema_row(
        {"unified_calendar": {"status": "current", "sha256": "not-a-sha256"}}
    )
    errors = schema_v1.validate_row_against_schema(malformed_sha, "operator_state_v1")
    assert "operator_state_current_artifact_invalid_sha256:unified_calendar" in errors
    assert (
        "operator_state_current_artifact_missing_fingerprint:unified_calendar:fingerprint_contract_version"
        in errors
    )


def test_operator_state_schema_rejects_deprecated_and_misplaced_run_row_fields():
    state = _operator_state_schema_row(
        {
            "core_opportunities": {
                **_current_artifact_fingerprint("jsonl_lines", item_count=1),
                "run_row_identity": {
                    "run_id": "schema-run",
                    "profile": "fixture",
                    "artifact_namespace": "schema-fixture",
                },
                "run_row_match_count": 1,
            },
            "run_ledger": {
                **_current_artifact_fingerprint("canonical_run_row", item_count=1),
                "run_row_identity": {
                    "run_id": "schema-run",
                    "profile": "fixture",
                    "artifact_namespace": "schema-fixture",
                },
                "run_row_match_count": 1,
                "run_row_sha256": "0" * 64,
            },
        }
    )

    errors = schema_v1.validate_row_against_schema(state, "operator_state_v1")

    assert (
        "operator_state_current_artifact_invalid_run_row_fields:core_opportunities"
        in errors
    )
    assert "operator_state_current_artifact_deprecated_run_row_sha256:run_ledger" in errors

    stray_run_digest = _operator_state_schema_row(
        {"run_ledger": {"status": "current", "run_row_sha256": "b" * 64}}
    )
    errors = schema_v1.validate_row_against_schema(stray_run_digest, "operator_state_v1")
    assert "operator_state_current_artifact_missing_fingerprint:run_ledger:sha256" in errors
    assert "operator_state_run_ledger_invalid_run_row_identity" in errors


def test_operator_state_schema_requires_complete_fingerprint_metadata_once_started():
    state = _operator_state_schema_row(
        {
            "daily_brief": {
                "status": "current",
                "fingerprint_contract_version": 1,
            }
        }
    )

    errors = schema_v1.validate_row_against_schema(state, "operator_state_v1")

    assert "operator_state_current_artifact_missing_fingerprint:daily_brief:fingerprint_kind" in errors
    assert "operator_state_current_artifact_missing_fingerprint:daily_brief:sha256" in errors
    assert "operator_state_current_artifact_missing_fingerprint:daily_brief:size_bytes" in errors
    assert "operator_state_current_artifact_missing_fingerprint:daily_brief:item_count" in errors
    assert "operator_state_current_artifact_invalid_fingerprint_kind:daily_brief" in errors
    assert "operator_state_current_artifact_invalid_sha256:daily_brief" in errors
    assert "operator_state_current_artifact_invalid_size_bytes:daily_brief" in errors
    assert "operator_state_current_artifact_invalid_item_count:daily_brief" in errors


def test_operator_state_schema_accepts_each_artifact_fingerprint_kind():
    state = _operator_state_schema_row(
        {
            "core_opportunities": _current_artifact_fingerprint("jsonl_lines", item_count=4),
            "research_cards": _current_artifact_fingerprint("directory_tree_v1", item_count=3),
            "daily_brief": _current_artifact_fingerprint("file_bytes"),
            "provider_readiness_json": _current_artifact_fingerprint("file_bytes"),
            "unified_calendar": _current_artifact_fingerprint("jsonl_lines", item_count=2),
        }
    )

    assert schema_v1.validate_row_against_schema(state, "operator_state_v1") == []


def test_operator_state_schema_rejects_malformed_common_fingerprint_fields():
    valid = _current_artifact_fingerprint("file_bytes")
    malformed = {
        "fingerprint_contract_version": True,
        "fingerprint_kind": "jsonl_lines",
        "sha256": "A" * 64,
        "size_bytes": True,
        "item_count": -1,
    }
    state = _operator_state_schema_row({"daily_brief": dict(valid, **malformed)})

    errors = schema_v1.validate_row_against_schema(state, "operator_state_v1")

    assert "operator_state_current_artifact_invalid_fingerprint_version:daily_brief" in errors
    assert "operator_state_current_artifact_invalid_fingerprint_kind:daily_brief" in errors
    assert "operator_state_current_artifact_invalid_sha256:daily_brief" in errors
    assert "operator_state_current_artifact_invalid_size_bytes:daily_brief" in errors
    assert "operator_state_current_artifact_invalid_item_count:daily_brief" in errors


def test_operator_state_schema_accepts_exact_canonical_run_row_fingerprint():
    run_ledger = _current_artifact_fingerprint("canonical_run_row")
    run_ledger.update(
        {
            "run_row_identity": {
                "run_id": "run-fingerprint",
                "profile": "fixture",
                "artifact_namespace": "fingerprint",
            },
            "run_row_match_count": 1,
        }
    )
    state = _operator_state_schema_row({"run_ledger": run_ledger})

    assert schema_v1.validate_row_against_schema(state, "operator_state_v1") == []


def test_operator_state_schema_rejects_ambiguous_or_incomplete_run_row_fingerprint():
    valid = _current_artifact_fingerprint("canonical_run_row")
    valid.update(
        {
            "run_row_identity": {
                "run_id": "run-fingerprint",
                "profile": "fixture",
                "artifact_namespace": "fingerprint",
            },
            "run_row_match_count": 1,
        }
    )

    missing_sha = dict(valid)
    missing_sha.pop("sha256")
    missing_sha["run_row_sha256"] = "b" * 64
    errors = schema_v1.validate_row_against_schema(
        _operator_state_schema_row({"run_ledger": missing_sha}),
        "operator_state_v1",
    )
    assert "operator_state_current_artifact_missing_fingerprint:run_ledger:sha256" in errors
    assert "operator_state_current_artifact_invalid_sha256:run_ledger" in errors

    wrong_identity = deepcopy(valid)
    wrong_identity["run_row_identity"]["run_id"] = "different-run"
    errors = schema_v1.validate_row_against_schema(
        _operator_state_schema_row({"run_ledger": wrong_identity}),
        "operator_state_v1",
    )
    assert "operator_state_run_ledger_identity_mismatch:run_id" in errors

    ambiguous = dict(valid, run_row_match_count=0, item_count=2)
    errors = schema_v1.validate_row_against_schema(
        _operator_state_schema_row({"run_ledger": ambiguous}),
        "operator_state_v1",
    )
    assert "operator_state_run_ledger_match_count_not_one" in errors
    assert "operator_state_run_ledger_item_count_not_one" in errors

    bool_match_count = dict(valid, run_row_match_count=True)
    errors = schema_v1.validate_row_against_schema(
        _operator_state_schema_row({"run_ledger": bool_match_count}),
        "operator_state_v1",
    )
    assert "operator_state_run_ledger_match_count_not_one" in errors

    wrong_kind = dict(valid, fingerprint_kind="jsonl_lines")
    errors = schema_v1.validate_row_against_schema(
        _operator_state_schema_row({"run_ledger": wrong_kind}),
        "operator_state_v1",
    )
    assert "operator_state_current_artifact_invalid_fingerprint_kind:run_ledger" in errors


def test_schema_registry_contains_required_ids():
    assert "integrated_radar_candidate_v1" in schema_v1.SCHEMAS
    assert "namespace_status_v1" in schema_v1.SCHEMAS
    assert schema_doctor.check_registry_schema_dependency_errors() == ()


def test_provider_lineage_schema_specs_preserve_registry_order_and_api():
    expected = [
        "provider_readiness_v1",
        "provider_preflight_v1",
        "coinalyze_request_ledger_v1",
        "provider_request_ledger_v1",
        "derivatives_state_snapshot_v1",
        "derivatives_crowding_candidate_v1",
        "fade_review_candidate_v1",
        "market_state_snapshot_v1",
        "targeted_market_refresh_ledger_v1",
        "targeted_market_refresh_report_v1",
    ]
    registered = list(schema_v1.SCHEMAS)
    start = registered.index(expected[0])
    assert registered[start:start + len(expected)] == expected
    assert all(schema_v1.get_schema(schema_id) is schema_v1.SCHEMAS[schema_id] for schema_id in expected)
    assert schema_v1.get_schema("provider_preflight_v1").required_fields == (
        "provider", "configured", "live_call_allowed",
    )
    provider_ledger_fields = schema_v1.get_schema("provider_request_ledger_v1").optional_fields
    assert {
        "response_headers_safe",
        "response_body_summary_redacted",
        "response_body_truncated",
        "response_bytes_captured",
    } <= set(provider_ledger_fields)
    assert schema_v1.get_schema("targeted_market_refresh_report_v1").path_fields == (
        "ledger_path", "snapshot_path",
    )


def test_doctor_check_registry_declares_schema_dependencies():
    rows = check_registry.registry_rows()
    categories = {str(row["category"]) for row in rows}
    assert set(check_registry.CATEGORIES).issubset(categories)
    assert check_registry.registry_errors() == ()
    assert check_registry.legacy_unregistered_count() <= check_registry.LEGACY_UNREGISTERED_BASELINE

    schema_fields = schema_v1.all_schema_fields()
    for row in rows:
        assert row["check_id"]
        assert row["description"]
        assert row["introduced_in_schema_version"] == schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION
        assert row["severity"] in check_registry.SEVERITIES
        for dependency in row["schema_dependencies"]:
            assert dependency in schema_fields, row["check_id"]


def test_artifact_module_import_shims_match_new_package_paths():
    import crypto_rsi_scanner.event_alpha.artifacts.context as old_context
    import crypto_rsi_scanner.event_alpha.namespace.status as old_namespace_status
    import crypto_rsi_scanner.event_alpha.artifacts.retention as old_retention
    import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as old_run_ledger
    import crypto_rsi_scanner.event_alpha.artifacts.locks as old_locks
    import crypto_rsi_scanner.event_alpha.artifacts.paths as old_paths
    from crypto_rsi_scanner.event_alpha.artifacts import (
        context as new_context,
        locks as new_locks,
        paths as new_paths,
        retention as new_retention,
        run_ledger as new_run_ledger,
    )
    from crypto_rsi_scanner.event_alpha.namespace import status as new_namespace_status

    assert old_context.context_from_profile is new_context.context_from_profile
    assert old_context.EventAlphaArtifactContext is new_context.EventAlphaArtifactContext
    assert old_paths.artifact_display_path is new_paths.artifact_display_path
    assert old_paths.normalize_operator_path_fields is new_paths.normalize_operator_path_fields
    assert old_paths.repo_root() == new_paths.repo_root()
    assert old_run_ledger.append_run_record is new_run_ledger.append_run_record
    assert old_run_ledger.EventAlphaRunLedgerConfig is new_run_ledger.EventAlphaRunLedgerConfig
    assert old_retention.prune_event_alpha_artifacts is new_retention.prune_event_alpha_artifacts
    assert old_retention.EventAlphaRetentionConfig is new_retention.EventAlphaRetentionConfig
    assert old_locks.acquire_run_lock is new_locks.acquire_run_lock
    assert old_locks.EventAlphaRunLockConfig is new_locks.EventAlphaRunLockConfig
    assert old_locks._read_lock is new_locks._read_lock
    assert old_namespace_status.mark_namespace_stale is new_namespace_status.mark_namespace_stale
    assert old_namespace_status.EventAlphaNamespaceStatus is new_namespace_status.EventAlphaNamespaceStatus


def test_large_event_alpha_internal_modules_have_small_public_wrappers():
    import inspect
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as old_daily_brief
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as old_core_store
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as old_evidence
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as old_hypotheses
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as old_integrated
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as old_research_cards
    from crypto_rsi_scanner.event_alpha.artifacts import daily_brief, research_cards
    from crypto_rsi_scanner.event_alpha.artifacts.daily_brief import builder as daily_builder
    from crypto_rsi_scanner.event_alpha.artifacts.research_cards import renderer as card_renderer
    from crypto_rsi_scanner.event_alpha.notifications import (
        delivery_writer,
        heartbeat,
        message_rendering,
        models as notification_models,
        pipeline,
        preview_writer,
        research_review_selection,
        skip_telemetry,
    )
    from crypto_rsi_scanner.event_alpha.radar import (
        core_opportunity_store,
        evidence_acquisition,
        impact_hypotheses,
        integrated_radar,
    )
    from crypto_rsi_scanner.event_alpha.radar.core import models as core_models
    from crypto_rsi_scanner.event_alpha.radar.evidence import models as evidence_models
    from crypto_rsi_scanner.event_alpha.radar.impact_hypotheses import models as hypothesis_models
    from crypto_rsi_scanner.event_alpha.radar.integrated import models as integrated_models

    root = Path(__file__).resolve().parents[2]
    assert sum(1 for _ in (root / "crypto_rsi_scanner/event_alpha/notifications/pipeline.py").open()) < 1500
    assert sum(1 for _ in (root / "crypto_rsi_scanner/event_alpha/artifacts/research_cards/__init__.py").open()) < 300
    assert sum(1 for _ in (root / "crypto_rsi_scanner/event_alpha/artifacts/daily_brief/__init__.py").open()) < 300
    assert sum(1 for _ in (root / "crypto_rsi_scanner/event_alpha/radar/integrated_radar.py").open()) < 300
    assert sum(1 for _ in (root / "crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/__init__.py").open()) < 300
    assert sum(1 for _ in (root / "crypto_rsi_scanner/event_alpha/radar/core_opportunity_store.py").open()) < 300
    assert sum(1 for _ in (root / "crypto_rsi_scanner/event_alpha/radar/evidence_acquisition.py").open()) < 300

    assert len(inspect.getsourcelines(pipeline.send_notifications)[0]) < 120
    assert len(inspect.getsourcelines(pipeline.write_notification_plan_preview)[0]) < 100
    assert len(inspect.getsourcelines(pipeline.select_research_review_candidates_with_diagnostics)[0]) < 100
    assert len(inspect.getsourcelines(daily_brief.build_daily_brief)[0]) < 120
    assert len(inspect.getsourcelines(integrated_radar.run_integrated_radar_cycle)[0]) < 150

    assert old_research_cards.render_research_card is research_cards.render_research_card
    assert old_daily_brief.build_daily_brief is daily_brief.build_daily_brief
    assert old_integrated.run_integrated_radar_cycle is integrated_radar.run_integrated_radar_cycle
    assert old_hypotheses.EventImpactHypothesis is impact_hypotheses.EventImpactHypothesis
    assert old_core_store.write_core_opportunities is core_opportunity_store.write_core_opportunities
    assert old_evidence.run_evidence_acquisition is evidence_acquisition.run_evidence_acquisition

    assert notification_models.EventAlphaNotificationPlan is pipeline.EventAlphaNotificationPlan
    assert delivery_writer._DeliveryWriter is pipeline._DeliveryWriter
    assert preview_writer.write_notification_plan_preview is not pipeline.write_notification_plan_preview
    assert research_review_selection.select_research_review_candidates_with_diagnostics is not pipeline.select_research_review_candidates_with_diagnostics
    assert skip_telemetry.EventAlphaResearchReviewSkippedItem is pipeline.EventAlphaResearchReviewSkippedItem
    assert heartbeat.format_health_heartbeat is pipeline.format_health_heartbeat
    assert message_rendering.format_preview is pipeline.format_preview
    assert card_renderer.render_research_card is research_cards.render_research_card
    assert daily_builder.build_daily_brief is not daily_brief.build_daily_brief
    assert integrated_models.EventIntegratedRadarResult is integrated_radar.EventIntegratedRadarResult
    assert hypothesis_models.EventImpactHypothesis is impact_hypotheses.EventImpactHypothesis
    assert core_models.EventCoreOpportunityStoreWriteResult is core_opportunity_store.EventCoreOpportunityStoreWriteResult
    assert evidence_models.EvidenceAcquisitionResult is evidence_acquisition.EvidenceAcquisitionResult


def test_event_alpha_split_runner_and_make_target_are_wired():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    output = subprocess.check_output(
        [sys.executable, str(root / "tests" / "test_indicators.py"), "--list-tests"],
        cwd=root,
        text=True,
    )
    counts = {
        key: int(value)
        for line in output.splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }
    assert counts["standalone_tests"] > 600
    assert counts["event_alpha_tests"] > 500

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert "test-event-alpha:" in makefile
    assert "$(PYTHON) -m pytest tests/event_alpha" in makefile
    assert "event-alpha-doctor-check-registry:" in makefile
    assert "$(PYTHON) -m crypto_rsi_scanner.event_alpha.doctor.check_registry" in makefile

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})

def test_event_impact_hypothesis_store_reports_schema_and_promotion_diagnostics():
    import json
    from datetime import datetime, timezone
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store as event_impact_hypothesis_store

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    rows = [
        {
            "row_type": "event_impact_hypothesis",
            "schema_version": event_impact_hypothesis_store.IMPACT_HYPOTHESIS_STORE_SCHEMA_VERSION,
            "observed_at": now.isoformat(),
            "run_id": "run-new",
            "hypothesis_id": "current",
            "status": "validation_search_pending",
            "validation_stage": "candidate_assets_suggested",
            "hypothesis_score": 54.0,
            "impact_category": "ai_ipo_proxy",
            "external_asset": "OpenAI",
            "external_entities": [{"name": "OpenAI"}],
            "crypto_candidate_assets": [{"symbol": "VELVET", "coin_id": "velvet", "source": "candidate_discovery_search"}],
            "why_not_promoted": ["candidate_identity_not_validated", "catalyst_link_missing"],
            "generated_queries": [
                {"query": "OpenAI crypto exposure", "query_type": "candidate_discovery"},
                {"query": "VELVET OpenAI exposure", "query_type": "candidate_validation"},
            ],
            "executed_queries": [
                {"query": "OpenAI crypto exposure", "query_type": "candidate_discovery"},
            ],
            "rejected_validation_samples": [{
                "query": "OpenAI crypto exposure",
                "query_type": "candidate_discovery",
                "result_title": "VELVET opens OpenAI venue",
                "source": "fixture",
                "candidate_symbol": "SECTOR",
                "score": 45,
                "result_score": 45,
                "rejection_reason": "result_identity_rejected",
            }],
        },
        {
            "row_type": "event_impact_hypothesis",
            "observed_at": "2026-06-17T12:00:00+00:00",
            "run_id": "run-old",
            "hypothesis_id": "legacy",
            "status": "hypothesis",
            "impact_category": "rwa_preipo_proxy",
            "external_asset": "SpaceX",
            "crypto_candidate_assets": [{"symbol": "OPENAI", "source": "legacy_bad_parse"}],
        },
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_impact_hypotheses.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        all_rows = event_impact_hypothesis_store.load_impact_hypotheses(path)
        report = event_impact_hypothesis_store.format_impact_hypotheses_store_report(all_rows, now=now)
        assert "schema_audit:" in report
        assert "latest_run_id: run-new" in report
        assert "historical_rows_available: 1" in report
        assert "legacy_rows=1" in report
        assert "missing_validation_stage=1" in report
        assert "legacy_schema_missing_stage=1" in report
        assert "entity_audit:" in report
        assert "suspicious_external_as_candidate=1" in report
        assert "generated_query_type_counts: candidate_discovery=1, candidate_validation=1" in report
        assert "executed_query_type_counts: candidate_discovery=1" in report
        assert "Why not promoted diagnostics:" in report
        assert "candidate_identity_not_validated=1" in report
        assert "Rejected validation evidence samples: 1" in report
        latest = event_impact_hypothesis_store.load_impact_hypotheses(path, latest_run=True, include_api=False)
        assert latest.rows_read == 1
        assert latest.rows[0]["hypothesis_id"] == "current"
        assert all(row["hypothesis_id"] != "legacy" for row in latest.rows)
        by_run = event_impact_hypothesis_store.load_impact_hypotheses(path, run_id="run-old", include_api=True)
        assert by_run.rows_read == 1
        assert by_run.rows[0]["hypothesis_id"] == "legacy"
        since = event_impact_hypothesis_store.load_impact_hypotheses(path, since="2026-06-18T00:00:00+00:00")
        assert since.rows_read == 1


def test_event_llm_source_triage_schema_and_quote_validation():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMSourceQualityProvider

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw_event(raw_id: str, provider: str, url: str, title: str, body: str) -> RawDiscoveredEvent:
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=url,
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.9,
            content_hash=raw_id,
        )

    provider = FixtureLLMSourceQualityProvider(cases={
        "good-triage": {
            "page_type": "article",
            "is_real_article": True,
            "article_quality": "fixture_text_used",
            "boilerplate_ratio_estimate": 0.08,
            "is_official_source": False,
            "is_recap": False,
            "is_affiliate_or_seo": False,
            "candidate_catalyst_mechanism_present": True,
            "evidence_quote": "Velvet offers SpaceX pre-IPO tokenized stock exposure",
            "confidence": 0.91,
            "reason": "direct mechanism quote",
        },
        "official-triage": {
            "page_type": "official_announcement",
            "is_real_article": True,
            "article_quality": "fixture_text_used",
            "boilerplate_ratio_estimate": 0.05,
            "is_official_source": True,
            "is_recap": False,
            "is_affiliate_or_seo": False,
            "candidate_catalyst_mechanism_present": True,
            "evidence_quote": "Binance will list TESTUSDT",
            "confidence": 0.94,
        },
        "seo-triage": {
            "page_type": "seo_affiliate",
            "is_real_article": True,
            "article_quality": "good",
            "boilerplate_ratio_estimate": 0.2,
            "is_official_source": False,
            "is_recap": False,
            "is_affiliate_or_seo": True,
            "candidate_catalyst_mechanism_present": False,
            "evidence_quote": "",
            "confidence": 0.88,
        },
        "bad-triage": {
            "page_type": "not_a_page_type",
            "is_real_article": True,
            "article_quality": "good",
            "boilerplate_ratio_estimate": 0.1,
            "is_official_source": False,
            "is_recap": False,
            "is_affiliate_or_seo": False,
            "candidate_catalyst_mechanism_present": True,
            "evidence_quote": "unsupported",
            "confidence": 0.8,
        },
        "missing-quote": {
            "page_type": "article",
            "is_real_article": True,
            "article_quality": "fixture_text_used",
            "boilerplate_ratio_estimate": 0.1,
            "is_official_source": False,
            "is_recap": False,
            "is_affiliate_or_seo": False,
            "candidate_catalyst_mechanism_present": True,
            "evidence_quote": "quote not in source",
            "confidence": 0.92,
        },
    })
    cfg = event_source_enrichment.EventSourceQualityJudgeConfig(enabled=True, min_importance_score=0)

    good = event_source_enrichment.run_llm_source_triage(
        raw_event(
            "good-triage",
            "cryptopanic_news",
            "https://fixture.test/velvet",
            "Velvet offers SpaceX exposure",
            "Velvet offers SpaceX pre-IPO tokenized stock exposure for crypto users.",
        ),
        provider=provider,
        cfg=cfg,
    )
    assert good is not None
    assert good.page_type == "article"
    assert good.candidate_catalyst_mechanism_present is True
    assert good.confidence > 0.8

    official = event_source_enrichment.run_llm_source_triage(
        raw_event(
            "official-triage",
            "binance_announcements",
            "https://www.binance.com/en/support/announcement/test",
            "Binance Will List TESTUSDT",
            "Binance will list TESTUSDT and open spot trading.",
        ),
        provider=provider,
        cfg=cfg,
    )
    assert official is not None
    assert official.is_official_source is True

    seo = event_source_enrichment.run_llm_source_triage(
        raw_event(
            "seo-triage",
            "rss",
            "https://seo.example/referral",
            "Register Binance now",
            "Register Binance now with referral code USD777 and sign up now for lifetime fee bonus.",
        ),
        provider=provider,
        cfg=cfg,
    )
    assert seo is not None
    assert seo.is_real_article is False
    assert seo.confidence <= 0.45

    missing = event_source_enrichment.run_llm_source_triage(
        raw_event(
            "missing-quote",
            "rss",
            "https://fixture.test/missing",
            "Velvet offers SpaceX exposure",
            "Velvet offers SpaceX exposure.",
        ),
        provider=provider,
        cfg=cfg,
    )
    assert missing is not None
    assert missing.confidence <= 0.50
    assert "evidence_quote_missing_from_source" in missing.warnings

    try:
        event_source_enrichment.run_llm_source_triage(
            raw_event("bad-triage", "rss", "https://fixture.test/bad", "Bad", "unsupported"),
            provider=provider,
            cfg=cfg,
        )
    except ValueError as exc:
        assert "invalid LLM source page_type" in str(exc)
    else:
        raise AssertionError("invalid LLM source triage enum should fail validation")


def test_official_exchange_activation_schema_for_bybit_and_binance_fixture_artifacts():
    import json

    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
    import crypto_rsi_scanner.event_alpha.providers.official_exchange as event_official_exchange
    import crypto_rsi_scanner.event_alpha.providers.official_exchange_activation as event_official_exchange_activation
    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        event_official_exchange.run_official_exchange_scan(
            namespace_dir=base,
            provider_paths={
                "binance_announcements": "fixtures/event_discovery/official_exchange_binance_announcements.json",
                "bybit_announcements": "fixtures/event_discovery/official_exchange_bybit_announcements.json",
            },
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            run_mode="fixture",
            run_id="run-official-activation",
            observed_at="2026-06-15T16:00:00Z",
        )
        activation = event_official_exchange_activation.build_activation_report(
            namespace_dir=base,
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            observed_at="2026-06-15T16:00:00Z",
        )
        json_path, md_path = event_official_exchange_activation.write_activation_artifacts(activation, base)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        rows = {str(row.get("provider") or ""): row for row in payload["providers"]}

        assert set(event_official_exchange_activation.SHARED_SCHEMA_FIELDS) <= set(rows["bybit_announcements_public"])
        assert set(event_official_exchange_activation.SHARED_SCHEMA_FIELDS) <= set(rows["binance_announcements_public_or_fixture"])
        assert set(event_official_exchange_activation.SHARED_SCHEMA_FIELDS) <= set(rows["binance_announcements_signed_listener"])
        assert rows["bybit_announcements_public"]["mode"] == "public_http_no_key"
        assert rows["bybit_announcements_public"]["configured"] is True
        assert rows["bybit_announcements_public"]["provider_health_status"] == "fixture_ready"
        assert rows["bybit_announcements_public"]["official_events_written"] >= 1
        assert rows["binance_announcements_public_or_fixture"]["mode"] == "public_or_fixture_parser"
        assert rows["binance_announcements_public_or_fixture"]["configured"] is True
        assert rows["binance_announcements_public_or_fixture"]["live_call_allowed"] is False
        assert rows["binance_announcements_public_or_fixture"]["provider_health_status"] == "fixture_ready"
        assert rows["binance_announcements_public_or_fixture"]["official_events_written"] >= 1
        assert rows["binance_announcements_signed_listener"]["mode"] == "signed_websocket_listener"
        assert rows["binance_announcements_signed_listener"]["configured"] is False
        assert rows["binance_announcements_signed_listener"]["live_call_allowed"] is False
        assert rows["binance_announcements_signed_listener"]["skip_reason"] == "blocked_without_signed_listener_env"
        assert all(row["strict_alerts_created"] == 0 for row in rows.values())
        assert all(row["telegram_sends"] == 0 for row in rows.values())
        assert "Binance public/fixture second" in md_path.read_text(encoding="utf-8")

        coverage = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=event_provider_status.build_event_discovery_provider_status(config),
            provider_health_rows={},
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            artifact_namespace_dir=base,
        )
        coverage_text = event_alpha_source_coverage.format_source_coverage_report(coverage)
        official_pack = next(pack for pack in coverage.packs if pack.source_pack == "official_exchange_listing_pack")
        assert "bybit_announcements_public" in official_pack.healthy_providers
        assert "binance_announcements_public_or_fixture" in official_pack.healthy_providers
        assert "binance_announcements_signed_listener" in official_pack.missing_providers
        assert "bybit_announcements_public mode=public_http_no_key" in coverage_text
        assert "binance_announcements_public_or_fixture mode=public_or_fixture_parser" in coverage_text
        assert "binance_announcements_signed_listener mode=signed_websocket_listener" in coverage_text
        assert "binance_announcements_public_or_fixture" in coverage_text
        assert "Binance requires API key" not in coverage_text

        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor.official_exchange_activation_missing_shared_schema == 0
        assert doctor.official_exchange_activation_live_without_ledger == 0
        assert doctor.official_exchange_activation_signed_listener_secret_leak == 0
        assert doctor.official_exchange_activation_forbidden_side_effect_claim == 0


def test_event_alpha_consolidation_import_shims_and_schema_registry():
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as old_integrated_radar
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as old_market_anomaly
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
    from crypto_rsi_scanner.event_alpha.artifacts import paths as new_paths
    from crypto_rsi_scanner.event_alpha.doctor import schema_doctor
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar as new_integrated_radar
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner as new_market_anomaly
    from crypto_rsi_scanner.event_alpha.artifacts.paths import artifact_display_path

    assert new_integrated_radar.run_integrated_radar_cycle is old_integrated_radar.run_integrated_radar_cycle
    assert new_market_anomaly.scan_market_rows is old_market_anomaly.scan_market_rows
    assert new_paths.artifact_display_path is artifact_display_path
    required = {
        "core_opportunity_v1",
        "integrated_radar_candidate_v1",
        "notification_delivery_v1",
        "integrated_notification_delivery_v1",
        "source_coverage_v1",
        "provider_readiness_v1",
        "provider_preflight_v1",
        "coinalyze_request_ledger_v1",
        "derivatives_state_snapshot_v1",
        "derivatives_crowding_candidate_v1",
        "fade_review_candidate_v1",
        "market_state_snapshot_v1",
        "market_anomaly_v1",
        "official_exchange_event_v1",
        "scheduled_catalyst_event_v1",
        "unlock_event_v1",
        "outcome_row_v1",
        "calibration_prior_v1",
        "namespace_status_v1",
        "run_ledger_v1",
        "event_alpha_daily_burn_in_run_v1",
        "event_alpha_candidate_mode_manifest_v1",
        "event_alpha_daily_review_inbox_v1",
        "event_alpha_burn_in_scorecard_v1",
        "event_alpha_burn_in_measurement_dashboard_v1",
        "event_alpha_source_yield_report_v1",
        "event_alpha_burn_in_archive_manifest_v1",
        "event_alpha_burn_in_namespace_policy_v1",
    }
    assert required.issubset(schema_v1.SCHEMAS)
    assert schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION == "event_alpha_schema_v1"
    assert schema_doctor.check_registry_schema_dependency_errors() == ()


def test_event_alpha_schema_v1_validation_policy(tmp_path):
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    schema = schema_v1.get_schema("integrated_radar_candidate_v1")
    valid = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "iar:test",
        "symbol": "TEST",
        "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        "research_only": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
    }
    assert schema_v1.validate_row_against_schema(valid, schema) == []

    missing = dict(valid)
    missing.pop("candidate_id")
    assert "missing_required_field:candidate_id" in schema_v1.validate_row_against_schema(missing, schema)

    invalid_enum = dict(valid, opportunity_type="BUY_NOW")
    assert any(error.startswith("invalid_enum:opportunity_type") for error in schema_v1.validate_row_against_schema(invalid_enum, schema))

    leaked_secret = dict(valid, api_key="plain-text-provider-key")
    assert "secret_field_unredacted:api_key" in schema_v1.validate_row_against_schema(leaked_secret, schema)
    redacted_secret = dict(valid, api_key="<redacted>")
    assert "secret_field_unredacted:api_key" not in schema_v1.validate_row_against_schema(redacted_secret, schema)

    path_schema = schema_v1.get_schema("core_opportunity_v1")
    bad_path = {
        "row_type": "event_core_opportunity",
        "core_opportunity_id": "agg:test",
        "symbol": "TEST",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "research_card_path": "/tmp/local-card.md",
    }
    assert "absolute_non_debug_path:research_card_path" in schema_v1.validate_row_against_schema(bad_path, path_schema)
    debug_abs = dict(bad_path, research_card_path="event_fade_cache/unit/card.md", research_card_path_abs_debug="/tmp/local-card.md")
    assert "absolute_non_debug_path:research_card_path" not in schema_v1.validate_row_against_schema(debug_abs, path_schema)
    bad_dir = dict(bad_path, research_card_path="event_fade_cache/unit/card.md", research_cards_dir="/tmp/local-cards")
    assert "absolute_non_debug_path:research_cards_dir" in schema_v1.validate_row_against_schema(bad_dir, path_schema)

    live_delivery = {
        "row_type": "event_alpha_notification_delivery",
        "delivery_id": "delivery-live",
        "status": "sent",
        "delivery_mode": "live_send",
        "send_guard_enabled": True,
        "no_send_rehearsal": False,
        "delivered_count": 1,
        "sent": True,
    }
    delivery_schema = schema_v1.get_schema("notification_delivery_v1")
    assert schema_v1.validate_row_against_schema(live_delivery, delivery_schema) == []
    unsafe_rehearsal = dict(live_delivery, no_send_rehearsal=True)
    assert "unsafe_side_effect_flag:sent" in schema_v1.validate_row_against_schema(
        unsafe_rehearsal,
        delivery_schema,
    )
    for inconsistent_delivery in (
        {key: value for key, value in live_delivery.items() if key != "delivered_count"},
        dict(live_delivery, delivered_count=0),
        {key: value for key, value in live_delivery.items() if key != "no_send_rehearsal"},
    ):
        assert "unsafe_side_effect_flag:sent" in schema_v1.validate_row_against_schema(
            inconsistent_delivery,
            delivery_schema,
        )
    unsafe_integrated = {
        "row_type": "event_integrated_radar_notification_delivery",
        "lane": "research_review_digest",
        "sent": True,
        "no_send_rehearsal": False,
    }
    assert "unsafe_side_effect_flag:sent" in schema_v1.validate_row_against_schema(
        unsafe_integrated,
        schema_v1.get_schema("integrated_notification_delivery_v1"),
    )

    guarded_run = {
        "row_type": "event_alpha_run",
        "run_id": "run-live",
        "profile": "notify_no_key",
        "send_requested": True,
        "send_attempted": True,
        "send_success": True,
        "send_items_delivered": 2,
        "sent": True,
    }
    assert schema_v1.validate_row_against_schema(
        guarded_run,
        schema_v1.get_schema("run_ledger_v1"),
    ) == []
    assert schema_v1.validate_row_against_schema(
        dict(guarded_run, send_success=False, send_items_delivered=1),
        schema_v1.get_schema("run_ledger_v1"),
    ) == []
    inconsistent_run = dict(guarded_run, send_items_delivered=0)
    assert "unsafe_side_effect_flag:sent" in schema_v1.validate_row_against_schema(
        inconsistent_run,
        schema_v1.get_schema("run_ledger_v1"),
    )

    legacy_path = tmp_path / "event_integrated_radar_candidates.jsonl"
    legacy_path.write_text(json.dumps(valid, sort_keys=True) + "\n", encoding="utf-8")
    result = schema_v1.validate_artifact_file(legacy_path)
    assert result["schema_id"] == "integrated_radar_candidate_v1"
    assert result["inferred_schema_id"] == "integrated_radar_candidate_v1"
    assert result["rows_validated"] == 1
    assert result["errors"] == []

    crowding_path = tmp_path / "event_derivatives_crowding_candidates.jsonl"
    shared_api_row_type = {
        "row_type": "fade_short_review_candidate",
        "symbol": "TESTFADE",
        "crowding_class": "extreme",
    }
    crowding_path.write_text(json.dumps(shared_api_row_type, sort_keys=True) + "\n", encoding="utf-8")
    crowding_result = schema_v1.validate_artifact_file(crowding_path)
    assert crowding_result["schema_id"] == "derivatives_crowding_candidate_v1"
    assert crowding_result["rows_validated"] == 1
    assert crowding_result["errors"] == []

    stamped = schema_v1.stamp_artifact_row(valid, path=legacy_path)
    assert stamped["schema_id"] == "integrated_radar_candidate_v1"
    assert stamped["schema_version"] == schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION

    core_stamped = schema_v1.stamp_artifact_row(
        {
            "row_type": "event_core_opportunity",
            "core_opportunity_id": "core:test",
            "symbol": "TEST",
            "opportunity_type": "UNCONFIRMED_RESEARCH",
            "schema_version": "event_core_opportunity_store_v1",
        },
        path=tmp_path / "event_core_opportunities.jsonl",
    )
    assert core_stamped["schema_id"] == "core_opportunity_v1"
    assert core_stamped["schema_version"] == "event_core_opportunity_store_v1"


def test_event_alpha_burn_in_operation_schemas_validate(tmp_path):
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    safety = {
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
    }
    payloads = {
        "event_alpha_daily_burn_in_run.json": {
            "row_type": "event_alpha_daily_burn_in_run",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "burn",
            "completed": True,
            "steps": [{"name": "doctor", "status": "passed", "timeout_seconds": 60}],
            **safety,
        },
        "event_alpha_candidate_mode_manifest.json": {
            "row_type": "event_alpha_candidate_mode_manifest",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "burn",
            "candidate_mode": True,
            "providers": {},
            **safety,
        },
        "event_alpha_daily_review_inbox.json": {
            "row_type": "event_alpha_daily_review_inbox",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "burn",
            "items": [],
            **safety,
        },
        "event_alpha_burn_in_scorecard.json": {
            "row_type": "event_alpha_burn_in_scorecard",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "burn",
            "evidence_scope": "active_burn_in_no_candidate_evidence",
            "auto_apply": False,
            **safety,
        },
        "event_alpha_burn_in_measurement_dashboard.json": {
            "row_type": "event_alpha_burn_in_measurement_dashboard",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "burn",
            "evidence_scope": "active_burn_in_no_candidate_evidence",
            "auto_apply_thresholds": False,
            **safety,
        },
        "event_alpha_source_yield_report.json": {
            "row_type": "event_alpha_source_yield_report",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "burn",
            "evidence_scope": "active_burn_in_no_candidate_evidence",
            "auto_apply": False,
            **safety,
        },
        "event_alpha_burn_in_archive_manifest.json": {
            "row_type": "event_alpha_burn_in_archive_manifest",
            "dry_run": True,
            "archive_scope": "active_burn_in_namespaces",
            "archive_path": "research/archive.zip",
            **safety,
        },
        "event_alpha_burn_in_namespace_policy.json": {
            "row_type": "event_alpha_burn_in_namespace_policy",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "burn",
            "namespace_policy_version": "burn_in_namespace_policy_v3",
            **safety,
        },
    }
    for filename, payload in payloads.items():
        path = tmp_path / filename
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        result = schema_v1.validate_artifact_file(path)
        assert result["rows_validated"] == 1
        assert result["errors"] == []

    bad = dict(payloads["event_alpha_burn_in_archive_manifest.json"], archive_path="/tmp/archive.zip")
    bad_path = tmp_path / "event_alpha_burn_in_archive_manifest.json"
    bad_path.write_text(json.dumps(bad, sort_keys=True) + "\n", encoding="utf-8")
    result = schema_v1.validate_artifact_file(bad_path)
    assert any(error["error"] == "absolute_non_debug_path:archive_path" for error in result["errors"])

    unsafe = dict(payloads["event_alpha_burn_in_scorecard.json"], normal_rsi_signal_rows_written=1)
    unsafe_path = tmp_path / "event_alpha_burn_in_scorecard.json"
    unsafe_path.write_text(json.dumps(unsafe, sort_keys=True) + "\n", encoding="utf-8")
    result = schema_v1.validate_artifact_file(unsafe_path)
    assert any(error["error"] == "unsafe_side_effect_count:normal_rsi_signal_rows_written" for error in result["errors"])


def test_medium_event_alpha_and_provider_packages_preserve_imports_and_hygiene():
    from crypto_rsi_scanner.event_alpha.radar import discovery, near_miss, validation, watchlist
    from crypto_rsi_scanner.event_alpha.radar.discovery.loader import load_discovery_events
    from crypto_rsi_scanner.event_alpha.radar.discovery.manual import run_manual_discovery
    from crypto_rsi_scanner.event_alpha.radar.near_miss.models import EventNearMissCandidate
    from crypto_rsi_scanner.event_alpha.radar.validation.models import EventFadeValidationReview
    from crypto_rsi_scanner.event_alpha.radar.watchlist.entries import (
        _entry_from_alert,
        _entry_from_hypothesis,
        _entry_from_row,
    )
    from crypto_rsi_scanner.event_alpha.radar.watchlist.models import EventWatchlistEntry
    from crypto_rsi_scanner.event_alpha.radar.asset_registry import CanonicalAsset
    from crypto_rsi_scanner.event_alpha.radar.canonical_asset import CanonicalAsset as NewCanonicalAsset
    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider
    from crypto_rsi_scanner.event_providers.binance_announcements.provider import (
        BinanceAnnouncementProvider as NewBinanceAnnouncementProvider,
    )
    from crypto_rsi_scanner.event_providers.bybit_announcements import BybitAnnouncementProvider
    from crypto_rsi_scanner.event_providers.bybit_announcements.provider import (
        BybitAnnouncementProvider as NewBybitAnnouncementProvider,
    )
    from crypto_rsi_scanner.event_providers.cryptopanic import (
        CryptoPanicProvider,
        GROWTH_WEEKLY_UNSUPPORTED_PARAMS,
        redact_cryptopanic_url,
    )
    from crypto_rsi_scanner.event_providers.cryptopanic.parser import plan_cryptopanic_currency_codes
    from crypto_rsi_scanner.event_providers.cryptopanic.provider import (
        CryptoPanicProvider as NewCryptoPanicProvider,
    )
    from crypto_rsi_scanner.event_providers.cryptopanic.request_ledger import _safe_body_excerpt
    from crypto_rsi_scanner.derivatives_providers.coinalyze import CoinalyzeDerivativesProvider
    from crypto_rsi_scanner.derivatives_providers.coinalyze.parser import resolve_future_market_symbols
    from crypto_rsi_scanner.derivatives_providers.coinalyze.provider import (
        CoinalyzeDerivativesProvider as NewCoinalyzeDerivativesProvider,
    )
    from crypto_rsi_scanner.event_alpha.providers import provider_health
    from crypto_rsi_scanner.event_alpha.providers.health.derivatives_provider import (
        HealthCheckedDerivativesProvider,
    )
    from crypto_rsi_scanner.event_alpha.providers.health.event_provider import HealthCheckedEventProvider
    from crypto_rsi_scanner.event_alpha.providers.health.universe_provider import HealthCheckedUniverseProvider
    from crypto_rsi_scanner.llm_providers.openai_extraction import (
        OpenAILLMExtractionProvider as NewOpenAILLMExtractionProvider,
    )
    from crypto_rsi_scanner.llm_providers.openai_provider import (
        OpenAILLMExtractionProvider,
        OpenAILLMRelationshipProvider,
    )
    from crypto_rsi_scanner.llm_providers.openai_relationship import (
        OpenAILLMRelationshipProvider as NewOpenAILLMRelationshipProvider,
    )

    assert validation.EventFadeValidationReview is EventFadeValidationReview
    assert callable(run_manual_discovery)
    assert callable(discovery.run_manual_discovery)
    assert discovery.load_discovery_events is load_discovery_events
    assert watchlist.EventWatchlistEntry is EventWatchlistEntry
    assert watchlist._entry_from_alert is _entry_from_alert
    assert watchlist._entry_from_hypothesis is _entry_from_hypothesis
    assert watchlist._entry_from_row is _entry_from_row
    assert near_miss.EventNearMissCandidate is EventNearMissCandidate
    assert CryptoPanicProvider is NewCryptoPanicProvider
    assert CoinalyzeDerivativesProvider is NewCoinalyzeDerivativesProvider
    assert BybitAnnouncementProvider is NewBybitAnnouncementProvider
    assert BinanceAnnouncementProvider is NewBinanceAnnouncementProvider
    assert CanonicalAsset is NewCanonicalAsset
    assert OpenAILLMRelationshipProvider is NewOpenAILLMRelationshipProvider
    assert OpenAILLMExtractionProvider is NewOpenAILLMExtractionProvider
    assert provider_health.HealthCheckedEventProvider is HealthCheckedEventProvider
    assert provider_health.HealthCheckedUniverseProvider is HealthCheckedUniverseProvider
    assert provider_health.HealthCheckedDerivativesProvider is HealthCheckedDerivativesProvider

    assert "search" in GROWTH_WEEKLY_UNSUPPORTED_PARAMS
    planned = plan_cryptopanic_currency_codes(
        [
            {"symbol": "BTC", "identity_validated": True},
            {"symbol": "BTC", "identity_validated": True},
            {"symbol": "REAL", "identity_validated": False},
        ]
    )
    assert planned.accepted == ("BTC",)
    assert any(row["reason"] == "duplicate_request" for row in planned.rejected)
    assert any(row["reason"] == "ticker_collision" for row in planned.rejected)
    redacted_url = redact_cryptopanic_url("https://example.test/posts/?auth_token=super-secret-token&currencies=BTC")
    assert "super-secret-token" not in redacted_url
    assert "auth_token=%3Credacted%3E" in redacted_url
    excerpt = _safe_body_excerpt("failure auth_token=super-secret-token api_token: abcdefghijklmnop1234")
    assert "super-secret-token" not in str(excerpt)
    assert "abcdefghijklmnop1234" not in str(excerpt)
    assert CoinalyzeDerivativesProvider(None, live_enabled=False).fetch_snapshots() == {}
    assert resolve_future_market_symbols([], ["BTC"]) == ()


def test_event_alpha_cli_package_and_make_targets_are_available():
    from crypto_rsi_scanner.cli.dispatch import dispatch_command_name
    from crypto_rsi_scanner.cli.parser import build_parser, command_group, dispatch_key_from_args
    from crypto_rsi_scanner.cli.main import main as cli_main

    root = _event_alpha_api_helpers.REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert callable(cli_main)
    parser = build_parser()
    default_args = parser.parse_args([])
    assert default_args.top_n is None
    assert default_args.dry_run is False
    assert dispatch_key_from_args(default_args) == "run_scan"
    preview_args = parser.parse_args(["--event-alpha-notify-preview", "--event-alpha-profile", "notify_no_key"])
    assert preview_args.event_alpha_notify_preview is True
    assert preview_args.event_alpha_profile == "notify_no_key"
    assert dispatch_key_from_args(preview_args) == "event_alpha_notify_preview"
    assert dispatch_command_name(["--event-alpha-integrated-radar-smoke"]) == "event_alpha_integrated_radar_smoke"
    assert dispatch_command_name(["--event-alpha-artifact-doctor"]) == "event_alpha_artifact_doctor"
    assert command_group(["-m", "crypto_rsi_scanner.backtest"]) == "backtest"
    assert command_group(["--event-alpha-live-provider-readiness"]) == "event_alpha_provider_readiness"
    assert command_group(["--event-alpha-coinalyze-no-send-rehearsal"]) == "event_alpha_coinalyze"
    assert command_group(["--event-alpha-bybit-announcements-preflight"]) == "event_alpha_official_exchange"
    assert dispatch_command_name(["--event-alpha-namespace-lifecycle-report"]) == "event_alpha_namespace_lifecycle_report"
    assert "test-pytest:" in makefile
    assert "test-pytest-safe:" in makefile
    assert "test-pytest-timed:" in makefile
    assert "test-pytest-durations:" in makefile
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in makefile
    assert "PYTEST_PATHS ?= tests/event_alpha tests/rsi tests/cli tests/test_indicators.py" in makefile
    assert "test-pytest-parallel:" in makefile
    assert "-p xdist.plugin" in makefile
    assert "event-alpha-namespace-lifecycle-report:" in makefile
    assert "event-alpha-list-active-namespaces:" in makefile
    assert "event-alpha-archive-stale-namespaces:" in makefile
