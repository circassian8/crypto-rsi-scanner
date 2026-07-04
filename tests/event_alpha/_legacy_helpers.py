"""Shared legacy helpers for Event Alpha tests split from tests.test_indicators.

This module intentionally mirrors helper globals from the umbrella runner so
mechanically moved tests keep their original behavior.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy as np
import pandas as pd

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]
REPO_ROOT = _REPO_ROOT
LEGACY_TEST_INDICATORS_PATH = _REPO_ROOT / "tests" / "test_indicators.py"
sys.path.insert(0, str(_REPO_ROOT))
__file__ = str(LEGACY_TEST_INDICATORS_PATH)

from crypto_rsi_scanner.indicators import (
    adaptive_thresholds,
    annualized_vol,
    btc_correlation,
    conviction_score,
    decide_flag,
    detect_divergence,
    regime_note,
    rsi_rate_of_change,
    rsi_z_score,
    trend_regime,
    volume_ratio,
    wilder_rsi,
)
from crypto_rsi_scanner.scanner import classify_tier
from crypto_rsi_scanner import formatting
import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status




def _event_provider_status_cfg(**overrides):
    values = {
        "EVENT_DISCOVERY_MODE": "research_only",
        "EVENT_DISCOVERY_CACHE_DIR": "/tmp/event_fade_cache",
        "EVENT_DISCOVERY_LOOKBACK_HOURS": 72,
        "EVENT_DISCOVERY_HORIZON_DAYS": 14,
        "EVENT_DISCOVERY_EVENTS_PATH": None,
        "EVENT_DISCOVERY_ALIASES_PATH": "fixtures/event_discovery/asset_aliases.json",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH": None,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE": False,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY": "",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET": "",
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": None,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE": False,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": None,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": None,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": None,
        "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": False,
        "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN": "",
        "EVENT_DISCOVERY_GDELT_PATH": None,
        "EVENT_DISCOVERY_GDELT_LIVE": False,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": None,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": False,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS": (),
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": None,
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH": None,
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH": None,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": None,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": False,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT": 100,
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH": None,
        "EVENT_DISCOVERY_COINALYZE_LIVE": False,
        "EVENT_DISCOVERY_COINALYZE_API_KEY": "",
        "EVENT_DISCOVERY_COINALYZE_SYMBOLS": (),
        "EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS": True,
        "EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH": None,
        "EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH": None,
        "EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH": None,
        "EVENT_DISCOVERY_DUNE_SUPPLY_PATH": None,
        "EVENT_DISCOVERY_UNIVERSE_PATH": None,
        "EVENT_DISCOVERY_UNIVERSE_LIVE": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _event_fade_velvet_candidate(now=None, *, direct=False, no_event_time=False, btc_risk_on=35):
    from datetime import datetime, timezone, timedelta
    from crypto_rsi_scanner import event_fade as ef

    now = now or datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    event_time = None if no_event_time else now - timedelta(hours=2)
    event = ef.CatalystEvent(
        event_id="testvelvet-spacex",
        coin_id="testvelvet",
        symbol="TESTVELVET",
        event_name="SpaceX IPO trading start",
        event_type="etf_approval" if direct else "ipo_proxy",
        event_time=event_time,
        first_seen_time=now - timedelta(days=2),
        source="manual_fixture",
        confidence=0.95,
        external_asset=None if direct else "SpaceX",
        is_proxy_narrative=not direct,
        is_direct_beneficiary=direct,
    )
    market = ef.EventMarketSnapshot(
        symbol="TESTVELVET",
        coin_id="testvelvet",
        timestamp=now,
        price=7.2,
        spot_volume_24h=8_000_000,
        market_cap=45_000_000,
        return_24h=1.2,
        return_72h=3.5,
        return_7d=8.5,
        distance_from_20d_ma=2.0,
        volume_zscore_24h=6.2,
        order_book_depth_1pct=8_000,
        order_book_depth_2pct=25_000,
        spread_bps=45,
    )
    derivatives = ef.EventDerivativesSnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        perp_available=True,
        open_interest_24h_change_pct=0.65,
        open_interest_to_market_cap=0.40,
        funding_rate_8h=0.0012,
        perp_spot_volume_ratio=22,
        long_short_ratio=2.1,
        basis=0.025,
    )
    supply = ef.EventSupplyPressureSnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        large_holder_exchange_inflow=True,
        cex_inflow_pct_supply=0.02,
        top_holder_concentration=0.62,
        team_or_mm_wallet_activity=True,
    )
    rsi = ef.EventRSISnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        rsi_daily=86,
        rsi_4h=78,
        rsi_weekly=72,
        target_overbought_score=90,
        btc_risk_on_score=btc_risk_on,
        rsi_rollover_confirmed=True,
        bearish_rsi_divergence=True,
    )
    technical = ef.EventTechnicalSnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        event_vwap=8.1,
        price_below_event_vwap=True,
        failed_reclaim_event_vwap=True,
        lower_high_confirmed=True,
        first_support_broken=True,
        post_event_high=9.4,
        post_event_lower_high=8.6,
        invalidation_level=8.65,
        entry_reference_price=7.2,
    )
    return ef.FadeCandidate(
        "TESTVELVET", "testvelvet", event, market, derivatives, supply, rsi, technical
    )


def _event_discovery_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "raw_events.json", root / "asset_aliases.json"


def _coingecko_universe_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "coingecko_smoke" / "top_markets.json"


def _exchange_announcement_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "binance_announcements.json", root / "bybit_announcements.json"


def _structured_calendar_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "coinmarketcal_events.json", root / "tokenomist_unlocks.json"


def _derivatives_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "coinalyze_derivatives.json"


def _news_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "cryptopanic_news.json", root / "gdelt_news.json", root / "project_blog_rss.json"


def _external_catalyst_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "external_ipo_events.json", root / "sports_fixtures.json", root / "prediction_market_events.json"


def _supply_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return (
        root / "tokenomist_supply.json",
        root / "etherscan_supply.json",
        root / "arkham_supply.json",
        root / "dune_supply.json",
    )


def _outcome_prices_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "outcome_prices.json"


def _outcome_klines_fixture_dir():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "outcome_klines"


def _llm_golden_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "llm_golden_cases.json"


def _llm_extraction_golden_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "llm_extraction_golden_cases.json"


def _stamp_review_provenance(row, reviewer="human", reviewed_at="2026-06-17T12:00:00+00:00"):
    row["reviewed_by"] = reviewer
    row["reviewed_at"] = reviewed_at
    return row


def _test_normalized_event(
    title,
    body="",
    *,
    event_id="test-event",
    event_type="ipo_proxy",
    external_asset="SpaceX",
    event_time=None,
    event_time_confidence=0.0,
    confidence=0.75,
    source="test",
):
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_core.models import NormalizedEvent

    return NormalizedEvent(
        event_id=event_id,
        raw_ids=(event_id,),
        event_name=title,
        event_type=event_type,
        event_time=event_time,
        event_time_confidence=event_time_confidence,
        first_seen_time=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        source=source,
        source_urls=(f"https://example.test/{event_id}",),
        external_asset=external_asset,
        description=body or None,
        confidence=confidence,
        event_time_source="explicit" if event_time else None,
    )


def _event_discovery_fixture_result():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(aliases_path)
    return event_discovery.run_discovery(raw, assets, now=now)


def _full_event_discovery_fixture_result():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    tokenomist_supply_path, etherscan_supply_path, arkham_supply_path, dune_supply_path = _supply_fixture_paths()
    cfg = event_discovery.EventDiscoveryConfig(lookback_hours=120, horizon_days=2)
    return event_discovery.run_manual_discovery(
        events_path,
        aliases_path,
        binance_announcements_path=binance_path,
        bybit_announcements_path=bybit_path,
        coinmarketcal_path=coinmarketcal_path,
        tokenomist_path=tokenomist_path,
        cryptopanic_path=cryptopanic_path,
        gdelt_path=gdelt_path,
        project_blog_rss_path=blog_path,
        external_ipo_path=ipo_path,
        sports_fixtures_path=sports_path,
        prediction_market_events_path=prediction_path,
        coinalyze_derivatives_path=_derivatives_fixture_path(),
        tokenomist_supply_path=tokenomist_supply_path,
        etherscan_supply_path=etherscan_supply_path,
        arkham_supply_path=arkham_supply_path,
        dune_supply_path=dune_supply_path,
        universe_path=_coingecko_universe_fixture_path(),
        cfg=cfg,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )


def _full_event_discovery_config_values():
    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    tokenomist_supply_path, etherscan_supply_path, arkham_supply_path, dune_supply_path = _supply_fixture_paths()
    return {
        "EVENT_DISCOVERY_EVENTS_PATH": events_path,
        "EVENT_DISCOVERY_ALIASES_PATH": aliases_path,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH": binance_path,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE": False,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": bybit_path,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE": False,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": coinmarketcal_path,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": tokenomist_path,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": cryptopanic_path,
        "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": False,
        "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN": "",
        "EVENT_DISCOVERY_GDELT_PATH": gdelt_path,
        "EVENT_DISCOVERY_GDELT_LIVE": False,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": blog_path,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": False,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS": (),
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH": ipo_path,
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH": sports_path,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": prediction_path,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": False,
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH": _derivatives_fixture_path(),
        "EVENT_DISCOVERY_COINALYZE_LIVE": False,
        "EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH": tokenomist_supply_path,
        "EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH": etherscan_supply_path,
        "EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH": arkham_supply_path,
        "EVENT_DISCOVERY_DUNE_SUPPLY_PATH": dune_supply_path,
        "EVENT_DISCOVERY_UNIVERSE_PATH": _coingecko_universe_fixture_path(),
        "EVENT_DISCOVERY_UNIVERSE_LIVE": False,
        "EVENT_SOURCE_ENRICHMENT_ENABLED": False,
        "EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN": 0,
        "EVENT_DISCOVERY_LOOKBACK_HOURS": 120,
        "EVENT_DISCOVERY_HORIZON_DAYS": 2,
        "EVENT_RESEARCH_NOW": "2026-06-15T16:00:00Z",
    }


def _llm_golden_result():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

    path = _llm_golden_fixture_path()
    raw = ManualJsonEventProvider(path, required=True).fetch_events(
        datetime(2026, 6, 15, tzinfo=timezone.utc),
        datetime(2026, 6, 21, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(path)
    return event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )


def _llm_packet_for(result, event_id, coin_id):
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer

    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    raw_by_id = {raw.raw_id: raw for raw in result.raw_events}
    links_by_event = {}
    for link in result.links:
        links_by_event.setdefault(link.event_id, []).append(link)
    candidates = {
        (candidate.event.event_id, candidate.asset.coin_id): candidate
        for candidate in result.candidates
    }
    alert_by_key = {
        (alert.discovery_candidate.event.event_id, alert.discovery_candidate.asset.coin_id): alert
        for alert in alerts
    }
    key = (event_id, coin_id)
    candidate = candidates[key]
    return event_llm_analyzer.build_evidence_packet(
        candidate,
        raw_by_id=raw_by_id,
        links=links_by_event.get(event_id, ()),
        alert=alert_by_key[key],
    )


def _llm_golden_alerts_and_rows(min_prefilter_score=0):
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
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
        cfg=event_llm_analyzer.EventLLMConfig(
            min_prefilter_score=min_prefilter_score,
            max_candidates_per_run=50,
        ),
    )
    return result, alerts, rows


def _llm_extraction_rows():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMExtractionProvider

    path = _llm_extraction_golden_fixture_path()
    raw_events = ManualJsonEventProvider(path, required=True).fetch_events(
        datetime(2026, 6, 15, tzinfo=timezone.utc),
        datetime(2026, 6, 21, tzinfo=timezone.utc),
    )
    rows = event_llm_extractor.analyze_raw_events(
        raw_events,
        FixtureLLMExtractionProvider(path, required=True),
        cfg=event_llm_extractor.EventLLMExtractorConfig(max_events_per_run=50),
    )
    return raw_events, rows


def _market(**over):
    base = {
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
        "current_price": 100.0, "market_cap": 1_000_000_000.0,
        "total_volume": 20_000_000.0,
        "price_change_percentage_24h_in_currency": 2.0,
    }
    base.update(over)
    return base


def _sample_signal(**over):
    base = {
        "symbol": "BNB", "flag": "OB", "severity": "WATCH", "conviction": 50,
        "tier": "DIGEST", "is_new": True, "rsi_daily": 72.7, "rsi_4h": 74.3,
        "rsi_weekly": 50.2, "rsi_z": 2.4, "rsi_delta": 20.0, "volume_ratio": 7.0,
        "btc_corr": 0.4, "divergence": None, "regime": "DOWNTREND",
        "regime_note": "reversal?", "line": "  BNB . c50 ...",
    }
    base.update(over)
    return base


def _fresh_storage():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    return Storage(Path(tempfile.mkdtemp()) / "subs.db")


def _test_watchlist_entry(*, state: str, symbol: str, coin_id: str):
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    high_priority = state == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
    return event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=f"cluster|{coin_id}|proxy_attention",
        cluster_id="cluster",
        event_id="event",
        coin_id=coin_id,
        symbol=symbol,
        relationship_type="proxy_exposure",
        external_asset="SpaceX",
        event_time="2026-06-16T00:00:00+00:00",
        state=state,
        previous_state=None,
        first_seen_at="2026-06-15T00:00:00+00:00",
        last_seen_at="2026-06-15T00:00:00+00:00",
        source_count=1,
        highest_score=80,
        latest_score=80,
        latest_tier="HIGH_PRIORITY_WATCH" if state == "HIGH_PRIORITY" else "WATCHLIST",
        latest_event_name="SpaceX pre-IPO exposure",
        latest_source="fixture",
        latest_playbook_type="proxy_attention",
        latest_effective_playbook_type="proxy_attention",
        latest_market_snapshot={},
        latest_score_components={
            "cluster_confidence": 70,
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_native",
            "evidence_specificity": "asset_and_catalyst",
            "market_confirmation_score": 88 if high_priority else 70,
            "market_confirmation_level": "strong" if high_priority else "confirmed",
            "opportunity_score_final": 92 if high_priority else 82,
            "opportunity_level": "high_priority" if high_priority else "watchlist",
            "opportunity_verdict_reasons": ["fixture_watchlist_quality_context"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify source, catalyst timing, and liquidity"],
            "upgrade_requirements": [],
            "downgrade_warnings": [],
        },
    )


def _notify_artifact_context(base, namespace):
    from types import SimpleNamespace
    from pathlib import Path

    base = Path(base)
    return SimpleNamespace(
        profile=namespace,
        run_mode="notification_burn_in",
        artifact_namespace=namespace,
        base_dir=base,
        namespace_dir=base / namespace,
    )


class _NotifyFakeStorage:
    def __init__(self):
        self.meta = {}

    def get_meta(self, key):
        return self.meta.get(key)

    def set_meta(self, key, value):
        self.meta[key] = value


def _notify_route_decision(symbol, lane, route):
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=f"{symbol}|proxy",
        cluster_id=f"{symbol}|cluster",
        event_id=f"evt-{symbol}",
        coin_id=symbol.lower(),
        symbol=symbol,
        relationship_type="proxy_attention",
        external_asset="SpaceX",
        event_time="2026-06-20T13:30:00+00:00",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state="WATCHLIST",
        first_seen_at="2026-06-19T09:00:00+00:00",
        last_seen_at="2026-06-19T11:00:00+00:00",
    )
    return event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=route,
        alertable=True,
        reason="state escalation",
        lane=lane,
    )


def _notify_suppressed_decision(
    symbol,
    *,
    key_suffix="proxy",
    playbook="market_anomaly_unknown",
    relationship="ambiguous",
    llm_role=None,
    score=35,
    source="fixture_source",
    reason="raw/store-only evidence, no alertable watchlist state",
):
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=f"{symbol}|{key_suffix}",
        cluster_id=f"{symbol}|cluster",
        event_id=f"evt-{symbol}",
        coin_id=symbol.lower(),
        symbol=symbol,
        relationship_type=relationship,
        external_asset="SpaceX" if playbook != "source_noise_control" else None,
        event_time="2026-06-20T13:30:00+00:00" if playbook != "source_noise_control" else None,
        state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        previous_state=None,
        first_seen_at="2026-06-19T09:00:00+00:00",
        last_seen_at="2026-06-19T11:00:00+00:00",
        source_count=1,
        highest_score=score,
        latest_score=score,
        latest_tier="STORE_ONLY",
        latest_event_name=f"{symbol} exploratory catalyst",
        latest_source=source,
        latest_playbook_type=playbook,
        latest_effective_playbook_type=playbook,
        latest_llm_asset_role=llm_role,
        latest_llm_confidence=0.82 if llm_role else None,
        latest_market_snapshot={
            "price": 1.23,
            "return_24h": 0.42,
            "return_72h": 1.404,
            "volume_mcap": 0.33,
            "volume_zscore_24h": 3.4,
        },
        latest_score_components={
            "classifier": 48,
            "market_move_volume": 65,
            "source_quality": 55,
            "cluster_confidence": 50,
            "novelty_freshness": 45,
        },
        suppressed_reason=reason,
        should_alert=False,
    )
    return event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.STORE_ONLY,
        alertable=False,
        reason=reason,
        lane=event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY,
    )


def _research_review_decision(symbol="DOGE", *, score=66, level="exploratory", playbook="meme_attention"):
    decision = _notify_suppressed_decision(
        symbol,
        playbook=playbook,
        relationship="proxy_attention",
        score=score,
        reason="missing independent source confirmation",
    )
    decision.entry.latest_score_components.update({
        "core_opportunity_id": f"agg:{symbol.lower()}-research-review",
        "opportunity_level": level,
        "opportunity_score_final": score,
        "impact_path_type": playbook,
        "candidate_role": "candidate_asset",
        "market_confirmation_score": 70,
        "source_quality": 58,
        "why_not_watchlist": "missing independent source confirmation",
        "upgrade_requirements": ["find independent catalyst evidence", "verify liquidity and organic volume"],
    })
    return decision


def _canonical_core_fixture_rows() -> list[dict[str, object]]:
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    base = {
        "profile": "market_refresh_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "market_refresh_smoke",
        "row_type": "event_impact_hypothesis",
        "source_class": "validated_source",
        "evidence_specificity": "specific",
    }
    return [
        {
            **base,
            "hypothesis_id": "hyp-velvet-core",
            "incident_id": "incident-spacex",
            "canonical_incident_name": "SpaceX pre-IPO exposure",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_category": "tokenized_stock_venue",
            "impact_path_type": "venue_value_capture",
            "opportunity_level": "high_priority",
            "opportunity_score_final": 92,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            "market_refresh_attempted": True,
            "market_refresh_success": True,
            "market_context_freshness_status": "fresh",
            "market_context_source": "market_refresh",
            "market_context_age_hours": 0.5,
            "market_context_freshness_cap_applied": False,
            "market_confirmation_after": 88,
            "evidence_acquisition_attempted": True,
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_quality_after": 91,
            "evidence_quotes": ["Velvet offers SpaceX exposure"],
        },
        {
            **base,
            "hypothesis_id": "hyp-velvet-stale-support",
            "incident_id": "incident-spacex",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_category": "rwa_preipo_proxy",
            "impact_path_type": "rwa_preipo_proxy",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 70,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "market_context_freshness_status": "stale",
            "market_context_freshness_cap_applied": True,
            "why_not_watchlist": ["market_context_stale_capped"],
            "evidence_quotes": ["SpaceX pre-IPO market mention"],
        },
        {
            **base,
            "hypothesis_id": "hyp-aave-core",
            "incident_id": "incident-kraken-aave",
            "canonical_incident_name": "Kraken strategic Aave stake",
            "symbol": "AAVE",
            "coin_id": "aave",
            "validated_symbol": "AAVE",
            "validated_coin_id": "aave",
            "candidate_role": "direct_beneficiary",
            "impact_category": "strategic_investment",
            "impact_path_type": "strategic_investment",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 76,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "evidence_quotes": ["Kraken acquired a strategic stake in Aave"],
        },
        {
            **base,
            "hypothesis_id": "hyp-rune-core",
            "incident_id": "incident-thorchain-exploit",
            "canonical_incident_name": "THORChain exploit and trading restart",
            "symbol": "RUNE",
            "coin_id": "thorchain",
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "candidate_role": "direct_beneficiary",
            "impact_category": "security_incident",
            "impact_path_type": "exploit_security_event",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 81,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.WATCHLIST.value,
            "market_refresh_attempted": True,
            "market_refresh_success": True,
            "market_confirmation_after": 73,
            "evidence_quotes": ["THORChain resumed trading after exploit response"],
        },
        {
            **base,
            "hypothesis_id": "hyp-meme-core",
            "incident_id": "incident-memecore",
            "symbol": "MEME",
            "coin_id": "memecore",
            "validated_symbol": "MEME",
            "validated_coin_id": "memecore",
            "candidate_role": "mentioned_asset",
            "impact_category": "market_anomaly",
            "impact_path_type": "insufficient_data",
            "opportunity_level": "local_only",
            "opportunity_score_final": 42,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "why_local_only": ["missing_direct_impact_path"],
        },
    ]
