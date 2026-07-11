"""Catalyst-search identity, provider-cache, enrichment, and pipeline regressions."""

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


def test_event_catalyst_search_cryptopanic_uses_symbol_and_coin_currency_filters():
    import json
    from datetime import datetime, timezone
    from urllib.parse import parse_qs, urlparse
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search

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
        return FakeResponse({"results": []})

    provider = event_catalyst_search.CryptoPanicCatalystSearchProvider(
        live_enabled=True,
        api_token="token123",
        base_url="https://cryptopanic.test/api/growth_weekly/v2",
        opener=fake_opener,
        min_seconds_between_requests=0,
    )
    result = provider.search(
        (
            event_catalyst_search.SearchQuery(
                anomaly_raw_id="hyp:rune",
                query="RUNE exploit official update",
                symbol="RUNE",
                coin_id="thorchain",
                aliases=("RUNE", "thorchain"),
                rank=1,
            ),
        ),
        max_results_per_query=1,
        now=datetime(2026, 6, 15, 12, tzinfo=timezone.utc),
    )

    params = parse_qs(urlparse(seen["url"]).query)
    assert urlparse(seen["url"]).path == "/api/growth_weekly/v2/posts/"
    assert params["currencies"] == ["RUNE"]
    assert params["kind"] == ["news"]
    assert params["public"] == ["true"]
    assert "search" not in params
    assert "size" not in params
    assert "last_pull" not in params
    assert "with_content" not in params
    assert seen["timeout"] == 10.0
    assert result.query_count == 1
    assert result.result_count == 0


def test_event_catalyst_search_scaffold_attaches_evidence_without_bypassing_discovery():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.anomaly_scanner as event_anomaly_scanner
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    rows = [{
        "id": "pump-protocol",
        "symbol": "pump",
        "name": "Pump Protocol",
        "current_price": 1.4,
        "market_cap": 100000000.0,
        "total_volume": 60000000.0,
        "price_change_percentage_24h_in_currency": 45.0,
        "price_change_percentage_7d_in_currency": 120.0,
        "volume_zscore_24h": 4.5,
    }]
    anomaly = event_anomaly_scanner.discover_market_anomalies(
        rows,
        cfg=event_anomaly_scanner.EventAnomalyScannerConfig(
            enabled=True,
            min_return_24h=0.30,
            min_volume_mcap=0.25,
            min_volume_zscore=3.0,
        ),
        now=now,
    )[0]
    queries = event_catalyst_search.generate_search_queries_for_anomaly(anomaly)
    assert "PUMP crypto why up" in queries
    assert "PUMP Binance listing" in queries
    assert "PUMP SpaceX exposure" in queries

    asset = DiscoveredAsset(
        coin_id="pump-protocol",
        symbol="PUMP",
        name="Pump Protocol",
        aliases=("pump protocol", "pump"),
    )
    market_by_asset = event_market_enrichment.market_snapshots_from_rows(rows, now=now)
    no_evidence_rows = event_catalyst_search.attach_search_results_to_anomaly(anomaly, ())
    no_evidence_result = event_discovery.run_discovery(
        no_evidence_rows,
        [asset],
        now=now,
        market_by_asset=market_by_asset,
    )
    no_evidence_alert = event_alerts.build_event_alert_candidates(no_evidence_result, now=now)[0]
    assert no_evidence_alert.playbook_type == event_playbooks.EventPlaybookType.MARKET_ANOMALY_UNKNOWN.value
    assert no_evidence_alert.tier in {
        event_alerts.EventAlertTier.STORE_ONLY,
        event_alerts.EventAlertTier.RADAR_DIGEST,
    }
    assert no_evidence_alert.tier != event_alerts.EventAlertTier.WATCHLIST

    listing_raw = RawDiscoveredEvent(
        raw_id="pump-binance-listing",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pump-binance-listing",
        title="Binance will list Pump Protocol (PUMP)",
        body="Binance will list Pump Protocol spot trading pairs today.",
        raw_json={
            "event": {
                "event_id": "pump-binance-listing",
                "event_name": "Binance will list Pump Protocol (PUMP)",
                "event_type": "exchange_listing",
                "event_time": "2026-06-18T20:00:00Z",
                "event_time_confidence": 0.95,
                "external_asset": None,
                "confidence": 0.90,
                "description": "Binance will list Pump Protocol spot trading pairs today.",
            }
        },
        source_confidence=0.90,
        content_hash="pump-binance-listing",
    )
    attached_rows = event_catalyst_search.attach_search_results_to_anomaly(anomaly, (listing_raw,))
    assert attached_rows[1].raw_json["market_anomaly_catalyst_search"]["role"] == "attached_source_evidence"
    with_evidence_result = event_discovery.run_discovery(
        attached_rows,
        [asset],
        now=now,
        market_by_asset=market_by_asset,
    )
    listing_alert = next(
        alert for alert in event_alerts.build_event_alert_candidates(with_evidence_result, now=now)
        if alert.discovery_candidate.event.event_id == "pump-binance-listing"
    )
    assert listing_alert.playbook_type == event_playbooks.EventPlaybookType.LISTING_VOLATILITY.value
    assert listing_alert.tier in {
        event_alerts.EventAlertTier.WATCHLIST,
        event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH,
    }
    assert listing_alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE


