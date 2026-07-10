"""Artifact-doctor public API, schema, filters, and provider-readiness regressions."""

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from types import SimpleNamespace

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_artifact_doctor_public_entrypoints_are_split():
    import inspect

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    from crypto_rsi_scanner.event_alpha.doctor import (
        aggregation,
        artifact_doctor,
        check_registry,
        context,
        discovery,
        execution,
        result,
    )
    from crypto_rsi_scanner.event_alpha.doctor.checks import secrets
    from crypto_rsi_scanner.event_alpha.doctor.report_sections import summary

    assert artifact_doctor.diagnose_artifacts is execution.diagnose_artifacts
    assert event_alpha_artifact_doctor.diagnose_artifacts is execution.diagnose_artifacts
    assert artifact_doctor.format_artifact_doctor_report is summary.format_artifact_doctor_report
    assert artifact_doctor.EventAlphaArtifactDoctorResult is result.EventAlphaArtifactDoctorResult
    assert hasattr(artifact_doctor, "_read_jsonl")
    assert hasattr(artifact_doctor, "event_alpha_shims")

    assert len(inspect.getsourcelines(execution.diagnose_artifacts)[0]) < 150
    assert len(inspect.getsourcelines(summary.format_artifact_doctor_report)[0]) < 80
    assert check_registry.legacy_unregistered_count() == 0
    assert context.build_doctor_context().args == ()
    assert discovery.discover_namespace_artifacts(context.build_doctor_context()).kwargs == {}
    assert aggregation.determine_doctor_status(SimpleNamespace(blockers=(), warnings=())) == "OK"
    assert secrets.secret_leak_count(({"api_key": "redacted"},)) == 1


def test_notification_rehearsal_namespace_does_not_require_daily_burn_in_artifact():
    from crypto_rsi_scanner.event_alpha.doctor.checks import operations

    ctx = SimpleNamespace(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        namespace_status=SimpleNamespace(status="active_live_rehearsal", safe_for_burn_in_measurement=False),
        daily_burn_in_run={},
        candidate_mode_manifest={},
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={},
        burn_in_archive_manifest={},
        integrated_conflicts={},
        integrated_candidates=[],
    )
    blockers: list[str] = []
    warnings: list[str] = []
    operations.apply_checks(ctx, blockers, warnings)
    assert not any("daily_burn_in_run_missing" in blocker for blocker in blockers)

    ctx.namespace_status = SimpleNamespace(status="active_live_rehearsal", safe_for_burn_in_measurement=True)
    operations.apply_checks(ctx, blockers, warnings)
    assert any("daily_burn_in_run_missing" in blocker for blocker in blockers)


