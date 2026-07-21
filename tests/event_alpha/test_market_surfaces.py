"""Market reaction, provider surface, and integrated-radar regressions."""

from __future__ import annotations

import json
from collections import Counter
from tempfile import TemporaryDirectory

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})

def test_market_reaction_official_listing_no_reaction_is_early_long_research():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction

    result = event_market_reaction.evaluate_market_reaction({
        "source_class": "official_exchange",
        "source_pack": "listing_liquidity_pack",
        "impact_path_type": "listing_liquidity_event",
        "evidence_quality_score": 92,
        "accepted_evidence_count": 1,
        "market_snapshot": {
            "return_24h": 0.01,
            "volume_zscore_24h": 0.1,
            "event_age_hours": -8,
            "market_context_freshness_status": "fresh",
        },
    })

    assert result.market_state == "no_reaction"
    assert result.opportunity_type == "EARLY_LONG_RESEARCH"
    assert result.source_requirements_met is True
    assert result.market_requirements_met is False


def test_market_reaction_official_listing_breakout_is_confirmed_long_research():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction

    result = event_market_reaction.evaluate_market_reaction({
        "source_class": "official_exchange",
        "source_pack": "listing_liquidity_pack",
        "impact_path_type": "listing_liquidity_event",
        "evidence_quality_score": 94,
        "accepted_evidence_count": 1,
        "market_confirmation_level": "moderate",
        "market_confirmation_score": 72,
        "market_snapshot": {
            "return_1h": 0.08,
            "return_24h": 0.18,
            "relative_return_vs_btc": 0.11,
            "volume_zscore_24h": 3.4,
            "event_age_hours": -2,
            "market_context_freshness_status": "fresh",
        },
    })

    assert result.market_state == "confirmed_breakout"
    assert result.opportunity_type == "CONFIRMED_LONG_RESEARCH"
    assert result.source_requirements_met is True
    assert result.market_requirements_met is True


def test_market_reaction_listing_pump_crowding_is_fade_short_review():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction

    result = event_market_reaction.evaluate_market_reaction({
        "source_class": "official_exchange",
        "source_pack": "listing_liquidity_pack",
        "impact_path_type": "listing_liquidity_event",
        "evidence_quality_score": 91,
        "accepted_evidence_count": 1,
        "market_snapshot": {
            "return_4h": 0.32,
            "return_24h": 0.72,
            "volume_zscore_24h": 5.0,
            "event_age_hours": 2,
            "market_context_freshness_status": "fresh",
        },
        "derivatives_snapshot": {
            "open_interest_24h_change_pct": 0.48,
            "funding_rate_8h": 0.0012,
            "liquidation_imbalance": 2.1,
        },
    })

    assert result.market_state == "post_event_fade_setup"
    assert result.opportunity_type == "FADE_SHORT_REVIEW"
    assert result.fade_requirements_met is True


def test_market_reaction_cryptopanic_fan_narrative_is_unconfirmed_without_market():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction

    result = event_market_reaction.evaluate_market_reaction({
        "source_class": "cryptopanic_tagged",
        "source_pack": "fan_sports_pack",
        "impact_path_type": "fan_token_attention",
        "evidence_quality_score": 82,
        "accepted_evidence_count": 1,
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "market_snapshot": {
            "return_24h": 0.02,
            "volume_zscore_24h": 0.4,
            "market_context_freshness_status": "fresh",
        },
    })

    assert result.market_state == "no_reaction"
    assert result.opportunity_type == "UNCONFIRMED_RESEARCH"
    assert "cryptopanic_only_narrative_not_confirmed" in result.why_not_alertable
    assert result.market_requirements_met is False


def test_market_reaction_security_incident_is_risk_only():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction

    result = event_market_reaction.evaluate_market_reaction({
        "source_class": "cryptopanic_tagged",
        "source_pack": "security_incident_pack",
        "impact_path_type": "exploit_security_event",
        "evidence_quality_score": 84,
        "accepted_evidence_count": 1,
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        "market_snapshot": {
            "return_24h": -0.04,
            "volume_zscore_24h": 1.1,
            "market_context_freshness_status": "fresh",
        },
    })

    assert result.opportunity_type == "RISK_ONLY"
    assert result.market_state == "no_reaction"


def test_market_reaction_fractional_latest_snapshot_not_double_scaled():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction
    import crypto_rsi_scanner.event_alpha.radar.market_units as event_market_units

    chz = event_market_reaction.evaluate_market_reaction({
        "source_class": "cryptopanic_tagged",
        "source_pack": "fan_sports_pack",
        "impact_path_type": "fan_token_attention",
        "evidence_quality_score": 75,
        "accepted_evidence_count": 1,
        "market_snapshot": {
            "return_1h": 0.005345456377672031,
            "return_4h": -0.006396566961983541,
            "return_24h": -0.05264195188444422,
            "volume_zscore_24h": 0.2,
            "market_context_freshness_status": "fresh",
        },
    })
    velvet = event_market_reaction.evaluate_market_reaction({
        "source_class": "cryptopanic_tagged",
        "source_pack": "proxy_preipo_rwa_pack",
        "impact_path_type": "venue_value_capture",
        "evidence_quality_score": 75,
        "accepted_evidence_count": 1,
        "market_snapshot": {
            "return_1h": -0.02849172797190569,
            "return_4h": 0.014859616004286647,
            "return_24h": -0.06803294958669015,
            "return_7d": 2.1615314699482866,
            "volume_zscore_24h": 0.2,
            "market_context_freshness_status": "fresh",
        },
    })

    chz_snapshot = chz.market_state_snapshot.to_dict()
    velvet_snapshot = velvet.market_state_snapshot.to_dict()
    assert chz_snapshot["return_unit"] == event_market_units.RETURN_UNIT_PERCENT_POINTS
    assert chz_snapshot["source_return_unit"] == event_market_units.RETURN_UNIT_FRACTION
    assert velvet_snapshot["source_return_unit"] == event_market_units.RETURN_UNIT_FRACTION
    assert round(chz_snapshot["return_1h"], 2) == 0.53
    assert round(chz_snapshot["return_4h"], 2) == -0.64
    assert round(chz_snapshot["return_24h"], 2) == -5.26
    assert round(velvet_snapshot["return_1h"], 2) == -2.85
    assert round(velvet_snapshot["return_4h"], 2) == 1.49
    assert round(velvet_snapshot["return_24h"], 2) == -6.8
    assert event_market_units.format_return_pct(chz_snapshot["return_1h"], unit="percent_points") == "+0.53%"
    assert event_market_units.format_return_pct(velvet_snapshot["return_4h"], unit="percent_points") == "+1.49%"

    recomputed = event_market_reaction.evaluate_market_reaction({
        "source_class": "cryptopanic_tagged",
        "source_pack": "proxy_preipo_rwa_pack",
        "impact_path_type": "venue_value_capture",
        "evidence_quality_score": 75,
        "accepted_evidence_count": 1,
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_1h": -284.91727971905686,
            "return_4h": 148.59616004286647,
            "return_24h": -6.8032949586690155,
        },
        "market_snapshot": {
            "return_1h": -0.02849172797190569,
            "return_4h": 0.014859616004286647,
            "return_24h": -0.06803294958669015,
            "return_7d": 2.1615314699482866,
        },
    }).market_state_snapshot.to_dict()
    assert recomputed["source_return_unit"] == event_market_units.RETURN_UNIT_FRACTION
    assert round(recomputed["return_1h"], 2) == -2.85
    assert round(recomputed["return_4h"], 2) == 1.49


def test_market_reaction_percent_point_snapshot_not_rescaled_again():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction
    import crypto_rsi_scanner.event_alpha.radar.market_state as event_market_state

    reaction = event_market_reaction.evaluate_market_reaction({
        "source_class": "official_exchange",
        "source_pack": "listing_liquidity_pack",
        "impact_path_type": "listing_liquidity_event",
        "evidence_quality_score": 92,
        "accepted_evidence_count": 1,
        "market_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 1.4859616004286647,
            "return_24h": -6.8032949586690155,
            "volume_zscore_24h": 0.2,
            "market_context_freshness_status": "fresh",
        },
    })
    snapshot = reaction.market_state_snapshot.to_dict()
    market_state_snapshot = event_market_state.snapshot_from_market_row({
        "symbol": "PCT",
        "id": "percent-token",
        "return_unit": "percent_points",
        "return_4h": 1.2,
        "return_24h": 5.0,
        "volume_zscore_24h": 0.1,
        "market_context_freshness_status": "fresh",
    }).to_dict()

    assert round(snapshot["return_4h"], 2) == 1.49
    assert round(snapshot["return_24h"], 2) == -6.8
    assert snapshot["source_return_unit"] == "percent_points"
    assert market_state_snapshot["return_4h"] == 1.2
    assert market_state_snapshot["return_24h"] == 5.0
    assert market_state_snapshot["source_return_unit"] == "percent_points"


def test_market_reaction_sector_theme_is_diagnostic():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction

    result = event_market_reaction.evaluate_market_reaction({
        "symbol": "SECTOR",
        "coin_id": "sports_fan_proxy",
        "source_class": "broad_news",
        "source_pack": "fan_sports_pack",
        "impact_path_type": "fan_token_attention",
        "market_snapshot": {"market_context_freshness_status": "missing"},
    })

    assert result.opportunity_type == "DIAGNOSTIC"
    assert "diagnostic_or_sector_row" in result.why_not_alertable


