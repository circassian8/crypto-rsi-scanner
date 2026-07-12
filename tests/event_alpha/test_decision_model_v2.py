"""Focused Crypto Radar Decision Model v2 regressions."""

from __future__ import annotations

from copy import deepcopy

from crypto_rsi_scanner.event_alpha.radar import decision_model


def _market_led_candidate(**overrides):
    row = {
        "row_type": "event_integrated_radar_candidate",
        "symbol": "MOVE",
        "coin_id": "move-token",
        "canonical_asset_id": "move-token",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.95,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "source_origin": "market_anomaly",
        "source_origins": ["market_anomaly"],
        "source_pack": "market_anomaly_pack",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "final_route_after_quality_gate": "STORE_ONLY",
        "market_state_class": "confirmed_breakout",
        "market_anomaly_bucket": "high_liquidity_breakout",
        "research_only": True,
        "created_alert": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "return_24h": 20.0,
            "relative_return_vs_btc_4h": 9.0,
            "volume_zscore_24h": 3.5,
            "volume_to_market_cap": 0.30,
            "liquidity_usd": 12_000_000,
            "spread_bps": 22.0,
            "freshness_status": "fresh",
        },
    }
    for key, value in overrides.items():
        if key == "market_state_snapshot":
            row[key] = {**row[key], **value}
        else:
            row[key] = value
    return row


def test_market_led_unknown_catalyst_is_actionable_with_soft_penalty():
    row = _market_led_candidate()

    result = decision_model.evaluate_radar_decision(row)

    assert result.decision_model_version == decision_model.DECISION_MODEL_VERSION
    assert result.thesis_origin == "market_led"
    assert result.directional_bias == "long"
    assert result.catalyst_status == "unknown"
    assert result.confidence_band == "actionable"
    assert result.tradability_status == "good"
    assert result.radar_route == "actionable_watch"
    assert result.radar_actionable is True
    assert result.decision_hard_blockers == ()
    assert "catalyst_unknown_soft_penalty" in result.decision_soft_penalties
    assert result.actionability_penalty_components["catalyst_unknown"] > 0
    assert "market_strength" in result.actionability_score_components
    assert "catalyst_clarity" in result.evidence_confidence_components
    assert "manipulation_risk" in result.risk_score_components
    assert any("not a trade instruction" in warning for warning in result.decision_warnings)


def test_unknown_catalyst_lowers_evidence_confidence_without_hard_block():
    unknown = decision_model.evaluate_radar_decision(_market_led_candidate())
    confirmed_row = _market_led_candidate(
        source_origin="official_exchange",
        source_origins=["official_exchange"],
        source_pack="official_exchange_listing_pack",
        source_class="official_exchange",
        source_strength="official_structured",
        accepted_evidence_count=1,
        latest_source_url="https://example.invalid/listing",
        latest_source_title="Official listing notice",
        official_exchange_event={
            "event_type": "spot_listing",
            "source_url": "https://example.invalid/listing",
            "title": "Official listing notice",
        },
    )
    confirmed = decision_model.evaluate_radar_decision(confirmed_row)

    assert unknown.catalyst_status == "unknown"
    assert unknown.decision_hard_blockers == ()
    assert unknown.radar_actionable is True
    assert confirmed.catalyst_status == "confirmed"
    assert confirmed.thesis_origin == "catalyst_led"
    assert confirmed.evidence_confidence_score > unknown.evidence_confidence_score
    assert confirmed.radar_route == "high_confidence_watch"
    assert confirmed.confidence_band == "high_confidence"


def test_suspicious_illiquid_move_is_diagnostic_and_high_risk():
    row = _market_led_candidate(
        market_state_class="suspicious_illiquid_move",
        market_anomaly_bucket="low_liquidity_suspicious",
        market_state_snapshot={"liquidity_usd": 18_000, "spread_bps": 300},
    )

    result = decision_model.evaluate_radar_decision(row)

    assert result.radar_route == "diagnostic"
    assert result.confidence_band == "diagnostic"
    assert result.tradability_status == "blocked"
    assert result.radar_actionable is False
    assert "suspicious_illiquid_move" in result.decision_hard_blockers
    assert "liquidity_below_minimum" in result.decision_hard_blockers
    assert "spread_above_maximum" in result.decision_hard_blockers
    assert result.risk_score >= 85


def test_stale_market_snapshot_is_a_hard_blocker():
    row = _market_led_candidate(market_state_snapshot={"freshness_status": "stale"})

    result = decision_model.evaluate_radar_decision(row)

    assert result.timing_state == "stale"
    assert result.radar_route == "diagnostic"
    assert result.radar_actionable is False
    assert "market_data_stale" in result.decision_hard_blockers


