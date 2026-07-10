"""Source reliability, registry semantics, source packs, and feed-coverage regressions."""

from __future__ import annotations

from datetime import datetime, timezone
from tempfile import TemporaryDirectory

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_source_reliability_report_recommendations():
    import crypto_rsi_scanner.event_alpha.providers.source_reliability as event_source_reliability

    alerts = [
        {"alert_key": "a", "source_provider": "rss", "primary_horizon_return": 0.12, "mfe_mae_ratio": 1.5},
        {"alert_key": "b", "source_provider": "rss", "primary_horizon_return": 0.05, "mfe_mae_ratio": 1.2},
        {"alert_key": "c", "source_provider": "bad", "primary_horizon_return": -0.02, "mfe_mae_ratio": 0.6},
        {"alert_key": "d", "source_provider": "bad", "primary_horizon_return": -0.03, "mfe_mae_ratio": 0.5},
    ]
    feedback = [
        {"key": "a", "label": "useful"},
        {"key": "b", "label": "useful"},
        {"key": "c", "label": "junk"},
        {"key": "d", "label": "junk"},
    ]
    missed = [{"failure_stage": "no_source_event"}, {"failure_stage": "no_source_event"}]
    report = event_source_reliability.format_source_reliability_report(alerts, feedback_rows=feedback, missed_rows=missed)
    assert "positive prior for rss" in report
    assert "tighten or demote bad" in report
    assert "coverage warning" in report


