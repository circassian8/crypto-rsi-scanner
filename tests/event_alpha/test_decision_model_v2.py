"""Focused Crypto Radar Decision Model v2 regressions."""

from __future__ import annotations

import json
from copy import deepcopy

from crypto_rsi_scanner.event_alpha.radar import decision_model


def _market_led_candidate(**overrides):
    row = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "decision-model-v2-move",
        "observed_at": "2026-06-15T16:00:00Z",
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


def test_decision_sector_and_quote_blockers_require_explicit_semantic_truth():
    false_like = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            is_theme_or_sector="false",
            is_quote_asset="0",
            quote_asset_excluded=2,
            duplicate_suppressed="false",
            is_duplicate=2,
            suppressed_duplicate="off",
        )
    )

    assert "theme_or_sector_control" not in false_like.decision_hard_blockers
    assert "quote_asset_control" not in false_like.decision_hard_blockers
    assert "duplicate_family_suppressed" not in false_like.decision_hard_blockers
    assert false_like.radar_actionable is True

    theme = decision_model.evaluate_radar_decision(
        _market_led_candidate(is_theme_or_sector="true")
    )
    quote = decision_model.evaluate_radar_decision(
        _market_led_candidate(quote_asset_excluded=1)
    )
    duplicate = decision_model.evaluate_radar_decision(
        _market_led_candidate(duplicate_suppressed="yes")
    )

    assert "theme_or_sector_control" in theme.decision_hard_blockers
    assert "quote_asset_control" in quote.decision_hard_blockers
    assert "duplicate_family_suppressed" in duplicate.decision_hard_blockers
    assert theme.radar_actionable is False
    assert quote.radar_actionable is False
    assert duplicate.radar_actionable is False


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


def test_market_led_missing_spread_is_provisional_dashboard_only():
    row = _market_led_candidate()
    row["market_state_snapshot"].pop("spread_bps")

    result = decision_model.evaluate_radar_decision(row)

    assert result.tradability_status == "acceptable"
    assert result.spread_status == "unavailable"
    assert result.radar_actionable is False
    assert result.radar_route == "dashboard_watch"
    assert "spread_unavailable_dashboard_only" in result.decision_soft_penalties
    assert "spread_bps" in result.decision_missing_data
    assert result.urgency_score <= 55.0


def test_invalid_canonical_market_numbers_do_not_borrow_legacy_aliases():
    for invalid in (True, "not-a-number", float("nan"), float("inf")):
        spread_result = decision_model.evaluate_radar_decision(
            _market_led_candidate(
                market_state_snapshot={
                    "spread_bps": invalid,
                    "bid_ask_spread_bps": 22.0,
                }
            )
        )

        assert spread_result.spread_status == "unavailable"
        assert spread_result.radar_route == "dashboard_watch"
        assert spread_result.radar_actionable is False
        assert "spread_bps" in spread_result.decision_missing_data

    liquidity_result = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            market_state_snapshot={
                "liquidity_usd": float("nan"),
                "order_book_depth_2pct": 12_000_000.0,
            }
        )
    )

    assert liquidity_result.tradability_status == "poor"
    assert liquidity_result.radar_actionable is False
    assert "liquidity_usd" in liquidity_result.decision_missing_data


def test_proxy_only_market_evidence_is_score_and_route_capped():
    result = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            market_state_snapshot={
                "market_feature_basis": {
                    "return_4h": "cross_sectional_return_proxy",
                    "return_24h": "provider_24h_volume_proxy",
                    "relative_return_vs_btc_4h": "cross_sectional_proxy",
                    "volume_zscore_24h": "cross_sectional_log_turnover_proxy",
                    "liquidity_usd": "coingecko_total_volume_24h_proxy",
                    "spread_bps": "unavailable",
                },
                "proxy_only_market_features": True,
                "temporal_baseline_status": "warming",
                "market_route_cap": "dashboard_watch",
            }
        )
    )

    assert result.radar_actionable is False
    assert result.radar_route == "dashboard_watch"
    assert result.radar_route_reason == "market_data_quality_limited_to_dashboard"
    assert result.actionability_score <= 64.0
    assert result.evidence_confidence_score <= 55.0
    assert result.risk_score >= 55.0
    assert result.urgency_score <= 45.0
    assert "proxy_only_market_evidence_dashboard_only" in result.decision_soft_penalties
    assert any("proxy-only" in warning for warning in result.decision_warnings)


def test_malformed_market_quality_claims_fail_closed_without_alias_fallback():
    malformed_snapshots = (
        {"proxy_only_market_features": "false"},
        {"market_route_cap": []},
        {"market_route_cap": {"route": "diagnostic"}},
        {"temporal_baseline_status": []},
        {"temporal_baseline_status": {"state": "warming"}},
        {"market_feature_basis": []},
        {"market_data_quality": []},
        {"market_feature_basis": {"volume_zscore_24h": []}},
        {
            "market_route_cap": [],
            "market_data_quality": {"market_route_cap": "dashboard_watch"},
        },
        {"temporal_baseline_status": "boiling"},
    )

    for snapshot in malformed_snapshots:
        result = decision_model.evaluate_radar_decision(
            _market_led_candidate(market_state_snapshot=snapshot)
        )

        assert result.radar_actionable is False
        assert result.radar_route == "diagnostic"
        assert "market_data_quality_invalid" in result.decision_hard_blockers
        assert any(
            "market-data-quality metadata is malformed" in warning
            for warning in result.decision_warnings
        )

    valid_direct = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            market_state_snapshot={
                "proxy_only_market_features": False,
                "market_feature_basis": {
                    "volume_zscore_24h": "temporal_direct",
                    "spread_bps": "direct_execution_quality",
                },
                "temporal_baseline_status": "warm",
            }
        )
    )
    assert valid_direct.radar_actionable is True
    assert valid_direct.radar_route == "actionable_watch"
    assert "market_data_quality_invalid" not in valid_direct.decision_hard_blockers


