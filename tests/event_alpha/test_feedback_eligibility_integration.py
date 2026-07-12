"""Producer, loader, schema, and doctor integration for feedback eligibility."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.doctor import artifact_doctor
from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts import feedback_checks
from crypto_rsi_scanner.event_alpha.outcomes import feedback_eligibility
from crypto_rsi_scanner.event_alpha.outcomes import feedback_labels


EVALUATED_AT = datetime(2026, 7, 12, 2, 0, tzinfo=timezone.utc)


def _core_row(*, core_id: str = "core:btc:listing", **overrides):
    row = {
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "row_type": "event_core_opportunity",
        "run_id": "run-1",
        "profile": "live_burn_in_no_send",
        "run_mode": "burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": core_id,
        "feedback_target": core_id,
        "feedback_target_type": "core_opportunity_id",
        "generated_at": "2026-07-12T00:00:00+00:00",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "source_provider": "official_exchange",
        "source_pack": "listing",
    }
    row.update(overrides)
    return row


def _feedback_row(*, core_id: str = "core:btc:listing", **overrides):
    row = {
        "schema_id": "feedback_row_v1",
        "schema_version": "event_alpha_feedback_v1",
        "row_type": "event_alpha_feedback",
        "run_id": "run-1",
        "profile": "live_burn_in_no_send",
        "run_mode": "burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": core_id,
        "feedback_id": "feedback-1",
        "feedback_target_type": "core_opportunity_id",
        "feedback_target": core_id,
        "target": core_id,
        "label": "useful",
        "marked_at": "2026-07-12T01:00:00+00:00",
        "marked_by": "human",
        "source": "manual_cli",
        "research_only": True,
    }
    row.update(overrides)
    row.update(feedback_eligibility.build_feedback_eligibility_fields(row))
    return row


def test_feedback_producer_persists_exact_core_contract_and_loader_preserves_it(
    tmp_path: Path,
):
    path = tmp_path / "event_alpha_feedback.jsonl"
    core = _core_row()
    record = feedback_labels.mark_feedback(
        "alert:btc",
        "useful",
        cfg=feedback_labels.EventFeedbackConfig(path),
        context_rows=[
            {
                "row_type": "event_alpha_alert_snapshot",
                "alert_id": "alert:btc",
                "core_opportunity_id": core["core_opportunity_id"],
                "source_provider": "untrusted-alert-alias",
            }
        ],
        core_opportunity_rows=[core],
        now=datetime(2026, 7, 12, 1, 0, tzinfo=timezone.utc),
    )

    assert record.target == core["core_opportunity_id"]
    assert record.feedback_target == core["core_opportunity_id"]
    assert record.feedback_target_type == "core_opportunity_id"
    assert record.run_id == core["run_id"]
    assert record.run_mode == core["run_mode"]
    assert record.profile == core["profile"]
    assert record.artifact_namespace == core["artifact_namespace"]
    assert record.source == "manual_cli"
    assert record.calibration_eligible is True
    assert record.calibration_ineligible_reasons == []
    assert feedback_eligibility.validate_contract(record.__dict__) == []

    loaded = feedback_labels.load_feedback(path)
    assert loaded.rows_read == 1
    assert loaded.diagnostics.accepted_rows == 1
    assert loaded.records[0].feedback_identity == record.feedback_identity
    assert loaded.records[0].feedback_identity_key == record.feedback_identity_key
    assert loaded.records[0].calibration_eligible is True
    validation = schema_v1.validate_artifact_file(path)
    assert validation["schema_id"] == "feedback_row_v1"
    assert validation["rows_validated"] == 1
    assert validation["errors"] == []


def test_calendar_risk_feedback_preserves_minimal_core_calendar_evidence(
    tmp_path: Path,
):
    from crypto_rsi_scanner.event_alpha.radar import decision_model

    calendar_event = {
        "calendar_event_id": "macro:fomc:2026-07-12",
        "event_kind": "macro_release",
        "importance": "high",
        "scheduled_at": "2026-07-12T03:00:00Z",
        "title": "Sensitive operator-facing title is not feedback evidence",
        "source_url": "https://calendar.example.test/fomc",
    }
    decision = decision_model.evaluate_radar_decision(
        {
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "canonical_asset_id": "bitcoin",
            "instrument_resolver_status": "resolved",
            "instrument_resolver_confidence": 0.95,
            "instrument_identity_trusted": True,
            "is_tradable_asset": True,
            "market_state_class": "risk_off_sell_pressure",
            "market_anomaly_bucket": "selloff_risk",
            "market_state_snapshot": {
                "return_unit": "percent_points",
                "return_4h": -8.0,
                "return_24h": -15.0,
                "volume_zscore_24h": 3.0,
                "volume_to_market_cap": 0.25,
                "liquidity_usd": 10_000_000,
                "spread_bps": 20.0,
                "freshness_status": "fresh",
            },
            "nearby_calendar_events": [calendar_event],
            "observed_at": "2026-07-12T00:00:00+00:00",
            "research_only": True,
        }
    ).to_dict()
    assert decision["radar_route"] == "calendar_risk"

    core = _core_row(
        research_only=True,
        nearby_calendar_events=[calendar_event],
        **decision,
    )
    path = tmp_path / "event_alpha_feedback.jsonl"
    record = feedback_labels.mark_feedback(
        core["core_opportunity_id"],
        "watch",
        cfg=feedback_labels.EventFeedbackConfig(path),
        context_rows=[
            {
                **core,
                "row_type": "event_alpha_alert_snapshot",
                # Core is the canonical calendar authority for the final row.
                "nearby_calendar_events": [],
            }
        ],
        core_opportunity_rows=[core],
        now=datetime(2026, 7, 12, 1, 0, tzinfo=timezone.utc),
    )

    assert record.radar_route == "calendar_risk"
    assert record.scheduled_at == "2026-07-12T03:00:00+00:00"
    assert record.nearby_calendar_events == (
        {
            "calendar_event_id": "macro:fomc:2026-07-12",
            "event_kind": "macro_release",
            "importance": "high",
            "scheduled_at": "2026-07-12T03:00:00+00:00",
        },
    )
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert schema_v1.validate_row_against_schema(
        persisted, "feedback_row_v1"
    ) == []
    assert "title" not in persisted["nearby_calendar_events"][0]
    assert "source_url" not in persisted["nearby_calendar_events"][0]
    loaded = feedback_labels.load_feedback(path).records[0]
    assert loaded.scheduled_at == record.scheduled_at
    assert loaded.nearby_calendar_events == record.nearby_calendar_events


def test_unmatched_and_legacy_feedback_remain_readable_but_ineligible(tmp_path: Path):
    unmatched_path = tmp_path / "unmatched" / "event_alpha_feedback.jsonl"
    record = feedback_labels.mark_feedback(
        "UNKNOWN",
        "useful",
        cfg=feedback_labels.EventFeedbackConfig(unmatched_path),
        allow_unmatched=True,
        now=datetime(2026, 7, 12, 1, 0, tzinfo=timezone.utc),
    )
    assert record.source == "manual_cli_unmatched"
    assert record.calibration_eligible is False
    assert "missing_exact_feedback_identity" in record.calibration_ineligible_reasons
    assert "invalid_feedback_source" in record.calibration_ineligible_reasons
    assert feedback_labels.load_feedback(unmatched_path).records[0].target == "UNKNOWN"

    legacy_path = tmp_path / "legacy" / "event_alpha_feedback.jsonl"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        json.dumps(
            {
                "row_type": "event_alpha_feedback",
                "target": "legacy-target",
                "label": "watch",
                "marked_at": "2026-07-12T01:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    legacy = feedback_labels.load_feedback(legacy_path)
    assert legacy.rows_read == 1
    assert legacy.records[0].target == "legacy-target"
    assert legacy.records[0].calibration_eligible is None
    assert schema_v1.validate_artifact_file(legacy_path)["errors"] == []


@pytest.mark.parametrize(
    "missing_field",
    ("feedback_id", "marked_by", "source", "research_only", "target"),
)
def test_feedback_loader_never_synthesizes_missing_exact_contract_fields(
    tmp_path: Path,
    missing_field: str,
):
    row = _feedback_row()
    row.pop(missing_field)
    path = tmp_path / f"missing-{missing_field}.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    loaded = feedback_labels.load_feedback(path)

    assert loaded.rows_read == 1
    record = loaded.records[0]
    assert getattr(record, missing_field) is None
    assert record.calibration_eligible is False
    assert "partial_feedback_contract" in record.calibration_ineligible_reasons
    eligible, excluded, _reasons = (
        feedback_eligibility.partition_joined_calibration_feedback(
            [record.__dict__],
            [_core_row()],
            now=EVALUATED_AT,
        )
    )
    assert eligible == ()
    assert len(excluded) == 1


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("feedback_id", 7),
        ("marked_by", {"role": "human"}),
        ("source", ["manual_cli"]),
        ("research_only", 1),
        ("target", ["core:btc:listing"]),
        ("run_id", 7),
        ("profile", {"invalid": True}),
        ("artifact_namespace", ["invalid"]),
        ("core_opportunity_id", 7),
        ("feedback_target", ["core:btc:listing"]),
        ("feedback_target_type", 7),
        ("label", {"invalid": True}),
        ("marked_at", ["2026-07-12T01:00:00+00:00"]),
        ("feedback_eligibility_contract_version", "1"),
        ("feedback_identity", ["invalid"]),
        ("feedback_identity_key", 7),
    ),
)
def test_feedback_loader_preserves_invalid_exact_values_as_ineligible_evidence(
    tmp_path: Path,
    field_name: str,
    invalid_value: object,
):
    row = _feedback_row()
    row[field_name] = invalid_value
    path = tmp_path / f"invalid-{field_name}.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    loaded = feedback_labels.load_feedback(path)

    assert loaded.rows_read == 1
    record = loaded.records[0]
    assert getattr(record, field_name) == invalid_value
    assert record.calibration_eligible is False
    eligible, excluded, _reasons = (
        feedback_eligibility.partition_joined_calibration_feedback(
            [record.__dict__],
            [_core_row()],
            now=EVALUATED_AT,
        )
    )
    assert eligible == ()
    assert len(excluded) == 1


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("calibration_eligible", 1),
        ("calibration_ineligible_reasons", {"forged": True}),
    ),
)
def test_feedback_loader_materializes_invalid_persisted_eligibility_markers_as_false(
    tmp_path: Path,
    field_name: str,
    invalid_value: object,
):
    row = _feedback_row()
    row[field_name] = invalid_value
    path = tmp_path / f"invalid-{field_name}.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    record = feedback_labels.load_feedback(path).records[0]

    assert record.calibration_eligible is False
    assert record.calibration_ineligible_reasons
    eligible, excluded, _reasons = (
        feedback_eligibility.partition_joined_calibration_feedback(
            [record.__dict__],
            [_core_row()],
            now=EVALUATED_AT,
        )
    )
    assert eligible == ()
    assert len(excluded) == 1


@pytest.mark.parametrize(
    ("unsafe_field", "unsafe_value"),
    (
        ("trade_created", True),
        ("telegram_sends", 1),
        ("decision_source_secret_safety_failed", True),
        ("decision_source_path_safety_failed", True),
    ),
)
def test_feedback_loader_never_upgrades_unsafe_flags(
    tmp_path: Path,
    unsafe_field: str,
    unsafe_value: object,
):
    row = _feedback_row()
    row[unsafe_field] = unsafe_value
    path = tmp_path / f"unsafe-{unsafe_field}.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    loaded = feedback_labels.load_feedback(path)

    assert loaded.rows_read == 1
    record = loaded.records[0]
    assert record.calibration_eligible is False
    assert "feedback_safety_contract_invalid" in record.calibration_ineligible_reasons
    eligible, excluded, _reasons = (
        feedback_eligibility.partition_joined_calibration_feedback(
            [record.__dict__],
            [_core_row()],
            now=EVALUATED_AT,
        )
    )
    assert eligible == ()
    assert len(excluded) == 1


def test_feedback_loader_keeps_malformed_rows_reportable_without_leaking_notes(
    tmp_path: Path,
):
    row = _feedback_row()
    row.update(
        {
            "feedback_id": {"invalid": True},
            "target": ["invalid-target"],
            "marked_at": {"invalid": True},
            "marked_by": ["invalid-reviewer"],
            "notes": "api_key=actual-secret-value",
        }
    )
    path = tmp_path / "malformed-feedback.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    loaded = feedback_labels.load_feedback(path)
    report = feedback_labels.format_feedback_report(loaded)

    assert loaded.rows_read == 1
    assert "[invalid list]" in report
    assert "[invalid dict]" in report
    assert "notes: [invalid or redacted]" in report
    assert "actual-secret-value" not in report


def test_feedback_and_outcome_schema_registration_covers_persisted_contracts():
    feedback_schema = schema_v1.get_schema("feedback_row_v1")
    record_fields = set(feedback_labels.EventFeedbackRecord.__dataclass_fields__)

    assert record_fields <= feedback_schema.declared_fields
    assert record_fields <= set(feedback_schema.field_types)
    assert schema_v1.infer_schema_id_for_file("event_alpha_outcomes.jsonl") == "outcome_row_v1"


def test_feedback_producer_rejects_ambiguous_core_authority(tmp_path: Path):
    core = _core_row()
    with pytest.raises(ValueError, match="multiple canonical core authorities"):
        feedback_labels.mark_feedback(
            core["core_opportunity_id"],
            "watch",
            cfg=feedback_labels.EventFeedbackConfig(tmp_path / "event_alpha_feedback.jsonl"),
            core_opportunity_rows=[core, copy.deepcopy(core)],
            now=datetime(2026, 7, 12, 1, 0, tzinfo=timezone.utc),
        )

    second = _core_row(core_id="core:eth:listing", symbol="ETH", coin_id="ethereum")
    with pytest.raises(ValueError, match="multiple canonical core authorities"):
        feedback_labels.mark_feedback(
            "shared-alert-alias",
            "watch",
            cfg=feedback_labels.EventFeedbackConfig(tmp_path / "event_alpha_feedback.jsonl"),
            context_rows=[
                {
                    "alert_id": "shared-alert-alias",
                    "core_opportunity_id": core["core_opportunity_id"],
                },
                {
                    "alert_id": "shared-alert-alias",
                    "core_opportunity_id": second["core_opportunity_id"],
                },
            ],
            core_opportunity_rows=[core, second],
            now=datetime(2026, 7, 12, 1, 0, tzinfo=timezone.utc),
        )


def test_feedback_producer_rejects_secret_bearing_notes_before_write(tmp_path: Path):
    path = tmp_path / "event_alpha_feedback.jsonl"
    core = _core_row()
    with pytest.raises(ValueError, match="without credential values"):
        feedback_labels.mark_feedback(
            core["core_opportunity_id"],
            "useful",
            cfg=feedback_labels.EventFeedbackConfig(path),
            core_opportunity_rows=[core],
            notes="api_key=actual-secret-value",
            now=datetime(2026, 7, 12, 1, 0, tzinfo=timezone.utc),
        )
    assert not path.exists()


def test_feedback_loader_and_schema_reject_duplicate_json_keys(tmp_path: Path):
    path = tmp_path / "event_alpha_feedback.jsonl"
    path.write_text(
        json.dumps(_feedback_row())
        + "\n"
        + '{"row_type":"event_alpha_feedback","target":"trusted","target":"forged","label":"junk","marked_at":"2026-07-12T01:00:00+00:00"}\n',
        encoding="utf-8",
    )
    loaded = feedback_labels.load_feedback(path)
    assert loaded.rows_read == 1
    assert loaded.diagnostics.duplicate_key_lines == (2,)
    assert schema_v1.validate_artifact_file(path)["rows_validated"] == 1


def test_feedback_doctor_reports_partition_and_integrity_telemetry(tmp_path: Path):
    core = _core_row()
    duplicated = _feedback_row()
    duplicate_summary = feedback_checks.summarize_feedback_eligibility(
        [duplicated, copy.deepcopy(duplicated)],
        [core],
        evaluated_at=EVALUATED_AT,
    )
    assert duplicate_summary["feedback_rows_supplied"] == 2
    assert duplicate_summary["feedback_rows_eligible"] == 0
    assert duplicate_summary["feedback_rows_excluded"] == 2
    assert duplicate_summary["feedback_duplicate_rows"] == 2
    assert duplicate_summary["feedback_persisted_eligible_invalid"] == 2

    missing_core = feedback_checks.summarize_feedback_eligibility(
        [_feedback_row()],
        [],
        evaluated_at=EVALUATED_AT,
    )
    assert missing_core["feedback_missing_core_rows"] == 1
    future = feedback_checks.summarize_feedback_eligibility(
        [_feedback_row(marked_at="2999-01-01T00:00:00+00:00")],
        [core],
        evaluated_at=EVALUATED_AT,
    )
    assert future["feedback_future_rows"] == 1
    assert future["feedback_duplicate_rows"] == 0
    before_core = feedback_checks.summarize_feedback_eligibility(
        [_feedback_row(marked_at="2026-07-11T23:00:00+00:00")],
        [core],
        evaluated_at=EVALUATED_AT,
    )
    assert before_core["feedback_unsafe_rows"] == 1
    assert before_core["feedback_duplicate_rows"] == 0
    unsafe = feedback_checks.summarize_feedback_eligibility(
        [_feedback_row(trade_created=True)],
        [core],
        evaluated_at=EVALUATED_AT,
    )
    assert unsafe["feedback_unsafe_rows"] == 1

    namespace = tmp_path / "doctor"
    namespace.mkdir()
    feedback_path = namespace / "event_alpha_feedback.jsonl"
    feedback_path.write_text(
        json.dumps(_feedback_row())
        + "\n"
        + '{"feedback_id":"trusted","feedback_id":"forged"}\n',
        encoding="utf-8",
    )
    result = artifact_doctor.diagnose_artifacts(
        core_opportunity_rows=[core],
        profile=core["profile"],
        artifact_namespace=core["artifact_namespace"],
        inspected_alert_store_path=namespace / "event_alpha_alerts.jsonl",
        strict=True,
        evaluated_at=EVALUATED_AT,
    )
    assert result.feedback_rows_supplied == 1
    assert result.feedback_rows_eligible == 1
    assert result.feedback_rows_excluded == 0
    assert result.feedback_duplicate_json_keys == 1
    assert any(
        "outcomes.feedback_eligibility_firewall: feedback_duplicate_json_keys=1"
        in blocker
        for blocker in result.blockers
    )
    report = artifact_doctor.format_artifact_doctor_report(result)
    assert "feedback eligibility: supplied=1 eligible=1 excluded=0" in report
