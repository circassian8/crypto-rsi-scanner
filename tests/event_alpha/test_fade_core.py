"""Focused Event Alpha research-only behavior tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_fade_component_scores_velvet_like_and_direct_beneficiary_low():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    cfg = ef.EventFadeConfig()
    candidate = _event_fade_velvet_candidate(now)
    score = ef.calculate_fade_score(candidate, cfg, now)
    assert score >= 80
    assert candidate.component_scores["event_clarity"] >= 70
    assert candidate.component_scores["proxy_purity"] >= 70
    assert candidate.component_scores["pre_event_pump"] >= 90
    assert candidate.component_scores["derivatives_crowding"] >= 80

    direct = _event_fade_velvet_candidate(now, direct=True)
    ef.calculate_fade_score(direct, cfg, now)
    assert direct.component_scores["proxy_purity"] < 50
    assert not ef.is_event_fade_candidate(direct, cfg, now)


def test_event_fade_pre_event_pump_and_optional_data_are_safe():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    event = ef.CatalystEvent(
        "pump-no-derivs", "p", "PUMP", "Manual catalyst", "other",
        now, confidence=0.9, is_proxy_narrative=True,
    )
    market = ef.EventMarketSnapshot(
        "PUMP", "p", now, 1.0, return_24h=0.8, return_7d=10.0, volume_zscore_24h=6.0
    )
    candidate = ef.FadeCandidate("PUMP", "p", event, market)
    ef.calculate_fade_score(candidate, ef.EventFadeConfig(), now)
    assert candidate.component_scores["pre_event_pump"] >= 90
    assert candidate.component_scores["derivatives_crowding"] == 50
    assert candidate.component_scores["supply_pressure"] == 50
    assert "derivatives data missing" in candidate.warnings


def test_event_fade_post_event_failure_requires_event_passed_and_confirmation():
    from datetime import datetime, timezone, timedelta
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    candidate = _event_fade_velvet_candidate(now)
    before_event = candidate.event.event_time - timedelta(minutes=1)
    assert ef.score_post_event_failure(candidate.event, candidate.technical, candidate.rsi, before_event) == 0
    assert ef.is_post_event_failure(candidate, ef.EventFadeConfig(), now)

    candidate.technical.failed_reclaim_event_vwap = False
    candidate.technical.lower_high_confirmed = False
    candidate.technical.first_support_broken = False
    assert not ef.is_post_event_failure(candidate, ef.EventFadeConfig(), now)


def test_event_fade_state_machine_reaches_short_only_after_failure():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    cfg = ef.EventFadeConfig()
    candidate = _event_fade_velvet_candidate(now)
    signal = ef.generate_fade_signal(candidate, cfg, now)
    assert signal.signal_type == ef.FadeSignalType.SHORT_TRIGGERED
    assert signal.state == ef.FadeState.TRIGGERED_SHORT
    assert "dated proxy catalyst" in signal.reason_codes

    no_tech = _event_fade_velvet_candidate(now)
    no_tech.technical = None
    signal = ef.generate_fade_signal(no_tech, cfg, now)
    assert signal.signal_type != ef.FadeSignalType.SHORT_TRIGGERED


def test_event_fade_direct_beneficiary_never_triggers_short():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    cfg = ef.EventFadeConfig(min_trigger_score=70)
    candidate = _event_fade_velvet_candidate(now, direct=True)
    signal = ef.generate_fade_signal(candidate, cfg, now)
    assert candidate.fade_score >= cfg.min_trigger_score
    assert candidate.component_scores["pre_event_pump"] == 100
    assert candidate.component_scores["post_event_failure"] == 100
    assert not ef.is_event_fade_candidate(candidate, cfg, now)
    assert signal.signal_type == ef.FadeSignalType.NO_TRADE
    assert signal.state == ef.FadeState.DISCOVERED
    assert "not an eligible proxy event-fade candidate" in signal.warnings


def test_event_fade_non_proxy_event_never_triggers_even_if_manually_armed():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    cfg = ef.EventFadeConfig()
    candidate = _event_fade_velvet_candidate(now)
    candidate.event.is_proxy_narrative = False
    candidate.state = ef.FadeState.ARMED
    signal = ef.generate_fade_signal(candidate, cfg, now)
    assert not ef.is_event_fade_candidate(candidate, cfg, now)
    assert signal.signal_type == ef.FadeSignalType.NO_TRADE
    assert signal.state == ef.FadeState.DISCOVERED


def test_event_fade_no_dated_catalyst_does_not_trigger():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    candidate = _event_fade_velvet_candidate(now, no_event_time=True)
    signal = ef.generate_fade_signal(candidate, ef.EventFadeConfig(), now)
    assert candidate.component_scores["event_clarity"] < 70
    assert signal.signal_type != ef.FadeSignalType.SHORT_TRIGGERED


def test_event_fade_btc_risk_on_blocks_weak_short():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    candidate = _event_fade_velvet_candidate(now, btc_risk_on=95)
    candidate.market.return_7d = 1.6
    candidate.derivatives.perp_spot_volume_ratio = 5.5
    ef.calculate_fade_score(candidate, ef.EventFadeConfig(), now)
    assert ef.is_btc_regime_blocking_short(candidate, ef.EventFadeConfig())
    assert not ef.is_post_event_failure(candidate, ef.EventFadeConfig(), now)


def test_event_fade_risk_sizing_and_technical_helpers():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    sizing = ef.calculate_position_size(
        account_equity=10_000,
        risk_pct=0.005,
        entry_price=7.0,
        stop_price=8.0,
        max_leverage_hint=2.0,
        liquidity_depth_2pct=1_000,
    )
    assert sizing["valid"]
    assert sizing["risk_usd"] == 50
    assert sizing["position_units"] == 50
    assert "notional is large relative to visible 2pct depth" in sizing["warnings"]
    assert not ef.calculate_position_size(10_000, 0.005, 7.0, 7.0, 2.0)["valid"]

    times = [datetime(2026, 1, i + 1, tzinfo=timezone.utc) for i in range(3)]
    assert abs(ef.anchored_vwap([10, 20, 30], [1, 1, 2], times, times[1]) - (80 / 3)) < 1e-9
    assert ef.price_below_level(9, 10)
    assert ef.failed_reclaim([8, 11, 9], 10, lookback=3)
    assert ef.lower_high_confirmed([10, 15, 12, 13, 11])
    assert ef.support_break_confirmed([12, 11, 9], 10)


def test_event_fade_json_loader_and_feature_vector():
    import json
    import tempfile
    from pathlib import Path
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_fade as ef

    path = Path(tempfile.mkdtemp()) / "events.json"
    path.write_text(json.dumps([{
        "event_id": "testvelvet-spacex-ipo",
        "coin_id": "testvelvet",
        "symbol": "TESTVELVET",
        "event_name": "SpaceX IPO trading start",
        "event_type": "ipo_proxy",
        "event_time": "2026-06-12T13:30:00Z",
        "first_seen_time": "2026-06-10T00:00:00Z",
        "source": "manual_fixture",
        "confidence": 0.95,
        "external_asset": "SpaceX",
        "is_proxy_narrative": True,
        "is_direct_beneficiary": False,
    }]))
    events = ef.load_event_fade_events(path)
    assert len(events) == 1
    assert events[0].symbol == "TESTVELVET"

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    candidate = _event_fade_velvet_candidate(now)
    ef.calculate_fade_score(candidate, ef.EventFadeConfig(), now)
    vector = ef.event_fade_feature_vector(candidate)
    assert vector["event_type"] == "ipo_proxy"
    assert vector["fade_score"] >= 80
    assert vector["rsi_rollover_confirmed"] is True
    assert vector["eligible"] is True
    assert vector["signal_type"] == "NO_TRADE"
    assert candidate.state == ef.FadeState.DISCOVERED

    unscored = _event_fade_velvet_candidate(now)
    assert unscored.component_scores == {}
    vector = ef.event_fade_feature_vector(unscored, now=now)
    assert vector["fade_score"] >= 80
    assert vector["eligible"] is True
    assert unscored.component_scores["event_clarity"] >= 70
    assert unscored.state == ef.FadeState.DISCOVERED

    candidate.state = ef.FadeState.WATCHLISTED
    assert ef.event_fade_feature_vector(candidate)["signal_type"] == "WATCHLIST"
    assert ef.event_fade_feature_vector(candidate, ef.EventFadeConfig(min_watchlist_score=95))["signal_type"] == "NO_TRADE"


def test_event_resolver_aliases_and_rejects_ticker_collision():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases, resolve_event_assets

    events_path, aliases_path = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(aliases_path)
    normalized = event_discovery.dedupe_events(event_discovery.normalize_raw_event(event) for event in raw)
    spacex = [event for event in normalized if event.event_name == "SpaceX IPO trading start"][0]
    links = resolve_event_assets(spacex, assets)
    assert links[0].coin_id == "testvelvet"
    assert links[0].link_confidence >= 0.95
    assert links[0].match_reason in ("coin_id", "known_alias")

    collision = [event for event in normalized if event.event_id == "collide-ticker-only"][0]
    assert resolve_event_assets(collision, assets) == []
    low_conf = resolve_event_assets(collision, assets, min_confidence=0.0)
    assert all(link.link_confidence < 0.80 for link in low_conf)


def test_event_resolver_rejects_generic_live_universe_identity_terms():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, NormalizedEvent
    from crypto_rsi_scanner.event_alpha.radar.resolver import resolve_event_assets

    event = NormalizedEvent(
        event_id="spacex-tokenized-access",
        raw_ids=("rss:1",),
        event_name="SpaceX debut is a win for crypto price discovery but just a fail for tokenized access",
        event_type="ipo_proxy",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=datetime(2026, 6, 16, tzinfo=timezone.utc),
        source="project_blog_rss",
        source_urls=("https://example.test/spacex",),
        external_asset="SpaceX",
        description="Crypto exchanges cash in on SpaceX frenzy with real pre-IPO derivatives.",
        confidence=0.75,
    )
    noisy_assets = [
        DiscoveredAsset("cash-4", "CASH", "Cash", 1, 1, 1, (), {}, "coingecko", ("cash-4", "Cash", "CASH")),
        DiscoveredAsset("just", "JST", "JUST", 1, 1, 1, (), {}, "coingecko", ("just", "JUST", "JST")),
        DiscoveredAsset("reallink", "REAL", "Reallink", 1, 1, 1, (), {}, "coingecko", ("real", "REAL")),
        DiscoveredAsset(
            "billions-network",
            "BILL",
            "Billions Network",
            1,
            1,
            1,
            (),
            {},
            "coingecko",
            ("bill", "BILL"),
        ),
    ]

    assert resolve_event_assets(event, noisy_assets) == []

    legislature_event = NormalizedEvent(
        event_id="state-legislature-secession",
        raw_ids=("polymarket:1",),
        event_name="Any US state legislature votes on secession by June 30, 2026?",
        event_type="external_proxy_event",
        event_time=datetime(2026, 6, 30, tzinfo=timezone.utc),
        event_time_confidence=0.90,
        first_seen_time=datetime(2026, 6, 16, tzinfo=timezone.utc),
        source="prediction_market_events",
        source_urls=("https://polymarket.com/event/state-secession",),
        external_asset=None,
        description="This market resolves Yes if a bill or resolution is formally voted on by a state legislature.",
        confidence=0.78,
    )

    assert resolve_event_assets(legislature_event, noisy_assets) == []


def test_event_resolver_strips_publisher_suffixes_and_source_origin_noise():
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset
    from crypto_rsi_scanner.event_alpha.radar.resolver import resolve_event_assets

    btc = DiscoveredAsset(
        coin_id="bitcoin",
        symbol="BTC",
        name="Bitcoin",
        aliases=("bitcoin", "btc"),
    )
    kcs = DiscoveredAsset(
        coin_id="kucoin-token",
        symbol="KCS",
        name="KuCoin Token",
        aliases=("kucoin", "kcs"),
    )

    msx = _test_normalized_event(
        "MSX Lists SpaceX Stock Token Ahead of IPO - Bitcoin World",
        "MSX offers tokenized stock exposure to SpaceX before its public debut.",
        event_id="msx-spacex-bitcoin-world",
    )
    rain = _test_normalized_event(
        "Rain Commits New Liquidity to Tokenized Pre-IPO Markets - Bitcoin News",
        "Rain is expanding synthetic exposure products for private companies.",
        event_id="rain-bitcoin-news",
    )
    rain_snippet_suffix = _test_normalized_event(
        "Rain Commits New Liquidity to Tokenized Pre-IPO Markets - Bitcoin News",
        "Rain is expanding synthetic exposure products for private companies - Bitcoin News",
        event_id="rain-snippet-bitcoin-news",
    )
    external_bitcoin_only = _test_normalized_event(
        "SpaceX pre-IPO market opens for prediction traders",
        "No crypto asset is named in this article body.",
        event_id="external-bitcoin-only",
        external_asset="Bitcoin",
    )
    source_origin = _test_normalized_event(
        "SpaceX pre-IPO market opens for prediction traders",
        "The source_origin is KuCoin, but no exchange token is named.",
        event_id="kucoin-source-origin-only",
        source="KuCoin",
    )
    explicit_token = _test_normalized_event(
        "KuCoin token liquidity jumps as SpaceX pre-IPO market opens",
        "KCS token traders discuss the exchange venue narrative.",
        event_id="kucoin-token-explicit",
        source="KuCoin",
    )

    assert resolve_event_assets(msx, [btc]) == []
    assert resolve_event_assets(rain, [btc]) == []
    assert resolve_event_assets(rain_snippet_suffix, [btc]) == []
    assert resolve_event_assets(external_bitcoin_only, [btc]) == []
    assert resolve_event_assets(source_origin, [kcs]) == []
    links = resolve_event_assets(explicit_token, [kcs])
    assert links and links[0].coin_id == "kucoin-token"


def test_event_resolver_rejects_common_word_and_ticker_collisions():
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset
    from crypto_rsi_scanner.event_alpha.radar.resolver import resolve_event_assets

    assets = [
        DiscoveredAsset("usat", "USAT", "USA Token", aliases=("usa", "usat", "usa token")),
        DiscoveredAsset("xrp", "XRP", "XRP", aliases=("ripple", "xrp")),
        DiscoveredAsset("hyperliquid", "HYPE", "Hyperliquid", aliases=("hype", "hyperliquid")),
        DiscoveredAsset("beat-token", "BEAT", "Beat Token", aliases=("beat", "beat token")),
        DiscoveredAsset("prime", "PRIME", "Prime", aliases=("prime",)),
    ]
    cases = [
        _test_normalized_event(
            "USA vs Paraguay match attracts fan token traders",
            "The World Cup fixture is a dated external sports catalyst.",
            event_id="usa-paraguay",
            event_type="sports_event",
            external_asset="USA vs Paraguay",
        ),
        _test_normalized_event(
            "Ripple effects from ETF optimism lift market sentiment",
            "The article uses a common phrase about broader market effects.",
            event_id="ripple-effects",
            external_asset=None,
        ),
        _test_normalized_event(
            "OpenAI IPO hype grows as prediction markets expand",
            "Prediction traders are watching private-market demand.",
            event_id="openai-hype",
            external_asset="OpenAI",
        ),
        _test_normalized_event(
            "Chainlink beat Polymarket in oracle market share this week",
            "The article uses beat as a verb in an oracle comparison.",
            event_id="chainlink-beat",
            external_asset=None,
        ),
        _test_normalized_event(
            "Prime Minister comments on crypto market structure",
            "The title refers to a government official.",
            event_id="prime-minister",
            external_asset=None,
        ),
    ]

    for event in cases:
        assert resolve_event_assets(event, assets) == []

    explicit_hype = _test_normalized_event(
        "OpenAI IPO hype grows as $HYPE traders watch pre-IPO perpetuals",
        "Hyperliquid users discuss synthetic exposure to OpenAI.",
        event_id="explicit-hype",
        external_asset="OpenAI",
    )
    links = resolve_event_assets(explicit_hype, assets)
    assert [link.coin_id for link in links] == ["hyperliquid"]


def test_event_resolver_penalizes_market_recap_resolution_confidence():
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset
    from crypto_rsi_scanner.event_alpha.radar.resolver import resolve_event_assets

    event = _test_normalized_event(
        "Weekly market recap: HYPE token and SpaceX pre-IPO markets lead top stories",
        "Hyperliquid appears in a broad market recap rather than a focused catalyst article.",
        event_id="market-recap-hype",
        external_asset="SpaceX",
    )
    asset = DiscoveredAsset("hyperliquid", "HYPE", "Hyperliquid", aliases=("hyperliquid", "hype"))

    assert resolve_event_assets(event, [asset]) == []
    low_conf = resolve_event_assets(event, [asset], min_confidence=0.0)
    assert low_conf[0].link_confidence == 0.75
