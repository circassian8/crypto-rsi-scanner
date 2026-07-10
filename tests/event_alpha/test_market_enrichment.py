"""Focused Event Alpha deterministic radar behavior tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_market_enrichment_from_coingecko_rows():
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
    from crypto_rsi_scanner.event_providers.coingecko_universe import load_market_rows

    rows = load_market_rows(Path("fixtures/coingecko_smoke/top_markets.json"))
    snapshots = event_market_enrichment.market_snapshots_from_rows(
        rows,
        now=datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc),
    )
    sol = snapshots["solana"]
    assert sol["symbol"] == "SOL"
    assert sol["price"] == 160.0
    assert sol["volume_24h"] == 4500000000.0
    assert abs(sol["return_24h"] - 0.034) < 1e-9
    assert abs(sol["return_7d"] - 0.092) < 1e-9
    assert abs(event_market_enrichment.volume_to_market_cap(rows[2]) - 0.06) < 1e-9


def test_event_market_enrichment_fills_candidates_without_overriding_raw_market():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="market-enriched-proxy",
        provider="test",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pumpx",
        title="PumpX token offers synthetic exposure to SpaceX pre-IPO market",
        body="PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
        raw_json={
            "event": {
                "event_id": "market-enriched-proxy",
                "event_name": "PumpX token offers synthetic exposure to SpaceX pre-IPO market",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-19T13:30:00Z",
                "event_time_confidence": 0.90,
                "external_asset": "SpaceX",
                "confidence": 0.90,
                "description": "PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
            }
        },
        source_confidence=0.90,
        content_hash="market-enriched-proxy",
    )
    asset = DiscoveredAsset(
        coin_id="pumpx",
        symbol="PUMPX",
        name="PumpX",
        aliases=("pumpx token", "PumpX"),
    )
    market_rows = [{
        "id": "pumpx",
        "symbol": "pumpx",
        "name": "PumpX",
        "current_price": 2.0,
        "market_cap": 100000000.0,
        "total_volume": 70000000.0,
        "price_change_percentage_24h_in_currency": 85.0,
        "price_change_percentage_7d_in_currency": 240.0,
        "volume_zscore_24h": 6.0,
    }]
    market = event_market_enrichment.market_snapshots_from_rows(market_rows, now=now)
    candidate = event_discovery.run_discovery(
        [raw],
        [asset],
        now=now,
        market_by_asset=market,
    ).candidates[0]
    assert candidate.fade_candidate is not None
    assert candidate.fade_candidate.market.return_24h == 0.85
    assert candidate.fade_candidate.market.volume_zscore_24h == 6.0

    raw_override = RawDiscoveredEvent(
        raw_id="market-raw-wins",
        provider="test",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pumpx-raw",
        title="PumpX token offers synthetic exposure to SpaceX pre-IPO market",
        body="PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
        raw_json={
            "event": raw.raw_json["event"],
            "market": {"coin_id": "pumpx", "symbol": "PUMPX", "price": 3.0, "return_24h": 0.10},
        },
        source_confidence=0.90,
        content_hash="market-raw-wins",
    )
    raw_candidate = event_discovery.run_discovery(
        [raw_override],
        [asset],
        now=now,
        market_by_asset=market,
    ).candidates[0]
    assert raw_candidate.fade_candidate is not None
    assert raw_candidate.fade_candidate.market.price == 3.0
    assert raw_candidate.fade_candidate.market.return_24h == 0.10


def test_event_anomaly_scanner_creates_store_only_research_rows():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.anomaly_scanner as event_anomaly_scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset

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
    anomalies = event_anomaly_scanner.discover_market_anomalies(
        rows,
        cfg=event_anomaly_scanner.EventAnomalyScannerConfig(
            enabled=True,
            min_return_24h=0.30,
            min_volume_mcap=0.25,
            min_volume_zscore=3.0,
        ),
        now=now,
    )
    assert len(anomalies) == 1
    assert anomalies[0].provider == "market_anomaly"
    assert anomalies[0].raw_json["event"]["event_type"] == "market_anomaly"
    assert anomalies[0].raw_json["market"]["return_24h"] == 0.45

    asset = DiscoveredAsset(
        coin_id="pump-protocol",
        symbol="PUMP",
        name="Pump Protocol",
        aliases=("pump protocol",),
    )
    result = event_discovery.run_discovery(
        anomalies,
        [asset],
        now=now,
        market_by_asset=event_market_enrichment.market_snapshots_from_rows(rows, now=now),
    )
    assert len(result.candidates) == 1
    alert = event_alerts.build_event_alert_candidates(result, cfg=event_alerts.EventAlertConfig(), now=now)[0]
    assert alert.tier == event_alerts.EventAlertTier.STORE_ONLY
    assert alert.playbook_type == "market_anomaly_unknown"
    assert alert.playbook_action == "store_only"
    assert alert.playbook_can_trigger_fade is False
    assert alert.expected_direction == "unknown"
    assert "catalyst is unknown" in alert.reason
    assert "find dated source evidence" in alert.verify
    assert "proxy instrument" not in "; ".join(alert.verify)
    assert "not a confirmed proxy narrative" in (alert.rejected_reason or "")
    assert "low classifier confidence" in (alert.rejected_reason or "")


def test_event_alpha_cycle_search_loop_uses_fixture_evidence_and_respects_limits():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.radar.anomaly_scanner as event_anomaly_scanner
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    rows = [
        {
            "id": "pump-protocol",
            "symbol": "pump",
            "name": "Pump Protocol",
            "current_price": 1.4,
            "market_cap": 100000000.0,
            "total_volume": 60000000.0,
            "price_change_percentage_24h_in_currency": 45.0,
            "price_change_percentage_7d_in_currency": 120.0,
            "volume_zscore_24h": 4.5,
        },
        {
            "id": "quiet-protocol",
            "symbol": "quiet",
            "name": "Quiet Protocol",
            "current_price": 2.0,
            "market_cap": 100000000.0,
            "total_volume": 1000000.0,
            "price_change_percentage_24h_in_currency": 1.0,
            "price_change_percentage_7d_in_currency": 10.0,
            "volume_zscore_24h": 1.0,
        },
    ]
    anomalies = event_anomaly_scanner.discover_market_anomalies(
        rows,
        cfg=event_anomaly_scanner.EventAnomalyScannerConfig(
            enabled=True,
            min_return_24h=0.03,
            min_volume_mcap=0.05,
            min_volume_zscore=3.0,
            max_assets=5,
        ),
        now=now,
    )
    assert [raw.raw_id for raw in anomalies] == ["market_anomaly:pump-protocol:2026-06-18"]
    listing_raw = RawDiscoveredEvent(
        raw_id="pump-binance-listing-dynamic",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pump-binance-listing",
        title="Binance will list Pump Protocol (PUMP)",
        body="Binance will list Pump Protocol spot trading pairs today.",
        raw_json={
            "event": {
                "event_id": "pump-binance-listing-dynamic",
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
        content_hash="pump-binance-listing-dynamic",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider({
        "PUMP Binance listing": (listing_raw,),
        "PUMP crypto why up": (),
    })
    cfg = event_catalyst_search.EventCatalystSearchConfig(
        enabled=True,
        max_anomalies=1,
        max_queries_per_anomaly=2,
        max_results_per_query=1,
        min_anomaly_score=60,
    )
    search_result = event_catalyst_search.run_catalyst_search(anomalies, provider, cfg=cfg, now=now)
    assert len(search_result.queries) == 2
    assert len(search_result.result_events) == 1
    assert len(search_result.attached_raw_events) == 2
    assert search_result.attached_raw_events[1].raw_id == "pump-binance-listing-dynamic"
    assert search_result.skip_reasons == {}

    asset = DiscoveredAsset(
        coin_id="pump-protocol",
        symbol="PUMP",
        name="Pump Protocol",
        aliases=("pump protocol", "pump"),
    )
    market_by_asset = event_market_enrichment.market_snapshots_from_rows(rows, now=now)

    def loader(observed, raw_event_transform):
        raw_events = tuple(anomalies)
        if raw_event_transform:
            raw_events = tuple(raw_event_transform(raw_events))
        return event_discovery.run_discovery(
            raw_events,
            [asset],
            now=observed,
            market_by_asset=market_by_asset,
        )

    pipeline_result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=loader,
        alert_cfg=event_alerts.EventAlertConfig(),
        now=now,
        catalyst_search_provider=provider,
        catalyst_search_cfg=cfg,
        refresh_watchlist=False,
        route=False,
    )
    assert pipeline_result.catalyst_queries == 2
    assert pipeline_result.catalyst_results == 1
    by_event = {alert.discovery_candidate.event.event_id: alert for alert in pipeline_result.alerts}
    assert by_event["market_anomaly:pump-protocol:2026-06-18"].playbook_type == (
        event_playbooks.EventPlaybookType.MARKET_ANOMALY_UNKNOWN.value
    )
    assert by_event["pump-binance-listing-dynamic"].playbook_type == (
        event_playbooks.EventPlaybookType.LISTING_VOLATILITY.value
    )
    assert by_event["pump-binance-listing-dynamic"].tier != event_alerts.EventAlertTier.TRIGGERED_FADE


def test_event_anomaly_lifecycle_tracks_found_validated_and_expired_states():
    from datetime import datetime, timedelta, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.anomaly_state as event_anomaly_state
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:pump:2026-06-18",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="PUMP market anomaly",
        body="No dated external catalyst has been validated.",
        raw_json={"market": {"symbol": "PUMP", "coin_id": "pump"}, "anomaly": {"score": 90}},
        source_confidence=0.55,
        content_hash="anomaly-pump",
    )
    listing = RawDiscoveredEvent(
        raw_id="pump-listing-lifecycle",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pump",
        title="Binance will list Pump Protocol (PUMP)",
        body="Binance will list Pump Protocol spot trading today.",
        raw_json={
            "event": {
                "event_id": "pump-listing-lifecycle",
                "event_name": "Binance will list Pump Protocol (PUMP)",
                "event_type": "exchange_listing",
                "event_time": "2026-06-18T20:00:00Z",
                "event_time_confidence": 0.95,
                "confidence": 0.90,
            }
        },
        source_confidence=0.90,
        content_hash="pump-listing-lifecycle",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider({"PUMP Binance listing": (listing,)})
    cfg = event_catalyst_search.EventCatalystSearchConfig(
        enabled=True,
        max_anomalies=1,
        max_queries_per_anomaly=2,
        max_results_per_query=1,
        min_anomaly_score=60,
    )
    search_result = event_catalyst_search.run_catalyst_search([anomaly], provider, cfg=cfg, now=now)
    rows = event_catalyst_search.attach_search_results_to_anomaly(anomaly, (listing,))
    discovery = event_discovery.run_discovery(
        rows,
        [DiscoveredAsset(coin_id="pump", symbol="PUMP", name="Pump Protocol", aliases=("pump protocol", "pump"))],
        now=now,
    )
    alerts = event_alerts.build_event_alert_candidates(discovery, now=now)
    lifecycle = event_anomaly_state.build_anomaly_lifecycle([anomaly], search_result, alerts, now=now)
    assert lifecycle.entries[0].state in {
        event_anomaly_state.EventAnomalyLifecycleState.PLAYBOOK_ASSIGNED.value,
        event_anomaly_state.EventAnomalyLifecycleState.ESCALATED.value,
    }
    assert lifecycle.entries[0].validated_catalyst_count == 1

    empty_search = event_catalyst_search.run_catalyst_search(
        [anomaly],
        event_catalyst_search.FixtureCatalystSearchProvider({"PUMP Binance listing": ()}),
        cfg=cfg,
        now=now,
    )
    expired = event_anomaly_state.build_anomaly_lifecycle(
        [anomaly],
        empty_search,
        [],
        now=now + timedelta(hours=25),
        expire_hours_no_catalyst=24,
    )
    assert expired.entries[0].state == event_anomaly_state.EventAnomalyLifecycleState.EXPIRED_NO_CATALYST.value