def test_event_catalyst_search_skip_reasons_flow_to_ledger_and_brief():
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def anomaly(raw_id="market_anomaly:pump:2026-06-18", score=90.0, symbol="PUMP"):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="market_anomaly",
            fetched_at=now,
            published_at=now,
            source_url=None,
            title=f"{symbol} market anomaly",
            body=None,
            raw_json={
                "symbol": symbol,
                "market": {"symbol": symbol, "coin_id": "pump-protocol", "name": "Pump Protocol"},
                "anomaly": {"score": score, "return_24h": 0.45},
            },
            source_confidence=0.70,
            content_hash=raw_id,
        )

    low = anomaly(raw_id="market_anomaly:low:2026-06-18", score=25.0, symbol="LOW")
    cfg = event_catalyst_search.EventCatalystSearchConfig(
        enabled=True,
        min_anomaly_score=60,
        max_queries_per_anomaly=4,
    )
    low_result = event_catalyst_search.run_catalyst_search(
        [low],
        event_catalyst_search.FixtureCatalystSearchProvider({}),
        cfg=cfg,
        now=now,
    )
    assert low_result.queries == ()
    assert low_result.skip_reasons["no_anomalies_over_threshold"] == 1

    high = anomaly()

    def loader(observed, raw_event_transform):
        raw_events = (high,)
        if raw_event_transform:
            raw_events = tuple(raw_event_transform(raw_events))
        return event_discovery.run_discovery(raw_events, [], now=observed)

    no_provider = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=loader,
        now=now,
        catalyst_search_provider=None,
        catalyst_search_cfg=cfg,
        refresh_watchlist=False,
        route=False,
    )
    assert no_provider.catalyst_search_skip_reasons["provider_unavailable"] == 1
    assert no_provider.catalyst_queries == 0

    class BackoffProvider:
        name = "backoff"

        def search(self, queries, *, max_results_per_query, now=None):
            queries = tuple(queries)
            return event_catalyst_search.CatalystSearchRunResult(
                provider=self.name,
                queries=queries,
                warnings=("provider in backoff until later",),
                query_count=len(queries),
            )

    backoff = event_catalyst_search.run_catalyst_search([high], BackoffProvider(), cfg=cfg, now=now)
    assert backoff.queries
    assert backoff.skip_reasons["provider_backoff"] == 1

    with tempfile.TemporaryDirectory() as tmp:
        row = event_alpha_run_ledger.append_run_record(
            replace(
                no_provider,
                cryptopanic_configured=True,
                cryptopanic_attempted=True,
                cryptopanic_requests_used=2,
                cryptopanic_results=3,
                cryptopanic_accepted_evidence=1,
                cryptopanic_rejected_evidence=2,
                cryptopanic_provider_status="healthy",
            ),
            cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(Path(tmp) / "runs.jsonl"),
            profile="fixture",
            started_at=now,
            finished_at=now,
            with_llm=False,
            send_requested=False,
        )
        assert row["catalyst_search_skip_reasons"]["provider_unavailable"] == 1
        assert row["cryptopanic_configured"] is True
        assert row["cryptopanic_attempted"] is True
        assert row["cryptopanic_requests_used"] == 2
        assert row["cryptopanic_results"] == 3
        assert row["cryptopanic_accepted_evidence"] == 1
        assert row["cryptopanic_rejected_evidence"] == 2
        assert row["cryptopanic_provider_status"] == "healthy"
        runs_report = event_alpha_run_ledger.format_run_ledger_report(
            event_alpha_run_ledger.EventAlphaRunLedgerReadResult(
                path=Path(tmp) / "runs.jsonl",
                rows_read=1,
                rows=[row],
            )
        )
        assert "catalyst_search_skip_reasons: provider_unavailable=1" in runs_report
        assert "cryptopanic configured=true attempted=true requests=2 results=3 accepted=1 rejected=2 status=healthy skip=none" in runs_report
        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[row],
            include_test_artifacts=True,
            include_api_artifacts=True,
        )
        assert "## Catalyst Search Skip Reasons" in brief
        assert "- provider_unavailable: 1" in brief