def test_market_led_missing_freshness_or_volume_cannot_be_actionable():
    missing_freshness = _market_led_candidate(
        market_state_snapshot={"freshness_status": ""}
    )
    missing_volume = _market_led_candidate()
    missing_volume["market_state_snapshot"].pop("volume_zscore_24h")
    missing_volume["market_state_snapshot"].pop("volume_to_market_cap")

    freshness_result = decision_model.evaluate_radar_decision(missing_freshness)
    volume_result = decision_model.evaluate_radar_decision(missing_volume)

    assert freshness_result.radar_actionable is False
    assert freshness_result.radar_route == "diagnostic"
    assert "market_data_freshness_unverified" in freshness_result.decision_hard_blockers
    assert volume_result.radar_actionable is False
    assert "market_turnover_unverified" in volume_result.decision_soft_penalties


def test_market_led_missing_spread_is_not_tradable_or_actionable():
    row = _market_led_candidate()
    row["market_state_snapshot"].pop("spread_bps")

    result = decision_model.evaluate_radar_decision(row)

    assert result.tradability_status == "poor"
    assert result.radar_actionable is False
    assert "spread_bps" in result.decision_missing_data


def test_acceptable_wide_spread_emits_higher_manipulation_warning():
    result = decision_model.evaluate_radar_decision(
        _market_led_candidate(market_state_snapshot={"spread_bps": 120.0})
    )

    assert result.tradability_status == "acceptable"
    assert result.risk_score_components["manipulation_risk"] >= 50
    assert any("Higher manipulation risk" in warning for warning in result.decision_warnings)


def test_market_led_missing_return_unit_is_a_hard_blocker():
    row = _market_led_candidate()
    row["market_state_snapshot"].pop("return_unit")

    result = decision_model.evaluate_radar_decision(row)

    assert result.radar_actionable is False
    assert "market_return_unit_missing" in result.decision_hard_blockers


def test_symbol_fallback_cannot_satisfy_strict_canonical_identity():
    result = decision_model.evaluate_radar_decision(
        _market_led_candidate(instrument_identity_trusted=False)
    )

    assert result.radar_actionable is False
    assert "canonical_asset_identity_untrusted" in result.decision_hard_blockers


def test_late_momentum_route_depends_on_derivatives_crowding():
    late = _market_led_candidate(
        market_state_class="late_momentum",
        market_anomaly_bucket="late_momentum_needs_crowding_check",
    )
    without_derivatives = decision_model.evaluate_radar_decision(late)
    with_derivatives = decision_model.evaluate_radar_decision({
        **late,
        "crowding_class": "high",
        "crowding_exhaustion_evidence": ["funding_zscore_elevated"],
        "derivatives_state_snapshot": {
            "freshness_status": "fresh",
            "funding_zscore": 3.0,
        },
    })

    assert without_derivatives.directional_bias == "fade_short_review"
    assert without_derivatives.radar_route == "rapid_market_anomaly"
    assert with_derivatives.directional_bias == "fade_short_review"
    assert with_derivatives.radar_route == "fade_exhaustion_review"


def test_specific_blowoff_anomaly_sets_exhausted_timing_over_shared_bucket():
    result = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            anomaly_type="blowoff_crowded",
            market_anomaly_bucket="late_momentum_needs_crowding_check",
        )
    )

    assert result.timing_state == "exhausted"


def test_selloff_risk_routes_to_calendar_risk():
    row = _market_led_candidate(
        market_state_class="risk_off_sell_pressure",
        market_anomaly_bucket="selloff_risk",
        market_state_snapshot={"return_4h": -8.0, "return_24h": -15.0},
    )

    result = decision_model.evaluate_radar_decision(row)

    assert result.directional_bias == "risk"
    assert result.radar_route == "calendar_risk"


def test_thresholds_are_configurable_without_runtime_config_fields():
    row = _market_led_candidate()
    strict = decision_model.RadarDecisionConfig(actionability_threshold=99.0)
    result = decision_model.evaluate_radar_decision(row, cfg=strict)

    assert result.actionability_score < strict.actionability_threshold
    assert result.radar_actionable is False
    assert result.radar_route == "diagnostic"


def test_actionability_is_not_implicitly_blocked_by_low_evidence_confidence():
    result = decision_model.evaluate_radar_decision(
        _market_led_candidate(source_strength="weak", source_class="unknown")
    )

    assert result.evidence_confidence_score < 60
    assert result.actionability_score >= 70
    assert result.radar_actionable is True


