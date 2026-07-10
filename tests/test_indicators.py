"""Unit tests for the indicator math. Pure functions, no network.

Run with pytest:   pytest
Or standalone:     python tests/test_indicators.py
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


# --- event-fade research sleeve ---------------------------------------------

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


def test_config_load_url_list_dedupes_comments_and_inline_notes():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "feeds.txt"
        path.write_text(
            "\n".join([
                "# public feeds",
                "https://example.test/rss",
                "https://example.test/rss  # duplicate",
                "",
                "https://example.test/atom",
            ]),
            encoding="utf-8",
        )

        urls = config._load_url_list(path)

    assert urls == ("https://example.test/rss", "https://example.test/atom")


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


# --- event discovery research sleeve ----------------------------------------

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


# --- pre-alert flag decision -------------------------------------------------


# --- tier routing ------------------------------------------------------------


# --- trend regime ------------------------------------------------------------


# --- setup taxonomy (split signal intent) ------------------------------------


# --- market-regime gating ----------------------------------------------------


def test_storage_save_signal_roundtrip():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    st = Storage(Path(tempfile.mkdtemp()) / "s.db")
    scan_id = st.save_scan(10, 2, 1)
    st.save_signal(scan_id, {
        "symbol": "BTC", "coin_id": "bitcoin", "flag": "OB", "severity": "ALERT",
        "rsi_daily": 75.0, "conviction": 60, "tier": "INSTANT", "regime": "UPTREND",
        "setup_type": "trend_continuation", "expected_dir": "up",
        "market_regime": "UPTREND", "market_aligned": "favorable",
        "price": 70000.0, "is_new": 1,
        "state_json": '{"version":1}',
    })
    row = st.conn.execute(
        "SELECT symbol, market_regime, market_aligned, setup_type, state_json FROM signals"
    ).fetchone()
    assert row["symbol"] == "BTC" and row["market_regime"] == "UPTREND"
    assert row["market_aligned"] == "favorable"
    assert row["setup_type"] == "trend_continuation"
    assert row["state_json"] == '{"version":1}'
    assert st.recent_signal_coin_ids("2020-01-01T00:00:00+00:00") == ["bitcoin"]
    st.close()


# --- .env loader -------------------------------------------------------------

def test_dotenv_skips_empty_values():
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner.config import _load_dotenv

    env_path = Path(tempfile.mkdtemp()) / ".env"
    env_path.write_text("RSI_TEST_FILLED=hello\nRSI_TEST_EMPTY=\n# comment\n", encoding="utf-8")

    for k in ("RSI_TEST_FILLED", "RSI_TEST_EMPTY"):
        os.environ.pop(k, None)
    try:
        _load_dotenv(env_path)
        # filled value is loaded; empty value is treated as unset (uses default)
        assert os.environ.get("RSI_TEST_FILLED") == "hello"
        assert "RSI_TEST_EMPTY" not in os.environ
    finally:
        os.environ.pop("RSI_TEST_FILLED", None)


def test_env_bool_strips_whitespace():
    from crypto_rsi_scanner.config import _env_bool

    key = "RSI_TEST_BOOL"
    old = os.environ.get(key)
    try:
        os.environ[key] = " 0 "
        assert _env_bool(key, True) is False
        os.environ[key] = " false "
        assert _env_bool(key, True) is False
        os.environ[key] = " yes "
        assert _env_bool(key, False) is True
    finally:
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old


# --- universe hygiene --------------------------------------------------------

def _market(**over):
    base = {
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
        "current_price": 100.0, "market_cap": 1_000_000_000.0,
        "total_volume": 20_000_000.0,
        "price_change_percentage_24h_in_currency": 2.0,
    }
    base.update(over)
    return base


# --- telegram formatting -----------------------------------------------------

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


def test_telegram_instant_has_html_and_emoji():
    s = _sample_signal(flag="OB", severity="EXTREME", conviction=93)
    out = formatting.telegram_html("instant", [s], "2026-05-31 19:59 UTC")
    assert "⚡" in out
    assert "<b>BNB</b>" in out
    assert "Conviction <b>93</b>/100" in out
    assert "RSI <b>73</b>" in out  # 72.7 -> 73


def test_telegram_digest_groups_by_direction():
    sigs = [
        _sample_signal(symbol="AAA", flag="OB"),
        _sample_signal(symbol="BBB", flag="OS", regime="DOWNTREND", regime_note="continuation"),
        _sample_signal(symbol="CCC", flag="PRE_OS", severity="APPROACHING", regime_note="continuation"),
    ]
    out = formatting.telegram_html("digest", sigs, "t")
    assert "Overbought" in out and "Oversold" in out and "Approaching" in out
    assert "<b>AAA</b>" in out and "<b>CCC</b>" in out


def test_telegram_escapes_special_chars():
    s = _sample_signal(symbol="A&B<X>")
    out = formatting.telegram_html("instant", [s], "t")
    assert "A&amp;B&lt;X&gt;" in out
    assert "<b>A&B<X></b>" not in out  # raw must not leak


def test_chart_link_escapes_quotes_in_href():
    s = _sample_signal(symbol='A&B<X>"')
    out = formatting.telegram_html("instant", [s], "t")
    assert 'symbol=A&amp;B&lt;X&gt;&quot;USDT' in out
    assert 'symbol=A&B<X>"USDT' not in out


def test_telegram_handles_missing_4h_nan():
    s = _sample_signal(rsi_4h=float("nan"))
    out = formatting.telegram_html("instant", [s], "t")
    assert "4H" not in out  # NaN timeframe omitted, no crash


def test_plain_text_uses_line():
    s = _sample_signal(line="  BNB . c50 stuff")
    out = formatting.plain_text("digest", [s], "t")
    assert "BNB . c50 stuff" in out


# --- signal outcome tracking -------------------------------------------------


# --- subscriber management ---------------------------------------------------

def _fresh_storage():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    return Storage(Path(tempfile.mkdtemp()) / "subs.db")


def test_subscribe_add_and_dedup():
    st = _fresh_storage()
    assert st.subscribe("111", "alice") is True       # new
    assert st.subscribe("111", "alice") is False      # already active -> no-op
    assert st.active_subscribers() == ["111"]
    st.close()


def test_unsubscribe_and_resubscribe():
    st = _fresh_storage()
    st.subscribe("111", "alice")
    st.subscribe("222", "bob")
    assert st.unsubscribe("111") is True
    assert st.unsubscribe("111") is False             # already inactive
    assert st.active_subscribers() == ["222"]
    assert st.subscribe("111", None) is True          # reactivated
    assert set(st.active_subscribers()) == {"111", "222"}
    st.close()


def test_seed_from_config(monkeypatch=None):
    from crypto_rsi_scanner import telegram, config
    st = _fresh_storage()
    orig = config.TELEGRAM_CHAT_IDS
    config.TELEGRAM_CHAT_IDS = ["999", "888"]
    try:
        telegram.seed_subscribers_from_config(st)
        assert set(st.active_subscribers()) == {"999", "888"}
    finally:
        config.TELEGRAM_CHAT_IDS = orig
        st.close()


# --- richer formatting (Part A) ----------------------------------------------

def test_sparkline_basic():
    assert formatting.sparkline([1, 2, 3, 4, 5, 6, 7, 8]) == "▁▂▃▄▅▆▇█"
    assert formatting.sparkline([]) == ""
    assert formatting.sparkline([5]) == ""
    assert set(formatting.sparkline([5, 5, 5])) == {"▁"}  # flat


def test_price_formatting():
    assert formatting._fmt_price(72000) == "$72,000"
    assert formatting._fmt_price(721.09) == "$721.09"
    assert formatting._fmt_price(0.0034) == "$0.0034"


def test_instant_card_has_rich_fields():
    s = _sample_signal(price=721.09, pct_24h=8.2, pct_7d=-3.1, ath_pct=-8.5,
                       sparkline=[700, 710, 690, 720])
    out = formatting.telegram_html("instant", [s], "t")
    assert "$721.09" in out
    assert "+8.2% 24h" in out
    assert "below ATH" in out
    assert "tradingview.com" in out  # chart link
    assert "<code>" in out          # sparkline


def test_digest_line_shows_24h():
    s = _sample_signal(pct_24h=-5.0)
    out = formatting.telegram_html("digest", [s], "t")
    assert "-5%" in out


# --- inline hit-rates (Part B) ------------------------------------------------

def test_track_records_and_text():
    from crypto_rsi_scanner import outcomes
    rows = []
    # 6 OB-in-downtrend, 5 favorable -> 83%
    for i in range(6):
        rows.append({"horizon_days": 7, "ret_pct": -4.0 if i < 5 else 2.0,
                     "favorable": 1 if i < 5 else 0, "flag": "OB",
                     "regime": "DOWNTREND", "regime_note": "reversal?",
                     "conviction": 70, "symbol": f"X{i}", "severity": "ALERT"})
    stats = outcomes.track_records(rows, 7)
    assert stats["mean_reversion"]["n"] == 6   # OB-in-downtrend -> mean_reversion
    txt = outcomes.track_record_text("mean_reversion", stats, 7)
    assert "5/6" in txt and "mean reversion" in txt


def test_track_record_insufficient_samples():
    from crypto_rsi_scanner import outcomes
    rows = [{"horizon_days": 7, "ret_pct": -4.0, "favorable": 1, "flag": "OB",
             "regime": "RANGE", "regime_note": "", "conviction": 50,
             "symbol": "A", "severity": "WATCH"}]
    stats = outcomes.track_records(rows, 7)  # only 1 sample < MIN
    assert stats == {}
    assert outcomes.track_record_text("mean_reversion", stats, 7) == ""


# --- heartbeat (Part D) -------------------------------------------------------

def test_heartbeat_health_checks(monkeypatch=None):
    from crypto_rsi_scanner import heartbeat, config
    sent = []
    orig = heartbeat.send_telegram
    heartbeat.send_telegram = lambda *a, **k: sent.append(a) or True
    try:
        assert heartbeat.check_health({"requested": 90, "fetched": 88, "analyzed": 80}) is True
        assert not sent
        # degraded: >30% failed
        assert heartbeat.check_health({"requested": 90, "fetched": 50, "analyzed": 40}) is False
        # no data
        assert heartbeat.check_health({"requested": 90, "fetched": 0, "analyzed": 0}) is False
        assert len(sent) == 2
    finally:
        heartbeat.send_telegram = orig


# --- bot commands (Part C) ----------------------------------------------------

def test_snapshot_save_load():
    from crypto_rsi_scanner import telegram
    st = _fresh_storage()
    sigs = [_sample_signal(symbol="AAA", flag="OB", conviction=80),
            _sample_signal(symbol="BBB", flag="OS", conviction=40)]
    telegram.save_latest_snapshot(st, sigs)
    loaded = telegram._load_snapshot(st)
    assert {s["symbol"] for s in loaded} == {"AAA", "BBB"}
    st.close()


def test_cmd_top_and_detail():
    from crypto_rsi_scanner import telegram
    st = _fresh_storage()
    telegram.save_latest_snapshot(st, [
        _sample_signal(symbol="AAA", flag="OB", conviction=80),
        _sample_signal(symbol="BBB", flag="OS", conviction=40),
    ])
    top = telegram._cmd_top(st)
    assert "AAA" in top and "BBB" in top
    detail = telegram._cmd_detail(st, "aaa")
    assert "AAA" in detail
    assert "isn't on the current watch-list" in telegram._cmd_detail(st, "ZZZ")
    st.close()


# --- self-tuning conviction --------------------------------------------------

def test_conviction_adjustment_insufficient_samples():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # below min_samples -> unchanged
    assert conviction_adjustment(50, 0.9, 3, min_samples=8) == 50
    assert conviction_adjustment(50, None, 100, min_samples=8) == 50


def test_conviction_adjustment_direction():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # high hit rate with ample samples -> nudges up; low -> nudges down
    up = conviction_adjustment(50, 0.9, 40, min_samples=8, max_swing=15)
    down = conviction_adjustment(50, 0.1, 40, min_samples=8, max_swing=15)
    assert up > 50 and down < 50
    # 50% hit rate -> no change
    assert conviction_adjustment(50, 0.5, 40, min_samples=8) == 50


def test_conviction_adjustment_bounded():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # swing capped; never exceeds max_swing, never leaves 0..100
    assert conviction_adjustment(95, 1.0, 100, max_swing=15) <= 100
    assert conviction_adjustment(5, 0.0, 100, max_swing=15) >= 0
    hi = conviction_adjustment(50, 1.0, 1000, min_samples=8, max_swing=15)
    assert hi - 50 <= 15


def test_conviction_adjustment_confidence_scaling():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # more samples -> larger (or equal) move toward the empirical signal
    few = conviction_adjustment(50, 0.9, 8, min_samples=8, max_swing=15)
    many = conviction_adjustment(50, 0.9, 80, min_samples=8, max_swing=15)
    assert (many - 50) >= (few - 50) >= 0


# --- macro context -----------------------------------------------------------

def test_macro_header_assembles():
    from crypto_rsi_scanner import macro
    m = {
        "n_ob": 17, "n_os": 3, "d_ob": 6, "d_os": -1,
        "fng": {"value": 22, "label": "Fear"},
        "btc_regime": "DOWNTREND",
        "glob": {"btc_dominance": 54.3, "mcap_change_24h": -2.8},
    }
    line = macro.macro_header(m)
    assert "F&amp;G 22 (Fear)" in line
    assert "Downtrend" in line
    assert "breadth 17🔴" in line and "3🟢" in line
    assert "-2.8% 24h" in line


def test_macro_header_empty_safe():
    from crypto_rsi_scanner import macro
    # missing pieces are omitted, never crash; breadth always present
    line = macro.macro_header({"n_ob": 0, "n_os": 0})
    assert "breadth" in line
    assert macro.macro_header(None) == ""


def test_macro_digest_includes_header():
    s = _sample_signal()
    out = formatting.telegram_html("digest", [s], "t", macro_line="🌍 test-macro")
    assert "test-macro" in out


def test_alert_render_smoke_suite():
    from crypto_rsi_scanner import alert_smoke
    results = alert_smoke.run_smoke()
    names = {r.name for r in results}
    assert names == {"telegram_instant", "telegram_digest", "plain_instant", "plain_digest"}
    assert all(r.chars > 0 for r in results)


# --- backtester ---------------------------------------------------------------


# --- paper-trade scoreboard --------------------------------------------------


# --- regression: NaN enrichment from the DataFrame self-tune path -------------


def test_telegram_send_chunks_long_messages():
    from crypto_rsi_scanner import notifications, config

    class Response:
        def raise_for_status(self):
            return None

    calls = []
    orig_post = notifications.requests.post
    orig_token = config.TELEGRAM_BOT_TOKEN
    orig_chat_ids = config.TELEGRAM_CHAT_IDS
    notifications.requests.post = lambda url, json, timeout: calls.append(json["text"]) or Response()
    config.TELEGRAM_BOT_TOKEN = "token"
    config.TELEGRAM_CHAT_IDS = ["1"]
    try:
        text = ("signal line\n\n" * 700).strip()
        assert len(text) > 4096
        assert notifications.send_telegram(text, parse_mode="HTML") is True
        assert len(calls) > 1
        assert all(len(body) <= 4096 for body in calls)
        assert not any("…" in body for body in calls)
        assert "signal line" in calls[-1]
    finally:
        notifications.requests.post = orig_post
        config.TELEGRAM_BOT_TOKEN = orig_token
        config.TELEGRAM_CHAT_IDS = orig_chat_ids


def test_telegram_structured_send_tracks_recipients_chunks_and_bool_compat():
    from crypto_rsi_scanner import notifications, config

    class Response:
        def __init__(self, fail=False):
            self.fail = fail

        def raise_for_status(self):
            if self.fail:
                raise RuntimeError("bad token=SECRET123")

    calls = []
    orig_post = notifications.requests.post
    orig_token = config.TELEGRAM_BOT_TOKEN
    orig_chat_ids = config.TELEGRAM_CHAT_IDS

    def fake_post(url, json, timeout):
        calls.append((url, dict(json), timeout))
        return Response(fail=json["chat_id"] == "bad")

    notifications.requests.post = fake_post
    config.TELEGRAM_BOT_TOKEN = "SECRET123"
    config.TELEGRAM_CHAT_IDS = ["good", "bad"]
    try:
        result = notifications.send_telegram_structured("hello", parse_mode="HTML")
        assert result.attempted is True
        assert result.success is False
        assert result.recipient_count == 2
        assert result.delivered_count == 1
        assert result.failed_count == 1
        assert result.chunk_count == 1
        assert result.delivered_chunks == 1
        assert result.failed_chunks == 1
        assert "SECRET123" not in str(result.error_message_safe)
        assert "SECRET123" not in str(result.channel_summary)
        assert notifications.send_telegram("legacy bool", parse_mode="HTML") is True
        assert len(calls) >= 4
        assert {call[2] for call in calls} == {notifications.TELEGRAM_SEND_TIMEOUT_SECONDS}
    finally:
        notifications.requests.post = orig_post
        config.TELEGRAM_BOT_TOKEN = orig_token
        config.TELEGRAM_CHAT_IDS = orig_chat_ids


def test_telegram_structured_send_counts_chunked_success():
    from crypto_rsi_scanner import notifications, config

    class Response:
        def raise_for_status(self):
            return None

    calls = []
    orig_post = notifications.requests.post
    orig_token = config.TELEGRAM_BOT_TOKEN
    orig_chat_ids = config.TELEGRAM_CHAT_IDS
    notifications.requests.post = lambda url, json, timeout: calls.append(json["text"]) or Response()
    config.TELEGRAM_BOT_TOKEN = "token"
    config.TELEGRAM_CHAT_IDS = ["1"]
    try:
        text = ("alpha\n\n" * 900).strip()
        result = notifications.send_telegram_structured(text, parse_mode="HTML")
        assert result.success is True
        assert result.delivered_count == 1
        assert result.failed_count == 0
        assert result.chunk_count == len(calls)
        assert result.delivered_chunks == result.chunk_count
        assert result.failed_chunks == 0
    finally:
        notifications.requests.post = orig_post
        config.TELEGRAM_BOT_TOKEN = orig_token
        config.TELEGRAM_CHAT_IDS = orig_chat_ids


def test_scan_staleness_alert_dedup_and_recovery():
    from datetime import datetime, timedelta, timezone
    from crypto_rsi_scanner import telegram, heartbeat, config

    sent = []
    orig_alert = heartbeat.alert_stale_scan
    orig_int = config.STALE_CHECK_INTERVAL_SEC
    heartbeat.alert_stale_scan = lambda last, hrs, storage=None: sent.append(hrs)
    config.STALE_CHECK_INTERVAL_SEC = 0           # disable throttle for the test
    try:
        now = datetime(2026, 6, 8, tzinfo=timezone.utc)

        class Store:
            def __init__(self, dt):
                self.dt = dt
            def last_scan_at(self):
                return self.dt

        state: dict = {}
        telegram._check_scan_staleness(Store(now - timedelta(hours=2)), state, now=now)
        assert sent == []                          # fresh -> no alert
        telegram._check_scan_staleness(Store(now - timedelta(hours=40)), state, now=now)
        assert len(sent) == 1                      # stale -> one alert
        telegram._check_scan_staleness(Store(now - timedelta(hours=41)), state, now=now)
        assert len(sent) == 1                      # still stale -> no repeat (dedup)
        telegram._check_scan_staleness(Store(now - timedelta(hours=1)), state, now=now)
        telegram._check_scan_staleness(Store(now - timedelta(hours=40)), state, now=now)
        assert len(sent) == 2                      # recovered then stale again -> re-alerts
        # no scan history yet -> never alerts
        telegram._check_scan_staleness(Store(None), {}, now=now)
        assert len(sent) == 2
    finally:
        heartbeat.alert_stale_scan = orig_alert
        config.STALE_CHECK_INTERVAL_SEC = orig_int


def test_scan_status_lifecycle_and_report():
    import json
    from datetime import datetime, timedelta, timezone

    from crypto_rsi_scanner import config, status_report, telegram

    st = _fresh_storage()
    orig_stale = config.STALE_SCAN_HOURS
    config.STALE_SCAN_HOURS = 36
    try:
        st.mark_scan_started(top_n=12)
        assert st.scan_status()["state"] == "running"

        st.mark_scan_success(
            top_n=12,
            requested=15,
            fetched=14,
            analyzed=12,
            coin_count=12,
            flagged_count=3,
            ob_count=2,
            os_count=1,
            instant_count=1,
            digest_count=2,
            matured_outcomes=4,
            paper_opened=1,
            paper_closed=0,
        )
        status = st.scan_status()
        assert status["state"] == "success"
        assert st.last_successful_scan_at() is not None
        telegram.save_latest_snapshot(st, [{"symbol": "AAA", "flag": "OB"}])
        st.subscribe("111", "alice")

        out = status_report.format_status(st)
        assert "health: OK" in out
        assert "fetch: requested 15, fetched 14, analyzed 12" in out
        assert "signals: scanned 12, flagged 3 (OB 2, OS 1)" in out
        assert "bot: 1 subscriber(s), 1 current snapshot signal(s)" in out

        old = datetime.now(timezone.utc) - timedelta(hours=40)
        status["last_success_at"] = old.isoformat()
        st.set_meta("scan_status", json.dumps(status))
        assert "health: STALE" in status_report.format_status(st, now=datetime.now(timezone.utc))
    finally:
        config.STALE_SCAN_HOURS = orig_stale
        st.close()


def test_scan_status_failure_and_bot_health_escapes():
    from crypto_rsi_scanner import telegram

    st = _fresh_storage()
    try:
        st.mark_scan_started(top_n=10)
        st.mark_scan_failure("bad <network> & token", requested=10, fetched=0, analyzed=0)
        plain = telegram._cmd_health(st)
        assert "RSI SCANNER STATUS" in plain
        assert "health: FAILED" in plain
        assert "bad &lt;network&gt; &amp; token" in plain
        assert "<network>" not in plain
    finally:
        st.close()


def test_log_rotation_copytruncate_and_retention():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from crypto_rsi_scanner.ops import log_file_status, rotate_logs

    root = Path(tempfile.mkdtemp())
    log = root / "bot.log"
    first_time = datetime(2026, 6, 8, 1, 0, 0, tzinfo=timezone.utc)
    second_time = datetime(2026, 6, 8, 1, 0, 1, tzinfo=timezone.utc)

    log.write_text("first rotation\n", encoding="utf-8")
    first = rotate_logs([log], max_bytes=3, keep=1, now=first_time)[0]
    assert first.reason == "rotated"
    assert first.rotated_to is not None
    assert first.rotated_to.read_text(encoding="utf-8") == "first rotation\n"
    assert log.read_text(encoding="utf-8") == ""

    log.write_text("second rotation\n", encoding="utf-8")
    second = rotate_logs([log], max_bytes=3, keep=1, now=second_time)[0]
    assert second.reason == "rotated"
    assert second.rotated_to is not None
    assert second.rotated_to.read_text(encoding="utf-8") == "second rotation\n"
    assert not first.rotated_to.exists()
    assert len(list(root.glob("bot.log.*"))) == 1
    assert log.read_text(encoding="utf-8") == ""

    status = log_file_status([log], max_bytes=3)[0]
    assert status.exists is True
    assert status.size_bytes == 0
    assert status.rotation_count == 1


def test_launchd_status_parser_and_formatter():
    from crypto_rsi_scanner.ops import _parse_launchctl_print, format_launchd_status

    text = """
