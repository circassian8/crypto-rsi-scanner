"""Focused Event Alpha provider and discovery tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


@pytest.fixture(autouse=True)
def _isolate_local_discovery_from_live_providers(monkeypatch):
    from crypto_rsi_scanner import config

    _force_disable_event_discovery_live(monkeypatch, config)


def test_local_discovery_tests_force_disable_all_live_provider_flags():
    from crypto_rsi_scanner import config

    assert all(
        getattr(config, name) is False
        for name in _EVENT_DISCOVERY_LIVE_FLAG_NAMES
    )


def test_event_discovery_cache_writes_point_in_time_jsonl_artifacts():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.cache as event_cache

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
            "event_source_independence_contracts",
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
        stack = list(snapshot_rows)
        references = []
        inline_contracts = []
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                if value.get("schema_id") == "event_alpha.source_independence_reference":
                    references.append(value)
                    continue
                if value.get("schema_id") == "event_alpha.source_independence":
                    inline_contracts.append(value)
                    continue
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
        assert references
        assert inline_contracts == []
        assert len(
            list((cache_dir / "event_source_independence_contracts").iterdir())
        ) == len(
            {
                (row["contract_digest"], row["blob_fingerprint"]["sha256"])
                for row in references
            }
        )
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
        assert latest_velvet["data_quality"]["source_independence"]["schema_id"] == (
            "event_alpha.source_independence"
        )


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
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult

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
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.artifacts.cache as event_cache
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult

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
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
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
