"""Current derivatives evidence is required for crowding decisions."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import decision_model


def _candidate(freshness: object) -> dict[str, object]:
    return {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "derivatives-freshness-contract",
        "observed_at": "2026-06-15T16:00:00Z",
        "symbol": "CROWD",
        "coin_id": "crowd-token",
        "canonical_asset_id": "crowd-token",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.95,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "source_origin": "market_anomaly",
        "source_origins": ["market_anomaly"],
        "source_pack": "market_anomaly_pack",
        "market_state_class": "blowoff_crowded",
        "market_anomaly_bucket": "late_momentum_needs_crowding_check",
        "crowding_class": "high",
        "crowding_exhaustion_evidence": ["open_interest_delta_4h_high"],
        "derivatives_state_snapshot": {
            "freshness_status": freshness,
            "open_interest_delta_4h": 30.0,
            "funding_zscore": 2.5,
        },
        "research_only": True,
        "created_alert": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 22.0,
            "return_24h": 38.0,
            "relative_return_vs_btc_4h": 18.0,
            "volume_zscore_24h": 4.0,
            "volume_to_market_cap": 0.45,
            "liquidity_usd": 18_000_000,
            "spread_bps": 18.0,
            "freshness_status": "fresh",
        },
    }


def test_stale_or_malformed_derivatives_cannot_supply_crowding():
    for freshness in (None, True, "unknown", "stale", "banana"):
        row = _candidate(freshness)

        assert decision_model._has_crowding(row) is False
        assert decision_model._derivatives_score(row) == 30.0

        result = decision_model.evaluate_radar_decision(row)
        assert result.radar_route != "fade_exhaustion_review"
        assert "derivatives_confirmation_missing_for_fade_review" in (
            result.decision_soft_penalties
        )


def test_fresh_derivatives_can_supply_crowding_review_context():
    row = _candidate("fresh")

    assert decision_model._has_crowding(row) is True
    assert decision_model._derivatives_score(row) == 85.0

    result = decision_model.evaluate_radar_decision(row)
    assert result.radar_route == "fade_exhaustion_review"
    assert "derivatives_confirmation_missing_for_fade_review" not in (
        result.decision_soft_penalties
    )


def test_invalid_canonical_derivatives_snapshot_cannot_expose_alias():
    row = _candidate("fresh")
    row["derivatives_state_snapshot"] = "malformed"
    row["derivatives_snapshot"] = {
        "freshness_status": "fresh",
        "open_interest_delta_4h": 30.0,
    }

    assert decision_model._has_crowding(row) is False
    assert decision_model._derivatives_score(row) == 30.0

    result = decision_model.evaluate_radar_decision(row)
    assert result.radar_actionable is False
    assert result.radar_route == "diagnostic"
    assert "derivatives_context_invalid" in result.decision_hard_blockers


def test_malformed_derivatives_context_cannot_create_or_hide_crowding_evidence():
    malformed_rows: list[dict[str, object]] = []

    for field, value in (
        ("derivatives_state_snapshot", []),
        ("derivatives_snapshot", True),
    ):
        row = _candidate("fresh")
        if field == "derivatives_snapshot":
            row.pop("derivatives_state_snapshot")
        row[field] = value
        malformed_rows.append(row)

    for snapshot_override in (
        {"freshness_status": True},
        {"freshness_status": "banana"},
        {"freshness_status": "fresh", "funding_zscore": {"value": 3.0}},
        {"freshness_status": "fresh", "open_interest_delta_4h": "30.0"},
    ):
        row = _candidate("fresh")
        row["derivatives_state_snapshot"] = snapshot_override
        malformed_rows.append(row)

    for field, value in (
        ("coinalyze_freshness_status", []),
        ("crowding_class", {"high": True}),
        ("crowding_exhaustion_evidence", {"funding_zscore_elevated": True}),
        ("crowding_exhaustion_evidence", ["funding_zscore_elevated", {"oi": True}]),
    ):
        row = _candidate("fresh")
        row["crowding_class"] = "none"
        row["crowding_exhaustion_evidence"] = []
        row[field] = value
        malformed_rows.append(row)

    for row in malformed_rows:
        result = decision_model.evaluate_radar_decision(row)

        assert result.radar_actionable is False
        assert result.radar_route == "diagnostic"
        assert "derivatives_context_invalid" in result.decision_hard_blockers


def test_typed_derivatives_context_keeps_valid_crowding_route():
    row = _candidate("fresh")
    row["coinalyze_freshness_status"] = "fresh"
    row["crowding_class"] = "high"
    row["crowding_exhaustion_evidence"] = [
        "open_interest_delta_4h_high",
        "funding_zscore_elevated",
    ]

    result = decision_model.evaluate_radar_decision(row)

    assert result.radar_route == "fade_exhaustion_review"
    assert "derivatives_context_invalid" not in result.decision_hard_blockers