gui/501/com.nasrenkaraf.rsibot = {
    path = /Users/nasrenkaraf/Library/LaunchAgents/com.nasrenkaraf.rsibot.plist
    state = running
    stdout path = /Users/nasrenkaraf/crypto-rsi-scanner/bot.log
    stderr path = /Users/nasrenkaraf/crypto-rsi-scanner/bot.log
    runs = 8
    pid = 73052
    last exit code = 0
}
"""
    status = _parse_launchctl_print("com.nasrenkaraf.rsibot", "gui/501", text)
    assert status.loaded is True
    assert status.state == "running"
    assert status.pid == 73052
    assert status.runs == 8
    assert status.last_exit_code == 0
    assert status.stdout_path.endswith("bot.log")

    out = format_launchd_status([status])
    assert "com.nasrenkaraf.rsibot: running, pid 73052, runs 8, last exit 0" in out
    assert "stdout: /Users/nasrenkaraf/crypto-rsi-scanner/bot.log" in out


def test_maintenance_agent_plist_contents():
    from pathlib import Path
    from crypto_rsi_scanner.ops import maintenance_agent_plist

    plist = maintenance_agent_plist(
        label="com.example.maint",
        python_path=Path("/repo/.venv/bin/python"),
        main_path=Path("/repo/main.py"),
        working_dir=Path("/repo"),
        log_path=Path("/repo/maintenance.log"),
        hour=3,
        minute=45,
    )
    assert plist["Label"] == "com.example.maint"
    assert plist["ProgramArguments"] == ["/repo/.venv/bin/python", "/repo/main.py", "--maintenance"]
    assert plist["WorkingDirectory"] == "/repo"
    assert plist["StandardOutPath"] == "/repo/maintenance.log"
    assert plist["StartCalendarInterval"] == {"Hour": 3, "Minute": 45}
    assert plist["RunAtLoad"] is False


def test_coingecko_client_fixture_mode():
    import asyncio
    import json
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.client import CoinGeckoClient

    root = Path(tempfile.mkdtemp())
    chart_dir = root / "market_chart"
    chart_dir.mkdir()
    (root / "top_markets.json").write_text(json.dumps([
        {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
    ]))
    (chart_dir / "bitcoin.json").write_text(json.dumps({
        "prices": [[1, 100.0]],
        "total_volumes": [[1, 1000.0]],
    }))

    orig = config.FIXTURE_DIR
    config.FIXTURE_DIR = root
    try:
        async def _run():
            async with CoinGeckoClient() as client:
                markets = await client.get_top_markets(1)
                chart = await client.get_market_chart("bitcoin", 250)
                return markets, chart
        markets, chart = asyncio.run(_run())
        assert [m["id"] for m in markets] == ["bitcoin"]
        assert chart["prices"][0][1] == 100.0
    finally:
        config.FIXTURE_DIR = orig


def test_storage_wal_and_busy_timeout():
    # The scan and the always-on listener share one DB file; WAL + busy_timeout
    # let them read/write concurrently without "database is locked".
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    st = Storage(Path(tempfile.mkdtemp()) / "wal.db")
    try:
        assert str(st.conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert st.conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 1000
    finally:
        st.close()


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


_EVENT_ALPHA_TEST_MODULES = (
    "tests.event_alpha.test_alert_outcomes",
    "tests.event_alpha.test_artifact_schema",
    "tests.event_alpha.test_burn_in_outcomes",
    "tests.event_alpha.test_canonical_imports",
    "tests.event_alpha.test_catalyst_search",
    "tests.event_alpha.test_catalyst_frames",
    "tests.event_alpha.test_claim_semantics",
    "tests.event_alpha.test_core_opportunities",
    "tests.event_alpha.test_core_reconciliation",
    "tests.event_alpha.test_discovery_cache_reports",
    "tests.event_alpha.test_discovery_pipeline",
    "tests.event_alpha.test_doctor_core",
    "tests.event_alpha.test_doctor_notifications",
    "tests.event_alpha.test_doctor_provider_conflicts",
    "tests.event_alpha.test_doctor_quality",
    "tests.event_alpha.test_doctor_reconciliation",
    "tests.event_alpha.test_event_alert_ranking",
    "tests.event_alpha.test_evidence_acquisition",
    "tests.event_alpha.test_evidence_quality",
    "tests.event_alpha.test_exchange_universe_providers",
    "tests.event_alpha.test_fade_core",
    "tests.event_alpha.test_fade_review_workflows",
    "tests.event_alpha.test_fade_validation",
    "tests.event_alpha.test_feedback_calibration",
    "tests.event_alpha.test_impact_hypotheses",
    "tests.event_alpha.test_integrated_merge_policy",
    "tests.event_alpha.test_incident_relevance",
    "tests.event_alpha.test_llm_radar",
    "tests.event_alpha.test_market_enrichment",
    "tests.event_alpha.test_market_data_providers",
    "tests.event_alpha.test_market_surfaces",
    "tests.event_alpha.test_namespace_integrations",
    "tests.event_alpha.test_namespace_ledgers",
    "tests.event_alpha.test_namespace_profiles",
    "tests.event_alpha.test_news_providers",
    "tests.event_alpha.test_no_old_event_alpha_imports",
    "tests.event_alpha.test_notification_delivery",
    "tests.event_alpha.test_notification_inbox_rehearsals",
    "tests.event_alpha.test_notification_lanes",
    "tests.event_alpha.test_notification_operations",
    "tests.event_alpha.test_notification_planning",
    "tests.event_alpha.test_notification_readiness",
    "tests.event_alpha.test_notification_routing",
    "tests.event_alpha.test_operator_identity",
    "tests.event_alpha.test_operator_presentation",
    "tests.event_alpha.test_operator_workflows",
    "tests.event_alpha.test_playbooks_graph",
    "tests.event_alpha.test_provider_activation",
    "tests.event_alpha.test_quality_feedback",
    "tests.event_alpha.test_radar_pipeline",
    "tests.event_alpha.test_scheduled_catalyst_namespaces",
    "tests.event_alpha.test_shim_registry",
    "tests.event_alpha.test_source_coverage_reports",
    "tests.event_alpha.test_source_registry",
    "tests.event_alpha.test_watchlist_router",
)

_RSI_TEST_MODULES = (
    "tests.rsi.test_backups",
    "tests.rsi.test_backtest",
    "tests.rsi.test_indicators_core",
    "tests.rsi.test_paper_risk",
    "tests.rsi.test_security",
)

_CLI_TEST_MODULES = (
    "tests.cli.test_dependency_ci",
    "tests.cli.test_event_alpha_operator_command_smoke",
    "tests.cli.test_make_targets",
    "tests.cli.test_parser",
)


def _iter_standalone_tests():
    import importlib

    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            yield __name__, name, value

    for module_name in _EVENT_ALPHA_TEST_MODULES + _RSI_TEST_MODULES + _CLI_TEST_MODULES:
        module = importlib.import_module(module_name)
        for name, value in sorted(vars(module).items()):
            if name.startswith("test_") and callable(value):
                yield module_name, name, value


def _call_standalone_test(fn):
    import copy
    import inspect
    from crypto_rsi_scanner import config

    kwargs = {}
    temp_dirs = []
    original_config = {}
    for config_name in dir(config):
        if not config_name.isupper():
            continue
        value = getattr(config, config_name)
        try:
            original_config[config_name] = copy.deepcopy(value)
        except Exception:  # noqa: BLE001
            original_config[config_name] = value
    for name, param in inspect.signature(fn).parameters.items():
        if param.default is not inspect.Parameter.empty:
            continue
        if name == "tmp_path":
            tmp = TemporaryDirectory()
            temp_dirs.append(tmp)
            kwargs[name] = Path(tmp.name)
            continue
        raise TypeError(f"unsupported standalone fixture: {name}")

    try:
        fn(**kwargs)
    finally:
        for config_name in tuple(dir(config)):
            if config_name.isupper() and config_name not in original_config:
                delattr(config, config_name)
        for config_name, value in original_config.items():
            setattr(config, config_name, value)
        for tmp in reversed(temp_dirs):
            tmp.cleanup()


def _run_all():
    funcs = list(_iter_standalone_tests())
    failures = 0
    for module_name, name, fn in funcs:
        label = name if module_name == __name__ else f"{module_name}.{name}"
        try:
            _call_standalone_test(fn)
            print(f"PASS {label}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {label}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"ERROR {label}: {type(e).__name__}: {e}")
    print(f"\n{len(funcs) - failures}/{len(funcs)} passed")
    return failures


if __name__ == "__main__":
    if "--list-tests" in sys.argv:
        tests = list(_iter_standalone_tests())
        event_alpha_tests = sum(1 for module_name, _, _ in tests if module_name.startswith("tests.event_alpha."))
        rsi_tests = sum(1 for module_name, _, _ in tests if module_name.startswith("tests.rsi."))
        cli_tests = sum(1 for module_name, _, _ in tests if module_name.startswith("tests.cli."))
        umbrella_tests = sum(1 for module_name, _, _ in tests if module_name == __name__)
        print(f"standalone_tests={len(tests)}")
        print(f"event_alpha_tests={event_alpha_tests}")
        print(f"rsi_tests={rsi_tests}")
        print(f"cli_tests={cli_tests}")
        print(f"umbrella_tests={umbrella_tests}")
        sys.exit(0)
    sys.exit(1 if _run_all() else 0)