def test_event_alpha_doctor_check_plugins_emit_regression_messages():
    from crypto_rsi_scanner.event_alpha.doctor.checks import (
        integrated_radar,
        namespace,
        notifications,
        outcomes,
        paths,
        provider_readiness,
        safety,
        source_coverage,
        stale_artifacts,
    )

    blockers: list[str] = []
    warnings: list[str] = []
    base = SimpleNamespace(strict=True)

    integrated_radar.apply_core_card_checks(
        SimpleNamespace(
            strict=True,
            card_count=1,
            index_present=False,
            acquisition_final_conflicts={},
            daily_brief_conflicts={"daily_brief_missing_selected_run": 1},
            live_confirmation_conflicts={"live_validated_without_confirmation": 1},
            raw_core_conflicts={},
            opportunity_lane_conflicts={"market_state_return_unit_missing": 1},
            market_anomaly_conflicts={"market_anomaly_needs_search_without_plan": 1},
        ),
        blockers,
        warnings,
    )
    provider_readiness.apply_structured_artifact_checks(
        SimpleNamespace(
            strict=True,
            official_exchange_conflicts={"official_exchange_secret_leak": 1},
            official_exchange_activation_conflicts={},
            instrument_resolution_conflicts={"instrument_resolution_sector_visible_as_tradable": 1},
            scheduled_conflicts={},
            derivatives_conflicts={"derivatives_unit_metadata_missing": 1},
        ),
        blockers,
        warnings,
    )
    integrated_radar.apply_integrated_artifact_checks(
        SimpleNamespace(strict=True, integrated_conflicts={"integrated_created_triggered_fade": 1}),
        blockers,
        warnings,
    )
    paths.apply_integrated_path_checks(
        SimpleNamespace(strict=True, integrated_conflicts={"operator_structured_path_absolute": 1}),
        blockers,
        warnings,
    )
    source_coverage.apply_checks(
        SimpleNamespace(
            strict=True,
            source_coverage_report_conflicts={"source_coverage_provider_marked_healthy_without_observation": 1},
            source_coverage_conflicts={"source_pack_provider_status_missing": 1},
            cryptopanic_conflicts={"cryptopanic_token_printed_or_unredacted": 1},
        ),
        blockers,
        warnings,
    )
    provider_readiness.apply_preflight_checks(
        SimpleNamespace(
            strict=True,
            live_provider_readiness_conflicts={"live_provider_readiness_live_calls_allowed_in_smoke": 1},
            coinalyze_preflight_conflicts={"coinalyze_rehearsal_live_without_ledger": 1},
            bybit_announcements_conflicts={"bybit_announcements_rehearsal_unsupported_params": 1},
            unlock_calendar_conflicts={"unlock_calendar_preflight_live_without_ledger": 1},
            dex_onchain_conflicts={"dex_onchain_live_without_ledger": 1},
        ),
        blockers,
        warnings,
    )
    notifications.apply_checks(
        SimpleNamespace(
            strict=True,
            research_review_enabled_but_lane_missing=1,
            delivery_summary=SimpleNamespace(failed=1),
            delivery_conflicts={"delivery_core_id_missing": 1, "legacy_pre_core_delivery_identity": 1},
            preview_conflicts={"notification_preview_no_send_status_unclear": 1},
        ),
        blockers,
        warnings,
    )
    outcomes.apply_checks(
        SimpleNamespace(
            strict=True,
            strict_api=True,
            core_store_available=True,
            fresh_missing=1,
            route_conflicts=1,
            fresh_route_conflicts=1,
            fresh_missing_final_route=1,
            quality={
                "quality_fields_missing_count": 1,
                "hypothesis_rows_missing_opportunity_verdict": 1,
                "watchlist_rows_missing_quality_fields": 0,
                "alert_rows_missing_quality_fields": 0,
                "fresh_hypothesis_rows_missing_top_level_quality": 1,
                "fresh_watchlist_rows_missing_top_level_quality": 0,
                "fresh_alert_rows_missing_top_level_quality": 0,
                "legacy_quality_missing_rows": 0,
            },
            snapshot_core_conflicts={"route_mismatch": 1},
            watchlist_conflicts={"fresh_uncapped": 1},
            incident_linkage={"active_incident_without_qualified_link": 1},
        ),
        blockers,
        warnings,
    )
    namespace.apply_checks(base, blockers, warnings)
    stale_artifacts.apply_checks(base, blockers, warnings)
    safety.apply_checks(base, blockers, warnings)

    assert "research cards exist but index.md was not found" in blockers
    assert "daily_brief_missing_selected_run=1" in blockers
    assert "official_exchange_secret_leak=1" in blockers
    assert "instrument_resolution_sector_visible_as_tradable=1" in blockers
    assert "integrated_created_triggered_fade=1" in blockers
    assert "operator_structured_path_absolute=1" in blockers
    assert "source_coverage_provider_marked_healthy_without_observation=1" in blockers
    assert "live_provider_readiness_live_calls_allowed_in_smoke=1" in blockers
    assert "coinalyze_rehearsal_live_without_ledger=1" in blockers
    assert "research_review_digest_enabled_but_lane_missing=1" in blockers
    assert "delivery_core_id_missing=1" in blockers
    assert "notification_preview_no_send_status_unclear=1" in blockers
    assert "fresh_quality_route_conflict_rows=1" in blockers
    assert "active_incident_without_qualified_link=1" in blockers
    assert "derivatives_unit_metadata_missing=1" in warnings
    assert "source_pack_provider_status_missing=1" in warnings
    assert any("pre-canonical notification delivery rows" in message for message in warnings)


def test_artifact_doctor_does_not_double_count_loaded_absolute_paths(tmp_path):
    import json
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    namespace_dir = tmp_path / "notify_no_key"
    namespace_dir.mkdir()
    absolute_alert_path = "/tmp/event_fade_cache/notify_no_key/event_alpha_alerts.jsonl"
    run = {
        "row_type": "event_alpha_run",
        "run_id": "legacy-path-run",
        "profile": "notify_no_key",
        "artifact_namespace": "notify_no_key",
        "run_mode": "notification_burn_in",
        "alert_store_path": absolute_alert_path,
    }
    (namespace_dir / "event_alpha_runs.jsonl").write_text(
        json.dumps(run) + "\n",
        encoding="utf-8",
    )
    source_coverage = namespace_dir / "event_alpha_source_coverage.md"
    source_coverage.write_text("research-only source coverage\n", encoding="utf-8")

    result = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[run],
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        inspected_alert_store_path=namespace_dir / "event_alpha_alerts.jsonl",
        source_coverage_report_path=source_coverage,
        strict=True,
    )
    assert result.operator_structured_path_absolute == 1


def test_event_alpha_live_provider_readiness_smoke_artifacts_are_safe_and_doctor_checked():
    import json
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.providers.live_provider_readiness as event_live_provider_readiness

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
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

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
        assert "Doctor Check Registry:" in text
        assert "legacy_unregistered=" in text
        assert "schema.validation_errors: schema_validation_errors=1" in result.blockers
        assert "schema_rows_validated=1" in text
        assert "schema_validation_errors=1" in text
        assert "missing_required_fields=1" in text


def test_event_alpha_artifact_doctor_skip_api_keeps_schema_phases_only():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        full = event_alpha_artifact_doctor.diagnose_artifacts(
            inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
        )
        skipped = event_alpha_artifact_doctor.diagnose_artifacts(
            inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
            skip_api_checks=True,
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
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight

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
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight

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
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts

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
            include_api_artifacts=True,
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
            include_api_artifacts=True,
        )
        assert legacy.status == "WARN"
        assert "legacy_run_missing_snapshot_rows" in "; ".join(legacy.warnings)
        legacy_strict = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "legacy", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
            alert_rows=[],
            include_api_artifacts=True,
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
