"""Placeholder package for future artifact doctor test extraction."""

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _legacy_helpers as _event_alpha_legacy_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_legacy_helpers).items()
    if not name.startswith("__")
})

def test_event_alpha_live_provider_readiness_smoke_artifacts_are_safe_and_doctor_checked():
    import json
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_live_provider_readiness

    source_coverage_text = "\n".join([
        "EVENT ALPHA SOURCE COVERAGE",
        "Most useful next data source categories:",
        "1. Derivatives/OI/funding",
        "2. Official exchange announcements",
        "3. Structured unlock/calendar",
        "6. Context/news",
        "Live-provider activation readiness:",
        "- readiness report: event_live_provider_activation_readiness.md",
        "Most useful next data source:",
        "- coinalyze: missing derivatives confirmation",
    ])
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        source_path = base / "event_alpha_source_coverage.md"
        source_path.write_text(source_coverage_text, encoding="utf-8")
        report = event_live_provider_readiness.build_readiness_report(
            profile="fixture",
            artifact_namespace="live_provider_readiness_smoke",
            smoke_mode=True,
            now=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        json_path, md_path = event_live_provider_readiness.write_readiness_artifacts(report, base)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["live_calls_allowed"] is False
        assert payload["smoke_mode"] is True
        assert payload["activation_runbook"]
        assert all(provider["live_call_allowed"] is False for provider in payload["providers"])
        by_provider = {provider["provider_name"]: provider for provider in payload["providers"]}
        assert by_provider["coinalyze"]["sidecar_fixture_available"] is True
        assert by_provider["coinalyze"]["smoke_target_available"] is True
        assert "event-alpha-derivatives-smoke" in by_provider["coinalyze"]["smoke_targets"]
        assert "event-alpha-fade-review-smoke" in by_provider["coinalyze"]["smoke_targets"]
        assert by_provider["bybit_announcements_public"]["env_vars_required"] == []
        assert by_provider["bybit_announcements_public"]["request_ledger_required"] is True
        assert "event-alpha-bybit-announcements-preflight-smoke" in by_provider["bybit_announcements_public"]["smoke_targets"]
        assert by_provider["bybit_announcements_public"]["next_safe_command"].startswith("make event-alpha-bybit-announcements-preflight")
        assert by_provider["bybit_announcements_public"]["no_send_rehearsal_command"].startswith("make event-alpha-bybit-announcements-no-send-rehearsal")
        assert by_provider["binance_announcements_public_or_fixture"]["env_vars_required"] == []
        assert by_provider["binance_announcements_public_or_fixture"]["preflight_status"] == "fixture_ready"
        assert by_provider["binance_announcements_signed_listener"]["env_vars_required"]
        assert by_provider["binance_announcements_signed_listener"]["activation_phase"] == "blocked"
        assert by_provider["tokenomist"]["env_vars_required"] == [
            "RSI_EVENT_ALPHA_SCHEDULED_CATALYST_TOKENOMIST_PATH",
            "TOKENOMIST_API_KEY",
        ]
        assert by_provider["messari_unlocks"]["env_vars_required"] == [
            "RSI_EVENT_ALPHA_SCHEDULED_CATALYST_MESSARI_PATH",
            "MESSARI_API_KEY",
        ]
        assert by_provider["coinmarketcal"]["env_vars_required"] == [
            "RSI_EVENT_ALPHA_SCHEDULED_CATALYST_COINMARKETCAL_PATH",
            "COINMARKETCAL_API_KEY",
        ]
        assert "event-alpha-tokenomist-preflight" in by_provider["tokenomist"]["smoke_targets"]
        assert "event-alpha-messari-unlocks-preflight" in by_provider["messari_unlocks"]["smoke_targets"]
        assert "event-alpha-coinmarketcal-preflight" in by_provider["coinmarketcal"]["smoke_targets"]
        assert by_provider["geckoterminal"]["env_vars_required"] == [
            "RSI_EVENT_ALPHA_DEX_GECKOTERMINAL_PATH",
        ]
        assert by_provider["geckoterminal"]["preflight_status"] == "quota_guarded"
        assert by_provider["geckoterminal"]["live_call_allowed"] is False
        assert "event-alpha-dex-onchain-readiness-smoke" in by_provider["geckoterminal"]["smoke_targets"]
        assert by_provider["coingecko_dex"]["env_vars_required"] == [
            "RSI_EVENT_ALPHA_DEX_COINGECKO_PATH",
            "COINGECKO_API_KEY",
        ]
        assert by_provider["coingecko_dex"]["preflight_status"] == "quota_guarded"
        assert by_provider["coingecko_dex"]["live_call_allowed"] is False
        assert by_provider["defillama_tvl_fees_revenue"]["env_vars_required"] == [
            "RSI_EVENT_ALPHA_PROTOCOL_DEFILLAMA_PATH",
        ]
        assert by_provider["defillama_tvl_fees_revenue"]["preflight_status"] == "quota_guarded"
        assert by_provider["defillama_tvl_fees_revenue"]["live_call_allowed"] is False
        assert not event_alpha_artifact_doctor._text_has_secret_like_value(md_path.read_text(encoding="utf-8"))
        clean = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=source_path,
            profile="fixture",
            artifact_namespace="live_provider_readiness_smoke",
            include_test_artifacts=True,
            strict=True,
        )
        assert clean.live_provider_readiness_missing == 0
        assert clean.live_provider_readiness_live_calls_allowed_in_smoke == 0
        assert clean.live_provider_readiness_configured_missing_env == 0
        assert clean.live_provider_readiness_secret_leak == 0

        payload["live_calls_allowed"] = True
        payload["providers"][0]["live_call_allowed"] = True
        payload["providers"][0]["configured"] = True
        payload["providers"][0]["preflight_status"] = "missing_config"
        payload["providers"][0]["last_error_safe"] = "api_key='THIS_IS_A_TEST_SECRET_VALUE_123456'"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        unsafe = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=source_path,
            profile="fixture",
            artifact_namespace="live_provider_readiness_smoke",
            include_test_artifacts=True,
            strict=True,
        )
        assert unsafe.live_provider_readiness_live_calls_allowed_in_smoke >= 1
        assert unsafe.live_provider_readiness_configured_missing_env == 1
        assert unsafe.live_provider_readiness_secret_leak == 1
        assert unsafe.status == "BLOCKED"


def test_event_alpha_artifact_doctor_schema_only_catches_bad_fixture():
    import json
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "event_integrated_radar_candidates.jsonl").write_text(
            json.dumps(
                {
                    "row_type": "event_integrated_radar_candidate",
                    "symbol": "BAD",
                    "opportunity_type": "CONFIRMED_LONG_RESEARCH",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
            schema_only=True,
        )
        text = event_alpha_artifact_doctor.format_artifact_doctor_report(result)

        assert result.status == "BLOCKED"
        assert result.schema_only is True
        assert result.legacy_checks_skipped is True
        assert result.schema_rows_validated == 1
        assert result.schema_validation_errors == 1
        assert result.missing_required_fields == 1
        assert "schema_rows_validated=1" in text
        assert "schema_validation_errors=1" in text
        assert "missing_required_fields=1" in text


def test_event_alpha_artifact_doctor_skip_legacy_keeps_schema_phases_only():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        full = event_alpha_artifact_doctor.diagnose_artifacts(
            inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
        )
        skipped = event_alpha_artifact_doctor.diagnose_artifacts(
            inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
            skip_legacy_checks=True,
        )
        text = event_alpha_artifact_doctor.format_artifact_doctor_report(skipped)

        assert full.status == "BLOCKED"
        assert "no matching operational/burn-in run rows found" in full.blockers
        assert skipped.status == "OK"
        assert skipped.legacy_checks_skipped is True
        assert skipped.blockers == ()
        assert "legacy_checks_skipped=true" in text


def test_event_alpha_coinalyze_preflight_smoke_artifacts_are_safe_and_doctor_checked():
    import json
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_coinalyze_preflight

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        report = event_coinalyze_preflight.build_preflight_report(
            namespace_dir=base,
            smoke_mode=True,
            allow_live_preflight=False,
            now=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        json_path, md_path = event_coinalyze_preflight.write_preflight_artifacts(report, base)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["provider"] == "coinalyze"
        assert payload["category"] == "derivatives_oi_funding"
        assert payload["smoke_mode"] is True
        assert payload["live_call_allowed"] is False
        assert payload["env_vars_required"] == ["RSI_EVENT_DISCOVERY_COINALYZE_API_KEY"]
        assert payload["fixture_parser_status"] == "pass"
        assert payload["fixture_symbol_mapping_status"] == "pass"
        assert "open_interest" in payload["supported_metrics"]
        assert "FADE_SHORT_REVIEW" in ", ".join(payload["lanes_enabled_if_healthy"])
        assert "No provider network calls" in md_path.read_text(encoding="utf-8")
        assert event_coinalyze_preflight.artifact_conflicts(base) == {
            "coinalyze_preflight_secret_leak": 0,
            "coinalyze_preflight_live_call_allowed_in_smoke": 0,
            "coinalyze_preflight_configured_missing_env": 0,
            "coinalyze_preflight_ready_without_request_ledger": 0,
            "coinalyze_preflight_missing_fixture_parser_status": 0,
            "coinalyze_preflight_forbidden_side_effect_claim": 0,
            "coinalyze_rehearsal_secret_leak": 0,
            "coinalyze_rehearsal_live_without_ledger": 0,
            "coinalyze_rehearsal_live_call_allowed_in_smoke": 0,
            "coinalyze_rehearsal_live_without_explicit_allow": 0,
            "coinalyze_rehearsal_request_budget_exceeded": 0,
            "coinalyze_rehearsal_success_without_derivatives_state": 0,
            "coinalyze_rehearsal_success_without_crowding_candidates": 0,
            "coinalyze_provider_health_healthy_without_successful_ledger": 0,
            "coinalyze_rehearsal_forbidden_side_effect_claim": 0,
            "coinalyze_supported_metric_implemented_missing_state": 0,
        }
        clean = event_alpha_artifact_doctor.diagnose_artifacts(
            profile="fixture",
            artifact_namespace="coinalyze_preflight_smoke",
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            include_test_artifacts=True,
            strict=True,
        )
        assert clean.coinalyze_preflight_live_call_allowed_in_smoke == 0
        assert clean.coinalyze_preflight_missing_fixture_parser_status == 0

        payload["live_call_allowed"] = True
        payload["configured"] = True
        payload["fixture_parser_status"] = ""
        payload["safety_notes"] = ["send Telegram and execute order"]
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        with md_path.open("a", encoding="utf-8") as fh:
            fh.write("api_key='THIS_IS_A_TEST_SECRET_VALUE_123456'\n")
        conflicts = event_coinalyze_preflight.artifact_conflicts(base)
        assert conflicts["coinalyze_preflight_secret_leak"] == 1
        assert conflicts["coinalyze_preflight_live_call_allowed_in_smoke"] == 1
        assert conflicts["coinalyze_preflight_missing_fixture_parser_status"] == 1
        assert conflicts["coinalyze_preflight_forbidden_side_effect_claim"] == 1
        unsafe = event_alpha_artifact_doctor.diagnose_artifacts(
            profile="fixture",
            artifact_namespace="coinalyze_preflight_smoke",
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            include_test_artifacts=True,
            strict=True,
        )
        assert unsafe.coinalyze_preflight_secret_leak == 1
        assert unsafe.coinalyze_preflight_live_call_allowed_in_smoke == 1
        assert unsafe.coinalyze_preflight_missing_fixture_parser_status == 1
        assert unsafe.status == "BLOCKED"


def test_event_alpha_coinalyze_rehearsal_doctor_blocks_missing_live_artifacts():
    import json
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_coinalyze_preflight

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        rehearsal = {
            "schema_version": "event_coinalyze_rehearsal_v1",
            "row_type": "event_coinalyze_rehearsal_report",
            "provider": "coinalyze",
            "status": "live_rehearsal_success",
            "configured": True,
            "allow_live_preflight": True,
            "live_call_allowed": True,
            "no_send": True,
            "research_only": True,
            "generated_at": "2026-06-15T16:00:00+00:00",
            "request_ledger_path": "event_coinalyze_request_ledger.jsonl",
            "snapshots_written": 1,
            "crowding_candidates_written": 0,
            "fade_review_candidates_written": 0,
            "supported_metric_status": {"basis": "implemented"},
            "max_requests_per_run": 6,
            "requests_used": 1,
            "strict_alerts_created": 0,
            "telegram_sends": 0,
            "trades_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fade_created": 0,
        }
        (base / event_coinalyze_preflight.REHEARSAL_JSON).write_text(json.dumps(rehearsal), encoding="utf-8")
        (base / event_coinalyze_preflight.REHEARSAL_MD).write_text("Research-only. Not a trade signal.\n", encoding="utf-8")
        (base / "event_provider_health.json").write_text(
            json.dumps({
                "schema_version": "event_provider_health_v1",
                "providers": {
                    "coinalyze:derivatives_no_send_rehearsal": {
                        "provider": "coinalyze",
                        "provider_key": "coinalyze:derivatives_no_send_rehearsal",
                        "provider_service": "coinalyze",
                        "provider_coverage_status": "observed_healthy",
                        "last_success_at": "2026-06-15T16:00:00+00:00",
                        "consecutive_failures": 0,
                    }
                },
            }),
            encoding="utf-8",
        )

        conflicts = event_coinalyze_preflight.artifact_conflicts(base)
        assert conflicts["coinalyze_rehearsal_live_without_ledger"] == 1
        assert conflicts["coinalyze_rehearsal_success_without_crowding_candidates"] == 1
        assert conflicts["coinalyze_provider_health_healthy_without_successful_ledger"] == 1
        assert conflicts["coinalyze_supported_metric_implemented_missing_state"] == 1

        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            profile="fixture",
            artifact_namespace="coinalyze_no_send_rehearsal",
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor.coinalyze_rehearsal_live_without_ledger == 1
        assert doctor.coinalyze_rehearsal_success_without_crowding_candidates == 1
        assert doctor.coinalyze_provider_health_healthy_without_successful_ledger == 1
        assert doctor.coinalyze_supported_metric_implemented_missing_state == 1
        assert doctor.status == "BLOCKED"


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

        index_only = event_alpha_artifact_doctor.diagnose_artifacts(
            card_paths=[Path("/tmp/research_cards/index.md")],
        )
        assert index_only.card_files == 0
        assert index_only.research_card_files == 0
        assert index_only.research_card_index_present is True
        two_cards = event_alpha_artifact_doctor.diagnose_artifacts(
            card_paths=[
                Path("/tmp/research_cards/index.md"),
                Path("/tmp/research_cards/card_a.md"),
                Path("/tmp/research_cards/card_b.md"),
            ],
        )
        assert two_cards.card_files == 2
        assert two_cards.research_card_files == 2
        assert two_cards.research_card_index_present is True
        high_without_card = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{**run_rows[0], "run_id": "hp", "snapshot_rows_written": 1}],
            alert_rows=[{**alert_rows[0], "run_id": "hp", "tier": "HIGH_PRIORITY_WATCH"}],
            card_paths=[Path("/tmp/research_cards/index.md")],
            profile="no_key_live",
            artifact_namespace="no_key_live",
        )
        assert "no research cards" in "; ".join(high_without_card.warnings)
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_event_alpha_doctor_flags_unconfirmed_narrative_digest_and_core_visibility():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alpha_artifact_doctor,
        event_alpha_notification_delivery as delivery,
        event_core_opportunities,
    )

    fan_core = {
        "row_type": "event_core_opportunity",
        "core_opportunity_id": "core-fan",
        "profile": "notify_llm_deep",
        "artifact_namespace": "notify_llm_deep",
        "run_mode": "notification_burn_in",
        "symbol": "FAN",
        "coin_id": "fan-token",
        "incident_id": "world-cup-single-source",
        "candidate_role": "proxy_instrument",
        "impact_path_type": "fan_sports",
        "source_pack": "fan_sports_pack",
        "final_route_after_quality_gate": "RESEARCH_DIGEST",
        "opportunity_level": "validated_digest",
        "accepted_evidence_count": 1,
        "accepted_provider_counts": {"cryptopanic": 1},
        "accepted_reason_codes": ("cryptopanic_currency_tag_match",),
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
    }
    row = delivery.build_record(
        run_id="run-fan",
        alert_id="core-fan",
        profile="notify_llm_deep",
        namespace="notify_llm_deep",
        lane="daily_digest",
        route="RESEARCH_DIGEST",
        content_hash="hash-fan",
        core_opportunity_id="core-fan",
        core_opportunity_ids=("core-fan",),
        canonical_symbol="FAN",
        canonical_coin_id="fan-token",
        feedback_target="core-fan",
        canonical_card_path="cards/fan.md",
        state=delivery.STATE_BLOCKED,
        delivery_state=delivery.STATE_BLOCKED,
        delivery_mode="no_send_preview",
        status_detail="would_send_but_guard_disabled",
        now=datetime(2026, 6, 20, 12, tzinfo=timezone.utc),
    ).to_row()
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        core_opportunity_rows=[fan_core],
        evidence_acquisition_rows=[
            {
                "core_opportunity_id": "core-fan",
                "profile": "notify_llm_deep",
                "artifact_namespace": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "accepted_evidence_count": 2,
                "accepted_evidence": [{"provider": "cryptopanic"}],
                "rejected_evidence_count": 0,
                "rejected_evidence": [],
            }
        ],
        delivery_rows=[row],
        run_rows=[{
            "run_id": "run-fan",
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep",
            "run_mode": "notification_burn_in",
        }],
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep",
        strict=False,
    )
    assert doctor.unconfirmed_narrative_daily_digest == 1
    assert doctor.single_source_no_market_fan_token_digest == 1
    assert doctor.evidence_count_mismatch == 1

    velvet_base = {
        "incident_id": "incident:spacex",
        "profile": "notify_llm_deep",
        "artifact_namespace": "notify_llm_deep",
        "run_mode": "notification_burn_in",
        "external_asset": "SpaceX",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "impact_path_type": "venue_value_capture",
        "source_pack": "proxy_preipo_rwa_pack",
        "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
        "opportunity_level": "high_priority",
        "opportunity_score_final": 92,
    }
    cores = event_core_opportunities.visible_core_opportunities([
        {**velvet_base, "main_frame_type": "tokenized_stock_venue", "hypothesis_id": "hyp:velvet:venue"},
        {**velvet_base, "main_frame_type": "rwa_preipo_proxy", "hypothesis_id": "hyp:velvet:rwa"},
        {
            "incident_id": "incident:sports-sector",
            "symbol": "SECTOR",
            "coin_id": "sector:sports_fan_proxy",
            "candidate_role": "sector_context",
            "impact_path_type": "fan_sports",
            "source_pack": "fan_sports_pack",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 77,
        },
    ])
    assert [item.symbol for item in cores] == ["VELVET"]
    assert len(cores[0].supporting_rows) == 2

    sector_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        core_opportunity_rows=[
            {
                "core_opportunity_id": "sector-core",
                "profile": "notify_llm_deep",
                "artifact_namespace": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "symbol": "SECTOR",
                "coin_id": "sector:sports_fan_proxy",
                "final_route_after_quality_gate": "RESEARCH_DIGEST",
                "opportunity_level": "validated_digest",
            },
            {**velvet_base, "core_opportunity_id": "velvet-a"},
            {**velvet_base, "core_opportunity_id": "velvet-b"},
        ],
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep",
        strict=False,
    )
    assert sector_doctor.visible_sector_core_without_config == 1
    assert sector_doctor.duplicate_proxy_core_rows == 1


