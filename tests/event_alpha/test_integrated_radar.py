"""Focused integrated-radar package refactor tests."""

from __future__ import annotations

import importlib
import json
from collections import Counter
from tempfile import TemporaryDirectory


def test_radar_old_and_new_import_paths_resolve_same_objects():
    module_pairs = (
        ("crypto_rsi_scanner.event_integrated_radar", "crypto_rsi_scanner.event_alpha.radar.integrated_radar", "run_integrated_radar_cycle"),
        ("crypto_rsi_scanner.event_market_state", "crypto_rsi_scanner.event_alpha.radar.market_state", "MarketStateSnapshot"),
        ("crypto_rsi_scanner.event_market_reaction", "crypto_rsi_scanner.event_alpha.radar.market_reaction", "evaluate_market_reaction"),
        ("crypto_rsi_scanner.event_market_anomaly_scanner", "crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner", "scan_market_rows"),
        ("crypto_rsi_scanner.event_core_opportunities", "crypto_rsi_scanner.event_alpha.radar.core_opportunities", "CoreOpportunity"),
        ("crypto_rsi_scanner.event_core_opportunity_store", "crypto_rsi_scanner.event_alpha.radar.core_opportunity_store", "EventCoreOpportunityStoreConfig"),
        ("crypto_rsi_scanner.event_evidence_acquisition", "crypto_rsi_scanner.event_alpha.radar.evidence_acquisition", "run_evidence_acquisition"),
        ("crypto_rsi_scanner.event_opportunity_verdict", "crypto_rsi_scanner.event_alpha.radar.opportunity_verdict", "evaluate_opportunity"),
        ("crypto_rsi_scanner.event_impact_hypotheses", "crypto_rsi_scanner.event_alpha.radar.impact_hypotheses", "generate_impact_hypotheses"),
        ("crypto_rsi_scanner.event_impact_hypothesis_store", "crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store", "write_impact_hypotheses"),
        ("crypto_rsi_scanner.event_incident_store", "crypto_rsi_scanner.event_alpha.radar.incidents", "write_incidents"),
    )

    for old_path, new_path, attr in module_pairs:
        old_module = importlib.import_module(old_path)
        new_module = importlib.import_module(new_path)
        assert getattr(old_module, attr) is getattr(new_module, attr)


def test_integrated_radar_fixture_lane_counts_and_core_types_stay_stable():
    from crypto_rsi_scanner.event_alpha.artifacts import context as artifact_context
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar

    with TemporaryDirectory() as tmp:
        context = artifact_context.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=tmp,
            artifact_namespace="pytest_integrated_radar",
        )
        result = integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        rows = [
            json.loads(line)
            for line in result.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        core_rows = [
            json.loads(line)
            for line in context.core_opportunity_store_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    assert Counter(row["opportunity_type"] for row in rows) == Counter(
        {
            "CONFIRMED_LONG_RESEARCH": 2,
            "DIAGNOSTIC": 2,
            "EARLY_LONG_RESEARCH": 1,
            "FADE_SHORT_REVIEW": 1,
            "RISK_ONLY": 2,
            "UNCONFIRMED_RESEARCH": 3,
        }
    )
    assert Counter(row["opportunity_type"] for row in core_rows) == Counter(
        {
            "CONFIRMED_LONG_RESEARCH": 2,
            "EARLY_LONG_RESEARCH": 1,
            "FADE_SHORT_REVIEW": 1,
            "RISK_ONLY": 2,
            "UNCONFIRMED_RESEARCH": 3,
        }
    )
    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["TESTPERP"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
    assert by_symbol["TESTFADE"]["opportunity_type"] == "FADE_SHORT_REVIEW"
    assert by_symbol["TESTLIST"]["opportunity_type"] == "EARLY_LONG_RESEARCH"
    assert by_symbol["SECTOR"]["opportunity_type"] == "DIAGNOSTIC"
    assert by_symbol["TESTPERP"]["normal_rsi_signal_written"] is False
    assert by_symbol["TESTFADE"]["triggered_fade_created"] is False

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _legacy_helpers as _event_alpha_legacy_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_legacy_helpers).items()
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
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases, resolve_event_assets

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
    from crypto_rsi_scanner.event_models import DiscoveredAsset, NormalizedEvent
    from crypto_rsi_scanner.event_resolver import resolve_event_assets

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
    from crypto_rsi_scanner.event_models import DiscoveredAsset
    from crypto_rsi_scanner.event_resolver import resolve_event_assets

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
    from crypto_rsi_scanner.event_models import DiscoveredAsset
    from crypto_rsi_scanner.event_resolver import resolve_event_assets

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
    from crypto_rsi_scanner.event_models import DiscoveredAsset
    from crypto_rsi_scanner.event_resolver import resolve_event_assets

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


def test_event_alerts_rank_proxy_candidates_without_human_review_fields():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alerts, event_discovery
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent
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
    from crypto_rsi_scanner import event_alerts, event_discovery
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent
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
    from crypto_rsi_scanner import event_alerts

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
    from crypto_rsi_scanner import event_alerts

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
    from crypto_rsi_scanner import event_alerts

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


def test_event_llm_model_enums_and_invalid_output_rejection():
    from crypto_rsi_scanner import event_llm_analyzer
    from crypto_rsi_scanner.event_llm_models import (
        ASSET_ROLE_VALUES,
        RECOMMENDED_ALERT_ACTION_VALUES,
        RELATIONSHIP_TYPE_VALUES,
    )
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    assert "source_noise" in ASSET_ROLE_VALUES
    assert "publisher_suffix_false_positive" in RELATIONSHIP_TYPE_VALUES
    assert "triggered_fade_not_set_by_llm" in RECOMMENDED_ALERT_ACTION_VALUES

    provider = FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True)
    raw = provider.analyze_relationship({"case_id": "llm-velvet-spacex"}).raw
    assert raw is not None
    bad = dict(raw)
    bad["asset_role"] = "trade_signal"
    packet = {
        "event": {"event_id": "llm-velvet-spacex", "external_asset": "SpaceX"},
        "asset": {"coin_id": "velvet", "symbol": "VELVET"},
    }
    try:
        event_llm_analyzer.validate_llm_analysis(
            bad,
            packet,
            provider_name="fixture",
            model=None,
            prompt_version="llm_proxy_context_v1",
        )
    except event_llm_analyzer.EventLLMValidationError as exc:
        assert "invalid LLM asset_role" in str(exc)
    else:
        raise AssertionError("invalid LLM enum should be rejected")


def test_event_llm_fixture_provider_golden_outputs():
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    provider = FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True)
    expected = {
        "llm-btc-bitcoin-world": ("source_noise", "publisher_suffix_false_positive", "store_only"),
        "llm-xrp-ripple-effects": ("ticker_word_collision", "word_collision_false_positive", "store_only"),
        "llm-hype-word-collision": ("ticker_word_collision", "word_collision_false_positive", "store_only"),
        "llm-kcs-kucoin-source": ("source_noise", "publisher_suffix_false_positive", "store_only"),
        "llm-chainlink-world-cup": ("infrastructure", "infrastructure_provider", "store_only"),
        "llm-velvet-spacex": ("proxy_venue", "proxy_exposure", "radar_digest"),
        "llm-chz-world-cup": ("proxy_instrument", "proxy_attention", "watchlist"),
        "llm-btc-etf": ("direct_beneficiary", "direct_protocol_event", "store_only"),
    }
    for case_id, values in expected.items():
        raw = provider.analyze_relationship({"case_id": case_id}).raw
        assert raw is not None
        assert (raw["asset_role"], raw["relationship_type"], raw["recommended_alert_action"]) == values


def test_event_llm_evidence_packet_and_quote_verification():
    from crypto_rsi_scanner import event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result = _llm_golden_result()
    packet = _llm_packet_for(result, "llm-velvet-spacex", "velvet")
    assert packet["event"]["clean_title"] == "Velvet Capital offers synthetic exposure to SpaceX pre-IPO trading"
    assert "Velvet Capital offers synthetic exposure" in packet["event"]["original_titles"][0]
    assert packet["resolver"]["candidate_assets"]
    assert packet["external_catalyst"]["name"] == "SpaceX"

    provider = FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True)
    raw = provider.analyze_relationship(packet).raw
    assert raw is not None
    analysis = event_llm_analyzer.validate_llm_analysis(
        raw,
        packet,
        provider_name="fixture",
        model=None,
        prompt_version="llm_proxy_context_v1",
    )
    assert analysis.asset_role == "proxy_venue"
    assert analysis.relationship_type == "proxy_exposure"
    assert all(quote.found_in_source for quote in analysis.evidence_quotes)


def test_event_llm_missing_quote_clamps_confidence():
    from crypto_rsi_scanner import event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result = _llm_golden_result()
    packet = _llm_packet_for(result, "llm-invalid-quote", "velvet")
    provider = FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True)
    raw = provider.analyze_relationship(packet).raw
    assert raw is not None
    analysis = event_llm_analyzer.validate_llm_analysis(
        raw,
        packet,
        provider_name="fixture",
        model=None,
        prompt_version="llm_proxy_context_v1",
    )
    assert analysis.confidence == 0.50
    assert any(not quote.found_in_source for quote in analysis.evidence_quotes)
    assert any("not found in source text" in warning for warning in analysis.warnings)


def test_event_llm_openai_provider_missing_key_fails_soft():
    from crypto_rsi_scanner.llm_providers.openai_provider import OpenAILLMRelationshipProvider

    result = OpenAILLMRelationshipProvider(api_key="", model="test-model").analyze_relationship({})
    assert result.raw is None
    assert result.warning and "missing OPENAI_API_KEY" in result.warning


def test_event_llm_openai_provider_uses_configured_timeout():
    import json
    from crypto_rsi_scanner.llm_providers.openai_provider import (
        OpenAILLMExtractionProvider,
        OpenAILLMRelationshipProvider,
    )

    class FakeResponse:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"output_text": json.dumps(self.payload)}).encode("utf-8")

    seen: list[float] = []

    def relationship_opener(request, timeout):
        seen.append(timeout)
        return FakeResponse({
            "asset_role": "source_noise",
            "relationship_type": "publisher_suffix_false_positive",
            "recommended_alert_action": "store_only",
            "confidence": 0.86,
            "reason": "publisher name only",
            "evidence_quotes": [],
            "external_catalyst": {
                "name": None,
                "catalyst_type": "unknown",
                "event_time": None,
                "confidence": 0.0,
                "evidence_quotes": [],
            },
            "source_quality": {
                "source_origin": None,
                "source_confidence": 0.5,
                "timing_quality": "unknown",
                "notes": "fixture",
            },
            "warnings": [],
        })

    def extraction_opener(request, timeout):
        seen.append(timeout)
        return FakeResponse({
            "confidence": 0.80,
            "external_catalysts": [],
            "crypto_asset_mentions": [],
            "false_positive_terms": [],
            "event_date_hints": [],
            "suggested_followup_queries": [],
            "warnings": [],
        })

    relationship = OpenAILLMRelationshipProvider(
        api_key="test-key",
        model="test-model",
        timeout=4.25,
        opener=relationship_opener,
    ).analyze_relationship({})
    extraction = OpenAILLMExtractionProvider(
        api_key="test-key",
        model="test-model",
        timeout=5.5,
        opener=extraction_opener,
    ).extract_raw_event({})

    assert relationship.warning is None
    assert extraction.warning is None
    assert seen == [4.25, 5.5]


def test_event_llm_shadow_report_formats_disagreements_and_warnings():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alerts, event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result = _llm_golden_result()
    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True),
        cfg=event_llm_analyzer.EventLLMConfig(min_prefilter_score=0, max_candidates_per_run=50),
    )
    report = event_llm_analyzer.format_llm_shadow_report(rows)
    assert "EVENT LLM SHADOW REPORT" in report
    assert "rule:" in report
    assert "llm:" in report
    assert "DISAGREE" in report
    assert "one or more evidence quotes were not found in source text" in report


def test_event_llm_advisory_adjusts_research_alert_tiers_only():
    from dataclasses import replace
    from crypto_rsi_scanner import event_alerts

    _, alerts, rows = _llm_golden_alerts_and_rows()
    rule = {
        (alert.discovery_candidate.event.event_id, alert.coin_id): alert
        for alert in alerts
    }
    adjusted = event_alerts.apply_llm_advisory(alerts, rows, event_alerts.EventAlertConfig())
    by_key = {
        (alert.discovery_candidate.event.event_id, alert.coin_id): alert
        for alert in adjusted
    }

    assert rule[("llm-btc-bitcoin-world", "bitcoin")].tier == event_alerts.EventAlertTier.RADAR_DIGEST
    assert by_key[("llm-btc-bitcoin-world", "bitcoin")].tier == event_alerts.EventAlertTier.STORE_ONLY
    assert by_key[("llm-btc-bitcoin-world", "bitcoin")].effective_playbook_type == "source_noise_control"
    assert by_key[("llm-btc-bitcoin-world", "bitcoin")].rule_playbook_type != "source_noise_control"
    assert by_key[("llm-xrp-ripple-effects", "xrp")].tier == event_alerts.EventAlertTier.STORE_ONLY
    assert by_key[("llm-xrp-ripple-effects", "xrp")].effective_playbook_type == "source_noise_control"
    assert by_key[("llm-kcs-kucoin-source", "kucoin-shares")].tier == event_alerts.EventAlertTier.STORE_ONLY
    assert by_key[("llm-chainlink-world-cup", "chainlink")].tier.value in {"STORE_ONLY", "RADAR_DIGEST"}
    assert by_key[("llm-chainlink-world-cup", "chainlink")].effective_playbook_type == "infrastructure_mention"
    assert by_key[("llm-chz-world-cup", "chiliz")].tier == event_alerts.EventAlertTier.WATCHLIST
    assert by_key[("llm-chz-world-cup", "chiliz")].effective_playbook_type != "ambiguous_control"
    assert by_key[("llm-velvet-spacex", "velvet")].tier == event_alerts.EventAlertTier.RADAR_DIGEST
    assert by_key[("llm-velvet-spacex", "velvet")].original_tier == event_alerts.EventAlertTier.STORE_ONLY
    assert by_key[("llm-velvet-spacex", "velvet")].effective_playbook_type == "proxy_attention"
    assert "proxy_venue" in (by_key[("llm-velvet-spacex", "velvet")].llm_adjustment_reason or "")

    invalid = rule[("llm-invalid-quote", "velvet")]
    forced_store = [replace(invalid, tier=event_alerts.EventAlertTier.STORE_ONLY)]
    clamped = event_alerts.apply_llm_advisory(forced_store, rows, event_alerts.EventAlertConfig())[0]
    assert clamped.tier == event_alerts.EventAlertTier.STORE_ONLY
    assert clamped.llm_confidence == 0.50

    missing = event_alerts.apply_llm_advisory(alerts, [], event_alerts.EventAlertConfig())
    assert [alert.tier for alert in missing] == [alert.tier for alert in alerts]
    assert all(alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE for alert in adjusted)


def test_event_llm_advisory_does_not_create_or_remove_triggered_fade():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alerts

    result = _event_discovery_fixture_result()
    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    adjusted = event_alerts.apply_llm_advisory(alerts, [], event_alerts.EventAlertConfig())
    by_symbol = {alert.symbol: alert for alert in adjusted}
    assert by_symbol["TESTVELVET"].tier == event_alerts.EventAlertTier.TRIGGERED_FADE

    _, llm_alerts, rows = _llm_golden_alerts_and_rows()
    llm_adjusted = event_alerts.apply_llm_advisory(llm_alerts, rows, event_alerts.EventAlertConfig())
    assert all(alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE for alert in llm_adjusted)


def test_event_llm_advisory_report_formats_before_after_and_warnings():
    from crypto_rsi_scanner import event_alerts

    _, alerts, rows = _llm_golden_alerts_and_rows()
    adjusted = event_alerts.apply_llm_advisory(alerts, rows, event_alerts.EventAlertConfig())
    report = event_alerts.format_event_alert_report(adjusted)
    assert "llm: role=source_noise" in report
    assert "llm tier adjustment: RADAR_DIGEST -> STORE_ONLY" in report
    assert "llm adjustment reason:" in report
    assert "llm: role=proxy_venue" in report


def test_event_llm_cache_keys_include_provider_model_and_metadata():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    _, alerts, _ = _llm_golden_alerts_and_rows()
    result = _llm_golden_result()
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "llm_cache.json"
        provider = FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True)
        for model in ("model-a", "model-b"):
            event_llm_analyzer.analyze_event_candidates(
                result,
                alerts,
                provider,
                cfg=event_llm_analyzer.EventLLMConfig(
                    model=model,
                    min_prefilter_score=0,
                    max_candidates_per_run=1,
                    cache_path=cache_path,
                ),
            )
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        assert len(cache) == 2
        models = {entry["model"] for entry in cache.values()}
        assert models == {"model-a", "model-b"}
        for entry in cache.values():
            assert entry["schema_version"] == event_llm_analyzer.LLM_ANALYSIS_SCHEMA_VERSION
            assert entry["provider"] == "fixture"
            assert entry["prompt_version"] == "llm_proxy_context_v1"
            assert entry["packet_hash"]
            assert entry["analyzed_at"]
            assert isinstance(entry["raw"], dict)


def test_event_llm_runtime_deadline_skips_uncached_provider_calls():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_llm_analyzer
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
            max_candidates_per_run=2,
            deadline_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        ),
    )
    assert provider.calls == 0
    assert [row.cache_status for row in rows] == ["skipped_runtime", "skipped_runtime"]
    assert all(any("runtime deadline exhausted" in warning for warning in row.warnings) for row in rows)


def test_event_llm_relationship_calls_run_with_bounded_parallelism():
    import threading
    import time
    from crypto_rsi_scanner import event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    result, alerts, _ = _llm_golden_alerts_and_rows(min_prefilter_score=0)

    class SlowProvider:
        name = "fixture"
        model = "parallel-fixture"

        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.calls = 0
            self.lock = threading.Lock()

        def analyze_relationship(self, packet):
            with self.lock:
                self.active += 1
                self.calls += 1
                self.max_active = max(self.max_active, self.active)
            try:
                time.sleep(0.05)
                return LLMProviderResult(raw={
                    "asset_role": "source_noise",
                    "relationship_type": "publisher_suffix_false_positive",
                    "recommended_alert_action": "store_only",
                    "confidence": 0.86,
                    "reason": "parallel fixture",
                    "evidence_quotes": [],
                    "external_catalyst": {
                        "name": None,
                        "catalyst_type": "unknown",
                        "event_time": None,
                        "confidence": 0.0,
                        "evidence_quotes": [],
                    },
                    "source_quality": {
                        "source_origin": None,
                        "source_confidence": 0.5,
                        "timing_quality": "unknown",
                        "notes": "parallel fixture",
                    },
                    "warnings": [],
                })
            finally:
                with self.lock:
                    self.active -= 1

    provider = SlowProvider()
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        provider,
        cfg=event_llm_analyzer.EventLLMConfig(
            min_prefilter_score=0,
            max_candidates_per_run=4,
            max_parallel_calls=4,
            require_evidence_quotes=False,
        ),
    )
    assert provider.calls == 4
    assert provider.max_active > 1
    assert len(rows) == 4
    assert [row.cache_status for row in rows] == ["miss", "miss", "miss", "miss"]


def test_event_llm_budget_ledger_persists_daily_caps_and_cost_limit():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result, alerts, _ = _llm_golden_alerts_and_rows(min_prefilter_score=0)

    class CountingProvider(FixtureLLMRelationshipProvider):
        def __init__(self, path):
            super().__init__(path, required=True)
            self.calls = 0

        def analyze_relationship(self, packet):
            self.calls += 1
            return super().analyze_relationship(packet)

    with tempfile.TemporaryDirectory() as tmp:
        ledger_path = Path(tmp) / "llm_budget.json"
        first = CountingProvider(_llm_golden_fixture_path())
        rows = event_llm_analyzer.analyze_event_candidates(
            result,
            alerts[:1],
            first,
            cfg=event_llm_analyzer.EventLLMConfig(
                min_prefilter_score=0,
                max_candidates_per_run=1,
                max_calls_per_day=1,
                budget_ledger_path=ledger_path,
                estimated_cost_per_call_usd=0.02,
                max_estimated_cost_usd_per_day=0.02,
            ),
        )
        assert first.calls == 1
        assert rows[0].cache_status == "miss"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        entry = ledger["entries"][0]
        assert entry["relationship_calls_attempted"] == 1
        assert entry["estimated_cost_usd"] == 0.02

        second = CountingProvider(_llm_golden_fixture_path())
        skipped = event_llm_analyzer.analyze_event_candidates(
            result,
            alerts[:1],
            second,
            cfg=event_llm_analyzer.EventLLMConfig(
                min_prefilter_score=0,
                max_candidates_per_run=1,
                max_calls_per_day=1,
                budget_ledger_path=ledger_path,
                estimated_cost_per_call_usd=0.02,
                max_estimated_cost_usd_per_day=0.02,
            ),
        )
        assert second.calls == 0
        assert skipped[0].cache_status == "skipped_budget"
        assert any("budget" in warning for warning in skipped[0].warnings)


def test_makefile_has_event_llm_eval_target():
    from pathlib import Path

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-llm-eval:" in text
    assert "python -m crypto_rsi_scanner.event_llm_eval" in text or "$(PYTHON) -m crypto_rsi_scanner.event_llm_eval" in text
    assert "event-alert-no-key-llm-report:" in text


def test_event_alpha_profiles_and_make_targets_are_available():
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_profiles

    fixture = event_alpha_profiles.get_profile("fixture")
    assert fixture.config_overrides["EVENT_CATALYST_SEARCH_PROVIDER"] == "fixture"
    no_key = event_alpha_profiles.get_profile("no_key_live")
    assert no_key.config_overrides["EVENT_CATALYST_SEARCH_PROVIDERS"] == ("gdelt", "rss", "polymarket")
    send = event_alpha_profiles.get_profile("research_send")
    assert send.send is True
    report = event_alpha_profiles.format_profile_report(send)
    assert "still requires --event-alert-send" in report
    assert "artifact policy:" in report
    assert event_alpha_profiles.artifact_policy(send)["snapshot_policy"] == "alertable"
    assert event_alpha_profiles.artifact_policy(send)["card_auto_write"] is True
    try:
        event_alpha_profiles.get_profile("unknown")
    except ValueError as exc:
        assert "choose one of" in str(exc)
    else:
        raise AssertionError("unknown Event Alpha profile should fail")

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-cycle-profile:" in text
    assert "--event-alpha-profile $(PROFILE)" in text


def test_event_alpha_artifact_context_display_uses_relative_paths():
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_artifacts, scanner

    context = event_alpha_artifacts.context_from_profile(
        "fixture",
        base_dir=Path("event_fade_cache").resolve(),
        artifact_namespace="display_paths",
    )
    text = scanner._event_alpha_context_block(context)  # noqa: SLF001

    assert "artifact context:" in text
    assert "- run_ledger_path: event_fade_cache/display_paths/event_alpha_runs.jsonl" in text
    assert "- research_cards_dir: event_fade_cache/display_paths/research_cards" in text
    assert "/Users/" not in text
    assert "/tmp/" not in text


def test_event_llm_golden_eval_passes_and_detects_mismatch():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_llm_eval

    result = event_llm_eval.run_fixture_eval(_llm_golden_fixture_path())
    assert result.success
    assert result.passed_cases == result.total_cases == 9
    assert any("llm-invalid-quote" in warning for warning in result.warnings)
    assert "PASS: all golden cases matched" in event_llm_eval.format_eval_result(result)

    with tempfile.TemporaryDirectory() as tmp:
        source = json.loads(_llm_golden_fixture_path().read_text(encoding="utf-8"))
        source["llm_outputs"][0]["expected"] = {
            "asset_role": "proxy_instrument",
            "relationship_type": source["llm_outputs"][0]["analysis"]["relationship_type"],
            "recommended_alert_action": source["llm_outputs"][0]["analysis"]["recommended_alert_action"],
        }
        path = Path(tmp) / "bad_llm_eval.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        failed = event_llm_eval.run_fixture_eval(path)
        assert not failed.success
        assert any("asset_role expected" in mismatch for mismatch in failed.mismatches)


def test_event_llm_extractor_models_fixture_outputs_and_quote_validation():
    from crypto_rsi_scanner import event_llm_extractor
    from crypto_rsi_scanner.event_llm_extraction_models import (
        ASSET_MENTION_TYPE_VALUES,
        CATALYST_TYPE_VALUES,
    )
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMExtractionProvider

    assert "project_or_token" in ASSET_MENTION_TYPE_VALUES
    assert "ipo_proxy" in CATALYST_TYPE_VALUES
    raw_events, rows = _llm_extraction_rows()
    by_raw = {row.raw_event.raw_id: row for row in rows}
    velvet = by_raw["extract-velvet-spacex"].extraction
    assert velvet is not None
    assert velvet.external_catalysts[0].name == "SpaceX"
    assert velvet.crypto_asset_mentions[0].symbol == "VELVET"
    assert all(quote.found_in_source for quote in velvet.crypto_asset_mentions[0].evidence_quotes)

    invalid = by_raw["extract-invalid-quote"].extraction
    assert invalid is not None
    assert invalid.confidence == 0.50
    assert any("not found in source text" in warning for warning in invalid.warnings)

    provider = FixtureLLMExtractionProvider(_llm_extraction_golden_fixture_path(), required=True)
    raw = provider.extract_raw_event({"case_id": "extract-velvet-spacex"}).raw
    assert raw is not None
    bad = dict(raw)
    bad["crypto_asset_mentions"] = [dict(raw["crypto_asset_mentions"][0], mention_type="trade_signal")]
    packet = event_llm_extractor.build_raw_event_packet(raw_events[0])
    try:
        event_llm_extractor.validate_llm_extraction(
            bad,
            packet,
            provider_name="fixture",
            model=None,
            prompt_version="llm_raw_event_extraction_v1",
        )
    except event_llm_extractor.EventLLMExtractionValidationError as exc:
        assert "invalid LLM extraction mention_type" in str(exc)
    else:
        raise AssertionError("invalid extraction enum should be rejected")


def test_event_llm_extractor_identifies_source_noise_and_word_collisions():
    _, rows = _llm_extraction_rows()
    by_raw = {row.raw_event.raw_id: row for row in rows}
    bitcoin_world = by_raw["extract-bitcoin-world-source-noise"].extraction
    ripple = by_raw["extract-ripple-effects"].extraction
    hype = by_raw["extract-hype-word-collision"].extraction
    assert bitcoin_world is not None and bitcoin_world.false_positive_terms[0].text == "Bitcoin World"
    assert bitcoin_world.crypto_asset_mentions[0].mention_type == "publisher_or_source"
    assert ripple is not None and ripple.false_positive_terms[0].text == "ripple effects"
    assert ripple.crypto_asset_mentions[0].mention_type == "ordinary_word"
    assert hype is not None and hype.false_positive_terms[0].text == "hype"
    assert hype.crypto_asset_mentions[0].mention_type == "ordinary_word"


def test_event_llm_extractor_runtime_deadline_skips_uncached_provider_calls():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_llm_extractor
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="deadline-proxy",
        provider="news",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/deadline-proxy",
        title="SpaceX pre-IPO exposure opens through DEADLINE token",
        body="DEADLINE token offers synthetic exposure to SpaceX pre-IPO markets.",
        raw_json={},
        source_confidence=0.90,
        content_hash="deadline-proxy",
    )

    class Provider:
        name = "fixture"

        def __init__(self):
            self.calls = 0

        def extract_raw_event(self, packet):
            self.calls += 1
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
        [raw],
        provider,
        cfg=event_llm_extractor.EventLLMExtractorConfig(
            max_events_per_run=1,
            deadline_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        ),
    )
    assert provider.calls == 0
    assert rows[0].cache_status == "skipped_runtime"
    assert any("runtime deadline exhausted" in warning for warning in rows[0].warnings)


def test_event_llm_extractor_calls_run_with_bounded_parallelism():
    import threading
    import time
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_llm_extractor
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw_events = [
        RawDiscoveredEvent(
            raw_id=f"parallel-proxy-{idx}",
            provider="news",
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/parallel-proxy-{idx}",
            title=f"SpaceX pre-IPO exposure opens through PAR{idx} token",
            body=f"PAR{idx} token offers synthetic exposure to SpaceX pre-IPO markets.",
            raw_json={},
            source_confidence=0.90,
            content_hash=f"parallel-proxy-{idx}",
        )
        for idx in range(4)
    ]

    class SlowProvider:
        name = "fixture"
        model = "parallel-fixture"

        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.calls = 0
            self.lock = threading.Lock()

        def extract_raw_event(self, packet):
            with self.lock:
                self.active += 1
                self.calls += 1
                self.max_active = max(self.max_active, self.active)
            try:
                time.sleep(0.05)
                return LLMProviderResult(raw={
                    "confidence": 0.80,
                    "external_catalysts": [],
                    "crypto_asset_mentions": [],
                    "false_positive_terms": [],
                    "event_date_hints": [],
                    "suggested_followup_queries": [],
                    "warnings": [],
                })
            finally:
                with self.lock:
                    self.active -= 1

    provider = SlowProvider()
    rows = event_llm_extractor.analyze_raw_events(
        raw_events,
        provider,
        cfg=event_llm_extractor.EventLLMExtractorConfig(
            max_events_per_run=4,
            max_parallel_calls=4,
            require_evidence_quotes=False,
        ),
    )
    assert provider.calls == 4
    assert provider.max_active > 1
    assert len(rows) == 4
    assert [row.cache_status for row in rows] == ["miss", "miss", "miss", "miss"]


def test_event_llm_extractor_openai_missing_key_fails_soft():
    from crypto_rsi_scanner.llm_providers.openai_provider import OpenAILLMExtractionProvider

    result = OpenAILLMExtractionProvider(api_key="", model="test-model").extract_raw_event({})
    assert result.raw is None
    assert result.warning and "missing OPENAI_API_KEY" in result.warning


def test_event_llm_extractor_enrichment_still_requires_resolver_validation():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery, event_llm_extractor
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent
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
                    "name": "Missed Proxy",
                    "symbol": "MISS",
                    "coin_id": None,
                    "contract_address": None,
                    "mention_type": "project_or_token",
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "MISS is the ticker", "source_field": "body", "supports": "asset mention"}],
                }],
                "false_positive_terms": [],
                "event_date_hints": [],
                "suggested_followup_queries": [],
                "warnings": [],
            })

    raw = RawDiscoveredEvent(
        raw_id="extract-missed-proxy",
        provider="test",
        fetched_at=datetime(2026, 6, 16, 12, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 16, 11, tzinfo=timezone.utc),
        source_url="https://example.test/missed-proxy",
        title="SpaceX exposure market opens",
        body="A source says MISS is the ticker for a new SpaceX exposure proxy.",
        raw_json={},
        source_confidence=0.90,
        content_hash="abc",
    )
    rows = event_llm_extractor.analyze_raw_events([raw], Provider())
    enriched = event_llm_extractor.enrich_raw_events_with_extractions([raw], rows)
    assert "LLM extracted research hints" in (enriched[0].body or "")
    assert event_discovery.run_discovery(enriched, [], now=datetime(2026, 6, 16, 12, tzinfo=timezone.utc)).candidates == ()

    assets = [DiscoveredAsset(
        coin_id="missed-proxy",
        symbol="MISS",
        name="Missed Proxy",
        aliases=("missed proxy", "miss"),
    )]
    result = event_discovery.run_discovery(
        enriched,
        assets,
        now=datetime(2026, 6, 16, 12, tzinfo=timezone.utc),
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].asset.coin_id == "missed-proxy"


def test_event_llm_extract_report_and_eval_pass():
    from crypto_rsi_scanner import event_llm_extract_eval, event_llm_extractor

    _, rows = _llm_extraction_rows()
    report = event_llm_extractor.format_llm_extract_report(rows)
    assert "EVENT LLM RAW EXTRACTION REPORT" in report
    assert "Velvet Capital/VELVET" in report
    assert "false-positive terms: Bitcoin World" in report
    assert "warning: one or more evidence quotes were not found in source text" in report

    result = event_llm_extract_eval.run_fixture_eval(_llm_extraction_golden_fixture_path())
    assert result.success
    assert result.passed_cases == result.total_cases == 7
    assert any("extract-invalid-quote" in warning for warning in result.warnings)
    assert "PASS: all golden cases matched" in event_llm_extract_eval.format_eval_result(result)


def test_makefile_has_event_llm_extract_eval_target():
    from pathlib import Path

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-llm-extract-eval:" in text
    assert "crypto_rsi_scanner.event_llm_extract_eval" in text


def test_event_llm_extract_scanner_report_uses_runtime_config():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner, event_alpha_notification_delivery as delivery

    path = _llm_extraction_golden_fixture_path()
    original = {
        "EVENT_DISCOVERY_EVENTS_PATH": config.EVENT_DISCOVERY_EVENTS_PATH,
        "EVENT_DISCOVERY_ALIASES_PATH": config.EVENT_DISCOVERY_ALIASES_PATH,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH": config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": config.EVENT_DISCOVERY_COINMARKETCAL_PATH,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": config.EVENT_DISCOVERY_TOKENOMIST_PATH,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        "EVENT_DISCOVERY_GDELT_PATH": config.EVENT_DISCOVERY_GDELT_PATH,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH": config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH,
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH": config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH": config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH,
        "EVENT_DISCOVERY_UNIVERSE_PATH": config.EVENT_DISCOVERY_UNIVERSE_PATH,
        "EVENT_DISCOVERY_LOOKBACK_HOURS": config.EVENT_DISCOVERY_LOOKBACK_HOURS,
        "EVENT_DISCOVERY_HORIZON_DAYS": config.EVENT_DISCOVERY_HORIZON_DAYS,
        "EVENT_LLM_EXTRACTOR_ENABLED": config.EVENT_LLM_EXTRACTOR_ENABLED,
        "EVENT_LLM_EXTRACTOR_MODE": config.EVENT_LLM_EXTRACTOR_MODE,
        "EVENT_LLM_EXTRACTOR_PROVIDER": config.EVENT_LLM_EXTRACTOR_PROVIDER,
        "EVENT_LLM_EXTRACTOR_MODEL": config.EVENT_LLM_EXTRACTOR_MODEL,
        "EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT": config.EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT,
        "EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN": config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN,
        "EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES": config.EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES,
        "EVENT_LLM_EXTRACTOR_CACHE_PATH": config.EVENT_LLM_EXTRACTOR_CACHE_PATH,
        "EVENT_LLM_EXTRACTOR_PROMPT_VERSION": config.EVENT_LLM_EXTRACTOR_PROMPT_VERSION,
        "EVENT_LLM_BUDGET_LEDGER_PATH": config.EVENT_LLM_BUDGET_LEDGER_PATH,
        "EVENT_LLM_MAX_PARALLEL_CALLS": config.EVENT_LLM_MAX_PARALLEL_CALLS,
    }
    budget_tmp = tempfile.TemporaryDirectory()
    config.EVENT_DISCOVERY_EVENTS_PATH = path
    config.EVENT_DISCOVERY_ALIASES_PATH = _llm_golden_fixture_path()
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    config.EVENT_DISCOVERY_LOOKBACK_HOURS = 120
    config.EVENT_DISCOVERY_HORIZON_DAYS = 14
    config.EVENT_LLM_EXTRACTOR_ENABLED = False
    config.EVENT_LLM_EXTRACTOR_MODE = "shadow"
    config.EVENT_LLM_EXTRACTOR_PROVIDER = "fixture"
    config.EVENT_LLM_EXTRACTOR_MODEL = None
    config.EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT = 30.0
    config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN = 50
    config.EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES = True
    config.EVENT_LLM_EXTRACTOR_CACHE_PATH = None
    config.EVENT_LLM_EXTRACTOR_PROMPT_VERSION = "llm_raw_event_extraction_v1"
    config.EVENT_LLM_BUDGET_LEDGER_PATH = Path(budget_tmp.name) / "event_llm_budget.json"
    config.EVENT_LLM_MAX_PARALLEL_CALLS = 1
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_llm_extract_report(event_now="2026-06-15T16:00:00Z")
        text = out.getvalue()
        assert "EVENT LLM RAW EXTRACTION REPORT" in text
        assert "extract-velvet-spacex" in text
        assert "Velvet Capital/VELVET" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)
        budget_tmp.cleanup()


def test_event_market_enrichment_from_coingecko_rows():
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_market_enrichment
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
    from crypto_rsi_scanner import event_discovery, event_market_enrichment
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent

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
    from crypto_rsi_scanner import event_alerts, event_anomaly_scanner, event_discovery, event_market_enrichment
    from crypto_rsi_scanner.event_models import DiscoveredAsset

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


def test_event_alerts_resolve_playbook_first_tiers_and_trigger_guards():
    from dataclasses import replace
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alerts, event_fade, event_playbooks

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


def test_event_alpha_cycle_search_loop_uses_fixture_evidence_and_respects_limits():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alerts,
        event_alpha_pipeline,
        event_anomaly_scanner,
        event_catalyst_search,
        event_discovery,
        event_market_enrichment,
        event_playbooks,
    )
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent

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
    from crypto_rsi_scanner import (
        event_alerts,
        event_anomaly_state,
        event_catalyst_search,
        event_discovery,
    )
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent

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


def test_event_playbooks_classify_proxy_attention_direct_infrastructure_and_noise():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alerts, event_discovery, event_playbooks
    from crypto_rsi_scanner.event_models import (
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
    from crypto_rsi_scanner import event_alerts, event_graph
    from crypto_rsi_scanner.event_models import (
        DiscoveredAsset,
        DiscoveredEventFadeCandidate,
        EventAssetLink,
        EventClassification,
        EventDiscoveryResult,
        NormalizedEvent,
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

    result = EventDiscoveryResult(
        raw_events=(),
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
    assert "sources: total=3 independent=3" in report
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
    from crypto_rsi_scanner import event_alerts, event_graph
    from crypto_rsi_scanner.event_models import (
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
    assert by_symbol["LIST"].score_components["cluster_confirmation"] > 0
    assert by_symbol["UNLOCK"].score_components["cluster_confirmation"] > 0
    assert by_symbol["PERP"].score_components["cluster_confirmation"] > 0
    assert by_symbol["LINK"].score_components["cluster_confirmation"] == 0


def test_event_impact_hypotheses_generate_seed_categories_and_queries():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import config, event_impact_hypotheses
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body, *, provider="fixture", event_type="external_proxy_event", external="SpaceX"):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
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
                    "event_time": "2026-06-20T13:30:00Z",
                    "event_time_confidence": 0.9,
                    "external_asset": external,
                    "description": body,
                    "confidence": 0.9,
                }
            },
            source_confidence=0.9,
            content_hash=raw_id,
        )

    def norm(raw_event, *, event_type="external_proxy_event", external="SpaceX"):
        return NormalizedEvent(
            event_id=raw_event.raw_id,
            raw_ids=(raw_event.raw_id,),
            event_name=raw_event.title,
            event_type=event_type,
            event_time=now,
            event_time_confidence=0.9,
            first_seen_time=now,
            source=raw_event.provider,
            source_urls=(raw_event.source_url,),
            external_asset=external,
            description=raw_event.body,
            confidence=0.9,
        )

    rows = [
        raw("spacex", "SpaceX pre-IPO exposure opens", "Tokenized stock venue launches SpaceX pre-IPO exposure."),
        raw("openai", "OpenAI pre-IPO market opens", "Crypto traders discuss OpenAI pre-IPO proxy exposure.", external="OpenAI"),
        raw("worldcup", "World Cup fan token prediction market", "CHZ-style fan tokens move before World Cup match.", event_type="sports_event", external="World Cup"),
        raw("genius", "GENIUS Act stablecoin reserve bill", "Stablecoin reserve rules and money market funds move forward.", event_type="regulatory_event", external="GENIUS Act"),
        RawDiscoveredEvent(
            raw_id="anomaly",
            provider="market_anomaly",
            fetched_at=now,
            published_at=now,
            source_url=None,
            title="PUMP market anomaly",
            body="No dated external catalyst found.",
            raw_json={"market": {"symbol": "PUMP", "coin_id": "pump"}, "anomaly": {"score": 90}},
            source_confidence=0.7,
            content_hash="anomaly",
        ),
    ]
    result = EventDiscoveryResult(
        raw_events=tuple(rows),
        normalized_events=tuple(norm(row, event_type=row.raw_json["event"]["event_type"], external=row.raw_json["event"]["external_asset"]) for row in rows if row.provider != "market_anomaly"),
        links=(),
        classifications=(),
        candidates=(),
    )
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(result, now=now)
    categories = {item.impact_category for item in hypotheses}
    assert "rwa_preipo_proxy" in categories
    assert "tokenized_stock_venue" in categories
    assert "ai_ipo_proxy" in categories
    assert "sports_fan_proxy" in categories
    assert "stablecoin_regulatory" in categories
    assert "market_anomaly_unknown" in categories
    spacex = next(item for item in hypotheses if item.impact_category == "rwa_preipo_proxy")
    assert "tokenized_stock_venues" in spacex.candidate_sectors
    assert "VELVET" in spacex.candidate_symbols
    assert any("VELVET SpaceX exposure" in query for query in spacex.search_queries)
    assert any("VELVET SpaceX pre-IPO exposure" in query for query in spacex.search_queries)
    assert any(
        detail["query_type"] == "candidate_discovery" and detail["query"] == "SpaceX crypto exposure"
        for detail in spacex.search_query_details
    )
    anomaly = next(item for item in hypotheses if item.impact_category == "market_anomaly_unknown")
    assert anomaly.status == "hypothesis"
    assert "TRIGGERED_FADE" not in event_impact_hypotheses.format_impact_hypothesis_report(hypotheses)


def test_event_impact_hypothesis_matching_uses_context_not_substrings():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_impact_hypotheses
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def row(raw_id, title, body, event_type="news", external=None):
        raw = RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture",
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
                    "external_asset": external,
                    "description": body,
                    "confidence": 0.85,
                }
            },
            source_confidence=0.85,
            content_hash=raw_id,
        )
        event = NormalizedEvent(
            event_id=raw_id,
            raw_ids=(raw_id,),
            event_name=title,
            event_type=event_type,
            event_time=None,
            event_time_confidence=0.0,
            first_seen_time=now,
            source="fixture",
            source_urls=(raw.source_url,),
            external_asset=external,
            description=body,
            confidence=0.85,
        )
        return raw, event

    negatives = [
        row("matched", "Matched market-anomaly filters", "The market signal was matched by research filters."),
        row("open", "Open interest rises", "Open markets and open-source tools are not OpenAI proxy catalysts."),
        row("prime", "Prime liquidity improves", "Prime market depth improved without prime minister or election context."),
        row("hype", "IPO hype builds", "Generic IPO hype without HYPE, Hyperliquid, tokenized stock, or explicit exposure."),
    ]
    result = EventDiscoveryResult(
        raw_events=tuple(raw for raw, _ in negatives),
        normalized_events=tuple(event for _, event in negatives),
        links=(),
        classifications=(),
        candidates=(),
    )
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(result, now=now)
    categories = {item.impact_category for item in hypotheses}
    assert "sports_fan_proxy" not in categories
    assert "ai_ipo_proxy" not in categories
    assert "political_meme_proxy" not in categories
    assert "rwa_preipo_proxy" not in categories

    positives = [
        row("sports", "World Cup fan token fixture", "Fan token attention rises before the World Cup kickoff.", "sports_event", "World Cup"),
        row("political", "Election meme prediction market", "Political meme tokens move around an election prediction market.", "political_event", "Election"),
        row("infra", "Prediction market oracle selected", "Chainlink oracle infrastructure will settle prediction market outcomes.", "infrastructure_event", "Polymarket"),
        row("stable", "GENIUS Act stablecoin reserve bill", "Stablecoin reserve regulation advances in the Senate.", "regulatory_event", "GENIUS Act"),
    ]
    positive_result = EventDiscoveryResult(
        raw_events=tuple(raw for raw, _ in positives),
        normalized_events=tuple(event for _, event in positives),
        links=(),
        classifications=(),
        candidates=(),
    )
    positive_categories = {
        item.impact_category
        for item in event_impact_hypotheses.generate_impact_hypotheses(positive_result, now=now)
    }
    assert "sports_fan_proxy" in positive_categories
    assert "political_meme_proxy" in positive_categories
    assert "prediction_market_infra" in positive_categories
    assert "stablecoin_regulatory" in positive_categories


def test_event_impact_hypothesis_category_refinements_for_validated_news():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_impact_hypotheses
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)

    def row(raw_id, title, body, event_type="news", external=None):
        raw = RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture",
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.85,
            content_hash=raw_id,
        )
        event = NormalizedEvent(
            event_id=raw_id,
            raw_ids=(raw_id,),
            event_name=title,
            event_type=event_type,
            event_time=None,
            event_time_confidence=0.0,
            first_seen_time=now,
            source="fixture",
            source_urls=(raw.source_url,),
            external_asset=external,
            description=body,
            confidence=0.85,
        )
        return raw, event

    cases = [
        row(
            "arb-prediction",
            "Arbitrum and Ethereum prediction market platform expands",
            "Arbitrum smart contracts and Ethereum settlement support a new prediction market platform for a Mike Tyson fight.",
            "infrastructure_event",
            "Polymarket",
        ),
        row(
            "sol-tokenized-equity",
            "Solana tokenized equity volume grows",
            "Solana venue activity rises as tokenized stock markets and synthetic exposure products gain volume.",
            "rwa_event",
            "tokenized equity",
        ),
        row(
            "btc-quantum-policy",
            "Bitcoin quantum-computing policy shock draws Trump comments",
            "Bitcoin technology risk rises as quantum-computing policy debate and Trump comments hit crypto headlines.",
            "technology_risk",
            "unknown",
        ),
        row(
            "zec-listing",
            "Zcash miner Nasdaq listing opens",
            "A Zcash mining company completes a public listing; liquidity and market access may change.",
            "listing_event",
            "Nasdaq",
        ),
        row(
            "rune-exploit",
            "THORChain exploit investigation begins",
            "THORChain RUNE faces an exploit and security incident investigation after an attack.",
            "security_event",
            "THORChain",
        ),
        row(
            "chz-world-cup",
            "World Cup fan token prediction market",
            "CHZ-style fan tokens move before a World Cup fixture and team kickoff.",
            "sports_event",
            "World Cup",
        ),
    ]
    result = EventDiscoveryResult(
        raw_events=tuple(raw for raw, _ in cases),
        normalized_events=tuple(event for _, event in cases),
        links=(),
        classifications=(),
        candidates=(),
    )
    by_event: dict[str, set[str]] = {}
    for item in event_impact_hypotheses.generate_impact_hypotheses(result, now=now):
        by_event.setdefault(item.source_event_ids[0], set()).add(item.impact_category)

    assert "prediction_market_infra" in by_event["arb-prediction"]
    assert "political_meme_proxy" not in by_event["arb-prediction"]
    assert {"tokenized_stock_venue", "rwa_preipo_proxy"} & by_event["sol-tokenized-equity"]
    assert "political_meme_proxy" not in by_event["sol-tokenized-equity"]
    assert "security_or_regulatory_shock" in by_event["btc-quantum-policy"]
    assert "political_meme_proxy" not in by_event["btc-quantum-policy"]
    assert "listing_liquidity_event" in by_event["zec-listing"]
    assert "security_or_regulatory_shock" not in by_event["zec-listing"]
    assert "security_or_regulatory_shock" in by_event["rune-exploit"]
    assert "sports_fan_proxy" in by_event["chz-world-cup"]


def test_event_impact_hypothesis_validation_is_identity_safe():
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_catalyst_search, event_impact_hypotheses
    from crypto_rsi_scanner import event_watchlist
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent
    from pathlib import Path

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp-test",
        event_cluster_id="spacex|ipo_proxy|2026-06-20",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category="rwa_preipo_proxy",
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET", "HYPE"),
        candidate_coin_ids=("velvet", "hyperliquid"),
        direction_hint="up_then_fade",
        playbook_hint="rwa_preipo_proxy",
        confidence=0.82,
        search_queries=("VELVET SpaceX pre-IPO exposure",),
        status="validation_search_pending",
    )

    queries = event_catalyst_search.generate_search_queries_for_hypothesis(hypothesis)
    assert "VELVET SpaceX exposure" in queries
    assert "VELVET SpaceX pre-IPO" in queries
    assert "VELVET SpaceX pre-IPO exposure" in queries
    assert "HYPE tokenized stock SpaceX" in queries
    specs = event_catalyst_search.generate_search_query_specs_for_hypothesis(hypothesis)
    assert any(spec.query_type == "candidate_discovery" and spec.query == "SpaceX crypto exposure" for spec in specs)

    good = RawDiscoveredEvent(
        raw_id="good",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/velvet-spacex",
        title="VELVET opens SpaceX pre-IPO exposure",
        body="Velvet Capital users can trade tokenized stock style exposure to SpaceX.",
        raw_json={},
        source_confidence=0.9,
        content_hash="good",
    )
    catalyst_only = RawDiscoveredEvent(
        raw_id="catalyst-only",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/spacex",
        title="SpaceX pre-IPO market attention rises",
        body="No crypto token is named.",
        raw_json={},
        source_confidence=0.9,
        content_hash="catalyst-only",
    )
    url_only = RawDiscoveredEvent(
        raw_id="url-only",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/search?q=VELVET+SpaceX",
        title="SpaceX pre-IPO market attention rises",
        body="No crypto token is named.",
        raw_json={},
        source_confidence=0.9,
        content_hash="url-only",
    )

    validated = event_impact_hypotheses.validate_hypotheses_with_raw_events([hypothesis], [good])[0]
    assert validated.status == "validated"
    assert validated.hypothesis_scope == "token"
    assert validated.candidate_symbols == ("VELVET",)
    assert any("identity_match" in reason for reason in validated.validation_reasons)
    with tempfile.TemporaryDirectory() as tmp:
        cfg = event_watchlist.EventWatchlistConfig(enabled=True, state_path=Path(tmp) / "watchlist.jsonl")
        first = event_watchlist.refresh_hypothesis_watchlist([hypothesis], cfg=cfg, now=now)
        second = event_watchlist.refresh_hypothesis_watchlist([validated], cfg=cfg, now=now)
        assert first.entries[0].state == event_watchlist.EventWatchlistState.HYPOTHESIS.value
        assert first.entries[0].symbol == "SECTOR"
        assert first.entries[0].coin_id == "rwa_preipo_proxy"
        assert first.entries[0].latest_score_components["candidate_symbols"] == ["VELVET", "HYPE"]
        assert first.entries[0].should_alert is False
        assert second.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert second.entries[0].symbol == "VELVET"
        assert second.entries[0].coin_id == "velvet"
        assert second.entries[0].should_alert is True
        assert second.entries[0].state != event_watchlist.EventWatchlistState.TRIGGERED_FADE.value
    unchanged = event_impact_hypotheses.validate_hypotheses_with_raw_events([hypothesis], [catalyst_only])[0]
    assert unchanged.status == "rejected"
    assert unchanged.validation_stage == event_impact_hypotheses.ValidationStage.REJECTED.value
    assert "source_mentions_catalyst_without_candidate_asset" in unchanged.rejection_reasons
    rejected = event_impact_hypotheses.validate_hypotheses_with_raw_events([hypothesis], [url_only])[0]
    assert rejected.status != "validated"


def test_event_impact_path_validation_distinguishes_real_impact_from_cooccurrence():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import config, event_impact_hypotheses
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent

    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body, market=None, provider="fixture_search"):
        market_payload = dict(market or {}) if market is not None else None
        if market_payload is not None:
            market_payload.setdefault("observed_at", now.isoformat())
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json={"market": market_payload or {}} if market is not None else {},
            source_confidence=0.9,
            content_hash=raw_id,
        )

    def hypothesis(hypothesis_id, symbol, coin_id, category, external="unknown"):
        return event_impact_hypotheses.EventImpactHypothesis(
            hypothesis_id=hypothesis_id,
            event_cluster_id=f"cluster:{hypothesis_id}",
            event_type="news",
            external_asset=external,
            impact_category=category,
            candidate_sectors=("direct_token_events",),
            candidate_symbols=(symbol,),
            candidate_coin_ids=(coin_id,),
            direction_hint="volatility",
            playbook_hint=category,
            confidence=0.85,
            hypothesis_score=70,
            validation_stage=event_impact_hypotheses.ValidationStage.VALIDATION_SEARCH_PENDING.value,
            status=event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value,
        )

    cases = [
        (
            hypothesis("hyp:rune", "RUNE", "thorchain", "security_or_regulatory_shock", "THORChain"),
            raw(
                "rune",
                "THORChain exploit investigation",
                "THORChain RUNE faces an exploit and security incident after an attack.",
                market={"return_24h": 0.32, "volume_zscore_24h": 3.4, "volume_to_market_cap": 0.28},
            ),
            "exploit_security_event",
            "impact_path_validated",
            "exploit_security_event",
            "direct_subject",
            "strong",
            "watchlist",
        ),
        (
            hypothesis("hyp:zec", "ZEC", "zcash", "listing_liquidity_event", "Nasdaq"),
            raw(
                "zec",
                "Zcash miner Nasdaq listing opens",
                "Zcash ZEC miner completes a Nasdaq listing and public market access changes.",
                market={"return_72h": 0.54, "volume_zscore_24h": 2.5},
            ),
            "listing_liquidity_event",
            "impact_path_validated",
            "listing_liquidity_event",
            "direct_subject",
            "strong",
            "watchlist",
        ),
        (
            hypothesis("hyp:chz", "CHZ", "chiliz", "sports_fan_proxy", "World Cup"),
            raw(
                "chz",
                "World Cup fan token demand",
                "CHZ fan token demand rises into a World Cup fixture and team kickoff.",
                market={"return_24h": 0.27, "volume_zscore_24h": 3.1, "relative_strength_vs_btc": 0.20},
            ),
            "fan_token_event",
            "impact_path_validated",
            "fan_token_attention",
            "proxy_instrument",
            "strong",
            "watchlist",
        ),
        (
            hypothesis("hyp:btc", "BTC", "bitcoin", "security_or_regulatory_shock", "unknown"),
            raw("btc", "Bitcoin quantum policy debate", "Bitcoin quantum-computing policy debate and Trump comments hit broad crypto headlines."),
            "generic_policy_only",
            "catalyst_link_validated",
            "technology_risk",
            "macro_affected_asset",
            "weak",
            "local_only",
        ),
        (
            hypothesis("hyp:cftc", "BTC", "bitcoin", "security_or_regulatory_shock", "CFTC"),
            raw("cftc", "CFTC chair talks perps", "The CFTC chair discussed perps generally while Bitcoin appeared in broader market coverage."),
            "generic_policy_only",
            "catalyst_link_validated",
            "market_structure_policy",
            "macro_affected_asset",
            "weak",
            "local_only",
        ),
        (
            hypothesis("hyp:re", "RE", "real", "political_meme_proxy", "Trump"),
            raw("re", "Trump quantum cryptography order", "Trump quantum cryptography policy mentions RE token relation only as weak market co-occurrence."),
            "generic_policy_only",
            "catalyst_link_validated",
            "technology_risk",
            "macro_affected_asset",
            "weak",
            "local_only",
        ),
    ]
    original_allow_stale_fixture = config.EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE
    config.EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE = True
    try:
        for hypothesis, source, reason, stage, path_type, role, strength, expected_level in cases:
            validated = event_impact_hypotheses.validate_hypotheses_with_raw_events((hypothesis,), (source,))[0]
            assert validated.status == event_impact_hypotheses.HypothesisStatus.VALIDATED.value
            assert validated.impact_path_reason == reason
            assert validated.validation_stage == stage
            assert validated.impact_path_type == path_type
            assert validated.candidate_role == role
            assert validated.impact_path_strength == strength
            assert validated.opportunity_score_v2 is not None
            assert "impact_path_strength" in validated.opportunity_score_components
            assert validated.evidence_quality_score is not None
            assert validated.source_class
            assert validated.evidence_specificity
            assert validated.market_confirmation_level
            assert validated.opportunity_score_final is not None
            assert validated.opportunity_level == expected_level
            assert validated.manual_verification_items
            if strength == "weak":
                assert validated.digest_eligible_by_impact_path is False
                assert validated.why_digest_ineligible
                assert validated.why_local_only or validated.why_not_watchlist
            else:
                assert validated.digest_eligible_by_impact_path is True
    finally:
        config.EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE = original_allow_stale_fixture


def test_event_impact_hypothesis_persists_upgrade_and_downgrade_paths():
    # Validated hypotheses must persist the opportunity upgrade/downgrade
    # diagnostics on the row (and through the store), not only compute them
    # on-demand in reports. Research-only; no routing/send/trade behavior.
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_impact_hypotheses, event_impact_hypothesis_store
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent

    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:rune-upgrade",
        event_cluster_id="cluster:rune",
        event_type="news",
        external_asset="THORChain",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("RUNE",),
        candidate_coin_ids=("thorchain",),
        direction_hint="volatility",
        playbook_hint="security_or_regulatory_shock",
        confidence=0.85,
        hypothesis_score=70,
        validation_stage=event_impact_hypotheses.ValidationStage.VALIDATION_SEARCH_PENDING.value,
        status=event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value,
    )
    source = RawDiscoveredEvent(
        raw_id="rune",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/rune",
        title="THORChain exploit investigation",
        body="THORChain RUNE faces an exploit and security incident after an attack.",
        raw_json={"market": {"return_24h": 0.32, "volume_zscore_24h": 3.4, "volume_to_market_cap": 0.28}},
        source_confidence=0.9,
        content_hash="rune",
    )
    validated = event_impact_hypotheses.validate_hypotheses_with_raw_events((hypothesis,), (source,))[0]
    # Fields exist and are tuples (the dataclass default is an empty tuple).
    assert isinstance(validated.upgrade_requirements, tuple)
    assert isinstance(validated.downgrade_warnings, tuple)
    # explain_upgrade_path always emits at least one downgrade warning, so a
    # validated hypothesis should carry concrete diagnostics, not just defaults.
    assert validated.downgrade_warnings, "validated hypothesis should persist downgrade warnings"

    # And the fields survive into the persisted JSONL store row.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_impact_hypotheses.jsonl"
        cfg = event_impact_hypothesis_store.EventImpactHypothesisStoreConfig(path=path)
        event_impact_hypothesis_store.write_impact_hypotheses(
            (validated,), cfg=cfg, run_id="r1", profile="quality_validation",
            run_mode="test", artifact_namespace="quality_validation", now=now,
        )
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        assert rows, "store should write at least one row"
        row = rows[0]
        assert "upgrade_requirements" in row and "downgrade_warnings" in row
        assert list(row["downgrade_warnings"]) == list(validated.downgrade_warnings)


def test_event_opportunity_verdict_uses_incident_confidence_and_cause_status():
    from crypto_rsi_scanner import (
        event_evidence_quality,
        event_impact_path_validator,
        event_market_confirmation,
        event_opportunity_verdict,
    )

    strong_market = event_market_confirmation.EventMarketConfirmationResult(
        market_confirmation_score=78,
        level="strong",
        reasons=("price_momentum", "volume_expansion"),
        data_quality=80,
    )
    strong_evidence = event_evidence_quality.EvidenceQualityResult(
        evidence_quality_score=82,
        source_class="crypto_news",
        evidence_specificity="direct_token_mechanism",
    )

    def path(role, *, cause="confirmed", polarity=("asserted",)):
        return event_impact_path_validator.ImpactPathValidation(
            impact_path_type=event_impact_path_validator.ImpactPathType.EXPLOIT_SECURITY_EVENT.value,
            impact_path_strength=event_impact_path_validator.ImpactPathStrength.STRONG.value,
            candidate_role=role,
            evidence_specificity_score=90,
            required_evidence_met=True,
            market_confirmation_required=False,
            digest_eligible_by_impact_path=True,
            why_digest_ineligible=None,
            impact_path_reason="exploit_security_event",
            opportunity_score_v2=82,
            cause_status=cause,
            claim_polarities=polarity,
        )

    ada_no_market = event_opportunity_verdict.evaluate_opportunity(
        impact_path=path(event_impact_path_validator.CandidateRole.ECOSYSTEM_AFFECTED_ASSET.value),
        market_confirmation=strong_market,
        evidence_quality=strong_evidence,
        hypothesis=SimpleNamespace(impact_category="security_or_regulatory_shock"),
        score_components={
            "incident_confidence": 84,
            "market_reaction_confirmed": False,
            "causal_mechanism_confirmed": True,
        },
    )
    assert ada_no_market.watchlist_eligible is False
    assert "ecosystem_asset_requires_market_reaction" in ada_no_market.verdict_reason_codes
    assert ada_no_market.opportunity_score_final <= 64

    rune_confirmed = event_opportunity_verdict.evaluate_opportunity(
        impact_path=path(event_impact_path_validator.CandidateRole.DIRECT_SUBJECT.value),
        market_confirmation=strong_market,
        evidence_quality=strong_evidence,
        hypothesis=SimpleNamespace(impact_category="security_or_regulatory_shock"),
        score_components={
            "incident_confidence": 88,
            "market_reaction_confirmed": True,
            "causal_mechanism_confirmed": True,
        },
    )
    assert rune_confirmed.watchlist_eligible is True
    assert "confirmed_direct_incident" in rune_confirmed.verdict_reason_codes
    assert "confirmed_causal_incident_with_market_reaction" in rune_confirmed.verdict_reason_codes

    memecore_ruled_out = event_opportunity_verdict.evaluate_opportunity(
        impact_path=path(
            event_impact_path_validator.CandidateRole.DIRECT_SUBJECT.value,
            cause="ruled_out",
            polarity=("ruled_out",),
        ),
        market_confirmation=strong_market,
        evidence_quality=strong_evidence,
        hypothesis=SimpleNamespace(impact_category="security_or_regulatory_shock"),
        score_components={
            "incident_confidence": 80,
            "market_reaction_confirmed": True,
            "causal_mechanism_confirmed": False,
        },
    )
    assert memecore_ruled_out.opportunity_level == "local_only"
    assert memecore_ruled_out.watchlist_eligible is False
    assert memecore_ruled_out.why_local_only == "incident_cause_ruled_out"

    rumored = event_opportunity_verdict.evaluate_opportunity(
        impact_path=path(
            event_impact_path_validator.CandidateRole.DIRECT_SUBJECT.value,
            cause="suspected",
            polarity=("rumored",),
        ),
        market_confirmation=strong_market,
        evidence_quality=strong_evidence,
        hypothesis=SimpleNamespace(impact_category="security_or_regulatory_shock"),
        score_components={
            "incident_confidence": 58,
            "market_reaction_confirmed": True,
            "causal_mechanism_confirmed": False,
        },
    )
    assert rumored.watchlist_eligible is False
    assert rumored.opportunity_score_final <= 59
    assert "unconfirmed_incident_cause_cap" in rumored.verdict_reason_codes


def test_event_impact_hypothesis_watchlist_uses_validated_asset_not_first_candidate():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_impact_hypotheses, event_watchlist

    now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)

    def hypothesis(
        hypothesis_id,
        symbols,
        coin_ids,
        validated_asset=None,
        *,
        category="security_or_regulatory_shock",
        playbook="security_or_regulatory_shock",
        status="validated",
        scope="token",
        impact_path_reason="exploit_security_event",
    ):
        return event_impact_hypotheses.EventImpactHypothesis(
            hypothesis_id=hypothesis_id,
            event_cluster_id=f"cluster:{hypothesis_id}",
            event_type="news",
            external_asset="unknown",
            impact_category=category,
            candidate_sectors=("infrastructure_tokens",),
            candidate_symbols=tuple(symbols),
            candidate_coin_ids=tuple(coin_ids),
            crypto_candidate_assets=tuple(
                {"source": "taxonomy", "symbol": symbol, "coin_id": coin_id}
                for symbol, coin_id in zip(symbols, coin_ids)
            ) + ((dict(validated_asset, validated=True),) if validated_asset else ()),
            validated_candidate_assets=((dict(validated_asset, validated=True),) if validated_asset else ()),
            hypothesis_scope=scope,
            playbook_hint=playbook,
            confidence=0.82,
            hypothesis_score=78,
            validation_stage=event_impact_hypotheses.ValidationStage.IMPACT_PATH_VALIDATED.value if status == "validated" else event_impact_hypotheses.ValidationStage.SECTOR_HYPOTHESIS.value,
            status=status,
            validation_reasons=("identity_match links candidate to catalyst",) if validated_asset else (),
            evidence_quotes=(f"{validated_asset.get('coin_id', '')} {validated_asset.get('symbol', '')} exploit catalyst link",) if validated_asset else (),
            impact_path_reason=impact_path_reason if validated_asset else None,
            impact_path_type=impact_path_reason if validated_asset else None,
            impact_path_strength="strong" if validated_asset else None,
            candidate_role="direct_subject" if validated_asset else None,
            evidence_specificity_score=88.0 if validated_asset else None,
            digest_eligible_by_impact_path=True if validated_asset else None,
            opportunity_score_v2=82.0 if validated_asset else None,
            opportunity_score_components={"impact_path_strength": 95.0, "source_evidence_specificity": 88.0} if validated_asset else {},
        )

    rune = hypothesis(
        "hyp:rune",
        ("LINK", "PYTH", "RUNE"),
        ("chainlink", "pyth-network", "thorchain"),
        {"source": "hypothesis_search", "symbol": "RUNE", "coin_id": "thorchain"},
    )
    arb = hypothesis(
        "hyp:arb",
        ("TRUMP", "UMA", "GNO"),
        ("official-trump", "uma", "gnosis"),
        {"source": "hypothesis_search", "symbol": "ARB", "coin_id": "arbitrum"},
        category="prediction_market_infra",
        playbook="infrastructure_mention",
        impact_path_reason="direct_token_event",
    )
    chz = hypothesis(
        "hyp:chz",
        ("CHZ", "ARG", "BAR"),
        ("chiliz", "argentine-football-association-fan-token", "fc-barcelona-fan-token"),
        {"source": "hypothesis_search", "symbol": "CHZ", "coin_id": "chiliz"},
        category="sports_fan_proxy",
        playbook="fan_sports_event",
        impact_path_reason="fan_token_event",
    )
    missing = hypothesis("hyp:missing", ("LINK", "PYTH"), ("chainlink", "pyth-network"), None)
    sector = hypothesis(
        "hyp:sector",
        ("VELVET",),
        ("velvet",),
        None,
        category="rwa_preipo_proxy",
        playbook="rwa_preipo_proxy",
        status="hypothesis",
        scope="sector",
    )

    with tempfile.TemporaryDirectory() as tmp:
        cfg = event_watchlist.EventWatchlistConfig(enabled=True, state_path=Path(tmp) / "watchlist.jsonl")
        result = event_watchlist.refresh_hypothesis_watchlist((rune, arb, chz, missing, sector), cfg=cfg, now=now)
    by_event = {entry.event_id: entry for entry in result.entries}
    assert by_event["hyp:rune"].symbol == "RUNE"
    assert by_event["hyp:rune"].coin_id == "thorchain"
    assert by_event["hyp:rune"].latest_score_components["hypothesis_id"] == "hyp:rune"
    assert by_event["hyp:rune"].latest_score_components["impact_category"] == "security_or_regulatory_shock"
    assert by_event["hyp:rune"].latest_score_components["validation_stage"] == "impact_path_validated"
    assert by_event["hyp:rune"].latest_score_components["impact_path_reason"] == "exploit_security_event"
    assert by_event["hyp:rune"].latest_score_components["impact_path_type"] == "exploit_security_event"
    assert by_event["hyp:rune"].latest_score_components["impact_path_strength"] == "strong"
    assert by_event["hyp:rune"].latest_score_components["candidate_role"] == "direct_subject"
    assert by_event["hyp:rune"].latest_score_components["opportunity_score_v2"] == 82.0
    assert by_event["hyp:rune"].latest_score_components["digest_eligible_by_impact_path"] is True
    assert by_event["hyp:rune"].latest_score_components["hypothesis_score"] == 78
    assert by_event["hyp:rune"].latest_score_components["score"] == 78
    assert by_event["hyp:rune"].latest_score_components["validated_symbol"] == "RUNE"
    assert by_event["hyp:rune"].latest_score_components["validated_coin_id"] == "thorchain"
    assert by_event["hyp:rune"].latest_score_components["route_eligibility"] == "validated_hypothesis_digest_candidate"
    assert any("first_candidate=LINK validated=RUNE" in warning for warning in by_event["hyp:rune"].warnings)
    assert by_event["hyp:arb"].symbol == "ARB"
    assert by_event["hyp:arb"].coin_id == "arbitrum"
    assert any("first_candidate=TRUMP validated=ARB" in warning for warning in by_event["hyp:arb"].warnings)
    assert by_event["hyp:chz"].symbol == "CHZ"
    assert by_event["hyp:chz"].coin_id == "chiliz"
    assert by_event["hyp:missing"].symbol == "SECTOR"
    assert by_event["hyp:missing"].coin_id == "security_or_regulatory_shock"
    assert "validated_hypothesis_missing_validated_asset" in by_event["hyp:missing"].warnings
    assert by_event["hyp:sector"].symbol == "SECTOR"
    assert by_event["hyp:sector"].state == event_watchlist.EventWatchlistState.HYPOTHESIS.value
    assert by_event["hyp:sector"].latest_score_components["route_eligibility"] == "local_only"


def test_event_impact_hypothesis_external_entities_never_become_crypto_candidates():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_impact_hypotheses
    from crypto_rsi_scanner.event_llm_extraction_models import (
        EventLLMCryptoAssetMention,
        EventLLMRawEventExtraction,
    )
    from crypto_rsi_scanner.event_llm_extractor import EventLLMExtractionReportRow
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    names = ("OpenAI", "Anthropic", "SpaceX", "Stripe", "Databricks", "Anduril", "Figma", "Fannie Mae", "Freddie Mac")
    body = " ".join(f"{name} pre-IPO exposure" for name in names)
    raw = RawDiscoveredEvent(
        raw_id="external-entities-only",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/external-entities",
        title="External pre-IPO proxy basket gets attention",
        body=body,
        raw_json={},
        source_confidence=0.90,
        content_hash="external-entities-only",
    )
    event = NormalizedEvent(
        event_id=raw.raw_id,
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="OpenAI",
        description=body,
        confidence=0.90,
    )
    extraction = EventLLMRawEventExtraction(
        schema_version="event_llm_extraction_v1",
        provider="fixture",
        model="fixture",
        prompt_version="test",
        raw_id=raw.raw_id,
        confidence=0.90,
        external_catalysts=(),
        crypto_asset_mentions=tuple(
            EventLLMCryptoAssetMention(
                name=name,
                symbol=name.upper().replace(" ", ""),
                coin_id=name.lower().replace(" ", "-"),
                contract_address=None,
                mention_type="project_or_token",
                confidence=0.90,
            )
            for name in names
        ),
    )
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((raw,), (event,), (), (), ()),
        extraction_rows=(EventLLMExtractionReportRow(raw_event=raw, extraction=extraction),),
        now=now,
        taxonomy={},
    )
    candidate_symbols = {symbol for hypothesis in hypotheses for symbol in hypothesis.candidate_symbols}
    crypto_symbols = {
        str(asset.get("symbol") or "")
        for hypothesis in hypotheses
        for asset in hypothesis.crypto_candidate_assets
    }
    rejected_reasons = {
        str(asset.get("rejection_reason") or "")
        for hypothesis in hypotheses
        for asset in hypothesis.rejected_candidate_assets
    }
    for name in names:
        symbol = name.upper().replace(" ", "")
        assert symbol not in candidate_symbols
        assert symbol not in crypto_symbols
    assert "external_entity_not_crypto_candidate" in rejected_reasons


def test_event_alpha_radar_scanner_report_with_fixture_anomalies():
    import contextlib
    import io
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner, event_alpha_notification_delivery as delivery

    original = {
        "EVENT_DISCOVERY_EVENTS_PATH": config.EVENT_DISCOVERY_EVENTS_PATH,
        "EVENT_DISCOVERY_ALIASES_PATH": config.EVENT_DISCOVERY_ALIASES_PATH,
        "EVENT_DISCOVERY_UNIVERSE_PATH": config.EVENT_DISCOVERY_UNIVERSE_PATH,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE": config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE": config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE,
        "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN": config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN,
        "EVENT_DISCOVERY_GDELT_PATH": config.EVENT_DISCOVERY_GDELT_PATH,
        "EVENT_DISCOVERY_GDELT_LIVE": config.EVENT_DISCOVERY_GDELT_LIVE,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE,
        "EVENT_DISCOVERY_COINALYZE_LIVE": config.EVENT_DISCOVERY_COINALYZE_LIVE,
        "EVENT_DISCOVERY_UNIVERSE_LIVE": config.EVENT_DISCOVERY_UNIVERSE_LIVE,
        "EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT": config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT,
        "EVENT_SOURCE_ENRICHMENT_ENABLED": config.EVENT_SOURCE_ENRICHMENT_ENABLED,
        "EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN": config.EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN,
        "EVENT_MARKET_ENRICHMENT_ENABLED": config.EVENT_MARKET_ENRICHMENT_ENABLED,
        "EVENT_ANOMALY_SCANNER_ENABLED": config.EVENT_ANOMALY_SCANNER_ENABLED,
        "EVENT_ANOMALY_MIN_RETURN_24H": config.EVENT_ANOMALY_MIN_RETURN_24H,
        "EVENT_ANOMALY_MIN_VOLUME_MCAP": config.EVENT_ANOMALY_MIN_VOLUME_MCAP,
        "EVENT_ANOMALY_MIN_VOLUME_ZSCORE": config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE,
        "EVENT_ANOMALY_MAX_ASSETS": config.EVENT_ANOMALY_MAX_ASSETS,
    }
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = Path("fixtures/coingecko_smoke/top_markets.json")
    config.EVENT_DISCOVERY_UNIVERSE_LIVE = False
    config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT = 0
    config.EVENT_MARKET_ENRICHMENT_ENABLED = True
    config.EVENT_ANOMALY_SCANNER_ENABLED = True
    config.EVENT_ANOMALY_MIN_RETURN_24H = 0.03
    config.EVENT_ANOMALY_MIN_VOLUME_MCAP = 0.05
    config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE = 3.0
    config.EVENT_ANOMALY_MAX_ASSETS = 10
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_alpha_radar_report(event_now="2026-06-15T16:00:00Z")
        text = out.getvalue()
        assert "EVENT RESEARCH ALERT REPORT" in text
        assert "market anomaly" in text
        assert "playbook: market_anomaly_unknown" in text
        assert "STORE_ONLY" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_event_alpha_pipeline_runs_watchlist_and_router_cycle():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_pipeline,
        event_alpha_router,
        event_alerts,
        event_watchlist,
    )

    result = _full_event_discovery_fixture_result()
    with tempfile.TemporaryDirectory() as tmp:
        pipe = event_alpha_pipeline.run_event_alpha_pipeline(
            result,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
        assert pipe.raw_events == 20
        assert pipe.candidates == 17
        assert pipe.clusters >= 1
        assert len(pipe.alerts) == 17
        assert pipe.watchlist_entries >= 17
        assert len(pipe.impact_hypotheses) >= 1
        assert pipe.watchlist_escalations >= 1
        assert pipe.routed >= 17
        assert pipe.alertable >= 1
        assert any(
            decision.route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
            and decision.entry.symbol == "TESTVELVET"
            for decision in pipe.router_result.decisions
        )
        text = event_alpha_pipeline.format_event_alpha_pipeline_report(pipe)
        assert "EVENT ALPHA PIPELINE REPORT" in text
        assert "raw_events=20" in text
        assert "clusters=" in text
        assert "TRIGGERED_FADE_RESEARCH" in text
        assert "no trades, paper rows, or live RSI routing" in text

        disabled = event_alpha_pipeline.run_event_alpha_pipeline(
            result,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=False,
                state_path=Path(tmp) / "disabled-watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
        assert disabled.watchlist_result is None
        assert disabled.router_result is None
        assert "watchlist refresh skipped" in "; ".join(disabled.warnings)
        assert "router skipped" in "; ".join(disabled.warnings)


def test_event_alpha_pipeline_writes_non_alertable_hypothesis_rows():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_notifications,
        event_alpha_pipeline,
        event_alpha_router,
        event_alerts,
        event_watchlist,
    )
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="spacex-hypothesis",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/spacex-hypothesis",
        title="SpaceX pre-IPO exposure heats up",
        body="Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
        raw_json={
            "event": {
                "event_id": "spacex-hypothesis",
                "event_name": "SpaceX pre-IPO exposure heats up",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.85,
                "external_asset": "SpaceX",
                "description": "Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
                "confidence": 0.88,
            }
        },
        source_confidence=0.88,
        content_hash="spacex-hypothesis",
    )
    event = NormalizedEvent(
        event_id="spacex-hypothesis",
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=now,
        event_time_confidence=0.85,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="SpaceX",
        description=raw.body,
        confidence=0.88,
    )
    result = EventDiscoveryResult(
        raw_events=(raw,),
        normalized_events=(event,),
        links=(),
        classifications=(),
        candidates=(),
    )

    with tempfile.TemporaryDirectory() as tmp:
        pipe = event_alpha_pipeline.run_event_alpha_pipeline(
            result,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=now,
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
        assert len(pipe.impact_hypotheses) >= 1
        assert pipe.watchlist_entries >= 1
        hypothesis_entries = [
            entry for entry in pipe.watchlist_result.entries
            if entry.state == event_watchlist.EventWatchlistState.HYPOTHESIS.value
        ]
        assert hypothesis_entries
        assert all(entry.should_alert is False for entry in hypothesis_entries)
        by_state = {decision.entry.state: decision for decision in pipe.router_result.decisions}
        assert by_state[event_watchlist.EventWatchlistState.HYPOTHESIS.value].alertable is False
        assert by_state[event_watchlist.EventWatchlistState.HYPOTHESIS.value].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
        cfg = event_alpha_notifications.EventAlphaNotificationConfig(
            enabled=True,
            exploratory_digest_enabled=True,
            exploratory_digest_include_controls=True,
            quality_mode="exploratory_only",
        )
        plan = event_alpha_notifications.build_notification_plan(
            pipe.router_result.decisions,
            storage=_NotifyFakeStorage(),
            cfg=cfg,
            now=now,
        )
        digest = event_alpha_notifications.format_exploratory_telegram_digest(
            plan.exploratory_items,
            profile="notify_no_key",
            cfg=cfg,
        )
        assert "impact hypothesis awaiting validation" in digest
        assert "not alertable yet" in digest


def test_event_alpha_pipeline_hypothesis_search_validates_before_token_watchlist():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_pipeline,
        event_alpha_router,
        event_alerts,
        event_catalyst_search,
        event_watchlist,
    )
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="spacex-sector",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/spacex-sector",
        title="SpaceX pre-IPO exposure heats up",
        body="Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
        raw_json={
            "event": {
                "event_id": "spacex-sector",
                "event_name": "SpaceX pre-IPO exposure heats up",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.85,
                "external_asset": "SpaceX",
                "description": "Tokenized stock venues may see attention around SpaceX pre-IPO markets.",
                "confidence": 0.88,
            }
        },
        source_confidence=0.88,
        content_hash="spacex-sector",
    )
    validation = RawDiscoveredEvent(
        raw_id="velvet-validation",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/velvet-spacex",
        title="VELVET opens SpaceX pre-IPO exposure",
        body="Velvet Capital users can trade tokenized stock style exposure to SpaceX.",
        raw_json={},
        source_confidence=0.92,
        content_hash="velvet-validation",
    )
    event = NormalizedEvent(
        event_id="spacex-sector",
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=now,
        event_time_confidence=0.85,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="SpaceX",
        description=raw.body,
        confidence=0.88,
    )
    result = EventDiscoveryResult(
        raw_events=(raw,),
        normalized_events=(event,),
        links=(),
        classifications=(),
        candidates=(),
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(
        rows_by_query={"VELVET SpaceX pre-IPO exposure": (validation,)}
    )
    with tempfile.TemporaryDirectory() as tmp:
        pipe = event_alpha_pipeline.run_event_alpha_pipeline(
            result,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=now,
            hypothesis_search_provider=provider,
            hypothesis_search_cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(
                enabled=True,
                max_hypotheses=5,
                max_queries_per_hypothesis=4,
                min_confidence=0.50,
                min_result_confidence=0.50,
            ),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
    assert pipe.hypothesis_search_queries > 0
    assert pipe.hypothesis_search_results >= 1
    assert pipe.hypotheses_validated >= 1
    entries = [entry for entry in pipe.watchlist_result.entries if entry.relationship_type == "impact_hypothesis"]
    assert any(entry.symbol == "VELVET" and entry.state == event_watchlist.EventWatchlistState.RADAR.value for entry in entries)
    assert all(entry.state != event_watchlist.EventWatchlistState.TRIGGERED_FADE.value for entry in entries)


def test_event_impact_hypothesis_store_persists_profile_scoped_rows():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_impact_hypotheses, event_impact_hypothesis_store

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:test",
        event_cluster_id="cluster:test",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category=event_impact_hypotheses.ImpactCategory.RWA_PREIPO_PROXY.value,
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        suggested_candidate_assets=({
            "source": "llm_extraction",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "confidence": 0.91,
        },),
        candidate_source="llm_extraction",
        confidence=0.82,
        search_queries=("VELVET SpaceX pre-IPO exposure",),
        status=event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value,
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "notify_llm" / "event_impact_hypotheses.jsonl"
        write = event_impact_hypothesis_store.write_impact_hypotheses(
            (hypothesis,),
            cfg=event_impact_hypothesis_store.EventImpactHypothesisStoreConfig(path=path),
            now=now,
            run_id="run-1",
            profile="notify_llm",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm",
        )
        assert write.success is True
        assert write.rows_written == 1
        read = event_impact_hypothesis_store.load_impact_hypotheses(path)
        assert read.rows_read == 1
        row = read.rows[0]
        assert row["run_id"] == "run-1"
        assert row["profile"] == "notify_llm"
        assert row["artifact_namespace"] == "notify_llm"
        assert row["candidate_source"] == "llm_extraction"
        assert row["suggested_candidate_assets"][0]["symbol"] == "VELVET"
        report = event_impact_hypothesis_store.format_impact_hypotheses_store_report(read)
        assert "EVENT IMPACT HYPOTHESES REPORT" in report
        assert "candidate_sources: llm_extraction=1" in report
        assert "VELVET/velvet" in report


def test_event_alpha_daily_brief_summarizes_rejected_hypothesis_samples():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_daily_brief

    text = event_alpha_daily_brief.build_daily_brief(
        run_rows=({
            "run_id": "r1",
            "profile": "notify_llm",
            "artifact_namespace": "notify_llm",
            "run_mode": "notification_burn_in",
            "started_at": "2026-06-18T12:00:00+00:00",
            "finished_at": "2026-06-18T12:01:00+00:00",
            "impact_hypotheses": 1,
            "hypotheses_validated": 0,
            "hypothesis_promotions": 0,
            "hypothesis_search_queries": 1,
            "hypothesis_search_results": 0,
        },),
        hypothesis_rows=({
            "row_type": "event_impact_hypothesis",
            "schema_version": "event_impact_hypothesis_store_v1",
            "profile": "notify_llm",
            "artifact_namespace": "notify_llm",
            "run_mode": "notification_burn_in",
            "status": "rejected",
            "validation_stage": "rejected",
            "impact_category": "ai_ipo_proxy",
            "external_asset": "OpenAI",
            "hypothesis_score": 44.0,
            "why_not_promoted": ["candidate_identity_not_validated"],
            "external_entities": [{"name": "OpenAI"}],
            "crypto_candidate_assets": [],
            "rejected_validation_samples": [{
                "result_title": "Generic OpenAI market recap",
                "rejection_reason": "result_identity_rejected",
            }],
        },),
        requested_profile="notify_llm",
        artifact_namespace="notify_llm",
        run_mode="notification_burn_in",
        generated_at=datetime(2026, 6, 18, 12, 2, tzinfo=timezone.utc),
    )
    assert "Rejected validation evidence samples: 1" in text
    assert "Rejected evidence reasons: result_identity_rejected=1" in text
    assert "Generic OpenAI market recap" in text


def test_event_impact_hypothesis_generation_uses_llm_suggested_assets_but_not_validation():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_impact_hypotheses
    from crypto_rsi_scanner.event_llm_extraction_models import (
        EventLLMCryptoAssetMention,
        EventLLMRawEventExtraction,
    )
    from crypto_rsi_scanner.event_llm_extractor import EventLLMExtractionReportRow
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="spacex-llm-mention",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/spacex",
        title="SpaceX pre-IPO exposure heats up",
        body="New source says Velvet Capital is adjacent to SpaceX pre-IPO exposure.",
        raw_json={},
        source_confidence=0.90,
        content_hash="spacex-llm-mention",
    )
    event = NormalizedEvent(
        event_id="spacex-llm-mention",
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=now,
        event_time_confidence=0.85,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="SpaceX",
        description=raw.body,
        confidence=0.90,
    )
    extraction = EventLLMRawEventExtraction(
        schema_version="event_llm_extraction_v1",
        provider="fixture",
        model="fixture",
        prompt_version="test",
        raw_id=raw.raw_id,
        confidence=0.90,
        external_catalysts=(),
        crypto_asset_mentions=(
            EventLLMCryptoAssetMention(
                name="Velvet Capital",
                symbol="VELVET",
                coin_id="velvet",
                contract_address=None,
                mention_type="project_or_token",
                confidence=0.92,
            ),
        ),
    )
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((raw,), (event,), (), (), ()),
        extraction_rows=(EventLLMExtractionReportRow(raw_event=raw, extraction=extraction),),
        now=now,
        taxonomy={},
    )
    assert hypotheses
    hypothesis = hypotheses[0]
    assert "VELVET" in hypothesis.candidate_symbols
    assert hypothesis.candidate_source == "llm_extraction"
    assert hypothesis.suggested_candidate_assets[0]["symbol"] == "VELVET"
    assert hypothesis.validated_candidate_assets == ()
    assert hypothesis.status == event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value


def test_event_impact_hypothesis_separates_external_entities_from_crypto_candidates():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_impact_hypotheses
    from crypto_rsi_scanner.event_llm_extraction_models import (
        EventLLMCryptoAssetMention,
        EventLLMRawEventExtraction,
    )
    from crypto_rsi_scanner.event_llm_extractor import EventLLMExtractionReportRow
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="openai-llm-mention",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/openai",
        title="OpenAI pre-IPO proxy exposure heats up",
        body="Velvet Capital is discussed as a venue for OpenAI pre-IPO exposure.",
        raw_json={},
        source_confidence=0.90,
        content_hash="openai-llm-mention",
    )
    event = NormalizedEvent(
        event_id="openai-llm-mention",
        raw_ids=(raw.raw_id,),
        event_name=raw.title,
        event_type="ipo_proxy",
        event_time=now,
        event_time_confidence=0.85,
        first_seen_time=now,
        source=raw.provider,
        source_urls=(raw.source_url,),
        external_asset="OpenAI",
        description=raw.body,
        confidence=0.90,
    )
    extraction = EventLLMRawEventExtraction(
        schema_version="event_llm_extraction_v1",
        provider="fixture",
        model="fixture",
        prompt_version="test",
        raw_id=raw.raw_id,
        confidence=0.90,
        external_catalysts=(),
        crypto_asset_mentions=(
            EventLLMCryptoAssetMention(
                name="OpenAI",
                symbol="OPENAI",
                coin_id="openai",
                contract_address=None,
                mention_type="project_or_token",
                confidence=0.92,
            ),
            EventLLMCryptoAssetMention(
                name="Velvet Capital",
                symbol="VELVET",
                coin_id="velvet",
                contract_address=None,
                mention_type="project_or_token",
                confidence=0.88,
            ),
        ),
    )
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((raw,), (event,), (), (), ()),
        extraction_rows=(EventLLMExtractionReportRow(raw_event=raw, extraction=extraction),),
        now=now,
        taxonomy={},
    )
    hypothesis = next(item for item in hypotheses if item.impact_category == "ai_ipo_proxy")
    assert any(entity["name"] == "OpenAI" for entity in hypothesis.external_entities)
    assert "OPENAI" not in hypothesis.candidate_symbols
    assert "VELVET" in hypothesis.candidate_symbols
    assert hypothesis.crypto_candidate_assets[0]["symbol"] == "VELVET"
    assert hypothesis.rejected_candidate_assets[0]["rejection_reason"] == "external_entity_not_crypto_candidate"
    assert hypothesis.validation_stage == event_impact_hypotheses.ValidationStage.VALIDATION_SEARCH_PENDING.value


def test_event_impact_hypothesis_search_skip_reason_buckets_are_specific():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_catalyst_search, event_impact_hypotheses
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    empty_provider = event_catalyst_search.FixtureCatalystSearchProvider(rows_by_query={})
    no_hypotheses = event_catalyst_search.run_hypothesis_search(
        (),
        empty_provider,
        cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(enabled=True),
        now=now,
    )
    assert no_hypotheses.skip_reasons["no_hypotheses"] == 1

    low_conf = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:low",
        event_cluster_id=None,
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category=event_impact_hypotheses.ImpactCategory.RWA_PREIPO_PROXY.value,
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        confidence=0.10,
    )
    low = event_catalyst_search.run_hypothesis_search(
        (low_conf,),
        empty_provider,
        cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(enabled=True, min_confidence=0.50),
        now=now,
    )
    assert low.skip_reasons["low_confidence"] == 1

    missing_assets = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:missing",
        event_cluster_id=None,
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category=event_impact_hypotheses.ImpactCategory.RWA_PREIPO_PROXY.value,
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=(),
        confidence=0.90,
    )
    missing = event_catalyst_search.run_hypothesis_search(
        (missing_assets,),
        empty_provider,
        cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(enabled=True, min_confidence=0.50),
        now=now,
    )
    assert missing.query_count > 0
    assert any(query.query_type == "candidate_discovery" for query in missing.queries)

    stale_result = RawDiscoveredEvent(
        raw_id="velvet-no-catalyst",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/velvet",
        title="VELVET opens unrelated product",
        body="Velvet Capital launches a generic crypto vault with no named catalyst reference.",
        raw_json={},
        source_confidence=0.90,
        content_hash="velvet-no-catalyst",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(
        rows_by_query={"VELVET SpaceX pre-IPO exposure": (stale_result,)}
    )
    good = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:spacex",
        event_cluster_id=None,
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category=event_impact_hypotheses.ImpactCategory.RWA_PREIPO_PROXY.value,
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        confidence=0.90,
    )
    result = event_catalyst_search.run_hypothesis_search(
        (good,),
        provider,
        cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(
            enabled=True,
            min_confidence=0.50,
            min_result_confidence=0.50,
            require_validated_identity=True,
        ),
        now=now,
    )
    assert result.rejected_result_count >= 1
    assert result.skip_reasons["result_catalyst_missing"] >= 1
    assert "result_catalyst_missing" in result.rejected_result_events[0].result_score_reasons
    sampled = event_impact_hypotheses.attach_hypothesis_search_samples((good,), result)[0]
    assert sampled.rejected_validation_samples
    assert sampled.rejected_validation_samples[0]["query_type"] == "candidate_validation"
    assert sampled.rejected_validation_samples[0]["rejection_reason"] == "result_catalyst_missing"
    assert sampled.rejected_validation_samples[0]["result_score"] == 45


def test_event_alpha_pipeline_operating_cycle_runs_extraction_before_discovery():
    from datetime import datetime, timezone
    from pathlib import Path
    import tempfile
    from crypto_rsi_scanner import (
        event_alpha_pipeline,
        event_alpha_router,
        event_alerts,
        event_discovery,
        event_llm_extractor,
        event_watchlist,
    )
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="pipeline-llm-stealth",
        provider="test",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pipeline-llm-stealth",
        title="SpaceX exposure desk opens",
        body="Stealth proxy venue is live for SpaceX exposure before the event.",
        raw_json={
            "event": {
                "event_id": "pipeline-llm-stealth",
                "event_name": "SpaceX proxy exposure opens",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-16T13:30:00Z",
                "event_time_confidence": 1.0,
                "external_asset": "SpaceX",
                "confidence": 0.90,
                "description": "A proxy venue opened for SpaceX exposure.",
            }
        },
        source_confidence=0.90,
        content_hash="pipeline-llm-stealth",
    )
    asset = DiscoveredAsset(
        coin_id="stealth-alpha",
        symbol="STEALTH",
        name="Stealth Alpha",
        aliases=("stealth alpha",),
    )

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

    seen = {
        "transform_calls": 0,
        "shadow_transform_applied": None,
        "advisory_transform_applied": None,
        "loader_now": None,
    }

    def loader(observed, raw_event_transform):
        seen["loader_now"] = observed
        transformed = tuple(raw_event_transform((raw,))) if raw_event_transform else (raw,)
        applied = bool(transformed[0].raw_json and transformed[0].raw_json.get("llm_extraction"))
        if raw_event_transform:
            seen["transform_calls"] += 1
            if seen["transform_calls"] == 1:
                seen["shadow_transform_applied"] = applied
            else:
                seen["advisory_transform_applied"] = applied
        return event_discovery.run_discovery(transformed, [asset], now=observed)

    with tempfile.TemporaryDirectory() as tmp:
        shadow_pipe = event_alpha_pipeline.run_event_alpha_operating_cycle(
            load_discovery_result=loader,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=now,
            with_llm=True,
            extraction_provider=Provider(),
            extraction_cfg=event_llm_extractor.EventLLMExtractorConfig(mode="shadow", provider="fixture"),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
        advisory_pipe = event_alpha_pipeline.run_event_alpha_operating_cycle(
            load_discovery_result=loader,
            alert_cfg=event_alerts.EventAlertConfig(),
            now=now,
            with_llm=True,
            extraction_provider=Provider(),
            extraction_cfg=event_llm_extractor.EventLLMExtractorConfig(mode="advisory", provider="fixture"),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(
                enabled=True,
                state_path=Path(tmp) / "watchlist-advisory.jsonl",
            ),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=True,
            route=True,
        )
    assert seen["loader_now"] == now
    assert seen["shadow_transform_applied"] is False
    assert seen["advisory_transform_applied"] is True
    assert shadow_pipe.extractions == 1
    assert shadow_pipe.extraction_hint_events == 0
    assert shadow_pipe.candidates == 0
    assert advisory_pipe.extractions == 1
    assert advisory_pipe.extraction_hint_events == 1
    assert advisory_pipe.candidates == 1
    assert advisory_pipe.alerts[0].symbol == "STEALTH"
    assert advisory_pipe.watchlist_entries >= 1
    assert advisory_pipe.routed >= 1


def test_event_alpha_cycle_scanner_runs_research_pipeline_with_fixture_anomalies():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    original = {
        "EVENT_DISCOVERY_EVENTS_PATH": config.EVENT_DISCOVERY_EVENTS_PATH,
        "EVENT_DISCOVERY_ALIASES_PATH": config.EVENT_DISCOVERY_ALIASES_PATH,
        "EVENT_DISCOVERY_UNIVERSE_PATH": config.EVENT_DISCOVERY_UNIVERSE_PATH,
        "EVENT_DISCOVERY_UNIVERSE_LIVE": config.EVENT_DISCOVERY_UNIVERSE_LIVE,
        "EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT": config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT,
        "EVENT_MARKET_ENRICHMENT_ENABLED": config.EVENT_MARKET_ENRICHMENT_ENABLED,
        "EVENT_ANOMALY_SCANNER_ENABLED": config.EVENT_ANOMALY_SCANNER_ENABLED,
        "EVENT_ANOMALY_MIN_RETURN_24H": config.EVENT_ANOMALY_MIN_RETURN_24H,
        "EVENT_ANOMALY_MIN_VOLUME_MCAP": config.EVENT_ANOMALY_MIN_VOLUME_MCAP,
        "EVENT_ANOMALY_MIN_VOLUME_ZSCORE": config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE,
        "EVENT_ANOMALY_MAX_ASSETS": config.EVENT_ANOMALY_MAX_ASSETS,
        "EVENT_WATCHLIST_ENABLED": config.EVENT_WATCHLIST_ENABLED,
        "EVENT_WATCHLIST_STATE_PATH": config.EVENT_WATCHLIST_STATE_PATH,
        "EVENT_ALPHA_ROUTER_ENABLED": config.EVENT_ALPHA_ROUTER_ENABLED,
        "EVENT_ALPHA_ALERT_STORE_PATH": config.EVENT_ALPHA_ALERT_STORE_PATH,
        "EVENT_ALPHA_RUN_LEDGER_PATH": config.EVENT_ALPHA_RUN_LEDGER_PATH,
        "EVENT_ALPHA_RUN_MODE": config.EVENT_ALPHA_RUN_MODE,
        "EVENT_ALPHA_ARTIFACT_NAMESPACE": config.EVENT_ALPHA_ARTIFACT_NAMESPACE,
        "EVENT_ALPHA_ARTIFACT_BASE_DIR": config.EVENT_ALPHA_ARTIFACT_BASE_DIR,
        "EVENT_ALERTS_ENABLED": config.EVENT_ALERTS_ENABLED,
    }
    with tempfile.TemporaryDirectory() as tmp:
        root_artifact_path = Path("event_fade_cache/event_alpha_runs.jsonl")
        root_existed = root_artifact_path.exists()
        config.EVENT_DISCOVERY_EVENTS_PATH = None
        config.EVENT_DISCOVERY_ALIASES_PATH = None
        config.EVENT_DISCOVERY_UNIVERSE_PATH = Path("fixtures/coingecko_smoke/top_markets.json")
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE = False
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE = False
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
        config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE = False
        config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN = ""
        config.EVENT_DISCOVERY_GDELT_PATH = None
        config.EVENT_DISCOVERY_GDELT_LIVE = False
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE = False
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS = ()
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE = False
        config.EVENT_DISCOVERY_COINALYZE_LIVE = False
        config.EVENT_DISCOVERY_UNIVERSE_LIVE = False
        config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT = 0
        config.EVENT_SOURCE_ENRICHMENT_ENABLED = False
        config.EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN = 0
        config.EVENT_MARKET_ENRICHMENT_ENABLED = True
        config.EVENT_ANOMALY_SCANNER_ENABLED = True
        config.EVENT_ANOMALY_MIN_RETURN_24H = 0.03
        config.EVENT_ANOMALY_MIN_VOLUME_MCAP = 0.05
        config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE = 3.0
        config.EVENT_ANOMALY_MAX_ASSETS = 10
        config.EVENT_WATCHLIST_ENABLED = True
        config.EVENT_WATCHLIST_STATE_PATH = Path(tmp) / "watchlist.jsonl"
        config.EVENT_ALPHA_ROUTER_ENABLED = True
        config.EVENT_ALPHA_ALERT_STORE_PATH = Path(tmp) / "event_alpha_alerts.jsonl"
        config.EVENT_ALPHA_RUN_LEDGER_PATH = Path(tmp) / "event_alpha_runs.jsonl"
        config.EVENT_ALPHA_RUN_MODE = "test"
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = "test"
        config.EVENT_ALPHA_ARTIFACT_BASE_DIR = Path(tmp)
        config.EVENT_ALERTS_ENABLED = False
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_cycle(event_now="2026-06-15T16:00:00Z")
            text = out.getvalue()
            assert "EVENT ALPHA PIPELINE REPORT" in text
            assert "raw_events=" in text
            assert "candidates=1" in text
            assert "impact_hypotheses=" in text
            assert "watchlist_entries=" in text
            assert "routed=" in text
            assert "routes: STORE_ONLY" in text
            assert "market_anomaly_unknown" in text
            assert "run ledger updated" in text.lower()
            assert config.EVENT_WATCHLIST_STATE_PATH.exists()
            assert config.EVENT_ALPHA_RUN_LEDGER_PATH.exists()
            run_rows = [
                __import__("json").loads(line)
                for line in config.EVENT_ALPHA_RUN_LEDGER_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert run_rows[-1]["run_mode"] == "test"
            assert run_rows[-1]["artifact_namespace"] == "test"
            assert root_artifact_path.exists() is root_existed
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_event_alpha_cycle_with_llm_feeds_extraction_hints_upstream():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
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

    attrs = (
        "EVENT_DISCOVERY_EVENTS_PATH",
        "EVENT_DISCOVERY_ALIASES_PATH",
        "EVENT_DISCOVERY_UNIVERSE_PATH",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE",
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE",
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH",
        "EVENT_DISCOVERY_CRYPTOPANIC_LIVE",
        "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN",
        "EVENT_DISCOVERY_GDELT_PATH",
        "EVENT_DISCOVERY_GDELT_LIVE",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS",
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH",
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE",
        "EVENT_DISCOVERY_COINALYZE_LIVE",
        "EVENT_DISCOVERY_UNIVERSE_LIVE",
        "EVENT_SOURCE_ENRICHMENT_ENABLED",
        "EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN",
        "EVENT_MARKET_ENRICHMENT_ENABLED",
        "EVENT_ANOMALY_SCANNER_ENABLED",
        "EVENT_WATCHLIST_ENABLED",
        "EVENT_WATCHLIST_STATE_PATH",
        "EVENT_ALPHA_ROUTER_ENABLED",
        "EVENT_ALPHA_ALERT_STORE_PATH",
        "EVENT_ALPHA_RUN_LEDGER_PATH",
        "EVENT_ALPHA_RUN_MODE",
        "EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "EVENT_ALERTS_ENABLED",
        "EVENT_LLM_BUDGET_LEDGER_PATH",
        "EVENT_LLM_EXTRACTOR_MODE",
        "EVENT_LLM_EXTRACTOR_PROVIDER",
        "EVENT_LLM_MODE",
        "EVENT_LLM_PROVIDER",
        "EVENT_LLM_CATALYST_FRAMES_ENABLED",
        "EVENT_LLM_CATALYST_FRAMES_PROVIDER",
    )
    original = {name: getattr(config, name) for name in attrs}
    original_extraction_provider = scanner._event_llm_extraction_provider
    original_relationship_provider = scanner._event_llm_provider
    raw_rows = [{
        "raw_id": "llm-cycle-stealth",
        "provider": "manual_json",
        "fetched_at": "2026-06-16T12:00:00Z",
        "published_at": "2026-06-16T11:00:00Z",
        "source_url": "https://example.test/stealth-alpha-cycle",
        "title": "SpaceX exposure desk opens before listing event",
        "body": "Stealth proxy venue is live for SpaceX exposure before the event.",
        "source_confidence": 0.90,
        "event": {
            "event_id": "stealth-cycle-spacex-event",
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
    with tempfile.TemporaryDirectory() as tmp:
        event_path = Path(tmp) / "events.json"
        alias_path = Path(tmp) / "aliases.json"
        event_path.write_text(json.dumps(raw_rows), encoding="utf-8")
        alias_path.write_text(json.dumps(alias_rows), encoding="utf-8")
        config.EVENT_DISCOVERY_EVENTS_PATH = event_path
        config.EVENT_DISCOVERY_ALIASES_PATH = alias_path
        config.EVENT_DISCOVERY_UNIVERSE_PATH = None
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE = False
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE = False
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
        config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE = False
        config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN = ""
        config.EVENT_DISCOVERY_GDELT_PATH = None
        config.EVENT_DISCOVERY_GDELT_LIVE = False
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE = False
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS = ()
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE = False
        config.EVENT_DISCOVERY_COINALYZE_LIVE = False
        config.EVENT_DISCOVERY_UNIVERSE_LIVE = False
        config.EVENT_SOURCE_ENRICHMENT_ENABLED = False
        config.EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN = 0
        config.EVENT_MARKET_ENRICHMENT_ENABLED = False
        config.EVENT_ANOMALY_SCANNER_ENABLED = False
        config.EVENT_WATCHLIST_ENABLED = True
        config.EVENT_WATCHLIST_STATE_PATH = Path(tmp) / "watchlist.jsonl"
        config.EVENT_ALPHA_ROUTER_ENABLED = True
        config.EVENT_ALPHA_ALERT_STORE_PATH = Path(tmp) / "event_alpha_alerts.jsonl"
        config.EVENT_ALPHA_RUN_LEDGER_PATH = Path(tmp) / "event_alpha_runs.jsonl"
        config.EVENT_ALPHA_RUN_MODE = "test"
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = "test"
        config.EVENT_ALPHA_ARTIFACT_BASE_DIR = Path(tmp)
        config.EVENT_ALERTS_ENABLED = False
        config.EVENT_LLM_BUDGET_LEDGER_PATH = Path(tmp) / "event_llm_budget.json"
        config.EVENT_LLM_EXTRACTOR_MODE = "advisory"
        config.EVENT_LLM_EXTRACTOR_PROVIDER = "fixture"
        config.EVENT_LLM_MODE = "shadow"
        config.EVENT_LLM_PROVIDER = "fixture"
        config.EVENT_LLM_CATALYST_FRAMES_ENABLED = False
        config.EVENT_LLM_CATALYST_FRAMES_PROVIDER = "fixture"
        scanner._event_llm_extraction_provider = lambda extractor_cfg: Provider()
        scanner._event_llm_provider = lambda llm_cfg: None
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_cycle(with_llm=True, event_now="2026-06-16T12:00:00Z")
            text = out.getvalue()
            assert "EVENT ALPHA PIPELINE REPORT" in text
            assert "extractions=1/1" in text
            assert "extraction_hints_applied=1" in text
            assert "candidates=1" in text
            assert "STEALTH/stealth-alpha" in text
            assert config.EVENT_WATCHLIST_STATE_PATH.exists()
            assert config.EVENT_ALPHA_RUN_LEDGER_PATH.exists()
        finally:
            scanner._event_llm_extraction_provider = original_extraction_provider
            scanner._event_llm_provider = original_relationship_provider
            for name, value in original.items():
                setattr(config, name, value)


def test_event_watchlist_refresh_tracks_escalations_and_suppresses_duplicates():
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_alerts, event_discovery, event_watchlist
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="watch-pumpx",
        provider="test",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/watch-pumpx",
        title="PumpX token offers synthetic exposure to SpaceX pre-IPO market",
        body="PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
        raw_json={
            "event": {
                "event_id": "watch-pumpx",
                "event_name": "PumpX SpaceX proxy watch",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.90,
                "external_asset": "SpaceX",
                "confidence": 0.90,
                "description": "PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
            }
        },
        source_confidence=0.90,
        content_hash="watch-pumpx",
    )
    asset = DiscoveredAsset(
        coin_id="pumpx",
        symbol="PUMPX",
        name="PumpX",
        aliases=("pumpx token", "PumpX"),
    )
    discovery = event_discovery.run_discovery([raw], [asset], now=now)
    base = event_alerts.build_event_alert_candidates(discovery, now=now)[0]
    active_quality = {
        **base.score_components,
        "impact_path_type": "proxy_exposure",
        "impact_path_strength": "strong",
        "candidate_role": "proxy_instrument",
        "evidence_quality_score": 82,
        "source_class": "crypto_news",
        "evidence_specificity": "direct_value_capture",
        "market_confirmation_score": 58,
        "market_confirmation_level": "weak",
        "opportunity_score_final": 72,
        "opportunity_level": "validated_digest",
        "opportunity_verdict_reasons": ["fixture_valid_proxy_watch"],
        "why_local_only": "not_local_only",
        "why_not_watchlist": "needs_strong_market_confirmation",
        "manual_verification_items": ["verify proxy instrument and market confirmation"],
        "upgrade_requirements": ["needs_strong_market_confirmation"],
        "downgrade_warnings": [],
    }
    radar = replace(base, tier=event_alerts.EventAlertTier.RADAR_DIGEST, opportunity_score=60, score_components=active_quality)
    watch_quality = {**active_quality, "market_confirmation_score": 70, "market_confirmation_level": "moderate", "opportunity_score_final": 82, "opportunity_level": "watchlist", "why_not_watchlist": "already_watchlisted", "upgrade_requirements": []}
    watch = replace(base, tier=event_alerts.EventAlertTier.WATCHLIST, opportunity_score=75, score_components=watch_quality)

    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "watchlist.jsonl"
        cfg = event_watchlist.EventWatchlistConfig(enabled=True, state_path=state_path)
        first = event_watchlist.refresh_watchlist([radar], cfg=cfg, now=now)
        assert first.rows_written == 1
        assert first.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert first.entries[0].should_alert is True
        assert first.entries[0].first_radar_at == now.isoformat()

        duplicate = event_watchlist.refresh_watchlist(
            [radar],
            cfg=cfg,
            now=datetime(2026, 6, 18, 13, 0, tzinfo=timezone.utc),
        )
        assert duplicate.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert duplicate.entries[0].should_alert is False
        assert duplicate.entries[0].suppressed_reason == "duplicate state, no escalation"
        assert duplicate.entries[0].first_seen_at == first.entries[0].first_seen_at

        escalated = event_watchlist.refresh_watchlist(
            [watch],
            cfg=cfg,
            now=datetime(2026, 6, 18, 14, 0, tzinfo=timezone.utc),
        )
        assert escalated.entries[0].state == event_watchlist.EventWatchlistState.WATCHLIST.value
        assert escalated.entries[0].previous_state == event_watchlist.EventWatchlistState.RADAR.value
        assert escalated.entries[0].should_alert is True
        assert escalated.entries[0].highest_score == 75
        assert len(event_watchlist.load_watchlist(state_path, latest_only=False).entries) == 3


def test_event_watchlist_expiration_and_backward_compatible_reads():
    import json
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_alerts, event_discovery, event_watchlist
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="expired-proxy",
        provider="test",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/expired",
        title="PumpX token offers synthetic exposure to SpaceX pre-IPO market",
        body="PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
        raw_json={
            "event": {
                "event_id": "expired-proxy",
                "event_name": "Expired proxy event",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-14T13:30:00Z",
                "event_time_confidence": 0.90,
                "external_asset": "SpaceX",
                "confidence": 0.90,
                "description": "PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
            }
        },
        source_confidence=0.90,
        content_hash="expired-proxy",
    )
    asset = DiscoveredAsset(coin_id="pumpx", symbol="PUMPX", name="PumpX", aliases=("pumpx token",))
    alert = event_alerts.build_event_alert_candidates(
        event_discovery.run_discovery([raw], [asset], now=now),
        now=now,
    )[0]
    alert = replace(alert, tier=event_alerts.EventAlertTier.RADAR_DIGEST, opportunity_score=60)

    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "watchlist.jsonl"
        cfg = event_watchlist.EventWatchlistConfig(
            enabled=True,
            state_path=state_path,
            expire_hours_after_event=72,
        )
        result = event_watchlist.refresh_watchlist([alert], cfg=cfg, now=now)
        assert result.entries[0].state == event_watchlist.EventWatchlistState.EXPIRED.value
        assert result.entries[0].should_alert is False
        assert result.entries[0].suppressed_reason == "terminal non-alert state"

        old_path = Path(tmp) / "old-watchlist.jsonl"
        old_path.write_text(
            json.dumps({
                "row_type": "event_watchlist_state",
                "key": "old|coin|rel||",
                "event_id": "old",
                "coin_id": "coin",
                "symbol": "OLD",
                "relationship_type": "proxy_attention",
                "state": "RADAR",
                "last_seen_at": now.isoformat(),
                "latest_score": 61,
            }) + "\nnot-json\n",
            encoding="utf-8",
        )
        loaded = event_watchlist.load_watchlist(old_path)
        assert loaded.rows_read == 1
        assert loaded.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert loaded.entries[0].highest_score == 61


def test_event_alpha_router_routes_watchlist_escalations_safely():
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_router, event_playbooks, event_watchlist

    def row(
        symbol,
        state,
        playbook,
        *,
        should_alert=True,
        score=75,
        suppressed_reason=None,
    ):
        quality = {
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_value_capture",
            "market_confirmation_score": 62,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": score,
            "opportunity_level": "high_priority"
            if state in {"HIGH_PRIORITY", "ARMED", "EVENT_PASSED"}
            else "watchlist",
            "opportunity_verdict_reasons": ["test_quality_fixture"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify catalyst and market confirmation"],
            "upgrade_requirements": [],
            "downgrade_warnings": ["none"],
        }
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|coin|rel|asset|time",
            cluster_id="spacex|ipo_proxy|2026-06-20",
            event_id=f"{symbol}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_exposure",
            external_asset="SpaceX",
            event_time="2026-06-20T13:30:00+00:00",
            state=state,
            previous_state="RADAR",
            first_seen_at="2026-06-18T12:00:00+00:00",
            last_seen_at="2026-06-18T13:00:00+00:00",
            source_count=1,
            highest_score=score,
            latest_score=score,
            latest_tier=state,
            latest_event_name=f"{symbol} SpaceX event",
            latest_source="test",
            latest_playbook_type=playbook,
            latest_playbook_score=score,
            latest_playbook_action="watchlist",
            latest_score_components=quality,
            should_alert=should_alert,
            suppressed_reason=suppressed_reason,
        )

    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=6,
        latest_only=True,
        entries=[
            row(
                "PFADE",
                event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
                event_playbooks.EventPlaybookType.PROXY_FADE.value,
                score=95,
            ),
            row(
                "BADTRIG",
                event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
                event_playbooks.EventPlaybookType.DIRECT_EVENT.value,
                score=90,
            ),
            row(
                "ATTN",
                event_watchlist.EventWatchlistState.WATCHLIST.value,
                event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
                score=74,
            ),
            row(
                "DUP",
                event_watchlist.EventWatchlistState.WATCHLIST.value,
                event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
                should_alert=False,
                suppressed_reason="duplicate state, no escalation",
            ),
            row(
                "ANOM",
                event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
                event_playbooks.EventPlaybookType.MARKET_ANOMALY.value,
                should_alert=False,
            ),
            row(
                "NOISE",
                event_watchlist.EventWatchlistState.RADAR.value,
                event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
            ),
        ],
    )
    result = event_alpha_router.route_watchlist(
        read,
        cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
    )
    by_symbol = {decision.entry.symbol: decision for decision in result.decisions}
    assert by_symbol["PFADE"].route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
    assert by_symbol["PFADE"].alertable is True
    assert by_symbol["BADTRIG"].route == event_alpha_router.EventAlphaRoute.LOCAL_REPORT
    assert by_symbol["BADTRIG"].alertable is False
    assert "non-proxy playbook cannot route triggered fade" in by_symbol["BADTRIG"].warnings
    assert by_symbol["ATTN"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["DUP"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert by_symbol["ANOM"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["NOISE"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY

    text = event_alpha_router.format_router_report(result)
    assert "EVENT ALPHA ROUTER REPORT" in text
    assert "TRIGGERED_FADE_RESEARCH" in text
    assert "SUPPRESS_DUPLICATE" in text
    assert "no sends, trades, or paper rows" in text
    routed_digest = event_alpha_router.format_routed_telegram_digest(result.alertable_decisions)
    assert "Event Alpha routed research alerts" in routed_digest
    assert "PFADE" in routed_digest
    assert "ATTN" in routed_digest
    assert "BADTRIG" not in routed_digest
    assert "alert_id: ea:" in text
    assert "card_id: card_" in text
    assert "FEEDBACK_TARGET=ea:" in text
    assert "alert_id=ea:" in routed_digest


def test_event_alpha_router_daily_digest_for_validated_impact_hypotheses():
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_router, event_research_cards, event_watchlist

    def entry(
        symbol,
        score=78,
        *,
        should_alert=True,
        impact_category="security_or_regulatory_shock",
        playbook="security_or_regulatory_shock",
        external_asset="unknown",
        evidence=None,
        validation_stage="impact_path_validated",
        impact_path_reason="exploit_security_event",
        impact_path_type=None,
        impact_path_strength="strong",
        candidate_role="direct_subject",
        opportunity_score_v2=None,
        opportunity_score_final=None,
        opportunity_level="validated_digest",
        market_confirmation_level="moderate",
        digest_eligible_by_impact_path=True,
        state=None,
    ):
        impact_path_type = impact_path_type or impact_path_reason
        opportunity_score_v2 = opportunity_score_v2 if opportunity_score_v2 is not None else score
        opportunity_score_final = opportunity_score_final if opportunity_score_final is not None else opportunity_score_v2
        evidence = evidence or (f"{symbol} {symbol.lower()} exploit catalyst link",)
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"hypothesis|cluster:{symbol}|{impact_category}",
            cluster_id=f"cluster:{symbol}",
            event_id=f"hyp:{symbol}",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="impact_hypothesis",
            external_asset=external_asset,
            event_time=None,
            state=state or event_watchlist.EventWatchlistState.RADAR.value,
            previous_state=event_watchlist.EventWatchlistState.HYPOTHESIS.value,
            first_seen_at="2026-06-23T12:00:00+00:00",
            last_seen_at="2026-06-23T12:30:00+00:00",
            source_count=1,
            highest_score=score,
            latest_score=score,
            latest_tier="HIGH_PRIORITY_WATCH" if state == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value else "RADAR_DIGEST",
            latest_event_name=f"{symbol} validated impact hypothesis",
            latest_source="impact_hypothesis",
            latest_playbook_type=playbook,
            latest_effective_playbook_type=playbook,
            latest_playbook_score=score,
            latest_playbook_action="high_priority_watch" if state == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value else "radar_digest",
            latest_score_components={
                "hypothesis_id": f"hyp:{symbol}",
                "impact_category": impact_category,
                "validation_stage": validation_stage,
                "impact_path_reason": impact_path_reason,
                "impact_path_type": impact_path_type,
                "impact_path_strength": impact_path_strength,
                "candidate_role": candidate_role,
                "evidence_specificity_score": 88,
                "digest_eligible_by_impact_path": digest_eligible_by_impact_path,
                "opportunity_score_v2": opportunity_score_v2,
                "opportunity_score_final": opportunity_score_final,
                "opportunity_level": opportunity_level,
                "market_confirmation_score": 50,
                "market_confirmation_level": market_confirmation_level,
                "evidence_quality_score": 82,
                "source_class": "crypto_news",
                "evidence_specificity": "direct_token_mechanism",
                "opportunity_verdict_reasons": ["direct_token_event_with_strong_evidence"],
                "manual_verification_items": ["verify independent source"],
                "opportunity_score_components": {
                    "impact_path_strength": 95 if impact_path_strength == "strong" else 35,
                    "source_evidence_specificity": 88,
                    "market_confirmation": 50,
                },
                "hypothesis_score": score,
                "score": score,
                "playbook_type": playbook,
                "effective_playbook_type": playbook,
                "validated_symbol": symbol,
                "validated_coin_id": symbol.lower(),
                "validated_asset": {"symbol": symbol, "coin_id": symbol.lower(), "name": symbol, "validated": True},
                "evidence_quotes": list(evidence),
                "validation_reasons": list(evidence),
            },
            material_change_reasons=("hypothesis_validated",),
            should_alert=should_alert,
        )

    def proxy_entry(symbol, score=72):
        quality = {
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_value_capture",
            "market_confirmation_score": 55,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": score,
            "opportunity_level": "watchlist",
            "opportunity_verdict_reasons": ["proxy_impact_path_explained"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify market confirmation"],
            "upgrade_requirements": [],
            "downgrade_warnings": [],
        }
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"proxy|cluster:{symbol}|proxy_attention",
            cluster_id=f"cluster:{symbol}",
            event_id=f"proxy:{symbol}",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time=None,
            state=event_watchlist.EventWatchlistState.RADAR.value,
            previous_state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
            first_seen_at="2026-06-23T12:00:00+00:00",
            last_seen_at="2026-06-23T12:30:00+00:00",
            source_count=2,
            highest_score=score,
            latest_score=score,
            latest_tier="RADAR_DIGEST",
            latest_event_name=f"{symbol} proxy candidate",
            latest_source="test",
            latest_playbook_type="proxy_attention",
            latest_playbook_score=score,
            latest_playbook_action="radar_digest",
            latest_score_components=quality,
            should_alert=True,
        )

    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=4,
        latest_only=True,
        entries=[
            entry("RUNE", 90, evidence=("THORChain RUNE faces an exploit and security incident investigation.",)),
            entry(
                "ZEC",
                82,
                impact_category="listing_liquidity_event",
                playbook="listing_volatility",
                evidence=("Zcash ZEC miner completes a Nasdaq listing and public market access changes.",),
                impact_path_reason="listing_liquidity_event",
            ),
            entry(
                "BTC",
                88,
                impact_category="political_meme_proxy",
                playbook="political_meme_event",
                evidence=("Bitcoin quantum-computing policy debate drew Trump comments.",),
                validation_stage="catalyst_link_validated",
                impact_path_reason="generic_policy_only",
                impact_path_type="technology_risk",
                impact_path_strength="weak",
                candidate_role="macro_affected_asset",
                opportunity_score_v2=76,
                digest_eligible_by_impact_path=False,
            ),
            entry("LOW", 50, evidence=("LOW token exploit catalyst link.",)),
            proxy_entry("VELVET", 72),
            entry("SECTOR", 70),
        ],
    )
    enabled = event_alpha_router.route_watchlist(
        read,
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            validated_hypothesis_digest_enabled=True,
            max_validated_hypothesis_digest_items=1,
            max_digest_items=2,
        ),
    )
    by_symbol = {decision.entry.symbol: decision for decision in enabled.decisions}
    assert by_symbol["RUNE"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["RUNE"].lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST
    assert by_symbol["RUNE"].alertable is True
    assert "digest opportunity verdict" in by_symbol["RUNE"].reason
    assert by_symbol["ZEC"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert by_symbol["ZEC"].alertable is False
    assert by_symbol["ZEC"].reason == "Validated impact hypothesis digest cap reached for this run."
    assert by_symbol["BTC"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["BTC"].alertable is False
    assert "impact_path_not_digest_eligible" in by_symbol["BTC"].reason
    assert by_symbol["LOW"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["LOW"].alertable is False
    assert "opportunity_score_final_below_threshold" in by_symbol["LOW"].reason
    assert by_symbol["VELVET"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["VELVET"].alertable is True
    assert by_symbol["SECTOR"].alertable is False
    assert by_symbol["SECTOR"].route != event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH

    canonical = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=2,
            latest_only=True,
            entries=[
                entry("AAVE", 72, opportunity_score_v2=64, opportunity_score_final=72, opportunity_level="validated_digest"),
                entry("VELVET", 96, opportunity_score_final=96, opportunity_level="high_priority", impact_category="tokenized_stock_venue", playbook="proxy_attention", impact_path_reason="venue_value_capture", impact_path_type="venue_value_capture", candidate_role="proxy_venue", external_asset="SpaceX", state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value),
                entry("BAD", 88, opportunity_score_v2=88, opportunity_score_final=40, opportunity_level="local_only"),
            ],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            validated_hypothesis_digest_enabled=True,
            max_validated_hypothesis_digest_items=5,
        ),
    )
    canonical_by_symbol = {decision.entry.symbol: decision for decision in canonical.decisions}
    assert canonical_by_symbol["AAVE"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert canonical_by_symbol["AAVE"].alertable is True
    assert canonical_by_symbol["AAVE"].routing_score_used == 72
    assert canonical_by_symbol["AAVE"].routing_score_source == "opportunity_score_final"
    assert canonical_by_symbol["AAVE"].routing_verdict_used == "validated_digest"
    assert canonical_by_symbol["VELVET"].route == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH
    assert canonical_by_symbol["VELVET"].alertable is True
    assert "Validated impact hypothesis reached high-priority opportunity verdict" in canonical_by_symbol["VELVET"].reason
    assert canonical_by_symbol["BAD"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert canonical_by_symbol["BAD"].alertable is False
    canonical_report = event_alpha_router.format_router_report(canonical)
    assert "source=opportunity_score_final value=72" in canonical_report
    assert "opportunity_score_v2_below_threshold" not in canonical_report

    disabled = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=1,
            latest_only=True,
            entries=[entry("RUNE", 90, evidence=("THORChain RUNE exploit catalyst link.",))],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            validated_hypothesis_digest_enabled=False,
        ),
    )
    only = disabled.decisions[0]
    assert only.route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert only.alertable is False

    message = event_alpha_router.format_routed_telegram_digest([by_symbol["RUNE"]], profile="notify_llm")
    assert "Validated impact hypothesis" in message
    assert "Not a trade signal" in message
    assert "not a calibrated strategy" in message

    card = event_research_cards.render_research_card(
        "RUNE",
        watchlist_entries=[by_symbol["RUNE"].entry],
        route_decisions=[by_symbol["RUNE"]],
    )
    assert card.found is True
    assert "## Impact Hypothesis Context" in card.markdown
    assert "Validated asset: RUNE/rune" in card.markdown
    assert "Final opportunity verdict" in card.markdown
    assert "Evidence quality" in card.markdown
    assert "Market confirmation" in card.markdown
    assert "Impact path reason: exploit_security_event" in card.markdown
    assert "Quality gate: passed" in card.markdown
    assert "not a calibrated strategy or trade signal" in card.markdown
    assert "OPENAI_API_KEY" not in card.markdown
    assert "TELEGRAM_BOT_TOKEN" not in card.markdown


def test_event_alpha_near_miss_refreshes_market_context_without_triggering_fade():
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_daily_brief,
        event_alpha_router,
        event_impact_hypotheses,
        event_near_miss,
        event_opportunity_audit,
        event_watchlist,
    )

    base_components = {
        "validated_symbol": "ENA",
        "validated_coin_id": "ethena",
        "impact_category": "security_or_regulatory_shock",
        "playbook_type": "security_or_regulatory_shock",
        "impact_path_type": "exploit_security_event",
        "impact_path_strength": "strong",
        "candidate_role": "direct_subject",
        "source_class": "crypto_news",
        "evidence_specificity": "direct_token_mechanism",
        "source_quality": 82,
        "evidence_quality_score": 82,
        "market_confirmation": 15,
        "market_confirmation_score": 15,
        "market_confirmation_level": "weak",
        "opportunity_score_final": 64,
        "opportunity_level": "exploratory",
        "missing_requirements": ["market_confirmation"],
        "why_not_watchlist": "market_confirmation",
        "opportunity_score_v2": 80,
    }
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:ena",
        event_cluster_id="cluster:ena",
        event_type="security_event",
        external_asset="Ethena",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("security",),
        candidate_symbols=("ENA",),
        candidate_coin_ids=("ethena",),
        validated_candidate_assets=({"symbol": "ENA", "coin_id": "ethena", "validated": True},),
        crypto_candidate_assets=({"symbol": "ENA", "coin_id": "ethena", "accepted": True},),
        playbook_hint="security_or_regulatory_shock",
        confidence=0.86,
        hypothesis_score=82,
        score_components=base_components,
        validation_stage="impact_path_validated",
        status="validated",
        evidence_quotes=("ENA exploit security event was confirmed.",),
        impact_path_reason="exploit_security_event",
        impact_path_type="exploit_security_event",
        impact_path_strength="strong",
        candidate_role="direct_subject",
        evidence_quality_score=82,
        source_class="crypto_news",
        evidence_specificity="direct_token_mechanism",
        market_confirmation_score=15,
        market_confirmation_level="weak",
        market_confirmation_missing_fields=("market_confirmation",),
        opportunity_score_v2=80,
        opportunity_score_final=64,
        opportunity_level="exploratory",
        missing_requirements=("market_confirmation",),
        why_not_watchlist="market_confirmation",
    )
    near = event_near_miss.detect_near_miss_rows((hypothesis,), cfg=event_near_miss.EventNearMissConfig())
    assert len(near) == 1
    assert near[0].symbol == "ENA"
    assert near[0].core_opportunity_id
    assert "targeted_market_refresh" in near[0].recommended_refresh_actions
    queue = event_near_miss.targeted_market_refresh_queue((hypothesis,), cfg=event_near_miss.EventNearMissConfig())
    assert queue[0].refresh_id == f"refresh:{near[0].core_opportunity_id}"
    duplicate_hypothesis = __import__("dataclasses").replace(
        hypothesis,
        hypothesis_id="hyp:ena:support",
        opportunity_score_final=63,
        score_components={**hypothesis.score_components, "opportunity_score_final": 63},
    )
    deduped_queue = event_near_miss.targeted_market_refresh_queue(
        (hypothesis, duplicate_hypothesis),
        cfg=event_near_miss.EventNearMissConfig(),
    )
    assert len(deduped_queue) == 1
    assert deduped_queue[0].core_opportunity_id == near[0].core_opportunity_id
    assert queue[0].reason == "market_confirmation"

    generic = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:generic",
        event_cluster_id="cluster:generic",
        event_type="macro",
        external_asset="Bitcoin World",
        impact_category="market_anomaly_unknown",
        candidate_sectors=("macro",),
        candidate_symbols=("BTC",),
        candidate_coin_ids=("bitcoin",),
        score_components={
            **base_components,
            "validated_symbol": "BTC",
            "validated_coin_id": "bitcoin",
            "impact_path_type": "generic_cooccurrence_only",
            "candidate_role": "generic_mention",
            "opportunity_score_final": 64,
            "opportunity_level": "exploratory",
        },
        impact_path_type="generic_cooccurrence_only",
        candidate_role="generic_mention",
        opportunity_score_final=64,
        opportunity_level="exploratory",
    )
    assert event_near_miss.detect_near_miss_rows((generic,), cfg=event_near_miss.EventNearMissConfig()) == ()

    stale_velvet = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:velvet-stale",
        event_cluster_id="cluster:spacex",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category="tokenized_stock_venue",
        candidate_sectors=("rwa",),
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        validated_candidate_assets=({"symbol": "VELVET", "coin_id": "velvet", "validated": True},),
        crypto_candidate_assets=({"symbol": "VELVET", "coin_id": "velvet", "accepted": True},),
        playbook_hint="proxy_attention",
        confidence=0.91,
        hypothesis_score=90,
        score_components={
            **base_components,
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "impact_category": "tokenized_stock_venue",
            "playbook_type": "proxy_attention",
            "impact_path_type": "venue_value_capture",
            "candidate_role": "proxy_venue",
            "external_asset": "SpaceX",
            "market_confirmation": 49,
            "market_confirmation_score": 49,
            "market_confirmation_level": "weak",
            "market_context_freshness_status": "stale",
            "market_context_freshness_cap_applied": True,
            "market_context_timestamp": "2026-06-14T00:00:00+00:00",
            "market_confirmation_warnings": ("market_context_stale_capped",),
            "market_confirmation_missing_fields": ("needs_fresh_market_confirmation",),
            "opportunity_score_final": 70,
            "opportunity_level": "validated_digest",
            "missing_requirements": ("needs_fresh_market_confirmation",),
            "why_not_watchlist": "needs_fresh_market_confirmation",
            "opportunity_score_v2": 88,
        },
        validation_stage="impact_path_validated",
        status="validated",
        evidence_quotes=("VELVET gives users SpaceX pre-IPO exposure.",),
        impact_path_reason="venue_value_capture",
        impact_path_type="venue_value_capture",
        impact_path_strength="strong",
        candidate_role="proxy_venue",
        evidence_quality_score=86,
        source_class="crypto_native",
        evidence_specificity="asset_and_catalyst",
        market_confirmation_score=49,
        market_confirmation_level="weak",
        market_confirmation_warnings=("market_context_stale_capped",),
        market_confirmation_missing_fields=("needs_fresh_market_confirmation",),
        market_context_timestamp="2026-06-14T00:00:00+00:00",
        market_context_freshness_status="stale",
        market_context_freshness_cap_applied=True,
        opportunity_score_v2=88,
        opportunity_score_final=70,
        opportunity_level="validated_digest",
        missing_requirements=("needs_fresh_market_confirmation",),
        why_not_watchlist="needs_fresh_market_confirmation",
    )
    stale_near = event_near_miss.detect_near_miss_rows((stale_velvet,), cfg=event_near_miss.EventNearMissConfig())
    assert len(stale_near) == 1
    assert stale_near[0].opportunity_level_before == "validated_digest"
    assert event_near_miss.is_upgrade_candidate(stale_near[0]) is True
    near_section, upgrade_section = event_near_miss.split_near_miss_candidates((*near, *stale_near))
    assert [item.symbol for item in near_section] == ["ENA"]
    assert [item.symbol for item in upgrade_section] == ["VELVET"]
    split_report = event_near_miss.format_near_miss_report((*near, *stale_near), profile="fixture")
    assert "## Near-Miss Candidates" in split_report
    assert "## Upgrade Candidates" in split_report
    assert "- ENA/ethena" in split_report.split("## Upgrade Candidates", 1)[0]
    assert "- VELVET/velvet" in split_report.split("## Upgrade Candidates", 1)[1]
    assert "targeted_market_refresh" in stale_near[0].recommended_refresh_actions
    stale_queue = event_near_miss.targeted_market_refresh_queue((stale_velvet,), cfg=event_near_miss.EventNearMissConfig())
    assert stale_queue[0].symbol == "VELVET"
    probe = event_near_miss.refresh_market_context_for_candidates(
        stale_queue,
        market_rows=({
            "coin_id": "velvet",
            "symbol": "VELVET",
            "return_24h": 82,
            "return_72h": 148,
            "volume_zscore_24h": 5.4,
            "volume_to_market_cap": 0.44,
            "timestamp": "2026-06-15T15:30:00+00:00",
            "source": "fixture_targeted_market_refresh",
        },),
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    assert probe[0]["success"] is True
    assert probe[0]["market_context_after"]["data_quality"] == "fresh"

    class FailingProvider:
        name = "failing_provider"

        def fetch_market_rows(self, coin_ids, *, max_assets=50):
            raise RuntimeError("boom")

    failed_probe = event_near_miss.refresh_market_context_for_candidates(
        stale_queue,
        targeted_market_provider=FailingProvider(),
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    assert failed_probe[0]["success"] is False
    assert failed_probe[0]["error_class"] == "RuntimeError"

    refreshed = event_near_miss.refresh_near_miss_hypotheses(
        (hypothesis,),
        cfg=event_near_miss.EventNearMissConfig(market_refresh_enabled=True, max_market_refresh_assets=5),
        market_rows=({
            "coin_id": "ethena",
            "symbol": "ENA",
            "return_24h": 58,
            "return_72h": 96,
            "volume_zscore_24h": 4.5,
            "volume_to_market_cap": 0.42,
            "timestamp": "2026-06-26T10:00:00+00:00",
            "source": "fixture_market",
        },),
        now=datetime(2026, 6, 26, 11, 0, tzinfo=timezone.utc),
    )
    updated = refreshed.hypotheses[0]
    refreshed_near = refreshed.near_misses[0]
    assert refreshed_near.market_refresh_attempted is True
    assert refreshed_near.market_refresh_success is True
    assert refreshed_near.market_refresh_provider == "cycle_rows"
    assert refreshed_near.refresh_upgrade_status in {"upgraded", "improved_score"}
    assert refreshed_near.opportunity_score_after > refreshed_near.opportunity_score_before
    assert updated.opportunity_level in {"validated_digest", "watchlist", "high_priority"}
    assert updated.opportunity_score_final >= 65
    assert updated.market_context_data_quality == "fresh"
    assert updated.opportunity_level_before_refresh == "exploratory"
    assert updated.opportunity_level_after_refresh == updated.opportunity_level
    assert updated.market_confirmation_after_refresh == updated.market_confirmation_score
    assert updated.score_components["final_opportunity_level"] == updated.opportunity_level
    assert updated.score_components["final_opportunity_score"] == updated.opportunity_score_final
    assert updated.score_components["final_verdict_source"] == "market_refresh"
    assert updated.score_components["market_data_freshness"] == "fresh"
    assert updated.score_components["market_reaction_confirmation"] in {"moderate", "strong"}
    assert updated.score_components["opportunity_score_v2"] == 80
    assert "TRIGGERED_FADE" not in event_near_miss.format_near_miss_report(refreshed.near_misses)

    report = event_near_miss.format_near_miss_report(refreshed.near_misses, profile="quality_validation")
    assert "ENA/ethena" in report
    assert "market_refresh: attempted=true success=true" in report
    assert "provider=cycle_rows" in report

    hypothesis_row = {
        **updated.__dict__,
        "profile": "quality_validation",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "quality_validation",
    }
    daily = event_alpha_daily_brief.build_daily_brief(
        hypothesis_rows=[hypothesis_row],
        requested_profile="quality_validation",
        artifact_namespace="quality_validation",
    )
    assert "## Near-Miss Candidates" in daily
    assert "ENA/ethena" in daily

    audit = event_opportunity_audit.format_opportunity_audit("ENA", hypotheses=[updated], profile="quality_validation")
    assert "## Near-miss status" in audit
    assert "status: targeted refresh previously applied" in audit
    assert "targeted refresh:" in audit
    assert "market_confirmation=" in audit

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|cluster:ena|security_or_regulatory_shock",
        cluster_id="cluster:ena",
        event_id="hyp:ena",
        coin_id="ethena",
        symbol="ENA",
        relationship_type="impact_hypothesis",
        external_asset="Ethena",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=event_watchlist.EventWatchlistState.HYPOTHESIS.value,
        first_seen_at="2026-06-26T10:00:00+00:00",
        last_seen_at="2026-06-26T11:00:00+00:00",
        latest_score=80,
        latest_tier="RADAR_DIGEST",
        latest_event_name="ENA refreshed near miss",
        latest_source="fixture",
        latest_score_components=updated.score_components,
        opportunity_score_final=updated.opportunity_score_final,
        opportunity_level=updated.opportunity_level,
        should_alert=True,
    )
    routed = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=1,
            latest_only=True,
            entries=[entry],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True, validated_hypothesis_digest_enabled=True),
    )
    assert routed.decisions[0].route != event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH


def test_event_alpha_router_routes_material_changes_with_lanes():
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_router, event_playbooks, event_watchlist

    def row(symbol, *, reasons=(), score_jump=0, state=None, playbook=None, should_alert=True, history=None):
        quality = {
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_value_capture",
            "market_confirmation_score": 62,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": 80,
            "opportunity_level": "watchlist",
            "opportunity_verdict_reasons": ["test_quality_fixture"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify catalyst and market confirmation"],
            "upgrade_requirements": [],
            "downgrade_warnings": [],
        }
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|coin|rel",
            cluster_id="spacex|ipo_proxy|2026-06-20",
            event_id=f"{symbol}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time="2026-06-20T13:30:00+00:00",
            state=state or event_watchlist.EventWatchlistState.WATCHLIST.value,
            previous_state=state or event_watchlist.EventWatchlistState.WATCHLIST.value,
            first_seen_at="2026-06-18T12:00:00+00:00",
            last_seen_at="2026-06-18T14:00:00+00:00",
            source_count=2,
            highest_score=80,
            latest_score=80,
            latest_tier="WATCHLIST",
            latest_event_name=f"{symbol} SpaceX event",
            latest_source="test",
            latest_playbook_type=playbook or event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
            latest_playbook_score=80,
            latest_playbook_action="watchlist",
            latest_score_components=quality,
            should_alert=should_alert,
            score_jump=score_jump,
            material_change_reasons=tuple(reasons),
            alert_history=history or [
                {"observed_at": "2026-06-18T12:00:00+00:00", "should_alert": False},
                {"observed_at": "2026-06-18T14:00:00+00:00", "should_alert": should_alert},
            ],
            suppressed_reason=None if should_alert else "duplicate state, no escalation",
        )

    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=5,
        latest_only=True,
        entries=[
            row("JUMP", reasons=("score_jump",), score_jump=15),
            row("SRC", reasons=("new_independent_source",)),
            row("TIME", reasons=("event_time_upgrade",)),
            row(
                "COOL",
                reasons=("score_jump",),
                score_jump=15,
                history=[
                    {"observed_at": "2026-06-18T13:00:00+00:00", "should_alert": True},
                    {"observed_at": "2026-06-18T14:00:00+00:00", "should_alert": True},
                ],
            ),
            row("DUP", should_alert=False),
            row(
                "TRIG",
                state=event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
                playbook=event_playbooks.EventPlaybookType.PROXY_FADE.value,
                should_alert=False,
            ),
        ],
    )
    result = event_alpha_router.route_watchlist(read, cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True))
    by_symbol = {decision.entry.symbol: decision for decision in result.decisions}
    assert by_symbol["JUMP"].alertable is True
    assert by_symbol["JUMP"].lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST
    assert by_symbol["SRC"].alertable is True
    assert by_symbol["TIME"].alertable is True
    assert by_symbol["COOL"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert "cooldown" in by_symbol["COOL"].reason.lower()
    assert by_symbol["DUP"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert by_symbol["TRIG"].route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
    assert by_symbol["TRIG"].lane == event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE


def test_event_alpha_cycle_send_uses_router_approved_decisions_only():
    from pathlib import Path
    from crypto_rsi_scanner import (
        config,
        event_alpha_router,
        event_alerts,
        event_playbooks,
        event_watchlist,
        scanner,
    )

    class FakeStorage:
        meta = {}

        def __init__(self, path):
            self.path = path
            self.closed = False

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

        def active_subscribers(self):
            return ["chat"]

        def close(self):
            self.closed = True

    def entry(symbol, *, alertable=True, playbook=None, state=None):
        state = state or event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
        playbook = playbook or event_playbooks.EventPlaybookType.PROXY_ATTENTION.value
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|coin|{playbook}",
            cluster_id="spacex|ipo_proxy|2026-06-20",
            event_id=f"{symbol}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time="2026-06-20T13:30:00+00:00",
            state=state,
            previous_state="WATCHLIST",
            first_seen_at="2026-06-18T12:00:00+00:00",
            last_seen_at="2026-06-18T13:00:00+00:00",
            source_count=1,
            highest_score=82,
            latest_score=82,
            latest_tier="HIGH_PRIORITY_WATCH",
            latest_event_name=f"{symbol} route event",
            latest_source="test",
            latest_playbook_type=playbook,
            latest_playbook_score=82,
            latest_playbook_action="high_priority_watch",
            should_alert=alertable,
            suppressed_reason=None if alertable else "duplicate state, no escalation",
        )

    sent = []

    def fake_send(message, *, parse_mode=None, chat_ids=None):
        sent.append((message, parse_mode, tuple(chat_ids or ())))
        return True

    original_storage = scanner.Storage
    original_send = scanner.send_telegram
    original_structured_send = scanner.send_telegram_structured
    original_ids = config.TELEGRAM_CHAT_IDS
    original_notification_flags = {
        "EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY": config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY,
        "EVENT_ALPHA_NOTIFY_SCOPE": config.EVENT_ALPHA_NOTIFY_SCOPE,
        "EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED": config.EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED,
        "EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED": config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
    }
    FakeStorage.meta = {}
    scanner.Storage = FakeStorage
    scanner.send_telegram = fake_send
    scanner.send_telegram_structured = fake_send
    config.TELEGRAM_CHAT_IDS = ["fallback"]
    config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY = True
    config.EVENT_ALPHA_NOTIFY_SCOPE = "global"
    config.EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED = False
    config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED = False
    try:
        cfg = event_alerts.EventAlertConfig(enabled=True)
        result = scanner._send_event_alpha_routed_digest([], cfg)
        assert result.requested is True
        assert result.attempted is False
        assert result.success is False
        assert result.block_reason == "no router-approved escalations"
        assert sent == []

        suppressed = event_alpha_router.EventAlphaRouteDecision(
            entry=entry("DUP", alertable=False),
            route=event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE,
            alertable=False,
            reason="duplicate",
        )
        result = scanner._send_event_alpha_routed_digest([suppressed], cfg)
        assert result.attempted is False
        assert result.block_reason == "no router-approved escalations"
        assert sent == []

        high = event_alpha_router.EventAlphaRouteDecision(
            entry=entry("HIGH"),
            route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
            alertable=True,
            reason="watchlist escalation",
        )
        result = scanner._send_event_alpha_routed_digest([suppressed, high], cfg)
        assert result.attempted is True
        assert result.success is True
        assert result.items_attempted == 1
        assert result.items_delivered == 1
        assert len(sent) == 1
        assert sent[0][1] == "HTML"
        assert sent[0][2] == ("chat",)
        assert "Event Alpha High-Priority Research" in sent[0][0]
        assert "high-priority research" in sent[0][0]
        assert "HIGH" in sent[0][0]
        assert "DUP" not in sent[0][0]
        assert any(
            key.startswith("event_alpha_sent_count_instant_") and value == "1"
            for key, value in FakeStorage.meta.items()
        )

        FakeStorage.meta = {}
        scanner.send_telegram = lambda message, *, parse_mode=None, chat_ids=None: False
        scanner.send_telegram_structured = lambda message, *, parse_mode=None, chat_ids=None: False
        failed = scanner._send_event_alpha_routed_digest([high], cfg)
        assert failed.attempted is True
        assert failed.success is False
        assert failed.items_attempted == 1
        assert failed.items_delivered == 0
        assert "no channel delivered" in failed.block_reason
        disabled = scanner._send_event_alpha_routed_digest([high], event_alerts.EventAlertConfig(enabled=False))
        assert disabled.requested is True
        assert disabled.attempted is False
        assert disabled.block_reason == "event alerts disabled"
    finally:
        scanner.Storage = original_storage
        scanner.send_telegram = original_send
        scanner.send_telegram_structured = original_structured_send
        config.TELEGRAM_CHAT_IDS = original_ids
        for name, value in original_notification_flags.items():
            setattr(config, name, value)


def test_event_alpha_core_digest_caps_daily_items_with_local_brief_overflow():
    from crypto_rsi_scanner import event_alpha_notifications as notif, event_alpha_router

    decisions = [
        _notify_route_decision(
            f"CORE{i}",
            event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
        )
        for i in range(18)
    ]

    message = notif.format_core_opportunity_telegram_digest(decisions, profile="notify_llm_deep", max_items=5)

    assert "Items: 5" in message
    assert "1. CORE0 / core0" in message
    assert "5. CORE4 / core4" in message
    assert "6. CORE5 / core5" not in message
    assert "+13 more in local brief." in message


def test_event_alpha_live_daily_digest_requires_confirmation_and_dedupes_family():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notifications as notif, event_alpha_router

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    confirmed = _notify_route_decision(
        "CHZ",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    duplicate = _notify_route_decision(
        "CHZ",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    weak = _notify_route_decision(
        "SYN",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    single_source_fan = _notify_route_decision(
        "FAN",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    core_rows = [
        {
            "core_opportunity_id": "core-chz",
            "source_alert_ids": [confirmed.alert_id, duplicate.alert_id],
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "incident_id": "world-cup",
            "impact_path_type": "fan_sports",
            "source_pack": "fan_sports_pack",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "final_opportunity_level": "validated_digest",
            "evidence_acquisition_status": "accepted_evidence_found",
            "accepted_evidence_count": 1,
            "accepted_provider_counts": {"cryptopanic": 1},
            "accepted_reason_codes": ["cryptopanic_currency_tag_match"],
            "source_class": "cryptopanic_tagged",
            "market_confirmation_level": "moderate",
            "market_context_freshness_status": "fresh",
        },
        {
            "core_opportunity_id": "core-fan",
            "source_alert_ids": [single_source_fan.alert_id],
            "symbol": "FAN",
            "coin_id": "fan-token",
            "incident_id": "world-cup-single-source",
            "impact_path_type": "fan_sports",
            "source_pack": "fan_sports_pack",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "final_opportunity_level": "validated_digest",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 82,
            "evidence_acquisition_status": "accepted_evidence_found",
            "accepted_evidence_count": 1,
            "accepted_provider_counts": {"cryptopanic": 1},
            "accepted_reason_codes": ["cryptopanic_currency_tag_match"],
            "source_class": "cryptopanic_tagged",
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
        },
        {
            "core_opportunity_id": "core-syn",
            "source_alert_ids": [weak.alert_id],
            "symbol": "SYN",
            "coin_id": "synapse",
            "incident_id": "strategic",
            "impact_path_type": "strategic_investment",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "final_opportunity_level": "validated_digest",
            "evidence_acquisition_status": "not_executed",
            "accepted_evidence_count": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
        },
    ]
    cfg = notif.EventAlphaNotificationConfig(
        enabled=True,
        profile_name="notify_llm_deep",
        artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
        daily_digest_cooldown_hours=0,
        daily_digest_max_items=5,
        research_review_digest_enabled=True,
        research_review_digest_min_score=0,
        research_review_digest_send_with_alerts=True,
    )

    plan = notif.build_notification_plan(
        [confirmed, duplicate, weak, single_source_fan],
        storage=FakeStorage(),
        cfg=cfg,
        now=datetime(2026, 6, 20, 12, tzinfo=timezone.utc),
        core_opportunity_rows=core_rows,
    )

    daily = plan.decisions_by_lane[notif.LANE_DAILY_DIGEST]
    assert len(daily) == 1
    assert daily[0].entry.symbol == "CHZ"
    assert all(item.entry.symbol != "SYN" for item in daily)
    assert any(getattr(item, "decision", item).entry.symbol == "FAN" for item in plan.research_review_items)
    assert all(item.entry.symbol != "FAN" for item in daily)


def test_event_alpha_status_profile_budget_and_unknown_profile():
    import contextlib
    import io
    import os
    from crypto_rsi_scanner import config, event_alpha_profiles, scanner

    profile_keys = set()
    for profile_name in event_alpha_profiles.profile_names():
        profile_keys.update(event_alpha_profiles.get_profile(profile_name).config_overrides)
    profile_keys.add("EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS")
    original = {
        name: getattr(config, name)
        for name in profile_keys
        if hasattr(config, name)
    }
    env_keys = (
        "RSI_EVENT_LLM_MAX_CANDIDATES_PER_RUN",
        "RSI_EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN",
        "RSI_EVENT_LLM_MAX_CALLS_PER_RUN",
        "RSI_EVENT_LLM_MAX_CALLS_PER_DAY",
        "RSI_EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY",
        "RSI_EVENT_LLM_ESTIMATED_COST_PER_CALL_USD",
        "RSI_EVENT_LLM_MAX_PARALLEL_CALLS",
        "RSI_EVENT_LLM_OPENAI_TIMEOUT",
        "RSI_EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT",
        "RSI_EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS",
        "RSI_EVENT_LLM_CACHE_TTL_HOURS",
    )
    original_env = {key: os.environ.get(key) for key in env_keys}
    try:
        profile = event_alpha_profiles.get_profile("full_llm_live")
        assert profile.config_overrides["EVENT_LLM_MAX_CALLS_PER_RUN"] > 0
        assert profile.config_overrides["EVENT_LLM_MAX_CALLS_PER_DAY"] > 0
        assert profile.config_overrides["EVENT_LLM_MAX_CANDIDATES_PER_RUN"] > 0
        assert profile.config_overrides["EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN"] > 0
        assert profile.config_overrides["EVENT_LLM_OPENAI_TIMEOUT"] >= 30.0
        assert profile.config_overrides["EVENT_LLM_MAX_PARALLEL_CALLS"] >= 12
        assert "LLM budget defaults" in event_alpha_profiles.format_profile_report(profile)
        assert "artifact policy:" in event_alpha_profiles.format_profile_report(profile)
        assert event_alpha_profiles.get_profile("research_send").config_overrides["EVENT_ALPHA_SNAPSHOT_POLICY"] == "alertable"
        assert profile.config_overrides["EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH"].name == "public_rss_feeds.txt"
        assert event_alpha_profiles.get_profile("research_send").config_overrides[
            "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH"
        ].name == "public_rss_feeds.txt"

        default_out = io.StringIO()
        with contextlib.redirect_stdout(default_out):
            scanner.event_alpha_status()
        profile_out = io.StringIO()
        with contextlib.redirect_stdout(profile_out):
            scanner.event_alpha_status(profile_name="no_key_live")
        full_llm_out = io.StringIO()
        with contextlib.redirect_stdout(full_llm_out):
            scanner.event_alpha_status(profile_name="full_llm_live")
        send_out = io.StringIO()
        with contextlib.redirect_stdout(send_out):
            scanner.event_alpha_status(profile_name="research_send")
        assert "profile: default" in default_out.getvalue()
        assert "profile: no_key_live" in profile_out.getvalue()
        assert default_out.getvalue() != profile_out.getvalue()
        assert "LLM budget:" in profile_out.getvalue()
        assert "max_candidates=" in full_llm_out.getvalue()
        assert "max_extract_events=" in full_llm_out.getvalue()
        assert "parallel=" in full_llm_out.getvalue()
        assert "timeouts=" in full_llm_out.getvalue()
        assert "watchlist_monitor:" in profile_out.getvalue()
        assert "- READY project_blog_rss" in full_llm_out.getvalue()
        assert "- READY project_blog_rss" in send_out.getvalue()

        os.environ["RSI_EVENT_LLM_MAX_CANDIDATES_PER_RUN"] = "111"
        os.environ["RSI_EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN"] = "222"
        os.environ["RSI_EVENT_LLM_MAX_CALLS_PER_RUN"] = "333"
        os.environ["RSI_EVENT_LLM_MAX_CALLS_PER_DAY"] = "444"
        os.environ["RSI_EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY"] = "55.5"
        os.environ["RSI_EVENT_LLM_ESTIMATED_COST_PER_CALL_USD"] = "0.06"
        os.environ["RSI_EVENT_LLM_MAX_PARALLEL_CALLS"] = "7"
        os.environ["RSI_EVENT_LLM_OPENAI_TIMEOUT"] = "41"
        os.environ["RSI_EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT"] = "42"
        os.environ["RSI_EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS"] = "543"
        os.environ["RSI_EVENT_LLM_CACHE_TTL_HOURS"] = "12"
        override_out = io.StringIO()
        with contextlib.redirect_stdout(override_out):
            scanner.event_alpha_status(profile_name="notify_llm")
        override_text = override_out.getvalue()
        assert "max_candidates=111" in override_text
        assert "max_extract_events=222" in override_text
        assert "max_run=333 max_day=444" in override_text
        assert "max_cost_day=55.5" in override_text
        assert "parallel=7" in override_text
        assert "timeouts=41/42s" in override_text
        assert "cache_ttl_hours=12" in override_text

        bad_out = io.StringIO()
        with contextlib.redirect_stdout(bad_out):
            scanner.event_alpha_status(profile_name="missing-profile")
        assert "unknown Event Alpha profile" in bad_out.getvalue()
    finally:
        for name, value in original.items():
            setattr(config, name, value)
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_event_watchlist_monitor_detects_material_updates_without_new_source():
    from pathlib import Path
    from crypto_rsi_scanner import event_watchlist, event_watchlist_monitor

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="spacex|velvet|proxy_attention",
        cluster_id="spacex|ipo_proxy|2026-06-20",
        event_id="velvet-event",
        coin_id="velvet",
        symbol="VELVET",
        relationship_type="proxy_attention",
        external_asset="SpaceX",
        event_time="2026-06-18T13:00:00+00:00",
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        previous_state="RADAR",
        first_seen_at="2026-06-18T10:00:00+00:00",
        last_seen_at="2026-06-18T11:00:00+00:00",
        source_count=2,
        highest_score=72,
        latest_score=72,
        latest_tier="WATCHLIST",
        latest_event_name="VELVET SpaceX proxy",
        latest_source="fixture",
        latest_score_components={"derivatives_crowding": 55, "cluster_confidence": 70},
    )
    expired = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="old|old|proxy_attention",
        cluster_id="old",
        event_id="old-event",
        coin_id="old",
        symbol="OLD",
        relationship_type="proxy_attention",
        external_asset=None,
        event_time=None,
        state=event_watchlist.EventWatchlistState.EXPIRED.value,
        previous_state="RADAR",
        first_seen_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-18T11:00:00+00:00",
        latest_event_name="old",
        latest_source="fixture",
    )
    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=2,
        entries=[entry, expired],
        latest_only=True,
    )
    result = event_watchlist_monitor.monitor_watchlist(
        read,
        market_rows=[{
            "id": "velvet",
            "symbol": "velvet",
            "name": "Velvet",
            "current_price": 1.25,
            "price_change_percentage_24h_in_currency": 38,
            "price_change_percentage_7d_in_currency": 120,
            "total_volume": 6000000,
            "market_cap": 20000000,
            "volume_zscore_24h": 4.2,
        }],
        now=pd.Timestamp("2026-06-18T14:00:00Z").to_pydatetime(),
    )
    assert result.active_entries == 1
    assert result.skipped_expired == 1
    row = result.rows[0]
    assert row.material_update is True
    assert "EVENT_PASSED" in row.state_transition_hints
    assert "DERIVATIVES_HEATED" in row.state_transition_hints
    assert "MARKET_SCORE_JUMP" in row.state_transition_hints
    assert "TRIGGERED_FADE" not in row.state_transition_hints
    assert "EVENT WATCHLIST MONITOR" in event_watchlist_monitor.format_watchlist_monitor_report(result)


def test_event_alpha_pipeline_routes_monitor_updates_without_new_source():
    import json
    import tempfile
    from dataclasses import asdict
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_pipeline,
        event_alpha_router,
        event_playbooks,
        event_watchlist,
    )
    from crypto_rsi_scanner.event_models import EventDiscoveryResult

    def entry(symbol, *, event_time, state=None):
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol.lower()}|coin|proxy_attention",
            cluster_id=f"{symbol.lower()}|proxy|2026-06-18",
            event_id=f"{symbol.lower()}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time=event_time,
            state=state or event_watchlist.EventWatchlistState.WATCHLIST.value,
            previous_state=event_watchlist.EventWatchlistState.RADAR.value,
            first_seen_at="2026-06-18T10:00:00+00:00",
            last_seen_at="2026-06-18T11:00:00+00:00",
            source_count=2,
            highest_score=72,
            latest_score=72,
            latest_tier="WATCHLIST",
            latest_event_name=f"{symbol} SpaceX proxy",
            latest_source="fixture",
            latest_playbook_type=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
            latest_playbook_score=72,
            latest_playbook_action="watchlist",
            latest_score_components={
                "derivatives_crowding": 55,
                "cluster_confidence": 70,
                "impact_path_type": "proxy_exposure",
                "impact_path_strength": "strong",
                "candidate_role": "proxy_instrument",
                "evidence_quality_score": 78,
                "source_class": "crypto_native",
                "evidence_specificity": "asset_and_catalyst",
                "market_confirmation_score": 65,
                "market_confirmation_level": "confirmed",
                "opportunity_score_final": 80,
                "opportunity_level": "watchlist",
                "opportunity_verdict_reasons": ["fixture_monitor_route_quality_context"],
                "why_local_only": "not_local_only",
                "why_not_watchlist": "already_watchlisted",
                "manual_verification_items": ["verify source, catalyst timing, and liquidity"],
                "upgrade_requirements": [],
                "downgrade_warnings": [],
            },
            should_alert=False,
            suppressed_reason="duplicate state, no escalation",
        )

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "watchlist.jsonl"
        rows = [
            entry("APPROACH", event_time="2026-06-18T17:00:00+00:00"),
            entry("PASSED", event_time="2026-06-18T12:30:00+00:00"),
            entry("ARMED", event_time="2026-06-18T12:30:00+00:00", state=event_watchlist.EventWatchlistState.ARMED.value),
        ]
        path.write_text(
            "\n".join(json.dumps(asdict(row), sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )
        result = event_alpha_pipeline.run_event_alpha_pipeline(
            EventDiscoveryResult((), (), (), (), ()),
            now=datetime(2026, 6, 18, 13, 0, tzinfo=timezone.utc),
            watchlist_cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=path),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=False,
            route=True,
            watchlist_monitor_enabled=True,
            watchlist_monitor_market_rows=[{
                "id": "passed",
                "symbol": "passed",
                "price_change_percentage_24h_in_currency": 45,
                "total_volume": 6000000,
                "market_cap": 20000000,
                "volume_zscore_24h": 4.0,
            }],
            watchlist_monitor_route_updates=True,
        )
    assert result.watchlist_monitor_active_entries == 3
    assert result.watchlist_monitor_material_updates == 3
    assert result.router_result is not None
    by_symbol = {decision.entry.symbol: decision for decision in result.router_result.decisions}
    assert by_symbol["APPROACH"].alertable is True
    assert by_symbol["APPROACH"].lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST
    assert by_symbol["PASSED"].alertable is True
    assert by_symbol["PASSED"].entry.state == event_watchlist.EventWatchlistState.EVENT_PASSED.value
    assert by_symbol["ARMED"].alertable is True
    assert by_symbol["ARMED"].entry.state == event_watchlist.EventWatchlistState.ARMED.value
    assert all(decision.entry.state != event_watchlist.EventWatchlistState.TRIGGERED_FADE.value for decision in by_symbol.values())
    assert "watchlist_monitor_material=3" in event_alpha_pipeline.format_event_alpha_pipeline_report(result)


def test_event_watchlist_scanner_refresh_and_report_with_fixture_anomalies():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    original = {
        "EVENT_DISCOVERY_EVENTS_PATH": config.EVENT_DISCOVERY_EVENTS_PATH,
        "EVENT_DISCOVERY_ALIASES_PATH": config.EVENT_DISCOVERY_ALIASES_PATH,
        "EVENT_DISCOVERY_UNIVERSE_PATH": config.EVENT_DISCOVERY_UNIVERSE_PATH,
        "EVENT_DISCOVERY_UNIVERSE_LIVE": config.EVENT_DISCOVERY_UNIVERSE_LIVE,
        "EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT": config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT,
        "EVENT_MARKET_ENRICHMENT_ENABLED": config.EVENT_MARKET_ENRICHMENT_ENABLED,
        "EVENT_ANOMALY_SCANNER_ENABLED": config.EVENT_ANOMALY_SCANNER_ENABLED,
        "EVENT_ANOMALY_MIN_RETURN_24H": config.EVENT_ANOMALY_MIN_RETURN_24H,
        "EVENT_ANOMALY_MIN_VOLUME_MCAP": config.EVENT_ANOMALY_MIN_VOLUME_MCAP,
        "EVENT_ANOMALY_MIN_VOLUME_ZSCORE": config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE,
        "EVENT_ANOMALY_MAX_ASSETS": config.EVENT_ANOMALY_MAX_ASSETS,
        "EVENT_WATCHLIST_ENABLED": config.EVENT_WATCHLIST_ENABLED,
        "EVENT_WATCHLIST_STATE_PATH": config.EVENT_WATCHLIST_STATE_PATH,
        "EVENT_WATCHLIST_EXPIRE_HOURS_AFTER_EVENT": config.EVENT_WATCHLIST_EXPIRE_HOURS_AFTER_EVENT,
        "EVENT_ALPHA_ROUTER_ENABLED": config.EVENT_ALPHA_ROUTER_ENABLED,
        "EVENT_ALPHA_FEEDBACK_PATH": config.EVENT_ALPHA_FEEDBACK_PATH,
    }
    with tempfile.TemporaryDirectory() as tmp:
        config.EVENT_DISCOVERY_EVENTS_PATH = None
        config.EVENT_DISCOVERY_ALIASES_PATH = None
        config.EVENT_DISCOVERY_UNIVERSE_PATH = Path("fixtures/coingecko_smoke/top_markets.json")
        config.EVENT_DISCOVERY_UNIVERSE_LIVE = False
        config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT = 0
        config.EVENT_MARKET_ENRICHMENT_ENABLED = True
        config.EVENT_ANOMALY_SCANNER_ENABLED = True
        config.EVENT_ANOMALY_MIN_RETURN_24H = 0.03
        config.EVENT_ANOMALY_MIN_VOLUME_MCAP = 0.05
        config.EVENT_ANOMALY_MIN_VOLUME_ZSCORE = 3.0
        config.EVENT_ANOMALY_MAX_ASSETS = 10
        config.EVENT_WATCHLIST_ENABLED = True
        config.EVENT_WATCHLIST_STATE_PATH = Path(tmp) / "watchlist.jsonl"
        config.EVENT_WATCHLIST_EXPIRE_HOURS_AFTER_EVENT = 72
        config.EVENT_ALPHA_ROUTER_ENABLED = True
        config.EVENT_ALPHA_FEEDBACK_PATH = Path(tmp) / "feedback.jsonl"
        try:
            refresh_out = io.StringIO()
            with contextlib.redirect_stdout(refresh_out):
                scanner.event_watchlist_refresh(event_now="2026-06-15T16:00:00Z")
            refresh_text = refresh_out.getvalue()
            assert "EVENT WATCHLIST REFRESH" in refresh_text
            assert "rows_written: 1" in refresh_text
            assert "alertable escalations: 0" in refresh_text

            report_out = io.StringIO()
            with contextlib.redirect_stdout(report_out):
                scanner.event_watchlist_report()
            report_text = report_out.getvalue()
            assert "EVENT WATCHLIST REPORT" in report_text
            assert "RAW_EVIDENCE" in report_text
            assert "SOL/solana" in report_text
            assert "playbook: market_anomaly_unknown" in report_text

            router_out = io.StringIO()
            with contextlib.redirect_stdout(router_out):
                scanner.event_alpha_router_report()
            router_text = router_out.getvalue()
            assert "EVENT ALPHA ROUTER REPORT" in router_text
            assert "router_enabled: true" in router_text
            assert "STORE_ONLY" in router_text
            assert "SOL/solana" in router_text

            feedback_out = io.StringIO()
            with contextlib.redirect_stdout(feedback_out):
                scanner.event_feedback_mark(
                    "SOL",
                    "junk",
                    notes="no catalyst",
                    marked_by="tester",
                )
            feedback_text = feedback_out.getvalue()
            assert "EVENT ALPHA FEEDBACK MARKED" in feedback_text
            assert "label: junk" in feedback_text
            assert "SOL/solana" in feedback_text

            feedback_report_out = io.StringIO()
            with contextlib.redirect_stdout(feedback_report_out):
                scanner.event_feedback_report()
            feedback_report = feedback_report_out.getvalue()
            assert "EVENT ALPHA FEEDBACK REPORT" in feedback_report
            assert "junk=1" in feedback_report
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_makefile_has_event_alpha_no_key_target():
    from pathlib import Path

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-eval:" in text
    assert "event_alpha_eval" in text
    assert "event-alpha-no-key-report:" in text
    assert "--event-alpha-radar-report" in text
    assert "event-alpha-cycle:" in text
    assert "event-alpha-cycle-llm:" in text
    assert "event-catalyst-search-fixture-report:" in text
    assert "event-alpha-cycle-search:" in text
    assert "event-alpha-cycle-search-llm:" in text
    assert "--event-catalyst-search-report" in text
    assert "event-alpha-cycle-send:" in text
    assert "event-alpha-notify-cycle:" in text
    assert "event-alpha-notify-no-key:" in text
    assert "event-alpha-notify-llm:" in text
    assert "event-alpha-notify-preview:" in text
    assert "event-alpha-notify-go-no-go:" in text
    assert "event-alpha-notification-checklist:" in text
    assert "event-alpha-notification-runs-report:" in text
    assert "event-alpha-provider-health-report:" in text
    assert "event-alpha-provider-health-reset:" in text
    assert "event-alpha-day1-start:" in text
    assert "event-alpha-day1-start-llm:" in text
    assert "event-alpha-notify-start-no-key:" in text
    assert "event-alpha-notify-start-llm:" in text
    assert "event-alpha-send-test:" in text
    assert "event-alpha-runs-report:" in text
    assert "event-alpha-status:" in text
    assert "event-alpha-daily-report:" in text
    assert "event-alpha-daily-llm-report:" in text
    assert "event-alpha-daily-send:" in text
    assert "event-alpha-health:" in text
    assert "event-alpha-open-items:" in text
    assert "event-alpha-daily-brief:" in text
    assert "event-alpha-replay:" in text
    assert "event-alpha-prune-artifacts:" in text
    assert "--event-alpha-profile no_key_live" in text
    assert "--event-alpha-profile full_llm_live" in text
    assert "--event-alpha-profile research_send --event-alert-send" in text
    assert "--event-alpha-notify-cycle --event-alpha-profile $(PROFILE) --event-alert-send" in text
    assert "RSI_EVENT_ALERTS_ENABLED=1" in text
    assert "RSI_EVENT_WATCHLIST_MONITOR_ENABLED=1" in text
    assert "event-alpha-alerts-report:" in text
    assert "event-alpha-fill-outcomes:" in text
    assert "--event-alpha-cycle" in text
    assert "--event-alpha-alerts-report" in text
    assert "--event-alpha-fill-outcomes" in text
    assert "RSI_EVENT_ANOMALY_SCANNER_ENABLED=1" in text
    assert "RSI_EVENT_CATALYST_SEARCH_ENABLED=1" in text
    assert "RSI_EVENT_WATCHLIST_ENABLED=1" in text
    assert "RSI_EVENT_ALPHA_ROUTER_ENABLED=1" in text
    assert "RSI_EVENT_ALPHA_ALERT_STORE_PATH" in text
    assert "event-watchlist-refresh:" in text
    assert "event-watchlist-report:" in text
    assert "event-watchlist-monitor:" in text
    assert "event-alpha-router-report:" in text
    assert "event-alpha-missed-report:" in text
    assert "event-alpha-calibration-report:" in text
    assert "event-research-cards:" in text
    assert "event-feedback-report:" in text
    assert "event-feedback-useful:" in text
    assert "event-feedback-junk:" in text
    assert "event-feedback-watch:" in text
    assert "--event-watchlist-refresh" in text
    assert "--event-alpha-router-report" in text
    assert "--event-alpha-runs-report" in text
    assert "--event-alpha-status" in text


def test_event_classification_proxy_direct_and_ambiguous_cases():
    result = _event_discovery_fixture_result()
    by_coin = {classification.coin_id: classification for classification in result.classifications}
    assert by_coin["testvelvet"].is_proxy_narrative is True
    assert by_coin["testvelvet"].is_direct_beneficiary is False
    assert by_coin["testvelvet"].relationship_type == "proxy_exposure"
    assert by_coin["testbtc"].is_proxy_narrative is False
    assert by_coin["testbtc"].is_direct_beneficiary is True
    assert by_coin["testbtc"].relationship_type == "direct_token_event"
    assert by_coin["testtoken"].relationship_type == "direct_listing"
    assert by_coin["testpump"].relationship_type == "ambiguous"


def test_event_fade_auto_report_groups_discovered_candidates():
    from crypto_rsi_scanner import event_discovery

    result = _full_event_discovery_fixture_result()
    report = event_discovery.format_event_fade_auto_report(result)
    assert "EVENT FADE AUTO REPORT" in report
    assert "no alerts, DB writes, paper trades, or orders" in report
    assert "EVENT RADAR" in report
    for section in (
        "PROXY WATCHLIST",
        "BLOWOFF RISK",
        "EVENT PASSED",
        "ARMED",
        "TRIGGERED",
        "REJECTED / NO TRADE",
        "AMBIGUOUS",
    ):
        assert section in report
    assert "TRIGGERED\n  TESTVELVET" in report
    assert "BLOWOFF RISK\n  TESTAI" in report
    assert "PROXY WATCHLIST\n  TESTPRED" in report
    assert "REJECTED / NO TRADE" in report
    assert "  TESTLIST     coin=testlist" in report
    assert "TESTUNLOCK" in report
    assert "AMBIGUOUS" in report
    assert "  TESTPUMP     coin=testpump" in report
    assert "missing:" in report
    assert "sources:" in report
    assert "invalidation: 8.65" in report


def test_event_fade_validation_sample_rows_and_serializers():
    import csv
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery

    exported_at = datetime(2026, 6, 16, 12, 5, tzinfo=timezone.utc)
    result = _full_event_discovery_fixture_result()
    rows = event_discovery.event_fade_validation_sample_rows(result, exported_at=exported_at)
    assert len(rows) == len(result.candidates)
    assert set(rows[0]) == set(event_discovery.VALIDATION_SAMPLE_FIELDS)

    velvet = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    assert velvet["schema_version"] == "event_fade_validation_sample_v1"
    assert velvet["exported_at"] == "2026-06-16T12:05:00+00:00"
    assert velvet["event_name"] == "SpaceX IPO trading start"
    assert velvet["event_time_source"] == "explicit"
    assert velvet["raw_ids"] == ["velvet-spacex-proxy-1", "velvet-spacex-proxy-duplicate"]
    assert len(velvet["raw_titles"]) == 2
    assert len(velvet["raw_content_hashes"]) == 2
    assert velvet["raw_published_at"] == [
        "2026-06-13T10:00:00+00:00",
        "2026-06-13T11:00:00+00:00",
    ]
    assert velvet["raw_fetched_at"] == [
        "2026-06-15T15:00:00+00:00",
        "2026-06-15T15:30:00+00:00",
    ]
    assert velvet["published_at_min"] == "2026-06-13T10:00:00+00:00"
    assert velvet["published_at_max"] == "2026-06-13T11:00:00+00:00"
    assert velvet["fetched_at_min"] == "2026-06-15T15:00:00+00:00"
    assert velvet["fetched_at_max"] == "2026-06-15T15:30:00+00:00"
    assert velvet["source_count"] == 2
    assert velvet["relationship_type"] == "proxy_exposure"
    assert velvet["is_proxy_narrative"] is True
    assert velvet["is_direct_beneficiary"] is False
    assert velvet["asset_role"] == "proxy_instrument"
    assert velvet["asset_role_confidence"] >= 0.75
    assert velvet["asset_role_reason"]
    assert velvet["asset_role_evidence"]
    assert velvet["signal_type"] == "SHORT_TRIGGERED"
    assert velvet["fade_state"] == "TRIGGERED_SHORT"
    assert velvet["eligible"] is True
    assert velvet["component_scores"]["post_event_failure"] >= 80
    assert velvet["reason_codes"]
    assert velvet["warnings"] == ["alert-only mode; no live order placed"]
    assert velvet["trigger_observed_at"] is not None
    assert velvet["entry_reference_price"] == 7.2
    assert velvet["invalidation_level"] == 8.65
    assert velvet["human_label"] == ""
    assert velvet["human_notes"] == ""
    assert velvet["reviewed_by"] == ""
    assert velvet["reviewed_at"] == ""
    assert velvet["max_adverse_excursion"] is None
    assert velvet["post_event_return_7d"] is None
    assert velvet["event_time_entry_price"] is None
    assert velvet["event_time_post_event_return_72h"] is None

    listing = next(
        row
        for row in rows
        if row["asset_symbol"] == "TESTLIST" and row["relationship_type"] == "direct_listing"
    )
    assert listing["eligible"] is False
    assert listing["signal_type"] == "NO_TRADE"
    assert listing["large_holder_exchange_inflow"] is True
    assert listing["missing_data"] == ["technical"]

    jsonl = event_discovery.format_validation_sample_jsonl(rows)
    parsed = [json.loads(line) for line in jsonl.splitlines()]
    assert len(parsed) == len(rows)
    assert parsed[0]["schema_version"] == "event_fade_validation_sample_v1"

    csv_text = event_discovery.format_validation_sample_csv(rows)
    csv_rows = list(csv.DictReader(csv_text.splitlines()))
    assert len(csv_rows) == len(rows)
    assert json.loads(csv_rows[0]["component_scores"])
    assert json.loads(csv_rows[0]["source_urls"])

    with tempfile.TemporaryDirectory() as tmp:
        jsonl_path = Path(tmp) / "sample.jsonl"
        csv_path = Path(tmp) / "sample.csv"
        event_discovery.write_validation_sample(rows, jsonl_path)
        event_discovery.write_validation_sample(rows, csv_path)
        assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == len(rows)
        assert len(list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))) == len(rows)


def test_event_fade_validation_review_blocks_unlabeled_export():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    review = event_validation.review_validation_sample(rows)
    assert review.total_rows == len(rows)
    assert review.reviewed_rows == 0
    assert review.unlabeled_rows == len(rows)
    assert review.promotion_ready is False
    assert "reviewed proxy candidates 0/25" in review.promotion_blockers
    assert "reviewed direct/ambiguous controls 0/50" in review.promotion_blockers
    assert "reviewed SHORT_TRIGGERED candidates 0/10" in review.promotion_blockers
    next_steps = event_validation.validation_review_next_steps(review)
    assert "Add/review 25 more proxy candidate row(s) (current 0/25)." in next_steps
    assert "Add/review 50 more direct or ambiguous control row(s) (current 0/50)." in next_steps
    assert "Add/review 10 more SHORT_TRIGGERED row(s) with outcomes (current 0/10)." in next_steps

    report = event_validation.format_validation_review(review)
    assert "EVENT FADE VALIDATION SAMPLE REVIEW" in report
    assert "No reviewed labels yet" in report
    assert "NEXT SAMPLE WORK" in report
    assert "Add/review 25 more proxy candidate row(s)" in report
    assert "PROMOTION STATUS" in report
    assert "BLOCKED" in report


def test_event_fade_validation_review_requires_explicit_review_status_and_label():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    labeled_without_status = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    labeled_without_status["human_label"] = "valid_proxy_fade"
    labeled_without_status["max_favorable_excursion"] = 0.42
    labeled_without_status["max_adverse_excursion"] = 0.08
    labeled_without_status["post_event_return_72h"] = -0.22
    labeled_without_status["event_time_post_event_return_72h"] = -0.12
    reviewed_without_label = next(row for row in rows if row["asset_symbol"] == "TESTBTC")
    reviewed_without_label["review_status"] = "reviewed"
    invalid_label = next(row for row in rows if row["asset_symbol"] == "TESTAI")
    invalid_label["human_label"] = "valid_proxy"

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=1,
        min_negative_controls=1,
        min_triggered_reviewed=1,
    )
    assert review.reviewed_rows == 0
    assert sum(cohort.reviewed_rows for cohort in review.event_type_cohorts) == 0
    assert sum(cohort.triggered_reviewed for cohort in review.event_type_cohorts) == 0
    assert review.unknown_label_rows == 1
    assert review.missing_review_status_rows == 2
    assert review.missing_human_label_rows == 1
    assert "1 labeled row(s) use unknown human_label values" in review.promotion_blockers
    assert "2 labeled row(s) are missing review_status=reviewed" in review.promotion_blockers
    assert "1 reviewed row(s) are missing human_label" in review.promotion_blockers
    next_steps = event_validation.validation_review_next_steps(review)
    assert "Fix 1 labeled row(s) with unknown human_label values." in next_steps
    assert (
        "Set review_status=reviewed for 2 labeled row(s), or clear labels that are not fully reviewed."
        in next_steps
    )
    assert "Fill human_label for 1 row(s) marked reviewed." in next_steps

    queue = event_validation.build_labeling_queue(rows, limit=3)
    categories = [item.category for item in queue.items]
    assert categories[0] == "fix_unknown_label"
    assert "fill_review_label" in categories
    assert "mark_reviewed_status" in categories


def test_event_fade_validation_review_requires_provenance_for_promotion():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    triggered = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    triggered["review_status"] = "reviewed"
    triggered["human_label"] = "valid_proxy_fade"
    triggered["max_favorable_excursion"] = 0.42
    triggered["max_adverse_excursion"] = 0.08
    triggered["post_event_return_72h"] = -0.22
    triggered["event_time_post_event_return_72h"] = -0.12

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=1,
        min_negative_controls=0,
        min_triggered_reviewed=1,
        min_trigger_precision=0.90,
        min_mfe_mae_ratio=2.0,
        min_proxy_event_types=1,
        min_proxy_source_providers=1,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.reviewed_rows == 1
    assert review.missing_review_provenance_rows == 1
    assert review.promotion_ready is False
    assert "1 reviewed row(s) are missing review provenance" in review.promotion_blockers
    assert (
        "Fill reviewed_by and reviewed_at for 1 reviewed row(s)."
        in event_validation.validation_review_next_steps(review)
    )

    report = event_validation.format_validation_review(review)
    assert "reviewed rows missing provenance: 1" in report

    queue = event_validation.build_labeling_queue(rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTVELVET")
    assert item.category == "add_review_provenance"
    assert item.missing_fields == ("reviewed_by", "reviewed_at")


def test_event_fade_validation_review_metrics_and_file_loaders():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())

    def pick(symbol, relationship=None):
        for row in rows:
            if row["asset_symbol"] != symbol:
                continue
            if relationship is not None and row["relationship_type"] != relationship:
                continue
            return row
        raise AssertionError(f"missing row for {symbol}")

    def mark(symbol, label, relationship=None):
        row = pick(symbol, relationship)
        row["human_label"] = label
        row["review_status"] = "reviewed"
        _stamp_review_provenance(row)
        row["first_seen_time"] = "2026-06-12T00:00:00+00:00"
        row["published_at_min"] = "2026-06-12T00:00:00+00:00"
        row["published_at_max"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_min"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_max"] = "2026-06-12T00:00:00+00:00"
        row["raw_published_at"] = ["2026-06-12T00:00:00+00:00"]
        row["raw_fetched_at"] = ["2026-06-12T00:00:00+00:00"]
        return row

    velvet = mark("TESTVELVET", "valid_proxy_fade")
    velvet["max_favorable_excursion"] = 0.42
    velvet["max_adverse_excursion"] = 0.08
    velvet["post_event_return_24h"] = -0.11
    velvet["post_event_return_72h"] = -0.22
    velvet["post_event_return_7d"] = -0.31
    velvet["event_time_entry_price"] = 8.0
    velvet["event_time_max_favorable_excursion"] = 0.33
    velvet["event_time_max_adverse_excursion"] = 0.03
    velvet["event_time_post_event_return_24h"] = -0.10
    velvet["event_time_post_event_return_72h"] = -0.12
    velvet["event_time_post_event_return_7d"] = -0.25

    mark("TESTAI", "valid_proxy_fade")
    mark("TESTPRED", "false_positive")
    mark("TESTBTC", "direct_event")
    mark("TESTLIST", "direct_event", "direct_listing")
    mark("TESTPUMP", "ambiguous")

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=3,
        min_negative_controls=3,
        min_triggered_reviewed=1,
        min_trigger_precision=0.90,
        min_mfe_mae_ratio=2.0,
        min_proxy_event_types=2,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.promotion_ready is True
    assert review.reviewed_rows == 6
    assert review.missing_review_status_rows == 0
    assert review.missing_human_label_rows == 0
    assert review.reviewed_proxy_candidates == 3
    assert review.reviewed_negative_controls == 3
    assert review.label_counts["valid_proxy_fade"] == 2
    assert review.label_counts["false_positive"] == 1
    assert review.triggered_reviewed == 1
    assert review.triggered_valid == 1
    assert review.trigger_precision == 1.0
    assert review.trigger_false_positive_rate == 0.0
    assert review.avg_mfe == 0.42
    assert review.avg_mae == 0.08
    assert round(review.mfe_mae_ratio, 2) == 5.25
    assert review.avg_post_event_return_72h == -0.22
    assert review.avg_event_time_post_event_return_72h == -0.12
    assert round(review.avg_trigger_vs_event_time_return_72h_edge, 2) == 0.10
    assert round(review.avg_trigger_latency_hours, 2) == 22.5
    assert round(review.median_trigger_latency_hours, 2) == 22.5
    assert review.negative_trigger_latency_rows == 0
    assert review.reviewed_proxy_event_types == 2
    assert review.reviewed_proxy_source_providers == 3
    assert review.reviewed_proxy_source_origins == 1
    assert review.triggered_btc_risk_buckets == 1
    assert review.missing_event_time_baseline_rows == 0
    assert review.low_confidence_trigger_event_time_rows == 0
    assert review.point_in_time_violation_rows == 0
    assert review.post_decision_source_rows == 0
    assert review.missing_source_timing_rows == 0
    assert review.promotion_blockers == ()
    assert event_validation.validation_review_next_steps(review) == (
        "Mechanical review gates are satisfied; explicit human approval is still required before promotion.",
    )

    event_type_cohorts = {cohort.name: cohort for cohort in review.event_type_cohorts}
    assert event_type_cohorts["ipo_proxy"].reviewed_rows == 2
    assert event_type_cohorts["ipo_proxy"].triggered_reviewed == 1
    assert event_type_cohorts["ipo_proxy"].trigger_precision == 1.0
    assert event_type_cohorts["ipo_proxy"].avg_post_event_return_72h == -0.22
    assert event_type_cohorts["etf_approval"].reviewed_negative_controls == 1

    relationship_cohorts = {cohort.name: cohort for cohort in review.relationship_type_cohorts}
    assert relationship_cohorts["proxy_exposure"].reviewed_proxy_candidates == 3
    assert relationship_cohorts["direct_listing"].reviewed_negative_controls == 1
    assert relationship_cohorts["ambiguous"].reviewed_negative_controls == 1

    asset_role_cohorts = {cohort.name: cohort for cohort in review.asset_role_cohorts}
    assert asset_role_cohorts["proxy_instrument"].reviewed_proxy_candidates == 3
    assert asset_role_cohorts["direct_beneficiary"].reviewed_negative_controls == 2
    assert asset_role_cohorts["ambiguous"].reviewed_negative_controls == 1

    time_source_cohorts = {cohort.name: cohort for cohort in review.event_time_source_cohorts}
    assert time_source_cohorts["explicit"].reviewed_proxy_candidates == 3
    assert time_source_cohorts["missing_event_time"].reviewed_negative_controls == 1

    source_cohorts = {cohort.name: cohort for cohort in review.source_provider_cohorts}
    assert source_cohorts["manual_json"].reviewed_rows == 3
    assert source_cohorts["manual_json"].reviewed_proxy_candidates == 1
    assert source_cohorts["cryptopanic"].reviewed_proxy_candidates == 1
    assert source_cohorts["prediction_market_events"].reviewed_proxy_candidates == 1

    origin_cohorts = {cohort.name: cohort for cohort in review.source_origin_cohorts}
    assert origin_cohorts["example.test"].reviewed_proxy_candidates == 3
    assert origin_cohorts["example.test"].reviewed_negative_controls == 2
    assert origin_cohorts["binance.com"].reviewed_negative_controls == 1

    btc_cohorts = {cohort.name: cohort for cohort in review.btc_risk_cohorts}
    assert btc_cohorts["btc_risk_neutral"].triggered_reviewed == 1
    assert btc_cohorts["btc_risk_unknown"].reviewed_negative_controls == 2

    report = event_validation.format_validation_review(review)
    assert "READY FOR HUMAN DECISION" in report
    assert "precision: 100.0%" in report
    assert "72h=-22.0%" in report
    assert "event-time short baseline" in report
    assert "trigger edge vs baseline=+10.0pp" in report
    assert "proxy event types: 2/2" in report
    assert "proxy source providers: 3/2" in report
    assert "proxy source origins: 1" in report
    assert "trigger BTC risk buckets: 1/1" in report
    assert "reviewed rows missing source timing: 0" in report
    assert "trigger latency: avg=22.5h" in report
    assert "low-confidence trigger event times: 0" in report
    assert "rows with post-decision source evidence: 0" in report
    assert "labeled rows missing review_status=reviewed: 0" in report
    assert "reviewed rows missing human_label: 0" in report
    assert "NEXT SAMPLE WORK" in report
    assert "explicit human approval is still required" in report
    assert "COHORTS" in report
    assert "By event type:" in report
    assert "ipo_proxy" in report
    assert "By asset role:" in report
    assert "proxy_instrument" in report
    assert "By event time source:" in report
    assert "explicit" in report
    assert "By source provider:" in report
    assert "prediction_market_events" in report
    assert "By source origin:" in report
    assert "example.test" in report
    assert "By BTC risk bucket:" in report

    with tempfile.TemporaryDirectory() as tmp:
        jsonl_path = Path(tmp) / "reviewed.jsonl"
        csv_path = Path(tmp) / "reviewed.csv"
        event_discovery.write_validation_sample(rows, jsonl_path)
        event_discovery.write_validation_sample(rows, csv_path)
        loaded_jsonl = event_validation.load_validation_sample(jsonl_path)
        loaded_csv = event_validation.load_validation_sample(csv_path)
        assert event_validation.review_validation_sample(
            loaded_jsonl,
            min_proxy_candidates=3,
            min_negative_controls=3,
            min_triggered_reviewed=1,
            min_trigger_precision=0.90,
            min_mfe_mae_ratio=2.0,
            min_proxy_event_types=2,
            min_trigger_btc_risk_buckets=1,
        ).promotion_ready
        assert event_validation.review_validation_sample(
            loaded_csv,
            min_proxy_candidates=3,
            min_negative_controls=3,
            min_triggered_reviewed=1,
            min_trigger_precision=0.90,
            min_mfe_mae_ratio=2.0,
            min_proxy_event_types=2,
            min_trigger_btc_risk_buckets=1,
        ).promotion_ready


def test_event_fade_validation_review_blocks_single_source_proxy_sample():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    for symbol in {"TESTAI", "TESTPRED"}:
        row = next(row for row in rows if row["asset_symbol"] == symbol)
        row["human_label"] = "valid_proxy_fade" if symbol == "TESTAI" else "false_positive"
        row["review_status"] = "reviewed"
        _stamp_review_provenance(row)
        row["raw_providers"] = ("manual_json",)
        row["source"] = "manual_json"
        row["first_seen_time"] = "2026-06-12T00:00:00+00:00"
        row["published_at_min"] = "2026-06-12T00:00:00+00:00"
        row["published_at_max"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_min"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_max"] = "2026-06-12T00:00:00+00:00"
        row["raw_published_at"] = ["2026-06-12T00:00:00+00:00"]
        row["raw_fetched_at"] = ["2026-06-12T00:00:00+00:00"]

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=2,
        min_negative_controls=0,
        min_triggered_reviewed=0,
        min_proxy_event_types=1,
        min_proxy_source_providers=2,
        min_trigger_btc_risk_buckets=0,
    )
    assert review.promotion_ready is False
    assert review.reviewed_proxy_candidates == 2
    assert review.reviewed_proxy_source_providers == 1
    assert "reviewed proxy source providers 1/2" in review.promotion_blockers
    assert (
        "Add reviewed proxy examples from 1 more source provider(s) (current 1/2)."
        in event_validation.validation_review_next_steps(review)
    )
    report = event_validation.format_validation_review(review)
    assert "proxy source providers: 1/2" in report
    assert "By source provider:" in report
    assert "manual_json" in report


def test_event_fade_validation_reports_google_news_publisher_origins():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    for symbol, title in (
        ("TESTAI", "TESTAI offers OpenAI pre-IPO exposure - CoinDesk"),
        ("TESTPRED", "TESTPRED opens prediction-market exposure - thedefiant.io"),
    ):
        row = next(row for row in rows if row["asset_symbol"] == symbol)
        row["human_label"] = "valid_proxy_fade"
        row["review_status"] = "reviewed"
        _stamp_review_provenance(row)
        row["raw_providers"] = ["project_blog_rss"]
        row["source"] = "project_blog_rss"
        row["source_urls"] = ["https://news.google.com/rss/articles/example?oc=5"]
        row["raw_titles"] = [title]
        row["first_seen_time"] = "2026-06-12T00:00:00+00:00"
        row["published_at_min"] = "2026-06-12T00:00:00+00:00"
        row["published_at_max"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_min"] = "2026-06-12T00:00:00+00:00"
        row["fetched_at_max"] = "2026-06-12T00:00:00+00:00"
        row["raw_published_at"] = ["2026-06-12T00:00:00+00:00"]
        row["raw_fetched_at"] = ["2026-06-12T00:00:00+00:00"]

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=2,
        min_negative_controls=0,
        min_triggered_reviewed=0,
        min_proxy_event_types=1,
        min_proxy_source_providers=2,
        min_trigger_btc_risk_buckets=0,
    )
    assert review.reviewed_proxy_source_providers == 1
    assert review.reviewed_proxy_source_origins == 2
    assert "reviewed proxy source providers 1/2" in review.promotion_blockers

    origin_cohorts = {cohort.name: cohort for cohort in review.source_origin_cohorts}
    assert origin_cohorts["coindesk"].reviewed_proxy_candidates == 1
    assert origin_cohorts["thedefiant.io"].reviewed_proxy_candidates == 1

    report = event_validation.format_validation_review(review)
    assert "proxy source origins: 2" in report
    assert "By source origin:" in report
    assert "coindesk" in report
    assert "thedefiant.io" in report

    queue_rows = [
        dict(row)
        for row in rows
        if row["asset_symbol"] in {"TESTAI", "TESTPRED"}
    ]
    for row in queue_rows:
        row["human_label"] = ""
        row["review_status"] = ""

    queue = event_validation.build_labeling_queue(queue_rows, limit=10)
    origin_items = {
        item.asset_symbol: item.source_origins
        for item in queue.items
        if item.asset_symbol in {"TESTAI", "TESTPRED"}
    }
    assert origin_items["TESTAI"] == ("coindesk",)
    assert origin_items["TESTPRED"] == ("thedefiant.io",)
    queue_report = event_validation.format_labeling_queue(queue)
    assert "origins: coindesk" in queue_report
    assert "origins: thedefiant.io" in queue_report

    template_rows = event_validation.build_review_template_rows(queue_rows, limit=10)
    template_by_symbol = {row["asset_symbol"]: row for row in template_rows}
    assert template_by_symbol["TESTAI"]["source_origins"] == ["coindesk"]
    assert template_by_symbol["TESTPRED"]["source_origins"] == ["thedefiant.io"]


def test_event_fade_validation_review_blocks_narrow_event_or_btc_samples():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    for row in rows:
        if row["asset_symbol"] in {"TESTVELVET", "TESTAI"}:
            row["human_label"] = "valid_proxy_fade"
            row["review_status"] = "reviewed"
            _stamp_review_provenance(row)
        elif row["asset_symbol"] in {"TESTBTC", "TESTPUMP"}:
            row["human_label"] = "direct_event" if row["asset_symbol"] == "TESTBTC" else "ambiguous"
            row["review_status"] = "reviewed"
            _stamp_review_provenance(row)

    velvet = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    velvet["max_favorable_excursion"] = 0.42
    velvet["max_adverse_excursion"] = 0.08
    velvet["post_event_return_72h"] = -0.22
    velvet["event_time_post_event_return_72h"] = -0.12

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=2,
        min_negative_controls=2,
        min_triggered_reviewed=1,
        min_trigger_precision=0.90,
        min_mfe_mae_ratio=2.0,
        min_proxy_event_types=2,
        min_trigger_btc_risk_buckets=2,
    )
    assert review.promotion_ready is False
    assert review.reviewed_proxy_event_types == 1
    assert review.triggered_btc_risk_buckets == 1
    assert "reviewed proxy event types 1/2" in review.promotion_blockers
    assert "reviewed trigger BTC risk buckets 1/2" in review.promotion_blockers


def test_event_fade_validation_review_blocks_low_confidence_trigger_event_time():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    triggered = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    triggered["human_label"] = "valid_proxy_fade"
    triggered["review_status"] = "reviewed"
    _stamp_review_provenance(triggered)
    triggered["event_time_confidence"] = 0.60
    triggered["event_time_source"] = "text_date"
    triggered["max_favorable_excursion"] = 0.42
    triggered["max_adverse_excursion"] = 0.08
    triggered["post_event_return_72h"] = -0.22
    triggered["event_time_post_event_return_72h"] = -0.12

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=1,
        min_negative_controls=0,
        min_triggered_reviewed=1,
        min_trigger_precision=0.90,
        min_mfe_mae_ratio=1.5,
        min_trigger_event_time_confidence=0.80,
        min_proxy_event_types=1,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.promotion_ready is False
    assert review.low_confidence_trigger_event_time_rows == 1
    assert (
        "1 reviewed SHORT_TRIGGERED row(s) have event_time_confidence below 80.0%"
        in review.promotion_blockers
    )
    assert event_validation.validation_review_next_steps(review) == (
        "Confirm event times from explicit source evidence for 1 reviewed triggered row(s).",
    )
    report = event_validation.format_validation_review(review)
    assert "low-confidence trigger event times: 1" in report
    assert "By event time source:" in report
    assert "text_date" in report


def test_event_fade_validation_merge_preserves_review_fields():
    from crypto_rsi_scanner import event_discovery, event_validation

    fresh = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    source = next(row for row in reviewed if row["asset_symbol"] == "TESTVELVET")
    source["review_status"] = "reviewed"
    source["reviewed_by"] = "Codex"
    source["reviewed_at"] = "2026-06-17T10:15:00+00:00"
    source["human_label"] = "valid_proxy_fade"
    source["human_notes"] = "Reviewed SpaceX proxy event."
    source["max_favorable_excursion"] = 0.42
    source["max_adverse_excursion"] = 0.08
    source["post_event_return_24h"] = -0.11
    source["post_event_return_72h"] = -0.22
    source["post_event_return_7d"] = -0.31
    stale = dict(source)
    stale["event_id"] = "missing-event"
    reviewed.append(stale)

    result = event_validation.merge_review_fields(fresh, reviewed)
    assert result.fresh_rows == len(fresh)
    assert result.reviewed_rows == len(reviewed)
    assert result.matched_rows == 1
    assert result.evidence_changed_rows == 0
    assert result.unmatched_reviewed_rows == 1
    assert result.copied_fields == 10

    merged = next(row for row in result.rows if row["asset_symbol"] == "TESTVELVET")
    assert merged["reviewed_by"] == "Codex"
    assert merged["reviewed_at"] == "2026-06-17T10:15:00+00:00"
    assert merged["human_label"] == "valid_proxy_fade"
    assert merged["human_notes"] == "Reviewed SpaceX proxy event."
    assert merged["max_favorable_excursion"] == 0.42
    assert merged["post_event_return_72h"] == -0.22
    other = next(row for row in result.rows if row["asset_symbol"] == "TESTPUMP")
    assert other["human_label"] == ""


def test_event_fade_validation_merge_skips_changed_evidence():
    from crypto_rsi_scanner import event_discovery, event_validation

    fresh = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    fresh_row = next(row for row in fresh if row["asset_symbol"] == "TESTVELVET")
    source = next(row for row in reviewed if row["asset_symbol"] == "TESTVELVET")
    source["review_status"] = "reviewed"
    source["human_label"] = "valid_proxy_fade"
    source["human_notes"] = "Reviewed original source evidence."
    source["post_event_return_72h"] = -0.22
    fresh_row["raw_content_hashes"] = ["changed-source-hash"]

    result = event_validation.merge_review_fields(fresh, reviewed)
    assert result.matched_rows == 1
    assert result.evidence_changed_rows == 1
    assert result.copied_fields == 0
    assert len(result.evidence_changes) == 1
    assert result.evidence_changes[0].asset_symbol == "TESTVELVET"
    assert result.evidence_changes[0].changed_fields == ("raw_content_hashes",)
    evidence_report = event_validation.format_merge_evidence_changes(result)
    assert "TESTVELVET" in evidence_report
    assert "raw_content_hashes" in evidence_report

    merged = next(row for row in result.rows if row["asset_symbol"] == "TESTVELVET")
    assert merged["review_status"] == ""
    assert merged["human_label"] == ""
    assert merged["human_notes"] == ""
    assert merged["post_event_return_72h"] is None


def test_event_fade_validation_uses_human_event_time_for_review_metrics():
    from datetime import datetime, timedelta, timezone
    from crypto_rsi_scanner import event_validation

    event_time = datetime(2026, 6, 20, 0, 0, tzinfo=timezone.utc)
    trigger_time = event_time + timedelta(hours=6)
    row = {
        "schema_version": "event_fade_validation_sample_v1",
        "event_id": "hype-spacex-human-time",
        "asset_symbol": "HYPE",
        "asset_coin_id": "hyperliquid",
        "event_name": "Hyperliquid SpaceX pre-IPO market",
        "event_type": "ipo_proxy",
        "relationship_type": "proxy_exposure",
        "asset_role": "proxy_instrument",
        "signal_type": "SHORT_TRIGGERED",
        "event_time": "",
        "event_time_source": "",
        "event_time_confidence": None,
        "human_event_time": event_time.isoformat(),
        "human_event_time_source": "https://example.test/hype-spacex",
        "human_event_time_confidence": 0.95,
        "is_proxy_narrative": True,
        "is_direct_beneficiary": False,
        "trigger_observed_at": trigger_time.isoformat(),
        "review_status": "reviewed",
        "reviewed_by": "human",
        "reviewed_at": "2026-06-17T12:00:00+00:00",
        "human_label": "valid_proxy_fade",
        "source": "project_blog_rss",
        "raw_providers": ["project_blog_rss"],
        "source_urls": ["https://example.test/hype-spacex"],
        "first_seen_time": (event_time - timedelta(hours=3)).isoformat(),
        "published_at_min": (event_time - timedelta(hours=3)).isoformat(),
        "published_at_max": (event_time - timedelta(hours=3)).isoformat(),
        "fetched_at_min": (event_time - timedelta(hours=2)).isoformat(),
        "fetched_at_max": (event_time - timedelta(hours=2)).isoformat(),
        "raw_published_at": [(event_time - timedelta(hours=3)).isoformat()],
        "raw_fetched_at": [(event_time - timedelta(hours=2)).isoformat()],
        "btc_risk_on_score": 35,
    }
    candles = [
        event_validation.ValidationOutcomeCandle(event_time, close=10.0, high=10.0, low=10.0, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(trigger_time, close=9.0, high=9.0, low=9.0, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(event_time + timedelta(hours=24), close=8.0, high=9.2, low=7.5, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(trigger_time + timedelta(hours=24), close=7.0, high=7.5, low=6.5, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(event_time + timedelta(hours=72), close=7.0, high=7.2, low=6.8, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(trigger_time + timedelta(hours=72), close=5.5, high=6.0, low=5.0, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(event_time + timedelta(hours=168), close=6.0, high=6.2, low=5.8, interval="1h", source="fixture"),
        event_validation.ValidationOutcomeCandle(trigger_time + timedelta(hours=168), close=4.5, high=5.0, low=4.0, interval="1h", source="fixture"),
    ]

    filled = event_validation.fill_validation_outcomes([row], {"hyperliquid": candles})
    assert filled.filled_rows == 1
    filled_row = filled.rows[0]
    assert filled_row["event_time"] == ""
    assert filled_row["human_event_time"] == event_time.isoformat()
    assert round(filled_row["event_time_entry_price"], 4) == 10.0
    assert round(filled_row["event_time_post_event_return_72h"], 4) == -0.3
    assert round(filled_row["post_event_return_72h"], 4) == -0.3889

    review = event_validation.review_validation_sample(
        filled.rows,
        min_proxy_candidates=1,
        min_negative_controls=0,
        min_triggered_reviewed=1,
        min_proxy_event_types=1,
        min_proxy_source_providers=1,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.low_confidence_trigger_event_time_rows == 0
    assert review.point_in_time_violation_rows == 0
    assert review.post_decision_source_rows == 0
    assert review.missing_source_timing_rows == 0
    assert review.missing_event_time_baseline_rows == 0
    assert review.avg_trigger_latency_hours == 6.0
    assert review.promotion_ready is True
    time_source_cohorts = {cohort.name: cohort for cohort in review.event_time_source_cohorts}
    assert time_source_cohorts["human_confirmed"].reviewed_proxy_candidates == 1
    report = event_validation.format_validation_review(review)
    assert "human_confirmed" in report


def test_event_fade_validation_labeling_queue_flags_low_confidence_trigger_time():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    prices = event_validation.load_outcome_price_fixture(_outcome_prices_fixture_path())
    filled = event_validation.fill_validation_outcomes(rows, prices)
    triggered = next(row for row in filled.rows if row["asset_symbol"] == "TESTVELVET")
    triggered["human_label"] = "valid_proxy_fade"
    triggered["review_status"] = "reviewed"
    _stamp_review_provenance(triggered)
    triggered["event_time_source"] = "text_date"
    triggered["event_time_confidence"] = 0.60

    queue = event_validation.build_labeling_queue(filled.rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTVELVET")
    assert item.category == "confirm_trigger_event_time"
    assert item.suggested_label == "valid_proxy_fade"
    assert item.missing_fields == ("event_time_source", "event_time_confidence")
    assert item.event_time_source == "text_date"
    assert item.event_time_confidence == 0.60

    report = event_validation.format_labeling_queue(queue)
    assert "confirm_trigger_event_time" in report
    assert "source: text_date" in report
    assert "confidence: 60.0%" in report

    template_rows = event_validation.build_review_template_rows(filled.rows, limit=1)
    assert template_rows[0]["asset_symbol"] == "TESTVELVET"
    assert template_rows[0]["queue_category"] == "confirm_trigger_event_time"


def test_event_fade_validation_labeling_queue_prefers_explicit_event_times():
    from crypto_rsi_scanner import event_validation

    rows = [
        {
            "event_id": "event-text-date",
            "asset_symbol": "TEXTDATE",
            "asset_coin_id": "textdate",
            "event_name": "Text Date Proxy",
            "relationship_type": "proxy_exposure",
            "signal_type": "NO_TRADE",
            "event_time": "2026-06-10T00:00:00+00:00",
            "event_time_source": "text_date",
            "event_time_confidence": 0.60,
            "is_proxy_narrative": True,
            "is_direct_beneficiary": False,
        },
        {
            "event_id": "event-missing-time",
            "asset_symbol": "MISSINGTIME",
            "asset_coin_id": "missingtime",
            "event_name": "Missing Time Proxy",
            "relationship_type": "proxy_exposure",
            "signal_type": "NO_TRADE",
            "event_time": "",
            "event_time_source": "",
            "event_time_confidence": None,
            "is_proxy_narrative": True,
            "is_direct_beneficiary": False,
        },
        {
            "event_id": "event-explicit",
            "asset_symbol": "EXPLICIT",
            "asset_coin_id": "explicit",
            "event_name": "Explicit Proxy",
            "relationship_type": "proxy_exposure",
            "signal_type": "NO_TRADE",
            "event_time": "2026-06-20T00:00:00+00:00",
            "event_time_source": "explicit",
            "event_time_confidence": 1.0,
            "is_proxy_narrative": True,
            "is_direct_beneficiary": False,
        },
    ]

    queue = event_validation.build_labeling_queue(rows)
    assert [item.asset_symbol for item in queue.items] == [
        "TEXTDATE",
        "MISSINGTIME",
        "EXPLICIT",
    ]
    assert [item.category for item in queue.items] == [
        "confirm_proxy_event_time",
        "confirm_proxy_event_time",
        "label_proxy_candidate",
    ]
    assert queue.items[0].missing_fields == (
        "human_label",
        "human_event_time_source",
        "human_event_time_confidence",
    )
    assert queue.items[1].missing_fields == (
        "human_label",
        "human_event_time",
        "human_event_time_source",
        "human_event_time_confidence",
    )


def test_event_fade_validation_review_template_roundtrips_human_event_time():
    from crypto_rsi_scanner import event_validation

    rows = [{
        "event_id": "event-missing-time",
        "asset_symbol": "HYPE",
        "asset_coin_id": "hyperliquid",
        "external_asset": "SpaceX",
        "event_name": "Hyperliquid SpaceX pre-IPO market",
        "relationship_type": "proxy_exposure",
        "signal_type": "NO_TRADE",
        "event_time": "",
        "event_time_source": "",
        "event_time_confidence": None,
        "is_proxy_narrative": True,
        "is_direct_beneficiary": False,
        "first_seen_time": "2026-06-17T10:00:00+00:00",
        "raw_published_at": ["2026-06-17T09:00:00+00:00"],
        "raw_fetched_at": ["2026-06-17T10:00:00+00:00"],
        "source_urls": ["https://example.test/hype-spacex"],
        "raw_titles": ["Hyperliquid launches SpaceX pre-IPO market"],
    }]

    template_rows = event_validation.build_review_template_rows(rows, limit=1)
    assert template_rows[0]["queue_category"] == "confirm_proxy_event_time"
    assert template_rows[0]["external_asset"] == "SpaceX"
    assert template_rows[0]["human_event_time"] is None
    assert template_rows[0]["primary_source_url"] == "https://example.test/hype-spacex"
    assert template_rows[0]["primary_raw_title"] == "Hyperliquid launches SpaceX pre-IPO market"
    assert "Hyperliquid+launches+SpaceX" in template_rows[0]["source_search_url"]
    assert "fill human_event_time" in template_rows[0]["review_prompt"]
    assert "No machine event time" in template_rows[0]["event_time_review_hint"]
    assert template_rows[0]["missing_fields"] == [
        "human_label",
        "human_event_time",
        "human_event_time_source",
        "human_event_time_confidence",
    ]

    template_rows[0]["review_status"] = "reviewed"
    template_rows[0]["reviewed_by"] = "human"
    template_rows[0]["reviewed_at"] = "2026-06-17T11:00:00+00:00"
    template_rows[0]["human_label"] = "valid_proxy_fade"
    template_rows[0]["human_event_time"] = "2026-06-20T13:30:00+00:00"
    template_rows[0]["human_event_time_source"] = "https://example.test/hype-spacex"
    template_rows[0]["human_event_time_confidence"] = 0.95
    template_rows[0]["human_event_time_notes"] = "Source states the market opens at 13:30 UTC."
    result = event_validation.apply_review_template(rows, template_rows)
    assert result.matched_rows == 1
    assert result.evidence_changed_rows == 0
    assert result.copied_fields == 8
    out = result.rows[0]
    assert out["event_time"] == ""
    assert out["reviewed_by"] == "human"
    assert out["reviewed_at"] == "2026-06-17T11:00:00+00:00"
    assert out["human_event_time"] == "2026-06-20T13:30:00+00:00"
    assert out["human_event_time_source"] == "https://example.test/hype-spacex"
    assert out["human_event_time_confidence"] == 0.95
    assert out["human_event_time_notes"] == "Source states the market opens at 13:30 UTC."


def test_event_fade_validation_review_template_check_requires_valid_proxy_event_time():
    from crypto_rsi_scanner import event_validation

    rows = [{
        "event_id": "event-missing-time",
        "asset_symbol": "HYPE",
        "asset_coin_id": "hyperliquid",
        "event_name": "Hyperliquid SpaceX pre-IPO market",
        "relationship_type": "proxy_exposure",
        "signal_type": "NO_TRADE",
        "event_time": "",
        "event_time_source": "",
        "event_time_confidence": None,
        "is_proxy_narrative": True,
        "is_direct_beneficiary": False,
        "first_seen_time": "2026-06-17T10:00:00+00:00",
        "raw_published_at": ["2026-06-17T09:00:00+00:00"],
        "raw_fetched_at": ["2026-06-17T10:00:00+00:00"],
        "source_urls": ["https://example.test/hype-spacex"],
        "raw_titles": ["Hyperliquid launches SpaceX pre-IPO market"],
    }]

    template_rows = event_validation.build_review_template_rows(rows, limit=1)
    template_rows[0]["review_status"] = "reviewed"
    template_rows[0]["reviewed_by"] = "human"
    template_rows[0]["reviewed_at"] = "2026-06-17T11:00:00+00:00"
    template_rows[0]["human_label"] = "valid_proxy_fade"

    check = event_validation.check_review_template(rows, template_rows)
    assert not check.ready_to_apply
    assert check.edited_rows == 1
    assert check.issues[0].category == "confirm_valid_proxy_event_time"
    assert check.issues[0].missing_fields == (
        "human_event_time",
        "human_event_time_source",
        "human_event_time_confidence",
    )
    formatted = event_validation.format_review_template_check(check)
    assert "Status: not ready to apply." in formatted
    assert "confirm_valid_proxy_event_time" in formatted

    template_rows[0]["human_event_time"] = "2026-06-20T13:30:00+00:00"
    template_rows[0]["human_event_time_source"] = "https://example.test/hype-spacex"
    template_rows[0]["human_event_time_confidence"] = 0.95
    check = event_validation.check_review_template(rows, template_rows)
    assert check.ready_to_apply
    assert check.issue_rows == 0
    assert "Status: ready to apply." in event_validation.format_review_template_check(check)


def test_event_fade_validation_review_template_surfaces_source_date_hints():
    from crypto_rsi_scanner import event_validation

    rows = [{
        "event_id": "event-world-cup-tonight",
        "asset_symbol": "USAT",
        "asset_coin_id": "usa-fan-token",
        "event_name": "USA vs Paraguay kicks off World Cup 2026 tonight",
        "relationship_type": "proxy_attention",
        "asset_role": "proxy_instrument",
        "event_type": "sports_event",
        "signal_type": "NO_TRADE",
        "event_time": "",
        "event_time_source": "",
        "event_time_confidence": None,
        "is_proxy_narrative": True,
        "is_direct_beneficiary": False,
        "source_urls": ["https://example.test/usat-world-cup-tonight"],
        "raw_titles": ["USA vs Paraguay kicks off World Cup 2026 tonight, and crypto is already on the pitch"],
    }]

    template_rows = event_validation.build_review_template_rows(rows, limit=1)
    assert template_rows[0]["queue_category"] == "confirm_proxy_event_time"
    assert template_rows[0]["source_date_hint"] == "World Cup 2026; tonight"

    csv_text = event_validation.format_review_template_csv(template_rows)
    assert "source_date_hint" in csv_text.splitlines()[0]
    assert "World Cup 2026; tonight" in csv_text

    packet = event_validation.format_review_packet(rows, limit=1)
    assert "Source date hint: World Cup 2026; tonight" in packet


def test_event_fade_validation_review_packet_formats_human_evidence():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    prices = event_validation.load_outcome_price_fixture(_outcome_prices_fixture_path())
    filled = event_validation.fill_validation_outcomes(rows, prices)
    packet = event_validation.format_review_packet(filled.rows, limit=1)

    assert "# Event-Fade Validation Review Packet" in packet
    assert "Rows: 17 | needing labels/status/outcomes: 17 | showing: 1" in packet
    assert "## 1. TESTVELVET - SpaceX IPO trading start" in packet
    assert "- Queue category: `label_triggered_candidate`" in packet
    assert "- Suggested label: `valid_proxy_fade or false_positive`" in packet
    assert "- Missing fields: `human_label`" in packet
    assert "time_source=`explicit` | time_confidence=`1.00`" in packet
    assert "trigger 72h=`-20.8%`" in packet
    assert "Event-time baseline: entry=`8.00` | 72h=`-20.0%` | trigger edge=`+0.8pp`" in packet
    assert "Classifier evidence:" in packet
    assert "Sources:" in packet
    assert "Source providers:" in packet
    assert "manual_json" in packet
    assert "Source origins:" in packet
    assert "example.test" in packet
    assert "Source search:" in packet
    assert "TestVelvet+offers+synthetic+exposure" in packet
    assert "human_label" in packet


def test_event_fade_validation_review_template_roundtrips_sidecar_labels():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    template_rows = event_validation.build_review_template_rows(rows, limit=2)
    assert len(template_rows) == 2
    assert template_rows[0]["asset_symbol"] == "TESTVELVET"
    assert template_rows[0]["queue_category"] == "label_triggered_candidate"
    assert template_rows[0]["event_time_confidence"] == 1.0
    assert template_rows[0]["event_time_source"] == "explicit"
    assert template_rows[0]["external_asset"] == "SpaceX"
    assert template_rows[0]["human_event_time"] is None
    assert template_rows[0]["suggested_label"] == "valid_proxy_fade or false_positive"
    assert template_rows[0]["source_origins"] == ["example.test"]
    assert template_rows[0]["source_providers"] == ["manual_json"]
    assert template_rows[0]["primary_source_url"] == "https://example.test/velvet-spacex-duplicate"
    assert template_rows[0]["primary_source_origin"] == "example.test"
    assert (
        template_rows[0]["primary_raw_title"]
        == "TestVelvet offers synthetic exposure to SpaceX pre-IPO trading before launch"
    )
    assert "TestVelvet+offers+synthetic+exposure" in template_rows[0]["source_search_url"]
    assert "Verify source evidence" in template_rows[0]["review_prompt"]
    assert "explicit/high confidence" in template_rows[0]["event_time_review_hint"]
    assert template_rows[0]["missing_fields"] == [
        "human_label",
        "max_adverse_excursion",
        "max_favorable_excursion",
        "post_event_return_72h",
        "event_time_post_event_return_72h",
    ]

    template_rows[0]["review_status"] = "reviewed"
    template_rows[0]["reviewed_by"] = "human"
    template_rows[0]["reviewed_at"] = "2026-06-17T11:00:00+00:00"
    template_rows[0]["human_label"] = "valid_proxy_fade"
    template_rows[0]["human_notes"] = "Reviewed source evidence."
    template_rows[0]["primary_source_url"] = "https://example.test/helper-column-change"
    template_rows[0]["review_prompt"] = "Helper-only reviewer note changed."
    template_rows[0]["source_search_url"] = "https://example.test/helper-search-change"
    template_rows[0]["source_providers"] = ["helper_provider"]
    template_rows[0]["post_event_return_72h"] = -0.21
    result = event_validation.apply_review_template(rows, template_rows)
    assert result.matched_rows == 1
    assert result.evidence_changed_rows == 0
    assert result.copied_fields == 6
    velvet = next(row for row in result.rows if row["asset_symbol"] == "TESTVELVET")
    assert velvet["review_status"] == "reviewed"
    assert velvet["reviewed_by"] == "human"
    assert velvet["reviewed_at"] == "2026-06-17T11:00:00+00:00"
    assert velvet["human_label"] == "valid_proxy_fade"
    assert velvet["human_notes"] == "Reviewed source evidence."
    assert velvet["post_event_return_72h"] == -0.21

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "review_template.csv"
        jsonl_path = Path(tmp) / "review_template.jsonl"
        event_validation.write_review_template(rows, csv_path, limit=1)
        event_validation.write_review_template(rows, jsonl_path, limit=1)
        csv_rows = event_validation.load_validation_sample(csv_path)
        jsonl_rows = event_validation.load_validation_sample(jsonl_path)
        assert csv_rows[0]["asset_symbol"] == "TESTVELVET"
        assert csv_rows[0]["external_asset"] == "SpaceX"
        assert csv_rows[0]["primary_source_url"] == "https://example.test/velvet-spacex-duplicate"
        assert "Verify source evidence" in csv_rows[0]["review_prompt"]
        assert "TestVelvet+offers+synthetic+exposure" in csv_rows[0]["source_search_url"]
        assert "source_date_hint" in csv_rows[0]
        assert csv_rows[0]["source_providers"] == ["manual_json"]
        assert csv_rows[0]["missing_fields"][0] == "human_label"
        assert jsonl_rows[0]["asset_symbol"] == "TESTVELVET"


def test_event_fade_validation_balanced_review_template_samples_gates():
    from collections import Counter
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    template_rows = event_validation.build_balanced_review_template_rows(
        rows,
        proxy_limit=2,
        control_limit=3,
    )
    slices = Counter(row["review_slice"] for row in template_rows)
    assert slices["triggered"] == 1
    assert slices["proxy_candidate"] == 2
    assert slices["negative_control"] == 3
    assert any(row["asset_symbol"] == "TESTVELVET" for row in template_rows)
    assert any(row["suggested_label"] == "direct_event" for row in template_rows)
    assert all("primary_source_url" in row for row in template_rows)
    assert all("external_asset" in row for row in template_rows)
    assert all("source_providers" in row for row in template_rows)
    assert all(row.get("source_search_url") for row in template_rows)

    csv_text = event_validation.format_review_template_csv(template_rows)
    assert "review_slice" in csv_text.splitlines()[0]
    assert "negative_control" in csv_text

    packet = event_validation.format_balanced_review_packet(
        rows,
        proxy_limit=2,
        control_limit=3,
    )
    assert "# Event-Fade Balanced Review Packet" in packet
    assert "Rows shown: 6 | proxy_limit=2 | control_limit=3 | triggered_limit=all" in packet
    assert "Slices: negative_control=3, proxy_candidate=2, triggered=1" in packet
    assert "- Review slice: `triggered`" in packet
    assert "- Review slice: `proxy_candidate`" in packet
    assert "- Review slice: `negative_control`" in packet
    assert "external=`SpaceX`" in packet
    assert "Source providers:" in packet
    assert "Source search:" in packet


def test_event_fade_validation_balanced_review_template_diversifies_controls():
    from crypto_rsi_scanner import event_validation

    def control_row(symbol: str, idx: int, *, origin: str = "example.test") -> dict:
        return {
            "event_id": f"control-{symbol.lower()}-{idx}",
            "asset_coin_id": symbol.lower(),
            "asset_symbol": symbol,
            "event_name": f"{symbol} market context story {idx}",
            "event_type": "other",
            "relationship_type": "ambiguous",
            "asset_role": "ambiguous",
            "is_proxy_narrative": False,
            "is_direct_beneficiary": False,
            "signal_type": "NO_TRADE",
            "source_urls": [f"https://{origin}/{symbol.lower()}-{idx}"],
            "raw_titles": [f"{symbol} market context story {idx}"],
        }

    rows = [
        *(control_row("BTC", idx) for idx in range(1, 6)),
        control_row("ETH", 1),
        control_row("SOL", 1),
    ]

    priority_rows = event_validation.build_review_template_rows(rows, limit=3)
    assert [row["asset_symbol"] for row in priority_rows] == ["BTC", "BTC", "BTC"]

    balanced_rows = event_validation.build_balanced_review_template_rows(
        rows,
        proxy_limit=0,
        control_limit=3,
        triggered_limit=0,
    )
    assert [row["review_slice"] for row in balanced_rows] == ["negative_control"] * 3
    assert {row["asset_symbol"] for row in balanced_rows} == {"BTC", "ETH", "SOL"}


def test_event_fade_validation_balanced_review_template_prefers_proxy_instruments():
    from crypto_rsi_scanner import event_validation

    def proxy_row(symbol: str, role: str, idx: int) -> dict:
        return {
            "event_id": f"proxy-{symbol.lower()}-{idx}",
            "asset_coin_id": symbol.lower(),
            "asset_symbol": symbol,
            "event_name": f"{symbol} external proxy story {idx}",
            "event_type": "ipo_proxy",
            "relationship_type": "proxy_attention",
            "asset_role": role,
            "is_proxy_narrative": True,
            "is_direct_beneficiary": False,
            "signal_type": "NO_TRADE",
            "source_urls": [f"https://example.test/{symbol.lower()}-{idx}"],
            "raw_titles": [f"{symbol} external proxy story {idx}"],
        }

    rows = [
        proxy_row("VENUE1", "proxy_venue", 1),
        proxy_row("VENUE2", "proxy_venue", 2),
        proxy_row("INST1", "proxy_instrument", 1),
        proxy_row("VENUE3", "proxy_venue", 3),
        proxy_row("INST2", "proxy_instrument", 2),
    ]

    instruments_only = event_validation.build_balanced_review_template_rows(
        rows,
        proxy_limit=2,
        control_limit=0,
        triggered_limit=0,
    )
    assert [row["review_slice"] for row in instruments_only] == ["proxy_candidate"] * 2
    assert {row["asset_role"] for row in instruments_only} == {"proxy_instrument"}
    assert {row["asset_symbol"] for row in instruments_only} == {"INST1", "INST2"}

    with_fill = event_validation.build_balanced_review_template_rows(
        rows,
        proxy_limit=4,
        control_limit=0,
        triggered_limit=0,
    )
    assert [row["asset_role"] for row in with_fill[:2]] == ["proxy_instrument", "proxy_instrument"]
    assert sum(row["asset_role"] == "proxy_venue" for row in with_fill) == 2


def test_event_fade_validation_review_template_skips_changed_sidecar_evidence():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    template_rows = event_validation.build_review_template_rows(rows, limit=1)
    template_rows[0]["review_status"] = "reviewed"
    template_rows[0]["human_label"] = "valid_proxy_fade"
    template_rows[0]["human_notes"] = "Reviewed compact source evidence."
    sample_row = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    sample_row["source_urls"] = ["https://example.test/changed-source"]

    result = event_validation.apply_review_template(rows, template_rows)
    assert result.matched_rows == 1
    assert result.evidence_changed_rows == 1
    assert result.copied_fields == 0
    assert result.evidence_changes[0].changed_fields == ("source_urls",)
    velvet = next(row for row in result.rows if row["asset_symbol"] == "TESTVELVET")
    assert velvet["review_status"] == ""
    assert velvet["human_label"] == ""

    check = event_validation.check_review_template(rows, template_rows)
    assert not check.ready_to_apply
    assert check.issues[0].category == "evidence_changed"
    assert check.issues[0].changed_fields == ("source_urls",)
    assert "Evidence fields changed" in event_validation.format_review_template_check(check)


def test_event_fade_validation_review_blocks_late_or_weak_trigger_evidence():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    triggered = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    triggered["human_label"] = "false_positive"
    triggered["review_status"] = "reviewed"
    _stamp_review_provenance(triggered)
    triggered["first_seen_time"] = "2026-06-14T00:00:00+00:00"
    triggered["fetched_at_min"] = "2026-06-14T00:00:00+00:00"
    triggered["published_at_min"] = "2026-06-14T00:00:00+00:00"
    triggered["fetched_at_max"] = "2026-06-14T00:00:00+00:00"
    triggered["published_at_max"] = "2026-06-14T00:00:00+00:00"
    triggered["trigger_observed_at"] = "2026-06-13T12:00:00+00:00"
    triggered["max_favorable_excursion"] = 0.03
    triggered["max_adverse_excursion"] = 0.08
    triggered["post_event_return_72h"] = 0.04

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=1,
        min_negative_controls=0,
        min_triggered_reviewed=1,
        min_trigger_precision=0.60,
        min_mfe_mae_ratio=1.5,
        min_proxy_event_types=1,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.promotion_ready is False
    assert review.trigger_precision == 0.0
    assert review.point_in_time_violation_rows == 1
    assert review.post_decision_source_rows == 1
    assert any("trigger precision 0.0% below 60.0%" == blocker for blocker in review.promotion_blockers)
    assert any("evidence first seen after the decision time" in blocker for blocker in review.promotion_blockers)
    assert any("source evidence after the decision time" in blocker for blocker in review.promotion_blockers)
    assert review.negative_trigger_latency_rows == 1
    assert any("trigger before event time" in blocker for blocker in review.promotion_blockers)
    assert any("MFE/MAE 0.38 below 1.50" == blocker for blocker in review.promotion_blockers)
    assert "reviewed SHORT_TRIGGERED rows do not show favorable 72h short returns" in review.promotion_blockers


def test_event_fade_validation_review_flags_mixed_late_source_evidence():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    triggered = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    triggered["human_label"] = "valid_proxy_fade"
    triggered["review_status"] = "reviewed"
    _stamp_review_provenance(triggered)
    triggered["max_favorable_excursion"] = 0.42
    triggered["max_adverse_excursion"] = 0.08
    triggered["post_event_return_72h"] = -0.22
    triggered["event_time_post_event_return_72h"] = -0.12
    triggered["fetched_at_min"] = "2026-06-15T12:00:00+00:00"
    triggered["fetched_at_max"] = "2026-06-17T12:00:00+00:00"
    triggered["raw_fetched_at"] = [
        "2026-06-15T12:00:00+00:00",
        "2026-06-17T12:00:00+00:00",
    ]

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=1,
        min_negative_controls=0,
        min_triggered_reviewed=1,
        min_trigger_precision=0.90,
        min_mfe_mae_ratio=2.0,
        min_proxy_event_types=1,
        min_trigger_btc_risk_buckets=1,
    )
    assert review.point_in_time_violation_rows == 0
    assert review.post_decision_source_rows == 1
    assert "1 reviewed row(s) include source evidence after the decision time" in review.promotion_blockers
    assert (
        "Review or remove 1 row(s) with post-decision source evidence."
        in event_validation.validation_review_next_steps(review)
    )

    queue = event_validation.build_labeling_queue(rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTVELVET")
    assert item.category == "review_post_decision_source"


def test_event_fade_validation_review_flags_late_control_evidence():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    direct = next(
        row
        for row in rows
        if row["asset_symbol"] == "TESTBTC" and row["relationship_type"] == "direct_token_event"
    )
    direct["human_label"] = "direct_event"
    direct["review_status"] = "reviewed"
    _stamp_review_provenance(direct)
    direct["event_time"] = "2026-06-15T13:30:00+00:00"
    direct["first_seen_time"] = "2026-06-15T14:00:00+00:00"
    direct["published_at_min"] = "2026-06-15T14:00:00+00:00"
    direct["published_at_max"] = "2026-06-15T14:00:00+00:00"
    direct["fetched_at_min"] = "2026-06-15T14:00:00+00:00"
    direct["fetched_at_max"] = "2026-06-15T14:00:00+00:00"
    direct["raw_published_at"] = ["2026-06-15T14:00:00+00:00"]
    direct["raw_fetched_at"] = ["2026-06-15T14:00:00+00:00"]

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=0,
        min_negative_controls=1,
        min_triggered_reviewed=0,
    )
    assert review.reviewed_negative_controls == 1
    assert review.point_in_time_violation_rows == 1
    assert review.post_decision_source_rows == 1
    assert any("evidence first seen after the decision time" in blocker for blocker in review.promotion_blockers)
    assert any("source evidence after the decision time" in blocker for blocker in review.promotion_blockers)

    queue = event_validation.build_labeling_queue(rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTBTC")
    assert item.category == "fix_point_in_time_evidence"


def test_event_fade_validation_review_blocks_missing_source_timing():
    from crypto_rsi_scanner import event_discovery, event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    direct = next(
        row
        for row in rows
        if row["asset_symbol"] == "TESTBTC" and row["relationship_type"] == "direct_token_event"
    )
    direct["human_label"] = "direct_event"
    direct["review_status"] = "reviewed"
    _stamp_review_provenance(direct)
    direct["first_seen_time"] = ""
    direct["published_at_min"] = ""
    direct["published_at_max"] = ""
    direct["fetched_at_min"] = ""
    direct["fetched_at_max"] = ""
    direct["raw_published_at"] = []
    direct["raw_fetched_at"] = []

    review = event_validation.review_validation_sample(
        rows,
        min_proxy_candidates=0,
        min_negative_controls=1,
        min_triggered_reviewed=0,
    )
    assert review.reviewed_negative_controls == 1
    assert review.missing_source_timing_rows == 1
    assert "1 reviewed row(s) are missing source timing evidence" in review.promotion_blockers
    assert (
        "Add source timing evidence or remove 1 reviewed row(s)."
        in event_validation.validation_review_next_steps(review)
    )

    queue = event_validation.build_labeling_queue(rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTBTC")
    assert item.category == "add_source_timing"
    assert "first_seen_time" in item.missing_fields


def test_event_alert_scanner_report_uses_local_fixtures_without_sending():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    events_path, aliases_path = _event_discovery_fixture_paths()
    original = {
        "EVENT_DISCOVERY_EVENTS_PATH": config.EVENT_DISCOVERY_EVENTS_PATH,
        "EVENT_DISCOVERY_ALIASES_PATH": config.EVENT_DISCOVERY_ALIASES_PATH,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH": config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": config.EVENT_DISCOVERY_COINMARKETCAL_PATH,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": config.EVENT_DISCOVERY_TOKENOMIST_PATH,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        "EVENT_DISCOVERY_GDELT_PATH": config.EVENT_DISCOVERY_GDELT_PATH,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH": config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH,
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH": config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH": config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH,
        "EVENT_DISCOVERY_UNIVERSE_PATH": config.EVENT_DISCOVERY_UNIVERSE_PATH,
        "EVENT_DISCOVERY_LOOKBACK_HOURS": config.EVENT_DISCOVERY_LOOKBACK_HOURS,
        "EVENT_DISCOVERY_HORIZON_DAYS": config.EVENT_DISCOVERY_HORIZON_DAYS,
        "EVENT_ALERTS_ENABLED": config.EVENT_ALERTS_ENABLED,
    }
    config.EVENT_DISCOVERY_EVENTS_PATH = events_path
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    config.EVENT_DISCOVERY_LOOKBACK_HOURS = 120
    config.EVENT_DISCOVERY_HORIZON_DAYS = 2
    config.EVENT_ALERTS_ENABLED = False
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_alert_report(send=False, event_now="2026-06-15T16:00:00Z")
        text = out.getvalue()
        assert "EVENT RESEARCH ALERT REPORT" in text
        assert "research-only; not trade signals" in text
        assert "TESTVELVET/testvelvet" in text
        assert "TRIGGERED_FADE" in text
        assert "what user should verify:" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_event_alert_scanner_report_with_llm_advisory_uses_runtime_config():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    path = _llm_golden_fixture_path()
    original = {
        "EVENT_DISCOVERY_EVENTS_PATH": config.EVENT_DISCOVERY_EVENTS_PATH,
        "EVENT_DISCOVERY_ALIASES_PATH": config.EVENT_DISCOVERY_ALIASES_PATH,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH": config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": config.EVENT_DISCOVERY_COINMARKETCAL_PATH,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": config.EVENT_DISCOVERY_TOKENOMIST_PATH,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": config.EVENT_DISCOVERY_CRYPTOPANIC_PATH,
        "EVENT_DISCOVERY_GDELT_PATH": config.EVENT_DISCOVERY_GDELT_PATH,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH,
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH": config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH,
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH": config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH,
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH": config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH,
        "EVENT_DISCOVERY_UNIVERSE_PATH": config.EVENT_DISCOVERY_UNIVERSE_PATH,
        "EVENT_DISCOVERY_LOOKBACK_HOURS": config.EVENT_DISCOVERY_LOOKBACK_HOURS,
        "EVENT_DISCOVERY_HORIZON_DAYS": config.EVENT_DISCOVERY_HORIZON_DAYS,
        "EVENT_ALERTS_ENABLED": config.EVENT_ALERTS_ENABLED,
        "EVENT_LLM_ENABLED": config.EVENT_LLM_ENABLED,
        "EVENT_LLM_MODE": config.EVENT_LLM_MODE,
        "EVENT_LLM_PROVIDER": config.EVENT_LLM_PROVIDER,
        "EVENT_LLM_MODEL": config.EVENT_LLM_MODEL,
        "EVENT_LLM_OPENAI_TIMEOUT": config.EVENT_LLM_OPENAI_TIMEOUT,
        "EVENT_LLM_MAX_CANDIDATES_PER_RUN": config.EVENT_LLM_MAX_CANDIDATES_PER_RUN,
        "EVENT_LLM_MIN_PREFILTER_SCORE": config.EVENT_LLM_MIN_PREFILTER_SCORE,
        "EVENT_LLM_REQUIRE_EVIDENCE_QUOTES": config.EVENT_LLM_REQUIRE_EVIDENCE_QUOTES,
        "EVENT_LLM_MAX_CALLS_PER_RUN": config.EVENT_LLM_MAX_CALLS_PER_RUN,
        "EVENT_LLM_MAX_CALLS_PER_DAY": config.EVENT_LLM_MAX_CALLS_PER_DAY,
        "EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY": config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY,
        "EVENT_LLM_ESTIMATED_COST_PER_CALL_USD": config.EVENT_LLM_ESTIMATED_COST_PER_CALL_USD,
        "EVENT_LLM_MAX_PARALLEL_CALLS": config.EVENT_LLM_MAX_PARALLEL_CALLS,
        "EVENT_LLM_CACHE_TTL_HOURS": config.EVENT_LLM_CACHE_TTL_HOURS,
        "EVENT_LLM_CACHE_PATH": config.EVENT_LLM_CACHE_PATH,
        "EVENT_LLM_BUDGET_LEDGER_PATH": config.EVENT_LLM_BUDGET_LEDGER_PATH,
        "EVENT_LLM_PROMPT_VERSION": config.EVENT_LLM_PROMPT_VERSION,
    }
    config.EVENT_DISCOVERY_EVENTS_PATH = path
    config.EVENT_DISCOVERY_ALIASES_PATH = path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    config.EVENT_DISCOVERY_LOOKBACK_HOURS = 120
    config.EVENT_DISCOVERY_HORIZON_DAYS = 14
    config.EVENT_ALERTS_ENABLED = False
    config.EVENT_LLM_ENABLED = False
    config.EVENT_LLM_MODE = "advisory"
    config.EVENT_LLM_PROVIDER = "fixture"
    config.EVENT_LLM_MODEL = None
    config.EVENT_LLM_OPENAI_TIMEOUT = 30.0
    config.EVENT_LLM_MAX_CANDIDATES_PER_RUN = 50
    config.EVENT_LLM_MIN_PREFILTER_SCORE = 0
    config.EVENT_LLM_REQUIRE_EVIDENCE_QUOTES = True
    config.EVENT_LLM_MAX_CALLS_PER_RUN = 50
    config.EVENT_LLM_MAX_CALLS_PER_DAY = 50
    config.EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY = 0.0
    config.EVENT_LLM_ESTIMATED_COST_PER_CALL_USD = 0.0
    config.EVENT_LLM_MAX_PARALLEL_CALLS = 1
    config.EVENT_LLM_CACHE_TTL_HOURS = 0.0
    config.EVENT_LLM_CACHE_PATH = None
    config.EVENT_LLM_BUDGET_LEDGER_PATH = None
    config.EVENT_LLM_PROMPT_VERSION = "llm_proxy_context_v1"
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_alert_report(send=False, with_llm=True, event_now="2026-06-15T16:00:00Z")
        text = out.getvalue()
        assert "EVENT RESEARCH ALERT REPORT" in text
        assert "llm tier adjustment: RADAR_DIGEST -> STORE_ONLY" in text
        assert "llm: role=source_noise" in text
        assert "llm adjustment reason:" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_event_fade_export_cache_sample_scanner_writes_latest_cached_rows():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    values = _full_event_discovery_config_values()
    attrs = tuple(values) + ("EVENT_DISCOVERY_CACHE_DIR",)
    original = {name: getattr(config, name) for name in attrs}
    for name, value in values.items():
        setattr(config, name, value)
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / "cache"
        out_path = Path(tmp) / "cached_sample.jsonl"
        config.EVENT_DISCOVERY_CACHE_DIR = cache_dir
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                scanner.event_discovery_refresh(event_now="2026-06-15T16:00:00Z")
                scanner.event_discovery_refresh(event_now="2026-06-15T16:00:00Z")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_fade_export_cache_sample(str(out_path))
            text = out.getvalue()
            assert "Event-fade cached validation sample" in text
            assert "read 34 snapshot(s)" in text
            assert "exported 17 latest row(s)" in text

            rows = [
                json.loads(line)
                for line in out_path.read_text(encoding="utf-8").splitlines()
            ]
            assert len(rows) == 17
            velvet = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
            assert velvet["schema_version"] == "event_fade_validation_sample_v1"
            assert velvet["row_type"] == "candidate"
            assert velvet["signal_type"] == "SHORT_TRIGGERED"
            assert "payload_row_type" not in velvet
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_event_fade_auto_scanner_report_uses_local_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    tokenomist_supply_path, etherscan_supply_path, arkham_supply_path, dune_supply_path = _supply_fixture_paths()
    attrs = (
        "EVENT_DISCOVERY_EVENTS_PATH",
        "EVENT_DISCOVERY_ALIASES_PATH",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH",
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH",
        "EVENT_DISCOVERY_COINMARKETCAL_PATH",
        "EVENT_DISCOVERY_TOKENOMIST_PATH",
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH",
        "EVENT_DISCOVERY_GDELT_PATH",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH",
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH",
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH",
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH",
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH",
        "EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH",
        "EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH",
        "EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH",
        "EVENT_DISCOVERY_DUNE_SUPPLY_PATH",
        "EVENT_DISCOVERY_UNIVERSE_PATH",
        "EVENT_DISCOVERY_LOOKBACK_HOURS",
        "EVENT_DISCOVERY_HORIZON_DAYS",
    )
    original = {name: getattr(config, name) for name in attrs}
    config.EVENT_DISCOVERY_EVENTS_PATH = events_path
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = binance_path
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = bybit_path
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = coinmarketcal_path
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = tokenomist_path
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = cryptopanic_path
    config.EVENT_DISCOVERY_GDELT_PATH = gdelt_path
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = blog_path
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = ipo_path
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = sports_path
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = prediction_path
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = _derivatives_fixture_path()
    config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH = tokenomist_supply_path
    config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH = etherscan_supply_path
    config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH = arkham_supply_path
    config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH = dune_supply_path
    config.EVENT_DISCOVERY_UNIVERSE_PATH = _coingecko_universe_fixture_path()
    config.EVENT_DISCOVERY_LOOKBACK_HOURS = 120
    config.EVENT_DISCOVERY_HORIZON_DAYS = 2
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_auto_report(event_now="2026-06-15T16:00:00Z")
        text = out.getvalue()
        assert "EVENT FADE AUTO REPORT" in text
        assert "TRIGGERED\n  TESTVELVET" in text
        assert "TESTAI" in text
        assert "REJECTED / NO TRADE" in text
        assert "  TESTLIST     coin=testlist" in text
        assert "AMBIGUOUS" in text
        assert "  TESTPUMP     coin=testpump" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_event_fade_export_sample_scanner_writes_jsonl_fixture():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    values = _full_event_discovery_config_values()
    original = {name: getattr(config, name) for name in values}
    for name, value in values.items():
        setattr(config, name, value)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "sample.jsonl"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_fade_export_sample(str(out_path), event_now="2026-06-15T16:00:00Z")
            text = out.getvalue()
            assert "wrote" in text
            assert out_path.exists()
            rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
            assert len(rows) == 17
            assert any(row["asset_symbol"] == "TESTVELVET" for row in rows)
            assert all(row["human_label"] == "" for row in rows)
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_event_fade_review_sample_scanner_reads_jsonl_fixture():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, scanner

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "sample.jsonl"
        event_discovery.write_validation_sample(rows, out_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_review_sample(str(out_path))
        text = out.getvalue()
        assert "EVENT FADE VALIDATION SAMPLE REVIEW" in text
        assert "Rows: 17" in text
        assert "BLOCKED" in text
        assert "reviewed proxy candidates 0/25" in text


def test_event_fade_labeling_queue_scanner_reads_jsonl_fixture():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, scanner

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "sample.jsonl"
        event_discovery.write_validation_sample(rows, out_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_labeling_queue(str(out_path), limit=3)
        text = out.getvalue()
        assert "EVENT FADE VALIDATION LABELING QUEUE" in text
        assert "showing: 3" in text
        assert "label_triggered_candidate" in text
        assert "TESTVELVET" in text


def test_event_fade_review_packet_scanner_writes_markdown_fixture():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, scanner

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        packet_path = Path(tmp) / "packet.md"
        event_discovery.write_validation_sample(rows, sample_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_review_packet(str(sample_path), str(packet_path), limit=1)
        text = out.getvalue()
        assert "Event-fade review packet" in text
        assert "wrote 1/17 row(s) needing review" in text

        packet = packet_path.read_text(encoding="utf-8")
        assert "# Event-Fade Validation Review Packet" in packet
        assert "## 1. TESTVELVET - SpaceX IPO trading start" in packet
        assert "Review fields to fill" in packet


def test_event_fade_review_template_scanner_exports_and_applies_sidecar():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, event_validation, scanner

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        template_path = Path(tmp) / "review_template.csv"
        reviewed_path = Path(tmp) / "reviewed.jsonl"
        event_discovery.write_validation_sample(rows, sample_path)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_export_review_template(
                str(sample_path),
                str(template_path),
                limit=1,
            )
        text = out.getvalue()
        assert "Event-fade review template" in text
        assert "wrote 1/17 row(s) needing review" in text

        template_rows = event_validation.load_validation_sample(template_path)
        template_rows[0]["review_status"] = "reviewed"
        template_rows[0]["reviewed_by"] = "Codex"
        template_rows[0]["reviewed_at"] = "2026-06-17T11:30:00+00:00"
        template_rows[0]["human_label"] = "valid_proxy_fade"
        template_rows[0]["human_notes"] = "Reviewed compact sidecar."
        template_path.write_text(
            event_validation.format_review_template_csv(template_rows),
            encoding="utf-8",
        )

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_apply_review_template(
                str(sample_path),
                str(template_path),
                str(reviewed_path),
            )
        text = out.getvalue()
        assert "Event-fade review template apply" in text
        assert "1 matched row(s)" in text
        assert "0 evidence-changed row(s)" in text
        assert "EVENT FADE VALIDATION SAMPLE REVIEW" in text
        assert "Rows: 17" in text
        assert "reviewed: 1" in text
        assert "NEXT SAMPLE WORK" in text

        written = [
            json.loads(line)
            for line in reviewed_path.read_text(encoding="utf-8").splitlines()
        ]
        velvet = next(row for row in written if row["asset_symbol"] == "TESTVELVET")
        assert velvet["reviewed_by"] == "Codex"
        assert velvet["reviewed_at"] == "2026-06-17T11:30:00+00:00"
        assert velvet["human_label"] == "valid_proxy_fade"
        assert velvet["human_notes"] == "Reviewed compact sidecar."


def test_event_fade_check_review_template_scanner_dry_checks_sidecar():
    import contextlib
    import io
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, event_validation, scanner

    rows = [{
        "event_id": "event-control",
        "asset_symbol": "CTRL",
        "asset_coin_id": "control-token",
        "event_name": "Control narrative mention",
        "relationship_type": "ambiguous",
        "signal_type": "NO_TRADE",
        "is_proxy_narrative": False,
        "is_direct_beneficiary": False,
        "first_seen_time": "2026-06-17T10:00:00+00:00",
        "source_urls": [],
        "raw_published_at": ["2026-06-17T09:00:00+00:00"],
        "raw_fetched_at": ["2026-06-17T10:00:00+00:00"],
    }]

    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        template_path = Path(tmp) / "review_template.csv"
        event_discovery.write_validation_sample(rows, sample_path)
        template_rows = event_validation.build_review_template_rows(rows, limit=1)
        template_rows[0]["review_status"] = "reviewed"
        template_rows[0]["reviewed_by"] = "Codex"
        template_rows[0]["reviewed_at"] = "2026-06-17T11:30:00+00:00"
        template_rows[0]["human_label"] = "ambiguous"
        template_path.write_text(
            event_validation.format_review_template_csv(template_rows),
            encoding="utf-8",
        )

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_check_review_template(str(sample_path), str(template_path))
        text = out.getvalue()
        assert "EVENT FADE REVIEW TEMPLATE CHECK" in text
        assert "Status: ready to apply." in text
        assert "edited rows: 1" in text


def test_event_fade_review_bundle_scanner_writes_workspace():
    import contextlib
    import csv
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, scanner

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        bundle_dir = Path(tmp) / "review_bundle"
        event_discovery.write_validation_sample(rows, sample_path)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_review_bundle(
                str(sample_path),
                str(bundle_dir),
                limit=1,
                prices_path=str(_outcome_prices_fixture_path()),
                event_now="2026-06-15T16:00:00Z",
            )
        text = out.getvalue()
        assert "Event-fade review bundle" in text
        assert "needing_review=17" in text
        assert "showing=1" in text

        expected = {
            "README.md",
            "manifest.json",
            "validation_sample.jsonl",
            "validation_sample_with_outcomes.jsonl",
            "labeling_queue.txt",
            "review_packet.md",
            "review_packet_balanced.md",
            "review_template.csv",
            "review_template_balanced.csv",
            "review_guide.md",
            "review_report.txt",
        }
        assert expected == {path.name for path in bundle_dir.iterdir()}

        readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
        assert "Research-only" in readme
        assert "validation_sample_with_outcomes.jsonl" in readme
        assert "review_guide.md" in readme
        assert "review_packet_balanced.md" in readme
        assert "review_template_balanced.csv" in readme
        assert "source_providers" in readme
        assert "manifest.json" in readme

        guide = (bundle_dir / "review_guide.md").read_text(encoding="utf-8")
        assert "Event-Fade Review Guide" in guide
        assert "`valid_proxy_fade`" in guide
        assert "`false_positive`" in guide
        assert "`direct_event`" in guide
        assert "`ambiguous`" in guide
        assert "reviewed_by" in guide
        assert "reviewed_at" in guide
        assert "human_event_time" in guide
        assert "external_asset" in guide
        assert "primary_source_url" in guide
        assert "source_search_url" in guide
        assert "source_date_hint" in guide
        assert "source_providers" in guide
        assert "review_prompt" in guide
        assert "helper columns are not copied back" in guide
        assert "review_template_balanced.csv" in guide

        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["source"]["sample_path"] == str(sample_path)
        assert manifest["source"]["review_rows"] == 17
        assert manifest["queue"]["shown_rows"] == 1
        assert manifest["files"]["review_packet_balanced"] == "review_packet_balanced.md"
        assert manifest["files"]["review_template"] == "review_template.csv"
        assert manifest["files"]["review_template_balanced"] == "review_template_balanced.csv"
        assert manifest["files"]["review_guide"] == "review_guide.md"
        assert manifest["balanced_review_template"]["rows"] >= 1
        assert manifest["balanced_review_template"]["proxy_limit"] == 25
        assert manifest["balanced_review_template"]["control_limit"] == 50
        assert manifest["outcome_fill"]["filled_rows"] == 1
        assert manifest["review"]["promotion_ready"] is False
        assert manifest["review"]["reviewed_proxy_event_types"] == 0
        assert manifest["review"]["min_proxy_event_types"] == 2
        assert manifest["review"]["reviewed_proxy_source_providers"] == 0
        assert manifest["review"]["min_proxy_source_providers"] == 2
        assert manifest["review"]["reviewed_proxy_source_origins"] == 0
        assert manifest["review"]["low_confidence_trigger_event_time_rows"] == 0
        assert manifest["sample_summary"]["rows"] == 17
        assert manifest["sample_summary"]["proxy_candidates"] == 6
        assert manifest["sample_summary"]["direct_beneficiaries"] == 9
        assert manifest["sample_summary"]["short_triggered_rows"] == 1
        assert manifest["sample_summary"]["asset_roles"]["proxy_instrument"] == 6
        assert manifest["sample_summary"]["source_providers"]["manual_json"] == 5
        assert manifest["sample_summary"]["source_provider_summary"]["manual_json"]["rows"] == 5
        assert manifest["sample_summary"]["source_provider_summary"]["manual_json"]["short_triggered_rows"] == 1
        assert manifest["sample_summary"]["source_provider_summary"]["cryptopanic"]["direct_beneficiaries"] == 2
        assert manifest["sample_summary"]["source_origins"]["example.test"] == 13
        assert manifest["sample_summary"]["source_origin_summary"]["example.test"]["short_triggered_rows"] == 1
        template_header = (bundle_dir / "review_template.csv").read_text(encoding="utf-8").splitlines()[0]
        assert "external_asset" in template_header
        assert "primary_source_url" in template_header
        assert "primary_raw_title" in template_header
        assert "source_search_url" in template_header
        assert "source_date_hint" in template_header
        assert "source_providers" in template_header
        assert "event_time_review_hint" in template_header
        balanced_header = (bundle_dir / "review_template_balanced.csv").read_text(encoding="utf-8").splitlines()[0]
        assert "review_slice" in balanced_header
        assert "external_asset" in balanced_header
        assert "primary_source_url" in balanced_header
        assert "source_search_url" in balanced_header
        assert "source_date_hint" in balanced_header
        assert "source_providers" in balanced_header
        assert "Sample summary:" in readme
        assert "Proxy candidates: 6" in readme
        assert "Asset roles: direct_beneficiary=9, proxy_instrument=6, ambiguous=2" in readme
        assert "Source provider detail:" in readme
        assert "Source origins:" in readme
        assert "Source origin detail:" in readme
        assert "Review gates:" in readme
        assert "Proxy diversity: event_types=0/2, source_providers=0/2, source_origins=0" in readme
        assert "manual_json: rows=5, proxy=1, direct=3, triggered=1, missing_time=1" in readme

        packet = (bundle_dir / "review_packet.md").read_text(encoding="utf-8")
        assert "## 1. TESTVELVET - SpaceX IPO trading start" in packet
        assert "trigger 72h=`-20.8%`" in packet
        balanced_packet = (bundle_dir / "review_packet_balanced.md").read_text(encoding="utf-8")
        assert "# Event-Fade Balanced Review Packet" in balanced_packet
        assert "- Review slice: `triggered`" in balanced_packet
        assert "- Review slice: `negative_control`" in balanced_packet
        assert "Source search:" in balanced_packet
        assert "Source providers:" in balanced_packet

        report = (bundle_dir / "review_report.txt").read_text(encoding="utf-8")
        assert "EVENT FADE VALIDATION SAMPLE REVIEW" in report
        assert "reviewed proxy candidates 0/25" in report

        template_text = (bundle_dir / "review_template.csv").read_text(encoding="utf-8")
        template_rows = list(csv.DictReader(template_text.splitlines()))
        assert len(template_rows) == 1
        assert template_rows[0]["asset_symbol"] == "TESTVELVET"

        filled_text = (bundle_dir / "validation_sample_with_outcomes.jsonl").read_text(
            encoding="utf-8"
        )
        filled_rows = [json.loads(line) for line in filled_text.splitlines()]
        velvet = next(row for row in filled_rows if row["asset_symbol"] == "TESTVELVET")
        assert round(velvet["post_event_return_72h"], 4) == -0.2083


def test_event_fade_review_bundle_scanner_auto_exports_price_fixture():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, scanner

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        bundle_dir = Path(tmp) / "review_bundle"
        event_discovery.write_validation_sample(rows, sample_path)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_review_bundle(
                str(sample_path),
                str(bundle_dir),
                limit=1,
                auto_export_prices=True,
                price_days=30,
                price_fixture_dir=str(_outcome_klines_fixture_dir()),
                event_now="2026-06-15T16:00:00Z",
            )
        text = out.getvalue()
        assert "Outcome price fixture" in text
        assert "Outcome-filled sample" in text

        expected = {
            "README.md",
            "manifest.json",
            "validation_sample.jsonl",
            "validation_sample_with_outcomes.jsonl",
            "outcome_prices.json",
            "labeling_queue.txt",
            "review_packet.md",
            "review_packet_balanced.md",
            "review_template.csv",
            "review_template_balanced.csv",
            "review_guide.md",
            "review_report.txt",
        }
        assert expected == {path.name for path in bundle_dir.iterdir()}

        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["price_export"]["exported"] is True
        assert manifest["price_export"]["assets_written"] == 1
        assert manifest["price_export"]["price_rows_written"] == 5
        assert manifest["files"]["outcome_prices"] == "outcome_prices.json"
        assert manifest["files"]["review_packet_balanced"] == "review_packet_balanced.md"
        assert manifest["files"]["review_template_balanced"] == "review_template_balanced.csv"
        assert manifest["outcome_fill"]["prices_path"] == str(bundle_dir / "outcome_prices.json")
        assert manifest["outcome_fill"]["filled_rows"] == 1

        readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
        assert "Auto price export: yes" in readme
        assert "`outcome_prices.json`" in readme

        prices = json.loads((bundle_dir / "outcome_prices.json").read_text(encoding="utf-8"))
        assert prices["schema_version"] == "event_fade_outcome_prices_v1"
        assert len(prices["prices"]) == 5

        filled_rows = [
            json.loads(line)
            for line in (bundle_dir / "validation_sample_with_outcomes.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
        ]
        velvet = next(row for row in filled_rows if row["asset_symbol"] == "TESTVELVET")
        assert round(velvet["post_event_return_72h"], 4) == -0.2083


def test_event_fade_cache_review_bundle_scanner_writes_workspace():
    import contextlib
    import csv
    import io
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import config, event_cache, scanner

    result = _full_event_discovery_fixture_result()
    original_cache_dir = config.EVENT_DISCOVERY_CACHE_DIR
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / "cache"
        bundle_dir = Path(tmp) / "cache_review_bundle"
        config.EVENT_DISCOVERY_CACHE_DIR = cache_dir
        try:
            event_cache.write_event_discovery_cache(
                result,
                cache_dir,
                observed_at=datetime(2026, 6, 16, 12, 30, tzinfo=timezone.utc),
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_fade_cache_review_bundle(
                    str(bundle_dir),
                    limit=1,
                    prices_path=str(_outcome_prices_fixture_path()),
                    event_now="2026-06-15T16:00:00Z",
                )
            text = out.getvalue()
            assert "Event-fade cached review bundle" in text
            assert "snapshots_read=17" in text
            assert "rows=17" in text
            assert "needing_review=17" in text

            expected = {
                "README.md",
                "manifest.json",
                "validation_sample.jsonl",
                "validation_sample_with_outcomes.jsonl",
                "labeling_queue.txt",
                "review_packet.md",
                "review_packet_balanced.md",
                "review_template.csv",
                "review_template_balanced.csv",
                "review_guide.md",
                "review_report.txt",
            }
            assert expected == {path.name for path in bundle_dir.iterdir()}

            readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
            assert f"Input sample: `cache:{cache_dir}`" in readme

            manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
            assert manifest["source"]["sample_path"] == f"cache:{cache_dir}"
            assert manifest["source"]["review_rows"] == 17
            assert manifest["queue"]["shown_rows"] == 1
            assert manifest["files"]["review_packet_balanced"] == "review_packet_balanced.md"
            assert manifest["balanced_review_template"]["rows"] >= 1
            assert manifest["outcome_fill"]["prices_path"] == str(_outcome_prices_fixture_path())
            assert manifest["sample_summary"]["rows"] == 17
            assert manifest["sample_summary"]["asset_roles"]["proxy_instrument"] == 6
            assert manifest["sample_summary"]["source_provider_summary"]["manual_json"]["short_triggered_rows"] == 1
            assert manifest["review"]["reviewed_proxy_source_providers"] == 0
            assert manifest["review"]["min_proxy_source_providers"] == 2

            template_text = (bundle_dir / "review_template.csv").read_text(encoding="utf-8")
            template_rows = list(csv.DictReader(template_text.splitlines()))
            assert len(template_rows) == 1
            assert template_rows[0]["asset_symbol"] == "TESTVELVET"

            filled_text = (bundle_dir / "validation_sample_with_outcomes.jsonl").read_text(
                encoding="utf-8"
            )
            filled_rows = [json.loads(line) for line in filled_text.splitlines()]
            velvet = next(row for row in filled_rows if row["asset_symbol"] == "TESTVELVET")
            assert round(velvet["post_event_return_72h"], 4) == -0.2083
        finally:
            config.EVENT_DISCOVERY_CACHE_DIR = original_cache_dir


def test_event_fade_cache_review_bundle_warns_on_empty_cache():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    original_cache_dir = config.EVENT_DISCOVERY_CACHE_DIR
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / "empty_cache"
        bundle_dir = Path(tmp) / "empty_bundle"
        config.EVENT_DISCOVERY_CACHE_DIR = cache_dir
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_fade_cache_review_bundle(
                    str(bundle_dir),
                    limit=5,
                    event_now="2026-06-15T16:00:00Z",
                )
            text = out.getvalue()
            assert "snapshots_read=0" in text
            assert "rows=0" in text
            assert "No validation rows were available" in text
            assert "event-discovery-status" in text

            manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
            assert manifest["source"]["review_rows"] == 0
            assert manifest["sample_summary"]["rows"] == 0
            assert manifest["sample_summary"]["asset_roles"] == {}
            assert manifest["sample_summary"]["source_provider_summary"] == {}
            assert manifest["warnings"]
            assert "No validation rows were available" in manifest["warnings"][0]

            readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
            assert "Warnings:" in readme
            assert "No validation rows were available" in readme
            assert "Sample summary:" in readme
            assert "Asset roles: none" in readme
        finally:
            config.EVENT_DISCOVERY_CACHE_DIR = original_cache_dir


def test_event_fade_merge_sample_scanner_writes_merged_jsonl():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, scanner

    fresh = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed_row = next(row for row in reviewed if row["asset_symbol"] == "TESTVELVET")
    reviewed_row["human_label"] = "valid_proxy_fade"
    reviewed_row["post_event_return_72h"] = -0.22
    with tempfile.TemporaryDirectory() as tmp:
        fresh_path = Path(tmp) / "fresh.jsonl"
        reviewed_path = Path(tmp) / "reviewed.jsonl"
        merged_path = Path(tmp) / "merged.jsonl"
        event_discovery.write_validation_sample(fresh, fresh_path)
        event_discovery.write_validation_sample(reviewed, reviewed_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_merge_sample(str(fresh_path), str(reviewed_path), str(merged_path))
        text = out.getvalue()
        assert "matched row(s)" in text
        assert "0 evidence-changed row(s)" in text
        rows = [json.loads(line) for line in merged_path.read_text(encoding="utf-8").splitlines()]
        velvet = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
        assert velvet["human_label"] == "valid_proxy_fade"
        assert velvet["post_event_return_72h"] == -0.22


def test_event_fade_merge_sample_scanner_reports_changed_evidence():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, scanner

    fresh = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    fresh_row = next(row for row in fresh if row["asset_symbol"] == "TESTVELVET")
    fresh_row["raw_content_hashes"] = ["changed-source-hash"]
    reviewed_row = next(row for row in reviewed if row["asset_symbol"] == "TESTVELVET")
    reviewed_row["review_status"] = "reviewed"
    _stamp_review_provenance(reviewed_row)
    reviewed_row["human_label"] = "valid_proxy_fade"
    reviewed_row["post_event_return_72h"] = -0.22
    with tempfile.TemporaryDirectory() as tmp:
        fresh_path = Path(tmp) / "fresh.jsonl"
        reviewed_path = Path(tmp) / "reviewed.jsonl"
        merged_path = Path(tmp) / "merged.jsonl"
        event_discovery.write_validation_sample(fresh, fresh_path)
        event_discovery.write_validation_sample(reviewed, reviewed_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_merge_sample(str(fresh_path), str(reviewed_path), str(merged_path))
        text = out.getvalue()
        assert "1 evidence-changed row(s)" in text
        assert "Evidence-changed rows" in text
        assert "TESTVELVET" in text
        assert "raw_content_hashes" in text
        rows = [json.loads(line) for line in merged_path.read_text(encoding="utf-8").splitlines()]
        velvet = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
        assert velvet["human_label"] == ""
        assert velvet["post_event_return_72h"] is None


def test_event_identity_shared_matcher_field_safety():
    from crypto_rsi_scanner import event_identity

    hype = event_identity.AssetIdentity(symbol="HYPE", coin_id="hyperliquid")
    result = event_identity.match_asset_identity(
        hype,
        event_identity.IdentityEvidence(strong_content=("IPO hype keeps building",)),
    )
    assert result.reason == "common_word_identity_rejected"

    pump = event_identity.AssetIdentity(symbol="PUMP", coin_id="pump-token")
    url_only = event_identity.match_asset_identity(
        pump,
        event_identity.IdentityEvidence(url="https://search.example/?q=PUMPUSDT"),
    )
    assert url_only.reason == "identity_url_only_rejected"
    body_match = event_identity.match_asset_identity(
        pump,
        event_identity.IdentityEvidence(strong_content=("PUMPUSDT volume surged after listing rumors",)),
    )
    assert body_match.matched and body_match.reason == "identity_match_pair"

    btc = event_identity.AssetIdentity(symbol="BTC", coin_id="bitcoin", project_name="Bitcoin")
    publisher = event_identity.match_asset_identity(
        btc,
        event_identity.IdentityEvidence(source_origin=("Bitcoin World",)),
    )
    assert publisher.reason == "identity_source_origin_rejected"

    address = "0x1111111111111111111111111111111111111111"
    contract = event_identity.AssetIdentity(symbol="AAA", contract_addresses=(address,))
    path_match = event_identity.match_asset_identity(
        contract,
        event_identity.IdentityEvidence(url=f"https://etherscan.io/token/{address}"),
    )
    assert path_match.matched and path_match.evidence_field == "url_path_contract"
    query_match = event_identity.match_asset_identity(
        contract,
        event_identity.IdentityEvidence(url=f"https://search.example/?contract={address}"),
    )
    assert query_match.reason == "identity_url_only_rejected"


def test_event_watchlist_market_sources_select_active_rows():
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import event_watchlist, event_watchlist_market

    entry = _test_watchlist_entry(state="WATCHLIST", symbol="VELVET", coin_id="velvet")
    read = event_watchlist.EventWatchlistReadResult(Path("state.jsonl"), 1, [entry], True)
    rows = [{"id": "velvet", "symbol": "velvet", "current_price": 1.23, "price_change_percentage_24h": 30}]
    selected = event_watchlist_market.market_rows_for_watchlist(read, source="cycle", cycle_rows=rows)
    assert selected.rows_selected == 1
    assert selected.rows[0]["id"] == "velvet"

    tmp = Path(tempfile.mkdtemp()) / "markets.json"
    tmp.write_text('[{"id":"velvet","symbol":"velvet","current_price":2.0}]')
    loaded = event_watchlist_market.load_market_rows(tmp)
    fixture = event_watchlist_market.market_rows_for_watchlist(read, source="fixture", fixture_rows=loaded)
    assert fixture.rows_selected == 1

    empty = event_watchlist_market.market_rows_for_watchlist(read, source="cycle", cycle_rows=[])
    assert empty.rows_selected == 0
    assert empty.warnings


def test_event_research_cards_write_files_and_index():
    from dataclasses import replace
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import event_alpha_router, event_research_cards, event_watchlist

    entry = _test_watchlist_entry(state="HIGH_PRIORITY", symbol="VELVET", coin_id="velvet")
    rune = replace(
        _test_watchlist_entry(state="WATCHLIST", symbol="RUNE", coin_id="thorchain"),
        key="incident:rune|thorchain|security",
        relationship_type="impact_hypothesis",
        external_asset="THORChain",
        latest_event_name="THORChain exploit and RUNE resumes trading",
        latest_playbook_type="security_or_regulatory_shock",
        latest_effective_playbook_type="security_or_regulatory_shock",
        requested_state_before_quality_gate=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        final_state_after_quality_gate=event_watchlist.EventWatchlistState.WATCHLIST.value,
        state_quality_capped=True,
        quality_state_block_reason="opportunity_level_caps_state:watchlist",
        latest_score_components={
            **entry.latest_score_components,
            "incident_id": "incident:rune",
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "impact_path_type": "exploit_security_event",
            "impact_path_reason": "exploit_security_event",
            "candidate_role": "direct_subject",
            "impact_category": "security_or_regulatory_shock",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 83,
        },
    )
    rune_suppressed = event_alpha_router.EventAlphaRouteDecision(
        entry=rune,
        route=event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE,
        alertable=False,
        reason="duplicate digest already sent",
        final_route_after_quality_gate=event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
        opportunity_level="watchlist",
        opportunity_score_final=83,
    )
    diagnostic = replace(
        _test_watchlist_entry(state="HIGH_PRIORITY", symbol="VELVET", coin_id="velvet"),
        key="cluster|velvet|source_noise_control",
        latest_playbook_type="source_noise_control",
        latest_effective_playbook_type="source_noise_control",
        latest_score_components={
            **entry.latest_score_components,
            "candidate_role": "source_noise",
            "impact_path_type": "generic_cooccurrence_only",
            "opportunity_level": "local_only",
            "opportunity_score_final": 0,
        },
    )
    out_dir = Path(tempfile.mkdtemp())
    result = event_research_cards.write_research_cards(
        out_dir,
        watchlist_entries=[entry, rune, diagnostic],
        alert_rows=[],
        route_decisions=[rune_suppressed],
    )
    assert result.cards_written == 2
    assert result.index_path.exists()
    card_text = "\n".join(path.read_text() for path in result.card_paths)
    assert "VELVET" in card_text
    assert "RUNE" in card_text
    rune_card = next(path for path in result.card_paths if "RUNE" in path.read_text())
    assert event_research_cards.card_core_opportunity_id(rune_card)
    assert event_research_cards.card_feedback_target(rune_card) == event_research_cards.card_core_opportunity_id(rune_card)
    assert rune_card.name in result.index_path.read_text()
    assert "Core Opportunity Cards" in result.index_path.read_text()
    assert "source_noise_control" not in result.index_path.read_text().split("## Core Opportunity Cards", 1)[1].split("## Diagnostic", 1)[0]


def test_event_alpha_explain_last_run_paths():
    from crypto_rsi_scanner import event_alpha_daily_brief, event_alpha_explain, event_alpha_run_ledger

    quiet = event_alpha_explain.format_last_run_explanation([
        {"run_id": "r1", "run_mode": "burn_in", "artifact_namespace": "no_key_live", "success": True, "raw_events": 0, "market_anomalies": 0, "candidates": 0, "alerts": 0, "routed": 0, "alertable": 0}
    ])
    assert "no source events or market anomalies" in quiet
    routed = event_alpha_explain.format_last_run_explanation([
        {"run_id": "r2", "run_mode": "burn_in", "artifact_namespace": "no_key_live", "success": True, "raw_events": 3, "market_anomalies": 1, "candidates": 2, "alerts": 2, "routed": 2, "alertable": 0, "llm_skipped_due_budget": 1}
    ], alert_rows=[{"run_mode": "burn_in", "artifact_namespace": "no_key_live", "tier": "STORE_ONLY", "rejected_reason": "source_noise"}])
    assert "router produced no alertable decisions" in routed
    assert "skipped_budget=1" in routed

    rows = [
        {"run_id": "default-newer", "profile": "default", "run_mode": "burn_in", "artifact_namespace": "default", "started_at": "2026-06-19T12:00:00+00:00", "success": True},
        {"run_id": "no-key-older", "profile": "no_key_live", "run_mode": "burn_in", "artifact_namespace": "no_key_live", "started_at": "2026-06-19T10:00:00+00:00", "success": True},
    ]
    assert event_alpha_run_ledger.latest_run(rows)["run_id"] == "default-newer"
    assert event_alpha_run_ledger.latest_run(rows, "no_key_live")["run_id"] == "no-key-older"
    assert event_alpha_run_ledger.latest_runs_by_profile(rows)["no_key_live"]["run_id"] == "no-key-older"
    explain = event_alpha_explain.format_last_run_explanation(rows, requested_profile="no_key_live")
    assert "requested_profile: no_key_live" in explain
    assert "selected_run_profile: no_key_live" in explain
    assert "profile_match: true" in explain
    fallback = event_alpha_explain.format_last_run_explanation(rows, requested_profile="full_llm_live")
    assert "No Event Alpha run ledger rows found." in fallback
    markdown = event_alpha_daily_brief.build_daily_brief(
        run_rows=rows,
        requested_profile="no_key_live",
        clock_status={
            "clock_mode": "fixed",
            "research_now": "2026-06-15T16:00:00+00:00",
            "wall_clock_now": "2026-06-20T16:00:00+00:00",
            "fixed_clock_age_hours": 120.0,
            "warnings": ("fixed research clock active", "fixed research clock is stale by 120.0h"),
        },
    )
    assert "Requested profile: no_key_live" in markdown
    assert "Selected run profile: no_key_live" in markdown
    assert "Profile match: true" in markdown
    assert "Clock: mode=fixed" in markdown
    assert "fixed_clock_age_hours=120.00h" in markdown
    assert "Clock warning: fixed research clock is stale by 120.0h" in markdown
    legacy_warning = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{"run_id": "legacy", "started_at": "2026-06-19T12:00:00+00:00", "success": True}],
        requested_profile="no_key_live",
    )
    assert "only legacy/default run rows were available" in legacy_warning


def test_event_watchlist_market_targeted_provider_and_fallback():
    from crypto_rsi_scanner import event_watchlist_market

    watchlist = type("Read", (), {
        "entries": [
            _test_watchlist_entry(state="WATCHLIST", symbol="VELVET", coin_id="velvet"),
        ]
    })()
    targeted = event_watchlist_market.FixtureWatchlistMarketProvider([
        {"id": "velvet", "symbol": "velvet", "price_change_percentage_24h": 22.0},
        {"id": "noise", "symbol": "noise"},
    ])
    result = event_watchlist_market.market_rows_for_watchlist(
        watchlist,
        source="fixture",
        fixture_rows=[{"id": "velvet", "symbol": "velvet", "price_change_percentage_24h": 4.0}],
        targeted_lookup=True,
        targeted_provider=targeted,
        cache_ttl_seconds=123,
    )
    assert result.assets_requested == 1
    assert result.rows_selected == 1
    assert result.rows[0]["price_change_percentage_24h"] == 22.0
    assert result.rows[0]["watchlist_market_source"] == "fixture"
    assert result.cache_status == "ttl=123s"

    fallback = event_watchlist_market.market_rows_for_watchlist(
        watchlist,
        source="coingecko",
        cycle_rows=[{"id": "velvet", "symbol": "velvet", "price_change_percentage_24h": 7.0}],
        targeted_lookup=True,
        cache_ttl_seconds=30,
    )
    assert fallback.rows[0]["price_change_percentage_24h"] == 7.0
    assert any("not configured" in warning for warning in fallback.warnings)


def test_watchlist_coingecko_targeted_provider_cache_and_fallback():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_watchlist, event_watchlist_market, event_watchlist_monitor

    calls = {"count": 0}

    def fetcher(ids):
        calls["count"] += 1
        return [
            {"id": coin_id, "symbol": coin_id[:3], "current_price": idx + 1, "price_change_percentage_24h": 20}
            for idx, coin_id in enumerate(ids)
        ]

    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    provider = event_watchlist_market.CoinGeckoWatchlistMarketProvider(
        fetcher=fetcher,
        cache_ttl_seconds=900,
        now_fn=lambda: now,
    )
    rows, warnings = provider.fetch_market_rows(["velvet", "bitcoin", "chiliz"], max_assets=2)
    assert warnings == ()
    assert len(rows) == 2
    assert calls["count"] == 1
    rows_again, _warnings_again = provider.fetch_market_rows(["bitcoin", "velvet"], max_assets=2)
    assert len(rows_again) == 2
    assert calls["count"] == 1
    assert provider.last_cache_status == "hit"

    entry = _test_watchlist_entry(state="WATCHLIST", symbol="VELVET", coin_id="velvet")
    read = event_watchlist.EventWatchlistReadResult(
        state_path=__import__("pathlib").Path("/tmp/watchlist.jsonl"),
        rows_read=1,
        entries=[entry],
        latest_only=True,
    )

    def failing_fetcher(ids):
        raise RuntimeError("boom")

    fallback = event_watchlist_market.market_rows_for_watchlist(
        read,
        source="coingecko",
        cycle_rows=[{"coin_id": "velvet", "symbol": "VELVET", "return_24h": 0.22, "volume_zscore_24h": 4.0}],
        targeted_lookup=True,
        targeted_provider=event_watchlist_market.CoinGeckoWatchlistMarketProvider(fetcher=failing_fetcher),
        now=now,
    )
    assert fallback.rows_selected == 1
    assert any("failed" in warning for warning in fallback.warnings)
    monitored = event_watchlist_monitor.monitor_watchlist(read, market_rows=fallback.rows, now=now)
    assert monitored.rows[0].material_update is True
    updated = event_watchlist_monitor.apply_monitor_updates_to_watchlist(read, monitored)
    assert updated.entries[0].state != "TRIGGERED_FADE"


def test_watchlist_monitor_uses_derivatives_and_supply_enrichment_without_triggering_fade():
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_router,
        event_watchlist,
        event_watchlist_enrichment,
        event_watchlist_monitor,
    )

    entry = _test_watchlist_entry(state="WATCHLIST", symbol="VELVET", coin_id="velvet")
    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=1,
        entries=[entry],
        latest_only=True,
    )
    enrichment = event_watchlist_enrichment.enrichment_for_watchlist(
        read,
        derivatives_source="fixture",
        supply_source="fixture",
        dex_liquidity_source="fixture",
        protocol_metrics_source="fixture",
        derivatives_rows=[{"coin_id": "velvet", "derivatives_crowding": 68}],
        supply_rows=[{"coin_id": "velvet", "supply_pressure": 72}],
        dex_liquidity_rows=[{"coin_id": "velvet", "pool_liquidity_usd": 500_000, "dex_volume_24h": 900_000}],
        protocol_metrics_rows=[{"coin_id": "velvet", "tvl_change_24h_pct": 0.12}],
    )
    assert enrichment.assets_requested == 1
    assert enrichment.derivatives["velvet"]["derivatives_crowding"] == 68
    assert enrichment.supply["velvet"]["supply_pressure"] == 72
    assert enrichment.dex_liquidity["velvet"]["pool_liquidity_usd"] == 500_000
    assert enrichment.protocol_metrics["velvet"]["tvl_change_24h_pct"] == 0.12
    monitored = event_watchlist_monitor.monitor_watchlist(
        read,
        derivatives_by_asset=enrichment.derivatives,
        supply_by_asset=enrichment.supply,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    row = monitored.rows[0]
    assert row.material_update is True
    assert "DERIVATIVES_HEATED" in row.state_transition_hints
    assert "SUPPLY_PRESSURE_UPGRADED" in row.state_transition_hints
    updated = event_watchlist_monitor.apply_monitor_updates_to_watchlist(read, monitored)
    updated_entry = updated.entries[0]
    assert updated_entry.state == event_watchlist.EventWatchlistState.WATCHLIST.value
    assert "derivatives_crowding_upgrade" in updated_entry.material_change_reasons
    assert "supply_pressure_upgrade" in updated_entry.material_change_reasons
    assert "score_jump" in updated_entry.material_change_reasons
    routed = event_alpha_router.route_watchlist(
        updated,
        cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
    )
    decision = routed.decisions[0]
    assert decision.alertable is True
    assert decision.route != event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH


def test_event_alpha_research_review_skipped_sample_dedupes_by_family():
    from crypto_rsi_scanner import event_alpha_notifications as notif

    skipped = [
        notif.EventAlphaResearchReviewSkippedItem(
            symbol="CHZ",
            coin_id="chiliz",
            core_opportunity_id=f"agg:chz-{idx}",
            candidate_family_id=f"world-cup:chiliz:{idx % 3}",
            score=70 - idx,
            rank_score=70 - idx,
            skip_reason="max_items",
            card_path=f"research_cards/chz_{idx}.md",
        )
        for idx in range(8)
    ]
    skipped.append(
        notif.EventAlphaResearchReviewSkippedItem(
            symbol="VELVET",
            coin_id="velvet",
            core_opportunity_id="agg:velvet-spacex",
            candidate_family_id="spacex:velvet",
            score=65,
            rank_score=65,
            skip_reason="max_items",
        )
    )
    skipped.append(
        notif.EventAlphaResearchReviewSkippedItem(
            symbol="SECTOR",
            coin_id="diagnostic",
            core_opportunity_id="diag:sector",
            candidate_family_id="sector:diagnostic",
            score=80,
            rank_score=80,
            skip_reason="sector_excluded",
            opportunity_type="DIAGNOSTIC",
        )
    )
    sample = notif._diverse_skipped_sample(skipped, limit=10)  # noqa: SLF001
    assert "VELVET" in [item.symbol for item in sample]
    assert len({item.candidate_family_id for item in sample}) >= 5
    candidate_summary = notif._research_review_skipped_family_summary(skipped)  # noqa: SLF001
    assert len([row for row in candidate_summary if str(row["candidate_family_id"]).startswith("world-cup:chiliz")]) == 3
    summary = notif._research_review_skipped_display_family_summary(skipped)  # noqa: SLF001
    by_label = {row["label"]: row for row in summary}
    assert by_label["CHZ/chiliz"]["skipped_count"] == 8
    assert by_label["CHZ/chiliz"]["sample_core_opportunity_ids"][:2] == ["agg:chz-0", "agg:chz-1"]
    assert by_label["CHZ/chiliz"]["representative_card_path"] == "research_cards/chz_0.md"
    assert by_label["VELVET/velvet"]["skipped_count"] == 1
    assert by_label["SECTOR/diagnostic"]["display_hidden"] is True
    display = notif._research_review_skipped_family_display(summary, limit=2)  # noqa: SLF001
    assert {row["label"] for row in display} == {"CHZ/chiliz", "VELVET/velvet"}


def test_event_catalyst_frames_separate_main_background_and_negation():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_catalyst_frames, event_claim_semantics, event_incident_graph
    from crypto_rsi_scanner.event_models import NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body, *, external="Aave"):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_news",
            fetched_at=now,
            published_at=now,
            source_url=f"https://alpha.example/{raw_id}",
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.90,
            content_hash=raw_id,
        ), NormalizedEvent(
            event_id=f"evt_{raw_id}",
            raw_ids=(raw_id,),
            event_name=title,
            event_type="news",
            event_time=None,
            event_time_confidence=0.0,
            first_seen_time=now,
            source="fixture_news",
            source_urls=(f"https://alpha.example/{raw_id}",),
            external_asset=external,
            description=title,
            confidence=0.90,
        )

    aave_raw, aave_event = raw(
        "aave_kraken",
        "Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        "The DeFi lender is rebuilding after the fallout from April's KelpDAO exploit "
        "sparked a multibillion-dollar exodus of deposits despite Aave itself not being hacked.",
    )
    frames = event_catalyst_frames.build_catalyst_frames((aave_raw,), event=aave_event)
    main, supporting = event_catalyst_frames.select_main_catalyst_frame(frames, aave_event)
    assert main is not None
    assert main.frame_role == "main_catalyst"
    assert main.frame_type == "acquisition_or_stake"
    assert main.subject == "Aave"
    assert main.actor == "Kraken"
    assert any(frame.frame_type == "prior_exploit_context" and frame.subject == "KelpDAO" for frame in supporting)
    assert any(frame.frame_type == "denied_or_negated_exploit" and frame.subject == "Aave" for frame in frames)
    aave_claims = event_claim_semantics.extract_event_claims((aave_raw,))
    assert event_claim_semantics.has_ruled_out_claim(aave_claims, "exploit")
    aave_incident = event_incident_graph.build_incidents((aave_event,), {"aave_kraken": aave_raw})[0]
    assert aave_incident.event_archetype == "strategic_investment"
    assert aave_incident.primary_subject == "Aave"
    assert aave_incident.main_frame_type == "acquisition_or_stake"
    assert aave_incident.background_frame_ids
    assert aave_incident.negated_frame_ids
    assert "KelpDAO" in (aave_incident.background_context_summary or "")

    thor_raw, thor_event = raw(
        "thor_exploit",
        "THORChain suffers exploit and RUNE resumes trading",
        "THORChain exploit drained funds before RUNE resumed trading.",
        external="THORChain",
    )
    thor_incident = event_incident_graph.build_incidents((thor_event,), {"thor_exploit": thor_raw})[0]
    assert thor_incident.event_archetype == "exploit_security_event"
    assert thor_incident.main_frame_type == "exploit_security_event"
    assert thor_incident.current_cause_status == "confirmed"

    meme_raw, meme_event = raw(
        "memecore_no_exploit",
        "MemeCore's M token crashes 80% with no exploit or announcement to explain it",
        "No exploit or announcement explains the M token selloff; cause unknown.",
        external="MemeCore",
    )
    meme_frames = event_catalyst_frames.build_catalyst_frames((meme_raw,), event=meme_event)
    meme_main, _ = event_catalyst_frames.select_main_catalyst_frame(meme_frames, meme_event)
    assert meme_main is not None
    assert meme_main.frame_type == "market_dislocation_unknown"
    assert any(frame.frame_type == "denied_or_negated_exploit" for frame in meme_frames)
    meme_incident = event_incident_graph.build_incidents((meme_event,), {"memecore_no_exploit": meme_raw})[0]
    assert meme_incident.event_archetype == "market_dislocation_unknown"
    assert meme_incident.current_cause_status == "ruled_out"


def test_aave_kraken_hypothesis_uses_strategic_frame_in_cards_and_audit():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_impact_hypotheses,
        event_opportunity_audit,
        event_research_cards,
        event_watchlist,
    )
    from crypto_rsi_scanner.event_models import (
        DiscoveredAsset,
        DiscoveredEventFadeCandidate,
        EventAssetLink,
        EventClassification,
        EventDiscoveryResult,
        NormalizedEvent,
        RawDiscoveredEvent,
    )

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="aave_kraken",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/aave-kraken",
        title="Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        body=(
            "The DeFi lender is rebuilding after the fallout from April's KelpDAO exploit "
            "sparked a multibillion-dollar exodus of deposits despite Aave itself not being hacked."
        ),
        raw_json={"market": {}},
        source_confidence=0.90,
        content_hash="aave_kraken",
    )
    event = NormalizedEvent(
        event_id="evt_aave_kraken",
        raw_ids=("aave_kraken",),
        event_name="Kraken stake in Aave",
        event_type="news",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source="fixture_news",
        source_urls=("https://alpha.example/aave-kraken",),
        external_asset="Aave",
        description=raw.title,
        confidence=0.90,
    )
    asset = DiscoveredAsset("aave", "AAVE", "Aave")
    link = EventAssetLink("evt_aave_kraken", "aave", "AAVE", "Aave", 0.95, "fixture", ("Aave",))
    classification = EventClassification(
        "evt_aave_kraken",
        "aave",
        False,
        True,
        "direct_token_event",
        0.90,
        "fixture",
        "Aave named as DeFi lender in strategic stake article",
        ("Aave",),
    )
    candidate = DiscoveredEventFadeCandidate(event, asset, link, classification, None, None, {})
    discovery = EventDiscoveryResult((raw,), (event,), (link,), (classification,), (candidate,))

    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(discovery, taxonomy={}, now=now)
    hypothesis = next(item for item in hypotheses if item.validated_candidate_assets)
    assert hypothesis.impact_category == "strategic_investment_or_valuation"
    assert hypothesis.impact_path_type == "strategic_investment_or_valuation"
    assert hypothesis.impact_path_reason == "strategic_investment"
    assert hypothesis.candidate_role == "direct_subject"
    assert hypothesis.event_archetype == "strategic_investment"
    assert hypothesis.main_frame_type == "acquisition_or_stake"
    assert hypothesis.background_frame_ids
    assert hypothesis.negated_frame_ids
    assert any("prior_exploit_context" in item for item in hypothesis.rejected_impact_paths)
    assert any("denied_or_negated_exploit" in item for item in hypothesis.rejected_impact_paths)
    assert hypothesis.opportunity_level == "validated_digest"
    assert hypothesis.why_not_watchlist == "market_confirmation"
    assert hypothesis.impact_path_type != "exploit_security_event"

    with tempfile.TemporaryDirectory() as tmp:
        watch = event_watchlist.refresh_hypothesis_watchlist(
            [hypothesis],
            cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=Path(tmp) / "watch.jsonl"),
            now=now,
        )
    entry = watch.entries[0]
    assert entry.state == event_watchlist.EventWatchlistState.RADAR.value
    assert entry.latest_score_components["main_frame_type"] == "acquisition_or_stake"
    assert "KelpDAO" in entry.latest_score_components["background_context_summary"]
    card = event_research_cards.render_research_card(entry.key, watchlist_entries=[entry])
    assert "Main catalyst: acquisition_or_stake" in card.markdown
    assert "Frame status:" in card.markdown
    assert "prior_exploit_context(KelpDAO)" in card.markdown
    assert "denied_or_negated_exploit" in card.markdown
    assert "Rejected/background impact paths:" in card.markdown
    assert "validated strategic investment / valuation catalyst" in card.markdown
    assert "Talks are denied" in card.markdown
    assert "event/catalyst relationship needs manual review" not in card.markdown
    assert "Source evidence fails identity/catalyst review" not in card.markdown
    audit = event_opportunity_audit.format_opportunity_audit(
        entry.key,
        hypotheses=[hypothesis],
        watchlist_entries=[entry],
        profile="quality_validation",
    )
    assert "main catalyst frame: acquisition_or_stake" in audit
    assert "frame status:" in audit
    assert "background context: background: prior_exploit_context(KelpDAO)" in audit
    assert "negated/corrective frame count: 1" in audit
    assert "rejected/background impact paths:" in audit


def test_llm_catalyst_frame_fixture_validation_and_downstream_use():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from crypto_rsi_scanner import (
        event_catalyst_frame_validator,
        event_catalyst_frames,
        event_impact_path_validator,
        event_incident_graph,
        event_llm_catalyst_frames,
    )
    from crypto_rsi_scanner.event_models import NormalizedEvent, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMCatalystFrameProvider

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body, *, external="Aave"):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_news",
            fetched_at=now,
            published_at=now,
            source_url=f"https://alpha.example/{raw_id}",
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.90,
            content_hash=raw_id,
        ), NormalizedEvent(
            event_id=f"evt_{raw_id}",
            raw_ids=(raw_id,),
            event_name=title,
            event_type="news",
            event_time=None,
            event_time_confidence=0.0,
            first_seen_time=now,
            source="fixture_news",
            source_urls=(f"https://alpha.example/{raw_id}",),
            external_asset=external,
            description=body,
            confidence=0.90,
        )

    provider = FixtureLLMCatalystFrameProvider(required=True)
    cfg = event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
        enabled=True,
        max_rows_per_run=10,
        min_source_score=0.0,
        only_ambiguous=False,
    )
    aave_raw, aave_event = raw(
        "aave_kraken",
        "Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        "The DeFi lender is rebuilding after the fallout from April's KelpDAO exploit "
        "sparked a multibillion-dollar exodus of deposits despite Aave itself not being hacked.",
    )
    report = event_llm_catalyst_frames.analyze_raw_events((aave_raw,), provider, cfg=cfg)
    assert report and report[0].analysis is not None
    analysis = report[0].analysis
    assert analysis.main_catalyst_frame is not None
    assert analysis.main_catalyst_frame.frame_type == "acquisition_or_stake"
    assert analysis.background_frames[0].frame_type == "prior_exploit_context"
    assert analysis.negated_or_corrective_frames[0].frame_type == "denied_or_negated_exploit"

    rule_exploit = event_catalyst_frames.EventCatalystFrame(
        frame_id="rule:exploit",
        frame_type="exploit_security_event",
        frame_role="main_catalyst",
        subject="Aave",
        event_archetype="exploit_security_event",
        claim_polarity="asserted",
        cause_status="confirmed",
        confidence=0.80,
        evidence_quote="KelpDAO exploit",
    )
    validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(
        analysis,
        (aave_raw,),
        event=aave_event,
        rule_frames=(rule_exploit,),
    )
    assert validation.selected_main_frame is not None
    assert validation.selected_main_frame.frame_type == "acquisition_or_stake"
    assert validation.frame_rule_disagreement is True
    assert validation.resolution == "llm_wins"
    assert any("prior_exploit_context" in item for item in validation.rejected_impact_paths)
    assert any("denied_or_negated_exploit" in item for item in validation.rejected_impact_paths)

    enriched_raw = event_catalyst_frame_validator.apply_validation_to_raw_event(aave_raw, analysis, validation)
    incident = event_incident_graph.build_incidents((aave_event,), {enriched_raw.raw_id: enriched_raw})[0]
    assert incident.event_archetype == "strategic_investment"
    assert incident.main_frame_type == "acquisition_or_stake"
    assert incident.main_frame_role == "main_catalyst"
    assert incident.main_frame_subject == "Aave"
    assert incident.main_frame_actor == "Kraken"
    assert "15% stake" in (incident.main_frame_object or "")
    assert "Kraken in talks" in (incident.main_frame_evidence_quote or "")
    assert incident.background_frame_ids
    assert incident.corrective_frame_ids
    assert incident.frame_rule_disagreement is True
    assert incident.rule_predicted_impact_path == "exploit_security_event"
    assert incident.llm_predicted_main_frame_type == "acquisition_or_stake"
    assert incident.disagreement_resolution == "llm_wins"
    impact = event_impact_path_validator.validate_impact_path(
        enriched_raw,
        SimpleNamespace(impact_category="security_or_regulatory_shock", external_asset="Aave", score_components={}),
        symbol="AAVE",
        coin_id="aave",
    )
    assert impact.impact_path_type == "strategic_investment_or_valuation"
    assert impact.impact_path_type != "exploit_security_event"

    thor_raw, _ = raw(
        "thor_exploit",
        "THORChain suffers exploit and RUNE resumes trading",
        "THORChain exploit drained funds before RUNE resumed trading.",
        external="THORChain",
    )
    thor_report = event_llm_catalyst_frames.analyze_raw_events((thor_raw,), provider, cfg=cfg)
    thor_validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(thor_report[0].analysis, (thor_raw,))
    assert thor_validation.selected_main_frame is not None
    assert thor_validation.selected_main_frame.frame_type == "exploit_security_event"
    assert thor_validation.frame_rule_disagreement is False


def test_llm_catalyst_frame_runtime_deadline_skips_and_bounds_timeout():
    from datetime import datetime, timedelta, timezone
    from crypto_rsi_scanner import event_llm_catalyst_frames
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="aave_kraken_deadline",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/aave-deadline",
        title="Kraken considers strategic stake in Aave",
        body="Kraken could acquire a stake in Aave after earlier exploit context.",
        raw_json={},
        source_confidence=0.90,
        content_hash="aave_kraken_deadline",
    )

    class ProbeProvider:
        name = "probe"

        def __init__(self):
            self.timeout = 30.0
            self.calls = 0
            self.seen_timeouts = []

        def analyze_catalyst_frames(self, packet):
            self.calls += 1
            self.seen_timeouts.append(float(self.timeout))
            return LLMProviderResult(warning="probe warning")

    expired_provider = ProbeProvider()
    expired_rows = event_llm_catalyst_frames.analyze_raw_events(
        (raw,),
        expired_provider,
        cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=True,
            max_rows_per_run=1,
            min_source_score=0.0,
            only_ambiguous=False,
            deadline_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        ),
    )
    assert expired_provider.calls == 0
    assert expired_rows
    assert any("runtime deadline exhausted" in warning for warning in expired_rows[0].warnings)

    bounded_provider = ProbeProvider()
    bounded_rows = event_llm_catalyst_frames.analyze_raw_events(
        (raw,),
        bounded_provider,
        cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=True,
            max_rows_per_run=1,
            min_source_score=0.0,
            only_ambiguous=False,
            deadline_at=datetime.now(timezone.utc) + timedelta(seconds=5),
        ),
    )
    assert bounded_provider.calls == 1
    assert bounded_rows and any("probe warning" in warning for warning in bounded_rows[0].warnings)
    assert 1.0 <= bounded_provider.seen_timeouts[0] <= 5.0
    assert bounded_provider.timeout == 30.0


def test_event_alpha_operating_cycle_applies_llm_catalyst_frame_validation():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alpha_pipeline,
        event_catalyst_frames,
        event_incident_graph,
        event_llm_catalyst_frames,
    )
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMCatalystFrameProvider

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="aave_kraken",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/aave",
        title="Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        body=(
            "The DeFi lender is rebuilding after the fallout from April's KelpDAO exploit "
            "sparked a multibillion-dollar exodus of deposits despite Aave itself not being hacked."
        ),
        raw_json={},
        source_confidence=0.90,
        content_hash="aave_kraken",
    )
    event = NormalizedEvent(
        event_id="evt_aave_kraken",
        raw_ids=("aave_kraken",),
        event_name=raw.title,
        event_type="news",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source="fixture_news",
        source_urls=(raw.source_url or "",),
        external_asset="Aave",
        description=raw.body,
        confidence=0.90,
    )

    def load_discovery_result(observed, raw_event_transform):
        raw_events = (raw,)
        if raw_event_transform is not None:
            raw_events = tuple(raw_event_transform(raw_events))
        return EventDiscoveryResult(
            raw_events=raw_events,
            normalized_events=(event,),
            links=(),
            classifications=(),
            candidates=(),
        )

    result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=load_discovery_result,
        now=now,
        with_llm=True,
        catalyst_frame_provider=FixtureLLMCatalystFrameProvider(required=True),
        catalyst_frame_cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=True,
            max_rows_per_run=10,
            min_source_score=0.0,
            only_ambiguous=False,
        ),
        refresh_watchlist=False,
        route=False,
    )

    assert result.catalyst_frame_analyses == 1
    assert result.catalyst_frame_validations_applied == 1
    enriched_raw = result.discovery_result.raw_events[0]
    validation = enriched_raw.raw_json["llm_catalyst_frame_validation"]
    assert validation["selected_main_frame"]["frame_type"] == "acquisition_or_stake"
    assert validation["rule_predicted_impact_path"] == "acquisition_or_stake"
    assert validation["llm_predicted_main_frame_type"] == "acquisition_or_stake"
    frames = event_catalyst_frames.build_catalyst_frames((enriched_raw,), event=event)
    selected_main, supporting_frames = event_catalyst_frames.select_main_catalyst_frame(frames)
    assert selected_main is not None
    assert selected_main.frame_type == "acquisition_or_stake"
    assert any(frame.frame_type == "prior_exploit_context" for frame in supporting_frames)
    incident = event_incident_graph.build_incidents((event,), {enriched_raw.raw_id: enriched_raw})[0]
    assert incident.event_archetype == "strategic_investment"
    assert incident.background_frame_ids
    assert incident.main_frame_subject == "Aave"
    assert incident.corrective_frame_ids


def test_llm_catalyst_frame_validator_rejects_bad_quotes_and_identity_noise():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_catalyst_frame_validator, event_llm_catalyst_frames
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMCatalystFrameProvider

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    invalid_raw = RawDiscoveredEvent(
        raw_id="invalid_quote",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/invalid",
        title="Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        body="The source says Aave itself was not hacked.",
        raw_json={},
        source_confidence=0.90,
        content_hash="invalid_quote",
    )
    cfg = event_llm_catalyst_frames.EventLLMCatalystFrameConfig(enabled=True, only_ambiguous=False, min_source_score=0.0)
    provider = FixtureLLMCatalystFrameProvider(required=True)
    report = event_llm_catalyst_frames.analyze_raw_events((invalid_raw,), provider, cfg=cfg)
    validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(report[0].analysis, (invalid_raw,))
    assert validation.selected_main_frame is None
    assert validation.invalid_frames[0]["reason"] == "llm_frame_quote_not_found"

    packet = event_llm_catalyst_frames.build_catalyst_frame_packet(invalid_raw, cfg=cfg)
    openai_noise = event_llm_catalyst_frames.parse_catalyst_frame_analysis(
        {
            "main_catalyst_frame": {
                "frame_type": "proxy_attention",
                "frame_role": "main_catalyst",
                "subject": "OpenAI",
                "actor": None,
                "object": "pre-IPO mention",
                "affected_entities": ["OpenAI"],
                "affected_assets": ["OpenAI"],
                "event_archetype": "proxy_attention",
                "claim_polarity": "asserted",
                "cause_status": "unknown",
                "confidence": 0.80,
                "evidence_quote": "Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
                "why_this_role": "identity-noise test",
            },
            "background_frames": [],
            "negated_or_corrective_frames": [],
            "external_entities": ["OpenAI"],
            "crypto_assets": ["OpenAI"],
            "rejected_impact_paths": [],
            "manual_verification_items": [],
            "semantic_confidence": 0.70,
            "warnings": [],
        },
        packet=packet,
        cfg=cfg,
    )
    openai_validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(openai_noise, (invalid_raw,))
    assert openai_validation.invalid_frames[0]["reason"] == "external_entity_cannot_be_crypto_asset"

    hype_noise = event_llm_catalyst_frames.parse_catalyst_frame_analysis(
        {
            "main_catalyst_frame": {
                "frame_type": "proxy_attention",
                "frame_role": "main_catalyst",
                "subject": "HYPE",
                "actor": None,
                "object": "IPO hype",
                "affected_entities": ["HYPE"],
                "affected_assets": ["HYPE"],
                "event_archetype": "proxy_attention",
                "claim_polarity": "asserted",
                "cause_status": "unknown",
                "confidence": 0.80,
                "evidence_quote": "Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
                "why_this_role": "generic ticker-noise test",
            },
            "background_frames": [],
            "negated_or_corrective_frames": [],
            "external_entities": [],
            "crypto_assets": ["HYPE"],
            "rejected_impact_paths": [],
            "manual_verification_items": [],
            "semantic_confidence": 0.70,
            "warnings": [],
        },
        packet=packet,
        cfg=cfg,
    )
    hype_validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(hype_noise, (invalid_raw,))
    assert hype_validation.invalid_frames[0]["reason"] == "ticker_word_collision_rejected"


def test_llm_catalyst_frame_profiles_make_target_and_missing_key_fail_soft():
    import subprocess
    from crypto_rsi_scanner import event_alpha_profiles
    from crypto_rsi_scanner.llm_providers.openai_provider import OpenAILLMRelationshipProvider

    assert event_alpha_profiles.get_profile("notify_no_key").config_overrides["EVENT_LLM_CATALYST_FRAMES_ENABLED"] is False
    assert event_alpha_profiles.get_profile("notify_llm_quality").config_overrides["EVENT_LLM_CATALYST_FRAMES_ENABLED"] is True
    assert event_alpha_profiles.get_profile("notify_llm_deep").config_overrides["EVENT_LLM_CATALYST_FRAMES_ENABLED"] is True
    assert event_alpha_profiles.get_profile("notify_llm_deep").config_overrides["EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN"] == 60
    assert event_alpha_profiles.get_profile("notify_llm_deep").config_overrides["EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED"] is True
    assert event_alpha_profiles.get_profile("full_llm_live").config_overrides["EVENT_LLM_CATALYST_FRAMES_ENABLED"] is True
    assert event_alpha_profiles.get_profile("catalyst_frame_validation").config_overrides["EVENT_LLM_CATALYST_FRAMES_PROVIDER"] == "fixture"
    assert event_alpha_profiles.get_profile("catalyst_frame_validation").with_llm is True
    e2e = event_alpha_profiles.get_profile("catalyst_frame_e2e")
    assert e2e.with_llm is True
    assert e2e.send is False
    assert e2e.config_overrides["EVENT_LLM_CATALYST_FRAMES_PROVIDER"] == "fixture"
    assert str(e2e.config_overrides["EVENT_DISCOVERY_EVENTS_PATH"]).endswith("catalyst_frame_e2e_events.json")
    assert e2e.config_overrides["EVENT_ANOMALY_SCANNER_ENABLED"] is False
    assert e2e.config_overrides["EVENT_DISCOVERY_UNIVERSE_LIVE"] is False
    quality_frame = event_alpha_profiles.get_profile("notify_llm_quality_frame")
    assert quality_frame.with_llm is True
    assert quality_frame.send is False
    assert quality_frame.config_overrides["EVENT_LLM_CATALYST_FRAMES_PROVIDER"] == "fixture"
    assert quality_frame.config_overrides["EVENT_LLM_CATALYST_FRAMES_ENABLED"] is True
    assert quality_frame.config_overrides["EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED"] is True
    assert quality_frame.config_overrides["EVENT_ALPHA_SNAPSHOT_POLICY"] == "all"
    quality_frame_report = event_alpha_profiles.format_profile_report(quality_frame)
    assert "catalyst-frame behavior:" in quality_frame_report
    assert "- provider=fixture" in quality_frame_report
    assert "official fixture/no-send proof profile" in quality_frame_report
    market_refresh = event_alpha_profiles.get_profile("market_refresh_smoke")
    assert market_refresh.send is False
    assert market_refresh.config_overrides["EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED"] is True
    assert market_refresh.config_overrides["EVENT_WATCHLIST_MONITOR_MARKET_SOURCE"] == "fixture"
    assert str(market_refresh.config_overrides["EVENT_WATCHLIST_MONITOR_MARKET_PATH"]).endswith("market_refresh_smoke_markets.json")
    quality_live_report = event_alpha_profiles.format_profile_report(event_alpha_profiles.get_profile("notify_llm_quality"))
    assert "official live-style frame-enabled quality profile" in quality_live_report
    report = event_alpha_profiles.format_profile_report(event_alpha_profiles.get_profile("notify_llm_deep"))
    assert "EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN=60" in report
    provider = OpenAILLMRelationshipProvider(api_key="")
    result = provider.analyze_catalyst_frames({"raw_id": "missing-key"})
    assert result.raw is None
    assert "missing OPENAI_API_KEY" in (result.warning or "")
    with open("Makefile", encoding="utf-8") as fh:
        text = fh.read()
    assert "event-alpha-catalyst-frame-validation-cycle" in text
    assert "event-alpha-catalyst-frame-e2e-cycle" in text
    assert "event-alpha-notify-llm-quality-frame-smoke" in text
    assert "event-alpha-market-refresh-smoke" in text
    assert "event-alpha-quality-frame-live-smoke" in text
    assert "event-alpha-feedback-readiness" in text
    assert "event-alpha-frame-quality-loop" in text
    dry = subprocess.run(
        ["make", "-n", "event-alpha-quality-frame-live-smoke", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alert-send" not in dry
    assert "--event-alpha-cycle --event-alpha-profile notify_llm_quality" in dry


def test_event_alpha_catalyst_frame_e2e_cycle_writes_frame_artifacts():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    original = {
        name: getattr(config, name)
        for name in dir(config)
        if name.startswith(("EVENT_", "TELEGRAM_"))
    }

    def read_jsonl(path):
        return [
            json.loads(line)
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    with tempfile.TemporaryDirectory() as tmp:
        config.EVENT_ALPHA_ARTIFACT_BASE_DIR = Path(tmp)
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
        config.EVENT_ALPHA_RUN_MODE = ""
        config.EVENT_ALERTS_ENABLED = False
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_cycle(profile_name="catalyst_frame_e2e", event_now="2026-06-15T16:00:00Z")
            text = out.getvalue()
            assert "EVENT ALPHA PIPELINE REPORT" in text
            assert "catalyst_frames=5/5" in text
            assert "send_attempted=false" in text
            with contextlib.redirect_stdout(io.StringIO()):
                scanner.event_alpha_daily_brief_report(
                    profile_name="catalyst_frame_e2e",
                    artifact_namespace="catalyst_frame_e2e",
                    include_test_artifacts=True,
            )
            daily_brief = Path(config.EVENT_ALPHA_DAILY_BRIEF_PATH).read_text(encoding="utf-8")
            assert "No run ledger rows found" not in daily_brief
            assert "Selected run profile: catalyst_frame_e2e" in daily_brief
            assert "Selected run namespace: catalyst_frame_e2e" in daily_brief

            incident_rows = read_jsonl(config.EVENT_INCIDENT_STORE_PATH)
            hypothesis_rows = read_jsonl(config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH)
            watchlist_rows = read_jsonl(config.EVENT_WATCHLIST_STATE_PATH)
            run_rows = read_jsonl(config.EVENT_ALPHA_RUN_LEDGER_PATH)
            assert incident_rows
            assert hypothesis_rows
            assert watchlist_rows
            assert run_rows[-1]["profile"] == "catalyst_frame_e2e"
            assert run_rows[-1]["send_requested"] is False
            assert run_rows[-1]["catalyst_frames_analyzed"] == 5
            assert run_rows[-1]["catalyst_frame_validations"] == 5

            aave_incident = next(row for row in incident_rows if row.get("main_frame_subject") == "Aave")
            assert aave_incident["event_archetype"] == "strategic_investment"
            assert aave_incident["main_frame_type"] == "acquisition_or_stake"
            assert aave_incident["main_frame_actor"] == "Kraken"
            assert aave_incident["corrective_frame_ids"]
            assert aave_incident["main_frame_type"] != "exploit_security_event"

            aave_hypothesis = next(row for row in hypothesis_rows if row.get("main_frame_subject") == "Aave")
            assert aave_hypothesis["main_frame_type"] == "acquisition_or_stake"
            assert aave_hypothesis["impact_path_reason"] == "strategic_investment"
            assert aave_hypothesis["impact_path_type"] == "strategic_investment_or_valuation"
            assert "prior_exploit_context:background_for:KelpDAO" in aave_hypothesis["rejected_impact_paths"]
            assert "background_context_not_primary_catalyst" in aave_hypothesis["rejected_impact_paths"]
            assert aave_hypothesis["selected_main_catalyst_reason"]

            thor_incident = next(row for row in incident_rows if row.get("main_frame_subject") == "THORChain")
            assert thor_incident["main_frame_type"] == "exploit_security_event"
            memecore_incident = next(row for row in incident_rows if row.get("main_frame_subject") == "MemeCore")
            assert memecore_incident["event_archetype"] == "market_dislocation_unknown"
            assert all(row.get("latest_tier") != "TRIGGERED_FADE" for row in watchlist_rows)
            card_files = list(Path(config.EVENT_RESEARCH_CARDS_DIR).glob("*.md"))
            assert card_files
            assert "Main catalyst: acquisition_or_stake" in card_files[0].read_text(encoding="utf-8") or any(
                "Main catalyst: acquisition_or_stake" in path.read_text(encoding="utf-8")
                for path in card_files
            )

            notify_out = io.StringIO()
            with contextlib.redirect_stdout(notify_out):
                scanner.event_alpha_cycle(
                    profile_name="notify_llm_quality_frame",
                    event_now="2026-06-15T16:00:00Z",
                )
            notify_text = notify_out.getvalue()
            assert "catalyst_frames=5/5" in notify_text
            notify_run_rows = read_jsonl(config.EVENT_ALPHA_RUN_LEDGER_PATH)
            notify_latest = notify_run_rows[-1]
            assert notify_latest["profile"] == "notify_llm_quality_frame"
            assert notify_latest["send_requested"] is False
            assert isinstance(notify_latest["catalyst_frames_analyzed"], int)
            assert isinstance(notify_latest["catalyst_frame_validations"], int)
            assert isinstance(notify_latest["catalyst_frame_disagreements"], int)
            assert isinstance(notify_latest["catalyst_frame_unresolved"], int)
            assert isinstance(notify_latest["catalyst_frame_rows_skipped"], int)
            assert isinstance(notify_latest["catalyst_frame_skip_reasons"], dict)
            assert notify_latest["catalyst_frames_analyzed"] == 5
            assert notify_latest["catalyst_frame_validations"] == 5
            notify_incidents = read_jsonl(config.EVENT_INCIDENT_STORE_PATH)
            notify_aave = next(row for row in notify_incidents if row.get("main_frame_subject") == "Aave")
            assert notify_aave["event_archetype"] == "strategic_investment"
            assert notify_aave["main_frame_type"] == "acquisition_or_stake"
            assert notify_aave["main_frame_actor"] == "Kraken"
            assert notify_aave["main_frame_type"] != "exploit_security_event"
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_catalyst_frame_missing_provider_records_skip_and_status():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_pipeline, event_alpha_run_ledger, event_llm_catalyst_frames
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="aave_kraken",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/aave",
        title="Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        body="The article also references the fallout from a prior KelpDAO exploit despite Aave itself not being hacked.",
        raw_json={},
        source_confidence=0.90,
        content_hash="aave",
    )
    event = NormalizedEvent(
        "evt_aave",
        ("aave_kraken",),
        raw.title,
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (raw.source_url or "",),
        "Aave",
        raw.body,
        0.90,
    )

    def load_discovery_result(observed, raw_event_transform):
        raws = (raw,)
        if raw_event_transform is not None:
            raws = tuple(raw_event_transform(raws))
        return EventDiscoveryResult(raws, (event,), (), (), ())

    result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=load_discovery_result,
        now=now,
        with_llm=True,
        catalyst_frame_provider=None,
        catalyst_frame_cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=True,
            provider="openai",
            only_ambiguous=True,
        ),
        refresh_watchlist=False,
        route=False,
    )
    payload = result.discovery_result.raw_events[0].raw_json
    assert payload["catalyst_frame_required"] is True
    assert payload["catalyst_frame_status"] == "missing_required_frame_analysis"
    assert payload["catalyst_frame_skip_reason"] == "missing_api_key"

    with tempfile.TemporaryDirectory() as tmp:
        row = event_alpha_run_ledger.append_run_record(
            result,
            cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(Path(tmp) / "runs.jsonl"),
            profile="notify_llm_quality",
            started_at=now,
            finished_at=now,
            with_llm=True,
            send_requested=False,
        )
    assert row["catalyst_frames_analyzed"] == 0
    assert row["catalyst_frame_validations"] == 0
    assert row["catalyst_frame_rows_skipped"] == 1
    assert row["catalyst_frame_skip_reasons"]["missing_api_key"] == 1


def test_catalyst_frame_missing_key_and_disabled_modes_record_clear_skip_reasons():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from crypto_rsi_scanner import event_alpha_pipeline, event_alpha_run_ledger, event_llm_catalyst_frames
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.openai_provider import OpenAILLMRelationshipProvider

    now = datetime(2026, 6, 27, 12, 30, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="aave_kraken_missing_key",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/aave-missing-key",
        title="Kraken in talks to buy 15% stake in Aave at $385 million valuation",
        body="The article references KelpDAO exploit fallout but says Aave itself was not hacked.",
        raw_json={},
        source_confidence=0.95,
        content_hash="aave-missing-key",
    )
    event = NormalizedEvent(
        "evt_aave_missing_key",
        (raw.raw_id,),
        raw.title,
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (raw.source_url or "",),
        "Aave",
        raw.body,
        0.95,
    )

    def load_discovery_result(observed, raw_event_transform):
        raws = (raw,)
        if raw_event_transform is not None:
            raws = tuple(raw_event_transform(raws))
        return EventDiscoveryResult(raws, (event,), (), (), ())

    missing_key_result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=load_discovery_result,
        now=now,
        with_llm=True,
        catalyst_frame_provider=OpenAILLMRelationshipProvider(api_key="", model="fixture"),
        catalyst_frame_cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=True,
            provider="openai",
            only_ambiguous=True,
        ),
        refresh_watchlist=False,
        route=False,
    )
    missing_payload = missing_key_result.discovery_result.raw_events[0].raw_json
    assert missing_payload["catalyst_frame_status"] == "missing_required_frame_analysis"
    assert missing_payload["catalyst_frame_skip_reason"] == "missing_api_key"

    disabled_result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=load_discovery_result,
        now=now,
        with_llm=True,
        catalyst_frame_provider=None,
        catalyst_frame_cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=False,
            provider="openai",
            only_ambiguous=True,
        ),
        refresh_watchlist=False,
        route=False,
    )
    disabled_payload = disabled_result.discovery_result.raw_events[0].raw_json
    assert disabled_payload["catalyst_frame_status"] == "missing_required_frame_analysis"
    assert disabled_payload["catalyst_frame_skip_reason"] == "disabled"

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "runs.jsonl"
        missing_row = event_alpha_run_ledger.append_run_record(
            missing_key_result,
            cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(path),
            profile="notify_llm_quality",
            started_at=now,
            finished_at=now,
            with_llm=True,
            send_requested=False,
        )
        disabled_row = event_alpha_run_ledger.append_run_record(
            disabled_result,
            cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(path),
            profile="notify_llm_quality",
            started_at=now,
            finished_at=now,
            with_llm=True,
            send_requested=False,
        )
        legacy_path = Path(tmp) / "legacy.jsonl"
        legacy_path.write_text(
            '{"row_type":"event_alpha_run","started_at":"2026-06-27T00:00:00+00:00",'
            '"catalyst_frames_analyzed":null,"catalyst_frame_validations":null,'
            '"catalyst_frame_disagreements":null,"catalyst_frame_unresolved":null,'
            '"catalyst_frame_rows_skipped":null,"catalyst_frame_skip_reasons":null}\n',
            encoding="utf-8",
        )
        legacy = event_alpha_run_ledger.load_run_records(legacy_path).rows[0]
    assert missing_row["catalyst_frames_analyzed"] == 0
    assert missing_row["catalyst_frame_skip_reasons"]["missing_api_key"] == 1
    assert disabled_row["catalyst_frame_skip_reasons"]["disabled"] == 1
    assert legacy["catalyst_frames_analyzed"] == 0
    assert legacy["catalyst_frame_validations"] == 0
    assert legacy["catalyst_frame_disagreements"] == 0
    assert legacy["catalyst_frame_unresolved"] == 0
    assert legacy["catalyst_frame_rows_skipped"] == 0
    assert legacy["catalyst_frame_skip_reasons"] == {}


def test_incident_asset_roles_demote_unvalidated_taxonomy_candidates():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_incident_graph, event_incident_store
    from crypto_rsi_scanner.event_models import NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        "thor_exploit",
        "fixture_news",
        now,
        now,
        "https://alpha.example/thor",
        "THORChain confirms RUNE exploit after attack",
        "THORChain confirms a RUNE exploit and security incident after an attack; RUNE trading reacts sharply.",
        {},
        0.90,
        "thor",
    )
    event = NormalizedEvent(
        "evt_thor",
        ("thor_exploit",),
        "THORChain RUNE exploit",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (raw.source_url or "",),
        "THORChain",
        raw.body,
        0.90,
    )
    incident = event_incident_graph.build_incidents((event,), {raw.raw_id: raw})[0]
    rows = event_incident_store._linked_assets(
        [
            {
                "candidate_symbols": ["LINK", "PYTH", "RUNE"],
                "candidate_coin_ids": ["chainlink", "pyth-network", "thorchain"],
                "candidate_role": "direct_subject",
                "candidate_source": "taxonomy",
                "crypto_candidate_assets": [
                    {"symbol": "LINK", "coin_id": "chainlink", "source": "taxonomy", "validated": False},
                    {"symbol": "PYTH", "coin_id": "pyth-network", "source": "taxonomy", "validated": False},
                ],
            },
            {
                "validated_symbol": "RUNE",
                "validated_coin_id": "thorchain",
                "candidate_role": "direct_subject",
                "validated_asset": {"symbol": "RUNE", "coin_id": "thorchain", "validated": True},
            },
        ],
        [],
        incident=incident,
    )
    assert any(asset["symbol"] == "RUNE" and asset["role"] == "direct_subject" for asset in rows)
    assert not any(asset["symbol"] == "LINK" and asset["role"] == "direct_subject" for asset in rows)
    assert any(asset["symbol"] == "LINK" and asset["role"] == "taxonomy_candidate" for asset in rows)


def test_validated_hypothesis_aggregation_preserves_supporting_paths():
    from crypto_rsi_scanner import event_impact_hypotheses

    base = dict(
        event_cluster_id="incident:spacex",
        event_type="news",
        external_asset="SpaceX",
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        validated_candidate_assets=({"symbol": "VELVET", "coin_id": "velvet", "validated": True},),
        crypto_candidate_assets=({"symbol": "VELVET", "coin_id": "velvet", "validated": True},),
        candidate_source="hypothesis_search",
        hypothesis_scope="token",
        direction_hint="up_then_fade",
        confidence=0.86,
        hypothesis_score=86.0,
        validation_stage="impact_path_validated",
        status="validated",
        incident_id="incident:spacex",
        candidate_role="proxy_venue",
        impact_path_type="venue_value_capture",
        impact_path_reason="venue_value_capture",
        opportunity_score_final=88,
        opportunity_level="high_priority",
    )
    first = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:velvet:rwa",
        impact_category="rwa_preipo_proxy",
        evidence_quotes=("VELVET users can trade SpaceX pre-IPO exposure.",),
        **base,
    )
    second = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:velvet:venue",
        impact_category="tokenized_stock_venue",
        evidence_quotes=("Velvet is the venue for tokenized SpaceX exposure.",),
        **base,
    )
    out = event_impact_hypotheses._dedupe_hypotheses((first, second))
    assert len(out) == 1
    item = out[0]
    assert item.aggregated_candidate_id
    assert item.supporting_hypothesis_count == 2
    assert set(item.supporting_categories) == {"rwa_preipo_proxy", "tokenized_stock_venue"}
    assert item.supporting_impact_paths == ("venue_value_capture",)
    assert "VELVET users can trade SpaceX pre-IPO exposure." in item.supporting_evidence_quotes


def test_event_core_opportunities_aggregate_duplicates_and_hide_controls():
    from crypto_rsi_scanner import event_alpha_router, event_core_opportunities, event_watchlist

    def row(symbol, *, category, path, role="proxy_venue", route="STORE_ONLY", level="local_only", score=58, playbook="proxy_attention"):
        return {
            "incident_id": "incident:spacex",
            "canonical_incident_name": "SpaceX pre-IPO exposure",
            "validated_symbol": symbol,
            "validated_coin_id": symbol.lower(),
            "candidate_role": role,
            "impact_category": category,
            "impact_path_type": path,
            "opportunity_level": level,
            "opportunity_score_final": score,
            "final_route_after_quality_gate": route,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
            if level == "high_priority"
            else event_watchlist.EventWatchlistState.RADAR.value,
            "latest_effective_playbook_type": playbook,
            "hypothesis_id": f"hyp:{symbol}:{category}",
            "evidence_quotes": [f"{symbol} evidence for {category}"],
        }

    rows = [
        row(
            "VELVET",
            category="tokenized_stock_venue",
            path="venue_value_capture",
            route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            level="high_priority",
            score=94,
        ),
        {
            **row("VELVET", category="rwa_preipo_proxy", path="proxy_exposure", score=67),
            "incident_id": "incident:spacex-alt-headline",
            "hypothesis_id": "hyp:VELVET:rwa_preipo_proxy_alt_headline",
        },
        {
            **row("VELVET", category="unknown", path="insufficient_data", role="unknown_with_reason", score=0),
            "opportunity_level": "local_only",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value,
            "state_quality_capped": True,
            "quality_state_block_reason": "impact_path_type_insufficient_data",
            "hypothesis_id": "hyp:VELVET:quality-capped-support",
        },
        row(
            "VELVET",
            category="publisher_noise",
            path="generic_cooccurrence_only",
            role="source_noise",
            playbook="source_noise_control",
        ),
        row("AAVE", category="strategic_investment", path="strategic_investment_or_valuation", role="direct_subject", score=72, level="validated_digest", route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value),
        row("RUNE", category="security_or_regulatory_shock", path="exploit_security_event", role="direct_subject", score=80, level="watchlist"),
        row("ZEC", category="listing_liquidity", path="listing_liquidity_event", role="direct_subject", score=70, level="validated_digest"),
    ]

    opportunities = event_core_opportunities.aggregate_core_opportunities(rows)
    velvet = [item for item in opportunities if item.symbol == "VELVET"]
    assert len(velvet) == 1
    assert velvet[0].final_route_after_quality_gate == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    assert {"tokenized_stock_venue", "rwa_preipo_proxy"} <= set(velvet[0].supporting_categories)
    assert "hyp:VELVET:rwa_preipo_proxy_alt_headline" in velvet[0].supporting_hypothesis_ids
    assert velvet[0].source_noise_control_count == 1
    assert velvet[0].diagnostic_row_count == 2
    assert velvet[0].quality_capped_supporting_rows == 1
    assert len([item for item in opportunities if item.symbol == "AAVE"]) == 1
    assert len([item for item in opportunities if item.symbol == "RUNE"]) == 1
    assert len([item for item in opportunities if item.symbol == "ZEC"]) == 1


def test_daily_brief_core_opportunity_excludes_promoted_supporting_near_miss():
    from dataclasses import replace
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_daily_brief, event_alpha_router, event_watchlist

    components = {
        "incident_id": "incident:spacex",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "validation_stage": "impact_path_validated",
        "impact_category": "tokenized_stock_venue",
        "impact_path_type": "venue_value_capture",
        "impact_path_strength": "strong",
        "candidate_role": "proxy_venue",
        "evidence_quality_score": 90,
        "source_class": "crypto_native",
        "evidence_specificity": "asset_and_catalyst",
        "market_confirmation_score": 90,
        "market_confirmation_level": "strong",
        "opportunity_score_final": 94,
        "opportunity_level": "high_priority",
        "supporting_categories": ["tokenized_stock_venue", "rwa_preipo_proxy"],
        "supporting_impact_paths": ["venue_value_capture", "proxy_exposure"],
        "supporting_evidence_quotes": ["VELVET users can trade SpaceX pre-IPO exposure."],
    }
    entry = replace(
        _test_watchlist_entry(state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value, symbol="VELVET", coin_id="velvet"),
        key="incident:spacex|velvet|proxy_venue",
        incident_id="incident:spacex",
        relationship_type="impact_hypothesis",
        latest_score=94,
        highest_score=94,
        latest_score_components=components,
        should_alert=True,
        material_change_reasons=("initial_validated_hypothesis",),
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="Validated impact hypothesis reached high-priority opportunity verdict (94).",
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
        final_route_after_quality_gate=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        opportunity_level="high_priority",
        opportunity_score_final=94,
    )
    near_support_row = {
        "hypothesis_id": "hyp:velvet:support",
        "incident_id": "incident:spacex",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "impact_category": "rwa_preipo_proxy",
        "impact_path_type": "proxy_exposure",
        "impact_path_strength": "medium",
        "evidence_quality_score": 70,
        "source_class": "crypto_native",
        "evidence_specificity": "asset_and_catalyst",
        "market_confirmation_score": 40,
        "market_confirmation_level": "weak",
        "opportunity_score_final": 61,
        "opportunity_level": "exploratory",
        "why_not_watchlist": "needs_market_confirmation",
        "upgrade_requirements": ["market_confirmation"],
    }
    brief = event_alpha_daily_brief.build_daily_brief(
        run_rows=[],
        hypothesis_rows=[near_support_row],
        watchlist_entries=[entry],
        router_result=event_alpha_router.EventAlphaRouterResult(Path("state.jsonl"), 1, [decision], True),
        requested_profile="fixture",
    )
    assert "core_" in brief
    assert "VELVET/velvet" in brief
    near_section = brief.split("## Near-Miss Candidates", 1)[1].split("## Quality-Capped / Local-Only Candidates", 1)[0]
    assert "VELVET/velvet" not in near_section


def test_daily_brief_core_sections_hide_promoted_from_exploratory_and_near_miss():
    from dataclasses import replace
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_daily_brief, event_alpha_router, event_watchlist

    def decision(symbol, *, state, route, level, score, path, incident):
        components = {
            "incident_id": incident,
            "validated_symbol": symbol,
            "validated_coin_id": symbol.lower(),
            "validation_stage": "impact_path_validated",
            "impact_category": path,
            "impact_path_type": path,
            "impact_path_strength": "strong",
            "candidate_role": "direct_subject",
            "evidence_quality_score": 82,
            "source_class": "crypto_native",
            "evidence_specificity": "asset_and_catalyst",
            "market_confirmation_score": 72,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": score,
            "opportunity_level": level,
            "supporting_evidence_quotes": [f"{symbol} catalyst evidence"],
        }
        entry = replace(
            _test_watchlist_entry(state=state, symbol=symbol, coin_id=symbol.lower()),
            key=f"{incident}|{symbol.lower()}|direct_subject",
            incident_id=incident,
            relationship_type="impact_hypothesis",
            latest_score=score,
            highest_score=score,
            latest_score_components=components,
            latest_event_name=f"{symbol} validated catalyst",
            suppressed_reason="not suppressed",
        )
        return event_alpha_router.EventAlphaRouteDecision(
            entry=entry,
            route=route,
            alertable=event_alpha_router.route_value_is_alertable(route.value),
            reason=f"{symbol} routed",
            lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
            final_route_after_quality_gate=route.value,
            opportunity_level=level,
            opportunity_score_final=score,
        )

    velvet = decision(
        "VELVET",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        level="high_priority",
        score=94,
        path="venue_value_capture",
        incident="incident:spacex",
    )
    aave = decision(
        "AAVE",
        state=event_watchlist.EventWatchlistState.RADAR.value,
        route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
        level="validated_digest",
        score=72,
        path="strategic_investment_or_valuation",
        incident="incident:aave",
    )
    rune = decision(
        "RUNE",
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        route=event_alpha_router.EventAlphaRoute.LOCAL_REPORT,
        level="watchlist",
        score=78,
        path="exploit_security_event",
        incident="incident:rune",
    )
    memecore = _notify_suppressed_decision("M", score=63, reason="local-only learning row")
    result = event_alpha_router.EventAlphaRouterResult(
        Path("state.jsonl"),
        4,
        [velvet, aave, rune, memecore],
        True,
    )
    brief = event_alpha_daily_brief.build_daily_brief(
        watchlist_entries=[velvet.entry, aave.entry, rune.entry, memecore.entry],
        router_result=result,
        requested_profile="fixture",
    )
    strong = brief.split("## High-Priority Core Opportunities", 1)[1].split("## Validated Digest Core Opportunities", 1)[0]
    digest = brief.split("## Validated Digest Core Opportunities", 1)[1].split("## Watchlist Core Opportunities", 1)[0]
    watchlist = brief.split("## Watchlist Core Opportunities", 1)[1].split("## Near-Miss Candidates", 1)[0]
    near = brief.split("## Near-Miss Candidates", 1)[1].split("## Upgrade Candidates", 1)[0]
    upgrades = brief.split("## Upgrade Candidates", 1)[1].split("## Quality-Capped / Local-Only Candidates", 1)[0]
    exploratory = brief.split("### Exploratory Digest", 1)[1].split("### Active Watchlist", 1)[0]
    diagnostics = brief.split("## Diagnostics Appendix", 1)[1]
    assert strong.count("VELVET/velvet") == 1
    assert digest.count("AAVE/aave") == 1
    assert watchlist.count("RUNE/rune") == 1
    assert "VELVET/velvet" not in near
    assert "AAVE/aave" not in near
    assert "RUNE/rune" not in near
    assert "AAVE/aave" in upgrades
    assert "RUNE/rune" in upgrades
    assert "VELVET/velvet" not in upgrades
    assert "VELVET/velvet" not in exploratory
    assert "AAVE/aave" not in exploratory
    assert "RUNE/rune" not in exploratory
    assert "M/m" in exploratory
    assert "### Active Watchlist" in diagnostics
    assert "### Validated Impact Hypothesis Routing" in diagnostics


def test_daily_brief_near_miss_and_card_groups_are_operator_friendly():
    from pathlib import Path
    import tempfile
    from crypto_rsi_scanner import event_alpha_daily_brief

    memecore = {
        "hypothesis_id": "hyp:memecore",
        "incident_id": "incident:memecore",
        "validated_symbol": "M",
        "validated_coin_id": "memecore",
        "candidate_role": "direct_subject",
        "impact_category": "market_anomaly_unknown",
        "impact_path_type": "market_dislocation_unknown",
        "source_class": "broad_news",
        "evidence_specificity": "direct_token_mechanism",
        "market_confirmation_score": 35,
        "market_confirmation_level": "weak",
        "opportunity_score_final": 61,
        "opportunity_level": "exploratory",
        "why_not_watchlist": ["needs_strong_market_confirmation", "cause_unknown_market_dislocation"],
        "upgrade_requirements": ["needs_direct_token_mechanism", "needs_market_confirmation"],
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        core = root / "card_velvet.md"
        near = root / "card_memecore.md"
        local = root / "card_btc.md"
        diagnostic = root / "card_kcs.md"
        core.write_text("Final opportunity verdict: high_priority\nFinal route: HIGH_PRIORITY_RESEARCH\n", encoding="utf-8")
        near.write_text("Final opportunity verdict: exploratory\nFinal route: STORE_ONLY\n", encoding="utf-8")
        local.write_text("Final route: STORE_ONLY\nLocal-only after quality/state gate.\n", encoding="utf-8")
        diagnostic.write_text("Playbook: source_noise_control\nImpact path type: generic_cooccurrence_only\n", encoding="utf-8")
        brief = event_alpha_daily_brief.build_daily_brief(
            hypothesis_rows=[memecore],
            card_paths=[core, near, local, diagnostic],
            requested_profile="fixture",
            include_test_artifacts=True,
            include_legacy_artifacts=True,
        )
    near_section = brief.split("## Near-Miss Candidates", 1)[1].split("## Quality-Capped / Local-Only Candidates", 1)[0]
    assert "M/memecore" in near_section
    assert "token moved, but the cause is still unknown" in near_section
    assert "needs proof that this event directly affects the token" in near_section
    assert "needs_strong_market_confirmation" not in near_section
    cards = brief.split("### Research Cards", 1)[1].split("### Missed Opportunities", 1)[0]
    core_cards = cards.split("#### Core Opportunity Cards", 1)[1].split("#### Near-Miss Cards", 1)[0]
    near_cards = cards.split("#### Near-Miss Cards", 1)[1].split("#### Local-Only / Quality-Capped Cards", 1)[0]
    local_cards = cards.split("#### Local-Only / Quality-Capped Cards", 1)[1].split("#### Diagnostic / Source-Noise / Control Cards", 1)[0]
    diagnostic_cards = cards.split("#### Diagnostic / Source-Noise / Control Cards", 1)[1]
    assert "card_velvet.md" in core_cards
    assert "card_memecore.md" not in core_cards
    assert "card_memecore.md" in near_cards
    assert "card_btc.md" in local_cards
    assert "card_kcs.md" not in diagnostic_cards
    assert "Hidden from main card list" in diagnostic_cards


def test_research_card_index_groups_core_local_near_miss_and_diagnostics():
    from datetime import datetime, timezone
    from pathlib import Path
    import tempfile
    from crypto_rsi_scanner import event_research_cards

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        core = root / "card_velvet.md"
        near = root / "card_memecore.md"
        local = root / "card_btc.md"
        diagnostic = root / "card_kcs.md"
        legacy = root / "legacy_old.md"
        core.write_text("Final opportunity verdict: high_priority\nFinal route: HIGH_PRIORITY_RESEARCH\n", encoding="utf-8")
        near.write_text("Final opportunity verdict: exploratory\nFinal route: LOCAL_REPORT\n", encoding="utf-8")
        local.write_text("Final route: STORE_ONLY\nLocal-only after quality/state gate.\n", encoding="utf-8")
        diagnostic.write_text("Playbook: source_noise_control\nImpact path type: generic_cooccurrence_only\n", encoding="utf-8")
        legacy.write_text("legacy card\n", encoding="utf-8")
        index = event_research_cards._render_index(
            [core, near, local, diagnostic, legacy],
            datetime(2026, 6, 20, tzinfo=timezone.utc),
        )
    assert "## Core Opportunity Cards" in index
    assert "card_velvet.md" in index.split("## Core Opportunity Cards", 1)[1].split("## Near-Miss Cards", 1)[0]
    assert "card_memecore.md" in index.split("## Near-Miss Cards", 1)[1].split("## Local-Only / Quality-Capped Cards", 1)[0]
    assert "card_btc.md" in index.split("## Local-Only / Quality-Capped Cards", 1)[1].split("## Diagnostic / Source-Noise / Control Cards", 1)[0]
    assert "card_kcs.md" in index.split("## Diagnostic / Source-Noise / Control Cards", 1)[1].split("## Legacy Cards", 1)[0]
    assert "legacy_old.md" in index.split("## Legacy Cards", 1)[1]


def test_research_card_index_collapses_near_miss_support_cards_by_asset_family():
    from pathlib import Path
    import tempfile
    from crypto_rsi_scanner import event_research_cards

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        chz_primary = root / "card_chz_accepted.md"
        chz_support = root / "card_chz_support.md"
        velvet_openai = root / "card_velvet_openai.md"
        velvet_stripe = root / "card_velvet_stripe.md"
        chz_primary.write_text(
            "- Asset: CHZ/chiliz\n"
            "- Event: Portugal · sports event\n"
            "- Playbook: fan_token_attention\n"
            "- Final route: STORE_ONLY\n"
            "- Evidence acquisition result: status=accepted_evidence_found accepted=1 rejected=0\n",
            encoding="utf-8",
        )
        chz_support.write_text(
            "- Asset: CHZ/chiliz\n"
            "- Event: World Cup · unlock supply event\n"
            "- Playbook: unlock_supply_event\n"
            "- Final route: SUPPRESS_DUPLICATE\n"
            "- Evidence acquisition result: status=not_executed accepted=0 rejected=0\n",
            encoding="utf-8",
        )
        velvet_openai.write_text(
            "- Asset: VELVET/velvet\n"
            "- Event: OpenAI · ipo proxy\n"
            "- Playbook: listing_liquidity_event\n"
            "- Final route: STORE_ONLY\n",
            encoding="utf-8",
        )
        velvet_stripe.write_text(
            "- Asset: VELVET/velvet\n"
            "- Event: Stripe · ipo proxy\n"
            "- Playbook: listing_liquidity_event\n"
            "- Final route: STORE_ONLY\n",
            encoding="utf-8",
        )
        collapsed = event_research_cards.collapse_card_paths_for_group(
            [chz_support, velvet_openai, chz_primary, velvet_stripe],
            group_name="Near-Miss Cards",
        )

    assert len(collapsed) == 2
    by_name = {path.name: hidden for path, hidden in collapsed}
    assert by_name["card_chz_accepted.md"] == 1
    assert by_name["card_velvet_openai.md"] == 1


def test_opportunity_audit_accepts_core_opportunity_id_and_hides_diagnostics_by_default():
    from crypto_rsi_scanner import event_core_opportunities, event_opportunity_audit

    primary = {
        "incident_id": "incident:aave",
        "canonical_incident_name": "Kraken stake in Aave",
        "validated_symbol": "AAVE",
        "validated_coin_id": "aave",
        "candidate_role": "direct_subject",
        "impact_category": "strategic_investment",
        "impact_path_type": "strategic_investment_or_valuation",
        "opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": "RESEARCH_DIGEST",
        "final_state_after_quality_gate": "RADAR",
        "hypothesis_id": "hyp:aave:kraken",
        "key": "incident:aave|aave|direct_subject|strategic_investment",
        "alert_id": "ea:aave-kraken",
        "card_id": "card_aave_kraken",
        "snapshot_id": "snap:aave",
        "evidence_quotes": ["Kraken in talks to buy 15% stake in DeFi lender Aave."],
        "main_frame_type": "acquisition_or_stake",
        "main_frame_actor": "Kraken",
    }
    diagnostic = {
        **primary,
        "hypothesis_id": "hyp:aave:kelpdao-background",
        "candidate_role": "source_noise",
        "latest_effective_playbook_type": "source_noise_control",
        "impact_category": "security_or_regulatory_shock",
        "impact_path_type": "exploit_security_event",
        "opportunity_level": "local_only",
        "opportunity_score_final": 0,
    }
    core_id = event_core_opportunities.aggregate_core_opportunities([primary, diagnostic])[0].core_opportunity_id
    audit = event_opportunity_audit.format_opportunity_audit(
        core_id,
        hypotheses=[primary, diagnostic],
        profile="fixture",
    )
    assert "## Core Opportunity" in audit
    assert "## Operator Presentation" in audit
    assert "Daily brief section: Validated Digest Core Opportunities" in audit
    assert "Research card group: Core Opportunity Cards" in audit
    assert core_id in audit
    assert "Kraken" in audit
    assert "hidden diagnostics: 1" in audit
    assert "watchlist keys:" in audit
    assert "alert ids: ea:aave-kraken" in audit
    assert "card ids/paths: card_aave_kraken" in audit
    assert "  - diagnostic:" not in audit
    by_hypothesis = event_opportunity_audit.format_opportunity_audit(
        "hyp:aave:kraken",
        hypotheses=[primary, diagnostic],
        profile="fixture",
    )
    assert core_id in by_hypothesis
    by_incident = event_opportunity_audit.format_opportunity_audit(
        "incident:aave",
        hypotheses=[primary, diagnostic],
        profile="fixture",
    )
    assert "Kraken stake in Aave" in by_incident
    audit_with_diagnostics = event_opportunity_audit.format_opportunity_audit(
        core_id,
        hypotheses=[primary, diagnostic],
        profile="fixture",
        include_diagnostics=True,
    )
    assert "  - diagnostic:" in audit_with_diagnostics
    orphan_audit = event_opportunity_audit.format_opportunity_audit(
        "core_missing",
        core_opportunity_rows=[primary],
        profile="fixture",
    )
    assert "matched_source: none" in orphan_audit
    assert "input target resolution status: orphan" in orphan_audit
    assert "visible_core_missing_store_row:core_missing" in orphan_audit
    assert "No matching hypothesis, watchlist row, alert snapshot, or route decision found." in orphan_audit


def test_research_cards_have_current_lineage_and_legacy_marker():
    from dataclasses import replace
    from crypto_rsi_scanner import event_core_opportunities, event_research_cards, event_watchlist

    entry = replace(
        _test_watchlist_entry(
            state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            symbol="VELVET",
            coin_id="velvet",
        ),
        incident_id="incident:velvet:spacex",
        hypothesis_id="hyp:velvet:spacex",
        latest_score_components={
            **_test_watchlist_entry(
                state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
                symbol="VELVET",
                coin_id="velvet",
            ).latest_score_components,
            "run_id": "run-123",
            "profile": "catalyst_frame_e2e",
            "artifact_namespace": "catalyst_frame_e2e",
            "incident_id": "incident:velvet:spacex",
            "hypothesis_id": "hyp:velvet:spacex",
            "source_raw_ids": ["velvet_spacex"],
            "source_event_ids": ["velvet-spacex-preipo"],
        },
    )
    core_id = event_core_opportunities.core_opportunity_id_for_row(entry)
    card = event_research_cards.render_research_card(
        entry.key,
        watchlist_entries=[entry],
        card_path="/tmp/card_velvet.md",
    )
    assert "- Run ID: run-123" in card.markdown
    assert "- Profile: catalyst_frame_e2e" in card.markdown
    assert "- Namespace: catalyst_frame_e2e" in card.markdown
    assert "- Incident ID: incident:velvet:spacex" in card.markdown
    assert "- Hypothesis ID: hyp:velvet:spacex" in card.markdown
    assert f"- Core opportunity ID: {core_id}" in card.markdown
    assert "- Card path: card_velvet.md" in card.markdown
    assert f"- Feedback target: {core_id}" in card.markdown
    assert "- Feedback target type: core_opportunity_id" in card.markdown
    assert "make event-feedback-useful PROFILE=catalyst_frame_e2e" in card.markdown
    assert "raw=velvet_spacex" in card.markdown
    assert "legacy_lineage_missing: false" in card.markdown
    assert "Lineage status: legacy_lineage_missing" not in card.markdown
    assert "Run ID: legacy_lineage_missing" not in card.markdown

    legacy = _test_watchlist_entry(
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        symbol="AAVE",
        coin_id="aave",
    )
    legacy_card = event_research_cards.render_research_card(legacy.key, watchlist_entries=[legacy])
    assert "Lineage status: legacy_lineage_missing" in legacy_card.markdown
    assert "legacy_lineage_missing: true" in legacy_card.markdown
    assert "- Run ID: legacy_lineage_missing" in legacy_card.markdown


def test_missing_unresolved_catalyst_frame_caps_validated_hypothesis():
    from crypto_rsi_scanner import event_impact_hypotheses

    missing_hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:aave:missing",
        event_cluster_id="incident:aave",
        event_type="news",
        external_asset="Aave",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("defi",),
        candidate_symbols=("AAVE",),
        candidate_coin_ids=("aave",),
        validated_candidate_assets=({"symbol": "AAVE", "coin_id": "aave", "validated": True},),
        confidence=0.90,
        hypothesis_score=90.0,
        validation_stage="impact_path_validated",
        status="validated",
        impact_path_type="exploit_security_event",
        impact_path_reason="exploit_security_event",
        candidate_role="direct_subject",
        opportunity_score_final=88,
        opportunity_level="high_priority",
        frame_required=True,
        frame_status="missing_required_frame_analysis",
        frame_gate_reason="catalyst_frame_missing",
        route_block_reason="catalyst_frame_missing",
    )
    missing_capped = event_impact_hypotheses._with_promotion_diagnostics(missing_hypothesis)
    assert missing_capped.opportunity_level == "exploratory"
    assert missing_capped.route_block_reason == "catalyst_frame_missing"
    assert missing_capped.impact_path_type == "exploit_security_event"

    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:aave:bad",
        event_cluster_id="incident:aave",
        event_type="news",
        external_asset="Aave",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("defi",),
        candidate_symbols=("AAVE",),
        candidate_coin_ids=("aave",),
        validated_candidate_assets=({"symbol": "AAVE", "coin_id": "aave", "validated": True},),
        confidence=0.90,
        hypothesis_score=90.0,
        validation_stage="impact_path_validated",
        status="validated",
        impact_path_type="exploit_security_event",
        impact_path_reason="exploit_security_event",
        candidate_role="direct_subject",
        opportunity_score_final=88,
        opportunity_level="high_priority",
        frame_required=True,
        frame_status="unresolved",
        frame_gate_reason="catalyst_frame_unresolved",
        route_block_reason="catalyst_frame_unresolved",
    )
    capped = event_impact_hypotheses._with_promotion_diagnostics(hypothesis)
    assert capped.opportunity_level == "exploratory"
    assert capped.opportunity_score_final <= 54
    assert capped.route_block_reason == "catalyst_frame_unresolved"
    assert "catalyst_frame_unresolved" in capped.why_not_promoted


def test_event_alpha_claim_semantics_incidents_roles_and_market_context():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_alert_store,
        event_alpha_artifact_doctor,
        event_alpha_router,
        event_claim_semantics,
        event_impact_hypotheses,
        event_incident_graph,
        event_incident_store,
        event_research_cards,
        event_watchlist,
    )
    from crypto_rsi_scanner.event_models import (
        DiscoveredAsset,
        DiscoveredEventFadeCandidate,
        EventAssetLink,
        EventClassification,
        EventDiscoveryResult,
        NormalizedEvent,
        RawDiscoveredEvent,
    )

    now = datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body, *, url, market=None):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_news",
            fetched_at=now,
            published_at=now,
            source_url=url,
            title=title,
            body=body,
            raw_json={"market": market or {}},
            source_confidence=0.88,
            content_hash=raw_id,
        )

    def anomaly_raw(raw_id, symbol, coin_id, name, *, fetched_at=now, score=86):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="market_anomaly",
            fetched_at=fetched_at,
            published_at=fetched_at,
            source_url=None,
            title=f"{symbol} market anomaly: 24h return 64%",
            body=(
                f"{name} ({symbol}) matched market-anomaly research filters: 24h return 64%, "
                "volume/mcap 0.34. No dated external catalyst has been validated; "
                "keep as radar/store-only until source evidence exists."
            ),
            raw_json={
                "event": {
                    "event_id": f"market_anomaly:{coin_id}:{fetched_at.date().isoformat()}",
                    "event_name": f"{symbol} market anomaly",
                    "event_type": "market_anomaly",
                    "event_time": None,
                    "event_time_confidence": 0.0,
                    "external_asset": None,
                    "description": f"{symbol} market anomaly",
                },
                "market": {
                    "symbol": symbol,
                    "coin_id": coin_id,
                    "name": name,
                    "return_24h": 64,
                    "volume_to_market_cap": 0.34,
                    "volume_zscore_24h": 4.5,
                    "anomaly_score": score,
                },
                "anomaly": {"score": score, "research_only": True, "requires_catalyst_evidence": True},
            },
            source_confidence=0.55,
            content_hash=raw_id,
        )

    claims = event_claim_semantics.claims_from_text(
        "MemeCore's M token crashes 80% with no exploit or announcement to explain it. "
        "The exploit was initially suspected, later ruled out."
    )
    assert any(claim.polarity == "negated" for claim in claims)
    assert any(claim.polarity == "ruled_out" for claim in claims)
    assert event_claim_semantics.current_cause_status(claims, "exploit") == "ruled_out"

    absence_claims = event_claim_semantics.claims_from_text("No dated external catalyst has been validated.")
    assert all(claim.subject != "No" for claim in absence_claims)
    assert any(claim.claim_type == "absence_of_validated_catalyst" for claim in absence_claims)
    assert not any(
        claim.predicate == "explains_market_move" and claim.cause_status == "confirmed"
        for claim in absence_claims
    )
    no_trigger_claims = event_claim_semantics.claims_from_text("No clear trigger for token crash.")
    assert all(claim.subject != "No" for claim in no_trigger_claims)
    assert all(claim.cause_status == "unknown" for claim in no_trigger_claims)
    no_exploit_claims = event_claim_semantics.claims_from_text("No exploit or announcement to explain it.")
    assert event_claim_semantics.has_ruled_out_claim(no_exploit_claims, "exploit")
    assert not event_claim_semantics.has_confirmed_claim(no_exploit_claims, "exploit")

    memecore_raw = raw(
        "memecore",
        "MemeCore's M token crashes 80% with no exploit or announcement to explain it",
        "No exploit or announcement explains the M token selloff; cause unknown.",
        url="https://alpha.example/memecore",
        market={"symbol": "M", "coin_id": "memecore", "return_24h": -71, "volume_zscore_24h": 5.0},
    )
    memecore_event = NormalizedEvent(
        event_id="evt_memecore",
        raw_ids=("memecore",),
        event_name="MemeCore M token crash",
        event_type="news",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source="fixture_news",
        source_urls=("https://alpha.example/memecore",),
        external_asset="MemeCore",
        description=memecore_raw.title,
        confidence=0.86,
    )
    memecore_asset = DiscoveredAsset("memecore", "M", "MemeCore")
    memecore_link = EventAssetLink("evt_memecore", "memecore", "M", "MemeCore", 0.95, "fixture", ("MemeCore M token",))
    memecore_cls = EventClassification("evt_memecore", "memecore", False, True, "direct_token_event", 0.90, "fixture", "fixture", ("MemeCore M token",))
    memecore_candidate = DiscoveredEventFadeCandidate(memecore_event, memecore_asset, memecore_link, memecore_cls, None, None, {})
    memecore_hyp = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((memecore_raw,), (memecore_event,), (memecore_link,), (memecore_cls,), (memecore_candidate,)),
        taxonomy={},
        now=now,
    )[0]
    assert memecore_hyp.impact_category == "market_anomaly_unknown"
    assert memecore_hyp.event_archetype == "market_dislocation_unknown"
    assert memecore_hyp.impact_path_type == "market_dislocation_unknown"
    assert memecore_hyp.cause_status == "ruled_out"
    assert memecore_hyp.market_context_source == "candidate_event_market_snapshot"
    assert memecore_hyp.market_context_snapshot["return_24h"] == -71
    assert memecore_hyp.market_reaction_confirmed is True
    assert memecore_hyp.causal_mechanism_confirmed is False

    sol_a = anomaly_raw("sol_a", "SOL", "solana", "Solana")
    sol_b = anomaly_raw("sol_b", "SOL", "solana", "Solana")
    usdt = anomaly_raw("usdt_a", "USDT", "tether", "Tether")
    anomaly_events = (
        NormalizedEvent("evt_sol_a", ("sol_a",), "SOL market anomaly", "market_anomaly", None, 0.0, now, "market_anomaly", (), None, sol_a.body, 0.55),
        NormalizedEvent("evt_sol_b", ("sol_b",), "SOL market anomaly update", "market_anomaly", None, 0.0, now, "market_anomaly", (), None, sol_b.body, 0.55),
        NormalizedEvent("evt_usdt_a", ("usdt_a",), "USDT market anomaly", "market_anomaly", None, 0.0, now, "market_anomaly", (), None, usdt.body, 0.55),
    )
    anomaly_incidents = event_incident_graph.build_incidents(
        anomaly_events,
        {row.raw_id: row for row in (sol_a, sol_b, usdt)},
    )
    assert len(anomaly_incidents) == 2
    sol_incident = next(item for item in anomaly_incidents if item.primary_subject == "SOL")
    usdt_incident = next(item for item in anomaly_incidents if item.primary_subject == "USDT")
    assert set(sol_incident.raw_ids) == {"sol_a", "sol_b"}
    assert set(usdt_incident.raw_ids) == {"usdt_a"}
    assert sol_incident.canonical_name == "SOL market anomaly"
    assert usdt_incident.canonical_name == "USDT market anomaly"
    assert sol_incident.current_cause_status == "unknown"
    assert all(claim.subject != "No" for claim in sol_incident.claim_history)
    assert any(claim.claim_type == "absence_of_validated_catalyst" for claim in sol_incident.claim_history)
    assert any(
        asset.symbol == "SOL" and asset.coin_id == "solana" and asset.role == "direct_subject"
        for asset in sol_incident.linked_assets
    )
    assert any(
        asset.symbol == "USDT" and asset.coin_id == "tether" and asset.role == "direct_subject"
        for asset in usdt_incident.linked_assets
    )
    missing_market = RawDiscoveredEvent(
        raw_id="missing_market_asset",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="No clear trigger market anomaly",
        body="No clear trigger or validated catalyst has been found for this market anomaly.",
        raw_json={
            "event": {
                "event_id": "market_anomaly:missing:2026-06-26",
                "event_name": "No clear trigger market anomaly",
                "event_type": "market_anomaly",
                "event_time": None,
                "event_time_confidence": 0.0,
                "external_asset": None,
                "description": "No clear trigger market anomaly",
            },
            "market": {"anomaly_score": 78},
            "anomaly": {"score": 78, "research_only": True, "requires_catalyst_evidence": True},
        },
        source_confidence=0.50,
        content_hash="missing_market_asset",
    )
    missing_incident = event_incident_graph.build_incidents(
        (
            NormalizedEvent(
                "evt_missing_market",
                ("missing_market_asset",),
                "No clear trigger market anomaly",
                "market_anomaly",
                None,
                0.0,
                now,
                "market_anomaly",
                (),
                None,
                missing_market.body,
                0.50,
            ),
        ),
        {"missing_market_asset": missing_market},
    )[0]
    assert missing_incident.primary_subject not in {"No", "SECTOR"}
    assert "market_anomaly_missing_validated_asset" in missing_incident.warnings

    prose_fragment_raw = raw(
        "prose_fragment",
        "Actions Announcements However",
        "However, it notes only announcements and no token-specific incident details.",
        url="https://fragment.example/actions",
    )
    prose_fragment_event = NormalizedEvent(
        "evt_prose_fragment",
        ("prose_fragment",),
        "Actions Announcements However",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (prose_fragment_raw.source_url,),
        None,
        prose_fragment_raw.body,
        0.40,
    )
    prose_fragment_incident = event_incident_graph.build_incidents(
        (prose_fragment_event,),
        {"prose_fragment": prose_fragment_raw},
    )[0]
    assert prose_fragment_incident.primary_subject is None
    assert prose_fragment_incident.subject_quality == "invalid"
    assert prose_fragment_incident.diagnostic_only is True
    assert "incident_primary_subject_invalid" in prose_fragment_incident.warnings
    assert event_claim_semantics.infer_primary_subject("OpenAI This suffered outage reports.") == "OpenAI"
    invalid_subject_examples = (
        "About",
        "All",
        "During",
        "Here",
        "LLM",
        "Need",
        "Not",
        "When",
        "Where",
        "Will",
        "Yes",
        "Best Prediction Market Apps",
        "Bitcoin And MSTR Are",
        "Polymarket Invite Code SBWIRE",
        "Polymarket Referral Code SBWIRE",
    )
    for idx, title in enumerate(invalid_subject_examples):
        bad_raw = raw(
            f"bad_subject_{idx}",
            title,
            f"{title} is a page heading, source label, or SEO phrase with no validated event subject.",
            url=f"https://fragment.example/{idx}",
        )
        bad_event = NormalizedEvent(
            f"evt_bad_subject_{idx}",
            (bad_raw.raw_id,),
            title,
            "news",
            None,
            0.0,
            now,
            "fixture_news",
            (bad_raw.source_url,),
            None,
            bad_raw.body,
            0.35,
        )
        bad_incident = event_incident_graph.build_incidents((bad_event,), {bad_raw.raw_id: bad_raw})[0]
        assert bad_incident.primary_subject != title
        assert bad_incident.subject_quality == "invalid"
        assert bad_incident.diagnostic_only is True
    polymarket_wc_raw = raw(
        "polymarket_world_cup_volume",
        "Polymarket World Cup Volume",
        "Polymarket World Cup volume rises before a prediction-market fixture.",
        url="https://fragment.example/polymarket-world-cup-volume",
    )
    polymarket_wc_event = NormalizedEvent(
        "evt_polymarket_world_cup",
        ("polymarket_world_cup_volume",),
        "Polymarket World Cup Volume",
        "sports_event",
        None,
        0.0,
        now,
        "fixture_news",
        (),
        "World Cup",
        polymarket_wc_raw.body,
        0.72,
    )
    polymarket_wc_incident = event_incident_graph.build_incidents(
        (polymarket_wc_event,),
        {"polymarket_world_cup_volume": polymarket_wc_raw},
    )[0]
    assert polymarket_wc_incident.primary_subject == "World Cup"
    assert polymarket_wc_incident.diagnostic_only is False
    next_bond_raw = raw(
        "next_bond",
        "Next James Bond prediction market",
        "A prediction market asks who will be the Next James Bond.",
        url="https://fragment.example/next-james-bond",
    )
    next_bond_event = NormalizedEvent(
        "evt_next_bond",
        ("next_bond",),
        "Next James Bond prediction market",
        "prediction_market",
        None,
        0.0,
        now,
        "fixture_news",
        (),
        "Next James Bond",
        next_bond_raw.body,
        0.74,
    )
    next_bond_incident = event_incident_graph.build_incidents((next_bond_event,), {"next_bond": next_bond_raw})[0]
    assert next_bond_incident.primary_subject == "Next James Bond"
    for valid_subject in ("SpaceX", "OpenAI", "Anthropic", "THORChain", "SecondFi", "Solana"):
        valid_raw = raw(
            f"valid_{valid_subject.lower()}",
            f"{valid_subject} suffered outage reports",
            f"{valid_subject} is the named subject in a concrete incident source.",
            url=f"https://fragment.example/{valid_subject.lower()}",
        )
        valid_event = NormalizedEvent(
            f"evt_valid_{valid_subject.lower()}",
            (valid_raw.raw_id,),
            f"{valid_subject} incident",
            "news",
            None,
            0.0,
            now,
            "fixture_news",
            (),
            valid_subject,
            valid_raw.body,
            0.80,
        )
        valid_incident = event_incident_graph.build_incidents((valid_event,), {valid_raw.raw_id: valid_raw})[0]
        assert valid_incident.primary_subject == valid_subject
        assert valid_incident.subject_quality == "valid"
    with tempfile.TemporaryDirectory() as diag_tmp:
        diag_write = event_incident_store.write_incidents(
            EventDiscoveryResult((prose_fragment_raw,), (prose_fragment_event,), (), (), ()),
            hypotheses=[],
            watchlist_rows=[],
            cfg=event_incident_store.EventIncidentStoreConfig(path=Path(diag_tmp) / "diagnostic_incidents.jsonl"),
            now=now,
            run_id="run-diagnostic-incident",
            profile="fixture",
            run_mode="test",
            artifact_namespace="fixture",
        )
        diag_loaded = event_incident_store.load_incidents(diag_write.path)
        assert diag_loaded.rows[0]["diagnostic_only"] is True
        diag_report = event_incident_store.format_incidents_report(diag_loaded)
        assert "diagnostic_rows_hidden: 1" in diag_report
        assert "diagnostic_rows_available: 1" in diag_report
        assert "Actions Announcements However" not in diag_report
        diag_visible = event_incident_store.load_incidents(diag_write.path, include_diagnostic=True)
        diag_visible_report = event_incident_store.format_incidents_report(diag_visible)
        assert "diagnostic_rows_hidden: 0" in diag_visible_report
        assert "Unknown subject" in diag_visible_report
        diagnostic_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-diagnostic-incident", "profile": "fixture", "artifact_namespace": "fixture", "run_mode": "test"}],
            incident_rows=diag_loaded.rows,
            include_test_artifacts=True,
            strict=True,
        )
        assert diagnostic_doctor.status == "WARN"
        assert diagnostic_doctor.diagnostic_incident_rows == 1
        assert diagnostic_doctor.garbage_primary_subject_incidents == 0
        canonical_bad = dict(diag_loaded.rows[0])
        canonical_bad["diagnostic_only"] = False
        canonical_bad["incident_subject_quality"] = "invalid"
        canonical_bad["primary_subject"] = "About"
        canonical_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-diagnostic-incident", "profile": "fixture", "artifact_namespace": "fixture", "run_mode": "test"}],
            incident_rows=[canonical_bad],
            include_test_artifacts=True,
            strict=True,
        )
        assert canonical_doctor.status == "BLOCKED"
        assert canonical_doctor.invalid_canonical_incident_rows == 1
        assert canonical_doctor.garbage_primary_subject_incidents == 1

        import json

        stale_garbage_path = Path(diag_tmp) / "stale_garbage_incidents.jsonl"
        stale_garbage_row = {
            "schema_version": event_incident_store.INCIDENT_STORE_SCHEMA_VERSION,
            "row_type": "event_incident",
            "observed_at": now.isoformat(),
            "run_id": "run-stale-garbage",
            "profile": "fixture",
            "run_mode": "test",
            "artifact_namespace": "fixture",
            "incident_id": "incident:stale_garbage",
            "canonical_name": "LLM political event",
            "event_archetype": "political_event",
            "primary_subject": "LLM",
            "incident_subject_quality": "valid",
            "incident_subject_quality_reason": "legacy_artifact",
            "diagnostic_only": False,
            "linked_hypothesis_ids": [],
            "linked_watchlist_keys": [],
            "linked_assets": [],
            "current_cause_status": "unknown",
            "source_update_count": 1,
            "independent_source_count": 1,
            "incident_confidence": 63,
            "warnings": [],
        }
        stale_garbage_path.write_text(json.dumps(stale_garbage_row) + "\n", encoding="utf-8")
        stale_loaded = event_incident_store.load_incidents(stale_garbage_path)
        assert stale_loaded.rows[0]["diagnostic_only"] is True
        assert stale_loaded.rows[0]["incident_subject_quality"] == "diagnostic_only"
        stale_report = event_incident_store.format_incidents_report(stale_loaded)
        assert "diagnostic_rows_hidden: 1" in stale_report
        assert "LLM political event" not in stale_report
        stale_visible = event_incident_store.load_incidents(stale_garbage_path, include_diagnostic=True)
        stale_visible_report = event_incident_store.format_incidents_report(stale_visible)
        assert "diagnostic_rows_hidden: 0" in stale_visible_report
        assert "LLM political event" in stale_visible_report
        stale_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-stale-garbage", "profile": "fixture", "artifact_namespace": "fixture", "run_mode": "test"}],
            incident_rows=stale_loaded.rows,
            include_test_artifacts=True,
            strict=True,
        )
        assert stale_doctor.status == "WARN"
        assert stale_doctor.diagnostic_incident_rows == 1
        assert stale_doctor.garbage_primary_subject_incidents == 1
        assert stale_doctor.invalid_canonical_incident_rows == 0

    secondfi_a = raw(
        "secondfi_a",
        "SecondFi loses $2.4m in Cardano wallet exploit",
        "A third-party SecondFi wallet exploit in the Cardano ecosystem affected ADA sentiment.",
        url="https://source-a.example/secondfi",
        market={"symbol": "ADA", "coin_id": "cardano", "return_24h": -9, "volume_zscore_24h": 2.6},
    )
    secondfi_b = raw(
        "secondfi_b",
        "SecondFi traces Cardano wallet exploit to address-level issue",
        "SecondFi says the Cardano wallet exploit was address-level and did not compromise the Cardano protocol.",
        url="https://source-b.example/secondfi-update",
        market={"symbol": "ADA", "coin_id": "cardano", "return_24h": -11, "volume_zscore_24h": 3.0},
    )
    unrelated = raw(
        "cardano_vote",
        "Cardano governance vote opens",
        "ADA holders discuss a governance vote unrelated to the SecondFi exploit.",
        url="https://source-c.example/cardano-vote",
    )
    events = (
        NormalizedEvent("evt_secondfi_a", ("secondfi_a",), "SecondFi Cardano wallet exploit", "news", None, 0.0, now, "fixture_news", (secondfi_a.source_url,), "SecondFi", secondfi_a.title, 0.84),
        NormalizedEvent("evt_secondfi_b", ("secondfi_b",), "SecondFi Cardano wallet exploit update", "news", None, 0.0, now, "fixture_news", (secondfi_b.source_url,), "SecondFi", secondfi_b.title, 0.84),
        NormalizedEvent("evt_cardano_vote", ("cardano_vote",), "Cardano governance vote", "governance", None, 0.0, now, "fixture_news", (unrelated.source_url,), "Cardano", unrelated.title, 0.70),
    )
    raw_by_id = {row.raw_id: row for row in (secondfi_a, secondfi_b, unrelated)}
    incidents = event_incident_graph.build_incidents(events, raw_by_id)
    secondfi_incidents = [item for item in incidents if item.primary_subject == "SecondFi"]
    assert len(secondfi_incidents) == 1
    assert set(secondfi_incidents[0].raw_ids) == {"secondfi_a", "secondfi_b"}
    assert len(secondfi_incidents[0].independent_source_domains) == 2
    assert len(incidents) == 2

    ada = DiscoveredAsset("cardano", "ADA", "Cardano")
    links = tuple(EventAssetLink(event.event_id, "cardano", "ADA", "Cardano", 0.90, "fixture", ("ADA",)) for event in events[:2])
    classes = tuple(EventClassification(event.event_id, "cardano", False, False, "ecosystem_event", 0.85, "fixture", "fixture", ("ADA",)) for event in events[:2])
    candidates = tuple(DiscoveredEventFadeCandidate(event, ada, link, cls, None, None, {}) for event, link, cls in zip(events[:2], links, classes))
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((secondfi_a, secondfi_b), events[:2], links, classes, candidates),
        taxonomy={},
        now=now,
    )
    assert len(hypotheses) == 1
    hyp = hypotheses[0]
    assert hyp.primary_subject == "SecondFi"
    assert hyp.affected_ecosystem == "Cardano"
    assert hyp.candidate_role == "ecosystem_affected_asset"
    assert hyp.impact_path_reason == "ecosystem_security_event"
    assert set(hyp.source_raw_ids) == {"secondfi_a", "secondfi_b"}
    assert "incident_evidence_update" in hyp.warnings
    assert len(hyp.independent_source_domains) == 2
    assert hyp.incident_id
    assert hyp.incident_canonical_name == hyp.canonical_incident_name
    assert hyp.incident_primary_subject == "SecondFi"
    assert hyp.incident_affected_ecosystem == "Cardano"
    assert hyp.incident_cause_status == hyp.cause_status
    assert hyp.incident_market_reaction_observed is True
    assert hyp.incident_causal_mechanism_confirmed is True

    thor_raw = raw(
        "thorchain",
        "THORChain confirms RUNE exploit after attack",
        "THORChain confirms a RUNE exploit and security incident after an attack; RUNE trading reacts sharply.",
        url="https://source-d.example/thorchain-rune-exploit",
        market={"symbol": "RUNE", "coin_id": "thorchain", "return_24h": -18, "volume_zscore_24h": 3.4},
    )
    thor_event = NormalizedEvent(
        "evt_thorchain",
        ("thorchain",),
        "THORChain RUNE exploit",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (thor_raw.source_url,),
        "THORChain",
        thor_raw.title,
        0.90,
    )
    rune = DiscoveredAsset("thorchain", "RUNE", "THORChain")
    thor_link = EventAssetLink("evt_thorchain", "thorchain", "RUNE", "THORChain", 0.95, "fixture", ("THORChain RUNE",))
    thor_cls = EventClassification("evt_thorchain", "thorchain", False, True, "direct_token_event", 0.90, "fixture", "fixture", ("THORChain RUNE",))
    thor_candidate = DiscoveredEventFadeCandidate(thor_event, rune, thor_link, thor_cls, None, None, {})
    thor_hyp = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((thor_raw,), (thor_event,), (thor_link,), (thor_cls,), (thor_candidate,)),
        taxonomy={},
        now=now,
    )[0]
    assert thor_hyp.candidate_role == "direct_subject"
    assert thor_hyp.cause_status == "confirmed"
    assert thor_hyp.market_reaction_confirmed is True
    assert thor_hyp.causal_mechanism_confirmed is True

    discovery = EventDiscoveryResult(
        raw_events=(memecore_raw, secondfi_a, secondfi_b, thor_raw),
        normalized_events=(memecore_event, events[0], events[1], thor_event),
        links=(memecore_link, *links, thor_link),
        classifications=(memecore_cls, *classes, thor_cls),
        candidates=(memecore_candidate, *candidates, thor_candidate),
    )
    with tempfile.TemporaryDirectory() as tmp:
        one_source_hyp = event_impact_hypotheses.generate_impact_hypotheses(
            EventDiscoveryResult((secondfi_a,), (events[0],), (links[0],), (classes[0],), (candidates[0],)),
            taxonomy={},
            now=now,
        )[0]
        watch_cfg = event_watchlist.EventWatchlistConfig(enabled=True, state_path=Path(tmp) / "watchlist.jsonl")
        event_watchlist.refresh_hypothesis_watchlist((one_source_hyp,), cfg=watch_cfg, now=now)
        updated_watch = event_watchlist.refresh_hypothesis_watchlist((hyp,), cfg=watch_cfg, now=now)
        updated_entry = updated_watch.entries[0]
        loaded_watch = event_watchlist.load_watchlist(watch_cfg.state_path)
        assert len(loaded_watch.entries) == 1
        assert loaded_watch.entries[0].key == updated_entry.key
        assert updated_entry.key.startswith(f"hypothesis|{hyp.incident_id}|cardano|ecosystem_affected_asset|")
        assert updated_entry.incident_id == hyp.incident_id
        assert updated_entry.hypothesis_id == hyp.hypothesis_id
        assert updated_entry.incident_canonical_name == hyp.incident_canonical_name
        assert updated_entry.incident_primary_subject == "SecondFi"
        assert updated_entry.incident_cause_status == hyp.cause_status
        assert updated_entry.incident_market_reaction_observed is True
        assert updated_entry.incident_causal_mechanism_confirmed is True
        assert updated_entry.source_count == 2
        assert "independent_source_confirmation" in updated_entry.material_change_reasons
        assert "incident_new_independent_source" in updated_entry.material_change_reasons
        assert "incident_confidence_changed" in updated_entry.material_change_reasons
        watch = event_watchlist.refresh_hypothesis_watchlist(
            (memecore_hyp, hyp, thor_hyp),
            cfg=watch_cfg,
            now=now,
        )
        write = event_incident_store.write_incidents(
            discovery,
            cfg=event_incident_store.EventIncidentStoreConfig(path=Path(tmp) / "event_incidents.jsonl"),
            hypotheses=(memecore_hyp, hyp, thor_hyp),
            watchlist_rows=watch.entries,
            now=now,
            run_id="run-incident-test",
            profile="quality_validation",
            run_mode="test",
            artifact_namespace="quality_validation",
        )
        assert write.success is True
        assert write.rows_written == 3
        loaded = event_incident_store.load_incidents(write.path)
        assert loaded.rows_read == 3
        secondfi_row = next(row for row in loaded.rows if row["primary_subject"] == "SecondFi")
        assert set(secondfi_row["source_raw_ids"]) == {"secondfi_a", "secondfi_b"}
        assert secondfi_row["source_update_count"] == 2
        assert secondfi_row["independent_source_count"] == 2
        assert secondfi_row["linked_hypothesis_ids"] == [hyp.hypothesis_id]
        assert secondfi_row["linked_watchlist_keys"]
        assert secondfi_row["market_reaction_confirmed"] is True
        assert secondfi_row["causal_mechanism_confirmed"] is True
        assert any(asset["role"] == "ecosystem_affected_asset" for asset in secondfi_row["linked_assets"])
        memecore_row = next(row for row in loaded.rows if row["primary_subject"] == "MemeCore")
        assert memecore_row["event_archetype"] == "market_dislocation_unknown"
        assert memecore_row["current_cause_status"] == "ruled_out"
        assert memecore_row["market_reaction_confirmed"] is True
        assert memecore_row["causal_mechanism_confirmed"] is False
        thor_row = next(row for row in loaded.rows if row["primary_subject"] == "THORChain")
        assert thor_row["event_archetype"] == "exploit_security_event"
        assert thor_row["current_cause_status"] == "confirmed"
        assert any(asset["symbol"] == "RUNE" and asset["role"] == "direct_subject" for asset in thor_row["linked_assets"])
        thor_entry = next(entry for entry in watch.entries if entry.symbol == "RUNE")
        assert thor_entry.incident_id == thor_hyp.incident_id
        assert thor_entry.hypothesis_id == thor_hyp.hypothesis_id
        assert thor_entry.incident_canonical_name == thor_hyp.incident_canonical_name
        assert thor_entry.incident_primary_subject == "THORChain"
        decision = event_alpha_router.EventAlphaRouteDecision(
            entry=thor_entry,
            route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
            alertable=True,
            reason="fixture incident-linked hypothesis",
            lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        )
        snap_path = Path(tmp) / "alerts.jsonl"
        event_alpha_alert_store.write_alert_snapshots(
            [],
            router_result=type("Router", (), {"decisions": [decision]})(),
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=snap_path),
            now=now,
            run_id="run-incident-test",
            profile="quality_validation",
            run_mode="test",
            artifact_namespace="quality_validation",
        )
        snap = event_alpha_alert_store.load_alert_snapshots(snap_path).rows[0]
        assert snap["incident_id"] == thor_hyp.incident_id
        assert snap["hypothesis_id"] == thor_hyp.hypothesis_id
        assert snap["incident_canonical_name"] == thor_hyp.incident_canonical_name
        assert snap["incident_primary_subject"] == "THORChain"
        card_path = Path(tmp) / "rune_card.md"
        card_index_path = Path(tmp) / "index.md"
        core_id = snap.get("core_opportunity_id")
        card_path.write_text(
            "\n".join([
                "# RUNE Event Research Card",
                "- Generated at: 2026-06-28T00:00:00+00:00",
                "- Lineage status: current",
                "- legacy_lineage_missing: false",
                "- Run ID: run-incident-test",
                "- Profile: quality_validation",
                "- Namespace: quality_validation",
                f"- Core opportunity ID: {core_id}",
                f"- Feedback target: {core_id}",
                "- Feedback target type: core_opportunity_id",
            ]),
            encoding="utf-8",
        )
        card_index_path.write_text(f"# Event Research Cards\n\n- [rune_card.md](rune_card.md) · feedback target: `{core_id}`\n", encoding="utf-8")
        assert event_research_cards.card_core_opportunity_id(card_path) == core_id
        clean_quality = {
            "impact_path_type": "exploit_security_event",
            "impact_path_strength": "strong",
            "candidate_role": "direct_subject",
            "evidence_quality_score": 85,
            "source_class": "primary_or_reputable_source",
            "evidence_specificity": "direct_token_mechanism",
            "market_confirmation_score": 80,
            "market_confirmation_level": "confirmed",
            "market_context_freshness_status": "fresh",
            "market_context_age_hours": 0.2,
            "market_context_stale": False,
            "market_context_freshness_cap_applied": False,
            "opportunity_score_final": 75,
            "opportunity_level": "validated_digest",
            "opportunity_verdict_reasons": ["incident_linked"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "not_watchlist_without_market_followthrough",
            "manual_verification_items": ["verify incident source and token-specific market reaction"],
            "upgrade_requirements": ["needs watchlist confirmation"],
            "downgrade_warnings": ["none"],
        }
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-incident-test",
                "profile": "quality_validation",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
                "alertable": 1,
                "snapshot_write_success": True,
                "snapshot_rows_written": 1,
            }],
            hypothesis_rows=[{
                "row_type": "event_impact_hypothesis",
                "run_id": "run-incident-test",
                "profile": "quality_validation",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
                "hypothesis_id": thor_hyp.hypothesis_id,
                "incident_id": thor_hyp.incident_id,
                **clean_quality,
            }],
            watchlist_rows=[thor_entry],
            alert_rows=[snap],
            incident_rows=loaded.rows,
            card_paths=[card_path, card_index_path],
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor.hypothesis_rows_missing_incident_id == 0
        assert doctor.watchlist_hypothesis_rows_missing_incident_id == 0
        assert doctor.alert_hypothesis_rows_missing_incident_id == 0
        assert doctor.status in {"OK", "WARN"}
        thor_with_blocked_support = dict(thor_row)
        thor_with_blocked_support["qualified_link_count"] = max(1, int(thor_with_blocked_support.get("qualified_link_count") or 0))
        thor_with_blocked_support["quality_blocked_link_count"] = 1
        doctor_with_diagnostic_link = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-incident-test",
                "profile": "quality_validation",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
            }],
            incident_rows=[thor_with_blocked_support],
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor_with_diagnostic_link.quality_blocked_links_present == 1
        assert doctor_with_diagnostic_link.quality_blocked_links_promoting_incident == 0
        assert doctor_with_diagnostic_link.status in {"OK", "WARN"}
        assert "quality_blocked_links_present=1" in event_alpha_artifact_doctor.format_artifact_doctor_report(doctor_with_diagnostic_link)
        thor_only_blocked_support = dict(thor_with_blocked_support)
        thor_only_blocked_support["qualified_link_count"] = 0
        doctor_only_blocked_link = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-incident-test",
                "profile": "quality_validation",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
            }],
            incident_rows=[thor_only_blocked_support],
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor_only_blocked_link.quality_blocked_links_promoting_incident == 1
        assert doctor_only_blocked_link.status == "BLOCKED"
        missing_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-incident-test", "alertable": 0}],
            watchlist_rows=[{
                "row_type": "event_watchlist_state",
                "relationship_type": "impact_hypothesis",
                "key": "fresh-missing-incident",
                "event_id": "hyp:missing",
                "coin_id": "missing",
                "symbol": "MISS",
                "run_mode": "burn_in",
                "artifact_namespace": "quality_validation",
                "opportunity_level": "validated_digest",
                "opportunity_score_final": 75,
                "impact_path_type": "exploit_security_event",
                "evidence_specificity": "direct_token_mechanism",
            }],
            include_test_artifacts=True,
            strict=True,
        )
        assert missing_doctor.status == "BLOCKED"
        assert missing_doctor.watchlist_hypothesis_rows_missing_incident_id == 1
        report = event_incident_store.format_incidents_report(loaded)
        assert "EVENT INCIDENTS REPORT" in report
        assert "market_dislocation_unknown=1" in report
        assert "exploit_security_event=2" in report
        assert "multiple_source_updates: 1" in report
        assert "incident_linked_hypotheses_count: 3" in report
        assert "incident_linked_watchlist_count: 3" in report

        anomaly_write = event_incident_store.write_incidents(
            EventDiscoveryResult((sol_a, sol_b, usdt), anomaly_events, (), (), ()),
            cfg=event_incident_store.EventIncidentStoreConfig(path=Path(tmp) / "market_incidents.jsonl"),
            now=now,
            run_id="run-market-anomaly-test",
            profile="quality_validation",
            run_mode="test",
            artifact_namespace="quality_validation",
        )
        assert anomaly_write.success is True
        assert anomaly_write.rows_written == 2
        anomaly_loaded = event_incident_store.load_incidents(anomaly_write.path)
        anomaly_report = event_incident_store.format_incidents_report(anomaly_loaded)
        assert "SOL market anomaly" in anomaly_report
        assert "USDT market anomaly" in anomaly_report
        assert "No · market anomaly" not in anomaly_report
        assert "primary_subjects: SOL=1, USDT=1" in anomaly_report
        assert "absence_of_validated_catalyst_claims: 3" in anomaly_report
        assert "market_reaction_unknown_cause: 2" in anomaly_report
        assert all(row["market_reaction_observed"] is True for row in anomaly_loaded.rows)
        assert all(row["current_cause_status"] == "unknown" for row in anomaly_loaded.rows)
        sol_row = next(row for row in anomaly_loaded.rows if row["primary_subject"] == "SOL")
        usdt_row = next(row for row in anomaly_loaded.rows if row["primary_subject"] == "USDT")
        assert any(
            asset["symbol"] == "SOL" and asset["coin_id"] == "solana" and asset["role"] == "direct_subject"
            for asset in sol_row["linked_assets"]
        )
        assert any(
            asset["symbol"] == "USDT" and asset["coin_id"] == "tether" and asset["role"] == "direct_subject"
            for asset in usdt_row["linked_assets"]
        )
        assert not any(asset["symbol"] == "SECTOR" and asset["role"] == "direct_subject" for asset in sol_row["linked_assets"])
        no_incident_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-no-incident", "alertable": 0}],
            hypothesis_rows=[{
                "row_type": "event_impact_hypothesis",
                "run_id": "run-no-incident",
                "profile": "quality_validation",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
                "hypothesis_id": "hyp:no-incident",
                "incident_link_status": "no_incident",
                "incident_link_reason": "no_canonical_incident_for_event_evidence",
                **clean_quality,
            }],
            watchlist_rows=[{
                "row_type": "event_watchlist_state",
                "relationship_type": "impact_hypothesis",
                "key": "fresh-no-incident",
                "event_id": "hyp:no-incident",
                "coin_id": "noincident",
                "symbol": "NOINC",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
                "incident_link_status": "no_incident",
                "incident_link_reason": "no_canonical_incident_for_event_evidence",
                "opportunity_level": "validated_digest",
                "opportunity_score_final": 75,
                "impact_path_type": "exploit_security_event",
                "evidence_specificity": "direct_token_mechanism",
            }],
            alert_rows=[{
                "row_type": "event_alpha_alert_snapshot",
                "run_id": "run-no-incident",
                "hypothesis_id": "hyp:no-incident",
                "incident_link_status": "no_incident",
                "incident_link_reason": "no_canonical_incident_for_event_evidence",
                **clean_quality,
            }],
            include_test_artifacts=True,
            strict=True,
        )
        assert no_incident_doctor.hypothesis_rows_missing_incident_id == 0
        assert no_incident_doctor.watchlist_hypothesis_rows_missing_incident_id == 0
        assert no_incident_doctor.alert_hypothesis_rows_missing_incident_id == 0


def test_event_incident_relevance_gates_raw_external_observations():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_incident_graph, event_incident_store
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id: str, title: str, body: str, *, provider: str = "fixture_news", confidence: float = 0.65, payload=None):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json=dict(payload or {}),
            source_confidence=confidence,
            content_hash=raw_id,
        )

    broad_raw = raw(
        "trump_putin_polymarket",
        "Where will Trump meet Putin?",
        "A Polymarket question asks where Trump will meet Putin. No crypto asset, token, venue value capture, or market anomaly is mentioned.",
        provider="polymarket",
        confidence=0.58,
    )
    broad_event = NormalizedEvent(
        "evt_trump_putin_polymarket",
        (broad_raw.raw_id,),
        "Where will Trump meet Putin?",
        "prediction_market",
        None,
        0.0,
        now,
        "polymarket",
        (broad_raw.source_url,),
        "Trump Putin meeting",
        broad_raw.body,
        0.58,
    )
    broad_result = EventDiscoveryResult((broad_raw,), (broad_event,), (), (), ())
    with tempfile.TemporaryDirectory() as tmp:
        live_path = Path(tmp) / "live_incidents.jsonl"
        live_write = event_incident_store.write_incidents(
            broad_result,
            cfg=event_incident_store.EventIncidentStoreConfig(path=live_path),
            now=now,
            run_id="run-broad-live",
            profile="notify_llm_quality_fresh",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm_quality_fresh",
        )
        assert live_write.success is True
        assert live_write.rows_written == 0

        debug_path = Path(tmp) / "debug_incidents.jsonl"
        debug_write = event_incident_store.write_incidents(
            broad_result,
            cfg=event_incident_store.EventIncidentStoreConfig(path=debug_path),
            now=now,
            run_id="run-broad-debug",
            profile="quality_validation",
            run_mode="test",
            artifact_namespace="quality_validation",
        )
        assert debug_write.success is True
        assert debug_write.rows_written == 1
        hidden = event_incident_store.load_incidents(debug_path)
        assert hidden.rows[0]["incident_relevance_status"] == "external_context_only"
        assert hidden.rows[0]["diagnostic_only"] is False
        assert hidden.rows[0]["external_context_only"] is True
        assert hidden.rows[0]["diagnostic_hidden_by_default"] is True
        hidden_report = event_incident_store.format_incidents_report(hidden)
        assert "diagnostic_rows_hidden: 0" in hidden_report
        assert "external_context_rows_hidden: 1" in hidden_report
        assert "Where will Trump meet Putin?" not in hidden_report
        visible_report = event_incident_store.format_incidents_report(
            event_incident_store.load_incidents(debug_path, include_diagnostic=True)
        )
        assert "diagnostic_rows_hidden: 0" in visible_report
        assert "external_context_rows_hidden: 0" in visible_report
        assert "Putin · prediction market" in visible_report
        debug_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-broad-debug", "profile": "quality_validation", "run_mode": "test"}],
            incident_rows=hidden.rows,
            include_test_artifacts=True,
            strict=True,
        )
        assert debug_doctor.diagnostic_incident_rows == 0
        assert debug_doctor.raw_observation_incident_rows == 0
        assert debug_doctor.external_context_incident_rows == 1
        assert debug_doctor.incident_rows_without_linked_hypotheses == 0
        assert debug_doctor.incident_rows_without_linked_watchlist == 0

        raw_observation = raw(
            "unstructured_unlinked_note",
            "Unstructured source note",
            "A source note has no clear external catalyst, no crypto token, and no market anomaly.",
            provider="fixture_news",
            confidence=0.42,
        )
        raw_event = NormalizedEvent(
            "evt_unstructured_note",
            (raw_observation.raw_id,),
            "Unstructured source note",
            "news",
            None,
            0.0,
            now,
            "fixture_news",
            (raw_observation.source_url,),
            None,
            raw_observation.body,
            0.42,
        )
        raw_path = Path(tmp) / "raw_incidents.jsonl"
        raw_write = event_incident_store.write_incidents(
            EventDiscoveryResult((raw_observation,), (raw_event,), (), (), ()),
            cfg=event_incident_store.EventIncidentStoreConfig(path=raw_path, store_raw_observations=True),
            now=now,
            run_id="run-raw-opt-in",
            profile="notify_llm_quality_fresh",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm_quality_fresh",
        )
        assert raw_write.success is True
        assert raw_write.rows_written == 1
        raw_rows = event_incident_store.load_incidents(raw_path)
        assert raw_rows.rows[0]["incident_relevance_status"] == "raw_observation"
        assert raw_rows.rows[0]["raw_observation"] is True
        assert "raw_observation_rows_hidden: 1" in event_incident_store.format_incidents_report(raw_rows)

        missing_relevance = {
            "schema_version": event_incident_store.INCIDENT_STORE_SCHEMA_VERSION,
            "row_type": "event_incident",
            "run_id": "run-missing-relevance",
            "profile": "notify_llm_quality_fresh",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_quality_fresh",
            "incident_id": "incident:missing_relevance",
            "canonical_name": "Missing relevance crypto incident",
            "event_archetype": "exploit_security_event",
            "primary_subject": "THORChain",
            "incident_subject_quality": "valid",
            "diagnostic_only": False,
            "linked_hypothesis_ids": [],
            "linked_watchlist_keys": [],
        }
        strict_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-missing-relevance", "profile": "notify_llm_quality_fresh", "run_mode": "notification_burn_in"}],
            incident_rows=[missing_relevance],
            strict=True,
        )
        assert strict_doctor.status == "BLOCKED"
        assert strict_doctor.incident_relevance_missing == 1

    thor_raw = raw(
        "thorchain_relevance",
        "THORChain confirms RUNE exploit",
        "THORChain confirms a RUNE exploit and security incident affecting the RUNE token.",
        confidence=0.91,
    )
    thor_event = NormalizedEvent(
        "evt_thorchain_relevance",
        (thor_raw.raw_id,),
        "THORChain RUNE exploit",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (thor_raw.source_url,),
        "THORChain",
        thor_raw.body,
        0.91,
    )
    thor_incident = event_incident_graph.build_incidents((thor_event,), {thor_raw.raw_id: thor_raw})[0]
    thor_relevance = event_incident_store.classify_incident_relevance(
        thor_incident,
        raw_by_id={thor_raw.raw_id: thor_raw},
        hypotheses=({
            "hypothesis_id": "hyp:rune",
            "incident_id": thor_incident.incident_id,
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "candidate_role": "direct_subject",
            "impact_path_type": "exploit_security_event",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 82,
        },),
        watchlist_rows=({
            "key": "watch:rune",
            "incident_id": thor_incident.incident_id,
            "state": "WATCHLIST",
            "final_state_after_quality_gate": "WATCHLIST",
            "symbol": "RUNE",
            "coin_id": "thorchain",
            "candidate_role": "direct_subject",
            "impact_path_type": "exploit_security_event",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 82,
        },),
    )
    assert thor_relevance["incident_relevance_status"] == "active_incident"
    assert thor_relevance["canonical_persistence_reason"] == "qualified_watchlist_link"
    assert thor_relevance["qualified_link_count"] == 2

    sol_raw = raw(
        "sol_market_anomaly_relevance",
        "SOL market anomaly",
        "SOL matched market-anomaly filters with no confirmed catalyst.",
        provider="market_anomaly",
        payload={
            "market": {"symbol": "SOL", "coin_id": "solana", "return_24h": 42},
            "anomaly": {"score": 91, "research_only": True},
        },
    )
    sol_event = NormalizedEvent(
        "evt_sol_market_anomaly_relevance",
        (sol_raw.raw_id,),
        "SOL market anomaly",
        "market_anomaly",
        None,
        0.0,
        now,
        "market_anomaly",
        (),
        None,
        sol_raw.body,
        0.72,
    )
    sol_incident = event_incident_graph.build_incidents((sol_event,), {sol_raw.raw_id: sol_raw})[0]
    sol_relevance = event_incident_store.classify_incident_relevance(sol_incident, raw_by_id={sol_raw.raw_id: sol_raw})
    assert sol_relevance["incident_relevance_status"] == "canonical_incident"
    assert sol_relevance["canonical_persistence_reason"] == "market_dislocation"

    openai_raw = raw(
        "openai_preipo_sector_relevance",
        "OpenAI pre-IPO markets expand",
        "OpenAI pre-IPO exposure could affect tokenized-stock crypto venues if listed by a venue.",
        confidence=0.86,
    )
    openai_event = NormalizedEvent(
        "evt_openai_preipo_relevance",
        (openai_raw.raw_id,),
        "OpenAI pre-IPO markets expand",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (openai_raw.source_url,),
        "OpenAI",
        openai_raw.body,
        0.86,
    )
    openai_incident = event_incident_graph.build_incidents((openai_event,), {openai_raw.raw_id: openai_raw})[0]
    openai_relevance = event_incident_store.classify_incident_relevance(
        openai_incident,
        raw_by_id={openai_raw.raw_id: openai_raw},
        hypotheses=({"hypothesis_id": "hyp:openai-sector", "incident_id": openai_incident.incident_id, "candidate_sectors": ("tokenized_stock_venues",)},),
    )
    assert openai_relevance["incident_relevance_status"] == "incident_candidate"
    assert openai_relevance["qualified_link_count"] == 0
    assert "weak_unqualified_hypothesis_link" in openai_relevance["link_quality_reasons"]

    sports_raw = raw(
        "sweden_sports_sector_relevance",
        "Sweden World Cup odds move",
        "A broad sports event references fan-token sectors, but no concrete crypto asset is validated.",
        confidence=0.84,
    )
    sports_event = NormalizedEvent(
        "evt_sweden_sports_sector_relevance",
        (sports_raw.raw_id,),
        "Sweden World Cup odds move",
        "sports_event",
        None,
        0.0,
        now,
        "fixture_news",
        (sports_raw.source_url,),
        "World Cup",
        sports_raw.body,
        0.84,
    )
    sports_incident = event_incident_graph.build_incidents((sports_event,), {sports_raw.raw_id: sports_raw})[0]
    sports_relevance = event_incident_store.classify_incident_relevance(
        sports_incident,
        raw_by_id={sports_raw.raw_id: sports_raw},
        watchlist_rows=({
            "key": "watch:sector:sports",
            "incident_id": sports_incident.incident_id,
            "state": "WATCHLIST",
            "final_state_after_quality_gate": "WATCHLIST",
            "symbol": "SECTOR",
            "coin_id": "sports_fan_proxy",
            "candidate_role": "proxy_instrument",
            "impact_path_type": "fan_token_attention",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 82,
        },),
    )
    assert sports_relevance["incident_relevance_status"] != "active_incident"
    assert sports_relevance["qualified_link_count"] == 0
    assert sports_relevance["sector_only_link_count"] == 1
    assert "sector_only_unqualified_link" in sports_relevance["link_quality_reasons"]

    fannie_raw = raw(
        "fannie_rwa_candidate",
        "Fannie Mae pre-IPO tokenized stock venue watch",
        "A high-quality source says Fannie Mae pre-IPO and tokenized stock venues may become relevant to RWA markets.",
        confidence=0.88,
    )
    fannie_event = NormalizedEvent(
        "evt_fannie_rwa_candidate",
        (fannie_raw.raw_id,),
        "Fannie Mae pre-IPO tokenized stock venue watch",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (fannie_raw.source_url,),
        "Fannie Mae",
        fannie_raw.body,
        0.88,
    )
    fannie_incident = event_incident_graph.build_incidents((fannie_event,), {fannie_raw.raw_id: fannie_raw})[0]
    fannie_relevance = event_incident_store.classify_incident_relevance(
        fannie_incident,
        raw_by_id={fannie_raw.raw_id: fannie_raw},
    )
    assert fannie_relevance["incident_relevance_status"] == "incident_candidate"

    def classify_weak_event(raw_id: str, title: str, body: str, event_type: str, symbol: str, coin_id: str):
        event_raw = raw(raw_id, title, body, confidence=0.76)
        event = NormalizedEvent(
            f"evt_{raw_id}",
            (event_raw.raw_id,),
            title,
            event_type,
            None,
            0.0,
            now,
            "fixture_news",
            (event_raw.source_url,),
            title,
            event_raw.body,
            0.76,
        )
        incident = event_incident_graph.build_incidents((event,), {event_raw.raw_id: event_raw})[0]
        weak_watchlist = {
            "key": f"watch:{raw_id}",
            "incident_id": incident.incident_id,
            "state": "WATCHLIST",
            "requested_state_before_quality_gate": "WATCHLIST",
            "final_state_after_quality_gate": "QUALITY_BLOCKED",
            "state_quality_capped": True,
            "symbol": symbol,
            "coin_id": coin_id,
            "candidate_role": "unknown",
            "impact_path_type": "insufficient_data",
            "evidence_specificity": "insufficient_data",
            "opportunity_level": "local_only",
            "opportunity_score_final": 0,
        }
        return event_incident_store.classify_incident_relevance(
            incident,
            raw_by_id={event_raw.raw_id: event_raw},
            watchlist_rows=(weak_watchlist,),
        )

    annexation = classify_weak_event(
        "annexation_weak_link",
        "Annexation prediction market",
        "A broad annexation prediction market mentions no validated crypto token impact path.",
        "political_event",
        "UMA",
        "uma",
    )
    assert annexation["incident_relevance_status"] == "external_context_only"
    assert annexation["qualified_link_count"] == 0
    assert "quality_blocked_link_only" in annexation["link_quality_reasons"]

    macron = classify_weak_event(
        "macron_weak_link",
        "Macron election odds move",
        "A broad election article mentions Macron and prediction markets but no direct TRUMP token value path.",
        "political_event",
        "TRUMP",
        "official-trump",
    )
    assert macron["incident_relevance_status"] == "external_context_only"
    assert macron["unknown_role_link_count"] == 1

    openai_fet = classify_weak_event(
        "openai_fet_weak_link",
        "OpenAI pre-IPO markets expand",
        "OpenAI pre-IPO exposure may matter to crypto AI tokens someday, but no FET value-capture path is validated.",
        "ai_ipo_proxy",
        "FET",
        "fetch-ai",
    )
    assert openai_fet["incident_relevance_status"] == "incident_candidate"
    assert openai_fet["canonical_persistence_reason"] == "quality_blocked_link_only"

    databricks_velvet_weak = classify_weak_event(
        "databricks_velvet_weak_link",
        "Databricks IPO closing",
        "Databricks IPO closing is broad pre-IPO news, while the VELVET link has not been quality validated.",
        "rwa_preipo_proxy",
        "VELVET",
        "velvet",
    )
    assert databricks_velvet_weak["incident_relevance_status"] == "incident_candidate"
    assert databricks_velvet_weak["qualified_link_count"] == 0

    velvet_quality_raw = raw(
        "velvet_spacex_quality_link",
        "Velvet offers SpaceX pre-IPO exposure",
        "VELVET users can trade SpaceX pre-IPO exposure through the Velvet crypto venue.",
        confidence=0.92,
    )
    velvet_event = NormalizedEvent(
        "evt_velvet_spacex_quality",
        (velvet_quality_raw.raw_id,),
        "Velvet offers SpaceX pre-IPO exposure",
        "rwa_preipo_proxy",
        None,
        0.0,
        now,
        "fixture_news",
        (velvet_quality_raw.source_url,),
        "SpaceX",
        velvet_quality_raw.body,
        0.92,
    )
    velvet_incident = event_incident_graph.build_incidents((velvet_event,), {velvet_quality_raw.raw_id: velvet_quality_raw})[0]
    velvet_relevance = event_incident_store.classify_incident_relevance(
        velvet_incident,
        raw_by_id={velvet_quality_raw.raw_id: velvet_quality_raw},
        hypotheses=({
            "hypothesis_id": "hyp:velvet-spacex",
            "incident_id": velvet_incident.incident_id,
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_path_type": "venue_value_capture",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 84,
        },),
    )
    assert velvet_relevance["incident_relevance_status"] == "active_incident"
    assert velvet_relevance["canonical_persistence_reason"] == "qualified_hypothesis_link"
    assert velvet_relevance["qualified_link_count"] == 1


def test_event_opportunity_upgrade_path_and_audit_sections():
    from crypto_rsi_scanner import event_opportunity_audit, event_opportunity_verdict

    weak = event_opportunity_verdict.explain_upgrade_path(components={
        "impact_path_type": "generic_cooccurrence_only",
        "candidate_role": "generic_mention",
        "market_confirmation_level": "weak",
        "market_confirmation_score": 20,
        "evidence_quality_score": 35,
        "opportunity_score_final": 42,
    })
    assert "blocked_by_generic_cooccurrence" in weak.upgrade_requirements
    assert "needs_market_confirmation" in weak.upgrade_requirements
    assert "no_value_capture" in weak.downgrade_warnings

    from crypto_rsi_scanner import event_alpha_router
    decision = _notify_route_decision(
        "VELVET",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    incident_row = {
        "row_type": "event_incident",
        "incident_id": "incident:velvet",
        "canonical_name": "SpaceX proxy attention",
        "primary_subject": "SpaceX",
        "affected_ecosystem": "Velvet",
        "current_cause_status": "unknown",
        "claim_history": [{"claim_type": "proxy", "polarity": "asserted", "cause_status": "unknown"}],
        "source_update_count": 2,
        "independent_source_count": 2,
        "market_reaction_confirmed": True,
        "causal_mechanism_confirmed": False,
        "market_context_source": "candidate_event_market_snapshot",
        "linked_assets": [{"symbol": "VELVET", "coin_id": "velvet", "role": "proxy_venue"}],
    }
    report = event_opportunity_audit.format_opportunity_audit(
        "incident:velvet",
        route_decisions=[decision],
        incident_rows=[incident_row],
        profile="fixture",
    )
    assert "EVENT OPPORTUNITY AUDIT" in report
    assert "## Incident" in report
    assert "SpaceX proxy attention" in report
    assert "market reaction vs causal mechanism" in report
    assert "## What would upgrade this candidate" in report
    assert "## What would downgrade / invalidate this candidate" in report
    assert "No secrets, Telegram sends, trades" in report


def test_event_incident_context_appears_in_daily_brief_and_cards():
    from crypto_rsi_scanner import event_alpha_daily_brief, event_research_cards, event_watchlist

    incident_row = {
        "row_type": "event_incident",
        "profile": "quality_validation",
        "run_mode": "test",
        "artifact_namespace": "quality_validation",
        "incident_id": "incident:rune",
        "canonical_name": "THORChain exploit security event",
        "event_archetype": "exploit_security_event",
        "primary_subject": "THORChain",
        "affected_ecosystem": "THORChain",
        "current_cause_status": "confirmed",
        "claim_history": [{"claim_type": "exploit", "polarity": "asserted", "cause_status": "confirmed"}],
        "source_update_count": 2,
        "independent_source_count": 2,
        "linked_assets": [{"symbol": "RUNE", "coin_id": "thorchain", "role": "direct_subject"}],
        "market_reaction_confirmed": True,
        "causal_mechanism_confirmed": True,
        "market_context_source": "candidate_event_market_snapshot",
        "incident_confidence": 91,
    }
    brief = event_alpha_daily_brief.build_daily_brief(
        incident_rows=[incident_row],
        requested_profile="quality_validation",
        artifact_namespace="quality_validation",
        include_test_artifacts=True,
    )
    assert "## Canonical Incidents" in brief
    assert "THORChain exploit security event" in brief
    assert "confirmed=1" in brief

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|incident:rune|security_or_regulatory_shock",
        cluster_id="incident:rune",
        event_id="hyp:rune",
        coin_id="thorchain",
        symbol="RUNE",
        relationship_type="impact_hypothesis",
        external_asset="THORChain",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=event_watchlist.EventWatchlistState.HYPOTHESIS.value,
        first_seen_at="2026-06-26T12:00:00+00:00",
        last_seen_at="2026-06-26T12:00:00+00:00",
        source_count=2,
        highest_score=82,
        latest_score=82,
        latest_tier="RADAR_DIGEST",
        latest_event_name="THORChain RUNE exploit validated",
        latest_source="impact_hypothesis",
        latest_playbook_type="security_or_regulatory_shock",
        latest_effective_playbook_type="direct_event",
        latest_score_components={
            "hypothesis_id": "hyp:rune",
            "incident_id": "incident:rune",
            "canonical_incident_name": "THORChain exploit security event",
            "event_archetype": "exploit_security_event",
            "primary_subject": "THORChain",
            "affected_ecosystem": "THORChain",
            "cause_status": "confirmed",
            "claim_polarities": ["asserted"],
            "claim_history": incident_row["claim_history"],
            "independent_source_domains": ["source-a.example", "source-b.example"],
            "conflicting_claims": [],
            "incident_confidence": 91,
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "validated_asset": {"symbol": "RUNE", "coin_id": "thorchain", "name": "THORChain"},
            "impact_path_type": "exploit_security_event",
            "impact_path_strength": "strong",
            "impact_path_reason": "exploit_security_event",
            "candidate_role": "direct_subject",
            "role_confidence": 0.9,
            "role_evidence": ["candidate_named_as_primary_subject"],
            "market_context_source": "candidate_event_market_snapshot",
            "market_context_age_seconds": 600,
            "market_context_data_quality": "fresh",
            "market_reaction_confirmed": True,
            "causal_mechanism_confirmed": True,
            "market_confirmation_level": "strong",
            "market_confirmation_score": 78,
            "evidence_quality_score": 82,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_score_final": 82,
            "opportunity_level": "watchlist",
            "opportunity_verdict_reasons": ["confirmed_direct_incident"],
            "manual_verification_items": ["verify incident source"],
        },
        should_alert=True,
    )
    card = event_research_cards.render_research_card(
        "ea:" + entry.key,
        watchlist_entries=[entry],
    )
    assert "## Impact Hypothesis Context" in card.markdown
    assert "Incident confidence: 91" in card.markdown
    assert "Claim history: exploit:asserted/confirmed" in card.markdown
    assert "Market context source: candidate_event_market_snapshot (fresh; age=10m; cap_applied=false)" in card.markdown


def test_event_watchlist_validated_hypothesis_market_confirmation_promotes_state():
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_watchlist

    hypothesis = SimpleNamespace(
        hypothesis_id="h-velvet",
        event_cluster_id="spacex|ipo|2026-06-20",
        status="validated",
        validation_stage="impact_path_validated",
        hypothesis_score=82,
        confidence=0.82,
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        validated_symbol="VELVET",
        validated_coin_id="velvet",
        candidate_sectors=("tokenized_stock_venues",),
        source_raw_ids=("r1", "r2"),
        impact_category="rwa_preipo_proxy",
        hypothesis_scope="token",
        playbook_hint="proxy_attention",
        external_asset="SpaceX",
        opportunity_level="watchlist",
        opportunity_score_final=82,
        market_confirmation_level="moderate",
        market_confirmation_score=62,
        evidence_quality_score=78,
        source_class="crypto_news",
        evidence_specificity="direct_value_capture",
        impact_path_type="proxy_exposure",
        impact_path_strength="strong",
        candidate_role="proxy_venue",
        score_components={"event_clarity": 80, "derivatives_crowding": 20},
    )
    with tempfile.TemporaryDirectory() as tmp:
        result = event_watchlist.refresh_hypothesis_watchlist(
            [hypothesis],
            cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=__import__("pathlib").Path(tmp) / "watch.jsonl"),
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
        )
    entry = result.entries[0]
    assert entry.state == event_watchlist.EventWatchlistState.WATCHLIST.value
    assert entry.latest_tier == "WATCHLIST"
    assert "market_confirmation_upgraded" in entry.material_change_reasons
    assert entry.should_alert
    assert entry.state != event_watchlist.EventWatchlistState.TRIGGERED_FADE.value


def test_event_incident_primary_subject_validator_quarantines_garbage_before_persistence():
    from datetime import datetime, timezone
    from pathlib import Path
    import tempfile

    from crypto_rsi_scanner import event_incident_graph, event_incident_store
    from crypto_rsi_scanner.event_models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    invalid_subjects = (
        "About",
        "All",
        "Best Prediction Market Apps",
        "Bitcoin And MSTR Are",
        "During",
        "Here",
        "LLM",
        "Need",
        "Not",
        "Polymarket Invite Code SBWIRE",
        "Polymarket Referral Code SBWIRE",
    )
    for subject in invalid_subjects:
        result = event_incident_graph.validate_incident_primary_subject(subject)
        assert result.status in {"invalid_subject", "diagnostic_only"}
        assert result.normalized_subject is None
    assert event_incident_graph.validate_incident_primary_subject("OpenAI This").normalized_subject == "OpenAI"
    assert event_incident_graph.validate_incident_primary_subject("World Cup").normalized_subject == "World Cup"
    for subject in ("SpaceX", "OpenAI", "Anthropic", "THORChain", "SecondFi", "Solana"):
        assert event_incident_graph.validate_incident_primary_subject(subject).status == "valid"

    now = datetime(2026, 6, 26, 16, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        "raw_about",
        "fixture_news",
        now,
        now,
        "https://example.com/about",
        "About",
        "About unlock supply event with no validated crypto subject.",
        {},
        0.72,
        "hash-about",
    )
    event = NormalizedEvent(
        "evt_about",
        (raw.raw_id,),
        "About",
        "unlock",
        None,
        0.0,
        now,
        "fixture_news",
        (raw.source_url,),
        "About",
        raw.body,
        0.72,
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_incidents.jsonl"
        write = event_incident_store.write_incidents(
            EventDiscoveryResult((raw,), (event,), (), (), ()),
            cfg=event_incident_store.EventIncidentStoreConfig(path=path, store_diagnostic=True),
            now=now,
            run_id="run-about",
            profile="notify_llm_quality",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm_quality",
        )
        assert write.success is True
        loaded = event_incident_store.load_incidents(path)
        assert loaded.rows[0]["diagnostic_only"] is True
        assert loaded.rows[0]["incident_subject_quality"] == "diagnostic_only"
        assert loaded.rows[0]["incident_relevance_status"] == "diagnostic_only"
        assert loaded.rows[0]["canonical_persistence_reason"] == "diagnostic_subject_only"
        report = event_incident_store.format_incidents_report(loaded)
        assert "diagnostic_rows_hidden: 1" in report
        visible = event_incident_store.load_incidents(path, include_diagnostic=True)
        visible_report = event_incident_store.format_incidents_report(visible)
        assert "diagnostic_rows_hidden: 0" in visible_report


def test_event_llm_evidence_planner_fixture_cases():
    from crypto_rsi_scanner import event_llm_evidence_planner

    aave = event_llm_evidence_planner.plan_evidence({
        "core_opportunity_id": "core:aave",
        "symbol": "AAVE",
        "coin_id": "aave",
        "external_asset": "Kraken",
        "playbook_type": "strategic_investment",
        "impact_path_type": "strategic_investment_or_valuation",
        "opportunity_score_final": 72,
        "opportunity_level": "validated_digest",
        "missing_requirements": ("official_source",),
    })
    assert aave.selected is True
    assert aave.source_pack == "strategic_investment_pack"
    assert any("AAVE" in query.query and "Kraken" in query.query for query in aave.query_plan)
    assert any("denies" in query.query.casefold() for query in aave.denial_searches)
    assert aave.official_confirmation_queries
    assert "official_confirmation" in aave.query_intents
    assert any("valuation" in item or "stake" in item for item in aave.expected_proof_criteria)
    assert "confirm token/project identity with non-URL evidence" in aave.checklist

    velvet = event_llm_evidence_planner.plan_evidence({
        "core_opportunity_id": "core:velvet",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "external_asset": "SpaceX",
        "playbook_type": "proxy_attention",
        "impact_path_type": "venue_value_capture",
        "candidate_role": "proxy_venue",
        "opportunity_score_final": 79,
        "opportunity_level": "watchlist",
    })
    assert velvet.source_pack == "proxy_preipo_rwa_pack"
    assert any(query.provider_hint == "polymarket" and query.must_validate_asset is False for query in velvet.query_plan)
    assert velvet.market_refresh_requests == ("velvet",)
    assert any("external exposure mechanism" in item for item in velvet.expected_proof_criteria)
    assert "check denial/correction sources for proxy relationship" in velvet.manual_checklist

    rune = event_llm_evidence_planner.plan_evidence({
        "core_opportunity_id": "core:rune",
        "symbol": "RUNE",
        "coin_id": "thorchain",
        "playbook_type": "security_or_regulatory_shock",
        "impact_path_type": "exploit_security_event",
        "opportunity_score_final": 80,
        "opportunity_level": "watchlist",
    })
    assert rune.source_pack == "security_shock_pack"
    assert any("exploit" in query.query.casefold() for query in rune.query_plan)
    assert any("denial" in item.casefold() for item in rune.expected_proof_criteria)

    generic = event_llm_evidence_planner.plan_evidence({
        "core_opportunity_id": "core:generic",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "provider": "polymarket",
        "playbook_type": "political_meme_proxy",
        "opportunity_score_final": 45,
        "opportunity_level": "local_only",
    })
    assert generic.selected is False
    assert "planner_not_selected_below_prefilter" in generic.warnings
    assert generic.source_pack == "political_meme_pack"
    assert "prediction_market_context_only_until_token_identity_validated" in generic.warnings


def test_event_llm_evidence_planner_contradiction_summary_and_budget():
    from crypto_rsi_scanner import event_llm_evidence_planner

    exploit_denied = {
        "core_opportunity_id": "core:aave-denial",
        "symbol": "AAVE",
        "coin_id": "aave",
        "event_name": "Aave not hacked after KelpDAO exploit rumors",
        "playbook_type": "security_or_regulatory_shock",
        "impact_path_type": "exploit_security_event",
        "opportunity_score_final": 70,
        "opportunity_level": "watchlist",
    }
    contradiction = event_llm_evidence_planner.detect_contradiction_or_denial(exploit_denied)
    assert contradiction.blocks_validation is True
    assert contradiction.reason == "exploit_or_hack_denied"
    assert any("exploit" in query.query.casefold() for query in contradiction.denial_queries)
    planned = event_llm_evidence_planner.plan_evidence(exploit_denied)
    assert "exploit_denial_blocks_security_path" in planned.warnings

    listing_denied = event_llm_evidence_planner.detect_contradiction_or_denial({
        "symbol": "TEST",
        "coin_id": "test-token",
        "event_name": "Exchange denies listing TEST after fake listing rumor",
        "playbook_type": "listing_volatility",
        "impact_path_type": "listing_liquidity_event",
        "opportunity_score_final": 64,
        "opportunity_level": "validated_digest",
    })
    assert listing_denied.blocks_validation is True
    assert listing_denied.reason == "listing_denied_or_fake"

    velvet_row = {
        "core_opportunity_id": "core:velvet-summary",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "external_asset": "SpaceX",
        "playbook_type": "proxy_attention",
        "impact_path_type": "venue_value_capture",
        "candidate_role": "proxy_venue",
        "opportunity_score_final": 82,
        "opportunity_level": "high_priority",
        "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
        "evidence_acquisition_plan": planned.to_metadata(),
    }
    velvet_plan = event_llm_evidence_planner.plan_evidence(velvet_row)
    summary = event_llm_evidence_planner.generate_analyst_summary(velvet_row, plan=velvet_plan)
    assert "VELVET surfaced as high_priority" in summary.why_surfaced
    assert "SpaceX" not in summary.why_surfaced  # summary is sourced from structured route fields, not invented copy.
    assert "source" in summary.what_would_upgrade.casefold() or "evidence" in summary.what_would_upgrade.casefold()
    assert any("identity" in item for item in summary.what_to_check_next)

    weak_btc = {
        "core_opportunity_id": "core:btc-weak",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "event_name": "Bitcoin World writes broad policy recap",
        "playbook_type": "political_meme_proxy",
        "impact_path_type": "insufficient_data",
        "opportunity_score_final": 0,
        "opportunity_level": "local_only",
        "final_route_after_quality_gate": "STORE_ONLY",
        "why_local_only": ("missing_direct_impact_path",),
    }
    weak_summary = event_llm_evidence_planner.generate_analyst_summary(weak_btc)
    assert "Not alertable" in weak_summary.why_not_alertable
    assert "missing_direct_impact_path" in weak_summary.why_not_alertable

    budget = event_llm_evidence_planner.select_llm_analyst_tools(
        [
            {
                "core_opportunity_id": "core:triage",
                "symbol": "RUNE",
                "coin_id": "thorchain",
                "source_url": "https://fixture.test/rune",
                "source_triage_decision": "send_to_llm_frame_analyzer",
                "playbook_type": "security_or_regulatory_shock",
                "impact_path_type": "exploit_security_event",
                "opportunity_score_final": 80,
                "opportunity_level": "watchlist",
            },
            {
                "core_opportunity_id": "core:budget-skip",
                "symbol": "AAVE",
                "coin_id": "aave",
                "source_url": "https://fixture.test/aave",
                "playbook_type": "strategic_investment",
                "impact_path_type": "strategic_investment_or_valuation",
                "opportunity_score_final": 78,
                "opportunity_level": "validated_digest",
            },
        ],
        cfg=event_llm_evidence_planner.LLMAnalystToolBudgetConfig(provider="fixture", max_calls_per_run=3),
    )
    assert budget.triage_llm_calls == 1
    assert budget.query_planner_llm_calls == 1
    assert budget.summary_llm_calls == 1
    assert budget.skipped_by_budget == 1

    missing_key = event_llm_evidence_planner.select_llm_analyst_tools(
        [weak_btc],
        cfg=event_llm_evidence_planner.LLMAnalystToolBudgetConfig(provider="openai", api_key_present=False),
    )
    assert missing_key.skipped_missing_api_key == 1
    assert "missing_api_key" in missing_key.warnings


def test_event_near_miss_source_pack_and_operator_surfaces():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alpha_daily_brief,
        event_near_miss,
        event_opportunity_audit,
        event_research_cards,
        event_watchlist,
    )

    row = {
        "hypothesis_id": "hyp:velvet-source-gap",
        "event_cluster_id": "cluster:spacex",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "external_asset": "SpaceX",
        "provider": "gdelt",
        "provider_coverage_status": "degraded",
        "title": "SpaceX IPO coverage mentions Velvet exposure",
        "playbook_type": "proxy_attention",
        "impact_category": "tokenized_stock_venue",
        "impact_path_type": "venue_value_capture",
        "candidate_role": "proxy_venue",
        "source_class": "broad_news",
        "evidence_specificity": "token_and_catalyst",
        "evidence_quality_score": 58,
        "market_confirmation_score": 35,
        "opportunity_score_final": 64,
        "opportunity_level": "exploratory",
        "missing_requirements": ("impact_path_validation", "source evidence"),
        "why_not_watchlist": "impact_path_not_validated",
        "score_components": {
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "external_asset": "SpaceX",
            "playbook_type": "proxy_attention",
            "impact_category": "tokenized_stock_venue",
            "impact_path_type": "venue_value_capture",
            "candidate_role": "proxy_venue",
            "source_class": "broad_news",
            "evidence_specificity": "token_and_catalyst",
            "evidence_quality_score": 58,
            "market_confirmation_score": 35,
            "opportunity_score_final": 64,
            "opportunity_level": "exploratory",
            "missing_requirements": ("impact_path_validation", "source evidence"),
            "why_not_watchlist": "impact_path_not_validated",
        },
    }
    near = event_near_miss.detect_near_miss_rows((row,), cfg=event_near_miss.EventNearMissConfig())
    assert len(near) == 1
    assert near[0].source_pack == "proxy_preipo_rwa_pack"
    assert near[0].provider_coverage_status == "degraded"
    assert near[0].source_coverage_gap == "provider_coverage_degraded:gdelt"
    assert near[0].evidence_absence_is_meaningful is False
    assert "source_pack_search" in near[0].recommended_refresh_actions
    assert near[0].evidence_acquisition_attempted is True
    assert near[0].evidence_acquisition_plan["evidence_acquisition_source_pack"] == "proxy_preipo_rwa_pack"

    report = event_near_miss.format_near_miss_report(near, profile="quality_validation")
    assert "source_pack: proxy_preipo_rwa_pack" in report
    assert "coverage=degraded" in report
    assert "evidence_plan:" in report

    brief = event_alpha_daily_brief.build_daily_brief(
        hypothesis_rows=[{**row, "profile": "quality_validation", "artifact_namespace": "quality_validation", "run_mode": "notification_burn_in"}],
        requested_profile="quality_validation",
        artifact_namespace="quality_validation",
    )
    assert "## Source Coverage / Evidence Acquisition" in brief
    assert "Candidates Blocked by Source Coverage" in brief
    assert "VELVET/velvet" in brief

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|cluster:spacex|velvet",
        cluster_id="cluster:spacex",
        event_id="hyp:velvet-source-gap",
        coin_id="velvet",
        symbol="VELVET",
        relationship_type="impact_hypothesis",
        external_asset="SpaceX",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=None,
        first_seen_at=datetime(2026, 6, 15, tzinfo=timezone.utc).isoformat(),
        last_seen_at=datetime(2026, 6, 15, tzinfo=timezone.utc).isoformat(),
        latest_source="gdelt",
        latest_playbook_type="proxy_attention",
        latest_score_components={
            **row["score_components"],
            "source_pack": near[0].source_pack,
            "provider_coverage_status": near[0].provider_coverage_status,
            "evidence_absence_is_meaningful": near[0].evidence_absence_is_meaningful,
            "source_coverage_gap": near[0].source_coverage_gap,
            "source_quality_prior": near[0].source_quality_prior,
            "source_confidence_cap": near[0].source_confidence_cap,
            "evidence_acquisition_attempted": near[0].evidence_acquisition_attempted,
            "evidence_acquisition_plan": near[0].evidence_acquisition_plan,
            "evidence_acquisition_failures": near[0].evidence_acquisition_failures,
        },
    )
    card = event_research_cards.render_research_card(entry.key, watchlist_entries=[entry])
    assert "## Analyst Summary" in card.markdown
    assert "Why surfaced: VELVET surfaced" in card.markdown
    assert "What would upgrade: source/evidence proof:" in card.markdown
    assert "## Source Coverage / Evidence Acquisition" in card.markdown
    assert "Source pack: proxy_preipo_rwa_pack" in card.markdown
    assert "Coverage status: degraded" in card.markdown
    assert "Source can prove:" in card.markdown
    assert "Source cannot prove:" in card.markdown
    assert "Relevant playbooks:" in card.markdown
    assert "OPENAI_API_KEY" not in card.markdown

    audit = event_opportunity_audit.format_opportunity_audit("VELVET", hypotheses=[row], watchlist_entries=[entry])
    assert "## Source coverage and acquisition plan" in audit
    assert "source pack: proxy_preipo_rwa_pack" in audit
    assert "provider coverage: degraded" in audit
    assert "source can prove:" in audit
    assert "source cannot prove:" in audit
    assert "relevant playbooks:" in audit


def test_event_core_opportunity_store_persists_canonical_rows():
    from crypto_rsi_scanner import (
        event_alpha_router,
        event_core_opportunity_store,
        event_watchlist,
    )

    rows = _canonical_core_fixture_rows()
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        result = event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-store",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        assert result.success
        assert result.rows_written == 4
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
        assert loaded.rows_read == 4
        by_symbol = {row["symbol"]: row for row in loaded.rows}
        assert by_symbol["VELVET"]["final_opportunity_level"] == "high_priority"
        assert by_symbol["VELVET"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
        assert by_symbol["RUNE"]["final_state_after_quality_gate"] == event_watchlist.EventWatchlistState.WATCHLIST.value
        assert set(by_symbol) == {"AAVE", "MEME", "RUNE", "VELVET"}


def test_event_core_opportunity_store_derives_route_from_final_verdict():
    from crypto_rsi_scanner import event_alpha_router, event_core_opportunity_store, event_watchlist

    rows = [{
        "row_type": "event_impact_hypothesis",
        "hypothesis_id": "hyp-digest-store-only",
        "incident_id": "incident-digest-store-only",
        "canonical_incident_name": "Digest-worthy core with stale route",
        "symbol": "TEST",
        "coin_id": "test-token",
        "validated_symbol": "TEST",
        "validated_coin_id": "test-token",
        "candidate_role": "direct_subject",
        "impact_path_type": "strategic_investment",
        "impact_path_reason": "strategic_investment",
        "opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "final_verdict_reason": "Validated impact hypothesis kept local-only: stale primary route.",
        "evidence_specificity": "direct_token_mechanism",
        "source_class": "crypto_news",
        "market_confirmation_level": "none",
    }]
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        result = event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-route-normalized",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        assert result.success
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)

    stored = loaded.rows[0]
    assert stored["final_opportunity_level"] == "validated_digest"
    assert stored["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    assert stored["route"] == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    assert stored["canonical_route_adjustment_reason"] == "core_route_derived_from_opportunity_level:validated_digest"
    assert "final route derived from canonical opportunity level" in stored["final_verdict_reason"]
    assert "local-only" not in stored["final_verdict_reason"]


def test_live_core_confirmation_caps_unconfirmed_digest_candidates():
    from crypto_rsi_scanner import event_alpha_router, event_core_opportunity_store, event_watchlist

    rows = [
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-eth-skipped-budget",
            "incident_id": "incident-eth-strategic",
            "symbol": "ETH",
            "coin_id": "ethereum",
            "validated_symbol": "ETH",
            "validated_coin_id": "ethereum",
            "candidate_role": "direct_beneficiary",
            "impact_path_type": "strategic_investment",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 74,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 80,
            "market_confirmation_score": 20,
            "market_context_freshness_status": "missing",
            "evidence_acquisition_status": "skipped_budget",
            "source_pack": "strategic_investment_pack",
        },
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-tao-rejected-only",
            "incident_id": "incident-tao-strategic",
            "symbol": "TAO",
            "coin_id": "bittensor",
            "candidate_role": "direct_beneficiary",
            "impact_path_type": "strategic_investment",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 78,
            "evidence_acquisition_status": "rejected_results_only",
            "evidence_acquisition_rejected_count": 2,
            "source_pack": "strategic_investment_pack",
        },
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-sector-sports",
            "incident_id": "incident-sector-sports",
            "symbol": "SECTOR",
            "coin_id": "sports_fan_proxy",
            "candidate_role": "sector_hypothesis",
            "impact_path_type": "sports_fan_proxy",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 70,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "source_class": "structured_calendar",
            "evidence_specificity": "event_time_only",
            "evidence_quality_score": 78,
            "evidence_acquisition_status": "no_results",
            "source_pack": "fan_sports_pack",
        },
    ]
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-live-confirmation-caps",
            profile="live_burn_in_no_send",
            run_mode="notification_burn_in",
            artifact_namespace="live_burn_in_no_send",
        )
        stored = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    by_symbol = {row["symbol"]: row for row in stored}
    assert by_symbol["ETH"]["final_opportunity_level"] == "exploratory"
    assert by_symbol["ETH"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert by_symbol["ETH"]["acquisition_confirmation_status"] == "unresolved"
    assert by_symbol["ETH"]["live_confirmation_reason"] == "skipped_budget_not_confirmation"
    assert by_symbol["TAO"]["final_opportunity_level"] == "exploratory"
    assert by_symbol["TAO"]["acquisition_confirmation_status"] == "does_not_confirm"
    assert by_symbol["TAO"]["live_confirmation_reason"] == "rejected_results_only_not_confirmation"
    assert by_symbol["SECTOR"]["final_opportunity_level"] == "local_only"
    assert by_symbol["SECTOR"]["live_confirmation_reason"] == "sector_only_digest_not_allowed"
    assert all(row["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value for row in stored)


def test_live_core_confirmation_allows_accepted_and_official_evidence():
    from crypto_rsi_scanner import event_alpha_router, event_core_opportunity_store, event_watchlist

    rows = [
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-velvet-accepted",
            "incident_id": "incident-spacex",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_path_type": "venue_value_capture",
            "opportunity_level": "high_priority",
            "opportunity_score_final": 91,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            "source_class": "cryptopanic_tagged",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 91,
            "market_confirmation_score": 88,
            "market_context_freshness_status": "fresh",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
            "source_pack": "proxy_preipo_rwa_pack",
        },
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-listing-official",
            "incident_id": "incident-listing",
            "symbol": "LIST",
            "coin_id": "listing-token",
            "candidate_role": "direct_beneficiary",
            "impact_path_type": "listing_liquidity_event",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "source_class": "official_exchange",
            "evidence_specificity": "official_direct_event",
            "evidence_quality_score": 82,
            "evidence_acquisition_status": "no_results",
            "source_pack": "listing_liquidity_pack",
        },
    ]
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-live-confirmation-accepted",
            profile="live_burn_in_no_send",
            run_mode="notification_burn_in",
            artifact_namespace="live_burn_in_no_send",
        )
        stored = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    by_symbol = {row["symbol"]: row for row in stored}
    assert by_symbol["VELVET"]["final_opportunity_level"] == "high_priority"
    assert by_symbol["VELVET"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    assert by_symbol["VELVET"]["live_confirmation_passed"] is True
    assert by_symbol["VELVET"]["acquisition_confirmation_status"] == "confirms"
    assert by_symbol["LIST"]["final_opportunity_level"] == "validated_digest"
    assert by_symbol["LIST"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    assert by_symbol["LIST"]["live_confirmation_reason"] == "official_or_structured_source_confirmation"


def test_live_confirmation_caps_broad_treasury_valuation_but_allows_direct_project_stake():
    from crypto_rsi_scanner import event_alpha_router, event_core_opportunity_store, event_watchlist

    rows = [
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-btc-strategy-valuation",
            "incident_id": "incident-strategy-valuation",
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "candidate_role": "direct_subject",
            "impact_category": "strategic_investment_or_valuation",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "strategic_investment",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 78,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "canonical_incident_name": "Strategy trades below Bitcoin treasury valuation",
            "latest_source_title": "MSTR valuation discount widens versus Bitcoin holdings",
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 90,
            "market_confirmation_score": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "evidence_acquisition_status": "planned",
            "source_pack": "strategic_investment_pack",
        },
        {
            "row_type": "event_impact_hypothesis",
            "hypothesis_id": "hyp-aave-kraken-stake",
            "incident_id": "incident-aave-kraken",
            "symbol": "AAVE",
            "coin_id": "aave",
            "candidate_role": "direct_subject",
            "impact_category": "strategic_investment_or_valuation",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "strategic_investment",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 78,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "canonical_incident_name": "Kraken takes strategic stake in Aave ecosystem",
            "latest_source_title": "Kraken strategic investment directly names AAVE",
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "evidence_quality_score": 90,
            "market_confirmation_score": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
            "evidence_acquisition_status": "planned",
            "source_pack": "strategic_investment_pack",
        },
    ]
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-live-broad-strategy",
            profile="live_burn_in_no_send",
            run_mode="notification_burn_in",
            artifact_namespace="live_burn_in_no_send",
        )
        stored = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    by_symbol = {row["symbol"]: row for row in stored}
    assert by_symbol["BTC"]["final_opportunity_level"] == "exploratory"
    assert by_symbol["BTC"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert by_symbol["BTC"]["live_confirmation_passed"] is False
    assert by_symbol["BTC"]["live_confirmation_reason"] == "evidence_acquisition_not_executed"
    assert by_symbol["AAVE"]["final_opportunity_level"] == "validated_digest"
    assert by_symbol["AAVE"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    assert by_symbol["AAVE"]["live_confirmation_reason"] == "strong_direct_original_source_evidence"


def test_live_confirmation_gated_rows_surface_in_reports():
    from crypto_rsi_scanner import event_alpha_daily_brief, event_alpha_quality_review, event_alpha_router, event_core_opportunity_store, event_watchlist

    row = {
        "row_type": "event_impact_hypothesis",
        "hypothesis_id": "hyp-doge-skipped-budget",
        "incident_id": "incident-doge-strategic",
        "symbol": "DOGE",
        "coin_id": "dogecoin",
        "candidate_role": "direct_beneficiary",
        "impact_path_type": "strategic_investment",
        "opportunity_level": "validated_digest",
        "opportunity_score_final": 73,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "source_class": "crypto_news",
        "evidence_specificity": "direct_token_mechanism",
        "evidence_quality_score": 78,
        "market_confirmation_score": 10,
        "market_context_freshness_status": "missing",
        "evidence_acquisition_status": "skipped_budget",
        "source_pack": "strategic_investment_pack",
    }
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            [row],
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-live-confirmation-report",
            profile="live_burn_in_no_send",
            run_mode="notification_burn_in",
            artifact_namespace="live_burn_in_no_send",
        )
        stored = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    brief = event_alpha_daily_brief.build_daily_brief(
        core_opportunity_rows=stored,
        requested_profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        include_test_artifacts=True,
    )
    assert "## Live Confirmation Gated Candidates" in brief
    assert "DOGE/dogecoin" in brief
    assert "skipped_budget_not_confirmation" in brief
    digest_section = brief.split("## Validated Digest Core Opportunities", 1)[1].split("## Watchlist Core Opportunities", 1)[0]
    assert "DOGE/dogecoin" not in digest_section

    review = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(
            profile="live_burn_in_no_send",
            core_opportunity_rows=stored,
        )
    )
    assert "live_confirmation_gates:" in review
    assert "skipped_budget_capped=1" in review
    assert "Live Confirmation Gated Candidates:" in review


def test_event_core_opportunity_store_uses_refreshed_nested_market_context():
    from crypto_rsi_scanner import event_core_opportunity_store

    rows = _canonical_core_fixture_rows()
    velvet = dict(rows[0])
    velvet.update({
        "market_context_freshness_status": "fresh",
        "market_context_source": "missing",
        "market_context_age_hours": "unknown",
        "market_context_data_quality": "missing",
        "market_context_freshness_cap_applied": True,
        "market_context_after": {
            "timestamp": "2026-06-15T15:30:00+00:00",
            "age_seconds": 1800,
            "data_quality": "fresh",
            "source": "fixture_targeted_market_refresh",
            "market_snapshot": {
                "symbol": "VELVET",
                "coin_id": "velvet",
                "source": "fixture_targeted_market_refresh",
                "timestamp": "2026-06-15T15:30:00+00:00",
            },
        },
    })
    rows[0] = velvet

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        result = event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-market-context",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        assert result.success
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
    stored = next(row for row in loaded.rows if row["symbol"] == "VELVET")
    assert stored["market_context_freshness_status"] == "fresh"
    assert stored["market_context_source"] == "fixture_targeted_market_refresh"
    assert stored["market_context_data_quality"] == "fresh"
    assert stored["market_context_age_hours"] == 0.5
    assert stored["market_context_freshness_cap_applied"] is False


def test_event_core_opportunity_store_prevents_stale_support_near_miss():
    from crypto_rsi_scanner import event_core_opportunity_store, event_near_miss

    rows = _canonical_core_fixture_rows()
    merged = event_core_opportunity_store.merge_core_opportunity_verdict(
        rows[0],
        support_rows=[rows[1]],
    )
    assert merged["symbol"] == "VELVET"
    assert merged["final_opportunity_level"] == "high_priority"

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-near-miss",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
    near = event_near_miss.detect_near_miss_rows(loaded.rows)
    symbols = {item.symbol for item in near}
    assert "VELVET" not in symbols
    assert "RUNE" not in symbols


def test_event_alpha_daily_brief_uses_canonical_core_store_rows():
    from crypto_rsi_scanner import event_alpha_daily_brief, event_core_opportunity_store

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-brief",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
    brief = event_alpha_daily_brief.build_daily_brief(
        core_opportunity_rows=loaded.rows,
        requested_profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
        run_mode="burn_in",
        generated_at=pd.Timestamp("2026-06-15T12:00:00Z").to_pydatetime(),
    )
    assert "canonical_store_rows=4" in brief
    assert "## High-Priority Core Opportunities" in brief
    high_section = brief.split("## High-Priority Core Opportunities", 1)[1].split("## Validated Digest Core Opportunities", 1)[0]
    near_section = brief.split("## Near-Miss Candidates", 1)[1].split("## Upgrade Candidates", 1)[0]
    assert "VELVET/velvet" in high_section
    assert "VELVET/velvet" not in near_section


def test_canonical_core_resolution_links_diagnostics_and_orphans():
    from crypto_rsi_scanner import event_core_opportunities, event_core_opportunity_store

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-resolution",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        store_rows = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    velvet_core = next(row["core_opportunity_id"] for row in store_rows if row["symbol"] == "VELVET")
    rune_core = next(row["core_opportunity_id"] for row in store_rows if row["symbol"] == "RUNE")

    rune_resolution = event_core_opportunities.resolve_canonical_core_opportunity_id(
        {
            "incident_id": "incident-thorchain-exploit",
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "candidate_role": "direct_beneficiary",
            "impact_path_type": "exploit_security_event",
        },
        store_rows,
    )
    assert rune_resolution.resolution_status == "canonical"
    assert rune_resolution.canonical_core_opportunity_id == rune_core

    diagnostic = event_core_opportunities.resolve_canonical_core_opportunity_id(
        {
            "core_opportunity_id": "core_601f14c59028",
            "incident_id": "incident-spacex",
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "candidate_role": "source_noise",
            "latest_effective_playbook_type": "source_noise_control",
            "impact_path_type": "generic_cooccurrence_only",
        },
        store_rows,
    )
    assert diagnostic.resolution_status == "diagnostic_support"
    assert diagnostic.diagnostic_support_for_core_opportunity_id == velvet_core
    assert "noncanonical_core_id_replaced:core_601f14c59028" in diagnostic.warnings

    orphan = event_core_opportunities.resolve_canonical_core_opportunity_id(
        {
            "core_opportunity_id": "core_missing_visible",
            "incident_id": "incident-orphan",
            "validated_symbol": "ORPHAN",
            "validated_coin_id": "orphan",
            "candidate_role": "direct_beneficiary",
            "impact_path_type": "listing_liquidity_event",
            "opportunity_level": "watchlist",
        },
        store_rows,
    )
    assert orphan.resolution_status == "orphan"
    assert "visible_core_missing_store_row:core_missing_visible" in orphan.warnings

    explicit_orphan = event_core_opportunities.resolve_canonical_core_opportunity_id(
        {"core_opportunity_id": "core_missing_from_store"},
        store_rows,
    )
    assert explicit_orphan.resolution_status == "orphan"
    assert explicit_orphan.canonical_core_opportunity_id == "core_missing_from_store"
    assert "visible_core_missing_store_row:core_missing_from_store" in explicit_orphan.warnings


def test_research_cards_use_canonical_core_store_groups():
    from crypto_rsi_scanner import event_core_opportunity_store, event_research_cards

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=store_path),
            run_id="run-core-cards",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        store_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
        result = event_research_cards.write_research_cards(
            root / "cards",
            watchlist_entries=[],
            alert_rows=store_rows,
        )
        store_ids = {row["core_opportunity_id"] for row in store_rows}
        groups = event_research_cards.card_index_group_map(result.card_paths)
        reviewable_core_groups = {
            "Early Long Research Cards",
            "Confirmed Long Research Cards",
            "Fade / Short-Review Cards",
            "Risk Only Cards",
            "Unconfirmed Research Cards",
            "Core Opportunity Cards",
        }
        core_paths = [path for path in result.card_paths if groups[path] in reviewable_core_groups]
        assert core_paths
        assert all(event_research_cards.card_core_opportunity_id(path) in store_ids for path in core_paths)
        index_text = result.index_path.read_text(encoding="utf-8")
        promoted_sections = "\n".join(
            index_text.split(f"## {group_name}", 1)[1].split("\n## ", 1)[0]
            for group_name in reviewable_core_groups
            if f"## {group_name}" in index_text
        )
        local_section = index_text.split("## Local-Only / Quality-Capped Cards", 1)[1].split("## Diagnostic", 1)[0]
        assert "RUNE" in "".join(path.read_text(encoding="utf-8") for path in core_paths)
        assert "card_core_aa617f5bc943" in promoted_sections
        assert any(
            "memecore" in path.read_text(encoding="utf-8").casefold()
            for path, group in groups.items()
            if group == "Unconfirmed Research Cards"
        )
        link_update = event_core_opportunity_store.update_core_opportunity_card_links(
            store_path,
            result.card_paths,
            run_id="run-core-cards",
        )
        assert link_update.success
        assert link_update.rows_updated == len(store_ids)
        linked_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
        assert all(row.get("card_path") for row in linked_rows)


def test_research_card_index_groups_normal_unconfirmed_lane_before_near_miss_fallback():
    from crypto_rsi_scanner import event_research_cards

    with TemporaryDirectory() as tmp:
        card_path = Path(tmp) / "card_chz.md"
        card_path.write_text(
            "# CHZ Event Research Card\n\n"
            "- Opportunity type: UNCONFIRMED_RESEARCH\n"
            "- Quality: exploratory\n",
            encoding="utf-8",
        )
        groups = event_research_cards.card_index_group_map([card_path])
        assert groups[card_path] == "Unconfirmed Research Cards"


def test_research_cards_backfill_aggregated_support_core_rows():
    from crypto_rsi_scanner import event_alpha_router, event_core_opportunity_store, event_research_cards, event_watchlist

    rows = _canonical_core_fixture_rows()
    hidden_support = {
        **rows[-1],
        "hypothesis_id": "hyp-meme-generic-support",
        "core_opportunity_id": "core_memecore_generic_support",
        "impact_path_type": "generic_cooccurrence_only",
        "primary_impact_path": "generic_cooccurrence_only",
        "candidate_role": "generic_mention",
        "opportunity_level": "local_only",
        "opportunity_score_final": 0,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HYPOTHESIS.value,
        "evidence_specificity": "insufficient_data",
        "evidence_quality_score": 0,
    }
    rows.append(hidden_support)
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=store_path),
            run_id="run-core-cards-hidden-support",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        store_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
        result = event_research_cards.write_research_cards(
            root / "cards",
            watchlist_entries=[],
            alert_rows=store_rows,
            limit=50,
        )
        link_update = event_core_opportunity_store.update_core_opportunity_card_links(
            store_path,
            result.card_paths,
            run_id="run-core-cards-hidden-support",
        )
        linked_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
        by_id = {row["core_opportunity_id"]: row for row in linked_rows}
        assert link_update.success
        assert by_id["core_memecore_generic_support"]["card_path"]
        assert any(
            event_research_cards.card_core_opportunity_id(path) == "core_memecore_generic_support"
            for path in result.card_paths
        )


def test_research_card_primary_fields_use_canonical_core_row():
    from crypto_rsi_scanner import event_core_opportunity_store, event_research_cards

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=store_path),
            run_id="run-core-card-primary",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        store_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
    velvet = {
        **next(row for row in store_rows if row["symbol"] == "VELVET"),
        "validation_stage": "impact_path_validated",
        "main_frame_type": "proxy_attention",
        "main_frame_role": "main_catalyst",
        "main_frame_subject": "SpaceX",
        "main_frame_actor": "Velvet",
        "main_frame_object": "pre-IPO exposure",
        "frame_status": "validated",
        "latest_source": "impact_hypothesis",
        "source_provider": "impact_hypothesis",
        "evidence_acquisition_accepted_count": 1,
        "evidence_acquisition_accepted_evidence": [{
            "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
            "provider": "cryptopanic",
            "source_url": "https://cryptopanic.com/news/velvet-spacex-pre-ipo",
            "reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        }],
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        "evidence_acquisition_results": {"status": "accepted_evidence_found", "accepted": 1, "rejected": 0},
    }
    stale_support = {
        **velvet,
        "row_type": "event_alpha_alert_snapshot",
        "tier": "STORE_ONLY",
        "state": "RADAR",
        "route": "STORE_ONLY",
        "opportunity_level": "local_only",
        "opportunity_score_final": 0,
        "impact_path_type": "insufficient_data",
        "evidence_acquisition_attempted": False,
        "evidence_acquisition_status": "not_executed",
    }
    card = event_research_cards.render_research_card(
        velvet["core_opportunity_id"],
        watchlist_entries=[],
        alert_rows=[stale_support, velvet],
    )
    assert "- State / alert tier: HIGH_PRIORITY / HIGH_PRIORITY_RESEARCH" in card.markdown
    assert "- Source pack: proxy_preipo_rwa_pack" in card.markdown
    assert "- Latest source: cryptopanic" in card.markdown
    assert "- Latest source: unknown" not in card.markdown
    assert "- Latest source: not available" not in card.markdown
    assert "- Evidence acquisition attempted: true" in card.markdown
    assert "accepted=1" in card.markdown
    assert "cryptopanic_currency_tag_match" in card.markdown
    assert "VELVET offers SpaceX pre-IPO tokenized stock exposure" in card.markdown
    assert "- Impact path strength: strong" in card.markdown
    assert "- Impact path strength: unknown" not in card.markdown
    assert "- Impact path reason: venue_value_capture" in card.markdown
    assert "- Impact path digest eligible: true" in card.markdown
    assert "- Market confirmation: strong / 88" in card.markdown
    assert "No market snapshot stored" not in card.markdown
    assert "Market data: not available" not in card.markdown
    assert "Already high priority" in card.markdown
    assert "blocked by generic cooccurrence" not in card.markdown
    assert "needs proof that this event directly affects the token" not in card.markdown
    assert "no token value-capture mechanism is visible" not in card.markdown
    assert "- Opportunity verdict: high_priority / 92.0" in card.markdown
    assert "- Relationship: venue_value_capture" in card.markdown
    assert "- Quality gate: passed final quality gate (HIGH_PRIORITY_RESEARCH)" in card.markdown
    assert "- Why promoted/local-only: Core opportunity verdict reached high_priority." in card.markdown
    assert "Quality gate: local-only" not in card.markdown
    assert "validated impact hypothesis promoted to RADAR" not in card.markdown
    assert "STORE_ONLY" not in card.markdown.split("## Artifact Lineage", 1)[0]


def test_opportunity_audit_primary_sections_use_canonical_core_view():
    from crypto_rsi_scanner import event_core_opportunity_store, event_opportunity_audit

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=store_path),
            run_id="run-core-audit-primary",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        store_rows = event_core_opportunity_store.load_core_opportunities(store_path, latest_run=True).rows
    velvet = {
        **next(row for row in store_rows if row["symbol"] == "VELVET"),
        "evidence_acquisition_accepted_count": 1,
        "evidence_acquisition_accepted_evidence": [{
            "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
            "provider": "cryptopanic",
            "source_url": "https://cryptopanic.com/news/velvet-spacex-pre-ipo",
            "reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        }],
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
        "evidence_acquisition_results": {"status": "accepted_evidence_found", "accepted": 1, "rejected": 0},
    }
    stale_support = {
        **velvet,
        "row_type": "event_alpha_alert_snapshot",
        "opportunity_level": "local_only",
        "opportunity_score_final": 0,
        "impact_path_type": "insufficient_data",
        "upgrade_requirements": ["blocked_by_generic_cooccurrence", "needs_direct_token_mechanism"],
        "downgrade_warnings": ["no_value_capture"],
    }
    incident_row = {
        "row_type": "event_incident",
        "run_id": "run-core-audit-primary",
        "profile": "market_refresh_smoke",
        "artifact_namespace": "market_refresh_smoke",
        "incident_id": velvet["incident_id"],
        "canonical_name": "SpaceX pre-IPO exposure via Velvet",
        "canonical_incident_name": "SpaceX pre-IPO exposure via Velvet",
        "incident_relevance_status": "active_incident",
        "incident_relevance_score": 100.0,
        "primary_subject": "SpaceX pre-IPO exposure",
        "main_frame_type": "proxy_attention",
        "main_frame_role": "main_catalyst",
        "main_frame_subject": "SpaceX pre-IPO exposure",
        "main_frame_actor": "Velvet",
        "main_frame_object": "pre-IPO trading venue",
        "main_frame_evidence_quote": "Velvet users can trade SpaceX pre-IPO exposure",
        "linked_assets": [{"symbol": "VELVET", "coin_id": "velvet", "role": "proxy_venue"}],
    }
    audit = event_opportunity_audit.format_opportunity_audit(
        velvet["core_opportunity_id"],
        core_opportunity_rows=[velvet],
        alert_rows=[stale_support],
        incident_rows=[incident_row],
        profile="market_refresh_smoke",
    )
    assert "- impact path: venue_value_capture" in audit
    assert "- strength: strong" in audit
    assert "- reason: venue_value_capture" in audit
    assert "- source pack: proxy_preipo_rwa_pack" in audit
    assert "accepted reason codes: cryptopanic_currency_tag_match; direct_token_mechanism" in audit
    assert "VELVET offers SpaceX pre-IPO tokenized stock exposure" in audit
    assert "- market level/score: strong / 88" in audit
    assert "Already high priority" in audit
    assert "blocked by generic cooccurrence" not in audit
    assert "needs proof that this event directly affects the token" not in audit
    assert "no token value-capture mechanism is visible" not in audit
    assert "- main catalyst frame: proxy_attention (main_catalyst)" in audit
    assert "- main catalyst subject/actor/object: SpaceX pre-IPO exposure / Velvet / pre-IPO trading venue" in audit
    assert "- main catalyst evidence: Velvet users can trade SpaceX pre-IPO exposure" in audit


def test_canonical_core_opportunity_view_loads_linked_artifacts():
    import json
    from crypto_rsi_scanner import event_alpha_router, event_core_opportunity_store, event_research_cards

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        alert_path = root / "event_alpha_alerts.jsonl"
        acquisition_path = root / "event_evidence_acquisition.jsonl"
        incident_path = root / "event_incidents.jsonl"
        feedback_path = root / "event_alpha_feedback.jsonl"
        card_dir = root / "cards"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-view",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        cards = event_research_cards.write_research_cards(card_dir, watchlist_entries=[], alert_rows=core_rows)
        event_core_opportunity_store.update_core_opportunity_card_links(
            core_path,
            cards.card_paths,
            run_id="run-core-view",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        velvet = next(row for row in core_rows if row["symbol"] == "VELVET")
        meme = next(row for row in core_rows if row["symbol"] == "MEME")
        alert_path.write_text(
            json.dumps({
                "row_type": "event_alpha_alert_snapshot",
                "run_id": "run-core-view",
                "profile": "market_refresh_smoke",
                "artifact_namespace": "market_refresh_smoke",
                "alert_id": "alert-velvet-core",
                "core_opportunity_id": velvet["core_opportunity_id"],
                "symbol": "VELVET",
                "coin_id": "velvet",
                "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            }) + "\n",
            encoding="utf-8",
        )
        acquisition_path.write_text(
            "\n".join([
                json.dumps({
                    "row_type": "event_evidence_acquisition",
                    "run_id": "run-core-view",
                    "profile": "market_refresh_smoke",
                    "artifact_namespace": "market_refresh_smoke",
                    "core_opportunity_id": velvet["core_opportunity_id"],
                    "hypothesis_id": "hyp-velvet-core",
                    "symbol": "VELVET",
                    "coin_id": "velvet",
                    "status": "accepted_evidence_found",
                    "queries_executed": 3,
                }),
                json.dumps({
                    "row_type": "event_evidence_acquisition",
                    "run_id": "run-core-view",
                    "profile": "market_refresh_smoke",
                    "artifact_namespace": "market_refresh_smoke",
                    "core_opportunity_id": meme["core_opportunity_id"],
                    "original_core_opportunity_id": "core_legacy_memecore",
                    "hypothesis_id": "hyp-meme-core",
                    "symbol": "MEME",
                    "coin_id": "memecore",
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        feedback_path.write_text(
            json.dumps({
                "row_type": "event_alpha_feedback",
                "target": velvet["core_opportunity_id"],
                "label": "useful",
                "marked_at": "2026-06-15T13:00:00+00:00",
                "marked_by": "human",
                "symbol": "VELVET",
                "coin_id": "velvet",
            }) + "\n",
            encoding="utf-8",
        )
        incident_path.write_text(
            json.dumps({
                "row_type": "event_incident",
                "run_id": "run-core-view",
                "profile": "market_refresh_smoke",
                "artifact_namespace": "market_refresh_smoke",
                "incident_id": velvet["incident_id"],
                "canonical_name": "SpaceX pre-IPO exposure via Velvet",
                "canonical_incident_name": "SpaceX pre-IPO exposure via Velvet",
                "incident_relevance_status": "active_incident",
                "incident_relevance_score": 100.0,
                "primary_subject": "SpaceX pre-IPO exposure",
                "main_frame_type": "proxy_attention",
                "main_frame_role": "main_catalyst",
                "main_frame_subject": "SpaceX pre-IPO exposure",
                "main_frame_actor": "Velvet",
                "main_frame_object": "pre-IPO trading venue",
                "main_frame_evidence_quote": "Velvet users can trade SpaceX pre-IPO exposure",
                "linked_assets": [{"symbol": "VELVET", "coin_id": "velvet", "role": "proxy_venue"}],
                "last_updated_at": "2026-06-15T13:00:00+00:00",
            }) + "\n",
            encoding="utf-8",
        )
        view = event_core_opportunity_store.load_canonical_core_opportunity_view(
            "market_refresh_smoke",
            "market_refresh_smoke",
            velvet["core_opportunity_id"],
            core_store_path=core_path,
            alert_store_path=alert_path,
            evidence_acquisition_path=acquisition_path,
            incident_store_path=incident_path,
            feedback_path=feedback_path,
            research_cards_dir=card_dir,
        )
        legacy = event_core_opportunity_store.load_canonical_core_opportunity_view(
            "market_refresh_smoke",
            "market_refresh_smoke",
            "core_legacy_memecore",
            core_store_path=core_path,
            evidence_acquisition_path=acquisition_path,
        )

    assert view.found
    assert view.symbol == "VELVET"
    assert view.coin_id == "velvet"
    assert view.opportunity_level == "high_priority"
    assert view.final_route_after_quality_gate == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    assert view.research_card_path and view.research_card_path.endswith(".md")
    assert len(view.evidence_acquisition_rows) == 1
    assert view.evidence_acquisition_rows[0]["status"] == "accepted_evidence_found"
    assert len(view.alert_snapshot_rows) == 1
    assert len(view.incident_rows) == 1
    assert view.incident_row
    assert view.incident_row["main_frame_type"] == "proxy_attention"
    assert view.incident_row["incident_relevance_status"] == "active_incident"
    assert view.feedback_status == "has_feedback"
    assert view.market_refresh_rows
    assert legacy.found
    assert legacy.symbol == "MEME"
    assert "input_target_resolved_to_canonical:core_legacy_memecore->" in ";".join(legacy.warnings)


def test_alert_snapshots_mark_source_noise_as_diagnostic_support():
    from dataclasses import replace
    from crypto_rsi_scanner import (
        event_alpha_alert_store,
        event_alpha_router,
        event_core_opportunity_store,
        event_watchlist,
    )

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-snapshots",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        velvet_core = next(row["core_opportunity_id"] for row in core_rows if row["symbol"] == "VELVET")
        entry = replace(
            _test_watchlist_entry(state=event_watchlist.EventWatchlistState.RADAR.value, symbol="VELVET", coin_id="velvet"),
            key="incident-spacex|velvet|source_noise_control",
            incident_id="incident-spacex",
            relationship_type="impact_hypothesis",
            latest_effective_playbook_type="source_noise_control",
            latest_playbook_type="source_noise_control",
            latest_score_components={
                "incident_id": "incident-spacex",
                "validated_symbol": "VELVET",
                "validated_coin_id": "velvet",
                "candidate_role": "source_noise",
                "impact_path_type": "generic_cooccurrence_only",
                "opportunity_level": "local_only",
                "opportunity_score_final": 0,
                "core_opportunity_id": "core_601f14c59028",
            },
        )
        decision = event_alpha_router.EventAlphaRouteDecision(
            entry=entry,
            route=event_alpha_router.EventAlphaRoute.STORE_ONLY,
            alertable=False,
            reason="source-noise control",
            requested_route_before_quality_gate=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            final_route_after_quality_gate=event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            quality_gate_block_reason="source_noise_control",
        )
        store_path = root / "alerts.jsonl"
        event_alpha_alert_store.write_alert_snapshots(
            [],
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=store_path),
            router_result=event_alpha_router.EventAlphaRouterResult(Path("state.jsonl"), 1, [decision], True),
            core_opportunity_rows=core_rows,
        )
        rows = event_alpha_alert_store.load_alert_snapshots(store_path).rows
    assert rows[0]["is_diagnostic_snapshot"] is True
    assert rows[0]["core_opportunity_id_status"] == "diagnostic_support"
    assert rows[0]["diagnostic_support_for_core_opportunity_id"] == velvet_core
    assert rows[0]["core_opportunity_id"] == velvet_core


def test_alert_snapshots_reconcile_with_canonical_core_store():
    from crypto_rsi_scanner import event_alpha_alert_store, event_alpha_router, event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-snapshot-reconcile",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_chz_world_cup",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "validated_symbol": "CHZ",
        "validated_coin_id": "chiliz",
        "final_opportunity_level": "exploratory",
        "opportunity_level": "exploratory",
        "final_opportunity_score": 58,
        "opportunity_score_final": 58,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "state": event_watchlist.EventWatchlistState.RADAR.value,
        "evidence_acquisition_status": "no_results",
        "acquisition_confirmation_status": "does_not_confirm",
        "acquisition_confirms_candidate": False,
        "acquisition_confirms_impact_path": False,
        "live_confirmation_required": True,
        "live_confirmation_passed": False,
        "live_confirmation_status": "missing",
        "live_confirmation_reason": "no_results_not_confirmation",
        "live_confirmation_capped": True,
        "live_confirmation_missing_requirements": ["accepted_evidence"],
        "feedback_target": "core_chz_world_cup",
        "feedback_target_type": "core_opportunity_id",
    }
    stale_snapshot = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-snapshot-reconcile",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "live_burn_in_no_send",
        "alert_id": "ea:chz",
        "alert_key": "event:chz",
        "core_opportunity_id": "core_chz_world_cup",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "opportunity_level": "validated_digest",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 71,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "route": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "tier": "RADAR_DIGEST",
        "final_tier_after_quality_gate": "RADAR_DIGEST",
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.WATCHLIST.value,
        "state": event_watchlist.EventWatchlistState.WATCHLIST.value,
        "alertable_after_quality_gate": True,
        "route_alertable": True,
        "evidence_acquisition_status": "not_executed",
    }

    reconciled = event_alpha_alert_store.reconcile_alert_snapshot_with_core_store(stale_snapshot, core)
    assert reconciled["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert reconciled["route"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert reconciled["final_opportunity_level"] == "exploratory"
    assert reconciled["opportunity_level"] == "exploratory"
    assert reconciled["final_state_after_quality_gate"] == event_watchlist.EventWatchlistState.RADAR.value
    assert reconciled["alertable_after_quality_gate"] is False
    assert reconciled["route_alertable"] is False
    assert reconciled["evidence_acquisition_status"] == "no_results"
    assert reconciled["acquisition_confirmation_status"] == "does_not_confirm"
    assert reconciled["live_confirmation_capped"] is True
    assert reconciled["live_confirmation_reason"] == "no_results_not_confirmation"
    assert reconciled["requested_route_before_core_reconciliation"] == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    assert reconciled["requested_opportunity_level_before_core_reconciliation"] == "validated_digest"
    assert reconciled["snapshot_core_reconciled"] is True
    assert reconciled["snapshot_core_resolution_status"] == event_alpha_alert_store.SNAPSHOT_CORE_RECONCILED
    assert reconciled["snapshot_core_reconciliation_reason"] == "canonical_core_final_state_applied"

    aligned = event_alpha_alert_store.reconcile_alert_snapshot_with_core_store(reconciled, core)
    assert aligned["snapshot_core_reconciliation_reason"] == "canonical_core_aligned"


def test_diagnostic_support_snapshot_does_not_inherit_canonical_alertable_route():
    import json
    from crypto_rsi_scanner import (
        event_alpha_alert_store,
        event_alpha_artifact_doctor,
        event_alpha_daily_brief,
        event_alpha_notification_inbox,
        event_alpha_router,
        event_watchlist,
    )

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-diagnostic-support",
        "profile": "evidence_acquisition_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "evidence_acquisition_smoke",
        "core_opportunity_id": "agg:3381ebd96566",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "impact_path_type": "venue_value_capture",
        "final_opportunity_level": "high_priority",
        "opportunity_level": "high_priority",
        "final_opportunity_score": 92,
        "opportunity_score_final": 92,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        "state": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        "feedback_target": "agg:3381ebd96566",
        "feedback_target_type": "core_opportunity_id",
    }
    canonical_snapshot = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-diagnostic-support",
        "profile": "evidence_acquisition_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "evidence_acquisition_smoke",
        "alert_id": "ea:velvet-canonical",
        "alert_key": "event:velvet-canonical",
        "core_opportunity_id": "agg:3381ebd96566",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "impact_path_type": "venue_value_capture",
        "final_opportunity_level": "high_priority",
        "opportunity_level": "high_priority",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "alertable_after_quality_gate": True,
        "route_alertable": True,
    }
    support_snapshot = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-diagnostic-support",
        "profile": "evidence_acquisition_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "evidence_acquisition_smoke",
        "alert_id": "ea:velvet-support",
        "alert_key": "event:velvet-support",
        "core_opportunity_id": "agg:3381ebd96566",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "candidate_role": "source_noise",
        "latest_effective_playbook_type": "source_noise_control",
        "impact_path_type": "insufficient_data",
        "evidence_specificity": "insufficient_data",
        "source_class": "insufficient_data",
        "quality_gate_block_reason": "impact_path_type_insufficient_data",
        "final_opportunity_level": "local_only",
        "opportunity_level": "local_only",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "alertable_after_quality_gate": False,
        "route_alertable": False,
    }

    rows = event_alpha_alert_store.reconcile_alert_snapshots_with_core_store(
        [canonical_snapshot, support_snapshot],
        [core],
    )
    canonical = next(row for row in rows if row["alert_id"] == "ea:velvet-canonical")
    support = next(row for row in rows if row["alert_id"] == "ea:velvet-support")

    assert canonical["snapshot_class"] == event_alpha_alert_store.SNAPSHOT_CLASS_CANONICAL_CORE
    assert canonical["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    assert canonical["alertable_after_quality_gate"] is True
    assert support["snapshot_class"] == event_alpha_alert_store.SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
    assert support["core_resolution_status"] == "diagnostic_support"
    assert support["diagnostic_support_for_core_opportunity_id"] == "agg:3381ebd96566"
    assert support["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert support["final_opportunity_level"] == "local_only"
    assert support["alertable_after_quality_gate"] is False
    assert support["support_for_core_summary"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        with (root / "event_core_opportunities.jsonl").open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(core) + "\n")
        with (root / "event_alpha_alerts.jsonl").open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        loaded = event_alpha_alert_store.load_alert_snapshots(root / "event_alpha_alerts.jsonl")
        loaded_support = next(row for row in loaded.rows if row["alert_id"] == "ea:velvet-support")
        assert loaded_support["snapshot_class"] == event_alpha_alert_store.SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        assert loaded_support["core_resolution_status"] == "diagnostic_support"
        assert loaded_support["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
        assert loaded_support["alertable_after_quality_gate"] is False

    alertable = [
        row for row in rows
        if row.get("alertable_after_quality_gate")
        and event_alpha_router.route_value_is_alertable(row.get("final_route_after_quality_gate"))
    ]
    assert [row["alert_id"] for row in alertable] == ["ea:velvet-canonical"]

    brief = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{
            "run_id": "run-diagnostic-support",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "success": True,
            "alertable": 2,
        }],
        core_opportunity_rows=[core],
        alert_rows=rows,
        requested_profile="evidence_acquisition_smoke",
        artifact_namespace="evidence_acquisition_smoke",
        include_test_artifacts=True,
    )
    assert "- Alertable routed decisions: 1" in brief

    inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=[{
            "run_id": "run-diagnostic-support",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "would_send_count": 2,
            "lane_counts_due": {"research_digest": 2},
        }],
        alert_rows=rows,
        feedback_rows=[],
        research_cards_dir=Path("/tmp"),
        profile="evidence_acquisition_smoke",
        artifact_namespace="evidence_acquisition_smoke",
        notification_runs_path=Path("/tmp/runs.jsonl"),
        alert_store_path=Path("/tmp/alerts.jsonl"),
        feedback_path=Path("/tmp/feedback.jsonl"),
    )
    assert all(item.get("alert_id") != "ea:velvet-support" for item in inbox.would_send_without_feedback)

    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-diagnostic-support",
            "profile": "evidence_acquisition_smoke",
            "artifact_namespace": "evidence_acquisition_smoke",
            "success": True,
        }],
        core_opportunity_rows=[core],
        alert_rows=rows,
        profile="evidence_acquisition_smoke",
        artifact_namespace="evidence_acquisition_smoke",
        strict=True,
    )
    assert doctor.diagnostic_support_snapshot_alertable == 0
    assert doctor.diagnostic_support_snapshot_inherits_core_route == 0
    assert doctor.duplicate_alertable_snapshot_for_core == 0
    assert not any("diagnostic_support_snapshot" in item for item in doctor.blockers)


def test_opportunity_audit_primary_snapshot_prefers_canonical_over_diagnostic():
    from crypto_rsi_scanner import event_alpha_router, event_opportunity_audit, event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-audit-canonical-snapshot",
        "profile": "evidence_acquisition_smoke",
        "artifact_namespace": "evidence_acquisition_smoke",
        "core_opportunity_id": "agg:3381ebd96566",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "primary_impact_path": "venue_value_capture",
        "impact_path_type": "venue_value_capture",
        "final_opportunity_level": "high_priority",
        "opportunity_level": "high_priority",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        "feedback_target": "agg:3381ebd96566",
    }
    diagnostic = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-audit-canonical-snapshot",
        "alert_id": "ea:velvet-support",
        "core_opportunity_id": "agg:3381ebd96566",
        "snapshot_class": "diagnostic_support_snapshot",
        "core_resolution_status": "diagnostic_support",
        "snapshot_core_resolution_status": "diagnostic_support",
        "is_diagnostic_snapshot": True,
        "candidate_role": "source_noise",
        "playbook_type": "source_noise_control",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
    }
    canonical = {
        **diagnostic,
        "alert_id": "ea:velvet-canonical",
        "snapshot_class": "canonical_core_snapshot",
        "core_resolution_status": "canonical",
        "snapshot_core_resolution_status": "core_reconciled",
        "is_diagnostic_snapshot": False,
        "candidate_role": "proxy_venue",
        "playbook_type": "proxy_attention",
        "tier": "HIGH_PRIORITY_WATCH",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "alertable_after_quality_gate": True,
    }

    audit = event_opportunity_audit.format_opportunity_audit(
        "agg:3381ebd96566",
        core_opportunity_rows=[core],
        alert_rows=[diagnostic, canonical],
        profile="evidence_acquisition_smoke",
    )
    assert "- primary snapshot class: canonical_core_snapshot" in audit
    assert "- snapshot route after reconciliation: HIGH_PRIORITY_RESEARCH" in audit
    assert "- reconciliation status: core_reconciled" in audit
    assert "diagnostic snapshot: alert_id=ea:velvet-support" not in audit

    audit_with_diagnostics = event_opportunity_audit.format_opportunity_audit(
        "agg:3381ebd96566",
        core_opportunity_rows=[core],
        alert_rows=[diagnostic, canonical],
        profile="evidence_acquisition_smoke",
        include_diagnostics=True,
    )
    assert "diagnostic snapshot: alert_id=ea:velvet-support" in audit_with_diagnostics


def test_alert_snapshot_load_reconciles_sibling_core_store_and_reports_counts():
    import json
    from crypto_rsi_scanner import (
        event_alpha_alert_store,
        event_alpha_daily_brief,
        event_alpha_feedback_readiness,
        event_alpha_notification_inbox,
        event_alpha_router,
        event_watchlist,
    )

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        alert_path = root / "event_alpha_alerts.jsonl"
        core = {
            "row_type": "event_core_opportunity",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": "run-load-reconcile",
            "profile": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "live_burn_in_no_send",
            "core_opportunity_id": "core_arg_world_cup",
            "symbol": "ARG",
            "coin_id": "argentine-football-association-fan-token",
            "final_opportunity_level": "exploratory",
            "opportunity_level": "exploratory",
            "final_opportunity_score": 52,
            "opportunity_score_final": 52,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "state": event_watchlist.EventWatchlistState.RADAR.value,
            "evidence_acquisition_status": "no_results",
            "live_confirmation_required": True,
            "live_confirmation_passed": False,
            "live_confirmation_capped": True,
            "live_confirmation_reason": "no_results_not_confirmation",
            "feedback_target": "core_arg_world_cup",
            "feedback_target_type": "core_opportunity_id",
        }
        stale_snapshot = {
            "row_type": "event_alpha_alert_snapshot",
            "run_id": "run-load-reconcile",
            "profile": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "live_burn_in_no_send",
            "observed_at": "2026-06-15T12:00:00+00:00",
            "alert_id": "ea:arg",
            "alert_key": "event:arg",
            "core_opportunity_id": "core_arg_world_cup",
            "symbol": "ARG",
            "coin_id": "argentine-football-association-fan-token",
            "opportunity_level": "validated_digest",
            "final_opportunity_level": "validated_digest",
            "opportunity_score_final": 73,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "route": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "tier": "RADAR_DIGEST",
            "alertable_after_quality_gate": True,
            "route_alertable": True,
        }
        core_path.write_text(json.dumps(core) + "\n", encoding="utf-8")
        alert_path.write_text(json.dumps(stale_snapshot) + "\n", encoding="utf-8")

        loaded = event_alpha_alert_store.load_alert_snapshots(alert_path)
        assert loaded.rows_read == 1
        row = loaded.rows[0]
        assert row["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
        assert row["alertable_after_quality_gate"] is False
        assert row["snapshot_core_reconciled"] is True

        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[{
                "run_id": "run-load-reconcile",
                "profile": "live_burn_in_no_send",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "live_burn_in_no_send",
                "success": True,
                "routed": 1,
                "alertable": 1,
                "sent": False,
            }],
            core_opportunity_rows=[core],
            alert_rows=loaded.rows,
            requested_profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
        )
        assert "- Alertable routed decisions: 0" in brief
        assert "- Routed/alertable/sent: 1 / 0 (run_ledger_pre_core=1) / false" in brief

        inbox = event_alpha_notification_inbox.build_notification_inbox(
            notification_runs=[{
                "run_id": "run-load-reconcile",
                "profile": "live_burn_in_no_send",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "live_burn_in_no_send",
                "would_send_count": 1,
                "lane_counts_due": {"research_digest": 1},
            }],
            alert_rows=loaded.rows,
            feedback_rows=[],
            research_cards_dir=root,
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            notification_runs_path=root / "runs.jsonl",
            alert_store_path=alert_path,
            feedback_path=root / "feedback.jsonl",
        )
        assert len(inbox.would_send_without_feedback) == 0
        assert len(inbox.sent_without_feedback) == 0

        readiness = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            card_paths=[],
            alert_rows=loaded.rows,
            feedback_rows=[],
            watchlist_entries=[],
            inbox_result=inbox,
        )
        assert readiness.alert_rows_core_reconciled == 1
        assert readiness.stale_snapshot_routes_capped == 1
        assert readiness.snapshots_missing_core_store == 0
        assert "stale_routes_capped=1" in event_alpha_feedback_readiness.format_feedback_readiness(readiness)


def test_opportunity_audit_exposes_snapshot_core_reconciliation():
    from crypto_rsi_scanner import event_alpha_alert_store, event_alpha_router, event_opportunity_audit, event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-snapshot-audit",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_audit_chz",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "candidate_role": "proxy_instrument",
        "primary_impact_path": "fan_token_event",
        "impact_path_type": "fan_token_event",
        "final_opportunity_level": "exploratory",
        "opportunity_level": "exploratory",
        "final_opportunity_score": 55,
        "opportunity_score_final": 55,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "state": event_watchlist.EventWatchlistState.RADAR.value,
    }
    stale = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-snapshot-audit",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_audit_chz",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "final_opportunity_level": "validated_digest",
        "opportunity_level": "validated_digest",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "route": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
    }
    reconciled = event_alpha_alert_store.reconcile_alert_snapshot_with_core_store(stale, core)
    audit = event_opportunity_audit.format_opportunity_audit(
        "core_audit_chz",
        core_opportunity_rows=[core],
        alert_rows=[reconciled],
        profile="live_burn_in_no_send",
    )
    assert "## Alert snapshot / core reconciliation" in audit
    assert "- snapshot route before reconciliation: RESEARCH_DIGEST" in audit
    assert "- snapshot route after reconciliation: STORE_ONLY" in audit
    assert "- canonical core final route/level: STORE_ONLY / exploratory" in audit
    assert "- reconciliation status: core_reconciled" in audit
    assert "- alertable after reconciliation: false" in audit


def test_daily_brief_splits_core_market_freshness_from_support_gaps():
    from crypto_rsi_scanner import event_alpha_daily_brief

    rows = _canonical_core_fixture_rows()
    brief = event_alpha_daily_brief.build_daily_brief(
        hypothesis_rows=rows,
        requested_profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
        include_test_artifacts=True,
        include_legacy_artifacts=True,
    )
    freshness = brief.split("## Market Freshness Readiness", 1)[1].split("## Diagnostics Appendix", 1)[0]
    velvet_line = next(line for line in freshness.splitlines() if "VELVET/velvet" in line)
    assert "core_market_freshness_status=fresh" in velvet_line
    assert "core_market_context_source=market_refresh" in velvet_line
    assert "core_market_refresh_needed=false" in velvet_line
    assert "support_rows_stale_or_missing_count=1" in velvet_line
    assert "status=fresh source=missing" not in freshness


def test_daily_brief_evidence_plans_and_executions_are_counted_separately():
    from crypto_rsi_scanner import event_alpha_daily_brief

    acquisition = {
        "row_type": "event_evidence_acquisition",
        "profile": "market_refresh_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "market_refresh_smoke",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "status": "accepted_evidence_found",
        "queries_executed": 3,
        "accepted_evidence": [{"title": "Velvet confirms SpaceX exposure"}],
    }
    brief = event_alpha_daily_brief.build_daily_brief(
        hypothesis_rows=[],
        evidence_acquisition_rows=[acquisition],
        requested_profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
        include_test_artifacts=True,
        include_legacy_artifacts=True,
    )
    coverage = brief.split("## Source Coverage / Evidence Acquisition", 1)[1].split("### Provider Health by Source Pack", 1)[0]
    assert "evidence_plans_created=0" in coverage
    assert "acquisition_requests_executed=1" in coverage
    assert "provider_queries_executed=3" in coverage
    assert "accepted_evidence_found=1" in coverage
    assert "Evidence plans: 0 candidate" not in coverage


def test_event_asset_knowledge_and_role_validation_caps_taxonomy_and_broad_assets():
    from crypto_rsi_scanner import event_identity

    btc = event_identity.asset_knowledge_for(symbol="BTC", coin_id="bitcoin")
    rune = event_identity.asset_knowledge_for(symbol="RUNE", coin_id="thorchain")
    velvet = event_identity.asset_knowledge_for(symbol="VELVET", coin_id="velvet")
    link = event_identity.asset_knowledge_for(symbol="LINK", coin_id="chainlink")
    tether = event_identity.asset_knowledge_for(symbol="USDT", coin_id="tether")
    assert btc.broad_macro_asset is True
    assert rune.project_entities == ("THORChain",)
    assert velvet.role_capabilities.can_be_proxy_venue is True
    assert link.role_capabilities.can_be_infrastructure is True

    taxonomy = event_identity.validate_asset_role(
        link,
        event_identity.ROLE_DIRECT_SUBJECT,
        impact_category="security_or_regulatory_shock",
        role_source=event_identity.ROLE_SOURCE_TAXONOMY_CANDIDATE,
        source_text="THORChain confirms a RUNE exploit; Chainlink is an oracle taxonomy candidate.",
    )
    assert taxonomy.accepted is False
    assert taxonomy.final_role == event_identity.ROLE_GENERIC_MENTION
    assert "taxonomy_candidate_not_affected_asset" in taxonomy.failures

    broad = event_identity.validate_asset_role(
        btc,
        event_identity.ROLE_DIRECT_SUBJECT,
        impact_category="strategic_investment_or_valuation",
        source_text="Kraken buys a stake in Aave while Bitcoin markets are mentioned as context.",
        market_confirmation=20,
    )
    assert broad.accepted is False
    assert broad.final_role == event_identity.ROLE_MACRO_AFFECTED_ASSET
    assert "broad_macro_asset_context_only" in broad.failures

    stable = event_identity.validate_asset_role(
        tether,
        event_identity.ROLE_DIRECT_SUBJECT,
        impact_category="market_anomaly_unknown",
        source_text="USDT market anomaly without catalyst evidence.",
    )
    assert stable.accepted is False
    assert "stable_or_wrapped_asset_not_market_anomaly_candidate" in stable.failures


def test_event_impact_path_uses_asset_knowledge_for_roles_and_broad_context():
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from crypto_rsi_scanner import event_impact_path_validator
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent

    now = datetime(2026, 6, 20, tzinfo=timezone.utc)

    def raw(raw_id: str, title: str, body: str) -> RawDiscoveredEvent:
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_news",
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.com/{raw_id}",
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.90,
            content_hash=raw_id,
        )

    aave_raw = raw(
        "aave_kraken",
        "Kraken buys strategic stake in Aave",
        "Kraken acquired a strategic stake in Aave; Bitcoin is mentioned only as broad market context.",
    )
    aave_hypothesis = SimpleNamespace(
        impact_category="strategic_investment_or_valuation",
        external_asset="Kraken",
        score_components={"validation_strength": 95, "market_confirmation": 45},
    )
    aave = event_impact_path_validator.validate_impact_path(
        aave_raw,
        aave_hypothesis,
        symbol="AAVE",
        coin_id="aave",
        score_components=aave_hypothesis.score_components,
    )
    assert aave.candidate_role == "direct_subject"
    assert aave.asset_kind == "protocol_token"
    assert aave.role_validation_failures == ()

    btc = event_impact_path_validator.validate_impact_path(
        aave_raw,
        aave_hypothesis,
        symbol="BTC",
        coin_id="bitcoin",
        score_components=aave_hypothesis.score_components,
    )
    assert btc.candidate_role == "macro_affected_asset"
    assert btc.impact_path_strength == "weak"
    assert btc.digest_eligible_by_impact_path is False
    assert "broad_macro_asset_context_only" in btc.role_validation_failures

    link = event_impact_path_validator.validate_impact_path(
        raw(
            "thor_link",
            "THORChain confirms RUNE exploit",
            "THORChain confirms a RUNE exploit; Chainlink appears only as an oracle taxonomy candidate.",
        ),
        SimpleNamespace(impact_category="security_or_regulatory_shock", external_asset="THORChain", score_components={"role_source": "taxonomy_candidate"}),
        symbol="LINK",
        coin_id="chainlink",
        score_components={"role_source": "taxonomy_candidate", "validation_strength": 40},
    )
    assert link.candidate_role == "generic_mention"
    assert link.role_source == "taxonomy_candidate"
    assert "taxonomy_candidate_not_affected_asset" in link.role_validation_failures

    velvet = event_impact_path_validator.validate_impact_path(
        raw(
            "velvet_spacex",
            "VELVET offers SpaceX pre-IPO exposure",
            "Velvet lets users trade tokenized stock exposure to SpaceX pre-IPO markets.",
        ),
        SimpleNamespace(impact_category="tokenized_stock_venue", external_asset="SpaceX", score_components={"validation_strength": 95}),
        symbol="VELVET",
        coin_id="velvet",
        score_components={"validation_strength": 95, "market_confirmation": 50},
    )
    assert velvet.candidate_role == "proxy_venue"
    assert velvet.asset_kind == "tokenized_equity_venue"
    assert velvet.digest_eligible_by_impact_path is True


def test_event_resolver_outputs_identity_metadata_and_rejects_generic_hype():
    from datetime import datetime, timezone

    from crypto_rsi_scanner.event_models import DiscoveredAsset, NormalizedEvent
    from crypto_rsi_scanner.event_resolver import resolve_event_assets

    now = datetime(2026, 6, 20, tzinfo=timezone.utc)
    assets = [
        DiscoveredAsset("hyperliquid", "HYPE", "Hyperliquid", aliases=("hyperliquid", "hype")),
        DiscoveredAsset("bitcoin", "BTC", "Bitcoin", aliases=("bitcoin", "btc")),
    ]
    generic = NormalizedEvent(
        event_id="evt_hype_generic",
        raw_ids=("raw",),
        event_name="IPO hype builds before SpaceX listing",
        event_type="news",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source="fixture",
        source_urls=(),
        external_asset="SpaceX",
        description="Market hype rises, but no crypto project is named.",
        confidence=0.85,
    )
    assert resolve_event_assets(generic, assets) == []

    direct = NormalizedEvent(
        event_id="evt_hyperliquid",
        raw_ids=("raw",),
        event_name="Hyperliquid launches HYPEUSDT perp",
        event_type="perp_listing",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source="fixture",
        source_urls=(),
        external_asset="Hyperliquid",
        description="Hyperliquid lists HYPEUSDT and references the HYPE token.",
        confidence=0.90,
    )
    link = resolve_event_assets(direct, assets)[0]
    assert link.symbol == "HYPE"
    assert link.matched_field in {"coin_id", "alias", "symbol", "name_and_symbol"}
    assert link.identity_confidence and link.identity_confidence >= 80
    assert link.collision_risk == "high"
    assert link.role_source in {"resolver_exact", "market_symbol_only"}


def test_event_operator_surfaces_show_asset_identity_metadata():
    from dataclasses import replace

    from crypto_rsi_scanner import event_alpha_daily_brief, event_opportunity_audit, event_research_cards, event_watchlist

    components = {
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "impact_path_type": "venue_value_capture",
        "impact_path_strength": "strong",
        "candidate_role": "proxy_venue",
        "asset_kind": "tokenized_equity_venue",
        "role_source": "resolver_exact",
        "identity_confidence": 95.0,
        "identity_evidence": ["VELVET offers SpaceX pre-IPO tokenized stock exposure"],
        "collision_risk": "none",
        "role_capabilities": {"can_be_proxy_venue": True, "can_be_market_anomaly": True},
        "role_validation_failures": [],
        "evidence_quality_score": 85,
        "source_class": "cryptopanic_tagged",
        "evidence_specificity": "direct_token_mechanism",
        "market_confirmation_score": 75,
        "market_confirmation_level": "confirmed",
        "market_context_freshness_status": "fresh",
        "market_context_age_hours": 0.2,
        "market_context_stale": False,
        "market_context_freshness_cap_applied": False,
        "opportunity_score_final": 92,
        "opportunity_level": "high_priority",
        "opportunity_verdict_reasons": ["proxy_impact_path_explained"],
        "why_local_only": "not_local_only",
        "why_not_watchlist": "not_watchlist",
        "manual_verification_items": ["verify source and liquidity"],
        "upgrade_requirements": [],
        "downgrade_warnings": [],
    }
    entry = replace(
        _test_watchlist_entry(state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value, symbol="VELVET", coin_id="velvet"),
        key="incident-spacex|velvet|proxy_venue",
        relationship_type="impact_hypothesis",
        latest_score_components=components,
        latest_event_name="SpaceX proxy exposure",
    )
    card = event_research_cards.render_research_card(entry.key, watchlist_entries=[entry])
    assert "Asset kind: tokenized_equity_venue" in card.markdown
    assert "Role source: resolver_exact" in card.markdown
    assert "Identity evidence: VELVET offers SpaceX pre-IPO tokenized stock exposure" in card.markdown
    brief = event_alpha_daily_brief.build_daily_brief(watchlist_entries=[entry], requested_profile="fixture")
    assert "asset_kind=tokenized_equity_venue" in brief
    assert "role_source=resolver_exact" in brief
    audit = event_opportunity_audit.format_opportunity_audit(
        entry.key,
        watchlist_entries=[entry],
        profile="fixture",
    )
    assert "asset kind: tokenized_equity_venue" in audit
    assert "role capabilities: can_be_market_anomaly, can_be_proxy_venue" in audit


def test_live_confirmation_caps_source_only_narrative_digest_without_market():
    from crypto_rsi_scanner import event_opportunity_verdict

    verdict = event_opportunity_verdict.apply_live_confirmation_policy(
        {
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "source_pack": "fan_sports_pack",
            "final_opportunity_level": "validated_digest",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "impact_path_type": "fan_token_event",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "accepted_provider_counts": {"cryptopanic": 1},
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
        }
    )
    assert verdict.required is True
    assert verdict.confirmed is False
    assert verdict.capped_level == "exploratory"
    assert verdict.reason == "source_only_narrative_without_market_confirmation"

    confirmed = event_opportunity_verdict.apply_live_confirmation_policy(
        {
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "source_pack": "fan_sports_pack",
            "final_opportunity_level": "validated_digest",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "impact_path_type": "fan_token_event",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "accepted_provider_counts": {"cryptopanic": 1},
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
            "market_confirmation_level": "moderate",
            "market_confirmation_score": 55,
            "market_context_freshness_status": "fresh",
        }
    )
    assert confirmed.confirmed is True
    assert confirmed.capped_level is None

    mispacked_unlock = event_opportunity_verdict.apply_live_confirmation_policy(
        {
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "source_pack": "unlock_supply_pack",
            "source_class": "cryptopanic_tagged",
            "final_opportunity_level": "validated_digest",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "impact_path_type": "unlock_supply_event",
            "supporting_categories": ["sports_fan_proxy"],
            "supporting_impact_paths": ["fan_token_attention"],
            "evidence_acquisition_status": "not_executed",
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
        }
    )
    assert mispacked_unlock.confirmed is False
    assert mispacked_unlock.reason == "source_only_narrative_without_market_confirmation"

    structured_unlock = event_opportunity_verdict.apply_live_confirmation_policy(
        {
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
            "symbol": "UNLK",
            "coin_id": "unlock-token",
            "source_pack": "unlock_supply_pack",
            "source_class": "structured_unlock",
            "final_opportunity_level": "validated_digest",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 78,
            "impact_path_type": "unlock_supply_event",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "accepted_provider_counts": {"tokenomist": 1},
            "accepted_evidence_reason_codes": ["structured_unlock_evidence", "tokenomist_unlock_match"],
            "market_context_freshness_status": "missing",
        }
    )
    assert structured_unlock.confirmed is True
    assert structured_unlock.capped_level is None


def test_core_store_load_normalizes_stale_source_only_narrative_digest():
    from crypto_rsi_scanner import event_alpha_router, event_core_opportunity_store

    stale = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "profile": "notify_llm_deep",
        "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
        "core_opportunity_id": "core_chz_source_only",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "incident_id": "world-cup-chz",
        "candidate_role": "direct_subject",
        "primary_impact_path": "fan_token_event",
        "impact_path_type": "fan_token_event",
        "opportunity_level": "validated_digest",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "final_state_after_quality_gate": "RADAR",
        "source_pack": "fan_sports_pack",
        "evidence_acquisition_status": "accepted_evidence_found",
        "evidence_acquisition_accepted_count": 1,
        "accepted_provider_counts": {"cryptopanic": 1},
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
    }
    opportunity = event_core_opportunity_store.core_opportunities_from_rows([stale])[0]
    assert opportunity.opportunity_level == "exploratory"
    assert opportunity.final_route_after_quality_gate == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert opportunity.primary_row["live_confirmation_reason"] == "source_only_narrative_without_market_confirmation"

    stale_mispacked = {
        **stale,
        "core_opportunity_id": "core_chz_mispacked_unlock",
        "primary_impact_path": "unlock_supply_event",
        "impact_path_type": "unlock_supply_event",
        "source_pack": "unlock_supply_pack",
        "source_class": "cryptopanic_tagged",
        "evidence_acquisition_status": "not_executed",
        "evidence_acquisition_accepted_count": 0,
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "supporting_categories": ["sports_fan_proxy"],
        "supporting_impact_paths": ["fan_token_attention"],
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
    }
    mispacked = event_core_opportunity_store.core_opportunities_from_rows([stale_mispacked])[0]
    assert mispacked.opportunity_level == "exploratory"
    assert mispacked.is_validated_digest is False
    assert mispacked.primary_row["live_confirmation_reason"] == "source_only_narrative_without_market_confirmation"


def test_core_store_normalize_rewrites_raw_source_only_narrative_digest():
    import json

    from crypto_rsi_scanner import event_alpha_router, event_core_opportunity_store

    stale = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-chz",
        "profile": "notify_llm_deep",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
        "core_opportunity_id": "core_chz_mispacked_unlock",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "incident_id": "world-cup-chz",
        "candidate_role": "proxy_instrument",
        "primary_impact_path": "unlock_supply_event",
        "impact_path_type": "unlock_supply_event",
        "opportunity_level": "validated_digest",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
        "source_pack": "unlock_supply_pack",
        "source_class": "cryptopanic_tagged",
        "evidence_acquisition_status": "not_executed",
        "accepted_evidence_count": 0,
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
        "supporting_categories": ["sports_fan_proxy"],
        "supporting_impact_paths": ["fan_token_attention", "fan_token_event"],
        "live_confirmation_status": "confirmed",
        "generated_at": "2026-07-01T00:00:00+00:00",
    }
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        path.write_text(json.dumps(stale) + "\n", encoding="utf-8")
        result = event_core_opportunity_store.normalize_core_opportunity_store(path, latest_run=True)
        raw = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert result.success is True
    assert result.rows_updated == 1
    assert raw[0]["opportunity_level"] == "exploratory"
    assert raw[0]["final_opportunity_level"] == "exploratory"
    assert raw[0]["requested_opportunity_level_before_live_confirmation"] == "validated_digest"
    assert raw[0]["live_confirmation_status"] != "confirmed"
    assert raw[0]["live_confirmation_reason"] == "source_only_narrative_without_market_confirmation"
    assert raw[0]["final_route_after_quality_gate"] not in {
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
    }


def test_market_reaction_official_listing_no_reaction_is_early_long_research():
    from crypto_rsi_scanner import event_market_reaction

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
    from crypto_rsi_scanner import event_market_reaction

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
    from crypto_rsi_scanner import event_market_reaction

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
    from crypto_rsi_scanner import event_market_reaction

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
    from crypto_rsi_scanner import event_market_reaction

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
    from crypto_rsi_scanner import event_market_reaction, event_market_units

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
    from crypto_rsi_scanner import event_market_reaction, event_market_state

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
    from crypto_rsi_scanner import event_market_reaction

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
    from crypto_rsi_scanner import event_market_anomaly_scanner, event_market_state

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
    from crypto_rsi_scanner import event_market_anomaly_scanner

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


def test_market_anomaly_artifacts_are_research_only_and_seed_search():
    from crypto_rsi_scanner import event_market_anomaly_scanner

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
        assert "Top Market Anomalies Needing Catalyst Search" in report_text
        assert "Catalyst Search Queue" in report_text


def test_market_anomaly_scanner_uses_registry_and_cached_universe_rows():
    from crypto_rsi_scanner import event_asset_registry, event_market_anomaly_scanner

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
    from crypto_rsi_scanner.event_providers.bybit_announcements import BybitAnnouncementProvider

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


def test_official_exchange_fixture_lanes_and_quote_filtering():
    from crypto_rsi_scanner import config, event_official_exchange

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
    from crypto_rsi_scanner import event_market_reaction, event_source_packs

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
    from crypto_rsi_scanner import event_alpha_daily_brief, event_official_exchange

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
    from crypto_rsi_scanner import event_scheduled_catalysts

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
    from crypto_rsi_scanner import event_alpha_daily_brief, event_scheduled_catalysts

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
    from crypto_rsi_scanner import event_derivatives_crowding

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
    from crypto_rsi_scanner import event_derivatives_crowding, event_research_cards

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
    from crypto_rsi_scanner import event_alpha_daily_brief, event_derivatives_crowding

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
    from crypto_rsi_scanner import event_derivatives_crowding, event_research_cards

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

    from crypto_rsi_scanner import config, event_asset_registry, event_instrument_resolver

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

    from crypto_rsi_scanner import event_alpha_artifacts, event_artifact_paths, event_core_opportunity_store, event_integrated_radar, event_research_cards

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
                if f"# {symbol} Event Research Card" in text:
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
        assert "Early Long Research" in preview
        assert "Confirmed Long Research" in preview
        assert "Fade / Short-Review" in preview
        assert "Skip reasons:" in preview
        assert "Research-only / unvalidated. Not a trade signal." in preview
        assert "Alerts:" not in preview
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


def test_integrated_dex_sidecars_gate_market_anomaly_confirmation():
    from datetime import datetime, timezone

    from crypto_rsi_scanner import event_dex_onchain_readiness, event_integrated_radar

    root = _event_alpha_legacy_helpers.REPO_ROOT
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
    from crypto_rsi_scanner import event_integrated_radar

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
    from crypto_rsi_scanner import event_integrated_radar

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
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_artifact_paths

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