def test_market_state_snapshot_normalizes_returns_and_relative_benchmarks():
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as event_market_anomaly_scanner
    import crypto_rsi_scanner.event_alpha.radar.market_state as event_market_state

    rows = event_market_anomaly_scanner.load_market_rows("fixtures/event_market_anomaly/market_rows.json")
    btc, eth = event_market_state.benchmark_rows(rows)
    token_b = next(row for row in rows if row["id"] == "token-b")
    snapshot = event_market_state.snapshot_from_market_row(token_b, btc_benchmark=btc, eth_benchmark=eth)

    assert snapshot.symbol == "TKNB"
    assert snapshot.coin_id == "token-b"
    assert round(snapshot.return_24h or 0, 1) == 18.0
    assert round(snapshot.relative_return_vs_btc_4h or 0, 1) == 10.7
    assert snapshot.return_unit == "percent_points"
    assert snapshot.source_return_unit == "fraction"
    assert "return_24h" in snapshot.observed_fields
    assert snapshot.freshness_status == "fresh"


def test_market_anomaly_scanner_classifies_fixture_rows():
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as event_market_anomaly_scanner

    rows = event_market_anomaly_scanner.load_market_rows("fixtures/event_market_anomaly/market_rows.json")
    snapshots, anomalies = event_market_anomaly_scanner.scan_market_rows(
        rows,
        observed_at="2026-06-15T16:00:00Z",
        profile="fixture",
        artifact_namespace="market_anomaly_smoke",
    )
    by_coin = {row["coin_id"]: row["anomaly_type"] for row in anomalies}

    assert len(snapshots) == 8
    assert by_coin["token-a"] == "stealth_accumulation"
    assert by_coin["token-b"] == "confirmed_breakout"
    assert by_coin["token-c"] == "suspicious_illiquid_move"
    assert by_coin["token-d"] == "risk_off_sell_pressure"
    assert by_coin["token-f"] == "post_event_fade_setup"
    assert "token-e" not in by_coin
    assert all(row["market_state_class"] == row["anomaly_type"] for row in anomalies)
    by_bucket = {row["coin_id"]: row["anomaly_bucket"] for row in anomalies}
    assert by_bucket["token-b"] == "high_liquidity_breakout"
    assert by_bucket["token-c"] == "low_liquidity_suspicious"
    assert by_bucket["token-a"] == "stealth_accumulation"
    assert by_bucket["token-f"] == "late_momentum_needs_crowding_check"
    assert all(row.get("priority_components") for row in anomalies)
    assert all(row.get("search_queries") for row in anomalies)


def test_market_anomaly_boolean_semantics_cannot_manufacture_risk_or_crowding():
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as scanner

    false_claims = {
        "negative_catalyst": "false",
        "risk_off_catalyst": "0",
        "event_passed": "no",
        "event_has_passed": "false",
        "post_event": "off",
        "post_event_monitoring": False,
        "post_event_failure": "false",
        "failed_reclaim": "0",
        "price_below_event_vwap": "no",
    }
    quiet_snapshot = {
        "return_4h": 0.0,
        "return_24h": 0.0,
        "volume_zscore_24h": 3.0,
    }
    assert scanner.classify_market_state(quiet_snapshot, false_claims) == (
        scanner.NO_REACTION
    )

    boolean_numerics = {
        "return_4h": 1.0,
        "return_24h": 30.0,
        "volume_zscore_24h": 1.0,
        "open_interest_delta": True,
        "funding_level": True,
        "funding_zscore": True,
        "liquidation_imbalance": True,
    }
    assert scanner.classify_market_state(boolean_numerics) == scanner.LATE_MOMENTUM


def test_market_anomaly_false_metadata_does_not_add_source_or_derivatives_claims():
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as scanner

    rows = [
        {
            "id": "typed-token",
            "symbol": "typed",
            "return_unit": "percent_points",
            "return_4h": 10.0,
            "return_24h": 20.0,
            "relative_return_vs_btc_4h": 10.0,
            "volume_zscore_24h": 3.0,
            "liquidity_usd": 10_000_000.0,
            "derivatives_available": "false",
            "open_interest_delta": False,
            "funding_level": False,
            "funding_zscore": False,
            "catalyst_confirmed": "false",
            "accepted_evidence_count": 0,
            "observed_at": "2026-06-15T16:00:00Z",
        }
    ]
    _, anomalies = scanner.scan_market_rows(
        rows,
        observed_at="2026-06-15T16:00:00Z",
    )

    assert len(anomalies) == 1
    assert anomalies[0]["anomaly_type"] == scanner.CONFIRMED_BREAKOUT
    assert anomalies[0]["derivatives_available"] is False
    assert anomalies[0]["priority_components"]["derivatives_availability"] == 0.0
    assert anomalies[0]["source_catalyst_knownness"] == "unknown"


def test_market_anomaly_source_knownness_requires_typed_evidence_reference():
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as scanner

    base = {
        "id": "source-contract-token",
        "symbol": "SOURCE",
        "return_unit": "percent_points",
        "return_4h": 10.0,
        "return_24h": 20.0,
        "relative_return_vs_btc_4h": 10.0,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 10_000_000.0,
        "freshness_status": "fresh",
        "observed_at": "2026-07-21T11:30:00Z",
    }

    def anomaly_for(**evidence):
        _, anomalies = scanner.scan_market_rows(
            [{**base, **evidence}],
            observed_at="2026-07-21T11:30:00Z",
        )
        assert len(anomalies) == 1
        return anomalies[0]

    for evidence in (
        {"published_at": "2026-07-21T11:00:00Z"},
        {"event_time": "2026-07-21T12:00:00Z"},
        {"source_url": {"borrowed": "https://example.test/event"}},
        {"official_source_url": ["https://example.test/event"]},
        {"source_urls": {"borrowed": "https://example.test/event"}},
        {"source_urls": ["", {"borrowed": "https://example.test/event"}]},
        {"accepted_evidence_count": True},
    ):
        anomaly = anomaly_for(**evidence)
        assert anomaly["source_catalyst_knownness"] == "unknown"
        assert anomaly["priority_components"]["source_catalyst_unknownness"] == 7.0

    for evidence in (
        {"source_url": "https://example.test/event"},
        {"official_source_url": "https://example.test/official"},
        {"source_urls": ["https://example.test/event"]},
        {"accepted_evidence_count": 1},
        {"catalyst_confirmed": "true"},
    ):
        anomaly = anomaly_for(**evidence)
        assert anomaly["source_catalyst_knownness"] == "known"
        assert anomaly["priority_components"]["source_catalyst_unknownness"] == -4.0


def test_market_anomaly_source_plan_requires_typed_pack_names():
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as scanner

    base = {
        "id": "source-plan-token",
        "symbol": "PLAN",
        "return_unit": "percent_points",
        "return_4h": 10.0,
        "return_24h": 20.0,
        "relative_return_vs_btc_4h": 10.0,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 10_000_000.0,
        "freshness_status": "fresh",
    }

    _, malformed_anomalies = scanner.scan_market_rows(
        [{
            **base,
            "suggested_source_packs_to_search": [
                {"borrowed": "official_project"},
                True,
            ],
        }],
        observed_at="2026-07-21T11:40:00Z",
    )
    malformed_queue = scanner.build_catalyst_search_queue(malformed_anomalies)
    assert malformed_anomalies[0]["suggested_source_packs_to_search"] == []
    assert malformed_queue[0]["suggested_source_packs"] == []
    assert malformed_queue[0]["source_plan_status"] == "missing_plan"

    _, valid_anomalies = scanner.scan_market_rows(
        [{
            **base,
            "suggested_source_packs_to_search": (
                "official_project",
                " project_blog_rss ",
            ),
        }],
        observed_at="2026-07-21T11:40:00Z",
    )
    valid_queue = scanner.build_catalyst_search_queue(valid_anomalies)
    assert valid_anomalies[0]["suggested_source_packs_to_search"] == [
        "official_project",
        "project_blog_rss",
    ]
    assert valid_queue[0]["suggested_source_packs"] == [
        "official_project",
        "project_blog_rss",
    ]
    assert valid_queue[0]["source_plan_status"] == "planned"


def test_market_anomaly_queue_parses_false_instead_of_using_string_truthiness():
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as scanner

    anomaly = {
        "market_anomaly_id": "mkt:typed-token:test",
        "canonical_asset_id": "typed-token",
        "symbol": "TYPED",
        "coin_id": "typed-token",
        "market_state_class": scanner.CONFIRMED_BREAKOUT,
        "anomaly_bucket": scanner.HIGH_LIQUIDITY_BREAKOUT,
        "priority": 50.0,
        "needs_catalyst_search": "false",
        "observed_at": "2026-06-15T16:00:00Z",
        "suggested_source_packs_to_search": ["official_project"],
    }
    assert scanner.build_catalyst_search_queue([anomaly]) == []

    anomaly["needs_catalyst_search"] = "true"
    assert len(scanner.build_catalyst_search_queue([anomaly])) == 1