def test_event_alpha_artifact_doctor_flags_notification_identity_and_preview_conflicts():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Telegram Body\n\n"
            "```html\n"
            "alert_id=ea:hypothesis|incident:btc route=RESEARCH_DIGEST research_card=/tmp/card.md\n"
            "```",
            encoding="utf-8",
        )
        core = {
            "row_type": "event_core_opportunity",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "core_opportunity_id": "agg:btc-weak",
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "final_opportunity_level": "validated_digest",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "treasury_context",
            "canonical_incident_name": "Strategy valuation discount versus Bitcoin treasury holdings",
            "latest_source_title": "MSTR valuation discount widens despite BTC holdings",
            "source_class": "crypto_news",
            "evidence_acquisition_status": "rejected_results_only",
            "acquisition_confirmation_status": "does_not_confirm",
            "accepted_evidence_count": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
        }
        delivery_row = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivery-1",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "alert_id": "ea:hypothesis|incident:btc",
            "core_opportunity_id": "agg:btc-weak",
            "lane": "daily_digest",
            "route": "RESEARCH_DIGEST",
            "state": "delivered",
            "attempted_at": "2026-06-28T12:00:00+00:00",
            "delivered_at": "2026-06-28T12:00:01+00:00",
            "notification_preview_path": str(preview),
            "notification_preview_relpath": str(preview),
        }
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-1",
                "row_type": "event_alpha_run",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "notify_llm_deep",
                "alertable": 1,
                "snapshot_write_success": True,
                "snapshot_rows_written": 1,
            }],
            alert_rows=[],
            core_opportunity_rows=[core],
            delivery_rows=[delivery_row],
            strict=True,
        )
    assert result.delivery_alert_id_not_canonical == 1
    assert result.delivery_feedback_target_missing == 1
    assert result.delivery_card_path_missing == 1
    assert result.digest_item_without_live_confirmation == 1
    assert result.digest_item_rejected_results_only == 1
    assert result.strategic_broad_asset_digest_without_confirmation == 1
    assert result.telegram_message_contains_absolute_path == 1
    assert result.telegram_message_contains_raw_debug_dump == 1
    assert result.status == "BLOCKED"


def test_event_alpha_artifact_doctor_blocks_preview_run_summary_mismatch():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        namespace = "preview_mismatch_test"
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane 1: health_heartbeat\n\n"
            "status: blocked\n"
            "would_send: true\n"
            "sent: false\n\n"
            "### Telegram Body\n\n"
            "```html\n"
            "<b>Event Alpha Heartbeat</b>\n"
            "Completed: no\n"
            "Raw events: 0 · Core opportunities: 0\n"
            "Alertable decisions: 0 · Sent by this lane: heartbeat\n"
            "```",
            encoding="utf-8",
        )
        delivery_row = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "heartbeat-blocked",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": namespace,
            "alert_id": "heartbeat",
            "lane": "health_heartbeat",
            "route": "HEALTH_HEARTBEAT",
            "state": "blocked",
            "error_class": "guard_blocked",
            "error_message_safe": "event alerts disabled",
            "attempted_at": "2026-06-29T12:00:00+00:00",
            "notification_preview_path": str(preview),
        }
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "row_type": "event_alpha_run",
                "run_id": "run-1",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": namespace,
                "cycle_completed": True,
                "raw_events": 159,
                "core_opportunity_rows_written": 122,
                "alertable": 0,
                "success": True,
            }],
            core_opportunity_rows=[],
            delivery_rows=[delivery_row],
            profile="notify_llm_deep",
            artifact_namespace=namespace,
            strict=True,
        )
        text = event_alpha_artifact_doctor.format_artifact_doctor_report(result)

    assert result.notification_preview_run_summary_mismatch >= 1
    assert result.notification_preview_core_count_mismatch == 1
    assert result.notification_preview_missing_send_guard_status == 1
    assert result.notification_preview_no_send_status_unclear == 1
    assert result.status == "BLOCKED"
    assert "preview_run_mismatch=" in text
    assert "preview_core_mismatch=1" in text


def test_event_alpha_send_readiness_blocks_missing_preview_file():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alpha_artifact_doctor,
        event_alpha_notification_delivery,
        event_alpha_send_readiness,
    )

    with TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            namespace = "missing_preview"
            delivery_row = event_alpha_notification_delivery.build_record(
                run_id="run-1",
                alert_id="heartbeat",
                profile="notify_llm_deep",
                namespace=namespace,
                lane="health_heartbeat",
                route="HEALTH_HEARTBEAT",
                content_hash="hash",
                state=event_alpha_notification_delivery.STATE_BLOCKED,
                now=datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc),
                error_class="guard_blocked",
                error_message="event alerts disabled",
                notification_preview_path="/Users/old/checkout/event_fade_cache/missing_preview/event_alpha_notification_preview.md",
            ).to_row()
            delivery_row["run_mode"] = "notification_burn_in"
            doctor = event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult(
                status="OK",
                profile="notify_llm_deep",
                artifact_namespace=namespace,
                run_rows=1,
                alert_rows=0,
                feedback_rows=0,
                outcome_rows=0,
                card_files=0,
            )
            result = event_alpha_send_readiness.build_send_readiness(
                profile="notify_llm_deep",
                artifact_namespace=namespace,
                run_rows=[{
                    "row_type": "event_alpha_run",
                    "run_id": "run-1",
                    "profile": "notify_llm_deep",
                    "run_mode": "notification_burn_in",
                    "artifact_namespace": namespace,
                    "started_at": "2026-06-29T12:00:00+00:00",
                    "cycle_completed": True,
                    "success": True,
                }],
                core_opportunity_rows=[],
                alert_rows=[],
                delivery_rows=[delivery_row],
                artifact_doctor=doctor,
                send_guard_enabled=False,
                telegram_ready=False,
            )
        finally:
            os.chdir(old_cwd)

    assert result.preview_path_source == "missing"
    assert any("notification preview" in blocker for blocker in result.blockers)


def test_event_alpha_artifact_doctor_blocks_digest_delivery_without_core_identity():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane 1: daily_digest\n\n"
            "### Telegram Body\n\n"
            "```html\n"
            "<b>Event Alpha Research Digest</b>\n"
            "TAO / bittensor\n"
            "```",
            encoding="utf-8",
        )
        delivery_row = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivery-missing-core",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "alert_id": "ea:hypothesis|incident:8ba9e42c8d86|bittensor",
            "lane": "daily_digest",
            "route": "RESEARCH_DIGEST",
            "state": "delivered",
            "attempted_at": "2026-06-28T12:00:00+00:00",
            "delivered_at": "2026-06-28T12:00:01+00:00",
            "notification_preview_path": str(preview),
            "identity_reconciliation_reason": "source_alert_identity",
        }
        heartbeat = dict(
            delivery_row,
            delivery_id="delivery-heartbeat",
            alert_id="heartbeat",
            lane="health_heartbeat",
            route="HEALTH_HEARTBEAT",
            identity_reconciliation_reason="heartbeat",
        )
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-1",
                "row_type": "event_alpha_run",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "notify_llm_deep",
                "alertable": 1,
                "snapshot_write_success": True,
                "snapshot_rows_written": 1,
            }],
            core_opportunity_rows=[],
            delivery_rows=[delivery_row, heartbeat],
            strict=True,
        )
    assert result.delivery_core_id_missing == 1
    assert result.delivery_feedback_target_missing == 1
    assert result.delivery_card_path_missing == 1
    assert result.delivery_alert_id_not_canonical == 1
    assert result.notification_preview_missing == 0
    assert result.status == "BLOCKED"


def test_event_alpha_artifact_doctor_accepts_multi_core_digest_and_core_route_derivation():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane 1: daily_digest\n\n"
            "### Telegram Body\n\n"
            "```html\n"
            "<b>Event Alpha Research Digest</b>\n"
            "VELVET / velvet\n"
            "AAVE / aave\n"
            "```",
            encoding="utf-8",
        )
        run = {
            "run_id": "run-1",
            "row_type": "event_alpha_run",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "cycle_completed": True,
            "success": True,
            "alertable": 2,
            "snapshot_write_success": True,
            "snapshot_rows_written": 1,
        }
        core_a = {
            "row_type": "event_core_opportunity",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "core_opportunity_id": "core_a",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "final_opportunity_level": "validated_digest",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "evidence_acquisition_status": "accepted_evidence_found",
            "acquisition_confirmation_status": "confirms",
            "accepted_evidence_count": 1,
            "market_confirmation_level": "fresh",
            "market_context_freshness_status": "fresh",
        }
        core_b = dict(
            core_a,
            core_opportunity_id="core_b",
            symbol="AAVE",
            coin_id="aave",
        )
        delivery_row = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivery-multi-core",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "alert_id": "core_b,core_a",
            "requested_alert_id": "core_a,core_b",
            "core_opportunity_id": "core_a,core_b",
            "feedback_target": "core_a,core_b",
            "canonical_card_path": "cards/core_a.md,cards/core_b.md",
            "lane": "daily_digest",
            "route": "RESEARCH_DIGEST",
            "state": "blocked",
            "delivery_mode": "no_send",
            "status_detail": "would_send_but_guard_disabled",
            "attempted_at": "2026-06-28T12:00:00+00:00",
            "notification_preview_path": str(preview),
            "notification_preview_relpath": str(preview),
        }
        alert_row = {
            "row_type": "event_alpha_alert_snapshot",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "alert_id": "ea:test|core_a",
            "core_opportunity_id": "core_a",
            "feedback_target": "core_a",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "opportunity_level": "validated_digest",
            "final_opportunity_level": "validated_digest",
            "opportunity_score_final": 72.0,
            "impact_path_type": "tokenized_stock_venue",
            "candidate_role": "proxy_venue",
            "source_class": "cryptopanic_tagged",
            "evidence_specificity": "token_and_catalyst",
            "requested_route_before_quality_gate": "STORE_ONLY",
            "route": "RESEARCH_DIGEST",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "route_alertable": True,
            "alertable_after_quality_gate": True,
            "quality_gate_block_reason": "core_route_derived_from_opportunity_level:validated_digest",
            "final_state_after_quality_gate": "RADAR",
        }
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[run],
            alert_rows=[alert_row],
            core_opportunity_rows=[core_a, core_b],
            delivery_rows=[delivery_row],
            strict=True,
        )

    assert result.delivery_identity_mismatch_core_store == 0
    assert result.delivery_alert_id_not_canonical == 0
    assert result.fresh_quality_route_conflict_rows == 0
    assert result.alert_snapshot_route_mismatch_core_store == 0


