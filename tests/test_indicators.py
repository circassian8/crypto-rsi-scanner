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
    assert "EVENT_FIXTURE_NOW ?= 2026-06-15T16:00:00Z" in makefile
    assert "EVENT_RESEARCH_NOW ?=" in makefile
    assert "EVENT_FIXTURE_NOW_ENV = RSI_EVENT_RESEARCH_NOW=$(EVENT_FIXTURE_NOW)" in makefile
    assert "EVENT_RESEARCH_NOW_ENV = $(if $(strip $(EVENT_RESEARCH_NOW)),RSI_EVENT_RESEARCH_NOW=$(EVENT_RESEARCH_NOW),)" in makefile
    assert "RSI_EVENT_RESEARCH_NOW=$(EVENT_RESEARCH_NOW) \\" not in makefile
    notify_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-no-key", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_RESEARCH_NOW=" not in notify_dry
    notify_fixed_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-notify-no-key",
            "PYTHON=python3",
            "EVENT_RESEARCH_NOW=2026-06-20T12:00:00Z",
        ],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_RESEARCH_NOW=2026-06-20T12:00:00Z" in notify_fixed_dry
    fixture_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-cycle", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_RESEARCH_NOW=2026-06-15T16:00:00Z" in fixture_dry
    assert "check-python:" in makefile
    assert "bootstrap:" in makefile
    assert "python3 -m venv .venv" in makefile
    assert "export-src:" in makefile
    assert "git archive --format=zip -o crypto-rsi-scanner-source.zip HEAD" in makefile
    assert "event-fade-check-review-template:" in makefile
    assert "--event-fade-check-review-template $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_REVIEW_TEMPLATE)" in makefile
    assert "event-fade-check-review-bundle:" in makefile
    assert "--event-fade-check-review-template $(EVENT_FADE_REVIEW_BUNDLE_SAMPLE) $(EVENT_FADE_REVIEW_BUNDLE_TEMPLATE)" in makefile
    assert "event-fade-apply-review-bundle:" in makefile
    assert "--event-fade-apply-review-template $(EVENT_FADE_REVIEW_BUNDLE_SAMPLE) $(EVENT_FADE_REVIEW_BUNDLE_TEMPLATE) $(EVENT_FADE_REVIEW_BUNDLE_APPLIED)" in makefile
    assert "event-fade-review-applied-bundle:" in makefile
    assert "--event-fade-review-sample $(EVENT_FADE_REVIEW_BUNDLE_APPLIED)" in makefile
    assert "event-fade-fill-review-bundle-outcomes:" in makefile
    assert "--event-fade-fill-outcomes $(EVENT_FADE_REVIEW_BUNDLE_APPLIED) $(EVENT_FADE_REVIEW_BUNDLE_OUTCOME_PRICES) $(EVENT_FADE_REVIEW_BUNDLE_OUTCOMES)" in makefile
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

    bundle_check_dry = subprocess.run(
        [
            "make",
            "-n",
            "event-fade-check-review-bundle",
            "PYTHON=python3",
            "EVENT_FADE_REVIEW_BUNDLE_DIR=/tmp/review_bundle",
        ],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert (
        "python3 main.py --event-fade-check-review-template "
        "/tmp/review_bundle/validation_sample.jsonl "
        "/tmp/review_bundle/review_template_balanced.csv"
    ) in bundle_check_dry.stdout

    bundle_outcomes_dry = subprocess.run(
        [
            "make",
            "-n",
            "event-fade-fill-review-bundle-outcomes",
            "PYTHON=python3",
            "EVENT_FADE_REVIEW_BUNDLE_DIR=/tmp/review_bundle",
        ],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert (
        "python3 main.py --event-fade-fill-outcomes "
        "/tmp/review_bundle/validation_sample_reviewed.jsonl "
        "/tmp/review_bundle/outcome_prices.json "
        "/tmp/review_bundle/validation_sample_reviewed_with_outcomes.jsonl"
    ) in bundle_outcomes_dry.stdout


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
    from crypto_rsi_scanner.event_models import NormalizedEvent

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
        "EVENT_RESEARCH_NOW": "2026-06-15T16:00:00Z",
    }


def test_event_clock_parses_research_now_values():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_clock, scanner

    parsed = event_clock.parse_event_now("2026-06-15T16:00:00Z")
    assert parsed == datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    assert event_clock.parse_event_now("2026-06-15T16:00:00") == parsed
    assert event_clock.event_research_now("2026-06-15T16:00:00Z") == parsed
    assert event_clock.event_research_now("2026-06-14T16:00:00Z", override=parsed) == parsed
    assert scanner.event_research_now_from_config(override="2026-06-15T16:00:00Z") == parsed
    live_status = event_clock.event_clock_status(wall_clock_now=parsed)
    assert live_status["clock_mode"] == "live"
    assert live_status["research_now"] == parsed.isoformat()
    fixed_status = event_clock.event_clock_status(
        "2026-06-15T16:00:00Z",
        wall_clock_now=datetime(2026, 6, 16, 17, 0, tzinfo=timezone.utc),
    )
    assert fixed_status["clock_mode"] == "fixed"
    assert fixed_status["fixed_clock_age_hours"] == 25.0
    assert "stale" in "; ".join(fixed_status["warnings"])
    assert "stale" in event_clock.fixed_clock_notification_blocker(fixed_status)
    future_status = event_clock.event_clock_status(
        override="2026-06-15T18:00:00Z",
        wall_clock_now=parsed,
    )
    assert "future" in event_clock.fixed_clock_notification_blocker(future_status)

    try:
        event_clock.parse_event_now("not-a-date")
    except ValueError as exc:
        assert "Invalid event research timestamp" in str(exc)
    else:
        raise AssertionError("invalid event research timestamp should fail")


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


def _llm_golden_result():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

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
    from crypto_rsi_scanner import event_alerts, event_llm_analyzer

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
        cfg=event_llm_analyzer.EventLLMConfig(
            min_prefilter_score=min_prefilter_score,
            max_candidates_per_run=50,
        ),
    )
    return result, alerts, rows


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


def test_event_llm_budget_skips_lower_priority_rows_and_cache_hits_are_free():
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

    provider = CountingProvider(_llm_golden_fixture_path())
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        provider,
        cfg=event_llm_analyzer.EventLLMConfig(
            min_prefilter_score=0,
            max_candidates_per_run=3,
            max_calls_per_run=1,
        ),
    )
    assert provider.calls == 1
    assert len([row for row in rows if row.cache_status == "skipped_budget"]) == 2
    assert any("budget exhausted" in "; ".join(row.warnings) for row in rows)

    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "llm_cache.json"
        warm = CountingProvider(_llm_golden_fixture_path())
        event_llm_analyzer.analyze_event_candidates(
            result,
            alerts[:1],
            warm,
            cfg=event_llm_analyzer.EventLLMConfig(
                min_prefilter_score=0,
                max_candidates_per_run=1,
                cache_path=cache_path,
            ),
        )
        cached_provider = CountingProvider(_llm_golden_fixture_path())
        cached_rows = event_llm_analyzer.analyze_event_candidates(
            result,
            alerts[:2],
            cached_provider,
            cfg=event_llm_analyzer.EventLLMConfig(
                min_prefilter_score=0,
                max_candidates_per_run=2,
                max_calls_per_run=1,
                cache_path=cache_path,
            ),
        )
        assert [row.cache_status for row in cached_rows] == ["hit", "miss"]
        assert cached_provider.calls == 1


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


def test_event_alpha_artifact_context_and_doctor_filter_modes():
    import os
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_alpha_artifacts

    env_keys = (
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "RSI_EVENT_ALPHA_RUN_MODE",
        "RSI_EVENT_ALPHA_RUN_LEDGER_PATH",
        "RSI_EVENT_ALPHA_ALERT_STORE_PATH",
        "RSI_EVENT_WATCHLIST_STATE_PATH",
    )
    old_env = {key: os.environ.get(key) for key in env_keys}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for key in env_keys:
                os.environ.pop(key, None)
            os.environ["RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR"] = tmp
            no_key = event_alpha_artifacts.context_from_profile("no_key_live")
            assert no_key.run_mode == "burn_in"
            assert no_key.artifact_namespace == "no_key_live"
            assert no_key.run_ledger_path == Path(tmp) / "no_key_live" / "event_alpha_runs.jsonl"
            send = event_alpha_artifacts.context_from_profile("research_send")
            assert send.run_mode == "operational"
            assert send.artifact_namespace == "research_send"
            os.environ["RSI_EVENT_ALPHA_ALERT_STORE_PATH"] = str(Path(tmp) / "explicit.jsonl")
            explicit = event_alpha_artifacts.context_from_profile("full_llm_live")
            assert explicit.alert_store_path == Path(tmp) / "explicit.jsonl"

        run_rows = [
            {
                "run_id": "op",
                "profile": "no_key_live",
                "run_mode": "burn_in",
                "artifact_namespace": "no_key_live",
                "alertable": 1,
                "snapshot_write_success": True,
                "snapshot_rows_written": 1,
            },
            {
                "run_id": "fixture",
                "profile": "fixture",
                "run_mode": "fixture",
                "artifact_namespace": "fixture",
                "alertable": 1,
                "snapshot_write_success": False,
                "snapshot_write_block_reason": "test_or_fixture_run",
            },
        ]
        alert_rows = [
            {
                "run_id": "op",
                "profile": "no_key_live",
                "run_mode": "burn_in",
                "artifact_namespace": "no_key_live",
                "alert_key": "a",
                "tier": "WATCHLIST",
            },
            {
                "run_id": "fixture",
                "profile": "fixture",
                "run_mode": "fixture",
                "artifact_namespace": "fixture",
                "alert_key": "b",
                "tier": "WATCHLIST",
            },
        ]
        filtered = event_alpha_artifacts.filter_artifact_rows(
            run_rows,
            profile="no_key_live",
            artifact_namespace="no_key_live",
        )
        assert [row["run_id"] for row in filtered] == ["op"]
        assert event_alpha_artifacts.filter_artifact_rows(run_rows) == [run_rows[0]]
        assert len(event_alpha_artifacts.filter_artifact_rows(run_rows, include_test_artifacts=True)) == 2
        assert event_alpha_artifacts.filter_artifact_rows([{"run_id": "legacy"}]) == []
        assert event_alpha_artifacts.filter_artifact_rows(
            [{"run_id": "legacy"}],
            include_legacy_artifacts=True,
        ) == [{"run_id": "legacy"}]
        assert event_alpha_artifacts.classify_snapshot_availability(
            run_rows[0],
            "event_alpha_alerts.jsonl",
            1,
        ) == event_alpha_artifacts.SNAPSHOT_AVAILABLE
        assert event_alpha_artifacts.classify_snapshot_availability(
            {**run_rows[0], "run_id": "missing"},
            "event_alpha_alerts.jsonl",
            0,
        ) == event_alpha_artifacts.SNAPSHOT_MISSING
        assert event_alpha_artifacts.classify_snapshot_availability(
            {**run_rows[0], "run_id": "external", "alert_store_path": "/tmp/external-alerts.jsonl"},
            "/tmp/inspected-alerts.jsonl",
            0,
        ) == event_alpha_artifacts.SNAPSHOT_EXTERNAL_PATH
        assert event_alpha_artifacts.classify_snapshot_availability(
            {**run_rows[1], "alert_store_path": "/tmp/fixture-alerts.jsonl"},
            "/tmp/inspected-alerts.jsonl",
            0,
        ) == event_alpha_artifacts.SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL
        assert event_alpha_artifacts.classify_snapshot_availability(
            {"run_id": "legacy", "alertable": 1},
            "event_alpha_alerts.jsonl",
            0,
        ) == event_alpha_artifacts.SNAPSHOT_UNKNOWN_LEGACY
        ok = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=run_rows,
            alert_rows=alert_rows,
            profile="no_key_live",
            artifact_namespace="no_key_live",
        )
        assert ok.status == "OK"
        blocked = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{**run_rows[0], "run_id": "zero", "snapshot_rows_written": 0}],
            alert_rows=[],
            profile="no_key_live",
            artifact_namespace="no_key_live",
        )
        assert blocked.status == "BLOCKED"
        assert "wrote zero alert snapshots" in "; ".join(blocked.blockers)
        missing_match = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{**run_rows[0], "run_id": "missing-match", "snapshot_rows_written": 1}],
            alert_rows=[],
            profile="no_key_live",
            artifact_namespace="no_key_live",
        )
        assert missing_match.status == "BLOCKED"
        assert "alertable_run_missing_matching_snapshot_rows" in "; ".join(missing_match.blockers)
        fixture_external = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{**run_rows[1], "alert_store_path": "/tmp/fixture-alerts.jsonl"}],
            alert_rows=[],
            include_test_artifacts=True,
            inspected_alert_store_path="/tmp/inspected-alerts.jsonl",
        )
        assert fixture_external.status == "WARN"
        assert "fixture_snapshot_external_allowed" in "; ".join(fixture_external.warnings)
        legacy = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "legacy", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
            alert_rows=[],
            include_legacy_artifacts=True,
        )
        assert legacy.status == "WARN"
        assert "legacy_run_missing_snapshot_rows" in "; ".join(legacy.warnings)
        legacy_strict = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "legacy", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
            alert_rows=[],
            include_legacy_artifacts=True,
            strict=True,
        )
        assert legacy_strict.status == "BLOCKED"
        assert "legacy_run_missing_snapshot_rows" in "; ".join(legacy_strict.blockers)
        orphan = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=run_rows[:1],
            alert_rows=[*alert_rows[:1], {**alert_rows[0], "run_id": "orphan"}],
            profile="no_key_live",
            artifact_namespace="no_key_live",
        )
        assert "unknown run_id" in "; ".join(orphan.warnings)
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_event_alpha_report_context_and_preflight_are_profile_scoped():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import config, event_alpha_artifacts, event_alpha_preflight, event_alpha_profiles, scanner

    base_attrs = (
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "EVENT_ALPHA_RUN_MODE",
        "EVENT_ALPHA_RUN_LEDGER_PATH",
        "EVENT_ALPHA_ALERT_STORE_PATH",
        "EVENT_WATCHLIST_STATE_PATH",
        "EVENT_ALPHA_FEEDBACK_PATH",
        "EVENT_ALPHA_MISSED_PATH",
        "EVENT_ALPHA_PRIORS_PATH",
        "EVENT_PROVIDER_HEALTH_PATH",
        "EVENT_ALPHA_DAILY_BRIEF_PATH",
        "EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
        "EVENT_RESEARCH_CARDS_DIR",
        "EVENT_LLM_BUDGET_LEDGER_PATH",
        "EVENT_ALPHA_OUTCOMES_PATH",
        "EVENT_ALERTS_ENABLED",
        "EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY",
        "EVENT_RESEARCH_NOW",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_IDS",
    )
    profile_attrs = []
    for profile_name in event_alpha_profiles.profile_names():
        profile_attrs.extend(event_alpha_profiles.get_profile(profile_name).config_overrides)
    attrs = tuple(dict.fromkeys((*base_attrs, *profile_attrs)))
    old_cfg = {name: getattr(config, name) for name in attrs}
    env_keys = (
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "RSI_EVENT_ALPHA_RUN_MODE",
        "RSI_EVENT_ALPHA_RUN_LEDGER_PATH",
        "RSI_EVENT_ALPHA_ALERT_STORE_PATH",
        "RSI_EVENT_WATCHLIST_STATE_PATH",
        "RSI_EVENT_ALPHA_FEEDBACK_PATH",
        "RSI_EVENT_ALPHA_MISSED_PATH",
        "RSI_EVENT_ALPHA_PRIORS_PATH",
        "RSI_EVENT_PROVIDER_HEALTH_PATH",
        "RSI_EVENT_ALPHA_DAILY_BRIEF_PATH",
        "RSI_EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
        "RSI_EVENT_RESEARCH_CARDS_DIR",
        "RSI_EVENT_LLM_BUDGET_LEDGER_PATH",
        "RSI_EVENT_ALPHA_OUTCOMES_PATH",
        "OPENAI_API_KEY",
    )
    old_env = {key: os.environ.get(key) for key in env_keys}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for key in env_keys:
                os.environ.pop(key, None)
            base = Path(tmp)
            config.EVENT_ALPHA_ARTIFACT_BASE_DIR = base
            config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
            config.EVENT_ALPHA_RUN_MODE = ""
            config.EVENT_ALPHA_RUN_LEDGER_PATH = base / "event_alpha_runs.jsonl"
            config.EVENT_ALPHA_ALERT_STORE_PATH = base / "event_alpha_alerts.jsonl"
            config.EVENT_WATCHLIST_STATE_PATH = base / "event_watchlist_state.jsonl"
            config.EVENT_ALPHA_FEEDBACK_PATH = base / "event_alpha_feedback.jsonl"
            config.EVENT_ALPHA_MISSED_PATH = base / "event_alpha_missed.jsonl"
            config.EVENT_ALPHA_PRIORS_PATH = base / "event_alpha_priors.json"
            config.EVENT_PROVIDER_HEALTH_PATH = base / "event_provider_health.json"
            config.EVENT_ALPHA_DAILY_BRIEF_PATH = base / "event_alpha_daily_brief.md"
            config.EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR = base / "proposed_eval_cases"
            config.EVENT_RESEARCH_CARDS_DIR = base / "research_cards"
            config.EVENT_LLM_BUDGET_LEDGER_PATH = base / "event_llm_budget.json"
            config.EVENT_ALPHA_OUTCOMES_PATH = base / "event_alpha_outcomes.jsonl"
            config.EVENT_ALERTS_ENABLED = False
            config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY = False
            config.EVENT_RESEARCH_NOW = None
            config.TELEGRAM_BOT_TOKEN = None
            config.TELEGRAM_CHAT_IDS = []

            root = base / "event_alpha_runs.jsonl"
            root.write_text(json.dumps({
                "row_type": "event_alpha_run",
                "run_id": "root-run",
                "profile": "default",
                "run_mode": "operational",
                "artifact_namespace": "default",
                "success": True,
                "alertable": 0,
            }) + "\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_artifact_doctor_report()
            text = out.getvalue()
            assert f"{root}" in text
            assert "rows: runs=1" in text

            no_key = base / "no_key_live"
            no_key.mkdir()
            (no_key / "event_alpha_runs.jsonl").write_text(
                json.dumps({
                    "row_type": "event_alpha_run",
                    "run_id": "no-key-run",
                    "profile": "no_key_live",
                    "run_mode": "burn_in",
                    "artifact_namespace": "no_key_live",
                    "success": True,
                    "alertable": 0,
                }) + "\n",
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_artifact_doctor_report(profile_name="no_key_live")
            text = out.getvalue()
            assert "event_fade_cache" not in text
            assert f"{no_key / 'event_alpha_runs.jsonl'}" in text
            assert "rows: runs=1" in text
            assert "root-run" not in text

            custom = base / "custom_ns"
            custom.mkdir()
            (custom / "event_alpha_runs.jsonl").write_text(
                json.dumps({
                    "row_type": "event_alpha_run",
                    "run_id": "custom-run",
                    "profile": "no_key_live",
                    "run_mode": "burn_in",
                    "artifact_namespace": "custom_ns",
                    "success": True,
                    "alertable": 0,
                }) + "\n",
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_artifact_doctor_report(
                    profile_name="no_key_live",
                    artifact_namespace="custom_ns",
                )
            text = out.getvalue()
            assert f"{custom / 'event_alpha_runs.jsonl'}" in text
            assert "namespace: custom_ns" in text

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="no_key_live")
            text = out.getvalue()
            assert "READY_TO_RUN: yes" in text
            assert "artifact_namespace: no_key_live" in text
            assert "clock: mode=live" in text
            assert str(no_key / "event_alpha_runs.jsonl") in text

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="full_llm_live")
            assert "OpenAI LLM profile/provider requires OPENAI_API_KEY" in out.getvalue()

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="research_send", send_requested=True)
            assert "requires RSI_EVENT_ALERTS_ENABLED=1" in out.getvalue()

            bad_base = base / "not-a-dir"
            bad_base.write_text("file", encoding="utf-8")
            bad_context = event_alpha_artifacts.context_from_profile(
                "no_key_live",
                base_dir=bad_base,
                artifact_namespace="fixture",
            )
            bad = event_alpha_preflight.run_preflight(
                profile_name="no_key_live",
                context=bad_context,
                cfg=config,
            )
            assert bad.ready is False
            joined = "; ".join((*bad.blockers, *bad.warnings))
            assert "non-operational namespace" in joined
            assert "not writable" in joined

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="unknown")
            assert "unknown Event Alpha profile" in out.getvalue()
    finally:
        for name, value in old_cfg.items():
            setattr(config, name, value)
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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


