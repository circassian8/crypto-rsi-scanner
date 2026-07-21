"""Exact, explicit human-review timing for Decision Radar ideas."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from crypto_rsi_scanner.event_alpha.operations import decision_review_timing as timing
from crypto_rsi_scanner.event_alpha.operations import (
    decision_review_card_inspection as card_inspection,
)
from crypto_rsi_scanner.event_alpha.operations import decision_review_timing_cli
from crypto_rsi_scanner.event_alpha.operations import (
    decision_review_timing_queue as timing_queue,
)
from crypto_rsi_scanner.event_alpha.operations import (
    market_observation_campaign as campaign,
)
from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign_render
from crypto_rsi_scanner.event_alpha.artifacts import fingerprints


REPO_ROOT = Path(__file__).resolve().parents[2]


def _binding(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "artifact_namespace": "radar_market_no_send_exact",
        "run_id": "2026-07-18T12:00:00+00:00|no_key_live",
        "profile": "no_key_live",
        "revision": 12,
        "operator_state_sha256": "1" * 64,
        "idea_id": "iar:exact-idea",
        "core_opportunity_id": "agg:exact-idea",
        "decision_projection_sha256": "2" * 64,
        "integrated_candidates_sha256": "3" * 64,
        "core_opportunities_sha256": "4" * 64,
        "publication_receipt_sha256": "5" * 64,
        "operations_receipt_sha256": "6" * 64,
        "idea_observed_at": "2026-07-18T12:00:00+00:00",
        "idea_available_at": "2026-07-18T12:00:05+00:00",
        "pipeline_latency_seconds": 5.0,
        "radar_route": "dashboard_watch",
        "primary_thesis_origin": "market_led",
        "directional_bias": "long",
        "decision_radar_campaign_counted": True,
    }
    value.update(overrides)
    return value


def _operator_context(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_id": "decision_radar.idea_review_operator_context",
        "schema_version": 2,
        "canonical_asset_id": "exact-asset",
        "symbol": "EXACT",
        "anomaly_type": "stealth_accumulation",
        "catalyst_status": "unknown",
        "confidence_band": "exploratory",
        "market_phase": "emerging",
        "timing_state": "early",
        "preferred_horizon": "3d_7d",
        "expires_at": "2026-07-19T12:00:00+00:00",
        "radar_actionable": False,
        "actionability_score": 62.5,
        "evidence_confidence_score": 52.0,
        "risk_score": 48.0,
        "urgency_score": 45.0,
        "candidate_identity_bound_by": "integrated_candidates_sha256",
        "decision_values_bound_by": "decision_projection_sha256",
        "presentation_only": True,
    }
    value.update(overrides)
    return value


def _base(tmp_path: Path) -> Path:
    base = tmp_path / "artifacts"
    (base / timing.LEDGER_DIRECTORY).mkdir(parents=True)
    return base


def test_event_binds_exact_idea_and_explicit_clock_without_policy_effect() -> None:
    event = timing.build_review_timing_event(
        _binding(),
        event_type="first_viewed",
        reviewer_alias="owner",
        recorded_at="2026-07-18T12:00:10+00:00",
    )

    assert timing.validate_review_timing_event(event) == ()
    assert event["event_id"].startswith("decision-review-timing-v1:")
    assert event["explicit_human_action"] is True
    assert event["clock_source"] == "host_utc_clock_at_explicit_confirmed_command"
    assert event["protocol_v2_evidence_eligible"] is False
    assert event["automatic_policy_effect"] == "none"
    assert all(value == 0 for value in event["safety"].values())

    drifted = dict(event)
    drifted["idea_id"] = "iar:different"
    assert "event_id_binding_mismatch" in timing.validate_review_timing_event(drifted)

    non_json = dict(event)
    non_json["artifact_namespace"] = object()
    errors = timing.validate_review_timing_event(non_json)
    assert "event_id_binding_value_invalid" in errors
    assert "event_not_canonical_json_value" in errors


def test_confirmed_ledger_enforces_first_view_then_completion_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _base(tmp_path)
    monkeypatch.setattr(timing, "load_idea_binding", lambda *_args: _binding())

    with pytest.raises(PermissionError, match="confirmation_required"):
        timing.record_review_timing_event(
            base,
            artifact_namespace="radar_market_no_send_exact",
            idea_id="iar:exact-idea",
            event_type="first_viewed",
            reviewer_alias="owner",
            confirm=False,
        )
    with pytest.raises(timing.DecisionReviewTimingError, match="completion_without"):
        timing.record_review_timing_event(
            base,
            artifact_namespace="radar_market_no_send_exact",
            idea_id="iar:exact-idea",
            event_type="review_completed",
            reviewer_alias="owner",
            confirm=True,
            recorded_at="2026-07-18T12:00:20+00:00",
        )

    first = timing.record_review_timing_event(
        base,
        artifact_namespace="radar_market_no_send_exact",
        idea_id="iar:exact-idea",
        event_type="first_viewed",
        reviewer_alias="owner",
        confirm=True,
        recorded_at="2026-07-18T12:00:10+00:00",
    )
    retry = timing.record_review_timing_event(
        base,
        artifact_namespace="radar_market_no_send_exact",
        idea_id="iar:exact-idea",
        event_type="first_viewed",
        reviewer_alias="another-reviewer",
        confirm=True,
        recorded_at="2026-07-18T12:00:15+00:00",
    )
    complete = timing.record_review_timing_event(
        base,
        artifact_namespace="radar_market_no_send_exact",
        idea_id="iar:exact-idea",
        event_type="review_completed",
        reviewer_alias="owner",
        confirm=True,
        recorded_at="2026-07-18T12:00:20+00:00",
    )

    assert first["status"] == "appended"
    assert retry["status"] == "already_present"
    assert retry["recorded_at"] == "2026-07-18T12:00:10+00:00"
    assert complete["status"] == "appended"
    rows = timing.read_review_timing_events(base)
    assert [row["event_type"] for row in rows] == ["first_viewed", "review_completed"]

    report = timing.build_review_timing_report(
        base,
        evaluated_at="2026-07-18T12:01:00+00:00",
    )
    record = report["records"][0]
    assert report["status"] == "complete"
    assert report["completed_review_record_count"] == 1
    assert record["pipeline_latency_seconds"] == 5.0
    assert record["time_to_first_view_seconds"] == 5.0
    assert record["review_duration_seconds"] == 10.0
    assert record["latency_seconds"] == 15.0
    assert record["idea_to_review_completed_seconds"] == 20.0
    assert record["decision_campaign_attached"] is True
    assert record["protocol_v2_evidence_eligible"] is False
    source_validation = timing.validate_review_timing_sources(base)
    assert source_validation["status"] == "valid"
    assert source_validation["source_namespaces"] == [
        "radar_market_no_send_exact"
    ]
    assert source_validation["event_count"] == 2
    assert source_validation["provider_calls"] == 0


def test_report_is_point_in_time_and_never_turns_dashboard_reads_into_views(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _base(tmp_path)
    monkeypatch.setattr(timing, "load_idea_binding", lambda *_args: _binding())
    timing.record_review_timing_event(
        base,
        artifact_namespace="radar_market_no_send_exact",
        idea_id="iar:exact-idea",
        event_type="first_viewed",
        reviewer_alias="owner",
        confirm=True,
        recorded_at="2026-07-18T12:00:10+00:00",
    )
    timing.record_review_timing_event(
        base,
        artifact_namespace="radar_market_no_send_exact",
        idea_id="iar:exact-idea",
        event_type="review_completed",
        reviewer_alias="owner",
        confirm=True,
        recorded_at="2026-07-18T12:00:20+00:00",
    )

    before_completion = timing.build_review_timing_report(
        base,
        evaluated_at="2026-07-18T12:00:15+00:00",
    )

    assert before_completion["status"] == "in_progress"
    assert before_completion["events_in_window_count"] == 1
    assert before_completion["events_after_evaluated_at_count"] == 1
    assert before_completion["records"][0]["review_completed_at"] is None
    assert before_completion["dashboard_reads_recorded_as_human_actions"] is False


def test_ledger_rejects_partial_rows_binding_drift_and_symlinks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _base(tmp_path)
    ledger = timing.review_timing_ledger_path(base)
    ledger.write_bytes(b'{"partial":true}')
    with pytest.raises(timing.DecisionReviewTimingError, match="partial_row"):
        timing.read_review_timing_events(base)

    ledger.unlink()
    first = timing.build_review_timing_event(
        _binding(),
        event_type="first_viewed",
        reviewer_alias="owner",
        recorded_at="2026-07-18T12:00:10+00:00",
    )
    complete = timing.build_review_timing_event(
        _binding(decision_projection_sha256="7" * 64),
        event_type="review_completed",
        reviewer_alias="owner",
        recorded_at="2026-07-18T12:00:20+00:00",
    )
    with pytest.raises(timing.DecisionReviewTimingError, match="binding_drift"):
        timing.validate_review_timing_events((first, complete))

    outside = tmp_path / "outside"
    outside.mkdir()
    outside_ledger = outside / "outside-ledger.jsonl"
    outside_ledger.write_bytes(b"outside-must-not-change\n")
    ledger.symlink_to(outside_ledger)
    monkeypatch.setattr(timing, "load_idea_binding", lambda *_args: _binding())
    with pytest.raises(timing.DecisionReviewTimingError, match="ledger_unsafe"):
        timing.record_review_timing_event(
            base,
            artifact_namespace="radar_market_no_send_exact",
            idea_id="iar:exact-idea",
            event_type="first_viewed",
            reviewer_alias="owner",
            confirm=True,
            recorded_at="2026-07-18T12:00:10+00:00",
        )
    assert outside_ledger.read_bytes() == b"outside-must-not-change\n"

    ledger.unlink()
    (base / timing.LEDGER_DIRECTORY).rmdir()
    (base / timing.LEDGER_DIRECTORY).symlink_to(outside, target_is_directory=True)
    with pytest.raises(timing.DecisionReviewTimingError, match="parent_unsafe"):
        timing.read_review_timing_events(base)
    assert not (outside / timing.LEDGER_FILENAME).exists()


def test_load_binding_requires_receipts_canonical_projection_and_genuine_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _base(tmp_path)
    namespace = "radar_market_no_send_exact"
    namespace_dir = base / namespace
    namespace_dir.mkdir()
    publication_path = namespace_dir / timing.daily_operations_publication.PUBLICATION_RECEIPT_FILENAME
    operations_path = namespace_dir / timing.daily_operations_publication.OPERATIONS_RECEIPT_FILENAME
    publication_path.write_text('{"status":"published"}\n', encoding="utf-8")
    operations_path.write_text('{"status":"dashboard_restarted"}\n', encoding="utf-8")
    publication_receipt = {
        "artifact_namespace": namespace,
        "recorded_at": "2026-07-18T12:00:04+00:00",
    }
    operations_receipt = {
        "artifact_namespace": namespace,
        "recorded_at": "2026-07-18T12:00:05+00:00",
    }
    monkeypatch.setattr(
        timing.daily_operations_publication,
        "validate_final_publication_contract",
        lambda *_args, **_kwargs: SimpleNamespace(
            valid=True,
            errors=(),
            publication_receipt=publication_receipt,
            operations_receipt=operations_receipt,
        ),
    )
    projection = {
        "decision_evaluated_at": "2026-07-18T12:00:00+00:00",
        "radar_route": "dashboard_watch",
        "primary_thesis_origin": "market_led",
        "directional_bias": "long",
        "anomaly_type": "stealth_accumulation",
        "catalyst_status": "unknown",
        "confidence_band": "exploratory",
        "market_phase": "emerging",
        "timing_state": "early",
        "preferred_horizon": "3d_7d",
        "expires_at": "2026-07-19T12:00:00+00:00",
        "radar_actionable": False,
        "actionability_score": 62.5,
        "evidence_confidence_score": 52.0,
        "risk_score": 48.0,
        "urgency_score": 45.0,
    }
    idea = {
        "integrated_candidate_id": "iar:exact-idea",
        "core_opportunity_id": "agg:exact-idea",
        "canonical_asset_id": "exact-asset",
        "symbol": "EXACT",
        "decision_projection": projection,
        "research_only": True,
        "decision_radar_campaign_counted": True,
        "decision_radar_campaign_eligible": True,
        "candidate_source_mode": "live_no_send",
        "data_acquisition_mode": "live_provider",
    }
    snapshot = SimpleNamespace(
        generation_authoritative=True,
        current_candidates=(idea,),
        run_id="2026-07-18T12:00:00+00:00|no_key_live",
        profile="no_key_live",
        revision=12,
        operator_state_sha256="1" * 64,
        operator_state={
            "artifacts": {
                "integrated_candidates": {"sha256": "3" * 64},
                "core_opportunities": {"sha256": "4" * 64},
            }
        },
    )
    monkeypatch.setattr(timing, "load_dashboard_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr(timing, "decision_model_values", lambda row: dict(row["decision_projection"]))

    binding = timing.load_idea_binding(base, namespace, "iar:exact-idea")

    assert binding["idea_available_at"] == "2026-07-18T12:00:05+00:00"
    assert binding["pipeline_latency_seconds"] == 5.0
    assert binding["publication_receipt_sha256"] != binding["operations_receipt_sha256"]

    contextual = timing.load_idea_binding(
        base,
        namespace,
        "iar:exact-idea",
        include_operator_context=True,
    )
    assert contextual["operator_review_context"] == _operator_context()

    projection["risk_score"] = 101.0
    with pytest.raises(timing.DecisionReviewTimingError, match="risk_score_invalid"):
        timing.load_idea_binding(
            base,
            namespace,
            "iar:exact-idea",
            include_operator_context=True,
        )
    projection["risk_score"] = 48.0

    idea["decision_radar_campaign_counted"] = False
    with pytest.raises(timing.DecisionReviewTimingError, match="not_genuine"):
        timing.load_idea_binding(base, namespace, "iar:exact-idea")


def test_exact_card_inspection_is_fingerprint_bound_explicitly_historical_and_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _base(tmp_path)
    namespace = "radar_market_no_send_exact"
    namespace_dir = base / namespace
    cards_dir = namespace_dir / "research_cards"
    cards_dir.mkdir(parents=True)
    card = cards_dir / "card_agg_exact_idea.md"
    card.write_text(
        "\n".join(
            (
                "# EXACT Crypto Decision Radar Card",
                "- Run ID: 2026-07-18T12:00:00+00:00|no_key_live",
                "- Profile: no_key_live",
                f"- Namespace: {namespace}",
                "- Core opportunity ID: agg:exact-idea",
                "Research-only / not a trade signal.",
                "",
            )
        ),
        encoding="utf-8",
    )
    projection = {
        "decision_evaluated_at": "2026-07-18T12:00:00+00:00",
        "radar_route": "dashboard_watch",
        "primary_thesis_origin": "market_led",
        "directional_bias": "long",
        "expires_at": "2026-07-19T12:00:00+00:00",
    }
    binding = _binding(
        decision_projection_sha256=timing._digest_value(projection),
        operator_review_context=_operator_context(),
    )
    card_tree = {
        **fingerprints.fingerprint_path(cards_dir),
        "status": "current",
        "path": "research_cards",
        "run_id": binding["run_id"],
    }
    core = {
        "integrated_candidate_id": binding["idea_id"],
        "core_opportunity_id": binding["core_opportunity_id"],
        "decision_projection": projection,
        "research_card_path": (
            f"event_fade_cache/{namespace}/research_cards/{card.name}"
        ),
    }
    snapshot = SimpleNamespace(
        namespace_dir=namespace_dir,
        artifact_namespace=namespace,
        run_id=binding["run_id"],
        profile=binding["profile"],
        revision=binding["revision"],
        operator_state_sha256=binding["operator_state_sha256"],
        operator_state={
            "artifacts": {
                "integrated_candidates": {
                    "sha256": binding["integrated_candidates_sha256"]
                },
                "core_opportunities": {
                    "sha256": binding["core_opportunities_sha256"]
                },
                "research_cards": card_tree,
            }
        },
        current_candidates=(core,),
    )
    monkeypatch.setattr(
        card_inspection.timing,
        "load_idea_binding",
        lambda *_args, **_kwargs: dict(binding),
    )
    monkeypatch.setattr(
        card_inspection,
        "load_dashboard_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        card_inspection,
        "decision_model_values",
        lambda row: dict(row["decision_projection"]),
    )
    monkeypatch.setattr(
        card_inspection.daily_operations_publication,
        "validate_final_publication_contract",
        lambda *_args, **_kwargs: SimpleNamespace(valid=False),
    )

    result = card_inspection.inspect_review_card(
        base,
        namespace,
        binding["idea_id"],
        evaluated_at="2026-07-20T12:00:00+00:00",
    )

    assert result["status"] == "verified"
    assert result["generation_role"] == "historical_published_generation"
    assert result["idea_temporal_status"] == "expired"
    assert result["card_markdown"] == card.read_text(encoding="utf-8")
    assert result["card_sha256"] == hashlib.sha256(card.read_bytes()).hexdigest()
    assert result["inspection_records_human_timing_event"] is False
    assert result["provider_calls"] == 0
    assert result["writes"] == 0

    card.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(
        timing.DecisionReviewTimingError,
        match="review_card_exact_read_invalid:fingerprint_content_mismatch",
    ):
        card_inspection.inspect_review_card(
            base,
            namespace,
            binding["idea_id"],
            evaluated_at="2026-07-20T12:00:00+00:00",
        )

    card.unlink()
    outside = tmp_path / "outside-card.md"
    outside.write_text("outside\n", encoding="utf-8")
    card.symlink_to(outside)
    with pytest.raises(
        timing.DecisionReviewTimingError,
        match="review_card_exact_read_invalid",
    ):
        card_inspection.inspect_review_card(
            base,
            namespace,
            binding["idea_id"],
            evaluated_at="2026-07-20T12:00:00+00:00",
        )


def test_status_without_ledger_is_clean_no_event_report(tmp_path: Path) -> None:
    base = _base(tmp_path)

    report = timing.build_review_timing_report(
        base,
        evaluated_at=datetime(2026, 7, 18, 12, tzinfo=timezone.utc),
    )

    assert report["status"] == "no_events"
    assert report["ledger_event_count"] == 0
    assert report["records"] == []
    assert report["report_scope"] == "recorded_explicit_human_actions_only"
    assert report["idea_record_count_definition"].endswith(
        "recorded_explicit_human_action"
    )
    assert report["eligible_idea_discovery_command"] == (
        "make radar-review-timing-queue PYTHON=.venv/bin/python"
    )
    assert report["zero_idea_records_meaning"] == (
        "no_explicit_human_actions_recorded_not_no_eligible_ideas"
    )
    assert report["provider_calls"] == 0


def test_review_status_summary_distinguishes_no_actions_from_no_eligible_ideas() -> None:
    report = {
        "status": "no_events",
        "evaluated_at": "2026-07-20T12:00:00+00:00",
        "ledger_event_count": 0,
        "idea_record_count": 0,
        "first_viewed_count": 0,
        "review_completed_count": 0,
        "report_scope": "recorded_explicit_human_actions_only",
        "zero_idea_records_meaning": "no_explicit_human_actions_recorded_not_no_eligible_ideas",
        "eligible_idea_discovery_command": "make radar-review-timing-queue PYTHON=.venv/bin/python",
        "provider_calls": 0,
        "writes": 0,
        "commands_require_explicit_confirmation": True,
        "dashboard_reads_recorded_as_human_actions": False,
        "protocol_v2_evidence_eligible": False,
        "safety": {
            "provider_calls": 0,
            "telegram_sends": 0,
            "trades": 0,
            "orders": 0,
            "event_alpha_paper_trades": 0,
            "normal_rsi_writes": 0,
            "event_alpha_triggered_fade": 0,
            "production_policy_mutations": 0,
        },
        "research_only": True,
    }

    output = decision_review_timing_cli._render_summary("status", report)

    assert "status=no_events" in output
    assert "report_scope=recorded_explicit_human_actions_only" in output
    assert "zero_idea_records_meaning=no_explicit_human_actions_recorded_not_no_eligible_ideas" in output
    assert "eligible_idea_discovery_command=make radar-review-timing-queue" in output


def test_review_queue_summary_keeps_exact_actions_and_safety_visible() -> None:
    queue = {
        "status": "action_required",
        "generated_at": "2026-07-20T12:00:00+00:00",
        "eligible_generation_count": 1,
        "eligible_idea_count": 1,
        "action_required_count": 1,
        "not_viewed_count": 1,
        "in_review_count": 0,
        "complete_count": 0,
        "expired_idea_count": 1,
        "unexpired_idea_count": 0,
        "skipped_candidate_count": 2,
        "provider_calls": 0,
        "writes": 0,
        "commands_require_explicit_confirmation": True,
        "dashboard_reads_recorded_as_human_actions": False,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
        "records": [
            {
                "review_status": "not_viewed",
                "radar_route": "dashboard_watch",
                "directional_bias": "long",
                "artifact_namespace": "radar_market_no_send_exact",
                "idea_id": "iar:exact",
                "core_opportunity_id": "agg:exact",
                "operator_review_context": _operator_context(),
                "idea_observed_at": "2026-07-20T11:00:00+00:00",
                "idea_available_at": "2026-07-20T11:00:08+00:00",
                "expires_at": "2026-07-19T12:00:00+00:00",
                "idea_temporal_status": "expired",
                "timing_action_warning": (
                    "historical_expired_idea_inspect_exact_card_before_recording_action"
                ),
                "inspection_command": (
                    "make radar-review-timing-inspect "
                    "RADAR_REVIEW_NAMESPACE=radar_market_no_send_exact "
                    "RADAR_REVIEW_IDEA_ID=iar:exact"
                ),
                "next_action": "record_first_view",
                "next_safe_command": (
                    "CONFIRM=1 make radar-review-timing-view "
                    "RADAR_REVIEW_NAMESPACE=radar_market_no_send_exact "
                    "RADAR_REVIEW_IDEA_ID=iar:exact "
                    "RADAR_REVIEWER_ALIAS=YOUR_ALIAS"
                ),
            }
        ],
        "safety": {
            "provider_calls": 0,
            "telegram_sends": 0,
            "trades": 0,
            "orders": 0,
            "event_alpha_paper_trades": 0,
            "normal_rsi_writes": 0,
            "event_alpha_triggered_fade": 0,
            "production_policy_mutations": 0,
        },
    }

    output = decision_review_timing_cli._render_summary("queue", queue)

    assert "action_required_count=1" in output
    assert "unique_idea_id_count=1" in output
    assert "recurring_idea_id_count=0" in output
    assert "idea_group[1].idea_id=iar:exact" in output
    assert "idea_group[1].core_opportunity_ids=agg:exact" in output
    assert "idea_group[1].symbols=EXACT" in output
    assert "idea_group[1].canonical_asset_ids=exact-asset" in output
    assert "idea_group[1].anomaly_types=stealth_accumulation" in output
    assert "idea_group[1].actionability_score_range=62.5..62.5" in output
    assert "idea_group[1].generation_count=1" in output
    assert "recurrence_is_presentation_only" in output
    assert "record[1].artifact_namespace=radar_market_no_send_exact" in output
    assert "record[1].idea_id=iar:exact" in output
    assert "record[1].symbol=EXACT" in output
    assert "record[1].anomaly_type=stealth_accumulation" in output
    assert "record[1].risk_score=48.0" in output
    assert "expired_idea_count=1" in output
    assert "record[1].idea_temporal_status=expired" in output
    assert "record[1].inspection_command=make radar-review-timing-inspect" in output
    assert "record[1].next_safe_command=CONFIRM=1 make" in output
    assert "commands_require_explicit_confirmation=true" in output
    assert "dashboard_reads_recorded_as_human_actions=false" in output
    assert "safety.provider_calls=0" in output
    assert "safety.orders=0" in output
    assert "RADAR_REVIEW_TIMING_OUTPUT=json" in output


def test_card_inspection_render_leads_with_expiry_and_does_not_claim_a_view() -> None:
    result = {
        "status": "verified",
        "artifact_namespace": "radar_market_no_send_exact",
        "idea_id": "iar:exact-idea",
        "generation_role": "historical_published_generation",
        "idea_temporal_status": "expired",
        "expires_at": "2026-07-19T12:00:00+00:00",
        "operator_warning": "historical published generation; idea expired",
        "card_sha256": "a" * 64,
        "card_markdown": "# Exact stored card\n\nResearch-only.\n",
    }

    output = decision_review_timing_cli._render_card_inspection(result)

    assert output.startswith("# Exact Decision Radar Review Card Inspection")
    assert "Idea temporal status: expired" in output
    assert "did not record a human timing event" in output
    assert "# Exact stored card" in output

    summary = decision_review_timing_cli._render_summary("inspect", result)
    assert "full_json_command=make radar-review-timing-inspect" in summary
    assert "RADAR_REVIEW_NAMESPACE=radar_market_no_send_exact" in summary
    assert "RADAR_REVIEW_IDEA_ID=iar:exact-idea" in summary
    assert "RADAR_REVIEW_INSPECTION_OUTPUT=json" in summary


def test_review_queue_summary_groups_recurrence_without_collapsing_actions() -> None:
    records = [
        {
            "idea_id": "iar:repeat",
            "core_opportunity_id": "agg:repeat",
            "radar_route": "dashboard_watch",
            "review_status": "not_viewed",
            "idea_available_at": "2026-07-18T01:00:00+00:00",
            "operator_review_context": _operator_context(
                actionability_score=60.0,
                risk_score=48.0,
            ),
        },
        {
            "idea_id": "iar:repeat",
            "core_opportunity_id": "agg:repeat",
            "radar_route": "risk_watch",
            "review_status": "in_review",
            "idea_available_at": "2026-07-20T01:00:00+00:00",
            "operator_review_context": _operator_context(
                anomaly_type="risk_off_sell_pressure",
                actionability_score=63.0,
                risk_score=56.0,
            ),
        },
        {
            "idea_id": "iar:single",
            "core_opportunity_id": "agg:single",
            "radar_route": "diagnostic",
            "review_status": "not_viewed",
            "idea_available_at": "2026-07-19T01:00:00+00:00",
            "operator_review_context": _operator_context(
                canonical_asset_id="single-asset",
                symbol="SINGLE",
                anomaly_type="confirmed_breakout",
                actionability_score=42.0,
                risk_score=70.0,
            ),
        },
    ]

    values = dict(decision_review_timing_cli._queue_recurrence_summary(records))

    assert values["generation_specific_review_record_count"] == 3
    assert values["unique_idea_id_count"] == 2
    assert values["recurring_idea_id_count"] == 1
    assert values["idea_group[1].idea_id"] == "iar:repeat"
    assert values["idea_group[1].generation_count"] == 2
    assert values["idea_group[1].symbols"] == "EXACT"
    assert values["idea_group[1].canonical_asset_ids"] == "exact-asset"
    assert values["idea_group[1].anomaly_types"] == (
        "risk_off_sell_pressure,stealth_accumulation"
    )
    assert values["idea_group[1].routes"] == "dashboard_watch,risk_watch"
    assert values["idea_group[1].review_statuses"] == "in_review,not_viewed"
    assert values["idea_group[1].first_available_at"] == (
        "2026-07-18T01:00:00+00:00"
    )
    assert values["idea_group[1].latest_available_at"] == (
        "2026-07-20T01:00:00+00:00"
    )
    assert values["idea_group[1].actionability_score_range"] == "60..63"
    assert values["idea_group[1].risk_score_range"] == "48..56"
    assert values["idea_group[2].idea_id"] == "iar:single"


def test_queue_cli_uses_exact_generation_projection_not_full_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = _base(tmp_path)
    evaluated_at = "2026-07-18T12:01:00+00:00"
    projection = {
        "schema_id": campaign.REVIEW_TIMING_GENERATION_PROJECTION_SCHEMA,
        "generation_summaries": [],
    }
    calls: list[object] = []

    monkeypatch.setattr(
        campaign,
        "build_campaign_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("queue must not build the comprehensive campaign report")
        ),
    )

    def build_projection(base_dir, *, evaluated_at):
        calls.extend((Path(base_dir), evaluated_at))
        return projection

    monkeypatch.setattr(
        campaign,
        "build_review_timing_generation_projection",
        build_projection,
    )
    monkeypatch.setattr(
        timing_queue,
        "build_review_timing_queue",
        lambda base_dir, rows, *, evaluated_at: {
            "status": "no_eligible_ideas",
            "base": str(base_dir),
            "row_count": len(tuple(rows)),
            "evaluated_at": evaluated_at,
        },
    )

    assert decision_review_timing_cli.main([
        "--artifact-base",
        str(base),
        "queue",
        "--evaluated-at",
        evaluated_at,
    ]) == 0
    output = json.loads(capsys.readouterr().out)

    assert calls == [base, evaluated_at]
    assert output["status"] == "no_eligible_ideas"
    assert output["row_count"] == 0
    assert output["evaluated_at"] == evaluated_at


def test_read_only_queue_discovers_receipt_backed_ideas_and_excludes_legacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _base(tmp_path)
    first = _binding(
        artifact_namespace="radar_market_no_send_first",
        idea_id="iar:first-idea",
        core_opportunity_id="agg:first-idea",
    )
    second = _binding(
        artifact_namespace="radar_market_no_send_second",
        idea_id="iar:second-idea",
        core_opportunity_id="agg:second-idea",
        radar_route="diagnostic",
        directional_bias="neutral",
    )
    bindings = {
        (first["artifact_namespace"], first["idea_id"]): first,
        (second["artifact_namespace"], second["idea_id"]): second,
    }

    def idea_ids(
        _base_dir: Path,
        namespace: str,
        *,
        expected_candidate_count: int,
    ) -> tuple[str, ...]:
        assert expected_candidate_count == 1
        return (
            "iar:first-idea"
            if namespace == "radar_market_no_send_first"
            else "iar:second-idea",
        )

    monkeypatch.setattr(timing_queue, "_receipt_backed_generation_idea_ids", idea_ids)
    def load_binding(
        _base_dir: Path,
        namespace: str,
        idea_id: str,
        *,
        include_operator_context: bool = False,
    ) -> dict[str, object]:
        value = dict(bindings[(namespace, idea_id)])
        if include_operator_context:
            value["operator_review_context"] = _operator_context(
                canonical_asset_id=f"{idea_id}-asset",
                symbol="FIRST" if idea_id == "iar:first-idea" else "SECOND",
            )
        return value

    monkeypatch.setattr(timing, "load_idea_binding", load_binding)
    receipt_backed = {
        "campaign_counted": True,
        "candidate_count": 1,
        "publication": {
            "ever_authoritative": True,
            "final_publication_receipt_valid": True,
            "operations_receipt_valid": True,
        },
    }
    generations = [
        {**receipt_backed, "artifact_namespace": "radar_market_no_send_first"},
        {**receipt_backed, "artifact_namespace": "radar_market_no_send_second"},
        {
            **receipt_backed,
            "artifact_namespace": "radar_market_no_send_legacy",
            "publication": {
                "ever_authoritative": True,
                "final_publication_receipt_valid": False,
                "operations_receipt_valid": False,
            },
        },
        {
            **receipt_backed,
            "artifact_namespace": "radar_market_no_send_unpublished",
            "publication": {
                "ever_authoritative": False,
                "final_publication_receipt_valid": False,
                "operations_receipt_valid": False,
            },
        },
    ]

    queue = timing_queue.build_review_timing_queue(
        base,
        generations,
        evaluated_at="2026-07-18T12:01:00+00:00",
    )

    assert queue["status"] == "action_required"
    assert queue["schema_version"] == 3
    assert queue["eligible_generation_count"] == 2
    assert queue["eligible_idea_count"] == 2
    assert queue["not_viewed_count"] == 2
    assert queue["expired_idea_count"] == 0
    assert queue["unexpired_idea_count"] == 2
    assert queue["skipped_candidate_count"] == 2
    assert queue["skipped_generation_reason_counts"] == {
        "final_publication_receipt_missing": 1,
        "never_authoritative": 1,
    }
    assert queue["writes"] == 0
    assert queue["provider_calls"] == 0
    assert queue["dashboard_reads_recorded_as_human_actions"] is False
    assert {
        row["operator_review_context"]["symbol"] for row in queue["records"]
    } == {"FIRST", "SECOND"}
    assert all(
        row["operator_review_context"]["presentation_only"] is True
        for row in queue["records"]
    )
    assert all(
        row["idea_temporal_status"] == "unexpired"
        and row["inspection_make_target"] == "radar-review-timing-inspect"
        and "make radar-review-timing-inspect" in row["inspection_command"]
        and row["inspection_requires_confirmation"] is False
        and row["inspection_records_human_timing_event"] is False
        for row in queue["records"]
    )
    assert all(
        row["next_make_target"] == "radar-review-timing-view"
        and "CONFIRM=1 make radar-review-timing-view" in row["next_safe_command"]
        and "RADAR_REVIEWER_ALIAS=YOUR_ALIAS" in row["next_safe_command"]
        for row in queue["records"]
    )
    campaign_projection = timing_queue.campaign_queue_projection(queue)
    assert campaign_projection["eligible_idea_count"] == 2
    assert campaign_projection["action_required_count"] == 2
    assert campaign_projection["absolute_paths_or_action_commands_embedded"] is False
    assert campaign_projection["operator_queue_command"] == (
        "make radar-review-timing-queue PYTHON=.venv/bin/python"
    )
    assert timing_queue.campaign_metric_values(campaign_projection) == {
        "review_timing_eligible_ideas": 2,
        "review_timing_action_required": 2,
        "review_timing_not_viewed": 2,
        "review_timing_in_review": 0,
        "review_timing_queue_complete": 0,
        "review_timing_skipped_candidates": 2,
    }
    serialized_projection = json.dumps(campaign_projection, sort_keys=True)
    assert str(base) not in serialized_projection
    assert "next_safe_command" not in serialized_projection
    assert "operator_review_context" not in serialized_projection

    tampered_queue = json.loads(json.dumps(queue))
    tampered_queue["records"][0]["operator_review_context"]["risk_score"] = 101.0
    with pytest.raises(
        timing.DecisionReviewTimingError,
        match="operator_context_invalid",
    ):
        timing_queue.campaign_queue_projection(tampered_queue)

    timing.record_review_timing_event(
        base,
        artifact_namespace="radar_market_no_send_first",
        idea_id="iar:first-idea",
        event_type="first_viewed",
        reviewer_alias="owner",
        confirm=True,
        recorded_at="2026-07-18T12:00:10+00:00",
    )
    updated = timing_queue.build_review_timing_queue(
        base,
        generations,
        evaluated_at="2026-07-18T12:01:00+00:00",
    )
    by_id = {row["idea_id"]: row for row in updated["records"]}
    assert updated["in_review_count"] == 1
    assert updated["not_viewed_count"] == 1
    assert by_id["iar:first-idea"]["next_make_target"] == (
        "radar-review-timing-complete"
    )
    assert "CONFIRM=1 make radar-review-timing-complete" in (
        by_id["iar:first-idea"]["next_safe_command"]
    )


def test_queue_revalidates_generation_candidate_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _base(tmp_path)
    namespace = "radar_market_no_send_exact"
    monkeypatch.setattr(
        timing_queue.daily_operations_publication,
        "validate_final_publication_contract",
        lambda *_args, **_kwargs: SimpleNamespace(
            valid=True,
            errors=(),
            operations_receipt={"recorded_at": "2026-07-18T12:00:05+00:00"},
        ),
    )
    monkeypatch.setattr(
        timing_queue,
        "load_dashboard_snapshot",
        lambda *_args, **_kwargs: SimpleNamespace(
            generation_authoritative=True,
            current_candidates=(),
        ),
    )

    with pytest.raises(
        timing.DecisionReviewTimingError,
        match="candidate_count_mismatch",
    ):
        timing_queue._receipt_backed_generation_idea_ids(
            base,
            namespace,
            expected_candidate_count=1,
        )


def test_receipt_backed_historical_queue_accepts_only_time_expiry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _base(tmp_path)
    namespace = "radar_market_no_send_historical"
    monkeypatch.setattr(
        timing_queue.daily_operations_publication,
        "validate_final_publication_contract",
        lambda *_args, **_kwargs: SimpleNamespace(
            valid=True,
            errors=(),
            operations_receipt={"recorded_at": "2026-07-18T12:00:05+00:00"},
        ),
    )
    snapshot = SimpleNamespace(
        generation_authoritative=False,
        generation_authority_reasons=("generation:stale", "doctor:stale"),
        current_candidates=({"integrated_candidate_id": "iar:historical"},),
    )
    monkeypatch.setattr(
        timing_queue,
        "load_dashboard_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )

    assert timing_queue._receipt_backed_generation_idea_ids(
        base,
        namespace,
        expected_candidate_count=1,
    ) == ("iar:historical",)

    snapshot.generation_authority_reasons = ("manifest:fingerprint_mismatch",)
    with pytest.raises(
        timing.DecisionReviewTimingError,
        match="generation_not_authoritative",
    ):
        timing_queue._receipt_backed_generation_idea_ids(
            base,
            namespace,
            expected_candidate_count=1,
        )


def test_campaign_markdown_labels_explicit_review_timing_as_annex_ineligible() -> None:
    review = {
        "status": "complete",
        "ledger_event_count": 2,
        "idea_record_count": 1,
        "first_view_record_count": 1,
        "completed_review_record_count": 1,
        "incomplete_review_record_count": 0,
        "events_after_evaluated_at_count": 0,
        "idea_available_at_definition": "exact operations receipt",
        "latency_seconds_definition": "idea_available_at_to_review_completed_at",
        "records": [
            {
                **_binding(),
                "review_status": "complete",
                "time_to_first_view_seconds": 5.0,
                "review_duration_seconds": 10.0,
                "latency_seconds": 15.0,
            }
        ],
    }

    markdown = market_observation_campaign_render.format_campaign_report(
        {
            "human_review_timing": review,
            "human_review_queue": {
                "eligible_idea_count": 3,
                "action_required_count": 2,
                "not_viewed_count": 1,
                "in_review_count": 1,
                "operator_queue_command": (
                    "make radar-review-timing-queue PYTHON=.venv/bin/python"
                ),
            },
        }
    )

    assert "## Human review timing" in markdown
    assert "dashboard GET/HEAD and health probes never create timing evidence" in markdown
    assert "| radar_market_no_send_exact | iar:exact-idea | dashboard_watch | complete | 5 | 5 | 10 | 15 |" in markdown
    assert "Protocol-v2 evidence eligible: `false`" in markdown
    assert "Receipt-backed ideas eligible for review timing: `3`" in markdown
    assert "Awaiting explicit human action: `2`" in markdown
    assert "Recorded-action status: `complete`" in markdown
    assert "Ideas with recorded human action: `1`" in markdown
    assert "- Idea records:" not in markdown
    assert "make radar-review-timing-queue PYTHON=.venv/bin/python" in markdown


def test_review_export_selects_every_validated_timing_source_namespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "tree"
    base = root / "event_fade_cache"
    history = base / timing.LEDGER_DIRECTORY
    source = base / "radar_market_no_send_reviewed"
    history.mkdir(parents=True)
    source.mkdir()
    ledger = history / timing.LEDGER_FILENAME
    ledger_payload = b"{}\n"
    ledger.write_bytes(ledger_payload)
    (source / "source-marker.json").write_text("{}\n", encoding="utf-8")
    (root / "Makefile").write_text("verify:\n\t@true\n", encoding="utf-8")
    policy_source = REPO_ROOT / "research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json"
    policy_target = root / "research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json"
    policy_target.parent.mkdir(parents=True)
    policy_target.write_bytes(policy_source.read_bytes())
    validation = {
        "status": "valid",
        "ledger_sha256": hashlib.sha256(ledger_payload).hexdigest(),
        "event_count": 2,
        "idea_count": 1,
        "source_namespace_count": 1,
        "source_namespaces": ["radar_market_no_send_reviewed"],
        "provider_calls": 0,
        "writes": 0,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
    }
    monkeypatch.setattr(
        timing,
        "validate_review_timing_sources",
        lambda _base: dict(validation),
    )
    spec = importlib.util.spec_from_file_location(
        "decision_review_timing_project_export",
        REPO_ROOT / "scripts/export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = root / "review.zip"

    assert module.main(root=root, out=output) == 0

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        manifest = json.loads(
            archive.read("event_fade_cache/PROJECT_ARTIFACT_EXPORT_MANIFEST.json")
        )
    assert (
        "event_fade_cache/radar_market_no_send_reviewed/source-marker.json"
        in names
    )
    selected = {
        row["kind"]: row for row in manifest["selector_results"]
    }["review_timing_source_namespaces"]
    assert selected["status"] == "selected"
    assert selected["source_validation_status"] == "valid"
    assert selected["source_namespaces"] == ["radar_market_no_send_reviewed"]
    assert selected["protocol_v2_evidence_eligible"] is False

    monkeypatch.setattr(
        timing,
        "validate_review_timing_sources",
        lambda _base: {**validation, "ledger_sha256": "f" * 64},
    )
    drifted_output = root / "review-drifted.zip"
    assert module.main(root=root, out=drifted_output) == 1
    assert not drifted_output.exists()