def test_event_alpha_artifact_doctor_scopes_delivery_identity_to_latest_run():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane 1: daily_digest\n\n"
            "### Telegram Body\n\n"
            "```html\n"
            "<b>Event Alpha Research Digest</b>\n"
            "VELVET / velvet\n"
            "```",
            encoding="utf-8",
        )
        old_bad = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivery-old",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "alert_id": "ea:hypothesis|incident:old|tao",
            "lane": "daily_digest",
            "route": "RESEARCH_DIGEST",
            "state": "delivered",
            "attempted_at": "2026-06-28T12:00:00+00:00",
            "delivered_at": "2026-06-28T12:00:01+00:00",
            "notification_preview_path": str(preview),
            "identity_reconciliation_reason": "source_alert_identity",
        }
        current_clean = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivery-new",
            "run_id": "run-2",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "alert_id": "agg:velvet-spacex",
            "requested_alert_id": "agg:velvet-spacex",
            "core_opportunity_id": "agg:velvet-spacex",
            "canonical_symbol": "VELVET",
            "canonical_coin_id": "velvet",
            "canonical_card_path": "research_cards/velvet.md",
            "feedback_target": "agg:velvet-spacex",
            "lane": "daily_digest",
            "route": "RESEARCH_DIGEST",
            "state": "blocked",
            "attempted_at": "2026-06-29T12:00:00+00:00",
            "notification_preview_path": str(preview),
            "identity_reconciliation_reason": "canonical_core_opportunity",
        }
        core = {
            "row_type": "event_core_opportunity",
            "run_id": "run-2",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "core_opportunity_id": "agg:velvet-spacex",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "final_opportunity_level": "validated_digest",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "impact_path_type": "tokenized_stock_venue",
            "evidence_acquisition_status": "accepted_evidence_found",
            "acquisition_confirmation_status": "confirms",
            "accepted_evidence_count": 1,
            "market_confirmation_level": "fresh",
            "market_context_freshness_status": "fresh",
        }
        runs = [
            {
                "run_id": "run-1",
                "row_type": "event_alpha_run",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "notify_llm_deep_rehearsal",
                "alertable": 1,
                "snapshot_write_success": True,
                "snapshot_rows_written": 0,
            },
            {
                "run_id": "run-2",
                "row_type": "event_alpha_run",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "notify_llm_deep_rehearsal",
                "alertable": 0,
                "snapshot_write_success": True,
                "snapshot_rows_written": 0,
            },
        ]
        latest = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=runs,
            core_opportunity_rows=[core],
            delivery_rows=[old_bad, current_clean],
            strict=True,
        )
        all_rows = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=runs,
            core_opportunity_rows=[core],
            delivery_rows=[old_bad, current_clean],
            strict=True,
            delivery_strict_scope="all_rows",
        )
    latest_text = event_alpha_artifact_doctor.format_artifact_doctor_report(latest)
    assert latest.latest_run_id == "run-2"
    assert latest.latest_run_delivery_rows == 1
    assert latest.stale_delivery_rows == 1
    assert latest.stale_delivery_identity_missing_core == 1
    assert latest.delivery_core_id_missing == 0
    assert latest.delivery_feedback_target_missing == 0
    assert latest.delivery_card_path_missing == 0
    assert "pre-canonical notification delivery rows" in latest_text
    assert any("run-1" in warning and "zero alert snapshots" in warning for warning in latest.warnings)
    assert "strict_scope=latest_run" in latest_text
    assert all_rows.status == "BLOCKED"
    assert all_rows.delivery_core_id_missing == 1
    assert any("run-1" in blocker and "zero alert snapshots" in blocker for blocker in all_rows.blockers)
    assert all_rows.delivery_strict_scope == "all_rows"


def test_artifact_doctor_blocks_broken_daily_brief_selection():
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_alpha_notifications as notif

    namespace = "notify_llm_deep_research_review_smoke"
    run_id = "2026-06-15T16:00:00+00:00|notify_llm_deep"
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        brief_path = root / "event_alpha_daily_brief.md"
        source_coverage = root / "event_alpha_source_coverage.md"
        source_coverage.write_text("EVENT ALPHA SOURCE COVERAGE\n", encoding="utf-8")
        brief_path.write_text(
            "\n".join([
                "# Event Alpha Daily Brief",
                "Requested profile: notify_llm_deep",
                f"Artifact namespace: {namespace}",
                "Selected run profile: none",
                "Selected run namespace: none",
                "",
                "## Executive Summary",
                "- Core opportunities: 0 (canonical_store_rows=0, high_priority=0)",
                "",
                "### Research Review Digest",
                "- Lane count sent/due: 0/0",
                "",
                "### System Health / Providers / Budget",
                "- No run ledger rows found.",
            ]),
            encoding="utf-8",
        )
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "row_type": "event_alpha_run",
                "run_id": run_id,
                "profile": "notify_llm_deep",
                "run_mode": "test",
                "artifact_namespace": namespace,
                "success": True,
                "research_review_digest_enabled": True,
                "research_review_digest_candidates": 1,
                "research_review_digest_would_send": 1,
            }],
            core_opportunity_rows=[
                {
                    "row_type": "event_core_opportunity",
                    "schema_version": "event_core_opportunity_store_v1",
                    "run_id": run_id,
                    "profile": "notify_llm_deep",
                    "run_mode": "test",
                    "artifact_namespace": namespace,
                    "core_opportunity_id": f"core-{idx}",
                    "symbol": f"COIN{idx}",
                    "coin_id": f"coin-{idx}",
                    "opportunity_level": "validated_digest",
                    "final_route_after_quality_gate": "RESEARCH_DIGEST",
                }
                for idx in range(5)
            ],
            delivery_rows=[{
                "row_type": "event_alpha_notification_delivery",
                "run_id": run_id,
                "profile": "notify_llm_deep",
                "artifact_namespace": namespace,
                "lane": notif.LANE_RESEARCH_REVIEW_DIGEST,
                "state": "blocked",
                "would_send": True,
            }],
            daily_brief_path=brief_path,
            source_coverage_report_path=source_coverage,
            profile="notify_llm_deep",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
        )

    assert doctor.daily_brief_missing_selected_run == 1
    assert doctor.daily_brief_selected_run_mismatch == 1
    assert doctor.daily_brief_core_count_mismatch_store == 1
    assert doctor.daily_brief_research_review_lane_missing == 1
    assert doctor.daily_brief_source_coverage_path_missing == 1
    assert doctor.status == "BLOCKED"
    assert any("daily_brief_missing_selected_run=1" in item for item in doctor.blockers)


def test_event_alpha_research_review_digest_inbox_and_doctor_checks():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_artifact_doctor as doctor,
        event_alpha_notification_delivery as delivery,
        event_alpha_notification_inbox as inbox,
        event_alpha_notifications as notif,
        event_alpha_router,
    )

    namespace = "research_review_digest_unit_doctor"
    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, namespace)
        dcfg = delivery.config_for_context(ctx)
        decision = _research_review_decision("DOGE", score=66)
        core_row = {
            "core_opportunity_id": "agg:doge-research-review",
            "key": decision.entry.key,
            "symbol": "DOGE",
            "coin_id": "dogecoin",
            "validated_symbol": "DOGE",
            "validated_coin_id": "dogecoin",
            "final_opportunity_level": "exploratory",
            "opportunity_score_final": 66,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "impact_path_type": "meme_attention",
            "candidate_role": "candidate_asset",
            "card_path": str(Path(tmp) / "cards" / "core_doge_research_review.md"),
            "feedback_target": "agg:doge-research-review",
            "profile": "fixture",
            "artifact_namespace": namespace,
            "run_mode": "test",
        }
        preview_plan = notif.build_notification_plan(
            [decision],
            storage=_NotifyFakeStorage(),
            cfg=notif.EventAlphaNotificationConfig(
                enabled=False,
                research_review_digest_enabled=True,
                research_review_digest_min_score=60,
            ),
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
            core_opportunity_rows=[core_row],
        )
        preview_body = notif.format_research_review_telegram_digest(
            preview_plan.research_review_items,
            profile="fixture",
            cfg=notif.EventAlphaNotificationConfig(
                enabled=False,
                research_review_digest_enabled=True,
                research_review_digest_min_score=60,
            ),
            core_row_by_alert_id=preview_plan.core_row_by_alert_id,
        )
        assert "DOGE / dogecoin" in preview_body
        assert "Card: core_doge_research_review.md" in preview_body
        assert "Feedback target: agg:doge-research-review" in preview_body
        sent_result = notif.send_notifications(
            [decision],
            storage=_NotifyFakeStorage(),
            cfg=notif.EventAlphaNotificationConfig(
                enabled=False,
                research_review_digest_enabled=True,
                research_review_digest_min_score=60,
            ),
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
            profile="fixture",
            send_fn=lambda message: True,
            delivery_cfg=dcfg,
            run_id="run-review",
            namespace=namespace,
            core_opportunity_rows=[core_row],
        )
        rows = delivery.load_delivery_records(dcfg.path)
        assert sent_result.deliveries_blocked == 1
        result = inbox.build_notification_inbox(
            notification_runs=[],
            alert_rows=[],
            feedback_rows=[],
            research_cards_dir=Path(tmp),
            profile="fixture",
            artifact_namespace=namespace,
            notification_runs_path=Path(tmp) / "runs.jsonl",
            alert_store_path=Path(tmp) / "alerts.jsonl",
            feedback_path=Path(tmp) / "feedback.jsonl",
            notification_delivery_rows=rows,
            core_opportunity_rows=[core_row],
        )
        assert len(result.research_review_without_feedback) == 1
        assert result.research_review_without_feedback[0].feedback_target == "agg:doge-research-review"
        report = inbox.format_notification_inbox(result)
        assert "research-review candidates needing feedback" in report

        clean = doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-review", "profile": "fixture", "artifact_namespace": namespace, "run_mode": "test"}],
            delivery_rows=rows,
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert clean.research_review_digest_contains_hard_gated_candidate == 0
        assert clean.research_review_digest_contains_strict_alertable == 0
        assert clean.research_review_digest_enabled_but_lane_missing == 0
        assert clean.research_review_digest_candidates_without_delivery == 0

        missing_lane = doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-missing-review-lane",
                "profile": "fixture",
                "artifact_namespace": namespace,
                "run_mode": "test",
                "research_review_digest_enabled": True,
                "research_review_digest_candidates": 1,
                "research_review_digest_would_send": 1,
            }],
            delivery_rows=[],
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert missing_lane.research_review_digest_enabled_but_lane_missing == 1
        assert missing_lane.research_review_digest_candidates_without_delivery == 1
        assert missing_lane.status == "BLOCKED"

        bad_preview = Path(tmp) / "bad_preview.md"
        bad_preview.write_text(
            "# Event Alpha Notification Preview\n\n```html\n1. <b>BAD</b>\nCard: /Users/example/card.md\n```\n",
            encoding="utf-8",
        )
        bad_row = {
            **rows[-1],
            "run_id": "bad-run",
            "notification_preview_path": str(bad_preview),
            "notification_preview_relpath": delivery.notification_preview_relpath_for_path(bad_preview),
            "feedback_target": "",
            "feedback_targets": [],
            "core_opportunity_id": "agg:bad-alertable",
            "core_opportunity_ids": ["agg:bad-alertable"],
            "canonical_symbols": ["BAD"],
            "canonical_coin_ids": ["bad"],
        }
        bad_core = {
            "core_opportunity_id": "agg:bad-alertable",
            "symbol": "BAD",
            "coin_id": "bad",
            "final_opportunity_level": "validated_digest",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "impact_path_type": "generic_cooccurrence_only",
            "profile": "fixture",
            "artifact_namespace": namespace,
            "run_mode": "test",
        }
        bad = doctor.diagnose_artifacts(
            run_rows=[{"run_id": "bad-run", "profile": "fixture", "artifact_namespace": namespace, "run_mode": "test"}],
            delivery_rows=[bad_row],
            core_opportunity_rows=[bad_core],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert bad.research_review_digest_missing_confirmation_label == 1
        assert bad.research_review_digest_contains_strict_alertable == 1
        assert bad.research_review_digest_contains_hard_gated_candidate == 1
        assert bad.research_review_digest_missing_feedback_target == 1
        assert bad.research_review_digest_absolute_path == 1
        assert bad.status == "BLOCKED"

        missing_family = {
            **rows[-1],
            "run_id": "run-missing-family-summary",
            "channel_summary": {
                "rendered_candidate_count": 1,
                "eligible_candidate_count": 20,
                "skipped_candidate_count": 19,
                "skip_reason_counts": {"max_items": 19},
                "skipped_candidates": [{"symbol": "CHZ", "coin_id": "chiliz", "skip_reason": "max_items"}],
            },
            "skipped_candidate_count": 19,
            "skipped_reason_counts": {"max_items": 19},
            "skipped_candidates_sample": [{"symbol": "CHZ", "coin_id": "chiliz", "skip_reason": "max_items"}],
            "skipped_family_summary": [],
        }
        missing_family_result = doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-missing-family-summary",
                "profile": "fixture",
                "artifact_namespace": namespace,
                "run_mode": "test",
            }],
            delivery_rows=[missing_family],
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert missing_family_result.research_review_digest_missing_family_summary == 1
        assert missing_family_result.status == "BLOCKED"

        missing_reason_counts = {
            **rows[-1],
            "run_id": "run-missing-reason-counts",
            "channel_summary": {
                "rendered_candidate_count": 1,
                "eligible_candidate_count": 2,
                "skipped_candidate_count": 1,
                "skipped_candidates_sample": [{"symbol": "VELVET", "coin_id": "velvet", "skip_reason": "max_items"}],
                "skipped_family_summary": [{"candidate_family_id": "spacex:velvet", "skipped_count": 1}],
            },
            "skipped_candidate_count": 1,
            "skipped_reason_counts": {},
            "skipped_candidates_sample": [{"symbol": "VELVET", "coin_id": "velvet", "skip_reason": "max_items"}],
            "skipped_family_summary": [{"candidate_family_id": "spacex:velvet", "skipped_count": 1}],
        }
        missing_reason_result = doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-missing-reason-counts",
                "profile": "fixture",
                "artifact_namespace": namespace,
                "run_mode": "test",
            }],
            delivery_rows=[missing_reason_counts],
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert missing_reason_result.research_review_digest_skipped_without_reason == 1
        assert missing_reason_result.status == "BLOCKED"