def _llm_extraction_rows():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_llm_extractor
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


def test_event_llm_extractor_prioritizes_high_value_raw_events_before_budget():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_llm_extractor
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, *, provider="news", score=None, source_conf=0.75, body=None):
        payload = {}
        if score is not None:
            payload = {
                "market": {"symbol": raw_id.upper(), "coin_id": raw_id},
                "anomaly": {"score": score, "reasons": ["24h return 80%"]},
            }
            provider = "market_anomaly"
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body or title,
            raw_json=payload,
            source_confidence=source_conf,
            content_hash=raw_id,
        )

    market_roundup = raw("roundup", "Daily market roundup: Bitcoin World recap", source_conf=0.85)
    high_anomaly = raw("pump", "PUMP market anomaly with 80% move", score=92, source_conf=0.55)
    proxy_article = raw(
        "proxy",
        "SpaceX pre-IPO exposure opens through PROXY token",
        body="PROXY token offers synthetic exposure to SpaceX pre-IPO markets.",
        source_conf=0.90,
    )
    publisher_noise = raw("noise", "Bitcoin World covers SpaceX IPO hype", source_conf=0.90)

    high_priority = event_llm_extractor.score_raw_event_for_llm_extraction(high_anomaly, now=now)
    recap_priority = event_llm_extractor.score_raw_event_for_llm_extraction(market_roundup, now=now)
    proxy_priority = event_llm_extractor.score_raw_event_for_llm_extraction(proxy_article, now=now)
    noise_priority = event_llm_extractor.score_raw_event_for_llm_extraction(publisher_noise, now=now)
    assert high_priority.score > recap_priority.score
    assert proxy_priority.score > recap_priority.score
    assert noise_priority.score < proxy_priority.score

    class Provider:
        name = "fixture"

        def __init__(self):
            self.seen = []

        def extract_raw_event(self, packet):
            self.seen.append(packet["raw_id"])
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
        [market_roundup, publisher_noise, proxy_article, high_anomaly],
        provider,
        cfg=event_llm_extractor.EventLLMExtractorConfig(max_events_per_run=2),
    )
    assert provider.seen == ["pump", "proxy"]
    assert [row.raw_event.raw_id for row in rows] == ["pump", "proxy"]
    assert all(row.extraction_priority_score > 0 for row in rows)
    assert any("catalyst_keywords" in ",".join(row.extraction_priority_reasons) for row in rows)


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


def test_event_discovery_transform_applies_llm_hints_before_resolver_validation():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_discovery, event_llm_extractor
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
    from crypto_rsi_scanner import config, scanner

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
        "EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN": config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN,
        "EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES": config.EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES,
        "EVENT_LLM_EXTRACTOR_CACHE_PATH": config.EVENT_LLM_EXTRACTOR_CACHE_PATH,
        "EVENT_LLM_EXTRACTOR_PROMPT_VERSION": config.EVENT_LLM_EXTRACTOR_PROMPT_VERSION,
    }
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
    config.EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN = 50
    config.EVENT_LLM_EXTRACTOR_REQUIRE_EVIDENCE_QUOTES = True
    config.EVENT_LLM_EXTRACTOR_CACHE_PATH = None
    config.EVENT_LLM_EXTRACTOR_PROMPT_VERSION = "llm_raw_event_extraction_v1"
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


def test_event_market_enrichment_live_fail_soft_records_provider_health():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_market_enrichment, event_provider_health

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
    from crypto_rsi_scanner import event_discovery, event_market_enrichment

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


def test_event_catalyst_search_scaffold_attaches_evidence_without_bypassing_discovery():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alerts,
        event_anomaly_scanner,
        event_catalyst_search,
        event_discovery,
        event_market_enrichment,
        event_playbooks,
    )
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent

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


def test_event_catalyst_search_proxy_evidence_still_requires_deterministic_validation():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alerts,
        event_alpha_pipeline,
        event_catalyst_search,
        event_discovery,
        event_playbooks,
    )
    from crypto_rsi_scanner.event_models import DiscoveredAsset, RawDiscoveredEvent

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


def test_event_catalyst_search_live_provider_adapters_are_evidence_only():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_catalyst_search

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


def test_event_catalyst_search_scores_filter_low_quality_results():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_catalyst_search
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:pump:2026-06-18",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="PUMP market anomaly: 24h return 80%",
        body="No dated external catalyst has been validated.",
        raw_json={"market": {"symbol": "PUMP", "coin_id": "pump"}, "anomaly": {"score": 90}},
        source_confidence=0.55,
        content_hash="anomaly-pump",
    )
    good = RawDiscoveredEvent(
        raw_id="pump-binance",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pump",
        title="Binance will list Pump Protocol (PUMP)",
        body="Binance will list PUMP spot trading today.",
        raw_json={
            "event": {
                "event_id": "pump-binance",
                "event_name": "Binance will list Pump Protocol (PUMP)",
                "event_type": "exchange_listing",
                "event_time": "2026-06-18T20:00:00Z",
                "event_time_confidence": 0.95,
                "confidence": 0.90,
            }
        },
        source_confidence=0.90,
        content_hash="pump-binance",
    )
    recap = RawDiscoveredEvent(
        raw_id="pump-recap",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/recap",
        title="Daily market recap: crypto prices today",
        body="A generic market recap mentions PUMP with no catalyst.",
        raw_json={},
        source_confidence=0.60,
        content_hash="pump-recap",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider({
        "PUMP Binance listing": (good, recap),
    })
    cfg = event_catalyst_search.EventCatalystSearchConfig(
        enabled=True,
        max_anomalies=1,
        max_queries_per_anomaly=2,
        max_results_per_query=5,
        min_anomaly_score=60,
        min_result_confidence=0.60,
    )
    result = event_catalyst_search.run_catalyst_search([anomaly], provider, cfg=cfg, now=now)
    assert [row.raw_event.raw_id for row in result.result_events] == ["pump-binance"]
    assert [row.raw_event.raw_id for row in result.rejected_result_events] == ["pump-recap"]
    assert result.result_events[0].result_score > result.rejected_result_events[0].result_score
    report = event_catalyst_search.format_catalyst_search_report(result)
    assert "accepted_results=1" in report
    assert "rejected_results=1" in report


def test_event_catalyst_search_requires_identity_before_attaching_catalyst_terms():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_catalyst_search
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent

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
    from crypto_rsi_scanner import event_catalyst_search
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent

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


def test_event_catalyst_search_identity_can_come_from_resolver_validated_llm_extraction():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_catalyst_search
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent

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
    from crypto_rsi_scanner import event_catalyst_search
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent

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
    from crypto_rsi_scanner import event_catalyst_search

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


def test_event_alpha_radar_scanner_report_with_fixture_anomalies():
    import contextlib
    import io
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
        assert pipe.watchlist_entries == 17
        assert pipe.watchlist_escalations >= 1
        assert pipe.routed == 17
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
    assert advisory_pipe.watchlist_entries == 1
    assert advisory_pipe.routed == 1


def test_event_alpha_alert_store_snapshots_and_fills_outcomes():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_alert_store, event_alerts

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    alerts = event_alerts.build_event_alert_candidates(
        _full_event_discovery_fixture_result(),
        now=now,
    )
    assert any(alert.symbol == "TESTVELVET" for alert in alerts)

    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "event_alpha_alerts.jsonl"
        cfg = event_alpha_alert_store.EventAlphaAlertStoreConfig(path=store_path)
        wrote = event_alpha_alert_store.write_alert_snapshots(alerts, cfg=cfg, now=now)
        assert wrote.rows_written == len(alerts)
        loaded = event_alpha_alert_store.load_alert_snapshots(store_path)
        assert loaded.rows_read == len(alerts)
        report = event_alpha_alert_store.format_alert_snapshot_report(loaded)
        assert "EVENT ALPHA ALERT SNAPSHOT REPORT" in report
        assert "by playbook:" in report
        assert "by expected direction:" in report
        assert "by tier:" in report

        prices_path = Path(tmp) / "prices.json"
        prices_path.write_text(json.dumps({
            "source": "fixture",
            "interval": "1h",
            "prices": [
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-15T17:00:00Z", "close": 9.0, "high": 9.2, "low": 8.8},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-15T20:00:00Z", "close": 8.2, "high": 8.5, "low": 8.0},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-16T16:00:00Z", "close": 7.2, "high": 7.4, "low": 6.9},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-18T16:00:00Z", "close": 6.0, "high": 6.3, "low": 5.8},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-22T16:00:00Z", "close": 5.4, "high": 5.6, "low": 5.1},
            ],
        }), encoding="utf-8")
        out_path = Path(tmp) / "with_outcomes.jsonl"
        filled = event_alpha_alert_store.fill_alert_outcomes(
            loaded.rows,
            prices_path,
            out_path,
            source_path=store_path,
        )
        assert filled.rows_written == len(alerts)
        assert filled.rows_with_outcomes >= 1
        out_rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
        velvet = next(row for row in out_rows if row.get("asset_symbol") == "TESTVELVET")
        assert velvet["outcome_price_interval"] == "1h"
        assert velvet["return_1h"] is not None
        assert velvet["return_24h"] is not None
        assert velvet["return_72h"] is not None
        assert velvet["return_7d"] is not None
        assert velvet["primary_horizon_return"] is not None
        assert velvet["direction_hit"] is True
        assert velvet["max_favorable_excursion"] is not None
        assert velvet["max_adverse_excursion"] is not None
        outcome_report = event_alpha_alert_store.format_alert_snapshot_report(
            event_alpha_alert_store.load_alert_snapshots(out_path)
        )
        assert "outcomes:" in outcome_report
        assert "MFE/MAE by playbook:" in outcome_report
        assert "Outcome metrics by playbook:" in outcome_report