def test_market_anomaly_sector_controls_require_explicit_semantic_truth():
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as scanner
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_report as report

    for false_value in (False, None, "false", "0", "no", "off", 2):
        assert scanner._is_sector_or_theme(  # noqa: SLF001
            {
                "symbol": "MOVE",
                "coin_id": "move-token",
                "is_theme_or_sector": false_value,
                "quote_asset_excluded": false_value,
                "is_quote_asset": false_value,
            }
        ) is False
        assert report._is_sector_or_theme(  # noqa: SLF001
            {
                "symbol": "MOVE",
                "coin_id": "move-token",
                "is_theme_or_sector": false_value,
                "quote_asset_excluded": false_value,
                "is_quote_asset": false_value,
            }
        ) is False

    for true_value in (True, "true", "1", "yes", "y", "on", 1):
        assert scanner._is_sector_or_theme(  # noqa: SLF001
            {
                "symbol": "MOVE",
                "coin_id": "move-token",
                "is_theme_or_sector": true_value,
            }
        ) is True
        assert report._is_sector_or_theme(  # noqa: SLF001
            {
                "symbol": "MOVE",
                "coin_id": "move-token",
                "is_theme_or_sector": true_value,
            }
        ) is True

    for untradable_value in (False, "false", "0", "no", "n", "off", 0, 0.0):
        assert scanner._is_sector_or_theme(  # noqa: SLF001
            {
                "symbol": "MOVE",
                "coin_id": "move-token",
                "is_tradable_asset": untradable_value,
            }
        ) is True
        assert report._is_sector_or_theme(  # noqa: SLF001
            {
                "symbol": "MOVE",
                "coin_id": "move-token",
                "is_tradable_asset": untradable_value,
            }
        ) is True

    text = report.format_market_anomaly_report(
        [
            {
                "symbol": "MOVE",
                "market_state_class": scanner.CONFIRMED_BREAKOUT,
                "decision_model_v2_catalyst_required": "false",
            }
        ],
        cfg=scanner.MarketAnomalyScannerConfig(),
    )
    assert "catalyst_required=false" in text


def test_semantically_untradable_asset_cannot_create_market_anomaly():
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as scanner

    base = {
        "id": "blocked-token",
        "coin_id": "blocked-token",
        "symbol": "BLOCK",
        "return_unit": "percent_points",
        "return_4h": 12.0,
        "return_24h": 18.0,
        "relative_return_vs_btc_4h": 10.0,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 100_000_000.0,
        "spread_bps": 5.0,
        "freshness_status": "fresh",
    }

    for untradable_value in (False, "false", "0", "no", "n", "off", 0, 0.0):
        snapshots, anomalies = scanner.scan_market_rows(
            [{**base, "is_tradable_asset": untradable_value}],
            observed_at="2026-07-21T10:50:00Z",
        )
        assert len(snapshots) == 1
        assert anomalies == []


def test_market_confirmation_dex_flags_and_numeric_evidence_are_type_safe():
    import crypto_rsi_scanner.event_alpha.radar.market_confirmation as confirmation

    for false_value in (False, None, "false", "0", "no", "off", 2):
        components, reasons, observed, illiquid = confirmation._dex_components(  # noqa: SLF001
            {
                "new_pool": false_value,
                "new_pool_detected": false_value,
                "pool_age_hours": True,
            }
        )
        assert "new_dex_pool" not in components
        assert confirmation.MarketConfirmationReason.NEW_DEX_POOL_DETECTED.value not in reasons
        assert observed == 0
        assert illiquid is False

    components, reasons, observed, illiquid = confirmation._dex_components(  # noqa: SLF001
        {"new_pool": "true"}
    )
    assert components["new_dex_pool"] == 8.0
    assert confirmation.MarketConfirmationReason.NEW_DEX_POOL_DETECTED.value in reasons
    assert observed == 1
    assert illiquid is False


def test_market_anomaly_artifacts_are_research_only_and_seed_search():
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as event_market_anomaly_scanner

    rows = event_market_anomaly_scanner.load_market_rows("fixtures/event_market_anomaly/market_rows.json")
    with TemporaryDirectory() as tmp:
        result = event_market_anomaly_scanner.run_market_anomaly_scan(
            market_rows=rows,
            namespace_dir=tmp,
            observed_at="2026-06-15T16:00:00Z",
            profile="fixture",
            artifact_namespace="market_anomaly_smoke",
        )
        loaded = event_market_anomaly_scanner.load_market_anomaly_rows(tmp)

        assert result.snapshot_count == 8
        assert result.anomaly_count == 5
        assert result.catalyst_search_queue_count == 5
        assert result.snapshots_path.exists()
        assert result.anomalies_path.exists()
        assert result.catalyst_search_queue_path.exists()
        assert result.report_path.exists()
        assert len(loaded) == 5
        queue = event_market_anomaly_scanner.load_market_anomaly_catalyst_search_queue(tmp)
        assert len(queue) == 5
        assert all(row["no_alert_until_evidence"] is True for row in queue)
        assert all(row["research_only"] is True for row in queue)
        assert all(row["telegram_sends"] == 0 for row in queue)
        assert all(row["trades_created"] == 0 for row in queue)
        assert all(row["paper_trades_created"] == 0 for row in queue)
        assert all(row["normal_rsi_signal_rows_written"] == 0 for row in queue)
        assert all(row["triggered_fade_created"] == 0 for row in queue)
        assert all(row.get("search_queries") for row in queue)
        assert all(row["created_alert"] is False for row in loaded)
        assert all(row["research_only"] is True for row in loaded)
        assert all(row["needs_catalyst_search"] is True for row in loaded)
        assert all(row.get("suggested_source_packs_to_search") for row in loaded)
        assert not any("alert_id" in row or "tier" in row for row in loaded)
        fade_row = next(row for row in loaded if row["coin_id"] == "token-f")
        assert fade_row["anomaly_type"] == "post_event_fade_setup"
        assert fade_row["market_state_class"] == "post_event_fade_setup"
        assert fade_row["suggested_source_packs_to_search"] == [
            "perp_listing_squeeze_pack",
            "cryptopanic_tagged",
            "coinalyze_derivatives",
        ]
        report_text = result.report_path.read_text(encoding="utf-8")
        assert "Top Market Anomalies for Catalyst Enrichment" in report_text
        assert "Catalyst Enrichment Queue" in report_text
        assert "catalyst_required=false" in report_text
        assert "no independent catalyst after bounded search" not in report_text


def test_market_anomaly_scanner_uses_registry_and_cached_universe_rows():
    import crypto_rsi_scanner.event_alpha.radar.asset_registry as event_asset_registry
    import crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner as event_market_anomaly_scanner

    universe_rows = [
        {
            "id": "bitcoin",
            "symbol": "btc",
            "return_4h": 0.001,
            "return_24h": 0.002,
            "total_volume": 20_000_000_000,
            "market_cap": 1_000_000_000_000,
            "observed_at": "2026-06-15T16:00:00Z",
        },
        {
            "id": "ethereum",
            "symbol": "eth",
            "return_4h": 0.001,
            "return_24h": 0.003,
            "total_volume": 10_000_000_000,
            "market_cap": 400_000_000_000,
            "observed_at": "2026-06-15T16:00:00Z",
        },
        {
            "id": "queue-token",
            "symbol": "queue",
            "name": "Queue Token",
            "return_4h": 0.12,
            "return_24h": 0.22,
            "volume_zscore_24h": 4.1,
            "total_volume": 45_000_000,
            "market_cap": 600_000_000,
            "liquidity_usd": 9_000_000,
            "observed_at": "2026-06-15T16:00:00Z",
        },
    ]
    registry = (
        event_asset_registry.CanonicalAsset(
            canonical_asset_id="queue-token",
            symbol="QUEUE",
            coin_id="queue-token",
            name="Queue Token",
            liquidity_tier="large",
            venues=("binance", "coinalyze"),
            perp_symbols=("QUEUEUSDT_PERP.A",),
            coinalyze_symbols=("QUEUEUSDT_PERP.A",),
            eligible_lanes=("research", "derivatives"),
        ),
    )
    snapshots, anomalies = event_market_anomaly_scanner.scan_market_rows(
        [],
        coingecko_universe_rows=universe_rows,
        asset_registry=registry,
        observed_at="2026-06-15T16:00:00Z",
    )
    by_coin = {row["coin_id"]: row for row in anomalies}

    assert len(snapshots) == 3
    assert by_coin["queue-token"]["canonical_asset_id"] == "queue-token"
    assert by_coin["queue-token"]["anomaly_bucket"] == "high_liquidity_breakout"
    assert by_coin["queue-token"]["derivatives_available"] is True
    assert by_coin["queue-token"]["market_state_snapshot"]["liquidity_tier"] == "large"


def test_makefile_exposes_market_anomaly_targets():
    text = Path("Makefile").read_text(encoding="utf-8")

    assert "event-alpha-market-anomaly-scan" in text
    assert "event-alpha-market-anomaly-smoke" in text
    assert "--event-alpha-market-anomaly-scan" in text


def test_bybit_announcement_provider_supports_documented_query_params():
    from crypto_rsi_scanner.event_providers.bybit_announcements import (
        BybitAnnouncementProvider,
        build_bybit_public_request,
    )

    provider = BybitAnnouncementProvider(
        None,
        live_enabled=True,
        locale="en-US",
        announcement_type="new_crypto",
        tag="spot",
        page=3,
        limit=50,
    )
    url = provider._request_url()

    assert "/v5/announcements/index" in url
    assert "locale=en-US" in url
    assert "type=new_crypto" in url
    assert "tag=spot" in url
    assert "page=3" in url
    assert "limit=50" in url

    first = build_bybit_public_request(url)
    second = build_bybit_public_request(url)
    first_request_id = first.get_header("Cdn-request-id")
    second_request_id = second.get_header("Cdn-request-id")
    assert first_request_id
    assert second_request_id
    assert first_request_id != second_request_id