def test_malformed_market_state_classifications_cannot_create_directional_evidence():
    malformed_values = (
        {"confirmed_breakout": False},
        ["confirmed_breakout"],
        True,
    )
    for value in malformed_values:
        result = decision_model.evaluate_radar_decision(
            _market_led_candidate(
                market_state_class=value,
                market_anomaly_bucket=value,
            )
        )

        assert result.radar_actionable is False
        assert result.radar_route == "diagnostic"
        assert result.directional_bias == "neutral"
        assert "market_state_classification_invalid" in result.decision_hard_blockers

    valid = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            market_state_class="confirmed_breakout",
            market_anomaly_bucket="high_liquidity_breakout",
        )
    )
    assert valid.radar_actionable is True
    assert valid.directional_bias == "long"
    assert "market_state_classification_invalid" not in valid.decision_hard_blockers


def test_malformed_source_classifications_cannot_select_thesis_origin_policy():
    malformed_candidates = (
        {"source_origin": ["official_exchange"], "source_origins": []},
        {"source_origin": {"official_exchange": True}, "source_origins": []},
        {"source_origin": None, "source_origins": {"official_exchange": True}},
        {"source_pack": {"official_exchange_listing_pack": True}},
        {"source_class": {"official_exchange": True}},
        {"source_packs": ["market_anomaly_pack", {"official": True}]},
    )
    for overrides in malformed_candidates:
        result = decision_model.evaluate_radar_decision(
            _market_led_candidate(**overrides)
        )

        assert result.radar_actionable is False
        assert result.radar_route == "diagnostic"
        assert "source_classification_invalid" in result.decision_hard_blockers

    malformed_source_row = decision_model.evaluate_radar_decision(
        _market_led_candidate(),
        source_rows=({"_source_origin": {"official_exchange": True}},),
    )
    assert malformed_source_row.radar_route == "diagnostic"
    assert "source_classification_invalid" in malformed_source_row.decision_hard_blockers

    valid = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            source_origin="market_anomaly",
            source_origins=["market_anomaly"],
            source_pack="market_anomaly_pack",
            source_packs=["market_anomaly_pack"],
            source_class="market_data",
        )
    )
    assert valid.primary_thesis_origin == "market_led"
    assert valid.radar_actionable is True
    assert "source_classification_invalid" not in valid.decision_hard_blockers


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


def test_decision_identity_rejects_non_text_and_invalid_confidence_claims():
    malformed_rows = (
        _market_led_candidate(canonical_asset_id=True),
        _market_led_candidate(canonical_asset_id={"forged": "identity"}),
        _market_led_candidate(symbol=["MOVE"]),
        _market_led_candidate(instrument_resolver_status=["resolved"]),
        _market_led_candidate(instrument_resolver_confidence=True),
        _market_led_candidate(instrument_resolver_confidence="0.95"),
        _market_led_candidate(instrument_resolver_confidence=101.0),
        _market_led_candidate(instrument_identity_trusted="true"),
    )

    for row in malformed_rows:
        result = decision_model.evaluate_radar_decision(row)

        assert result.radar_actionable is False
        assert result.radar_route == "diagnostic"
        assert "canonical_asset_identity_invalid" in result.decision_hard_blockers
        assert "canonical_asset_identity_untrusted" in result.decision_hard_blockers
        assert result.actionability_score_components["asset_identity"] == 0.0
        assert result.evidence_confidence_components["asset_identity"] == 0.0


def test_decision_requires_exact_boolean_tradability() -> None:
    for value in ("false", 0, None, {"forged": "tradability"}):
        result = decision_model.evaluate_radar_decision(
            _market_led_candidate(is_tradable_asset=value)
        )

        assert result.radar_actionable is False
        assert result.radar_route == "diagnostic"
        assert "asset_tradability_unverified" in result.decision_hard_blockers
        assert "canonical_asset_identity_invalid" not in result.decision_hard_blockers
        assert result.actionability_score_components["asset_identity"] == 0.0
        assert result.evidence_confidence_components["asset_identity"] == 0.0

    blocked = decision_model.evaluate_radar_decision(
        _market_led_candidate(is_tradable_asset=False)
    )
    assert "asset_not_tradable" in blocked.decision_hard_blockers
    assert "asset_tradability_unverified" not in blocked.decision_hard_blockers


def test_blank_canonical_identity_retains_typed_coin_id_compatibility() -> None:
    result = decision_model.evaluate_radar_decision(
        _market_led_candidate(canonical_asset_id="")
    )

    assert result.radar_actionable is True
    assert result.radar_route == "actionable_watch"
    assert result.decision_hard_blockers == ()
    assert result.actionability_score_components["asset_identity"] == 95.0
    assert result.evidence_confidence_components["asset_identity"] == 95.0


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
    assert without_derivatives.radar_route == "dashboard_watch"
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


def test_unscheduled_selloff_routes_to_risk_watch():
    row = _market_led_candidate(
        market_state_class="risk_off_sell_pressure",
        market_anomaly_bucket="selloff_risk",
        market_state_snapshot={"return_4h": -8.0, "return_24h": -15.0},
    )

    result = decision_model.evaluate_radar_decision(row)

    assert result.directional_bias == "risk"
    assert result.radar_route == "risk_watch"
    assert result.radar_actionable is False


