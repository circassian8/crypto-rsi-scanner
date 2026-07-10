"""Focused provider/readiness package architecture tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


def test_live_provider_readiness_smoke_new_package_path_is_no_call():
    from crypto_rsi_scanner.event_alpha.providers import live_provider_readiness

    with TemporaryDirectory() as tmp:
        report = live_provider_readiness.build_readiness_report(
            profile="fixture",
            artifact_namespace="provider_readiness_pytest",
            smoke_mode=True,
            now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        )
        json_path, md_path = live_provider_readiness.write_readiness_artifacts(report, tmp)
        payload = json.loads(json_path.read_text(encoding="utf-8"))

    providers = {row["provider_name"]: row for row in payload["providers"]}
    assert payload["live_calls_allowed"] is False
    assert providers["coinalyze"]["live_call_allowed"] is False
    assert providers["bybit_announcements_public"]["live_call_allowed"] is False
    assert providers["geckoterminal"]["live_call_allowed"] is False
    assert md_path.name == live_provider_readiness.READINESS_MD


# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})

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


def test_event_provider_health_preserves_cryptopanic_safe_error_class():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health

    with tempfile.TemporaryDirectory() as tmp:
        cfg = event_provider_health.EventProviderHealthConfig(path=Path(tmp) / "provider_health.jsonl")
        event_provider_health.record_provider_failure(
            "cryptopanic_live_news",
            "CryptoPanic live news fetch failed: json_parse_error",
            cfg=cfg,
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
            provider_service="cryptopanic",
            provider_role="event_source",
        )
        rows = event_provider_health.load_provider_health(cfg.path)
        row = rows["cryptopanic:event_source"]
        assert row["last_error_class"] == "json_parse_error"


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


def test_event_alpha_report_context_and_preflight_are_profile_scoped():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.config.preflight as event_alpha_preflight
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

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
        "EVENT_LLM_ENABLED",
        "EVENT_LLM_PROVIDER",
        "EVENT_LLM_EXTRACTOR_ENABLED",
        "EVENT_LLM_EXTRACTOR_PROVIDER",
        "EVENT_LLM_CATALYST_FRAMES_ENABLED",
        "EVENT_LLM_CATALYST_FRAMES_PROVIDER",
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
            config.EVENT_LLM_ENABLED = False
            config.EVENT_LLM_PROVIDER = "fixture"
            config.EVENT_LLM_EXTRACTOR_ENABLED = False
            config.EVENT_LLM_EXTRACTOR_PROVIDER = "fixture"
            config.EVENT_LLM_CATALYST_FRAMES_ENABLED = False
            config.EVENT_LLM_CATALYST_FRAMES_PROVIDER = "fixture"
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
            assert "- run_ledger_path: event_alpha_runs.jsonl" in text
            assert str(root) not in text
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
            assert "- run_ledger_path: event_alpha_runs.jsonl" in text
            assert str(no_key / "event_alpha_runs.jsonl") not in text
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
            assert "- run_ledger_path: event_alpha_runs.jsonl" in text
            assert str(custom / "event_alpha_runs.jsonl") not in text
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


def test_event_discovery_transform_applies_llm_hints_before_resolver_validation():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
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


def test_event_market_enrichment_live_fail_soft_records_provider_health():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health

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
    from crypto_rsi_scanner.event_alpha.radar import discovery as event_discovery
    from crypto_rsi_scanner.event_alpha.radar import market_enrichment as event_market_enrichment

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


def test_event_catalyst_search_live_provider_adapters_are_evidence_only():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search

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


def test_event_catalyst_search_gdelt_fetch_cap_prevents_repeated_live_failures():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    calls = {"count": 0}

    def failing_opener(request, timeout):
        del request, timeout
        calls["count"] += 1
        raise RuntimeError("HTTP 429")

    queries = tuple(
        event_catalyst_search.SearchQuery(
            anomaly_raw_id=f"market_anomaly:pump:{idx}",
            query=f"PUMP catalyst query {idx}",
            symbol="PUMP",
            rank=idx,
            coin_id="pump-fun",
            project_name="Pump.fun",
            aliases=("Pump.fun",),
        )
        for idx in range(8)
    )
    provider = event_catalyst_search.GdeltCatalystSearchProvider(
        live_enabled=True,
        opener=failing_opener,
        max_fetches_per_search=1,
    )
    result = provider.search(queries, max_results_per_query=1, now=now)
    assert calls["count"] == 1
    assert result.provider_fetch_count == 1
    assert result.provider_cache_misses == 1
    assert result.query_count == 8
    assert any("GDELT live news fetch failed" in warning for warning in result.warnings)
    assert any("fetch cap reached" in warning for warning in result.warnings)


def test_event_candidate_discovery_rejects_common_word_false_positives():
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from datetime import datetime, timezone

    now = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_search",
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.75,
            content_hash=raw_id,
        )

    velvet = event_impact_hypotheses._candidate_asset_from_discovery_raw(
        raw("velvet", "OpenAI pre-IPO crypto venue Velvet", "Velvet offers crypto exposure to private AI shares.")
    )
    assert velvet
    accepted, rejected = event_impact_hypotheses._split_suggested_assets(
        (velvet,),
        external_entities=(),
        text="OpenAI pre-IPO crypto venue Velvet",
    )
    assert accepted and accepted[0]["symbol"] == "VELVET"
    assert not rejected

    for title, symbol, reason in (
        ("IPO hype returns to crypto markets", "HYPE", "generic_symbol_without_project_identity"),
        ("Prime minister talks crypto policy", "PRIME", "common_word_or_title_not_asset_identity"),
        ("Bitcoin World covers SpaceX prediction market", "BTC", "publisher_source_name_not_asset_identity"),
    ):
        row = {"symbol": symbol, "coin_id": symbol.lower(), "source_title": title, "source": "candidate_discovery_search"}
        accepted, rejected = event_impact_hypotheses._split_suggested_assets((row,), external_entities=(), text=title)
        assert not accepted
        assert rejected[0]["rejection_reason"] == reason


def test_event_impact_candidate_discovery_suggests_then_requires_identity_validation():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp-openai-sector",
        event_cluster_id="openai|ipo_proxy|2026-06-20",
        event_type="ipo_proxy",
        external_asset="OpenAI",
        impact_category="ai_ipo_proxy",
        candidate_sectors=("ai_tokens", "tokenized_stock_venues"),
        candidate_symbols=(),
        direction_hint="up_then_fade",
        playbook_hint="ai_ipo_proxy",
        confidence=0.86,
        hypothesis_score=67.0,
        search_query_details=(
            {"query": "OpenAI crypto exposure", "query_type": "candidate_discovery"},
        ),
        search_queries=("OpenAI crypto exposure",),
    )
    query = event_catalyst_search.SearchQuery(
        anomaly_raw_id=hypothesis.hypothesis_id,
        query="OpenAI crypto exposure",
        symbol="SECTOR",
        rank=1,
        query_type="candidate_discovery",
    )
    raw = RawDiscoveredEvent(
        raw_id="velvet-openai-discovery",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/velvet-openai",
        title="VELVET opens OpenAI pre-IPO crypto venue",
        body="Velvet Capital users can trade tokenized stock style exposure to OpenAI.",
        raw_json={
            "asset": {
                "symbol": "VELVET",
                "coin_id": "velvet",
                "name": "Velvet Capital",
                "confidence": 0.90,
            }
        },
        source_confidence=0.90,
        content_hash="velvet-openai-discovery",
    )
    hype = RawDiscoveredEvent(
        raw_id="hype-openai-discovery",
        provider="fixture_search",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/hype-openai",
        title="IPO hype builds around OpenAI",
        body="Generic IPO hype mentions crypto without naming Hyperliquid or $HYPE.",
        raw_json={
            "asset": {
                "symbol": "HYPE",
                "coin_id": "hyperliquid",
                "name": "Hype",
                "confidence": 0.80,
            }
        },
        source_confidence=0.80,
        content_hash="hype-openai-discovery",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(
        rows_by_query={"OpenAI crypto exposure": (raw, hype)}
    )
    executed = event_catalyst_search.run_hypothesis_search(
        (hypothesis,),
        provider,
        cfg=event_catalyst_search.EventImpactHypothesisSearchConfig(
            enabled=True,
            max_hypotheses=1,
            max_queries_per_hypothesis=0,
            max_results_per_query=5,
            min_confidence=0.50,
            min_result_confidence=0.50,
            candidate_discovery_enabled=True,
            max_candidate_discovery_queries=1,
            max_candidate_discovery_results=5,
        ),
        now=now,
    )
    assert any(query.query_type == "candidate_discovery" for query in executed.queries)
    assert len(executed.result_events) >= 1
    discovered_from_search = event_impact_hypotheses.attach_hypothesis_search_samples((hypothesis,), executed)[0]
    assert discovered_from_search.crypto_candidate_assets[0]["symbol"] == "VELVET"
    assert any(row.get("symbol") == "HYPE" for row in discovered_from_search.rejected_candidate_assets)
    assert any(query.get("query_type") == "candidate_discovery" for query in discovered_from_search.executed_queries)
    validated_from_search = event_impact_hypotheses.validate_hypotheses_with_raw_events(
        (discovered_from_search,),
        tuple(result.raw_event for result in executed.result_events),
    )[0]
    assert validated_from_search.validation_stage == event_impact_hypotheses.ValidationStage.IMPACT_PATH_VALIDATED.value
    assert "TRIGGERED_FADE" not in event_impact_hypotheses.format_impact_hypothesis_report((validated_from_search,))

    search_result = event_catalyst_search.CatalystSearchRunResult(
        provider="fixture",
        queries=(query,),
        rejected_result_events=(
            event_catalyst_search.SearchResultEvent(
                query=query,
                raw_event=raw,
                result_score=45,
                result_score_reasons=("result_identity_rejected",),
                accepted=False,
            ),
        ),
        rejected_count=1,
    )
    discovered = event_impact_hypotheses.attach_hypothesis_search_samples((hypothesis,), search_result)[0]
    assert discovered.status == event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value
    assert discovered.validation_stage == event_impact_hypotheses.ValidationStage.CANDIDATE_ASSETS_SUGGESTED.value
    assert discovered.candidate_symbols == ("VELVET",)
    assert discovered.crypto_candidate_assets[0]["source"] == "candidate_discovery_search"
    assert "candidate_identity_not_validated" in discovered.why_not_promoted

    validated = event_impact_hypotheses.validate_hypotheses_with_raw_events((discovered,), (raw,))[0]
    assert validated.status == event_impact_hypotheses.HypothesisStatus.VALIDATED.value
    assert validated.validation_stage == event_impact_hypotheses.ValidationStage.IMPACT_PATH_VALIDATED.value
    assert validated.impact_path_reason == event_impact_hypotheses.ImpactPathReason.VENUE_VALUE_CAPTURE.value
    assert validated.candidate_symbols == ("VELVET",)
    assert validated.why_not_promoted == ()


def test_event_alpha_provider_health_report_and_reset_are_profile_scoped():
    import contextlib
    import io
    import json
    import os
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

    profile = event_alpha_profiles.get_profile("notify_no_key")
    path_attrs = (
        "EVENT_ALPHA_RUN_LEDGER_PATH",
        "EVENT_ALPHA_ALERT_STORE_PATH",
        "EVENT_ALPHA_NOTIFICATION_RUNS_PATH",
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
    )
    attrs = tuple(
        name
        for name in dict.fromkeys((
            "EVENT_ALPHA_ARTIFACT_BASE_DIR",
            "EVENT_ALPHA_ARTIFACT_NAMESPACE",
            "EVENT_ALPHA_RUN_MODE",
            *path_attrs,
            *profile.config_overrides,
        ))
        if hasattr(config, name)
    )
    original = {name: getattr(config, name) for name in attrs}
    env_names = (
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "RSI_EVENT_ALPHA_RUN_MODE",
        "RSI_EVENT_PROVIDER_HEALTH_PATH",
    )
    original_env = {name: os.environ.get(name) for name in env_names}
    try:
        for name in env_names:
            os.environ.pop(name, None)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config.EVENT_ALPHA_ARTIFACT_BASE_DIR = base
            config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
            config.EVENT_ALPHA_RUN_MODE = ""
            context = event_alpha_artifacts.context_from_profile("notify_no_key", base_dir=base)
            context.provider_health_path.parent.mkdir(parents=True, exist_ok=True)
            context.provider_health_path.write_text(
                json.dumps({
                    "schema_version": "event_provider_health_v1",
                    "providers": {
                        "gdelt:event_source": {
                            "provider": "gdelt",
                            "provider_key": "gdelt:event_source",
                            "provider_service": "gdelt",
                            "provider_role": "event_source",
                            "consecutive_failures": 2,
                            "disabled_until": "2099-06-20T12:00:00+00:00",
                            "last_success_at": "2026-06-19T00:00:00+00:00",
                            "last_failure_at": "2026-06-20T10:00:00+00:00",
                            "last_error_class": "HTTPError",
                        },
                        "rss:event_source": {
                            "provider": "rss",
                            "provider_key": "rss:event_source",
                            "provider_service": "rss",
                            "provider_role": "event_source",
                            "consecutive_failures": 1,
                            "disabled_until": "2099-06-20T12:00:00+00:00",
                            "last_error_class": "URLError",
                        },
                    },
                }),
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_provider_health_report(profile_name="notify_no_key")
            text = out.getvalue()
            assert f"provider_health_path: {context.provider_health_path}" in text
            assert "gdelt:event_source" in text
            assert "status=backoff" in text
            assert "RSI_" not in text

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_provider_health_reset(
                    profile_name="notify_no_key",
                    provider_key="gdelt:event_source",
                    confirm=False,
                )
            assert "pass --confirm" in out.getvalue()
            preserved = json.loads(context.provider_health_path.read_text(encoding="utf-8"))["providers"]
            assert preserved["gdelt:event_source"]["disabled_until"]

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_provider_health_reset(
                    profile_name="notify_no_key",
                    provider_key="gdelt:event_source",
                    confirm=True,
                )
            text = out.getvalue()
            assert "providers_matched: 1" in text
            rows = json.loads(context.provider_health_path.read_text(encoding="utf-8"))["providers"]
            assert rows["gdelt:event_source"]["disabled_until"] is None
            assert rows["gdelt:event_source"]["consecutive_failures"] == 0
            assert rows["gdelt:event_source"]["last_failure_at"] == "2026-06-20T10:00:00+00:00"
            assert rows["rss:event_source"]["disabled_until"]

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_provider_health_reset(
                    profile_name="notify_no_key",
                    reset_all=True,
                    confirm=True,
                )
            assert "providers_matched: 2" in out.getvalue()
            rows = json.loads(context.provider_health_path.read_text(encoding="utf-8"))["providers"]
            assert all(row.get("disabled_until") is None for row in rows.values())
    finally:
        for name, value in original.items():
            setattr(config, name, value)
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_event_discovery_asset_role_demotes_proxy_context_noise():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent
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
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

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
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

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


def test_event_discovery_pipeline_and_event_fade_safety():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
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


def test_event_alpha_visible_core_coverage_readiness_and_doctor():
    import tempfile
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_feedback_readiness
    import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities

    visible_row = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-core",
        "profile": "market_refresh_smoke",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "market_refresh_smoke",
        "alert_key": "incident:rune|thorchain|security",
        "event_id": "event:rune",
        "incident_id": "incident:rune",
        "symbol": "RUNE",
        "coin_id": "thorchain",
        "validated_symbol": "RUNE",
        "validated_coin_id": "thorchain",
        "candidate_role": "direct_subject",
        "impact_path_type": "exploit_security_event",
        "opportunity_level": "watchlist",
        "opportunity_score_final": 83,
        "final_route_after_quality_gate": "RESEARCH_DIGEST",
        "final_state_after_quality_gate": "WATCHLIST",
        "route": "RESEARCH_DIGEST",
        "tier": "WATCHLIST",
        "core_opportunity_id": None,
    }
    core_id = event_core_opportunities.core_opportunity_id_for_row(visible_row)
    visible_row["core_opportunity_id"] = core_id
    visible_row["feedback_target"] = core_id
    visible_row["feedback_target_type"] = "core_opportunity_id"
    readiness_missing = event_alpha_feedback_readiness.build_feedback_readiness(
        profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
        card_paths=[],
        alert_rows=[visible_row],
        feedback_rows=[],
        watchlist_entries=[],
    )
    assert readiness_missing.visible_core_opportunities == 1
    assert readiness_missing.visible_core_opportunities_missing_cards == 1
    assert "visible_core_opportunities_missing_cards" in readiness_missing.blockers
    doctor_missing = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "run-core", "profile": "market_refresh_smoke", "run_mode": "notification_burn_in", "artifact_namespace": "market_refresh_smoke", "alertable": 0}],
        alert_rows=[visible_row],
        strict=True,
        profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
    )
    assert doctor_missing.status == "BLOCKED"
    assert doctor_missing.visible_core_opportunities_missing_cards == 1
    assert doctor_missing.alert_snapshots_missing_core_opportunity_id == 0

    with tempfile.TemporaryDirectory() as tmp:
        card_path = Path(tmp) / "rune.md"
        card_path.write_text(
            "\n".join([
                "# RUNE Event Research Card",
                "- Generated at: 2026-06-28T00:00:00+00:00",
                "- Lineage status: current",
                "- legacy_lineage_missing: false",
                "- Run ID: run-core",
                "- Profile: market_refresh_smoke",
                "- Namespace: market_refresh_smoke",
                f"- Core opportunity ID: {core_id}",
                f"- Feedback target: {core_id}",
                "- Feedback target type: core_opportunity_id",
            ]),
            encoding="utf-8",
        )
        readiness_ready = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="market_refresh_smoke",
            artifact_namespace="market_refresh_smoke",
            card_paths=[card_path],
            alert_rows=[visible_row],
            feedback_rows=[],
            watchlist_entries=[],
        )
        assert readiness_ready.visible_core_opportunities_with_cards == 1
        assert readiness_ready.visible_core_opportunities_missing_cards == 0
        assert "visible_core_opportunities_missing_cards" not in readiness_ready.blockers
        doctor_ready = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-core", "profile": "market_refresh_smoke", "run_mode": "notification_burn_in", "artifact_namespace": "market_refresh_smoke", "alertable": 0}],
            alert_rows=[visible_row],
            card_paths=[card_path],
            strict=True,
            profile="market_refresh_smoke",
            artifact_namespace="market_refresh_smoke",
        )
        assert doctor_ready.visible_core_opportunities_missing_cards == 0
        assert "visible_core_opportunities_missing_cards=1" not in event_alpha_artifact_doctor.format_artifact_doctor_report(doctor_ready)


def test_event_provider_health_backoff_and_report():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health

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
    assert "status=backoff" in event_provider_health.format_provider_health_report(rows, now=now)
    assert "consecutive_failures=2" in text
    assert "last_error_class=RuntimeError" in text
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


def test_event_provider_health_reset_and_ignore_backoff():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health

    now = datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc)
    path = Path(tempfile.mkdtemp()) / "provider_health.json"
    cfg = event_provider_health.EventProviderHealthConfig(
        path=path,
        max_consecutive_failures=1,
        backoff_minutes=60,
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
    event_provider_health.record_provider_failure(
        "rss",
        RuntimeError("dns"),
        cfg=cfg,
        now=now,
        provider_service="rss",
        provider_role="event_source",
        provider_kind="event_source",
    )
    rows = event_provider_health.load_provider_health(path)
    assert event_provider_health.provider_allowed(
        "gdelt",
        cfg=cfg,
        now=now,
        provider_service="gdelt",
        provider_role="event_source",
    ).allowed is False
    ignore_cfg = event_provider_health.EventProviderHealthConfig(path=path, ignore_backoff=True)
    ignored = event_provider_health.provider_allowed(
        "gdelt",
        cfg=ignore_cfg,
        now=now,
        provider_service="gdelt",
        provider_role="event_source",
    )
    assert ignored.allowed is True
    assert ignored.reason == "provider_backoff_ignored_for_run"
    assert event_provider_health.load_provider_health(path)["gdelt:event_source"]["disabled_until"]

    reset_rows, result = event_provider_health.reset_provider_health_rows(rows, provider_key="gdelt:event_source")
    assert result.providers_matched == 1
    assert reset_rows["gdelt:event_source"]["disabled_until"] is None
    assert reset_rows["gdelt:event_source"]["consecutive_failures"] == 0
    assert reset_rows["rss:event_source"]["disabled_until"]
    assert reset_rows["gdelt:event_source"]["last_failure_at"]

    reset_all_rows, all_result = event_provider_health.reset_provider_health_rows(rows, reset_all=True)
    assert all_result.providers_matched == 2
    assert all(not row.get("disabled_until") for row in reset_all_rows.values())
    assert all(int(row.get("consecutive_failures") or 0) == 0 for row in reset_all_rows.values())
    text = event_provider_health.format_provider_health_reset_result(all_result, path=path)
    assert "providers_matched: 2" in text
    assert "RSI_" not in text
    try:
        event_provider_health.reset_provider_health_rows(rows)
    except ValueError as exc:
        assert "requires" in str(exc)
    else:
        raise AssertionError("reset without selector should fail")


def test_event_provider_health_wraps_event_and_enrichment_providers():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health
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
    ignored_cfg = event_provider_health.EventProviderHealthConfig(
        path=skip_path,
        max_consecutive_failures=1,
        backoff_minutes=15,
        ignore_backoff=True,
    )
    ignored_provider = SkippedProvider()
    ignored_wrapped = event_provider_health.HealthCheckedEventProvider(ignored_provider, cfg=ignored_cfg)
    assert ignored_wrapped.fetch_events(now, now) == ["should not call"]
    assert ignored_provider.calls == 1
    ignored_rows = event_provider_health.load_provider_health(skip_path)
    assert (ignored_rows.get("skipped_source:event_source") or ignored_rows["skipped_source"])["disabled_until"]

    class StillFailingProvider:
        name = "skipped_source"

        def fetch_events(self, start, end):
            raise RuntimeError("still failing")

    before_row = event_provider_health.load_provider_health(skip_path)
    before_failures = int(
        (before_row.get("skipped_source:event_source") or before_row["skipped_source"])["consecutive_failures"]
    )
    assert event_provider_health.HealthCheckedEventProvider(
        StillFailingProvider(),
        cfg=ignored_cfg,
    ).fetch_events(now, now) == []
    after_rows = event_provider_health.load_provider_health(skip_path)
    after_row = after_rows.get("skipped_source:event_source") or after_rows["skipped_source"]
    assert int(after_row["consecutive_failures"]) == before_failures + 1
    assert after_row["disabled_until"]

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


def test_event_provider_health_wrappers_use_injected_now_and_api_signatures():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health

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


def test_event_alpha_v1_readiness_health_tuning_and_pack_reports():
    import tempfile
    import zipfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.outcomes.burn_in as event_alpha_burn_in_pack
    import crypto_rsi_scanner.event_alpha.config.health_guard as event_alpha_health_guard
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_tuning
    import crypto_rsi_scanner.event_alpha.config.v1_readiness as event_alpha_v1_readiness
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

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
    assert "READY_TO_START_DAY1_NOTIFICATIONS: no" in day1_text
    assert "READY_FOR_CALIBRATED_RESEARCH_SEND: no" in day1_text
    assert "Day-1 notifications are unvalidated research output" in day1_text

    contract_blocked = event_alpha_v1_readiness.build_v1_readiness(
        run_rows=run_rows,
        alert_rows=alert_rows,
        feedback_rows=feedback_rows,
        missed_rows=missed_rows,
        provider_health_rows=health_rows,
        outcome_rows=alert_rows,
        now=now,
        burn_in_contract_scorecard={
            "enough_data": False,
            "enough_data_reasons": ["min_real_candidates:0/300"],
            "promotion_freeze_status_by_lane": {
                "EARLY_LONG_RESEARCH": "frozen_insufficient_data",
            },
        },
    )
    contract_text = event_alpha_v1_readiness.format_v1_readiness_report(contract_blocked)
    assert "BURN_IN_CONTRACT_ENOUGH_DATA: no" in contract_text
    assert "READY_FOR_CALIBRATED_RESEARCH_SEND: no" in contract_text
    assert "min_real_candidates:0/300" in contract_text
    assert "EARLY_LONG_RESEARCH: frozen_insufficient_data" in contract_text

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


def test_daily_brief_declares_canonical_view_and_market_freshness_readiness():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief

    row = {
        "run_id": "run-1",
        "profile": "notify_llm_quality",
        "artifact_namespace": "notify_llm_quality",
        "run_mode": "notification_burn_in",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "incident_id": "incident:velvet",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "impact_path_type": "venue_value_capture",
        "opportunity_level": "validated_digest",
        "opportunity_score_final": 74,
        "final_route_after_quality_gate": "RESEARCH_DIGEST",
        "final_state_after_quality_gate": "RADAR",
        "market_context_freshness_status": "stale",
        "market_context_source": "candidate_event_market_snapshot",
        "market_context_age_hours": 72,
        "market_context_freshness_cap_applied": True,
    }
    markdown = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{
            "run_id": "run-1",
            "profile": "notify_llm_quality",
            "artifact_namespace": "notify_llm_quality",
            "run_mode": "notification_burn_in",
            "success": True,
        }],
        hypothesis_rows=[row],
        requested_profile="notify_llm_quality",
        artifact_namespace="notify_llm_quality",
    )
    assert "Canonical operator view: Core Opportunities sections above." in markdown
    assert "## Burn-In Readiness" in markdown
    assert "Burn-in mode: no-send" in markdown
    assert "What to review manually" in markdown
    assert "Missing keys/providers" in markdown
    assert "## Market Freshness Readiness" in markdown
    assert "Capped by stale/unknown context: 1" in markdown
    assert "Needs targeted market refresh: 1" in markdown
    assert "### Diagnostic Appendix: Diagnostics / Source-Noise / Controls" in markdown


def test_daily_brief_source_coverage_uses_json_effective_provider_health():
    import json

    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "event_alpha_source_coverage.json").write_text(
            json.dumps({
                "cryptopanic_configured": True,
                "cryptopanic_health_status": "healthy",
                "cryptopanic_coverage_status": "observed_healthy",
                "cryptopanic_observed": True,
                "cryptopanic_successful_requests": 2,
                "cryptopanic_failed_requests": 0,
                "cryptopanic_accepted_evidence": 1,
                "cryptopanic_rejected_evidence": 0,
                "cryptopanic_backoff_reconciled_after_success": True,
                "packs": [{
                    "source_pack": "fan_sports_pack",
                    "provider_coverage_status": "partial",
                    "healthy_providers": ["cryptopanic"],
                    "unknown_or_unobserved_providers": ["sports_fixtures"],
                    "degraded_or_backoff_providers": [],
                    "missing_providers": ["project_blog_rss"],
                    "candidates_blocked_by_coverage_gap": 1,
                    "accepted_evidence_count": 1,
                    "rejected_only_count": 0,
                    "skipped_budget_count": 0,
                    "provider_unavailable_count": 0,
                    "recommended_actions": ["add sports fixture confirmation"],
                }],
            }),
            encoding="utf-8",
        )
        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[{
                "row_type": "event_alpha_run",
                "run_id": "run-1",
                "profile": "notify_llm_deep",
                "artifact_namespace": "ns",
                "started_at": "2026-07-01T00:00:00+00:00",
                "success": True,
            }],
            requested_profile="notify_llm_deep",
            artifact_namespace="ns",
            run_ledger_path=base / "event_alpha_runs.jsonl",
        )
    assert "CryptoPanic effective coverage" in brief
    assert "status=healthy" in brief
    assert "fan_sports_pack: coverage=partial healthy=cryptopanic" in brief
    assert "What data source would most improve next run: fan_sports_pack: add sports fixture confirmation" in brief


def test_event_alpha_bybit_announcements_preflight_fixture_and_default_no_network():
    import json
    from datetime import datetime, timezone

    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight as event_bybit_announcements_preflight

    fixture_path = Path("fixtures/event_discovery/official_exchange_bybit_announcements.json")
    original_path = config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH
    original_allow = os.environ.get(event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT)
    try:
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = fixture_path
        os.environ.pop(event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT, None)
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = event_bybit_announcements_preflight.build_preflight_report(
                namespace_dir=base,
                smoke_mode=True,
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
            )
            json_path, md_path = event_bybit_announcements_preflight.write_preflight_artifacts(report, base)

            def forbidden_opener(_request, _timeout):
                raise AssertionError("Bybit opener must not be called without explicit allow")

            _preflight, rehearsal, _paths = event_bybit_announcements_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="fixture",
                artifact_namespace="bybit_announcements_no_send_rehearsal",
                allow_live_preflight=False,
                opener=forbidden_opener,
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
            )

            assert json.loads(json_path.read_text(encoding="utf-8"))["provider"] == "bybit_announcements"
            assert "No provider network calls" in md_path.read_text(encoding="utf-8")
            assert report.configured is True
            assert report.env_vars_required == ()
            assert report.live_call_allowed is False
            assert report.fixture_parser_status == "pass"
            assert report.fixture_rows_observed >= 1
            assert rehearsal.status == "skipped_live_calls_disabled"
            assert rehearsal.requests_used == 0
            assert rehearsal.telegram_sends == 0
            assert rehearsal.trades_created == 0
            assert rehearsal.paper_trades_created == 0
            assert rehearsal.normal_rsi_signal_rows_written == 0
            assert rehearsal.triggered_fade_created == 0
            assert not (base / event_bybit_announcements_preflight.REQUEST_LEDGER).exists()
            assert event_bybit_announcements_preflight.artifact_conflicts(base)[
                "bybit_announcements_preflight_live_call_allowed_in_smoke"
            ] == 0
    finally:
        config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH = original_path
        if original_allow is None:
            os.environ.pop(event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT, None)
        else:
            os.environ[event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT] = original_allow
