"""Focused Event Alpha provider and discovery tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_discovery_transform_applies_llm_hints_before_resolver_validation():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    class Provider:
        name = "fixture"

        def extract_raw_event(self, packet):
            return LLMProviderResult(raw={
                "confidence": 0.91,
                "external_catalysts": [{
                    "name": "SpaceX",
                    "catalyst_type": "ipo_proxy",
                    "event_time": None,
                    "event_time_confidence": 0.0,
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "SpaceX exposure", "source_field": "body", "supports": "external catalyst"}],
                }],
                "crypto_asset_mentions": [{
                    "name": "Stealth Alpha",
                    "symbol": "STEALTH",
                    "coin_id": "stealth-alpha",
                    "contract_address": None,
                    "mention_type": "project_or_token",
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "Stealth proxy venue", "source_field": "body", "supports": "asset mention"}],
                }],
                "false_positive_terms": [],
                "event_date_hints": [],
                "suggested_followup_queries": [],
                "warnings": [],
            })

    raw_rows = [{
        "raw_id": "llm-upstream-stealth",
        "provider": "manual_json",
        "fetched_at": "2026-06-16T12:00:00Z",
        "published_at": "2026-06-16T11:00:00Z",
        "source_url": "https://example.test/stealth-alpha",
        "title": "SpaceX exposure desk opens before listing event",
        "body": "Stealth proxy venue is live for SpaceX exposure before the event.",
        "source_confidence": 0.90,
        "event": {
            "event_id": "stealth-spacex-event",
            "event_name": "SpaceX proxy exposure opens",
            "event_type": "ipo_proxy",
            "event_time": "2026-06-16T13:30:00Z",
            "event_time_confidence": 1.0,
            "external_asset": "SpaceX",
            "confidence": 0.90,
            "description": "A proxy venue opened for SpaceX exposure.",
        },
    }]
    alias_rows = {"assets": [{
        "coin_id": "stealth-alpha",
        "symbol": "STEALTH",
        "name": "Stealth Alpha",
        "aliases": ["stealth alpha"],
    }]}
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        event_path = Path(tmp) / "events.json"
        alias_path = Path(tmp) / "aliases.json"
        event_path.write_text(json.dumps(raw_rows), encoding="utf-8")
        alias_path.write_text(json.dumps(alias_rows), encoding="utf-8")

        without_hints = event_discovery.run_manual_discovery(event_path, alias_path, now=now)
        assert without_hints.candidates == ()

        seen_rows = []

        def transform(raw_events):
            nonlocal seen_rows
            seen_rows = event_llm_extractor.analyze_raw_events(raw_events, Provider())
            return event_llm_extractor.enrich_raw_events_with_extractions(raw_events, seen_rows)

        with_hints = event_discovery.run_manual_discovery(
            event_path,
            alias_path,
            now=now,
            raw_event_transform=transform,
        )
        assert len(seen_rows) == 1
        assert len(with_hints.candidates) == 1
        candidate = with_hints.candidates[0]
        assert candidate.asset.coin_id == "stealth-alpha"
        assert candidate.link.match_reason in {"coin_id", "known_alias", "name_and_symbol", "name"}
        assert candidate.event.raw_ids == ("llm-upstream-stealth",)
        assert candidate.event.description and "LLM extracted research hints" in candidate.event.description
        assert with_hints.raw_events[0].raw_json["llm_extraction"]["crypto_asset_mentions"][0]["coin_id"] == "stealth-alpha"


def test_event_market_enrichment_live_fail_soft_records_provider_health():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health

    class FailingClient:
        calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get_top_markets(self, n):
            type(self).calls += 1
            raise OSError("DNS temporary failure in name resolution")

    now = datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        health_cfg = event_provider_health.EventProviderHealthConfig(
            path=Path(tmp) / "provider_health.json",
            max_consecutive_failures=1,
            backoff_minutes=30,
            fail_fast_on_dns=True,
        )
        rows, warnings = event_market_enrichment.load_market_enrichment_rows_safe(
            None,
            live=True,
            fetch_limit=5,
            fail_soft=True,
            client_factory=FailingClient,
            provider_health_cfg=health_cfg,
            now=now,
        )
        assert rows == []
        assert warnings == ("market_enrichment_live_fetch_failed: OSError",)
        health = event_provider_health.load_provider_health(health_cfg.path)
        assert health["coingecko:market_enrichment"]["last_error_class"] == "OSError"
        assert health["coingecko:market_enrichment"]["disabled_until"]

        class ShouldNotRunClient(FailingClient):
            calls = 0

        rows_again, warnings_again = event_market_enrichment.load_market_enrichment_rows_safe(
            None,
            live=True,
            fetch_limit=5,
            fail_soft=True,
            client_factory=ShouldNotRunClient,
            provider_health_cfg=health_cfg,
            now=now,
        )
        assert rows_again == []
        assert ShouldNotRunClient.calls == 0
        assert any("coingecko:market_enrichment in backoff" in warning for warning in warnings_again)

        try:
            event_market_enrichment.load_market_enrichment_rows(
                None,
                live=True,
                fetch_limit=5,
                fail_soft=False,
                client_factory=FailingClient,
            )
        except OSError:
            pass
        else:
            raise AssertionError("non-fail-soft live market enrichment should raise")


def test_event_discovery_market_enrichment_failure_continues_fail_soft():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_alpha.radar import discovery as event_discovery
    from crypto_rsi_scanner.event_alpha.radar import market_enrichment as event_market_enrichment

    original_loader = event_market_enrichment.load_market_enrichment_rows_safe

    def fake_loader(*args, **kwargs):
        assert kwargs["fail_soft"] is True
        return [], ("market_enrichment_live_fetch_failed: OSError",)

    event_market_enrichment.load_market_enrichment_rows_safe = fake_loader
    try:
        result = event_discovery.run_manual_discovery(
            None,
            None,
            market_enrichment_enabled=True,
            market_enrichment_live=True,
            anomaly_scanner_enabled=True,
            market_enrichment_fail_soft=True,
            now=datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc),
        )
    finally:
        event_market_enrichment.load_market_enrichment_rows_safe = original_loader
    assert result.raw_events == ()
    assert "market_enrichment_live_fetch_failed: OSError" in result.warnings


def test_event_catalyst_search_live_provider_adapters_are_evidence_only():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    query = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:pump:2026-06-18",
        query="PUMP Binance listing",
        symbol="PUMP",
        rank=1,
        score=90,
    )
    news_row = {
        "id": "pump-listing",
        "title": "Binance will list Pump Protocol (PUMP)",
        "body": "Binance will list Pump Protocol spot trading pairs today.",
        "published_at": now.isoformat(),
        "fetched_at": now.isoformat(),
        "url": "https://example.test/pump",
        "source_confidence": 0.90,
    }
    poly_row = {
        "id": "pump-spacex-market",
        "title": "Will Pump Protocol offer SpaceX pre-IPO exposure?",
        "description": "Prediction market for PUMP and SpaceX pre-IPO exposure.",
        "createdAt": now.isoformat(),
        "endDate": "2026-06-20T12:00:00Z",
        "url": "https://polymarket.test/event/pump-spacex",
        "source_confidence": 0.80,
    }
    with tempfile.TemporaryDirectory() as tmp:
        news_path = Path(tmp) / "news.json"
        news_path.write_text(json.dumps({"articles": [news_row]}), encoding="utf-8")
        poly_path = Path(tmp) / "polymarket.json"
        poly_path.write_text(json.dumps({"events": [poly_row]}), encoding="utf-8")
        providers = [
            event_catalyst_search.GdeltCatalystSearchProvider(path=news_path),
            event_catalyst_search.ProjectRssCatalystSearchProvider(path=news_path),
            event_catalyst_search.PolymarketCatalystSearchProvider(path=poly_path),
        ]
        for provider in providers:
            result = provider.search([query], max_results_per_query=2, now=now)
            assert result.result_events
            raw = result.result_events[0].raw_event
            assert raw.raw_json["market_anomaly_catalyst_search_source"]["research_only"] is True
            assert raw.raw_json["market_anomaly_catalyst_search_source"]["query"] == query.query

    missing_key = event_catalyst_search.CryptoPanicCatalystSearchProvider(live_enabled=True, api_token="")
    result = missing_key.search([query], max_results_per_query=2, now=now)
    assert result.result_events == ()


def test_event_catalyst_search_gdelt_fetch_cap_prevents_repeated_live_failures():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    calls = {"count": 0}

    def failing_opener(request, timeout):
        del request, timeout
        calls["count"] += 1
        raise RuntimeError("HTTP 429")

    queries = tuple(
        event_catalyst_search.SearchQuery(
            anomaly_raw_id=f"market_anomaly:pump:{idx}",
            query=f"PUMP catalyst query {idx}",
            symbol="PUMP",
            rank=idx,
            coin_id="pump-fun",
            project_name="Pump.fun",
            aliases=("Pump.fun",),
        )
        for idx in range(8)
    )
    provider = event_catalyst_search.GdeltCatalystSearchProvider(
        live_enabled=True,
        opener=failing_opener,
        max_fetches_per_search=1,
    )
    result = provider.search(queries, max_results_per_query=1, now=now)
    assert calls["count"] == 1
    assert result.provider_fetch_count == 1
    assert result.provider_cache_misses == 1
    assert result.query_count == 8
    assert any("GDELT live news fetch failed" in warning for warning in result.warnings)
    assert any("fetch cap reached" in warning for warning in result.warnings)


def test_event_catalyst_search_gdelt_fetch_cap_prioritizes_highest_scored_query():
    import json
    from datetime import datetime, timezone
    from urllib.parse import parse_qs, urlparse

    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"articles": []}).encode("utf-8")

    seen_queries = []

    def opener(request, timeout):
        del timeout
        seen_queries.append(parse_qs(urlparse(request.full_url).query)["query"][0])
        return FakeResponse()

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    low = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:test",
        query="TEST crypto why up",
        symbol="TEST",
        rank=1,
        score=20,
    )
    high = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:test",
        query="TEST exploit",
        symbol="TEST",
        rank=2,
        score=80,
    )
    provider = event_catalyst_search.GdeltCatalystSearchProvider(
        live_enabled=True,
        opener=opener,
        fetched_at=now,
        max_fetches_per_search=1,
    )
    result = provider.search((low, high), max_results_per_query=1, now=now)
    assert seen_queries == ["TEST exploit"]
    assert result.queries == (high, low)
    assert result.provider_fetch_count == 1


def test_event_candidate_discovery_rejects_common_word_false_positives():
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from datetime import datetime, timezone

    now = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_search",
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.75,
            content_hash=raw_id,
        )

    velvet = event_impact_hypotheses._candidate_asset_from_discovery_raw(
        raw("velvet", "OpenAI pre-IPO crypto venue Velvet", "Velvet offers crypto exposure to private AI shares.")
    )
    assert velvet
    accepted, rejected = event_impact_hypotheses._split_suggested_assets(
        (velvet,),
        external_entities=(),
        text="OpenAI pre-IPO crypto venue Velvet",
    )
    assert accepted and accepted[0]["symbol"] == "VELVET"
    assert not rejected

    for title, symbol, reason in (
        ("IPO hype returns to crypto markets", "HYPE", "generic_symbol_without_project_identity"),
        ("Prime minister talks crypto policy", "PRIME", "common_word_or_title_not_asset_identity"),
        ("Bitcoin World covers SpaceX prediction market", "BTC", "publisher_source_name_not_asset_identity"),
    ):
        row = {"symbol": symbol, "coin_id": symbol.lower(), "source_title": title, "source": "candidate_discovery_search"}
        accepted, rejected = event_impact_hypotheses._split_suggested_assets((row,), external_entities=(), text=title)
        assert not accepted
        assert rejected[0]["rejection_reason"] == reason


def test_event_impact_candidate_discovery_suggests_then_requires_identity_validation():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp-openai-sector",
        event_cluster_id="openai|ipo_proxy|2026-06-20",
        event_type="ipo_proxy",
        external_asset="OpenAI",
        impact_category="ai_ipo_proxy",
        candidate_sectors=("ai_tokens", "tokenized_stock_venues"),
        candidate_symbols=(),
        direction_hint="up_then_fade",
        playbook_hint="ai_ipo_proxy",
        confidence=0.86,
        hypothesis_score=67.0,
        search_query_details=(
            {"query": "OpenAI crypto exposure", "query_type": "candidate_discovery"},
        ),
        search_queries=("OpenAI crypto exposure",),
    )
    query = event_catalyst_search.SearchQuery(
        anomaly_raw_id=hypothesis.hypothesis_id,
        query="OpenAI crypto exposure",
        symbol="SECTOR",
        rank=1,
        query_type="candidate_discovery",
    )
    raw = RawDiscoveredEvent(
        raw_id="velvet-openai-discovery",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/velvet-openai",
        title="VELVET opens OpenAI pre-IPO crypto venue",
        body="Velvet Capital users can trade tokenized stock style exposure to OpenAI.",
        raw_json={
            "asset": {
                "symbol": "VELVET",
                "coin_id": "velvet",
                "name": "Velvet Capital",
                "confidence": 0.90,
            }
        },
        source_confidence=0.90,
        content_hash="velvet-openai-discovery",
    )
    hype = RawDiscoveredEvent(
        raw_id="hype-openai-discovery",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/hype-openai",
        title="IPO hype builds around OpenAI",
        body="Generic IPO hype mentions crypto without naming Hyperliquid or $HYPE.",
        raw_json={
            "asset": {
                "symbol": "HYPE",
                "coin_id": "hyperliquid",
                "name": "Hype",
                "confidence": 0.80,
            }
        },
        source_confidence=0.80,
        content_hash="hype-openai-discovery",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(
        rows_by_query={"OpenAI crypto exposure": (raw, hype)}
    )
    executed = event_catalyst_search.run_hypothesis_search(
        (hypothesis,),
        provider,
        cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(
            enabled=True,
            max_hypotheses=1,
            max_queries_per_hypothesis=0,
            max_results_per_query=5,
            min_confidence=0.50,
            min_result_confidence=0.50,
            candidate_discovery_enabled=True,
            max_candidate_discovery_queries=1,
            max_candidate_discovery_results=5,
        ),
        now=now,
    )
    assert any(query.query_type == "candidate_discovery" for query in executed.queries)
    assert len(executed.result_events) >= 1
    discovered_from_search = event_impact_hypotheses.attach_hypothesis_search_samples((hypothesis,), executed)[0]
    assert discovered_from_search.crypto_candidate_assets[0]["symbol"] == "VELVET"
    assert any(row.get("symbol") == "HYPE" for row in discovered_from_search.rejected_candidate_assets)
    assert any(query.get("query_type") == "candidate_discovery" for query in discovered_from_search.executed_queries)
    validated_from_search = event_impact_hypotheses.validate_hypotheses_with_raw_events(
        (discovered_from_search,),
        tuple(result.raw_event for result in executed.result_events),
    )[0]
    assert validated_from_search.validation_stage == event_impact_hypotheses.ValidationStage.IMPACT_PATH_VALIDATED.value
    assert "TRIGGERED_FADE" not in event_impact_hypotheses.format_impact_hypothesis_report((validated_from_search,))

    search_result = event_catalyst_search.CatalystSearchRunResult(
        provider="fixture",
        queries=(query,),
        rejected_result_events=(
            event_catalyst_search.SearchResultEvent(
                query=query,
                raw_event=raw,
                result_score=45,
                result_score_reasons=("result_identity_rejected",),
                accepted=False,
            ),
        ),
        rejected_count=1,
    )
    discovered = event_impact_hypotheses.attach_hypothesis_search_samples((hypothesis,), search_result)[0]
    assert discovered.status == event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value
    assert discovered.validation_stage == event_impact_hypotheses.ValidationStage.CANDIDATE_ASSETS_SUGGESTED.value
    assert discovered.candidate_symbols == ("VELVET",)
    assert discovered.crypto_candidate_assets[0]["source"] == "candidate_discovery_search"
    assert "candidate_identity_not_validated" in discovered.why_not_promoted

    validated = event_impact_hypotheses.validate_hypotheses_with_raw_events((discovered,), (raw,))[0]
    assert validated.status == event_impact_hypotheses.HypothesisStatus.VALIDATED.value
    assert validated.validation_stage == event_impact_hypotheses.ValidationStage.IMPACT_PATH_VALIDATED.value
    assert validated.impact_path_reason == event_impact_hypotheses.ImpactPathReason.VENUE_VALUE_CAPTURE.value
    assert validated.candidate_symbols == ("VELVET",)
    assert validated.why_not_promoted == ()


def test_event_discovery_asset_role_demotes_proxy_context_noise():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent
    from crypto_rsi_scanner.event_providers.manual_json import content_hash

    def raw_event(raw_id, title, body, external_asset="SpaceX"):
        payload = {
            "raw_id": raw_id,
            "title": title,
            "body": body,
            "event": {
                "event_id": raw_id,
                "event_name": title,
                "event_type": "ipo_proxy",
                "event_time": None,
                "event_time_confidence": 0.0,
                "external_asset": external_asset,
                "confidence": 0.75,
                "description": body,
            },
        }
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="test_rss",
            fetched_at=datetime(2026, 6, 16, 13, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json=payload,
            source_confidence=0.75,
            content_hash=content_hash(payload),
        )

    assets = [
        DiscoveredAsset(
            coin_id="bitcoin",
            symbol="BTC",
            name="Bitcoin",
            market_cap=1_000_000_000_000,
            volume_24h=20_000_000_000,
            price=65_000,
            categories=("store-of-value",),
            contract_addresses={},
            source="test",
            aliases=("bitcoin", "btc"),
        ),
        DiscoveredAsset(
            coin_id="hyperliquid",
            symbol="HYPE",
            name="Hyperliquid",
            market_cap=1_000_000_000,
            volume_24h=200_000_000,
            price=35.0,
            categories=("perp-dex",),
            contract_addresses={},
            source="test",
            aliases=("hyperliquid", "hype"),
        ),
        DiscoveredAsset(
            coin_id="solana",
            symbol="SOL",
            name="Solana",
            market_cap=100_000_000_000,
            volume_24h=5_000_000_000,
            price=150.0,
            categories=("layer-1",),
            contract_addresses={},
            source="test",
            aliases=("solana", "sol"),
        ),
        DiscoveredAsset(
            coin_id="chainlink",
            symbol="LINK",
            name="Chainlink",
            market_cap=20_000_000_000,
            volume_24h=1_000_000_000,
            price=18.0,
            categories=("oracle",),
            contract_addresses={},
            source="test",
            aliases=("chainlink", "link"),
        ),
    ]
    raw = [
        raw_event(
            "spacex-bitcoin-hyperliquid",
            "SpaceX S-1 Reveals 18,712 Bitcoin as Hyperliquid's Pre-IPO Market Prices SPCX",
            "Hyperliquid lists pre-IPO SpaceX contracts while the filing mentions Bitcoin holdings.",
        ),
        raw_event(
            "spacex-hype-common-word",
            "SpaceX Hype Spurs Crypto Shadow Market for Pre-IPO Bets",
            "A shadow market is forming for SpaceX pre-IPO exposure, but the exchange token is not named.",
        ),
        raw_event(
            "spacex-on-solana",
            "SpaceX tokenized stock demand on Solana surged before allocations were canceled",
            "Tokenized stock infrastructure on Solana saw demand, but Solana is the chain, not the proxy instrument.",
        ),
        raw_event(
            "world-cup-chainlink-oracle",
            "Chainlink Beat Polymarket and Kalshi to the World Cup",
            "Chainlink powers the World Cup prediction market as an oracle provider, not the proxy token instrument.",
            external_asset="World Cup",
        ),
    ]

    result = event_discovery.run_discovery(raw, assets, now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc))
    by_event_asset = {
        (candidate.event.event_id, candidate.asset.coin_id): candidate
        for candidate in result.candidates
    }

    btc = by_event_asset[("spacex-bitcoin-hyperliquid", "bitcoin")]
    assert btc.classification.relationship_type == "proxy_context"
    assert btc.classification.asset_role == "mentioned_asset"
    assert btc.classification.is_proxy_narrative is False

    venue = by_event_asset[("spacex-bitcoin-hyperliquid", "hyperliquid")]
    assert venue.classification.relationship_type == "proxy_attention"
    assert venue.classification.asset_role == "proxy_venue"
    assert venue.classification.is_proxy_narrative is True
    assert venue.data_quality["forced_no_trade_reason"] == "proxy_venue_review_only"
    assert venue.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert "proxy venue candidates are watchlist-only by default" in venue.fade_signal.warnings

    assert ("spacex-hype-common-word", "hyperliquid") not in by_event_asset

    sol = by_event_asset[("spacex-on-solana", "solana")]
    assert sol.classification.relationship_type == "proxy_context"
    assert sol.classification.asset_role == "infrastructure"
    assert sol.classification.is_proxy_narrative is False

    link = by_event_asset[("world-cup-chainlink-oracle", "chainlink")]
    assert link.classification.relationship_type == "proxy_context"
    assert link.classification.asset_role == "infrastructure"
    assert link.classification.is_proxy_narrative is False


def test_event_discovery_news_pipeline_proxy_direct_late_and_ambiguous_safety():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

    _events_path, aliases_path = _event_discovery_fixture_paths()
    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = event_discovery.load_discovery_events(
        None,
        start,
        end,
        cryptopanic_path=cryptopanic_path,
        gdelt_path=gdelt_path,
        project_blog_rss_path=blog_path,
    )
    assets = load_asset_aliases(aliases_path)
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert len(raw) == 5
    assert set(by_symbol) == {"TESTAI", "TESTBTC", "TESTFAN", "TESTLATE", "TESTAMBIG"}

    ai = by_symbol["TESTAI"]
    assert ai.classification.is_proxy_narrative is True
    assert ai.classification.is_direct_beneficiary is False
    assert ai.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED

    btc = by_symbol["TESTBTC"]
    assert btc.classification.is_direct_beneficiary is True
    assert btc.classification.relationship_type == "direct_token_event"
    assert btc.fade_signal.signal_type == FadeSignalType.NO_TRADE

    fan = by_symbol["TESTFAN"]
    assert fan.classification.is_proxy_narrative is True
    assert fan.classification.relationship_type in ("proxy_exposure", "proxy_attention")
    assert fan.fade_signal.signal_type == FadeSignalType.NO_TRADE

    late = by_symbol["TESTLATE"]
    assert late.classification.is_proxy_narrative is True
    assert late.fade_candidate.component_scores["event_clarity"] < 70
    assert late.fade_signal.signal_type == FadeSignalType.NO_TRADE

    ambiguous = by_symbol["TESTAMBIG"]
    assert ambiguous.classification.relationship_type == "ambiguous"
    assert ambiguous.data_quality["classifier_pass"] is False
    assert ambiguous.fade_signal.signal_type == FadeSignalType.NO_TRADE


def test_event_discovery_external_catalyst_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.external_ipo import ExternalIpoProvider
    from crypto_rsi_scanner.event_providers.prediction_market_events import PredictionMarketEventsProvider
    from crypto_rsi_scanner.event_providers.sports_fixtures import SportsFixturesProvider

    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    ipo_events = ExternalIpoProvider(ipo_path, required=True).fetch_events(start, end)
    sports_events = SportsFixturesProvider(sports_path, required=True).fetch_events(start, end)
    prediction_events = PredictionMarketEventsProvider(prediction_path, required=True).fetch_events(start, end)
    assert len(ipo_events) == 1
    assert len(sports_events) == 2
    assert len(prediction_events) == 2
    assert ipo_events[0].provider == "external_ipo"
    assert ipo_events[0].raw_json["event"]["event_type"] == "ipo_proxy"
    assert ipo_events[0].raw_json["event"]["event_time_confidence"] == 0.45
    assert sports_events[0].raw_json["event"]["event_type"] == "sports_event"
    assert prediction_events[0].raw_json["event"]["event_type"] == "external_proxy_event"

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_external.json"
        bad_path.write_text(json.dumps({"events": ["not an object"]}), encoding="utf-8")
        assert ExternalIpoProvider(bad_path).fetch_events(start, end) == []
        try:
            ExternalIpoProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed external catalyst fixture should fail")


def test_event_discovery_prediction_market_live_provider_parses_polymarket_offline():
    import json
    from datetime import datetime, timezone
    from urllib.parse import parse_qs, urlparse
    from crypto_rsi_scanner.event_providers.prediction_market_events import PredictionMarketEventsProvider

    class FakeResponse:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    seen = {}

    def fake_opener(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["accept"] = request.headers.get("Accept")
        return FakeResponse([
            {
                "id": "pm-spacex",
                "slug": "will-spacex-launch-before-july",
                "title": "Will SpaceX launch Starship before July?",
                "description": "Prediction market attention around SpaceX.",
                "createdAt": "2026-06-15T08:00:00Z",
                "endDate": "2026-12-31T23:59:00Z",
                "volume24hr": 125000,
                "openInterest": 43000,
                "markets": [
                    {"endDate": "2026-06-20T23:59:00Z", "active": True, "closed": False},
                    {"endDate": "2026-06-18T23:59:00Z", "active": False, "closed": True},
                ],
            },
            {
                "id": "pm-old",
                "slug": "old-election-market",
                "title": "Will the old election result be certified?",
                "description": "Outside the requested event window.",
                "createdAt": "2026-06-01T08:00:00Z",
                "endDate": "2026-07-20T23:59:00Z",
            },
        ])

    start = datetime(2026, 6, 16, tzinfo=timezone.utc)
    end = datetime(2026, 6, 30, tzinfo=timezone.utc)
    fetched_at = datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc)
    provider = PredictionMarketEventsProvider(
        None,
        live_enabled=True,
        base_url="https://gamma.test/events",
        limit=7,
        timeout=3.5,
        opener=fake_opener,
        fetched_at=fetched_at,
    )
    events = provider.fetch_events(start, end)

    assert len(events) == 1
    parsed = urlparse(seen["url"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "gamma.test"
    assert params["active"] == ["true"]
    assert params["closed"] == ["false"]
    assert params["limit"] == ["7"]
    assert params["order"] == ["volume_24hr"]
    assert params["ascending"] == ["false"]
    assert seen["timeout"] == 3.5
    assert seen["accept"] == "application/json"

    event = events[0]
    assert event.provider == "prediction_market_events"
    assert event.fetched_at == fetched_at
    assert event.published_at.isoformat() == "2026-06-15T08:00:00+00:00"
    assert event.source_url == "https://polymarket.com/event/will-spacex-launch-before-july"
    assert event.raw_json["provider_source"] == "polymarket_gamma"
    assert event.raw_json["event"]["event_type"] == "external_proxy_event"
    assert event.raw_json["event"]["event_time"] == "2026-06-20T23:59:00+00:00"
    assert event.raw_json["event"]["event_time_confidence"] == 0.90
    assert event.raw_json["event"]["external_asset"] == "SpaceX"

    def failing_opener(request, timeout):
        raise TimeoutError("offline timeout")

    assert PredictionMarketEventsProvider(
        None,
        live_enabled=True,
        opener=failing_opener,
    ).fetch_events(start, end) == []


def test_event_discovery_prediction_market_external_asset_infers_generic_ipo_entity():
    import json
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_providers.prediction_market_events import PredictionMarketEventsProvider

    class FakeResponse:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def fake_opener(_request, _timeout):
        return FakeResponse([{
            "id": "cerebras-ipo",
            "slug": "will-cerebras-ipo-before-july",
            "title": "Will Cerebras IPO before July 31?",
            "description": "Prediction markets are tracking the Cerebras public debut.",
            "createdAt": "2026-06-15T08:00:00Z",
            "endDate": "2026-06-20T23:59:00Z",
        }])

    events = PredictionMarketEventsProvider(
        None,
        live_enabled=True,
        opener=fake_opener,
        fetched_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
    ).fetch_events(
        datetime(2026, 6, 16, tzinfo=timezone.utc),
        datetime(2026, 6, 30, tzinfo=timezone.utc),
    )

    assert len(events) == 1
    assert events[0].raw_json["event"]["event_type"] == "ipo_proxy"
    assert events[0].raw_json["event"]["external_asset"] == "Cerebras"
    assert events[0].source_url == "https://polymarket.com/event/will-cerebras-ipo-before-july"


def test_event_discovery_external_catalysts_are_radar_first_and_link_narrowly():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

    _events_path, aliases_path = _event_discovery_fixture_paths()
    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = event_discovery.load_discovery_events(
        None,
        start,
        end,
        external_ipo_path=ipo_path,
        sports_fixtures_path=sports_path,
        prediction_market_events_path=prediction_path,
    )
    assets = load_asset_aliases(aliases_path)
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert len(raw) == 5
    event_names = {event.event_name for event in result.normalized_events}
    assert "SpaceX IPO calendar placeholder" in event_names
    assert "Test FC vs Rival FC" in event_names
    assert "Will the Example City election result be certified today?" in event_names

    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert set(by_symbol) == {"TESTFAN", "TESTPRED"}

    fan = by_symbol["TESTFAN"]
    assert fan.classification.is_proxy_narrative is True
    assert fan.event.event_type == "sports_event"
    assert fan.fade_signal.signal_type == FadeSignalType.NO_TRADE

    pred = by_symbol["TESTPRED"]
    assert pred.classification.is_proxy_narrative is True
    assert pred.event.event_type == "external_proxy_event"
    assert pred.fade_candidate.component_scores["pre_event_pump"] >= 60
    assert pred.fade_signal.signal_type in {FadeSignalType.NO_TRADE, FadeSignalType.WATCHLIST}


def test_event_discovery_pipeline_and_event_fade_safety():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType

    result = _event_discovery_fixture_result()
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert len(result.raw_events) == 6
    assert len(result.normalized_events) == 5
    assert "COLLIDE" not in by_symbol

    velvet = by_symbol["TESTVELVET"]
    assert velvet.classification.is_proxy_narrative is True
    assert velvet.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED

    btc = by_symbol["TESTBTC"]
    assert btc.classification.is_direct_beneficiary is True
    assert btc.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert btc.fade_candidate.state.value == "DISCOVERED"

    listing = by_symbol["TESTTOKEN"]
    assert listing.classification.relationship_type == "direct_listing"
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    ambiguous = by_symbol["TESTPUMP"]
    assert ambiguous.classification.relationship_type == "ambiguous"
    assert ambiguous.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert ambiguous.data_quality["classifier_pass"] is False

    report = event_discovery.format_discovery_report(result)
    assert "EVENT DISCOVERY REPORT" in report
    assert "EVENT RADAR" in report
    assert "TESTVELVET" in report
    assert "TESTBTC" in report
