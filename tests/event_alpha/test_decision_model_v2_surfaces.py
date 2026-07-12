"""Focused propagation tests for Crypto Radar Decision Model v2 surfaces."""

from __future__ import annotations

from pathlib import Path


def _market_led_candidate(**overrides):
    row = {
        "schema_version": 1,
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "candidate-v2",
        "core_opportunity_id": "core-v2",
        "alert_key": "candidate-v2",
        "asset_symbol": "V2",
        "asset_coin_id": "v2-coin",
        "symbol": "V2",
        "coin_id": "v2-coin",
        "canonical_asset_id": "v2-coin",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.95,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "event_name": "Fresh liquid breakout",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "market_state_class": "confirmed_breakout",
        "market_anomaly_bucket": "high_liquidity_breakout",
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "return_24h": 20.0,
            "relative_return_vs_btc_4h": 8.0,
            "volume_zscore_24h": 3.0,
            "volume_to_market_cap": 0.25,
            "liquidity_usd": 10_000_000,
            "spread_bps": 20.0,
            "freshness_status": "fresh",
        },
        "source_pack": "market_anomaly_pack",
        "decision_model_version": "crypto_radar_decision_model_v2",
        "decision_model_enabled": True,
        "thesis_origin": "market_led",
        "primary_thesis_origin": "market_led",
        "thesis_origins": ["market_led"],
        "directional_bias": "long",
        "catalyst_status": "unknown",
        "confidence_band": "actionable",
        "timing_state": "active",
        "tradability_status": "good",
        "spread_status": "verified_good",
        "radar_route": "actionable_watch",
        "radar_route_reason": "fresh_liquid_market_structure",
        "radar_actionable": True,
        "actionability_score": 84.0,
        "evidence_confidence_score": 61.0,
        "risk_score": 38.0,
        "urgency_score": 74.0,
        "market_phase": "breakout",
        "preferred_horizon": "1d_3d",
        "expires_at": "2026-06-16T16:00:00+00:00",
        "chase_risk_score": 31.0,
        "actionability_score_components": {"liquidity": 20, "relative_move": 18},
        "actionability_penalty_components": {"unknown_catalyst": 5},
        "evidence_confidence_score_components": {"market_evidence": 42},
        "risk_score_components": {"manipulation_risk": 10},
        "decision_hard_blockers": (),
        "decision_soft_penalties": ("unknown_catalyst",),
        "decision_missing_data": ("derivatives",),
        "decision_warnings": ("unknown_catalyst", "manipulation_risk_review"),
        "why_still_worth_reviewing": ("fresh liquid breakout with relative strength",),
        "radar_what_confirms": ("continued volume-backed follow-through",),
        "radar_what_invalidates": ("failed breakout and mean reversion",),
        "anomaly_type": "high_liquidity_breakout",
        "research_only": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    row.update(overrides)
    return row