def test_event_catalyst_search_proxy_evidence_still_requires_deterministic_validation():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:pumpx:2026-06-18",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="PUMPX market anomaly: 24h return 95%",
        body="No dated external catalyst has been validated.",
        raw_json={
            "event": {
                "event_id": "market_anomaly:pumpx:2026-06-18",
                "event_name": "PUMPX market anomaly",
                "event_type": "market_anomaly",
                "event_time": None,
                "event_time_confidence": 0.0,
                "confidence": 0.60,
                "description": "No dated external catalyst has been validated.",
            },
            "market": {"symbol": "PUMPX", "coin_id": "pumpx", "return_24h": 0.95, "volume_zscore_24h": 5.0},
            "anomaly": {"score": 95, "reasons": ["24h return 95%"]},
        },
        source_confidence=0.55,
        content_hash="anomaly-pumpx",
    )
    proxy_raw = RawDiscoveredEvent(
        raw_id="pumpx-openai-proxy",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pumpx-openai",
        title="PumpX launches OpenAI pre-IPO exposure market",
        body="PumpX token holders can use the PUMPX venue for OpenAI pre-IPO exposure.",
        raw_json={
            "event": {
                "event_id": "pumpx-openai-proxy",
                "event_name": "PumpX launches OpenAI pre-IPO exposure market",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.90,
                "external_asset": "OpenAI",
                "confidence": 0.90,
                "description": "PumpX token holders can use the PUMPX venue for OpenAI pre-IPO exposure.",
            }
        },
        source_confidence=0.90,
        content_hash="pumpx-openai-proxy",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider({"PUMPX OpenAI exposure": (proxy_raw,)})
    cfg = event_catalyst_search.EventCatalystSearchConfig(
        enabled=True,
        max_anomalies=1,
        max_queries_per_anomaly=6,
        max_results_per_query=1,
        min_anomaly_score=60,
    )

    def loader_without_asset(observed, raw_event_transform):
        raw_events = tuple(raw_event_transform((anomaly,))) if raw_event_transform else (anomaly,)
        return event_discovery.run_discovery(raw_events, [], now=observed)

    no_asset = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=loader_without_asset,
        now=now,
        catalyst_search_provider=provider,
        catalyst_search_cfg=cfg,
        refresh_watchlist=False,
        route=False,
    )
    assert no_asset.candidates == 0

    asset = DiscoveredAsset(coin_id="pumpx", symbol="PUMPX", name="PumpX", aliases=("pumpx",))

    def loader_with_asset(observed, raw_event_transform):
        raw_events = tuple(raw_event_transform((anomaly,))) if raw_event_transform else (anomaly,)
        return event_discovery.run_discovery(raw_events, [asset], now=observed)

    with_asset = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=loader_with_asset,
        alert_cfg=event_alerts.EventAlertConfig(),
        now=now,
        catalyst_search_provider=provider,
        catalyst_search_cfg=cfg,
        refresh_watchlist=False,
        route=False,
    )
    proxy_alert = next(
        alert for alert in with_asset.alerts
        if alert.discovery_candidate.event.event_id == "pumpx-openai-proxy"
    )
    assert proxy_alert.playbook_type in {
        event_playbooks.EventPlaybookType.PROXY_FADE.value,
        event_playbooks.EventPlaybookType.AI_IPO_PROXY.value,
        event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
    }
    assert proxy_alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE


