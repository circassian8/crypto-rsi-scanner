"""Focused Event Alpha notification tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_notification_inbox_prefers_canonical_core_items_and_hides_diagnostics():
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-review-items",
            profile="evidence_acquisition_smoke",
            run_mode="burn_in",
            artifact_namespace="evidence_acquisition_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        cards = event_research_cards.write_research_cards(root / "cards", watchlist_entries=[], alert_rows=core_rows)
        event_core_opportunity_store.update_core_opportunity_card_links(
            core_path,
            cards.card_paths,
            run_id="run-core-review-items",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        velvet = next(row for row in core_rows if row["symbol"] == "VELVET")
        canonical = {
            "row_type": "event_alpha_alert_snapshot",
            "run_id": "run-core-review-items",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "alert_id": "ea:velvet-canonical",
            "alert_key": "incident-spacex|velvet|proxy_attention",
            "core_opportunity_id": velvet["core_opportunity_id"],
            "core_resolution_status": "canonical",
            "snapshot_core_resolution_status": "core_reconciled",
            "snapshot_class": "canonical_core_snapshot",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "tier": "HIGH_PRIORITY_WATCH",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            "opportunity_level": "high_priority",
            "alertable_after_quality_gate": True,
            "route_alertable": True,
        }
        diagnostic = {
            **canonical,
            "alert_id": "ea:velvet-support",
            "alert_key": "incident-spacex|velvet|source_noise_control",
            "core_resolution_status": "diagnostic_support",
            "snapshot_core_resolution_status": "diagnostic_support",
            "snapshot_class": "diagnostic_support_snapshot",
            "is_diagnostic_snapshot": True,
            "candidate_role": "source_noise",
            "playbook_type": "source_noise_control",
            "tier": "STORE_ONLY",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "alertable_after_quality_gate": False,
            "route_alertable": False,
            "feedback_target": "ea:velvet-support",
        }
        inbox = event_alpha_notification_inbox.build_notification_inbox(
            notification_runs=[{
                "run_id": "run-core-review-items",
                "profile": "evidence_acquisition_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "evidence_acquisition_smoke",
                "would_send_count": 1,
                "lane_counts_due": {"instant_escalation": 1},
            }],
            alert_rows=[diagnostic, canonical],
            feedback_rows=[],
            research_cards_dir=root / "cards",
            profile="evidence_acquisition_smoke",
            artifact_namespace="evidence_acquisition_smoke",
            notification_runs_path=root / "runs.jsonl",
            alert_store_path=root / "alerts.jsonl",
            feedback_path=root / "feedback.jsonl",
            core_opportunity_rows=core_rows,
        )

    velvet_item = next(item for item in inbox.canonical_review_items if item.symbol == "VELVET")
    assert Path(velvet_item.card_path).name == Path(velvet["card_path"]).name
    assert velvet_item.alert_id == velvet["core_opportunity_id"]
    assert velvet_item.alert_key == "ea:velvet-canonical"
    assert velvet_item.feedback_target == velvet["core_opportunity_id"]
    assert velvet_item.core_opportunity_id == velvet["core_opportunity_id"]
    assert any(item.alert_id == "ea:velvet-support" for item in inbox.diagnostic_review_items_hidden)
    assert all(item.alert_id != "ea:velvet-support" for item in inbox.quality_gated_local_only)
    assert all(item.alert_id != "ea:velvet-support" for item in inbox.exploratory_without_feedback)
    text = event_alpha_notification_inbox.format_notification_inbox(inbox)
    assert f"core_id={velvet['core_opportunity_id']}" in text
    assert "source_alert_id: ea:velvet-canonical" in text
    assert "card: not_written" not in text.split("VELVET/velvet", 1)[1].split("run_id:", 1)[0]
    assert "feedback_target: ea:velvet-support" not in text

    diagnostics = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=[],
        alert_rows=[diagnostic, canonical],
        feedback_rows=[],
        research_cards_dir=Path(velvet["card_path"]).parent,
        profile="evidence_acquisition_smoke",
        artifact_namespace="evidence_acquisition_smoke",
        notification_runs_path=Path("/tmp/runs.jsonl"),
        alert_store_path=Path("/tmp/alerts.jsonl"),
        feedback_path=Path("/tmp/feedback.jsonl"),
        core_opportunity_rows=[velvet],
        include_diagnostics=True,
    )
    assert any(item.alert_id == "ea:velvet-support" for item in diagnostics.diagnostic_review_items)


def test_notification_delivery_records_persist_explicit_status_fields():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery

    delivered = delivery.build_record(
        run_id="run-delivered",
        alert_id="core-1",
        profile="notify_no_key",
        namespace="notify_no_key",
        lane="daily_digest",
        route="RESEARCH_DIGEST",
        content_hash="hash-delivered",
        state=delivery.STATE_DELIVERED,
        now=datetime(2026, 6, 29, 12, tzinfo=timezone.utc),
        delivered_at=datetime(2026, 6, 29, 12, tzinfo=timezone.utc),
        delivered_count=1,
    ).to_row()
    assert delivered["delivery_state"] == delivery.DELIVERY_STATE_SENT
    assert delivered["status_detail"] == delivery.STATUS_DETAIL_SENT
    assert delivered["delivery_mode"] == delivery.DELIVERY_MODE_LIVE_SEND
    assert delivered["send_guard_enabled"] is True
    assert delivered["would_send"] is True
    assert delivered["sent"] is True
    assert delivered["failed"] is False

    blocked = delivery.build_record(
        run_id="run-blocked",
        alert_id="heartbeat",
        profile="notify_llm_deep",
        namespace="notify_llm_deep_rehearsal",
        lane="health_heartbeat",
        route="HEALTH_HEARTBEAT",
        content_hash="hash-blocked",
        state=delivery.STATE_BLOCKED,
        now=datetime(2026, 6, 29, 12, tzinfo=timezone.utc),
        error_class="guard_blocked",
        error_message="event alerts disabled; RSI_EVENT_ALERTS_ENABLED=1 required",
    ).to_row()
    assert blocked["delivery_state"] == delivery.DELIVERY_STATE_BLOCKED
    assert blocked["status_detail"] == delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED
    assert blocked["delivery_mode"] == delivery.DELIVERY_MODE_NO_SEND_REHEARSAL
    assert blocked["send_guard_enabled"] is False
    assert blocked["would_send"] is True
    assert blocked["sent"] is False
    assert blocked["failed"] is False


def test_notification_inbox_burn_in_review_collapses_low_value_rows():
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox

    item = event_alpha_notification_inbox.EventAlphaNotificationInboxItem(
        alert_id="core_velvet",
        alert_key="core_velvet",
        core_opportunity_id="core_velvet",
        symbol="VELVET",
        coin_id="velvet",
        run_id="run-1",
        tier="HIGH_PRIORITY_WATCH",
        playbook="proxy_attention",
        card_path="/tmp/cards/core_velvet.md",
        sent=False,
        would_send=True,
        blocked_by_guard=True,
        delivery_state="blocked",
        reviewed=False,
        reason="high-priority accepted evidence",
        final_route_after_quality_gate="HIGH_PRIORITY_RESEARCH",
        final_state_after_quality_gate="HIGH_PRIORITY",
        alertable_after_quality_gate=True,
        feedback_target="core_velvet",
    )
    local = event_alpha_notification_inbox.EventAlphaNotificationInboxItem(
        alert_id="core_noise",
        alert_key="core_noise",
        core_opportunity_id="core_noise",
        symbol="BTC",
        coin_id="bitcoin",
        run_id="run-1",
        tier="STORE_ONLY",
        playbook="source_noise_control",
        card_path="",
        sent=False,
        would_send=False,
        blocked_by_guard=False,
        delivery_state="",
        reviewed=False,
        reason="quality gated",
        alertable_after_quality_gate=False,
        feedback_target="core_noise",
    )
    doge = event_alpha_notification_inbox.EventAlphaNotificationInboxItem(
        alert_id="core_doge",
        alert_key="core_doge",
        core_opportunity_id="core_doge",
        symbol="DOGE",
        coin_id="dogecoin",
        run_id="run-1",
        tier="RESEARCH_REVIEW",
        playbook="market_anomaly",
        card_path="/tmp/cards/core_doge.md",
        sent=False,
        would_send=False,
        blocked_by_guard=False,
        delivery_state="",
        reviewed=False,
        reason="near-miss score 64; missing confirmation; fresh opportunity",
        final_route_after_quality_gate="LOCAL_REPORT",
        final_state_after_quality_gate="RADAR",
        alertable_after_quality_gate=False,
        feedback_target="core_doge",
        item_type="near_miss_core",
    )
    diagnostic = event_alpha_notification_inbox.EventAlphaNotificationInboxItem(
        alert_id="core_btc_noise",
        alert_key="core_btc_noise",
        core_opportunity_id="core_btc_noise",
        symbol="BTC",
        coin_id="bitcoin",
        run_id="run-1",
        tier="STORE_ONLY",
        playbook="source_noise_control",
        card_path="/tmp/cards/core_btc_noise.md",
        sent=False,
        would_send=False,
        blocked_by_guard=False,
        delivery_state="",
        reviewed=False,
        reason="source_noise publisher suffix; diagnostic only",
        alertable_after_quality_gate=False,
        feedback_target="core_btc_noise",
        is_diagnostic=True,
    )
    result = event_alpha_notification_inbox.EventAlphaNotificationInboxResult(
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep_rehearsal",
        notification_runs_path=Path("/tmp/runs.jsonl"),
        alert_store_path=Path("/tmp/alerts.jsonl"),
        feedback_path=Path("/tmp/feedback.jsonl"),
        research_cards_dir=Path("/tmp/cards"),
        outcomes_path=None,
        notification_runs_read=1,
        alert_rows_read=2,
        feedback_rows_read=0,
        research_cards_read=1,
        outcome_rows_read=0,
        sent_without_feedback=(),
        partial_delivered_without_feedback=(),
        would_send_without_feedback=(),
        would_send_blocked_without_feedback=(item,),
        weak_validated_local_only=(),
        quality_gated_local_only=(local,),
        legacy_quality_conflicts=(),
        research_review_without_feedback=(doge,),
        exploratory_without_feedback=(),
        high_priority_unreviewed=(),
        triggered_fade_unreviewed=(),
        heartbeat_only_runs=(),
        duplicate_or_in_flight_runs=(),
        provider_degraded_runs=({"run_id": "run-1", "warnings": ["gdelt timeout"]},),
        canonical_review_items=(item, doge, local),
        diagnostic_review_items_hidden=(diagnostic,),
    )
    queue = event_alpha_notification_inbox.build_ranked_review_queue(result)
    assert queue[0].category == event_alpha_notification_inbox.REVIEW_QUEUE_HIGH_PRIORITY_WOULD_SEND
    assert queue[0].symbol == "VELVET"
    assert any(row.symbol == "DOGE" and row.category == event_alpha_notification_inbox.REVIEW_QUEUE_RESEARCH_REVIEW_NEAR_MISS for row in queue)
    assert not any(row.symbol == "BTC" for row in queue)
    text = event_alpha_notification_inbox.format_notification_inbox(result, burn_in_review=True)
    assert "EVENT ALPHA BURN-IN REVIEW INBOX" in text
    assert "Ranked review queue:" in text
    assert "1. [high-priority would-send] VELVET/velvet" in text
    assert "[research-review near-miss] DOGE/dogecoin" in text
    assert "BTC/bitcoin" not in text
    assert "Would-send / sent core opportunities: 1" in text
    assert "VELVET/velvet" in text
    assert "card=core_velvet.md" in text
    assert "/tmp/cards" not in text
    assert "Local-only / quality-capped rows: 1" in text
    assert "collapsed in burn-in review" in text
    assert "provider-degraded notification runs: 1" in text


def test_event_alpha_rehearsal_make_targets_include_fixture_and_fast_caps():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-notify-llm-deep-real-no-send-rehearsal-with-fixture-candidate" in makefile
    assert "event-alpha-notify-llm-deep-rehearsal-with-fixture-candidate" in makefile
    fast = makefile.split("event-alpha-notify-llm-deep-real-no-send-rehearsal-fast:", 1)[1].split("event-alpha-send-readiness:", 1)[0]
    assert "RSI_EVENT_ALERTS_ENABLED=0" in fast
    assert "RSI_EVENT_CATALYST_SEARCH_MAX_ANOMALIES=5" in fast
    assert "RSI_EVENT_LLM_MAX_CALLS_PER_RUN=40" in fast
    assert "RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES=5" in fast


def test_notification_runs_filters_cryptopanic_backoff_after_same_run_success():
    import crypto_rsi_scanner.event_alpha.notifications.runs as event_alpha_notification_runs

    row = event_alpha_notification_runs.notification_run_record(
        SimpleNamespace(
            run_id="run-1",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
            warnings=("cryptopanic:event_source in backoff until later", "gdelt timeout"),
            cryptopanic_successful_requests=1,
            cryptopanic_effective_provider_status="healthy",
        ),
        profile="notify_llm_deep",
        started_at=pd.Timestamp("2026-07-01T00:00:00Z").to_pydatetime(),
        finished_at=pd.Timestamp("2026-07-01T00:01:00Z").to_pydatetime(),
        telegram_ready=False,
        send_guard_enabled=False,
        provider_health_rows={
            "cryptopanic:event_source": {
                "provider_key": "cryptopanic:event_source",
                "provider": "cryptopanic",
                "disabled_until": "2026-07-01T01:00:00+00:00",
            },
            "gdelt:event_source": {
                "provider_key": "gdelt:event_source",
                "provider": "gdelt",
                "disabled_until": "2026-07-01T01:00:00+00:00",
            },
        },
    )
    blocks = " ".join(row["provider_fail_fast_blocks"]).casefold()
    assert "cryptopanic" not in blocks
    assert "gdelt" in blocks


def test_daily_brief_reflects_planned_research_review_delivery_without_decisions():
    import json

    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "event_alpha_notification_deliveries.jsonl").write_text(
            json.dumps({
                "lane": "research_review_digest",
                "delivery_state": "blocked",
                "would_send": True,
                "core_opportunity_id": "core_velvet_review",
                "core_opportunity_ids": ["core_chz_review", "core_velvet_review"],
                "canonical_symbols": ["CHZ", "VELVET"],
                "canonical_coin_ids": ["chiliz", "velvet"],
                "attempted_at": "2026-07-01T00:01:00+00:00",
                "mode": "no_send_rehearsal",
            }) + "\n",
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
                "research_review_digest_enabled": True,
                "research_review_digest_candidates": 1,
                "research_review_digest_would_send": 1,
            }],
            requested_profile="notify_llm_deep",
            artifact_namespace="ns",
            run_ledger_path=base / "event_alpha_runs.jsonl",
        )
    assert "### Research Review Digest" in brief
    assert "CHZ + VELVET/2 coin(s) core=2 core(s): core_chz_review, core_velvet_review" in brief
    assert "would_send=true" in brief


def test_event_alpha_bybit_announcements_rehearsal_mocked_live_success_feeds_coverage_and_integrated_radar():
    import json
    from datetime import datetime, timezone

    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
    import crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight as event_bybit_announcements_preflight
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar
    import crypto_rsi_scanner.event_alpha.providers.official_exchange as event_official_exchange
    import crypto_rsi_scanner.event_alpha.providers.official_exchange_activation as event_official_exchange_activation
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health
    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status

    class MockBybitResponse:
        status = 200

        def __init__(self, payload):
            self.payload = json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self):
            return self.payload

    original_max_pages = os.environ.get(event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES)
    original_limit = os.environ.get(event_bybit_announcements_preflight.ENV_PREFLIGHT_LIMIT)
    original_allow = os.environ.get(event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT)
    try:
        os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES] = "1"
        os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_LIMIT] = "20"
        os.environ[event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT] = "1"
        fixture_payload = json.loads(Path("fixtures/event_discovery/official_exchange_bybit_announcements.json").read_text(encoding="utf-8"))
        fixture_payload["result"]["list"] = fixture_payload["result"]["list"][:2]
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            namespace = "bybit_live_mock"
            namespace_dir = root / namespace
            calls: list[str] = []

            def opener(request, _timeout):
                calls.append(request.full_url)
                return MockBybitResponse(fixture_payload)

            _preflight, report, _paths = event_bybit_announcements_preflight.run_no_send_rehearsal(
                namespace_dir=namespace_dir,
                provider_health_path=namespace_dir / "event_provider_health.json",
                profile="fixture",
                artifact_namespace=namespace,
                allow_live_preflight=True,
                opener=opener,
                now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
            )
            candidates = event_official_exchange.load_official_listing_candidates(namespace_dir)
            by_symbol = {str(row.get("symbol") or ""): row for row in candidates}
            ledger_rows = [
                json.loads(line)
                for line in (namespace_dir / event_bybit_announcements_preflight.REQUEST_LEDGER).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            health_rows = event_provider_health.load_provider_health(namespace_dir / "event_provider_health.json")
            coverage = event_alpha_source_coverage.build_source_coverage_report(
                provider_status_report=event_provider_status.build_event_discovery_provider_status(config),
                provider_health_rows=health_rows,
                profile="fixture",
                artifact_namespace=namespace,
                artifact_namespace_dir=namespace_dir,
            )
            official_pack = next(pack for pack in coverage.packs if pack.source_pack == "official_exchange_listing_pack")
            context = event_alpha_artifacts.context_from_profile(
                "fixture",
                run_mode="fixture",
                base_dir=root,
                artifact_namespace=namespace,
            )
            integrated = event_integrated_radar.run_integrated_radar_cycle(
                context=context,
                fixture=False,
                input_mode=event_integrated_radar.INPUT_MODE_LOAD_EXISTING,
                observed_at="2026-06-15T16:00:00Z",
            )
            integrated_rows = [
                json.loads(line)
                for line in integrated.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            integrated_symbols = {str(row.get("symbol") or "") for row in integrated_rows}

            assert len(calls) == 1
            assert "type=new_crypto" in calls[0]
            assert report.status == "live_rehearsal_success"
            assert report.provider_health_status == "observed_healthy"
            assert report.requests_used == 1
            assert report.provider_generation_id
            assert report.run_id
            assert report.http_successes == 1
            assert report.announcements_inspected == 2
            assert report.official_events_written == 2
            assert report.official_listing_candidates_written == 2
            assert report.telegram_sends == 0
            assert report.trades_created == 0
            assert report.paper_trades_created == 0
            assert report.normal_rsi_signal_rows_written == 0
            assert report.triggered_fade_created == 0
            activation_rows = event_official_exchange_activation.load_activation_rows(namespace_dir)
            activation_by_provider = {str(row.get("provider") or ""): row for row in activation_rows}
            bybit_activation = activation_by_provider["bybit_announcements_public"]
            assert bybit_activation["mode"] == "public_http_no_key"
            assert bybit_activation["live_call_allowed"] is True
            assert bybit_activation["no_send_rehearsal"] is True
            assert bybit_activation["announcements_seen"] == 2
            assert bybit_activation["official_events_written"] == 2
            assert bybit_activation["listing_candidates_written"] >= 1
            assert bybit_activation["strict_alerts_created"] == 0
            assert bybit_activation["telegram_sends"] == 0
            assert ledger_rows[0]["success"] is True
            assert ledger_rows[0]["live_call_allowed"] is True
            assert ledger_rows[0]["no_send_rehearsal"] is True
            assert ledger_rows[0]["unsupported_query_params"] == []
            assert ledger_rows[0]["provider_generation_id"] == report.provider_generation_id
            assert ledger_rows[0]["run_id"] == report.run_id
            assert set(ledger_rows[0]["query_params"]) <= set(event_bybit_announcements_preflight.SUPPORTED_PARAMS)
            assert by_symbol["TESTSPOT"]["source_url"]
            assert by_symbol["TESTSPOT"]["published_at"]
            assert by_symbol["TESTSPOT"]["provider_generation_id"] == report.provider_generation_id
            assert by_symbol["TESTSPOT"]["provider_request_succeeded"] is True
            assert by_symbol["TESTSPOT"]["provider_source_artifact"]
            assert by_symbol["TESTSPOT"]["request_ledger_path"]
            assert by_symbol["TESTPERP"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
            assert "bybit_announcements_public" in official_pack.healthy_providers
            assert coverage.bybit_announcements_provider_health_status == "observed_healthy"
            assert coverage.bybit_announcements_official_events_written == 2
            assert "TESTPERP" in integrated_symbols
            assert "TESTSPOT" in integrated_symbols
            integrated_by_symbol = {str(row.get("symbol") or ""): row for row in integrated_rows}
            assert integrated_by_symbol["TESTSPOT"]["provider_generation_id"] == report.provider_generation_id
            assert integrated_by_symbol["TESTSPOT"]["provider_request_succeeded"] is True
            assert event_bybit_announcements_preflight.artifact_conflicts(namespace_dir)[
                "bybit_announcements_rehearsal_live_without_ledger"
            ] == 0
            assert event_official_exchange_activation.artifact_conflicts(namespace_dir)[
                "official_exchange_activation_live_without_ledger"
            ] == 0
    finally:
        if original_max_pages is None:
            os.environ.pop(event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES, None)
        else:
            os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES] = original_max_pages
        if original_limit is None:
            os.environ.pop(event_bybit_announcements_preflight.ENV_PREFLIGHT_LIMIT, None)
        else:
            os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_LIMIT] = original_limit
        if original_allow is None:
            os.environ.pop(event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT, None)
        else:
            os.environ[event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT] = original_allow


def test_notification_digest_labels_fade_short_review_lane():
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="TESTLIST|fade",
        cluster_id="cluster-testlist",
        event_id="evt-testlist",
        coin_id="testlist",
        symbol="TESTLIST",
        relationship_type="listing_liquidity_event",
        external_asset=None,
        event_time="2026-06-15T13:00:00+00:00",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state="WATCHLIST",
        first_seen_at="2026-06-15T12:00:00+00:00",
        last_seen_at="2026-06-15T16:00:00+00:00",
        latest_event_name="TESTLIST official listing pump",
        opportunity_level="high_priority",
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="fade review escalation",
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
        final_route_after_quality_gate=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        opportunity_level="high_priority",
        opportunity_score_final=88,
    )
    message = notif.format_core_opportunity_telegram_digest(
        [decision],
        profile="fixture",
        card_path_by_alert_id={},
        core_row_by_alert_id={
            decision.alert_id: {
                "core_opportunity_id": "core-testlist",
                "symbol": "TESTLIST",
                "coin_id": "testlist",
                "canonical_incident_name": "TESTLIST official listing pump",
                "opportunity_type": "FADE_SHORT_REVIEW",
                "market_state": "blowoff_crowded",
                "final_opportunity_level": "high_priority",
                "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
                "impact_path_type": "listing_liquidity_event",
                "candidate_role": "direct_beneficiary",
                "evidence_acquisition_status": "accepted_evidence_found",
                "accepted_evidence_count": 1,
                "source_pack": "listing_liquidity_pack",
                "why_opportunity_visible": "Move already happened and derivatives are crowded.",
            }
        },
    )

    assert "Event Alpha Fade / Short-Review Research" in message
    assert "move already happened" in message
    assert "Research-only. Not a trade signal." in message


def test_event_alpha_notification_delivery_status_fallback_and_api_preview_wording():
    import json

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    from crypto_rsi_scanner.event_alpha.notifications.delivery import NotificationDeliveryRecord

    record = NotificationDeliveryRecord(
        delivery_id="delivery-1",
        run_id="run-preview",
        alert_id="heartbeat:run-preview",
        profile="fixture",
        namespace="preview_status",
        lane="heartbeat",
        route="heartbeat",
        content_hash="hash-preview",
        state="blocked",
        delivery_state="",
        status_detail="",
        send_guard_enabled=False,
        would_send=True,
        sent=False,
        failed=False,
    )
    row = record.to_row()
    assert row["status"] == "would_send_but_guard_disabled"
    assert row["status_detail"] == "would_send_but_guard_disabled"
    legacy_row = dict(row)
    legacy_row.pop("status", None)
    assert event_alpha_artifact_doctor._delivery_status_field_conflicts(legacy_row)["delivery_status_missing"] == 1  # noqa: SLF001
    normalized = delivery.normalize_delivery_row(legacy_row)
    assert normalized["status"] == "would_send_but_guard_disabled"
    assert event_alpha_artifact_doctor._delivery_status_field_conflicts(normalized)["delivery_status_missing"] == 0  # noqa: SLF001

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        preview = base / "event_alpha_notification_preview.md"
        preview.write_text(
            "\n".join([
                "Completed: yes",
                "Raw events: 1 · Core opportunities: 1",
                "Alertable decisions: 0 · Alerts: 41",
                "Extraction rows: 1",
                "LLM calls/skips: 0/0",
                "Delivery lanes: due=1 · sent=0",
                "Send guard: no-send rehearsal",
                "No-send rehearsal: would send, but send guard is disabled.",
            ]),
            encoding="utf-8",
        )
        deliveries = base / "event_alpha_notification_deliveries.jsonl"
        row["notification_preview_path"] = str(preview)
        row["notification_preview_relpath"] = str(preview)
        deliveries.write_text(json.dumps(row) + "\n", encoding="utf-8")
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[
                {
                    "row_type": "event_alpha_run",
                    "run_id": "run-preview",
                    "started_at": "2026-06-15T16:00:00+00:00",
                    "profile": "fixture",
                    "artifact_namespace": "preview_status",
                    "run_mode": "test",
                    "cycle_completed": True,
                    "raw_events": 1,
                    "extraction_rows": 1,
                    "core_opportunity_rows_written": 1,
                    "alertable": 0,
                    "alerts": 0,
                    "send_lane_items_attempted": {"heartbeat": 1},
                    "send_lane_items_delivered": {"heartbeat": 0},
                }
            ],
            delivery_rows=[row],
            profile="fixture",
            artifact_namespace="preview_status",
            include_test_artifacts=True,
            strict=True,
        )
    assert result.notification_preview_api_alerts_wording == 1
    assert any("notification_preview_api_alerts_wording=1" in item for item in result.blockers)


def test_event_alpha_heartbeat_uses_strict_alert_and_research_candidate_copy():
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as event_alpha_notifications

    message = event_alpha_notifications.format_health_heartbeat(
        profile="fixture",
        result={
            "cycle_completed": True,
            "raw_events": 12,
            "core_opportunity_rows_written": 6,
            "extraction_rows": 0,
            "alertable": 0,
            "alerts": 0,
            "candidates": 7,
            "send_lane_items_attempted": {"heartbeat": 1},
            "send_lane_items_delivered": {"heartbeat": 0},
            "send_heartbeat_due": True,
            "send_heartbeat_sent": False,
        },
        send_guard_status="no-send guard enabled",
    )

    assert "Alerts:" not in message
    assert "Strict alerts: 0" in message
    assert "Research candidates: 7" in message
    assert "Current-generation core rows: 6" in message


def test_event_alpha_coinalyze_rehearsal_guards_no_key_default_and_budget():
    import json
    from datetime import datetime, timezone
    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight

    original_key = config.EVENT_DISCOVERY_COINALYZE_API_KEY
    original_symbols = config.EVENT_DISCOVERY_COINALYZE_SYMBOLS
    original_budget = os.environ.get(event_coinalyze_preflight.ENV_PREFLIGHT_MAX_REQUESTS)
    original_env_key = os.environ.get(event_coinalyze_preflight.ENV_API_KEY)
    original_allow = os.environ.get(event_coinalyze_preflight.ENV_ALLOW_LIVE_PREFLIGHT)
    calls = []

    def opener(_request, _timeout):
        calls.append("called")
        raise AssertionError("Coinalyze opener must not be called")

    try:
        config.EVENT_DISCOVERY_COINALYZE_API_KEY = ""
        config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A")
        os.environ.pop(event_coinalyze_preflight.ENV_API_KEY, None)
        os.environ.pop(event_coinalyze_preflight.ENV_ALLOW_LIVE_PREFLIGHT, None)
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=False,
                opener=opener,
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
            )
            assert report.status == "missing_config"
            assert not (base / event_coinalyze_preflight.REQUEST_LEDGER).exists()

        config.EVENT_DISCOVERY_COINALYZE_API_KEY = "coinalyze-key"
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=False,
                opener=opener,
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
            )
            assert report.status == "live_call_blocked_by_default"
            assert not (base / event_coinalyze_preflight.REQUEST_LEDGER).exists()
            assert any(
                event_coinalyze_preflight.ENV_ALLOW_LIVE_PREFLIGHT in note
                and "already exists in the environment" in note
                and "CLI allow flag may only accompany" in note
                for note in preflight.safety_notes
            )
            rehearsal_text = (base / event_coinalyze_preflight.REHEARSAL_MD).read_text(encoding="utf-8")
            assert f"set {event_coinalyze_preflight.ENV_ALLOW_LIVE_PREFLIGHT}=1 manually" in rehearsal_text
            assert "CLI allow flag may only accompany" in rehearsal_text

        os.environ[event_coinalyze_preflight.ENV_PREFLIGHT_MAX_REQUESTS] = "1"
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=True,
                opener=opener,
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
            )
            assert report.status == "live_call_blocked_by_default"
            assert not (base / event_coinalyze_preflight.REQUEST_LEDGER).exists()
        assert calls == []
    finally:
        config.EVENT_DISCOVERY_COINALYZE_API_KEY = original_key
        config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = original_symbols
        if original_budget is None:
            os.environ.pop(event_coinalyze_preflight.ENV_PREFLIGHT_MAX_REQUESTS, None)
        else:
            os.environ[event_coinalyze_preflight.ENV_PREFLIGHT_MAX_REQUESTS] = original_budget
        if original_env_key is None:
            os.environ.pop(event_coinalyze_preflight.ENV_API_KEY, None)
        else:
            os.environ[event_coinalyze_preflight.ENV_API_KEY] = original_env_key
        if original_allow is None:
            os.environ.pop(event_coinalyze_preflight.ENV_ALLOW_LIVE_PREFLIGHT, None)
        else:
            os.environ[event_coinalyze_preflight.ENV_ALLOW_LIVE_PREFLIGHT] = original_allow


def test_event_alpha_coinalyze_rehearsal_mocked_live_success_and_errors_are_redacted():
    import json
    from datetime import datetime, timezone
    from urllib.error import HTTPError
    from urllib.parse import urlparse
    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight

    original_key = config.EVENT_DISCOVERY_COINALYZE_API_KEY
    original_symbols = config.EVENT_DISCOVERY_COINALYZE_SYMBOLS
    original_base_url = config.EVENT_DISCOVERY_COINALYZE_BASE_URL
    original_allow = os.environ.get(event_coinalyze_preflight.ENV_ALLOW_LIVE_PREFLIGHT)
    try:
        config.EVENT_DISCOVERY_COINALYZE_API_KEY = "coinalyze-key"
        config.EVENT_DISCOVERY_COINALYZE_BASE_URL = "https://example.test/v1/"
        os.environ[event_coinalyze_preflight.ENV_ALLOW_LIVE_PREFLIGHT] = "1"

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

        def coinalyze_opener(
            symbol,
            *,
            price_end=140,
            oi_end=160,
            funding=0.0015,
            long_liq=12,
            short_liq=3,
            calls=None,
            empty=False,
        ):
            def opener(request, _timeout):
                endpoint = urlparse(request.full_url).path.rsplit("/", 1)[-1]
                if calls is not None:
                    calls.append(endpoint)
                if empty:
                    return FakeResponse([])
                if endpoint == "open-interest":
                    return FakeResponse([{"symbol": symbol, "value": 1000, "update": 1781513400}])
                if endpoint == "funding-rate":
                    return FakeResponse([{"symbol": symbol, "value": funding, "update": 1781513400}])
                if endpoint == "predicted-funding-rate":
                    return FakeResponse([{"symbol": symbol, "value": funding * 1.1, "update": 1781513400}])
                if endpoint == "open-interest-history":
                    return FakeResponse([{"symbol": symbol, "history": [{"c": 100}, {"c": oi_end}]}])
                if endpoint == "liquidation-history":
                    return FakeResponse([{"symbol": symbol, "history": [{"l": long_liq, "s": short_liq}]}])
                if endpoint == "long-short-ratio-history":
                    return FakeResponse([{"symbol": symbol, "history": [{"r": 1.8}]}])
                if endpoint == "ohlcv-history":
                    return FakeResponse([{"symbol": symbol, "history": [{"c": 100, "v": 50}, {"c": price_end, "v": 60}]}])
                raise AssertionError(endpoint)

            return opener

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            calls = []
            config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = ("TESTFADEUSDT_PERP.A",)
            _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=True,
                opener=coinalyze_opener("TESTFADEUSDT_PERP.A", calls=calls),
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
                clock=lambda: 1781513400,
            )
            assert report.status == "live_rehearsal_success"
            assert report.requests_used == 7
            assert report.provider_generation_id
            assert report.run_id
            assert calls == [
                "open-interest",
                "funding-rate",
                "predicted-funding-rate",
                "open-interest-history",
                "liquidation-history",
                "long-short-ratio-history",
                "ohlcv-history",
            ]
            assert report.snapshots_written == 1
            assert report.crowding_candidates_written == 1
            assert report.fade_review_candidates_written == 1
            assert report.fade_readiness_counts == {"ready_for_review": 1}
            ledger_text = (base / event_coinalyze_preflight.REQUEST_LEDGER).read_text(encoding="utf-8")
            assert "coinalyze-key" not in ledger_text
            assert all(json.loads(line)["token_redacted"] is True for line in ledger_text.splitlines() if line.strip())
            assert (base / "event_derivatives_state.jsonl").read_text(encoding="utf-8").count("\n") == 1
            state_rows = [
                json.loads(line)
                for line in (base / "event_derivatives_state.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            crowding_rows = [
                json.loads(line)
                for line in (base / "event_derivatives_crowding_candidates.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            fade_rows = [
                json.loads(line)
                for line in (base / "event_fade_short_review_candidates.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert state_rows[0]["supported_metric_status"]["predicted_funding"] == "implemented"
            assert state_rows[0]["supported_metric_status"]["basis"] == "not_implemented"
            assert state_rows[0]["open_interest_unit"] == "usd_notional"
            assert state_rows[0]["funding_rate_unit"] == "decimal_rate"
            assert state_rows[0]["basis_unit"] == "decimal_rate"
            assert state_rows[0]["derivatives_snapshot_freshness_status"] == "fresh"
            assert state_rows[0]["provider_generation_id"] == report.provider_generation_id
            assert state_rows[0]["provider_request_succeeded"] is True
            assert state_rows[0]["request_ledger_path"]
            assert len(crowding_rows) == 1
            assert len(fade_rows) == 1
            assert crowding_rows[0]["supported_metric_status"]["predicted_funding"] == "implemented"
            assert crowding_rows[0]["unit_metadata"]["funding_rate_unit"] == "decimal_rate"
            assert crowding_rows[0]["provider_generation_id"] == report.provider_generation_id
            assert fade_rows[0]["symbol"] == "TESTFADE"
            assert fade_rows[0]["opportunity_type"] == "FADE_SHORT_REVIEW"
            assert fade_rows[0]["research_only"] is True
            assert fade_rows[0]["no_send_rehearsal"] is True
            assert fade_rows[0]["strict_alerts_created"] == 0
            assert fade_rows[0]["telegram_sends"] == 0
            assert fade_rows[0]["trades_created"] == 0
            assert fade_rows[0]["paper_trades_created"] == 0
            assert fade_rows[0]["normal_rsi_signal_rows_written"] == 0
            assert fade_rows[0]["triggered_fade_created"] is False
            report_payload = json.loads((base / event_coinalyze_preflight.REHEARSAL_JSON).read_text(encoding="utf-8"))
            assert report_payload["crowding_candidates_written"] == 1
            assert report_payload["fade_review_candidates_written"] == 1
            assert report_payload["supported_metric_status"]["predicted_funding"] == "implemented"
            assert report_payload["supported_metric_status"]["basis"] == "not_implemented"
            assert report_payload["strict_alerts_created"] == 0
            assert report_payload["telegram_sends"] == 0
            assert report_payload["trades_created"] == 0
            assert report_payload["paper_trades_created"] == 0
            assert report_payload["normal_rsi_signal_rows_written"] == 0
            assert report_payload["triggered_fade_created"] == 0
            health = json.loads((base / "event_provider_health.json").read_text(encoding="utf-8"))
            assert "observed_healthy" in json.dumps(health)
            assert event_coinalyze_preflight.artifact_conflicts(base)["coinalyze_rehearsal_secret_leak"] == 0

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = ("TESTBREAKUSDT_PERP.A",)
            _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=True,
                opener=coinalyze_opener("TESTBREAKUSDT_PERP.A", price_end=114, oi_end=108, funding=0.001, long_liq=4, short_liq=4),
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
                clock=lambda: 1781513400,
            )
            assert report.status == "live_rehearsal_success"
            assert report.crowding_candidates_written == 1
            assert report.fade_review_candidates_written == 0
            rows = [
                json.loads(line)
                for line in (base / "event_derivatives_crowding_candidates.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert rows[0]["symbol"] == "TESTBREAK"
            assert rows[0]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
            assert rows[0]["crowding_class"] == "moderate"
            assert "confirmed_long_derivatives_crowding_warning" in rows[0]["warnings"]
            assert report.symbols_with_confirmed_long_crowding_warning == ("TESTBREAK",)
            assert not (base / "event_fade_short_review_candidates.jsonl").read_text(encoding="utf-8").strip()

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = ("EMPTYUSDT_PERP.A",)
            _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=True,
                opener=coinalyze_opener("EMPTYUSDT_PERP.A", empty=True),
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
                clock=lambda: 1781513400,
            )
            assert report.status == "provider_unavailable"
            assert report.snapshots_written == 0
            assert report.provider_health_status == "provider_unavailable"
            assert "observed_healthy" not in (base / "event_provider_health.json").read_text(encoding="utf-8")

        for code, expected_status in ((429, "rate_limited"), (401, "auth_or_access_error"), (403, "auth_or_access_error")):
            with TemporaryDirectory() as tmp:
                base = Path(tmp)
                config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = ("TESTFADEUSDT_PERP.A",)

                def failing_opener(request, _timeout, *, code=code):
                    raise HTTPError(request.full_url, code, "safe failure", hdrs={}, fp=None)

                _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                    namespace_dir=base,
                    provider_health_path=base / "event_provider_health.json",
                    profile="notify_llm_deep",
                    artifact_namespace="coinalyze_no_send_rehearsal",
                    allow_live_preflight=True,
                    opener=failing_opener,
                    now=datetime(2026, 6, 15, tzinfo=timezone.utc),
                    clock=lambda: 1781513400,
                )
                assert report.status == expected_status
                ledger = (base / event_coinalyze_preflight.REQUEST_LEDGER).read_text(encoding="utf-8")
                assert "coinalyze-key" not in ledger
                assert str(code) in ledger
    finally:
        config.EVENT_DISCOVERY_COINALYZE_API_KEY = original_key
        config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = original_symbols
        config.EVENT_DISCOVERY_COINALYZE_BASE_URL = original_base_url
        if original_allow is None:
            os.environ.pop(event_coinalyze_preflight.ENV_ALLOW_LIVE_PREFLIGHT, None)
        else:
            os.environ[event_coinalyze_preflight.ENV_ALLOW_LIVE_PREFLIGHT] = original_allow