def test_official_exchange_fixture_lanes_and_quote_filtering():
    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.providers.official_exchange as event_official_exchange

    original_allow_major = config.EVENT_ALPHA_ALLOW_MAJOR_PAIR_CATALYSTS
    try:
        config.EVENT_ALPHA_ALLOW_MAJOR_PAIR_CATALYSTS = False
        with TemporaryDirectory() as tmp:
            result = event_official_exchange.run_official_exchange_scan(
                namespace_dir=tmp,
                provider_paths={
                    "binance_announcements": "fixtures/event_discovery/official_exchange_binance_announcements.json",
                    "bybit_announcements": "fixtures/event_discovery/official_exchange_bybit_announcements.json",
                },
                profile="fixture",
                artifact_namespace="official_exchange_smoke",
                run_mode="fixture",
                run_id="run-official-fixture",
                observed_at="2026-06-15T16:00:00Z",
            )
            candidates = event_official_exchange.load_official_listing_candidates(tmp)
        with TemporaryDirectory() as tmp:
            config.EVENT_ALPHA_ALLOW_MAJOR_PAIR_CATALYSTS = True
            allowed = event_official_exchange.run_official_exchange_scan(
                namespace_dir=tmp,
                provider_paths={
                    "binance_announcements": "fixtures/event_discovery/official_exchange_binance_announcements.json",
                    "bybit_announcements": "fixtures/event_discovery/official_exchange_bybit_announcements.json",
                },
                profile="fixture",
                artifact_namespace="official_exchange_smoke",
                run_mode="fixture",
                run_id="run-official-fixture",
                observed_at="2026-06-15T16:00:00Z",
            )
    finally:
        config.EVENT_ALPHA_ALLOW_MAJOR_PAIR_CATALYSTS = original_allow_major

    by_symbol = {str(row.get("symbol") or ""): row for row in candidates}
    allowed_by_symbol = {str(row.get("symbol") or ""): row for row in allowed.candidates}
    event_types = {row["event_type"] for row in result.events}

    assert result.announcement_count >= 8
    assert result.event_count == result.announcement_count
    assert result.candidate_count >= 7
    assert "spot_listing" in event_types
    assert "perp_listing" in event_types
    assert "delisting" in event_types
    assert by_symbol["TESTSPOT"]["opportunity_type"] == "EARLY_LONG_RESEARCH"
    assert by_symbol["TESTPERP"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
    assert by_symbol["TESTDEL"]["opportunity_type"] == "RISK_ONLY"
    assert by_symbol["TESTFARM"]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert "deterministic_resolver_validation_missing" in by_symbol["TESTFARM"]["why_not_alertable"]
    assert "USDT" not in by_symbol
    assert by_symbol["BTC"]["coin_id"] == "bitcoin"
    assert by_symbol["BTC"]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert by_symbol["BTC"]["major_pair_simple_announcement"] is True
    assert "major_pair_simple_announcement_not_alpha" in by_symbol["BTC"]["why_not_alertable"]
    assert "major_pair_simple_announcement_capped" in by_symbol["BTC"]["reason_codes"]
    assert allowed_by_symbol["BTC"]["opportunity_type"] == "EARLY_LONG_RESEARCH"
    assert all(row["source_class"] == "official_exchange" for row in candidates)
    assert all(row["created_alert"] is False for row in candidates)
    assert all(row["research_only"] is True for row in candidates)


def test_cryptopanic_listing_article_is_not_official_exchange_proof():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction
    import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs

    row = {
        "provider": "cryptopanic",
        "source_class": "cryptopanic_tagged",
        "source_pack": "official_exchange_listing_pack",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "title": "CHZ fans react to listing rumors",
        "currency_tags": ["CHZ"],
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "market_snapshot": {
            "return_24h": 0.20,
            "volume_zscore_24h": 3.0,
            "market_context_freshness_status": "fresh",
        },
    }
    pack_result = event_source_packs.evaluate_pack_evidence(row, pack=event_source_packs.get_source_pack("official_exchange_listing_pack"))
    reaction = event_market_reaction.evaluate_market_reaction({
        **row,
        "impact_path_type": "listing_liquidity_event",
        "evidence_quality_score": 86,
        "accepted_evidence_count": 1,
    })

    assert pack_result["source_pack_validated_digest_sufficient"] is False
    assert "preferred_source_missing" in pack_result["source_pack_missing_evidence"]
    assert reaction.opportunity_type == "UNCONFIRMED_RESEARCH"
    assert "official_exchange_source_required" in reaction.why_not_alertable


def test_daily_brief_renders_official_exchange_section():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.providers.official_exchange as event_official_exchange

    with TemporaryDirectory() as tmp:
        result = event_official_exchange.run_official_exchange_scan(
            namespace_dir=tmp,
            provider_paths={
                "binance_announcements": "fixtures/event_discovery/official_exchange_binance_announcements.json",
                "bybit_announcements": "fixtures/event_discovery/official_exchange_bybit_announcements.json",
            },
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            run_mode="fixture",
            run_id="run-official-fixture",
            observed_at="2026-06-15T16:00:00Z",
        )
        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[],
            official_exchange_candidate_rows=result.candidates,
            requested_profile="fixture",
            artifact_namespace="official_exchange_smoke",
            include_test_artifacts=True,
        )

    assert "## Fresh Official Exchange Catalysts" in brief
    assert "TESTSPOT/test-spot" in brief
    assert "TESTPERP/test-perp" in brief


def test_makefile_exposes_official_exchange_targets():
    text = Path("Makefile").read_text(encoding="utf-8")

    assert "event-alpha-official-exchange-report" in text
    assert "event-alpha-official-exchange-smoke" in text
    assert "--event-alpha-official-exchange-report" in text


def test_scheduled_catalyst_messari_fixture_shape_and_materiality():
    import crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts as event_scheduled_catalysts

    with TemporaryDirectory() as tmp:
        result = event_scheduled_catalysts.run_scheduled_catalyst_scan(
            namespace_dir=tmp,
            provider_paths={
                "messari_unlocks": "fixtures/event_discovery/scheduled_messari_unlocks.json",
            },
            profile="fixture",
            artifact_namespace="scheduled_catalyst_smoke",
            run_mode="fixture",
            run_id="run-messari-fixture",
            observed_at="2026-06-15T16:00:00Z",
        )

    assert result.scheduled_count == 1
    assert result.unlock_count == 1
    row = result.unlock_candidates[0]
    assert row["source_provider"] == "messari_unlocks"
    assert row["symbol"] == "TESTVEST"
    assert row["coin_id"] == "test-vesting"
    assert row["unlock_pct_circulating"] == 0.055
    assert row["unlock_usd"] == 1260000
    assert row["unlock_vs_30d_adv"] == 1.1
    assert row["vesting_category"] == "investors"
    assert row["cliff_or_linear"] == "cliff"
    assert row["event_timestamp_confidence"] == "confirmed"
    assert row["structured_unlock_evidence"] is True
    assert row["created_alert"] is False
    assert row["research_only"] is True


def test_daily_brief_renders_scheduled_catalyst_sections():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts as event_scheduled_catalysts

    with TemporaryDirectory() as tmp:
        result = event_scheduled_catalysts.run_scheduled_catalyst_scan(
            namespace_dir=tmp,
            provider_paths={
                "tokenomist": "fixtures/event_discovery/scheduled_tokenomist_unlocks.json",
                "coinmarketcal": "fixtures/event_discovery/scheduled_coinmarketcal_events.json",
            },
            profile="fixture",
            artifact_namespace="scheduled_catalyst_smoke",
            run_mode="fixture",
            run_id="run-scheduled-fixture",
            observed_at="2026-06-15T16:00:00Z",
        )
        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[],
            scheduled_catalyst_rows=result.scheduled_events,
            unlock_candidate_rows=result.unlock_candidates,
            requested_profile="fixture",
            artifact_namespace="scheduled_catalyst_smoke",
            include_test_artifacts=True,
        )

    assert "## Upcoming Scheduled Catalysts" in brief
    assert "## Unlock / Supply Risk" in brief
    assert "## Catalyst Calendar Gaps" in brief
    assert "## Near-Term Events Needing Market Watch" in brief
    assert "TESTUP/test-upgrade" in brief
    assert "TESTUNLOCK/test-unlock" in brief


def test_makefile_exposes_scheduled_catalyst_targets():
    text = Path("Makefile").read_text(encoding="utf-8")

    assert "event-alpha-scheduled-catalyst-report" in text
    assert "event-alpha-scheduled-catalyst-smoke" in text
    assert "event-alpha-unlock-risk-smoke" in text
    assert "event-alpha-tokenomist-preflight" in text
    assert "event-alpha-messari-unlocks-preflight" in text
    assert "event-alpha-coinmarketcal-preflight" in text
    assert "--event-alpha-scheduled-catalyst-report" in text
    assert "--event-alpha-tokenomist-preflight" in text
    assert "--event-alpha-messari-unlocks-preflight" in text
    assert "--event-alpha-coinmarketcal-preflight" in text


