"""Focused Event Alpha provider and discovery tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


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
        markdown = md_path.read_text(encoding="utf-8")

    providers = {row["provider_name"]: row for row in payload["providers"]}
    assert payload["live_calls_allowed"] is False
    assert providers["coinalyze"]["live_call_allowed"] is False
    assert providers["bybit_announcements_public"]["live_call_allowed"] is False
    assert providers["geckoterminal"]["live_call_allowed"] is False
    assert [row["category"] for row in payload["recommended_next_activation_order"][:2]] == [
        "Derivatives/OI/funding",
        "Official exchange announcements",
    ]
    assert [row["category"] for row in payload["recommended_next_activation_order"][-2:]] == [
        "CryptoPanic context",
        "RSS/GDELT context only",
    ]
    assert [row["provider"] for row in payload["activation_runbook"][:2]] == [
        "coinalyze",
        "bybit_announcements_public",
    ]
    assert payload["official_exchange_activation_runbook"][0].startswith("Overall activation category #2;")
    assert markdown.index("- Coinalyze first:") < markdown.index("- Official exchange announcements second:")
    assert md_path.name == live_provider_readiness.READINESS_MD


def test_integrated_source_coverage_uses_canonical_activation_order():
    from crypto_rsi_scanner.event_alpha.radar import source_coverage
    from crypto_rsi_scanner.event_alpha.radar.integrated.pipeline_parts import report as integrated_report

    markdown = integrated_report.format_integrated_source_coverage(())
    payload = integrated_report.format_integrated_source_coverage_json(())
    canonical = source_coverage.SOURCE_COVERAGE_CATEGORY_PRIORITIES

    assert markdown.index("1. Derivatives/OI/funding") < markdown.index("2. Official exchange announcements")
    assert payload["lane_critical_priority"][:2] == [
        "derivatives_oi_funding",
        "official_exchange_announcements",
    ]
    assert payload["lane_critical_priority"][-2:] == [
        "cryptopanic_context",
        "rss_gdelt_context_only",
    ]
    assert [row["category"] for row in payload["category_priorities"]] == [
        row["category"] for row in canonical
    ]


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


def test_event_provider_health_rate_limit_enters_backoff_after_first_failure():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health

    now = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
    path = Path(tempfile.mkdtemp()) / "provider_health.json"
    cfg = event_provider_health.EventProviderHealthConfig(
        path=path,
        max_consecutive_failures=3,
        backoff_minutes=30,
    )
    row = event_provider_health.record_provider_failure(
        "gdelt",
        "GDELT live news fetch failed: rate_limited_or_forbidden status=429 retry_after=120",
        cfg=cfg,
        now=now,
        provider_service="gdelt",
        provider_role="event_source",
        provider_kind="event_source",
    )

    assert row["consecutive_failures"] == 1
    assert row["last_error_class"] == "rate_limited_or_forbidden"
    assert row["disabled_until"] is not None
    assert event_provider_health.provider_allowed(
        "gdelt",
        cfg=cfg,
        now=now,
        provider_service="gdelt",
        provider_role="event_source",
    ).allowed is False


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
    assert "READY_FOR_CALIBRATED_RESEARCH_SEND: no" in readiness_text
    assert "calibrated research send still requires burn-in evidence" in readiness_text
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
    assert "feedback authority: supplied=3 eligible=0 excluded=3" in worksheet_text
    assert "source_noise_control" not in worksheet_text
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
    assert "Feedback rows supplied: 3" in card.markdown
    assert "Eligible exact-Core feedback rows: 0" in card.markdown
    assert "legacy_feedback_contract=3" in card.markdown
    assert "feedback: useful" not in card.markdown
    assert "outcome: not filled" in card.markdown

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
    assert "- burn_in_mode: `no_send_notification_burn_in`" in markdown
    assert "What to review manually" in markdown
    assert "Missing keys/providers" in markdown
    assert "## Market Freshness Readiness" in markdown
    assert "current_core_rows_capped_by_stale_or_unknown_context: 1" in markdown
    assert "current_core_rows_needing_targeted_market_refresh: 1" in markdown
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
    assert "Largest current source-pack coverage gap: fan_sports_pack: add sports fixture confirmation" in brief


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
            _preflight, cli_only_rehearsal, _paths = event_bybit_announcements_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="fixture",
                artifact_namespace="bybit_announcements_no_send_rehearsal",
                allow_live_preflight=True,
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
            assert any(
                event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT in note
                and "already exists in the environment" in note
                and "CLI allow flag may only accompany" in note
                for note in report.safety_notes
            )
            assert rehearsal.status == "skipped_live_calls_disabled"
            assert cli_only_rehearsal.status == "skipped_live_calls_disabled"
            rehearsal_text = (base / event_bybit_announcements_preflight.REHEARSAL_MD).read_text(encoding="utf-8")
            assert f"set {event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT}=1 manually" in rehearsal_text
            assert "CLI allow flag may only accompany" in rehearsal_text
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