def test_new_routes_and_origin_lanes_are_independently_configurable():
    late = _market_led_candidate(
        market_state_class="late_momentum",
        market_anomaly_bucket="late_momentum_needs_crowding_check",
    )
    route_off = decision_model.evaluate_radar_decision(
        late,
        cfg=decision_model.RadarDecisionConfig(rapid_anomaly_route_enabled=False),
    )
    lane_off = decision_model.evaluate_radar_decision(
        late,
        cfg=decision_model.RadarDecisionConfig(market_led_enabled=False),
    )

    assert route_off.radar_route == "diagnostic"
    assert route_off.radar_actionable is False
    assert route_off.radar_route_reason == "rapid_market_anomaly_route_disabled"
    assert lane_off.radar_route == "diagnostic"
    assert lane_off.radar_actionable is False
    assert lane_off.radar_route_reason == "market_led_route_disabled"


def test_high_confidence_threshold_is_authoritative_for_confirmed_catalyst():
    row = _market_led_candidate(
        source_origin="official_exchange",
        source_origins=["official_exchange"],
        source_pack="official_exchange_listing_pack",
        source_class="official_exchange",
        source_strength="official_structured",
        accepted_evidence_count=1,
        latest_source_url="https://example.invalid/listing",
        latest_source_title="Official listing notice",
        official_exchange_event={
            "event_type": "spot_listing",
            "source_url": "https://example.invalid/listing",
            "title": "Official listing notice",
        },
    )
    strict = decision_model.RadarDecisionConfig(high_confidence_threshold=99.0)

    result = decision_model.evaluate_radar_decision(row, cfg=strict)

    assert result.radar_actionable is True
    assert result.actionability_score < strict.high_confidence_threshold
    assert result.confidence_band == "actionable"
    assert result.radar_route == "actionable_watch"


def test_confirmed_catalyst_missing_source_metadata_is_softly_penalized():
    complete = _market_led_candidate(
        source_origin="official_exchange",
        source_origins=["official_exchange"],
        source_pack="official_exchange_listing_pack",
        source_class="official_exchange",
        source_strength="official_structured",
        accepted_evidence_count=1,
        latest_source_url="https://example.invalid/listing",
        latest_source_title="Official listing notice",
        official_exchange_event={
            "event_type": "spot_listing",
            "source_url": "https://example.invalid/listing",
            "title": "Official listing notice",
        },
    )
    incomplete = {
        **complete,
        "latest_source_url": None,
        "latest_source_title": None,
        "event_name": None,
        "official_exchange_event": {"event_type": "spot_listing"},
    }

    complete_result = decision_model.evaluate_radar_decision(complete)
    incomplete_result = decision_model.evaluate_radar_decision(incomplete)

    assert incomplete_result.catalyst_status == "confirmed"
    assert incomplete_result.decision_hard_blockers == ()
    assert "official_source_url_missing" in incomplete_result.decision_soft_penalties
    assert "catalyst_article_title_missing" in incomplete_result.decision_soft_penalties
    assert incomplete_result.evidence_confidence_score < complete_result.evidence_confidence_score


def test_technical_evidence_does_not_invent_a_plausible_catalyst():
    row = _market_led_candidate(
        source_origin="derivatives",
        source_origins=["derivatives"],
        source_pack="derivatives_pack",
        source_class="derivatives",
        accepted_evidence_count=3,
        latest_source_url="https://example.invalid/derivatives",
    )

    result = decision_model.evaluate_radar_decision(row)

    assert result.thesis_origin == "technical_led"
    assert result.catalyst_status == "unknown"
    assert "catalyst_unknown_soft_penalty" in result.decision_soft_penalties


def test_operator_summary_counts_only_explicit_enabled_v2_rows():
    from crypto_rsi_scanner.event_alpha.artifacts import operator_state

    enabled = decision_model.evaluate_radar_decision(_market_led_candidate()).to_dict()
    disabled = {**enabled, "decision_model_enabled": False, "radar_actionable": True}
    wrong_version = {
        **enabled,
        "decision_model_version": "future_decision_model",
        "radar_actionable": True,
    }

    summary = operator_state._decision_model_summary((enabled, disabled, wrong_version))

    assert summary["decision_model_v2_enabled"] is True
    assert summary["actionable_research_ideas"] == 1
    assert summary["radar_route_counts"] == {"actionable_watch": 1}
    assert summary["catalyst_status_counts"] == {"unknown": 1}
    assert summary["tradability_status_counts"] == {"good": 1}

    empty_enabled = operator_state._decision_model_summary((), configured_enabled=True)
    assert empty_enabled["decision_model_v2_enabled"] is True
    assert empty_enabled["decision_model_version"] == decision_model.DECISION_MODEL_VERSION
    assert empty_enabled["decision_model_v2_row_count"] == 0


