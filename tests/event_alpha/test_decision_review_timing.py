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
    decision_review_timing_queue as timing_queue,
)
from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign_render


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
    }
    idea = {
        "integrated_candidate_id": "iar:exact-idea",
        "core_opportunity_id": "agg:exact-idea",
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

    idea["decision_radar_campaign_counted"] = False
    with pytest.raises(timing.DecisionReviewTimingError, match="not_genuine"):
        timing.load_idea_binding(base, namespace, "iar:exact-idea")


def test_status_without_ledger_is_clean_no_event_report(tmp_path: Path) -> None:
    base = _base(tmp_path)

    report = timing.build_review_timing_report(
        base,
        evaluated_at=datetime(2026, 7, 18, 12, tzinfo=timezone.utc),
    )

    assert report["status"] == "no_events"
    assert report["ledger_event_count"] == 0
    assert report["records"] == []
    assert report["provider_calls"] == 0


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
    monkeypatch.setattr(
        timing,
        "load_idea_binding",
        lambda _base_dir, namespace, idea_id: dict(bindings[(namespace, idea_id)]),
    )
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
    assert queue["eligible_generation_count"] == 2
    assert queue["eligible_idea_count"] == 2
    assert queue["not_viewed_count"] == 2
    assert queue["skipped_candidate_count"] == 2
    assert queue["skipped_generation_reason_counts"] == {
        "final_publication_receipt_missing": 1,
        "never_authoritative": 1,
    }
    assert queue["writes"] == 0
    assert queue["provider_calls"] == 0
    assert queue["dashboard_reads_recorded_as_human_actions"] is False
    assert all(
        row["next_make_target"] == "radar-review-timing-view"
        and "CONFIRM=1 make radar-review-timing-view" in row["next_safe_command"]
        and "RADAR_REVIEWER_ALIAS=YOUR_ALIAS" in row["next_safe_command"]
        for row in queue["records"]
    )

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
        {"human_review_timing": review}
    )

    assert "## Human review timing" in markdown
    assert "dashboard GET/HEAD and health probes never create timing evidence" in markdown
    assert "| radar_market_no_send_exact | iar:exact-idea | dashboard_watch | complete | 5 | 5 | 10 | 15 |" in markdown
    assert "Protocol-v2 evidence eligible: `false`" in markdown


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