def test_selloff_with_attached_calendar_event_routes_to_calendar_risk():
    row = _market_led_candidate(
        market_state_class="risk_off_sell_pressure",
        market_anomaly_bucket="selloff_risk",
        market_state_snapshot={"return_4h": -8.0, "return_24h": -15.0},
        unified_calendar_event={
            "event_id": "fomc-window",
            "scheduled_at": "2026-06-15T18:00:00Z",
        },
    )

    result = decision_model.evaluate_radar_decision(row)

    assert result.radar_route == "calendar_risk"
    assert result.radar_actionable is False
    assert result.preferred_horizon == "scheduled_window"


def test_calendar_overlay_adds_bounded_risk_warning_and_expiry_without_bias():
    base_row = _market_led_candidate(observed_at="2026-06-15T16:00:00Z")
    base = decision_model.evaluate_radar_decision(base_row)
    overlaid = decision_model.evaluate_radar_decision({
        **base_row,
        "nearby_calendar_events": [{
            "event_id": "fomc-window",
            "scheduled_at": "2026-06-15T20:00:00Z",
        }],
        "calendar_risk_score_adjustment": 12.0,
        "calendar_context_warning": "FOMC window overlaps the idea horizon.",
        "expires_at": "2026-06-15T19:00:00Z",
    })

    assert base.directional_bias == "long"
    assert overlaid.directional_bias == "long"
    assert overlaid.radar_route == "calendar_risk"
    assert overlaid.risk_score == base.risk_score + 12.0
    assert overlaid.risk_score_components["calendar_risk_adjustment"] == 12.0
    assert overlaid.expires_at == "2026-06-15T19:00:00Z"
    assert "FOMC window overlaps the idea horizon." in overlaid.decision_warnings


def test_validated_rsi_adapter_deltas_adjust_canonical_scores_transparently():
    from crypto_rsi_scanner.event_alpha.radar.rsi_technical_context import (
        apply_rsi_technical_context,
    )

    base_row = _market_led_candidate(
        observed_at="2026-07-12T12:00:00Z",
        directional_bias="long",
        technical_context={"adapter": "rsi"},
    )
    artifact = {
        "symbol": "MOVE",
        "coin_id": "move-token",
        "setup_type": "dip_buy",
        "rsi_daily": 22.0,
        "severity": "ALERT",
        "market_regime": "BULL",
        "conviction": 74,
        "expected_dir": "up",
        "observed_at": "2026-07-12T10:00:00Z",
        "freshness_status": "fresh",
    }
    enriched = apply_rsi_technical_context(
        base_row,
        artifact,
        evaluated_at="2026-07-12T12:00:00Z",
    )
    base = decision_model.evaluate_radar_decision(base_row)
    adjusted = decision_model.evaluate_radar_decision(enriched)

    assert adjusted.primary_thesis_origin == "technical_led"
    assert adjusted.actionability_score == round(
        base.actionability_score + enriched["rsi_actionability_adjustment"],
        2,
    )
    assert adjusted.risk_score == round(base.risk_score + enriched["rsi_risk_adjustment"], 2)
    assert adjusted.actionability_score_components["rsi_technical_context_bonus_points"] == enriched[
        "rsi_actionability_adjustment"
    ]
    assert adjusted.risk_score_components["rsi_technical_context_adjustment"] == enriched[
        "rsi_risk_adjustment"
    ]
    assert any("Validated RSI technical context adjusted" in item for item in adjusted.decision_warnings)


def test_rsi_scalar_injection_is_ignored_and_direction_mismatch_fails_closed():
    from crypto_rsi_scanner.event_alpha.radar.rsi_technical_context import (
        apply_rsi_technical_context,
    )

    base_row = _market_led_candidate(
        directional_bias="long",
        technical_context={"adapter": "rsi"},
    )
    baseline = decision_model.evaluate_radar_decision(base_row)
    injected = decision_model.evaluate_radar_decision({
        **base_row,
        "rsi_actionability_adjustment": 12.0,
        "rsi_risk_adjustment": -8.0,
        "rsi_adjustment_reason_codes": ["free_standing_injection"],
    })
    artifact = {
        "setup_type": "dip_buy",
        "rsi_daily": 22.0,
        "severity": "ALERT",
        "market_regime": "BULL",
        "conviction": 74,
        "expected_dir": "up",
        "observed_at": "2026-07-12T10:00:00Z",
        "freshness_status": "fresh",
    }
    mismatched = apply_rsi_technical_context(
        {**base_row, "directional_bias": "risk"},
        artifact,
        evaluated_at="2026-07-12T12:00:00Z",
    )
    rejected_mismatch = decision_model.evaluate_radar_decision(mismatched)
    no_bias_base = dict(base_row)
    no_bias_base.pop("directional_bias")
    no_bias = apply_rsi_technical_context(
        no_bias_base,
        artifact,
        evaluated_at="2026-07-12T12:00:00Z",
    )
    rejected_unknown_bias = decision_model.evaluate_radar_decision(no_bias)
    no_bias_baseline = decision_model.evaluate_radar_decision(no_bias_base)

    assert injected.actionability_score == baseline.actionability_score
    assert injected.risk_score == baseline.risk_score
    assert "rsi_technical_context_bonus_points" not in injected.actionability_score_components
    assert rejected_mismatch.actionability_score == baseline.actionability_score
    assert rejected_mismatch.risk_score == baseline.risk_score
    assert "rsi_technical_context_adjustment" not in rejected_mismatch.risk_score_components
    assert rejected_unknown_bias.actionability_score == no_bias_baseline.actionability_score
    assert rejected_unknown_bias.risk_score == no_bias_baseline.risk_score