def test_event_alpha_artifact_doctor_blocks_research_review_body_not_using_canonical_core():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_artifact_doctor as doctor,
        event_alpha_notification_delivery as delivery,
    )

    namespace = "research_review_canonical_body_unit"
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        preview = base / namespace / "event_alpha_notification_preview.md"
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane: research_review_digest\n\n"
            "```html\n"
            "<b>Event Alpha Research Review</b>\n"
            "<i>Not alertable. Missing confirmation. Not a trade signal.</i>\n"
            "1. <b>VELVET / velvet</b>\n"
            "   Card: hyp_velvet_card.md\n"
            "   Feedback target: hyp:velvet-stale-support\n"
            "```\n",
            encoding="utf-8",
        )
        core_row = {
            "core_opportunity_id": "agg:velvet-spacex-core",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "final_opportunity_level": "exploratory",
            "final_route_after_quality_gate": "STORE_ONLY",
            "profile": "fixture",
            "artifact_namespace": namespace,
            "run_mode": "test",
        }
        delivery_row = {
            "row_type": "event_alpha_notification_delivery",
            "run_id": "run-review-body",
            "profile": "fixture",
            "artifact_namespace": namespace,
            "namespace": namespace,
            "run_mode": "test",
            "lane": "research_review_digest",
            "state": delivery.STATE_BLOCKED,
            "delivery_state": delivery.STATE_BLOCKED,
            "status_detail": "would_send_but_guard_disabled",
            "delivery_mode": "no_send_rehearsal",
            "content_hash": "review-body-canonical",
            "attempted_at": datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc).isoformat(),
            "notification_preview_path": str(preview),
            "notification_preview_relpath": delivery.notification_preview_relpath_for_path(preview),
            "core_opportunity_id": "agg:velvet-spacex-core",
            "core_opportunity_ids": ["agg:velvet-spacex-core"],
            "canonical_card_path": "event_fade_cache/cards/core_velvet_spacex.md",
            "canonical_card_paths": ["event_fade_cache/cards/core_velvet_spacex.md"],
            "feedback_target": "agg:velvet-spacex-core",
            "feedback_targets": ["agg:velvet-spacex-core"],
        }
        result = doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-review-body",
                "profile": "fixture",
                "artifact_namespace": namespace,
                "run_mode": "test",
            }],
            delivery_rows=[delivery_row],
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert result.notification_body_card_mismatch_canonical == 1
        assert result.notification_body_feedback_mismatch_canonical == 1
        assert result.research_review_body_uses_hypothesis_target_when_core_exists == 1
        assert result.status == "BLOCKED"

        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "```html\n"
            "<b>Event Alpha Research Review</b>\n"
            "<i>Not alertable. Missing confirmation. Not a trade signal.</i>\n"
            "1. <b>VELVET / velvet</b>\n"
            "   Card: core_velvet_spacex.md\n"
            "   Feedback target: agg:velvet-spacex-core\n"
            "```\n",
            encoding="utf-8",
        )
        clean = doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-review-body",
                "profile": "fixture",
                "artifact_namespace": namespace,
                "run_mode": "test",
            }],
            delivery_rows=[delivery_row],
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert clean.notification_body_card_mismatch_canonical == 0
        assert clean.notification_body_feedback_mismatch_canonical == 0
        assert clean.research_review_body_uses_hypothesis_target_when_core_exists == 0


def test_event_alpha_quality_fields_enforced_and_doctor_reports_legacy_missing():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from types import SimpleNamespace
    from crypto_rsi_scanner import (
        event_alpha_alert_store,
        event_alpha_artifact_doctor,
        event_alpha_router,
        event_impact_hypothesis_store,
        event_watchlist,
    )

    hypothesis = SimpleNamespace(
        hypothesis_id="h-velvet-quality",
        event_cluster_id="spacex|ipo|2026-06-20",
        status="validated",
        validation_stage="impact_path_validated",
        hypothesis_score=86,
        confidence=0.86,
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        validated_symbol="VELVET",
        validated_coin_id="velvet",
        candidate_sectors=("tokenized_stock_venues",),
        source_raw_ids=("r1",),
        impact_category="rwa_preipo_proxy",
        hypothesis_scope="token",
        playbook_hint="proxy_attention",
        external_asset="SpaceX",
        impact_path_type="venue_value_capture",
        impact_path_strength="strong",
        candidate_role="proxy_venue",
        evidence_quality_score=82,
        source_class="primary",
        evidence_specificity="direct_value_capture",
        market_confirmation_score=75,
        market_confirmation_level="strong",
        opportunity_score_final=88,
        opportunity_level="high_priority",
        opportunity_verdict_reasons=("strong_market_confirmation",),
        why_local_only=None,
        why_not_watchlist=None,
        manual_verification_items=("verify liquidity",),
        score_components={"event_clarity": 80},
    )
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        watch = event_watchlist.refresh_hypothesis_watchlist(
            [hypothesis],
            cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=base / "watch.jsonl"),
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
        )
        entry = watch.entries[0]
        assert entry.opportunity_level == "high_priority"
        assert entry.market_confirmation_level == "strong"
        store = event_impact_hypothesis_store.write_impact_hypotheses(
            [hypothesis],
            cfg=event_impact_hypothesis_store.EventImpactHypothesisStoreConfig(path=base / "hypotheses.jsonl"),
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
            watchlist_rows=watch.entries,
        )
        rows = event_impact_hypothesis_store.load_impact_hypotheses(store.path).rows
        assert rows[0]["opportunity_level"] == "high_priority"
        assert rows[0]["upgrade_requirements"]
        assert rows[0]["downgrade_warnings"]
        decision = event_alpha_router.EventAlphaRouteDecision(
            entry=entry,
            route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
            alertable=True,
            reason="quality escalation",
            lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
        )
        snap = event_alpha_alert_store.write_alert_snapshots(
            [],
            router_result=SimpleNamespace(decisions=[decision]),
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=base / "alerts.jsonl"),
            now=datetime(2026, 6, 20, 12, 1, tzinfo=timezone.utc),
        )
        alert_rows = event_alpha_alert_store.load_alert_snapshots(snap.path).rows
        assert alert_rows[0]["opportunity_level"] == "high_priority"
        assert alert_rows[0]["manual_verification_items"] == ["verify liquidity"]
        assert alert_rows[0]["upgrade_requirements"]
        assert alert_rows[0]["downgrade_warnings"]
        legacy = {"row_type": "event_watchlist_state", "key": "legacy", "event_id": "legacy", "coin_id": "old", "symbol": "OLD", "relationship_type": "impact_hypothesis"}
        fresh_missing = {
            "row_type": "event_watchlist_state",
            "key": "fresh-missing",
            "event_id": "fresh",
            "coin_id": "fresh",
            "symbol": "FRESH",
            "relationship_type": "impact_hypothesis",
            "run_mode": "test",
            "artifact_namespace": "quality_validation",
        }
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "r1", "alertable": 0}],
            hypothesis_rows=rows,
            watchlist_rows=[entry, legacy],
            alert_rows=alert_rows,
            include_legacy_artifacts=True,
            strict=False,
        )
        assert doctor.quality_fields_missing_count >= 1
        assert doctor.legacy_quality_missing_rows >= 1
        assert doctor.fresh_watchlist_rows_missing_top_level_quality == 0
        assert doctor.status in {"OK", "WARN"}
        strict = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "r1", "alertable": 0}],
            watchlist_rows=[legacy],
            include_legacy_artifacts=True,
            strict=True,
        )
        assert strict.status in {"OK", "WARN"}
        strict_fresh = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "r1", "alertable": 0}],
            watchlist_rows=[fresh_missing],
            include_test_artifacts=True,
            strict=True,
        )
        assert strict_fresh.status == "BLOCKED"
        assert strict_fresh.fresh_watchlist_rows_missing_top_level_quality == 1


def test_event_alpha_notification_run_summary_flows_to_runs_doctor_and_brief():
    from types import SimpleNamespace
    from crypto_rsi_scanner import (
        event_alpha_artifact_doctor,
        event_alpha_daily_brief,
        event_alpha_notification_runs as runs,
    )

    started = "2026-06-20T12:00:00+00:00"
    delivered_result = SimpleNamespace(
        run_id="r1", run_mode="notification_burn_in", artifact_namespace="notify_no_key",
        warnings=(), notification_lock_acquired=True, notification_stale_lock_recovered=False,
        notification_skipped_due_to_active_lock=False, notification_delivery_records_written=2,
        notification_deliveries_delivered=1, notification_deliveries_failed=1,
        notification_deliveries_skipped_duplicate=0, notification_deliveries_blocked=0,
    )
    row = runs.notification_run_record(
        delivered_result, profile="notify_no_key",
        started_at=__import__("datetime").datetime.fromisoformat(started),
        finished_at=__import__("datetime").datetime.fromisoformat(started),
        telegram_ready=True, send_guard_enabled=True,
    )
    assert runs.row_has_delivery_failures(row)
    report = runs.format_notification_runs_report(
        runs.EventAlphaNotificationRunsReadResult(path="runs.jsonl", rows_read=1, rows=[row])
    )
    assert "lock_acquired=yes" in report
    assert "deliveries=1d/1f/0dup" in report

    skipped_result = SimpleNamespace(
        run_id="r2", run_mode="notification_burn_in", artifact_namespace="notify_no_key",
        warnings=("notification_cycle_skipped_active_lock",),
        notification_skipped_due_to_active_lock=True, notification_lock_acquired=False,
    )
    skipped_row = runs.notification_run_record(
        skipped_result, profile="notify_no_key",
        started_at=__import__("datetime").datetime.fromisoformat(started),
        finished_at=__import__("datetime").datetime.fromisoformat(started),
        telegram_ready=True, send_guard_enabled=True,
    )
    skipped_report = runs.format_notification_runs_report(
        runs.EventAlphaNotificationRunsReadResult(path="runs.jsonl", rows_read=1, rows=[skipped_row])
    )
    assert "skipped_active_lock=yes" in skipped_report

    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r", "profile": "notify_no_key", "run_mode": "notification_burn_in", "artifact_namespace": "notify_no_key", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
        alert_rows=[{"run_id": "r", "profile": "notify_no_key", "run_mode": "notification_burn_in", "artifact_namespace": "notify_no_key", "alert_key": "a", "tier": "WATCHLIST"}],
        delivery_rows=[{"row_type": "event_alpha_notification_delivery", "delivery_id": "d1", "state": "failed", "lane": "daily_digest"}],
        profile="notify_no_key", artifact_namespace="notify_no_key",
    )
    assert doctor.deliveries_failed == 1
    assert any("notification deliveries failed" in w for w in doctor.warnings)

    brief = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{"row_type": "event_alpha_run", "started_at": started, "profile": "notify_no_key", "run_mode": "notification_burn_in", "artifact_namespace": "notify_no_key", "success": True}],
        notification_runs=[row], requested_profile="notify_no_key", artifact_namespace="notify_no_key",
    )
    assert "Notify delivery failures" in brief


def test_event_alpha_environment_doctor_blocks_missing_and_unwritable_inputs():
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace
    from crypto_rsi_scanner import event_alpha_environment_doctor as doctor

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        ctx = SimpleNamespace(namespace_dir=base / "notify", base_dir=base, artifact_namespace="notify_no_key")
        profile = SimpleNamespace(name="notify_no_key", send=True, notification_burn_in=True)
        provider_status = SimpleNamespace(ready_event_source_count=3, ready_enrichment_count=1)
        blocked = doctor.build_environment_doctor(
            profile=profile,
            context=ctx,
            provider_status=provider_status,
            provider_health_rows={},
            lock_path=base / "notify" / "lock.json",
            delivery_ledger_path=base / "notify" / "deliveries.jsonl",
            notification_runs_path=base / "notify" / "runs.jsonl",
            research_cards_dir=base / "notify" / "cards",
            telegram_token_present=False,
            telegram_chat_ids_present=False,
            send_guard_enabled=False,
            llm_provider="fixture",
            llm_enabled=False,
            llm_extractor_provider="fixture",
            llm_extractor_enabled=False,
            openai_key_present=False,
            clock_status={"now": "wall-clock"},
            python_executable="python3",
            working_directory=str(base),
        )
        assert not blocked.ready_for_scheduled_notify
        assert any("TELEGRAM_BOT_TOKEN" in item for item in blocked.blockers)
        assert "secret" not in doctor.format_environment_doctor(blocked).lower()

        ready = doctor.build_environment_doctor(
            profile=profile,
            context=ctx,
            provider_status=provider_status,
            provider_health_rows={},
            lock_path=base / "notify" / "lock.json",
            delivery_ledger_path=base / "notify" / "deliveries.jsonl",
            notification_runs_path=base / "notify" / "runs.jsonl",
            research_cards_dir=base / "notify" / "cards",
            telegram_token_present=True,
            telegram_chat_ids_present=True,
            send_guard_enabled=True,
            llm_provider="fixture",
            llm_enabled=False,
            llm_extractor_provider="fixture",
            llm_extractor_enabled=False,
            openai_key_present=False,
            clock_status={"now": "wall-clock"},
            python_executable="python3",
            working_directory=str(base),
        )
        assert ready.ready_for_scheduled_notify

        file_base = base / "not_a_dir"
        file_base.write_text("x", encoding="utf-8")
        bad_ctx = SimpleNamespace(namespace_dir=file_base / "child", base_dir=file_base, artifact_namespace="notify_no_key")
        bad = doctor.build_environment_doctor(
            profile=profile,
            context=bad_ctx,
            provider_status=provider_status,
            provider_health_rows={},
            lock_path=file_base / "lock.json",
            delivery_ledger_path=file_base / "deliveries.jsonl",
            notification_runs_path=file_base / "runs.jsonl",
            research_cards_dir=file_base / "cards",
            telegram_token_present=True,
            telegram_chat_ids_present=True,
            send_guard_enabled=True,
            llm_provider="fixture",
            llm_enabled=False,
            llm_extractor_provider="fixture",
            llm_extractor_enabled=False,
            openai_key_present=False,
            clock_status={"now": "wall-clock"},
            python_executable="python3",
            working_directory=str(base),
        )
        assert not bad.ready_for_scheduled_notify
        assert any("not writable" in item for item in bad.blockers)


def test_event_alpha_live_path_caps_non_hypothesis_watchlist_and_doctor_sees_path_scoped_rows():
    from dataclasses import asdict
    from datetime import datetime, timezone
    from pathlib import Path
    import tempfile

    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_watchlist

    now = datetime(2026, 6, 26, 15, 30, tzinfo=timezone.utc)
    quality = {
        "impact_path_type": "insufficient_data",
        "impact_path_strength": "none",
        "candidate_role": "unknown_with_reason",
        "evidence_quality_score": 0.0,
        "source_class": "insufficient_data",
        "evidence_specificity": "insufficient_data",
        "market_confirmation_score": 0.0,
        "market_confirmation_level": "insufficient_data",
        "opportunity_score_final": 0.0,
        "opportunity_level": "local_only",
        "opportunity_verdict_reasons": ["quality_context_missing"],
        "why_local_only": "quality_context_missing",
        "why_not_watchlist": "quality_context_missing",
        "manual_verification_items": ["verify catalyst and asset identity"],
        "upgrade_requirements": ["needs_quality_context"],
        "downgrade_warnings": ["insufficient_data"],
    }
    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="world-cup|sports-event|2026-06-26|chiliz|fan_sports_event",
        cluster_id="world-cup|sports-event|2026-06-26",
        event_id="evt:world-cup",
        coin_id="chiliz",
        symbol="CHZ",
        relationship_type="proxy_attention",
        external_asset="World Cup",
        event_time=now.isoformat(),
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        previous_state=event_watchlist.EventWatchlistState.RADAR.value,
        requested_state_before_quality_gate=event_watchlist.EventWatchlistState.WATCHLIST.value,
        final_state_after_quality_gate=event_watchlist.EventWatchlistState.WATCHLIST.value,
        state_quality_capped=False,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=1,
        highest_score=82,
        latest_score=82,
        latest_tier="WATCHLIST",
        latest_event_name="World Cup fan token attention",
        latest_source="project_blog_rss",
        latest_playbook_type="fan_sports_event",
        latest_effective_playbook_type="fan_sports_event",
        latest_score_components={
            "cluster_confidence": 72,
            "market_move_volume": 12,
        },
        should_alert=True,
        material_change_reasons=("score_jump",),
        **quality,
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_watchlist_state.jsonl"
        event_watchlist._append_entries(path, [entry])
        persisted = event_watchlist.load_watchlist(path).entries[0]
        assert persisted.state == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        assert persisted.final_state_after_quality_gate == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        assert persisted.state_quality_capped is True
        assert persisted.quality_state_block_reason == "impact_path_type_insufficient_data"
        raw_missing_metadata = asdict(entry)
        raw_missing_metadata.pop("profile", None)
        raw_missing_metadata.pop("artifact_namespace", None)
        raw_missing_metadata.pop("run_mode", None)
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            watchlist_rows=[raw_missing_metadata],
            profile="notify_llm_quality",
            artifact_namespace="notify_llm_quality",
            strict=True,
        )
        assert doctor.status == "BLOCKED"
        assert doctor.universal_watchlist_state_conflicts == 1
        assert doctor.non_hypothesis_watchlist_quality_conflicts == 1
        assert doctor.fresh_watchlist_state_conflict_rows == 1
        capped_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            watchlist_rows=[asdict(persisted)],
            profile="notify_llm_quality",
            artifact_namespace="notify_llm_quality",
            strict=True,
        )
        assert capped_doctor.fresh_watchlist_state_conflict_rows == 0
        assert capped_doctor.quality_capped_watchlist_rows == 1
        assert capped_doctor.universal_watchlist_state_conflicts == 0