def test_event_alpha_outcomes_playbook_specific_metrics():
    from crypto_rsi_scanner import event_alpha_outcomes

    listing_row = {
        "observed_at": "2026-06-18T12:00:00+00:00",
        "entry_reference_price": 10.0,
        "playbook_type": "listing_volatility",
        "expected_direction": "volatility",
        "success_metric": "volatility",
        "primary_horizon": "24h",
    }
    prices = [
        {"timestamp": "2026-06-18T13:00:00+00:00", "close": 10.5, "high": 11.5, "low": 9.8},
        {"timestamp": "2026-06-18T20:00:00+00:00", "close": 9.2, "high": 10.0, "low": 8.8},
    ]
    metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(
        listing_row,
        prices,
        returns={"max_favorable_excursion": 0.15, "max_adverse_excursion": 0.12, "primary_horizon_return": -0.08},
    )
    assert metrics["volatility_hit"] is True
    assert metrics["mfe_mae_ratio"] > 1.0

    proxy_row = {
        "observed_at": "2026-06-18T12:00:00+00:00",
        "entry_reference_price": 10.0,
        "playbook_type": "proxy_attention",
        "expected_direction": "up_then_fade",
        "success_metric": "mfe_mae",
        "primary_horizon": "72h",
    }
    proxy_metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(
        proxy_row,
        prices,
        returns={"return_72h": -0.10, "max_favorable_excursion": 0.15, "max_adverse_excursion": 0.05},
    )
    assert proxy_metrics["up_then_fade_hit"] is True

    unlock_row = {
        "observed_at": "2026-06-18T12:00:00+00:00",
        "entry_reference_price": 10.0,
        "playbook_type": "unlock_supply_pressure",
        "expected_direction": "down",
        "success_metric": "direction_hit",
        "primary_horizon": "24h",
        "btc_primary_horizon_return": 0.02,
    }
    unlock_metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(
        unlock_row,
        prices,
        returns={"primary_horizon_return": -0.08},
    )
    assert unlock_metrics["underperformance_vs_btc"] == -0.10

    anomaly_row = {
        "event_type": "exchange_listing",
        "source": "market_anomaly+catalyst_search",
    }
    anomaly_metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(anomaly_row, [])
    assert anomaly_metrics["catalyst_found_after_anomaly"] is True


def test_event_alpha_alert_store_snapshot_policy_filters_rows():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_alert_store, event_alerts

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    alerts = event_alerts.build_event_alert_candidates(_full_event_discovery_fixture_result(), now=now)
    store_only_count = sum(1 for alert in alerts if alert.tier == event_alerts.EventAlertTier.STORE_ONLY)
    non_store_count = len(alerts) - store_only_count
    assert store_only_count > 2
    assert non_store_count > 0

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        all_path = root / "all.jsonl"
        all_result = event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=all_path, snapshot_policy="all"),
            now=now,
        )
        assert all_result.rows_written == len(alerts)

        non_store_path = root / "non-store.jsonl"
        non_store_result = event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=non_store_path, snapshot_policy="non_store"),
            now=now,
        )
        assert non_store_result.rows_written == non_store_count
        assert all(
            json.loads(line)["tier"] != event_alerts.EventAlertTier.STORE_ONLY.value
            for line in non_store_path.read_text(encoding="utf-8").splitlines()
        )

        sampled_path = root / "sampled.jsonl"
        sampled_result = event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(
                path=sampled_path,
                snapshot_policy="sampled_controls",
                sampled_controls_limit=2,
            ),
            now=now,
        )
        assert sampled_result.rows_written == non_store_count + 2
        sampled_rows = [
            json.loads(line)
            for line in sampled_path.read_text(encoding="utf-8").splitlines()
        ]
        assert sum(1 for row in sampled_rows if row["tier"] == event_alerts.EventAlertTier.STORE_ONLY.value) == 2


def test_event_alpha_alert_store_scanner_report_and_outcome_fill_commands():
    import contextlib
    import io
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import config, event_alpha_alert_store, event_alerts, scanner

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    alerts = event_alerts.build_event_alert_candidates(_full_event_discovery_fixture_result(), now=now)
    original = {
        "EVENT_ALPHA_ALERT_STORE_PATH": config.EVENT_ALPHA_ALERT_STORE_PATH,
        "EVENT_ALPHA_FEEDBACK_PATH": config.EVENT_ALPHA_FEEDBACK_PATH,
    }
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "alerts.jsonl"
        feedback_path = Path(tmp) / "feedback.jsonl"
        config.EVENT_ALPHA_ALERT_STORE_PATH = store_path
        config.EVENT_ALPHA_FEEDBACK_PATH = feedback_path
        event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=store_path),
            now=now,
        )
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_alerts_report()
            text = out.getvalue()
            assert "EVENT ALPHA ALERT SNAPSHOT REPORT" in text
            assert "by playbook:" in text

            prices_path = Path(tmp) / "prices.json"
            prices_path.write_text(json.dumps({
                "source": "fixture",
                "interval": "1h",
                "prices": [
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-15T17:00:00Z", "close": 9.0, "high": 9.1, "low": 8.9},
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-16T16:00:00Z", "close": 7.0, "high": 7.3, "low": 6.8},
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-18T16:00:00Z", "close": 6.0, "high": 6.2, "low": 5.8},
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-22T16:00:00Z", "close": 5.0, "high": 5.3, "low": 4.9},
                ],
            }), encoding="utf-8")
            filled_path = Path(tmp) / "filled.jsonl"
            fill_out = io.StringIO()
            with contextlib.redirect_stdout(fill_out):
                scanner.event_alpha_fill_outcomes(str(prices_path), str(filled_path))
            fill_text = fill_out.getvalue()
            assert "EVENT ALPHA ALERT OUTCOMES FILLED" in fill_text
            assert filled_path.exists()
        finally:
            for name, value in original.items():
                setattr(config, name, value)


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
            assert "watchlist_entries=1" in text
            assert "routed=1" in text
            assert "routes: STORE_ONLY=1" in text
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
        "EVENT_DISCOVERY_UNIVERSE_LIVE",
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
        "EVENT_LLM_EXTRACTOR_MODE",
        "EVENT_LLM_EXTRACTOR_PROVIDER",
        "EVENT_LLM_MODE",
        "EVENT_LLM_PROVIDER",
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
        config.EVENT_DISCOVERY_UNIVERSE_LIVE = False
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
        config.EVENT_LLM_EXTRACTOR_MODE = "advisory"
        config.EVENT_LLM_EXTRACTOR_PROVIDER = "fixture"
        config.EVENT_LLM_MODE = "shadow"
        config.EVENT_LLM_PROVIDER = "fixture"
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
    radar = replace(base, tier=event_alerts.EventAlertTier.RADAR_DIGEST, opportunity_score=60)
    watch = replace(base, tier=event_alerts.EventAlertTier.WATCHLIST, opportunity_score=75)

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


def test_event_alpha_router_routes_material_changes_with_lanes():
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_router, event_playbooks, event_watchlist

    def row(symbol, *, reasons=(), score_jump=0, state=None, playbook=None, should_alert=True, history=None):
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
    original_ids = config.TELEGRAM_CHAT_IDS
    FakeStorage.meta = {}
    scanner.Storage = FakeStorage
    scanner.send_telegram = fake_send
    config.TELEGRAM_CHAT_IDS = ["fallback"]
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
        assert "HIGH_PRIORITY_RESEARCH" in sent[0][0]
        assert "HIGH" in sent[0][0]
        assert "DUP" not in sent[0][0]
        assert any(
            key.startswith("event_alpha_sent_count_instant_") and value == "1"
            for key, value in FakeStorage.meta.items()
        )

        FakeStorage.meta = {}
        scanner.send_telegram = lambda message, *, parse_mode=None, chat_ids=None: False
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
        config.TELEGRAM_CHAT_IDS = original_ids


def test_event_alpha_notification_profiles_and_preflight_guards():
    import contextlib
    import io
    import os
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, event_alpha_artifacts, event_alpha_profiles, scanner

    no_key = event_alpha_profiles.get_profile("notify_no_key")
    assert no_key.notification_burn_in is True
    assert no_key.with_llm is False
    assert no_key.config_overrides["EVENT_DISCOVERY_GDELT_LIVE"] is True
    assert no_key.config_overrides["EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE"] is True
    assert no_key.config_overrides["EVENT_ALPHA_ROUTER_ENABLED"] is True
    assert no_key.config_overrides["EVENT_RESEARCH_CARDS_AUTO_WRITE"] is True
    assert no_key.config_overrides["EVENT_LLM_PROVIDER"] == "fixture"
    assert no_key.config_overrides["EVENT_ALPHA_RUN_MODE"] == "notification_burn_in"
    assert no_key.config_overrides["EVENT_ALPHA_SNAPSHOT_POLICY"] == "alertable"

    llm = event_alpha_profiles.get_profile("notify_llm")
    assert llm.with_llm is True
    assert llm.config_overrides["EVENT_LLM_PROVIDER"] == "openai"
    assert llm.config_overrides["EVENT_LLM_EXTRACTOR_PROVIDER"] == "openai"
    assert llm.config_overrides["EVENT_LLM_MAX_CALLS_PER_RUN"] <= 10
    assert llm.config_overrides["EVENT_LLM_MAX_CALLS_PER_DAY"] <= 50
    assert llm.config_overrides["EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY"] <= 1.0
    assert llm.config_overrides["EVENT_LLM_CACHE_TTL_HOURS"] == 168

    ctx = event_alpha_artifacts.context_from_profile("notify_no_key", base_dir=Path("/tmp/event-alpha-test"))
    assert ctx.run_mode == "notification_burn_in"
    assert ctx.artifact_namespace == "notify_no_key"

    base_attrs = (
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "EVENT_ALPHA_RUN_MODE",
        "EVENT_ALERTS_ENABLED",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_IDS",
    )
    profile_attrs = tuple(dict.fromkeys((*no_key.config_overrides, *llm.config_overrides)))
    attrs = tuple(name for name in dict.fromkeys((*base_attrs, *profile_attrs)) if hasattr(config, name))
    original = {name: getattr(config, name) for name in attrs}
    old_key = os.environ.get("OPENAI_API_KEY")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("OPENAI_API_KEY", None)
            config.EVENT_ALPHA_ARTIFACT_BASE_DIR = Path(tmp)
            config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
            config.EVENT_ALPHA_RUN_MODE = ""
            config.EVENT_ALERTS_ENABLED = False
            config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY = False
            config.EVENT_RESEARCH_NOW = None
            config.TELEGRAM_BOT_TOKEN = None
            config.TELEGRAM_CHAT_IDS = []
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_no_key")
            text = out.getvalue()
            assert "READY_TO_RUN: yes" in text
            assert "requires RSI_EVENT_ALERTS_ENABLED=1" not in text
            assert "requires Telegram token" not in text
            assert "clock: mode=live" in text

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_no_key", send_requested=True)
            text = out.getvalue()
            assert "requires RSI_EVENT_ALERTS_ENABLED=1" in text
            assert "requires Telegram token" in text

            config.EVENT_RESEARCH_NOW = "2026-06-15T16:00:00Z"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_no_key", send_requested=True)
            text = out.getvalue()
            assert "clock: mode=fixed" in text
            assert "fixed research clock blocks notification send" in text

            config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY = True
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_no_key", send_requested=True)
            text = out.getvalue()
            assert "fixed research clock active for notification profile" in text
            assert "fixed research clock blocks notification send" not in text
            config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY = False
            config.EVENT_RESEARCH_NOW = None

            config.EVENT_ALERTS_ENABLED = True
            config.TELEGRAM_BOT_TOKEN = "token"
            config.TELEGRAM_CHAT_IDS = ["chat"]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_no_key")
            assert "READY_TO_RUN: yes" in out.getvalue()

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_llm")
            assert "OPENAI_API_KEY" in out.getvalue()
    finally:
        for name, value in original.items():
            setattr(config, name, value)
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key


def test_event_alpha_notification_lane_state_is_independent_and_dedupes_triggered():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from crypto_rsi_scanner import event_alpha_notifications, event_alpha_router

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    def decision(symbol, lane, alert_id=None):
        return SimpleNamespace(
            alertable=True,
            lane=lane,
            alert_id=alert_id or f"ea:{symbol}",
        )

    storage = FakeStorage()
    cfg = event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=True,
        daily_digest_cooldown_hours=12,
        instant_escalation_cooldown_hours=1,
        max_instant_per_day=1,
        health_heartbeat_enabled=True,
    )
    nine = datetime(2026, 6, 19, 9, 0, tzinfo=timezone.utc)
    eleven = datetime(2026, 6, 19, 11, 0, tzinfo=timezone.utc)
    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_DAILY_DIGEST,
        item_count=1,
        now=nine,
    )
    plan = event_alpha_notifications.build_notification_plan(
        [
            decision("DIG", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST),
            decision("FAST", event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION),
            decision("TRIG", event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE),
        ],
        storage=storage,
        cfg=cfg,
        now=eleven,
    )
    assert event_alpha_notifications.LANE_DAILY_DIGEST not in plan.decisions_by_lane
    assert plan.decisions_by_lane[event_alpha_notifications.LANE_INSTANT_ESCALATION][0].alert_id == "ea:FAST"
    assert plan.decisions_by_lane[event_alpha_notifications.LANE_TRIGGERED_FADE][0].alert_id == "ea:TRIG"

    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_INSTANT_ESCALATION,
        item_count=1,
        now=eleven,
    )
    later = datetime(2026, 6, 19, 12, 30, tzinfo=timezone.utc)
    capped = event_alpha_notifications.build_notification_plan(
        [decision("FAST2", event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION)],
        storage=storage,
        cfg=cfg,
        now=later,
    )
    assert event_alpha_notifications.LANE_INSTANT_ESCALATION not in capped.decisions_by_lane
    assert "daily instant cap" in capped.blocked_by_lane[event_alpha_notifications.LANE_INSTANT_ESCALATION]

    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_TRIGGERED_FADE,
        item_count=1,
        now=later,
        alert_ids=["ea:TRIG"],
    )
    deduped = event_alpha_notifications.build_notification_plan(
        [decision("TRIG", event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE, alert_id="ea:TRIG")],
        storage=storage,
        cfg=cfg,
        now=later,
    )
    assert event_alpha_notifications.LANE_TRIGGERED_FADE not in deduped.decisions_by_lane
    assert "already sent" in deduped.blocked_by_lane[event_alpha_notifications.LANE_TRIGGERED_FADE]