def test_event_catalyst_search_requires_identity_before_attaching_catalyst_terms():
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
        title="PUMP market anomaly",
        body="No catalyst validated.",
        raw_json={
            "market": {
                "symbol": "PUMP",
                "coin_id": "pump-fun",
                "name": "Pump.fun",
                "aliases": ["Pump.fun", "Pump Protocol"],
            },
            "anomaly": {"score": 95},
        },
        source_confidence=0.55,
        content_hash="anomaly-pump",
    )
    unrelated = RawDiscoveredEvent(
        raw_id="other-listing",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/other",
        title="Binance will list Other Protocol (OTHER)",
        body="Binance listing catalyst for Other only.",
        raw_json={"event": {"event_type": "exchange_listing", "event_time": "2026-06-18T20:00:00Z"}},
        source_confidence=0.95,
        content_hash="other-listing",
    )
    alias = RawDiscoveredEvent(
        raw_id="pump-alias",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pump",
        title="Pump.fun confirms PUMPUSDT perp listing",
        body="Pump.fun will launch PUMPUSDT futures trading.",
        raw_json={"event": {"event_type": "perp_listing", "event_time": "2026-06-18T20:00:00Z"}},
        source_confidence=0.95,
        content_hash="pump-alias",
    )
    query = event_catalyst_search.generate_search_query_objects_for_anomaly(anomaly, max_queries=20)[0]
    unrelated_score = event_catalyst_search.score_search_result(unrelated, query, anomaly, now=now)
    alias_score = event_catalyst_search.score_search_result(alias, query, anomaly, now=now)
    assert "identity_missing_cap" in unrelated_score.reason_codes
    assert unrelated_score.score < 50
    assert any(
        reason in alias_score.reason_codes
        for reason in ("identity_match_alias", "identity_match_pair", "identity_match_project")
    )
    assert alias_score.score >= 50


def test_event_catalyst_search_rejects_common_word_symbol_without_strong_identity():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:hype:2026-06-18",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="HYPE market anomaly",
        body="No catalyst validated.",
        raw_json={"market": {"symbol": "HYPE", "coin_id": "hyperliquid", "name": "Hyperliquid"}, "anomaly": {"score": 95}},
        source_confidence=0.55,
        content_hash="anomaly-hype",
    )
    generic = RawDiscoveredEvent(
        raw_id="ipo-hype",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/hype",
        title="IPO hype builds around Stripe",
        body="A story about IPO hype and prediction markets for private companies.",
        raw_json={},
        source_confidence=0.90,
        content_hash="ipo-hype",
    )
    query = event_catalyst_search.generate_search_query_objects_for_anomaly(anomaly, max_queries=1)[0]
    score = event_catalyst_search.score_search_result(generic, query, anomaly, now=now)
    assert "common_word_identity_rejected" in score.reason_codes
    assert score.score < 50


