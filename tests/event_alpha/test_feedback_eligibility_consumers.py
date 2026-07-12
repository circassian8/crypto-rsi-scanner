"""Cross-consumer tests for exact Core-authorized feedback evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone


NOW = datetime(2026, 7, 12, 3, 0, tzinfo=timezone.utc)


def _core(
    *,
    core_id: str = "core:velvet:listing",
    run_id: str = "run-feedback-consumer",
    profile: str = "fixture",
    artifact_namespace: str = "feedback_consumer",
) -> dict:
    return {
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "row_type": "event_core_opportunity",
        "run_id": run_id,
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "run_mode": "fixture",
        "core_opportunity_id": core_id,
        "feedback_target": core_id,
        "feedback_target_type": "core_opportunity_id",
        "generated_at": "2026-07-12T01:00:00+00:00",
        "research_only": True,
        "symbol": "VELVET",
        "coin_id": "velvet",
        "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        "source_provider": "official_exchange",
        "source_provider_domain": "exchange.example",
        "source_domain": "exchange.example",
        "source_pack": "official_listing_pack",
        "source_class": "official_exchange",
        "lane": "CONFIRMED_LONG_RESEARCH",
        "playbook_type": "listing",
        "effective_playbook_type": "listing",
        "impact_path_type": "listing",
        "candidate_role": "direct_beneficiary",
        "opportunity_level": "high_priority",
        "final_opportunity_level": "high_priority",
        "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
        "thesis_origin": "catalyst_led",
        "directional_bias": "long",
        "catalyst_status": "confirmed",
        "confidence_band": "high_confidence",
        "timing_state": "early",
        "tradability_status": "acceptable",
        "radar_route": "high_confidence_watch",
        "actionability_score_cohort": "80_89",
        "anomaly_type": "none",
    }


def _feedback(
    *,
    label: str = "useful",
    core_id: str = "core:velvet:listing",
    feedback_id: str | None = None,
    marked_at: str = "2026-07-12T02:00:00+00:00",
) -> dict:
    from crypto_rsi_scanner.event_alpha.outcomes import feedback_eligibility

    row = {
        "schema_version": "event_alpha_feedback_v1",
        "row_type": "event_alpha_feedback",
        "feedback_id": feedback_id or f"feedback:{label}:{core_id}",
        "run_id": "run-feedback-consumer",
        "profile": "fixture",
        "artifact_namespace": "feedback_consumer",
        "run_mode": "fixture",
        "core_opportunity_id": core_id,
        "target": core_id,
        "feedback_target": core_id,
        "feedback_target_type": "core_opportunity_id",
        "label": label,
        "marked_at": marked_at,
        "marked_by": "human-reviewer",
        "source": "manual_cli",
        "research_only": True,
    }
    row.update(feedback_eligibility.build_feedback_eligibility_fields(row))
    return row


def _alert() -> dict:
    return {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-feedback-consumer",
        "profile": "fixture",
        "artifact_namespace": "feedback_consumer",
        "core_opportunity_id": "core:velvet:listing",
        "feedback_target": "core:velvet:listing",
        "feedback_target_type": "core_opportunity_id",
        "alert_id": "alert:velvet:listing",
        "alert_key": "alert:velvet:listing",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "playbook_type": "listing",
        "source_provider": "official_exchange",
        "opportunity_level": "high_priority",
        "opportunity_score_final": 88,
        "impact_path_type": "listing",
        "impact_path_strength": "strong",
        "candidate_role": "direct_beneficiary",
        "market_confirmation_level": "strong",
        "evidence_quality_score": 90,
        "validation_stage": "impact_path_validated",
        "tier": "HIGH_PRIORITY_WATCH",
        "route": "HIGH_PRIORITY_RESEARCH",
        "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
        "alertable_after_quality_gate": True,
        "research_only": True,
    }


def test_exact_feedback_drives_policy_tuning_reliability_and_quality_export(tmp_path):
    from crypto_rsi_scanner.event_alpha.outcomes import policy_simulator
    from crypto_rsi_scanner.event_alpha.outcomes.quality import exports, scoring
    from crypto_rsi_scanner.event_alpha.providers import source_reliability

    core = _core()
    feedback = _feedback()
    alert = _alert()

    simulation = policy_simulator.simulate_policy(
        [alert],
        profile="fixture",
        feedback_rows=[feedback],
        core_rows=[core],
        include_api=True,
        now=NOW,
    )
    assert simulation.feedback_rows_eligible == 1
    current = next(row for row in simulation.scenarios if row["scenario"] == "current")
    assert current["known_useful_selected"] == ("alert:velvet:listing",)

    worksheet = scoring.build_tuning_worksheet(
        alert_rows=[alert],
        feedback_rows=[feedback],
        core_rows=[core],
        now=NOW,
    )
    assert worksheet.feedback_rows == 1
    assert worksheet.feedback_rows_supplied == 1
    assert worksheet.feedback_rows_excluded == 0

    reliability = source_reliability.format_source_reliability_report(
        [alert],
        feedback_rows=[feedback],
        core_rows=[core],
        now=NOW,
    )
    assert "feedback_eligible=1" in reliability
    assert "official_exchange: useful=1" in reliability

    out = tmp_path / "quality.json"
    result = exports.export_signal_quality_cases(
        out,
        alert_rows=[alert],
        feedback_rows=[feedback],
        core_rows=[core],
        generated_at=NOW,
        now=NOW,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert result.feedback_rows_eligible == 1
    assert payload["feedback_rows_eligible"] == 1
    assert any(
        case["reason_to_add_case"] == "useful_feedback_positive_case"
        for case in payload["cases"]
    )


def test_exact_feedback_drives_eval_export_and_inbox_review_state(tmp_path):
    from crypto_rsi_scanner.event_alpha.notifications import inbox
    from crypto_rsi_scanner.event_alpha.outcomes import feedback as feedback_reports

    core = _core()
    feedback = _feedback()
    alert = _alert()

    result = feedback_reports.export_cases_from_feedback(
        [alert],
        [feedback],
        tmp_path / "eval",
        core_rows=[core],
        now=NOW,
    )
    assert result.feedback_rows_eligible == 1
    assert result.proposed_cases == 1

    inbox_result = inbox.build_notification_inbox(
        notification_runs=[
            {
                "run_id": "run-feedback-consumer",
                "lane_counts_due": {"daily_digest": 1},
                "would_send_count": 1,
            }
        ],
        alert_rows=[alert],
        feedback_rows=[feedback],
        core_opportunity_rows=[core],
        research_cards_dir=tmp_path / "cards",
        profile="fixture",
        artifact_namespace="feedback_consumer",
        notification_runs_path=tmp_path / "runs.jsonl",
        alert_store_path=tmp_path / "alerts.jsonl",
        feedback_path=tmp_path / "feedback.jsonl",
        now=NOW,
    )
    assert inbox_result.feedback_rows_supplied == 1
    assert inbox_result.feedback_rows_eligible == 1
    assert inbox_result.feedback_rows_read == 1
    assert inbox_result.feedback_rows_excluded == 0
    assert len(inbox_result.canonical_review_items) == 1
    assert inbox_result.canonical_review_items[0].reviewed is True
    assert inbox_result.high_priority_unreviewed == ()


def test_legacy_feedback_is_visible_but_never_consumed(tmp_path):
    from crypto_rsi_scanner.event_alpha.notifications import inbox
    from crypto_rsi_scanner.event_alpha.operations import feedback_evidence
    from crypto_rsi_scanner.event_alpha.outcomes import policy_simulator

    legacy = {
        "target": "VELVET",
        "label": "useful",
        "symbol": "VELVET",
    }
    simulation = policy_simulator.simulate_policy(
        [_alert()],
        feedback_rows=[legacy],
        core_rows=[_core()],
        now=NOW,
    )
    assert simulation.feedback_rows_supplied == 1
    assert simulation.feedback_rows_eligible == 0
    assert simulation.feedback_rows_excluded == 1
    telemetry = feedback_evidence.telemetry(
        [legacy],
        [],
        [legacy],
        {"legacy_feedback_contract": 1},
    )
    assert telemetry == {
        "feedback_rows_supplied": 1,
        "feedback_rows_eligible": 0,
        "feedback_rows_excluded": 1,
        "feedback_exclusion_reason_counts": {"legacy_feedback_contract": 1},
    }

    inbox_result = inbox.build_notification_inbox(
        notification_runs=[
            {
                "run_id": "run-feedback-consumer",
                "lane_counts_due": {"daily_digest": 1},
                "would_send_count": 1,
            }
        ],
        alert_rows=[_alert()],
        feedback_rows=[legacy],
        core_opportunity_rows=[_core()],
        research_cards_dir=tmp_path / "cards",
        profile="fixture",
        artifact_namespace="feedback_consumer",
        notification_runs_path=tmp_path / "runs.jsonl",
        alert_store_path=tmp_path / "alerts.jsonl",
        feedback_path=tmp_path / "feedback.jsonl",
        now=NOW,
    )
    assert inbox_result.feedback_rows_supplied == 1
    assert inbox_result.feedback_rows_eligible == 0
    assert inbox_result.feedback_rows_read == 0
    assert inbox_result.feedback_rows_excluded == 1


def test_daily_brief_signal_quality_uses_only_exact_feedback_denominator():
    from crypto_rsi_scanner.event_alpha.artifacts import daily_brief

    legacy_same_asset = {
        "row_type": "event_alpha_feedback",
        "target": "VELVET",
        "label": "junk",
        "marked_at": "2026-07-12T02:30:00+00:00",
        "profile": "fixture",
        "artifact_namespace": "feedback_consumer",
        "run_id": "run-feedback-consumer",
        "run_mode": "fixture",
        "research_only": True,
        "symbol": "VELVET",
        "coin_id": "velvet",
        "impact_path_type": "forged_legacy_path",
    }
    markdown = daily_brief.build_daily_brief(
        alert_rows=[_alert()],
        feedback_rows=[_feedback(), legacy_same_asset],
        core_opportunity_rows=[_core()],
        requested_profile="fixture",
        artifact_namespace="feedback_consumer",
        include_test_artifacts=True,
        generated_at=NOW,
    )

    assert "Feedback eligibility: supplied=2; eligible=1; excluded=1" in markdown
    assert "Feedback by Impact Path: listing:useful=1" in markdown
    assert "forged_legacy_path" not in markdown


def test_research_card_renders_only_exact_core_authorized_feedback(
    monkeypatch,
):
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as research_cards
    from crypto_rsi_scanner.event_alpha.outcomes import feedback_eligibility

    exact_core = _core()
    other_core_id = "core:velvet:other-listing"
    other_core = _core(core_id=other_core_id)
    exact_feedback = _feedback()
    other_core_feedback = _feedback(
        label="junk",
        core_id=other_core_id,
        feedback_id="feedback:junk:other-core",
        marked_at="2026-07-12T02:10:00+00:00",
    )
    legacy_same_symbol = {
        "symbol": "VELVET",
        "coin_id": "velvet",
        "label": "legacy_poison_label",
        "marked_at": "2026-07-12T02:20:00+00:00",
    }
    original_partition = feedback_eligibility.partition_joined_calibration_feedback
    calls = []

    def tracked_partition(feedback_rows, core_rows, *, now=None):
        calls.append((list(feedback_rows), list(core_rows), now))
        return original_partition(calls[-1][0], calls[-1][1], now=now)

    monkeypatch.setattr(
        feedback_eligibility,
        "partition_joined_calibration_feedback",
        tracked_partition,
    )

    card = research_cards.render_research_card(
        exact_core["core_opportunity_id"],
        alert_rows=[exact_core, other_core],
        feedback_rows=[exact_feedback, other_core_feedback, legacy_same_symbol],
        generated_at=NOW,
    )

    assert card.found is True
    assert len(calls) == 1
    assert calls[0][2] == NOW
    assert (
        "feedback: useful at 2026-07-12T02:00:00+00:00 by human-reviewer"
        in card.markdown
    )
    assert "- feedback: junk at" not in card.markdown
    assert "2026-07-12T02:10:00+00:00" not in card.markdown
    assert "legacy_poison_label" not in card.markdown
    assert "2026-07-12T02:20:00+00:00" not in card.markdown
    assert "## Feedback Evidence Diagnostics" in card.markdown
    assert "Feedback rows supplied: 3" in card.markdown
    assert "Eligible exact-Core feedback rows: 2" in card.markdown
    assert "Eligible feedback rows matched to this card: 1" in card.markdown
    assert "Eligible feedback rows for other Core opportunities: 1" in card.markdown
    assert "Excluded feedback rows: 1" in card.markdown
    assert "legacy_feedback_contract=1" in card.markdown


def test_core_view_and_opportunity_audit_use_only_exact_feedback_authority():
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as opportunity_audit
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit_matching as audit_matching
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as core_store

    shared_event_id = "event:velvet:shared-listing"
    exact_core = {
        **_core(),
        "incident_id": "incident:velvet:primary",
        "event_id": shared_event_id,
    }
    other_core_id = "core:velvet:other-listing"
    other_core = {
        **_core(core_id=other_core_id),
        "incident_id": "incident:velvet:other",
        "event_id": shared_event_id,
    }
    exact_feedback = _feedback()
    other_core_feedback = _feedback(
        label="junk",
        core_id=other_core_id,
        feedback_id="feedback:junk:other-core-audit",
        marked_at="2026-07-12T02:10:00+00:00",
    )
    legacy_same_symbol = {
        "target": "legacy-symbol-target",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "label": "late",
        "marked_at": "2026-07-12T02:20:00+00:00",
    }
    legacy_same_event = {
        "target": "legacy-event-target",
        "event_id": shared_event_id,
        "label": "watch",
        "marked_at": "2026-07-12T02:30:00+00:00",
    }
    feedback_rows = [
        exact_feedback,
        other_core_feedback,
        legacy_same_symbol,
        legacy_same_event,
    ]
    core_rows = [exact_core, other_core]

    view = core_store.canonical_core_opportunity_view_from_rows(
        exact_core["core_opportunity_id"],
        core_rows=core_rows,
        feedback_rows=feedback_rows,
        profile="fixture",
        artifact_namespace="feedback_consumer",
        now=NOW,
    )

    assert view.found is True
    assert view.feedback_status == "has_feedback"
    assert tuple(row["feedback_label"] for row in view.feedback_rows) == ("useful",)
    assert view.feedback_rows_supplied == 4
    assert view.feedback_rows_eligible == 2
    assert view.feedback_rows_matched_to_core == 1
    assert view.feedback_rows_eligible_other_core == 1
    assert view.feedback_rows_excluded == 2
    assert view.feedback_exclusion_reason_counts["legacy_feedback_contract"] == 2

    exact_matches = audit_matching._matching_feedback_rows(
        exact_core["core_opportunity_id"],
        exact_core,
        feedback_rows,
        core_rows=core_rows,
        now=NOW,
    )
    assert tuple(row["feedback_label"] for row in exact_matches) == ("useful",)
    assert audit_matching._matching_feedback_rows(
        exact_core["core_opportunity_id"],
        exact_core,
        feedback_rows,
        now=NOW,
    ) == ()
    assert audit_matching._matching_feedback_rows(
        exact_core["core_opportunity_id"],
        exact_core,
        feedback_rows,
        core_rows=core_rows,
    ) == ()

    audit = opportunity_audit.format_opportunity_audit(
        exact_core["core_opportunity_id"],
        core_opportunity_rows=core_rows,
        feedback_rows=feedback_rows,
        profile="fixture",
        now=NOW,
    )

    assert "- feedback status: has_feedback" in audit
    assert "- feedback label: useful" in audit
    assert "- feedback label: junk" not in audit
    assert "- feedback label: late" not in audit
    assert "- feedback label: watch" not in audit
    assert "- feedback rows supplied: 4" in audit
    assert "- eligible exact-Core feedback rows: 2" in audit
    assert "- eligible feedback rows matched to this Core: 1" in audit
    assert "- eligible feedback rows for other Core opportunities: 1" in audit
    assert "- excluded feedback rows: 2" in audit
    assert "legacy_feedback_contract=2" in audit

    no_authority_audit = opportunity_audit.format_opportunity_audit(
        exact_core["core_opportunity_id"],
        hypotheses=[exact_core],
        feedback_rows=[exact_feedback],
        profile="fixture",
        now=NOW,
    )
    assert "- feedback status: pending_or_unknown" in no_authority_audit
    assert "- feedback label: none" in no_authority_audit
    assert "- feedback rows supplied: 1" in no_authority_audit
    assert "- eligible exact-Core feedback rows: 0" in no_authority_audit
    assert "- excluded feedback rows: 1" in no_authority_audit
    assert "missing_core_authority=1" in no_authority_audit