def test_v2_fields_propagate_to_core_and_alert_reconciliation_without_legacy_promotion():
    from crypto_rsi_scanner.event_alpha.artifacts.alert_store import (
        reconcile_alert_snapshot_with_core_store,
    )
    from crypto_rsi_scanner.event_alpha.radar.core.merge import _apply_integrated_candidate_truth
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values
    from crypto_rsi_scanner.event_alpha.radar.market_reaction import (
        MarketReactionResult,
        MarketStateSnapshot,
    )

    candidate = _market_led_candidate()
    reaction = MarketReactionResult(
        market_state_snapshot=MarketStateSnapshot(),
        market_state="no_reaction",
        opportunity_type="UNCONFIRMED_RESEARCH",
        why_now="generic fallback",
    )
    core = _apply_integrated_candidate_truth(
        {}, primary=candidate, all_rows=(candidate,), reaction=reaction
    )

    assert core["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert core["radar_route"] == "actionable_watch"
    assert core["radar_actionable"] is True
    assert core["actionability_penalty_components"]["catalyst_unknown"] > 0
    assert core.get("normal_rsi_signal_written") is not True
    assert core.get("triggered_fade_created") is not True

    reconciled = reconcile_alert_snapshot_with_core_store(
        {"alert_id": "alert-v2", "route": "STORE_ONLY"},
        {
            **core,
            "symbol": "V2",
            "coin_id": "v2-coin",
            "final_route_after_quality_gate": "STORE_ONLY",
            "final_opportunity_level": "local_only",
            "final_state_after_quality_gate": "RADAR",
        },
    )
    assert reconciled["radar_route"] == "actionable_watch"
    assert reconciled["actionability_score"] == core["actionability_score"]
    assert reconciled["catalyst_status"] == "unknown"
    assert decision_model_values({"opportunity_type": "CONFIRMED_LONG_RESEARCH"}) == {}
    assert decision_model_values({**candidate, "decision_model_enabled": "true"}) == {}
    assert decision_model_values({**candidate, "decision_model_enabled": None}) == {}
    assert decision_model_values({**candidate, "decision_model_version": "future"}) == {}


def test_v2_projection_preserves_explicit_empty_contract_fields_and_one_authority():
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values

    canonical = _market_led_candidate(
        actionability_penalty_components={},
        decision_hard_blockers=[],
        decision_soft_penalties=[],
        decision_missing_data=[],
    )
    unversioned_override = {
        "radar_actionable": False,
        "radar_route": "diagnostic",
        "actionability_score": 1.0,
        "decision_hard_blockers": ["legacy_override"],
    }

    projected = decision_model_values(canonical, unversioned_override)

    assert projected["radar_actionable"] is True
    assert projected["radar_route"] == "actionable_watch"
    assert projected["actionability_score"] == 84.0
    assert projected["actionability_penalty_components"] == {}
    assert projected["decision_hard_blockers"] == []
    assert projected["decision_soft_penalties"] == []
    assert projected["decision_missing_data"] == []

    disabled_root = {
        **canonical,
        "decision_model_enabled": False,
        "score_components": canonical,
    }
    malformed_root = {
        **canonical,
        "radar_actionable": False,
        "score_components": canonical,
    }
    assert decision_model_values(disabled_root) == {}
    assert decision_model_values(malformed_root) == {}
    assert decision_model_values(malformed_root, canonical) == {}


def test_v2_projection_remains_backward_compatible_before_contract_extension():
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values

    extended_fields = {
        "primary_thesis_origin",
        "thesis_origins",
        "spread_status",
        "urgency_score",
        "market_phase",
        "preferred_horizon",
        "expires_at",
        "chase_risk_score",
    }
    historical = {
        key: value
        for key, value in _market_led_candidate().items()
        if key not in extended_fields
    }

    projected = decision_model_values(historical)

    assert projected["decision_model_version"] == "crypto_radar_decision_model_v2"
    assert projected["radar_route"] == "actionable_watch"
    assert projected["thesis_origin"] == "market_led"
    assert "primary_thesis_origin" not in projected


def test_v2_projection_preserves_source_safety_attestations_and_diagnostic_aggregate():
    from crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes import (
        _performance_observation_rows,
    )
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values

    diagnostic = _market_led_candidate(
        confidence_band="diagnostic",
        tradability_status="blocked",
        radar_route="diagnostic",
        radar_route_reason="source_safety_failed",
        radar_actionable=False,
        decision_hard_blockers=["secret_safety_failed"],
        decision_source_secret_safety_failed=True,
    )

    projected = decision_model_values(diagnostic)
    rows = _performance_observation_rows(
        Path("."),
        candidates=[diagnostic],
        core_rows=[],
        outcome_rows=[],
        delivery_rows=[],
        generated_at="2026-06-20T00:00:00+00:00",
        stale_after_days=14,
    )

    assert projected["decision_source_secret_safety_failed"] is True
    assert rows[0]["radar_route"] == "diagnostic"
    assert rows[0]["include_in_main_aggregate"] is False


def test_v2_projection_fails_closed_on_malformed_actionable_route():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import validate_contract
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
        decision_preview_lane,
        group_decision_rows,
    )

    malformed = _market_led_candidate(
        radar_actionable=False,
        confidence_band="diagnostic",
        tradability_status="blocked",
        decision_hard_blockers=["canonical_asset_identity_untrusted"],
    )

    errors = validate_contract(malformed)
    assert "decision_model_watch_route_not_actionable" in errors
    assert "decision_model_hard_blocker_non_diagnostic_route" in errors
    assert decision_model_values(malformed) == {}
    assert decision_preview_lane(malformed) == "decision_diagnostic"
    assert all(not rows for rows in group_decision_rows([malformed]).values())
    diagnostic = group_decision_rows([malformed], include_diagnostics=True)
    assert diagnostic["decision_diagnostic"] == [malformed]