def test_derivatives_crowding_fixture_lanes_and_artifacts():
    import crypto_rsi_scanner.event_alpha.radar.derivatives_crowding as event_derivatives_crowding

    with TemporaryDirectory() as tmp:
        result = event_derivatives_crowding.run_derivatives_crowding_scan(
            namespace_dir=tmp,
            derivatives_path="fixtures/event_derivatives_crowding/derivatives_crowding_rows.json",
            profile="fixture",
            artifact_namespace="derivatives_crowding_smoke",
            run_mode="fixture",
            run_id="run-derivatives-fixture",
            observed_at="2026-06-15T16:00:00Z",
        )
        states = event_derivatives_crowding.load_derivatives_state(tmp)
        evaluated_rows = event_derivatives_crowding.load_derivatives_candidates(tmp)
        fade_rows = event_derivatives_crowding.load_fade_review_candidates(tmp)
        derivatives_candidates_path_exists = result.derivatives_candidates_path.exists()
        report = result.report_path.read_text(encoding="utf-8")

    by_symbol = {str(row.get("symbol") or ""): row for row in result.candidate_rows}

    assert result.derivatives_state_count == 4
    assert result.evaluated_candidate_count == 5
    assert result.fade_review_candidate_count == 1
    assert len(states) == 4
    assert len(evaluated_rows) == 5
    assert derivatives_candidates_path_exists is True
    assert len(fade_rows) == 1
    state_by_symbol = {str(row.get("symbol") or ""): row for row in states}
    assert state_by_symbol["TESTLIST"]["supported_metric_status"]["predicted_funding"] == "implemented"
    assert state_by_symbol["TESTLIST"]["supported_metric_status"]["basis"] == "fixture_only"
    assert state_by_symbol["TESTLIST"]["funding_rate_unit"] == "decimal_rate"
    assert state_by_symbol["TESTLIST"]["basis_unit"] == "decimal_rate"
    assert state_by_symbol["TESTLIST"]["open_interest_freshness"] == "fresh"
    assert state_by_symbol["TESTLIST"]["derivatives_snapshot_freshness_status"] == "fresh"
    assert by_symbol["TESTLIST"]["opportunity_type"] == "FADE_SHORT_REVIEW"
    assert by_symbol["TESTLIST"]["completed_move"] is True
    assert by_symbol["TESTLIST"]["fade_requirements_met"] is True
    assert by_symbol["TESTBREAK"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
    assert by_symbol["TESTCROWD"]["opportunity_type"] in {"FADE_SHORT_REVIEW", "CONFIRMED_LONG_RESEARCH"}
    if by_symbol["TESTCROWD"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH":
        assert "confirmed_long_derivatives_crowding_warning" in by_symbol["TESTCROWD"]["warnings"]
        assert "warnings: confirmed_long_derivatives_crowding_warning" in report
    assert by_symbol["TESTILLIQ"]["opportunity_type"] == "RISK_ONLY"
    assert by_symbol["TESTRISK"]["opportunity_type"] == "RISK_ONLY"
    assert all(row["created_alert"] is False for row in result.candidate_rows)
    assert all(row["normal_rsi_signal_written"] is False for row in result.candidate_rows)
    assert all(row["triggered_fade_created"] is False for row in result.candidate_rows)
    assert all(row["paper_trade_created"] is False for row in result.candidate_rows)
    assert "predicted_funding=0.2%" in report
    assert "basis=2.4%" in report
    assert "basis=fixture_only" in report
    assert "Research-only. Not a trade signal" in report


def test_derivatives_crowding_missing_predicted_funding_and_basis_are_explicit():
    import json
    import crypto_rsi_scanner.event_alpha.radar.derivatives_crowding as event_derivatives_crowding
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    payload = {
        "derivatives": [
            {
                "provider": "coinalyze",
                "coin_id": "testmissing",
                "symbol": "TESTMISSUSDT_PERP",
                "base_symbol": "TESTMISS",
                "market": "TESTMISSUSDT_PERP",
                "timestamp": "2026-06-15T15:30:00Z",
                "open_interest": 9000000,
                "open_interest_delta_24h": 0.22,
                "funding_rate": 0.0008,
                "funding_zscore": 1.2,
                "liquidation_long_usd": 500000,
                "liquidation_short_usd": 250000,
                "long_short_ratio": 1.7,
                "perp_volume": 22000000,
                "spot_volume": 9000000,
            }
        ],
        "candidates": [
            {
                "symbol": "TESTMISS",
                "coin_id": "testmissing",
                "event_name": "TESTMISS moderate crowding check",
                "source_class": "derivatives_provider",
                "source_pack": "derivatives_crowding_pack",
                "impact_path_type": "derivatives_crowding_research",
                "playbook_type": "derivatives_crowding_research",
                "evidence_quality_score": 82,
                "accepted_evidence_count": 1,
                "market_snapshot": {
                    "return_24h": 0.08,
                    "return_4h": 0.03,
                    "market_context_freshness_status": "fresh",
                },
            }
        ],
    }
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "derivatives.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        result = event_derivatives_crowding.run_derivatives_crowding_scan(
            namespace_dir=tmp,
            derivatives_path=path,
            profile="fixture",
            artifact_namespace="missing_metric_status",
            run_mode="fixture",
            run_id="run-missing-metrics",
            observed_at="2026-06-15T16:00:00Z",
        )
        report = result.report_path.read_text(encoding="utf-8")

    state = result.derivatives_state_rows[0]
    candidate = {**result.candidate_rows[0], "alert_id": "TESTMISS", "tier": "STORE_ONLY"}
    card = event_research_cards.render_research_card("TESTMISS", alert_rows=[candidate])

    assert state["supported_metric_status"]["predicted_funding"] == "missing_from_response"
    assert state["supported_metric_status"]["basis"] == "not_implemented"
    assert state["basis_freshness"] == "missing"
    assert "predicted_funding=missing_from_response" in report
    assert "basis=not_implemented" in report
    assert card.found is True
    assert "predicted=missing_from_response" in card.markdown
    assert "- Basis: not_implemented" in card.markdown
    assert "predicted=n/a" not in card.markdown
    assert "- Basis: n/a" not in card.markdown


def test_daily_brief_renders_derivatives_fade_review_section():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.radar.derivatives_crowding as event_derivatives_crowding

    with TemporaryDirectory() as tmp:
        result = event_derivatives_crowding.run_derivatives_crowding_scan(
            namespace_dir=tmp,
            derivatives_path="fixtures/event_derivatives_crowding/derivatives_crowding_rows.json",
            profile="fixture",
            artifact_namespace="derivatives_crowding_smoke",
            run_mode="fixture",
            run_id="run-derivatives-fixture",
            observed_at="2026-06-15T16:00:00Z",
        )
        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[],
            derivatives_state_rows=result.derivatives_state_rows,
            fade_review_candidate_rows=result.fade_review_candidates,
            requested_profile="fixture",
            artifact_namespace="derivatives_crowding_smoke",
            include_test_artifacts=True,
        )

    assert "## Derivatives Crowding / Fade-Review Research" in brief
    assert "Research-only. Not a trade signal" in brief
    assert "TESTLIST/testlist" in brief
    assert "crowding=extreme" in brief


def test_research_card_renders_derivatives_crowding_section():
    import crypto_rsi_scanner.event_alpha.radar.derivatives_crowding as event_derivatives_crowding
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    with TemporaryDirectory() as tmp:
        result = event_derivatives_crowding.run_derivatives_crowding_scan(
            namespace_dir=tmp,
            derivatives_path="fixtures/event_derivatives_crowding/derivatives_crowding_rows.json",
            profile="fixture",
            artifact_namespace="fade_review_smoke",
            run_mode="fixture",
            run_id="run-derivatives-fixture",
            observed_at="2026-06-15T16:00:00Z",
        )
    row = next(item for item in result.fade_review_candidates if item["symbol"] == "TESTLIST")
    row = {**row, "alert_id": "TESTLIST", "tier": "STORE_ONLY"}
    card = event_research_cards.render_research_card("TESTLIST", alert_rows=[row])

    assert card.found is True
    assert "## Derivatives / Crowding" in card.markdown
    assert "- Research-only. Not a trade signal." in card.markdown
    assert "predicted=+0.15%" in card.markdown
    assert "- Basis: +2.40%" in card.markdown
    assert "basis=fixture_only" in card.markdown
    assert "predicted=n/a" not in card.markdown
    assert "- Crowding class: extreme" in card.markdown
    assert "What invalidates fade review" in card.markdown


def test_makefile_exposes_derivatives_targets():
    text = Path("Makefile").read_text(encoding="utf-8")

    assert "event-alpha-derivatives-report" in text
    assert "event-alpha-derivatives-smoke" in text
    assert "event-alpha-fade-review-smoke" in text
    assert "--event-alpha-derivatives-report" in text


def test_event_instrument_resolver_cross_provider_identity_and_guardrails():
    import json

    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.radar.asset_registry as event_asset_registry
    import crypto_rsi_scanner.event_alpha.radar.instrument_resolver as event_instrument_resolver

    with TemporaryDirectory() as tmp:
        universe_path = Path(tmp) / "coingecko_universe.json"
        universe_path.write_text(
            json.dumps({"coins": [{"id": "chiliz", "symbol": "chz", "name": "Chiliz", "market_cap_rank": 80}]}),
            encoding="utf-8",
        )
        official_rows = [
            {
                "row_type": "official_listing_candidate",
                "provider": "binance_announcements",
                "exchange": "binance",
                "symbol": "CHZ",
                "coin_id": "chiliz",
                "pairs": ["CHZ/USDT"],
                "listing_scope": "spot",
            }
        ]
        coinalyze_rows = [
            {
                "row_type": "derivatives_state_snapshot",
                "provider": "coinalyze",
                "symbol": "CHZUSDT_PERP.A",
                "market_symbol": "CHZUSDT_PERP.A",
                "base_symbol": "CHZ",
                "coin_id": "chiliz",
            }
        ]
        registry = event_asset_registry.build_asset_registry(
            fixture_path=config.EVENT_ASSET_REGISTRY_PATH,
            coingecko_universe_path=universe_path,
            official_exchange_rows=official_rows,
            coinalyze_rows=coinalyze_rows,
        )
        rows = [
            {"provider": "cryptopanic", "source_class": "cryptopanic_tagged", "symbol": "CHZ", "coin_id": "chiliz"},
            *official_rows,
            *coinalyze_rows,
        ]
        enriched, _resolutions = event_instrument_resolver.resolve_rows(rows, registry)
        assert {row["canonical_asset_id"] for row in enriched} == {"chiliz"}
        assert all(row["instrument_resolver_confidence"] >= 0.9 for row in enriched)
        assert all("coinalyze_symbol_not_linked_to_asset" not in row.get("instrument_resolver_warnings", ()) for row in enriched)
        chiliz = next(asset for asset in registry if asset.canonical_asset_id == "chiliz")
        assert "CHZUSDT_PERP.A" in chiliz.coinalyze_symbols
        assert "CHZ/USDT" in chiliz.binance_symbols

        guardrail_rows, _guardrail_resolutions = event_instrument_resolver.resolve_rows(
            [
                {"row_type": "official_listing_candidate", "symbol": "BTC", "coin_id": "bitcoin", "major_pair_simple_announcement": True},
                {"row_type": "official_listing_candidate", "symbol": "USDT", "coin_id": "tether", "opportunity_type": "EARLY_LONG_RESEARCH"},
                {"row_type": "scheduled_catalyst_event", "symbol": "SECTOR", "coin_id": "ai_theme"},
                {"row_type": "event_integrated_radar_candidate", "symbol": "VELVET", "coin_id": "velvet", "candidate_role": "direct_event"},
            ],
            registry,
        )
        btc, quote, sector, proxy = guardrail_rows
        assert btc["canonical_asset_id"] == "bitcoin"
        assert "major_pair_simple_announcement_capped" in btc["instrument_resolver_warnings"]
        assert quote["is_tradable_asset"] is False
        assert quote["quote_asset_excluded"] is True
        assert "quote_asset_target_excluded" in quote["instrument_resolver_warnings"]
        assert sector["is_theme_or_sector"] is True
        assert sector["is_tradable_asset"] is False
        assert sector["instrument_resolver_status"] == "resolved_theme"
        assert proxy["canonical_asset_id"] == "velvet"
        assert proxy["candidate_role"] == "proxy_instrument"
        assert "proxy_asset_labeled_proxy" in proxy["instrument_resolver_warnings"]