def test_event_catalyst_search_single_character_symbol_requires_project_identity():
    import re
    from datetime import datetime, timezone
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 7, 11, 4, 0, tzinfo=timezone.utc)
    anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:b:2026-07-11",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="B market anomaly",
        body="No catalyst validated.",
        raw_json={
            "market": {
                "symbol": "B",
                "coin_id": "build-on",
                "name": "Build On",
                "aliases": ("A", "AI", "Build Ecosystem"),
            },
            "anomaly": {"score": 61},
        },
        source_confidence=0.55,
        content_hash="anomaly-b",
    )
    queries = event_catalyst_search.generate_search_query_objects_for_anomaly(anomaly, max_queries=2)
    assert queries[0].query == "Build On crypto why up"
    assert queries[0].is_common_word_symbol is True
    all_anomaly_queries = event_catalyst_search.generate_search_queries_for_anomaly(anomaly)
    assert "A crypto catalyst" not in all_anomaly_queries
    assert "AI crypto catalyst" not in all_anomaly_queries
    assert "Build Ecosystem crypto catalyst" in all_anomaly_queries

    no_name = RawDiscoveredEvent(
        raw_id="market_anomaly:build-on:2026-07-11",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="B market anomaly",
        body="No catalyst validated.",
        raw_json={"market": {"symbol": "B", "coin_id": "build-on"}, "anomaly": {"score": 61}},
        source_confidence=0.55,
        content_hash="anomaly-b-no-name",
    )
    no_name_queries = event_catalyst_search.generate_search_query_objects_for_anomaly(no_name, max_queries=6)
    assert len(no_name_queries) == 6
    assert all(query.query.startswith("Build On ") for query in no_name_queries)
    assert not any(re.search(r"(?<![A-Za-z0-9])B(?![A-Za-z0-9])", query.query) for query in no_name_queries)

    bitcoin_noise = RawDiscoveredEvent(
        raw_id="bitcoin-noise",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/bitcoin",
        title="B crypto market recap: Bitcoin returns to recent highs",
        body="Bitcoin-backed lending grows while crypto markets recover.",
        raw_json={},
        source_confidence=0.90,
        content_hash="bitcoin-noise",
    )
    score = event_catalyst_search.score_search_result(bitcoin_noise, queries[0], anomaly, now=now)
    assert "common_word_identity_rejected" in score.reason_codes
    assert score.score < 50

    project_result = RawDiscoveredEvent(
        raw_id="build-on-project",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/build-on",
        title="Build On announces a dated ecosystem catalyst",
        body="The Build On project published the update.",
        raw_json={},
        source_confidence=0.90,
        content_hash="build-on-project",
    )
    project_score = event_catalyst_search.score_search_result(project_result, queries[0], anomaly, now=now)
    assert "identity_match_project" in project_score.reason_codes
    assert project_score.score >= 50

    hypothesis_specs = event_catalyst_search.generate_search_query_specs_for_hypothesis(
        SimpleNamespace(
            impact_category="market_anomaly_unknown",
            external_asset="",
            candidate_symbols=("B",),
            candidate_coin_ids=("build-on",),
            candidate_sectors=(),
        )
    )
    assert [spec.query for spec in hypothesis_specs] == ["Build On crypto catalyst"]
    assert all(not spec.query.startswith("B ") for spec in hypothesis_specs)

    bare_name = SimpleNamespace(
        impact_category="market_anomaly_unknown",
        external_asset="",
        candidate_symbols=("B",),
        candidate_coin_ids=(),
        candidate_sectors=(),
        crypto_candidate_assets=({"symbol": "B", "name": "B"},),
    )
    assert event_catalyst_search.generate_search_query_specs_for_hypothesis(bare_name) == ()

    for symbol, collision_label in (("B", "A"), ("HYPE", "AI")):
        collision_name = SimpleNamespace(
            impact_category="market_anomaly_unknown",
            external_asset="",
            candidate_symbols=(symbol,),
            candidate_coin_ids=(),
            candidate_sectors=(),
            crypto_candidate_assets=({"symbol": symbol, "name": collision_label},),
        )
        assert event_catalyst_search.generate_search_query_specs_for_hypothesis(
            collision_name
        ) == ()

    bare_anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:b-bare:2026-07-11",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="B market anomaly",
        body="No catalyst validated.",
        raw_json={"market": {"symbol": "B", "name": "B"}, "anomaly": {"score": 61}},
        source_confidence=0.55,
        content_hash="anomaly-b-bare-name",
    )
    assert event_catalyst_search.generate_search_queries_for_anomaly(bare_anomaly) == ()

    bare_name_with_coin = RawDiscoveredEvent(
        raw_id="market_anomaly:b-bare-with-coin:2026-07-11",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="B market anomaly",
        body="No catalyst validated.",
        raw_json={
            "market": {"symbol": "B", "name": "B", "coin_id": "build-on"},
            "anomaly": {"score": 61},
        },
        source_confidence=0.55,
        content_hash="anomaly-b-bare-name-with-coin",
    )
    safe_coin_queries = event_catalyst_search.generate_search_queries_for_anomaly(
        bare_name_with_coin
    )
    assert safe_coin_queries
    assert all(not query.startswith("B ") for query in safe_coin_queries)


