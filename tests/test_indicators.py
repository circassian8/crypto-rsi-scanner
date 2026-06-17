"""Unit tests for the indicator math. Pure functions, no network.

Run with pytest:   pytest
Or standalone:     python tests/test_indicators.py
"""

from __future__ import annotations

import os
import sys
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
from crypto_rsi_scanner import event_provider_status, formatting


def test_rsi_bounds():
    s = pd.Series(np.random.RandomState(0).randn(200).cumsum() + 100)
    rsi = wilder_rsi(s, 14).dropna()
    assert rsi.between(0, 100).all()


def test_rsi_pure_uptrend_is_high():
    s = pd.Series(np.arange(1, 101, dtype=float))  # strictly increasing
    rsi = wilder_rsi(s, 14).dropna()
    assert rsi.iloc[-1] == 100.0


def test_rsi_pure_downtrend_is_low():
    s = pd.Series(np.arange(100, 0, -1, dtype=float))  # strictly decreasing
    rsi = wilder_rsi(s, 14).dropna()
    assert rsi.iloc[-1] == 0.0


def test_rsi_matches_known_value():
    # Classic Wilder worked example (first 14 deltas), final RSI ~ 70.46
    closes = pd.Series([
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28,
    ])
    rsi = wilder_rsi(closes, 14).dropna()
    assert abs(rsi.iloc[-1] - 70.46) < 0.5


def test_annualized_vol_constant_is_zero():
    s = pd.Series([100.0] * 50)
    assert annualized_vol(s) == 0.0


def test_z_score_zero_when_flat():
    rsi = pd.Series([50.0] * 100)
    assert rsi_z_score(rsi, 90) == 0.0


def test_rate_of_change():
    rsi = pd.Series([50, 52, 55, 66], dtype=float)
    assert rsi_rate_of_change(rsi, 3) == 16.0


def test_adaptive_thresholds_ordering():
    rsi = pd.Series(np.linspace(20, 80, 100))
    ob, os_ = adaptive_thresholds(rsi, 95, 5)
    assert os_ < ob
    assert 20 <= os_ <= 80 and 20 <= ob <= 80


def test_adaptive_thresholds_fallback_when_short():
    rsi = pd.Series([50.0, 51.0])
    assert adaptive_thresholds(rsi) == (70.0, 30.0)


def test_volume_ratio_spike():
    vols = pd.Series([100.0] * 20 + [300.0])
    assert abs(volume_ratio(vols, 20) - 3.0) < 1e-6


def test_state_features_realized_vol_flat_and_changing():
    from crypto_rsi_scanner import state_features as sf

    flat = pd.Series([100.0] * 80)
    changing = pd.Series(np.linspace(100, 130, 80) + np.sin(np.arange(80)) * 3.0)
    assert sf.realized_vol(flat, window=20) == 0.0
    assert sf.realized_vol(changing, window=20) > 0.0
    vol_s = sf.realized_vol_series(changing, window=20)
    assert vol_s.dropna().iloc[-1] > 0.0


def test_state_features_trailing_percentile_is_trailing_only():
    from crypto_rsi_scanner import state_features as sf

    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 0.0])
    pct = sf.trailing_percentile_series(s, window=5)
    assert pct.iloc[4] >= 0.9      # current max in [1,2,3,4,5]
    assert pct.iloc[5] <= 0.1      # current min in [2,3,4,5,0]
    assert sf.trailing_percentile(pd.Series([10.0] * 10), window=5) == 0.5


def test_state_features_volatility_state_rules():
    from crypto_rsi_scanner import state_features as sf

    assert sf.volatility_state(float("nan"), 0.2, 0.5) == "unknown"
    assert sf.volatility_state(0.10, 0.20, 0.20) == "low_compressed"
    assert sf.volatility_state(0.25, 0.25, 0.50) == "normal"
    assert sf.volatility_state(0.35, 0.30, 0.72) == "high"
    assert sf.volatility_state(0.40, 0.30, 0.80) == "high_expanding"
    assert sf.volatility_state(0.50, 0.35, 0.95) == "crisis"


