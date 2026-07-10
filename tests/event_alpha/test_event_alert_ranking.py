"""Focused Event Alpha research-only behavior tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alerts_rank_proxy_candidates_without_human_review_fields():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent
    from crypto_rsi_scanner.event_providers.manual_json import content_hash

    def raw_proxy(raw_id, title, body, symbol, coin_id, external_asset, event_type="ipo_proxy"):
        payload = {
            "raw_id": raw_id,
            "title": title,
            "body": body,
            "event": {
                "event_id": raw_id,
                "event_name": title,
                "event_type": event_type,
                "event_time": None,
                "event_time_confidence": 0.0,
                "external_asset": external_asset,
                "confidence": 0.78,
                "description": body,
            },
            "market": {
                "symbol": symbol,
                "coin_id": coin_id,
                "timestamp": "2026-06-16T16:00:00Z",
                "price": 10.0,
                "market_cap": 100_000_000,
                "volume_24h": 120_000_000,
                "return_24h": 1.1,
                "return_72h": 2.2,
                "return_7d": 4.0,
                "volume_zscore_24h": 5.5,
            },
        }
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="test_news",
            fetched_at=datetime(2026, 6, 16, 13, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json=payload,
            source_confidence=0.78,
            content_hash=content_hash(payload),
        )

    assets = [
        DiscoveredAsset("hyperliquid", "HYPE", "Hyperliquid", aliases=("hyperliquid", "hype")),
        DiscoveredAsset("aster", "ASTER", "Aster", aliases=("aster", "aster token")),
        DiscoveredAsset("chiliz", "CHZ", "Chiliz", aliases=("chiliz", "chz")),
    ]
    raw = [
        raw_proxy(
            "hype-spacex-preipo",
            "Hyperliquid $HYPE token rallies as SpaceX pre-IPO perpetual market opens",
            "$HYPE token traders chase synthetic exposure to SpaceX before a dated catalyst is confirmed.",
            "HYPE",
            "hyperliquid",
            "SpaceX",
        ),
        raw_proxy(
            "aster-openai-preipo",
            "ASTER token jumps as OpenAI pre-IPO perpetual launches",
            "ASTER token is discussed as a synthetic exposure instrument for OpenAI private-market demand.",
            "ASTER",
            "aster",
            "OpenAI",
        ),
        raw_proxy(
            "chz-world-cup-fan-token",
            "$CHZ fan token volume jumps before World Cup kickoff",
            "Chiliz fan token traders chase World Cup attention before a confirmed match catalyst.",
            "CHZ",
            "chiliz",
            "World Cup",
            event_type="sports_event",
        ),
    ]

    result = event_discovery.run_discovery(raw, assets, now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc))
    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
    )
    by_symbol = {alert.symbol: alert for alert in alerts}

    assert by_symbol["HYPE"].tier == event_alerts.EventAlertTier.WATCHLIST
    assert by_symbol["ASTER"].tier == event_alerts.EventAlertTier.WATCHLIST
    assert by_symbol["CHZ"].tier in {
        event_alerts.EventAlertTier.RADAR_DIGEST,
        event_alerts.EventAlertTier.WATCHLIST,
    }
    assert all("review_status" not in alert.score_components for alert in alerts)
    report = event_alerts.format_event_alert_report(alerts)
    assert "EVENT RESEARCH ALERT REPORT" in report
    assert "not trade signals" in report
    assert "what user should verify:" in report


def test_event_alerts_proxy_venue_digest_only_unless_enabled():
    from dataclasses import replace
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent
    from crypto_rsi_scanner.event_providers.manual_json import content_hash

    payload = {
        "raw_id": "hyperliquid-venue-spacex",
        "title": "Hyperliquid lists SpaceX pre-IPO perpetual market",
        "body": "The platform lists SpaceX pre-IPO contracts and prices the market for private-company exposure.",
        "event": {
            "event_id": "hyperliquid-venue-spacex",
            "event_name": "Hyperliquid lists SpaceX pre-IPO perpetual market",
            "event_type": "ipo_proxy",
            "event_time": "2026-06-20T00:00:00+00:00",
            "event_time_confidence": 1.0,
            "external_asset": "SpaceX",
            "confidence": 0.88,
            "description": "The platform lists SpaceX pre-IPO contracts and prices the market for private-company exposure.",
        },
        "market": {
            "symbol": "HYPE",
            "coin_id": "hyperliquid",
            "timestamp": "2026-06-16T16:00:00Z",
            "price": 35.0,
            "market_cap": 1_000_000_000,
            "volume_24h": 900_000_000,
            "return_24h": 1.2,
            "return_72h": 2.5,
            "return_7d": 4.5,
            "volume_zscore_24h": 6.0,
        },
        "derivatives": {
            "symbol": "HYPE",
            "timestamp": "2026-06-16T16:00:00Z",
            "perp_available": True,
            "open_interest_24h_change_pct": 0.80,
            "funding_rate_8h": 0.0012,
            "perp_spot_volume_ratio": 25.0,
        },
    }
    raw = RawDiscoveredEvent(
        raw_id="hyperliquid-venue-spacex",
        provider="test_news",
        fetched_at=datetime(2026, 6, 16, 13, 0, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        source_url="https://example.test/hyperliquid-venue-spacex",
        title=payload["title"],
        body=payload["body"],
        raw_json=payload,
        source_confidence=0.88,
        content_hash=content_hash(payload),
    )
    assets = [
        DiscoveredAsset(
            "hyperliquid",
            "HYPE",
            "Hyperliquid",
            aliases=("hyperliquid", "hype"),
            market_cap=1_000_000_000,
            volume_24h=900_000_000,
            price=35.0,
        )
    ]
    result = event_discovery.run_discovery(raw_events=[raw], assets=assets, now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc))
    assert result.candidates[0].classification.asset_role == "proxy_venue"

    default_alert = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
    )[0]
    assert default_alert.tier == event_alerts.EventAlertTier.RADAR_DIGEST

    low_confidence_result = replace(
        result,
        candidates=(replace(
            result.candidates[0],
            classification=replace(result.candidates[0].classification, confidence=0.60),
        ),),
    )
    low_confidence_alert = event_alerts.build_event_alert_candidates(
        low_confidence_result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
    )[0]
    assert low_confidence_alert.tier == event_alerts.EventAlertTier.STORE_ONLY
    assert "low classifier confidence" in (low_confidence_alert.rejected_reason or "")

    strict_alert = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(allow_proxy_venue=True),
        now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
    )[0]
    assert strict_alert.tier in {
        event_alerts.EventAlertTier.WATCHLIST,
        event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH,
    }


def test_event_alerts_short_triggered_candidate_gets_triggered_fade_tier():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    result = _event_discovery_fixture_result()
    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    by_symbol = {alert.symbol: alert for alert in alerts}
    assert by_symbol["TESTVELVET"].tier == event_alerts.EventAlertTier.TRIGGERED_FADE
    assert "SHORT_TRIGGERED" in by_symbol["TESTVELVET"].reason


def test_event_alerts_expose_cluster_components_without_boosting_noise():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    result = _llm_golden_result()
    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    by_key = {
        (alert.discovery_candidate.event.event_id, alert.coin_id): alert
        for alert in alerts
    }
    velvet = by_key[("llm-velvet-spacex", "velvet")]
    assert "cluster_confidence" in velvet.score_components
    assert "independent_source_count" in velvet.score_components
    assert "accepted_link_kind" in velvet.score_components
    assert "event_time_consensus" in velvet.score_components

    word_collision = by_key[("llm-hype-word-collision", "hyperliquid")]
    assert word_collision.score_components["cluster_confirmation"] == 0


def test_event_alerts_rejection_gates_override_inconsistent_triggered_signal():
    from dataclasses import replace
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    result = _event_discovery_fixture_result()
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    inconsistent_direct = replace(
        by_symbol["TESTBTC"],
        fade_signal=by_symbol["TESTVELVET"].fade_signal,
    )
    inconsistent_result = replace(result, candidates=(inconsistent_direct,))

    alert = event_alerts.build_event_alert_candidates(
        inconsistent_result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )[0]
    assert alert.tier == event_alerts.EventAlertTier.STORE_ONLY
    assert "direct beneficiary" in (alert.rejected_reason or "")


def test_event_alerts_resolve_playbook_first_tiers_and_trigger_guards():
    from dataclasses import replace
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    alerts = event_alerts.build_event_alert_candidates(_full_event_discovery_fixture_result(), now=now)
    by_symbol = {alert.symbol: alert for alert in alerts}

    listing = by_symbol["TESTTOKEN"]
    assert listing.playbook_type == event_playbooks.EventPlaybookType.LISTING_VOLATILITY.value
    assert listing.playbook_action == event_playbooks.EventPlaybookAction.WATCHLIST.value
    assert listing.tier == event_alerts.EventAlertTier.WATCHLIST
    assert listing.playbook_can_trigger_fade is False

    strong_listing = by_symbol["TESTLIST"]
    assert strong_listing.playbook_type == event_playbooks.EventPlaybookType.LISTING_VOLATILITY.value
    assert strong_listing.score_components["derivatives_crowding"] == 100
    assert strong_listing.tier == event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH

    fake_trigger = event_fade.FadeSignal(
        symbol=listing.symbol,
        timestamp=now,
        signal_type=event_fade.FadeSignalType.SHORT_TRIGGERED,
        state=event_fade.FadeState.TRIGGERED_SHORT,
        fade_score=99,
        confidence=1.0,
        reason_codes=["fixture_bad_direct_trigger"],
        warnings=[],
    )
    bad_direct = replace(listing.discovery_candidate, fade_signal=fake_trigger)
    bad_playbook = event_playbooks.assess_event_playbook(
        bad_direct,
        listing.score_components,
        rejected_reason=listing.rejected_reason,
    )
    assert event_alerts.resolve_playbook_alert_tier(
        bad_direct,
        listing.opportunity_score,
        listing.score_components,
        bad_playbook,
        listing.rejected_reason,
        event_alerts.EventAlertConfig(),
    ) == event_alerts.EventAlertTier.STORE_ONLY

    low_quality_direct = by_symbol["TESTCAL"]
    assert low_quality_direct.playbook_type == event_playbooks.EventPlaybookType.DIRECT_EVENT.value
    assert low_quality_direct.tier == event_alerts.EventAlertTier.STORE_ONLY

    unlock = by_symbol["TESTUNLOCK"]
    unlock_components = {
        **unlock.score_components,
        "market_move_volume": 60,
        "supply_pressure": 85,
        "source_quality": 95,
    }
    unlock_playbook = event_playbooks.assess_event_playbook(
        unlock.discovery_candidate,
        unlock_components,
        rejected_reason=unlock.rejected_reason,
    )
    assert unlock_playbook.playbook_type == event_playbooks.EventPlaybookType.UNLOCK_SUPPLY_PRESSURE.value
    assert event_alerts.resolve_playbook_alert_tier(
        unlock.discovery_candidate,
        generic_score=72,
        components=unlock_components,
        playbook_assessment=unlock_playbook,
        rejected_reason=unlock.rejected_reason,
        cfg=event_alerts.EventAlertConfig(),
    ) == event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH

    perp = by_symbol["TESTPERP"]
    perp_components = {
        **perp.score_components,
        "market_move_volume": 55,
        "derivatives_crowding": 85,
        "source_quality": 95,
    }
    perp_playbook = event_playbooks.assess_event_playbook(
        perp.discovery_candidate,
        perp_components,
        rejected_reason=perp.rejected_reason,
    )
    assert perp_playbook.playbook_type == event_playbooks.EventPlaybookType.PERP_LISTING_SQUEEZE.value
    assert event_alerts.resolve_playbook_alert_tier(
        perp.discovery_candidate,
        generic_score=72,
        components=perp_components,
        playbook_assessment=perp_playbook,
        rejected_reason=perp.rejected_reason,
        cfg=event_alerts.EventAlertConfig(),
    ) == event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH

    anomaly = by_symbol["TESTPUMP"]
    assert anomaly.playbook_type == event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value
    assert anomaly.tier == event_alerts.EventAlertTier.STORE_ONLY