def test_v2_artifact_schema_accepts_explicit_row_and_rejects_unsafe_promotion():
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    decision = decision_model.evaluate_radar_decision(_market_led_candidate()).to_dict()
    row = {
        **_market_led_candidate(),
        **decision,
        "candidate_id": "candidate-v2-schema",
    }

    assert schema_v1.validate_row_against_schema(row, "integrated_radar_candidate_v1") == []

    malformed = {
        **row,
        "decision_hard_blockers": ["duplicate_family_suppressed"],
        "radar_actionable": True,
    }
    errors = schema_v1.validate_row_against_schema(
        malformed,
        "integrated_radar_candidate_v1",
    )
    assert "decision_model_actionable_with_hard_blocker" in errors

    incomplete = dict(row)
    incomplete.pop("actionability_score_components")
    incomplete.pop("why_still_worth_reviewing")
    incomplete_errors = schema_v1.validate_row_against_schema(
        incomplete,
        "integrated_radar_candidate_v1",
    )
    assert "decision_model_missing_field:actionability_score_components" in incomplete_errors
    assert "decision_model_missing_field:why_still_worth_reviewing" in incomplete_errors


def test_secret_or_side_effect_claim_hard_blocks_v2_research_promotion():
    secret = decision_model.evaluate_radar_decision(
        _market_led_candidate(provider_api_key="not-redacted")
    )
    side_effect = decision_model.evaluate_radar_decision(
        _market_led_candidate(notification_send_enabled=True)
    )

    assert "secret_safety_failed" in secret.decision_hard_blockers
    assert secret.radar_actionable is False
    assert "research_safety_invariant_failed" in side_effect.decision_hard_blockers
    assert side_effect.radar_actionable is False


def test_nested_and_source_row_safety_failures_hard_block_promotion():
    nested = decision_model.evaluate_radar_decision(
        _market_led_candidate(provider_payload={"authorization": "Bearer leaked"})
    )
    source_secret = decision_model.evaluate_radar_decision(
        _market_led_candidate(),
        source_rows=({"provider": "fixture", "api_token": "leaked"},),
    )
    source_send = decision_model.evaluate_radar_decision(
        _market_led_candidate(),
        source_rows=({"notification_send_enabled": True},),
    )
    source_path = decision_model.evaluate_radar_decision(
        _market_led_candidate(),
        source_rows=({"operator_report_path": "/tmp/unsafe.md"},),
    )

    assert "secret_safety_failed" in nested.decision_hard_blockers
    assert "secret_safety_failed" in source_secret.decision_hard_blockers
    assert "research_safety_invariant_failed" in source_send.decision_hard_blockers
    assert "operator_path_safety_failed" in source_path.decision_hard_blockers


def test_final_decision_reevaluation_invalidates_resolution_and_duplicate_changes():
    initial = {
        **_market_led_candidate(),
        **decision_model.evaluate_radar_decision(_market_led_candidate()).to_dict(),
    }
    unresolved = {
        **initial,
        "instrument_resolver_status": "unresolved",
        "instrument_identity_trusted": False,
    }
    duplicate = {**initial, "final_route_after_quality_gate": "SUPPRESS_DUPLICATE"}

    unresolved_result = decision_model.reevaluate_radar_decision_fields(unresolved)
    duplicate_result = decision_model.reevaluate_radar_decision_fields(duplicate)

    assert unresolved_result["radar_actionable"] is False
    assert "canonical_asset_identity_unresolved" in unresolved_result["decision_hard_blockers"]
    assert duplicate_result["radar_actionable"] is False
    assert "duplicate_family_suppressed" in duplicate_result["decision_hard_blockers"]


def test_actionability_score_cohort_boundaries_are_canonical():
    from crypto_rsi_scanner.event_alpha.radar.decision_models import (
        actionability_score_cohort,
    )

    assert {
        score: actionability_score_cohort(score)
        for score in (0, 24.99, 25, 49.99, 50, 69.99, 70, 84.99, 85, 100)
    } == {
        0: "0_24", 24.99: "0_24", 25: "25_49", 49.99: "25_49",
        50: "50_69", 69.99: "50_69", 70: "70_84", 84.99: "70_84",
        85: "85_100", 100: "85_100",
    }