def test_thresholds_are_configurable_without_runtime_config_fields():
    row = _market_led_candidate()
    strict = decision_model.RadarDecisionConfig(actionability_threshold=99.0)
    result = decision_model.evaluate_radar_decision(row, cfg=strict)

    assert result.actionability_score < strict.actionability_threshold
    assert result.radar_actionable is False
    assert result.radar_route == "dashboard_watch"


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
        cfg=decision_model.RadarDecisionConfig(
            actionability_threshold=50.0,
            rapid_anomaly_actionability_threshold=55.0,
            rapid_anomaly_route_enabled=False,
        ),
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


def test_derivatives_evidence_does_not_invent_a_plausible_catalyst():
    row = _market_led_candidate(
        source_origin="derivatives",
        source_origins=["derivatives"],
        source_pack="derivatives_pack",
        source_class="derivatives",
        accepted_evidence_count=3,
        latest_source_url="https://example.invalid/derivatives",
    )

    result = decision_model.evaluate_radar_decision(row)

    assert result.thesis_origin == "derivatives_led"
    assert result.primary_thesis_origin == "derivatives_led"
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


def test_malformed_side_effect_and_research_only_claims_fail_closed():
    from crypto_rsi_scanner.event_alpha.radar.decision_safety import (
        source_safety_attestations,
    )

    malformed_candidates = (
        _market_led_candidate(execution_enabled=[]),
        _market_led_candidate(notification_send_enabled="false"),
        _market_led_candidate(telegram_sends="0"),
        _market_led_candidate(strict_alerts_created=None),
        _market_led_candidate(source_context={"research_only": "false"}),
    )
    for row in malformed_candidates:
        result = decision_model.evaluate_radar_decision(row)

        assert result.radar_actionable is False
        assert result.radar_route == "diagnostic"
        assert "research_safety_invariant_failed" in result.decision_hard_blockers

    safe = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            execution_enabled=False,
            notification_send_enabled=False,
            telegram_sends=0,
            strict_alerts_created=0.0,
            source_context={"research_only": True},
        )
    )
    assert safe.radar_actionable is True
    assert safe.decision_hard_blockers == ()
    assert source_safety_attestations(
        [{"research_only": "false"}]
    )["decision_source_side_effect_safety_failed"] is True