def test_event_alpha_notification_state_is_profile_namespace_scoped():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from crypto_rsi_scanner import event_alpha_notifications, event_alpha_router

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    storage = FakeStorage()
    now = datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc)
    no_key_cfg = event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=True,
        notification_scope="namespace",
        profile_name="notify_no_key",
        artifact_namespace="notify_no_key",
        max_instant_per_day=1,
    )
    llm_cfg = event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=True,
        notification_scope="namespace",
        profile_name="notify_llm",
        artifact_namespace="notify_llm",
        max_instant_per_day=1,
    )
    research_cfg = event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=True,
        notification_scope="namespace",
        profile_name="research_send",
        artifact_namespace="research_send",
        max_instant_per_day=1,
    )

    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_DAILY_DIGEST,
        item_count=1,
        now=now,
        cfg=no_key_cfg,
    )
    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_INSTANT_ESCALATION,
        item_count=1,
        now=now,
        cfg=no_key_cfg,
    )
    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_TRIGGERED_FADE,
        item_count=1,
        now=now,
        alert_ids=["ea:scoped"],
        cfg=no_key_cfg,
    )
    decision_daily = SimpleNamespace(
        alertable=True,
        lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        alert_id="ea:daily",
    )
    decision_instant = SimpleNamespace(
        alertable=True,
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
        alert_id="ea:instant",
    )
    decision_triggered = SimpleNamespace(
        alertable=True,
        lane=event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE,
        alert_id="ea:scoped",
    )
    llm_plan = event_alpha_notifications.build_notification_plan(
        [decision_daily, decision_triggered],
        storage=storage,
        cfg=llm_cfg,
        now=now,
    )
    assert llm_plan.decisions_by_lane[event_alpha_notifications.LANE_DAILY_DIGEST][0].alert_id == "ea:daily"
    assert llm_plan.decisions_by_lane[event_alpha_notifications.LANE_TRIGGERED_FADE][0].alert_id == "ea:scoped"
    assert llm_plan.scope_value == "notify_llm"

    research_plan = event_alpha_notifications.build_notification_plan(
        [decision_instant],
        storage=storage,
        cfg=research_cfg,
        now=now,
    )
    assert research_plan.decisions_by_lane[event_alpha_notifications.LANE_INSTANT_ESCALATION][0].alert_id == "ea:instant"
    preview = event_alpha_notifications.format_preview(
        profile="notify_llm",
        artifact_namespace="notify_llm",
        telegram_ready=False,
        provider_ready_event_sources=1,
        provider_ready_enrichment_sources=1,
        llm_budget_status="fixture",
        plan=llm_plan,
        card_auto_write=True,
        provider_health_rows={
            "coingecko:market_enrichment": {
                "provider_key": "coingecko:market_enrichment",
                "consecutive_failures": 1,
                "disabled_until": "2026-06-19T12:00:00+00:00",
            }
        },
    )
    assert "notification_scope: namespace" in preview
    assert "event_alpha_notify:notify_llm:last_sent:daily_digest" in preview
    assert "partial_results_allowed: yes" in preview
    assert "provider_health_backoff_count: 1" in preview
    assert "coingecko:market_enrichment disabled_until=2026-06-19T12:00:00+00:00" in preview
    live_day_status = event_alpha_notifications.cooldown_status_by_lane(
        storage,
        cfg=llm_cfg,
        now=datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc),
    )
    fixed_day_status = event_alpha_notifications.cooldown_status_by_lane(
        storage,
        cfg=llm_cfg,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    assert "sent_count:instant:2026-06-20" in live_day_status[
        event_alpha_notifications.LANE_INSTANT_ESCALATION
    ]["count_meta_key"]
    assert "sent_count:instant:2026-06-15" in fixed_day_status[
        event_alpha_notifications.LANE_INSTANT_ESCALATION
    ]["count_meta_key"]

    global_cfg = event_alpha_notifications.EventAlphaNotificationConfig(enabled=True, notification_scope="global")
    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_DAILY_DIGEST,
        item_count=1,
        now=now,
        cfg=global_cfg,
    )
    assert storage.meta[event_alpha_notifications.LAST_SENT_META_KEYS[event_alpha_notifications.LANE_DAILY_DIGEST]]


def test_event_alpha_routed_notification_message_is_research_only_and_reviewable():
    from crypto_rsi_scanner import event_alpha_router, event_playbooks, event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="spacex|solana|proxy_attention",
        cluster_id="spacex|ipo_proxy|2026-06-20",
        event_id="evt",
        coin_id="solana",
        symbol="SOL",
        relationship_type="proxy_attention",
        external_asset="SpaceX <IPO>",
        event_time="2026-06-20T13:30:00+00:00",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state="WATCHLIST",
        first_seen_at="2026-06-19T09:00:00+00:00",
        last_seen_at="2026-06-19T11:00:00+00:00",
        source_count=2,
        highest_score=88,
        latest_score=88,
        latest_tier="HIGH_PRIORITY_WATCH",
        latest_event_name="SpaceX <IPO> proxy heats up",
        latest_source="test",
        latest_playbook_type=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        latest_rule_playbook_type=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        latest_playbook_action="high_priority_watch",
        latest_llm_asset_role="proxy_instrument",
        latest_llm_confidence=0.86,
        latest_market_snapshot={"price": 123.4, "return_24h": 0.12, "volume_zscore_24h": 3.2},
        should_alert=True,
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="state escalation",
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
    )
    message = event_alpha_router.format_routed_telegram_digest(
        [decision],
        profile="notify_no_key",
        card_path_by_alert_id={decision.alert_id: "/tmp/card.md"},
    )
    assert "Research-only / DAY-1 UNVALIDATED" in message
    assert "Validation status: DAY-1 UNVALIDATED" in message
    assert "Trading action: NONE" in message
    assert "Review before acting" in message
    assert "Not a trade signal" in message
    assert "alert_id=ea:spacex|solana|proxy_attention" in message
    assert "playbook=proxy_attention" in message
    assert "tier=HIGH_PRIORITY_WATCH" in message
    assert "route=HIGH_PRIORITY_RESEARCH" in message
    assert "lane=INSTANT_ESCALATION" in message
    assert "external_catalyst=SpaceX &lt;IPO&gt;" in message
    assert "event_time=2026-06-20T13:30:00+00:00" in message
    assert "market=price=123.4" in message
    assert "llm_role=proxy_instrument" in message
    assert "research_card=/tmp/card.md" in message
    assert "make event-feedback-useful FEEDBACK_TARGET=ea:spacex|solana|proxy_attention" in message
    assert "<IPO> proxy" not in message


def test_event_alpha_notification_disabled_records_would_send_and_heartbeat():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from crypto_rsi_scanner import event_alpha_notifications, event_alpha_router

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    sent = []
    decision = SimpleNamespace(
        alertable=True,
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
        alert_id="ea:fast",
    )
    result = event_alpha_notifications.send_notifications(
        [decision],
        storage=FakeStorage(),
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(enabled=False),
        send_fn=lambda message: sent.append(message) or True,
        now=datetime(2026, 6, 19, 11, 0, tzinfo=timezone.utc),
        profile="notify_no_key",
        include_health_heartbeat=True,
    )
    assert result.requested is True
    assert result.attempted is False
    assert result.block_reason == "event alerts disabled"
    assert result.would_send_items == 2
    assert result.lane_items_attempted[event_alpha_notifications.LANE_INSTANT_ESCALATION] == 1
    assert result.lane_items_attempted[event_alpha_notifications.LANE_HEALTH_HEARTBEAT] == 1
    assert sent == []


def test_event_alpha_notification_runs_and_checklist_report_guard_state():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from crypto_rsi_scanner import (
        event_alpha_notification_checklist,
        event_alpha_notification_runs,
        event_alpha_notifications,
        event_provider_status,
    )

    now = datetime(2026, 6, 19, 11, 0, tzinfo=timezone.utc)
    plan = event_alpha_notifications.EventAlphaNotificationPlan(
        heartbeat_due=True,
        cooldown_status=event_alpha_notifications.cooldown_status_by_lane(
            SimpleNamespace(get_meta=lambda key: None),
            cfg=event_alpha_notifications.EventAlphaNotificationConfig(
                notification_scope="namespace",
                artifact_namespace="notify_no_key",
            ),
            now=now,
        ),
        notification_scope="namespace",
        scope_value="notify_no_key",
    )
    status = event_provider_status.EventDiscoveryProviderStatus(
        mode="configured",
        cache_dir="cache",
        lookback_hours=24,
        horizon_days=7,
        sources=(),
        enrichment=(),
        warnings=(),
        next_steps=(),
    )
    checklist = event_alpha_notification_checklist.build_notification_checklist(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        send_guard_enabled=False,
        telegram_ready=False,
        provider_status=status,
        provider_health_rows={
            "coingecko:market_enrichment": {
                "provider_key": "coingecko:market_enrichment",
                "disabled_until": "2026-06-19T12:00:00+00:00",
            }
        },
        plan=plan,
        llm_budget_status="provider=fixture/fixture",
        card_auto_write=True,
        artifact_doctor_status="WARN",
    )
    text = event_alpha_notification_checklist.format_notification_checklist(checklist)
    assert "READY_TO_PREVIEW: yes" in text
    assert "READY_TO_NOTIFY_NOW: no" in text
    assert "send: blocked, RSI_EVENT_ALERTS_ENABLED missing" in text
    assert "send: blocked, TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_IDS missing" in text
    assert "no ready event sources" in text
    assert "Trading action: NONE" in text
    assert "clock: mode=unknown" in text
    assert "event_alpha_notify:notify_no_key:last_sent:daily_digest" in text
    assert "coingecko:market_enrichment disabled_until=2026-06-19T12:00:00+00:00" in text
    dedup_checklist = event_alpha_notification_checklist.build_notification_checklist(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        send_guard_enabled=False,
        telegram_ready=False,
        provider_status=status,
        provider_health_rows={},
        plan=plan,
        llm_budget_status="provider=fixture/fixture",
        card_auto_write=True,
        artifact_doctor_status="WARN",
        preflight_blockers=(
            "send requested/profile requires RSI_EVENT_ALERTS_ENABLED=1",
            "send requested/profile requires Telegram token and chat id configuration",
        ),
    )
    assert dedup_checklist.blockers.count("send: blocked, RSI_EVENT_ALERTS_ENABLED missing") == 1
    assert dedup_checklist.blockers.count("send: blocked, TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_IDS missing") == 1

    llm_checklist = event_alpha_notification_checklist.build_notification_checklist(
        profile="notify_llm",
        artifact_namespace="notify_llm",
        send_guard_enabled=True,
        telegram_ready=True,
        provider_status=status,
        provider_health_rows={},
        plan=plan,
        llm_budget_status="provider=openai/openai",
        card_auto_write=True,
        artifact_doctor_status="WARN",
        preflight_blockers=("OpenAI LLM profile/provider requires OPENAI_API_KEY",),
    )
    llm_text = event_alpha_notification_checklist.format_notification_checklist(llm_checklist)
    assert "use PROFILE=notify_no_key until OPENAI_API_KEY is configured" in llm_text

    result = SimpleNamespace(
        run_id="run-1",
        run_mode="notification_burn_in",
        artifact_namespace="notify_no_key",
        send_lane_items_attempted={"instant_escalation": 1, "health_heartbeat": 1},
        send_lane_items_delivered={"instant_escalation": 0, "health_heartbeat": 0},
        send_heartbeat_due=True,
        send_heartbeat_sent=False,
        send_would_send_items=2,
        send_block_reason="event alerts disabled",
        send_cooldown_blocks={"daily_digest": "cooldown active"},
        notification_scope="namespace",
        notification_scope_value="notify_no_key",
        cycle_completed=False,
        partial_results=True,
        warnings=("rss failed: DNS", "notification_runtime_budget_exhausted"),
    )
    row = event_alpha_notification_runs.notification_run_record(
        result,
        profile="notify_no_key",
        started_at=now,
        finished_at=now,
        telegram_ready=False,
        send_guard_enabled=False,
        plan=plan,
        provider_health_rows={"rss:event_source": {"provider_key": "rss:event_source", "disabled_until": "2026-06-19T12:00:00+00:00"}},
    )
    assert row["would_send_count"] == 2
    assert row["heartbeat_due"] is True
    assert row["cycle_completed"] is False
    assert row["partial_results"] is True
    assert row["runtime_budget_exhausted"] is True
    report = event_alpha_notification_runs.format_notification_runs_report(
        event_alpha_notification_runs.EventAlphaNotificationRunsReadResult(path=__import__("pathlib").Path("/tmp/runs.jsonl"), rows_read=1, rows=[row])
    )
    assert "provider_fail_fast_blocks" in report
    assert "partial_results=yes" in report
    assert "trading action is NONE" in report


def test_event_alpha_degraded_heartbeat_copy_and_delivery():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from crypto_rsi_scanner import event_alpha_notifications

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    sent = []
    result = SimpleNamespace(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        cycle_completed=False,
        partial_results=True,
        warnings=("notification_cycle_failed_soft: RuntimeError", "market_enrichment_live_fetch_failed: OSError"),
        raw_events=0,
        anomaly_lifecycle_entries=0,
        candidates=0,
        watchlist_entries=0,
        alertable=0,
        extraction_rows=(),
        relationship_rows=(),
    )
    send_result = event_alpha_notifications.send_notifications(
        [],
        storage=FakeStorage(),
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(enabled=True, notification_scope="namespace", artifact_namespace="notify_no_key"),
        send_fn=lambda message: sent.append(message) or True,
        now=datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc),
        profile="notify_no_key",
        pipeline_result=result,
        include_health_heartbeat=True,
    )
    assert send_result.heartbeat_due is True
    assert send_result.heartbeat_sent is True
    assert send_result.lane_items_delivered[event_alpha_notifications.LANE_HEALTH_HEARTBEAT] == 1
    message = sent[0]
    assert "Research-only / DAY-1 UNVALIDATED" in message
    assert "Trading action: NONE" in message
    assert "namespace=notify_no_key" in message
    assert "cycle_completed=no" in message
    assert "degraded=yes" in message
    assert "partial_results=yes" in message
    assert "alertable_count=0" in message
    assert "warnings_summary=notification_cycle_failed_soft: RuntimeError" in message


def test_event_alpha_notification_provider_fail_fast_defaults():
    from urllib.error import URLError
    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.client import CoinGeckoClient
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    calls = []

    def failing_opener(request, timeout):
        calls.append((request.full_url, timeout))
        raise URLError("DNS temporary failure in name resolution")

    provider = ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://one.invalid/rss", "https://two.invalid/rss"),
        timeout=5,
        fail_fast_on_error=True,
        opener=failing_opener,
    )
    assert provider.fetch_events(
        __import__("datetime").datetime(2026, 6, 19, tzinfo=__import__("datetime").timezone.utc),
        __import__("datetime").datetime(2026, 6, 20, tzinfo=__import__("datetime").timezone.utc),
    ) == []
    assert len(calls) == 1
    assert any("skipped remaining feeds" in warning for warning in provider.last_warnings)

    original_mode = config.EVENT_ALPHA_RUN_MODE
    original_timeout = config.EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS
    original_fast_fail = config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS
    try:
        config.EVENT_ALPHA_RUN_MODE = "notification_burn_in"
        config.EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS = 4
        config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS = True
        client = CoinGeckoClient()
        assert client.timeout_seconds == 4
        assert client.max_retries == 1
    finally:
        config.EVENT_ALPHA_RUN_MODE = original_mode
        config.EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS = original_timeout
        config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS = original_fast_fail


def test_event_alpha_send_test_refuses_without_guard_and_does_not_send():
    import contextlib
    import io
    from pathlib import Path
    from crypto_rsi_scanner import config, event_alpha_profiles, scanner

    base_attrs = (
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "EVENT_ALPHA_RUN_MODE",
        "EVENT_ALERTS_ENABLED",
        "EVENT_ALERT_MODE",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_IDS",
    )
    notify_profile = event_alpha_profiles.get_profile("notify_no_key")
    attrs = tuple(name for name in dict.fromkeys((*base_attrs, *notify_profile.config_overrides)) if hasattr(config, name))
    original = {name: getattr(config, name) for name in attrs}
    original_send = scanner.send_telegram
    calls = []
    try:
        config.EVENT_ALPHA_ARTIFACT_BASE_DIR = Path("/tmp")
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
        config.EVENT_ALPHA_RUN_MODE = ""
        config.EVENT_ALERTS_ENABLED = False
        config.EVENT_ALERT_MODE = "research_only"
        config.TELEGRAM_BOT_TOKEN = "token"
        config.TELEGRAM_CHAT_IDS = ["chat"]
        scanner.send_telegram = lambda *args, **kwargs: calls.append((args, kwargs)) or True
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_alpha_send_test(profile_name="notify_no_key")
        assert "Refusing Event Alpha test send" in out.getvalue()
        assert calls == []
    finally:
        scanner.send_telegram = original_send
        for name, value in original.items():
            setattr(config, name, value)