def test_hypothesis_query_identity_preserves_multi_asset_symbol_coin_pairing():
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_alpha.radar.catalyst_search import query_builder

    paired = SimpleNamespace(
        hypothesis_id="hyp-a-b",
        impact_category="market_anomaly_unknown",
        external_asset="",
        candidate_symbols=("A", "B"),
        candidate_coin_ids=("build-on",),
        candidate_sectors=(),
        crypto_candidate_assets=(
            {
                "symbol": "A",
                "coin_id": "alpha",
                "name": "Alpha",
                "aliases": ("A",),
                "source": "deterministic_resolver",
            },
            {
                "symbol": "B",
                "coin_id": "build-on",
                "name": "Build On",
                "aliases": ("B",),
                "source": "deterministic_resolver",
            },
        ),
        confidence=0.80,
        status="hypothesis",
    )
    specs = event_catalyst_search.generate_search_query_specs_for_hypothesis(paired)
    queries = query_builder._queries_for_hypotheses(
        (paired,),
        event_catalyst_search.EventImpactHypothesisSearchConfig(
            max_queries_per_hypothesis=4,
            candidate_discovery_enabled=False,
        ),
    )

    assert [spec.query for spec in specs] == ["Alpha crypto catalyst", "Build On crypto catalyst"]
    assert [(query.query, query.symbol, query.coin_id) for query in queries] == [
        ("Alpha crypto catalyst", "A", "alpha"),
        ("Build On crypto catalyst", "B", "build-on"),
    ]
    assert query_builder._hypothesis_query_identities(
        paired,
        ("A unrelated discovery text",),
    ) == {}

    ambiguous = SimpleNamespace(
        impact_category="market_anomaly_unknown",
        external_asset="",
        candidate_symbols=("A", "B"),
        candidate_coin_ids=("build-on",),
        candidate_sectors=(),
    )
    assert event_catalyst_search.generate_search_query_specs_for_hypothesis(ambiguous) == ()


def test_event_catalyst_search_identity_can_come_from_resolver_validated_llm_extraction():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="stealth-source",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/stealth",
        title="New protocol launches OpenAI pre-IPO exposure",
        body="A venue launches OpenAI pre-IPO exposure.",
        raw_json={
            "llm_extraction": {
                "crypto_asset_mentions": [
                    {
                        "name": "Stealth Alpha",
                        "symbol": "STEALTH",
                        "coin_id": "stealth-alpha",
                        "confidence": 0.91,
                        "resolver_validated": True,
                        "mention_type": "project_or_token",
                    }
                ]
            }
        },
        source_confidence=0.85,
        content_hash="stealth-source",
    )
    query = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:stealth-alpha:2026-06-18",
        query="STEALTH OpenAI exposure",
        symbol="STEALTH",
        rank=1,
        coin_id="stealth-alpha",
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(raw, query, None) is True


