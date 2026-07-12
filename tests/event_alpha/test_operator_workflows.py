"""Focused Event Alpha operator behavior tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_core_digest_caps_daily_items_with_local_brief_overflow():
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

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
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

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
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

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
        assert profile.config_overrides["EVENT_LLM_MAX_PARALLEL_CALLS"] == 3
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
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor

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
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult

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
    assert "crypto_rsi_scanner.event_alpha.outcomes.eval" in text
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


def test_event_identity_shared_matcher_field_safety():
    import crypto_rsi_scanner.event_alpha.radar.identity as event_identity

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

    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    import crypto_rsi_scanner.event_alpha.radar.watchlist_market as event_watchlist_market

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

    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

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
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.artifacts.explain as event_alpha_explain
    import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger

    quiet = event_alpha_explain.format_last_run_explanation([
        {"run_id": "r1", "run_mode": "burn_in", "artifact_namespace": "no_key_live", "success": True, "raw_events": 0, "market_anomalies": 0, "candidates": 0, "alerts": 0, "routed": 0, "alertable": 0}
    ])
    assert "no source events or market anomalies" in quiet
    routed = event_alpha_explain.format_last_run_explanation([
        {"run_id": "r2", "run_mode": "burn_in", "artifact_namespace": "no_key_live", "success": True, "raw_events": 3, "market_anomalies": 1, "candidates": 2, "alerts": 2, "routed": 2, "alertable": 0, "llm_skipped_due_budget": 1}
    ], alert_rows=[{"run_mode": "burn_in", "artifact_namespace": "no_key_live", "tier": "STORE_ONLY", "rejected_reason": "source_noise"}])
    assert "router produced no alertable decisions" in routed
    assert "skipped_budget=1" in routed
    assert "candidate_events=2 · research_candidates=2 · source_alert_snapshots=0" in routed
    assert "alertable_decisions=0 · strict_alerts=0" in routed
    assert " · candidates=" not in routed
    assert " · alerts=" not in routed
    assert "top route suppression reasons: source_noise=1" in routed

    canonical = event_alpha_explain.format_last_run_explanation([
        {
            "run_id": "r3",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "no_key_live",
            "success": True,
            "raw_events": 8,
            "candidate_events": 4,
            "research_candidates": 3,
            "source_alert_snapshots": 2,
            "current_generation_core_rows": 5,
            "current_generation_visible_core_rows": 3,
            "cumulative_store_rows": 21,
            "routed": 3,
            "alertable_decisions": 1,
            "strict_alerts": 0,
            "preview_rendered_items": 2,
            "send_requested": False,
            "send_attempted": False,
        }
    ])
    assert "candidate_events=4 · research_candidates=3 · source_alert_snapshots=2" in canonical
    assert "current_generation_core_rows=5 · current_generation_visible_core_rows=3 · cumulative_store_rows=21" in canonical
    assert "alertable_decisions=1 · strict_alerts=0 · preview_rendered_items=2" in canonical
    assert "burn_in_mode=no_send_notification_burn_in" in canonical
    assert "none qualified as strict alerts" in canonical

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
    import crypto_rsi_scanner.event_alpha.radar.watchlist_market as event_watchlist_market

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
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    import crypto_rsi_scanner.event_alpha.radar.watchlist_market as event_watchlist_market
    import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor

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
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    import crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment as event_watchlist_enrichment
    import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor

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
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif

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


def test_daily_brief_writer_uses_context_paths_and_one_research_clock(
    monkeypatch,
    tmp_path,
):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from crypto_rsi_scanner.cli.services import event_alpha_reports as reports

    namespace = tmp_path / "scoped"
    context = SimpleNamespace(
        profile="fixture",
        run_mode="fixture",
        artifact_namespace="scoped",
        namespace_dir=namespace,
        run_ledger_path=namespace / "event_alpha_runs.jsonl",
        alert_store_path=namespace / "event_alpha_alerts.jsonl",
        notification_runs_path=namespace / "event_alpha_notification_runs.jsonl",
        watchlist_state_path=namespace / "event_watchlist_state.jsonl",
        feedback_path=namespace / "event_alpha_feedback.jsonl",
        missed_path=namespace / "event_alpha_missed.jsonl",
        provider_health_path=namespace / "event_provider_health.json",
        daily_brief_path=namespace / "event_alpha_daily_brief.md",
        impact_hypothesis_store_path=namespace / "event_impact_hypotheses.jsonl",
        core_opportunity_store_path=namespace / "event_core_opportunities.jsonl",
        incident_store_path=namespace / "event_incidents.jsonl",
        evidence_acquisition_path=namespace / "event_evidence_acquisition.jsonl",
        research_cards_dir=namespace / "research_cards",
    )
    evaluation_now = datetime(2026, 7, 12, 4, 5, tzinfo=timezone.utc)
    calls: dict[str, object] = {}
    clock_calls: list[None] = []

    monkeypatch.setattr(
        reports,
        "_event_research_now",
        lambda: clock_calls.append(None) or evaluation_now,
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "config",
        SimpleNamespace(
            EVENT_RESEARCH_CARDS_WRITE_TIERS=(),
            EVENT_RESEARCH_CARDS_WRITE_LIMIT=25,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "event_alpha_profiles",
        SimpleNamespace(get_profile=lambda _name: SimpleNamespace(name="fixture")),
        raising=False,
    )
    def load_runs(path, limit):
        calls["runs"] = path
        calls["run_limit"] = limit
        return SimpleNamespace(rows=[])

    monkeypatch.setattr(
        reports,
        "event_alpha_run_ledger",
        SimpleNamespace(load_run_records=load_runs),
        raising=False,
    )
    monkeypatch.setattr(reports, "_ensure_daily_operator_state", lambda *_args: None, raising=False)

    def load_alerts(path, latest_only, *, core_opportunity_store_path):
        calls["alerts"] = path
        calls["alerts_latest_only"] = latest_only
        calls["alerts_core"] = core_opportunity_store_path
        return SimpleNamespace(rows=[])

    monkeypatch.setattr(
        reports,
        "event_alpha_alert_store",
        SimpleNamespace(load_alert_snapshots=load_alerts),
        raising=False,
    )

    def normalize_core(path, *, latest_run, now):
        calls["core_normalize"] = (path, latest_run, now)

    def load_cores(path, *, latest_run):
        calls["cores"] = (path, latest_run)
        return SimpleNamespace(rows=[])

    monkeypatch.setattr(
        reports,
        "event_core_opportunity_store",
        SimpleNamespace(
            normalize_core_opportunity_store=normalize_core,
            load_core_opportunities=load_cores,
        ),
        raising=False,
    )

    def normalize_runs(path, *, request_ledger_path):
        calls["notification_normalize"] = (path, request_ledger_path)

    def load_notification_runs(path):
        calls["notification_runs"] = path
        return SimpleNamespace(rows=[])

    monkeypatch.setattr(
        reports,
        "event_alpha_notification_runs",
        SimpleNamespace(
            normalize_notification_runs_after_cryptopanic_success=normalize_runs,
            load_notification_runs=load_notification_runs,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "event_impact_hypothesis_store",
        SimpleNamespace(
            load_impact_hypotheses=lambda path, **_kwargs: (
                calls.__setitem__("hypotheses", path) or SimpleNamespace(rows=[])
            )
        ),
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "event_feedback",
        SimpleNamespace(
            load_feedback=lambda path: (
                calls.__setitem__("feedback", path) or SimpleNamespace(records=[])
            )
        ),
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "event_alpha_missed",
        SimpleNamespace(
            load_missed_rows=lambda path: calls.__setitem__("missed", path) or []
        ),
        raising=False,
    )
    watchlist = SimpleNamespace(entries=[])
    monkeypatch.setattr(
        reports,
        "event_watchlist",
        SimpleNamespace(
            load_watchlist=lambda path: (
                calls.__setitem__("watchlist", path) or watchlist
            )
        ),
        raising=False,
    )
    router_result = SimpleNamespace(decisions=[], alertable_decisions=[])
    monkeypatch.setattr(
        reports,
        "event_alpha_router",
        SimpleNamespace(route_watchlist=lambda *_args, **_kwargs: router_result),
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "_event_alpha_router_config_from_runtime",
        lambda: object(),
        raising=False,
    )

    def monitor_result(_watchlist, *, now):
        calls["monitor_now"] = now
        return SimpleNamespace(rows=[])

    monkeypatch.setattr(
        reports,
        "_event_watchlist_monitor_result_from_runtime",
        monitor_result,
        raising=False,
    )

    card_result = SimpleNamespace(
        card_paths=(),
        out_dir=context.research_cards_dir,
        cards_written=0,
    )

    def write_cards(path, **kwargs):
        calls["cards"] = path
        calls["cards_now"] = kwargs["now"]
        return card_result

    monkeypatch.setattr(
        reports,
        "event_research_cards",
        SimpleNamespace(write_research_cards=write_cards),
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "_event_alpha_card_lineage_context",
        lambda **_kwargs: {},
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "event_incident_store",
        SimpleNamespace(
            load_incidents=lambda path, **_kwargs: (
                calls.__setitem__("incidents", path) or SimpleNamespace(rows=[])
            )
        ),
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "event_evidence_acquisition",
        SimpleNamespace(
            load_acquisition_results=lambda path: (
                calls.__setitem__("acquisition", path) or []
            )
        ),
        raising=False,
    )
    for name in (
        "event_market_anomaly_scanner",
        "event_official_exchange",
        "event_scheduled_catalysts",
        "event_derivatives_crowding",
    ):
        loaders = {
            "event_market_anomaly_scanner": {
                "load_market_anomaly_rows": lambda path: calls.__setitem__("market", path) or [],
            },
            "event_official_exchange": {
                "load_official_listing_candidates": lambda path: calls.__setitem__("official", path) or [],
            },
            "event_scheduled_catalysts": {
                "load_scheduled_catalysts": lambda path: calls.__setitem__("scheduled", path) or [],
                "load_unlock_candidates": lambda path: calls.__setitem__("unlocks", path) or [],
            },
            "event_derivatives_crowding": {
                "load_derivatives_state": lambda path: calls.__setitem__("derivatives", path) or [],
                "load_fade_review_candidates": lambda path: calls.__setitem__("fade", path) or [],
            },
        }
        monkeypatch.setattr(
            reports,
            name,
            SimpleNamespace(**loaders[name]),
            raising=False,
        )
    monkeypatch.setattr(
        reports,
        "event_provider_health",
        SimpleNamespace(
            load_provider_health=lambda path: (
                calls.__setitem__("provider_health", path) or {}
            )
        ),
        raising=False,
    )

    def build_daily_brief(**kwargs):
        calls["brief_kwargs"] = kwargs
        return "brief\n"

    def write_daily_brief(path, **kwargs):
        calls["brief_write"] = path
        return SimpleNamespace(path=path, markdown=kwargs["markdown"], cards=())

    monkeypatch.setattr(
        reports,
        "event_alpha_daily_brief",
        SimpleNamespace(
            build_daily_brief=build_daily_brief,
            write_daily_brief=write_daily_brief,
            format_daily_brief_result=lambda _result: "brief-written",
        ),
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "_record_daily_brief_operator_state",
        lambda *_args, **_kwargs: None,
        raising=False,
    )
    monkeypatch.setattr(
        reports,
        "_event_alpha_context_block",
        lambda _context: "context",
        raising=False,
    )

    reports._event_alpha_daily_brief_report_locked(  # noqa: SLF001
        context,
        selected_profile="fixture",
        artifact_namespace="scoped",
        include_test_artifacts=True,
        include_api_artifacts=False,
    )

    assert len(clock_calls) == 1
    assert calls["alerts"] == context.alert_store_path
    assert calls["alerts_core"] == context.core_opportunity_store_path
    assert calls["feedback"] == context.feedback_path
    assert calls["missed"] == context.missed_path
    assert calls["watchlist"] == context.watchlist_state_path
    assert calls["provider_health"] == context.provider_health_path
    assert calls["cards"] == context.research_cards_dir
    assert calls["brief_write"] == context.daily_brief_path
    assert calls["core_normalize"] == (
        context.core_opportunity_store_path,
        True,
        evaluation_now,
    )
    assert calls["monitor_now"] == evaluation_now
    assert calls["cards_now"] == evaluation_now
    assert calls["brief_kwargs"]["generated_at"] == evaluation_now


def test_feedback_mark_persists_and_loads_watchlist_through_resolved_context(
    monkeypatch,
    tmp_path,
):
    from types import SimpleNamespace

    from crypto_rsi_scanner.cli.services.scanner_parts import utility_commands

    namespace = tmp_path / "scoped"
    cards_dir = namespace / "research_cards"
    cards_dir.mkdir(parents=True)
    (cards_dir / "context-card.md").write_text("context", encoding="utf-8")
    context = SimpleNamespace(
        alert_store_path=namespace / "event_alpha_alerts.jsonl",
        core_opportunity_store_path=namespace / "event_core_opportunities.jsonl",
        impact_hypothesis_store_path=namespace / "event_impact_hypotheses.jsonl",
        watchlist_state_path=namespace / "event_watchlist_state.jsonl",
        feedback_path=namespace / "event_alpha_feedback.jsonl",
        research_cards_dir=cards_dir,
    )
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        utility_commands,
        "_setup_event_discovery_logging",
        lambda _verbose: None,
    )

    def resolve(profile_name, artifact_namespace):
        calls["resolved"] = (profile_name, artifact_namespace)
        return context

    monkeypatch.setattr(
        utility_commands,
        "resolve_event_alpha_artifact_context_for_report",
        resolve,
    )
    monkeypatch.setattr(
        utility_commands,
        "_event_watchlist_config_from_runtime",
        lambda: (_ for _ in ()).throw(AssertionError("runtime watchlist path used")),
    )
    monkeypatch.setattr(
        utility_commands,
        "_event_feedback_config_from_runtime",
        lambda *_args: (_ for _ in ()).throw(AssertionError("runtime feedback path used")),
    )

    def load_watchlist(path):
        calls["watchlist"] = path
        return SimpleNamespace(entries=[])

    monkeypatch.setattr(
        utility_commands.event_watchlist,
        "load_watchlist",
        load_watchlist,
    )
    monkeypatch.setattr(
        utility_commands.event_alpha_alert_store,
        "load_alert_snapshots",
        lambda path, **kwargs: (
            calls.update(alerts=path, alerts_core=kwargs.get("core_opportunity_store_path"))
            or SimpleNamespace(rows=[])
        ),
    )
    monkeypatch.setattr(
        utility_commands.event_core_opportunity_store,
        "load_core_opportunities",
        lambda path, **_kwargs: calls.__setitem__("cores", path) or SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        utility_commands.event_impact_hypothesis_store,
        "load_impact_hypotheses",
        lambda path, **_kwargs: calls.__setitem__("hypotheses", path) or SimpleNamespace(rows=[]),
    )

    utility_commands.event_feedback_mark(
        "missed-context-case",
        "missed",
        marked_by="tester",
    )

    assert calls["resolved"] == (None, None)
    assert calls["watchlist"] == context.watchlist_state_path
    assert calls["alerts"] == context.alert_store_path
    assert calls["alerts_core"] == context.core_opportunity_store_path
    assert calls["cores"] == context.core_opportunity_store_path
    assert calls["hypotheses"] == context.impact_hypothesis_store_path
    assert context.feedback_path.exists()
    persisted = context.feedback_path.read_text(encoding="utf-8")
    assert '"target":"missed-context-case"' in persisted
    assert '"label":"missed"' in persisted