def test_cards_daily_brief_and_preview_render_v2_transparently_and_no_send():
    from crypto_rsi_scanner.event_alpha.artifacts.research_cards import render_research_card
    from crypto_rsi_scanner.event_alpha.radar.integrated_radar import (
        build_integrated_notification_delivery_rows,
        format_integrated_daily_brief,
        format_integrated_notification_preview_from_deliveries,
    )

    candidate = _market_led_candidate()
    diagnostic = _market_led_candidate(
        candidate_id="diagnostic-v2",
        alert_key="diagnostic-v2",
        symbol="DIAG",
        coin_id="diag",
        asset_symbol="DIAG",
        asset_coin_id="diag",
        opportunity_type="DIAGNOSTIC",
        radar_route="diagnostic",
        radar_actionable=False,
        confidence_band="diagnostic",
    )
    card = render_research_card("candidate-v2", alert_rows=(candidate,))
    assert card.found is True
    for text in (
        "## Crypto Radar Decision",
        "Radar actionable: true",
        "Actionability components: liquidity=20; relative_move=18",
        "Actionability penalties: unknown_catalyst=5",
        "Evidence-confidence components: market_evidence=42",
        "Risk components: manipulation_risk=10",
        "Missing data: derivatives",
        "Why this is still worth human review: fresh liquid breakout with relative strength",
        "Catalyst unknown:",
        "Higher manipulation risk:",
        "Research idea, not a trade instruction.",
    ):
        assert text in card.markdown
    assert "['fresh liquid breakout" not in card.markdown

    deliveries = build_integrated_notification_delivery_rows((candidate, diagnostic))
    by_lane = {row["lane"]: row for row in deliveries}
    assert deliveries[0]["lane"] == "high_confidence"
    assert deliveries[1]["lane"] == "actionable"
    assert next(
        index for index, row in enumerate(deliveries) if row["lane"] == "unconfirmed_research"
    ) > next(index for index, row in enumerate(deliveries) if row["lane"] == "actionable")
    assert "unconfirmed_research" in by_lane
    assert "actionable" in by_lane
    assert "decision_diagnostic" not in by_lane
    assert by_lane["source_provider_health"]["skipped_item_count"] >= 1
    assert all(row["sent"] is False for row in deliveries)
    assert all(row["no_send_rehearsal"] is True for row in deliveries)

    brief = format_integrated_daily_brief(
        (candidate, diagnostic), delivery_rows=deliveries
    )
    preview = format_integrated_notification_preview_from_deliveries(
        deliveries, candidates=(candidate, diagnostic)
    )
    assert "## Actionable Ideas" in brief
    assert "## High-Confidence Ideas" in brief
    assert "## Rapid Market Anomalies" in brief
    assert "## Dashboard Watch" in brief
    assert "## Fade / Exhaustion Review" in brief
    assert "## Risk Watch" in brief
    assert "## Calendar / Scheduled Risk" in brief
    assert "Crypto Radar v2: route=actionable_watch" in brief
    assert "## Lane: Actionable Ideas" in preview
    assert "Catalyst unknown:" in preview
    assert "Higher manipulation risk:" in preview
    assert "Research idea, not a trade instruction." in preview
    assert "send_attempted: false" in preview
    assert "delivered: false" in preview