def test_event_alpha_notify_cycle_pipeline_exception_fails_soft_and_writes_ledgers():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, event_alpha_profiles, event_alpha_pipeline, scanner

    notify_profile = event_alpha_profiles.get_profile("notify_no_key")
    base_attrs = (
        "DB_PATH",
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "EVENT_ALPHA_RUN_MODE",
        "EVENT_ALERTS_ENABLED",
        "EVENT_ALERT_MODE",
        "EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS",
        "EVENT_RESEARCH_CARDS_AUTO_WRITE",
        "EVENT_RESEARCH_NOW",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_IDS",
    )
    attrs = tuple(name for name in dict.fromkeys((*base_attrs, *notify_profile.config_overrides)) if hasattr(config, name))
    original = {name: getattr(config, name) for name in attrs}
    original_runner = event_alpha_pipeline.run_event_alpha_operating_cycle

    def raising_runner(**kwargs):
        raise RuntimeError("simulated CoinGecko market enrichment crash")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            config.DB_PATH = tmp_path / "scanner.db"
            config.EVENT_ALPHA_ARTIFACT_BASE_DIR = tmp_path / "event_alpha"
            config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
            config.EVENT_ALPHA_RUN_MODE = ""
            config.EVENT_ALERTS_ENABLED = False
            config.EVENT_ALERT_MODE = "research_only"
            config.EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS = True
            config.EVENT_RESEARCH_CARDS_AUTO_WRITE = False
            config.EVENT_RESEARCH_NOW = "2026-06-15T16:00:00Z"
            config.TELEGRAM_BOT_TOKEN = ""
            config.TELEGRAM_CHAT_IDS = []
            event_alpha_pipeline.run_event_alpha_operating_cycle = raising_runner
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_notify_cycle(profile_name="notify_no_key", send=True)
            text = out.getvalue()
            assert "notification_cycle_failed_soft: RuntimeError" in text
            assert "fixed research clock blocks notification send" in text
            assert "cycle_completed=false" in text
            assert "partial_results=true" in text

            namespace_dir = tmp_path / "event_alpha" / "notify_no_key"
            run_rows = [
                json.loads(line)
                for line in (namespace_dir / "event_alpha_runs.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            notification_rows = [
                json.loads(line)
                for line in (namespace_dir / "event_alpha_notification_runs.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert run_rows[-1]["notification_burn_in"] is True
            assert run_rows[-1]["cycle_completed"] is False
            assert run_rows[-1]["partial_results"] is True
            assert run_rows[-1]["notification_summary"]["heartbeat_due"] is True
            assert notification_rows[-1]["would_send_count"] == 1
            assert notification_rows[-1]["heartbeat_due"] is True
            assert notification_rows[-1]["cycle_completed"] is False
            assert notification_rows[-1]["partial_results"] is True
            assert any("notification_cycle_failed_soft: RuntimeError" in item for item in notification_rows[-1]["warnings"])
            assert any("fixed research clock blocks notification send" in item for item in notification_rows[-1]["warnings"])
            assert run_rows[-1]["clock_mode"] == "fixed"
            assert "fixed research clock" in (run_rows[-1]["send_block_reason"] or "")
            alert_path = namespace_dir / "event_alpha_alerts.jsonl"
            assert not alert_path.exists() or alert_path.read_text(encoding="utf-8").strip() == ""
        finally:
            event_alpha_pipeline.run_event_alpha_operating_cycle = original_runner
            for name, value in original.items():
                setattr(config, name, value)


def test_event_alpha_run_ledger_records_send_accounting():
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_pipeline,
        event_alpha_run_ledger,
        event_alpha_router,
        event_watchlist,
    )
    from crypto_rsi_scanner.event_models import EventDiscoveryResult

    now = datetime(2026, 6, 18, 13, 0, tzinfo=timezone.utc)

    def empty_loader(observed, raw_event_transform):
        return EventDiscoveryResult((), (), (), (), ())

    with tempfile.TemporaryDirectory() as tmp:
        watch_path = Path(tmp) / "watchlist.jsonl"
        no_decisions = event_alpha_pipeline.run_event_alpha_operating_cycle(
            load_discovery_result=empty_loader,
            now=now,
            watchlist_cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=watch_path),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=False,
            route=True,
            send=True,
            send_callback=lambda decisions: event_alpha_pipeline.EventAlphaSendResult(
                requested=True,
                attempted=True,
                success=True,
                items_attempted=len(decisions),
                items_delivered=len(decisions),
            ),
        )
        assert no_decisions.send_requested is True
        assert no_decisions.send_attempted is False
        assert no_decisions.send_block_reason == "no alertable route decisions"
        cfg = event_alpha_run_ledger.EventAlphaRunLedgerConfig(path=Path(tmp) / "runs.jsonl")
        row = event_alpha_run_ledger.append_run_record(
            no_decisions,
            cfg=cfg,
            profile="fixture",
            started_at=now,
            finished_at=now,
            with_llm=False,
            send_requested=True,
        )
        assert row["send_requested"] is True
        assert row["send_attempted"] is False
        assert row["send_success"] is False
        assert row["send_block_reason"] == "no alertable route decisions"

        delivered = event_alpha_pipeline._normalize_send_result(True, [])
        delivered_result = event_alpha_pipeline._with_send_result(no_decisions, delivered)
        delivered_result = replace(
            delivered_result,
            clock_status={
                "clock_mode": "fixed",
                "research_now": "2026-06-15T16:00:00+00:00",
                "wall_clock_now": "2026-06-20T12:00:00+00:00",
                "fixed_clock_age_hours": 116.0,
            },
        )
        row2 = event_alpha_run_ledger.append_run_record(
            delivered_result,
            cfg=cfg,
            profile="fixture",
            started_at=now,
            finished_at=now,
            with_llm=False,
            send_requested=True,
        )
        assert row2["send_attempted"] is True
        assert row2["send_success"] is True
        assert row2["clock_mode"] == "fixed"
        assert row2["fixed_clock_age_hours"] == 116.0
        assert "send=0/0" in event_alpha_run_ledger.format_run_ledger_report(
            event_alpha_run_ledger.load_run_records(cfg.path)
        )


def test_event_alpha_feedback_marks_watchlist_rows_and_missed_items():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_feedback, event_playbooks, event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="feed|solana|proxy_attention|SpaceX|",
        cluster_id="spacex|ipo_proxy|2026-06-18",
        event_id="feed",
        coin_id="solana",
        symbol="SOL",
        relationship_type="proxy_attention",
        external_asset="SpaceX",
        event_time=None,
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        previous_state="RADAR",
        first_seen_at="2026-06-18T12:00:00+00:00",
        last_seen_at="2026-06-18T13:00:00+00:00",
        source_count=2,
        highest_score=74,
        latest_score=74,
        latest_tier="WATCHLIST",
        latest_event_name="SOL proxy attention",
        latest_source="fixture",
        latest_playbook_type=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        latest_playbook_score=74,
        latest_playbook_action="watchlist",
        should_alert=True,
    )
    with tempfile.TemporaryDirectory() as tmp:
        cfg = event_feedback.EventFeedbackConfig(path=Path(tmp) / "feedback.jsonl")
        marked = event_feedback.mark_feedback(
            "SOL",
            "useful",
            watchlist_entries=[entry],
            cfg=cfg,
            marked_by="tester",
            notes="good lead",
            now=datetime(2026, 6, 18, 14, 0, tzinfo=timezone.utc),
        )
        assert marked.label == event_feedback.EventFeedbackLabel.USEFUL.value
        assert marked.key == entry.key
        assert marked.state == event_watchlist.EventWatchlistState.WATCHLIST.value
        assert "No live signal" in event_feedback.format_feedback_record(marked, path=cfg.path)
        by_alert_id = event_feedback.mark_feedback(
            f"ea:{entry.key}",
            "watch",
            watchlist_entries=[entry],
            cfg=cfg,
            marked_by="tester",
        )
        assert by_alert_id.key == entry.key

        try:
            event_feedback.mark_feedback("UNKNOWN", "junk", watchlist_entries=[entry], cfg=cfg)
        except ValueError as exc:
            assert "label=missed" in str(exc)
        else:
            raise AssertionError("expected unmatched non-missed feedback to fail")

        missed = event_feedback.mark_feedback(
            "missed velvet article",
            "missed",
            watchlist_entries=[entry],
            cfg=cfg,
            marked_by="tester",
        )
        assert missed.key is None
        assert missed.label == event_feedback.EventFeedbackLabel.MISSED.value
        loaded = event_feedback.load_feedback(cfg.path)
        assert loaded.rows_read == 3
        report = event_feedback.format_feedback_report(loaded)
        assert "useful=1" in report
        assert "watch=1" in report
        assert "missed=1" in report


def test_event_alpha_status_profile_budget_and_unknown_profile():
    import contextlib
    import io
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
    try:
        profile = event_alpha_profiles.get_profile("full_llm_live")
        assert profile.config_overrides["EVENT_LLM_MAX_CALLS_PER_RUN"] > 0
        assert profile.config_overrides["EVENT_LLM_MAX_CALLS_PER_DAY"] > 0
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
        assert "watchlist_monitor:" in profile_out.getvalue()
        assert "- READY project_blog_rss" in full_llm_out.getvalue()
        assert "- READY project_blog_rss" in send_out.getvalue()

        bad_out = io.StringIO()
        with contextlib.redirect_stdout(bad_out):
            scanner.event_alpha_status(profile_name="missing-profile")
        assert "unknown Event Alpha profile" in bad_out.getvalue()
    finally:
        for name, value in original.items():
            setattr(config, name, value)


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
            latest_score_components={"derivatives_crowding": 55, "cluster_confidence": 70},
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


def test_event_alpha_missed_calibration_and_research_card_reports():
    from crypto_rsi_scanner import (
        event_alpha_calibration,
        event_alpha_missed,
        event_alpha_router,
        event_graph,
        event_playbooks,
        event_research_cards,
        event_watchlist,
    )
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent
    from pathlib import Path

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="cup|chiliz|fan_sports_event",
        cluster_id="cup|sports|2026-06-20",
        event_id="chz-event",
        coin_id="chiliz",
        symbol="CHZ",
        relationship_type="proxy_attention",
        external_asset="World Cup",
        event_time="2026-06-20T18:00:00+00:00",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state="WATCHLIST",
        first_seen_at="2026-06-18T10:00:00+00:00",
        last_seen_at="2026-06-18T12:00:00+00:00",
        source_count=3,
        highest_score=86,
        latest_score=86,
        latest_tier="HIGH_PRIORITY_WATCH",
        latest_event_name="CHZ World Cup fan token surge",
        latest_source="fixture",
        latest_playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
        latest_rule_playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
        latest_effective_playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
        latest_playbook_score=86,
        latest_playbook_action="high_priority_watch",
        latest_llm_asset_role="proxy_instrument",
        latest_llm_confidence=0.88,
        latest_score_components={"cluster_confidence": 78, "derivatives_crowding": 20},
        latest_market_snapshot={"price": 0.21, "return_24h": 0.18},
        alert_history=[{"observed_at": "2026-06-18T12:00:00+00:00", "state": "HIGH_PRIORITY", "tier": "HIGH_PRIORITY_WATCH", "score": 86}],
        should_alert=True,
    )
    alerts = [{
        "alert_key": entry.key,
        "asset_symbol": "CHZ",
        "asset_coin_id": "chiliz",
        "event_name": entry.latest_event_name,
        "tier": "HIGH_PRIORITY_WATCH",
        "playbook_type": entry.latest_playbook_type,
        "source": "fixture",
        "feedback_label": "useful",
        "primary_horizon_return": 0.12,
        "mfe_mae_ratio": 1.8,
        "direction_hit": True,
        "volatility_hit": True,
        "llm_asset_role": "proxy_instrument",
        "score_components": {"cluster_confidence": 78},
    }]
    missed = event_alpha_missed.detect_missed_opportunities(
        [
            {
                "id": "new-pump",
                "symbol": "pump",
                "name": "New Pump",
                "current_price": 2.0,
                "price_change_percentage_24h_in_currency": 150,
                "total_volume": 10000000,
                "market_cap": 20000000,
            },
            {
                "id": "chiliz",
                "symbol": "chz",
                "name": "Chiliz",
                "current_price": 0.21,
                "price_change_percentage_24h_in_currency": 150,
            },
        ],
        alert_rows=alerts,
        watchlist_entries=[entry],
    )
    assert [row.symbol for row in missed.rows] == ["PUMP"]
    assert missed.rows[0].failure_stage == "no_source_event"
    assert "PUMP crypto catalyst" in missed.rows[0].suggested_queries
    missed_report = event_alpha_missed.format_missed_report(missed)
    assert "missed=1" in missed_report

    url_only_raw = RawDiscoveredEvent(
        raw_id="url-only",
        provider="gdelt",
        fetched_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        published_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        source_url="https://search.example.test/?q=PUMPUSDT",
        title="Market update",
        body="No asset identity in the source text.",
        raw_json={},
        source_confidence=0.60,
        content_hash="url-only",
    )
    url_only = event_alpha_missed.detect_missed_opportunities(
        [{
            "id": "new-pump",
            "symbol": "pump",
            "name": "New Pump",
            "price_change_percentage_24h_in_currency": 150,
        }],
        raw_events=[url_only_raw],
    )
    assert url_only.rows[0].failure_stage == "no_source_event"
    assert "weak_url_only_identity_hint" in url_only.rows[0].reason

    body_raw = RawDiscoveredEvent(
        raw_id="body-identity",
        provider="gdelt",
        fetched_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        published_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        source_url="https://example.test/article",
        title="PUMPUSDT doubles before listing rumors",
        body="PUMPUSDT volume spiked after a catalyst rumor.",
        raw_json={},
        source_confidence=0.80,
        content_hash="body-identity",
    )
    body_identity = event_alpha_missed.detect_missed_opportunities(
        [{
            "id": "new-pump",
            "symbol": "pump",
            "name": "New Pump",
            "price_change_percentage_24h_in_currency": 150,
        }],
        raw_events=[body_raw],
    )
    assert body_identity.rows[0].failure_stage == "resolver_missed_asset"

    metadata_raw = RawDiscoveredEvent(
        raw_id="metadata-bitcoin",
        provider="Bitcoin World",
        fetched_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        published_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        source_url="https://example.test/market",
        title="SpaceX market opens",
        body="The article is about an external catalyst, not the asset.",
        raw_json={"publisher": "Bitcoin World"},
        source_confidence=0.70,
        content_hash="metadata-bitcoin",
    )
    metadata_only = event_alpha_missed.detect_missed_opportunities(
        [{
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "price_change_percentage_24h_in_currency": 150,
        }],
        raw_events=[metadata_raw],
    )
    assert metadata_only.rows[0].failure_stage == "no_source_event"
    assert "metadata_only_identity_hint" in metadata_only.rows[0].reason

    calibration = event_alpha_calibration.format_calibration_report(
        alerts,
        feedback_rows=[{"key": entry.key, "label": "useful"}],
        missed_rows=[row.__dict__ for row in missed.rows],
    )
    assert "feedback by playbook" in calibration
    assert "missed opportunities by failure stage" in calibration
    assert "recommendations:" in calibration

    routed = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="watchlist escalation",
    )
    cluster = event_graph.EventCluster(
        schema_version=event_graph.EVENT_GRAPH_SCHEMA_VERSION,
        cluster_id=entry.cluster_id,
        external_asset_slug="world-cup",
        event_type="sports_event",
        event_date_bucket="2026-06-20",
        external_asset="World Cup",
        event_time=pd.Timestamp("2026-06-20T18:00:00Z").to_pydatetime(),
        event_ids=("chz-event", "btc-noise"),
        raw_ids=("raw-chz", "raw-btc"),
        source_urls=("https://sports.example.test/chz", "https://bitcoinworld.example.test/noise"),
        source_count=2,
        independent_source_count=2,
        source_quality_score=80,
        event_time_consensus=90,
        accepted_asset_count=1,
        rejected_asset_count=1,
        cluster_confidence=78,
        evidence=(
            event_graph.ClusterEvidence(
                event_id="chz-event",
                raw_ids=("raw-chz",),
                source_urls=("https://sports.example.test/chz",),
                event_name="CHZ World Cup fan token surge",
                source="sports_fixture",
                first_seen_time=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
                confidence=0.90,
            ),
        ),
        asset_links=(
            event_graph.EventClusterAssetLink(
                cluster_id=entry.cluster_id,
                event_id="chz-event",
                coin_id="chiliz",
                symbol="CHZ",
                playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
                relationship_type="proxy_attention",
                asset_role="proxy_instrument",
                accepted=True,
                link_confidence=0.90,
                classifier_confidence=0.90,
                accepted_kind="proxy",
                accepted_for_playbook=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
            ),
            event_graph.EventClusterAssetLink(
                cluster_id=entry.cluster_id,
                event_id="btc-noise",
                coin_id="bitcoin",
                symbol="BTC",
                playbook_type=event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
                relationship_type="publisher_suffix_false_positive",
                asset_role="source_noise",
                accepted=False,
                link_confidence=0.20,
                classifier_confidence=0.90,
                rejected_reason="publisher/source noise",
            ),
        ),
        warnings=("single source should be reviewed",),
    )
    card = event_research_cards.render_research_card(
        "CHZ",
        watchlist_entries=[entry],
        alert_rows=alerts,
        route_decisions=[routed],
        clusters=[cluster],
    )
    assert card.found is True
    assert "CHZ Event Research Card" in card.markdown
    assert "Evidence Sources" in card.markdown
    assert "Cluster Context" in card.markdown
    assert "Accepted links by kind: proxy=CHZ/chiliz" in card.markdown
    assert "Rejected/noise links: BTC/bitcoin:publisher/source noise" in card.markdown
    assert "World Cup" in card.markdown
    assert ".env" not in card.markdown
    card_by_alert_id = event_research_cards.render_research_card(
        routed.alert_id,
        watchlist_entries=[entry],
        alert_rows=alerts,
        route_decisions=[routed],
        clusters=[cluster],
    )
    assert card_by_alert_id.found is True
    card_dir = __import__("pathlib").Path(__import__("tempfile").mkdtemp())
    written_cards = event_research_cards.write_research_cards(
        card_dir,
        watchlist_entries=[entry],
        alert_rows=alerts,
        route_decisions=[routed],
        selected_tiers=("HIGH_PRIORITY_WATCH",),
    )
    assert any(routed.card_id in str(path) for path in written_cards.card_paths)


