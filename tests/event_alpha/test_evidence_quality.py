"""Focused Event Alpha outcomes and quality tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_integrated_radar_outcome_smoke_writes_research_only_artifacts(tmp_path):
    from crypto_rsi_scanner.event_alpha.outcomes import integrated_radar_outcomes
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar

    candidate = {
        "candidate_id": "candidate:TESTLIST",
        "core_opportunity_id": "core:TESTLIST",
        "run_id": "run-1",
        "profile": "fixture",
        "artifact_namespace": "pytest_outcomes",
        "symbol": "TESTLIST",
        "coin_id": "testlist",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "source_origin": "official_exchange",
        "source_pack": "listing_pack",
        "provider": "pytest",
        "market_state_class": "high_liquidity_breakout",
        "source_strength": "structured",
        "observed_at": "2026-06-15T16:00:00+00:00",
        "market_state_snapshot": {"price": 1.0},
    }
    (tmp_path / integrated_radar.INTEGRATED_CANDIDATES_FILENAME).write_text(
        json.dumps(candidate, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rows = integrated_radar_outcomes.fill_integrated_radar_outcomes(
        tmp_path,
        observed_at=datetime(2026, 6, 15, 17, tzinfo=timezone.utc),
    )
    loaded = integrated_radar_outcomes.load_integrated_radar_outcomes(tmp_path)
    report = (tmp_path / integrated_radar.INTEGRATED_OUTCOME_REPORT_FILENAME).read_text(encoding="utf-8")

    assert len(rows) == 1
    assert loaded == rows
    assert rows[0]["outcome_label"] == "inconclusive"
    assert rows[0]["synthetic_diagnostic_label"] == "early_good"
    assert rows[0]["outcome_data_source"] == "synthetic_fixture"
    assert rows[0]["calibration_eligible"] is False
    assert rows[0]["outcome_status"] == "pending"
    assert rows[0]["research_only"] is True
    assert rows[0]["trade_created"] is False
    assert rows[0]["paper_trade_created"] is False
    assert rows[0]["normal_rsi_signal_written"] is False
    assert rows[0]["triggered_fade_created"] is False
    assert "Calibration exclusion reasons" in integrated_radar_outcomes.format_integrated_radar_calibration_report(rows)
    assert "early_good" in report


def test_calibration_report_keeps_research_only_terms():
    from crypto_rsi_scanner.event_alpha.outcomes import calibration

    alert = {
        "alert_key": "core:TESTLIST",
        "core_opportunity_id": "core:TESTLIST",
        "symbol": "TESTLIST",
        "coin_id": "testlist",
        "playbook_type": "listing",
        "source": "official_exchange",
        "source_provider": "pytest",
        "tier": "watchlist",
        "primary_horizon_return": 0.08,
        "direction_hit": True,
    }
    feedback = {
        "target": "core:TESTLIST",
        "label": "useful",
        "source_provider": "pytest",
        "source_pack": "listing_pack",
    }

    report = calibration.format_calibration_report([alert], feedback_rows=[feedback])

    assert "EVENT ALPHA CALIBRATION REPORT" in report
    assert "feedback_supplied=1" in report
    assert "feedback_eligible=0" in report
    assert "feedback_excluded=1" in report
    assert "legacy_feedback_contract=1" in report
    assert "No calibration artifacts found." in report


def test_feedback_readiness_smoke_is_research_only():
    from crypto_rsi_scanner.event_alpha.outcomes import feedback

    result = feedback.build_feedback_readiness(
        profile="fixture",
        artifact_namespace="pytest_outcomes",
        card_paths=[],
        alert_rows=[],
        feedback_rows=[],
        watchlist_entries=[],
    )
    text = feedback.format_feedback_readiness(result)

    assert result.ready is True
    assert "EVENT ALPHA FEEDBACK READINESS" in text
    assert "warnings: no_research_cards_found, no_alert_snapshots_found" in text
    assert "Artifact-only check; no sends, trades, paper rows, normal RSI rows, or event-fade state were changed." in text


def test_event_provider_status_formats_burn_in_readiness_summary_and_pack_gaps():
    cfg = _event_provider_status_cfg(
        EVENT_DISCOVERY_CRYPTOPANIC_LIVE=True,
        EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN="",
        EVENT_DISCOVERY_GDELT_LIVE=True,
        EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=False,
    )
    report = event_provider_status.build_event_discovery_provider_status(cfg)
    text = event_provider_status.format_event_discovery_provider_status(report)

    assert "Provider readiness summary:" in text
    assert "providers_configured:" in text
    assert "gdelt_news" in text
    assert "providers_not_configured:" in text
    assert "cryptopanic_news" in text
    assert "Source pack coverage gaps:" in text
    assert "evidence_absence_meaningful=false" in text
    assert "CryptoPanic live mode is enabled but the API token is missing" in text
    assert "api_token=missing" in text


def test_event_llm_budget_skips_lower_priority_rows_and_cache_hits_are_free():
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result, alerts, _ = _llm_golden_alerts_and_rows(min_prefilter_score=0)

    class CountingProvider(FixtureLLMRelationshipProvider):
        def __init__(self, path):
            super().__init__(path, required=True)
            self.calls = 0

        def analyze_relationship(self, packet):
            self.calls += 1
            return super().analyze_relationship(packet)

    provider = CountingProvider(_llm_golden_fixture_path())
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        provider,
        cfg=event_llm_analyzer.EventLLMConfig(
            min_prefilter_score=0,
            max_candidates_per_run=3,
            max_calls_per_run=1,
        ),
    )
    assert provider.calls == 1
    assert len([row for row in rows if row.cache_status == "skipped_budget"]) == 2
    assert any("budget exhausted" in "; ".join(row.warnings) for row in rows)

    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "llm_cache.json"
        warm = CountingProvider(_llm_golden_fixture_path())
        event_llm_analyzer.analyze_event_candidates(
            result,
            alerts[:1],
            warm,
            cfg=event_llm_analyzer.EventLLMConfig(
                min_prefilter_score=0,
                max_candidates_per_run=1,
                cache_path=cache_path,
            ),
        )
        cached_provider = CountingProvider(_llm_golden_fixture_path())
        cached_rows = event_llm_analyzer.analyze_event_candidates(
            result,
            alerts[:2],
            cached_provider,
            cfg=event_llm_analyzer.EventLLMConfig(
                min_prefilter_score=0,
                max_candidates_per_run=2,
                max_calls_per_run=1,
                cache_path=cache_path,
            ),
        )
        assert [row.cache_status for row in cached_rows] == ["hit", "miss"]
        assert cached_provider.calls == 1


def test_event_llm_extractor_prioritizes_high_value_raw_events_before_budget():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, *, provider="news", score=None, source_conf=0.75, body=None):
        payload = {}
        if score is not None:
            payload = {
                "market": {"symbol": raw_id.upper(), "coin_id": raw_id},
                "anomaly": {"score": score, "reasons": ["24h return 80%"]},
            }
            provider = "market_anomaly"
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body or title,
            raw_json=payload,
            source_confidence=source_conf,
            content_hash=raw_id,
        )

    market_roundup = raw("roundup", "Daily market roundup: Bitcoin World recap", source_conf=0.85)
    high_anomaly = raw("pump", "PUMP market anomaly with 80% move", score=92, source_conf=0.55)
    proxy_article = raw(
        "proxy",
        "SpaceX pre-IPO exposure opens through PROXY token",
        body="PROXY token offers synthetic exposure to SpaceX pre-IPO markets.",
        source_conf=0.90,
    )
    publisher_noise = raw("noise", "Bitcoin World covers SpaceX IPO hype", source_conf=0.90)

    high_priority = event_llm_extractor.score_raw_event_for_llm_extraction(high_anomaly, now=now)
    recap_priority = event_llm_extractor.score_raw_event_for_llm_extraction(market_roundup, now=now)
    proxy_priority = event_llm_extractor.score_raw_event_for_llm_extraction(proxy_article, now=now)
    noise_priority = event_llm_extractor.score_raw_event_for_llm_extraction(publisher_noise, now=now)
    assert high_priority.score > recap_priority.score
    assert proxy_priority.score > recap_priority.score
    assert noise_priority.score < proxy_priority.score

    class Provider:
        name = "fixture"

        def __init__(self):
            self.seen = []

        def extract_raw_event(self, packet):
            self.seen.append(packet["raw_id"])
            return LLMProviderResult(raw={
                "confidence": 0.80,
                "external_catalysts": [],
                "crypto_asset_mentions": [],
                "false_positive_terms": [],
                "event_date_hints": [],
                "suggested_followup_queries": [],
                "warnings": [],
            })

    provider = Provider()
    rows = event_llm_extractor.analyze_raw_events(
        [market_roundup, publisher_noise, proxy_article, high_anomaly],
        provider,
        cfg=event_llm_extractor.EventLLMExtractorConfig(max_events_per_run=2),
    )
    assert provider.seen == ["pump", "proxy"]
    assert [row.raw_event.raw_id for row in rows] == ["pump", "proxy"]
    assert all(row.extraction_priority_score > 0 for row in rows)
    assert any("catalyst_keywords" in ",".join(row.extraction_priority_reasons) for row in rows)


def test_event_catalyst_search_scores_filter_low_quality_results():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:pump:2026-06-18",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="PUMP market anomaly: 24h return 80%",
        body="No dated external catalyst has been validated.",
        raw_json={"market": {"symbol": "PUMP", "coin_id": "pump"}, "anomaly": {"score": 90}},
        source_confidence=0.55,
        content_hash="anomaly-pump",
    )
    good = RawDiscoveredEvent(
        raw_id="pump-binance",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pump",
        title="Binance will list Pump Protocol (PUMP)",
        body="Binance will list PUMP spot trading today.",
        raw_json={
            "event": {
                "event_id": "pump-binance",
                "event_name": "Binance will list Pump Protocol (PUMP)",
                "event_type": "exchange_listing",
                "event_time": "2026-06-18T20:00:00Z",
                "event_time_confidence": 0.95,
                "confidence": 0.90,
            }
        },
        source_confidence=0.90,
        content_hash="pump-binance",
    )
    recap = RawDiscoveredEvent(
        raw_id="pump-recap",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/recap",
        title="Daily market recap: crypto prices today",
        body="A generic market recap mentions PUMP with no catalyst.",
        raw_json={},
        source_confidence=0.60,
        content_hash="pump-recap",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider({
        "PUMP Binance listing": (good, recap),
    })
    cfg = event_catalyst_search.EventCatalystSearchConfig(
        enabled=True,
        max_anomalies=1,
        max_queries_per_anomaly=2,
        max_results_per_query=5,
        min_anomaly_score=60,
        min_result_confidence=0.60,
    )
    result = event_catalyst_search.run_catalyst_search([anomaly], provider, cfg=cfg, now=now)
    assert [row.raw_event.raw_id for row in result.result_events] == ["pump-binance"]
    assert [row.raw_event.raw_id for row in result.rejected_result_events] == ["pump-recap"]
    assert result.result_events[0].result_score > result.rejected_result_events[0].result_score
    report = event_catalyst_search.format_catalyst_search_report(result)
    assert "accepted_results=1" in report
    assert "rejected_results=1" in report


def test_event_market_evidence_and_opportunity_verdict_quality_layers():
    import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
    import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
    import crypto_rsi_scanner.event_alpha.radar.market_confirmation as event_market_confirmation
    import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from datetime import datetime, timezone

    now = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="velvet",
        provider="cryptopanic",
        fetched_at=now,
        published_at=now,
        source_url="https://cryptopanic.com/news/velvet",
        title="VELVET offers SpaceX pre-IPO exposure",
        body="Velvet lets users trade tokenized SpaceX pre-IPO exposure through a crypto venue.",
        raw_json={
            "currencies": ["VELVET"],
            "market": {"return_24h": 0.38, "volume_zscore_24h": 3.2, "volume_to_market_cap": 0.31},
        },
        source_confidence=0.88,
        content_hash="velvet",
    )
    hypothesis = SimpleNamespace(
        impact_category="rwa_preipo_proxy",
        external_asset="SpaceX",
        playbook_hint="rwa_preipo_proxy",
        score_components={"validation_strength": 90, "event_clarity": 80},
    )
    market = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot=raw.raw_json["market"],
            playbook_type="rwa_preipo_proxy",
            now=now,
            market_context_observed_at=now,
            market_context_source="unit_test_live_market",
            allow_stale_fixture_market_context=False,
        )
    )
    evidence = event_evidence_quality.evaluate_evidence_quality(raw, hypothesis=hypothesis, symbol="VELVET", coin_id="velvet")
    path = event_impact_path_validator.validate_impact_path(raw, hypothesis, symbol="VELVET", coin_id="velvet")
    verdict = event_opportunity_verdict.evaluate_opportunity(
        impact_path=path,
        market_confirmation=market,
        evidence_quality=evidence,
        hypothesis=hypothesis,
        score_components=hypothesis.score_components,
    )
    assert market.level == "strong"
    assert market.market_context_freshness_status == "fresh"
    assert market.freshness_cap_applied is False
    assert "price_momentum" in market.reasons
    assert "volume_expansion" in market.reasons
    assert evidence.source_class == "cryptopanic_tagged"
    assert evidence.evidence_specificity == "direct_token_mechanism"
    assert verdict.opportunity_level in {"watchlist", "high_priority"}
    assert verdict.watchlist_eligible is True

    stale_market = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot=raw.raw_json["market"],
            playbook_type="rwa_preipo_proxy",
            now=now,
            market_context_observed_at="2026-06-24T00:00:00Z",
            market_context_source="live_market_enrichment",
            allow_stale_fixture_market_context=False,
        )
    )
    stale_verdict = event_opportunity_verdict.evaluate_opportunity(
        impact_path=path,
        market_confirmation=stale_market,
        evidence_quality=evidence,
        hypothesis=hypothesis,
        score_components=hypothesis.score_components,
    )
    assert stale_market.market_context_freshness_status == "stale"
    assert stale_market.level == "weak"
    assert stale_market.freshness_cap_applied is True
    assert stale_verdict.watchlist_eligible is False
    assert "needs_fresh_market_confirmation" in stale_verdict.missing_requirements

    stale_fixture_market = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot=raw.raw_json["market"],
            playbook_type="rwa_preipo_proxy",
            now=now,
            market_context_observed_at="2026-06-24T00:00:00Z",
            market_context_source="fixture_signal_quality",
            allow_stale_fixture_market_context=True,
        )
    )
    assert stale_fixture_market.market_context_freshness_status == "fixture_allowed_stale"
    assert stale_fixture_market.level == "strong"
    assert stale_fixture_market.freshness_cap_applied is False

    perp_listing = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot={
                "return_24h": 0.18,
                "volume_zscore_24h": 3.1,
                "volume_to_market_cap": 0.24,
                "timestamp": now.isoformat(),
                "source": "unit_test_market",
            },
            derivatives_snapshot={
                "open_interest_24h_change_pct": 0.72,
                "funding_rate_8h": 0.0008,
                "liquidations_24h": 2_500_000,
                "long_short_ratio": 2.1,
                "futures_volume_24h": 12_000_000,
                "timestamp": now.isoformat(),
                "source": "coinalyze_fixture",
            },
            playbook_type="perp_listing_squeeze",
            now=now,
            market_context_observed_at=now,
            market_context_source="unit_test_market",
            allow_stale_fixture_market_context=False,
        )
    )
    assert perp_listing.derivatives_confirmation_level in {"moderate", "strong"}
    assert perp_listing.derivatives_freshness_status == "fresh"
    assert "oi_expansion" in perp_listing.derivatives_confirmation_reasons
    assert "funding_heated" in perp_listing.derivatives_confirmation_reasons

    stale_derivatives = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot={
                "return_24h": 0.18,
                "volume_zscore_24h": 3.1,
                "timestamp": now.isoformat(),
            },
            derivatives_snapshot={
                "open_interest_24h_change_pct": 0.72,
                "funding_rate_8h": 0.0008,
                "timestamp": "2026-06-24T00:00:00Z",
                "source": "coinalyze_live",
            },
            playbook_type="perp_listing_squeeze",
            now=now,
            market_context_observed_at=now,
            market_context_source="unit_test_market",
            allow_stale_fixture_market_context=False,
        )
    )
    assert stale_derivatives.derivatives_freshness_status == "stale"
    assert "needs_fresh_derivatives_confirmation" in stale_derivatives.missing_fields
    assert "oi_expansion" not in stale_derivatives.reasons

    proxy_with_liquidity = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot={
                "return_24h": 0.42,
                "volume_zscore_24h": 4.0,
                "volume_to_market_cap": 0.34,
                "timestamp": now.isoformat(),
            },
            dex_liquidity_snapshot={
                "pool_liquidity_usd": 850_000,
                "dex_volume_24h": 1_600_000,
                "pool_age_hours": 28,
                "timestamp": now.isoformat(),
                "source": "geckoterminal_fixture",
            },
            playbook_type="rwa_preipo_proxy",
            now=now,
            market_context_observed_at=now,
            market_context_source="unit_test_market",
            allow_stale_fixture_market_context=False,
        )
    )
    assert proxy_with_liquidity.dex_liquidity_level in {"moderate", "strong"}
    assert proxy_with_liquidity.dex_freshness_status == "fresh"
    assert "dex_volume_spike" in proxy_with_liquidity.dex_liquidity_reasons

    illiquid_proxy = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot={
                "return_24h": 0.60,
                "volume_zscore_24h": 6.0,
                "volume_to_market_cap": 0.45,
                "timestamp": now.isoformat(),
            },
            dex_liquidity_snapshot={
                "pool_liquidity_usd": 45_000,
                "dex_volume_24h": 500_000,
                "price_impact_2pct": 0.08,
                "timestamp": now.isoformat(),
                "source": "geckoterminal_fixture",
            },
            playbook_type="rwa_preipo_proxy",
            now=now,
            market_context_observed_at=now,
            market_context_source="unit_test_market",
            allow_stale_fixture_market_context=False,
        )
    )
    assert illiquid_proxy.market_confirmation_score <= 74
    assert "liquidity_sanity" in illiquid_proxy.missing_fields
    assert "dex_liquidity_sanity_cap" in illiquid_proxy.warnings

    strategic_protocol = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot={"return_24h": 0.10, "volume_zscore_24h": 2.8, "timestamp": now.isoformat()},
            protocol_metrics_snapshot={
                "tvl": 1_200_000_000,
                "tvl_change_24h_pct": 0.11,
                "fees_change_24h_pct": 0.22,
                "protocol_dex_volume_24h": 18_000_000,
                "timestamp": now.isoformat(),
                "source": "defillama_fixture",
            },
            playbook_type="strategic_investment_or_valuation",
            now=now,
            market_context_observed_at=now,
            market_context_source="unit_test_market",
            allow_stale_fixture_market_context=False,
        )
    )
    assert strategic_protocol.protocol_metrics_level in {"moderate", "strong"}
    assert "protocol_tvl_growth" in strategic_protocol.protocol_metrics_reasons

    security_outflow = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot={"return_24h": -0.22, "volume_zscore_24h": 3.2, "timestamp": now.isoformat()},
            protocol_metrics_snapshot={
                "tvl_change_24h_pct": -0.18,
                "timestamp": now.isoformat(),
                "source": "defillama_fixture",
            },
            playbook_type="security_or_regulatory_shock",
            now=now,
            market_context_observed_at=now,
            market_context_source="unit_test_market",
            allow_stale_fixture_market_context=False,
        )
    )
    assert "downside_reaction" in security_outflow.reasons
    assert "protocol_tvl_outflow" in security_outflow.protocol_metrics_reasons

    weak_market = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(playbook_type="market_anomaly_unknown")
    )
    assert weak_market.market_context_freshness_status == "missing"
    assert "market_context_missing" in weak_market.reasons
    assert weak_market.level == "none"
    assert "insufficient_data" in weak_market.reasons
    low_quality = event_evidence_quality.evaluate_evidence_quality(
        RawDiscoveredEvent(
            raw_id="poly",
            provider="polymarket",
            fetched_at=now,
            published_at=now,
            source_url="https://polymarket.com/event/will-spacex-ipo",
            title="Will SpaceX IPO this year?",
            body="Prediction market context only; no token impact path is explained.",
            raw_json={},
            source_confidence=0.5,
            content_hash="poly",
        ),
        hypothesis=SimpleNamespace(impact_category="rwa_preipo_proxy"),
        symbol="VELVET",
        coin_id="velvet",
    )
    assert low_quality.source_class == "prediction_market"
    assert low_quality.evidence_quality_score <= 55


def test_evidence_quality_uses_registry_authority_and_contract_caps():
    import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry
    import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality

    untrusted = (
        {
            "provider": "gdelt",
            "source_url": "https://reuters.example/story",
            "title": "Binance will list TEST in an official announcement",
            "body": "TEST token listing creates a direct trading mechanism.",
        },
        {
            "provider": "gdelt",
            "source_url": "https://medium.com/@random/test",
            "title": "Official project TEST listing",
            "body": "TEST token offers direct pre-IPO exposure.",
        },
        {
            "provider": "gdelt",
            "source_url": "https://binance.evil.example/story",
            "title": "TEST listing",
            "body": "TEST token listing creates a direct trading mechanism.",
        },
    )
    for row in untrusted:
        registry = event_source_registry.assess_source(row, symbol="TEST", coin_id="test")
        quality = event_evidence_quality.evaluate_evidence_quality(row, symbol="TEST", coin_id="test")
        assert registry.source_class == "broad_news"
        assert quality.source_class == "broad_news"
        assert quality.evidence_quality_score <= registry.confidence_cap <= 58
        assert "source_authority_unverified" in quality.reason_codes

    official = {
        "provider": "official_exchange",
        "title": "TEST listing",
        "body": "TEST/USDT trading pair will be listed.",
    }
    registry = event_source_registry.assess_source(official, symbol="TEST", coin_id="test")
    quality = event_evidence_quality.evaluate_evidence_quality(official, symbol="TEST", coin_id="test")
    assert registry.source_class == "official_exchange"
    assert quality.source_class == "official_exchange"
    assert quality.evidence_quality_score <= registry.confidence_cap


def test_evidence_quality_rejects_boolean_and_nonfinite_reliability_priors():
    import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality

    row = {
        "provider": "gdelt",
        "source_url": "https://reuters.example/story",
        "title": "TEST market context",
        "body": "General context mentions TEST without an official catalyst.",
    }
    baseline = event_evidence_quality.evaluate_evidence_quality(
        row,
        symbol="TEST",
        coin_id="test",
    )

    for invalid in (True, float("nan"), float("inf"), float("-inf")):
        result = event_evidence_quality.evaluate_evidence_quality(
            row,
            symbol="TEST",
            coin_id="test",
            source_reliability_prior=invalid,
            use_source_reliability_prior=True,
        )

        assert result.evidence_quality_score == baseline.evidence_quality_score
        assert result.source_reliability_prior is None
        assert "source_reliability_prior_applied" not in result.reason_codes


def test_event_source_enrichment_article_quality_statuses_and_llm_body_gate():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw_event(raw_id: str, url: str, title: str, body: str = "RSS summary says SpaceX pre-IPO exposure.") -> RawDiscoveredEvent:
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="rss",
            fetched_at=now,
            published_at=now,
            source_url=url,
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.9,
            content_hash=raw_id,
        )

    cfg = event_source_enrichment.EventSourceEnrichmentConfig(enabled=True, min_source_confidence=0.5)
    google_raw = raw_event(
        "google-placeholder",
        "https://news.google.com/rss/articles/placeholder?oc=5",
        "SpaceX pre-IPO exposure - Google News",
    )
    google = event_source_enrichment.enrich_source_text(
        google_raw,
        cfg=cfg,
        fetch_fn=lambda *_: "<html><title>Google News</title><body>Google News</body></html>",
    )
    assert google.article is not None
    assert google.article.article_quality_status == event_source_enrichment.ARTICLE_QUALITY_REDIRECT_PLACEHOLDER
    google_packet = event_llm_extractor.build_raw_event_packet(event_source_enrichment.annotate_raw_event_with_enrichment(google))
    assert google_packet["body"] == google_raw.body
    assert google_packet["source_enrichment"]["article_quality_status"] == "redirect_placeholder"

    ticker_html = """
    <html><body>
    BTC $60000 +1% ETH $1500 -2% SOL $70 +3% XRP $1 +4% DOGE $0.10 +5%
    ADA $0.50 +1% BNB $500 -1% TRX $0.30 +2% LINK $8 +4% HYPE $50 +5%
    <article><h1>SpaceX pre-IPO exposure</h1>
    <p>Velvet Capital lets users trade tokenized SpaceX pre-IPO exposure with a clear proxy mechanism.</p>
    <p>This paragraph adds enough real article text to avoid the thin-page detector while the ticker sidebar remains obvious.</p>
    <p>Independent source context says the proxy venue narrative is the catalyst, not a generic price table.</p>
    </article></body></html>
    """
    ticker = event_source_enrichment.enrich_source_text(
        raw_event("ticker-sidebar", "https://cointelegraph.com/news/spacex-pre-ipo-exposure", "SpaceX pre-IPO exposure"),
        cfg=cfg,
        fetch_fn=lambda *_: ticker_html,
    )
    assert ticker.article is not None
    assert ticker.article.ticker_sidebar_detected is True
    assert ticker.article.article_quality_status == event_source_enrichment.ARTICLE_QUALITY_BOILERPLATE_HEAVY

    good_html = """
    <html><head><title>Velvet offers SpaceX exposure</title>
    <meta name="author" content="Reporter">
    <meta property="article:published_time" content="2026-06-18T10:00:00Z">
    <link rel="canonical" href="https://example.com/velvet-spacex"></head>
    <body><article><h1>Velvet offers SpaceX exposure</h1>
    <p>Velvet Capital lets users trade tokenized SpaceX pre-IPO exposure through its crypto venue.</p>
    <p>The article explains why VELVET token demand may respond to the external SpaceX catalyst.</p>
    <p>It includes the candidate asset, the external catalyst, and a direct mechanism rather than sidebar boilerplate.</p>
    <p>Operators still need market confirmation before any research alert can be promoted.</p></article></body></html>
    """
    good = event_source_enrichment.enrich_source_text(
        raw_event("good-article", "https://coindesk.com/markets/velvet-spacex", "Velvet offers SpaceX exposure"),
        cfg=cfg,
        fetch_fn=lambda *_: good_html,
    )
    assert good.article is not None
    assert good.article.article_quality_status == event_source_enrichment.ARTICLE_QUALITY_GOOD
    assert good.article.canonical_url == "https://example.com/velvet-spacex"
    assert good.triage is not None
    assert good.triage.decision == event_source_enrichment.SOURCE_TRIAGE_SEND_TO_LLM

    blocked = event_source_enrichment.enrich_source_text(
        raw_event("anti-bot", "https://news.example/blocked", "SpaceX pre-IPO exposure blocked"),
        cfg=cfg,
        fetch_fn=lambda *_: {"body": "<html><body>Checking your browser. Verify you are human.</body></html>", "status_code": 403},
    )
    assert blocked.article is not None
    assert blocked.article.article_quality_status == event_source_enrichment.ARTICLE_QUALITY_PAYWALL_OR_BLOCKED
    assert blocked.triage is not None
    assert blocked.triage.decision == event_source_enrichment.SOURCE_TRIAGE_REJECT


def test_event_source_enrichment_triage_and_fixture_source_quality_judge():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMSourceQualityProvider

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw_event(raw_id: str, provider: str, url: str, body: str, raw_json=None) -> RawDiscoveredEvent:
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=url,
            title="AAVE strategic investment and listing catalyst",
            body=body,
            raw_json=raw_json or {},
            source_confidence=0.9,
            content_hash=raw_id,
        )

    article = event_source_enrichment.EventArticleExtraction(
        extractor_version=event_source_enrichment.SOURCE_ENRICHMENT_EXTRACTOR_VERSION,
        cleaner_version="source_enrichment_cleaner_test",
        fetched_url="https://www.binance.com/en/support/announcement/aave",
        final_url="https://www.binance.com/en/support/announcement/aave",
        canonical_url="https://www.binance.com/en/support/announcement/aave",
        body_text=(
            "Binance announces AAVEUSDT spot listing and explains the trading pair, token identity, "
            "and catalyst mechanics for AAVE liquidity. The official announcement is long enough "
            "to be treated as a real article for source triage."
        ),
        body_char_count=220,
        article_quality_status=event_source_enrichment.ARTICLE_QUALITY_GOOD,
    )
    official = event_source_enrichment.triage_source(
        raw_event("official", "binance_announcements", "https://www.binance.com/en/support/announcement/aave", article.body_text),
        article=article,
    )
    assert official.source_is_official is True
    assert official.source_has_direct_token_mechanism is True
    assert official.decision == event_source_enrichment.SOURCE_TRIAGE_SEND_TO_LLM

    cryptopanic = event_source_enrichment.triage_source(
        raw_event(
            "cryptopanic",
            "cryptopanic_news",
            "https://cryptopanic.com/news/rune",
            "RUNE token exploit coverage explains the hack catalyst and THORChain protocol impact.",
            raw_json={"currency_tags": ["RUNE"]},
        ),
        article=article,
    )
    assert cryptopanic.source_has_direct_token_mechanism is True
    assert cryptopanic.decision == event_source_enrichment.SOURCE_TRIAGE_SEND_TO_LLM

    seo_article = event_source_enrichment.EventArticleExtraction(
        extractor_version="x",
        cleaner_version="x",
        fetched_url="https://seo.example/binance-guide",
        final_url="https://seo.example/binance-guide",
        canonical_url=None,
        body_text="Register Binance now with referral code USD777 and sign up now for lifetime fee bonus.",
        body_char_count=95,
        article_quality_status=event_source_enrichment.ARTICLE_QUALITY_BOILERPLATE_HEAVY,
        warnings=("boilerplate_heavy",),
    )
    seo = event_source_enrichment.triage_source(
        raw_event("seo", "rss", "https://seo.example/binance-guide", seo_article.body_text),
        article=seo_article,
    )
    assert seo.source_is_affiliate_or_seo is True
    assert seo.decision == event_source_enrichment.SOURCE_TRIAGE_DIAGNOSTIC_ONLY

    recap = event_source_enrichment.triage_source(
        raw_event("recap", "rss", "https://news.example/market-recap", "Market recap and price prediction for AAVE token today."),
        article=article,
    )
    assert recap.source_is_recapped_news is True
    assert recap.source_quality_score < official.source_quality_score

    prediction_context = event_source_enrichment.triage_source(
        raw_event("poly", "polymarket", "https://polymarket.com/event/world-cup", "Prediction market context for World Cup odds."),
        article=article,
    )
    assert prediction_context.decision == event_source_enrichment.SOURCE_TRIAGE_RAW_OBSERVATION

    annotated = event_source_enrichment.annotate_raw_event_with_enrichment(
        event_source_enrichment.EventSourceEnrichmentResult(
            raw_event=raw_event("seo-judge", "rss", "https://seo.example/binance-guide", seo_article.body_text),
            enriched_text=seo_article.body_text,
            article=seo_article,
            triage=seo,
            status=seo_article.article_quality_status,
        )
    )
    provider = FixtureLLMSourceQualityProvider(cases={
        "seo-judge": {
            "is_real_article": True,
            "article_quality_status": "good",
            "source_quality_score": 95,
            "reason": "LLM incorrectly trusts the page",
            "warnings": [],
        },
        "real-judge": {
            "is_real_article": True,
            "article_quality_status": "good",
            "source_quality_score": 88,
            "reason": "real article",
            "warnings": [],
        },
        "boilerplate-judge": {
            "is_real_article": False,
            "article_quality_status": "boilerplate_heavy",
            "source_quality_score": 22,
            "reason": "mostly navigation",
            "warnings": ["boilerplate"],
        },
    })
    unsafe = event_source_enrichment.run_source_quality_judge(
        annotated,
        provider=provider,
        cfg=event_source_enrichment.EventSourceQualityJudgeConfig(enabled=True, min_importance_score=0),
    )
    assert unsafe is not None
    assert unsafe.is_real_article is False
    assert unsafe.source_quality_score <= 35
    assert "deterministic_triage_override" in unsafe.warnings

    real_raw = event_source_enrichment.annotate_raw_event_with_enrichment(
        event_source_enrichment.EventSourceEnrichmentResult(
            raw_event=raw_event("real-judge", "rss", "https://coindesk.com/aave", article.body_text),
            enriched_text=article.body_text,
            article=article,
            triage=official,
            status=article.article_quality_status,
        )
    )
    real = event_source_enrichment.run_source_quality_judge(
        real_raw,
        provider=provider,
        cfg=event_source_enrichment.EventSourceQualityJudgeConfig(enabled=True, min_importance_score=0),
    )
    assert real is not None
    assert real.is_real_article is True
    assert real.article_quality_status == "good"

    boilerplate = event_source_enrichment.run_source_quality_judge(
        RawDiscoveredEvent(
            raw_id="boilerplate-judge",
            provider="fixture",
            fetched_at=now,
            published_at=now,
            source_url="https://fixture.test/boilerplate",
            title="Boilerplate source",
            body="Boilerplate",
            raw_json={},
            source_confidence=0.9,
            content_hash="boilerplate-judge",
        ),
        provider=provider,
        cfg=event_source_enrichment.EventSourceQualityJudgeConfig(enabled=True, min_importance_score=0),
    )
    assert boilerplate is not None
    assert boilerplate.article_quality_status == "boilerplate_heavy"
    assert boilerplate.is_real_article is False


def test_source_enrichment_persisted_and_llm_flags_require_semantic_truth():
    import crypto_rsi_scanner.event_alpha.radar.source_enrichment as source_enrichment
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    bool_confidence = RawDiscoveredEvent(
        raw_id="bool-confidence",
        provider="fixture",
        fetched_at=datetime(2026, 6, 18, 12, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 18, 12, tzinfo=timezone.utc),
        source_url="https://example.test/bool-confidence",
        title="Token listing announcement",
        body="A listing catalyst.",
        raw_json={},
        source_confidence=True,
        content_hash="bool-confidence",
    )
    assert source_enrichment.should_enrich_source(bool_confidence) is False

    cached = {
        "article": {
            "body_text": "A source body with enough text for the cache adapter.",
            "article_quality_status": source_enrichment.ARTICLE_QUALITY_GOOD,
            "ticker_sidebar_detected": "false",
            "boilerplate_ratio": True,
            "body_char_count": True,
        },
        "triage": {
            "is_real_article": "false",
            "source_is_official": "0",
            "source_is_recapped_news": "no",
            "source_is_affiliate_or_seo": "off",
            "source_has_direct_token_mechanism": 2,
            "source_has_candidate_and_catalyst": "unknown",
            "source_quality_score": True,
        },
    }
    article = source_enrichment._article_from_cache(  # noqa: SLF001
        cached,
        fallback_text="fallback",
    )
    triage = source_enrichment._triage_from_cache(cached)  # noqa: SLF001

    assert article.ticker_sidebar_detected is False
    assert article.boilerplate_ratio == 0.0
    assert article.body_char_count == len(article.body_text)
    assert triage is not None
    assert triage.is_real_article is False
    assert triage.source_is_official is False
    assert triage.source_is_recapped_news is False
    assert triage.source_is_affiliate_or_seo is False
    assert triage.source_has_direct_token_mechanism is False
    assert triage.source_has_candidate_and_catalyst is False
    assert triage.source_quality_score == 0.0

    quality = source_enrichment._validate_source_quality_judgment(  # noqa: SLF001
        {
            "is_real_article": "false",
            "article_quality_status": source_enrichment.ARTICLE_QUALITY_GOOD,
            "source_quality_score": True,
        },
        deterministic=None,
    )
    llm = source_enrichment.validate_llm_source_triage(
        {
            "page_type": "article",
            "is_real_article": "false",
            "article_quality": source_enrichment.ARTICLE_QUALITY_GOOD,
            "boilerplate_ratio_estimate": True,
            "is_official_source": "0",
            "is_recap": "no",
            "is_affiliate_or_seo": "off",
            "candidate_catalyst_mechanism_present": "false",
            "evidence_quote": "direct token mechanism",
            "confidence": True,
        },
        source_text="This source describes a direct token mechanism.",
    )

    assert quality.is_real_article is False
    assert quality.source_quality_score == 0.0
    assert llm.is_real_article is False
    assert llm.is_official_source is False
    assert llm.is_recap is False
    assert llm.is_affiliate_or_seo is False
    assert llm.candidate_catalyst_mechanism_present is False
    assert llm.boilerplate_ratio_estimate == 0.0
    assert llm.confidence == 0.0
    assert "mechanism_without_quote" not in llm.warnings

    explicit_true = source_enrichment.validate_llm_source_triage(
        {
            "page_type": "article",
            "is_real_article": "yes",
            "article_quality": source_enrichment.ARTICLE_QUALITY_GOOD,
            "is_official_source": "on",
            "is_recap": 1,
            "is_affiliate_or_seo": False,
            "candidate_catalyst_mechanism_present": "true",
            "evidence_quote": "direct token mechanism",
            "confidence": 0.8,
        },
        source_text="This source describes a direct token mechanism.",
    )
    assert explicit_true.is_real_article is True
    assert explicit_true.is_official_source is True
    assert explicit_true.is_recap is True
    assert explicit_true.candidate_catalyst_mechanism_present is True
