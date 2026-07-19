"""Exact zero evidence must remain distinct from unavailable operator data."""

from __future__ import annotations


def test_market_diagnostics_preserve_zero_canonical_values_over_aliases():
    from crypto_rsi_scanner.event_alpha.dashboard.layer_diagnostics import (
        render_market_anomaly_evidence_table,
        render_market_observation_table,
    )

    observations = render_market_observation_table(
        [
            {
                "symbol": "ZERO",
                "liquidity_usd": 0.0,
                "volume_24h": 123_456.0,
            }
        ]
    )
    anomalies = render_market_anomaly_evidence_table(
        [
            {
                "symbol": "ZERO",
                "anomaly_strength": 0.0,
                "anomaly_score": 99.0,
            }
        ]
    )

    assert "$0" in observations
    assert "$123,456" not in observations
    assert "0.000" in anomalies
    assert "99.000" not in anomalies


def test_research_card_details_render_zero_as_observed():
    from crypto_rsi_scanner.event_alpha.artifacts import research_cards

    assert research_cards._display_text(0.0) == "0.0"

    monitor = research_cards._monitor_lines(
        {"event_countdown_hours": 0.0, "event_age_hours": 0.0}
    )
    assert "- Event countdown hours: 0.0" in monitor
    assert "- Event age hours: 0.0" in monitor

    derivatives = research_cards._derivatives_crowding_lines(
        None,
        {
            "derivatives_state_snapshot": {
                "provider": "fixture",
                "funding_zscore": 0.0,
                "liquidation_imbalance": 0.0,
            }
        },
    )
    assert any("z=0.0" in line for line in derivatives)
    assert "- Liquidation imbalance: 0.0" in derivatives


def test_unlock_and_final_score_precedence_preserve_zero():
    from crypto_rsi_scanner.event_alpha.artifacts import research_cards
    from crypto_rsi_scanner.event_alpha.artifacts.research_cards.components import (
        outcomes,
    )
    from crypto_rsi_scanner.event_alpha.radar.watchlist import EventWatchlistEntry

    unlock = research_cards._scheduled_catalyst_lines(
        None,
        {
            "row_type": "unlock_event",
            "source_pack": "unlock_pack",
            "unlock_pct_circulating_supply": 0.0,
            "unlock_vs_30d_adv": 0.0,
            "unlock_event": {
                "unlock_pct_circulating_supply": 12.0,
                "unlock_vs_30d_adv": 4.0,
            },
        },
    )
    assert "- Unlock pct circulating: 0.0" in unlock
    assert "- Unlock vs 30d ADV: 0.0" in unlock

    entry = EventWatchlistEntry(
        schema_version="test",
        row_type="event_watchlist",
        key="zero",
        cluster_id=None,
        event_id="event-zero",
        coin_id="zero",
        symbol="ZERO",
        relationship_type="impact_hypothesis",
        external_asset=None,
        event_time=None,
        state="RADAR",
        previous_state=None,
        first_seen_at="2026-01-01T00:00:00Z",
        last_seen_at="2026-01-01T00:00:00Z",
    )
    context = outcomes._impact_hypothesis_context(
        entry,
        {"final_opportunity_score": 0.0, "opportunity_score_final": 88.0},
    )
    assert context["final_opportunity_score"] == 0.0


def test_opportunity_audit_preserves_zero_scores_over_legacy_fallbacks():
    from crypto_rsi_scanner.event_alpha.artifacts import opportunity_audit

    row = {
        "evidence_quality_score": 91.0,
        "market_confirmation_score": 92.0,
        "derivatives_confirmation_score": 93.0,
        "dex_liquidity_score": 94.0,
        "protocol_metrics_score": 95.0,
        "final_opportunity_score": 96.0,
    }
    components = {
        "evidence_quality_score": 0.0,
        "market_confirmation_score": 0.0,
        "derivatives_confirmation_score": 0.0,
        "dex_liquidity_score": 0.0,
        "protocol_metrics_score": 0.0,
        "final_opportunity_score": 0.0,
    }

    rendered = "\n".join(
        opportunity_audit._impact_and_evidence_quality_audit_lines(row, components)
        + opportunity_audit._market_confirmation_audit_lines(row, components)
        + opportunity_audit._final_verdict_audit_lines(row, components)
    )

    assert "- evidence score: 0.0" in rendered
    assert "- market level/score: unknown / 0.0" in rendered
    assert "- derivatives confirmation: unknown / 0.0" in rendered
    assert "- DEX liquidity confirmation: unknown / 0.0" in rendered
    assert "- protocol metrics confirmation: unknown / 0.0" in rendered
    assert "- level/score: unknown / 0.0" in rendered
    for shadowed in ("91.0", "92.0", "93.0", "94.0", "95.0", "96.0"):
        assert shadowed not in rendered
