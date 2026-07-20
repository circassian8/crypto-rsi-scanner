"""Decision snapshot precedence must preserve explicit invalidity."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import decision_model, decision_policy


def _actionable_candidate() -> dict[str, object]:
    return {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "snapshot-container-contract",
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
        "market_state_class": "confirmed_breakout",
        "market_anomaly_bucket": "high_liquidity_breakout",
        "research_only": True,
        "created_alert": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "market_snapshot": {
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


def test_malformed_snapshot_container_cannot_borrow_valid_legacy_snapshot():
    for invalid in ([], True, "not-a-snapshot"):
        row = _actionable_candidate()
        row["market_state_snapshot"] = invalid

        result = decision_model.evaluate_radar_decision(row)

        assert result.radar_actionable is False
        assert result.radar_route == "diagnostic"
        assert "market_snapshot_contract_invalid" in result.decision_hard_blockers

    valid = decision_model.evaluate_radar_decision(_actionable_candidate())
    assert valid.radar_actionable is True
    assert "market_snapshot_contract_invalid" not in valid.decision_hard_blockers


def test_invalid_later_snapshot_returns_mask_older_values():
    invalid_values = (True, "not-a-number", float("nan"), float("inf"), 10.0)
    for invalid in invalid_values:
        merged = decision_policy.market_snapshot({
            "market_snapshot": {
                "return_unit": "percent_points",
                "return_4h": 12.0,
                "freshness_status": "fresh",
            },
            "market_state_snapshot": {
                "return_unit": "fraction",
                "return_4h": invalid,
                "freshness_status": "fresh",
            },
        })

        assert "return_4h" not in merged
        assert any(
            warning.endswith(":return_4h")
            for warning in merged["unit_warnings"]
        )


def test_absent_later_snapshot_return_preserves_earlier_observation():
    merged = decision_policy.market_snapshot({
        "market_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "freshness_status": "fresh",
        },
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "freshness_status": "fresh",
        },
    })

    assert merged["return_4h"] == 12.0
    assert merged.get("unit_warnings") is None


def test_spread_verification_requires_ordered_freshness_evidence():
    classify = decision_policy.spread_status
    limits = {"good_spread_bps": 50.0, "maximum_spread_bps": 150.0}

    for invalid in (True, "unknown", "unavailable", 3, [], {}):
        assert classify(
            {
                "spread_bps": 22.0,
                "spread_freshness_status": invalid,
                "freshness_status": "fresh",
            },
            **limits,
        ) == "unavailable"

    assert classify({"spread_bps": 22.0}, **limits) == "unavailable"
    assert classify(
        {"spread_bps": 22.0, "freshness_status": "fresh"},
        **limits,
    ) == "verified_good"
    assert classify(
        {
            "spread_bps": 22.0,
            "spread_freshness_status": "stale",
            "freshness_status": "fresh",
        },
        **limits,
    ) == "stale"