def test_event_catalyst_search_identity_field_safety_rejects_url_and_source_noise():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, *, title="", body="", source_url=None, provider="fixture_search_result", raw_json=None):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=source_url,
            title=title,
            body=body,
            raw_json=raw_json or {},
            source_confidence=0.85,
            content_hash=raw_id,
        )

    pump_query = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:pump:2026-06-18",
        query="PUMP Binance listing",
        symbol="PUMP",
        rank=1,
        coin_id="pump-token",
    )
    url_only = raw(
        "url-only",
        title="Exchange listing roundup",
        body="A listing roundup mentions other tokens.",
        source_url="https://example.test/search?q=PUMPUSDT",
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(url_only, pump_query, None) is False
    score = event_catalyst_search.score_search_result(url_only, pump_query, now=now)
    assert "identity_url_only_rejected" in score.reason_codes

    body_pair = raw(
        "body-pair",
        title="Binance lists a new perp",
        body="Binance confirms PUMPUSDT perpetual trading starts today.",
        source_url="https://example.test/news/listing",
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(body_pair, pump_query, None) is True
    assert "identity_match_pair" in event_catalyst_search.score_search_result(body_pair, pump_query, now=now).reason_codes

    btc_query = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:bitcoin:2026-06-18",
        query="BTC catalyst",
        symbol="BTC",
        rank=1,
        coin_id="bitcoin",
    )
    publisher = raw(
        "publisher",
        title="SpaceX pre-IPO markets expand",
        body="The article is about SpaceX exposure.",
        source_url="https://bitcoinworld.example/news/spacex",
        raw_json={"source_origin": "Bitcoin World"},
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(publisher, btc_query, None) is False
    assert "identity_source_origin_rejected" in event_catalyst_search.score_search_result(publisher, btc_query, now=now).reason_codes

    address = "0x1234567890abcdef1234567890abcdef12345678"
    contract_query = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:contract-token:2026-06-18",
        query="CONTRACT catalyst",
        symbol="CONTRACT",
        rank=1,
        contract_addresses=(address,),
    )
    path_contract = raw(
        "contract-path",
        title="Protocol update",
        body="Contract details published.",
        source_url=f"https://etherscan.io/token/{address}",
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(path_contract, contract_query, None) is True

    query_contract = raw(
        "contract-query",
        title="Protocol update",
        body="Contract details published.",
        source_url=f"https://example.test/search?contract={address}",
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(query_contract, contract_query, None) is False
    assert "identity_url_only_rejected" in event_catalyst_search.score_search_result(query_contract, contract_query, now=now).reason_codes


def test_event_catalyst_search_provider_cache_fetches_broad_sources_once():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    article = {
        "id": "pump-rss",
        "title": "Pump.fun confirms PUMPUSDT perp listing",
        "body": "Pump.fun will launch PUMPUSDT futures trading.",
        "published_at": now.isoformat(),
        "fetched_at": now.isoformat(),
        "url": "https://example.test/pump-rss",
        "source_confidence": 0.90,
    }
    queries = tuple(
        event_catalyst_search.SearchQuery(
            anomaly_raw_id=f"market_anomaly:pump:{idx}",
            query=f"PUMP catalyst {idx}",
            symbol="PUMP",
            rank=idx,
            coin_id="pump-fun",
            project_name="Pump.fun",
            aliases=("Pump.fun",),
        )
        for idx in range(10)
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rss.json"
        path.write_text(json.dumps({"articles": [article]}), encoding="utf-8")
        provider = event_catalyst_search.ProjectRssCatalystSearchProvider(path=path)
        result = provider.search(queries, max_results_per_query=1, now=now)
        assert result.provider_fetch_count == 1
        assert result.provider_cache_misses == 1
        assert result.provider_cache_hits == 9
        assert result.query_count == 10


def test_event_source_enrichment_extracts_and_reuses_cache():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="article",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://news.example/article",
        title="SpaceX pre-IPO exposure",
        body="Short RSS summary.",
        raw_json={},
        source_confidence=0.9,
        content_hash="article",
    )
    html = """
    <html><head><style>.x{}</style><script>ignore()</script></head>
    <body><nav>Home Markets Prices News Learn Newsletter</nav>
    <div>BTC $104000 +2.1% ETH $2500 -1.0% SOL $150 +4.4%</div>
    <article><h1>SpaceX pre-IPO exposure</h1>
    <p>Velvet Capital is named in the full article, but not the RSS summary.</p>
    <p>Hyperliquid HYPE token traders are watching the proxy venue.</p>
    <p>The article explains the candidate asset, the external SpaceX catalyst,
    and the direct proxy mechanism clearly enough to pass source-quality gating.</p>
    <p>This extra body copy keeps the synthetic fixture above the thin article
    threshold while preserving the expected article text.</p></article></body></html>
    """
    calls = {"count": 0}

    def fetch(url, timeout):
        calls["count"] += 1
        assert url == "https://news.example/article"
        assert timeout == 2
        return html

    with tempfile.TemporaryDirectory() as tmp:
        cfg = event_source_enrichment.EventSourceEnrichmentConfig(
            enabled=True,
            cache_dir=Path(tmp),
            timeout_seconds=2,
        )
        first = event_source_enrichment.enrich_source_text(raw, cfg=cfg, fetch_fn=fetch)
        second = event_source_enrichment.enrich_source_text(raw, cfg=cfg, fetch_fn=lambda *_: (_ for _ in ()).throw(RuntimeError("should not fetch")))
        assert first.fetched is True
        assert "Velvet Capital is named" in first.enriched_text
        assert "Hyperliquid HYPE token traders" in first.enriched_text
        assert "Home Markets Prices" not in first.enriched_text
        assert "BTC $104000" not in first.enriched_text
        assert second.used_cache is True
        assert "Velvet Capital is named" in second.enriched_text
        assert "Hyperliquid HYPE token traders" in second.enriched_text
        assert calls["count"] == 1
        refreshed = event_source_enrichment.enrich_source_text(
            raw,
            cfg=event_source_enrichment.EventSourceEnrichmentConfig(
                enabled=True,
                cache_dir=Path(tmp),
                timeout_seconds=2,
                cleaner_version="source_enrichment_cleaner_v999",
            ),
            fetch_fn=fetch,
        )
        assert refreshed.fetched is True
        assert calls["count"] == 2
        annotated = event_source_enrichment.annotate_raw_event_with_enrichment(first)
        packet = event_llm_extractor.build_raw_event_packet(annotated)
        assert "Velvet Capital is named" in packet["body"]

    failed = event_source_enrichment.enrich_source_text(
        raw,
        cfg=event_source_enrichment.EventSourceEnrichmentConfig(enabled=True),
        fetch_fn=lambda *_: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    assert failed.warning == "source enrichment failed: RuntimeError"
    assert "Short RSS summary" in failed.enriched_text


def test_event_source_enrichment_uses_fixture_text_for_example_test_urls():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="fixture_article",
        provider="fixture_rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/article?fixture=VELVET",
        title="SpaceX pre-IPO exposure",
        body="Fixture body mentions Velvet Capital and SpaceX pre-IPO exposure.",
        raw_json={},
        source_confidence=0.9,
        content_hash="fixture_article",
    )

    result = event_source_enrichment.enrich_source_text(
        raw,
        cfg=event_source_enrichment.EventSourceEnrichmentConfig(enabled=True),
        fetch_fn=lambda *_: (_ for _ in ()).throw(RuntimeError("should not fetch fixture URL")),
    )

    assert result.status == "fixture_text_used"
    assert result.fetched is False
    assert "Velvet Capital" in result.enriched_text
    annotated = event_source_enrichment.annotate_raw_event_with_enrichment(result)
    assert annotated.raw_json["source_enrichment"]["status"] == "fixture_text_used"


def test_event_alpha_pipeline_source_enrichment_runs_before_llm_extraction():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="source-enrich-before-llm",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://news.example/enrich",
        title="SpaceX pre-IPO exposure opens",
        body="Short summary without the asset name.",
        raw_json={},
        source_confidence=0.90,
        content_hash="source-enrich-before-llm",
    )
    seen = {"body": ""}

    class Provider:
        name = "fixture"

        def extract_raw_event(self, packet):
            seen["body"] = packet["body"]
            return LLMProviderResult(raw={
                "confidence": 0.90,
                "external_catalysts": [{
                    "name": "SpaceX",
                    "catalyst_type": "ipo_proxy",
                    "event_time": None,
                    "event_time_confidence": 0.0,
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "SpaceX pre-IPO exposure", "source_field": "body", "supports": "external catalyst"}],
                }],
                "crypto_asset_mentions": [{
                    "name": "Velvet Capital",
                    "symbol": "VELVET",
                    "coin_id": "velvet",
                    "contract_address": None,
                    "mention_type": "project_or_token",
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "Velvet Capital users", "source_field": "body", "supports": "asset mention"}],
                }],
                "false_positive_terms": [],
                "event_date_hints": [],
                "suggested_followup_queries": [],
                "warnings": [],
            })

    def loader(observed, raw_event_transform):
        transformed = tuple(raw_event_transform((raw,))) if raw_event_transform else (raw,)
        return EventDiscoveryResult(
            raw_events=transformed,
            normalized_events=(),
            links=(),
            classifications=(),
            candidates=(),
            warnings=(),
        )

    pipe = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=loader,
        now=now,
        with_llm=True,
        extraction_provider=Provider(),
        extraction_cfg=event_llm_extractor.EventLLMExtractorConfig(mode="shadow", provider="fixture"),
        source_enrichment_cfg=event_source_enrichment.EventSourceEnrichmentConfig(
            enabled=True,
            max_chars=1000,
            min_source_confidence=0.50,
        ),
        source_enrichment_fetch_fn=lambda url, timeout: (
            "<html><body><article>"
            "Velvet Capital users can trade SpaceX pre-IPO exposure through a tokenized venue. "
            "The source names Velvet Capital, the SpaceX pre-IPO catalyst, and the direct proxy mechanism. "
            "This additional paragraph keeps the fixture above the thin-page threshold while preserving "
            "the exact quote used by the offline LLM extraction fixture."
            "</article></body></html>"
        ),
        refresh_watchlist=False,
        route=False,
    )
    assert pipe.extractions == 1
    assert "Velvet Capital users" in seen["body"]
    assert "source enrichment: selected=1 fetched=1 cache_hits=0" in "; ".join(pipe.warnings)