def test_integrated_radar_fixture_lanes_and_merge():
    import json

    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.artifacts.paths as event_artifact_paths
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    with TemporaryDirectory() as tmp:
        context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=tmp,
            artifact_namespace="integrated_test",
        )
        result = event_integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        rows = [
            json.loads(line)
            for line in result.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        by_symbol = {row["symbol"]: row for row in rows}
        assert result.asset_registry_path and result.asset_registry_path.exists()
        assert result.instrument_resolution_path and result.instrument_resolution_path.exists()
        assert result.asset_resolution_report_path and result.asset_resolution_report_path.exists()
        assert result.asset_registry_assets >= 6
        assert result.instrument_resolution_rows >= len(rows)

        assert by_symbol["TESTLIST"]["opportunity_type"] == "EARLY_LONG_RESEARCH"
        assert by_symbol["TESTPERP"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
        assert by_symbol["TESTFADE"]["opportunity_type"] == "FADE_SHORT_REVIEW"
        assert by_symbol["TESTUNLOCK"]["opportunity_type"] == "RISK_ONLY"
        assert by_symbol["TESTRUMOR"]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
        assert by_symbol["SECTOR"]["opportunity_type"] == "DIAGNOSTIC"
        assert by_symbol["TKNB"]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
        assert by_symbol["TKNB"]["dex_liquidity_level"] in {"moderate", "strong"}
        assert by_symbol["TKNC"]["opportunity_type"] == "DIAGNOSTIC"
        assert "dex_low_liquidity_pump_diagnostic_only" in by_symbol["TKNC"]["warnings"]
        assert by_symbol["AAVE"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
        assert by_symbol["AAVE"]["protocol_fundamentals_class"] == "protocol_revenue_tvl_growth"
        assert by_symbol["AAVE"]["protocol_metrics_level"] in {"moderate", "strong"}
        assert by_symbol["TKND"]["opportunity_type"] == "RISK_ONLY"
        assert by_symbol["TKND"]["protocol_fundamentals_class"] == "protocol_fundamentals_deterioration"
        assert by_symbol["BTC"]["opportunity_type"] != "EARLY_LONG_RESEARCH"
        assert by_symbol["BTC"]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
        assert by_symbol["BTC"]["why_now"] == "simple major-pair announcement capped as unconfirmed research"
        assert "major_pair_simple_announcement_capped" in by_symbol["BTC"]["warnings"]
        assert "major_pair_simple_announcement_not_alpha" in by_symbol["BTC"]["why_not_alertable"]
        assert by_symbol["BTC"]["source_url"]
        assert by_symbol["BTC"]["official_exchange_event"]["event_type"] == "new_trading_pair"
        assert by_symbol["BTC"]["canonical_asset_id"] == "bitcoin"
        assert by_symbol["BTC"]["major_base_asset"] is True

        assert set(by_symbol["TESTPERP"]["source_origins"]) >= {"official_exchange", "market_anomaly", "derivatives"}
        assert set(by_symbol["TESTFADE"]["source_origins"]) >= {"official_exchange", "market_anomaly", "derivatives"}
        assert by_symbol["TESTPERP"]["canonical_asset_id"] == "test-perp"
        assert by_symbol["TESTPERP"]["instrument_resolver_confidence"] >= 0.9
        assert by_symbol["TESTPERP"]["asset_registry_coinalyze_symbols"]
        assert by_symbol["TESTFADE"]["derivatives_snapshot"]
        assert by_symbol["TESTFADE"]["canonical_asset_id"] == "test-fade"
        assert by_symbol["TESTFADE"]["crowding_class"] == "extreme"
        assert by_symbol["TESTFADE"]["fade_readiness"] == "ready_for_review"
        assert "open_interest_delta_24h_high" in by_symbol["TESTFADE"]["crowding_exhaustion_evidence"]
        assert by_symbol["TESTFADE"]["integrated_market_confirmation_level"] == "post_event_fade_setup"
        assert by_symbol["TESTFADE"]["triggered_fade_created"] is False
        assert by_symbol["TESTFADE"]["normal_rsi_signal_written"] is False
        assert by_symbol["TESTPERP"]["crowding_class"] == "moderate"
        assert by_symbol["TESTPERP"]["fade_readiness"] == "not_ready"
        assert "confirmed_long_derivatives_crowding_warning" in by_symbol["TESTPERP"]["warnings"]
        assert by_symbol["TESTPERP"]["integrated_market_confirmation_level"] == "confirmed_breakout"
        assert by_symbol["SECTOR"]["is_theme_or_sector"] is True
        assert by_symbol["SECTOR"]["is_tradable_asset"] is False

        cores = [
            json.loads(line)
            for line in context.core_opportunity_store_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        core_by_symbol = {row["symbol"]: row for row in cores}
        assert "SECTOR" not in core_by_symbol
        assert core_by_symbol["BTC"]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
        assert core_by_symbol["BTC"]["source_url"] == by_symbol["BTC"]["source_url"]
        assert core_by_symbol["BTC"]["canonical_asset_id"] == "bitcoin"
        assert core_by_symbol["BTC"]["official_exchange_event_type"] == "new_trading_pair"
        assert core_by_symbol["BTC"]["official_exchange_event"]["event_type"] == "new_trading_pair"
        assert core_by_symbol["TESTLIST"]["official_exchange_event_type"] == "spot_listing"
        assert core_by_symbol["TESTPERP"]["official_exchange_event_type"] == "perp_listing"
        assert core_by_symbol["TESTPERP"]["canonical_asset_id"] == "test-perp"
        assert core_by_symbol["TESTPERP"]["asset_registry_coinalyze_symbols"]
        assert core_by_symbol["TESTPERP"]["crowding_class"] == "moderate"
        assert "confirmed_long_derivatives_crowding_warning" in core_by_symbol["TESTPERP"]["warnings"]
        assert core_by_symbol["TESTFADE"]["crowding_class"] == "extreme"
        assert core_by_symbol["TESTFADE"]["fade_readiness"] == "ready_for_review"
        assert "liquidation_imbalance_extreme" in core_by_symbol["TESTFADE"]["crowding_exhaustion_evidence"]
        assert core_by_symbol["AAVE"]["protocol_metrics_level"] in {"moderate", "strong"}
        assert "protocol_tvl_growth" in core_by_symbol["AAVE"]["protocol_metrics_reasons"]
        assert "TKNC" not in core_by_symbol
        assert core_by_symbol["TESTUNLOCK"]["scheduled_catalyst_event"]["event_type"] == "token_unlock"
        assert core_by_symbol["TESTUNLOCK"]["unlock_event"]["event_type"] == "token_unlock"
        loaded_cores = event_core_opportunity_store.core_opportunities_from_rows(cores)
        loaded_btc = next(item for item in loaded_cores if item.symbol == "BTC")
        assert loaded_btc.primary_row["opportunity_type"] == "UNCONFIRMED_RESEARCH"

        card_text_by_symbol = {}
        for path in result.research_card_paths:
            if "index.md" in str(path):
                continue
            text = path.read_text(encoding="utf-8")
            for symbol in ("BTC", "TESTFADE", "TESTPERP", "AAVE", "TKND"):
                if f"# {symbol} Crypto Decision Radar Card" in text:
                    card_text_by_symbol[symbol] = text
        card_text = "\n".join(card_text_by_symbol.values())
        assert "Opportunity type: UNCONFIRMED_RESEARCH" in card_text
        assert "## Official Exchange Evidence" in card_text
        assert "Exchange: binance" in card_text
        assert "Event type: new_trading_pair" in card_text
        assert by_symbol["BTC"]["source_url"] in card_text
        assert "- Opportunity type: UNCONFIRMED_RESEARCH" in card_text_by_symbol["BTC"]
        assert "- Why now: simple major-pair announcement capped as unconfirmed research" in card_text_by_symbol["BTC"]
        assert "major_pair_simple_announcement_capped" in card_text_by_symbol["BTC"]
        assert "- Opportunity type: EARLY_LONG_RESEARCH" not in card_text_by_symbol["BTC"]
        assert "- Canonical asset: bitcoin" in card_text_by_symbol["BTC"]
        assert "- Canonical asset: test-fade" in card_text_by_symbol["TESTFADE"]
        assert "- Crowding class: extreme" in card_text_by_symbol["TESTFADE"]
        assert "- Fade readiness: ready_for_review" in card_text_by_symbol["TESTFADE"]
        assert "Derivatives crowding: n/a" not in card_text_by_symbol["TESTFADE"]
        assert "- Canonical asset: test-perp" in card_text_by_symbol["TESTPERP"]
        assert "- Integrated market state: post_event_fade_setup" in card_text_by_symbol["TESTFADE"]
        assert "- Crowding class: moderate" in card_text_by_symbol["TESTPERP"]
        assert "confirmed_long_derivatives_crowding_warning" in card_text_by_symbol["TESTPERP"]
        assert "- Integrated market state: confirmed_breakout" in card_text_by_symbol["TESTPERP"]
        assert "Market confirmation: none" not in card_text_by_symbol["TESTPERP"]
        assert "Protocol metrics confirmation:" in card_text_by_symbol["AAVE"]
        assert "DEX liquidity confirmation:" in card_text_by_symbol["AAVE"]
        card_groups = event_research_cards.card_index_group_map(result.research_card_paths)
        group_names = set(card_groups.values())
        assert "Early Long Research Cards" in group_names
        assert "Confirmed Long Research Cards" in group_names
        assert "Fade / Short-Review Cards" in group_names
        assert "Unconfirmed Research Cards" in group_names

        daily = result.daily_brief_path.read_text(encoding="utf-8")
        before_diagnostics = daily.split("## Diagnostics Appendix", 1)[0]
        assert "SECTOR/ai_theme" not in before_diagnostics
        assert "TKNC/token-c" not in before_diagnostics
        assert "## DEX / On-Chain Liquidity" in daily
        assert "## Protocol Fundamentals" in daily
        assert "## Diagnostics Appendix" in daily
        assert "SECTOR/ai_theme DIAGNOSTIC" in daily
        assert "TKNC/token-c DIAGNOSTIC" in daily
        assert f"run_id: {result.run_id}" in daily
        assert "candidate_events=15" in daily
        assert "research_candidates=15" in daily
        assert "current_generation_core_rows=12" in daily
        assert "current_generation_visible_core_rows=12" in daily
        assert "cumulative_store_rows=12" in daily
        assert "- current_core_market_freshness: total=12; statuses=" in daily
        assert "- current_generation_visible_core_freshness: total=12; statuses=" in daily
        assert "- support_row_market_freshness: total=0; statuses=none" in daily
        assert "- quality_row_market_freshness: total=15; statuses=" in daily
        assert "- Core opportunities:" not in daily

        manifest = json.loads(result.input_manifest_path.read_text(encoding="utf-8"))
        assert manifest["input_mode"] == "auto"
        assert manifest["row_counts"]["official_exchange"] >= 4
        assert manifest["row_counts"]["dex_pool_state"] == 3
        assert manifest["row_counts"]["dex_pool_anomaly"] == 3
        assert manifest["row_counts"]["protocol_fundamentals"] == 2
        assert manifest["dex_pool_state_rows_loaded"] == 3
        assert manifest["dex_pool_anomaly_rows_loaded"] == 3
        assert manifest["protocol_fundamental_rows_loaded"] == 2
        for sidecar in manifest["sidecars"]:
            assert sidecar["sidecar_research_observed_at"] == "2026-06-15T16:00:00+00:00"
            assert sidecar["sidecar_wall_started_at"] != sidecar["sidecar_research_observed_at"]
            assert sidecar["sidecar_wall_finished_at"] != sidecar["sidecar_research_observed_at"]
            assert sidecar["started_at"] == sidecar["sidecar_wall_started_at"]
            assert sidecar["finished_at"] == sidecar["sidecar_wall_finished_at"]
        assert result.source_coverage_json_path.exists()
        source_coverage = json.loads(result.source_coverage_json_path.read_text(encoding="utf-8"))
        assert source_coverage["candidate_count"] == len(rows)
        assert "official_exchange_announcements" in source_coverage["lane_critical_priority"]
        assert source_coverage["dex_pool_state_rows"] == 3
        assert source_coverage["dex_pool_anomaly_rows"] == 3
        assert source_coverage["protocol_fundamental_rows"] == 2
        assert source_coverage["dex_onchain_readiness_status"] == "fixture_ready"
        assert source_coverage["live_provider_readiness_report_path"].endswith("event_live_provider_activation_readiness.md")
        assert source_coverage["live_provider_readiness_json_path"].endswith("event_live_provider_activation_readiness.json")
        assert (context.namespace_dir / "event_live_provider_activation_readiness.md").exists()
        source_coverage_md = result.source_coverage_path.read_text(encoding="utf-8")
        assert "Live-provider activation readiness:" in source_coverage_md
        assert "event_live_provider_activation_readiness.md" in source_coverage_md

        run_row = json.loads(context.run_ledger_path.read_text(encoding="utf-8").splitlines()[-1])
        assert 0 <= float(run_row["runtime_seconds"]) < 60
        assert run_row["research_observed_at"] == "2026-06-15T16:00:00+00:00"
        assert run_row["wall_started_at"] != run_row["research_observed_at"]
        assert run_row["market_anomalies"] >= 2
        assert run_row["market_state_snapshots"] >= 2
        assert run_row["official_exchange_events"] >= 4
        assert run_row["derivatives_state_rows"] >= 2
        assert result.dex_pool_state_rows == 3
        assert result.dex_pool_anomaly_rows == 3
        assert result.protocol_fundamental_rows == 2

        preview = result.notification_preview_path.read_text(encoding="utf-8")
        assert result.notification_preview_path.name == "event_integrated_radar_notification_preview.md"
        assert "Early Long Research" in preview
        assert "Confirmed Long Research" in preview
        assert "Fade / Short-Review" in preview
        assert "Skip reasons:" in preview
        assert "Research-only / unvalidated. Not a trade signal." in preview
        assert "Alerts:" not in preview
        assert f"run_id: {result.run_id}" in preview
        assert "Send guard: disabled (no-send rehearsal)" in preview
        assert "Raw events: 25 · Candidate events: 15 · Research candidates: 15" in preview
        assert "Source alert snapshots: 0 · Current-generation core rows: 12" in preview
        assert "Alertable decisions: 0 · Strict alerts: 0 · Preview-rendered items:" in preview
        assert "Raw source candidates:" not in preview
        assert "/Users/" not in preview
        assert result.integrated_delivery_path and result.integrated_delivery_path.exists()
        deliveries = [
            json.loads(line)
            for line in result.integrated_delivery_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        lanes = {row["lane"]: row for row in deliveries}
        assert {"early_long_research", "confirmed_long_research", "fade_short_review", "risk_only", "unconfirmed_research", "source_provider_health"} <= set(lanes)
        assert lanes["early_long_research"]["status"] == "would_send_but_guard_disabled"
        assert lanes["early_long_research"]["preview_kind"] == "integrated_radar"
        assert lanes["early_long_research"]["preview_path"].endswith("event_integrated_radar_notification_preview.md")
        assert not event_artifact_paths.has_operator_absolute_path(lanes["early_long_research"]["preview_path"])
        assert lanes["early_long_research"]["zero_candidate_preview"] is False
        assert lanes["source_provider_health"]["skipped_item_count"] >= 2
        assert {
            item["reason"] for item in lanes["source_provider_health"]["skipped_items"]
        } == {"diagnostic_only_hidden_from_research_lanes"}
        assert all(row["sent"] is False for row in deliveries)
        assert all(row["normal_rsi_signal_written"] is False for row in deliveries)
        assert all(row["triggered_fade_created"] is False for row in deliveries)
        assert all(not event_artifact_paths.has_operator_absolute_path(row.get("message_text", "")) for row in deliveries)
        assert all(not event_artifact_paths.has_operator_absolute_path(row.get("card_paths", ())) for row in deliveries)
        assert result.preview_rendered_items >= 5
        assert result.preview_skipped_items >= 1
        assert result.integrated_delivery_rows == len(deliveries)
        assert run_row["integrated_delivery_rows"] == len(deliveries)
        assert run_row["preview_rendered_items"] == result.preview_rendered_items
        assert run_row["operator_absolute_path_count"] == 0
        assert run_row["source_coverage_md_path_rel"].endswith("event_alpha_source_coverage.md")
        assert "event_alpha_source_coverage.md" in daily
        assert "/Users/" not in daily


def test_integrated_zero_candidate_preview_delivery_traceability(tmp_path):
    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    from crypto_rsi_scanner.event_alpha.artifacts import paths as event_artifact_paths
    from crypto_rsi_scanner.event_alpha.radar.integrated.pipeline_parts.report import (
        build_integrated_notification_delivery_rows,
        format_integrated_notification_preview_from_deliveries,
    )
    from crypto_rsi_scanner.event_alpha.radar.integrated.pipeline_parts.runtime import (
        NOTIFICATION_PREVIEW_FILENAME,
    )

    context = event_alpha_artifacts.context_from_profile(
        "live_burn_in_no_send",
        run_mode="burn_in",
        base_dir=tmp_path,
        artifact_namespace="zero_preview",
    )
    preview_path = context.namespace_dir / NOTIFICATION_PREVIEW_FILENAME
    rows = build_integrated_notification_delivery_rows(
        (),
        core_rows=(),
        context=context,
        run_id="zero-candidate-run",
        generated_at="2026-07-05T00:00:00+00:00",
        send_guard_enabled=False,
        preview_path=preview_path,
    )
    preview_text = format_integrated_notification_preview_from_deliveries(
        rows,
        candidates=(),
        core_rows=(),
        context=context,
    )
    assert "Event Alpha Integrated Radar Preview" in preview_text
    assert "Zero candidate lanes" in preview_text
    assert "Strict alerts: 0" in preview_text
    assert "run_id: zero-candidate-run" in preview_text
    assert "Send guard: disabled (no-send rehearsal)" in preview_text
    assert "Raw source candidates:" not in preview_text
    assert all(row["preview_kind"] == "integrated_radar" for row in rows)
    assert all(row["zero_candidate_preview"] is True for row in rows)
    assert all(row["preview_path"].endswith(NOTIFICATION_PREVIEW_FILENAME) for row in rows)
    assert all(not event_artifact_paths.has_operator_absolute_path(row["preview_path"]) for row in rows)
    candidate_lanes = [row for row in rows if row["lane"] != "source_provider_health"]
    assert all(row["status"] == "not_due" for row in candidate_lanes)
    assert all(row["status_detail"] == "skipped_empty" for row in candidate_lanes)


def test_integrated_dex_sidecars_gate_market_anomaly_confirmation():
    from datetime import datetime, timezone

    import crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness as event_dex_onchain_readiness
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar

    root = _event_alpha_api_helpers.REPO_ROOT
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        dex_result = event_dex_onchain_readiness.run_dex_onchain_readiness(
            namespace_dir=base,
            profile="fixture",
            artifact_namespace="dex_merge_test",
            geckoterminal_path=root / "fixtures/event_dex_onchain/geckoterminal_pools.json",
            coingecko_dex_path=root / "fixtures/event_dex_onchain/coingecko_dex_pools.json",
            defillama_path=root / "fixtures/event_dex_onchain/defillama_protocol_fundamentals.json",
            smoke_mode=True,
            now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        )
        market_rows = [
            {
                "row_type": "event_market_anomaly",
                "source_class": "market_data",
                "source_pack": "market_anomaly_pack",
                "impact_path_type": "market_anomaly_unknown",
                "symbol": "TKNB",
                "coin_id": "token-b",
                "canonical_asset_id": "token-b",
                "market_state_class": "high_liquidity_breakout",
                "market_anomaly_bucket": "high_liquidity_breakout",
                "market_snapshot": {
                    "return_unit": "percent_points",
                    "return_24h": 21,
                    "volume_zscore_24h": 3.5,
                    "volume_24h": 2_000_000,
                    "market_cap": 24_000_000,
                    "liquidity_usd": 2_200_000,
                    "spread_bps": 34,
                    "observed_at": "2026-06-15T16:00:00Z",
                    "market_context_freshness_status": "fresh",
                },
            },
            {
                "row_type": "event_market_anomaly",
                "source_class": "market_data",
                "source_pack": "market_anomaly_pack",
                "impact_path_type": "market_anomaly_unknown",
                "symbol": "TKNC",
                "coin_id": "token-c",
                "canonical_asset_id": "token-c",
                "market_state_class": "low_liquidity_suspicious",
                "market_anomaly_bucket": "low_liquidity_suspicious",
                "market_snapshot": {
                    "return_unit": "percent_points",
                    "return_24h": 62,
                    "volume_zscore_24h": 2.8,
                    "volume_24h": 300_000,
                    "market_cap": 900_000,
                    "liquidity_usd": 18_000,
                    "spread_bps": 340,
                    "observed_at": "2026-06-15T16:00:00Z",
                    "market_context_freshness_status": "fresh",
                },
            },
        ]
        rows = event_integrated_radar.build_integrated_candidates(
            sidecar_rows={
                "market_anomaly": market_rows,
                "dex_pool_state": dex_result.dex_pool_state_rows,
                "dex_pool_anomaly": dex_result.dex_pool_anomaly_rows,
                "protocol_fundamentals": dex_result.protocol_fundamental_rows,
            },
            profile="fixture",
            artifact_namespace="dex_merge_test",
            run_mode="fixture",
            run_id="dex-merge-run",
            observed_at=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        )
        by_symbol = {row["symbol"]: row for row in rows}
        assert by_symbol["TKNB"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
        assert set(by_symbol["TKNB"]["source_origins"]) >= {"market_anomaly", "dex_pool_state", "dex_pool_anomaly"}
        assert by_symbol["TKNB"]["dex_liquidity_level"] in {"moderate", "strong"}
        assert by_symbol["TKNB"]["market_requirements_met"] is True
        assert by_symbol["TKNC"]["opportunity_type"] == "DIAGNOSTIC"
        assert "dex_low_liquidity_pump_diagnostic_only" in by_symbol["TKNC"]["warnings"]


def test_integrated_market_anomaly_alone_does_not_confirm():
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar

    rows = event_integrated_radar.build_integrated_candidates(
        sidecar_rows={
            "market_anomaly": [
                {
                    "row_type": "event_market_anomaly",
                    "symbol": "ONLYMOVE",
                    "coin_id": "only-move",
                    "market_state": "confirmed_breakout",
                    "market_state_class": "confirmed_breakout",
                    "market_state_snapshot": {
                        "return_unit": "percent_points",
                        "return_4h": 12.0,
                        "return_24h": 20.0,
                        "volume_turnover_zscore": 3.0,
                        "liquidity_usd": 2_000_000,
                    },
                    "source_pack": "market_anomaly_pack",
                }
            ]
        },
        profile="fixture",
        artifact_namespace="integrated_test",
        run_mode="fixture",
        run_id="run",
        observed_at="2026-06-15T16:00:00Z",
    )

    assert len(rows) == 1
    assert rows[0]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert rows[0]["created_alert"] is False
    assert rows[0]["triggered_fade_created"] is False


def test_integrated_low_liquidity_suspicious_anomaly_is_diagnostic_even_with_official_source():
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar

    rows = event_integrated_radar.build_integrated_candidates(
        sidecar_rows={
            "market_anomaly": [
                {
                    "row_type": "event_market_anomaly",
                    "symbol": "THIN",
                    "coin_id": "thin-token",
                    "canonical_asset_id": "thin-token",
                    "anomaly_type": "suspicious_illiquid_move",
                    "anomaly_bucket": "low_liquidity_suspicious",
                    "market_state": "suspicious_illiquid_move",
                    "market_state_class": "suspicious_illiquid_move",
                    "market_state_snapshot": {
                        "return_unit": "percent_points",
                        "return_4h": 30.0,
                        "return_24h": 75.0,
                        "volume_zscore_24h": 4.0,
                        "liquidity_usd": 18_000,
                        "spread_bps": 250,
                    },
                    "source_pack": "market_anomaly_pack",
                    "needs_catalyst_search": True,
                    "suggested_source_packs_to_search": ["market_anomaly_pack", "dex_liquidity_pack"],
                }
            ],
            "official_exchange": [
                {
                    "row_type": "official_listing_candidate",
                    "symbol": "THIN",
                    "coin_id": "thin-token",
                    "canonical_asset_id": "thin-token",
                    "title": "Bybit Lists THIN/USDT",
                    "source_url": "https://announcements.bybit.com/thin",
                    "published_at": "2026-06-15T15:00:00Z",
                    "source_class": "official_exchange",
                    "source_pack": "official_exchange_listing_pack",
                    "impact_path_type": "listing_liquidity_event",
                    "accepted_evidence_count": 1,
                    "source_strength": "official_structured",
                }
            ],
        },
        profile="fixture",
        artifact_namespace="integrated_test",
        run_mode="fixture",
        run_id="run",
        observed_at="2026-06-15T16:00:00Z",
    )

    assert len(rows) == 1
    assert rows[0]["opportunity_type"] == "DIAGNOSTIC"
    assert rows[0]["created_alert"] is False
    assert rows[0]["triggered_fade_created"] is False


def test_makefile_exposes_integrated_radar_target():
    text = Path("Makefile").read_text(encoding="utf-8")

    assert "event-alpha-integrated-radar-smoke" in text
    assert "event-alpha-integrated-radar-doctor" in text
    assert "event-alpha-integrated-radar-outcome-smoke" in text
    assert "event-alpha-integrated-radar-calibration-report" in text
    assert "--event-alpha-integrated-radar-cycle" in text
    assert "--event-alpha-integrated-radar-fixture" in text
    assert "--event-alpha-integrated-radar-run-sidecars" in text
    assert "--event-alpha-integrated-radar-load-existing" in text
    assert "--event-alpha-integrated-radar-auto" in text
    assert "--event-alpha-integrated-radar-coinalyze-namespace" in text
    assert "--event-alpha-integrated-radar-fill-outcomes" in text


def test_event_alpha_operator_path_fields_are_portable_and_debug_only_abs_allowed():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.artifacts.paths as event_artifact_paths

    row = {
        "research_cards_dir": "/Users/example/crypto-rsi-scanner/event_fade_cache/demo/research_cards",
        "canonical_card_paths": [
            "/Users/example/crypto-rsi-scanner/event_fade_cache/demo/research_cards/card_core_demo.md",
        ],
        "nested": {
            "notification_preview_path": "/Users/example/crypto-rsi-scanner/event_fade_cache/demo/event_alpha_notification_preview.md",
        },
    }

    normalized = event_artifact_paths.normalize_operator_path_fields(row)

    assert normalized["research_cards_dir"] == "event_fade_cache/demo/research_cards"
    assert normalized["research_cards_dir_abs_debug"].startswith("/Users/example/")
    assert normalized["canonical_card_paths"] == ["event_fade_cache/demo/research_cards/card_core_demo.md"]
    assert normalized["nested"]["notification_preview_path"] == "event_fade_cache/demo/event_alpha_notification_preview.md"
    assert not event_artifact_paths.has_operator_absolute_path(normalized["research_cards_dir"])
    assert event_alpha_artifact_doctor._structured_operator_path_conflicts([normalized]) == 0  # noqa: SLF001
    assert event_alpha_artifact_doctor._structured_operator_path_conflicts([row]) >= 1  # noqa: SLF001
