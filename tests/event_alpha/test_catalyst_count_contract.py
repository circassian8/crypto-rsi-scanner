"""Closed accepted-evidence count regressions across catalyst layers."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import (
    decision_model,
    market_anomaly_scanner,
    market_reaction,
)
from crypto_rsi_scanner.event_alpha.radar.integrated.pipeline_parts import (
    merge_policy,
    utilities,
)
from crypto_rsi_scanner.event_alpha.radar.market_reaction import EventOpportunityType


INVALID_COUNTS = (True, 0.5, -1, float("nan"), float("inf"), "1")


def _market_led_candidate(**overrides):
    row = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "catalyst-count-contract",
        "observed_at": "2026-06-15T16:00:00Z",
        "symbol": "COUNT",
        "coin_id": "count-token",
        "canonical_asset_id": "count-token",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.95,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "source_origin": "cryptopanic",
        "source_origins": ["cryptopanic"],
        "source_pack": "cryptopanic_tagged",
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
    row.update(overrides)
    return row


def test_malformed_counts_cannot_promote_decision_catalyst_status():
    for value in INVALID_COUNTS:
        result = decision_model.evaluate_radar_decision(
            _market_led_candidate(accepted_evidence_count=value)
        )

        assert result.catalyst_status == "unknown"
        assert result.evidence_confidence_components["source_specificity"] == 42.0

    valid = decision_model.evaluate_radar_decision(
        _market_led_candidate(accepted_evidence_count=1)
    )

    assert valid.catalyst_status == "plausible"
    assert valid.evidence_confidence_components["source_specificity"] == 58.0


def test_malformed_counts_do_not_claim_anomaly_source_confirmation():
    base = {
        "symbol": "COUNT",
        "coin_id": "count-token",
        "return_unit": "percent_points",
        "return_4h": 10.0,
        "return_24h": 18.0,
        "relative_return_vs_btc_4h": 8.0,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 12_000_000.0,
        "freshness_status": "fresh",
    }

    for invalid in INVALID_COUNTS:
        _, anomalies = market_anomaly_scanner.scan_market_rows(
            [{**base, "accepted_evidence_count": invalid}],
            observed_at="2026-06-15T16:00:00Z",
        )

        assert anomalies[0]["priority_components"]["source_catalyst_unknownness"] == 7.0

    _, valid = market_anomaly_scanner.scan_market_rows(
        [{**base, "accepted_evidence_count": 1}],
        observed_at="2026-06-15T16:00:00Z",
    )

    assert valid[0]["priority_components"]["source_catalyst_unknownness"] == -4.0


def test_market_reaction_does_not_render_malformed_counts_as_evidence():
    base = {
        "source_class": "cryptopanic_tagged",
        "source_pack": "security_incident_pack",
        "impact_path_type": "exploit_security_event",
        "evidence_quality_score": 84,
        "market_snapshot": {
            "return_24h": -0.04,
            "market_context_freshness_status": "fresh",
        },
    }

    for invalid in INVALID_COUNTS:
        result = market_reaction.evaluate_market_reaction(
            {**base, "accepted_evidence_count": invalid}
        )

        assert not any(
            item.startswith("accepted_evidence=")
            for item in result.evidence_summary
        )

    valid = market_reaction.evaluate_market_reaction(
        {**base, "accepted_evidence_count": 1}
    )

    assert "accepted_evidence=1" in valid.evidence_summary


def test_integrated_source_gates_require_strict_counts():
    for value in INVALID_COUNTS:
        rows = [{"accepted_evidence_count": value}]

        assert utilities._int(value) == 0
        assert merge_policy._source_requirements_met(
            EventOpportunityType.RISK_ONLY.value,
            rows,
            "weak",
        ) is False

    assert utilities._int(1) == 1
    assert merge_policy._source_requirements_met(
        EventOpportunityType.RISK_ONLY.value,
        [{"accepted_evidence_count": 1}],
        "weak",
    ) is True