def test_integrated_source_safety_attestations_survive_final_reevaluation():
    from crypto_rsi_scanner.event_alpha.radar.integrated_radar import build_integrated_candidates
    from crypto_rsi_scanner.event_alpha.radar.decision_safety import source_safety_attestations

    base_source = {
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
    cases = (
        (
            "side_effect",
            {"notification_send_enabled": True},
            "decision_source_side_effect_safety_failed",
            "research_safety_invariant_failed",
        ),
        (
            "nested_secret",
            {"provider_payload": {"authorization": "Bearer leaked-source-secret"}},
            "decision_source_secret_safety_failed",
            "secret_safety_failed",
        ),
        (
            "absolute_path",
            {
                "operator_report_path": "/tmp/unsafe-source-report.md",
                "provider_source_artifact": "/tmp/private/source-artifact.jsonl",
                "request_ledger_path": "/tmp/private/request-ledger.jsonl",
            },
            "decision_source_path_safety_failed",
            "operator_path_safety_failed",
        ),
    )

    for label, unsafe_fields, attestation, blocker in cases:
        row = build_integrated_candidates(
            sidecar_rows={"market_anomaly": [{**base_source, **unsafe_fields}]},
            profile="fixture",
            artifact_namespace=f"decision_model_source_safety_{label}",
            run_mode="fixture",
            run_id=f"decision-model-source-safety-{label}",
            observed_at="2026-06-15T16:00:00Z",
        )[0]

        assert row[attestation] is True
        assert blocker in row["decision_hard_blockers"]
        reevaluated = decision_model.reevaluate_radar_decision_fields(row)
        assert reevaluated["radar_actionable"] is False
        assert reevaluated["radar_route"] == "diagnostic"
        assert blocker in reevaluated["decision_hard_blockers"]
        assert "leaked-source-secret" not in json.dumps(row, sort_keys=True)
        if label == "absolute_path":
            assert row["provider_source_artifact"] == "source-artifact.jsonl"
            assert row["request_ledger_path"] == "request-ledger.jsonl"
            assert "/tmp/private" not in json.dumps(row, sort_keys=True)

    for path_row in (
        {"path": "/tmp/private/exact-path.json"},
        {"artifact_paths": {"candidate": "/tmp/private/nested-path.json"}},
    ):
        assert source_safety_attestations([path_row])["decision_source_path_safety_failed"] is True


def test_source_safety_attestations_are_fail_closed_schema_contracts():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import validate_contract
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values

    base = _market_led_candidate()
    canonical = {**base, **decision_model.evaluate_radar_decision(base).to_dict()}
    missing_blocker = {**canonical, "decision_source_secret_safety_failed": True}
    malformed_attestation = {**canonical, "decision_source_secret_safety_failed": "true"}
    errors = validate_contract(missing_blocker)

    assert any("source_safety_attestation_without_blocker" in error for error in errors)
    assert "decision_model_invalid_type:decision_source_secret_safety_failed" in validate_contract(
        malformed_attestation
    )
    assert decision_model_values(missing_blocker) == {}
    assert decision_model_values(malformed_attestation) == {}

    diagnostic = {
        **canonical,
        "confidence_band": "diagnostic",
        "tradability_status": "blocked",
        "radar_route": "diagnostic",
        "radar_route_reason": "source_secret_safety_failed",
        "radar_actionable": False,
        "decision_hard_blockers": ["secret_safety_failed"],
        "decision_source_secret_safety_failed": True,
    }
    assert validate_contract(diagnostic) == []
    assert decision_model_values(diagnostic)["decision_source_secret_safety_failed"] is True


def test_research_only_must_be_explicit_true_for_v2_promotion_and_schema():
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    missing = _market_led_candidate()
    missing.pop("research_only")
    malformed = _market_led_candidate(research_only="false")

    for row in (missing, malformed):
        result = decision_model.evaluate_radar_decision(row)
        assert result.radar_actionable is False
        assert result.radar_route == "diagnostic"
        assert "research_safety_invariant_failed" in result.decision_hard_blockers
        artifact = {
            **row,
            **result.to_dict(),
            "candidate_id": "candidate-v2-research-only-contract",
        }
        assert "decision_model_research_only_required" in schema_v1.validate_row_against_schema(
            artifact,
            "integrated_radar_candidate_v1",
        )


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


def test_final_reevaluation_applies_catalyst_disproof_before_derived_status():
    source = _market_led_candidate(
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
    initial = {
        **source,
        **decision_model.evaluate_radar_decision(source).to_dict(),
    }
    assert initial["catalyst_status"] == "confirmed"
    assert initial["radar_route"] == "high_confidence_watch"

    for correction in ({"catalyst_disproven": True}, {"cause_status": "ruled_out"}):
        reevaluated = decision_model.reevaluate_radar_decision_fields(
            {**initial, **correction}
        )
        assert reevaluated["catalyst_status"] == "disproven"
        assert reevaluated["confidence_band"] != "high_confidence"
        assert reevaluated["radar_route"] != "high_confidence_watch"
        source_corrected = decision_model.evaluate_radar_decision(
            source,
            source_rows=[correction],
        )
        assert source_corrected.catalyst_status == "disproven"
        assert source_corrected.radar_route != "high_confidence_watch"


def test_retrospective_official_source_cannot_claim_catalyst_confirmation():
    from crypto_rsi_scanner.event_alpha.radar import catalyst_attribution

    attribution = catalyst_attribution.assess_mapping_attribution(
        {
            "market_anomaly_id": "decision-model-v2-move",
            "observed_at": "2026-06-15T16:00:00Z",
        },
        {
            "raw_id": "later-official-source",
            "provider": "official_exchange",
            "source_url": "https://exchange.example/notices/move",
            "content_hash": "a" * 64,
            "published_at": "2026-06-15T16:30:00Z",
            "row_type": "official_listing_candidate",
            "source_class": "official_exchange",
            "source_strength": "official_structured",
            "accepted_evidence_count": 1,
            "main_frame_role": "background_context",
            "candidate_role": "background_context",
            "impact_path_strength": "direct",
        },
    )
    row = _market_led_candidate(
        source_origin="official_exchange",
        source_origins=["market_anomaly", "official_exchange"],
        source_pack="official_exchange_listing_pack",
        source_class="official_exchange",
        source_strength="official_structured",
        accepted_evidence_count=1,
        latest_source_url="https://exchange.example/notices/move",
        official_exchange_event={"event_type": "spot_listing"},
        catalyst_attributions=[attribution],
    )

    result = decision_model.evaluate_radar_decision(row)

    assert attribution["evidence_use"] == "retrospective_context"
    assert result.catalyst_status == "unknown"
    assert result.confidence_band == "actionable"
    assert result.radar_route == "actionable_watch"
    assert result.radar_route != "high_confidence_watch"
    assert any("retrospective or contextual" in item for item in result.decision_warnings)


def test_antecedent_official_source_can_confirm_catalyst_with_attribution():
    from crypto_rsi_scanner.event_alpha.radar import catalyst_attribution

    attribution = catalyst_attribution.assess_mapping_attribution(
        {
            "market_anomaly_id": "decision-model-v2-move",
            "observed_at": "2026-06-15T16:00:00Z",
        },
        {
            "raw_id": "earlier-official-source",
            "provider": "official_exchange",
            "source_url": "https://exchange.example/notices/move",
            "content_hash": "b" * 64,
            "published_at": "2026-06-15T15:30:00Z",
            "row_type": "official_listing_candidate",
            "source_class": "official_exchange",
            "source_strength": "official_structured",
            "accepted_evidence_count": 1,
            "main_frame_role": "main_catalyst",
            "candidate_role": "direct_subject",
            "impact_path_strength": "direct",
        },
    )
    row = _market_led_candidate(
        source_origin="official_exchange",
        source_origins=["market_anomaly", "official_exchange"],
        source_pack="official_exchange_listing_pack",
        source_class="official_exchange",
        source_strength="official_structured",
        accepted_evidence_count=1,
        latest_source_url="https://exchange.example/notices/move",
        official_exchange_event={"event_type": "spot_listing"},
        catalyst_attributions=[attribution],
    )

    result = decision_model.evaluate_radar_decision(row)

    assert attribution["causal_eligible"] is True
    assert result.catalyst_status == "confirmed"
    assert result.confidence_band == "high_confidence"
    assert result.radar_route == "high_confidence_watch"


def test_invalid_supplied_catalyst_attribution_fails_closed():
    from crypto_rsi_scanner.event_alpha.radar import catalyst_attribution

    attribution = catalyst_attribution.assess_mapping_attribution(
        {
            "market_anomaly_id": "decision-model-v2-move",
            "observed_at": "2026-06-15T16:00:00Z",
        },
        {
            "raw_id": "official-source",
            "provider": "official_exchange",
            "published_at": "2026-06-15T15:30:00Z",
            "row_type": "official_listing_candidate",
            "source_class": "official_exchange",
            "source_strength": "official_structured",
            "accepted_evidence_count": 1,
            "main_frame_role": "main_catalyst",
        },
    )
    attribution["causal_eligible"] = False
    row = _market_led_candidate(
        source_origin="official_exchange",
        source_origins=["market_anomaly", "official_exchange"],
        source_pack="official_exchange_listing_pack",
        source_class="official_exchange",
        source_strength="official_structured",
        accepted_evidence_count=1,
        catalyst_attributions=[attribution],
    )

    result = decision_model.evaluate_radar_decision(row)

    assert result.catalyst_status == "unknown"
    assert result.radar_route != "high_confidence_watch"
    assert any("closed contract" in item for item in result.decision_warnings)

    disproven = decision_model.evaluate_radar_decision(
        {**row, "catalyst_status": "disproven"}
    )
    assert disproven.catalyst_status == "disproven"
    assert disproven.radar_route != "high_confidence_watch"


def test_catalyst_attribution_survives_projection_and_pending_outcome_exactly():
    from crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcome_rows import (
        _outcome_placeholder_row,
    )
    from crypto_rsi_scanner.event_alpha.radar import catalyst_attribution
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
    )

    attribution = catalyst_attribution.assess_mapping_attribution(
        {
            "market_anomaly_id": "decision-model-v2-move",
            "observed_at": "2026-06-15T16:00:00Z",
        },
        {
            "raw_id": "later-official-source",
            "provider": "official_exchange",
            "published_at": "2026-06-15T16:30:00Z",
            "row_type": "official_listing_candidate",
            "source_class": "official_exchange",
            "source_strength": "official_structured",
            "accepted_evidence_count": 1,
            "main_frame_role": "background_context",
            "candidate_role": "background_context",
        },
    )
    raw = _market_led_candidate(
        catalyst_attributions=[attribution],
        run_id="catalyst-attribution-run",
        profile="fixture",
        artifact_namespace="catalyst_attribution",
    )
    candidate = {**raw, **decision_model.evaluate_radar_decision(raw).to_dict()}

    projected = decision_model_values(candidate)
    outcome = _outcome_placeholder_row(
        candidate, now="2026-06-15T16:01:00+00:00"
    )

    assert projected["catalyst_attributions"] == [attribution]
    assert decision_model_values(projected) == projected
    assert outcome["catalyst_attributions"] == [attribution]
    assert outcome["decision_projection"]["catalyst_attributions"] == [attribution]


def test_empty_projection_attribution_list_preserves_legacy_confirmed_status():
    from crypto_rsi_scanner.event_alpha.radar import decision_catalyst_policy
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
    )

    raw = _market_led_candidate(
        source_origin="official_exchange",
        source_origins=["official_exchange"],
        source_pack="official_exchange_listing_pack",
        source_class="official_exchange",
        source_strength="official_structured",
        accepted_evidence_count=1,
        latest_source_url="https://exchange.example/notices/move",
        official_exchange_event={"event_type": "spot_listing"},
    )
    candidate = {**raw, **decision_model.evaluate_radar_decision(raw).to_dict()}
    projection = decision_model_values(candidate)

    assert projection["catalyst_status"] == "confirmed"
    assert projection["catalyst_attributions"] == []
    assert decision_catalyst_policy.catalyst_status(projection, ()) == "confirmed"
    assert decision_model_values(projection) == projection