def test_event_source_registry_v2_provider_semantics():
    import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry

    polymarket_context = event_source_registry.assess_source(
        {"provider": "polymarket", "title": "SpaceX IPO market opens"},
        symbol="VELVET",
        coin_id="velvet",
    )
    assert polymarket_context.source_class == "prediction_market"
    assert polymarket_context.source_mission == "external_context"
    assert polymarket_context.can_validate_token_identity is False
    assert "external_context" in polymarket_context.can_prove
    assert "impact_path_validation" in polymarket_context.cannot_prove
    assert polymarket_context.evidence_absence_is_meaningful is False
    assert "prediction_market_external_context_only" in polymarket_context.reason_codes

    polymarket_named = event_source_registry.assess_source(
        {"provider": "polymarket", "title": "VELVET market for SpaceX exposure"},
        symbol="VELVET",
        coin_id="velvet",
    )
    assert polymarket_named.can_validate_token_identity is True
    assert "prediction_market_token_named_context" in polymarket_named.reason_codes

    gdelt_degraded = event_source_registry.assess_source(
        {"provider": "gdelt", "title": "Broad policy article mentions crypto"},
        symbol="BTC",
        coin_id="bitcoin",
        provider_coverage_status="degraded",
    )
    assert gdelt_degraded.source_class == "broad_news"
    assert gdelt_degraded.evidence_absence_is_meaningful is False
    assert gdelt_degraded.source_coverage_gap_reason == "provider_coverage_degraded:gdelt"
    assert "provider_coverage_degraded" in gdelt_degraded.warnings

    cryptopanic = event_source_registry.assess_source(
        {
            "provider": "cryptopanic",
            "title": "RUNE exploit update is important",
            "raw_json": {
                "currency_tags": ("RUNE",),
                "kind": "important",
            },
        },
        symbol="RUNE",
        coin_id="thorchain",
    )
    assert cryptopanic.source_class == "cryptopanic_tagged"
    assert cryptopanic.cryptopanic_currency_tag_match is True
    assert cryptopanic.narrative_heat is True
    assert "cryptopanic_currency_tag_match" in cryptopanic.reason_codes
    cryptopanic_mismatch = event_source_registry.assess_source(
        {
            "provider": "cryptopanic",
            "title": "Bullish market heat mentions RUNE",
            "currency_tags": ("BTC",),
            "kind": "hot",
        },
        symbol="RUNE",
        coin_id="thorchain",
    )
    assert cryptopanic_mismatch.source_class == "cryptopanic_tagged"
    assert cryptopanic_mismatch.cryptopanic_currency_tag_match is False
    assert cryptopanic_mismatch.can_validate_token_identity is False
    assert cryptopanic_mismatch.can_validate_impact_path is False
    assert "cryptopanic_narrative_heat_without_matching_tag" in cryptopanic_mismatch.warnings
    cryptopanic_contract = event_source_registry.source_contract_metadata(
        {"provider": "cryptopanic", "raw_json": {"currency_tags": ("RUNE",)}},
        evidence_rows=(
            {
                "source_can_prove": ("token_identity_validation", "impact_path_validation"),
                "source_cannot_prove": ("official_confirmation",),
                "source_useful_playbooks": ("security_or_regulatory_shock",),
            },
        ),
        symbol="RUNE",
        coin_id="thorchain",
    )
    assert "impact_path_validation" in cryptopanic_contract["source_can_prove"]
    assert "official_confirmation" in cryptopanic_contract["source_cannot_prove"]
    assert cryptopanic_contract["source_useful_playbooks"] == ("security_or_regulatory_shock",)

    exchange = event_source_registry.assess_source(
        {"provider": "binance_announcements", "title": "Binance Will List TEST"},
        symbol="TEST",
        coin_id="test-token",
    )
    assert exchange.source_class == "official_exchange"
    assert exchange.can_validate_token_identity is True
    assert exchange.can_validate_catalyst is True
    assert "official_confirmation" in exchange.can_prove
    assert "listing_volatility" in exchange.useful_playbooks

    market_data = event_source_registry.assess_source(
        {"provider": "coingecko_market_data", "title": "RUNE price snapshot"},
        symbol="RUNE",
        coin_id="thorchain",
    )
    assert market_data.source_class == "market_data"
    assert market_data.source_mission == "market_confirmation"
    assert "market_confirmation" in market_data.can_prove
    assert "impact_path_validation" in market_data.cannot_prove
    defillama = event_source_registry.assess_source(
        {"provider": "defillama", "title": "AAVE TVL and protocol fees snapshot"},
        symbol="AAVE",
        coin_id="aave",
    )
    assert defillama.source_class == "market_data"
    assert "market_confirmation" in defillama.can_prove
    assert "impact_path_validation" in defillama.cannot_prove
    geckoterminal = event_source_registry.assess_source(
        {"provider": "geckoterminal", "title": "VELVET DEX liquidity and pool volume snapshot"},
        symbol="VELVET",
        coin_id="velvet",
    )
    assert geckoterminal.source_class == "market_data"
    assert geckoterminal.source_mission == "market_confirmation"
    assert "market_confirmation" in geckoterminal.can_prove

    seo = event_source_registry.assess_source(
        {"provider": "rss", "title": "Best crypto to buy price prediction market recap"},
        symbol="HYPE",
        coin_id="hyperliquid",
    )
    assert seo.source_class in {"seo_or_affiliate", "market_recap"}
    assert seo.can_validate_token_identity is False
    assert "diagnostic_only_low_quality_source" in seo.warnings


