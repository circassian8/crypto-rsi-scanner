"""Focused Event Alpha outcomes and quality tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_near_miss_dedupes_and_excludes_promoted_or_zero_quality_rows():
    import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss

    base = {
        "incident_id": "incident:memecore",
        "validated_symbol": "M",
        "validated_coin_id": "memecore",
        "candidate_role": "direct_subject",
        "impact_path_type": "meme_attention",
        "source_class": "crypto_native",
        "evidence_specificity": "asset_and_catalyst",
        "market_confirmation_score": 48,
        "opportunity_score_final": 61,
        "opportunity_level": "local_only",
        "why_not_watchlist": ["needs_market_confirmation"],
    }
    rows = [
        {**base, "hypothesis_id": "hyp:m:1"},
        {**base, "hypothesis_id": "hyp:m:2", "opportunity_score_final": 62},
        {
            **base,
            "hypothesis_id": "hyp:velvet",
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "opportunity_level": "high_priority",
            "opportunity_score_final": 95,
            "market_confirmation_score": 82,
            "market_context_freshness_status": "fresh",
            "why_not_watchlist": [],
        },
        {**base, "hypothesis_id": "hyp:zero", "validated_symbol": "ZERO", "validated_coin_id": "zero", "opportunity_score_final": 0, "why_local_only": ["quality_context_missing"]},
    ]
    near = event_near_miss.detect_near_miss_rows(rows)
    assert [item.symbol for item in near] == ["M"]
    assert near[0].opportunity_score_before == 62


def test_quality_review_possible_false_positives_require_suspicion_reason():
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review

    strong = {
        "symbol": "VELVET",
        "coin_id": "velvet",
        "opportunity_level": "high_priority",
        "impact_path_type": "venue_value_capture",
        "candidate_role": "proxy_venue",
        "source_class": "crypto_native",
        "evidence_specificity": "asset_and_catalyst",
        "opportunity_score_final": 94,
    }
    noisy = {
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "opportunity_level": "local_only",
        "impact_path_type": "generic_cooccurrence_only",
        "candidate_role": "source_noise",
        "source_class": "publisher_suffix_false_positive",
        "evidence_specificity": "insufficient_data",
        "opportunity_score_final": 0,
    }
    market_dislocation = {
        "symbol": "M",
        "coin_id": "memecore",
        "opportunity_level": "exploratory",
        "impact_path_type": "market_dislocation_unknown",
        "candidate_role": "direct_subject",
        "source_class": "broad_news",
        "evidence_specificity": "direct_token_mechanism",
        "why_not_watchlist": ["cause_unknown_market_dislocation", "needs_market_confirmation"],
        "opportunity_score_final": 54,
    }
    clean_text = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(hypothesis_rows=[strong])
    )
    clean_fp = clean_text.split("Possible false positives:", 1)[1].split("Quality Gate Conflicts:", 1)[0]
    assert "- none" in clean_fp
    assert "VELVET" not in clean_fp
    mixed_text = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(hypothesis_rows=[strong, noisy, market_dislocation])
    )
    mixed_fp = mixed_text.split("Possible false positives:", 1)[1].split("Quality Gate Conflicts:", 1)[0]
    assert "BTC" in mixed_fp
    assert "VELVET" not in mixed_fp
    assert "M" not in mixed_fp

    explicit_text = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(hypothesis_rows=[
            {**strong, "symbol": "RUNE", "coin_id": "thorchain", "opportunity_level": "watchlist"},
            {"symbol": "HYPE", "coin_id": "hyperliquid", "warnings": ["invalid_subject"]},
            {"symbol": "KCS", "coin_id": "kucoin-shares", "why_local_only": "diagnostic_only"},
            {"symbol": "HYPE", "coin_id": "hyperliquid", "impact_path_type": "generic_cooccurrence_only"},
            {"symbol": "BTC", "coin_id": "bitcoin", "source_class": "publisher_suffix_false_positive"},
        ])
    )
    explicit_fp = explicit_text.split("Possible false positives:", 1)[1].split("Quality Gate Conflicts:", 1)[0]
    assert "RUNE" not in explicit_fp
    assert "HYPE" in explicit_fp
    assert "KCS" in explicit_fp
    assert "BTC" in explicit_fp


def test_event_alpha_feedback_readiness_and_core_feedback_target():
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_feedback_readiness
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_labels as event_feedback
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    entry = _test_watchlist_entry(
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        symbol="AAVE",
        coin_id="aave",
    )
    entry = __import__("dataclasses").replace(
        entry,
        incident_id="incident:aave",
        hypothesis_id="hyp:aave",
        latest_score_components={
            **entry.latest_score_components,
            "run_id": "run-aave",
            "profile": "notify_llm_quality_frame",
            "artifact_namespace": "notify_llm_quality_frame",
            "incident_id": "incident:aave",
            "hypothesis_id": "hyp:aave",
        },
    )
    card = event_research_cards.render_research_card(
        entry.key,
        watchlist_entries=[entry],
        card_path="/tmp/card_aave.md",
        lineage_context={
            "run_id": "run-aave",
            "profile": "notify_llm_quality_frame",
            "artifact_namespace": "notify_llm_quality_frame",
        },
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        card_path = tmp_path / "card_aave.md"
        card_path.write_text(card.markdown, encoding="utf-8")
        core_id = __import__(
            "crypto_rsi_scanner.event_alpha.radar.core_opportunities",
            fromlist=["core_opportunity_id_for_row"],
        ).core_opportunity_id_for_row(entry)
        alert = {
            "alert_id": "ea:aave",
            "card_id": "card_aave",
            "alert_key": entry.key,
            "symbol": "AAVE",
            "coin_id": "aave",
            "incident_id": "incident:aave",
            "core_opportunity_id": core_id,
            "feedback_target": core_id,
            "feedback_target_type": "core_opportunity_id",
            "impact_path_type": "strategic_investment_or_valuation",
            "candidate_role": "direct_subject",
            "opportunity_level": "validated_digest",
        }
        ready = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="notify_llm_quality_frame",
            artifact_namespace="notify_llm_quality_frame",
            card_paths=[card_path],
            alert_rows=[alert],
            feedback_rows=[],
            watchlist_entries=[entry],
        )
        assert ready.ready is True
        assert ready.cards_with_lineage == 1
        assert ready.cards_with_feedback_target == 1
        assert ready.core_opportunity_cards_ready == 1
        text = event_alpha_feedback_readiness.format_feedback_readiness(ready)
        assert "ready_for_feedback_collection: true" in text
        assert "burn_in_contract_maturity: not evaluated by this command" in text
        assert "cards_with_feedback_target: 1/1" in text
        cfg = event_feedback.EventFeedbackConfig(path=tmp_path / "feedback.jsonl")
        record = event_feedback.mark_feedback(core_id, "useful", watchlist_entries=[entry], cfg=cfg)
        assert record.key == entry.key
        report = event_feedback.format_feedback_report(event_feedback.load_feedback(cfg.path))
        assert "useful" in report
        assert "AAVE/aave" in report
        audit = event_opportunity_audit.format_opportunity_audit(
            core_id,
            watchlist_entries=[entry],
            feedback_rows=event_feedback.load_feedback(cfg.path).records,
            card_paths=[card_path],
            profile="notify_llm_quality_frame",
        )
        assert "- feedback status: pending_or_unknown" in audit
        assert "- feedback label: none" in audit
        assert "- feedback rows supplied: 1" in audit
        assert "- eligible exact-Core feedback rows: 0" in audit
        assert "- excluded feedback rows: 1" in audit
        assert "missing_core_authority=1" in audit
        assert f"FEEDBACK_TARGET='{core_id}'" in audit

        no_alert_ready = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="catalyst_frame_e2e",
            artifact_namespace="catalyst_frame_e2e",
            card_paths=[card_path],
            alert_rows=[],
            feedback_rows=[],
            watchlist_entries=[entry],
        )
        assert no_alert_ready.ready is True
        assert "no_alert_snapshots_found" in no_alert_ready.warnings

        legacy_path = tmp_path / "legacy.md"
        legacy_path.write_text("# Card\n\n- Run ID: legacy_lineage_missing\n", encoding="utf-8")
        blocked = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="notify_llm_quality_frame",
            artifact_namespace="notify_llm_quality_frame",
            card_paths=[legacy_path],
            alert_rows=[alert],
            feedback_rows=[],
            watchlist_entries=[entry],
        )
        assert "research_cards_missing_lineage" in blocked.blockers

        missing_target_path = tmp_path / "missing_target.md"
        missing_target_path.write_text(
            "# Card\n\n"
            "## Artifact Lineage\n"
            "- Generated at: 2026-06-15T16:00:00+00:00\n"
            "- Lineage status: current\n"
            "- legacy_lineage_missing: false\n"
            "- Run ID: run-aave\n"
            "- Profile: catalyst_frame_e2e\n"
            "- Namespace: catalyst_frame_e2e\n",
            encoding="utf-8",
        )
        missing_target = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="catalyst_frame_e2e",
            artifact_namespace="catalyst_frame_e2e",
            card_paths=[missing_target_path],
            alert_rows=[],
            feedback_rows=[],
            watchlist_entries=[entry],
        )
        assert "research_cards_missing_feedback_target" in missing_target.blockers

        index_path = tmp_path / "index.md"
        index_path.write_text("# Event Research Cards\n\n", encoding="utf-8")
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-aave", "profile": "catalyst_frame_e2e", "artifact_namespace": "catalyst_frame_e2e", "run_mode": "test"}],
            card_paths=[index_path, card_path],
            profile="catalyst_frame_e2e",
            artifact_namespace="catalyst_frame_e2e",
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor.research_card_index_present is True
        assert doctor.cards_missing_lineage == 0
        assert doctor.cards_missing_feedback_target == 0
        assert doctor.status in {"OK", "WARN"}

        doctor_missing = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-aave", "profile": "catalyst_frame_e2e", "artifact_namespace": "catalyst_frame_e2e", "run_mode": "test"}],
            card_paths=[card_path],
            profile="catalyst_frame_e2e",
            artifact_namespace="catalyst_frame_e2e",
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor_missing.research_card_index_present is False
        assert "index.md" in "; ".join(doctor_missing.blockers)


def test_event_alpha_quality_review_policy_simulation_and_export():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.outcomes.policy_simulator as event_alpha_policy_simulator
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_signal_quality_export

    rows = [
        {
            "alert_key": "velvet",
            "symbol": "VELVET",
            "opportunity_level": "high_priority",
            "opportunity_score_final": 88,
            "impact_path_type": "venue_value_capture",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_venue",
            "market_confirmation_level": "strong",
            "market_confirmation_score": 75,
            "evidence_quality_score": 82,
            "source_class": "primary",
            "evidence_specificity": "direct_value_capture",
            "manual_verification_items": ["verify liquidity"],
            "validation_stage": "impact_path_validated",
            "crypto_candidate_assets": [
                {"symbol": "VELVET", "coin_id": "velvet", "accepted": True},
                {"symbol": "LINK", "coin_id": "chainlink", "source": "taxonomy", "validated": False},
            ],
            "rejected_candidate_assets": [
                {"symbol": "HYPE", "reason": "generic_symbol_word_collision"},
                {"symbol": "NAV", "source": "navigation", "mention_type": "source_navigation"},
            ],
            "row_type": "event_alpha_alert_snapshot",
            "route": "HIGH_PRIORITY_RESEARCH",
            "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
            "alertable_after_quality_gate": True,
        },
        {
            "alert_key": "btc-policy",
            "symbol": "BTC",
            "opportunity_level": "local_only",
            "opportunity_score_final": 45,
            "impact_path_type": "generic_cooccurrence_only",
            "impact_path_strength": "weak",
            "candidate_role": "generic_mention",
            "market_confirmation_level": "none",
            "market_confirmation_score": 0,
            "evidence_quality_score": 35,
            "source_class": "secondary",
            "evidence_specificity": "weak_cooccurrence",
            "why_local_only": "generic_cooccurrence_only",
            "row_type": "event_alpha_alert_snapshot",
            "route": "STORE_ONLY",
            "final_route_after_quality_gate": "STORE_ONLY",
            "alertable_after_quality_gate": False,
        },
        {
            "alert_key": "openai-velvet",
            "symbol": "VELVET",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 66,
            "impact_path_type": "venue_value_capture",
            "impact_path_strength": "medium",
            "candidate_role": "proxy_venue",
            "market_confirmation_level": "weak",
            "market_confirmation_score": 25,
            "evidence_quality_score": 70,
            "source_class": "independent",
            "evidence_specificity": "direct_value_capture",
            "row_type": "event_alpha_alert_snapshot",
            "route": "RESEARCH_DIGEST",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "alertable_after_quality_gate": True,
        },
        {
            "alert_key": "near-threshold",
            "symbol": "NEAR",
            "opportunity_level": "exploratory",
            "opportunity_score_final": 58,
            "impact_path_type": "venue_value_capture",
            "impact_path_strength": "medium",
            "candidate_role": "proxy_venue",
            "market_confirmation_level": "weak",
            "market_confirmation_score": 25,
            "evidence_quality_score": 58,
            "source_class": "independent",
            "evidence_specificity": "direct_value_capture",
            "row_type": "event_alpha_alert_snapshot",
            "route": "STORE_ONLY",
            "final_route_after_quality_gate": "STORE_ONLY",
            "alertable_after_quality_gate": False,
        },
        {
            "alert_key": "legacy-btc-conflict",
            "symbol": "BTC",
            "opportunity_level": "local_only",
            "opportunity_score_final": 0,
            "impact_path_type": "insufficient_data",
            "impact_path_strength": "none",
            "candidate_role": "unknown_with_reason",
            "market_confirmation_level": "none",
            "market_confirmation_score": 0,
            "evidence_quality_score": 0,
            "source_class": "insufficient_data",
            "evidence_specificity": "insufficient_data",
            "row_type": "event_alpha_alert_snapshot",
            "route": "RESEARCH_DIGEST",
            "route_alertable": True,
        },
    ]
    review = event_alpha_quality_review.build_quality_review(profile="fixture", alert_rows=rows)
    report = event_alpha_quality_review.format_quality_review(review)
    assert review.candidate_discovery_funnel["raw_terms_extracted"] == 4
    assert review.candidate_discovery_funnel["candidate_like_terms"] == 1
    assert review.candidate_discovery_funnel["resolver_attempted"] == 3
    assert review.candidate_discovery_funnel["resolver_accepted_candidates"] == 1
    assert review.candidate_discovery_funnel["resolver_rejected_terms"] == 2
    assert review.candidate_discovery_funnel["context_validated_candidates"] >= 1
    assert review.candidate_discovery_funnel["promoted_candidates"] >= 1
    assert "candidates_added" not in review.candidate_discovery_funnel
    assert "candidate_terms_added" not in review.candidate_discovery_funnel
    assert "raw_candidate_terms_added" in review.candidate_discovery_funnel
    assert "Strong opportunities" in report
    assert "quality_coverage:" in report
    assert "candidate_discovery_funnel:" in report
    assert "Quality Tuning Suggestions" in report
    assert "closest_to_digest_threshold" in report
    assert "VELVET" in report
    assert "Weak co-occurrence / local-only" in report
    assert "Validated but market-unconfirmed" in report
    missed_rows = [{"symbol": "MISS", "return_pct": 150, "failure_stage": "quality_gate_too_strict", "feedback_target": "missed:MISS"}]
    sim = event_alpha_policy_simulator.simulate_policy(
        rows,
        profile="fixture",
        feedback_rows=[
            {"feedback_target": "velvet", "label": "useful"},
            {"feedback_target": "btc-policy", "label": "junk"},
        ],
        missed_rows=missed_rows,
    )
    text = event_alpha_policy_simulator.format_policy_simulation(sim)
    assert "lower_opportunity_threshold" in text
    assert "high_quality_only" in text
    assert "legacy_conflicts_excluded: 1" in text
    assert "near-threshold" in text
    high_counts = [row["alertable_count"] for row in sim.scenarios if row["scenario"] == "high_quality_only"]
    low_counts = [row["alertable_count"] for row in sim.scenarios if row["scenario"] == "lower_opportunity_threshold"]
    assert max(low_counts) >= max(high_counts)
    assert "near-threshold" in next(row for row in sim.scenarios if row["scenario"] == "lower_opportunity_threshold")["gained"]
    assert "warning_weak_or_generic_alertable" not in text
    assert "known_useful_selected" not in text
    assert "known_junk_selected" not in text
    assert sim.feedback_rows_supplied == 2
    assert sim.feedback_rows_eligible == 0
    assert sim.feedback_rows_excluded == 2
    assert "missed_recall_candidates" in text
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proposed.json"
        result = event_alpha_signal_quality_export.export_signal_quality_cases(
            out,
            alert_rows=rows,
            feedback_rows=[
                {"feedback_target": "velvet", "label": "useful", "notes": "good proxy evidence"},
                {"feedback_target": "btc-policy", "label": "junk", "notes": "weak macro cooccurrence"},
                {"feedback_target": "openai-velvet", "label": "watch"},
            ],
            missed_rows=missed_rows,
        )
        payload = json.loads(out.read_text())
        assert result.cases_written >= 3
        assert result.feedback_rows_supplied == 3
        assert result.feedback_rows_eligible == 0
        assert result.feedback_rows_excluded == 3
        assert not any(case["reason_to_add_case"] == "useful_feedback_positive_case" for case in payload["cases"])
        assert not any(case["reason_to_add_case"] == "junk_feedback_negative_case" for case in payload["cases"])
        assert not any(case["reason_to_add_case"] == "watch_feedback_borderline_case" for case in payload["cases"])
        assert any(case["reason_to_add_case"] == "missed_opportunity_recall_case" for case in payload["cases"])
        assert "OPENAI_API_KEY" not in out.read_text()


def test_event_alpha_quality_make_targets_exist_and_do_not_send():
    from pathlib import Path

    text = Path("Makefile").read_text()
    for target in (
        "event-alpha-quality-review",
        "event-alpha-quality-coverage-report",
        "event-alpha-policy-simulate",
        "event-alpha-quality-validation-cycle",
        "event-alpha-export-signal-quality-cases",
        "event-alpha-quality-loop",
        "event-alpha-quality-loop-llm",
        "event-alpha-frame-quality-loop",
    ):
        assert f"{target}:" in text
    loop = text.split("event-alpha-quality-loop:", 1)[1].split("event-alpha-quality-loop-llm:", 1)[0]
    assert "event-alpha-signal-quality-eval" in loop
    assert "event-alpha-quality-review" in loop
    assert "event-alpha-policy-simulate" in loop
    assert "event-alpha-notification-inbox" in loop
    assert "event-impact-hypotheses-report" in loop
    assert "event-alpha-daily-brief" in loop
    assert "event-alpha-cycle-send" not in loop
    assert "event-alert-send" not in loop
    frame_loop = text.split("event-alpha-frame-quality-loop:", 1)[1].split("event-alpha-signal-quality-eval:", 1)[0]
    assert "event-alpha-signal-quality-eval" in frame_loop
    assert "event-alpha-catalyst-frame-e2e-cycle" in frame_loop
    assert "event-alpha-quality-review" in frame_loop
    assert "event-incidents-report" in frame_loop
    assert "event-impact-hypotheses-report" in frame_loop
    assert "event-alpha-daily-brief" in frame_loop
    assert "event-alpha-artifact-doctor" in frame_loop
    assert "STRICT=1" in frame_loop
    assert "event-opportunity-audit" in frame_loop
    assert "TARGET=$(TARGET)" in frame_loop
    assert "event-alpha-cycle-send" not in frame_loop
    assert "event-alert-send" not in frame_loop
    daily_brief_target = text.split("event-alpha-daily-brief:", 1)[1].split("event-alpha-replay:", 1)[0]
    assert "$(EVENT_ALPHA_INCLUDE_TEST_ARG)" in daily_brief_target


def test_event_alpha_quality_coverage_checks_latest_raw_rows_only():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_coverage
    import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields

    started = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 6, 25, 12, 2, tzinfo=timezone.utc)
    run = {
        "row_type": "event_alpha_run",
        "run_id": "run-quality",
        "profile": "notify_llm_quality",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "success": True,
    }
    full = event_alpha_quality_fields.ensure_quality_fields({
        "run_id": "run-quality",
        "profile": "notify_llm_quality",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm_quality",
    })
    hypothesis = {**full, "row_type": "event_impact_hypothesis", "hypothesis_id": "hyp:velvet"}
    alert = {**full, "row_type": "event_alpha_alert_snapshot", "alert_key": "alert:velvet"}
    watch = event_alpha_quality_fields.ensure_quality_fields({
        "row_type": "event_watchlist_state",
        "key": "watch:velvet",
        "last_seen_at": "2026-06-25T12:01:00+00:00",
    })
    old_missing = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "old-run",
        "profile": "notify_llm_quality",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm_quality",
        "alert_key": "old-missing",
    }
    result = event_alpha_quality_coverage.build_latest_run_quality_coverage(
        profile="notify_llm_quality",
        artifact_namespace="notify_llm_quality",
        run_rows=[run],
        hypothesis_rows=[hypothesis],
        watchlist_rows=[watch],
        alert_rows=[alert, old_missing],
    )
    assert result.status == "OK"
    assert result.run_id == "run-quality"
    assert {bucket.row_type: bucket.rows for bucket in result.buckets} == {
        "hypothesis": 1,
        "watchlist": 1,
        "alert_snapshot": 1,
    }
    assert all(not bucket.missing_rows for bucket in result.buckets)

    bad_alert = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-quality",
        "profile": "notify_llm_quality",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm_quality",
        "alert_key": "bad-alert",
    }
    blocked = event_alpha_quality_coverage.build_latest_run_quality_coverage(
        profile="notify_llm_quality",
        artifact_namespace="notify_llm_quality",
        run_rows=[run],
        hypothesis_rows=[hypothesis],
        watchlist_rows=[watch],
        alert_rows=[bad_alert],
    )
    assert blocked.status == "BLOCKED"
    report = event_alpha_quality_coverage.format_quality_coverage_report(blocked)
    assert "bad-alert" in report
    assert "missing=" in report


def test_event_alpha_quality_stale_warning_uses_quality_validation_reference():
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_coverage
    import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review
    import crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store as event_impact_hypothesis_store

    stale_row = {
        "row_type": "event_impact_hypothesis",
        "run_id": "run-old",
        "profile": "notify_llm",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm",
        "hypothesis_id": "hyp:old",
    }
    reference = event_alpha_quality_fields.ensure_quality_fields({
        "row_type": "event_impact_hypothesis",
        "run_id": "run-ref",
        "profile": "quality_validation",
        "run_mode": "test",
        "artifact_namespace": "quality_validation",
        "hypothesis_id": "hyp:ref",
    })
    warning = event_alpha_quality_coverage.stale_quality_artifact_warning(
        [stale_row],
        reference_rows=[reference],
    )
    assert warning == event_alpha_quality_coverage.STALE_QUALITY_ARTIFACT_WARNING

    review = event_alpha_quality_review.build_quality_review(
        profile="notify_llm",
        hypothesis_rows=[stale_row],
        stale_warning=warning,
    )
    assert "stale_artifact_warning: " + warning in event_alpha_quality_review.format_quality_review(review)

    loaded = event_impact_hypothesis_store.EventImpactHypothesisStoreReadResult(
        path=Path("hypotheses.jsonl"),
        rows_read=1,
        rows=[stale_row],
        total_rows_read=1,
    )
    text = event_impact_hypothesis_store.format_impact_hypotheses_store_report(
        loaded,
        stale_quality_warning=warning,
    )
    assert "stale_artifact_warning: " + warning in text


def test_feedback_and_calibration_include_signal_quality_fields():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.outcomes.calibration as event_alpha_calibration
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_labels as event_feedback

    entry = _test_watchlist_entry(
        state="WATCHLIST",
        symbol="VELVET",
        coin_id="velvet",
    )
    core_id = "core_velvet_spacex"
    entry = __import__("dataclasses").replace(entry, latest_score_components={
        "run_id": "run-velvet",
        "profile": "catalyst_frame_e2e",
        "artifact_namespace": "catalyst_frame_e2e",
        "core_opportunity_id": core_id,
        "incident_id": "incident:velvet-spacex",
        "hypothesis_id": "hyp:velvet",
        "impact_path_type": "proxy_exposure",
        "candidate_role": "proxy_venue",
        "evidence_specificity": "source_explains_mechanism",
        "market_confirmation_level": "moderate",
        "market_context_freshness_status": "fresh",
        "opportunity_level": "watchlist",
        "source_class": "crypto_native",
        "source_domain": "cryptopanic.com",
        "evidence_acquisition_providers_used": ("cryptopanic",),
        "catalyst_frame_status": "validated",
        "main_frame_type": "proxy_exposure",
        "final_route_after_quality_gate": "WATCHLIST",
        "lane": "daily_digest",
        "accepted_evidence_reason_codes": ("cryptopanic_currency_tag_match", "direct_token_mechanism"),
    })
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        card_path = tmp_path / "velvet.md"
        card_path.write_text(
            "# Card\n\n"
            "- Run ID: run-velvet\n"
            "- Profile: catalyst_frame_e2e\n"
            "- Namespace: catalyst_frame_e2e\n"
            f"- Core opportunity ID: {core_id}\n"
            f"- Feedback target: {core_id}\n",
            encoding="utf-8",
        )
        context_row = {
            "row_type": "event_core_opportunity",
            "schema_id": "core_opportunity_v1",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": "run-velvet",
            "profile": "catalyst_frame_e2e",
            "artifact_namespace": "catalyst_frame_e2e",
            "run_mode": "burn_in",
            "core_opportunity_id": core_id,
            "feedback_target": core_id,
            "feedback_target_type": "core_opportunity_id",
            "generated_at": "2026-06-20T11:00:00+00:00",
            "research_only": True,
            "symbol": "VELVET",
            "coin_id": "velvet",
            "opportunity_type": "UNCONFIRMED_RESEARCH",
            "incident_id": "incident:velvet-spacex",
            "hypothesis_id": "hyp:velvet",
            "impact_path_type": "proxy_exposure",
            "candidate_role": "proxy_venue",
            "evidence_specificity": "source_explains_mechanism",
            "source_class": "crypto_native",
            "source_domain": "cryptopanic.com",
            "source_provider": "cryptopanic",
            "source_pack": "proxy_preipo_rwa_pack",
            "accepted_evidence_reason_codes": ("cryptopanic_currency_tag_match", "direct_token_mechanism"),
            "market_confirmation_level": "moderate",
            "market_context_freshness_status": "fresh",
            "catalyst_frame_status": "validated",
            "main_frame_type": "proxy_exposure",
            "opportunity_level": "watchlist",
            "final_route_after_quality_gate": "WATCHLIST",
            "lane": "daily_digest",
        }
        cfg = event_feedback.EventFeedbackConfig(path=tmp_path / "feedback.jsonl")
        record = event_feedback.mark_feedback(
            str(card_path),
            "useful",
            watchlist_entries=[entry],
            context_rows=[context_row],
            core_opportunity_rows=[context_row],
            card_paths=[card_path],
            cfg=cfg,
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
        )
        loaded = event_feedback.load_feedback(cfg.path)
    assert record.impact_path_type == "proxy_exposure"
    assert record.incident_id == "incident:velvet-spacex"
    assert record.hypothesis_id == "hyp:velvet"
    assert record.core_opportunity_id == core_id
    assert record.feedback_target == core_id
    assert record.card_path and record.card_path.endswith("velvet.md")
    assert record.run_id == "run-velvet"
    assert record.profile == "catalyst_frame_e2e"
    assert record.artifact_namespace == "catalyst_frame_e2e"
    assert record.source_pack == "proxy_preipo_rwa_pack"
    assert record.source_provider == "cryptopanic"
    assert record.source_provider_domain == "cryptopanic.com"
    assert record.market_context_freshness_status == "fresh"
    assert record.catalyst_frame_status == "validated"
    assert record.main_frame_type == "proxy_exposure"
    assert record.final_route_after_quality_gate == "WATCHLIST"
    assert "direct_token_mechanism" in record.accepted_evidence_reason_codes
    assert loaded.records[0].incident_id == "incident:velvet-spacex"
    report = event_alpha_calibration.format_calibration_report(
        [],
        feedback_rows=[r.__dict__ for r in loaded.records],
        core_rows=[context_row],
        now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
    )
    assert "feedback by impact path type: proxy_exposure: useful=1" in report
    assert "feedback by candidate role: proxy_venue: useful=1" in report
    assert "feedback by source class: crypto_native: useful=1" in report
    assert "feedback by source pack: proxy_preipo_rwa_pack: useful=1" in report
    assert "feedback by accepted evidence reason" not in report
    assert "feedback by incident id: incident:velvet-spacex: useful=1" in report
    assert "feedback by source domain: cryptopanic.com: useful=1" in report
    assert "feedback by market freshness: fresh: useful=1" in report
    assert "feedback by catalyst frame status: validated: useful=1" in report
    assert "feedback by main frame type: proxy_exposure: useful=1" in report
    assert "feedback by route/lane: WATCHLIST/daily_digest: useful=1" in report


def test_event_alpha_signal_quality_make_targets_exist():
    from pathlib import Path

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-signal-quality-eval:" in text
    assert "--event-alpha-signal-quality-eval" in text
    assert "event-opportunity-audit:" in text
    assert "--event-opportunity-audit" in text


def test_quality_review_uses_core_opportunities_as_primary_sections():
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    rows = _canonical_core_fixture_rows()
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-quality-review",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    review = event_alpha_quality_review.build_quality_review(
        profile="market_refresh_smoke",
        core_opportunity_rows=core_rows,
        hypothesis_rows=rows,
    )
    text = event_alpha_quality_review.format_quality_review(review)
    strong = text.split("Strong opportunities:", 1)[1].split("Validated but market-unconfirmed:", 1)[0]
    weak = text.split("Weak co-occurrence / local-only:", 1)[1].split("Sector hypotheses awaiting validation:", 1)[0]
    upgrades = text.split("Top upgrade candidates:", 1)[1].split("Top downgrade risks:", 1)[0]
    downgrades = text.split("Top downgrade risks:", 1)[1].split("Quality Tuning Suggestions:", 1)[0]
    freshness = text.split("Market Freshness Readiness:", 1)[1].split("Top upgrade candidates:", 1)[0]
    assert "operator_view: canonical_core_rows=4" in text
    assert "VELVET" in strong
    assert "VELVET" not in weak
    assert "VELVET" not in upgrades
    assert "VELVET" in downgrades
    assert "invalid exposure/value-capture claim" in downgrades
    assert "no token value-capture mechanism is visible" not in downgrades
    assert "AAVE" in upgrades
    assert "status=fresh source=missing" not in freshness
    assert "support_or_diagnostic_rows=" in text


def test_feedback_readiness_counts_canonical_review_items_not_diagnostics():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_feedback_readiness
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-feedback-canonical-review",
            profile="evidence_acquisition_smoke",
            run_mode="burn_in",
            artifact_namespace="evidence_acquisition_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        cards = event_research_cards.write_research_cards(root / "cards", watchlist_entries=[], alert_rows=core_rows)
        event_core_opportunity_store.update_core_opportunity_card_links(
            core_path,
            cards.card_paths,
            run_id="run-feedback-canonical-review",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        velvet = next(row for row in core_rows if row["symbol"] == "VELVET")
        canonical = {
            "row_type": "event_alpha_alert_snapshot",
            "run_id": "run-feedback-canonical-review",
            "alert_id": "ea:velvet-canonical",
            "alert_key": "incident-spacex|velvet|proxy_attention",
            "core_opportunity_id": velvet["core_opportunity_id"],
            "snapshot_class": "canonical_core_snapshot",
            "core_resolution_status": "canonical",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            "tier": "HIGH_PRIORITY_WATCH",
            "feedback_target": velvet["core_opportunity_id"],
        }
        diagnostic_without_target = {
            **canonical,
            "alert_id": "ea:velvet-support",
            "alert_key": "incident-spacex|velvet|source_noise_control",
            "snapshot_class": "diagnostic_support_snapshot",
            "core_resolution_status": "diagnostic_support",
            "snapshot_core_resolution_status": "diagnostic_support",
            "is_diagnostic_snapshot": True,
            "candidate_role": "source_noise",
            "playbook_type": "source_noise_control",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "feedback_target": "",
        }
        inbox = event_alpha_notification_inbox.build_notification_inbox(
            notification_runs=[],
            alert_rows=[diagnostic_without_target, canonical],
            feedback_rows=[],
            research_cards_dir=root / "cards",
            profile="evidence_acquisition_smoke",
            artifact_namespace="evidence_acquisition_smoke",
            notification_runs_path=root / "runs.jsonl",
            alert_store_path=root / "alerts.jsonl",
            feedback_path=root / "feedback.jsonl",
            core_opportunity_rows=core_rows,
        )
        readiness = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="evidence_acquisition_smoke",
            artifact_namespace="evidence_acquisition_smoke",
            card_paths=cards.card_paths,
            alert_rows=[diagnostic_without_target, canonical],
            feedback_rows=[],
            watchlist_entries=[],
            core_opportunity_rows=core_rows,
            inbox_result=inbox,
        )

    assert readiness.canonical_review_items >= 1
    assert readiness.diagnostic_review_items_hidden >= 1
    assert "alert_snapshots_missing_feedback_targets" not in readiness.blockers
    assert "canonical_review_items_missing_feedback_targets" not in readiness.blockers


def test_daily_brief_evidence_acquisition_uses_canonical_post_policy_verdict():
    import json

    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        core_row = {
            "row_type": "event_core_opportunity",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "ns",
            "core_opportunity_id": "core_chz_review",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "incident_id": "world-cup-chz",
            "candidate_role": "proxy_instrument",
            "primary_impact_path": "unlock_supply_event",
            "impact_path_type": "unlock_supply_event",
            "opportunity_level": "validated_digest",
            "final_opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "final_state_after_quality_gate": "RADAR",
            "source_pack": "unlock_supply_pack",
            "source_class": "cryptopanic_tagged",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "accepted_provider_counts": {"cryptopanic": 1},
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "supporting_categories": ["sports_fan_proxy"],
            "supporting_impact_paths": ["fan_token_attention"],
            "generated_at": "2026-07-01T00:00:00+00:00",
        }
        acquisition = {
            "row_type": "event_evidence_acquisition",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "ns",
            "core_opportunity_id": "core_chz_review",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "source_pack": "fan_sports_pack",
            "status": "accepted_evidence_found",
            "accepted_evidence": [{"provider": "cryptopanic", "source_class": "cryptopanic_tagged"}],
            "rejected_evidence_samples": [],
            "opportunity_score_before": 64,
            "opportunity_score_after": 72,
            "acquisition_evidence_status": "accepted_evidence_found",
            "final_upgrade_status": "unchanged",
            "final_opportunity_level": "validated_digest",
            "final_verdict_source": "evidence_acquisition",
        }
        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[{
                "row_type": "event_alpha_run",
                "run_id": "run-1",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "ns",
                "started_at": "2026-07-01T00:00:00+00:00",
                "success": True,
            }],
            core_opportunity_rows=[core_row],
            evidence_acquisition_rows=[acquisition],
            requested_profile="notify_llm_deep",
            artifact_namespace="ns",
            run_ledger_path=base / "event_alpha_runs.jsonl",
        )
    assert "## Validated Digest Core Opportunities\n- None." in brief
    assert "## Live Confirmation Gated Candidates" in brief
    assert "source_only_narrative_without_market_confirmation" in brief
    assert "verdict=exploratory source=core_opportunity_merge" in brief


def test_integrated_radar_outcomes_and_calibration_are_research_only():
    import json

    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar
    import crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes as event_integrated_radar_outcomes

    with TemporaryDirectory() as tmp:
        context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=tmp,
            artifact_namespace="integrated_outcomes",
        )
        event_integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        rows = event_integrated_radar_outcomes.fill_integrated_radar_outcomes(
            context.namespace_dir,
            observed_at="2026-06-16T16:00:00Z",
        )
        by_symbol = {row["symbol"]: row for row in rows}
        assert by_symbol["TESTLIST"]["synthetic_diagnostic_label"] == "early_good"
        assert by_symbol["TESTPERP"]["synthetic_diagnostic_label"] == "continuation_good"
        assert by_symbol["TESTFADE"]["synthetic_diagnostic_label"] == "fade_review_good"
        assert by_symbol["TESTUNLOCK"]["synthetic_diagnostic_label"] == "risk_validated"
        assert by_symbol["BTC"]["synthetic_diagnostic_label"] == "remained_noise"
        assert by_symbol["TESTRUMOR"]["synthetic_diagnostic_label"] == "remained_noise"
        assert all(row["outcome_label"] == "inconclusive" for row in rows)
        assert all(row["calibration_eligible"] is False for row in rows)
        assert by_symbol["TESTFADE"]["primary_horizon_return"] < 0
        assert by_symbol["TESTFADE"]["thesis_direction"] == "downside_or_risk_research"
        assert by_symbol["TESTFADE"]["thesis_primary_move"] > 0
        assert by_symbol["TESTFADE"]["thesis_favorable_excursion"] > 0
        assert "asset fell" in by_symbol["TESTFADE"]["thesis_outcome_interpretation"]
        assert by_symbol["TESTUNLOCK"]["primary_horizon_return"] < 0
        assert by_symbol["TESTUNLOCK"]["thesis_direction"] == "downside_or_risk_research"
        assert by_symbol["TESTUNLOCK"]["thesis_primary_move"] > 0
        assert all(row["research_only"] is True for row in rows)
        assert all(row["normal_rsi_signal_written"] is False for row in rows)
        assert all(row["triggered_fade_created"] is False for row in rows)
        assert all(row["paper_trade_created"] is False for row in rows)
        report = (context.namespace_dir / "event_integrated_radar_outcome_report.md").read_text(encoding="utf-8")
        assert "Event Alpha Integrated Radar Outcome Report" in report
        assert "No trades or paper trades" in report
        assert "Non-authoritative rows excluded from calibration" in report
        assert "synthetic_fixture" in report
        priors = json.loads((context.namespace_dir / "event_integrated_radar_calibration_priors.json").read_text(encoding="utf-8"))
        assert priors["auto_apply"] is False
        assert "EARLY_LONG_RESEARCH" in priors["opportunity_type_priors"]
        assert "validated_count" in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        assert "invalidated_count" in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        assert "validation_rate" in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        assert "useful" not in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        assert "junk" not in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        assert "legacy_aliases" in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        calibration = (context.namespace_dir / "event_integrated_radar_calibration_report.md").read_text(encoding="utf-8")
        assert "Non-authoritative rows excluded from calibration" in calibration
        assert "Calibration exclusion reasons" in calibration
        assert " junk" not in calibration.casefold()
