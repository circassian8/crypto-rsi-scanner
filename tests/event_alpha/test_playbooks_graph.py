"""Focused Event Alpha deterministic radar behavior tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_playbooks_classify_proxy_attention_direct_infrastructure_and_noise():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    from crypto_rsi_scanner.event_core.models import (
        DiscoveredAsset,
        DiscoveredEventFadeCandidate,
        EventAssetLink,
        EventClassification,
        NormalizedEvent,
        RawDiscoveredEvent,
    )

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw_event(raw_id, title, body, event_type="ipo_proxy", event_time="2026-06-20T13:30:00Z"):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="test",
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json={
                "event": {
                    "event_id": raw_id,
                    "event_name": title,
                    "event_type": event_type,
                    "event_time": event_time,
                    "event_time_confidence": 0.90 if event_time else 0.0,
                    "external_asset": "SpaceX",
                    "confidence": 0.90,
                    "description": body,
                }
            },
            source_confidence=0.90,
            content_hash=raw_id,
        )

    pumpx = DiscoveredAsset(coin_id="pumpx", symbol="PUMPX", name="PumpX", aliases=("pumpx token", "PumpX"))
    proxy = event_discovery.run_discovery(
        [raw_event(
            "playbook-proxy-fade",
            "PumpX token offers synthetic exposure to SpaceX pre-IPO market",
            "PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
        )],
        [pumpx],
        now=now,
    ).candidates[0]
    proxy_alert = event_alerts.build_event_alert_candidates(
        event_discovery.EventDiscoveryResult((), (), (), (), (proxy,)),
        now=now,
    )[0]
    assert proxy_alert.playbook_type == event_playbooks.EventPlaybookType.PROXY_FADE.value
    assert proxy_alert.playbook_can_trigger_fade is True
    assert proxy_alert.expected_direction == "down"
    assert proxy_alert.primary_horizon == "72h"

    attention = event_discovery.run_discovery(
        [raw_event(
            "playbook-proxy-attention",
            "PumpX token offers synthetic exposure to SpaceX pre-IPO market",
            "PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
            event_time=None,
        )],
        [pumpx],
        now=now,
    ).candidates[0]
    attention_alert = event_alerts.build_event_alert_candidates(
        event_discovery.EventDiscoveryResult((), (), (), (), (attention,)),
        now=now,
    )[0]
    assert attention_alert.playbook_type == event_playbooks.EventPlaybookType.RWA_PREIPO_PROXY.value
    assert attention_alert.playbook_can_trigger_fade is False
    assert attention_alert.playbook_hypothesis

    direct = event_discovery.run_discovery(
        [raw_event(
            "playbook-direct",
            "PumpX Binance listing starts tomorrow",
            "Binance will list PumpX spot trading pairs.",
            event_type="exchange_listing",
        )],
        [pumpx],
        now=now,
    ).candidates[0]
    direct_alert = event_alerts.build_event_alert_candidates(
        event_discovery.EventDiscoveryResult((), (), (), (), (direct,)),
        now=now,
    )[0]
    assert direct_alert.playbook_type == event_playbooks.EventPlaybookType.LISTING_VOLATILITY.value
    assert direct_alert.expected_direction == "volatility"
    assert direct_alert.playbook_can_trigger_fade is False
    assert direct_alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE
    assert "Fresh venue access" in direct_alert.reason
    assert "confirm spot listing details" in direct_alert.verify
    assert "proxy instrument" not in "; ".join(direct_alert.verify)

    link = EventAssetLink(
        event_id="noise",
        coin_id="hype",
        symbol="HYPE",
        name="Hype",
        link_confidence=0.90,
        match_reason="ticker",
        evidence=("hype",),
    )
    noise = DiscoveredEventFadeCandidate(
        event=NormalizedEvent(
            event_id="noise",
            raw_ids=("noise",),
            event_name="IPO hype grows",
            event_type="ipo_proxy",
            event_time=None,
            event_time_confidence=0.0,
            first_seen_time=now,
            source="test",
            source_urls=(),
            external_asset="SpaceX",
            description="IPO hype grows around SpaceX.",
            confidence=0.70,
        ),
        asset=DiscoveredAsset(coin_id="hype", symbol="HYPE", name="Hype"),
        link=link,
        classification=EventClassification(
            event_id="noise",
            coin_id="hype",
            is_proxy_narrative=False,
            is_direct_beneficiary=False,
            relationship_type="proxy_context",
            confidence=0.55,
            classifier_version="test",
            reason="ticker word collision",
            evidence=("hype",),
            asset_role="ticker_word_collision",
            asset_role_confidence=0.90,
            asset_role_reason="ordinary word",
            asset_role_evidence=("hype",),
        ),
        fade_candidate=None,
        fade_signal=None,
        data_quality={},
    )
    noise_assessment = event_playbooks.assess_event_playbook(
        noise,
        {"asset_resolution": 90, "source_quality": 70, "classifier": 55},
        rejected_reason="ticker_word_collision",
    )
    assert noise_assessment.playbook_type == event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value
    assert noise_assessment.can_trigger_fade is False

    infra = DiscoveredEventFadeCandidate(
        event=noise.event,
        asset=DiscoveredAsset(coin_id="chainlink", symbol="LINK", name="Chainlink"),
        link=EventAssetLink("infra", "chainlink", "LINK", "Chainlink", 0.95, "alias", ("Chainlink",)),
        classification=EventClassification(
            event_id="infra",
            coin_id="chainlink",
            is_proxy_narrative=False,
            is_direct_beneficiary=False,
            relationship_type="proxy_context",
            confidence=0.60,
            classifier_version="test",
            reason="infrastructure context",
            evidence=("oracle provider",),
            asset_role="infrastructure",
            asset_role_confidence=0.90,
            asset_role_reason="oracle provider",
            asset_role_evidence=("oracle provider",),
        ),
        fade_candidate=None,
        fade_signal=None,
        data_quality={},
    )
    infra_assessment = event_playbooks.assess_event_playbook(
        infra,
        {"asset_resolution": 95, "source_quality": 80, "classifier": 60},
    )
    assert infra_assessment.playbook_type == event_playbooks.EventPlaybookType.INFRASTRUCTURE_MENTION.value
    assert infra_assessment.max_research_tier == "RADAR_DIGEST"

    def manual_candidate(raw_id, event_type, title, body, *, external_asset="SpaceX", role="proxy_instrument",
                         relationship="proxy_attention", proxy=True, direct=False):
        event = NormalizedEvent(
            event_id=raw_id,
            raw_ids=(raw_id,),
            event_name=title,
            event_type=event_type,
            event_time=now,
            event_time_confidence=0.90,
            first_seen_time=now,
            source="test",
            source_urls=(f"https://example.test/{raw_id}",),
            external_asset=external_asset,
            description=body,
            confidence=0.90,
        )
        asset = DiscoveredAsset(coin_id=raw_id, symbol=raw_id.upper(), name=raw_id.title())
        return DiscoveredEventFadeCandidate(
            event=event,
            asset=asset,
            link=EventAssetLink(raw_id, asset.coin_id, asset.symbol, asset.name, 0.95, "alias", (asset.symbol,)),
            classification=EventClassification(
                event_id=raw_id,
                coin_id=asset.coin_id,
                is_proxy_narrative=proxy,
                is_direct_beneficiary=direct,
                relationship_type=relationship,
                confidence=0.90,
                classifier_version="test",
                reason="fixture",
                evidence=(title,),
                asset_role=role,
                asset_role_confidence=0.90,
                asset_role_reason="fixture",
                asset_role_evidence=(body,),
            ),
            fade_candidate=None,
            fade_signal=None,
            data_quality={},
        )

    cases = [
        (
            manual_candidate("perp", "perp_listing", "PERP futures listing", "Perp listing opens."),
            event_playbooks.EventPlaybookType.PERP_LISTING_SQUEEZE,
        ),
        (
            manual_candidate("unlock", "token_unlock", "UNLOCK vesting event", "Large unlock starts.", proxy=False,
                             direct=True, role="direct_beneficiary", relationship="direct_unlock"),
            event_playbooks.EventPlaybookType.UNLOCK_SUPPLY_PRESSURE,
        ),
        (
            manual_candidate("airdrop", "airdrop", "AIRDROP claim opens", "Airdrop claim starts.", proxy=False,
                             direct=True, role="direct_beneficiary", relationship="direct_protocol_event"),
            event_playbooks.EventPlaybookType.AIRDROP_TGE_SELL_PRESSURE,
        ),
        (
            manual_candidate("fan", "sports_event", "FAN token World Cup match", "Fan token pumps into match.",
                             external_asset="World Cup"),
            event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT,
        ),
        (
            manual_candidate("politics", "political_event", "MEME election catalyst", "Political meme token event.",
                             external_asset="US election"),
            event_playbooks.EventPlaybookType.POLITICAL_MEME_EVENT,
        ),
        (
            manual_candidate("ai", "ipo_proxy", "AI token OpenAI pre-IPO exposure",
                             "Token offers OpenAI synthetic exposure.", external_asset="OpenAI"),
            event_playbooks.EventPlaybookType.AI_IPO_PROXY,
        ),
        (
            manual_candidate("spacex", "ipo_proxy", "SpaceX stock token listing pre-IPO exposure",
                             "Tokenized stock listing gives synthetic exposure to SpaceX pre-IPO markets.",
                             external_asset="SpaceX"),
            event_playbooks.EventPlaybookType.RWA_PREIPO_PROXY,
        ),
        (
            manual_candidate("openai", "external_proxy_event", "OpenAI pre-IPO proxy market opens",
                             "Crypto venue offers OpenAI pre-IPO proxy access.",
                             external_asset="OpenAI"),
            event_playbooks.EventPlaybookType.AI_IPO_PROXY,
        ),
        (
            manual_candidate("listing", "exchange_listing", "LIST Binance listing",
                             "Binance listing opens spot trading pairs.", proxy=False,
                             direct=True, role="direct_beneficiary", relationship="direct_listing"),
            event_playbooks.EventPlaybookType.LISTING_VOLATILITY,
        ),
        (
            manual_candidate("shock", "security_event", "SHOCK exploit disclosed", "Security exploit hits protocol.",
                             proxy=False, direct=True, role="direct_beneficiary", relationship="direct_protocol_event"),
            event_playbooks.EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK,
        ),
    ]
    for candidate, expected in cases:
        assessment = event_playbooks.assess_event_playbook(
            candidate,
            {
                "asset_resolution": 95,
                "source_quality": 85,
                "classifier": 90,
                "event_time_quality": 90,
                "market_move_volume": 70,
                "derivatives_crowding": 20,
            },
        )
        assert assessment.playbook_type == expected.value
        assert assessment.can_trigger_fade is False
        assert assessment.hypothesis
        assert assessment.what_to_verify
        assert assessment.timing_window
        assert assessment.invalidation
        if expected == event_playbooks.EventPlaybookType.UNLOCK_SUPPLY_PRESSURE:
            assert assessment.expected_direction == "down"
            assert any("unlock size" in item for item in assessment.what_to_verify)
        if expected == event_playbooks.EventPlaybookType.LISTING_VOLATILITY:
            assert assessment.expected_direction == "volatility"


def test_event_graph_clusters_catalyst_variants_and_rejects_noise_links():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
    from crypto_rsi_scanner.event_core.models import (
        DiscoveredAsset,
        DiscoveredEventFadeCandidate,
        EventAssetLink,
        EventClassification,
        EventDiscoveryResult,
        NormalizedEvent,
        RawDiscoveredEvent,
    )

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    event_time = datetime(2026, 6, 20, 13, 30, tzinfo=timezone.utc)

    def event(event_id, title, *, domain="example.test"):
        return NormalizedEvent(
            event_id=event_id,
            raw_ids=(f"raw-{event_id}",),
            event_name=title,
            event_type="ipo_proxy",
            event_time=event_time,
            event_time_confidence=0.90,
            first_seen_time=now,
            source="test",
            source_urls=(f"https://{domain}/{event_id}",),
            external_asset="SpaceX",
            description=title,
            confidence=0.90,
        )

    events = (
        event("spacex-1", "SpaceX IPO trading starts Friday", domain="alpha.test"),
        event("spacex-2", "SpaceX pre-IPO market opens on June 20", domain="beta.test"),
        event("spacex-3", "Bitcoin World covers SpaceX prediction market volume", domain="bitcoinworld.test"),
    )

    def candidate(norm_event, coin_id, symbol, *, role="proxy_instrument", proxy=True, direct=False):
        asset = DiscoveredAsset(coin_id=coin_id, symbol=symbol, name=symbol)
        relationship = "proxy_exposure" if proxy else "publisher_suffix_false_positive"
        return DiscoveredEventFadeCandidate(
            event=norm_event,
            asset=asset,
            link=EventAssetLink(
                norm_event.event_id,
                coin_id,
                symbol,
                symbol,
                0.95,
                "alias",
                (symbol, norm_event.event_name),
            ),
            classification=EventClassification(
                event_id=norm_event.event_id,
                coin_id=coin_id,
                is_proxy_narrative=proxy,
                is_direct_beneficiary=direct,
                relationship_type=relationship,
                confidence=0.90,
                classifier_version="test",
                reason="fixture",
                evidence=(norm_event.event_name,),
                asset_role=role,
                asset_role_confidence=0.90,
                asset_role_reason="fixture",
                asset_role_evidence=(symbol,),
            ),
            fade_candidate=None,
            fade_signal=None,
            data_quality={},
        )

    raw_events = tuple(
        RawDiscoveredEvent(
            raw_id=norm_event.raw_ids[0],
            provider="test",
            fetched_at=now,
            published_at=now,
            source_url=norm_event.source_urls[0],
            title=norm_event.event_name,
            body=(
                f"{norm_event.event_name} with independently reported context "
                f"and source-specific details for catalyst review number {index}"
            ),
            raw_json={"source_class": "broad_news"},
            source_confidence=0.90,
            content_hash=f"hash-{index}",
        )
        for index, norm_event in enumerate(events, start=1)
    )

    result = EventDiscoveryResult(
        raw_events=raw_events,
        normalized_events=events,
        links=(),
        classifications=(),
        candidates=(
            candidate(events[0], "velvet", "VELVET"),
            candidate(events[1], "aster", "ASTER"),
            candidate(events[2], "bitcoin", "BTC", role="mentioned_asset", proxy=False),
        ),
    )

    clusters = event_graph.build_event_clusters(result)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.cluster_id == "spacex|ipo-proxy|2026-06-20"
    assert set(cluster.event_ids) == {"spacex-1", "spacex-2", "spacex-3"}
    assert cluster.source_count == 3
    assert cluster.independent_source_count == 3
    assert cluster.source_quality_score > 0
    assert cluster.event_time_consensus == 100
    assert cluster.accepted_asset_count == 2
    assert cluster.rejected_asset_count == 1
    assert cluster.cluster_confidence > 70
    links = {link.symbol: link for link in cluster.asset_links}
    assert links["VELVET"].accepted is True
    assert links["VELVET"].accepted_kind == "proxy"
    assert links["VELVET"].accepted_for_playbook == "proxy_fade"
    assert links["ASTER"].accepted is True
    assert links["ASTER"].accepted_kind == "proxy"
    assert links["BTC"].accepted is False
    assert links["BTC"].accepted_kind == "none"
    assert links["BTC"].playbook_type == "source_noise_control"
    assert "mentioned_asset" in (links["BTC"].rejected_reason or "")
    report = event_graph.format_event_cluster_report(clusters)
    assert "EVENT CLUSTER REPORT" in report
    assert "cluster_conf=" in report
    assert (
        "sources: raw=3 domains=3 independent=3 corroborations=2 "
        "content_clusters=3"
    ) in report
    assert "VELVET/velvet accepted" in report
    assert "accepted_kinds=proxy:2" in report
    assert "ASTER/aster accepted" in report
    assert "BTC/bitcoin rejected" in report

    alerts = event_alerts.build_event_alert_candidates(result, now=now)
    by_symbol = {alert.symbol: alert for alert in alerts}
    assert by_symbol["VELVET"].score_components["cluster_confirmation"] == cluster.cluster_confidence
    assert by_symbol["ASTER"].score_components["cluster_confirmation"] == cluster.cluster_confidence
    assert by_symbol["BTC"].score_components["cluster_confirmation"] == 0


def test_event_graph_accepts_direct_supply_and_derivatives_without_boosting_infrastructure():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
    from crypto_rsi_scanner.event_core.models import (
        DiscoveredAsset,
        DiscoveredEventFadeCandidate,
        EventAssetLink,
        EventClassification,
        EventDiscoveryResult,
        NormalizedEvent,
    )

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    event_time = datetime(2026, 6, 18, 20, 0, tzinfo=timezone.utc)

    def event(event_id, event_type, title):
        return NormalizedEvent(
            event_id=event_id,
            raw_ids=(f"raw-{event_id}",),
            event_name=title,
            event_type=event_type,
            event_time=event_time,
            event_time_confidence=0.95,
            first_seen_time=now,
            source="test",
            source_urls=(f"https://alpha.test/{event_id}", f"https://beta.test/{event_id}"),
            external_asset=None,
            description=title,
            confidence=0.90,
        )

    def candidate(norm_event, symbol, role, relationship, *, direct=True):
        asset = DiscoveredAsset(coin_id=symbol.lower(), symbol=symbol, name=symbol)
        return DiscoveredEventFadeCandidate(
            event=norm_event,
            asset=asset,
            link=EventAssetLink(norm_event.event_id, asset.coin_id, symbol, symbol, 0.95, "alias", (symbol,)),
            classification=EventClassification(
                event_id=norm_event.event_id,
                coin_id=asset.coin_id,
                is_proxy_narrative=False,
                is_direct_beneficiary=direct,
                relationship_type=relationship,
                confidence=0.90,
                classifier_version="test",
                reason="fixture",
                evidence=(norm_event.event_name,),
                asset_role=role,
                asset_role_confidence=0.90,
                asset_role_reason="fixture",
                asset_role_evidence=(symbol,),
            ),
            fade_candidate=None,
            fade_signal=None,
            data_quality={},
        )

    listing = event("listing", "exchange_listing", "Binance lists LIST")
    unlock = event("unlock", "token_unlock", "UNLOCK vesting unlock")
    perp = event("perp", "perp_listing", "PERP futures listing")
    infra = event("infra", "external_proxy_event", "Chainlink powers prediction market")
    result = EventDiscoveryResult(
        raw_events=(),
        normalized_events=(listing, unlock, perp, infra),
        links=(),
        classifications=(),
        candidates=(
            candidate(listing, "LIST", "direct_beneficiary", "direct_listing"),
            candidate(unlock, "UNLOCK", "direct_beneficiary", "direct_unlock"),
            candidate(perp, "PERP", "direct_beneficiary", "direct_listing"),
            candidate(infra, "LINK", "infrastructure", "infrastructure_provider", direct=False),
        ),
    )
    links = {
        link.symbol: link
        for cluster in event_graph.build_event_clusters(result)
        for link in cluster.asset_links
    }
    assert links["LIST"].accepted_kind == "direct"
    assert links["UNLOCK"].accepted_kind == "supply"
    assert links["PERP"].accepted_kind == "derivatives"
    assert links["LINK"].accepted is True
    assert links["LINK"].accepted_kind == "infrastructure"

    alerts = event_alerts.build_event_alert_candidates(result, now=now)
    by_symbol = {alert.symbol: alert for alert in alerts}
    assert by_symbol["LIST"].score_components["cluster_confirmation"] == 0
    assert "source_independence_source_context_incomplete" in by_symbol[
        "LIST"
    ].score_components["source_independence_errors"]
    assert by_symbol["UNLOCK"].score_components["cluster_confirmation"] == 0
    assert by_symbol["PERP"].score_components["cluster_confirmation"] == 0
    assert by_symbol["LINK"].score_components["cluster_confirmation"] == 0