def test_v2_outcomes_inbox_and_feedback_keep_decision_context(tmp_path: Path):
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
    from crypto_rsi_scanner.event_alpha.notifications.inbox.builder import _inbox_item
    from crypto_rsi_scanner.event_alpha.notifications.inbox.render import _append_item_section
    from crypto_rsi_scanner.event_alpha.outcomes.feedback_labels import (
        EventFeedbackConfig,
        load_feedback,
        mark_feedback,
        valid_labels,
    )
    from crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes import (
        _outcome_row,
        write_integrated_radar_outcome_placeholders,
    )

    candidate = _market_led_candidate(
        symbol="TESTPERP",
        asset_symbol="TESTPERP",
        opportunity_type="CONFIRMED_LONG_RESEARCH",
    )
    outcome = _outcome_row(candidate, now="2026-06-15T17:00:00Z")
    assert outcome["thesis_origin"] == "market_led"
    assert outcome["catalyst_status"] == "unknown"
    assert outcome["confidence_band"] == "actionable"
    assert outcome["primary_thesis_origin"] == "market_led"
    assert outcome["thesis_origins"] == ["market_led"]
    assert outcome["market_phase"] == "breakout"
    assert outcome["evidence_confidence_score_cohort"] == "45_64"
    assert outcome["risk_score_cohort"] == "25_44"
    assert outcome["actionability_score_cohort"] == "70_84"
    assert outcome["anomaly_type"] == "high_liquidity_breakout"
    assert outcome["normal_rsi_signal_written"] is False
    assert outcome["triggered_fade_created"] is False

    placeholder_candidate = {
        **candidate,
        "run_id": "decision-v2-run",
        "profile": "fixture",
        "artifact_namespace": "decision_v2",
        "observed_at": "2026-06-15T16:00:00+00:00",
    }
    placeholders = write_integrated_radar_outcome_placeholders(
        tmp_path,
        (placeholder_candidate,),
        observed_at="2026-06-15T16:01:00+00:00",
    )
    assert len(placeholders) == 1
    assert placeholders[0]["outcome_data_source"] == "pending_observation"
    assert placeholders[0]["outcome_status"] == "pending"
    assert placeholders[0]["automatic_outcome"] is True
    assert placeholders[0]["human_preference_feedback"] is None
    assert placeholders[0]["calibration_eligible"] is False
    assert placeholders[0]["normal_rsi_signal_written"] is False
    assert placeholders[0]["triggered_fade_created"] is False
    assert schema_v1.validate_row_against_schema(
        placeholders[0], "outcome_row_v1"
    ) == []

    item = _inbox_item(candidate, None, {}, set(), {})
    assert item.radar_route == "actionable_watch"
    assert item.primary_thesis_origin == "market_led"
    assert item.thesis_origins == ("market_led",)
    assert item.spread_status == "verified_good"
    assert item.urgency_score == 74.0
    assert item.market_phase == "breakout"
    assert item.preferred_horizon == "1d_3d"
    assert item.chase_risk_score == 31.0
    assert item.actionability_score == 84.0
    assert item.why_still_worth_reviewing == (
        "fresh liquid breakout with relative strength",
    )
    lines: list[str] = []
    _append_item_section(lines, "v2", (item,), profile="fixture")
    rendered = "\n".join(lines)
    assert "feedback_manipulation_risk" in rendered
    assert "radar_timing: phase=breakout" in rendered
    assert "feedback_missing_confirmation" in rendered
    assert "feedback_late" in rendered
    assert "feedback_useful" in rendered

    assert {"useful", "late", "manipulation_risk", "missing_confirmation"} <= set(valid_labels())
    cfg = EventFeedbackConfig(tmp_path / "feedback.jsonl")
    marked = mark_feedback(
        "core-v2",
        "manipulation_risk",
        cfg=cfg,
        context_rows=(candidate,),
    )
    assert marked.radar_route == "actionable_watch"
    assert marked.actionability_score == 84.0
    assert marked.why_still_worth_reviewing == (
        "fresh liquid breakout with relative strength",
    )
    loaded = load_feedback(cfg.path).records
    assert loaded[0].label == "manipulation_risk"
    assert loaded[0].decision_missing_data == ("derivatives",)


