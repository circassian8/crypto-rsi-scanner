"""Focused outcomes package architecture tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone



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
    assert rows[0]["outcome_label"] == "early_good"
    assert rows[0]["research_only"] is True
    assert rows[0]["trade_created"] is False
    assert rows[0]["paper_trade_created"] is False
    assert rows[0]["normal_rsi_signal_written"] is False
    assert rows[0]["triggered_fade_created"] is False
    assert "validation_rate" in integrated_radar_outcomes.format_integrated_radar_calibration_report(rows)
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
    assert "useful=1" in report
    assert "recommendations:" in report
    assert "No thresholds, alert tiers, paper trades, live DB rows, or execution were changed." in report


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

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})

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


def test_event_alpha_alert_store_snapshots_and_fills_outcomes():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    alerts = event_alerts.build_event_alert_candidates(
        _full_event_discovery_fixture_result(),
        now=now,
    )
    assert any(alert.symbol == "TESTVELVET" for alert in alerts)

    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "event_alpha_alerts.jsonl"
        cfg = event_alpha_alert_store.EventAlphaAlertStoreConfig(path=store_path)
        wrote = event_alpha_alert_store.write_alert_snapshots(alerts, cfg=cfg, now=now)
        assert wrote.rows_written == len(alerts)
        loaded = event_alpha_alert_store.load_alert_snapshots(store_path)
        assert loaded.rows_read == len(alerts)
        report = event_alpha_alert_store.format_alert_snapshot_report(loaded)
        assert "EVENT ALPHA ALERT SNAPSHOT REPORT" in report
        assert "by playbook:" in report
        assert "by expected direction:" in report
        assert "by tier:" in report

        prices_path = Path(tmp) / "prices.json"
        prices_path.write_text(json.dumps({
            "source": "fixture",
            "interval": "1h",
            "prices": [
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-15T17:00:00Z", "close": 9.0, "high": 9.2, "low": 8.8},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-15T20:00:00Z", "close": 8.2, "high": 8.5, "low": 8.0},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-16T16:00:00Z", "close": 7.2, "high": 7.4, "low": 6.9},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-18T16:00:00Z", "close": 6.0, "high": 6.3, "low": 5.8},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-22T16:00:00Z", "close": 5.4, "high": 5.6, "low": 5.1},
            ],
        }), encoding="utf-8")
        out_path = Path(tmp) / "with_outcomes.jsonl"
        filled = event_alpha_alert_store.fill_alert_outcomes(
            loaded.rows,
            prices_path,
            out_path,
            source_path=store_path,
        )
        assert filled.rows_written == len(alerts)
        assert filled.rows_with_outcomes >= 1
        out_rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
        velvet = next(row for row in out_rows if row.get("asset_symbol") == "TESTVELVET")
        assert velvet["outcome_price_interval"] == "1h"
        assert velvet["outcome_status"] == "filled"
        assert velvet["outcome_source"] == "fixture"
        assert velvet["return_1h"] is not None
        assert velvet["return_24h"] is not None
        assert velvet["return_72h"] is not None
        assert velvet["return_7d"] is not None
        assert velvet["primary_horizon_return"] is not None
        assert velvet["direction_hit"] is True
        assert velvet["max_favorable_excursion"] is not None
        assert velvet["max_adverse_excursion"] is not None
        outcome_report = event_alpha_alert_store.format_alert_snapshot_report(
            event_alpha_alert_store.load_alert_snapshots(out_path)
        )
        assert "outcomes:" in outcome_report

        status_out = Path(tmp) / "status_outcomes.jsonl"
        status_result = event_alpha_alert_store.fill_alert_outcomes(
            [
                {"observed_at": "2026-06-15T16:00:00+00:00", "asset_symbol": "TESTVELVET", "entry_reference_price": 10.0},
                {"observed_at": "2026-06-15T16:00:00+00:00", "asset_symbol": "MEME", "entry_reference_price": 1.0},
                {"observed_at": "2026-06-15T16:00:00+00:00", "entry_reference_price": 1.0},
            ],
            prices_path,
            status_out,
        )
        status_rows = [json.loads(line) for line in status_out.read_text(encoding="utf-8").splitlines()]
        assert [row["outcome_status"] for row in status_rows] == [
            "filled",
            "insufficient_market_data",
            "skipped_no_asset",
        ]
        assert status_result.missing_price_rows == 2
        assert "MFE/MAE by playbook:" in outcome_report
        assert "Outcome metrics by playbook:" in outcome_report


def test_event_alpha_outcomes_playbook_specific_metrics():
    import crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts as event_alpha_outcomes

    listing_row = {
        "observed_at": "2026-06-18T12:00:00+00:00",
        "entry_reference_price": 10.0,
        "playbook_type": "listing_volatility",
        "expected_direction": "volatility",
        "success_metric": "volatility",
        "primary_horizon": "24h",
    }
    prices = [
        {"timestamp": "2026-06-18T13:00:00+00:00", "close": 10.5, "high": 11.5, "low": 9.8},
        {"timestamp": "2026-06-18T20:00:00+00:00", "close": 9.2, "high": 10.0, "low": 8.8},
    ]
    metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(
        listing_row,
        prices,
        returns={"max_favorable_excursion": 0.15, "max_adverse_excursion": 0.12, "primary_horizon_return": -0.08},
    )
    assert metrics["volatility_hit"] is True
    assert metrics["mfe_mae_ratio"] > 1.0

    proxy_row = {
        "observed_at": "2026-06-18T12:00:00+00:00",
        "entry_reference_price": 10.0,
        "playbook_type": "proxy_attention",
        "expected_direction": "up_then_fade",
        "success_metric": "mfe_mae",
        "primary_horizon": "72h",
    }
    proxy_metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(
        proxy_row,
        prices,
        returns={"return_72h": -0.10, "max_favorable_excursion": 0.15, "max_adverse_excursion": 0.05},
    )
    assert proxy_metrics["up_then_fade_hit"] is True

    unlock_row = {
        "observed_at": "2026-06-18T12:00:00+00:00",
        "entry_reference_price": 10.0,
        "playbook_type": "unlock_supply_pressure",
        "expected_direction": "down",
        "success_metric": "direction_hit",
        "primary_horizon": "24h",
        "btc_primary_horizon_return": 0.02,
    }
    unlock_metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(
        unlock_row,
        prices,
        returns={"primary_horizon_return": -0.08},
    )
    assert unlock_metrics["underperformance_vs_btc"] == -0.10

    anomaly_row = {
        "event_type": "exchange_listing",
        "source": "market_anomaly+catalyst_search",
    }
    anomaly_metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(anomaly_row, [])
    assert anomaly_metrics["catalyst_found_after_anomaly"] is True


def test_event_alpha_alert_store_snapshot_policy_filters_rows():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    alerts = event_alerts.build_event_alert_candidates(_full_event_discovery_fixture_result(), now=now)
    store_only_count = sum(1 for alert in alerts if alert.tier == event_alerts.EventAlertTier.STORE_ONLY)
    non_store_count = len(alerts) - store_only_count
    assert store_only_count > 2
    assert non_store_count > 0

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        all_path = root / "all.jsonl"
        all_result = event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=all_path, snapshot_policy="all"),
            now=now,
        )
        assert all_result.rows_written == len(alerts)
        all_rows = [
            json.loads(line)
            for line in all_path.read_text(encoding="utf-8").splitlines()
        ]
        final_store_only_count = sum(
            1 for row in all_rows
            if row["final_tier_after_quality_gate"] == event_alerts.EventAlertTier.STORE_ONLY.value
        )
        final_non_store_count = len(all_rows) - final_store_only_count

        non_store_path = root / "non-store.jsonl"
        non_store_result = event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=non_store_path, snapshot_policy="non_store"),
            now=now,
        )
        assert non_store_result.rows_written == final_non_store_count
        assert all(
            json.loads(line)["final_tier_after_quality_gate"] != event_alerts.EventAlertTier.STORE_ONLY.value
            for line in non_store_path.read_text(encoding="utf-8").splitlines()
        )

        sampled_path = root / "sampled.jsonl"
        sampled_result = event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(
                path=sampled_path,
                snapshot_policy="sampled_controls",
                sampled_controls_limit=2,
            ),
            now=now,
        )
        assert sampled_result.rows_written == final_non_store_count + 2
        sampled_rows = [
            json.loads(line)
            for line in sampled_path.read_text(encoding="utf-8").splitlines()
        ]
        assert sum(
            1 for row in sampled_rows
            if row["final_tier_after_quality_gate"] == event_alerts.EventAlertTier.STORE_ONLY.value
        ) == 2


def test_event_alpha_alert_store_scanner_report_and_outcome_fill_commands():
    import contextlib
    import io
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    alerts = event_alerts.build_event_alert_candidates(_full_event_discovery_fixture_result(), now=now)
    original = {
        "EVENT_ALPHA_ALERT_STORE_PATH": config.EVENT_ALPHA_ALERT_STORE_PATH,
        "EVENT_ALPHA_FEEDBACK_PATH": config.EVENT_ALPHA_FEEDBACK_PATH,
    }
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "alerts.jsonl"
        feedback_path = Path(tmp) / "feedback.jsonl"
        config.EVENT_ALPHA_ALERT_STORE_PATH = store_path
        config.EVENT_ALPHA_FEEDBACK_PATH = feedback_path
        event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=store_path),
            now=now,
        )
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_alerts_report()
            text = out.getvalue()
            assert "EVENT ALPHA ALERT SNAPSHOT REPORT" in text
            assert "by playbook:" in text

            prices_path = Path(tmp) / "prices.json"
            prices_path.write_text(json.dumps({
                "source": "fixture",
                "interval": "1h",
                "prices": [
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-15T17:00:00Z", "close": 9.0, "high": 9.1, "low": 8.9},
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-16T16:00:00Z", "close": 7.0, "high": 7.3, "low": 6.8},
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-18T16:00:00Z", "close": 6.0, "high": 6.2, "low": 5.8},
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-22T16:00:00Z", "close": 5.0, "high": 5.3, "low": 4.9},
                ],
            }), encoding="utf-8")
            filled_path = Path(tmp) / "filled.jsonl"
            fill_out = io.StringIO()
            with contextlib.redirect_stdout(fill_out):
                scanner.event_alpha_fill_outcomes(str(prices_path), str(filled_path))
            fill_text = fill_out.getvalue()
            assert "EVENT ALPHA ALERT OUTCOMES FILLED" in fill_text
            assert filled_path.exists()
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_event_alpha_quality_gate_dominates_router_and_artifacts():
    import json
    import tempfile
    from dataclasses import asdict
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
    import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
    import crypto_rsi_scanner.event_alpha.radar.market_confirmation as event_market_confirmation
    import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    def quality(level, score, *, path="proxy_exposure", role="proxy_instrument", source="crypto_news", specificity="direct_value_capture"):
        return {
            "impact_path_type": path,
            "impact_path_strength": "strong" if path != "insufficient_data" else "none",
            "candidate_role": role,
            "evidence_quality_score": 80 if source != "insufficient_data" else 0,
            "source_class": source,
            "evidence_specificity": specificity,
            "market_confirmation_score": 60 if level in {"watchlist", "high_priority"} else 35,
            "market_confirmation_level": "moderate" if level in {"watchlist", "high_priority"} else "weak",
            "opportunity_score_final": score,
            "opportunity_level": level,
            "opportunity_verdict_reasons": ["test_quality_gate"],
            "why_local_only": "quality_gate_test_local_only" if level == "local_only" else "not_local_only",
            "why_not_watchlist": "quality_gate_test_not_watchlist" if level in {"local_only", "exploratory", "validated_digest"} else "already_watchlisted",
            "manual_verification_items": ["verify source, identity, market confirmation, and liquidity"],
            "upgrade_requirements": ["needs confirmed impact path"] if level in {"local_only", "exploratory"} else [],
            "downgrade_warnings": ["insufficient_data"] if path == "insufficient_data" else [],
        }

    positive_market_block = quality(
        "local_only",
        35,
        path="proxy_attention",
        role="proxy_instrument",
        source="crypto_news",
        specificity="token_and_catalyst",
    )
    positive_market_block["why_local_only"] = "strong_market_confirmation"
    positive_market_block["impact_path_strength"] = "weak"
    positive_market_block["market_confirmation_level"] = "strong"
    positive_market_block["market_confirmation_score"] = 90
    _, normalized_block = event_watchlist.quality_cap_watchlist_state(
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        positive_market_block,
    )
    assert normalized_block == "weak_impact_path_despite_market_confirmation"
    verdict = event_opportunity_verdict.evaluate_opportunity(
        impact_path=event_impact_path_validator.ImpactPathValidation(
            impact_path_type=event_impact_path_validator.ImpactPathType.TECHNOLOGY_RISK.value,
            impact_path_strength=event_impact_path_validator.ImpactPathStrength.WEAK.value,
            candidate_role=event_impact_path_validator.CandidateRole.MACRO_AFFECTED_ASSET.value,
            evidence_specificity_score=50,
            required_evidence_met=False,
            market_confirmation_required=True,
            digest_eligible_by_impact_path=False,
            why_digest_ineligible="technology_risk",
            impact_path_reason="generic_policy_only",
            opportunity_score_v2=45,
        ),
        market_confirmation=event_market_confirmation.EventMarketConfirmationResult(
            market_confirmation_score=82,
            level=event_market_confirmation.MarketConfirmationLevel.STRONG.value,
            reasons=("price_momentum",),
        ),
        evidence_quality=event_evidence_quality.EvidenceQualityResult(
            evidence_quality_score=72,
            source_class=event_evidence_quality.SourceClass.CRYPTO_NEWS.value,
            evidence_specificity=event_evidence_quality.EvidenceSpecificity.GENERIC_CONTEXT.value,
        ),
    )
    assert verdict.why_local_only != "strong_market_confirmation"
    assert verdict.why_not_watchlist != "strong_market_confirmation"
    assert "weak_impact_path_despite_market_confirmation" in verdict.missing_requirements
    assert verdict.score_components and verdict.score_components["market_confirmation"] > 0

    def entry(symbol, *, state, playbook, q, event_name=None, relationship="proxy_attention", external_asset="World Cup"):
        requested_state = state
        final_state, block_reason = event_watchlist.quality_cap_watchlist_state(requested_state, q)
        capped = bool(block_reason and final_state != requested_state)
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|cluster|{playbook}",
            cluster_id=f"cluster:{symbol}",
            event_id=f"event:{symbol}",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type=relationship,
            external_asset=external_asset,
            event_time="2026-06-25T12:00:00+00:00",
            state=final_state,
            previous_state=event_watchlist.EventWatchlistState.RADAR.value,
            requested_state_before_quality_gate=requested_state,
            final_state_after_quality_gate=final_state,
            state_quality_capped=capped,
            quality_state_block_reason=block_reason,
            first_seen_at="2026-06-25T08:00:00+00:00",
            last_seen_at="2026-06-25T08:30:00+00:00",
            source_count=1,
            highest_score=85,
            latest_score=85,
            latest_tier="WATCHLIST" if state == event_watchlist.EventWatchlistState.WATCHLIST.value else "HIGH_PRIORITY_WATCH",
            latest_event_name=event_name or f"{symbol} quality gate fixture",
            latest_source="Bitcoin World" if symbol == "BTC" else "fixture",
            latest_playbook_type=playbook,
            latest_effective_playbook_type=playbook,
            latest_playbook_score=85,
            latest_playbook_action="watchlist",
            latest_score_components=q,
            should_alert=True,
            material_change_reasons=("score_jump",),
            score_jump=20,
        )

    btc = entry(
        "BTC",
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        q=quality(
            "local_only",
            0,
            path="insufficient_data",
            role="unknown_with_reason",
            source="insufficient_data",
            specificity="insufficient_data",
        ),
        event_name="Polymarket World Cup Volume Surges - Bitcoin World",
    )
    zero = entry(
        "ZERO",
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        q=quality("watchlist", 0),
    )
    digest = entry(
        "DIG",
        state=event_watchlist.EventWatchlistState.RADAR.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        q=quality("validated_digest", 72),
    )
    watch = entry(
        "WATCH",
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        q=quality("watchlist", 82),
    )
    rune_quality = quality(
        "watchlist",
        83,
        path="exploit_security_event",
        role="direct_subject",
        source="crypto_news",
        specificity="direct_token_mechanism",
    )
    rune_quality.update({
        "validated_symbol": "RUNE",
        "validated_coin_id": "thorchain",
        "validation_stage": "impact_path_validated",
        "impact_category": event_playbooks.EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK.value,
        "playbook_type": event_playbooks.EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK.value,
        "impact_path_reason": "exploit_security_event",
        "market_confirmation_level": "moderate",
        "market_confirmation_score": 65,
    })
    rune = entry(
        "RUNE",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        playbook=event_playbooks.EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK.value,
        q=rune_quality,
        event_name="THORChain RUNE exploit validated impact hypothesis",
        relationship="impact_hypothesis",
        external_asset="THORChain",
    )
    high = entry(
        "HIGH",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_FADE.value,
        q=quality("high_priority", 92),
    )
    trigger = entry(
        "FADE",
        state=event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_FADE.value,
        q=quality("local_only", 0, path="insufficient_data"),
    )

    routed = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=7,
            latest_only=True,
            entries=[btc, zero, digest, watch, rune, high, trigger],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            score_jump_threshold=10,
            validated_hypothesis_digest_enabled=True,
        ),
    )
    by_symbol = {decision.entry.symbol: decision for decision in routed.decisions}
    assert event_watchlist.final_state_value(btc) == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
    assert event_watchlist.requested_state_value(btc) == event_watchlist.EventWatchlistState.WATCHLIST.value
    assert event_watchlist.state_is_quality_capped(btc) is True
    assert event_watchlist.requested_state_value(rune) == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
    assert event_watchlist.final_state_value(rune) == event_watchlist.EventWatchlistState.WATCHLIST.value
    assert event_watchlist.state_is_quality_capped(rune) is True
    assert rune.quality_state_block_reason == "opportunity_level_caps_state:watchlist"
    assert event_watchlist.final_state_value(watch) == event_watchlist.EventWatchlistState.WATCHLIST.value
    assert event_watchlist.final_state_value(high) == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
    assert event_watchlist.final_state_value(trigger) == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value
    assert by_symbol["BTC"].requested_route_before_quality_gate == "RESEARCH_DIGEST"
    assert by_symbol["BTC"].final_route_after_quality_gate == "STORE_ONLY"
    assert by_symbol["BTC"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["BTC"].alertable is False
    assert by_symbol["BTC"].quality_gate_block_reason == "impact_path_type_insufficient_data"
    assert by_symbol["ZERO"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["ZERO"].quality_gate_block_reason == "opportunity_score_final_zero"
    assert by_symbol["DIG"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["WATCH"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["RUNE"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["RUNE"].alertable is True
    assert by_symbol["RUNE"].quality_gate_block_reason in (None, "")
    assert "opportunity_level_caps_state:watchlist" not in by_symbol["RUNE"].reason
    assert by_symbol["HIGH"].route == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH
    assert by_symbol["FADE"].route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
    assert by_symbol["FADE"].alertable is True

    report = event_alpha_router.format_router_report(routed)
    assert "quality gate:" in report
    assert "requested=RESEARCH_DIGEST final=STORE_ONLY" in report

    now = datetime(2026, 6, 25, 8, 31, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "alerts.jsonl"
        write = event_alpha_alert_store.write_alert_snapshots(
            [],
            router_result=routed,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=out, snapshot_policy="all"),
            now=now,
        )
        rows = event_alpha_alert_store.load_alert_snapshots(write.path).rows
    btc_snapshot = next(row for row in rows if row.get("symbol") == "BTC")
    assert btc_snapshot["requested_route_before_quality_gate"] == "RESEARCH_DIGEST"
    assert btc_snapshot["final_route_after_quality_gate"] == "STORE_ONLY"
    assert btc_snapshot["requested_state_before_quality_gate"] == "WATCHLIST"
    assert btc_snapshot["final_state_after_quality_gate"] == "QUALITY_BLOCKED"
    assert btc_snapshot["quality_state_block_reason"] == "impact_path_type_insufficient_data"
    assert btc_snapshot["state_quality_capped"] is True
    assert btc_snapshot["final_tier_after_quality_gate"] == "STORE_ONLY"
    assert btc_snapshot["quality_gate_block_reason"] == "impact_path_type_insufficient_data"
    assert btc_snapshot["route"] == "STORE_ONLY"
    assert btc_snapshot["lane"] == "LOCAL_ONLY"
    assert btc_snapshot["tier"] == "STORE_ONLY"
    assert btc_snapshot["snapshot_quality_classification"] == "quality_gated_local"
    assert btc_snapshot["requested_tier_before_quality_gate"] == "WATCHLIST"
    assert btc_snapshot["route_alertable"] is False
    assert btc_snapshot["alertable_after_quality_gate"] is False
    snapshots_by_symbol = {row.get("symbol"): row for row in rows}
    assert snapshots_by_symbol["DIG"]["final_route_after_quality_gate"] == "RESEARCH_DIGEST"
    assert snapshots_by_symbol["DIG"]["final_tier_after_quality_gate"] == "RADAR_DIGEST"
    assert snapshots_by_symbol["WATCH"]["final_route_after_quality_gate"] == "RESEARCH_DIGEST"
    assert snapshots_by_symbol["WATCH"]["state_quality_capped"] is False
    assert snapshots_by_symbol["WATCH"]["final_state_after_quality_gate"] == "WATCHLIST"
    assert snapshots_by_symbol["WATCH"]["final_tier_after_quality_gate"] == "WATCHLIST"
    assert snapshots_by_symbol["RUNE"]["requested_state_before_quality_gate"] == "HIGH_PRIORITY"
    assert snapshots_by_symbol["RUNE"]["final_state_after_quality_gate"] == "WATCHLIST"
    assert snapshots_by_symbol["RUNE"]["final_route_after_quality_gate"] == "RESEARCH_DIGEST"
    assert snapshots_by_symbol["RUNE"]["quality_state_block_reason"] == "opportunity_level_caps_state:watchlist"
    assert snapshots_by_symbol["RUNE"]["quality_gate_block_reason"] in (None, "")
    assert snapshots_by_symbol["RUNE"]["core_opportunity_id"]
    assert snapshots_by_symbol["RUNE"]["feedback_target"] == snapshots_by_symbol["RUNE"]["core_opportunity_id"]
    assert snapshots_by_symbol["RUNE"]["feedback_target_type"] == "core_opportunity_id"
    assert snapshots_by_symbol["HIGH"]["final_route_after_quality_gate"] == "HIGH_PRIORITY_RESEARCH"
    assert snapshots_by_symbol["HIGH"]["final_tier_after_quality_gate"] == "HIGH_PRIORITY_WATCH"
    assert snapshots_by_symbol["FADE"]["final_route_after_quality_gate"] == "TRIGGERED_FADE_RESEARCH"
    assert snapshots_by_symbol["FADE"]["final_tier_after_quality_gate"] == "TRIGGERED_FADE"
    inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=[{"run_id": "r1", "would_send_count": 1, "lane_counts_due": {"daily_digest": 1}}],
        alert_rows=rows,
        feedback_rows=[],
        research_cards_dir=Path(tmp) / "cards",
        profile="fixture",
        artifact_namespace="fixture",
        notification_runs_path=Path(tmp) / "runs.jsonl",
        alert_store_path=out,
        feedback_path=Path(tmp) / "feedback.jsonl",
    )
    assert "BTC" in {item.symbol for item in inbox.quality_gated_local_only}
    assert "BTC" not in {item.symbol for item in inbox.would_send_without_feedback}
    inbox_text = event_alpha_notification_inbox.format_notification_inbox(inbox)
    assert "local-only learning rows for optional review" in inbox_text
    review = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(profile="fixture", alert_rows=rows)
    )
    assert "Quality Gate Conflicts" in review
    assert "Quality Gate Conflicts:\n- none" in review
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": len(rows)}],
        alert_rows=rows,
        watchlist_rows=[btc, zero, digest, watch, rune, high, trigger],
        include_api_artifacts=True,
    )
    assert doctor.alertable_route_conflicts_with_opportunity_level == 0
    assert doctor.active_watchlist_rows_quality_capped >= 1
    assert doctor.universal_watchlist_state_conflicts == 0
    assert doctor.non_hypothesis_watchlist_quality_conflicts == 0
    assert doctor.quality_capped_watchlist_rows >= 1
    assert doctor.fresh_watchlist_state_conflict_rows == 0
    doctor_text = event_alpha_artifact_doctor.format_artifact_doctor_report(doctor)
    assert "quality-capped rows present:" in doctor_text
    assert "watchlist quality state:" in doctor_text
    uncapped_watchlist_conflict = asdict(btc)
    uncapped_watchlist_conflict["state"] = "WATCHLIST"
    uncapped_watchlist_conflict["final_state_after_quality_gate"] = "WATCHLIST"
    uncapped_watchlist_conflict["state_quality_capped"] = False
    uncapped_watchlist_conflict["run_mode"] = "burn_in"
    uncapped_watchlist_conflict["artifact_namespace"] = "notify_llm_quality"
    doctor_uncapped_watchlist = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 0}],
        watchlist_rows=[uncapped_watchlist_conflict],
        include_api_artifacts=True,
        strict=True,
    )
    assert doctor_uncapped_watchlist.status == "BLOCKED"
    assert doctor_uncapped_watchlist.fresh_watchlist_state_conflict_rows == 1
    with tempfile.TemporaryDirectory() as stale_tmp:
        stale_path = Path(stale_tmp) / "event_watchlist_state.jsonl"
        stale_non_hypothesis = asdict(btc)
        stale_non_hypothesis["key"] = "stale-non-hypothesis|chz"
        stale_non_hypothesis["symbol"] = "CHZ"
        stale_non_hypothesis["coin_id"] = "chiliz"
        stale_non_hypothesis["hypothesis_id"] = None
        stale_non_hypothesis["incident_id"] = None
        stale_non_hypothesis["state"] = "WATCHLIST"
        stale_non_hypothesis["requested_state_before_quality_gate"] = "WATCHLIST"
        stale_non_hypothesis["final_state_after_quality_gate"] = "WATCHLIST"
        stale_non_hypothesis["state_quality_capped"] = False
        stale_non_hypothesis["run_mode"] = "burn_in"
        stale_non_hypothesis["artifact_namespace"] = "notify_llm_quality"
        stale_path.write_text(json.dumps(stale_non_hypothesis) + "\n", encoding="utf-8")
        loaded_stale = event_watchlist.load_watchlist(stale_path).entries[0]
        assert event_watchlist.requested_state_value(loaded_stale) == "WATCHLIST"
        assert event_watchlist.final_state_value(loaded_stale) == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        assert loaded_stale.state == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        assert loaded_stale.state_quality_capped is True
        assert loaded_stale.quality_state_block_reason == "impact_path_type_insufficient_data"
        assert event_watchlist.final_state_value(stale_non_hypothesis) == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        stale_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "r1", "alertable": 0}],
            watchlist_rows=[stale_non_hypothesis],
            include_api_artifacts=True,
            strict=True,
        )
        assert stale_doctor.status == "BLOCKED"
        assert stale_doctor.universal_watchlist_state_conflicts == 1
        assert stale_doctor.non_hypothesis_watchlist_quality_conflicts == 1
    legacy_conflict = dict(btc_snapshot)
    legacy_conflict["run_id"] = "r1"
    legacy_conflict["route_alertable"] = True
    legacy_conflict["route"] = "RESEARCH_DIGEST"
    legacy_conflict["tier"] = "WATCHLIST"
    legacy_conflict.pop("alertable_after_quality_gate", None)
    legacy_conflict.pop("final_route_after_quality_gate", None)
    legacy_conflict.pop("final_tier_after_quality_gate", None)
    legacy_conflict.pop("snapshot_quality_classification", None)
    assert event_alpha_alert_store.classify_alert_snapshot(legacy_conflict) == "legacy_conflict"
    doctor_conflict = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
        alert_rows=[legacy_conflict],
        include_api_artifacts=True,
        strict=True,
    )
    assert doctor_conflict.alertable_route_conflicts_with_opportunity_level == 1
    assert doctor_conflict.status == "WARN"
    assert "alertable_route_conflicts_with_opportunity_level=1" in event_alpha_artifact_doctor.format_artifact_doctor_report(doctor_conflict)
    doctor_conflict_strict_api = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
        alert_rows=[legacy_conflict],
        include_api_artifacts=True,
        strict=True,
        strict_api=True,
    )
    assert doctor_conflict_strict_api.status == "BLOCKED"
    legacy_review = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(profile="fixture", alert_rows=[legacy_conflict])
    )
    assert "Quality Gate Conflicts" in legacy_review
    assert "BTC" in legacy_review
    legacy_inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=[{"run_id": "r1", "would_send_count": 1, "lane_counts_due": {"daily_digest": 1}}],
        alert_rows=[legacy_conflict],
        feedback_rows=[],
        research_cards_dir=Path(tmp) / "cards",
        profile="fixture",
        artifact_namespace="fixture",
        notification_runs_path=Path(tmp) / "runs.jsonl",
        alert_store_path=out,
        feedback_path=Path(tmp) / "feedback.jsonl",
    )
    assert "BTC" in {item.symbol for item in legacy_inbox.legacy_quality_conflicts}
    assert "BTC" not in {item.symbol for item in legacy_inbox.would_send_without_feedback}
    assert "legacy quality conflicts" in event_alpha_notification_inbox.format_notification_inbox(legacy_inbox)
    fresh_conflict = dict(btc_snapshot)
    fresh_conflict["run_mode"] = "burn_in"
    fresh_conflict["artifact_namespace"] = "notify_llm_quality"
    fresh_conflict["final_route_after_quality_gate"] = "RESEARCH_DIGEST"
    fresh_conflict["route"] = "RESEARCH_DIGEST"
    fresh_conflict["route_alertable"] = True
    assert event_alpha_alert_store.classify_alert_snapshot(fresh_conflict) == "legacy_conflict"
    doctor_fresh_conflict = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
        alert_rows=[fresh_conflict],
        include_api_artifacts=True,
        strict=True,
    )
    assert doctor_fresh_conflict.status == "BLOCKED"
    fresh_missing_final = dict(btc_snapshot)
    fresh_missing_final["run_mode"] = "burn_in"
    fresh_missing_final["artifact_namespace"] = "notify_llm_quality"
    fresh_missing_final.pop("final_route_after_quality_gate", None)
    assert event_alpha_alert_store.classify_alert_snapshot(fresh_missing_final) in {"legacy_conflict", "stale_pre_quality_gate"}
    doctor_missing_final = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
        alert_rows=[fresh_missing_final],
        include_api_artifacts=True,
        strict=True,
    )
    assert doctor_missing_final.status == "BLOCKED"

    daily = event_alpha_daily_brief.build_daily_brief(router_result=routed, watchlist_entries=[btc, zero, digest, watch, rune, high, trigger])
    assert "### Quality Gate Downgrades" in daily
    assert "BTC/btc:RESEARCH_DIGEST->STORE_ONLY" in daily
    assert "### Quality-Capped Watchlist Rows" in daily
    assert "BTC/btc: requested=WATCHLIST final=QUALITY_BLOCKED" in daily
    active_section = daily.split("### Active Watchlist", 1)[1].split("### Quality-Capped Watchlist Rows", 1)[0]
    assert "BTC/btc" not in active_section
    assert "WATCH/watch" in active_section
    assert "### Legacy Quality Conflicts" in daily
    freshness_section = daily.split("## Market Freshness Readiness", 1)[1].split("## Diagnostics Appendix", 1)[0]
    assert "Core opportunity freshness:" in freshness_section
    assert freshness_section.count("RUNE/thorchain") == 1
    card = event_research_cards.render_research_card(
        "BTC",
        watchlist_entries=[btc],
        alert_rows=[btc_snapshot],
        route_decisions=[by_symbol["BTC"]],
    )
    assert "## Quality Gate Result" in card.markdown
    assert "Requested route: RESEARCH_DIGEST" in card.markdown
    assert "Final route: STORE_ONLY" in card.markdown
    assert "Final tier: STORE_ONLY" in card.markdown
    assert "Snapshot classification: quality_gated_local" in card.markdown
    assert "## Lifecycle State Gate" in card.markdown
    assert "Requested WATCHLIST blocked because impact_path_type_insufficient_data" in card.markdown
    assert "impact_path_type_insufficient_data" in card.markdown


def test_event_alpha_feedback_marks_watchlist_rows_and_missed_items():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_labels as event_feedback
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="feed|solana|proxy_attention|SpaceX|",
        cluster_id="spacex|ipo_proxy|2026-06-18",
        event_id="feed",
        coin_id="solana",
        symbol="SOL",
        relationship_type="proxy_attention",
        external_asset="SpaceX",
        event_time=None,
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        previous_state="RADAR",
        first_seen_at="2026-06-18T12:00:00+00:00",
        last_seen_at="2026-06-18T13:00:00+00:00",
        source_count=2,
        highest_score=74,
        latest_score=74,
        latest_tier="WATCHLIST",
        latest_event_name="SOL proxy attention",
        latest_source="fixture",
        latest_playbook_type=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        latest_playbook_score=74,
        latest_playbook_action="watchlist",
        should_alert=True,
    )
    with tempfile.TemporaryDirectory() as tmp:
        cfg = event_feedback.EventFeedbackConfig(path=Path(tmp) / "feedback.jsonl")
        marked = event_feedback.mark_feedback(
            "SOL",
            "useful",
            watchlist_entries=[entry],
            cfg=cfg,
            marked_by="tester",
            notes="good lead",
            now=datetime(2026, 6, 18, 14, 0, tzinfo=timezone.utc),
        )
        assert marked.label == event_feedback.EventFeedbackLabel.USEFUL.value
        assert marked.key == entry.key
        assert marked.state == event_watchlist.EventWatchlistState.WATCHLIST.value
        assert "No live signal" in event_feedback.format_feedback_record(marked, path=cfg.path)
        by_alert_id = event_feedback.mark_feedback(
            f"ea:{entry.key}",
            "watch",
            watchlist_entries=[entry],
            cfg=cfg,
            marked_by="tester",
        )
        assert by_alert_id.key == entry.key

        try:
            event_feedback.mark_feedback("UNKNOWN", "junk", watchlist_entries=[entry], cfg=cfg)
        except ValueError as exc:
            assert "label=missed" in str(exc)
        else:
            raise AssertionError("expected unmatched non-missed feedback to fail")

        missed = event_feedback.mark_feedback(
            "missed velvet article",
            "missed",
            watchlist_entries=[entry],
            cfg=cfg,
            marked_by="tester",
        )
        assert missed.key is None
        assert missed.label == event_feedback.EventFeedbackLabel.MISSED.value
        loaded = event_feedback.load_feedback(cfg.path)
        assert loaded.rows_read == 3
        report = event_feedback.format_feedback_report(loaded)
        assert "useful=1" in report
        assert "watch=1" in report
        assert "missed=1" in report


def test_event_alpha_missed_calibration_and_research_card_reports():
    import crypto_rsi_scanner.event_alpha.outcomes.calibration as event_alpha_calibration
    import crypto_rsi_scanner.event_alpha.radar.missed as event_alpha_missed
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from pathlib import Path

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="cup|chiliz|fan_sports_event",
        cluster_id="cup|sports|2026-06-20",
        event_id="chz-event",
        coin_id="chiliz",
        symbol="CHZ",
        relationship_type="proxy_attention",
        external_asset="World Cup",
        event_time="2026-06-20T18:00:00+00:00",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state="WATCHLIST",
        first_seen_at="2026-06-18T10:00:00+00:00",
        last_seen_at="2026-06-18T12:00:00+00:00",
        source_count=3,
        highest_score=86,
        latest_score=86,
        latest_tier="HIGH_PRIORITY_WATCH",
        latest_event_name="CHZ World Cup fan token surge",
        latest_source="fixture",
        latest_playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
        latest_rule_playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
        latest_effective_playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
        latest_playbook_score=86,
        latest_playbook_action="high_priority_watch",
        latest_llm_asset_role="proxy_instrument",
        latest_llm_confidence=0.88,
        latest_score_components={"cluster_confidence": 78, "derivatives_crowding": 20},
        latest_market_snapshot={"price": 0.21, "return_24h": 0.18},
        alert_history=[{"observed_at": "2026-06-18T12:00:00+00:00", "state": "HIGH_PRIORITY", "tier": "HIGH_PRIORITY_WATCH", "score": 86}],
        should_alert=True,
    )
    alerts = [{
        "alert_key": entry.key,
        "asset_symbol": "CHZ",
        "asset_coin_id": "chiliz",
        "event_name": entry.latest_event_name,
        "tier": "HIGH_PRIORITY_WATCH",
        "playbook_type": entry.latest_playbook_type,
        "source": "fixture",
        "feedback_label": "useful",
        "primary_horizon_return": 0.12,
        "mfe_mae_ratio": 1.8,
        "direction_hit": True,
        "volatility_hit": True,
        "llm_asset_role": "proxy_instrument",
        "score_components": {"cluster_confidence": 78},
    }]
    missed = event_alpha_missed.detect_missed_opportunities(
        [
            {
                "id": "new-pump",
                "symbol": "pump",
                "name": "New Pump",
                "current_price": 2.0,
                "price_change_percentage_24h_in_currency": 150,
                "total_volume": 10000000,
                "market_cap": 20000000,
            },
            {
                "id": "chiliz",
                "symbol": "chz",
                "name": "Chiliz",
                "current_price": 0.21,
                "price_change_percentage_24h_in_currency": 150,
            },
        ],
        alert_rows=alerts,
        watchlist_entries=[entry],
    )
    assert [row.symbol for row in missed.rows] == ["PUMP"]
    assert missed.rows[0].failure_stage == "no_source_event"
    assert "PUMP crypto catalyst" in missed.rows[0].suggested_queries
    missed_report = event_alpha_missed.format_missed_report(missed)
    assert "missed=1" in missed_report

    url_only_raw = RawDiscoveredEvent(
        raw_id="url-only",
        provider="gdelt",
        fetched_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        published_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        source_url="https://search.example.test/?q=PUMPUSDT",
        title="Market update",
        body="No asset identity in the source text.",
        raw_json={},
        source_confidence=0.60,
        content_hash="url-only",
    )
    url_only = event_alpha_missed.detect_missed_opportunities(
        [{
            "id": "new-pump",
            "symbol": "pump",
            "name": "New Pump",
            "price_change_percentage_24h_in_currency": 150,
        }],
        raw_events=[url_only_raw],
    )
    assert url_only.rows[0].failure_stage == "no_source_event"
    assert "weak_url_only_identity_hint" in url_only.rows[0].reason

    body_raw = RawDiscoveredEvent(
        raw_id="body-identity",
        provider="gdelt",
        fetched_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        published_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        source_url="https://example.test/article",
        title="PUMPUSDT doubles before listing rumors",
        body="PUMPUSDT volume spiked after a catalyst rumor.",
        raw_json={},
        source_confidence=0.80,
        content_hash="body-identity",
    )
    body_identity = event_alpha_missed.detect_missed_opportunities(
        [{
            "id": "new-pump",
            "symbol": "pump",
            "name": "New Pump",
            "price_change_percentage_24h_in_currency": 150,
        }],
        raw_events=[body_raw],
    )
    assert body_identity.rows[0].failure_stage == "resolver_missed_asset"

    metadata_raw = RawDiscoveredEvent(
        raw_id="metadata-bitcoin",
        provider="Bitcoin World",
        fetched_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        published_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        source_url="https://example.test/market",
        title="SpaceX market opens",
        body="The article is about an external catalyst, not the asset.",
        raw_json={"publisher": "Bitcoin World"},
        source_confidence=0.70,
        content_hash="metadata-bitcoin",
    )
    metadata_only = event_alpha_missed.detect_missed_opportunities(
        [{
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "price_change_percentage_24h_in_currency": 150,
        }],
        raw_events=[metadata_raw],
    )
    assert metadata_only.rows[0].failure_stage == "no_source_event"
    assert "metadata_only_identity_hint" in metadata_only.rows[0].reason

    manual_missing_source = event_alpha_missed.build_manual_missed_opportunity(
        symbol="VELVET",
        coin_id="velvet",
        event_description="SpaceX pre-IPO proxy venue moved before catalyst",
        source_url="https://example.test/velvet-spacex",
        why_it_mattered="large move with proxy catalyst",
        approximate_time="2026-06-18T12:00:00Z",
        expected_playbook="proxy_attention",
    )
    assert manual_missing_source.failure_stage == "source_not_ingested"
    assert manual_missing_source.feedback_target.startswith("missed:velvet")
    assert "VELVET crypto catalyst" in manual_missing_source.suggested_queries

    manual_quality_blocked = event_alpha_missed.build_manual_missed_opportunity(
        symbol="MEME",
        coin_id="memecore",
        event_description="MemeCore moved but stayed local",
        source_text="MemeCore volume surged after a vague catalyst.",
        core_rows=[{
            "core_opportunity_id": "core_memecore",
            "symbol": "MEME",
            "coin_id": "memecore",
            "incident_id": "incident:meme",
            "opportunity_level": "local_only",
            "final_route_after_quality_gate": "STORE_ONLY",
        }],
    )
    assert manual_quality_blocked.failure_stage == "quality_gate_too_strict"
    assert manual_quality_blocked.linked_core_opportunity_id == "core_memecore"

    calibration = event_alpha_calibration.format_calibration_report(
        alerts,
        feedback_rows=[{"key": entry.key, "label": "useful"}],
        missed_rows=[row.__dict__ for row in [*missed.rows, manual_missing_source, manual_quality_blocked]],
    )
    assert "feedback by playbook" in calibration
    assert "missed opportunities by failure stage" in calibration
    assert "source_not_ingested=1" in calibration
    assert "quality_gate_too_strict=1" in calibration
    assert "recommendations:" in calibration

    routed = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="watchlist escalation",
    )
    cluster = event_graph.EventCluster(
        schema_version=event_graph.EVENT_GRAPH_SCHEMA_VERSION,
        cluster_id=entry.cluster_id,
        external_asset_slug="world-cup",
        event_type="sports_event",
        event_date_bucket="2026-06-20",
        external_asset="World Cup",
        event_time=pd.Timestamp("2026-06-20T18:00:00Z").to_pydatetime(),
        event_ids=("chz-event", "btc-noise"),
        raw_ids=("raw-chz", "raw-btc"),
        source_urls=("https://sports.example.test/chz", "https://bitcoinworld.example.test/noise"),
        source_count=2,
        independent_source_count=2,
        source_quality_score=80,
        event_time_consensus=90,
        accepted_asset_count=1,
        rejected_asset_count=1,
        cluster_confidence=78,
        evidence=(
            event_graph.ClusterEvidence(
                event_id="chz-event",
                raw_ids=("raw-chz",),
                source_urls=("https://sports.example.test/chz",),
                event_name="CHZ World Cup fan token surge",
                source="sports_fixture",
                first_seen_time=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
                confidence=0.90,
            ),
        ),
        asset_links=(
            event_graph.EventClusterAssetLink(
                cluster_id=entry.cluster_id,
                event_id="chz-event",
                coin_id="chiliz",
                symbol="CHZ",
                playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
                relationship_type="proxy_attention",
                asset_role="proxy_instrument",
                accepted=True,
                link_confidence=0.90,
                classifier_confidence=0.90,
                accepted_kind="proxy",
                accepted_for_playbook=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
            ),
            event_graph.EventClusterAssetLink(
                cluster_id=entry.cluster_id,
                event_id="btc-noise",
                coin_id="bitcoin",
                symbol="BTC",
                playbook_type=event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
                relationship_type="publisher_suffix_false_positive",
                asset_role="source_noise",
                accepted=False,
                link_confidence=0.20,
                classifier_confidence=0.90,
                rejected_reason="publisher/source noise",
            ),
        ),
        warnings=("single source should be reviewed",),
    )
    card = event_research_cards.render_research_card(
        "CHZ",
        watchlist_entries=[entry],
        alert_rows=alerts,
        route_decisions=[routed],
        clusters=[cluster],
    )
    assert card.found is True
    assert "CHZ Event Research Card" in card.markdown
    assert "Evidence Sources" in card.markdown
    assert "Cluster Context" in card.markdown
    assert "Accepted links by kind: proxy=CHZ/chiliz" in card.markdown
    assert "Rejected/noise links: BTC/bitcoin:publisher/source noise" in card.markdown
    assert "World Cup" in card.markdown
    assert ".env" not in card.markdown
    card_by_alert_id = event_research_cards.render_research_card(
        routed.alert_id,
        watchlist_entries=[entry],
        alert_rows=alerts,
        route_decisions=[routed],
        clusters=[cluster],
    )
    assert card_by_alert_id.found is True
    card_dir = __import__("pathlib").Path(__import__("tempfile").mkdtemp())
    stale_card = card_dir / "card_stale.md"
    stale_card.write_text("stale absolute path /Users/example/card_stale.md", encoding="utf-8")
    written_cards = event_research_cards.write_research_cards(
        card_dir,
        watchlist_entries=[entry],
        alert_rows=alerts,
        route_decisions=[routed],
        selected_tiers=("HIGH_PRIORITY_WATCH",),
    )
    assert any(routed.card_id in str(path) for path in written_cards.card_paths)
    assert not stale_card.exists()


def test_event_alpha_eval_fixture_passes():
    import crypto_rsi_scanner.event_alpha.outcomes.eval as event_alpha_eval

    path = "fixtures/event_discovery/event_alpha_golden_cases.json"
    result = event_alpha_eval.run_eval(path)
    assert result.passed == result.total
    assert result.failures == ()
    assert "PASS" in event_alpha_eval.format_eval_result(result, path)


def test_event_fade_validation_outcome_fill_from_local_prices():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    prices = event_validation.load_outcome_price_fixture(_outcome_prices_fixture_path())
    result = event_validation.fill_validation_outcomes(rows, prices)
    assert result.sample_rows == len(rows)
    assert result.triggered_rows == 1
    assert result.filled_rows == 1
    assert result.missing_history_rows == 0
    assert result.insufficient_history_rows == 0
    assert result.skipped_existing_rows == 0

    velvet = next(row for row in result.rows if row["asset_symbol"] == "TESTVELVET")
    assert round(velvet["max_favorable_excursion"], 4) == 0.3333
    assert round(velvet["max_adverse_excursion"], 4) == 0.0833
    assert round(velvet["post_event_return_24h"], 4) == -0.1111
    assert round(velvet["post_event_return_72h"], 4) == -0.2083
    assert round(velvet["post_event_return_7d"], 4) == -0.2778
    assert round(velvet["event_time_entry_price"], 4) == 8.0
    assert round(velvet["event_time_post_event_return_24h"], 4) == -0.1
    assert round(velvet["event_time_post_event_return_72h"], 4) == -0.2
    assert round(velvet["event_time_post_event_return_7d"], 4) == -0.2875

    velvet["human_label"] = "valid_proxy_fade"
    velvet["review_status"] = "reviewed"
    _stamp_review_provenance(velvet)
    queue = event_validation.build_labeling_queue(result.rows)
    assert not any(item.asset_symbol == "TESTVELVET" for item in queue.items)

    second = event_validation.fill_validation_outcomes(result.rows, prices)
    assert second.filled_rows == 0
    assert second.skipped_existing_rows == 1


def test_event_fade_outcome_price_export_from_klines_fixture():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.price_history as event_price_history
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "prices.json"
        result = event_price_history.export_outcome_price_fixture(
            rows,
            out_path,
            days=30,
            fixture_dir=_outcome_klines_fixture_dir(),
        )
        assert result.assets_requested == 1
        assert result.assets_written == 1
        assert result.price_rows_written == 5
        assert result.missing_assets == ()
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == event_price_history.PRICE_FIXTURE_SCHEMA_VERSION
        assert payload["source"].startswith("fixture:")
        assert len(payload["prices"]) == 5
        assert payload["prices"][0]["asset_coin_id"] == "testvelvet"
        assert payload["prices"][2]["high"] == 7.8

        prices = event_validation.load_outcome_price_fixture(out_path)
        filled = event_validation.fill_validation_outcomes(rows, prices)
        velvet = next(row for row in filled.rows if row["asset_symbol"] == "TESTVELVET")
        assert round(velvet["max_adverse_excursion"], 4) == 0.0833
        assert round(velvet["post_event_return_7d"], 4) == -0.2778
        assert round(velvet["event_time_post_event_return_72h"], 4) == -0.2


def test_event_fade_validation_labeling_queue_prioritizes_missing_review_work():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    queue = event_validation.build_labeling_queue(rows, limit=10)
    assert queue.total_rows == len(rows)
    assert queue.needed_rows == len(rows)
    assert queue.shown_rows == 10

    first = queue.items[0]
    assert first.asset_symbol == "TESTVELVET"
    assert first.category == "label_triggered_candidate"
    assert first.event_time_source == "explicit"
    assert first.event_time_confidence == 1.0
    assert first.suggested_label == "valid_proxy_fade or false_positive"
    assert first.missing_fields == (
        "human_label",
        "max_adverse_excursion",
        "max_favorable_excursion",
        "post_event_return_72h",
        "event_time_post_event_return_72h",
    )

    assert any(item.category == "label_proxy_candidate" for item in queue.items)
    assert any(item.category == "label_negative_control" for item in queue.items)

    report = event_validation.format_labeling_queue(queue)
    assert "EVENT FADE VALIDATION LABELING QUEUE" in report
    assert "needing labels/status/outcomes: 17" in report
    assert "label_triggered_candidate" in report
    assert "TESTVELVET" in report
    assert "source: explicit" in report
    assert "confidence: 100.0%" in report
    assert "valid_proxy_fade or false_positive" in report


def test_event_fade_validation_labeling_queue_flags_reviewed_trigger_outcomes():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    triggered = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    triggered["human_label"] = "valid_proxy_fade"
    triggered["review_status"] = "reviewed"
    _stamp_review_provenance(triggered)
    queue = event_validation.build_labeling_queue(rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTVELVET")
    assert item.category == "fill_trigger_outcomes"
    assert item.missing_fields == (
        "max_adverse_excursion",
        "max_favorable_excursion",
        "post_event_return_72h",
        "event_time_post_event_return_72h",
    )


def test_event_fade_review_bundle_scanner_merges_prior_reviewed_sample():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed_row = next(row for row in reviewed if row["asset_symbol"] == "TESTVELVET")
    reviewed_row["review_status"] = "reviewed"
    _stamp_review_provenance(reviewed_row)
    reviewed_row["human_label"] = "valid_proxy_fade"
    reviewed_row["human_notes"] = "Reviewed prior bundle evidence."
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        reviewed_path = Path(tmp) / "reviewed.jsonl"
        bundle_dir = Path(tmp) / "review_bundle"
        event_discovery.write_validation_sample(rows, sample_path)
        event_discovery.write_validation_sample(reviewed, reviewed_path)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_review_bundle(
                str(sample_path),
                str(bundle_dir),
                limit=1,
                prices_path=str(_outcome_prices_fixture_path()),
                reviewed_path=str(reviewed_path),
                event_now="2026-06-15T16:00:00Z",
            )
        text = out.getvalue()
        assert "Review merge: 1 matched row(s)" in text
        assert "0 evidence-changed row(s)" in text
        assert "needing_review=16" in text

        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["review_merge"]["enabled"] is True
        assert manifest["review_merge"]["reviewed_path"] == str(reviewed_path)
        assert manifest["review_merge"]["matched_rows"] == 1
        assert manifest["review_merge"]["copied_fields"] == 5
        assert manifest["queue"]["needed_rows"] == 16

        readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
        assert "Prior reviewed sample" in readme

        copied_rows = [
            json.loads(line)
            for line in (bundle_dir / "validation_sample.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        copied_velvet = next(row for row in copied_rows if row["asset_symbol"] == "TESTVELVET")
        assert copied_velvet["reviewed_by"] == "human"
        assert copied_velvet["reviewed_at"] == "2026-06-17T12:00:00+00:00"
        assert copied_velvet["human_label"] == "valid_proxy_fade"
        assert copied_velvet["human_notes"] == "Reviewed prior bundle evidence."

        filled_rows = [
            json.loads(line)
            for line in (bundle_dir / "validation_sample_with_outcomes.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
        ]
        filled_velvet = next(row for row in filled_rows if row["asset_symbol"] == "TESTVELVET")
        assert filled_velvet["human_label"] == "valid_proxy_fade"
        assert round(filled_velvet["post_event_return_72h"], 4) == -0.2083


def test_event_fade_fill_outcomes_scanner_writes_outcome_jsonl():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        out_path = Path(tmp) / "with_outcomes.jsonl"
        event_discovery.write_validation_sample(rows, sample_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_fill_outcomes(
                str(sample_path),
                str(_outcome_prices_fixture_path()),
                str(out_path),
            )
        text = out.getvalue()
        assert "Event-fade validation outcome fill" in text
        assert "1/1 triggered row(s) filled" in text

        written = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
        velvet = next(row for row in written if row["asset_symbol"] == "TESTVELVET")
        assert round(velvet["post_event_return_72h"], 4) == -0.2083
        assert round(velvet["max_favorable_excursion"], 4) == 0.3333


def test_event_fade_export_outcome_prices_scanner_writes_price_fixture():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        out_path = Path(tmp) / "prices.json"
        event_discovery.write_validation_sample(rows, sample_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_export_outcome_prices(
                str(sample_path),
                str(out_path),
                days=30,
                fixture_dir=str(_outcome_klines_fixture_dir()),
            )
        text = out.getvalue()
        assert "Event-fade outcome price export" in text
        assert "assets=1/1" in text
        assert "price_rows=5" in text
        assert "interval=1d" in text
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["interval"] == "1d"
        assert payload["source"].endswith(":1d")
        assert payload["prices"][0]["asset_symbol"] == "TESTVELVET"
        assert payload["prices"][0]["interval"] == "1d"


def test_event_fade_outcome_price_export_supports_1h_fixture_and_metadata():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.price_history as event_price_history
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fixture_dir = root / "klines"
        fixture_dir.mkdir()
        (fixture_dir / "TESTVELVETUSDT.csv").write_text(
            "\n".join([
                "date,high,low,close,volume,quote_volume",
                "2026-06-15 13:30:00+00:00,8.2,7.9,8.0,1000,8000",
                "2026-06-16 12:00:00+00:00,7.3,7.1,7.2,1000,7200",
                "2026-06-16 13:00:00+00:00,7.5,6.6,6.8,1200,8160",
                "2026-06-17 12:00:00+00:00,6.9,5.9,6.2,1200,7440",
                "2026-06-19 12:00:00+00:00,6.4,5.5,5.8,1100,6380",
                "2026-06-23 12:00:00+00:00,6.0,4.9,5.1,900,4590",
            ]) + "\n",
            encoding="utf-8",
        )
        prices_path = root / "prices-1h.json"
        result = event_price_history.export_outcome_price_fixture(
            rows,
            prices_path,
            days=30,
            fixture_dir=root,
            interval="1h",
            now=None,
        )
        assert result.interval == "1h"
        assert result.source.endswith(":1h")
        assert result.price_rows_written == 6

        payload = json.loads(prices_path.read_text(encoding="utf-8"))
        assert payload["interval"] == "1h"
        assert payload["prices"][0]["interval"] == "1h"

        filled = event_validation.fill_validation_outcomes(
            rows,
            event_validation.load_outcome_price_fixture(prices_path),
        )
        velvet = next(row for row in filled.rows if row["asset_symbol"] == "TESTVELVET")
        assert velvet["outcome_price_interval"] == "1h"
        assert velvet["outcome_price_source"].endswith(":1h")
        assert round(velvet["max_adverse_excursion"], 4) == 0.0417
        assert round(velvet["max_favorable_excursion"], 4) == 0.3194
        assert round(velvet["post_event_return_72h"], 4) == -0.1944

        packet = event_validation.format_review_packet([velvet], limit=1)
        assert "prices=`1h/fixture:" in packet


def test_event_alpha_missed_uses_shared_identity_for_common_words():
    from datetime import datetime, timezone

    import crypto_rsi_scanner.event_alpha.radar.missed as event_alpha_missed
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    raw = RawDiscoveredEvent(
        raw_id="raw-hype",
        provider="news",
        fetched_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        source_url="https://example.com/ipo-hype",
        title="IPO hype keeps building before the event",
        body="No token mention appears here.",
        raw_json={},
        source_confidence=0.7,
        content_hash="h",
    )
    market = [{"id": "hyperliquid", "symbol": "hype", "name": "Hyperliquid", "price_change_percentage_24h_in_currency": 180}]
    result = event_alpha_missed.detect_missed_opportunities(market, raw_events=[raw])
    assert result.rows
    assert result.rows[0].failure_stage == "no_source_event"


def test_event_alpha_calibration_priors_export():
    import tempfile
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.outcomes.calibration as event_alpha_calibration

    alerts = [
        {"alert_key": "a", "playbook_type": "proxy_attention", "source": "rss", "tier": "WATCHLIST", "primary_horizon_return": 0.1},
        {"alert_key": "b", "playbook_type": "proxy_attention", "source": "rss", "tier": "WATCHLIST", "primary_horizon_return": 0.2},
    ]
    feedback = [{"key": "a", "label": "useful"}, {"key": "b", "label": "useful"}]
    out = Path(tempfile.mkdtemp()) / "priors.json"
    payload = event_alpha_calibration.write_calibration_priors(out, alerts, feedback_rows=feedback, min_sample=3)
    assert out.exists()
    assert payload["playbook_priors"]["proxy_attention"]["score_adjustment"] == 3
    assert payload["playbook_priors"]["proxy_attention"]["min_sample_warning"] is True


def test_event_alpha_eval_export_from_feedback_and_missed():
    import json
    import tempfile
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_eval_export

    out_dir = Path(tempfile.mkdtemp())
    feedback_result = event_alpha_eval_export.export_cases_from_feedback(
        [{"alert_key": "k1", "event_name": "Bitcoin World article", "asset_symbol": "BTC", "asset_coin_id": "bitcoin"}],
        [{"key": "k1", "label": "junk", "notes": "publisher noise"}],
        out_dir,
    )
    assert feedback_result.proposed_cases == 1
    llm_cases = json.loads((out_dir / "proposed_llm_golden_cases.json").read_text())
    assert llm_cases["cases"][0]["expected_asset_role"] == "source_noise"

    missed_result = event_alpha_eval_export.export_cases_from_missed(
        [{"symbol": "XYZ", "coin_id": "xyz", "name": "XYZ", "move_window": "24h", "return_pct": 1.5, "failure_stage": "resolver_missed_asset", "suggested_queries": ["XYZ catalyst"]}],
        out_dir,
    )
    assert missed_result.proposed_cases == 2
    extraction = json.loads((out_dir / "proposed_llm_extraction_golden_cases.json").read_text())
    assert extraction["cases"][0]["expected_crypto_asset_mentions"][0]["symbol"] == "XYZ"


def test_event_alpha_priors_adjust_research_score_but_not_triggered_fade():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.outcomes.priors as event_alpha_priors

    alerts = event_alerts.build_event_alert_candidates(
        _full_event_discovery_fixture_result(),
        cfg=event_alerts.EventAlertConfig(),
    )
    triggered = next(alert for alert in alerts if alert.tier == event_alerts.EventAlertTier.TRIGGERED_FADE)
    non_triggered = next(alert for alert in alerts if alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE)
    path = Path(tempfile.mkdtemp()) / "priors.json"
    path.write_text(json.dumps({
        "schema_version": "event_alpha_priors_v1",
        "generated_at": "2026-06-18T00:00:00+00:00",
        "playbook_priors": {
            triggered.effective_playbook_type: {"multiplier": 0.2},
            non_triggered.effective_playbook_type: {"multiplier": 1.3},
        },
    }), encoding="utf-8")
    adjusted = event_alpha_priors.apply_priors_to_alerts(
        [triggered, non_triggered],
        cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=True, path=path, min_multiplier=0.7, max_multiplier=1.3),
        alert_cfg=event_alerts.EventAlertConfig(),
    )
    adjusted_triggered = next(alert for alert in adjusted if alert.symbol == triggered.symbol)
    adjusted_other = next(alert for alert in adjusted if alert.symbol == non_triggered.symbol)
    assert adjusted_triggered.tier == event_alerts.EventAlertTier.TRIGGERED_FADE
    assert adjusted_triggered.score_after_priors >= int(triggered.opportunity_score * 0.69)
    assert adjusted_other.score_before_priors == non_triggered.opportunity_score
    assert adjusted_other.score_after_priors >= adjusted_other.score_before_priors
    assert adjusted_other.prior_file == str(path)


def test_event_alpha_priors_shadow_report_and_raw_replay_are_local():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.outcomes.priors as event_alpha_priors
    import crypto_rsi_scanner.event_alpha.artifacts.replay as event_alpha_replay
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    result = _full_event_discovery_fixture_result()
    alerts = event_alerts.build_event_alert_candidates(result)
    non_triggered = next(alert for alert in alerts if alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE)
    tmp = Path(tempfile.mkdtemp())
    priors_path = tmp / "priors.json"
    priors_path.write_text(json.dumps({
        "schema_version": "event_alpha_priors_v1",
        "generated_at": "2026-06-18T00:00:00+00:00",
        "playbook_priors": {non_triggered.effective_playbook_type: {"multiplier": 1.2}},
    }), encoding="utf-8")
    shadow = event_alpha_priors.compare_priors_shadow(
        alerts,
        cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=False, path=priors_path),
        alert_cfg=event_alerts.EventAlertConfig(),
    )
    assert shadow.rows
    text = event_alpha_priors.format_priors_shadow_report(shadow)
    assert "EVENT ALPHA PRIORS SHADOW REPORT" in text
    assert "No sends" in text

    _events_path, aliases_path = _event_discovery_fixture_paths()
    market_rows = event_alpha_replay.load_market_rows(_coingecko_universe_fixture_path())
    assets = event_discovery.load_discovery_assets(aliases_path, universe_path=_coingecko_universe_fixture_path())
    replay = event_alpha_replay.replay_from_raw_events(
        raw_events=result.raw_events,
        assets=assets,
        market_rows=market_rows,
        priors_cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=True, path=priors_path),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert replay.raw_events == len(result.raw_events)
    assert replay.candidates > 0
    replay_text = event_alpha_replay.format_replay_report(replay)
    assert "local artifacts only" in replay_text
    assert "No live providers" in replay_text
    comparison = event_alpha_replay.compare_replay_policies(
        raw_events=result.raw_events,
        assets=assets,
        market_rows=market_rows,
        policies=("baseline", "priors", "router_threshold_variant", "profile_variant"),
        priors_cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=True, path=priors_path),
        router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True, score_jump_threshold=20),
        profile_variant_router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True, score_jump_threshold=5),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert [row.policy for row in comparison.rows] == [
        "baseline",
        "priors",
        "router_threshold_variant",
        "profile_variant",
    ]
    assert comparison.diffs
    assert any(diff.policy == "priors" and diff.score_delta for diff in comparison.diffs)
    comparison_text = event_alpha_replay.format_replay_comparison_report(comparison)
    assert "EVENT ALPHA REPLAY POLICY COMPARISON" in comparison_text
    assert "candidate diffs:" in comparison_text
    assert "local-only" in comparison_text
    assert "router_threshold_variant" in comparison_text


def test_event_alpha_daily_brief_replay_retention_and_unmatched_feedback():
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.artifacts.replay as event_alpha_replay
    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_labels as event_feedback

    entry = _test_watchlist_entry(state="HIGH_PRIORITY", symbol="VELVET", coin_id="velvet")
    markdown = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{
            "run_id": "run-1",
            "run_mode": "burn_in",
            "artifact_namespace": "no_key_live",
            "success": True,
            "raw_events": 2,
            "candidates": 1,
            "alerts": 1,
            "routed": 1,
            "alertable": 0,
            "llm_calls_attempted": 0,
            "llm_skipped_due_budget": 1,
        }],
        alert_rows=[{"run_mode": "burn_in", "artifact_namespace": "no_key_live", "run_id": "run-1", "alert_key": entry.key, "tier": "HIGH_PRIORITY_WATCH", "asset_symbol": "VELVET", "playbook_type": "proxy_attention"}],
        watchlist_entries=[entry],
        provider_health_rows={"gdelt": {"provider_kind": "event_source", "consecutive_failures": 2, "disabled_until": "2026-06-18T10:30:00+00:00"}},
        card_paths=[Path("/tmp/velvet.md")],
    )
    assert "Event Alpha Daily Brief" in markdown
    assert "Why No Alerts" in markdown
    assert "Provider Health" in markdown
    assert "LLM Budget" in markdown
    assert "Watchlist Got Hotter" in markdown
    assert "Calibration Recommendations" in markdown
    assert ".env" not in markdown

    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor
    entry_fade = __import__("dataclasses").replace(
        entry,
        latest_playbook_type="proxy_fade",
        latest_effective_playbook_type="proxy_fade",
    )
    monitor_row = event_watchlist_monitor.EventWatchlistMonitorRow(
        key=entry_fade.key,
        symbol="VELVET",
        coin_id="velvet",
        state="HIGH_PRIORITY",
        event_name="SpaceX pre-IPO exposure",
        event_time="2026-06-16T00:00:00+00:00",
        event_countdown_hours=None,
        event_age_hours=12.0,
        current_price=1.23,
        return_24h=0.24,
        return_72h=0.72,
        return_7d=1.4,
        volume_to_market_cap=0.4,
        volume_zscore_24h=4.5,
        derivatives_crowding=68,
        supply_pressure=20,
        cluster_confidence=80,
        state_transition_hints=("MARKET_SCORE_JUMP", "DERIVATIVES_HEATED"),
        material_update=True,
    )
    card = event_research_cards.render_research_card(
        entry_fade.key,
        watchlist_entries=[entry_fade],
        alert_rows=[{
            "alert_key": entry_fade.key,
            "asset_symbol": "VELVET",
            "asset_coin_id": "velvet",
            "event_name": "SpaceX pre-IPO exposure",
            "playbook_type": "proxy_fade",
            "expected_direction": "down",
            "primary_horizon": "24h",
            "playbook_invalidation": "Price reclaims event VWAP",
            "score_components": {"external_catalyst": 90, "event_time_quality": 90, "market_move_volume": 80},
        }],
        monitor_rows=[monitor_row],
    )
    assert "## Research Review Checklist" in card.markdown
    assert "## Latest Monitor Update" in card.markdown
    assert "MARKET_SCORE_JUMP" in card.markdown
    assert "DERIVATIVES_HEATED" in card.markdown
    assert "cannot create TRIGGERED_FADE" in card.markdown
    assert "post-event failure" in card.markdown

    replay = event_alpha_replay.replay_from_artifacts(
        alert_rows=[{"alert_key": "a1", "tier": "WATCHLIST", "route": "RESEARCH_DIGEST", "opportunity_score": 50}],
        watchlist_rows=[{"key": entry.key}],
        priors_enabled=True,
        llm_advisory=True,
    )
    assert replay.alert_rows == 1
    assert "local artifacts only" in event_alpha_replay.format_replay_report(replay)

    tmp = Path(tempfile.mkdtemp())
    feedback_cfg = event_feedback.EventFeedbackConfig(path=tmp / "feedback.jsonl")
    record = event_feedback.mark_feedback(
        "UNKNOWN",
        "junk",
        watchlist_entries=[],
        cfg=feedback_cfg,
        allow_unmatched=True,
        notes="bad key",
    )
    assert record.source == "manual_cli_unmatched"
    assert "warning:" in (record.notes or "")

    runs = tmp / "runs.jsonl"
    alerts = tmp / "alerts.jsonl"
    cards = tmp / "cards"
    cards.mkdir()
    runs.write_text('{"row_type":"event_alpha_run","started_at":"2025-01-01T00:00:00+00:00"}\n', encoding="utf-8")
    alerts.write_text('{"row_type":"event_alpha_alert_snapshot","observed_at":"2025-01-01T00:00:00+00:00"}\n', encoding="utf-8")
    old_card = cards / "old.md"
    old_card.write_text("# old\n", encoding="utf-8")
    cfg = event_alpha_retention.EventAlphaRetentionConfig(
        runs_path=runs,
        alerts_path=alerts,
        cards_dir=cards,
        run_days=1,
        alert_days=1,
        card_days=1,
    )
    dry = event_alpha_retention.prune_event_alpha_artifacts(cfg, confirm=False, now=__import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc))
    assert dry.dry_run is True
    assert dry.runs_pruned == 1
    assert runs.read_text(encoding="utf-8").strip()
    confirmed = event_alpha_retention.prune_event_alpha_artifacts(cfg, confirm=True, now=__import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc))
    assert confirmed.dry_run is False
    assert runs.read_text(encoding="utf-8") == ""


def test_event_alpha_burn_in_scorecard_summarizes_operational_health():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.outcomes.burn_in as event_alpha_burn_in
    import crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist as event_alpha_burn_in_checklist

    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    meta = {"profile": "no_key_live", "run_mode": "burn_in", "artifact_namespace": "no_key_live"}
    scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[
            {
                **meta,
                "run_id": "run-1",
                "started_at": "2026-06-19T10:00:00+00:00",
                "success": True,
                "raw_events": 5,
                "candidates": 3,
                "alertable": 1,
            },
            {
                **meta,
                "run_id": "run-2",
                "started_at": "2026-06-18T10:00:00+00:00",
                "success": False,
                "raw_events": 0,
                "candidates": 0,
                "alertable": 0,
            },
        ],
        alert_rows=[
            {
                **meta,
                "run_id": "run-1",
                "observed_at": "2026-06-19T10:01:00+00:00",
                "alert_key": "cluster|velvet|proxy_attention",
                "tier": "WATCHLIST",
                "playbook_type": "proxy_attention",
                "source": "gdelt",
            },
            {
                **meta,
                "run_id": "run-1",
                "observed_at": "2026-06-19T10:02:00+00:00",
                "alert_key": "cluster|btc|source_noise_control",
                "tier": "STORE_ONLY",
                "playbook_type": "source_noise_control",
                "source": "rss",
            },
        ],
        feedback_rows=[
            {
                **meta,
                "marked_at": "2026-06-19T11:00:00+00:00",
                "key": "cluster|btc|source_noise_control",
                "label": "junk",
            },
            {
                **meta,
                "marked_at": "2026-06-19T11:05:00+00:00",
                "key": "cluster|velvet|proxy_attention",
                "label": "useful",
            },
        ],
        outcome_rows=[
            {
                **meta,
                "observed_at": "2026-06-19T12:00:00+00:00",
                "alert_key": "cluster|velvet|proxy_attention",
                "primary_horizon_return": 0.18,
            }
        ],
        missed_rows=[
            {
                **meta,
                "observed_at": "2026-06-19T11:30:00+00:00",
                "failure_stage": "resolver_missed_asset",
            }
        ],
        provider_health_rows={
            "gdelt:event_source": {
                "provider_key": "gdelt:event_source",
                "consecutive_failures": 2,
                "disabled_until": "2026-06-19T12:30:00+00:00",
            }
        },
        llm_budget_rows=[
            {
                **meta,
                "date": "2026-06-19",
                "extractor_calls_attempted": 2,
                "relationship_calls_attempted": 1,
                "cache_hits": 4,
                "cache_misses": 3,
                "skipped_due_budget": 1,
                "estimated_cost_usd": 0.12,
            }
        ],
    )
    text = event_alpha_burn_in.format_burn_in_scorecard(scorecard)
    assert "EVENT ALPHA BURN-IN SCORECARD" in text
    assert "runs=2 successful=1 failed=1" in text
    assert "WATCHLIST=1" in text
    assert "resolver_missed_asset=1" in text
    assert "gdelt:event_source(2)" in text
    assert "calls=3" in text
    assert "artifact coverage:" in text
    assert "alert_snapshots=2" in text
    assert "inspect degraded provider health" in text
    assert "No thresholds, alert tiers, paper trades, live DB rows, or execution were changed." in text
    checklist = event_alpha_burn_in_checklist.build_burn_in_checklist(
        scorecard,
        card_paths=("card.md",),
    )
    assert checklist.ready_for_research_send is False
    assert any("backoff" in item for item in checklist.blockers)
    checklist_text = event_alpha_burn_in_checklist.format_burn_in_checklist(checklist)
    assert "READY_FOR_RESEARCH_SEND: no" in checklist_text

    ready_scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{**meta, "run_id": "ready-run", "started_at": "2026-06-19T10:00:00+00:00", "success": True, "alertable": 1}],
        alert_rows=[{**meta, "run_id": "ready-run", "observed_at": "2026-06-19T10:01:00+00:00", "alert_key": "a", "tier": "WATCHLIST"}],
        feedback_rows=[{**meta, "marked_at": "2026-06-19T11:00:00+00:00", "key": "a", "label": "useful"}],
        outcome_rows=[{**meta, "observed_at": "2026-06-19T12:00:00+00:00", "alert_key": "a", "primary_horizon_return": 0.1}],
        missed_rows=[{**meta, "observed_at": "2026-06-19T12:00:00+00:00", "failure_stage": "unknown"}],
        provider_health_rows={"gdelt:event_source": {"provider_key": "gdelt:event_source", "consecutive_failures": 0}},
    )
    assert event_alpha_burn_in_checklist.build_burn_in_checklist(ready_scorecard).ready_for_research_send is True

    missing_snapshots = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{**meta, "run_id": "missing-run", "started_at": "2026-06-19T10:00:00+00:00", "success": True, "alertable": 1}],
        alert_rows=[],
        missed_rows=[],
        profile="no_key_live",
    )
    assert "alert snapshots missing for alertable runs" in missing_snapshots.coverage_warnings
    assert "provider health missing for live profiles" in missing_snapshots.coverage_warnings
    blocked = event_alpha_burn_in_checklist.build_burn_in_checklist(missing_snapshots)
    assert blocked.ready_for_research_send is False
    assert any("alertable runs" in item for item in blocked.blockers)

    legacy_only = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{"run_id": "legacy", "started_at": "2026-06-19T10:00:00+00:00", "success": True}],
        alert_rows=[{"run_id": "legacy", "observed_at": "2026-06-19T10:01:00+00:00", "alert_key": "legacy-a"}],
    )
    assert legacy_only.run_rows == []
    assert legacy_only.legacy_rows_skipped == 2
    assert "no operational burn-in rows found" in legacy_only.coverage_warnings
    legacy_counted = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{"run_id": "legacy", "started_at": "2026-06-19T10:00:00+00:00", "success": True}],
        include_api_artifacts=True,
    )
    assert len(legacy_counted.run_rows) == 1


def test_event_alpha_burn_in_readiness_requires_no_send_and_reviewable_artifacts():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.outcomes.burn_in as event_alpha_burn_in_readiness
    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_feedback_readiness
    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status

    with TemporaryDirectory() as tmp:
        brief = Path(tmp) / "event_alpha_daily_brief.md"
        brief.write_text("## Market Freshness Readiness\n- fresh\n", encoding="utf-8")
        provider_report = event_provider_status.EventDiscoveryProviderStatus(
            mode="research_only",
            cache_dir="event_fade_cache/live_burn_in_no_send",
            lookback_hours=72,
            horizon_days=14,
            sources=(event_provider_status.ProviderStatus("gdelt_news", "event_source", True),),
            enrichment=(event_provider_status.ProviderStatus("coingecko_universe", "enrichment", True),),
            warnings=(),
            next_steps=(),
        )
        doctor = event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult(
            status="OK",
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            run_rows=1,
            alert_rows=1,
            feedback_rows=0,
            outcome_rows=0,
            card_files=1,
        )
        feedback = event_alpha_feedback_readiness.EventAlphaFeedbackReadinessResult(
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            cards_checked=1,
            cards_with_lineage=1,
            cards_with_feedback_target=1,
            core_opportunity_cards_ready=1,
            near_miss_cards_ready=0,
            local_only_cards_ready=0,
            alert_rows_checked=1,
            alert_rows_with_feedback_targets=1,
            inbox_review_items=1,
            feedback_rows=0,
            calibration_ready_rows=1,
            visible_core_opportunities=1,
            visible_core_opportunities_with_cards=1,
            visible_core_opportunities_with_feedback_targets=1,
        )
        run = {
            "run_id": "run-live-burn",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "live_burn_in_no_send",
            "success": True,
            "send_requested": False,
            "sent": False,
            "send_items_delivered": 0,
            "raw_events": 4,
            "candidates": 2,
            "evidence_acquisition_attempted": 1,
        }
        result = event_alpha_burn_in_readiness.build_burn_in_readiness(
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            run_rows=[run],
            provider_status=provider_report,
            artifact_doctor=doctor,
            feedback_readiness=feedback,
            core_opportunity_rows=[{"core_opportunity_id": "core:velvet"}],
            evidence_acquisition_rows=[{"accepted_evidence_count": 1}],
            daily_brief_path=brief,
        )
        text = event_alpha_burn_in_readiness.format_burn_in_readiness(result)

        assert result.ready is True
        assert result.no_send_confirmed is True
        assert result.market_freshness_visible is True
        assert "READY_FOR_NO_SEND_BURN_IN_REVIEW: yes" in text
        assert "provider_coverage:" in text
        assert "manual review checklist:" in text

        stale_inbox_feedback = event_alpha_feedback_readiness.EventAlphaFeedbackReadinessResult(
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            cards_checked=1,
            cards_with_lineage=1,
            cards_with_feedback_target=1,
            core_opportunity_cards_ready=1,
            near_miss_cards_ready=0,
            local_only_cards_ready=0,
            alert_rows_checked=1,
            alert_rows_with_feedback_targets=1,
            inbox_review_items=1,
            feedback_rows=0,
            calibration_ready_rows=1,
            visible_core_opportunities=1,
            visible_core_opportunities_with_cards=1,
            visible_core_opportunities_with_feedback_targets=1,
            visible_core_opportunities_missing_cards=0,
            visible_core_opportunities_missing_feedback_targets=0,
            canonical_review_items=1,
            canonical_review_items_with_cards=0,
            canonical_review_items_with_feedback_targets=1,
            blockers=("canonical_review_items_missing_cards",),
        )
        stale_inbox_result = event_alpha_burn_in_readiness.build_burn_in_readiness(
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            run_rows=[run],
            provider_status=provider_report,
            artifact_doctor=doctor,
            feedback_readiness=stale_inbox_feedback,
            core_opportunity_rows=[{"core_opportunity_id": "core:velvet"}],
            evidence_acquisition_rows=[{"accepted_evidence_count": 1}],
            daily_brief_path=brief,
        )
        assert stale_inbox_result.feedback_readiness_ready is True
        assert "feedback readiness has blockers" not in "\n".join(stale_inbox_result.blockers)


def test_makefile_has_event_alpha_burn_in_and_priors_targets():
    text = __import__("pathlib").Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-priors-shadow-report:" in text
    assert "event-alpha-burn-in-no-key:" in text
    assert "event-alpha-source-coverage-report:" in text
    assert "event-alpha-burn-in-llm:" in text
    assert "event-alpha-burn-in-scorecard:" in text
    assert "event-alpha-burn-in-checklist:" in text
    assert "event-alpha-live-burn-in-no-send:" in text
    assert "event-alpha-burn-in-readiness:" in text
    assert "event-alpha-v1-readiness:" in text
    assert "event-alpha-health-guard:" in text
    assert "event-alpha-artifact-doctor:" in text
    assert "event-alpha-preflight:" in text
    assert "event-alpha-notify-cycle:" in text
    assert "event-alpha-notify-no-key:" in text
    assert "event-alpha-notify-llm:" in text
    assert "event-alpha-notify-preview:" in text
    assert "event-alpha-notify-go-no-go:" in text
    assert "event-alpha-provider-health-report:" in text
    assert "event-alpha-provider-health-reset:" in text
    assert "event-alpha-day1-start:" in text
    assert "event-alpha-send-test:" in text
    assert "event-alpha-tuning-worksheet:" in text
    assert "event-alpha-export-burn-in-pack:" in text
    assert "event-alpha-launchd-template:" in text
    assert "event-alpha-weekly-review:" in text
    assert "--event-alpha-priors-shadow-report" in text
    assert "--event-alpha-v1-readiness" in text
    assert "--event-alpha-health-guard" in text
    assert "--event-alpha-artifact-doctor" in text
    assert "--event-alpha-preflight" in text
    assert "--event-alpha-notify-cycle --event-alpha-profile $(PROFILE) --event-alert-send" in text
    assert "--event-alpha-notify-preview --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-notify-go-no-go --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-notification-checklist --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-notification-runs-report" in text
    assert "--event-alpha-send-test --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-tuning-worksheet" in text
    assert "--event-alpha-export-burn-in-pack" in text
    assert __import__("pathlib").Path("research/event_alpha_launchd_template.plist").exists()
    assert __import__("pathlib").Path("research/event_alpha_cron_example.txt").exists()
    burn_in = text.split("event-alpha-burn-in-no-key:", 1)[1].split("event-alpha-burn-in-llm:", 1)[0]
    assert "--event-alert-send" not in burn_in
    assert "--event-alpha-profile no_key_live" in burn_in
    live_burn_in = text.split("event-alpha-live-burn-in-no-send:", 1)[1].split("event-alpha-burn-in-readiness:", 1)[0]
    assert "--event-alpha-cycle" in live_burn_in
    assert "--event-alpha-burn-in-readiness" in live_burn_in
    assert "--event-alert-send" not in live_burn_in
    assert "EVENT_ALPHA_PROFILE_DIR" in text
    llm_burn_in = text.split("event-alpha-burn-in-llm:", 1)[1].split("event-alpha-weekly-review:", 1)[0]
    assert "--event-alpha-profile full_llm_live" in llm_burn_in

    import subprocess
    dry = subprocess.run(
        ["make", "-n", "event-alpha-daily-llm-report", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-profile full_llm_live" in dry
    assert "event_fade_cache/full_llm_live/event_alpha_runs.jsonl" in dry
    assert "event_fade_cache/no_key_live/event_alpha_runs.jsonl" not in dry

    preflight = subprocess.run(
        ["make", "-n", "event-alpha-preflight", "PROFILE=no_key_live", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-preflight --event-alpha-profile no_key_live" in preflight

    checklist = subprocess.run(
        ["make", "-n", "event-alpha-notification-checklist", "PROFILE=notify_no_key", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-notification-checklist --event-alpha-profile notify_no_key" in checklist


def test_event_alpha_signal_quality_fixture_passes_and_reports_stage_failure():
    import json
    import tempfile
    import crypto_rsi_scanner.event_alpha.outcomes.quality as quality

    result = quality.evaluate_signal_quality_cases()
    assert result.failed_cases == 0
    assert result.total_cases >= 13
    text = quality.format_signal_quality_eval(result)
    assert "failures_by_stage: none" in text
    assert "brief_section=" in text
    assert "diagnostic_visibility=" in text
    assert "false_positive=" in text
    assert "reason=\"" in text

    cases = list(quality.load_signal_quality_cases())
    cases[0] = {**cases[0], "expected": {**dict(cases[0]["expected"]), "route_tier": "STORE_ONLY"}}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "bad_cases.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"cases": cases[:1]}, fh)
        bad = quality.evaluate_signal_quality_cases(path)
    assert bad.failed_cases == 1
    assert "routing" in bad.case_results[0].stage_failures
    assert any("route_tier" in diff for diff in bad.case_results[0].diffs)


def test_event_near_miss_dedupes_and_excludes_promoted_or_zero_quality_rows():
    import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss

    base = {
        "incident_id": "incident:memecore",
        "validated_symbol": "M",
        "validated_coin_id": "memecore",
        "candidate_role": "direct_subject",
        "impact_path_type": "meme_attention",
        "source_class": "crypto_native",
        "evidence_specificity": "asset_and_catalyst",
        "market_confirmation_score": 48,
        "opportunity_score_final": 61,
        "opportunity_level": "local_only",
        "why_not_watchlist": ["needs_market_confirmation"],
    }
    rows = [
        {**base, "hypothesis_id": "hyp:m:1"},
        {**base, "hypothesis_id": "hyp:m:2", "opportunity_score_final": 62},
        {
            **base,
            "hypothesis_id": "hyp:velvet",
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "opportunity_level": "high_priority",
            "opportunity_score_final": 95,
            "market_confirmation_score": 82,
            "market_context_freshness_status": "fresh",
            "why_not_watchlist": [],
        },
        {**base, "hypothesis_id": "hyp:zero", "validated_symbol": "ZERO", "validated_coin_id": "zero", "opportunity_score_final": 0, "why_local_only": ["quality_context_missing"]},
    ]
    near = event_near_miss.detect_near_miss_rows(rows)
    assert [item.symbol for item in near] == ["M"]
    assert near[0].opportunity_score_before == 62


def test_quality_review_possible_false_positives_require_suspicion_reason():
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review

    strong = {
        "symbol": "VELVET",
        "coin_id": "velvet",
        "opportunity_level": "high_priority",
        "impact_path_type": "venue_value_capture",
        "candidate_role": "proxy_venue",
        "source_class": "crypto_native",
        "evidence_specificity": "asset_and_catalyst",
        "opportunity_score_final": 94,
    }
    noisy = {
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "opportunity_level": "local_only",
        "impact_path_type": "generic_cooccurrence_only",
        "candidate_role": "source_noise",
        "source_class": "publisher_suffix_false_positive",
        "evidence_specificity": "insufficient_data",
        "opportunity_score_final": 0,
    }
    market_dislocation = {
        "symbol": "M",
        "coin_id": "memecore",
        "opportunity_level": "exploratory",
        "impact_path_type": "market_dislocation_unknown",
        "candidate_role": "direct_subject",
        "source_class": "broad_news",
        "evidence_specificity": "direct_token_mechanism",
        "why_not_watchlist": ["cause_unknown_market_dislocation", "needs_market_confirmation"],
        "opportunity_score_final": 54,
    }
    clean_text = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(hypothesis_rows=[strong])
    )
    clean_fp = clean_text.split("Possible false positives:", 1)[1].split("Quality Gate Conflicts:", 1)[0]
    assert "- none" in clean_fp
    assert "VELVET" not in clean_fp
    mixed_text = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(hypothesis_rows=[strong, noisy, market_dislocation])
    )
    mixed_fp = mixed_text.split("Possible false positives:", 1)[1].split("Quality Gate Conflicts:", 1)[0]
    assert "BTC" in mixed_fp
    assert "VELVET" not in mixed_fp
    assert "M" not in mixed_fp

    explicit_text = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(hypothesis_rows=[
            {**strong, "symbol": "RUNE", "coin_id": "thorchain", "opportunity_level": "watchlist"},
            {"symbol": "HYPE", "coin_id": "hyperliquid", "warnings": ["invalid_subject"]},
            {"symbol": "KCS", "coin_id": "kucoin-shares", "why_local_only": "diagnostic_only"},
            {"symbol": "HYPE", "coin_id": "hyperliquid", "impact_path_type": "generic_cooccurrence_only"},
            {"symbol": "BTC", "coin_id": "bitcoin", "source_class": "publisher_suffix_false_positive"},
        ])
    )
    explicit_fp = explicit_text.split("Possible false positives:", 1)[1].split("Quality Gate Conflicts:", 1)[0]
    assert "RUNE" not in explicit_fp
    assert "HYPE" in explicit_fp
    assert "KCS" in explicit_fp
    assert "BTC" in explicit_fp


def test_event_alpha_feedback_readiness_and_core_feedback_target():
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_feedback_readiness
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_labels as event_feedback
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    entry = _test_watchlist_entry(
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        symbol="AAVE",
        coin_id="aave",
    )
    entry = __import__("dataclasses").replace(
        entry,
        incident_id="incident:aave",
        hypothesis_id="hyp:aave",
        latest_score_components={
            **entry.latest_score_components,
            "run_id": "run-aave",
            "profile": "notify_llm_quality_frame",
            "artifact_namespace": "notify_llm_quality_frame",
            "incident_id": "incident:aave",
            "hypothesis_id": "hyp:aave",
        },
    )
    card = event_research_cards.render_research_card(
        entry.key,
        watchlist_entries=[entry],
        card_path="/tmp/card_aave.md",
        lineage_context={
            "run_id": "run-aave",
            "profile": "notify_llm_quality_frame",
            "artifact_namespace": "notify_llm_quality_frame",
        },
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        card_path = tmp_path / "card_aave.md"
        card_path.write_text(card.markdown, encoding="utf-8")
        core_id = __import__(
            "crypto_rsi_scanner.event_alpha.radar.core_opportunities",
            fromlist=["core_opportunity_id_for_row"],
        ).core_opportunity_id_for_row(entry)
        alert = {
            "alert_id": "ea:aave",
            "card_id": "card_aave",
            "alert_key": entry.key,
            "symbol": "AAVE",
            "coin_id": "aave",
            "incident_id": "incident:aave",
            "core_opportunity_id": core_id,
            "feedback_target": core_id,
            "feedback_target_type": "core_opportunity_id",
            "impact_path_type": "strategic_investment_or_valuation",
            "candidate_role": "direct_subject",
            "opportunity_level": "validated_digest",
        }
        ready = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="notify_llm_quality_frame",
            artifact_namespace="notify_llm_quality_frame",
            card_paths=[card_path],
            alert_rows=[alert],
            feedback_rows=[],
            watchlist_entries=[entry],
        )
        assert ready.ready is True
        assert ready.cards_with_lineage == 1
        assert ready.cards_with_feedback_target == 1
        assert ready.core_opportunity_cards_ready == 1
        text = event_alpha_feedback_readiness.format_feedback_readiness(ready)
        assert "ready: true" in text
        assert "cards_with_feedback_target: 1/1" in text
        cfg = event_feedback.EventFeedbackConfig(path=tmp_path / "feedback.jsonl")
        record = event_feedback.mark_feedback(core_id, "useful", watchlist_entries=[entry], cfg=cfg)
        assert record.key == entry.key
        report = event_feedback.format_feedback_report(event_feedback.load_feedback(cfg.path))
        assert "useful" in report
        assert "AAVE/aave" in report
        audit = event_opportunity_audit.format_opportunity_audit(
            core_id,
            watchlist_entries=[entry],
            feedback_rows=event_feedback.load_feedback(cfg.path).records,
            card_paths=[card_path],
            profile="notify_llm_quality_frame",
        )
        assert "- feedback status: has_feedback" in audit
        assert "- feedback label: useful" in audit
        assert f"FEEDBACK_TARGET='{core_id}'" in audit

        no_alert_ready = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="catalyst_frame_e2e",
            artifact_namespace="catalyst_frame_e2e",
            card_paths=[card_path],
            alert_rows=[],
            feedback_rows=[],
            watchlist_entries=[entry],
        )
        assert no_alert_ready.ready is True
        assert "no_alert_snapshots_found" in no_alert_ready.warnings

        legacy_path = tmp_path / "legacy.md"
        legacy_path.write_text("# Card\n\n- Run ID: legacy_lineage_missing\n", encoding="utf-8")
        blocked = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="notify_llm_quality_frame",
            artifact_namespace="notify_llm_quality_frame",
            card_paths=[legacy_path],
            alert_rows=[alert],
            feedback_rows=[],
            watchlist_entries=[entry],
        )
        assert "research_cards_missing_lineage" in blocked.blockers

        missing_target_path = tmp_path / "missing_target.md"
        missing_target_path.write_text(
            "# Card\n\n"
            "## Artifact Lineage\n"
            "- Generated at: 2026-06-15T16:00:00+00:00\n"
            "- Lineage status: current\n"
            "- legacy_lineage_missing: false\n"
            "- Run ID: run-aave\n"
            "- Profile: catalyst_frame_e2e\n"
            "- Namespace: catalyst_frame_e2e\n",
            encoding="utf-8",
        )
        missing_target = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="catalyst_frame_e2e",
            artifact_namespace="catalyst_frame_e2e",
            card_paths=[missing_target_path],
            alert_rows=[],
            feedback_rows=[],
            watchlist_entries=[entry],
        )
        assert "research_cards_missing_feedback_target" in missing_target.blockers

        index_path = tmp_path / "index.md"
        index_path.write_text("# Event Research Cards\n\n", encoding="utf-8")
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-aave", "profile": "catalyst_frame_e2e", "artifact_namespace": "catalyst_frame_e2e", "run_mode": "test"}],
            card_paths=[index_path, card_path],
            profile="catalyst_frame_e2e",
            artifact_namespace="catalyst_frame_e2e",
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor.research_card_index_present is True
        assert doctor.cards_missing_lineage == 0
        assert doctor.cards_missing_feedback_target == 0
        assert doctor.status in {"OK", "WARN"}

        doctor_missing = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-aave", "profile": "catalyst_frame_e2e", "artifact_namespace": "catalyst_frame_e2e", "run_mode": "test"}],
            card_paths=[card_path],
            profile="catalyst_frame_e2e",
            artifact_namespace="catalyst_frame_e2e",
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor_missing.research_card_index_present is False
        assert "index.md" in "; ".join(doctor_missing.blockers)


def test_event_alpha_quality_review_policy_simulation_and_export():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.outcomes.policy_simulator as event_alpha_policy_simulator
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_signal_quality_export

    rows = [
        {
            "alert_key": "velvet",
            "symbol": "VELVET",
            "opportunity_level": "high_priority",
            "opportunity_score_final": 88,
            "impact_path_type": "venue_value_capture",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_venue",
            "market_confirmation_level": "strong",
            "market_confirmation_score": 75,
            "evidence_quality_score": 82,
            "source_class": "primary",
            "evidence_specificity": "direct_value_capture",
            "manual_verification_items": ["verify liquidity"],
            "validation_stage": "impact_path_validated",
            "crypto_candidate_assets": [
                {"symbol": "VELVET", "coin_id": "velvet", "accepted": True},
                {"symbol": "LINK", "coin_id": "chainlink", "source": "taxonomy", "validated": False},
            ],
            "rejected_candidate_assets": [
                {"symbol": "HYPE", "reason": "generic_symbol_word_collision"},
                {"symbol": "NAV", "source": "navigation", "mention_type": "source_navigation"},
            ],
            "row_type": "event_alpha_alert_snapshot",
            "route": "HIGH_PRIORITY_RESEARCH",
            "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
            "alertable_after_quality_gate": True,
        },
        {
            "alert_key": "btc-policy",
            "symbol": "BTC",
            "opportunity_level": "local_only",
            "opportunity_score_final": 45,
            "impact_path_type": "generic_cooccurrence_only",
            "impact_path_strength": "weak",
            "candidate_role": "generic_mention",
            "market_confirmation_level": "none",
            "market_confirmation_score": 0,
            "evidence_quality_score": 35,
            "source_class": "secondary",
            "evidence_specificity": "weak_cooccurrence",
            "why_local_only": "generic_cooccurrence_only",
            "row_type": "event_alpha_alert_snapshot",
            "route": "STORE_ONLY",
            "final_route_after_quality_gate": "STORE_ONLY",
            "alertable_after_quality_gate": False,
        },
        {
            "alert_key": "openai-velvet",
            "symbol": "VELVET",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 66,
            "impact_path_type": "venue_value_capture",
            "impact_path_strength": "medium",
            "candidate_role": "proxy_venue",
            "market_confirmation_level": "weak",
            "market_confirmation_score": 25,
            "evidence_quality_score": 70,
            "source_class": "independent",
            "evidence_specificity": "direct_value_capture",
            "row_type": "event_alpha_alert_snapshot",
            "route": "RESEARCH_DIGEST",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "alertable_after_quality_gate": True,
        },
        {
            "alert_key": "near-threshold",
            "symbol": "NEAR",
            "opportunity_level": "exploratory",
            "opportunity_score_final": 58,
            "impact_path_type": "venue_value_capture",
            "impact_path_strength": "medium",
            "candidate_role": "proxy_venue",
            "market_confirmation_level": "weak",
            "market_confirmation_score": 25,
            "evidence_quality_score": 58,
            "source_class": "independent",
            "evidence_specificity": "direct_value_capture",
            "row_type": "event_alpha_alert_snapshot",
            "route": "STORE_ONLY",
            "final_route_after_quality_gate": "STORE_ONLY",
            "alertable_after_quality_gate": False,
        },
        {
            "alert_key": "legacy-btc-conflict",
            "symbol": "BTC",
            "opportunity_level": "local_only",
            "opportunity_score_final": 0,
            "impact_path_type": "insufficient_data",
            "impact_path_strength": "none",
            "candidate_role": "unknown_with_reason",
            "market_confirmation_level": "none",
            "market_confirmation_score": 0,
            "evidence_quality_score": 0,
            "source_class": "insufficient_data",
            "evidence_specificity": "insufficient_data",
            "row_type": "event_alpha_alert_snapshot",
            "route": "RESEARCH_DIGEST",
            "route_alertable": True,
        },
    ]
    review = event_alpha_quality_review.build_quality_review(profile="fixture", alert_rows=rows)
    report = event_alpha_quality_review.format_quality_review(review)
    assert review.candidate_discovery_funnel["raw_terms_extracted"] == 4
    assert review.candidate_discovery_funnel["candidate_like_terms"] == 1
    assert review.candidate_discovery_funnel["resolver_attempted"] == 3
    assert review.candidate_discovery_funnel["resolver_accepted_candidates"] == 1
    assert review.candidate_discovery_funnel["resolver_rejected_terms"] == 2
    assert review.candidate_discovery_funnel["context_validated_candidates"] >= 1
    assert review.candidate_discovery_funnel["promoted_candidates"] >= 1
    assert "candidates_added" not in review.candidate_discovery_funnel
    assert "candidate_terms_added" not in review.candidate_discovery_funnel
    assert "raw_candidate_terms_added" in review.candidate_discovery_funnel
    assert "Strong opportunities" in report
    assert "quality_coverage:" in report
    assert "candidate_discovery_funnel:" in report
    assert "Quality Tuning Suggestions" in report
    assert "closest_to_digest_threshold" in report
    assert "VELVET" in report
    assert "Weak co-occurrence / local-only" in report
    assert "Validated but market-unconfirmed" in report
    missed_rows = [{"symbol": "MISS", "return_pct": 150, "failure_stage": "quality_gate_too_strict", "feedback_target": "missed:MISS"}]
    sim = event_alpha_policy_simulator.simulate_policy(
        rows,
        profile="fixture",
        feedback_rows=[
            {"feedback_target": "velvet", "label": "useful"},
            {"feedback_target": "btc-policy", "label": "junk"},
        ],
        missed_rows=missed_rows,
    )
    text = event_alpha_policy_simulator.format_policy_simulation(sim)
    assert "lower_opportunity_threshold" in text
    assert "high_quality_only" in text
    assert "legacy_conflicts_excluded: 1" in text
    assert "near-threshold" in text
    high_counts = [row["alertable_count"] for row in sim.scenarios if row["scenario"] == "high_quality_only"]
    low_counts = [row["alertable_count"] for row in sim.scenarios if row["scenario"] == "lower_opportunity_threshold"]
    assert max(low_counts) >= max(high_counts)
    assert "near-threshold" in next(row for row in sim.scenarios if row["scenario"] == "lower_opportunity_threshold")["gained"]
    assert "warning_weak_or_generic_alertable" not in text
    assert "known_useful_selected" in text
    assert "known_junk_selected" not in text
    assert "missed_recall_candidates" in text
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proposed.json"
        result = event_alpha_signal_quality_export.export_signal_quality_cases(
            out,
            alert_rows=rows,
            feedback_rows=[
                {"feedback_target": "velvet", "label": "useful", "notes": "good proxy evidence"},
                {"feedback_target": "btc-policy", "label": "junk", "notes": "weak macro cooccurrence"},
                {"feedback_target": "openai-velvet", "label": "watch"},
            ],
            missed_rows=missed_rows,
        )
        payload = json.loads(out.read_text())
        assert result.cases_written >= 3
        assert any(case["reason_to_add_case"] == "useful_feedback_positive_case" for case in payload["cases"])
        assert any(case["reason_to_add_case"] == "junk_feedback_negative_case" for case in payload["cases"])
        assert any(case["reason_to_add_case"] == "watch_feedback_borderline_case" for case in payload["cases"])
        assert any(case["reason_to_add_case"] == "missed_opportunity_recall_case" for case in payload["cases"])
        useful_case = next(case for case in payload["cases"] if case["reason_to_add_case"] == "useful_feedback_positive_case")
        assert useful_case["expected_route_behavior"] in {"high_priority_if_quality_gates_pass", "research_digest_if_quality_gates_pass"}
        junk_case = next(case for case in payload["cases"] if case["reason_to_add_case"] == "junk_feedback_negative_case")
        assert junk_case["expected_opportunity_level"] == "local_only"
        assert "OPENAI_API_KEY" not in out.read_text()


def test_event_alpha_quality_make_targets_exist_and_do_not_send():
    from pathlib import Path

    text = Path("Makefile").read_text()
    for target in (
        "event-alpha-quality-review",
        "event-alpha-quality-coverage-report",
        "event-alpha-policy-simulate",
        "event-alpha-quality-validation-cycle",
        "event-alpha-export-signal-quality-cases",
        "event-alpha-quality-loop",
        "event-alpha-quality-loop-llm",
        "event-alpha-frame-quality-loop",
    ):
        assert f"{target}:" in text
    loop = text.split("event-alpha-quality-loop:", 1)[1].split("event-alpha-quality-loop-llm:", 1)[0]
    assert "event-alpha-signal-quality-eval" in loop
    assert "event-alpha-quality-review" in loop
    assert "event-alpha-policy-simulate" in loop
    assert "event-alpha-notification-inbox" in loop
    assert "event-impact-hypotheses-report" in loop
    assert "event-alpha-daily-brief" in loop
    assert "event-alpha-cycle-send" not in loop
    assert "event-alert-send" not in loop
    frame_loop = text.split("event-alpha-frame-quality-loop:", 1)[1].split("event-alpha-signal-quality-eval:", 1)[0]
    assert "event-alpha-signal-quality-eval" in frame_loop
    assert "event-alpha-catalyst-frame-e2e-cycle" in frame_loop
    assert "event-alpha-quality-review" in frame_loop
    assert "event-incidents-report" in frame_loop
    assert "event-impact-hypotheses-report" in frame_loop
    assert "event-alpha-daily-brief" in frame_loop
    assert "event-alpha-artifact-doctor" in frame_loop
    assert "STRICT=1" in frame_loop
    assert "event-opportunity-audit" in frame_loop
    assert "TARGET=$(TARGET)" in frame_loop
    assert "event-alpha-cycle-send" not in frame_loop
    assert "event-alert-send" not in frame_loop
    daily_brief_target = text.split("event-alpha-daily-brief:", 1)[1].split("event-alpha-replay:", 1)[0]
    assert "$(EVENT_ALPHA_INCLUDE_TEST_ARG)" in daily_brief_target


def test_event_alpha_quality_coverage_checks_latest_raw_rows_only():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_coverage
    import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields

    started = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 6, 25, 12, 2, tzinfo=timezone.utc)
    run = {
        "row_type": "event_alpha_run",
        "run_id": "run-quality",
        "profile": "notify_llm_quality",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "success": True,
    }
    full = event_alpha_quality_fields.ensure_quality_fields({
        "run_id": "run-quality",
        "profile": "notify_llm_quality",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm_quality",
    })
    hypothesis = {**full, "row_type": "event_impact_hypothesis", "hypothesis_id": "hyp:velvet"}
    alert = {**full, "row_type": "event_alpha_alert_snapshot", "alert_key": "alert:velvet"}
    watch = event_alpha_quality_fields.ensure_quality_fields({
        "row_type": "event_watchlist_state",
        "key": "watch:velvet",
        "last_seen_at": "2026-06-25T12:01:00+00:00",
    })
    old_missing = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "old-run",
        "profile": "notify_llm_quality",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm_quality",
        "alert_key": "old-missing",
    }
    result = event_alpha_quality_coverage.build_latest_run_quality_coverage(
        profile="notify_llm_quality",
        artifact_namespace="notify_llm_quality",
        run_rows=[run],
        hypothesis_rows=[hypothesis],
        watchlist_rows=[watch],
        alert_rows=[alert, old_missing],
    )
    assert result.status == "OK"
    assert result.run_id == "run-quality"
    assert {bucket.row_type: bucket.rows for bucket in result.buckets} == {
        "hypothesis": 1,
        "watchlist": 1,
        "alert_snapshot": 1,
    }
    assert all(not bucket.missing_rows for bucket in result.buckets)

    bad_alert = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-quality",
        "profile": "notify_llm_quality",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm_quality",
        "alert_key": "bad-alert",
    }
    blocked = event_alpha_quality_coverage.build_latest_run_quality_coverage(
        profile="notify_llm_quality",
        artifact_namespace="notify_llm_quality",
        run_rows=[run],
        hypothesis_rows=[hypothesis],
        watchlist_rows=[watch],
        alert_rows=[bad_alert],
    )
    assert blocked.status == "BLOCKED"
    report = event_alpha_quality_coverage.format_quality_coverage_report(blocked)
    assert "bad-alert" in report
    assert "missing=" in report


def test_event_alpha_quality_stale_warning_uses_quality_validation_reference():
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_coverage
    import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review
    import crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store as event_impact_hypothesis_store

    stale_row = {
        "row_type": "event_impact_hypothesis",
        "run_id": "run-old",
        "profile": "notify_llm",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm",
        "hypothesis_id": "hyp:old",
    }
    reference = event_alpha_quality_fields.ensure_quality_fields({
        "row_type": "event_impact_hypothesis",
        "run_id": "run-ref",
        "profile": "quality_validation",
        "run_mode": "test",
        "artifact_namespace": "quality_validation",
        "hypothesis_id": "hyp:ref",
    })
    warning = event_alpha_quality_coverage.stale_quality_artifact_warning(
        [stale_row],
        reference_rows=[reference],
    )
    assert warning == event_alpha_quality_coverage.STALE_QUALITY_ARTIFACT_WARNING

    review = event_alpha_quality_review.build_quality_review(
        profile="notify_llm",
        hypothesis_rows=[stale_row],
        stale_warning=warning,
    )
    assert "stale_artifact_warning: " + warning in event_alpha_quality_review.format_quality_review(review)

    loaded = event_impact_hypothesis_store.EventImpactHypothesisStoreReadResult(
        path=Path("hypotheses.jsonl"),
        rows_read=1,
        rows=[stale_row],
        total_rows_read=1,
    )
    text = event_impact_hypothesis_store.format_impact_hypotheses_store_report(
        loaded,
        stale_quality_warning=warning,
    )
    assert "stale_artifact_warning: " + warning in text


def test_feedback_and_calibration_include_signal_quality_fields():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.outcomes.calibration as event_alpha_calibration
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_labels as event_feedback

    entry = _test_watchlist_entry(
        state="WATCHLIST",
        symbol="VELVET",
        coin_id="velvet",
    )
    core_id = "core_velvet_spacex"
    entry = __import__("dataclasses").replace(entry, latest_score_components={
        "run_id": "run-velvet",
        "profile": "catalyst_frame_e2e",
        "artifact_namespace": "catalyst_frame_e2e",
        "core_opportunity_id": core_id,
        "incident_id": "incident:velvet-spacex",
        "hypothesis_id": "hyp:velvet",
        "impact_path_type": "proxy_exposure",
        "candidate_role": "proxy_venue",
        "evidence_specificity": "source_explains_mechanism",
        "market_confirmation_level": "moderate",
        "market_context_freshness_status": "fresh",
        "opportunity_level": "watchlist",
        "source_class": "crypto_native",
        "source_domain": "cryptopanic.com",
        "evidence_acquisition_providers_used": ("cryptopanic",),
        "catalyst_frame_status": "validated",
        "main_frame_type": "proxy_exposure",
        "final_route_after_quality_gate": "WATCHLIST",
        "lane": "daily_digest",
        "accepted_evidence_reason_codes": ("cryptopanic_currency_tag_match", "direct_token_mechanism"),
    })
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        card_path = tmp_path / "velvet.md"
        card_path.write_text(
            "# Card\n\n"
            "- Run ID: run-velvet\n"
            "- Profile: catalyst_frame_e2e\n"
            "- Namespace: catalyst_frame_e2e\n"
            f"- Core opportunity ID: {core_id}\n"
            f"- Feedback target: {core_id}\n",
            encoding="utf-8",
        )
        context_row = {
            "row_type": "event_core_opportunity",
            "run_id": "run-velvet",
            "profile": "catalyst_frame_e2e",
            "artifact_namespace": "catalyst_frame_e2e",
            "core_opportunity_id": core_id,
            "feedback_target": core_id,
            "feedback_target_type": "core_opportunity_id",
            "card_path": str(card_path),
            "symbol": "VELVET",
            "coin_id": "velvet",
            "incident_id": "incident:velvet-spacex",
            "hypothesis_id": "hyp:velvet",
            "impact_path_type": "proxy_exposure",
            "candidate_role": "proxy_venue",
            "evidence_specificity": "source_explains_mechanism",
            "source_class": "crypto_native",
            "source_domain": "cryptopanic.com",
            "source_provider": "cryptopanic",
            "source_pack": "proxy_preipo_rwa_pack",
            "accepted_evidence_reason_codes": ("cryptopanic_currency_tag_match", "direct_token_mechanism"),
            "market_confirmation_level": "moderate",
            "market_context_freshness_status": "fresh",
            "catalyst_frame_status": "validated",
            "main_frame_type": "proxy_exposure",
            "opportunity_level": "watchlist",
            "final_route_after_quality_gate": "WATCHLIST",
            "lane": "daily_digest",
        }
        cfg = event_feedback.EventFeedbackConfig(path=tmp_path / "feedback.jsonl")
        record = event_feedback.mark_feedback(
            str(card_path),
            "useful",
            watchlist_entries=[entry],
            context_rows=[context_row],
            card_paths=[card_path],
            cfg=cfg,
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
        )
        loaded = event_feedback.load_feedback(cfg.path)
    assert record.impact_path_type == "proxy_exposure"
    assert record.incident_id == "incident:velvet-spacex"
    assert record.hypothesis_id == "hyp:velvet"
    assert record.core_opportunity_id == core_id
    assert record.feedback_target == core_id
    assert record.card_path and record.card_path.endswith("velvet.md")
    assert record.run_id == "run-velvet"
    assert record.profile == "catalyst_frame_e2e"
    assert record.artifact_namespace == "catalyst_frame_e2e"
    assert record.source_pack == "proxy_preipo_rwa_pack"
    assert record.source_provider == "cryptopanic"
    assert record.source_provider_domain == "cryptopanic.com"
    assert record.market_context_freshness_status == "fresh"
    assert record.catalyst_frame_status == "validated"
    assert record.main_frame_type == "proxy_exposure"
    assert record.final_route_after_quality_gate == "WATCHLIST"
    assert "direct_token_mechanism" in record.accepted_evidence_reason_codes
    assert loaded.records[0].incident_id == "incident:velvet-spacex"
    report = event_alpha_calibration.format_calibration_report([], feedback_rows=[r.__dict__ for r in loaded.records])
    assert "feedback by impact path type: proxy_exposure: useful=1" in report
    assert "feedback by candidate role: proxy_venue: useful=1" in report
    assert "feedback by source class: crypto_native: useful=1" in report
    assert "feedback by source pack: proxy_preipo_rwa_pack: useful=1" in report
    assert "feedback by accepted evidence reason: cryptopanic_currency_tag_match: useful=1" in report
    assert "direct_token_mechanism: useful=1" in report
    assert "feedback by incident id: incident:velvet-spacex: useful=1" in report
    assert "feedback by source domain: cryptopanic.com: useful=1" in report
    assert "feedback by market freshness: fresh: useful=1" in report
    assert "feedback by catalyst frame status: validated: useful=1" in report
    assert "feedback by main frame type: proxy_exposure: useful=1" in report
    assert "feedback by route/lane: WATCHLIST/daily_digest: useful=1" in report


def test_event_alpha_signal_quality_make_targets_exist():
    from pathlib import Path

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-signal-quality-eval:" in text
    assert "--event-alpha-signal-quality-eval" in text
    assert "event-opportunity-audit:" in text
    assert "--event-opportunity-audit" in text


def test_quality_review_uses_core_opportunities_as_primary_sections():
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    rows = _canonical_core_fixture_rows()
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-quality-review",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    review = event_alpha_quality_review.build_quality_review(
        profile="market_refresh_smoke",
        core_opportunity_rows=core_rows,
        hypothesis_rows=rows,
    )
    text = event_alpha_quality_review.format_quality_review(review)
    strong = text.split("Strong opportunities:", 1)[1].split("Validated but market-unconfirmed:", 1)[0]
    weak = text.split("Weak co-occurrence / local-only:", 1)[1].split("Sector hypotheses awaiting validation:", 1)[0]
    upgrades = text.split("Top upgrade candidates:", 1)[1].split("Top downgrade risks:", 1)[0]
    downgrades = text.split("Top downgrade risks:", 1)[1].split("Quality Tuning Suggestions:", 1)[0]
    freshness = text.split("Market Freshness Readiness:", 1)[1].split("Top upgrade candidates:", 1)[0]
    assert "operator_view: canonical_core_rows=4" in text
    assert "VELVET" in strong
    assert "VELVET" not in weak
    assert "VELVET" not in upgrades
    assert "VELVET" in downgrades
    assert "invalid exposure/value-capture claim" in downgrades
    assert "no token value-capture mechanism is visible" not in downgrades
    assert "AAVE" in upgrades
    assert "status=fresh source=missing" not in freshness
    assert "support_or_diagnostic_rows=" in text


def test_feedback_readiness_counts_canonical_review_items_not_diagnostics():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_feedback_readiness
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-feedback-canonical-review",
            profile="evidence_acquisition_smoke",
            run_mode="burn_in",
            artifact_namespace="evidence_acquisition_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        cards = event_research_cards.write_research_cards(root / "cards", watchlist_entries=[], alert_rows=core_rows)
        event_core_opportunity_store.update_core_opportunity_card_links(
            core_path,
            cards.card_paths,
            run_id="run-feedback-canonical-review",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        velvet = next(row for row in core_rows if row["symbol"] == "VELVET")
        canonical = {
            "row_type": "event_alpha_alert_snapshot",
            "run_id": "run-feedback-canonical-review",
            "alert_id": "ea:velvet-canonical",
            "alert_key": "incident-spacex|velvet|proxy_attention",
            "core_opportunity_id": velvet["core_opportunity_id"],
            "snapshot_class": "canonical_core_snapshot",
            "core_resolution_status": "canonical",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            "tier": "HIGH_PRIORITY_WATCH",
            "feedback_target": velvet["core_opportunity_id"],
        }
        diagnostic_without_target = {
            **canonical,
            "alert_id": "ea:velvet-support",
            "alert_key": "incident-spacex|velvet|source_noise_control",
            "snapshot_class": "diagnostic_support_snapshot",
            "core_resolution_status": "diagnostic_support",
            "snapshot_core_resolution_status": "diagnostic_support",
            "is_diagnostic_snapshot": True,
            "candidate_role": "source_noise",
            "playbook_type": "source_noise_control",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "feedback_target": "",
        }
        inbox = event_alpha_notification_inbox.build_notification_inbox(
            notification_runs=[],
            alert_rows=[diagnostic_without_target, canonical],
            feedback_rows=[],
            research_cards_dir=root / "cards",
            profile="evidence_acquisition_smoke",
            artifact_namespace="evidence_acquisition_smoke",
            notification_runs_path=root / "runs.jsonl",
            alert_store_path=root / "alerts.jsonl",
            feedback_path=root / "feedback.jsonl",
            core_opportunity_rows=core_rows,
        )
        readiness = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="evidence_acquisition_smoke",
            artifact_namespace="evidence_acquisition_smoke",
            card_paths=cards.card_paths,
            alert_rows=[diagnostic_without_target, canonical],
            feedback_rows=[],
            watchlist_entries=[],
            core_opportunity_rows=core_rows,
            inbox_result=inbox,
        )

    assert readiness.canonical_review_items >= 1
    assert readiness.diagnostic_review_items_hidden >= 1
    assert "alert_snapshots_missing_feedback_targets" not in readiness.blockers
    assert "canonical_review_items_missing_feedback_targets" not in readiness.blockers


def test_daily_brief_evidence_acquisition_uses_canonical_post_policy_verdict():
    import json

    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        core_row = {
            "row_type": "event_core_opportunity",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "ns",
            "core_opportunity_id": "core_chz_review",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "incident_id": "world-cup-chz",
            "candidate_role": "proxy_instrument",
            "primary_impact_path": "unlock_supply_event",
            "impact_path_type": "unlock_supply_event",
            "opportunity_level": "validated_digest",
            "final_opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "final_state_after_quality_gate": "RADAR",
            "source_pack": "unlock_supply_pack",
            "source_class": "cryptopanic_tagged",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "accepted_provider_counts": {"cryptopanic": 1},
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "supporting_categories": ["sports_fan_proxy"],
            "supporting_impact_paths": ["fan_token_attention"],
            "generated_at": "2026-07-01T00:00:00+00:00",
        }
        acquisition = {
            "row_type": "event_evidence_acquisition",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "ns",
            "core_opportunity_id": "core_chz_review",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "source_pack": "fan_sports_pack",
            "status": "accepted_evidence_found",
            "accepted_evidence": [{"provider": "cryptopanic", "source_class": "cryptopanic_tagged"}],
            "rejected_evidence_samples": [],
            "opportunity_score_before": 64,
            "opportunity_score_after": 72,
            "acquisition_evidence_status": "accepted_evidence_found",
            "final_upgrade_status": "unchanged",
            "final_opportunity_level": "validated_digest",
            "final_verdict_source": "evidence_acquisition",
        }
        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[{
                "row_type": "event_alpha_run",
                "run_id": "run-1",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "ns",
                "started_at": "2026-07-01T00:00:00+00:00",
                "success": True,
            }],
            core_opportunity_rows=[core_row],
            evidence_acquisition_rows=[acquisition],
            requested_profile="notify_llm_deep",
            artifact_namespace="ns",
            run_ledger_path=base / "event_alpha_runs.jsonl",
        )
    assert "## Validated Digest Core Opportunities\n- None." in brief
    assert "## Live Confirmation Gated Candidates" in brief
    assert "source_only_narrative_without_market_confirmation" in brief
    assert "verdict=exploratory source=core_opportunity_merge" in brief


def test_integrated_radar_outcomes_and_calibration_are_research_only():
    import json

    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar
    import crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes as event_integrated_radar_outcomes

    with TemporaryDirectory() as tmp:
        context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=tmp,
            artifact_namespace="integrated_outcomes",
        )
        event_integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        rows = event_integrated_radar_outcomes.fill_integrated_radar_outcomes(
            context.namespace_dir,
            observed_at="2026-06-16T16:00:00Z",
        )
        by_symbol = {row["symbol"]: row for row in rows}
        assert by_symbol["TESTLIST"]["outcome_label"] == "early_good"
        assert by_symbol["TESTPERP"]["outcome_label"] == "continuation_good"
        assert by_symbol["TESTFADE"]["outcome_label"] == "fade_review_good"
        assert by_symbol["TESTUNLOCK"]["outcome_label"] == "risk_validated"
        assert by_symbol["BTC"]["outcome_label"] == "remained_noise"
        assert by_symbol["TESTRUMOR"]["outcome_label"] == "remained_noise"
        assert by_symbol["TESTFADE"]["primary_horizon_return"] < 0
        assert by_symbol["TESTFADE"]["thesis_direction"] == "downside_or_risk_research"
        assert by_symbol["TESTFADE"]["thesis_primary_move"] > 0
        assert by_symbol["TESTFADE"]["thesis_favorable_excursion"] > 0
        assert "asset fell" in by_symbol["TESTFADE"]["thesis_outcome_interpretation"]
        assert by_symbol["TESTUNLOCK"]["primary_horizon_return"] < 0
        assert by_symbol["TESTUNLOCK"]["thesis_direction"] == "downside_or_risk_research"
        assert by_symbol["TESTUNLOCK"]["thesis_primary_move"] > 0
        assert all(row["research_only"] is True for row in rows)
        assert all(row["normal_rsi_signal_written"] is False for row in rows)
        assert all(row["triggered_fade_created"] is False for row in rows)
        assert all(row["paper_trade_created"] is False for row in rows)
        report = (context.namespace_dir / "event_integrated_radar_outcome_report.md").read_text(encoding="utf-8")
        assert "Event Alpha Integrated Radar Outcome Report" in report
        assert "No trades or paper trades" in report
        assert "Median asset primary return" in report
        assert "Median thesis-favorable move" in report
        priors = json.loads((context.namespace_dir / "event_integrated_radar_calibration_priors.json").read_text(encoding="utf-8"))
        assert priors["auto_apply"] is False
        assert "EARLY_LONG_RESEARCH" in priors["opportunity_type_priors"]
        assert "validated_count" in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        assert "invalidated_count" in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        assert "validation_rate" in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        assert "useful" not in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        assert "junk" not in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        assert "legacy_aliases" in priors["opportunity_type_priors"]["FADE_SHORT_REVIEW"]
        calibration = (context.namespace_dir / "event_integrated_radar_calibration_report.md").read_text(encoding="utf-8")
        assert "validated=" in calibration
        assert "invalidated/noise=" in calibration
        assert "validation_rate=" in calibration
        assert " junk" not in calibration.casefold()