def test_event_source_packs_and_feed_coverage_semantics():
    import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs
    import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry

    names = set(event_source_packs.source_pack_names())
    assert {
        "listing_liquidity_pack",
        "perp_listing_squeeze_pack",
        "unlock_supply_pack",
        "project_event_pack",
        "proxy_preipo_rwa_pack",
        "ai_ipo_proxy_pack",
        "security_shock_pack",
        "fan_sports_pack",
        "political_meme_pack",
        "strategic_investment_pack",
        "protocol_business_event_pack",
        "market_anomaly_pack",
    }.issubset(names)

    listing = event_source_packs.source_pack_for_playbook("listing_volatility")
    assert listing.name == "listing_liquidity_pack"
    assert "official_exchange" in listing.preferred_source_classes
    assert "cryptopanic_tagged" in listing.preferred_source_classes
    assert "official_exchange_source" in listing.sufficient_for_validated_digest
    assert "coinalyze" in listing.preferred_providers

    proxy = event_source_packs.source_pack_for_playbook("proxy_attention", impact_path_type="venue_value_capture")
    assert proxy.name == "proxy_preipo_rwa_pack"
    assert "prediction_market" in proxy.context_only_sources
    assert "official_project" in proxy.impact_path_validating_sources
    assert "geckoterminal" in proxy.preferred_providers
    assert "liquidity_sanity" in proxy.required_for_high_priority

    strategic = event_source_packs.source_pack_for_playbook(
        "strategic_investment",
        impact_path_type="strategic_investment_or_valuation",
    )
    assert strategic.name == "strategic_investment_pack"
    assert "denial_or_correction_search" in strategic.validation_requirements
    assert "second_source_confirmation" in strategic.sufficient_for_validated_digest
    assert "defillama" in strategic.preferred_providers
    protocol_business = event_source_packs.source_pack_for_playbook(
        "protocol_business_event",
        impact_path_type="protocol_business_event",
    )
    assert protocol_business.name == "protocol_business_event_pack"
    project_event = event_source_packs.source_pack_for_playbook("direct_event", impact_path_type="direct_protocol_event")
    assert project_event.name == "project_event_pack"
    security = event_source_packs.source_pack_for_playbook("security_or_regulatory_shock")
    fan = event_source_packs.source_pack_for_playbook("fan_sports_proxy")
    political = event_source_packs.source_pack_for_playbook("political_meme_proxy")
    assert "cryptopanic_tagged" in security.preferred_source_classes
    assert "cryptopanic_tagged" in fan.preferred_source_classes
    assert "cryptopanic_tagged" in political.preferred_source_classes

    pack_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "polymarket",
            "title": "SpaceX IPO odds move",
            "playbook_type": "proxy_attention",
            "impact_path_type": "venue_value_capture",
            "symbol": "VELVET",
            "coin_id": "velvet",
        },
        pack=proxy,
    )
    assert pack_eval["source_pack"] == "proxy_preipo_rwa_pack"
    assert pack_eval["source_pack_context_only"] is True
    assert pack_eval["source_pack_validated_digest_sufficient"] is False
    assert "source_is_context_only" in pack_eval["source_pack_missing_evidence"]

    listing_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "bybit_announcements",
            "title": "Bybit Will List TESTUSDT",
            "announcement_symbols": ("TEST",),
            "announcement_pairs": ("TEST/USDT",),
            "playbook_type": "listing_volatility",
            "symbol": "TEST",
            "coin_id": "test-token",
            "market_confirmation_score": 75,
        },
        pack=listing,
    )
    assert listing_eval["source_pack_validated_digest_sufficient"] is True
    assert listing_eval["source_pack_watchlist_requirements_met"] is True
    assert listing_eval["source_pack_impact_path_validating_source"] is True
    listing_mismatch = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "binance_announcements",
            "title": "Binance Will List OTHERUSDT",
            "announcement_symbols": ("OTHER",),
            "announcement_pairs": ("OTHER/USDT",),
            "playbook_type": "listing_volatility",
            "symbol": "TEST",
            "coin_id": "test-token",
            "market_confirmation_score": 75,
        },
        pack=listing,
    )
    assert listing_mismatch["source_pack_validated_digest_sufficient"] is False
    assert "symbol_or_pair_match" not in listing_mismatch["source_pack_met_requirements"]
    listing_substring_mismatch = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "binance_announcements",
            "title": "Binance Will List TESTLISTUSDT",
            "announcement_symbols": ("TESTLIST",),
            "announcement_pairs": ("TESTLIST/USDT",),
            "playbook_type": "listing_volatility",
            "symbol": "TEST",
            "coin_id": "test",
            "market_confirmation_score": 75,
        },
        pack=listing,
    )
    assert listing_substring_mismatch["source_pack_validated_digest_sufficient"] is False
    assert "symbol_or_pair_match" not in listing_substring_mismatch["source_pack_met_requirements"]

    unlock = event_source_packs.source_pack_for_playbook("unlock_supply_pressure")
    large_unlock_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "tokenomist",
            "title": "TESTUNLOCK token cliff unlock",
            "playbook_type": "unlock_supply_pressure",
            "symbol": "TESTUNLOCK",
            "coin_id": "testunlock",
            "source_url": "https://tokenomist.ai/testunlock",
            "unlock_pct_circulating": 0.12,
            "event_time": "2026-07-01T00:00:00Z",
            "as_of": "2026-06-20T00:00:00Z",
            "market_confirmation_score": 72,
        },
        pack=unlock,
    )
    assert large_unlock_eval["source_pack_validated_digest_sufficient"] is True
    assert large_unlock_eval["source_pack_watchlist_requirements_met"] is True
    assert "material_unlock" in large_unlock_eval["source_pack_met_requirements"]
    small_unlock_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "tokenomist",
            "title": "SMALL token small unlock",
            "playbook_type": "unlock_supply_pressure",
            "symbol": "SMALL",
            "coin_id": "small-token",
            "unlock_pct_circulating": 0.01,
        },
        pack=unlock,
    )
    assert small_unlock_eval["source_pack_validated_digest_sufficient"] is False
    assert "unlock_not_material" in small_unlock_eval["source_pack_missing_evidence"]
    missing_supply_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "tokenomist",
            "title": "MISS token unlock",
            "playbook_type": "unlock_supply_pressure",
            "symbol": "MISS",
            "coin_id": "missing-supply",
        },
        pack=unlock,
    )
    assert missing_supply_eval["source_pack_validated_digest_sufficient"] is False
    assert "needs_supply_materiality" in missing_supply_eval["source_pack_missing_evidence"]
    stale_unlock_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "tokenomist",
            "title": "STALE token unlock",
            "playbook_type": "unlock_supply_pressure",
            "symbol": "STALE",
            "coin_id": "stale-token",
            "unlock_pct_circulating": 0.20,
            "event_time": "2026-06-01T00:00:00Z",
            "as_of": "2026-06-20T00:00:00Z",
        },
        pack=unlock,
    )
    assert stale_unlock_eval["source_pack_validated_digest_sufficient"] is False
    assert "stale_unlock_data" in stale_unlock_eval["source_pack_missing_evidence"]

    calendar_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "coinmarketcal",
            "title": "TESTCAL mainnet launch",
            "playbook_type": "direct_event",
            "impact_path_type": "direct_protocol_event",
            "symbol": "TESTCAL",
            "coin_id": "testcal",
            "event_type": "mainnet_launch",
            "event_time": "2026-07-01T00:00:00Z",
        },
        pack=project_event,
    )
    assert calendar_eval["source_pack_validated_digest_sufficient"] is True
    assert "event_time_confirmation" in calendar_eval["source_pack_met_requirements"]
    ama_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "coinmarketcal",
            "title": "TESTCAL community AMA",
            "playbook_type": "direct_event",
            "impact_path_type": "direct_protocol_event",
            "symbol": "TESTCAL",
            "coin_id": "testcal",
            "event_type": "community_ama",
            "event_time": "2026-07-01T00:00:00Z",
        },
        pack=project_event,
    )
    assert ama_eval["source_pack_validated_digest_sufficient"] is False
    assert "low_authority_calendar_event" in ama_eval["source_pack_missing_evidence"]

    feed_403 = event_source_registry.feed_health_from_fetch(
        feed_url="https://example.test/rss",
        failure_type="http_403",
        rows_fetched=0,
        rows_kept=0,
        rows_rejected=0,
    )
    assert feed_403.quarantined is True
    assert feed_403.cooldown_reason == "feed_403_quarantined"
    assert feed_403.feed_source_class == feed_403.source_class
    assert feed_403.feed_quality_score <= 30

    bad_recap = event_source_registry.feed_health_from_fetch(
        feed_url="https://recap.example.test/price-prediction/rss",
        failure_count=4,
        rows_fetched=10,
        rows_kept=1,
        rows_rejected=9,
    )
    assert bad_recap.quarantined is True
    assert bad_recap.quality in {"low", "medium"}
    assert bad_recap.to_metadata()["feed_quality_score"] <= 50
    assert event_source_registry.evidence_absence_is_meaningful(
        provider="gdelt",
        source_class="broad_news",
        coverage_status="degraded",
    ) is False