def test_event_alpha_artifact_doctor_reports_core_store_coverage():
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_core_opportunity_store

    rows = _canonical_core_fixture_rows()
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-doctor",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-core-doctor",
            "profile": "market_refresh_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "market_refresh_smoke",
            "success": True,
            "alertable": 0,
        }],
        core_opportunity_rows=loaded.rows,
        profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
    )
    assert doctor.core_opportunity_store_rows == 4
    assert doctor.visible_core_opportunities_missing_store_rows == 0
    assert doctor.core_opportunity_store_rows_missing_card_path == 4
    assert "core_opportunity_store_rows=4" in event_alpha_artifact_doctor.format_artifact_doctor_report(doctor)

    with TemporaryDirectory() as tmp:
        card_paths = []
        for row in loaded.rows:
            card = Path(tmp) / f"{row['core_opportunity_id']}.md"
            card.write_text(
                "\n".join([
                    f"# {row.get('symbol') or 'Core'} Event Research Card",
                    "- Generated at: 2026-06-28T00:00:00+00:00",
                    "- Lineage status: current",
                    "- legacy_lineage_missing: false",
                    "- Run ID: run-core-doctor",
                    "- Profile: market_refresh_smoke",
                    "- Namespace: market_refresh_smoke",
                    f"- Core opportunity ID: {row['core_opportunity_id']}",
                    f"- Feedback target: {row['core_opportunity_id']}",
                    "- Feedback target type: core_opportunity_id",
                ]),
                encoding="utf-8",
            )
            card_paths.append(card)
        card_mapped = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-core-doctor",
                "profile": "market_refresh_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "market_refresh_smoke",
                "success": True,
                "alertable": 0,
            }],
            core_opportunity_rows=loaded.rows,
            card_paths=card_paths,
            profile="market_refresh_smoke",
            artifact_namespace="market_refresh_smoke",
        )
        assert card_mapped.core_opportunity_store_rows_missing_card_path == 0

    missing = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-core-doctor",
            "profile": "market_refresh_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "market_refresh_smoke",
            "success": True,
            "alertable": 0,
        }],
        hypothesis_rows=[rows[0]],
        profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
    )
    assert missing.visible_core_opportunities_missing_store_rows == 1


def test_event_alpha_artifact_doctor_blocks_core_route_verdict_conflict():
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_alpha_router, event_watchlist

    conflict = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-core-route-conflict",
        "profile": "live_burn_in_no_send",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_route_conflict",
        "symbol": "TEST",
        "coin_id": "test-token",
        "candidate_role": "direct_subject",
        "primary_impact_path": "strategic_investment",
        "impact_path_type": "strategic_investment",
        "evidence_specificity": "direct_token_mechanism",
        "source_class": "crypto_news",
        "final_opportunity_level": "validated_digest",
        "opportunity_level": "validated_digest",
        "final_opportunity_score": 72,
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "state_quality_capped": False,
    }
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-core-route-conflict",
            "profile": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "live_burn_in_no_send",
            "success": True,
        }],
        core_opportunity_rows=[conflict],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )

    assert doctor.core_route_conflicts_with_opportunity_level == 1
    assert doctor.status == "BLOCKED"
    assert any("core_route_conflicts_with_opportunity_level=1" in item for item in doctor.blockers)


def test_event_alpha_artifact_doctor_blocks_live_promoted_without_confirmation():
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_alpha_router, event_watchlist

    conflict = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-live-unconfirmed",
        "profile": "live_burn_in_no_send",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_live_unconfirmed",
        "symbol": "TAO",
        "coin_id": "bittensor",
        "candidate_role": "direct_beneficiary",
        "primary_impact_path": "strategic_investment",
        "impact_path_type": "strategic_investment",
        "evidence_specificity": "direct_token_mechanism",
        "source_class": "crypto_news",
        "final_opportunity_level": "validated_digest",
        "opportunity_level": "validated_digest",
        "final_opportunity_score": 72,
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "route": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "evidence_acquisition_status": "rejected_results_only",
        "evidence_acquisition_rejected_count": 2,
        "live_confirmation_required": True,
        "live_confirmation_passed": False,
    }
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-live-unconfirmed",
            "profile": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "live_burn_in_no_send",
            "success": True,
        }],
        core_opportunity_rows=[conflict],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )
    assert doctor.live_validated_without_confirmation == 1
    assert doctor.live_rejected_results_promoted == 1
    assert doctor.status == "BLOCKED"
    assert any("live_validated_without_confirmation=1" in item for item in doctor.blockers)


def test_event_alpha_artifact_doctor_accepts_quality_blocked_local_card_group():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        card = root / "card_core_quality_blocked.md"
        card.write_text(
            "\n".join([
                "# ADA quality blocked",
                "",
                "## Lineage",
                "- Core opportunity ID: core_quality_blocked",
                "- Feedback target: core_quality_blocked",
            ]),
            encoding="utf-8",
        )
        (root / "index.md").write_text(
            "\n".join([
                "# Event Research Cards",
                "",
                "## Local-Only / Quality-Capped Cards",
                "",
                "- [card_core_quality_blocked.md](card_core_quality_blocked.md) · group: Local-Only / Quality-Capped Cards · feedback target: `core_quality_blocked`",
            ]),
            encoding="utf-8",
        )
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-quality-blocked-card",
                "profile": "fixture",
                "run_mode": "burn_in",
                "artifact_namespace": "fixture",
                "success": True,
            }],
            core_opportunity_rows=[{
                "row_type": "event_core_opportunity",
                "run_id": "run-quality-blocked-card",
                "profile": "fixture",
                "run_mode": "burn_in",
                "artifact_namespace": "fixture",
                "core_opportunity_id": "core_quality_blocked",
                "symbol": "ADA",
                "coin_id": "cardano",
                "candidate_role": "direct_subject",
                "impact_path_type": "strategic_investment_or_valuation",
                "opportunity_level": "exploratory",
                "opportunity_score_final": 64,
                "final_route_after_quality_gate": "STORE_ONLY",
                "final_state_after_quality_gate": "QUALITY_BLOCKED",
                "state_quality_capped": True,
                "card_path": str(card),
                "research_card_path": str(card),
                "feedback_target": "core_quality_blocked",
            }],
            card_paths=[card, root / "index.md"],
            profile="fixture",
            artifact_namespace="fixture",
            strict=True,
        )
    assert doctor.daily_brief_card_group_mismatch_with_index == 0
    assert "daily_brief_card_group_mismatch_with_index" not in "\n".join(doctor.blockers)


def test_artifact_doctor_blocks_stale_acquisition_validated_digest():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    result = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "row_type": "event_alpha_run",
            "run_id": "run-acq-stale",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "success": True,
        }],
        evidence_acquisition_rows=[{
            "row_type": "event_evidence_acquisition",
            "run_id": "run-acq-stale",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "status": "skipped_budget",
            "accepted_evidence_count": 0,
            "final_opportunity_level": "validated_digest",
        }],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )

    assert result.evidence_acquisition_stale_validated_digest == 1
    assert any("evidence_acquisition_stale_validated_digest=1" in item for item in result.blockers)


def test_artifact_doctor_detects_canonical_core_rendering_mismatch_and_acquisition_orphan():
    import json
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_core_opportunity_store

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-doctor-primary",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        velvet = next(row for row in core_rows if row["symbol"] == "VELVET")
        stale_card = root / "card_stale_velvet.md"
        stale_card.write_text(
            "\n".join([
                "# VELVET Event Research Card",
                "- Run ID: run-core-doctor-primary",
                "- Profile: market_refresh_smoke",
                "- Namespace: market_refresh_smoke",
                f"- Core opportunity ID: {velvet['core_opportunity_id']}",
                f"- Feedback target: {velvet['core_opportunity_id']}",
                "- State / alert tier: HIGH_PRIORITY / STORE_ONLY",
                "- Final route: STORE_ONLY",
                "- Opportunity verdict: local_only / 0.0",
                "- Source pack: market_anomaly_pack",
                "- Evidence acquisition result: status=accepted_evidence_found evidence=accepted accepted=0 rejected=0 final=unchanged",
                "- Latest source: unknown",
                "- Market data: not available.",
                "- What would upgrade this candidate: blocked by generic cooccurrence; needs proof that this event directly affects the token",
            ]),
            encoding="utf-8",
        )
        acquisition_velvet = {
            "row_type": "event_evidence_acquisition",
            "run_id": "run-core-doctor-primary",
            "profile": "market_refresh_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "market_refresh_smoke",
            "core_opportunity_id": velvet["core_opportunity_id"],
            "symbol": "VELVET",
            "coin_id": "velvet",
            "source_pack": "proxy_preipo_rwa_pack",
            "status": "accepted_evidence_found",
            "accepted_evidence": [{
                "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
                "reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
            }],
        }
        acquisition_orphan = {
            "row_type": "event_evidence_acquisition",
            "run_id": "run-core-doctor-primary",
            "profile": "market_refresh_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "market_refresh_smoke",
            "core_opportunity_id": "core_orphan",
            "symbol": "MEME",
            "coin_id": "memecore",
        }
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-core-doctor-primary",
                "profile": "market_refresh_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "market_refresh_smoke",
                "success": True,
                "alertable": 0,
            }],
            core_opportunity_rows=core_rows,
            evidence_acquisition_rows=[acquisition_velvet, acquisition_orphan],
            card_paths=[stale_card],
            profile="market_refresh_smoke",
            artifact_namespace="market_refresh_smoke",
            strict=True,
        )
    assert doctor.card_primary_fields_mismatch_core_store == 1
    assert doctor.card_evidence_acquisition_count_mismatch == 1
    assert doctor.card_source_pack_mismatch_core_acquisition == 1
    assert doctor.card_primary_section_contains_support_row_blockers == 1
    assert doctor.card_upgrade_text_inconsistent_with_final_level == 1
    assert doctor.card_market_confirmation_missing_but_core_has_market_confirmation == 1
    assert doctor.card_latest_source_unknown_but_accepted_evidence_exists == 1
    assert doctor.evidence_acquisition_core_id_missing_from_store == 1
    assert any("card_primary_fields_mismatch_core_store=1" in item for item in doctor.blockers)
    assert any("card_evidence_acquisition_count_mismatch=1" in item for item in doctor.blockers)
    assert any("card_source_pack_mismatch_core_acquisition=1" in item for item in doctor.blockers)
    assert any("evidence_acquisition_core_id_missing_from_store=1" in item for item in doctor.blockers)


def test_artifact_doctor_detects_orphan_core_cards_and_snapshot_ids():
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_core_opportunity_store

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-doctor-orphan",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        card_dir = root / "cards"
        card_dir.mkdir()
        orphan = card_dir / "card_core_missing.md"
        orphan.write_text(
            "# Orphan\n\n- Core opportunity ID: core_missing_visible\n- Feedback target: core_missing_visible\nFinal route: HIGH_PRIORITY_RESEARCH\n",
            encoding="utf-8",
        )
        index = card_dir / "index.md"
        index.write_text("# Cards\n\n## Core Opportunity Cards\n\n- [card_core_missing.md](card_core_missing.md)\n", encoding="utf-8")
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-core-doctor-orphan",
                "profile": "market_refresh_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "market_refresh_smoke",
                "success": True,
                "alertable": 0,
            }],
            core_opportunity_rows=core_rows,
            alert_rows=[{
                "row_type": "event_alpha_alert_snapshot",
                "run_id": "run-core-doctor-orphan",
                "profile": "market_refresh_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "market_refresh_smoke",
                "core_opportunity_id": "core_missing_visible",
                "final_route_after_quality_gate": "RESEARCH_DIGEST",
                "opportunity_level": "validated_digest",
            }],
            card_paths=[orphan, index],
            profile="market_refresh_smoke",
            artifact_namespace="market_refresh_smoke",
            strict=True,
        )
    assert doctor.core_cards_missing_store_row == 1
    assert doctor.alert_snapshots_core_id_missing_from_store == 1
    assert any("core_cards_missing_store_row=1" in item for item in doctor.blockers)
    assert any("alert_snapshots_core_id_missing_from_store=1" in item for item in doctor.blockers)


def test_artifact_doctor_checks_core_first_review_surfaces():
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_alpha_router, event_watchlist

    quality = {
        "impact_path_strength": "strong",
        "evidence_quality_score": 90,
        "source_class": "cryptopanic_tagged",
        "evidence_specificity": "direct_token_mechanism",
        "market_confirmation_score": 88,
        "market_confirmation_level": "strong",
        "market_context_freshness_status": "fresh",
        "market_context_age_hours": 0.1,
        "market_context_stale": False,
        "market_context_freshness_cap_applied": False,
        "opportunity_verdict_reasons": ["impact_path_validated"],
        "why_local_only": [],
        "why_not_watchlist": [],
        "manual_verification_items": [],
        "upgrade_requirements": [],
        "downgrade_warnings": [],
    }
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        card = root / "card_agg_3381ebd96566.md"
        card.write_text(
            "\n".join([
                "# VELVET core",
                "",
                "## Lineage",
                "- Core opportunity ID: agg:3381ebd96566",
                "- Feedback target: agg:3381ebd96566",
            ]),
            encoding="utf-8",
        )
        core = {
            "row_type": "event_core_opportunity",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": "run-review-doctor",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "core_opportunity_id": "agg:3381ebd96566",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_path_type": "venue_value_capture",
            "final_opportunity_level": "high_priority",
            "opportunity_level": "high_priority",
            "final_opportunity_score": 92,
            "opportunity_score_final": 92,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            "card_path": str(card),
            "research_card_path": str(card),
            "feedback_target": "agg:3381ebd96566",
            **quality,
        }
        canonical = {
            "row_type": "event_alpha_alert_snapshot",
            "run_id": "run-review-doctor",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "alert_id": "ea:velvet-canonical",
            "core_opportunity_id": "agg:3381ebd96566",
            "snapshot_class": "canonical_core_snapshot",
            "core_resolution_status": "canonical",
            "snapshot_core_resolution_status": "core_reconciled",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_path_type": "venue_value_capture",
            "final_opportunity_level": "high_priority",
            "opportunity_level": "high_priority",
            "final_opportunity_score": 92,
            "opportunity_score_final": 92,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "tier": "HIGH_PRIORITY_WATCH",
            "feedback_target": "agg:3381ebd96566",
            **quality,
        }
        diagnostic = {
            **canonical,
            "alert_id": "ea:velvet-support",
            "snapshot_class": "diagnostic_support_snapshot",
            "core_resolution_status": "diagnostic_support",
            "snapshot_core_resolution_status": "diagnostic_support",
            "is_diagnostic_snapshot": True,
            "candidate_role": "source_noise",
            "impact_path_type": "insufficient_data",
            "playbook_type": "source_noise_control",
            "final_opportunity_level": "local_only",
            "opportunity_level": "local_only",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "feedback_target": "",
        }
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-review-doctor",
                "profile": "evidence_acquisition_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "evidence_acquisition_smoke",
                "success": True,
            }],
            core_opportunity_rows=[core],
            alert_rows=[diagnostic, canonical],
            card_paths=[card],
            profile="evidence_acquisition_smoke",
            artifact_namespace="evidence_acquisition_smoke",
            strict=True,
        )
    assert doctor.inbox_diagnostic_snapshot_visible_by_default == 0
    assert doctor.audit_primary_snapshot_not_canonical_when_canonical_exists == 0
    assert doctor.inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists == 0
    assert doctor.feedback_readiness_counts_diagnostic_as_required == 0
    assert not any("inbox_diagnostic_snapshot_visible_by_default" in item for item in doctor.blockers)
    assert not any("audit_primary_snapshot_not_canonical_when_canonical_exists" in item for item in doctor.blockers)