def test_event_alpha_eval_fixture_passes():
    from crypto_rsi_scanner import event_alpha_eval

    path = "fixtures/event_discovery/event_alpha_golden_cases.json"
    result = event_alpha_eval.run_eval(path)
    assert result.passed == result.total
    assert result.failures == ()
    assert "PASS" in event_alpha_eval.format_eval_result(result, path)


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
    assert "event-alpha-notification-checklist:" in text
    assert "event-alpha-notification-runs-report:" in text
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
            scanner.event_discovery_report(event_now="2026-06-15T16:00:00Z")
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
        "EVENT_LLM_MAX_CANDIDATES_PER_RUN": config.EVENT_LLM_MAX_CANDIDATES_PER_RUN,
        "EVENT_LLM_MIN_PREFILTER_SCORE": config.EVENT_LLM_MIN_PREFILTER_SCORE,
        "EVENT_LLM_REQUIRE_EVIDENCE_QUOTES": config.EVENT_LLM_REQUIRE_EVIDENCE_QUOTES,
        "EVENT_LLM_CACHE_PATH": config.EVENT_LLM_CACHE_PATH,
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
    config.EVENT_LLM_MAX_CANDIDATES_PER_RUN = 50
    config.EVENT_LLM_MIN_PREFILTER_SCORE = 0
    config.EVENT_LLM_REQUIRE_EVIDENCE_QUOTES = True
    config.EVENT_LLM_CACHE_PATH = None
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
                scanner.event_discovery_refresh(event_now="2026-06-15T16:00:00Z")
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
            scanner._event_discovery_result_from_config = lambda now=None: EventDiscoveryResult(
                raw_events=(),
                normalized_events=(),
                links=(),
                classifications=(),
                candidates=(),
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_discovery_refresh(event_now="2026-06-15T16:00:00Z")
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
                scanner.event_discovery_binance_listen(event_now="2026-06-15T16:00:00Z")
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
                event_now="2026-06-15T16:00:00Z",
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
            scanner.event_discovery_report(event_now="2026-06-15T16:00:00Z")
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
            scanner.event_discovery_report(event_now="2026-06-15T16:00:00Z")
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
            scanner.event_discovery_report(event_now="2026-06-15T16:00:00Z")
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
            scanner.event_discovery_report(event_now="2026-06-15T16:00:00Z")
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
            scanner.event_discovery_report(event_now="2026-06-15T16:00:00Z")
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
            scanner.event_discovery_report(event_now="2026-06-15T16:00:00Z")
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
        assert "sparkline" not in path.read_text(encoding="utf-8")
    finally:
        config.CSV_OUT = orig


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
            "regime": "UPTREND" if setup == "dip_buy" else "DOWNTREND",
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

    mkt_base = {
        ("UPTREND", "BULL", 7): [1.0, -1.0] * 10,
        ("DOWNTREND", "BEAR", 7): [1.0, -1.0] * 10,
    }
    mkt_wf = backtest.format_market_walk_forward(signals, mkt_base, folds=4, min_test_n=1)
    assert "Walk-forward setup × MARKET regime stability" in mkt_wf
    assert "Base = full-period same coin-regime × BTC-market base" in mkt_wf
    assert "dip_buy" in mkt_wf
    assert "BULL" in mkt_wf
    assert "+50" in mkt_wf


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


def test_event_alpha_missed_uses_shared_identity_for_common_words():
    from datetime import datetime, timezone

    from crypto_rsi_scanner import event_alpha_missed
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent

    raw = RawDiscoveredEvent(
        raw_id="raw-hype",
        provider="news",
        fetched_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        source_url="https://example.com/ipo-hype",
        title="IPO hype keeps building before the event",
        body="No token mention appears here.",
        raw_json={},
        source_confidence=0.7,
        content_hash="h",
    )
    market = [{"id": "hyperliquid", "symbol": "hype", "name": "Hyperliquid", "price_change_percentage_24h_in_currency": 180}]
    result = event_alpha_missed.detect_missed_opportunities(market, raw_events=[raw])
    assert result.rows
    assert result.rows[0].failure_stage == "no_source_event"


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


def test_event_source_reliability_report_recommendations():
    from crypto_rsi_scanner import event_source_reliability

    alerts = [
        {"alert_key": "a", "source_provider": "rss", "primary_horizon_return": 0.12, "mfe_mae_ratio": 1.5},
        {"alert_key": "b", "source_provider": "rss", "primary_horizon_return": 0.05, "mfe_mae_ratio": 1.2},
        {"alert_key": "c", "source_provider": "bad", "primary_horizon_return": -0.02, "mfe_mae_ratio": 0.6},
        {"alert_key": "d", "source_provider": "bad", "primary_horizon_return": -0.03, "mfe_mae_ratio": 0.5},
    ]
    feedback = [
        {"key": "a", "label": "useful"},
        {"key": "b", "label": "useful"},
        {"key": "c", "label": "junk"},
        {"key": "d", "label": "junk"},
    ]
    missed = [{"failure_stage": "no_source_event"}, {"failure_stage": "no_source_event"}]
    report = event_source_reliability.format_source_reliability_report(alerts, feedback_rows=feedback, missed_rows=missed)
    assert "positive prior for rss" in report
    assert "tighten or demote bad" in report
    assert "coverage warning" in report


def test_event_alpha_calibration_priors_export():
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import event_alpha_calibration

    alerts = [
        {"alert_key": "a", "playbook_type": "proxy_attention", "source": "rss", "tier": "WATCHLIST", "primary_horizon_return": 0.1},
        {"alert_key": "b", "playbook_type": "proxy_attention", "source": "rss", "tier": "WATCHLIST", "primary_horizon_return": 0.2},
    ]
    feedback = [{"key": "a", "label": "useful"}, {"key": "b", "label": "useful"}]
    out = Path(tempfile.mkdtemp()) / "priors.json"
    payload = event_alpha_calibration.write_calibration_priors(out, alerts, feedback_rows=feedback, min_sample=3)
    assert out.exists()
    assert payload["playbook_priors"]["proxy_attention"]["score_adjustment"] == 3
    assert payload["playbook_priors"]["proxy_attention"]["min_sample_warning"] is True


def test_event_alpha_eval_export_from_feedback_and_missed():
    import json
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import event_alpha_eval_export

    out_dir = Path(tempfile.mkdtemp())
    feedback_result = event_alpha_eval_export.export_cases_from_feedback(
        [{"alert_key": "k1", "event_name": "Bitcoin World article", "asset_symbol": "BTC", "asset_coin_id": "bitcoin"}],
        [{"key": "k1", "label": "junk", "notes": "publisher noise"}],
        out_dir,
    )
    assert feedback_result.proposed_cases == 1
    llm_cases = json.loads((out_dir / "proposed_llm_golden_cases.json").read_text())
    assert llm_cases["cases"][0]["expected_asset_role"] == "source_noise"

    missed_result = event_alpha_eval_export.export_cases_from_missed(
        [{"symbol": "XYZ", "coin_id": "xyz", "name": "XYZ", "move_window": "24h", "return_pct": 1.5, "failure_stage": "resolver_missed_asset", "suggested_queries": ["XYZ catalyst"]}],
        out_dir,
    )
    assert missed_result.proposed_cases == 2
    extraction = json.loads((out_dir / "proposed_llm_extraction_golden_cases.json").read_text())
    assert extraction["cases"][0]["expected_crypto_asset_mentions"][0]["symbol"] == "XYZ"


def test_event_research_cards_write_files_and_index():
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import event_research_cards

    entry = _test_watchlist_entry(state="HIGH_PRIORITY", symbol="VELVET", coin_id="velvet")
    out_dir = Path(tempfile.mkdtemp())
    result = event_research_cards.write_research_cards(out_dir, watchlist_entries=[entry], alert_rows=[], route_decisions=[])
    assert result.cards_written == 1
    assert result.index_path.exists()
    assert "VELVET" in result.card_paths[0].read_text()
    assert result.card_paths[0].name in result.index_path.read_text()


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
    )
    assert "Requested profile: no_key_live" in markdown
    assert "Selected run profile: no_key_live" in markdown
    assert "Profile match: true" in markdown
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


def test_event_provider_health_backoff_and_report():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_provider_health

    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    path = Path(tempfile.mkdtemp()) / "provider_health.json"
    cfg = event_provider_health.EventProviderHealthConfig(
        path=path,
        max_consecutive_failures=2,
        backoff_minutes=15,
    )
    assert event_provider_health.provider_allowed("gdelt", cfg=cfg, now=now).allowed
    event_provider_health.record_provider_failure(
        "gdelt",
        RuntimeError("timeout"),
        cfg=cfg,
        now=now,
        provider_service="gdelt",
        provider_role="event_source",
        provider_kind="event_source",
    )
    event_provider_health.record_provider_failure(
        "gdelt",
        RuntimeError("timeout"),
        cfg=cfg,
        now=now,
        provider_service="gdelt",
        provider_role="event_source",
        provider_kind="event_source",
    )
    event_provider_health.record_provider_success(
        "gdelt",
        cfg=cfg,
        now=now,
        provider_service="gdelt",
        provider_role="catalyst_search",
        provider_kind="catalyst_search",
    )
    decision = event_provider_health.provider_allowed(
        "gdelt",
        cfg=cfg,
        now=now,
        provider_service="gdelt",
        provider_role="event_source",
    )
    assert decision.allowed is False
    assert "backoff" in (decision.reason or "")
    search_decision = event_provider_health.provider_allowed(
        "gdelt",
        cfg=cfg,
        now=now,
        provider_service="gdelt",
        provider_role="catalyst_search",
    )
    assert search_decision.allowed is True
    rows = event_provider_health.load_provider_health(path)
    assert "gdelt:event_source" in rows
    assert "gdelt:catalyst_search" in rows
    text = event_provider_health.format_provider_health_report(rows)
    assert "gdelt" in text
    assert "failures=2" in text
    assert "service health:" in text
    assert "role health:" in text
    assert "event_source:" in text
    assert "catalyst_search:" in text

    legacy_path = Path(tempfile.mkdtemp()) / "legacy_provider_health.json"
    legacy_until = (now.replace(hour=11)).isoformat()
    legacy_path.write_text(
        json.dumps({"providers": {"gdelt": {"disabled_until": legacy_until, "consecutive_failures": 2}}}),
        encoding="utf-8",
    )
    legacy_cfg = event_provider_health.EventProviderHealthConfig(path=legacy_path)
    legacy_decision = event_provider_health.provider_allowed(
        "gdelt",
        cfg=legacy_cfg,
        now=now,
        provider_service="gdelt",
        provider_role="event_source",
    )
    assert legacy_decision.allowed is False