def test_runtime_config_uses_canonical_decision_model_v2_names():
    class RuntimeConfig:
        EVENT_ALPHA_DECISION_MODEL_V2_ENABLED = True
        EVENT_ALPHA_DECISION_MODEL_V2_ACTIONABLE_THRESHOLD = 74
        EVENT_ALPHA_DECISION_MODEL_V2_HIGH_CONFIDENCE_THRESHOLD = 88
        EVENT_ALPHA_DECISION_MODEL_V2_ROUTE_RAPID_MARKET_ANOMALY_ENABLED = False
        EVENT_ALPHA_DECISION_MODEL_V2_MIN_LIQUIDITY_USD = 300_000
        EVENT_ALPHA_DECISION_MODEL_V2_GOOD_LIQUIDITY_USD = 6_000_000
        EVENT_ALPHA_DECISION_MODEL_V2_MAX_SPREAD_BPS = 120
        EVENT_ALPHA_DECISION_MODEL_V2_MIN_VOLUME_ZSCORE = 1.5

    cfg = decision_model.RadarDecisionConfig.from_runtime(RuntimeConfig())

    assert cfg.enabled is True
    assert cfg.actionability_threshold == 74
    assert cfg.high_confidence_threshold == 88
    assert cfg.rapid_anomaly_route_enabled is False
    assert cfg.minimum_liquidity_usd == 300_000
    assert cfg.good_liquidity_usd == 6_000_000
    assert cfg.maximum_spread_bps == 120
    assert cfg.minimum_volume_zscore == 1.5


def test_integrated_hook_preserves_legacy_lane_route_and_safety():
    from crypto_rsi_scanner.event_alpha.radar.integrated_radar import build_integrated_candidates

    source = {
        "row_type": "event_market_anomaly",
        "symbol": "MOVE",
        "coin_id": "move-token",
        "canonical_asset_id": "move-token",
        "market_state": "confirmed_breakout",
        "market_state_class": "confirmed_breakout",
        "anomaly_bucket": "high_liquidity_breakout",
        "market_state_snapshot": deepcopy(_market_led_candidate()["market_state_snapshot"]),
        "source_pack": "market_anomaly_pack",
        "research_only": True,
    }
    rows = build_integrated_candidates(
        sidecar_rows={"market_anomaly": [source]},
        profile="fixture",
        artifact_namespace="decision_model_v2_test",
        run_mode="fixture",
        run_id="decision-model-v2-run",
        observed_at="2026-06-15T16:00:00Z",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["decision_model_version"] == "crypto_radar_decision_model_v2"
    assert row["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert row["route"] == "STORE_ONLY"
    assert row["final_route_after_quality_gate"] == "STORE_ONLY"
    assert row["radar_route"] == "actionable_watch"
    assert row["radar_actionable"] is True
    assert row["created_alert"] is False
    assert row["normal_rsi_signal_written"] is False
    assert row["triggered_fade_created"] is False
    assert row["paper_trade_created"] is False
    assert row["notification_send_enabled"] is False
    assert row["radar_route"] != "triggered_fade"
    assert row["anomaly_type"] == "confirmed_breakout"
    assert row["anomaly_bucket"] == "high_liquidity_breakout"
    assert row["market_anomaly_bucket"] == "high_liquidity_breakout"


def test_integrated_symbol_only_anomaly_cannot_invent_trusted_identity():
    from crypto_rsi_scanner.event_alpha.radar.integrated_radar import build_integrated_candidates

    source = {
        "row_type": "event_market_anomaly",
        "symbol": "COLLIDE",
        "market_state": "confirmed_breakout",
        "market_state_class": "confirmed_breakout",
        "anomaly_bucket": "high_liquidity_breakout",
        "market_state_snapshot": deepcopy(_market_led_candidate()["market_state_snapshot"]),
        "source_pack": "market_anomaly_pack",
        "research_only": True,
    }

    row = build_integrated_candidates(
        sidecar_rows={"market_anomaly": [source]},
        profile="fixture",
        artifact_namespace="decision_model_identity_test",
        run_mode="fixture",
        run_id="decision-model-identity-run",
        observed_at="2026-06-15T16:00:00Z",
    )[0]

    assert row["instrument_identity_trusted"] is False
    assert row["radar_actionable"] is False
    assert row["radar_route"] == "diagnostic"
    assert "canonical_asset_identity_untrusted" in row["decision_hard_blockers"]
    assert row["anomaly_type"] == "confirmed_breakout"
    assert row["anomaly_bucket"] == "high_liquidity_breakout"
    assert row["market_anomaly_bucket"] == "high_liquidity_breakout"