def test_canonical_daily_brief_v2_preview_is_explicit_and_config_gated():
    from unittest.mock import patch

    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.event_alpha.artifacts.daily_brief import build_daily_brief

    candidate = _market_led_candidate()
    diagnostic = _market_led_candidate(
        candidate_id="diagnostic-v2",
        core_opportunity_id="diagnostic-core-v2",
        alert_key="diagnostic-v2",
        symbol="DIAG",
        coin_id="diag",
        asset_symbol="DIAG",
        asset_coin_id="diag",
        event_name="Explicit v2 diagnostic",
        radar_route="diagnostic",
        radar_actionable=False,
        confidence_band="diagnostic",
    )
    legacy = {
        **candidate,
        "candidate_id": "legacy-row",
        "core_opportunity_id": "legacy-core",
        "symbol": "LEGACY",
        "coin_id": "legacy",
        "asset_symbol": "LEGACY",
        "asset_coin_id": "legacy",
        "decision_model_version": None,
        "decision_model_enabled": None,
    }

    with patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED", False):
        disabled = build_daily_brief(
            core_opportunity_rows=(candidate, diagnostic, legacy),
            include_api_artifacts=True,
        )
    assert "Crypto Radar Decision Model v2 Preview" not in disabled

    with (
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED", True),
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_SHOW_DIAGNOSTICS", True),
    ):
        default_hidden = build_daily_brief(
            core_opportunity_rows=(candidate, diagnostic, legacy),
            include_diagnostics=False,
            include_api_artifacts=True,
        )
    assert "## Crypto Radar Decision Model v2 Preview" in default_hidden
    assert "### Actionable Ideas" in default_hidden
    assert "### High-Confidence Ideas" in default_hidden
    assert "### Rapid Market Anomalies" in default_hidden
    assert "### Dashboard Watch" in default_hidden
    assert "### Fade / Exhaustion Review" in default_hidden
    assert "### Risk Watch" in default_hidden
    assert "### Calendar / Scheduled Risk" in default_hidden
    assert "Actionability components: liquidity=20; relative_move=18" in default_hidden
    assert "Actionability penalties: unknown_catalyst=5" in default_hidden
    assert "Evidence-confidence components: market_evidence=42" in default_hidden
    assert "Risk components: manipulation_risk=10" in default_hidden
    assert "Catalyst unknown:" in default_hidden
    assert "Research idea, not a trade instruction." in default_hidden
    assert "#### DIAG/diag" not in default_hidden
    assert "#### LEGACY/legacy" not in default_hidden

    with (
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED", True),
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_SHOW_DIAGNOSTICS", True),
    ):
        diagnostics = build_daily_brief(
            core_opportunity_rows=(candidate, diagnostic, legacy),
            include_diagnostics=True,
            include_api_artifacts=True,
        )
    assert "### Decision Diagnostics" in diagnostics
    assert "#### DIAG/diag - Explicit v2 diagnostic" in diagnostics
    assert "#### LEGACY/legacy" not in diagnostics

    with (
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_PREVIEW_ENABLED", True),
        patch.object(config, "EVENT_ALPHA_DECISION_MODEL_V2_SHOW_DIAGNOSTICS", False),
    ):
        config_hidden = build_daily_brief(
            core_opportunity_rows=(candidate, diagnostic),
            include_diagnostics=True,
            include_api_artifacts=True,
        )
    assert "### Decision Diagnostics" not in config_hidden


def test_feedback_report_cohorts_only_explicit_v2_rows(tmp_path: Path):
    from dataclasses import replace

    from crypto_rsi_scanner.event_alpha.outcomes.feedback_labels import (
        EventFeedbackConfig,
        EventFeedbackReadResult,
        format_feedback_report,
        mark_feedback,
    )

    record = mark_feedback(
        "core-v2",
        "useful",
        cfg=EventFeedbackConfig(tmp_path / "feedback.jsonl"),
        context_rows=(_market_led_candidate(),),
    )
    legacy = replace(
        record,
        feedback_id="legacy-feedback",
        target="legacy-core",
        decision_model_version=None,
        decision_model_enabled=None,
        thesis_origin="catalyst_led",
        catalyst_status="confirmed",
        confidence_band="high_confidence",
        actionability_score_cohort="85_100",
        anomaly_type="legacy_should_not_count",
        label="junk",
    )
    report = format_feedback_report(EventFeedbackReadResult(
        path=tmp_path / "feedback.jsonl",
        rows_read=2,
        records=[record, legacy],
    ))
    cohort_section = report.split(
        "Crypto Radar Decision Model v2 feedback cohorts (explicit v2 rows only):",
        1,
    )[1]
    assert "- explicit_v2_rows: 1" in cohort_section
    assert "- thesis_origin:\n  - market_led: rows=1 labels=useful=1" in cohort_section
    assert "- catalyst_status:\n  - unknown: rows=1 labels=useful=1" in cohort_section
    assert "- confidence_band:\n  - actionable: rows=1 labels=useful=1" in cohort_section
    assert "- actionability_score_cohort:\n  - 70_84: rows=1 labels=useful=1" in cohort_section
    assert "- anomaly_type:\n  - high_liquidity_breakout: rows=1 labels=useful=1" in cohort_section
    assert "catalyst_led" not in cohort_section
    assert "legacy_should_not_count" not in cohort_section