def test_foreign_anomaly_attribution_fails_closed_in_raw_and_projection():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import (
        validate_contract,
    )
    from crypto_rsi_scanner.event_alpha.radar import catalyst_attribution
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_values,
    )

    attribution = catalyst_attribution.assess_mapping_attribution(
        {"market_anomaly_id": "anomaly-a", "observed_at": "2026-06-15T16:00:00Z"},
        {
            "raw_id": "official-a",
            "provider": "official_exchange",
            "published_at": "2026-06-15T15:30:00Z",
            "row_type": "official_listing_candidate",
            "main_frame_role": "main_catalyst",
        },
    )
    foreign = _market_led_candidate(
        market_anomaly_id="anomaly-b",
        source_origin="official_exchange",
        source_origins=["market_anomaly", "official_exchange"],
        source_pack="official_exchange_listing_pack",
        source_class="official_exchange",
        source_strength="official_structured",
        accepted_evidence_count=1,
        catalyst_attributions=[attribution],
    )

    foreign_result = decision_model.evaluate_radar_decision(foreign)
    foreign_candidate = {**foreign, **foreign_result.to_dict()}
    foreign_projection = decision_model_values(foreign_candidate)

    assert foreign_result.catalyst_status == "unknown"
    assert foreign_result.radar_route != "high_confidence_watch"
    assert foreign_projection["catalyst_attributions"] == []

    bound = {**foreign, "market_anomaly_id": "anomaly-a"}
    bound_candidate = {**bound, **decision_model.evaluate_radar_decision(bound).to_dict()}
    projection = decision_model_values(bound_candidate)
    projection["observation_ids"] = ["anomaly-b"]

    assert any(
        "anomaly_binding_mismatch" in error for error in validate_contract(projection)
    )
    assert decision_model_values(projection) == {}


