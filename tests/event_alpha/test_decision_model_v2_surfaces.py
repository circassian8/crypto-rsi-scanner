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
        "directional_bias": "long",
        "catalyst_status": "unknown",
        "confidence_band": "actionable",
        "timing_state": "active",
        "tradability_status": "good",
        "radar_route": "actionable_watch",
        "radar_route_reason": "fresh_liquid_market_structure",
        "radar_actionable": True,
        "actionability_score": 84.0,
        "evidence_confidence_score": 61.0,
        "risk_score": 38.0,
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
    assert "unconfirmed_research" in by_lane
    assert "actionable_market_led" in by_lane
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
    assert "## Actionable Market-Led Ideas" in brief
    assert "## High-Confidence Catalyst Ideas" in brief
    assert "## Rapid Anomalies" in brief
    assert "## Fade / Exhaustion Review" in brief
    assert "## Calendar / Risk" in brief
    assert "Crypto Radar v2: route=actionable_watch" in brief
    assert "## Lane: Actionable Market-Led Ideas" in preview
    assert "Catalyst unknown:" in preview
    assert "Higher manipulation risk:" in preview
    assert "Research idea, not a trade instruction." in preview
    assert "send_attempted: false" in preview
    assert "delivered: false" in preview


def test_v2_outcomes_inbox_and_feedback_keep_decision_context(tmp_path: Path):
    from crypto_rsi_scanner.event_alpha.notifications.inbox.builder import _inbox_item
    from crypto_rsi_scanner.event_alpha.notifications.inbox.render import _append_item_section
    from crypto_rsi_scanner.event_alpha.outcomes.feedback_labels import (
        EventFeedbackConfig,
        load_feedback,
        mark_feedback,
        valid_labels,
    )
    from crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes import _outcome_row

    candidate = _market_led_candidate(
        symbol="TESTPERP",
        asset_symbol="TESTPERP",
        opportunity_type="CONFIRMED_LONG_RESEARCH",
    )
    outcome = _outcome_row(candidate, now="2026-06-15T17:00:00Z")
    assert outcome["thesis_origin"] == "market_led"
    assert outcome["catalyst_status"] == "unknown"
    assert outcome["confidence_band"] == "actionable"
    assert outcome["actionability_score_cohort"] == "70_84"
    assert outcome["anomaly_type"] == "high_liquidity_breakout"
    assert outcome["normal_rsi_signal_written"] is False
    assert outcome["triggered_fade_created"] is False

    item = _inbox_item(candidate, None, {}, set(), {})
    assert item.radar_route == "actionable_watch"
    assert item.actionability_score == 84.0
    assert item.why_still_worth_reviewing == (
        "fresh liquid breakout with relative strength",
    )
    lines: list[str] = []
    _append_item_section(lines, "v2", (item,), profile="fixture")
    rendered = "\n".join(lines)
    assert "feedback_manipulation_risk" in rendered
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
    assert "### Actionable Market-Led Ideas" in default_hidden
    assert "### High-Confidence Catalyst Ideas" in default_hidden
    assert "### Rapid Anomalies" in default_hidden
    assert "### Fade / Exhaustion Review" in default_hidden
    assert "### Calendar / Risk" in default_hidden
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