def test_artifact_doctor_blocks_bad_diagnostic_support_snapshot_and_duplicate_canonical_alerts():
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_alpha_router, event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-bad-diagnostic-support",
        "profile": "evidence_acquisition_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "evidence_acquisition_smoke",
        "core_opportunity_id": "agg:3381ebd96566",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "final_opportunity_level": "high_priority",
        "opportunity_level": "high_priority",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
    }
    bad_support = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-bad-diagnostic-support",
        "profile": "evidence_acquisition_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "evidence_acquisition_smoke",
        "alert_id": "ea:bad-support",
        "core_opportunity_id": "agg:3381ebd96566",
        "core_resolution_status": "diagnostic_support",
        "snapshot_class": "diagnostic_support_snapshot",
        "is_diagnostic_snapshot": True,
        "candidate_role": "source_noise",
        "impact_path_type": "insufficient_data",
        "final_opportunity_level": "high_priority",
        "opportunity_level": "high_priority",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "alertable_after_quality_gate": True,
        "route_alertable": True,
    }
    duplicate_a = {
        **bad_support,
        "alert_id": "ea:canonical-a",
        "core_resolution_status": "canonical",
        "snapshot_class": "canonical_core_snapshot",
        "is_diagnostic_snapshot": False,
        "candidate_role": "proxy_venue",
        "impact_path_type": "venue_value_capture",
    }
    duplicate_b = {**duplicate_a, "alert_id": "ea:canonical-b"}
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-bad-diagnostic-support",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "success": True,
        }],
        core_opportunity_rows=[core],
        alert_rows=[bad_support, duplicate_a, duplicate_b],
        profile="evidence_acquisition_smoke",
        artifact_namespace="evidence_acquisition_smoke",
        strict=True,
    )
    assert doctor.diagnostic_support_snapshot_alertable == 1
    assert doctor.diagnostic_support_snapshot_inherits_core_route == 1
    assert doctor.duplicate_alertable_snapshot_for_core == 1
    assert doctor.status == "BLOCKED"
    assert any("diagnostic_support_snapshot_alertable=1" in item for item in doctor.blockers)
    assert any("diagnostic_support_snapshot_inherits_core_route=1" in item for item in doctor.blockers)
    assert any("duplicate_alertable_snapshot_for_core=1" in item for item in doctor.blockers)


def test_artifact_doctor_detects_unreconciled_snapshot_core_mismatch():
    from crypto_rsi_scanner import event_alpha_alert_store, event_alpha_artifact_doctor, event_alpha_router, event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-snapshot-doctor",
        "profile": "live_burn_in_no_send",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_stale_live",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "final_opportunity_level": "exploratory",
        "opportunity_level": "exploratory",
        "final_opportunity_score": 0,
        "opportunity_score_final": 0,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "state": event_watchlist.EventWatchlistState.RADAR.value,
        "live_confirmation_required": True,
        "live_confirmation_passed": False,
        "live_confirmation_status": "missing",
        "live_confirmation_reason": "rejected_results_only_not_confirmation",
        "live_confirmation_capped": True,
    }
    stale = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-snapshot-doctor",
        "profile": "live_burn_in_no_send",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_stale_live",
        "alert_id": "ea:btc",
        "alert_key": "event:btc",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "final_opportunity_level": "validated_digest",
        "opportunity_level": "validated_digest",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "route": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.WATCHLIST.value,
        "state": event_watchlist.EventWatchlistState.WATCHLIST.value,
        "alertable_after_quality_gate": True,
        "route_alertable": True,
    }
    run = {
        "run_id": "run-snapshot-doctor",
        "profile": "live_burn_in_no_send",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "success": True,
    }
    bad = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[run],
        core_opportunity_rows=[core],
        alert_rows=[stale],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )
    assert bad.alert_snapshot_route_mismatch_core_store == 1
    assert bad.alert_snapshot_level_mismatch_core_store == 1
    assert bad.alert_snapshot_live_confirmation_stale == 1
    assert bad.status == "BLOCKED"

    reconciled = event_alpha_alert_store.reconcile_alert_snapshot_with_core_store(stale, core)
    clean = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[run],
        core_opportunity_rows=[core],
        alert_rows=[reconciled],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )
    assert clean.alert_snapshot_route_mismatch_core_store == 0
    assert clean.alert_snapshot_level_mismatch_core_store == 0
    assert clean.alert_snapshot_live_confirmation_stale == 0
    assert clean.alert_snapshot_pre_reconciliation_alertable == 1
    assert not any("alert_snapshot_pre_reconciliation_alertable" in item for item in clean.blockers)

    missing = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[run],
        core_opportunity_rows=[{**core, "core_opportunity_id": "core_other"}],
        alert_rows=[{**stale, "core_opportunity_id": "core_missing"}],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )
    assert missing.alert_snapshot_core_resolution_missing == 1
    assert missing.status == "BLOCKED"


def test_artifact_doctor_blocks_latest_delivery_rows_missing_explicit_status():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            namespace = "status_missing"
            preview = Path("event_fade_cache") / namespace / "event_alpha_notification_preview.md"
            preview.parent.mkdir(parents=True, exist_ok=True)
            preview.write_text(
                "# Event Alpha Notification Preview\n\n"
                "## Lane 1: health_heartbeat\n\n"
                "### Telegram Body\n\n"
                "```html\n"
                "<b>Event Alpha Heartbeat</b>\n"
                "Completed: yes\n"
                "Raw events: 0 · Core opportunities: 0\n"
                "Extraction rows: 0\n"
                "Alertable decisions: 0 · Alerts: 0\n"
                "Delivery lanes: due=1 · sent=0 · would_send_but_guard_disabled=1 · blocked_by_quality=0 · blocked_by_cooldown=0 · not_due=0\n"
                "Send guard: No-send rehearsal: would send, but send guard is disabled. This is expected in rehearsal mode.\n"
                "LLM calls/skips: 0/0\n"
                "```",
                encoding="utf-8",
            )
            run = {
                "row_type": "event_alpha_run",
                "run_id": "run-status",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": namespace,
                "cycle_completed": True,
                "success": True,
                "raw_events": 0,
                "extraction_rows": 0,
                "core_opportunity_rows_written": 0,
                "alertable": 0,
                "alerts": 0,
                "llm_calls_attempted": 0,
                "llm_skipped_due_budget": 0,
                "send_lane_items_attempted": {"health_heartbeat": 1},
                "send_lane_items_delivered": {"health_heartbeat": 0},
            }
            legacy_delivery = {
                "row_type": "event_alpha_notification_delivery",
                "run_id": "run-status",
                "alert_id": "heartbeat",
                "profile": "notify_llm_deep",
                "namespace": namespace,
                "artifact_namespace": namespace,
                "lane": "health_heartbeat",
                "route": "HEALTH_HEARTBEAT",
                "content_hash": "hash",
                "state": "blocked",
                "error_class": "guard_blocked",
                "error_message_safe": "event alerts disabled",
                "notification_preview_relpath": preview.as_posix(),
                "attempted_at": "2026-06-29T12:00:00+00:00",
            }
            result = event_alpha_artifact_doctor.diagnose_artifacts(
                run_rows=[run],
                delivery_rows=[legacy_delivery],
                profile="notify_llm_deep",
                artifact_namespace=namespace,
                strict=True,
                delivery_strict_scope="latest_run",
            )
        finally:
            os.chdir(old_cwd)
    assert result.status == "BLOCKED"
    assert result.delivery_status_missing == 1
    assert result.delivery_status_detail_missing == 1
    assert result.delivery_mode_missing == 1
    text = event_alpha_artifact_doctor.format_artifact_doctor_report(result)
    assert "status_missing=1" in text
    assert "delivery_status_missing=1" in "\n".join(result.blockers)


def test_send_readiness_blocks_missing_delivery_status_fields():
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_alpha_send_readiness

    doctor = event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult(
        status="BLOCKED",
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep_rehearsal",
        run_rows=1,
        alert_rows=0,
        feedback_rows=0,
        outcome_rows=0,
        card_files=0,
        delivery_status_missing=1,
        delivery_status_detail_missing=1,
        delivery_mode_missing=1,
        blockers=("delivery_status_missing=1",),
    )
    result = event_alpha_send_readiness.build_send_readiness(
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep_rehearsal",
        run_rows=[{
            "run_id": "run-status",
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "cycle_completed": True,
            "success": True,
        }],
        core_opportunity_rows=[],
        alert_rows=[],
        delivery_rows=[{
            "row_type": "event_alpha_notification_delivery",
            "run_id": "run-status",
            "profile": "notify_llm_deep",
            "namespace": "notify_llm_deep_rehearsal",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "lane": "health_heartbeat",
            "state": "blocked",
        }],
        artifact_doctor=doctor,
        send_guard_enabled=False,
        telegram_ready=False,
        preview_path="/tmp/missing-preview.md",
    )
    blockers = "\n".join(result.blockers)
    assert "delivery rows are missing explicit delivery_state" in blockers
    assert "delivery row missing explicit delivery_state" in blockers
    assert result.ready is False


def test_artifact_doctor_blocks_raw_core_source_only_narrative_stale_final_level():
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_alpha_router

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
        "candidate_role": "proxy_instrument",
        "primary_impact_path": "unlock_supply_event",
        "impact_path_type": "unlock_supply_event",
        "opportunity_level": "validated_digest",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
        "route": event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
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
    }
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        core_opportunity_rows=[stale],
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
        strict=True,
    )
    assert doctor.status == "BLOCKED"
    assert doctor.raw_core_validated_without_confirmation == 1
    assert doctor.raw_core_source_only_narrative_validated == 1
    assert doctor.raw_core_cryptopanic_tag_only_direct_path_confirmed == 1
    assert doctor.raw_core_suppressed_duplicate_validated_stale == 1


def test_artifact_doctor_flags_invalid_opportunity_lanes():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    rows = [
        {
            "core_opportunity_id": "core_bad_confirmed",
            "opportunity_type": "CONFIRMED_LONG_RESEARCH",
            "market_state": "no_reaction",
            "market_state_snapshot": {"observed_fields": 1},
            "opportunity_type_source_requirements_met": True,
            "opportunity_type_market_requirements_met": False,
        },
        {
            "core_opportunity_id": "core_bad_fade",
            "opportunity_type": "FADE_SHORT_REVIEW",
            "market_state": "late_momentum",
            "market_state_snapshot": {"return_24h": 45},
            "opportunity_type_fade_requirements_met": False,
        },
        {
            "core_opportunity_id": "core_missing_snapshot",
            "opportunity_type": "EARLY_LONG_RESEARCH",
            "market_state": "no_reaction",
            "opportunity_type_source_strength": "weak",
        },
        {
            "core_opportunity_id": "core_bad_crypto",
            "opportunity_type": "CONFIRMED_LONG_RESEARCH",
            "market_state": "confirmed_breakout",
            "market_state_snapshot": {"return_24h": 20},
            "opportunity_type_source_requirements_met": True,
            "opportunity_type_market_requirements_met": True,
            "source_class": "cryptopanic_tagged",
            "source_pack": "fan_sports_pack",
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
            "accepted_evidence_count": 1,
            "market_confirmation_level": "strong",
            "market_context_freshness_status": "fresh",
        },
        {
            "core_opportunity_id": "core_bad_risk_bucket",
            "opportunity_type": "RISK_ONLY",
            "market_state": "no_reaction",
            "market_state_snapshot": {"observed_fields": 1},
            "opportunity_type_why_not_alertable": ["strong_source_missing", "market_reaction_missing"],
            "impact_path_type": "proxy_attention",
        },
        {
            "core_opportunity_id": "core_bad_diagnostic_visible",
            "opportunity_type": "DIAGNOSTIC",
            "market_state": "no_reaction",
            "market_state_snapshot": {"observed_fields": 1},
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
        },
        {
            "core_opportunity_id": "core_double_scaled",
            "opportunity_type": "CONFIRMED_LONG_RESEARCH",
            "market_state": "confirmed_breakout",
            "source_requirements_met": True,
            "market_requirements_met": True,
            "latest_market_snapshot": {"return_4h": 0.014859616004286647},
            "market_state_snapshot": {"return_unit": "percent_points", "return_4h": 148.59616004286647},
        },
    ]
    conflicts = event_alpha_artifact_doctor._opportunity_lane_conflicts(rows)

    assert conflicts["confirmed_long_without_source_market"] == 1
    assert conflicts["fade_short_without_crowding_exhaustion"] == 1
    assert conflicts["early_long_without_fresh_strong_source"] == 1
    assert conflicts["cryptopanic_only_narrative_confirmed_lane"] == 1
    assert conflicts["risk_only_missing_evidence_only"] == 1
    assert conflicts["diagnostic_visible_default_operator_lane"] == 1
    assert conflicts["core_missing_market_state_snapshot"] == 1
    assert conflicts["market_state_possible_double_scaled"] == 1
    assert conflicts["market_state_lane_possible_double_scaled"] == 1


def test_artifact_doctor_flags_malformed_market_anomaly_artifacts():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    rows = [
        {
            "row_type": "event_market_anomaly",
            "symbol": "BAD",
            "coin_id": "bad",
            "anomaly_type": "confirmed_breakout",
            "market_state_snapshot": {
                "return_4h": 3.0,
                "return_24h": 4.0,
                "volume_zscore_24h": 0.5,
                "relative_return_vs_btc_4h": 1.0,
                "freshness_status": "fresh",
            },
            "market_state_class": "confirmed_breakout",
            "needs_catalyst_search": True,
            "suggested_source_packs_to_search": ["market_anomaly_pack"],
        },
        {
            "row_type": "event_market_anomaly",
            "symbol": "ILL",
            "coin_id": "ill",
            "anomaly_type": "suspicious_illiquid_move",
            "market_state_class": "suspicious_illiquid_move",
            "market_state_snapshot": {"return_24h": 70, "freshness_status": "fresh"},
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
        },
        {
            "row_type": "event_market_anomaly",
            "symbol": "ALRT",
            "coin_id": "alert-leak",
            "anomaly_type": "late_momentum",
            "market_state_class": "late_momentum",
            "market_state_snapshot": {"return_24h": 35, "freshness_status": "fresh"},
            "alert_id": "should_not_exist",
        },
        {
            "row_type": "event_market_anomaly",
            "symbol": "NOSNAP",
            "coin_id": "nosnap",
            "anomaly_type": "late_momentum",
            "market_state_class": "late_momentum",
        },
        {
            "row_type": "event_market_anomaly",
            "symbol": "NOPLAN",
            "coin_id": "noplan",
            "anomaly_type": "stealth_accumulation",
            "market_state_snapshot": {"return_4h": 4, "volume_zscore_24h": 1.4},
            "needs_catalyst_search": True,
        },
    ]
    conflicts = event_alpha_artifact_doctor._market_anomaly_artifact_conflicts(rows)

    assert conflicts["market_anomaly_confirmed_breakout_missing_evidence"] == 1
    assert conflicts["market_anomaly_suspicious_illiquid_promoted_confirmed"] == 1
    assert conflicts["market_anomaly_created_alert_rows"] == 2
    assert conflicts["market_anomaly_missing_market_state_snapshot"] == 1
    assert conflicts["market_anomaly_missing_market_state_class"] == 1
    assert conflicts["market_anomaly_missing_freshness_status"] == 2
    assert conflicts["market_anomaly_needs_search_without_plan"] == 1