def test_event_provider_health_wraps_event_and_enrichment_providers():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_provider_health
    from crypto_rsi_scanner.event_providers.coingecko_universe import CoinGeckoUniverseProvider

    now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
    path = Path(tempfile.mkdtemp()) / "provider_health.json"
    cfg = event_provider_health.EventProviderHealthConfig(
        path=path,
        max_consecutive_failures=2,
        backoff_minutes=15,
    )

    class FlakyEventProvider:
        name = "flaky_gdelt"

        def __init__(self):
            self.calls = 0

        def fetch_events(self, start, end):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary timeout")
            return []

    flaky = FlakyEventProvider()
    wrapped = event_provider_health.HealthCheckedEventProvider(flaky, cfg=cfg)
    assert wrapped.fetch_events(now, now) == []
    assert wrapped.last_warnings
    assert wrapped.fetch_events(now, now) == []
    row = event_provider_health.load_provider_health(path)["flaky_gdelt:event_source"]
    assert row["consecutive_failures"] == 0
    assert row["provider_kind"] == "event_source"
    assert row["provider_role"] == "event_source"

    skip_path = Path(tempfile.mkdtemp()) / "skip_health.json"
    skip_now = datetime.now(timezone.utc)
    skip_cfg = event_provider_health.EventProviderHealthConfig(
        path=skip_path,
        max_consecutive_failures=1,
        backoff_minutes=15,
    )
    event_provider_health.record_provider_failure(
        "skipped_source",
        RuntimeError("dns failure"),
        cfg=skip_cfg,
        now=skip_now,
        provider_kind="event_source",
    )

    class SkippedProvider:
        name = "skipped_source"
        calls = 0

        def fetch_events(self, start, end):
            self.calls += 1
            return ["should not call"]

    skipped = SkippedProvider()
    skipped_wrapped = event_provider_health.HealthCheckedEventProvider(skipped, cfg=skip_cfg)
    assert skipped_wrapped.fetch_events(now, now) == []
    assert skipped.calls == 0
    assert "backoff" in skipped_wrapped.last_warnings[0]

    class FailingUniverse:
        name = "coingecko_universe"

        def fetch_assets(self):
            raise RuntimeError("rate limit")

    assets = event_provider_health.HealthCheckedUniverseProvider(FailingUniverse(), cfg=cfg).fetch_assets()
    assert assets == []
    rows = event_provider_health.load_provider_health(path)
    assert rows["coingecko:universe"]["provider_kind"] == "enrichment"
    assert rows["coingecko:universe"]["provider_role"] == "universe"

    missing_fixture = Path(tempfile.mkdtemp()) / "missing-markets.json"
    real_provider = CoinGeckoUniverseProvider(missing_fixture)
    assert event_provider_health.HealthCheckedUniverseProvider(real_provider, cfg=cfg).fetch_assets() == []
    rows = event_provider_health.load_provider_health(path)
    assert rows["coingecko:universe"]["consecutive_failures"] >= 1
    assert rows["coingecko:universe"]["last_error_class"]
    report = event_provider_health.format_provider_health_report(rows)
    assert "event_source:" in report
    assert "universe:" in report


def test_event_provider_health_wrappers_use_injected_now_and_legacy_signatures():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_provider_health

    now = datetime(2026, 6, 19, 9, 30, tzinfo=timezone.utc)
    path = Path(tempfile.mkdtemp()) / "health.json"
    cfg = event_provider_health.EventProviderHealthConfig(path=path)

    class ClockedEventProvider:
        name = "clocked_events"

        def __init__(self):
            self.now_seen = None

        def fetch_events(self, start, end, now=None):
            self.now_seen = now
            return []

    clocked = ClockedEventProvider()
    assert event_provider_health.HealthCheckedEventProvider(clocked, cfg=cfg).fetch_events(now, now, now=now) == []
    assert clocked.now_seen == now
    rows = event_provider_health.load_provider_health(path)
    assert rows["clocked_events:event_source"]["last_success_at"] == now.isoformat()

    class LegacyUniverse:
        name = "legacy_universe"

        def fetch_assets(self):
            return []

    class ClockedDerivatives:
        name = "clocked_derivatives"

        def __init__(self):
            self.now_seen = None

        def fetch_snapshots(self, now=None):
            self.now_seen = now
            return {}

    assert event_provider_health.HealthCheckedUniverseProvider(LegacyUniverse(), cfg=cfg).fetch_assets(now=now) == []
    clocked_derivatives = ClockedDerivatives()
    assert event_provider_health.HealthCheckedDerivativesProvider(clocked_derivatives, cfg=cfg).fetch_snapshots(now=now) == {}
    assert clocked_derivatives.now_seen == now
    rows = event_provider_health.load_provider_health(path)
    assert rows["legacy_universe:universe"]["last_success_at"] == now.isoformat()
    assert rows["clocked_derivatives:derivatives"]["last_success_at"] == now.isoformat()


def test_event_alpha_priors_adjust_research_score_but_not_triggered_fade():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_alerts, event_alpha_priors

    alerts = event_alerts.build_event_alert_candidates(
        _full_event_discovery_fixture_result(),
        cfg=event_alerts.EventAlertConfig(),
    )
    triggered = next(alert for alert in alerts if alert.tier == event_alerts.EventAlertTier.TRIGGERED_FADE)
    non_triggered = next(alert for alert in alerts if alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE)
    path = Path(tempfile.mkdtemp()) / "priors.json"
    path.write_text(json.dumps({
        "schema_version": "event_alpha_priors_v1",
        "generated_at": "2026-06-18T00:00:00+00:00",
        "playbook_priors": {
            triggered.effective_playbook_type: {"multiplier": 0.2},
            non_triggered.effective_playbook_type: {"multiplier": 1.3},
        },
    }), encoding="utf-8")
    adjusted = event_alpha_priors.apply_priors_to_alerts(
        [triggered, non_triggered],
        cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=True, path=path, min_multiplier=0.7, max_multiplier=1.3),
        alert_cfg=event_alerts.EventAlertConfig(),
    )
    adjusted_triggered = next(alert for alert in adjusted if alert.symbol == triggered.symbol)
    adjusted_other = next(alert for alert in adjusted if alert.symbol == non_triggered.symbol)
    assert adjusted_triggered.tier == event_alerts.EventAlertTier.TRIGGERED_FADE
    assert adjusted_triggered.score_after_priors >= int(triggered.opportunity_score * 0.69)
    assert adjusted_other.score_before_priors == non_triggered.opportunity_score
    assert adjusted_other.score_after_priors >= adjusted_other.score_before_priors
    assert adjusted_other.prior_file == str(path)


def test_event_alpha_priors_shadow_report_and_raw_replay_are_local():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_alerts, event_alpha_priors, event_alpha_replay, event_alpha_router, event_discovery

    result = _full_event_discovery_fixture_result()
    alerts = event_alerts.build_event_alert_candidates(result)
    non_triggered = next(alert for alert in alerts if alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE)
    tmp = Path(tempfile.mkdtemp())
    priors_path = tmp / "priors.json"
    priors_path.write_text(json.dumps({
        "schema_version": "event_alpha_priors_v1",
        "generated_at": "2026-06-18T00:00:00+00:00",
        "playbook_priors": {non_triggered.effective_playbook_type: {"multiplier": 1.2}},
    }), encoding="utf-8")
    shadow = event_alpha_priors.compare_priors_shadow(
        alerts,
        cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=False, path=priors_path),
        alert_cfg=event_alerts.EventAlertConfig(),
    )
    assert shadow.rows
    text = event_alpha_priors.format_priors_shadow_report(shadow)
    assert "EVENT ALPHA PRIORS SHADOW REPORT" in text
    assert "No sends" in text

    _events_path, aliases_path = _event_discovery_fixture_paths()
    market_rows = event_alpha_replay.load_market_rows(_coingecko_universe_fixture_path())
    assets = event_discovery.load_discovery_assets(aliases_path, universe_path=_coingecko_universe_fixture_path())
    replay = event_alpha_replay.replay_from_raw_events(
        raw_events=result.raw_events,
        assets=assets,
        market_rows=market_rows,
        priors_cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=True, path=priors_path),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert replay.raw_events == len(result.raw_events)
    assert replay.candidates > 0
    replay_text = event_alpha_replay.format_replay_report(replay)
    assert "local artifacts only" in replay_text
    assert "No live providers" in replay_text
    comparison = event_alpha_replay.compare_replay_policies(
        raw_events=result.raw_events,
        assets=assets,
        market_rows=market_rows,
        policies=("baseline", "priors", "router_threshold_variant", "profile_variant"),
        priors_cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=True, path=priors_path),
        router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True, score_jump_threshold=20),
        profile_variant_router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True, score_jump_threshold=5),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert [row.policy for row in comparison.rows] == [
        "baseline",
        "priors",
        "router_threshold_variant",
        "profile_variant",
    ]
    assert comparison.diffs
    assert any(diff.policy == "priors" and diff.score_delta for diff in comparison.diffs)
    comparison_text = event_alpha_replay.format_replay_comparison_report(comparison)
    assert "EVENT ALPHA REPLAY POLICY COMPARISON" in comparison_text
    assert "candidate diffs:" in comparison_text
    assert "local-only" in comparison_text
    assert "router_threshold_variant" in comparison_text


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
        derivatives_rows=[{"coin_id": "velvet", "derivatives_crowding": 68}],
        supply_rows=[{"coin_id": "velvet", "supply_pressure": 72}],
    )
    assert enrichment.assets_requested == 1
    assert enrichment.derivatives["velvet"]["derivatives_crowding"] == 68
    assert enrichment.supply["velvet"]["supply_pressure"] == 72
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


def test_event_alpha_daily_brief_replay_retention_and_unmatched_feedback():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_daily_brief,
        event_alpha_replay,
        event_alpha_retention,
        event_feedback,
    )

    entry = _test_watchlist_entry(state="HIGH_PRIORITY", symbol="VELVET", coin_id="velvet")
    markdown = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{
            "run_id": "run-1",
            "run_mode": "burn_in",
            "artifact_namespace": "no_key_live",
            "success": True,
            "raw_events": 2,
            "candidates": 1,
            "alerts": 1,
            "routed": 1,
            "alertable": 0,
            "llm_calls_attempted": 0,
            "llm_skipped_due_budget": 1,
        }],
        alert_rows=[{"run_mode": "burn_in", "artifact_namespace": "no_key_live", "run_id": "run-1", "alert_key": entry.key, "tier": "HIGH_PRIORITY_WATCH", "asset_symbol": "VELVET", "playbook_type": "proxy_attention"}],
        watchlist_entries=[entry],
        provider_health_rows={"gdelt": {"provider_kind": "event_source", "consecutive_failures": 2, "disabled_until": "2026-06-18T10:30:00+00:00"}},
        card_paths=[Path("/tmp/velvet.md")],
    )
    assert "Event Alpha Daily Brief" in markdown
    assert "Why No Alerts" in markdown
    assert "Provider Health" in markdown
    assert "LLM Budget" in markdown
    assert "Watchlist Got Hotter" in markdown
    assert "Calibration Recommendations" in markdown
    assert ".env" not in markdown

    from crypto_rsi_scanner import event_research_cards, event_watchlist_monitor
    entry_fade = __import__("dataclasses").replace(
        entry,
        latest_playbook_type="proxy_fade",
        latest_effective_playbook_type="proxy_fade",
    )
    monitor_row = event_watchlist_monitor.EventWatchlistMonitorRow(
        key=entry_fade.key,
        symbol="VELVET",
        coin_id="velvet",
        state="HIGH_PRIORITY",
        event_name="SpaceX pre-IPO exposure",
        event_time="2026-06-16T00:00:00+00:00",
        event_countdown_hours=None,
        event_age_hours=12.0,
        current_price=1.23,
        return_24h=0.24,
        return_72h=0.72,
        return_7d=1.4,
        volume_to_market_cap=0.4,
        volume_zscore_24h=4.5,
        derivatives_crowding=68,
        supply_pressure=20,
        cluster_confidence=80,
        state_transition_hints=("MARKET_SCORE_JUMP", "DERIVATIVES_HEATED"),
        material_update=True,
    )
    card = event_research_cards.render_research_card(
        entry_fade.key,
        watchlist_entries=[entry_fade],
        alert_rows=[{
            "alert_key": entry_fade.key,
            "asset_symbol": "VELVET",
            "asset_coin_id": "velvet",
            "event_name": "SpaceX pre-IPO exposure",
            "playbook_type": "proxy_fade",
            "expected_direction": "down",
            "primary_horizon": "24h",
            "playbook_invalidation": "Price reclaims event VWAP",
            "score_components": {"external_catalyst": 90, "event_time_quality": 90, "market_move_volume": 80},
        }],
        monitor_rows=[monitor_row],
    )
    assert "## Trade-Readiness Checklist" in card.markdown
    assert "## Latest Monitor Update" in card.markdown
    assert "MARKET_SCORE_JUMP" in card.markdown
    assert "DERIVATIVES_HEATED" in card.markdown
    assert "cannot create TRIGGERED_FADE" in card.markdown
    assert "post-event failure" in card.markdown

    replay = event_alpha_replay.replay_from_artifacts(
        alert_rows=[{"alert_key": "a1", "tier": "WATCHLIST", "route": "RESEARCH_DIGEST", "opportunity_score": 50}],
        watchlist_rows=[{"key": entry.key}],
        priors_enabled=True,
        llm_advisory=True,
    )
    assert replay.alert_rows == 1
    assert "local artifacts only" in event_alpha_replay.format_replay_report(replay)

    tmp = Path(tempfile.mkdtemp())
    feedback_cfg = event_feedback.EventFeedbackConfig(path=tmp / "feedback.jsonl")
    record = event_feedback.mark_feedback(
        "UNKNOWN",
        "junk",
        watchlist_entries=[],
        cfg=feedback_cfg,
        allow_unmatched=True,
        notes="bad key",
    )
    assert record.source == "manual_cli_unmatched"
    assert "warning:" in (record.notes or "")

    runs = tmp / "runs.jsonl"
    alerts = tmp / "alerts.jsonl"
    cards = tmp / "cards"
    cards.mkdir()
    runs.write_text('{"row_type":"event_alpha_run","started_at":"2025-01-01T00:00:00+00:00"}\n', encoding="utf-8")
    alerts.write_text('{"row_type":"event_alpha_alert_snapshot","observed_at":"2025-01-01T00:00:00+00:00"}\n', encoding="utf-8")
    old_card = cards / "old.md"
    old_card.write_text("# old\n", encoding="utf-8")
    cfg = event_alpha_retention.EventAlphaRetentionConfig(
        runs_path=runs,
        alerts_path=alerts,
        cards_dir=cards,
        run_days=1,
        alert_days=1,
        card_days=1,
    )
    dry = event_alpha_retention.prune_event_alpha_artifacts(cfg, confirm=False, now=__import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc))
    assert dry.dry_run is True
    assert dry.runs_pruned == 1
    assert runs.read_text(encoding="utf-8").strip()
    confirmed = event_alpha_retention.prune_event_alpha_artifacts(cfg, confirm=True, now=__import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc))
    assert confirmed.dry_run is False
    assert runs.read_text(encoding="utf-8") == ""