def test_makefile_has_clean_export_and_bootstrap_targets():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert "PYTHON ?= .venv/bin/python" in makefile
    assert "check-python:" in makefile
    assert "bootstrap:" in makefile
    assert "python3 -m venv .venv" in makefile
    assert "export-src:" in makefile
    assert "git archive --format=zip -o crypto-rsi-scanner-source.zip HEAD" in makefile
    assert "event-fade-check-review-template:" in makefile
    assert "--event-fade-check-review-template $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_REVIEW_TEMPLATE)" in makefile
    assert "Run 'make bootstrap' or override with 'make verify PYTHON=python3'." in makefile

    export_dry = subprocess.run(
        ["make", "-n", "export-src"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "git archive --format=zip -o crypto-rsi-scanner-source.zip HEAD" in export_dry.stdout

    verify_dry = subprocess.run(
        ["make", "-n", "verify", "PYTHON=python3"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "python3 tests/test_indicators.py" in verify_dry.stdout
    assert ".venv/bin/python tests/test_indicators.py" not in verify_dry.stdout


def test_state_features_cross_sectional_ranks_monotonic():
    from crypto_rsi_scanner import state_features as sf

    ranks = sf.cross_sectional_ranks({"weak": -1.0, "mid": 0.0, "strong": 2.0})
    assert ranks["weak"] == 0.0
    assert ranks["mid"] == 0.5
    assert ranks["strong"] == 1.0
    tied = sf.cross_sectional_ranks({"a": 1.0, "b": 1.0, "c": float("nan")})
    assert tied["a"] == tied["b"]
    assert tied["c"] == 0.5


def test_state_features_rolling_beta_synthetic():
    from crypto_rsi_scanner import state_features as sf

    rng = np.random.RandomState(7)
    btc_ret = rng.normal(0.0005, 0.01, 140)
    asset_ret = 2.0 * btc_ret + rng.normal(0.0, 0.001, 140)
    eth_ret = rng.normal(0.0002, 0.012, 140)
    btc = pd.Series(100.0 * np.cumprod(1.0 + btc_ret))
    asset = pd.Series(50.0 * np.cumprod(1.0 + asset_ret))
    eth = pd.Series(80.0 * np.cumprod(1.0 + eth_ret))

    assert abs(sf.rolling_beta(asset, btc, window=120) - 2.0) < 0.15
    multi = sf.rolling_multi_beta(asset, {"BTC": btc, "ETH": eth}, window=120)
    assert abs(multi["beta_BTC"] - 2.0) < 0.15
    assert abs(multi["beta_ETH"]) < 0.15
    assert 0.0 <= multi["r2"] <= 1.0


def test_state_features_volume_and_liquidity():
    from crypto_rsi_scanner import state_features as sf

    volume = pd.Series([100.0] * 89 + [250.0])
    close = pd.Series([10.0] * 90)
    market_cap = pd.Series([10_000.0] * 90)

    assert sf.volume_z_score(volume, window=90) > 5.0
    assert sf.dollar_volume_20(close, volume, volume_is_usd=True) > 100.0
    assert sf.dollar_volume_20(close, volume, volume_is_usd=False) > 1000.0
    assert sf.turnover_20(close * volume, market_cap) > 0.10
    assert sf.volume_price_state(-0.04, 2.0) == "down_high_volume"
    assert sf.volume_price_state(0.04, 2.0) == "up_high_volume"
    assert sf.volume_price_state(0.0, 2.0) == "spike_flat_price"
    assert sf.volume_price_state(0.04, 0.0) == "up_normal_volume"
    assert sf.rank_bucket(0.9) == "high"
    assert sf.rank_bucket(0.1) == "low"
    assert sf.liquidity_bucket(1_000_000, 0.02) == "low"
    assert sf.liquidity_bucket(200_000_000, 0.0) == "high"
    assert sf.falling_knife_bucket(75) == "high"
    assert sf.falling_knife_score(
        vol_state="crisis",
        breadth_state="breadth_collapse",
        rs_bucket="low",
        regime="DOWNTREND",
        volume_state="down_high_volume",
        ret_30d=-0.30,
        btc_beta_60=1.5,
        beta_r2_60=0.6,
    ) >= 90


def test_state_features_breadth_snapshot_handles_missing_and_short_histories():
    from crypto_rsi_scanner import state_features as sf

    assert sf.breadth_snapshot({"a": pd.Series([1.0, 2.0])}, {})["state"] == "unknown"

    idx = pd.date_range("2026-01-01", periods=220, freq="D", tz="UTC")
    closes = {
        "a": pd.Series(np.linspace(10, 40, 220), index=idx),
        "b": pd.Series(np.linspace(20, 50, 220), index=idx),
        "c": pd.Series(np.linspace(30, 45, 220), index=idx),
        "short": pd.Series([1.0, 2.0, 3.0], index=idx[:3]),
    }
    rsi = {
        "a": pd.Series([65.0] * 220, index=idx),
        "b": pd.Series([62.0] * 220, index=idx),
        "c": pd.Series([45.0] * 220, index=idx),
    }
    snap = sf.breadth_snapshot(closes, rsi, asof=idx[-1])
    assert snap["median_rsi"] == 62.0
    assert snap["pct_rsi_gt_60"] == 2 / 3
    assert snap["pct_above_50dma"] == 1.0
    assert snap["pct_above_200dma"] == 1.0
    assert snap["state"] == "risk_on_broad"


def test_btc_correlation_perfect():
    btc = pd.Series(np.arange(1, 41, dtype=float))
    coin = btc * 2.0  # perfectly correlated returns
    assert btc_correlation(coin, btc, 30) > 0.99


def test_divergence_bearish():
    # price higher high, RSI lower high -> bearish
    n = 40
    price = pd.Series(np.concatenate([
        np.linspace(10, 20, 10),  # peak ~20
        np.linspace(20, 12, 10),
        np.linspace(12, 25, 10),  # higher peak ~25
        np.linspace(25, 18, 10),
    ]))
    rsi = pd.Series(np.concatenate([
        np.linspace(40, 85, 10),  # high RSI peak
        np.linspace(85, 45, 10),
        np.linspace(45, 70, 10),  # lower RSI peak
        np.linspace(70, 55, 10),
    ]))
    assert detect_divergence(price, rsi, lookback=40, order=3) == "bearish"


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


def test_event_provider_status_blocks_enrichment_only_config():
    cfg = _event_provider_status_cfg(
        EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH="fixtures/event_discovery/coinalyze_derivatives.json",
        EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH="fixtures/event_discovery/tokenomist_supply.json",
    )
    report = event_provider_status.build_event_discovery_provider_status(cfg)
    text = event_provider_status.format_event_discovery_provider_status(report)
    as_dict = event_provider_status.provider_status_to_dict(report)

    assert report.ready_event_source_count == 0
    assert report.ready_enrichment_count >= 3  # aliases plus the two explicit fixtures
    assert not report.ready_for_configured_review_cycle
    assert "No event sources are ready" in text
    assert "configured review cycle ready: no" in text
    assert as_dict["ready_for_configured_review_cycle"] is False


def test_event_provider_status_ready_with_live_source_and_redacted_credentials():
    cfg = _event_provider_status_cfg(
        EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE=True,
        EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY="secret-key",
        EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET="secret-value",
        EVENT_DISCOVERY_CRYPTOPANIC_LIVE=True,
    )
    report = event_provider_status.build_event_discovery_provider_status(cfg)
    text = event_provider_status.format_event_discovery_provider_status(report)

    assert report.ready_event_source_count == 1
    assert report.ready_for_configured_review_cycle
    assert "binance_announcements" in text
    assert "api_key=present" in text
    assert "api_secret=present" in text
    assert "secret-key" not in text
    assert "secret-value" not in text
    assert "CryptoPanic live mode is enabled but the API token is missing" in text


def test_event_provider_status_ready_with_rss_url_file():
    cfg = _event_provider_status_cfg(
        EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=True,
        EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS=("https://example.test/rss",),
        EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH="public_rss_feeds.txt",
    )
    report = event_provider_status.build_event_discovery_provider_status(cfg)
    text = event_provider_status.format_event_discovery_provider_status(report)

    assert report.ready_event_source_count == 1
    assert report.ready_for_configured_review_cycle
    assert "project_blog_rss" in text
    assert "url_count=1" in text
    assert "url_file=public_rss_feeds.txt" in text
    assert "Project blog/RSS live mode is enabled but no RSS/Atom URLs are configured" not in text


def test_event_provider_status_ready_with_live_prediction_market_source():
    cfg = _event_provider_status_cfg(
        EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=True,
        EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT=12,
    )
    report = event_provider_status.build_event_discovery_provider_status(cfg)
    text = event_provider_status.format_event_discovery_provider_status(report)

    assert report.ready_event_source_count == 1
    assert report.ready_for_configured_review_cycle
    assert "prediction_market_events" in text
    assert "live=on" in text
    assert "limit=12" in text


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


def test_public_rss_make_target_does_not_inject_fixture_aliases():
    import subprocess

    result = subprocess.run(
        ["make", "-n", "event-discovery-refresh-public-rss"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH=fixtures/event_discovery/public_rss_feeds.txt" in result.stdout
    assert "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1" in result.stdout
    assert "RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT=250" in result.stdout
    assert "RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=720" in result.stdout
    assert "fixtures/event_discovery/asset_aliases.json" not in result.stdout


def test_public_rss_feed_list_targets_proxy_instrument_research():
    from pathlib import Path
    from urllib.parse import parse_qs, urlparse

    path = Path("fixtures/event_discovery/public_rss_feeds.txt")
    urls = [
        line.split("#", 1)[0].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.split("#", 1)[0].strip()
    ]
    google_queries = [
        parse_qs(urlparse(url).query).get("q", [""])[0].lower()
        for url in urls
        if "news.google.com/rss/search" in url
    ]
    joined = " ".join(google_queries)

    assert len(google_queries) >= 5
    for term in (
        "pre-ipo",
        "synthetic exposure",
        "tokenized stock",
        "spacex",
        "openai",
        "fan token",
        "prediction market",
        "election",
    ):
        assert term in joined


def test_polymarket_make_target_uses_live_prediction_market_source():
    import subprocess

    result = subprocess.run(
        ["make", "-n", "event-fade-polymarket-review-cycle"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "event-discovery-refresh-polymarket" in result.stdout
    assert "RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=1" in result.stdout
    assert "RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT=100" in result.stdout
    assert "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1" in result.stdout
    assert "event-fade-cache-review-bundle" in result.stdout


def test_gdelt_make_target_uses_live_news_source():
    import subprocess

    result = subprocess.run(
        ["make", "-n", "event-fade-gdelt-review-cycle"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "event-discovery-refresh-gdelt" in result.stdout
    assert "RSI_EVENT_DISCOVERY_GDELT_LIVE=1" in result.stdout
    assert "RSI_EVENT_DISCOVERY_GDELT_QUERY=" in result.stdout
    assert "RSI_EVENT_DISCOVERY_GDELT_MAX_RECORDS=50" in result.stdout
    assert "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1" in result.stdout
    assert "event-fade-cache-review-bundle" in result.stdout
    assert "fixtures/event_discovery/asset_aliases.json" not in result.stdout


def test_no_key_make_target_combines_public_rss_gdelt_and_polymarket_sources():
    import subprocess

    result = subprocess.run(
        ["make", "-n", "event-fade-no-key-review-cycle"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "event-discovery-refresh-public-rss" in result.stdout
    assert "event-discovery-refresh-gdelt" in result.stdout
    assert "event-discovery-refresh-polymarket" in result.stdout
    assert "RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1" in result.stdout
    assert "RSI_EVENT_DISCOVERY_GDELT_LIVE=1" in result.stdout
    assert "RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=1" in result.stdout
    assert "event-fade-cache-review-bundle" in result.stdout


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


def _stamp_review_provenance(row, reviewer="human", reviewed_at="2026-06-17T12:00:00+00:00"):
    row["reviewed_by"] = reviewer
    row["reviewed_at"] = reviewed_at
    return row


def _event_discovery_fixture_result():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

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
    from crypto_rsi_scanner import event_discovery

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
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": bybit_path,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": coinmarketcal_path,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": tokenomist_path,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": cryptopanic_path,
        "EVENT_DISCOVERY_GDELT_PATH": gdelt_path,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": blog_path,
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH": ipo_path,
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH": sports_path,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": prediction_path,
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH": _derivatives_fixture_path(),
        "EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH": tokenomist_supply_path,
        "EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH": etherscan_supply_path,
        "EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH": arkham_supply_path,
        "EVENT_DISCOVERY_DUNE_SUPPLY_PATH": dune_supply_path,
        "EVENT_DISCOVERY_UNIVERSE_PATH": _coingecko_universe_fixture_path(),
        "EVENT_DISCOVERY_LOOKBACK_HOURS": 120,
        "EVENT_DISCOVERY_HORIZON_DAYS": 2,
    }


def test_event_discovery_manual_provider_fixture_and_missing_path():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider

    events_path, _ = _event_discovery_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    events = ManualJsonEventProvider(events_path, required=True).fetch_events(start, end)
    assert len(events) == 6
    assert events[0].content_hash
    assert events[0].published_at <= events[0].fetched_at
    assert ManualJsonEventProvider(Path("/definitely/missing.json")).fetch_events(start, end) == []

    try:
        ManualJsonEventProvider(Path("/definitely/missing.json"), required=True).fetch_events(start, end)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("required missing manual fixture should fail")

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad.json"
        bad_path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        assert ManualJsonEventProvider(bad_path).fetch_events(start, end) == []

        try:
            ManualJsonEventProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed manual fixture should fail")


def test_event_discovery_coingecko_universe_provider_uses_hygiene():
    from crypto_rsi_scanner.event_providers.coingecko_universe import CoinGeckoUniverseProvider

    assets = CoinGeckoUniverseProvider(_coingecko_universe_fixture_path(), required=True).fetch_assets()
    by_id = {asset.coin_id: asset for asset in assets}
    assert set(by_id) == {"bitcoin", "ethereum", "solana"}
    assert by_id["bitcoin"].symbol == "BTC"
    assert by_id["bitcoin"].price == 68000.0
    assert by_id["bitcoin"].source == "coingecko_universe"
    assert "tether" not in by_id


def test_event_discovery_coingecko_universe_provider_can_fetch_live_offline():
    from crypto_rsi_scanner.event_providers.coingecko_universe import CoinGeckoUniverseProvider

    calls = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def get_top_markets(self, n):
            calls.append(n)
            return [
                {
                    "id": "bitcoin",
                    "symbol": "btc",
                    "name": "Bitcoin",
                    "current_price": 68000.0,
                    "market_cap": 1300000000000.0,
                    "total_volume": 35000000000.0,
                    "price_change_percentage_24h_in_currency": 1.2,
                },
                {
                    "id": "tether",
                    "symbol": "usdt",
                    "name": "Tether",
                    "current_price": 1.0,
                    "market_cap": 110000000000.0,
                    "total_volume": 60000000000.0,
                    "price_change_percentage_24h_in_currency": 0.01,
                },
                {
                    "id": "ethereum",
                    "symbol": "eth",
                    "name": "Ethereum",
                    "current_price": 3600.0,
                    "market_cap": 430000000000.0,
                    "total_volume": 18000000000.0,
                    "price_change_percentage_24h_in_currency": -0.8,
                },
                {
                    "id": "solana",
                    "symbol": "sol",
                    "name": "Solana",
                    "current_price": 160.0,
                    "market_cap": 75000000000.0,
                    "total_volume": 4500000000.0,
                    "price_change_percentage_24h_in_currency": 3.4,
                },
            ]

    assets = CoinGeckoUniverseProvider(
        None,
        live_enabled=True,
        limit=2,
        live_fetch_limit=4,
        client_factory=lambda: FakeClient(),
        required=True,
    ).fetch_assets()

    assert calls == [4]
    assert [asset.coin_id for asset in assets] == ["bitcoin", "ethereum"]
    assert assets[0].symbol == "BTC"
    assert assets[1].price == 3600.0


def test_event_discovery_coingecko_universe_provider_live_fail_soft():
    from crypto_rsi_scanner.event_providers.coingecko_universe import CoinGeckoUniverseProvider

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def get_top_markets(self, _n):
            raise TimeoutError("fixture timeout")

    assert CoinGeckoUniverseProvider(
        None,
        live_enabled=True,
        client_factory=lambda: FailingClient(),
    ).fetch_assets() == []


def test_event_discovery_exchange_announcement_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider
    from crypto_rsi_scanner.event_providers.bybit_announcements import BybitAnnouncementProvider

    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    binance_events = BinanceAnnouncementProvider(binance_path, required=True).fetch_events(start, end)
    bybit_events = BybitAnnouncementProvider(bybit_path, required=True).fetch_events(start, end)
    assert len(binance_events) == 1
    assert len(bybit_events) == 1
    assert binance_events[0].provider == "binance_announcements"
    assert binance_events[0].raw_json["event"]["event_type"] == "exchange_listing"
    assert binance_events[0].raw_json["event"]["event_time"] == "2026-06-15T12:00:00+00:00"
    assert bybit_events[0].provider == "bybit_announcements"
    assert bybit_events[0].raw_json["event"]["event_type"] == "perp_listing"

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_announcements.json"
        bad_path.write_text(json.dumps({"result": {"list": ["not an object"]}}), encoding="utf-8")
        assert BinanceAnnouncementProvider(bad_path).fetch_events(start, end) == []
        try:
            BinanceAnnouncementProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed announcement fixture should fail")


def test_event_discovery_binance_cms_websocket_payload_fixture():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider

    payload = {
        "type": "DATA",
        "topic": "com_announcement_en",
        "data": json.dumps({
            "catalogId": 48,
            "catalogName": "New Cryptocurrency Listing",
            "publishDate": 1781514000000,
            "title": "Binance Will List Test Live (TLIVE)",
            "body": "Binance will list Test Live and open spot trading for TLIVE/USDT.",
            "disclaimer": "Trade on-the-go.",
        }),
    }
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "binance_cms_payload.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        events = BinanceAnnouncementProvider(path, required=True).fetch_events(start, end)
    assert len(events) == 1
    event = events[0]
    assert event.provider == "binance_announcements"
    assert event.title == "Binance Will List Test Live (TLIVE)"
    assert event.published_at.isoformat() == "2026-06-15T09:00:00+00:00"
    assert event.raw_json["topic"] == "com_announcement_en"
    assert event.raw_json["message_type"] == "DATA"
    assert event.raw_json["catalogName"] == "New Cryptocurrency Listing"
    assert event.raw_json["event"]["event_type"] == "exchange_listing"
    assert event.raw_json["event"]["event_time"] == "2026-06-15T09:00:00+00:00"
    assert event.raw_json["event"]["event_time_confidence"] == 0.60


def test_event_discovery_binance_live_websocket_provider_parses_offline():
    import hashlib
    import hmac
    import json
    from datetime import datetime, timezone

    import aiohttp

    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider

    payload = {
        "type": "DATA",
        "topic": "com_announcement_en",
        "data": json.dumps({
            "catalogId": 48,
            "catalogName": "New Cryptocurrency Listing",
            "publishDate": 1781514000000,
            "title": "Binance Will List Test Live (TLIVE)",
            "body": "Binance will list Test Live and open spot trading for TLIVE/USDT.",
        }),
    }
    messages = [
        type("Msg", (), {"type": aiohttp.WSMsgType.TEXT, "data": json.dumps({"type": "COMMAND", "code": "000000"})}),
        type("Msg", (), {"type": aiohttp.WSMsgType.TEXT, "data": json.dumps(payload)}),
        type("Msg", (), {"type": aiohttp.WSMsgType.CLOSED, "data": ""}),
    ]
    seen = {}

    class FakeWs:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def receive(self):
            return messages.pop(0)

    class FakeSession:
        def __init__(self, **kwargs):
            seen["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def ws_connect(self, url, *, headers=None, heartbeat=None):
            seen["url"] = url
            seen["headers"] = headers
            seen["heartbeat"] = heartbeat
            return FakeWs()

    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    events = BinanceAnnouncementProvider(
        None,
        live_enabled=True,
        api_key="binance-key",
        api_secret="binance-secret",
        ws_url="wss://example.test/sapi/wss",
        listen_seconds=1,
        session_factory=FakeSession,
        clock=lambda: 1781514000.0,
        random_factory=lambda: "fixed-random",
        required=True,
    ).fetch_events(start, end)

    signed_payload = "random=fixed-random&topic=com_announcement_en&recvWindow=30000&timestamp=1781514000000"
    signature = hmac.new(b"binance-secret", signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    assert seen["url"] == f"wss://example.test/sapi/wss?{signed_payload}&signature={signature}"
    assert seen["headers"] == {"X-MBX-APIKEY": "binance-key"}
    assert seen["heartbeat"] == 30.0
    assert len(events) == 1
    assert events[0].provider == "binance_announcements"
    assert events[0].title == "Binance Will List Test Live (TLIVE)"
    assert events[0].raw_json["message_type"] == "DATA"
    assert events[0].raw_json["event"]["event_type"] == "exchange_listing"


def test_event_discovery_binance_live_websocket_missing_credentials_fail_soft():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider

    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    assert BinanceAnnouncementProvider(None, live_enabled=True).fetch_events(start, end) == []


def test_event_discovery_bybit_live_provider_parses_documented_response_offline():
    import json
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_providers.bybit_announcements import BybitAnnouncementProvider

    class FakeResponse:
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
        return FakeResponse({
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "total": 2,
                "list": [
                    {
                        "title": "New Listing: Test Live (TLIVE) — Deposit and Trade TLIVE",
                        "description": "Bybit is excited to announce the listing of TLIVE on Spot.",
                        "type": {"title": "New Listings", "key": "new_crypto"},
                        "tags": ["Spot", "Spot Listings"],
                        "url": "https://announcements.bybit.com/en-US/article/test-live/",
                        "dateTimestamp": 1781514000000,
                        "startDateTimestamp": 1781524800000,
                    },
                    {
                        "title": "Bybit savings campaign for TLIVE holders",
                        "description": "Earn rewards for completing tasks.",
                        "type": {"title": "Latest Activities", "key": "latest_activities"},
                        "dateTimestamp": 1781517600000,
                    },
                ],
            },
        })

    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    provider = BybitAnnouncementProvider(
        None,
        live_enabled=True,
        base_url="https://api.bybit.test",
        locale="en-US",
        announcement_type="new_crypto",
        limit=2,
        timeout=3.5,
        opener=fake_opener,
    )
    events = provider.fetch_events(start, end)
    assert len(events) == 1
    assert seen["url"] == "https://api.bybit.test/v5/announcements/index?locale=en-US&page=1&limit=2&type=new_crypto"
    assert seen["timeout"] == 3.5
    event = events[0]
    assert event.provider == "bybit_announcements"
    assert event.source_url == "https://announcements.bybit.com/en-US/article/test-live/"
    assert event.published_at.isoformat() == "2026-06-15T09:00:00+00:00"
    assert event.raw_json["event"]["event_type"] == "exchange_listing"
    assert event.raw_json["event"]["event_time"] == "2026-06-15T12:00:00+00:00"
    assert event.raw_json["event"]["event_time_confidence"] == 1.0

    def failing_opener(request, timeout):
        raise TimeoutError("offline timeout")

    assert BybitAnnouncementProvider(
        None,
        live_enabled=True,
        opener=failing_opener,
    ).fetch_events(start, end) == []


def test_event_discovery_structured_calendar_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.coinmarketcal import CoinMarketCalProvider
    from crypto_rsi_scanner.event_providers.tokenomist import TokenomistProvider

    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    calendar_events = CoinMarketCalProvider(coinmarketcal_path, required=True).fetch_events(start, end)
    unlock_events = TokenomistProvider(tokenomist_path, required=True).fetch_events(start, end)
    assert len(calendar_events) == 1
    assert len(unlock_events) == 1
    assert calendar_events[0].provider == "coinmarketcal"
    assert calendar_events[0].raw_json["event"]["event_type"] == "mainnet_launch"
    assert "TESTCAL" in (calendar_events[0].body or "")
    assert unlock_events[0].provider == "tokenomist"
    assert unlock_events[0].raw_json["event"]["event_type"] == "token_unlock"
    assert unlock_events[0].raw_json["supply"]["unlock_pct_circulating"] == 0.12

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_calendar.json"
        bad_path.write_text(json.dumps({"events": ["not an object"]}), encoding="utf-8")
        assert CoinMarketCalProvider(bad_path).fetch_events(start, end) == []
        try:
            CoinMarketCalProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed calendar fixture should fail")


def test_event_discovery_normalizes_and_dedupes_events():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider

    events_path, _ = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    normalized = [event_discovery.normalize_raw_event(event) for event in raw]
    assert len(normalized) == 6
    deduped = event_discovery.dedupe_events(normalized)
    assert len(deduped) == 5
    spacex = [event for event in deduped if event.event_name == "SpaceX IPO trading start"][0]
    assert spacex.event_type == "ipo_proxy"
    assert spacex.external_asset == "SpaceX"
    assert len(spacex.raw_ids) == 2
    assert spacex.confidence == 1.0


def test_event_discovery_canonical_dedupe_merges_variant_headlines_and_payloads():
    import copy
    from dataclasses import replace
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider, content_hash
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    base = raw[0]

    def variant(raw_id, title, body, *, keep_sections):
        payload = copy.deepcopy(base.raw_json)
        payload["raw_id"] = raw_id
        payload["title"] = title
        payload["body"] = body
        payload["event"]["event_id"] = raw_id
        payload["event"]["event_name"] = title
        payload["event"]["description"] = body
        for section in ("market", "derivatives", "supply", "rsi", "technical"):
            if section not in keep_sections:
                payload.pop(section, None)
        return replace(
            base,
            raw_id=raw_id,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json=payload,
            content_hash=content_hash(payload),
        )

    first = variant(
        "spacex-ipo-rich-market",
        "TESTVELVET lets traders access SpaceX pre-IPO market before debut",
        "TESTVELVET offers synthetic exposure to SpaceX before IPO trading starts.",
        keep_sections={"market", "derivatives", "supply", "rsi"},
    )
    second = variant(
        "spacex-nasdaq-rich-technical",
        "SpaceX opens Nasdaq trading on June 15 as TESTVELVET proxy token demand peaks",
        "TESTVELVET proxy token failed reclaim after the SpaceX pre-IPO proxy event.",
        keep_sections={"technical"},
    )
    result = event_discovery.run_discovery(
        [first, second],
        load_asset_aliases(aliases_path),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )

    assert len(result.normalized_events) == 1
    event = result.normalized_events[0]
    assert set(event.raw_ids) == {"spacex-ipo-rich-market", "spacex-nasdaq-rich-technical"}
    assert set(event.source_urls) == {
        "https://example.test/spacex-ipo-rich-market",
        "https://example.test/spacex-nasdaq-rich-technical",
    }
    candidate = result.candidates[0]
    assert candidate.data_quality["source_count"] == 2
    assert candidate.fade_candidate.market.price == 7.2
    assert candidate.fade_candidate.technical.failed_reclaim_event_vwap is True
    assert candidate.fade_candidate.technical.entry_reference_price == 7.2
    assert candidate.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED


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


def test_event_discovery_resolves_real_assets_from_clean_universe_fixture():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider

    events_path, _aliases_path = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = event_discovery.load_discovery_assets(
        None,
        universe_path=_coingecko_universe_fixture_path(),
    )
    assert {asset.coin_id for asset in assets} == {"bitcoin", "ethereum", "solana"}

    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    by_coin = {candidate.asset.coin_id: candidate for candidate in result.candidates}
    assert set(by_coin) == {"bitcoin"}
    btc = by_coin["bitcoin"]
    assert btc.asset.symbol == "BTC"
    assert btc.asset.price == 68000.0
    assert btc.classification.is_direct_beneficiary is True
    assert btc.fade_signal.signal_type == FadeSignalType.NO_TRADE


def test_event_discovery_exchange_announcements_are_direct_no_trade():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = event_discovery.load_discovery_events(
        None,
        start,
        end,
        binance_announcements_path=binance_path,
        bybit_announcements_path=bybit_path,
    )
    assets = load_asset_aliases(aliases_path)
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert len(raw) == 2
    assert set(by_symbol) == {"TESTLIST", "TESTPERP"}

    listing = by_symbol["TESTLIST"]
    assert listing.event.event_type == "exchange_listing"
    assert listing.classification.relationship_type == "direct_listing"
    assert listing.classification.is_direct_beneficiary is True
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    perp = by_symbol["TESTPERP"]
    assert perp.event.event_type == "perp_listing"
    assert perp.classification.relationship_type == "direct_listing"
    assert perp.classification.is_direct_beneficiary is True
    assert perp.fade_signal.signal_type == FadeSignalType.NO_TRADE


def test_event_discovery_calendar_and_unlock_events_are_direct_no_trade():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    _events_path, aliases_path = _event_discovery_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = event_discovery.load_discovery_events(
        None,
        start,
        end,
        coinmarketcal_path=coinmarketcal_path,
        tokenomist_path=tokenomist_path,
    )
    assets = load_asset_aliases(aliases_path)
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert len(raw) == 2
    assert set(by_symbol) == {"TESTCAL", "TESTUNLOCK"}

    calendar = by_symbol["TESTCAL"]
    assert calendar.event.event_type == "mainnet_launch"
    assert calendar.classification.relationship_type == "direct_protocol_upgrade"
    assert calendar.classification.is_direct_beneficiary is True
    assert calendar.fade_signal.signal_type == FadeSignalType.NO_TRADE

    unlock = by_symbol["TESTUNLOCK"]
    assert unlock.event.event_type == "token_unlock"
    assert unlock.classification.relationship_type == "direct_unlock"
    assert unlock.classification.is_direct_beneficiary is True
    assert unlock.fade_candidate.supply.unlock_pct_circulating == 0.12
    assert unlock.fade_candidate.supply.unlock_amount == 2500000
    assert unlock.fade_signal.signal_type == FadeSignalType.NO_TRADE


def test_event_discovery_coinalyze_derivatives_provider_parses_fixture():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.derivatives_providers.coinalyze import CoinalyzeDerivativesProvider

    snapshots = CoinalyzeDerivativesProvider(_derivatives_fixture_path(), required=True).fetch_snapshots()
    assert "testlist" in snapshots
    assert "TESTLIST" in snapshots
    assert "TESTLISTUSDT_PERP" in snapshots
    assert "TEST" not in snapshots
    listing = snapshots["testlist"]
    assert listing["symbol"] == "TESTLIST"
    assert listing["perp_available"] is True
    assert listing["funding_rate_8h"] == 0.0012
    assert listing["perp_spot_volume_ratio"] == 22.0
    assert snapshots["testperp"]["perp_available"] is False

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_derivatives.json"
        bad_path.write_text(json.dumps({"snapshots": ["not an object"]}), encoding="utf-8")
        assert CoinalyzeDerivativesProvider(bad_path).fetch_snapshots() == {}
        try:
            CoinalyzeDerivativesProvider(bad_path, required=True).fetch_snapshots()
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed derivatives fixture should fail")


def test_event_discovery_coinalyze_live_provider_parses_offline():
    import json
    from urllib.parse import parse_qs, urlparse
    from crypto_rsi_scanner.derivatives_providers.coinalyze import CoinalyzeDerivativesProvider

    seen = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def opener(request, timeout):
        parsed = urlparse(request.full_url)
        endpoint = parsed.path.rsplit("/", 1)[-1]
        query = parse_qs(parsed.query)
        header_value = next(
            value
            for key, value in request.headers.items()
            if key.lower() == "api_key"
        )
        seen.append((endpoint, query, header_value, timeout))
        payloads = {
            "open-interest": [
                {"symbol": "TESTLISTUSDT_PERP.A", "value": 18000000, "update": 1781513400},
                {"symbol": "TESTPERPUSDT_PERP.A", "value": 3000000, "update": 1781513400},
            ],
            "funding-rate": [
                {"symbol": "TESTLISTUSDT_PERP.A", "value": 0.0012, "update": 1781513400},
                {"symbol": "TESTPERPUSDT_PERP.A", "value": -0.0002, "update": 1781513400},
            ],
            "open-interest-history": [
                {
                    "symbol": "TESTLISTUSDT_PERP.A",
                    "history": [{"t": 1781427000, "c": 10000000}, {"t": 1781513400, "c": 18000000}],
                },
                {
                    "symbol": "TESTPERPUSDT_PERP.A",
                    "history": [{"t": 1781427000, "c": 3000000}, {"t": 1781513400, "c": 3000000}],
                },
            ],
            "liquidation-history": [
                {
                    "symbol": "TESTLISTUSDT_PERP.A",
                    "history": [{"t": 1781510000, "l": 1500000, "s": 1000000}],
                }
            ],
            "long-short-ratio-history": [
                {"symbol": "TESTLISTUSDT_PERP.A", "history": [{"t": 1781510000, "r": 1.8}, {"t": 1781513400, "r": 2.1}]}
            ],
            "ohlcv-history": [
                {
                    "symbol": "TESTLISTUSDT_PERP.A",
                    "history": [{"t": 1781510000, "v": 50000000}, {"t": 1781513400, "v": 20000000}],
                }
            ],
        }
        return FakeResponse(payloads[endpoint])

    snapshots = CoinalyzeDerivativesProvider(
        None,
        live_enabled=True,
        api_key="coinalyze-key",
        symbols=("TESTLISTUSDT_PERP.A", "TESTPERPUSDT_PERP.A"),
        base_url="https://example.test/v1/",
        timeout=3.0,
        opener=opener,
        clock=lambda: 1781513400,
        required=True,
    ).fetch_snapshots()

    assert [row[0] for row in seen] == [
        "open-interest",
        "funding-rate",
        "open-interest-history",
        "liquidation-history",
        "long-short-ratio-history",
        "ohlcv-history",
    ]
    assert all(row[2] == "coinalyze-key" for row in seen)
    assert seen[0][1]["symbols"] == ["TESTLISTUSDT_PERP.A,TESTPERPUSDT_PERP.A"]
    assert seen[0][1]["convert_to_usd"] == ["true"]

    listing = snapshots["TESTLIST"]
    assert listing["symbol"] == "TESTLIST"
    assert listing["open_interest"] == 18000000.0
    assert listing["open_interest_24h_change_pct"] == 0.8
    assert listing["funding_rate_8h"] == 0.0012
    assert listing["liquidations_24h"] == 2500000.0
    assert listing["long_short_ratio"] == 2.1
    assert listing["futures_volume_24h"] == 70000000.0
    assert snapshots["TESTPERP"]["open_interest_24h_change_pct"] == 0.0


def test_event_discovery_coinalyze_live_provider_auto_resolves_future_markets_offline():
    import json
    from urllib.parse import parse_qs, urlparse
    from crypto_rsi_scanner.derivatives_providers.coinalyze import CoinalyzeDerivativesProvider

    seen = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def opener(request, timeout):
        parsed = urlparse(request.full_url)
        endpoint = parsed.path.rsplit("/", 1)[-1]
        query = parse_qs(parsed.query)
        seen.append((endpoint, query, timeout))
        payloads = {
            "future-markets": [
                {
                    "symbol": "TESTLISTUSD_PERP.0",
                    "exchange": "SLOW",
                    "base_asset": "TESTLIST",
                    "quote_asset": "USD",
                    "is_perpetual": True,
                    "margined": "COIN",
                },
                {
                    "symbol": "TESTLISTUSDT_PERP.A",
                    "exchange": "BINANCE",
                    "base_asset": "TESTLIST",
                    "quote_asset": "USDT",
                    "is_perpetual": True,
                    "margined": "STABLE",
                },
                {
                    "symbol": "TESTPERPUSDT_PERP.A",
                    "exchange": "BYBIT",
                    "base_asset": "TESTPERP",
                    "quote_asset": "USDT",
                    "is_perpetual": True,
                    "margined": "STABLE",
                },
                {
                    "symbol": "UNRELATEDUSDT_PERP.A",
                    "exchange": "BINANCE",
                    "base_asset": "UNRELATED",
                    "quote_asset": "USDT",
                    "is_perpetual": True,
                    "margined": "STABLE",
                },
            ],
            "open-interest": [
                {"symbol": "TESTLISTUSDT_PERP.A", "value": 18000000, "update": 1781513400},
                {"symbol": "TESTPERPUSDT_PERP.A", "value": 3000000, "update": 1781513400},
            ],
            "funding-rate": [],
            "open-interest-history": [],
            "liquidation-history": [],
            "long-short-ratio-history": [],
            "ohlcv-history": [],
        }
        return FakeResponse(payloads[endpoint])

    snapshots = CoinalyzeDerivativesProvider(
        None,
        live_enabled=True,
        api_key="coinalyze-key",
        base_symbols=("TESTLIST", "TESTPERP"),
        base_url="https://example.test/v1/",
        opener=opener,
        clock=lambda: 1781513400,
        required=True,
    ).fetch_snapshots()

    assert seen[0][0] == "future-markets"
    assert seen[1][0] == "open-interest"
    assert seen[1][1]["symbols"] == ["TESTLISTUSDT_PERP.A,TESTPERPUSDT_PERP.A"]
    assert snapshots["TESTLIST"]["open_interest"] == 18000000.0
    assert snapshots["TESTPERP"]["open_interest"] == 3000000.0
    assert "UNRELATED" not in snapshots


def test_event_discovery_coinalyze_base_symbols_from_assets():
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_models import DiscoveredAsset

    assets = [
        DiscoveredAsset(coin_id="testlist", symbol="TESTLIST", name="Test List", aliases=("Test List",)),
        DiscoveredAsset(coin_id="testperp", symbol="TESTPERPUSDT", name="Test Perp"),
        DiscoveredAsset(coin_id="bad", symbol="", name="Bad", aliases=("not a ticker",)),
    ]
    assert event_discovery._coinalyze_base_symbols(assets) == ("TESTLIST", "TESTPERP")


def test_event_discovery_coinalyze_live_provider_missing_config_fail_soft():
    from crypto_rsi_scanner.derivatives_providers.coinalyze import CoinalyzeDerivativesProvider

    assert CoinalyzeDerivativesProvider(None, live_enabled=True).fetch_snapshots() == {}
    assert CoinalyzeDerivativesProvider(
        None,
        live_enabled=True,
        api_key="coinalyze-key",
    ).fetch_snapshots() == {}


def test_event_discovery_derivatives_enrich_candidates_without_overriding_raw():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(start, end)
    raw.extend(event_discovery.load_discovery_events(
        None,
        start,
        end,
        binance_announcements_path=binance_path,
        bybit_announcements_path=bybit_path,
    ))
    assets = load_asset_aliases(aliases_path)
    derivatives = event_discovery.load_derivatives_snapshots(_derivatives_fixture_path())
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        derivatives_by_asset=derivatives,
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}

    listing = by_symbol["TESTLIST"]
    assert listing.fade_candidate.derivatives is not None
    assert listing.fade_candidate.derivatives.open_interest_24h_change_pct == 0.65
    assert listing.fade_candidate.component_scores["derivatives_crowding"] == 100
    assert listing.data_quality["has_derivatives_snapshot"] is True
    assert listing.classification.is_direct_beneficiary is True
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    perp = by_symbol["TESTPERP"]
    assert perp.fade_candidate.derivatives is not None
    assert perp.fade_candidate.derivatives.perp_available is False
    assert perp.fade_candidate.component_scores["derivatives_crowding"] == 30
    assert perp.fade_signal.signal_type == FadeSignalType.NO_TRADE

    velvet = by_symbol["TESTVELVET"]
    assert velvet.fade_candidate.derivatives is not None
    assert velvet.fade_candidate.derivatives.open_interest is None
    assert velvet.fade_candidate.derivatives.open_interest_to_market_cap == 0.4
    assert velvet.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED


def test_event_discovery_supply_providers_parse_fixtures():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.supply_providers.arkham import ArkhamSupplyProvider
    from crypto_rsi_scanner.supply_providers.dune import DuneSupplyProvider
    from crypto_rsi_scanner.supply_providers.etherscan import EtherscanSupplyProvider
    from crypto_rsi_scanner.supply_providers.tokenomist import TokenomistSupplyProvider

    tokenomist_path, etherscan_path, arkham_path, dune_path = _supply_fixture_paths()
    tokenomist = TokenomistSupplyProvider(tokenomist_path, required=True).fetch_snapshots()
    etherscan = EtherscanSupplyProvider(etherscan_path, required=True).fetch_snapshots()
    arkham = ArkhamSupplyProvider(arkham_path, required=True).fetch_snapshots()
    dune = DuneSupplyProvider(dune_path, required=True).fetch_snapshots()
    assert tokenomist["testprediction"]["unlock_pct_circulating"] == 0.08
    assert tokenomist["TESTPRED"]["unlock_amount"] == 1800000.0
    assert tokenomist["testvelvet"]["unlock_pct_circulating"] == 0.0
    assert tokenomist["TESTVELVET"]["top_holder_concentration"] == 0.10
    assert etherscan["testlist"]["large_holder_exchange_inflow"] is True
    assert etherscan["TESTLIST"]["cex_inflow_pct_supply"] == 0.04
    assert arkham["testai"]["team_or_mm_wallet_activity"] is True
    assert dune["testfan"]["admin_or_mint_risk"] is True

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_supply.json"
        bad_path.write_text(json.dumps({"snapshots": ["not an object"]}), encoding="utf-8")
        assert TokenomistSupplyProvider(bad_path).fetch_snapshots() == {}
        try:
            TokenomistSupplyProvider(bad_path, required=True).fetch_snapshots()
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed supply fixture should fail")


def test_event_discovery_supply_enriches_without_overriding_raw_or_bypassing_gates():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, _bybit_path = _exchange_announcement_fixture_paths()
    _cryptopanic_path, _gdelt_path, _blog_path = _news_fixture_paths()
    _ipo_path, _sports_path, prediction_path = _external_catalyst_fixture_paths()
    tokenomist_path, etherscan_path, arkham_path, dune_path = _supply_fixture_paths()
    start = datetime(2026, 6, 13, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(start, end)
    raw.extend(event_discovery.load_discovery_events(
        None,
        start,
        end,
        binance_announcements_path=binance_path,
        prediction_market_events_path=prediction_path,
    ))
    assets = load_asset_aliases(aliases_path)
    supply = event_discovery.load_supply_snapshots(
        tokenomist_supply_path=tokenomist_path,
        etherscan_supply_path=etherscan_path,
        arkham_supply_path=arkham_path,
        dune_supply_path=dune_path,
    )
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        supply_by_asset=supply,
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}

    listing = by_symbol["TESTLIST"]
    assert listing.fade_candidate.supply is not None
    assert listing.fade_candidate.supply.large_holder_exchange_inflow is True
    assert listing.fade_candidate.component_scores["supply_pressure"] >= 60
    assert listing.classification.is_direct_beneficiary is True
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    pred = by_symbol["TESTPRED"]
    assert pred.fade_candidate.supply is not None
    assert pred.fade_candidate.supply.unlock_pct_circulating == 0.08
    assert pred.data_quality["has_supply_snapshot"] is True
    assert pred.fade_signal.signal_type in {FadeSignalType.NO_TRADE, FadeSignalType.WATCHLIST}

    velvet = by_symbol["TESTVELVET"]
    assert velvet.fade_candidate.supply is not None
    assert velvet.fade_candidate.supply.top_holder_concentration == 0.62
    assert velvet.fade_candidate.supply.unlock_pct_circulating is None
    assert velvet.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED


def test_event_discovery_news_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.cryptopanic import CryptoPanicProvider
    from crypto_rsi_scanner.event_providers.gdelt import GdeltProvider
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    cryptopanic = CryptoPanicProvider(cryptopanic_path, required=True).fetch_events(start, end)
    gdelt = GdeltProvider(gdelt_path, required=True).fetch_events(start, end)
    blog = ProjectBlogRssProvider(blog_path, required=True).fetch_events(start, end)
    assert len(cryptopanic) == 2
    assert len(gdelt) == 1
    assert len(blog) == 2
    assert cryptopanic[0].provider == "cryptopanic"
    assert cryptopanic[0].raw_json["event"]["event_type"] == "ipo_proxy"
    assert gdelt[0].provider == "gdelt"
    assert gdelt[0].raw_json["event"]["event_type"] == "sports_event"
    assert blog[0].provider == "project_blog_rss"
    assert blog[0].raw_json["event"]["event_id"] == "testlate-anthropic-demo"

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_news.json"
        bad_path.write_text(json.dumps({"results": ["not an object"]}), encoding="utf-8")
        assert CryptoPanicProvider(bad_path).fetch_events(start, end) == []
        try:
            CryptoPanicProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed news fixture should fail")


def test_event_discovery_cryptopanic_live_provider_parses_posts_offline():
    import json
    from datetime import datetime, timezone
    from urllib.parse import parse_qs, urlparse
    from crypto_rsi_scanner.event_providers.cryptopanic import CryptoPanicProvider

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
        return FakeResponse({
            "results": [
                {
                    "id": "cp-testai-openai-preipo",
                    "title": "TESTAI offers synthetic exposure to OpenAI pre IPO event",
                    "published_at": "2026-06-15T10:15:00Z",
                    "url": "https://example.test/cryptopanic/testai-openai",
                    "source": {"domain": "example.test"},
                    "currencies": [{"code": "TESTAI", "title": "Test AI"}],
                },
            ],
        })

    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    fetched_at = datetime(2026, 6, 15, 10, 20, tzinfo=timezone.utc)
    provider = CryptoPanicProvider(
        None,
        live_enabled=True,
        api_token="token123",
        base_url="https://cryptopanic.test/api/v1/posts/",
        public=True,
        filter_name="hot",
        currencies="BTC,ETH",
        regions="en",
        kind="news",
        search="pre-ipo",
        timeout=2.5,
        opener=fake_opener,
        fetched_at=fetched_at,
    )
    events = provider.fetch_events(start, end)
    assert len(events) == 1
    parsed = urlparse(seen["url"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "cryptopanic.test"
    assert params["auth_token"] == ["token123"]
    assert params["public"] == ["true"]
    assert params["filter"] == ["hot"]
    assert params["currencies"] == ["BTC,ETH"]
    assert params["regions"] == ["en"]
    assert params["kind"] == ["news"]
    assert params["search"] == ["pre-ipo"]
    assert seen["timeout"] == 2.5
    assert seen["accept"] == "application/json"
    event = events[0]
    assert event.provider == "cryptopanic"
    assert event.source_url == "https://example.test/cryptopanic/testai-openai"
    assert event.published_at.isoformat() == "2026-06-15T10:15:00+00:00"
    assert event.fetched_at == fetched_at
    assert event.raw_json["event"]["event_type"] == "ipo_proxy"
    assert event.raw_json["currencies"][0]["code"] == "TESTAI"

    assert CryptoPanicProvider(None, live_enabled=True, api_token="").fetch_events(start, end) == []
    try:
        CryptoPanicProvider(None, live_enabled=True, api_token="", required=True).fetch_events(start, end)
    except ValueError:
        pass
    else:
        raise AssertionError("required missing CryptoPanic token should fail")

    def failing_opener(request, timeout):
        raise TimeoutError("offline timeout")

    assert CryptoPanicProvider(
        None,
        live_enabled=True,
        api_token="token123",
        opener=failing_opener,
    ).fetch_events(start, end) == []


def test_event_discovery_gdelt_live_provider_parses_article_list_offline():
    import json
    from datetime import datetime, timezone
    from urllib.parse import parse_qs, urlparse
    from crypto_rsi_scanner.event_providers.gdelt import GdeltProvider

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
        return FakeResponse({
            "articles": [
                {
                    "url": "https://example.test/news/testai-openai-preipo",
                    "title": "TESTAI offers synthetic exposure to OpenAI pre IPO event",
                    "seendate": "20260615143000",
                    "domain": "example.test",
                    "language": "English",
                    "sourceCountry": "US",
                },
            ],
        })

    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    fetched_at = datetime(2026, 6, 15, 14, 45, tzinfo=timezone.utc)
    provider = GdeltProvider(
        None,
        live_enabled=True,
        base_url="https://api.gdelt.test/api/v2/doc/doc",
        query='("pre-ipo" OR "synthetic exposure")',
        max_records=7,
        timeout=3.5,
        opener=fake_opener,
        fetched_at=fetched_at,
    )
    events = provider.fetch_events(start, end)
    assert len(events) == 1
    parsed = urlparse(seen["url"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "api.gdelt.test"
    assert params["query"] == ['("pre-ipo" OR "synthetic exposure")']
    assert params["mode"] == ["artlist"]
    assert params["format"] == ["json"]
    assert params["maxrecords"] == ["7"]
    assert params["sort"] == ["datedesc"]
    assert params["startdatetime"] == ["20260615000000"]
    assert params["enddatetime"] == ["20260616000000"]
    assert seen["timeout"] == 3.5
    event = events[0]
    assert event.provider == "gdelt"
    assert event.source_url == "https://example.test/news/testai-openai-preipo"
    assert event.published_at.isoformat() == "2026-06-15T14:30:00+00:00"
    assert event.fetched_at == fetched_at
    assert event.raw_json["event"]["event_type"] == "ipo_proxy"

    def empty_opener(request, timeout):
        return FakeResponse({"articles": []})

    assert GdeltProvider(None, live_enabled=True, opener=empty_opener).fetch_events(start, end) == []

    def failing_opener(request, timeout):
        raise TimeoutError("offline timeout")

    assert GdeltProvider(None, live_enabled=True, opener=failing_opener).fetch_events(start, end) == []


def test_event_discovery_project_blog_live_rss_provider_parses_feeds_offline():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    class FakeResponse:
        status = 200

        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self.body.encode("utf-8")

    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TESTRSS Blog</title>
    <item>
      <guid>testrss-openai-preipo</guid>
      <title>TESTRSS offers synthetic exposure to OpenAI pre IPO event by June 20, 2026</title>
      <description>The project blog describes synthetic exposure to OpenAI.</description>
      <link>https://example.test/blog/testrss-openai</link>
      <pubDate>Tue, 16 Jun 2026 12:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
    atom = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>TESTATOM Updates</title>
  <entry>
    <id>tag:example.test,2026:testatom</id>
    <title>TESTATOM fan token rallies before Test FC World Cup match kickoff</title>
    <summary>The fan token is a proxy attention trade for the dated match fixture.</summary>
    <link rel="alternate" href="https://example.test/blog/testatom-world-cup" />
    <published>2026-06-16T13:30:00Z</published>
  </entry>
</feed>
"""
    seen = []

    def fake_opener(request, timeout):
        seen.append((request.full_url, timeout, request.headers.get("Accept")))
        if request.full_url.endswith("/rss"):
            return FakeResponse(rss)
        if request.full_url.endswith("/atom"):
            return FakeResponse(atom)
        return FakeResponse("<rss><channel /></rss>")

    start = datetime(2026, 6, 16, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    fetched_at = datetime(2026, 6, 16, 14, 0, tzinfo=timezone.utc)
    provider = ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://example.test/rss", "https://example.test/atom"),
        timeout=4.0,
        opener=fake_opener,
        fetched_at=fetched_at,
    )
    events = provider.fetch_events(start, end)
    assert len(events) == 2
    assert [url for url, _timeout, _accept in seen] == ["https://example.test/rss", "https://example.test/atom"]
    assert all(timeout == 4.0 for _url, timeout, _accept in seen)
    assert all("application/rss+xml" in accept for _url, _timeout, accept in seen)
    by_title = {event.title: event for event in events}
    rss_event = by_title["TESTRSS offers synthetic exposure to OpenAI pre IPO event by June 20, 2026"]
    assert rss_event.provider == "project_blog_rss"
    assert rss_event.source_url == "https://example.test/blog/testrss-openai"
    assert rss_event.published_at.isoformat() == "2026-06-16T12:30:00+00:00"
    assert rss_event.fetched_at == fetched_at
    assert rss_event.raw_json["event"]["event_type"] == "ipo_proxy"
    assert rss_event.raw_json["event"]["event_time"] == "2026-06-20T00:00:00+00:00"
    assert rss_event.raw_json["event"]["event_time_confidence"] == 0.60
    assert rss_event.raw_json["event"]["event_time_source"] == "text_date"
    atom_event = by_title["TESTATOM fan token rallies before Test FC World Cup match kickoff"]
    assert atom_event.source_url == "https://example.test/blog/testatom-world-cup"
    assert atom_event.published_at.isoformat() == "2026-06-16T13:30:00+00:00"
    assert atom_event.raw_json["event"]["event_type"] == "sports_event"

    def failing_opener(request, timeout):
        raise TimeoutError("offline timeout")

    assert ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://example.test/rss",),
        opener=failing_opener,
    ).fetch_events(start, end) == []


def test_event_discovery_news_external_asset_inference_handles_generic_ipo_entities():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_providers._news_common import news_events_from_items

    start = datetime(2026, 6, 16, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    rows = [
        {
            "id": "mercury-exposure",
            "title": "TESTMERC offers synthetic exposure to Mercury before IPO on June 20, 2026",
            "description": "The token is being used as a temporary proxy for Mercury pre-IPO demand.",
            "url": "https://example.test/mercury-preipo",
            "published_at": "2026-06-16T12:00:00Z",
        },
        {
            "id": "cerebras-ipo-market",
            "title": "Will Cerebras IPO before July 31?",
            "description": "Prediction markets and crypto traders are watching the Cerebras public debut.",
            "url": "https://example.test/cerebras-ipo",
            "published_at": "2026-06-16T13:00:00Z",
        },
        {
            "id": "team-match",
            "title": "USA vs Paraguay match attracts fan token traders",
            "description": "The match fixture is a dated external sports catalyst.",
            "url": "https://example.test/usa-paraguay",
            "published_at": "2026-06-16T14:00:00Z",
        },
        {
            "id": "preipo-market-shutdown",
            "title": "Hyperliquid-Based Ventuals Winds Down On-Chain Pre-IPO Markets",
            "description": "The article is about a venue shutting down generic pre-IPO markets, not a named external IPO catalyst.",
            "url": "https://example.test/ventuals-shutdown",
            "published_at": "2026-06-16T15:00:00Z",
        },
    ]

    events = news_events_from_items(rows, provider="project_blog_rss", start=start, end=end)
    by_id = {event.raw_id: event for event in events}
    assert by_id["project_blog_rss:mercury-exposure"].raw_json["event"]["external_asset"] == "Mercury"
    assert by_id["project_blog_rss:mercury-exposure"].raw_json["event"]["event_type"] == "ipo_proxy"
    assert by_id["project_blog_rss:mercury-exposure"].raw_json["event"]["event_time"] == "2026-06-20T00:00:00+00:00"
    assert by_id["project_blog_rss:cerebras-ipo-market"].raw_json["event"]["external_asset"] == "Cerebras"
    assert by_id["project_blog_rss:cerebras-ipo-market"].raw_json["event"]["event_type"] == "ipo_proxy"
    assert by_id["project_blog_rss:team-match"].raw_json["event"]["external_asset"] == "USA vs Paraguay"
    assert by_id["project_blog_rss:team-match"].raw_json["event"]["event_type"] == "sports_event"
    assert by_id["project_blog_rss:preipo-market-shutdown"].raw_json["event"]["external_asset"] is None
    assert by_id["project_blog_rss:preipo-market-shutdown"].raw_json["event"]["event_type"] == "ipo_proxy"


def test_event_discovery_proxy_article_with_text_date_becomes_dated_review_candidate():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_models import DiscoveredAsset
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <guid>hype-spacex-dated-preipo</guid>
      <title>Hyperliquid's HYPE token rallies as pre-IPO perpetual market for SpaceX launches by June 20, 2026</title>
      <description>Trade.xyz launches synthetic exposure to SpaceX through crypto derivatives.</description>
      <link>https://example.test/hype-spacex-dated-preipo</link>
      <pubDate>Tue, 16 Jun 2026 12:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""".encode("utf-8")

    start = datetime(2026, 6, 16, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://example.test/rss",),
        opener=lambda _request, _timeout: FakeResponse(),
        fetched_at=datetime(2026, 6, 16, 13, 0, tzinfo=timezone.utc),
    ).fetch_events(start, end)
    assert raw[0].raw_json["event"]["event_time"] == "2026-06-20T00:00:00+00:00"
    assert raw[0].raw_json["event"]["event_time_confidence"] == 0.60
    assert raw[0].raw_json["event"]["event_time_source"] == "text_date"

    result = event_discovery.run_discovery(
        raw,
        [
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
            )
        ],
        now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
    )

    candidate = result.candidates[0]
    assert candidate.event.event_time.isoformat() == "2026-06-20T00:00:00+00:00"
    assert candidate.event.event_time_source == "text_date"
    assert candidate.data_quality["has_event_time"] is True
    assert candidate.classification.is_proxy_narrative is True
    assert candidate.classification.relationship_type == "proxy_exposure"
    assert candidate.classification.asset_role == "proxy_instrument"
    assert candidate.fade_candidate.event.confidence == 0.60
    assert candidate.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert candidate.data_quality["event_time_confidence_pass"] is False
    assert candidate.data_quality["forced_no_trade_reason"] == "low_event_time_confidence"
    assert "event time confidence below discovery trigger threshold; review-only" in candidate.fade_signal.warnings

    rows = event_discovery.event_fade_validation_sample_rows(result)
    assert rows[0]["event_time_source"] == "text_date"
    assert rows[0]["event_time_confidence"] == 0.60


def test_event_discovery_explicit_event_time_can_trigger_but_text_date_is_review_only():
    import copy
    from dataclasses import replace
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider, content_hash
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(aliases_path)
    explicit = event_discovery.run_discovery(
        [raw[0]],
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    ).candidates[0]
    assert explicit.event.event_time_source == "explicit"
    assert explicit.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED
    assert explicit.data_quality["forced_no_trade_reason"] is None

    payload = copy.deepcopy(raw[0].raw_json)
    payload["event"]["event_time_confidence"] = 0.60
    payload["event"]["event_time_source"] = "text_date"
    text_date_raw = replace(
        raw[0],
        raw_id="velvet-text-date-low-confidence",
        raw_json=payload,
        content_hash=content_hash(payload),
    )
    text_date = event_discovery.run_discovery(
        [text_date_raw],
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    ).candidates[0]
    assert text_date.event.event_time_source == "text_date"
    assert text_date.fade_signal.fade_score >= 80
    assert text_date.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert text_date.data_quality["forced_no_trade_reason"] == "low_event_time_confidence"


def test_event_discovery_forces_no_trade_on_low_classifier_confidence():
    from dataclasses import replace
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(aliases_path)
    original_classifier = event_discovery.classify_event_asset

    def low_confidence_classifier(event, asset, link):
        classification = original_classifier(event, asset, link)
        if asset.coin_id == "testvelvet":
            return replace(classification, confidence=0.79)
        return classification

    event_discovery.classify_event_asset = low_confidence_classifier
    try:
        candidate = event_discovery.run_discovery(
            [raw[0]],
            assets,
            now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        ).candidates[0]
    finally:
        event_discovery.classify_event_asset = original_classifier

    assert candidate.fade_signal.fade_score >= 80
    assert candidate.data_quality["has_technical_snapshot"] is True
    assert candidate.data_quality["classifier_pass"] is False
    assert candidate.data_quality["forced_no_trade_reason"] == "low_classifier_confidence"
    assert candidate.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert "classifier confidence below discovery trigger threshold; review-only" in candidate.fade_signal.warnings


def test_event_discovery_proxy_article_without_event_time_stays_reviewable_no_trade():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_models import DiscoveredAsset
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <guid>hype-spacex-preipo</guid>
      <title>Hyperliquid's HYPE token rallies as pre-IPO perpetual market for SpaceX launches</title>
      <description>Trade.xyz launches synthetic exposure to SpaceX through crypto derivatives.</description>
      <link>https://example.test/hype-spacex-preipo</link>
      <pubDate>Tue, 16 Jun 2026 12:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""".encode("utf-8")

    start = datetime(2026, 6, 16, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://example.test/rss",),
        opener=lambda _request, _timeout: FakeResponse(),
        fetched_at=datetime(2026, 6, 16, 13, 0, tzinfo=timezone.utc),
    ).fetch_events(start, end)
    assert raw[0].raw_json["event"]["event_type"] == "ipo_proxy"
    assert raw[0].raw_json["event"]["external_asset"] == "SpaceX"
    assert raw[0].raw_json["event"]["event_time"] is None

    result = event_discovery.run_discovery(
        raw,
        [
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
            )
        ],
        now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
    )

    candidate = result.candidates[0]
    assert candidate.classification.is_proxy_narrative is True
    assert candidate.classification.relationship_type == "proxy_attention"
    assert candidate.classification.asset_role == "proxy_instrument"
    assert candidate.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert "not an eligible proxy event-fade candidate" in candidate.fade_signal.warnings


def test_event_discovery_asset_role_demotes_proxy_context_noise():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent
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

    ticker_word = by_event_asset[("spacex-hype-common-word", "hyperliquid")]
    assert ticker_word.classification.relationship_type == "proxy_context"
    assert ticker_word.classification.asset_role == "ticker_word_collision"
    assert ticker_word.classification.is_proxy_narrative is False

    sol = by_event_asset[("spacex-on-solana", "solana")]
    assert sol.classification.relationship_type == "proxy_context"
    assert sol.classification.asset_role == "infrastructure"
    assert sol.classification.is_proxy_narrative is False


def test_event_discovery_news_pipeline_proxy_direct_late_and_ambiguous_safety():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

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
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

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


def test_event_discovery_pipeline_and_event_fade_safety():
    from crypto_rsi_scanner import event_discovery
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


def test_event_discovery_cache_writes_point_in_time_jsonl_artifacts():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_cache

    result = _full_event_discovery_fixture_result()
    observed_at = datetime(2026, 6, 16, 12, 30, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / "event_fade_cache"
        write = event_cache.write_event_discovery_cache(
            result,
            cache_dir,
            observed_at=observed_at,
            diagnostics={"refresh_warnings": [], "provider_status": {"ready_for_configured_review_cycle": True}},
        )
        assert write.raw_events_written == len(result.raw_events)
        assert write.normalized_events_written == len(result.normalized_events)
        assert write.event_asset_links_written == len(result.links)
        assert write.classifications_written == len(result.classifications)
        assert write.candidate_snapshots_written == len(result.candidates)
        assert write.runs_written == 1
        assert write.diagnostics["provider_status"]["ready_for_configured_review_cycle"] is True

        expected_files = {
            "raw_events.jsonl",
            "normalized_events.jsonl",
            "event_asset_links.jsonl",
            "classifications.jsonl",
            "candidate_snapshots.jsonl",
            "discovery_runs.jsonl",
        }
        assert expected_files == {path.name for path in cache_dir.iterdir()}

        raw_rows = [
            json.loads(line)
            for line in (cache_dir / "raw_events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert raw_rows[0]["schema_version"] == event_cache.CACHE_SCHEMA_VERSION
        assert raw_rows[0]["row_type"] == "raw_event"
        assert raw_rows[0]["observed_at"] == "2026-06-16T12:30:00+00:00"
        assert raw_rows[0]["run_id"] == write.run_id
        assert raw_rows[0]["fetched_at"].endswith("+00:00")

        run_rows = [
            json.loads(line)
            for line in (cache_dir / "discovery_runs.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert run_rows[0]["diagnostics"]["refresh_warnings"] == []
        assert run_rows[0]["diagnostics"]["provider_status"]["ready_for_configured_review_cycle"] is True

        snapshot_rows = [
            json.loads(line)
            for line in (cache_dir / "candidate_snapshots.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        velvet = next(row for row in snapshot_rows if row["asset_symbol"] == "TESTVELVET")
        assert velvet["row_type"] == "candidate_snapshot"
        assert velvet["schema_version"] == event_cache.CACHE_SCHEMA_VERSION
        assert velvet["exported_at"] == "2026-06-16T12:30:00+00:00"
        assert velvet["signal_type"] == "SHORT_TRIGGERED"
        assert velvet["first_seen_at"] == "2026-06-16T12:30:00+00:00"
        assert velvet["last_seen_at"] == "2026-06-16T12:30:00+00:00"
        assert velvet["first_watchlisted_at"] == "2026-06-16T12:30:00+00:00"
        assert velvet["first_armed_at"] == "2026-06-16T12:30:00+00:00"
        assert velvet["first_triggered_at"] == "2026-06-16T12:00:00+00:00"

        later_observed_at = datetime(2026, 6, 16, 12, 31, tzinfo=timezone.utc)
        second = event_cache.write_event_discovery_cache(result, cache_dir, observed_at=later_observed_at)
        assert second.raw_events_written == 0
        assert second.normalized_events_written == 0
        assert second.event_asset_links_written == 0
        assert second.classifications_written == 0
        assert second.candidate_snapshots_written == len(result.candidates)

        recent_runs = event_cache.load_discovery_runs(cache_dir, limit=1)
        assert recent_runs.cache_dir == cache_dir
        assert recent_runs.runs_read == 2
        assert recent_runs.limit == 1
        assert len(recent_runs.rows) == 1
        assert recent_runs.rows[0]["run_id"] == second.run_id

        all_snapshots = event_cache.load_cached_validation_sample(cache_dir, latest_per_identity=False)
        assert all_snapshots.snapshots_read == len(result.candidates) * 2
        assert len(all_snapshots.rows) == len(result.candidates) * 2

        latest = event_cache.load_cached_validation_sample(cache_dir)
        assert latest.cache_dir == cache_dir
        assert latest.latest_per_identity is True
        assert latest.snapshots_read == len(result.candidates) * 2
        assert len(latest.rows) == len(result.candidates)
        latest_velvet = next(row for row in latest.rows if row["asset_symbol"] == "TESTVELVET")
        assert latest_velvet["schema_version"] == "event_fade_validation_sample_v1"
        assert latest_velvet["row_type"] == "candidate"
        assert latest_velvet["exported_at"] == "2026-06-16T12:31:00+00:00"
        assert "payload_schema_version" not in latest_velvet
        assert latest_velvet["signal_type"] == "SHORT_TRIGGERED"
        assert latest_velvet["first_seen_at"] == "2026-06-16T12:30:00+00:00"
        assert latest_velvet["last_seen_at"] == "2026-06-16T12:31:00+00:00"
        assert latest_velvet["first_watchlisted_at"] == "2026-06-16T12:30:00+00:00"
        assert latest_velvet["first_armed_at"] == "2026-06-16T12:30:00+00:00"
        assert latest_velvet["first_triggered_at"] == "2026-06-16T12:00:00+00:00"


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


def test_event_fade_validation_outcome_fill_from_local_prices():
    from crypto_rsi_scanner import event_discovery, event_validation

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


def test_event_fade_outcome_price_export_from_klines_fixture():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, event_price_history, event_validation

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
    from crypto_rsi_scanner import event_discovery, event_validation

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


def test_event_fade_validation_labeling_queue_flags_reviewed_trigger_outcomes():
    from crypto_rsi_scanner import event_discovery, event_validation

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


def test_event_discovery_scanner_report_uses_local_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    events_path, aliases_path = _event_discovery_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    orig_lookback = config.EVENT_DISCOVERY_LOOKBACK_HOURS
    orig_horizon = config.EVENT_DISCOVERY_HORIZON_DAYS
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
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "EVENT DISCOVERY REPORT" in text
        assert "TESTVELVET" in text
        assert "TESTBTC" in text
        assert "no alerts, DB writes, or trades" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe
        config.EVENT_DISCOVERY_LOOKBACK_HOURS = orig_lookback
        config.EVENT_DISCOVERY_HORIZON_DAYS = orig_horizon


def test_event_discovery_refresh_scanner_writes_cache_fixture():
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
        config.EVENT_DISCOVERY_CACHE_DIR = Path(tmp) / "cache"
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_discovery_refresh()
            text = out.getvalue()
            assert "Event-discovery cache refresh" in text
            assert "candidate_snapshots=17" in text
            raw_path = config.EVENT_DISCOVERY_CACHE_DIR / "raw_events.jsonl"
            run_path = config.EVENT_DISCOVERY_CACHE_DIR / "discovery_runs.jsonl"
            assert raw_path.exists()
            assert run_path.exists()
            run = json.loads(run_path.read_text(encoding="utf-8").splitlines()[0])
            assert run["row_type"] == "discovery_run"
            assert run["candidate_snapshots"] == 17
            assert run["diagnostics"]["refresh_warnings"] == []
            assert run["diagnostics"]["provider_status"]["ready_for_configured_review_cycle"] is True
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_event_discovery_refresh_scanner_warns_and_caches_zero_output_diagnostics():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    from crypto_rsi_scanner.event_models import EventDiscoveryResult

    attrs = (
        "EVENT_DISCOVERY_EVENTS_PATH",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE",
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH",
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE",
        "EVENT_DISCOVERY_COINMARKETCAL_PATH",
        "EVENT_DISCOVERY_TOKENOMIST_PATH",
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH",
        "EVENT_DISCOVERY_CRYPTOPANIC_LIVE",
        "EVENT_DISCOVERY_GDELT_PATH",
        "EVENT_DISCOVERY_GDELT_LIVE",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS",
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH",
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH",
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH",
        "EVENT_DISCOVERY_CACHE_DIR",
    )
    original = {name: getattr(config, name) for name in attrs}
    original_result_from_config = scanner._event_discovery_result_from_config
    with tempfile.TemporaryDirectory() as tmp:
        try:
            for name in attrs:
                if name == "EVENT_DISCOVERY_CACHE_DIR":
                    setattr(config, name, Path(tmp) / "cache")
                elif name == "EVENT_DISCOVERY_GDELT_LIVE":
                    setattr(config, name, True)
                elif name == "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS":
                    setattr(config, name, ())
                elif name.endswith("_LIVE"):
                    setattr(config, name, False)
                else:
                    setattr(config, name, None)
            scanner._event_discovery_result_from_config = lambda: EventDiscoveryResult(
                raw_events=(),
                normalized_events=(),
                links=(),
                classifications=(),
                candidates=(),
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_discovery_refresh()
            text = out.getvalue()
            assert "Event-discovery cache refresh" in text
            assert "WARNING: no_raw_events_collected" in text
            run_path = config.EVENT_DISCOVERY_CACHE_DIR / "discovery_runs.jsonl"
            run = json.loads(run_path.read_text(encoding="utf-8").splitlines()[0])
            assert run["raw_events"] == 0
            assert run["candidate_snapshots"] == 0
            assert run["diagnostics"]["provider_status"]["ready_for_configured_review_cycle"] is True
            assert run["diagnostics"]["provider_status"]["ready_event_source_count"] == 1
            assert run["diagnostics"]["refresh_warnings"][0].startswith("no_raw_events_collected")
        finally:
            scanner._event_discovery_result_from_config = original_result_from_config
            for name, value in original.items():
                setattr(config, name, value)


def test_event_discovery_runs_scanner_reports_recent_diagnostics():
    import contextlib
    import io
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import config, event_cache, scanner
    from crypto_rsi_scanner.event_models import EventDiscoveryResult

    original_cache_dir = config.EVENT_DISCOVERY_CACHE_DIR
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / "cache"
        config.EVENT_DISCOVERY_CACHE_DIR = cache_dir
        try:
            event_cache.write_event_discovery_cache(
                EventDiscoveryResult(raw_events=(), normalized_events=(), links=(), classifications=(), candidates=()),
                cache_dir,
                observed_at=datetime(2026, 6, 16, 12, 30, tzinfo=timezone.utc),
                diagnostics={
                    "provider_status": {
                        "ready_for_configured_review_cycle": True,
                        "ready_event_source_count": 1,
                    },
                    "refresh_warnings": ["no_raw_events_collected: provider returned no rows"],
                },
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_discovery_runs(limit=5)
            text = out.getvalue()
            assert "EVENT DISCOVERY CACHE RUNS" in text
            assert "Runs shown: 1/1" in text
            assert "ready_sources=1" in text
            assert "warnings=1" in text
            assert "no_raw_events_collected" in text

            json_out = io.StringIO()
            with contextlib.redirect_stdout(json_out):
                scanner.event_discovery_runs(limit=5, json_output=True)
            payload = json.loads(json_out.getvalue())
            assert payload["runs_read"] == 1
            assert payload["rows"][0]["diagnostics"]["refresh_warnings"][0].startswith("no_raw_events_collected")
        finally:
            config.EVENT_DISCOVERY_CACHE_DIR = original_cache_dir


def test_event_discovery_binance_listen_scanner_writes_raw_cache():
    import contextlib
    import io
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent
    from crypto_rsi_scanner.event_providers.manual_json import content_hash

    payload = {
        "catalogId": 48,
        "catalogName": "New Cryptocurrency Listing",
        "publishDate": 1781514000000,
        "title": "Binance Will List Test Live (TLIVE)",
        "body": "Binance will list Test Live and open spot trading for TLIVE/USDT.",
    }
    event = RawDiscoveredEvent(
        raw_id="binance_announcements:test-live",
        provider="binance_announcements",
        fetched_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
        source_url=None,
        title="Binance Will List Test Live (TLIVE)",
        body="Binance will list Test Live and open spot trading for TLIVE/USDT.",
        raw_json=payload,
        source_confidence=0.85,
        content_hash=content_hash(payload),
    )
    seen = {}

    class FakeProvider:
        def __init__(self, path, **kwargs):
            seen["path"] = path
            seen["kwargs"] = kwargs

        def fetch_events(self, start, end):
            seen["start"] = start
            seen["end"] = end
            return [event]

    attrs = (
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_WS_URL",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_TOPIC",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_RECV_WINDOW_MS",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_MAX_MESSAGES",
        "EVENT_DISCOVERY_LOOKBACK_HOURS",
        "EVENT_DISCOVERY_HORIZON_DAYS",
        "EVENT_DISCOVERY_CACHE_DIR",
    )
    original = {name: getattr(config, name) for name in attrs}
    original_provider = scanner.BinanceAnnouncementProvider
    with tempfile.TemporaryDirectory() as tmp:
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE = True
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY = "key"
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET = "secret"
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_WS_URL = "wss://example.test/sapi/wss"
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_TOPIC = "com_announcement_en"
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_RECV_WINDOW_MS = 30000
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LISTEN_SECONDS = 1
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_MAX_MESSAGES = 2
        config.EVENT_DISCOVERY_LOOKBACK_HOURS = 24
        config.EVENT_DISCOVERY_HORIZON_DAYS = 1
        config.EVENT_DISCOVERY_CACHE_DIR = Path(tmp) / "cache"
        scanner.BinanceAnnouncementProvider = FakeProvider
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_discovery_binance_listen()
            text = out.getvalue()
            assert "Binance announcement cache listen" in text
            assert "seen=1" in text
            assert "raw=1" in text
            assert seen["path"] is None
            assert seen["kwargs"]["live_enabled"] is True
            assert seen["kwargs"]["api_key"] == "key"
            raw_path = config.EVENT_DISCOVERY_CACHE_DIR / "raw_events.jsonl"
            run_path = config.EVENT_DISCOVERY_CACHE_DIR / "discovery_runs.jsonl"
            raw = json.loads(raw_path.read_text(encoding="utf-8").splitlines()[0])
            run = json.loads(run_path.read_text(encoding="utf-8").splitlines()[0])
            assert raw["row_type"] == "raw_event"
            assert raw["provider"] == "binance_announcements"
            assert raw["title"] == "Binance Will List Test Live (TLIVE)"
            assert run["row_type"] == "discovery_run"
            assert run["raw_events"] == 1
            assert run["candidate_snapshots"] == 0
        finally:
            scanner.BinanceAnnouncementProvider = original_provider
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
                scanner.event_discovery_refresh()
                scanner.event_discovery_refresh()
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
            scanner.event_fade_auto_report()
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
                scanner.event_fade_export_sample(str(out_path))
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


def test_event_fade_review_bundle_scanner_merges_prior_reviewed_sample():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, scanner

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
                scanner.event_fade_cache_review_bundle(str(bundle_dir), limit=5)
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


def test_event_fade_fill_outcomes_scanner_writes_outcome_jsonl():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, scanner

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
    from crypto_rsi_scanner import event_discovery, scanner

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
    from crypto_rsi_scanner import event_discovery, event_price_history, event_validation

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


def test_event_discovery_scanner_report_accepts_exchange_only_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = binance_path
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = bybit_path
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
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "TESTLIST" in text
        assert "TESTPERP" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_derivatives_fixture():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    derivatives_path = _derivatives_fixture_path()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = binance_path
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = bybit_path
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = derivatives_path
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "TESTLIST" in text
        assert "TESTPERP" in text
        assert "deriv=yes" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_supply_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, _bybit_path = _exchange_announcement_fixture_paths()
    tokenomist_path, etherscan_path, arkham_path, dune_path = _supply_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_tokenomist_supply = config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH
    orig_etherscan_supply = config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH
    orig_arkham_supply = config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH
    orig_dune_supply = config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = binance_path
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
    config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH = tokenomist_path
    config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH = etherscan_path
    config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH = arkham_path
    config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH = dune_path
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "TESTLIST" in text
        assert "supply=yes" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH = orig_tokenomist_supply
        config.EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH = orig_etherscan_supply
        config.EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH = orig_arkham_supply
        config.EVENT_DISCOVERY_DUNE_SUPPLY_PATH = orig_dune_supply
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_news_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = cryptopanic_path
    config.EVENT_DISCOVERY_GDELT_PATH = gdelt_path
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = blog_path
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "TESTAI" in text
        assert "TESTFAN" in text
        assert "TESTLATE" in text
        assert "TESTAMBIG" in text
        assert "proxy" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_external_catalyst_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = None
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = None
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = ipo_path
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = sports_path
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = prediction_path
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "SpaceX IPO calendar placeholder" in text
        assert "TESTFAN" in text
        assert "TESTPRED" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_event_discovery_scanner_report_accepts_structured_calendar_fixtures():
    import contextlib
    import io
    from crypto_rsi_scanner import config, scanner

    _events_path, aliases_path = _event_discovery_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    orig_events = config.EVENT_DISCOVERY_EVENTS_PATH
    orig_aliases = config.EVENT_DISCOVERY_ALIASES_PATH
    orig_binance = config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH
    orig_bybit = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    orig_coinmarketcal = config.EVENT_DISCOVERY_COINMARKETCAL_PATH
    orig_tokenomist = config.EVENT_DISCOVERY_TOKENOMIST_PATH
    orig_cryptopanic = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    orig_gdelt = config.EVENT_DISCOVERY_GDELT_PATH
    orig_blog = config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH
    orig_external_ipo = config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH
    orig_sports = config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH
    orig_prediction = config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH
    orig_derivatives = config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH
    orig_universe = config.EVENT_DISCOVERY_UNIVERSE_PATH
    config.EVENT_DISCOVERY_EVENTS_PATH = None
    config.EVENT_DISCOVERY_ALIASES_PATH = aliases_path
    config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = None
    config.EVENT_DISCOVERY_COINMARKETCAL_PATH = coinmarketcal_path
    config.EVENT_DISCOVERY_TOKENOMIST_PATH = tokenomist_path
    config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
    config.EVENT_DISCOVERY_GDELT_PATH = None
    config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = None
    config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = None
    config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = None
    config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = None
    config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = None
    config.EVENT_DISCOVERY_UNIVERSE_PATH = None
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_discovery_report()
        text = out.getvalue()
        assert "TESTCAL" in text
        assert "TESTUNLOCK" in text
        assert "NO_TRADE/DISCOVERED" in text
    finally:
        config.EVENT_DISCOVERY_EVENTS_PATH = orig_events
        config.EVENT_DISCOVERY_ALIASES_PATH = orig_aliases
        config.EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH = orig_binance
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = orig_bybit
        config.EVENT_DISCOVERY_COINMARKETCAL_PATH = orig_coinmarketcal
        config.EVENT_DISCOVERY_TOKENOMIST_PATH = orig_tokenomist
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = orig_cryptopanic
        config.EVENT_DISCOVERY_GDELT_PATH = orig_gdelt
        config.EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH = orig_blog
        config.EVENT_DISCOVERY_EXTERNAL_IPO_PATH = orig_external_ipo
        config.EVENT_DISCOVERY_SPORTS_FIXTURES_PATH = orig_sports
        config.EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH = orig_prediction
        config.EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH = orig_derivatives
        config.EVENT_DISCOVERY_UNIVERSE_PATH = orig_universe


def test_conviction_monotonic_with_severity():
    base = {"flag": "OB", "rsi_z": 0.0, "volume_ratio": 1.0}
    watch = conviction_score({**base, "severity": "WATCH"})
    alert = conviction_score({**base, "severity": "ALERT"})
    extreme = conviction_score({**base, "severity": "EXTREME"})
    assert watch < alert < extreme


def test_conviction_rewards_confluence():
    weak = conviction_score({"flag": "OB", "severity": "WATCH"})
    strong = conviction_score({
        "flag": "OB",
        "severity": "WATCH",
        "rsi_4h": 75,
        "rsi_weekly": 72,
        "volume_ratio": 2.0,
        "divergence": "bearish",
        "rsi_z": 2.5,
    })
    assert strong > weak
    assert 0 <= strong <= 100


def test_conviction_uses_edge_prior_when_setup_known():
    favorable = conviction_score({
        "flag": "OS", "severity": "WATCH", "setup_type": "dip_buy",
        "market_aligned": "favorable", "rsi_z": 0.0, "volume_ratio": 1.0,
    })
    adverse = conviction_score({
        "flag": "OS", "severity": "WATCH", "setup_type": "dip_buy",
        "market_aligned": "adverse", "rsi_z": 0.0, "volume_ratio": 1.0,
    })
    no_edge = conviction_score({
        "flag": "OS", "severity": "WATCH", "setup_type": "breakdown_risk",
        "market_aligned": "adverse", "rsi_z": 0.0, "volume_ratio": 1.0,
    })
    assert favorable > adverse > no_edge


def test_conviction_unflagged_is_zero():
    assert conviction_score({"flag": "", "severity": ""}) == 0


# --- pre-alert flag decision -------------------------------------------------

def test_decide_flag_crossed():
    assert decide_flag(72, 5, 70, 30, 5, 3) == "OB"
    assert decide_flag(25, -5, 70, 30, 5, 3) == "OS"


def test_decide_flag_pre_ob_requires_momentum():
    # within margin (67 in [65,70)) and rising fast -> PRE_OB
    assert decide_flag(67, 4, 70, 30, 5, 3) == "PRE_OB"
    # same level but not moving toward -> no flag
    assert decide_flag(67, 1, 70, 30, 5, 3) == ""


def test_decide_flag_pre_os():
    assert decide_flag(33, -4, 70, 30, 5, 3) == "PRE_OS"
    assert decide_flag(33, 0, 70, 30, 5, 3) == ""


def test_decide_flag_neutral():
    assert decide_flag(50, 1, 70, 30, 5, 3) == ""


def test_decide_flag_adaptive_threshold():
    # a coin whose effective OB is 64 flags OB at 65 even though < 70
    assert decide_flag(65, 2, 64, 30, 5, 3) == "OB"


# --- tier routing ------------------------------------------------------------

def test_classify_tier_instant_on_severity():
    assert classify_tier("OB", "EXTREME", 40) == "INSTANT"
    assert classify_tier("OB", "ALERT", 10) == "INSTANT"


def test_classify_tier_instant_on_conviction():
    assert classify_tier("OB", "WATCH", 80) == "INSTANT"


def test_classify_tier_digest_low_conviction_watch():
    assert classify_tier("OB", "WATCH", 30) == "DIGEST"


def test_classify_tier_pre_always_digest():
    assert classify_tier("PRE_OB", "APPROACHING", 99) == "DIGEST"
    assert classify_tier("PRE_OS", "APPROACHING", 99) == "DIGEST"


def test_conviction_approaching_below_watch():
    appr = conviction_score({"flag": "PRE_OB", "severity": "APPROACHING"})
    watch = conviction_score({"flag": "OB", "severity": "WATCH"})
    assert appr < watch


# --- trend regime ------------------------------------------------------------

def test_regime_unknown_when_short():
    s = pd.Series(np.arange(50, dtype=float))
    assert trend_regime(s, 50, 200, 20) == "UNKNOWN"


def test_regime_uptrend():
    # steadily rising over 260 bars: price > 200MA, 50MA > 200MA, slope up
    s = pd.Series(np.linspace(10, 110, 260))
    assert trend_regime(s, 50, 200, 20) == "UPTREND"


def test_regime_downtrend():
    s = pd.Series(np.linspace(110, 10, 260))
    assert trend_regime(s, 50, 200, 20) == "DOWNTREND"


def test_regime_range():
    # oscillating with no net drift -> neither aligned up nor down
    x = np.arange(260)
    s = pd.Series(50 + 5 * np.sin(x / 5.0))
    assert trend_regime(s, 50, 200, 20) == "RANGE"


def test_regime_note_direction_matters():
    assert regime_note("OB", "UPTREND") == "continuation"
    assert regime_note("OB", "DOWNTREND") == "reversal?"
    assert regime_note("OS", "UPTREND") == "dip?"
    assert regime_note("OS", "DOWNTREND") == "continuation"
    # pre-states map to their direction
    assert regime_note("PRE_OB", "RANGE") == "range-top"
    assert regime_note("PRE_OS", "RANGE") == "range-bottom"


def test_regime_note_empty_when_unknown_or_unflagged():
    assert regime_note("OB", "UNKNOWN") == ""
    assert regime_note("", "UPTREND") == ""


# --- setup taxonomy (split signal intent) ------------------------------------

def test_signal_registry_definitions_cover_core_setups():
    from crypto_rsi_scanner import signal_registry as reg
    assert set(reg.SETUPS) == {
        "mean_reversion", "dip_buy", "trend_continuation", "breakdown_risk",
    }
    assert reg.signal_for("OB", "UPTREND").setup_type == "trend_continuation"
    assert reg.signal_for("OS", "DOWNTREND").expected_dir == "down"
    assert reg.edge_conviction_prior("dip_buy", "favorable") > reg.edge_conviction_prior("dip_buy", "adverse")
    assert reg.edge_conviction_prior("breakdown_risk", "favorable") == reg.edge_conviction_prior("breakdown_risk", "adverse")


def test_signal_registry_loads_explicit_prior_overrides():
    import json
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import signal_registry as reg

    path = Path(tempfile.mkdtemp()) / "registry_priors.json"
    path.write_text(json.dumps({
        "schema": 1,
        "setups": {
            "dip_buy": {"edge_priors": {"favorable": 73, "neutral": 41, "adverse": 11}},
            "breakdown_risk": {"edge_priors": {"adverse": 99, "no_edge": 19}},
        },
    }))
    overrides = reg.load_prior_overrides(path, strict=True)

    assert reg.edge_conviction_prior("dip_buy", "favorable", overrides=overrides) == 73
    assert reg.edge_conviction_prior("dip_buy", "adverse", overrides=overrides) == 11
    # Context-only setups still read the no_edge prior, never an alignment key.
    assert reg.edge_conviction_prior("breakdown_risk", "adverse", overrides=overrides) == 19


def test_setup_for_mapping():
    from crypto_rsi_scanner.indicators import setup_for
    assert setup_for("OB", "UPTREND") == ("trend_continuation", "up")
    assert setup_for("OS", "UPTREND") == ("dip_buy", "up")
    assert setup_for("OS", "DOWNTREND") == ("breakdown_risk", "down")
    assert setup_for("OB", "DOWNTREND") == ("mean_reversion", "down")
    assert setup_for("OB", "RANGE") == ("mean_reversion", "down")
    assert setup_for("OS", "RANGE") == ("mean_reversion", "up")
    # pre-states collapse to their direction
    assert setup_for("PRE_OB", "UPTREND") == ("trend_continuation", "up")
    assert setup_for("PRE_OS", "DOWNTREND") == ("breakdown_risk", "down")
    # unknown / missing regime -> base mean-reversion read
    assert setup_for("OB", "UNKNOWN") == ("mean_reversion", "down")
    assert setup_for("OS", "") == ("mean_reversion", "up")
    assert setup_for("", "UPTREND") == ("", "")


def test_favorable_by_direction():
    from crypto_rsi_scanner.outcomes import favorable
    assert favorable("up", 5.0) == 1 and favorable("up", -5.0) == 0
    assert favorable("down", -5.0) == 1 and favorable("down", 5.0) == 0
    # legacy flags still accepted (base mean-reversion read)
    assert favorable("OB", -5.0) == 1
    assert favorable("OS", 5.0) == 1


def test_setup_aware_grading_flips_continuation():
    # The whole point: continuation setups are graded against their OWN
    # direction, so a correct continuation no longer counts as a failed reversion.
    from crypto_rsi_scanner.indicators import setup_for
    from crypto_rsi_scanner.outcomes import favorable
    # OS in a downtrend = breakdown_risk: price falling further CONFIRMS it
    _, exp = setup_for("OS", "DOWNTREND")
    assert favorable(exp, -8.0) == 1     # was 0 under the old OS=bounce convention
    # OB in an uptrend = trend_continuation: price rising CONFIRMS it
    _, exp = setup_for("OB", "UPTREND")
    assert favorable(exp, 6.0) == 1      # was 0 under the old OB=fade convention


def test_card_headlines_setup():
    s = _sample_signal(setup_type="dip_buy", expected_dir="up")
    out = formatting.telegram_html("instant", [s], "t")
    assert "Dip Buy" in out and "expecting upside" in out


# --- market-regime gating ----------------------------------------------------

def test_market_alignment_mapping():
    from crypto_rsi_scanner.indicators import market_alignment
    assert market_alignment("dip_buy", "UPTREND") == "favorable"
    assert market_alignment("dip_buy", "BULL") == "favorable"  # backtest label
    assert market_alignment("trend_continuation", "UPTREND") == "favorable"
    assert market_alignment("mean_reversion", "RANGE") == "favorable"
    assert market_alignment("mean_reversion", "CHOP") == "favorable"  # backtest label
    assert market_alignment("mean_reversion", "UPTREND") == "adverse"
    assert market_alignment("dip_buy", "DOWNTREND") == "adverse"
    assert market_alignment("dip_buy", "BEAR") == "adverse"  # backtest label
    assert market_alignment("trend_continuation", "RANGE") == "adverse"
    # breakdown_risk: no edge anywhere -> never favorable
    assert market_alignment("breakdown_risk", "DOWNTREND") == "adverse"
    assert market_alignment("breakdown_risk", "RANGE") == "adverse"
    # neutral cells / unknown / unflagged
    assert market_alignment("mean_reversion", "DOWNTREND") == "neutral"
    assert market_alignment("dip_buy", "UNKNOWN") == "neutral"
    assert market_alignment("", "UPTREND") == "neutral"


def test_setup_has_edge():
    from crypto_rsi_scanner.indicators import setup_has_edge
    assert setup_has_edge("mean_reversion") and setup_has_edge("dip_buy")
    assert not setup_has_edge("breakdown_risk")
    assert not setup_has_edge("")


def test_market_conviction_adjustment():
    from crypto_rsi_scanner.indicators import market_conviction_adjustment
    assert market_conviction_adjustment(50, "favorable", 12) == 62
    assert market_conviction_adjustment(50, "adverse", 12) == 38
    assert market_conviction_adjustment(50, "neutral", 12) == 50
    assert market_conviction_adjustment(95, "favorable", 12) == 100   # clamped
    assert market_conviction_adjustment(5, "adverse", 12) == 0        # clamped


def test_classify_tier_market_gating():
    from crypto_rsi_scanner.scanner import classify_tier
    # adverse setup that would normally be INSTANT (ALERT) -> held to digest
    assert classify_tier("OB", "ALERT", 80, "adverse") == "DIGEST"
    # ...unless it's an outright extreme
    assert classify_tier("OB", "EXTREME", 80, "adverse") == "INSTANT"
    # favorable / neutral unaffected; default arg preserves old behavior
    assert classify_tier("OB", "ALERT", 10, "favorable") == "INSTANT"
    assert classify_tier("OB", "WATCH", 80, "neutral") == "INSTANT"
    assert classify_tier("OB", "ALERT", 10) == "INSTANT"


def test_card_shows_market_alignment():
    s = _sample_signal(setup_type="dip_buy", expected_dir="up",
                       market_regime="UPTREND", market_aligned="favorable")
    out = formatting.telegram_html("instant", [s], "t")
    assert "Bull market" in out and "favors this setup" in out


def test_card_mutes_no_edge_setup():
    s = _sample_signal(setup_type="breakdown_risk", expected_dir="down",
                       market_regime="DOWNTREND", market_aligned="adverse")
    out = formatting.telegram_html("instant", [s], "t")
    assert "no historical edge" in out
    assert "expecting downside" not in out      # direction muted
    assert "Bear market" in out and "little edge" in out


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


def test_scanner_state_context_is_shadow_only():
    import json
    from crypto_rsi_scanner import scanner

    idx = pd.date_range("2025-01-01", periods=240, freq="D", tz="UTC")
    rng = np.random.RandomState(42)
    btc = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, len(idx)))), index=idx)
    eth = pd.Series(80 * np.exp(np.cumsum(rng.normal(0.001, 0.035, len(idx)))), index=idx)
    coin = pd.Series(20 * np.exp(np.cumsum(rng.normal(0.001, 0.05, len(idx)))), index=idx)
    vols = pd.Series(np.linspace(8_000_000, 12_000_000, len(idx)), index=idx)
    btc_vols = pd.Series(np.linspace(500_000_000, 650_000_000, len(idx)), index=idx)
    eth_vols = pd.Series(np.linspace(300_000_000, 400_000_000, len(idx)), index=idx)
    daily = {
        "bitcoin": (btc, btc_vols),
        "ethereum": (eth, eth_vols),
        "shadowcoin": (coin, vols),
    }
    market = {
        "id": "shadowcoin", "symbol": "shd", "name": "ShadowCoin",
        "current_price": float(coin.iloc[-1]), "market_cap": 300_000_000,
        "total_volume": 12_000_000, "market_cap_rank": 123,
    }
    coin_map = {
        "bitcoin": {"id": "bitcoin", "symbol": "btc", "market_cap": 1_000_000_000_000},
        "ethereum": {"id": "ethereum", "symbol": "eth", "market_cap": 500_000_000_000},
        "shadowcoin": market,
    }
    base = scanner._analyze_coin(coin, vols, None, btc, market, "UPTREND")
    ctx = scanner._build_state_context(daily, coin_map, btc, eth)
    shadow = scanner._analyze_coin(coin, vols, None, btc, market, "UPTREND", ctx)

    assert base is not None and shadow is not None
    for key in ("flag", "setup_type", "expected_dir", "market_aligned", "conviction", "tier"):
        assert shadow[key] == base[key]
    assert shadow["vol_state"] in {"unknown", "low_compressed", "normal", "high", "high_expanding", "crisis"}
    assert shadow["breadth_state"] == json.loads(shadow["state_json"])["breadth"]["state"]
    assert set(("rs_bucket", "liquidity_bucket", "falling_knife_score")).issubset(shadow)


def test_format_signal_adds_compact_state_tokens():
    from crypto_rsi_scanner import scanner

    s = _sample_signal(
        vol_state="crisis",
        breadth_state="washout",
        rs_bucket="low",
        liquidity_bucket="low",
        falling_knife_score=82,
    )
    line = scanner._format_signal(s, is_new=False)
    assert "vol-state:crisis" in line
    assert "breadth:washout" in line
    assert "RS:low" in line
    assert "liq:low" in line
    assert "knife:82" in line


def test_dry_run_csv_helper_does_not_write():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner, config

    path = Path(tempfile.mkdtemp()) / "latest.csv"
    orig = config.CSV_OUT
    config.CSV_OUT = path
    try:
        df = pd.DataFrame([{"symbol": "AAA", "sparkline": [1, 2], "state": {"x": 1}}])
        assert scanner._write_latest_csv(df, dry_run=True) is False
        assert not path.exists()
        assert scanner._write_latest_csv(df, dry_run=False) is True
        assert path.exists()
        assert "sparkline" not in path.read_text()
    finally:
        config.CSV_OUT = orig


# --- .env loader -------------------------------------------------------------

def test_dotenv_skips_empty_values():
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner.config import _load_dotenv

    env_path = Path(tempfile.mkdtemp()) / ".env"
    env_path.write_text("RSI_TEST_FILLED=hello\nRSI_TEST_EMPTY=\n# comment\n")

    for k in ("RSI_TEST_FILLED", "RSI_TEST_EMPTY"):
        os.environ.pop(k, None)
    try:
        _load_dotenv(env_path)
        # filled value is loaded; empty value is treated as unset (uses default)
        assert os.environ.get("RSI_TEST_FILLED") == "hello"
        assert "RSI_TEST_EMPTY" not in os.environ
    finally:
        os.environ.pop("RSI_TEST_FILLED", None)


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


def test_universe_filters_stable_wrapped_and_bad_quality():
    from crypto_rsi_scanner import universe
    cases = [
        (_market(id="tether", symbol="usdt", name="Tether"), "stable_like"),
        (_market(id="usd1-wlfi", symbol="usd1", name="USD1"), "stable_like"),
        (_market(id="global-dollar", symbol="usdg", name="Global Dollar"), "stable_like"),
        (_market(id="usdtb", symbol="usdtb", name="USDtb"), "stable_like"),
        (_market(id="bfusd", symbol="bfusd", name="BFUSD"), "stable_like"),
        (_market(id="apxusd", symbol="apxusd", name="apxUSD"), "stable_like"),
        (_market(id="united-stables", symbol="u", name="United Stables"), "stable_like"),
        (_market(id="gho", symbol="gho", name="GHO"), "stable_like"),
        (_market(id="ylds", symbol="ylds", name="YLDS"), "stable_like"),
        (_market(id="usx", symbol="usx", name="USX"), "stable_like"),
        (_market(id="tether-gold", symbol="xaut", name="Tether Gold"), "stable_like"),
        (_market(id="pax-gold", symbol="paxg", name="PAX Gold"), "stable_like"),
        (_market(id="wrapped-bitcoin", symbol="wbtc", name="Wrapped Bitcoin"), "excluded_symbol"),
        (_market(id="bridged-eth", symbol="beth", name="Bridged ETH"), "wrapped_staked_or_synthetic"),
        (_market(id="thin", symbol="thin", name="Thin", total_volume=10.0), "low_liquidity"),
        (_market(id="bad", symbol="bad", name="Bad", price_change_percentage_24h_in_currency=900.0), "suspicious_24h_move"),
    ]
    for market, reason in cases:
        assert universe.exclusion_reason(market) == reason


def test_universe_keeps_stacks_and_limits_clean_results():
    from crypto_rsi_scanner import universe
    markets = [
        _market(id="tether", symbol="usdt", name="Tether"),
        _market(id="blockstack", symbol="stx", name="Stacks"),
        _market(id="ethereum", symbol="eth", name="Ethereum"),
    ]
    kept, excluded = universe.filter_markets(markets, limit=1)
    assert [m["symbol"] for m in kept] == ["stx"]
    assert excluded["stable_like"] == 1


def test_universe_candidate_count_overfetches():
    from crypto_rsi_scanner import universe
    assert universe.candidate_count(20) > 20
    assert universe.candidate_count(500) <= 250


def test_universe_audit_keeps_exclusion_examples_after_limit():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import universe

    markets = [
        _market(id="blockstack", symbol="stx", name="Stacks"),
        _market(id="tether", symbol="usdt", name="Tether"),
        _market(id="thin", symbol="thin", name="Thin", total_volume=10.0),
    ]
    kept, excluded, audit = universe.filter_markets_with_audit(
        markets,
        limit=1,
        now=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )
    assert [m["symbol"] for m in kept] == ["stx"]
    assert excluded["stable_like"] == 1
    assert excluded["low_liquidity"] == 1
    assert audit["kept_count"] == 1
    assert audit["excluded_count"] == 2
    assert {x["reason"] for x in audit["excluded_examples"]} == {"stable_like", "low_liquidity"}
    assert "UNIVERSE HYGIENE AUDIT" in universe.format_audit(audit)


def test_universe_audit_flags_suspicious_kept_rows():
    from crypto_rsi_scanner import universe

    audit = {
        "kept": [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "rank": 1},
            {"id": "example-yield", "symbol": "yield", "name": "Example Yield", "rank": 99},
        ],
        "excluded_by_reason": {},
    }
    leaks = universe.suspicious_kept(audit)
    assert [x["symbol"] for x in leaks] == ["yield"]
    assert "suspicious kept" in universe.format_audit(audit)

    markets = [
        {
            "id": f"plain-{i}",
            "symbol": f"p{i}",
            "name": f"Plain {i}",
            "market_cap": 1_000_000_000,
            "total_volume": 20_000_000,
            "market_cap_rank": i + 1,
        }
        for i in range(90)
    ]
    markets.append({
        "id": "example-yield",
        "symbol": "yield",
        "name": "Example Yield",
        "market_cap": 900_000_000,
        "total_volume": 20_000_000,
        "market_cap_rank": 99,
    })
    _, _, full_audit = universe.filter_markets_with_audit(markets, limit=100)
    assert len(full_audit["kept"]) == 91
    assert universe.suspicious_kept(full_audit)[0]["symbol"] == "yield"


def test_scanner_fetch_universe_audit_uses_shared_filter():
    import asyncio
    from crypto_rsi_scanner import scanner

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get_top_markets(self, n):
            assert n >= 2
            return [
                _market(id="blockstack", symbol="stx", name="Stacks"),
                _market(id="usd1-wlfi", symbol="usd1", name="USD1"),
            ]

    orig = scanner.CoinGeckoClient
    scanner.CoinGeckoClient = FakeClient
    try:
        audit = asyncio.run(scanner.fetch_universe_audit(top_n=1))
    finally:
        scanner.CoinGeckoClient = orig

    assert audit["kept_count"] == 1
    assert audit["kept"][0]["symbol"] == "stx"
    assert audit["excluded_by_reason"] == {"stable_like": 1}


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

def test_favorable_convention():
    from crypto_rsi_scanner.outcomes import favorable
    assert favorable("OB", -5.0) == 1   # overbought + price fell = good
    assert favorable("OB", 5.0) == 0
    assert favorable("OS", 5.0) == 1    # oversold + price rose = good
    assert favorable("OS", -5.0) == 0
    assert favorable("PRE_OB", -2.0) == 1


def test_price_asof():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.outcomes import _price_asof
    idx = pd.date_range("2026-05-01", periods=10, freq="D", tz="UTC")
    closes = pd.Series(range(10), index=idx, dtype=float)
    # returns last value at/before the timestamp
    assert _price_asof(closes, datetime(2026, 5, 5, tzinfo=timezone.utc)) == 4.0
    assert _price_asof(pd.Series(dtype=float), datetime(2026, 5, 5, tzinfo=timezone.utc)) is None
    # before the series start -> None
    assert _price_asof(closes, datetime(2026, 4, 1, tzinfo=timezone.utc)) is None


def test_price_asof_mixed_time_units():
    # Regression: pandas 3 Series.asof() raises "Cannot losslessly convert
    # units" when index resolution (ms, from unit='ms' parsing) != Timestamp
    # resolution (us, from an isoformat string with microseconds).
    from datetime import datetime
    from crypto_rsi_scanner.outcomes import _price_asof
    idx = pd.to_datetime([1714521600000 + i * 86400000 for i in range(10)],
                         unit="ms", utc=True)  # ms-resolution index
    closes = pd.Series(range(10), index=idx, dtype=float)
    ts = datetime.fromisoformat("2026-05-02T07:08:23.760073+00:00")  # us-resolution
    val = _price_asof(closes, ts)  # must not raise
    assert val is not None and val >= 0


def test_outcome_evaluation_records_matured():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import outcomes

    db = Path(tempfile.mkdtemp()) / "o.db"
    st = Storage(db)
    now = datetime(2026, 5, 31, tzinfo=timezone.utc)
    run_at = now - timedelta(days=10)
    st.conn.execute(
        "INSERT INTO signals (symbol, coin_id, flag, severity, price, is_new, run_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("AAA", "aaa", "OB", "ALERT", 100.0, 1, run_at.isoformat()),
    )
    st.conn.commit()

    # price 100 at entry, then declines 1/day -> OB fade is favorable
    idx = pd.date_range(end=now, periods=16, freq="D", tz="UTC")
    vals = [100.0 if (d - pd.Timestamp(run_at)).days <= 0
            else 100.0 - (d - pd.Timestamp(run_at)).days for d in idx]
    closes = pd.Series(vals, index=idx)

    n = outcomes.evaluate_coin(st, "aaa", closes, [1, 3, 7, 14], now=now)
    assert n == 3  # 1/3/7 matured; 14d not (only 10 days elapsed)
    recs = st.conn.execute(
        "SELECT horizon_days, ret_pct, favorable FROM outcomes ORDER BY horizon_days"
    ).fetchall()
    assert [r["horizon_days"] for r in recs] == [1, 3, 7]
    assert all(r["favorable"] == 1 for r in recs)
    assert abs(recs[-1]["ret_pct"] - (-7.0)) < 1e-6  # 93/100 - 1
    # idempotent: re-running records nothing new
    assert outcomes.evaluate_coin(st, "aaa", closes, [1, 3, 7, 14], now=now) == 0
    st.close()


def test_build_report_empty_and_populated():
    from crypto_rsi_scanner.outcomes import build_report
    assert "No matured" in build_report([])

    rows = [
        {"horizon_days": 7, "ret_pct": -3.0, "favorable": 1, "flag": "OB",
         "regime": "DOWNTREND", "regime_note": "reversal?", "conviction": 80,
         "symbol": "A", "severity": "ALERT", "market_regime": "DOWNTREND",
         "market_aligned": "neutral",
         "state_json": '{"volatility":{"state":"high"},"breadth":{"state":"washout"}}'},
        {"horizon_days": 7, "ret_pct": 2.0, "favorable": 0, "flag": "OB",
         "regime": "UPTREND", "regime_note": "continuation", "conviction": 55,
         "symbol": "B", "severity": "WATCH", "market_regime": "DOWNTREND",
         "market_aligned": "favorable"},
        {"horizon_days": 7, "ret_pct": 4.0, "favorable": 1, "flag": "OS",
         "regime": "DOWNTREND", "regime_note": "continuation", "conviction": 70,
         "symbol": "C", "severity": "ALERT", "market_regime": "DOWNTREND",
         "market_aligned": "adverse"},
    ]
    out = build_report(rows, primary_horizon=7)
    assert "RSI SIGNAL OUTCOMES" in out
    assert "By setup" in out and "By conviction" in out
    assert "By actionable/control" in out
    assert "By market alignment" in out
    assert "By state cohort" in out and "washout" in out


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

def test_backtest_edge_zero_when_signal_matches_base():
    # The anti-tautology guarantee: a setup that confirms 100% in a regime that
    # *always* moves that way has ZERO edge — it's just "trends trend".
    from crypto_rsi_scanner import backtest
    regime_base = {("DOWNTREND", 1): [-5.0, -4.0, -6.0, -3.0]}  # P(down)=100%
    signals = [{"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                "h": 1, "ret": -5.0, "fav": 1, "conv": 60} for _ in range(4)]
    r = backtest.summarize(signals, regime_base)[0]
    assert r["conf"] == 100.0 and r["base"] == 100.0
    assert abs(r["edge"]) < 1e-9


def test_backtest_positive_edge_when_signal_beats_base():
    from crypto_rsi_scanner import backtest
    regime_base = {("DOWNTREND", 1): [-2.0, -1.0, 2.0, 1.0]}  # P(down)=50%, mean 0
    signals = [{"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                "h": 1, "ret": -3.0, "fav": 1, "conv": 60} for _ in range(5)]
    r = backtest.summarize(signals, regime_base)[0]
    assert r["conf"] == 100.0
    assert abs(r["base"] - 50.0) < 1e-9
    assert abs(r["edge"] - 50.0) < 1e-9
    assert r["med_excess"] > 0  # fell more than the regime's average day


def test_backtest_conditional_table_buckets_by_feature():
    # low-vol oversold-in-downtrend bounces (+ret); high-vol continues down (-ret).
    # The slice should show that, with edge measured vs same-vol-bucket base days.
    from crypto_rsi_scanner import backtest
    signals = []
    for v, r in [(0.1, +3.0)] * 10 + [(0.5, -1.0)] * 10 + [(0.9, -6.0)] * 10:
        signals.append({"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                        "h": 3, "ret": r, "fav": 1 if r < 0 else 0, "conv": 50,
                        "vol": v, "mom": -10.0})
    # base: each vol level falls ~50% of the time, regardless of vol
    cond_base = {("DOWNTREND", 3): [(v, -10.0, r)
                 for v in (0.1, 0.5, 0.9) for r in (-1.0, 1.0)] * 20}
    res = backtest.conditional_table(signals, cond_base, "breakdown_risk",
                                     "DOWNTREND", "down", 3, "vol")
    assert res is not None
    (q1, q2), rows = res
    assert rows[0]["sig"] < 20    # low vol -> rarely falls (bounces)
    assert rows[2]["sig"] > 80    # high vol -> keeps falling
    assert rows[2]["edge"] > 20   # and beats the same-vol-bucket base (~50%)


def test_backtest_market_regime_series():
    from crypto_rsi_scanner import backtest
    idx_up = pd.date_range("2020-01-01", periods=300, freq="D", tz="UTC")
    up = pd.Series(np.linspace(10, 110, 300), index=idx_up)
    down = pd.Series(np.linspace(110, 10, 300), index=idx_up)
    assert backtest.market_regime_series(up).iloc[-1] == "BULL"
    assert backtest.market_regime_series(down).iloc[-1] == "BEAR"
    assert backtest.market_regime_series(up).iloc[0] == "NA"  # 200d warm-up


def test_backtest_summarize_market_splits_regime():
    # mean_reversion confirms in BULL, fails in BEAR — must not blend away.
    from crypto_rsi_scanner import backtest
    signals = []
    for _ in range(10):
        signals.append({"setup": "mean_reversion", "exp": "up", "regime": "RANGE",
                        "mkt": "BULL", "h": 7, "ret": 5.0, "fav": 1, "conv": 50})
    for _ in range(10):
        signals.append({"setup": "mean_reversion", "exp": "up", "regime": "RANGE",
                        "mkt": "BEAR", "h": 7, "ret": -5.0, "fav": 0, "conv": 50})
    mkt_base = {("RANGE", "BULL", 7): [1.0, 1.0, -1.0, 1.0],   # base P(up)=75%
                ("RANGE", "BEAR", 7): [-1.0, -1.0, 1.0, -1.0]}  # base P(up)=25%
    by = {(r["setup"], r["mkt"]): r for r in backtest.summarize_market(signals, mkt_base, 7)}
    assert by[("mean_reversion", "BULL")]["conf"] == 100.0
    assert by[("mean_reversion", "BEAR")]["conf"] == 0.0
    assert abs(by[("mean_reversion", "BULL")]["edge"] - 25.0) < 1e-9   # 100 - 75
    assert abs(by[("mean_reversion", "BEAR")]["edge"] + 25.0) < 1e-9   # 0 - 25


def test_backtest_state_slices_compare_same_state_base():
    from crypto_rsi_scanner import backtest

    signals = []
    for _ in range(10):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "h": 7, "ret": 4.0, "fav": 1, "conv": 60,
                        "vol_state": "low_compressed", "breadth_state": "neutral",
                        "rs_bucket": "high", "liquidity_bucket": "high",
                        "knife_bucket": "low"})
    for _ in range(10):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "h": 7, "ret": -4.0, "fav": 0, "conv": 60,
                        "vol_state": "crisis", "breadth_state": "breadth_collapse",
                        "rs_bucket": "low", "liquidity_bucket": "low",
                        "knife_bucket": "high"})

    state_base = {
        ("UPTREND", "vol_state", "low_compressed", 7): [1.0, -1.0] * 20,
        ("UPTREND", "vol_state", "crisis", 7): [1.0, -1.0] * 20,
        ("UPTREND", "rs_bucket", "high", 7): [1.0, -1.0] * 20,
        ("UPTREND", "rs_bucket", "low", 7): [1.0, -1.0] * 20,
        ("UPTREND", "liquidity_bucket", "high", 7): [1.0, -1.0] * 20,
        ("UPTREND", "liquidity_bucket", "low", 7): [1.0, -1.0] * 20,
        ("UPTREND", "knife_bucket", "low", 7): [1.0, -1.0] * 20,
        ("UPTREND", "knife_bucket", "high", 7): [1.0, -1.0] * 20,
        ("UPTREND", "breadth_state", "neutral", 7): [1.0, -1.0] * 20,
        ("UPTREND", "breadth_state", "breadth_collapse", 7): [1.0, -1.0] * 20,
    }
    rows = backtest.summarize_state_slices(signals, state_base, 7, min_n=8)
    by = {(r["feature"], r["bucket"]): r for r in rows}
    assert by[("vol_state", "low_compressed")]["edge"] == 50.0
    assert by[("vol_state", "crisis")]["edge"] == -50.0
    assert by[("knife_bucket", "high")]["med_dir"] < 0
    text = backtest.format_state_slices(signals, state_base, 7, min_n=8)
    assert "State-conditioned edge slices" in text
    assert "falling-knife bucket" in text


def test_backtest_build_state_frames_contains_shadow_labels():
    from crypto_rsi_scanner import backtest

    idx = pd.date_range("2025-01-01", periods=280, freq="D", tz="UTC")
    btc = pd.DataFrame({
        "close": pd.Series(np.linspace(100, 180, len(idx)), index=idx),
        "volume": pd.Series(1_000.0, index=idx),
    })
    weak = pd.DataFrame({
        "close": pd.Series(np.linspace(80, 30, len(idx)), index=idx),
        "volume": pd.Series(np.linspace(20_000, 40_000, len(idx)), index=idx),
    })
    frames = {"BTC": btc, "WEAK": weak}
    state = backtest.build_state_frames(frames)
    assert set(state) == {"BTC", "WEAK"}
    cols = set(state["WEAK"].columns)
    assert {"vol_state", "breadth_state", "rs_bucket", "liquidity_bucket",
            "falling_knife_score", "knife_bucket"}.issubset(cols)
    assert state["WEAK"]["rs_bucket"].iloc[-1] in {"low", "mid", "high"}


def test_backtest_builds_registry_prior_calibration():
    from crypto_rsi_scanner import backtest, signal_registry as reg

    signals = []
    # Favorable dip-buy in BULL: 100% confirms vs 50% base -> prior should rise.
    for _ in range(16):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "mkt": "BULL", "h": 7, "ret": 4.0, "fav": 1, "conv": 60})
    # Adverse dip-buy in BEAR: 0% confirms vs 50% base -> prior should fall.
    for _ in range(16):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "mkt": "BEAR", "h": 7, "ret": -4.0, "fav": 0, "conv": 60})
    # Breakdown risk can have apparent edge in evidence, but it must stay context-only.
    for _ in range(16):
        signals.append({"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                        "mkt": "BEAR", "h": 7, "ret": -4.0, "fav": 1, "conv": 40})

    mkt_base = {
        ("UPTREND", "BULL", 7): [1.0, -1.0] * 20,
        ("UPTREND", "BEAR", 7): [1.0, -1.0] * 20,
        ("DOWNTREND", "BEAR", 7): [1.0, -1.0] * 20,
    }

    payload = backtest.build_registry_prior_export(
        signals, mkt_base, n_coins=3, days=365, source="unit-test", min_samples=8
    )
    priors = payload["setups"]["dip_buy"]["edge_priors"]
    defaults = reg.SETUPS["dip_buy"].edge_priors
    assert priors["favorable"] > defaults["favorable"]
    assert priors["adverse"] < defaults["adverse"]
    assert payload["setups"]["breakdown_risk"]["edge_priors"]["no_edge"] == (
        reg.SETUPS["breakdown_risk"].edge_priors["no_edge"]
    )
    assert "context_only_no_edge_not_auto_promoted" in payload["setups"]["breakdown_risk"]["notes"]


def test_backtest_cost_and_walk_forward_reports():
    from crypto_rsi_scanner import backtest

    idx = pd.date_range("2026-01-01", periods=8, freq="D", tz="UTC")
    signals = []
    for i, ts in enumerate(idx):
        setup = "dip_buy" if i % 2 == 0 else "breakdown_risk"
        exp = "up" if setup == "dip_buy" else "down"
        ret = 2.0 if setup == "dip_buy" else -1.0
        signals.append({
            "setup": setup,
            "exp": exp,
            "h": 7,
            "ret": ret,
            "fav": 1,
            "conv": 70 - i,
            "mkt": "BULL" if setup == "dip_buy" else "BEAR",
            "ts": ts,
            "symbol": f"T{i}",
            "liquidity_bucket": "low" if i == 0 else "high",
        })

    costs = backtest.format_cost_report(
        signals, fee_bps=10, slippage_bps=20, max_trades_per_day=1
    )
    assert "Cost-aware backtest book" in costs
    assert "actionable" in costs
    assert "dip_buy" in costs

    wf = backtest.format_walk_forward(signals, folds=4)
    assert "Walk-forward setup stability" in wf
    assert "Train = all earlier folds" in wf


def test_backtest_pit_membership():
    # Point-in-time top-2: a coin that's big early then shrinks should be a
    # member only while it ranks in the top-2 by mcap on each date.
    from crypto_rsi_scanner import backtest
    idx = pd.date_range("2025-01-01", periods=4, freq="D", tz="UTC")
    histories = {
        "big":   pd.DataFrame({"mcap": [100, 100, 100, 100]}, index=idx),
        "faller": pd.DataFrame({"mcap": [90, 90, 10, 10]}, index=idx),   # drops out
        "riser": pd.DataFrame({"mcap": [5, 5, 80, 80]}, index=idx),      # climbs in
    }
    member = backtest.build_pit_membership(histories, top_n=2)
    assert list(member["big"]) == [True, True, True, True]
    assert list(member["faller"]) == [True, True, False, False]
    assert list(member["riser"]) == [False, False, True, True]


def test_backtest_volume_membership_rolling_rank():
    # Membership = top-N by TRAILING mean dollar volume: needs `window` days of
    # history to enter (no lookahead), and rank flips follow the trailing mean.
    from crypto_rsi_scanner import backtest
    idx = pd.date_range("2025-01-01", periods=6, freq="D", tz="UTC")
    frames = {
        "BIG": pd.DataFrame({"quote_volume": [100.0] * 6}, index=idx),
        "FADE": pd.DataFrame({"quote_volume": [90, 90, 1, 1, 1, 1]}, index=idx),
        "RISE": pd.DataFrame({"quote_volume": [1, 1, 95, 95, 95, 95]}, index=idx),
    }
    m = backtest.build_volume_membership(frames, top_n=2, window=2)
    # day 0: trailing-2 mean undefined for everyone -> nobody is a member
    assert not m.iloc[0].any()
    assert list(m["BIG"])[1:] == [True] * 5
    # FADE trailing means: 90, 45.5, 1, 1, 1 — loses rank 2 to RISE (48) on day 2
    assert list(m["FADE"])[1:] == [True, False, False, False, False]
    # RISE trailing means: 1, 48, 95, 95, 95 — enters as soon as its ramp shows up
    assert list(m["RISE"])[1:] == [False, True, True, True, True]


def test_backtest_volume_membership_rejects_invalid_args():
    from crypto_rsi_scanner import backtest
    idx = pd.date_range("2025-01-01", periods=3, freq="D", tz="UTC")
    frames = {"AAA": pd.DataFrame({"quote_volume": [1.0, 2.0, 3.0]}, index=idx)}

    try:
        backtest.build_volume_membership(frames, top_n=0, window=2)
    except ValueError as e:
        assert "top_n" in str(e)
    else:
        raise AssertionError("top_n=0 should fail")

    try:
        backtest.build_volume_membership(frames, top_n=1, window=0)
    except ValueError as e:
        assert "window" in str(e)
    else:
        raise AssertionError("window=0 should fail")


def test_backtest_main_rejects_invalid_cli_args():
    import contextlib
    import io
    from crypto_rsi_scanner import backtest

    for argv in (
        ["--pit-volume", "--volume-window", "0"],
        ["--top-n", "0"],
        ["--compare-triggers", "--pit"],
    ):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                backtest.main(argv)
            except SystemExit as e:
                assert e.code == 2
            else:
                raise AssertionError(f"{argv} should fail")


def test_backtest_main_compare_triggers_uses_volume_pit():
    import contextlib
    import io
    from crypto_rsi_scanner import backtest

    calls = {}
    orig_pit_triggers = backtest.run_pit_volume_triggers
    orig_triggers = backtest.run_triggers
    orig_format = backtest.format_trigger_comparison

    def fake_pit_triggers(top_n, days, **kwargs):
        calls["pit"] = {
            "top_n": top_n,
            "days": days,
            "cache_dir": kwargs.get("cache_dir"),
            "refresh_cache": kwargs.get("refresh_cache"),
            "volume_window": kwargs.get("volume_window"),
        }
        return {"cross_into": ([], {}, {}, {}, {}), "confirm": ([], {}, {}, {}, {})}, 2

    def fail_default_triggers(*args, **kwargs):
        raise AssertionError("default trigger path should not run")

    def fake_format(results):
        assert set(results) == {"cross_into", "confirm"}
        return "pit-volume comparison"

    backtest.run_pit_volume_triggers = fake_pit_triggers
    backtest.run_triggers = fail_default_triggers
    backtest.format_trigger_comparison = fake_format
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            backtest.main([
                "--compare-triggers",
                "--pit-volume",
                "--top-n", "7",
                "--days", "30",
                "--volume-window", "3",
                "--no-pit-cache",
            ])
        assert "pit-volume comparison" in out.getvalue()
        assert calls["pit"] == {
            "top_n": 7,
            "days": 30,
            "cache_dir": None,
            "refresh_cache": False,
            "volume_window": 3,
        }
    finally:
        backtest.run_pit_volume_triggers = orig_pit_triggers
        backtest.run_triggers = orig_triggers
        backtest.format_trigger_comparison = orig_format


def test_backtest_fetch_volume_pit_frames_cache_hit_no_sleep_and_closes_session():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import backtest

    cache = Path(tempfile.mkdtemp())
    periods = backtest._START + max(backtest.HORIZONS) + 1
    rows = [
        [
            1735689600000 + i * 86_400_000,
            "1", "2", "0.5", str(100 + i), "10", 0, "15", 0, 0, 0, 0,
        ]
        for i in range(periods)
    ]
    for symbol in ("BTCUSDT", "ETHUSDT"):
        backtest._write_binance_klines_cache(cache, symbol, periods, rows)

    class FakeSession:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.closed = True

    fake_session = FakeSession()
    sleeps = []
    orig_session = backtest.requests.Session
    orig_pool = backtest.binance_usdt_pool
    orig_sleep = backtest.time.sleep
    backtest.requests.Session = lambda: fake_session
    backtest.binance_usdt_pool = lambda session: ["BTC", "ETH"]
    backtest.time.sleep = lambda seconds: sleeps.append(seconds)
    try:
        frames = backtest._fetch_volume_pit_frames(periods, cache_dir=cache)
        assert set(frames) == {"BTC", "ETH"}
        assert sleeps == []
        assert fake_session.closed is True
    finally:
        backtest.requests.Session = orig_session
        backtest.binance_usdt_pool = orig_pool
        backtest.time.sleep = orig_sleep


def test_backtest_filter_usdt_bases_hygiene():
    from crypto_rsi_scanner import backtest
    syms = [
        {"baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
        {"baseAsset": "JUP", "quoteAsset": "USDT", "status": "TRADING"},   # real coin, UP suffix
        {"baseAsset": "USDC", "quoteAsset": "USDT", "status": "TRADING"},  # stable
        {"baseAsset": "EUR", "quoteAsset": "USDT", "status": "TRADING"},   # fiat
        {"baseAsset": "WBTC", "quoteAsset": "USDT", "status": "TRADING"},  # wrapped
        {"baseAsset": "OLD", "quoteAsset": "USDT", "status": "BREAK"},     # not trading
        {"baseAsset": "ETH", "quoteAsset": "BTC", "status": "TRADING"},    # wrong quote
        {"baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},   # dup
    ]
    assert backtest._filter_usdt_bases(syms) == ["BTC", "JUP"]


def test_backtest_klines_rows_to_frame_quote_volume():
    from crypto_rsi_scanner import backtest
    # Binance kline array: [open_ms, open, high, low, close, base_vol, close_ms, quote_vol, ...]
    rows = [
        [1735689600000, "1", "2", "0.5", "1.5", "1000", 0, "1500.5", 0, 0, 0, 0],
        [1735776000000, "1.5", "2", "1", "1.8", "2000", 0, "3600.25", 0, 0, 0, 0],
    ]
    df = backtest._klines_rows_to_frame(rows)
    assert list(df["close"]) == [1.5, 1.8]
    assert list(df["high"]) == [2.0, 2.0]
    assert list(df["low"]) == [0.5, 1.0]
    assert list(df["volume"]) == [1000.0, 2000.0]
    assert list(df["quote_volume"]) == [1500.5, 3600.25]
    assert df.index.tz is not None


def test_backtest_binance_klines_cache_roundtrip():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import backtest
    cache = Path(tempfile.mkdtemp())
    rows = [[1735689600000, "1", "2", "0.5", "1.5", "10", 0, "15", 0, 0, 0, 0]]
    backtest._write_binance_klines_cache(cache, "AAAUSDT", 30, rows)
    # cache hit must not touch the network: session=None would fail otherwise
    df = backtest.fetch_klines("AAAUSDT", 30, session=None, cache_dir=cache)
    assert df is not None and list(df["quote_volume"]) == [15.0]
    assert list(df["high"]) == [2.0]
    assert list(df["low"]) == [0.5]
    # no cache entry + no session -> None (still no network)
    assert backtest.fetch_klines("BBBUSDT", 30, session=None, cache_dir=cache) is None


def test_backtest_pit_history_cache_roundtrip():
    import asyncio
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import backtest

    idx = pd.date_range("2025-01-01", periods=280, freq="D", tz="UTC")
    data = {
        "prices": [[int(ts.timestamp() * 1000), float(i + 1)] for i, ts in enumerate(idx)],
        "market_caps": [[int(ts.timestamp() * 1000), float(1_000_000 + i)] for i, ts in enumerate(idx)],
        "total_volumes": [[int(ts.timestamp() * 1000), float(10_000 + i)] for i, ts in enumerate(idx)],
    }
    cache_dir = Path(tempfile.mkdtemp())
    backtest._write_cg_chart_cache(cache_dir, "bitcoin/test", 365, data)

    path = backtest._cg_chart_cache_path(cache_dir, "bitcoin/test", 365)
    assert path.name == "bitcoin_test-365d.json"
    assert backtest._load_cg_chart_cache(cache_dir, "bitcoin/test", 365)["prices"][0][1] == 1.0

    histories = asyncio.run(backtest._fetch_cg_histories(
        ["bitcoin/test"], 365, cache_dir=cache_dir
    ))
    assert set(histories) == {"bitcoin/test"}
    assert len(histories["bitcoin/test"]) == len(idx)
    assert {"close", "mcap", "volume"}.issubset(histories["bitcoin/test"].columns)


def test_backtest_klines_fixture_loader_and_symbols():
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner.backtest import fixture_symbols, load_klines_fixture

    root = Path(tempfile.mkdtemp()) / "fixture"
    klines = root / "klines"
    klines.mkdir(parents=True)
    (klines / "BTCUSDT.csv").write_text(
        "date,high,low,close,volume,quote_volume\n"
        "2026-01-02T00:00:00Z,102,99,101,1000,101000\n"
        "2026-01-01T00:00:00Z,101,98,100,900,90000\n"
        "2026-01-03T00:00:00Z,104,100,103,1100,113300\n"
    )
    (klines / "ETHUSDT.csv").write_text(
        "date,close,volume\n"
        "2026-01-01T00:00:00Z,10,50\n"
    )

    assert fixture_symbols(root) == ["BTC", "ETH"]
    df = load_klines_fixture("BTCUSDT", 2, root)
    assert df is not None
    assert list(df["close"]) == [101, 103]
    assert list(df["high"]) == [102, 104]
    assert list(df["low"]) == [99, 100]
    assert list(df["quote_volume"]) == [101000, 113300]
    assert str(df.index.tz) == "UTC"


def test_backtest_walk_respects_membership():
    # With a membership mask all-False, no signals and no base days accrue.
    from collections import defaultdict
    from crypto_rsi_scanner import backtest
    rng = np.random.RandomState(2)
    n = 420
    close = pd.Series(
        np.linspace(100, 40, n) + rng.randn(n) * 1.5,
        index=pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
    )
    df = pd.DataFrame({"close": close, "volume": pd.Series(1000.0, index=close.index)})
    sig: list = []
    base: dict = defaultdict(list)
    backtest.walk_coin(df, sig, base, member=np.zeros(n, dtype=bool))
    assert sig == [] and not base


def test_backtest_trigger_modes_differ():
    # An oscillator drives RSI in and out of OB/OS; cross_into and confirm enter
    # on opposite edges of the zone, so their graded outcomes must differ.
    from collections import defaultdict
    from crypto_rsi_scanner import backtest
    n = 500
    close = pd.Series(
        100 + 20 * np.sin(np.arange(n) / 9.0),
        index=pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC"),
    )
    df = pd.DataFrame({"close": close, "volume": pd.Series(1000.0, index=close.index)})
    out = {}
    for trig in ("cross_into", "confirm"):
        sig: list = []
        backtest.walk_coin(df, sig, defaultdict(list), trigger=trig)
        out[trig] = sig
    assert out["cross_into"] and out["confirm"]
    a = sorted(round(s["ret"], 3) for s in out["cross_into"] if s["h"] == 7)
    b = sorted(round(s["ret"], 3) for s in out["confirm"] if s["h"] == 7)
    assert a != b   # different entry timing -> different outcomes


def test_backtest_walk_generates_signals_offline():
    from collections import defaultdict
    from crypto_rsi_scanner import backtest
    rng = np.random.RandomState(1)
    n = 420
    close = pd.Series(
        np.linspace(100, 40, n) + rng.randn(n) * 1.5,  # noisy downtrend
        index=pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
    )
    df = pd.DataFrame({"close": close, "volume": pd.Series(1000.0, index=close.index)})
    signals: list = []
    regime_base: dict = defaultdict(list)
    backtest.walk_coin(df, signals, regime_base)
    assert signals, "expected crossing signals in a long downtrend"
    assert any(s["setup"] == "breakdown_risk" for s in signals)
    assert regime_base
    assert all(s["fav"] in (0, 1) and s["h"] in backtest.HORIZONS for s in signals)


# --- paper-trade scoreboard --------------------------------------------------

def test_paper_is_actionable():
    from crypto_rsi_scanner.paper import _is_actionable
    assert _is_actionable({"setup_type": "dip_buy", "market_aligned": "favorable"})
    assert _is_actionable({"setup_type": "mean_reversion", "market_aligned": "neutral"})
    assert not _is_actionable({"setup_type": "mean_reversion", "market_aligned": "adverse"})
    assert not _is_actionable({"setup_type": "breakdown_risk", "market_aligned": "neutral"})


def test_paper_open_close_pnl_sign():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper, config

    st = Storage(Path(tempfile.mkdtemp()) / "p.db")
    now0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    signals = [
        {"symbol": "AAA", "coin_id": "aaa", "flag": "OS", "is_new": True, "price": 100.0,
         "setup_type": "dip_buy", "expected_dir": "up", "market_regime": "UPTREND",
         "market_aligned": "favorable", "conviction": 70, "state_json": '{"version":1}'},
        {"symbol": "BBB", "coin_id": "bbb", "flag": "OS", "is_new": True, "price": 100.0,
         "setup_type": "breakdown_risk", "expected_dir": "down", "market_regime": "DOWNTREND",
         "market_aligned": "adverse", "conviction": 40},
    ]
    assert paper.update(st, signals, {}, now=now0) == (2, 0)
    assert paper.update(st, signals, {}, now=now0) == (0, 0)   # one open per coin

    h = config.PAPER_HOLD_DAYS
    idx = pd.date_range(now0, periods=h + 2, freq="D", tz="UTC")
    closes = pd.Series([100.0 + 10.0 * i / h for i in range(len(idx))], index=idx)  # +10% by +h
    later = now0 + timedelta(days=h + 1)
    assert paper.update(st, [], {"aaa": closes, "bbb": closes}, now=later) == (0, 2)

    rows = {r["symbol"]: dict(r) for r in st.closed_paper_trades()}
    assert rows["AAA"]["direction"] == "long" and rows["AAA"]["ret_pct"] > 5   # rose, long wins
    assert rows["AAA"]["state_json"] == '{"version":1}'
    assert rows["BBB"]["direction"] == "short" and rows["BBB"]["ret_pct"] < -5  # rose, short loses
    st.close()


def test_paper_closes_before_opening_same_coin_new_crossing():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper, config

    st = Storage(Path(tempfile.mkdtemp()) / "roll.db")
    now0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    sig = {"symbol": "AAA", "coin_id": "aaa", "flag": "OS", "is_new": True, "price": 100.0,
           "setup_type": "dip_buy", "expected_dir": "up",
           "market_regime": "UPTREND", "market_aligned": "favorable", "conviction": 70}
    assert paper.update(st, [sig], {}, now=now0) == (1, 0)

    h = config.PAPER_HOLD_DAYS
    idx = pd.date_range(now0, periods=h + 2, freq="D", tz="UTC")
    closes = pd.Series([100.0 + i for i in range(len(idx))], index=idx)
    later = now0 + timedelta(days=h + 1)
    new_sig = {**sig, "price": 120.0, "conviction": 75}
    assert paper.update(st, [new_sig], {"aaa": closes}, now=later) == (1, 1)
    assert len(st.closed_paper_trades()) == 1
    open_rows = [dict(r) for r in st.open_paper_trades()]
    assert len(open_rows) == 1
    assert open_rows[0]["entry_price"] == 120.0
    st.close()


def test_paper_not_closed_before_maturity():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper, config

    st = Storage(Path(tempfile.mkdtemp()) / "p2.db")
    now0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    sig = [{"symbol": "AAA", "coin_id": "aaa", "flag": "OB", "is_new": True, "price": 50.0,
            "setup_type": "trend_continuation", "expected_dir": "up",
            "market_regime": "UPTREND", "market_aligned": "favorable", "conviction": 60}]
    paper.update(st, sig, {}, now=now0)
    idx = pd.date_range(now0, periods=config.PAPER_HOLD_DAYS + 1, freq="D", tz="UTC")
    closes = pd.Series(55.0, index=idx)
    # only 1 day elapsed -> still open
    early = now0 + timedelta(days=1)
    assert paper.update(st, [], {"aaa": closes}, now=early) == (0, 0)
    assert len(st.open_paper_trades()) == 1
    st.close()


def test_paper_report_empty_and_populated():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper

    st = Storage(Path(tempfile.mkdtemp()) / "p3.db")
    assert "No paper trades yet" in paper.report(st)
    st.conn.execute(
        "INSERT INTO paper_trades (symbol, coin_id, setup_type, market_regime, "
        "market_aligned, state_json, direction, conviction, entry_price, entry_at, hold_days, "
        "exit_price, exit_at, ret_pct, status) VALUES "
        "('AAA','aaa','dip_buy','UPTREND','favorable',"
        "'{\"volatility\":{\"state\":\"high\"},\"breadth\":{\"state\":\"washout\"},"
        "\"relative_strength\":{\"bucket\":\"low\"},\"liquidity\":{\"bucket\":\"mid\"},"
        "\"risk\":{\"falling_knife_score\":80}}',"
        "'long',70,100,'2026-05-01',7,"
        "110,'2026-05-08',10.0,'closed')"
    )
    st.conn.execute(
        "INSERT INTO paper_trades (symbol, coin_id, setup_type, market_regime, "
        "market_aligned, direction, conviction, entry_price, entry_at, hold_days, "
        "exit_price, exit_at, ret_pct, status) VALUES "
        "('BBB','bbb','breakdown_risk','DOWNTREND','adverse','short',40,100,'2026-05-01',7,"
        "108,'2026-05-08',-8.0,'closed')"
    )
    st.conn.commit()
    out = paper.report(st)
    assert "PAPER-TRADE SCOREBOARD" in out
    assert "actionable" in out and "control" in out
    assert "By conviction bucket" in out
    cohorts = paper.report(st, cohorts=True)
    assert "By state cohort" in cohorts
    assert "volatility" in cohorts and "high" in cohorts
    assert "falling-knife" in cohorts
    data = paper.summary(st)
    assert data["closed_count"] == 2
    assert data["books"]["actionable"]["n"] == 1
    assert data["by_conviction_bucket"]["65-79"]["n"] == 1
    assert data["by_conviction_bucket"]["0-49"]["n"] == 1
    assert data["by_state"]["volatility"]["high"]["n"] == 1
    st.close()


def test_refresh_paper_closes_without_scan_or_alerts():
    import contextlib
    import io
    from crypto_rsi_scanner import scanner

    calls = {}

    class FakeStorage:
        def __init__(self, path):
            self.path = path
            calls["storage_path"] = path

        def open_paper_coin_ids(self):
            return ["aaa", "bbb"]

        def close(self):
            calls["closed_storage"] = True

    async def fake_fetch(ids):
        calls["fetch_ids"] = list(ids)
        return {"aaa": pd.Series([1.0]), "bbb": pd.Series([2.0])}

    def fake_update(storage, signals, closes_map):
        calls["update"] = (storage, list(signals), sorted(closes_map))
        return 0, 2

    def fake_report(storage, cohorts=False):
        calls["cohorts"] = cohorts
        return "paper report"

    orig_storage = scanner.Storage
    orig_fetch = scanner._fetch_extra_daily_closes
    orig_update = scanner.paper.update
    orig_report = scanner.paper.report
    scanner.Storage = FakeStorage
    scanner._fetch_extra_daily_closes = fake_fetch
    scanner.paper.update = fake_update
    scanner.paper.report = fake_report
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.refresh_paper(cohorts=True)
        assert "closed 2 trade(s)" in out.getvalue()
        assert "paper report" in out.getvalue()
        assert calls["fetch_ids"] == ["aaa", "bbb"]
        assert calls["update"][1] == []
        assert calls["update"][2] == ["aaa", "bbb"]
        assert calls["cohorts"] is True
        assert calls["closed_storage"] is True
    finally:
        scanner.Storage = orig_storage
        scanner._fetch_extra_daily_closes = orig_fetch
        scanner.paper.update = orig_update
        scanner.paper.report = orig_report


# --- regression: NaN enrichment from the DataFrame self-tune path -------------

def test_tg_card_tolerates_nan_enrichment():
    # _apply_live_edge_adjustments adds track_record/conviction_base columns; rows
    # without a value arrive here as NaN (float). _tg_card must not crash/leak it.
    s = _sample_signal(setup_type="mean_reversion", expected_dir="up",
                       track_record=float("nan"), conviction_base=float("nan"))
    out = formatting._tg_card(s)            # must not raise
    assert "nan" not in out.lower()


def test_live_edge_adjust_render_no_nan():
    import pandas as pd
    from crypto_rsi_scanner import scanner, outcomes

    class _FakeStore:
        def outcomes_joined(self):
            return [{"x": 1}]                # non-empty so the adjuster proceeds

    orig = outcomes.track_records
    outcomes.track_records = lambda rows, h: {"dip_buy": {"n": 10, "hit": 7, "med_ret": 2.0}}
    try:
        def row(sym, setup):
            return {"symbol": sym, "coin_id": sym.lower(), "flag": "OS",
                    "severity": "ALERT", "conviction": 55, "setup_type": setup,
                    "expected_dir": "up", "regime": "RANGE", "regime_note": "x",
                    "market_regime": "UPTREND", "market_aligned": "favorable",
                    "rsi_daily": 28.0, "rsi_4h": None, "rsi_weekly": None,
                    "rsi_z": 0.0, "rsi_delta": 0.0, "volume_ratio": 1.0,
                    "btc_corr": 0.0, "divergence": None, "price": 100.0}
        # AAA has a track record (dip_buy); ZZZ does NOT (mean_reversion) -> NaN row
        df = pd.DataFrame([row("AAA", "dip_buy"), row("ZZZ", "mean_reversion")])
        df = scanner._apply_live_edge_adjustments(df, _FakeStore())
        _, signals = scanner.build_message(df, {})
        for s in signals:
            card = formatting._tg_card(s)    # must not raise for the NaN-row coin
            assert "nan" not in card.lower(), f"NaN leaked for {s['symbol']}"
    finally:
        outcomes.track_records = orig


def test_route_notifications_only_marks_successful_sends():
    from crypto_rsi_scanner import scanner

    class Store:
        def __init__(self):
            self.alerted = []
            self.digest_marked = False
        def active_subscribers(self):
            return ["1"]
        def is_on_cooldown(self, symbol, flag, cooldown_hours):
            return False
        def mark_alerted(self, symbol, flag):
            self.alerted.append((symbol, flag))
        def digest_due(self, interval_hours):
            return True
        def mark_digest_sent(self):
            self.digest_marked = True

    signals = [
        {"symbol": "AAA", "flag": "OB", "tier": "INSTANT", "is_new": True, "conviction": 90},
        {"symbol": "BBB", "flag": "PRE_OS", "tier": "DIGEST", "is_new": True, "conviction": 35},
    ]
    orig = scanner.notify_all
    try:
        store = Store()
        scanner.notify_all = lambda *args, **kwargs: []
        stats = scanner._route_notifications(signals, store, dry_run=False)
        assert stats["instant_sent"] is False and stats["digest_sent"] is False
        assert store.alerted == []
        assert store.digest_marked is False

        store = Store()
        scanner.notify_all = lambda *args, **kwargs: ["Telegram"]
        stats = scanner._route_notifications(signals, store, dry_run=False)
        assert stats["instant_sent"] is True and stats["digest_sent"] is True
        assert store.alerted == [("AAA", "OB")]
        assert store.digest_marked is True
    finally:
        scanner.notify_all = orig


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


def test_sqlite_backup_api_integrity_and_retention():
    import sqlite3
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from crypto_rsi_scanner.backups import backup_database

    root = Path(tempfile.mkdtemp())
    src = root / "source.db"
    backup_dir = root / "backups"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO sample (value) VALUES ('ok')")
    conn.commit()
    conn.close()

    result = backup_database(
        src,
        backup_dir,
        keep=2,
        now=datetime(2026, 6, 8, 1, 2, 3, tzinfo=timezone.utc),
    )
    assert result.path.exists()
    assert result.quick_check == "ok"
    copied = sqlite3.connect(result.path)
    try:
        assert copied.execute("SELECT value FROM sample").fetchone()[0] == "ok"
    finally:
        copied.close()

    backup_database(src, backup_dir, keep=2, now=datetime(2026, 6, 8, 1, 2, 4, tzinfo=timezone.utc))
    third = backup_database(src, backup_dir, keep=2, now=datetime(2026, 6, 8, 1, 2, 5, tzinfo=timezone.utc))
    backups = sorted(backup_dir.glob("source-*.db"))
    assert len(backups) == 2
    assert backups[-1] == third.path
    assert not result.path.exists()


def test_sqlite_restore_drill_checks_schema_counts():
    import sqlite3
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from crypto_rsi_scanner.backups import backup_database, format_restore_result, verify_restore

    root = Path(tempfile.mkdtemp())
    src = root / "source.db"
    backup_dir = root / "backups"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE signals (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("CREATE TABLE paper_trades (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO scans DEFAULT VALUES")
    conn.execute("INSERT INTO meta (key, value) VALUES ('k', 'v')")
    conn.commit()
    conn.close()

    backup = backup_database(
        src,
        backup_dir,
        now=datetime(2026, 6, 8, 2, 0, 0, tzinfo=timezone.utc),
    )
    result = verify_restore(
        backup.path,
        expected_tables=("scans", "signals", "meta", "paper_trades"),
    )
    assert result.quick_check == "ok"
    assert result.table_counts["scans"] == 1
    assert result.table_counts["meta"] == 1
    assert "SQLite restore drill complete" in format_restore_result(result)


def test_backup_freshness_status_report():
    import sqlite3
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    from crypto_rsi_scanner import config, status_report
    from crypto_rsi_scanner.backups import backup_database

    root = Path(tempfile.mkdtemp())
    src = root / "rsi_scanner.db"
    backup_dir = root / "backups"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    st = _fresh_storage()
    orig_db = config.DB_PATH
    orig_dir = config.BACKUP_DIR
    orig_keep = config.BACKUP_KEEP
    orig_stale = config.BACKUP_STALE_HOURS
    orig_logs = config.LOG_FILES
    config.DB_PATH = src
    config.BACKUP_DIR = backup_dir
    config.BACKUP_KEEP = 2
    config.BACKUP_STALE_HOURS = 24
    config.LOG_FILES = []
    try:
        created = datetime(2026, 6, 8, 1, 0, 0, tzinfo=timezone.utc)
        backup_database(src, backup_dir, keep=2, now=created)

        fresh = status_report.format_status(st, now=created + timedelta(hours=2))
        assert "backup: OK" in fresh
        assert "rsi_scanner-20260608T010000Z.db" in fresh
        assert "2.0h ago" in fresh
        assert "1/2 retained" in fresh

        stale = status_report.format_status(st, now=created + timedelta(hours=25))
        assert "backup: STALE" in stale

        config.BACKUP_DIR = root / "empty"
        missing = status_report.format_status(st, now=created + timedelta(hours=2))
        assert "backup: MISSING" in missing
        assert "run main.py --backup-db" in missing
    finally:
        config.DB_PATH = orig_db
        config.BACKUP_DIR = orig_dir
        config.BACKUP_KEEP = orig_keep
        config.BACKUP_STALE_HOURS = orig_stale
        config.LOG_FILES = orig_logs
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

    log.write_text("first rotation\n")
    first = rotate_logs([log], max_bytes=3, keep=1, now=first_time)[0]
    assert first.reason == "rotated"
    assert first.rotated_to is not None
    assert first.rotated_to.read_text() == "first rotation\n"
    assert log.read_text() == ""

    log.write_text("second rotation\n")
    second = rotate_logs([log], max_bytes=3, keep=1, now=second_time)[0]
    assert second.reason == "rotated"
    assert second.rotated_to is not None
    assert second.rotated_to.read_text() == "second rotation\n"
    assert not first.rotated_to.exists()
    assert len(list(root.glob("bot.log.*"))) == 1
    assert log.read_text() == ""

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


def _run_all():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(funcs) - failures}/{len(funcs)} passed")
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)