def test_event_alpha_bybit_announcements_rehearsal_mocked_429_403_and_doctor_conflicts_are_safe():
    import json
    from datetime import datetime, timezone
    from urllib.error import HTTPError

    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_bybit_announcements_preflight

    original_max_pages = os.environ.get(event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES)
    try:
        os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES] = "1"

        def raising_opener(code):
            def opener(request, _timeout):
                raise HTTPError(request.full_url, code, "blocked", None, None)

            return opener

        for code, expected_status, expected_health in (
            (429, "rate_limited", "rate_limited"),
            (403, "auth_or_access_error", "auth_or_access_error"),
        ):
            with TemporaryDirectory() as tmp:
                base = Path(tmp)
                _preflight, report, _paths = event_bybit_announcements_preflight.run_no_send_rehearsal(
                    namespace_dir=base,
                    provider_health_path=base / "event_provider_health.json",
                    profile="fixture",
                    artifact_namespace="bybit_error_mock",
                    allow_live_preflight=True,
                    opener=raising_opener(code),
                    now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
                )
                ledger_text = (base / event_bybit_announcements_preflight.REQUEST_LEDGER).read_text(encoding="utf-8")
                ledger_rows = [json.loads(line) for line in ledger_text.splitlines() if line.strip()]
                assert report.status == expected_status
                assert report.provider_health_status == expected_health
                assert ledger_rows[0]["status_code"] == code
                assert ledger_rows[0]["success"] is False
                assert "Authorization" not in ledger_text
                assert "api_key" not in ledger_text.casefold()

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / event_bybit_announcements_preflight.REHEARSAL_JSON).write_text(
                json.dumps({
                    "provider": "bybit_announcements",
                    "live_call_allowed": True,
                    "allow_live_preflight": False,
                    "telegram_sends": 1,
                }),
                encoding="utf-8",
            )
            (base / event_bybit_announcements_preflight.REQUEST_LEDGER).write_text(
                json.dumps({
                    "provider": "bybit_announcements",
                    "live_call_allowed": True,
                    "unsupported_query_params": ["category"],
                })
                + "\n",
                encoding="utf-8",
            )
            conflicts = event_bybit_announcements_preflight.artifact_conflicts(base)
            assert conflicts["bybit_announcements_rehearsal_live_without_explicit_allow"] == 1
            assert conflicts["bybit_announcements_rehearsal_unsupported_params"] == 1
            assert conflicts["bybit_announcements_rehearsal_forbidden_side_effect_claim"] == 1
            doctor = event_alpha_artifact_doctor.diagnose_artifacts(
                inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
                profile="fixture",
                artifact_namespace="bybit_error_mock",
                include_test_artifacts=True,
                strict=True,
            )
            assert doctor.bybit_announcements_rehearsal_live_without_explicit_allow == 1
            assert doctor.bybit_announcements_rehearsal_unsupported_params == 1
            assert doctor.bybit_announcements_rehearsal_forbidden_side_effect_claim == 1
            assert doctor.status == "BLOCKED"
    finally:
        if original_max_pages is None:
            os.environ.pop(event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES, None)
        else:
            os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES] = original_max_pages


def test_official_exchange_artifact_doctor_conflicts():
    import json

    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_official_exchange_activation

    rows = [
        {
            "row_type": "official_listing_candidate",
            "symbol": "BAD",
            "coin_id": "bad",
            "event_type": "spot_listing",
            "source_class": "crypto_news",
            "source_pack": "official_exchange_listing_pack",
            "title": "Media says BAD listed",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://example.test/bad",
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "USDT",
            "coin_id": "tether",
            "event_type": "spot_listing",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_listing_pack",
            "title": "Binance Adds BTC/USDT",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://www.binance.com/en/support/announcement/btc-usdt",
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "DLST",
            "coin_id": "delist",
            "event_type": "delisting",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_risk_pack",
            "title": "Binance Will Delist DLST",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://www.binance.com/en/support/announcement/dlst",
            "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "MISS",
            "coin_id": "missing",
            "event_type": "spot_listing",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_listing_pack",
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "LEAK",
            "coin_id": "leak",
            "event_type": "spot_listing",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_listing_pack",
            "title": "Binance Will List LEAK",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://www.binance.com/en/support/announcement/leak?signature=abc",
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "ALRT",
            "coin_id": "alert",
            "event_type": "spot_listing",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_listing_pack",
            "title": "Binance Will List ALRT",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://www.binance.com/en/support/announcement/alrt",
            "created_alert": True,
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "event_type": "spot_listing",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_listing_pack",
            "title": "Bybit Adds BTC/USDT",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://announcements.bybit.com/article/btc-usdt",
            "major_pair_simple_announcement": True,
            "opportunity_type": "EARLY_LONG_RESEARCH",
        },
    ]
    conflicts = event_alpha_artifact_doctor._official_exchange_artifact_conflicts(rows)

    assert conflicts["official_exchange_listing_without_official_source"] == 1
    assert conflicts["official_exchange_quote_asset_misclassified"] == 1
    assert conflicts["official_exchange_delisting_long_research"] == 1
    assert conflicts["official_exchange_candidate_missing_source_fields"] == 1
    assert conflicts["official_exchange_secret_leak"] == 1
    assert conflicts["official_exchange_major_pair_noise_promoted_early_long"] == 1
    assert conflicts["official_exchange_created_alert_rows"] == 1

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / event_official_exchange_activation.ACTIVATION_JSON).write_text(
            json.dumps(
                {
                    "schema_version": "event_official_exchange_activation_v1",
                    "providers": [
                        {
                            "provider": "bybit_announcements_public",
                            "mode": "public_http_no_key",
                            "configured": True,
                            "live_call_allowed": True,
                            "no_send_rehearsal": True,
                            "request_ledger_path": None,
                            "provider_health_key": "bybit_announcements",
                            "source_url_count": 1,
                            "announcements_seen": 1,
                            "official_events_written": 1,
                            "listing_candidates_written": 1,
                            "risk_candidates_written": 0,
                            "strict_alerts_created": 0,
                            "telegram_sends": 1,
                        },
                        {
                            "provider": "binance_announcements_signed_listener",
                            "mode": "signed_websocket_listener",
                            "configured": True,
                            "live_call_allowed": False,
                            "no_send_rehearsal": True,
                            "request_ledger_path": None,
                            "provider_health_key": "binance_announcements_signed_listener",
                            "source_url_count": 0,
                            "announcements_seen": 0,
                            "official_events_written": 0,
                            "listing_candidates_written": 0,
                            "risk_candidates_written": 0,
                            "strict_alerts_created": 0,
                            "telegram_sends": 0,
                            "last_error_safe": "api_secret='THIS_IS_A_TEST_SECRET_VALUE_123456'",
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        activation_conflicts = event_official_exchange_activation.artifact_conflicts(base)
        assert activation_conflicts["official_exchange_activation_live_without_ledger"] == 1
        assert activation_conflicts["official_exchange_activation_signed_listener_secret_leak"] == 1
        assert activation_conflicts["official_exchange_activation_forbidden_side_effect_claim"] == 1
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor.official_exchange_activation_live_without_ledger == 1
        assert doctor.official_exchange_activation_signed_listener_secret_leak == 1
        assert doctor.official_exchange_activation_forbidden_side_effect_claim == 1
        assert doctor.status == "BLOCKED"


def test_scheduled_catalyst_artifact_doctor_conflicts():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    rows = [
        {
            "row_type": "unlock_event",
            "symbol": "MEDIA",
            "coin_id": "media",
            "event_type": "token_unlock",
            "impact_path_type": "unlock_supply_event",
            "source_class": "cryptopanic_tagged",
            "source_url": "https://cryptopanic.com/news/media",
            "unlock_time": "2026-06-16T16:00:00Z",
            "unlock_pct_circulating_supply": 0.12,
            "opportunity_type": "RISK_ONLY",
        },
        {
            "row_type": "unlock_event",
            "symbol": "MISS",
            "coin_id": "missing",
            "event_type": "token_unlock",
            "source_class": "structured_unlock",
            "source_url": "https://tokenomist.ai/miss",
            "opportunity_type": "RISK_ONLY",
        },
        {
            "row_type": "unlock_event",
            "symbol": "SIZE",
            "coin_id": "size",
            "event_type": "token_unlock",
            "source_class": "structured_unlock",
            "source_url": "https://tokenomist.ai/size",
            "unlock_time": "2026-06-16T16:00:00Z",
            "opportunity_type": "FADE_SHORT_REVIEW",
        },
        {
            "row_type": "scheduled_catalyst_event",
            "symbol": "STALE",
            "coin_id": "stale",
            "event_type": "protocol_upgrade",
            "event_status": "completed",
            "event_age_hours": 48,
            "source_url": "https://project.test/stale",
            "opportunity_type": "EARLY_LONG_RESEARCH",
        },
        {
            "row_type": "scheduled_catalyst_event",
            "symbol": "NOSRC",
            "coin_id": "nosrc",
            "event_type": "protocol_upgrade",
            "opportunity_type": "EARLY_LONG_RESEARCH",
        },
        {
            "row_type": "scheduled_catalyst_event",
            "symbol": "ALRT",
            "coin_id": "alert",
            "event_type": "protocol_upgrade",
            "source_url": "https://project.test/alert",
            "created_alert": True,
        },
    ]
    conflicts = event_alpha_artifact_doctor._scheduled_catalyst_artifact_conflicts(rows)

    assert conflicts["unlock_without_structured_evidence"] == 1
    assert conflicts["media_unlock_promoted_structured"] == 1
    assert conflicts["cryptopanic_unlock_proof"] == 1
    assert conflicts["unlock_missing_event_time"] == 1
    assert conflicts["unlock_promoted_without_size_metrics"] == 2
    assert conflicts["stale_completed_catalyst_upcoming"] == 1
    assert conflicts["calendar_event_missing_source_url"] == 1
    assert conflicts["scheduled_catalyst_created_alert_rows"] == 1


def test_derivatives_crowding_artifact_doctor_conflicts():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    rows = [
        {
            "row_type": "derivatives_state_snapshot",
            "symbol": "MISS",
            "funding_rate": 0.001,
            "supported_metric_status": {"basis": "implemented"},
            "raw_payload_redacted": {"api_key": "should_not_show"},
        },
        {
            "row_type": "fade_short_review_candidate",
            "symbol": "NOMOVE",
            "opportunity_type": "FADE_SHORT_REVIEW",
            "completed_move": False,
            "fade_requirements_met": True,
            "crowding_exhaustion_evidence": ["funding_zscore_elevated"],
            "research_only_disclaimer": "Research-only. Not a trade signal.",
            "derivatives_state_snapshot": {"freshness_status": "stale"},
        },
        {
            "row_type": "fade_short_review_candidate",
            "symbol": "NOCROWD",
            "opportunity_type": "FADE_SHORT_REVIEW",
            "completed_move": True,
            "fade_requirements_met": False,
            "crowding_exhaustion_evidence": [],
            "research_only_disclaimer": "Research-only. Not a trade signal.",
        },
        {
            "row_type": "fade_short_review_candidate",
            "symbol": "LEAK",
            "opportunity_type": "FADE_SHORT_REVIEW",
            "completed_move": True,
            "fade_requirements_met": True,
            "crowding_exhaustion_evidence": ["funding_zscore_elevated"],
            "research_only_disclaimer": "fade review",
            "triggered_fade_created": True,
            "normal_rsi_signal_written": True,
            "raw_payload_redacted": {"auth_token": "abc"},
        },
        {
            "row_type": "fade_short_review_candidate",
            "symbol": "CROWDLONG",
            "opportunity_type": "CONFIRMED_LONG_RESEARCH",
            "crowding_class": "high",
            "warnings": [],
            "research_only_disclaimer": "Research-only. Not a trade signal.",
        },
    ]
    conflicts = event_alpha_artifact_doctor._derivatives_crowding_artifact_conflicts(rows)

    assert conflicts["fade_review_without_completed_move"] == 1
    assert conflicts["fade_review_without_crowding_exhaustion"] == 1
    assert conflicts["fade_review_created_triggered_fade"] == 1
    assert conflicts["fade_review_created_normal_rsi_signal"] == 1
    assert conflicts["fade_review_notification_missing_disclaimer"] == 1
    assert conflicts["derivatives_artifact_secret_leak"] == 2
    assert conflicts["derivatives_state_missing_freshness_status"] == 1
    assert conflicts["derivatives_metric_claim_implemented_missing"] == 1
    assert conflicts["derivatives_unit_metadata_missing"] == 1
    assert conflicts["stale_derivatives_snapshot_promoted_fade_review"] == 1
    assert conflicts["confirmed_long_crowded_without_warning"] == 1


def test_instrument_resolution_artifact_doctor_conflicts():
    import json

    from crypto_rsi_scanner import config, event_asset_registry, event_instrument_resolver

    with TemporaryDirectory() as tmp:
        namespace = Path(tmp)
        registry = event_asset_registry.build_asset_registry(fixture_path=config.EVENT_ASSET_REGISTRY_PATH)
        event_asset_registry.write_asset_registry_artifact(
            registry,
            namespace,
            generated_at="2026-06-15T16:00:00Z",
            profile="fixture",
            artifact_namespace="instrument_resolution_test",
            run_mode="fixture",
            run_id="run",
        )
        bad_candidates = [
            {
                "row_type": "event_integrated_radar_candidate",
                "symbol": "TESTPERP",
                "coin_id": "test-perp",
                "opportunity_type": "CONFIRMED_LONG_RESEARCH",
            },
            {
                "row_type": "event_integrated_radar_candidate",
                "symbol": "USDT",
                "coin_id": "tether",
                "canonical_asset_id": "tether",
                "opportunity_type": "EARLY_LONG_RESEARCH",
                "is_tradable_asset": True,
                "quote_asset_excluded": True,
            },
            {
                "row_type": "event_integrated_radar_candidate",
                "symbol": "SECTOR",
                "coin_id": "ai_theme",
                "canonical_asset_id": "ai_theme",
                "opportunity_type": "CONFIRMED_LONG_RESEARCH",
                "is_tradable_asset": True,
                "is_theme_or_sector": True,
            },
        ]
        (namespace / "event_integrated_radar_candidates.jsonl").write_text(
            "\n".join(json.dumps(row) for row in bad_candidates) + "\n",
            encoding="utf-8",
        )
        (namespace / event_instrument_resolver.INSTRUMENT_RESOLUTION_JSONL).write_text(
            json.dumps({
                "row_type": "event_instrument_resolution",
                "resolver_warnings": ["coinalyze_symbol_not_linked_to_asset"],
            })
            + "\n",
            encoding="utf-8",
        )

        conflicts = event_instrument_resolver.artifact_conflicts(namespace)
        assert conflicts["instrument_resolution_missing_canonical_id_when_fixture_has_it"] == 1
        assert conflicts["instrument_resolution_quote_asset_misclassified"] == 1
        assert conflicts["instrument_resolution_sector_visible_as_tradable"] == 1
        assert conflicts["instrument_resolution_coinalyze_symbol_unlinked"] == 1


def test_integrated_doctor_catches_core_and_card_mismatches():
    import json

    from crypto_rsi_scanner import event_alpha_artifact_doctor

    candidate = {
        "row_type": "event_integrated_radar_candidate",
        "symbol": "BTC",
        "core_opportunity_id": "core-btc",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "market_state_class": "no_reaction",
        "source_url": "https://example.com/btc",
        "reason_codes": ["major_pair_simple_announcement_capped"],
        "major_pair_simple_announcement": True,
        "why_now": "simple major-pair announcement capped as unconfirmed research",
        "official_exchange_event": {"event_type": "new_trading_pair", "exchange": "binance", "source_url": "https://example.com/btc"},
    }
    core = {
        "core_opportunity_id": "core-btc",
        "symbol": "BTC",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "market_state_class": "confirmed_breakout",
        "reason_codes": [],
    }

    conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
        [candidate],
        core_rows=[core],
        research_card_paths=(),
    )

    assert conflicts["integrated_candidate_core_opportunity_type_mismatch"] == 1
    assert conflicts["integrated_candidate_core_market_state_mismatch"] == 1
    assert conflicts["integrated_candidate_core_reason_code_loss"] == 1
    assert conflicts["integrated_candidate_core_source_url_loss"] == 1
    assert conflicts["integrated_candidate_core_official_event_loss"] == 1
    assert conflicts["integrated_core_silent_upgrade"] == 1

    with TemporaryDirectory() as tmp:
        bad_card = Path(tmp) / "card_core_btc.md"
        bad_card.write_text(
            "\n".join([
                "# BTC Event Research Card",
                "",
                "## Opportunity Lane",
                "- Opportunity type: EARLY_LONG_RESEARCH",
                "- Why now: strong source with no reaction; monitor before the move is crowded",
                "",
                "## Artifact Lineage",
                "- Core opportunity ID: core-btc",
            ]),
            encoding="utf-8",
        )
        card_conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [candidate],
            core_rows=[{**candidate, "row_type": "event_core_opportunity"}],
            research_card_paths=(bad_card,),
        )
    assert card_conflicts["integrated_candidate_card_opportunity_type_mismatch"] == 1
    assert card_conflicts["card_opportunity_lane_core_mismatch"] == 1
    assert card_conflicts["integrated_candidate_card_why_now_mismatch"] == 1
    assert card_conflicts["integrated_major_pair_card_early_long"] == 1
    assert card_conflicts["integrated_card_generic_lane_override"] == 1

    fade_candidate = {
        "row_type": "event_integrated_radar_candidate",
        "symbol": "TESTFADE",
        "core_opportunity_id": "core-fade",
        "opportunity_type": "FADE_SHORT_REVIEW",
        "market_state_class": "post_event_fade_setup",
        "market_requirements_met": True,
        "derivatives_state_snapshot": {"funding_rate": 0.12},
        "crowding_class": "extreme",
        "fade_readiness": "ready_for_review",
        "crowding_exhaustion_evidence": ["open_interest_delta_24h_high"],
    }
    with TemporaryDirectory() as tmp:
        bad_fade_card = Path(tmp) / "card_core_fade.md"
        bad_fade_card.write_text(
            "\n".join([
                "# TESTFADE Event Research Card",
                "",
                "## Opportunity Lane",
                "- Opportunity type: FADE_SHORT_REVIEW",
                "- Why now: completed move with derivatives crowding/exhaustion evidence",
                "",
                "## Derivatives / Crowding",
                "- Funding: current=+12.00% predicted=n/a z=n/a",
                "- Basis: n/a unit=unknown",
                "- Crowding class: unknown",
                "- Fade readiness: unknown",
                "",
                "## Outcome Tracking",
                "- Asset primary return: -12.00%",
                "",
                "## Artifact Lineage",
                "- Core opportunity ID: core-fade",
            ]),
            encoding="utf-8",
        )
        fade_conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [fade_candidate],
            core_rows=[{**fade_candidate, "row_type": "event_core_opportunity"}],
            research_card_paths=(bad_fade_card,),
        )
    assert fade_conflicts["integrated_fade_card_missing_disclaimer"] == 1
    assert fade_conflicts["integrated_fade_card_crowding_unknown"] == 1
    assert fade_conflicts["derivatives_card_metric_claim_without_data"] == 2
    assert fade_conflicts["integrated_outcome_card_thesis_interpretation_missing"] == 1

    coinalyze_candidate = {
        "row_type": "event_integrated_radar_candidate",
        "symbol": "TESTPERP",
        "core_opportunity_id": "core-perp",
        "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        "market_state_class": "confirmed_breakout",
        "source_requirements_met": True,
        "market_requirements_met": True,
        "coinalyze_derivatives_attached": True,
        "coinalyze_artifact_namespace": "external_coinalyze",
        "derivatives_state_snapshot": {
            "provider": "coinalyze",
            "coinalyze_artifact_namespace": "external_coinalyze",
            "coinalyze_source_artifact_path": "event_fade_cache/external_coinalyze/event_derivatives_state.jsonl",
            "funding_rate": 0.0008,
            "freshness_status": "fresh",
        },
        "crowding_class": "high",
        "crowding_exhaustion_evidence": ["open_interest_delta_24h_high"],
    }
    with TemporaryDirectory() as tmp:
        missing_coinalyze_card = Path(tmp) / "card_core_perp.md"
        missing_coinalyze_card.write_text(
            "\n".join([
                "# TESTPERP Event Research Card",
                "",
                "## Opportunity Lane",
                "- Opportunity type: CONFIRMED_LONG_RESEARCH",
                "- Why now: official/structured source plus fresh market confirmation",
                "",
                "## Derivatives / Crowding",
                "- Research-only. Not a trade signal.",
                "- Provider: coinalyze",
                "- Crowding class: high",
                "",
                "## Artifact Lineage",
                "- Core opportunity ID: core-perp",
            ]),
            encoding="utf-8",
        )
        coinalyze_card_conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [coinalyze_candidate],
            core_rows=[{**coinalyze_candidate, "row_type": "event_core_opportunity"}],
            research_card_paths=(missing_coinalyze_card,),
        )
    assert coinalyze_card_conflicts["integrated_coinalyze_crowding_card_missing"] == 1

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        manifest = tmp_path / "event_integrated_radar_input_manifest.json"
        manifest.write_text(
            json.dumps({
                "sidecars": [
                    {
                        "sidecar_name": "coinalyze",
                        "mode": "loaded_external_coinalyze",
                        "coinalyze_artifact_namespace": "external_coinalyze",
                        "coinalyze_artifact_namespace_status": "stale_deprecated",
                        "coinalyze_derivatives_state_rows_loaded": 2,
                        "coinalyze_crowding_candidates_loaded": 2,
                        "coinalyze_fade_review_candidates_loaded": 1,
                        "coinalyze_freshness_status": "stale",
                        "warnings": [],
                    }
                ]
            }),
            encoding="utf-8",
        )
        manifest_conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [
                {
                    "row_type": "event_integrated_radar_candidate",
                    "candidate_id": "iar:no-coinalyze",
                    "core_opportunity_id": "agg:no-coinalyze",
                    "symbol": "TEST",
                    "coin_id": "test",
                    "opportunity_type": "EARLY_LONG_RESEARCH",
                    "market_state_snapshot": {"market_state": "no_reaction"},
                    "source_strength": "official_structured",
                    "market_state_class": "no_reaction",
                }
            ],
            core_rows=[],
            manifest_path=manifest,
        )
    assert manifest_conflicts["integrated_coinalyze_loaded_no_rows_attached"] == 1
    assert manifest_conflicts["integrated_coinalyze_stale_loaded_without_warning"] == 1
    assert manifest_conflicts["integrated_coinalyze_loaded_from_stale_namespace"] == 1

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        manifest = tmp_path / "event_integrated_radar_input_manifest.json"
        manifest.write_text(
            json.dumps({
                "sidecars": [
                    {
                        "sidecar_name": "coinalyze",
                        "mode": "skipped_missing_artifact",
                        "coinalyze_artifact_namespace": "missing_coinalyze",
                        "coinalyze_derivatives_state_rows_loaded": 0,
                        "coinalyze_crowding_candidates_loaded": 0,
                        "coinalyze_fade_review_candidates_loaded": 0,
                        "warnings": ["coinalyze_artifacts_missing_or_empty"],
                    }
                ]
            }),
            encoding="utf-8",
        )
        skip_conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [candidate],
            core_rows=[{**candidate, "row_type": "event_core_opportunity"}],
            manifest_path=manifest,
        )
    assert skip_conflicts["integrated_coinalyze_missing_skip_reason"] == 1