def test_actionability_score_cohort_boundaries_are_canonical():
    from crypto_rsi_scanner.event_alpha.radar.decision_models import (
        actionability_score_cohort,
        evidence_confidence_score_cohort,
        risk_score_cohort,
    )

    assert {
        score: actionability_score_cohort(score)
        for score in (0, 24.99, 25, 49.99, 50, 69.99, 70, 84.99, 85, 100)
    } == {
        0: "0_24", 24.99: "0_24", 25: "25_49", 49.99: "25_49",
        50: "50_69", 69.99: "50_69", 70: "70_84", 84.99: "70_84",
        85: "85_100", 100: "85_100",
    }
    expected_evidence_risk = {
        0: "0_24", 24.99: "0_24", 25: "25_44", 44.99: "25_44",
        45: "45_64", 64.99: "45_64", 65: "65_79", 79.99: "65_79",
        80: "80_100", 100: "80_100",
    }
    assert {
        score: evidence_confidence_score_cohort(score)
        for score in expected_evidence_risk
    } == expected_evidence_risk
    assert {
        score: risk_score_cohort(score)
        for score in expected_evidence_risk
    } == expected_evidence_risk
    for invalid in (True, -0.01, 100.01, float("nan"), float("inf"), None):
        assert actionability_score_cohort(invalid) is None
        assert evidence_confidence_score_cohort(invalid) is None
        assert risk_score_cohort(invalid) is None


def test_multiple_thesis_origins_preserve_primary_and_contributors():
    market_with_derivatives = decision_model.evaluate_radar_decision({
        **_market_led_candidate(),
        "derivatives_state_snapshot": {
            "freshness_status": "fresh",
            "funding_zscore": 2.2,
        },
    })
    dex_with_market = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            source_origin="dex_onchain",
            source_origins=["dex_onchain"],
            source_pack="dex_liquidity_pack",
            source_class="dex_onchain",
            dex_state_snapshot={"freshness_status": "fresh", "volume_change": 2.0},
        )
    )
    technical_with_market = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            technical_context={"setup_type": "mean_reversion", "rsi": 24.0},
        )
    )
    derivatives_only = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            source_origin="derivatives",
            source_origins=["derivatives"],
            source_pack="derivatives_pack",
            source_class="derivatives",
            market_state_class="",
            market_anomaly_bucket="",
            derivatives_state_snapshot={"freshness_status": "fresh"},
        )
    )

    assert market_with_derivatives.primary_thesis_origin == "market_led"
    assert market_with_derivatives.thesis_origins == ("market_led", "derivatives_led")
    assert dex_with_market.primary_thesis_origin == "onchain_led"
    assert dex_with_market.thesis_origins == ("onchain_led", "market_led")
    assert technical_with_market.primary_thesis_origin == "technical_led"
    assert technical_with_market.thesis_origins == ("technical_led", "market_led")
    assert derivatives_only.primary_thesis_origin == "derivatives_led"
    assert derivatives_only.thesis_origins == ("derivatives_led",)


def test_market_primary_with_confirmed_catalyst_contributor_can_be_high_confidence():
    source = {
        "_source_origin": "official_exchange",
        "source_origin": "official_exchange",
        "source_class": "official_exchange",
        "source_pack": "official_exchange_listing_pack",
        "source_strength": "official_structured",
        "accepted_evidence_count": 1,
        "latest_source_url": "https://example.invalid/listing",
        "latest_source_title": "Official listing notice",
        "event_type": "spot_listing",
    }

    result = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            latest_source_url=source["latest_source_url"],
            latest_source_title=source["latest_source_title"],
        ),
        source_rows=[source],
    )

    assert result.primary_thesis_origin == "market_led"
    assert result.thesis_origins[:2] == ("market_led", "catalyst_led")
    assert result.catalyst_status == "confirmed"
    assert result.confidence_band == "high_confidence"
    assert result.radar_route == "high_confidence_watch"


def test_spoofed_catalyst_contributor_without_evidence_cannot_be_high_confidence():
    result = decision_model.evaluate_radar_decision(
        _market_led_candidate(),
        source_rows=[{"_source_origin": "official_exchange"}],
    )

    assert result.primary_thesis_origin == "market_led"
    assert "catalyst_led" in result.thesis_origins
    assert result.catalyst_status == "unknown"
    assert result.radar_route != "high_confidence_watch"


def test_middle_score_is_dashboard_visible_without_becoming_actionable():
    result = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            market_state_class="late_momentum",
            market_anomaly_bucket="late_momentum_needs_crowding_check",
        )
    )

    assert 55.0 <= result.actionability_score < 65.0
    assert result.confidence_band == "exploratory"
    assert result.radar_route == "dashboard_watch"
    assert result.radar_actionable is False


def test_explicit_spread_tiers_gate_push_without_hiding_liquid_ideas():
    good = decision_model.evaluate_radar_decision(_market_led_candidate())
    acceptable = decision_model.evaluate_radar_decision(
        _market_led_candidate(market_state_snapshot={"spread_bps": 80.0})
    )
    wide = decision_model.evaluate_radar_decision(
        _market_led_candidate(market_state_snapshot={"spread_bps": 200.0})
    )
    stale = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            market_state_snapshot={
                "spread_bps": 20.0,
                "spread_freshness_status": "stale",
            }
        )
    )

    assert good.spread_status == "verified_good"
    assert good.radar_actionable is True
    assert acceptable.spread_status == "verified_acceptable"
    assert acceptable.radar_actionable is True
    assert wide.spread_status == "verified_wide"
    assert wide.radar_route == "diagnostic"
    assert "spread_above_maximum" in wide.decision_hard_blockers
    assert stale.spread_status == "stale"
    assert stale.radar_route == "dashboard_watch"
    assert stale.radar_actionable is False