def test_event_alpha_burn_in_scorecard_summarizes_operational_health():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_burn_in, event_alpha_burn_in_checklist

    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    meta = {"profile": "no_key_live", "run_mode": "burn_in", "artifact_namespace": "no_key_live"}
    scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[
            {
                **meta,
                "run_id": "run-1",
                "started_at": "2026-06-19T10:00:00+00:00",
                "success": True,
                "raw_events": 5,
                "candidates": 3,
                "alertable": 1,
            },
            {
                **meta,
                "run_id": "run-2",
                "started_at": "2026-06-18T10:00:00+00:00",
                "success": False,
                "raw_events": 0,
                "candidates": 0,
                "alertable": 0,
            },
        ],
        alert_rows=[
            {
                **meta,
                "run_id": "run-1",
                "observed_at": "2026-06-19T10:01:00+00:00",
                "alert_key": "cluster|velvet|proxy_attention",
                "tier": "WATCHLIST",
                "playbook_type": "proxy_attention",
                "source": "gdelt",
            },
            {
                **meta,
                "run_id": "run-1",
                "observed_at": "2026-06-19T10:02:00+00:00",
                "alert_key": "cluster|btc|source_noise_control",
                "tier": "STORE_ONLY",
                "playbook_type": "source_noise_control",
                "source": "rss",
            },
        ],
        feedback_rows=[
            {
                **meta,
                "marked_at": "2026-06-19T11:00:00+00:00",
                "key": "cluster|btc|source_noise_control",
                "label": "junk",
            },
            {
                **meta,
                "marked_at": "2026-06-19T11:05:00+00:00",
                "key": "cluster|velvet|proxy_attention",
                "label": "useful",
            },
        ],
        outcome_rows=[
            {
                **meta,
                "observed_at": "2026-06-19T12:00:00+00:00",
                "alert_key": "cluster|velvet|proxy_attention",
                "primary_horizon_return": 0.18,
            }
        ],
        missed_rows=[
            {
                **meta,
                "observed_at": "2026-06-19T11:30:00+00:00",
                "failure_stage": "resolver_missed_asset",
            }
        ],
        provider_health_rows={
            "gdelt:event_source": {
                "provider_key": "gdelt:event_source",
                "consecutive_failures": 2,
                "disabled_until": "2026-06-19T12:30:00+00:00",
            }
        },
        llm_budget_rows=[
            {
                **meta,
                "date": "2026-06-19",
                "extractor_calls_attempted": 2,
                "relationship_calls_attempted": 1,
                "cache_hits": 4,
                "cache_misses": 3,
                "skipped_due_budget": 1,
                "estimated_cost_usd": 0.12,
            }
        ],
    )
    text = event_alpha_burn_in.format_burn_in_scorecard(scorecard)
    assert "EVENT ALPHA BURN-IN SCORECARD" in text
    assert "runs=2 successful=1 failed=1" in text
    assert "WATCHLIST=1" in text
    assert "resolver_missed_asset=1" in text
    assert "gdelt:event_source(2)" in text
    assert "calls=3" in text
    assert "artifact coverage:" in text
    assert "alert_snapshots=2" in text
    assert "inspect degraded provider health" in text
    assert "No thresholds, alert tiers, paper trades, live DB rows, or execution were changed." in text
    checklist = event_alpha_burn_in_checklist.build_burn_in_checklist(
        scorecard,
        card_paths=("card.md",),
    )
    assert checklist.ready_for_research_send is False
    assert any("backoff" in item for item in checklist.blockers)
    checklist_text = event_alpha_burn_in_checklist.format_burn_in_checklist(checklist)
    assert "READY_FOR_RESEARCH_SEND: no" in checklist_text

    ready_scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{**meta, "run_id": "ready-run", "started_at": "2026-06-19T10:00:00+00:00", "success": True, "alertable": 1}],
        alert_rows=[{**meta, "run_id": "ready-run", "observed_at": "2026-06-19T10:01:00+00:00", "alert_key": "a", "tier": "WATCHLIST"}],
        feedback_rows=[{**meta, "marked_at": "2026-06-19T11:00:00+00:00", "key": "a", "label": "useful"}],
        outcome_rows=[{**meta, "observed_at": "2026-06-19T12:00:00+00:00", "alert_key": "a", "primary_horizon_return": 0.1}],
        missed_rows=[{**meta, "observed_at": "2026-06-19T12:00:00+00:00", "failure_stage": "unknown"}],
        provider_health_rows={"gdelt:event_source": {"provider_key": "gdelt:event_source", "consecutive_failures": 0}},
    )
    assert event_alpha_burn_in_checklist.build_burn_in_checklist(ready_scorecard).ready_for_research_send is True

    missing_snapshots = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{**meta, "run_id": "missing-run", "started_at": "2026-06-19T10:00:00+00:00", "success": True, "alertable": 1}],
        alert_rows=[],
        missed_rows=[],
        profile="no_key_live",
    )
    assert "alert snapshots missing for alertable runs" in missing_snapshots.coverage_warnings
    assert "provider health missing for live profiles" in missing_snapshots.coverage_warnings
    blocked = event_alpha_burn_in_checklist.build_burn_in_checklist(missing_snapshots)
    assert blocked.ready_for_research_send is False
    assert any("alertable runs" in item for item in blocked.blockers)

    legacy_only = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{"run_id": "legacy", "started_at": "2026-06-19T10:00:00+00:00", "success": True}],
        alert_rows=[{"run_id": "legacy", "observed_at": "2026-06-19T10:01:00+00:00", "alert_key": "legacy-a"}],
    )
    assert legacy_only.run_rows == []
    assert legacy_only.legacy_rows_skipped == 2
    assert "no operational burn-in rows found" in legacy_only.coverage_warnings
    legacy_counted = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{"run_id": "legacy", "started_at": "2026-06-19T10:00:00+00:00", "success": True}],
        include_legacy_artifacts=True,
    )
    assert len(legacy_counted.run_rows) == 1


def test_event_alpha_v1_readiness_health_tuning_and_pack_reports():
    import tempfile
    import zipfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_burn_in_pack,
        event_alpha_health_guard,
        event_alpha_tuning,
        event_alpha_v1_readiness,
        event_research_cards,
    )

    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    run_rows = [
        {"run_id": "no-key-run", "started_at": "2026-06-19T10:00:00+00:00", "profile": "no_key_live", "run_mode": "burn_in", "artifact_namespace": "no_key_live", "success": True, "alertable": 1},
        {"run_id": "research-send-run", "started_at": "2026-06-19T10:05:00+00:00", "profile": "research_send", "run_mode": "operational", "artifact_namespace": "research_send", "success": True, "alertable": 1},
        {"run_id": "full-llm-run", "started_at": "2026-06-19T10:10:00+00:00", "profile": "full_llm_live", "run_mode": "burn_in", "artifact_namespace": "full_llm_live", "success": True, "alertable": 1},
    ]
    alert_rows = [
        {
            "run_id": "no-key-run",
            "run_mode": "burn_in",
            "artifact_namespace": "no_key_live",
            "observed_at": "2026-06-19T10:06:00+00:00",
            "alert_key": "cluster|velvet|proxy_attention",
            "tier": "WATCHLIST",
            "playbook_type": "proxy_attention",
            "source": "gdelt",
            "asset_symbol": "VELVET",
            "asset_coin_id": "velvet",
            "primary_horizon_return": 0.12,
        },
        {
            "run_id": "research-send-run",
            "run_mode": "operational",
            "artifact_namespace": "research_send",
            "observed_at": "2026-06-19T10:07:00+00:00",
            "alert_key": "cluster|btc|source_noise_control",
            "tier": "RADAR_DIGEST",
            "playbook_type": "source_noise_control",
            "source": "rss",
        },
        {
            "run_id": "full-llm-run",
            "run_mode": "burn_in",
            "artifact_namespace": "full_llm_live",
            "observed_at": "2026-06-19T10:08:00+00:00",
            "alert_key": "cluster|llm|proxy_attention",
            "tier": "WATCHLIST",
            "playbook_type": "proxy_attention",
            "source": "gdelt",
        },
    ]
    feedback_rows = [
        {"run_mode": "burn_in", "artifact_namespace": "no_key_live", "marked_at": "2026-06-19T11:00:00+00:00", "key": "cluster|velvet|proxy_attention", "label": "useful", "marked_by": "human"},
        {"run_mode": "operational", "artifact_namespace": "research_send", "marked_at": "2026-06-19T11:01:00+00:00", "key": "cluster|btc|source_noise_control", "label": "junk", "marked_by": "human"},
        {"run_mode": "operational", "artifact_namespace": "research_send", "marked_at": "2026-06-19T11:02:00+00:00", "key": "cluster|btc|source_noise_control", "label": "junk", "marked_by": "human"},
    ]
    missed_rows = [
        {"run_mode": "burn_in", "artifact_namespace": "no_key_live", "observed_at": "2026-06-19T11:30:00+00:00", "failure_stage": "resolver_missed_asset"},
        {"run_mode": "operational", "artifact_namespace": "research_send", "observed_at": "2026-06-19T11:31:00+00:00", "failure_stage": "resolver_missed_asset"},
    ]
    health_rows = {"gdelt:event_source": {"provider_key": "gdelt:event_source", "consecutive_failures": 0}}
    readiness = event_alpha_v1_readiness.build_v1_readiness(
        run_rows=run_rows,
        alert_rows=alert_rows,
        feedback_rows=feedback_rows,
        missed_rows=missed_rows,
        provider_health_rows=health_rows,
        outcome_rows=alert_rows,
        now=now,
    )
    readiness_text = event_alpha_v1_readiness.format_v1_readiness_report(readiness)
    assert "READY_FOR_CALIBRATED_RESEARCH_SEND: yes" in readiness_text
    assert "READY_FOR_FULL_LLM_LIVE: yes" in readiness_text
    assert "profile matrix:" in readiness_text

    day1 = event_alpha_v1_readiness.build_v1_readiness(
        run_rows=[],
        provider_health_rows={},
        now=now,
        profiles=("notify_no_key", "research_send"),
    )
    day1_text = event_alpha_v1_readiness.format_v1_readiness_report(day1)
    assert "READY_TO_START_DAY1_NOTIFICATIONS: yes" in day1_text
    assert "READY_FOR_CALIBRATED_RESEARCH_SEND: no" in day1_text
    assert "Day-1 notifications are unvalidated research output" in day1_text

    guard = event_alpha_health_guard.evaluate_health_guard(
        run_rows=run_rows,
        alert_rows=alert_rows,
        watchlist_entries=[],
        provider_health_rows=health_rows,
        cfg=event_alpha_health_guard.EventAlphaHealthGuardConfig(require_profile="no_key_live"),
        now=now,
    )
    assert guard.status == "HEALTHY"
    assert "profile_mismatch" not in guard.reason_codes
    stale = event_alpha_health_guard.evaluate_health_guard(
        run_rows=[{"run_id": "stale", "started_at": "2026-06-18T00:00:00+00:00", "profile": "no_key_live", "run_mode": "burn_in", "artifact_namespace": "no_key_live", "success": True}],
        cfg=event_alpha_health_guard.EventAlphaHealthGuardConfig(max_run_age_hours=6, max_success_age_hours=12),
        now=now,
    )
    assert stale.status == "STALE"

    worksheet = event_alpha_tuning.build_tuning_worksheet(
        alert_rows=alert_rows,
        feedback_rows=feedback_rows,
        missed_rows=missed_rows,
        run_rows=run_rows,
    )
    worksheet_text = event_alpha_tuning.format_tuning_worksheet(worksheet)
    assert "resolver_missed_asset" in worksheet_text
    assert "source_noise_control" in worksheet_text
    assert "No thresholds" in worksheet_text

    entry = _test_watchlist_entry(state="HIGH_PRIORITY", symbol="VELVET", coin_id="velvet")
    card = event_research_cards.render_research_card(
        entry.key,
        watchlist_entries=[entry],
        alert_rows=alert_rows,
        feedback_rows=feedback_rows,
        outcome_rows=alert_rows,
    )
    assert "## Lifecycle Timeline" in card.markdown
    assert "## Artifact Lineage" in card.markdown
    assert "feedback: useful" in card.markdown
    assert "outcome:" in card.markdown

    tmp = Path(tempfile.mkdtemp())
    cards = tmp / "cards"
    cards.mkdir()
    (cards / "card.md").write_text("# Card\nOPENAI_API_KEY\n", encoding="utf-8")
    (cards / ".env").write_text("SECRET=1\n", encoding="utf-8")
    out = tmp / "pack.zip"
    pack = event_alpha_burn_in_pack.export_burn_in_pack(
        out,
        daily_brief="# Daily\n",
        burn_in_scorecard="scorecard\n",
        v1_readiness=readiness_text,
        health_guard=event_alpha_health_guard.format_health_guard_report(guard),
        tuning=worksheet_text,
        run_rows=run_rows,
        alert_rows=alert_rows,
        feedback_rows=feedback_rows,
        missed_rows=missed_rows,
        provider_health_rows=health_rows,
        cards_dir=cards,
    )
    assert pack.files_written >= 10
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "reports/v1_readiness.txt" in names
        assert "reports/artifact_doctor.txt" in names
        assert "cards/card.md" in names
        assert "cards/.env" not in names
        assert "OPENAI_API_KEY" not in zf.read("cards/card.md").decode()


def test_makefile_has_event_alpha_burn_in_and_priors_targets():
    text = __import__("pathlib").Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-priors-shadow-report:" in text
    assert "event-alpha-burn-in-no-key:" in text
    assert "event-alpha-burn-in-llm:" in text
    assert "event-alpha-burn-in-scorecard:" in text
    assert "event-alpha-burn-in-checklist:" in text
    assert "event-alpha-v1-readiness:" in text
    assert "event-alpha-health-guard:" in text
    assert "event-alpha-artifact-doctor:" in text
    assert "event-alpha-preflight:" in text
    assert "event-alpha-notify-cycle:" in text
    assert "event-alpha-notify-no-key:" in text
    assert "event-alpha-notify-llm:" in text
    assert "event-alpha-notify-preview:" in text
    assert "event-alpha-send-test:" in text
    assert "event-alpha-tuning-worksheet:" in text
    assert "event-alpha-export-burn-in-pack:" in text
    assert "event-alpha-launchd-template:" in text
    assert "event-alpha-weekly-review:" in text
    assert "--event-alpha-priors-shadow-report" in text
    assert "--event-alpha-v1-readiness" in text
    assert "--event-alpha-health-guard" in text
    assert "--event-alpha-artifact-doctor" in text
    assert "--event-alpha-preflight" in text
    assert "--event-alpha-notify-cycle --event-alpha-profile $(PROFILE) --event-alert-send" in text
    assert "--event-alpha-notify-preview --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-notification-checklist --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-notification-runs-report" in text
    assert "--event-alpha-send-test --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-tuning-worksheet" in text
    assert "--event-alpha-export-burn-in-pack" in text
    assert __import__("pathlib").Path("research/event_alpha_launchd_template.plist").exists()
    assert __import__("pathlib").Path("research/event_alpha_cron_example.txt").exists()
    burn_in = text.split("event-alpha-burn-in-no-key:", 1)[1].split("event-alpha-burn-in-llm:", 1)[0]
    assert "--event-alert-send" not in burn_in
    assert "--event-alpha-profile no_key_live" in burn_in
    assert "EVENT_ALPHA_PROFILE_DIR" in text
    llm_burn_in = text.split("event-alpha-burn-in-llm:", 1)[1].split("event-alpha-weekly-review:", 1)[0]
    assert "--event-alpha-profile full_llm_live" in llm_burn_in

    import subprocess
    dry = subprocess.run(
        ["make", "-n", "event-alpha-daily-llm-report", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-profile full_llm_live" in dry
    assert "event_fade_cache/full_llm_live/event_alpha_runs.jsonl" in dry
    assert "event_fade_cache/no_key_live/event_alpha_runs.jsonl" not in dry

    preflight = subprocess.run(
        ["make", "-n", "event-alpha-preflight", "PROFILE=no_key_live", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-preflight --event-alpha-profile no_key_live" in preflight

    checklist = subprocess.run(
        ["make", "-n", "event-alpha-notification-checklist", "PROFILE=notify_no_key", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-notification-checklist --event-alpha-profile notify_no_key" in checklist


def _test_watchlist_entry(*, state: str, symbol: str, coin_id: str):
    from crypto_rsi_scanner import event_watchlist

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
        latest_score_components={"cluster_confidence": 70},
    )


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