def test_integrated_doctor_catches_delivery_and_outcome_conflicts():
    import json

    from crypto_rsi_scanner import event_alpha_artifact_doctor

    candidate = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "iar:test",
        "core_opportunity_id": "agg:test",
        "symbol": "TEST",
        "coin_id": "test",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "market_state_snapshot": {"market_state": "no_reaction"},
        "source_strength": "official_structured",
        "market_state_class": "no_reaction",
    }
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        preview = tmp_path / "event_alpha_notification_preview.md"
        preview.write_text("Alertable decisions: 0 · Alerts: 1\nNo research-only disclaimer", encoding="utf-8")
        deliveries = tmp_path / "event_integrated_radar_notification_deliveries.jsonl"
        deliveries.write_text(
            "\n".join([
                json.dumps({
                    "row_type": "event_integrated_radar_notification_delivery",
                    "lane": "early_long_research",
                    "lane_title": "Early Long Research",
                    "message_text": "Card: /Users/test/card.md",
                    "sent": True,
                    "no_send_rehearsal": True,
                    "skipped_item_count": 1,
                    "card_paths": ["/Users/test/card.md"],
                    "normal_rsi_signal_written": True,
                }),
                json.dumps({
                    "row_type": "event_integrated_radar_notification_delivery",
                    "lane": "early_long_research",
                    "lane_title": "Early Long Research",
                    "message_text": "Research-only. Not a trade signal. Card: none",
                    "sent": False,
                    "no_send_rehearsal": True,
                    "skipped_item_count": 0,
                    "card_paths": ["event_fade_cache/test/research_cards/card_core_test.md"],
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        outcomes = tmp_path / "event_integrated_radar_outcomes.jsonl"
        outcomes.write_text(
            json.dumps({
                "row_type": "event_integrated_radar_outcome",
                "candidate_id": "iar:test",
                "symbol": "",
                "coin_id": "",
                "opportunity_type": "DIAGNOSTIC",
                "primary_horizon_return": 10.0,
                "price_at_observation": None,
                "include_in_performance": True,
                "triggered_fade_created": True,
                "outcome_status": "missing_data",
            }) + "\n",
            encoding="utf-8",
        )
        (tmp_path / "event_integrated_radar_calibration_priors.json").write_text(
            json.dumps({
                "auto_apply": False,
                "recommendation_only": True,
                "eligible_for_auto_apply": False,
                "opportunity_type_priors": {
                    "DIAGNOSTIC": {"sample_size": 1, "auto_apply": True},
                    "EARLY_LONG_RESEARCH": {"sample_size": 1, "min_sample_size": 25},
                },
            }),
            encoding="utf-8",
        )
        manifest = tmp_path / "event_integrated_radar_input_manifest.json"
        manifest.write_text(json.dumps({"sidecars": []}), encoding="utf-8")
        daily = tmp_path / "event_alpha_daily_brief.md"
        daily.write_text("Input manifest: not available\n", encoding="utf-8")
        conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [candidate],
            core_rows=[{**candidate, "row_type": "event_core_opportunity"}],
            daily_brief_path=daily,
            manifest_path=manifest,
            delivery_path=deliveries,
            outcome_path=outcomes,
            preview_path=preview,
        )
    assert conflicts["integrated_legacy_preview_alerts_wording"] == 1
    assert conflicts["integrated_delivery_missing_disclaimer"] == 1
    assert conflicts["integrated_delivery_sent_in_no_send"] == 1
    assert conflicts["integrated_delivery_side_effect_flag"] == 1
    assert conflicts["integrated_delivery_missing_skip_reasons"] == 1
    assert conflicts["integrated_delivery_card_path_absolute"] == 1
    assert conflicts["integrated_delivery_card_path_not_rendered"] == 1
    assert conflicts["operator_structured_path_absolute"] >= 1
    assert conflicts["integrated_manifest_daily_brief_unavailable"] == 1
    assert conflicts["integrated_outcome_side_effect_flag"] == 1
    assert conflicts["integrated_outcome_schema_missing"] >= 1
    assert conflicts["integrated_outcome_missing_identity"] == 1
    assert conflicts["integrated_outcome_returns_without_price"] == 1
    assert conflicts["integrated_outcome_diagnostic_in_performance"] == 1
    assert conflicts["integrated_calibration_diagnostic_in_main_priors"] == 1
    assert conflicts["integrated_calibration_prior_safety_missing"] >= 1
    assert conflicts["integrated_outcome_return_double_scaled"] == 1
    assert conflicts["integrated_outcome_missing_data_unlabeled"] == 1


def test_integrated_doctor_requires_thesis_interpretation_for_fade_and_risk_outcomes():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    candidate = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "iar:fade",
        "core_opportunity_id": "core-fade",
        "symbol": "TESTFADE",
        "coin_id": "testfade",
        "opportunity_type": "FADE_SHORT_REVIEW",
        "market_state_snapshot": {"market_state": "post_event_fade_setup"},
        "market_state_class": "post_event_fade_setup",
    }
    missing_thesis = {
        "row_type": "event_integrated_radar_outcome",
        "candidate_id": "iar:fade",
        "symbol": "TESTFADE",
        "coin_id": "testfade",
        "opportunity_type": "FADE_SHORT_REVIEW",
        "outcome_label": "fade_review_good",
        "outcome_status": "filled",
        "primary_horizon_return": -0.12,
        "thesis_primary_move": None,
        "price_at_observation": 1.0,
        "include_in_performance": True,
        "no_trade_created": True,
        "no_paper_trade_created": True,
        "outcome_horizons": ["24h"],
        "return_by_horizon": {"24h": -0.12},
        "relative_return_vs_btc_by_horizon": {"24h": -0.14},
        "relative_return_vs_eth_by_horizon": {"24h": -0.13},
        "max_favorable_excursion_by_window": {"24h": -0.02},
        "max_adverse_excursion_by_window": {"24h": -0.12},
        "benchmark_btc_price_at_observation": 65000.0,
    }

    conflicts = event_alpha_artifact_doctor._integrated_outcome_conflicts(  # noqa: SLF001
        [candidate],
        [missing_thesis],
    )

    assert conflicts["integrated_outcome_thesis_move_missing"] == 1
    assert conflicts["integrated_outcome_schema_missing"] >= 1