def test_timing_profile_is_deterministic_and_expired_ideas_fail_closed():
    breakout = decision_model.evaluate_radar_decision(
        _market_led_candidate(observed_at="2026-06-15T16:00:00Z")
    )
    exhausted = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            anomaly_type="blowoff_crowded",
            observed_at="2026-06-15T16:00:00Z",
        )
    )
    expired = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            observed_at="2026-06-15T16:00:00Z",
            expires_at="2026-06-15T15:59:59Z",
        )
    )

    assert breakout.market_phase == "breakout"
    assert breakout.urgency_score >= 72.0
    assert breakout.preferred_horizon == "1d_3d"
    assert breakout.expires_at == "2026-06-16T16:00:00Z"
    assert 0.0 <= breakout.chase_risk_score <= 100.0
    assert exhausted.market_phase == "exhaustion"
    assert exhausted.chase_risk_score > breakout.chase_risk_score
    assert expired.radar_route == "diagnostic"
    assert expired.radar_actionable is False
    assert "idea_expired" in expired.decision_hard_blockers


def test_return_units_normalize_exactly_and_mixed_metadata_is_explicit():
    percent_points = decision_model.evaluate_radar_decision(_market_led_candidate())
    fraction = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            market_state_snapshot={
                "return_unit": "fraction",
                "return_4h": 0.12,
                "return_24h": 0.20,
                "relative_return_vs_btc_4h": 0.09,
            }
        )
    )
    mixed = decision_model.evaluate_radar_decision(
        _market_led_candidate(
            market_state_snapshot={
                "return_unit": "fraction",
                "return_units": {"relative_return_vs_btc_4h": "percent_points"},
                "return_4h": 0.12,
                "return_24h": 0.20,
                "relative_return_vs_btc_4h": 9.0,
            }
        )
    )

    assert fraction.actionability_score == percent_points.actionability_score
    assert mixed.actionability_score == percent_points.actionability_score
    assert fraction.radar_actionable is True
    assert mixed.radar_actionable is True
    assert "invalid_market_return_units" not in fraction.decision_hard_blockers
    assert "invalid_market_return_units" not in mixed.decision_hard_blockers


def test_separate_market_snapshots_normalize_before_precedence_merge():
    row = _market_led_candidate()
    row["latest_market_snapshot"] = {
        "return_unit": "fraction",
        "return_4h": 0.12,
        "return_24h": 0.20,
        "relative_return_vs_btc_4h": 0.09,
    }
    row["market_state_snapshot"] = {
        "volume_zscore_24h": 3.5,
        "volume_to_market_cap": 0.30,
        "liquidity_usd": 12_000_000,
        "spread_bps": 22.0,
        "freshness_status": "fresh",
    }

    result = decision_model.evaluate_radar_decision(row)

    assert result.radar_actionable is True
    assert result.actionability_score == decision_model.evaluate_radar_decision(
        _market_led_candidate()
    ).actionability_score
    assert "invalid_market_return_units" not in result.decision_hard_blockers


def test_implausible_fraction_return_fails_model_and_schema_validation():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import validate_contract

    candidate = _market_led_candidate(
        market_state_snapshot={
            "return_unit": "fraction",
            "return_4h": 0.10,
            "return_24h": 0.20,
            "relative_return_vs_btc_4h": 10.0,
        }
    )
    result = decision_model.evaluate_radar_decision(candidate)
    artifact = {**candidate, **result.to_dict()}

    assert result.radar_actionable is False
    assert "invalid_market_return_units" in result.decision_hard_blockers
    assert "decision_model_implausible_fraction_return:market_state_snapshot:relative_return_vs_btc_4h" in validate_contract(
        artifact
    )


def test_v2_schema_rejects_boolean_scores_and_market_returns():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import validate_contract

    candidate = _market_led_candidate()
    valid = {**candidate, **decision_model.evaluate_radar_decision(candidate).to_dict()}
    assert validate_contract(valid) == []

    for field in (
        "actionability_score",
        "evidence_confidence_score",
        "risk_score",
        "urgency_score",
        "chase_risk_score",
    ):
        malformed = deepcopy(valid)
        malformed[field] = True
        assert f"decision_model_invalid_score:{field}" in validate_contract(malformed)

    malformed_return = deepcopy(valid)
    malformed_return["market_state_snapshot"]["return_4h"] = True
    assert (
        "decision_model_invalid_return_value:market_state_snapshot:return_4h"
        in validate_contract(malformed_return)
    )


def test_v2_schema_requires_ordered_origins_and_verified_actionable_spread():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import validate_contract

    candidate = _market_led_candidate()
    valid = {**candidate, **decision_model.evaluate_radar_decision(candidate).to_dict()}
    wrong_order = {
        **valid,
        "primary_thesis_origin": "derivatives_led",
        "thesis_origins": ["market_led", "derivatives_led"],
    }
    unverified_spread = {**valid, "spread_status": "unavailable"}

    assert validate_contract(valid) == []
    assert "decision_model_primary_thesis_origin_order_mismatch" in validate_contract(wrong_order)
    assert "decision_model_actionable_spread_unverified" in validate_contract(unverified_spread)


def test_disabled_v2_contract_keeps_unknown_origin_explicit_without_promotion():
    from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import validate_contract

    disabled = decision_model.evaluate_radar_decision(
        _market_led_candidate(),
        cfg=decision_model.RadarDecisionConfig(enabled=False),
    ).to_dict()

    assert disabled["primary_thesis_origin"] == "mixed"
    assert disabled["thesis_origins"] == ["mixed"]
    assert disabled["radar_actionable"] is False
    assert validate_contract(disabled) == []


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
