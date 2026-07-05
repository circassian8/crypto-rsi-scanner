"""Event Alpha CLI registry regression tests."""

from __future__ import annotations

import importlib
import inspect

from crypto_rsi_scanner.cli import commands_event_alpha
from crypto_rsi_scanner.cli.services import (
    event_alpha_fade_review,
    event_alpha_integrated,
    event_alpha_namespace,
    event_alpha_notifications,
    event_alpha_outcomes,
    event_alpha_provider_preflights,
    event_alpha_reports,
    event_alpha_research,
)
from crypto_rsi_scanner.cli.event_alpha_command_registry import EVENT_ALPHA_COMMANDS
from crypto_rsi_scanner.cli.event_alpha_command_registry import dispatch as registry_dispatch
from crypto_rsi_scanner.cli.parser import build_parser


def test_event_alpha_registry_handlers_import():
    assert EVENT_ALPHA_COMMANDS
    for row in EVENT_ALPHA_COMMANDS:
        module = importlib.import_module(row.handler_module)
        assert getattr(module, row.handler_name)


def test_event_alpha_registry_safe_by_default():
    assert all(row.allows_live_provider_call is False for row in EVENT_ALPHA_COMMANDS)
    assert all(row.requires_no_send is True for row in EVENT_ALPHA_COMMANDS)
    assert all("research-only" in row.safety_notes for row in EVENT_ALPHA_COMMANDS)


def test_event_alpha_registry_covers_parser_command_flags():
    parser = build_parser()
    parser_dests = {
        action.dest
        for action in parser._actions
        if action.dest.startswith("event_") and any(option.startswith("--event-") for option in action.option_strings)
    }
    registry_dests = {row.parsed_attr for row in EVENT_ALPHA_COMMANDS}
    missing = sorted(dest for dest in parser_dests if dest not in registry_dests)
    allowed_options = {
        "event_alpha_artifact_doctor_delivery_scope",
        "event_alpha_artifact_doctor_strict",
        "event_alpha_artifact_doctor_strict_api",
        "event_alpha_artifact_namespace",
        "event_alpha_bybit_announcements_allow_live_preflight",
        "event_alpha_coinalyze_allow_live_preflight",
        "event_alpha_doctor_schema_only",
        "event_alpha_doctor_skip_api_checks",
        "event_alpha_include_api_artifacts",
        "event_alpha_include_stale_artifacts",
        "event_alpha_include_test_artifacts",
        "event_alpha_profile",
        "event_alpha_stale_archive",
        "event_alpha_stale_superseded_by",
        "event_alpha_unlock_calendar_provider",
    }
    assert [dest for dest in missing if dest not in allowed_options] == []


def test_event_alpha_handle_is_small_registry_bridge():
    assert len(inspect.getsourcelines(commands_event_alpha.handle)[0]) < 150


def test_event_impact_hypotheses_report_dispatch_uses_current_include_legacy_flag(monkeypatch):
    parser = build_parser()
    calls = []

    def fake_report(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(registry_dispatch, "event_impact_hypotheses_report", fake_report, raising=False)
    args = parser.parse_args([
        "--event-impact-hypotheses-report",
        "--event-alpha-profile",
        "fixture",
        "--include-legacy",
    ])

    assert registry_dispatch._dispatch_event_alpha_command_section_2(args) is True
    assert calls and calls[0]["include_api"] is True


def test_event_incidents_report_dispatch_does_not_require_stale_include_api_attr(monkeypatch):
    parser = build_parser()
    calls = []

    def fake_report(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(registry_dispatch, "event_incidents_report", fake_report, raising=False)
    args = parser.parse_args([
        "--event-incidents-report",
        "--event-alpha-profile",
        "fixture",
    ])
    assert not hasattr(args, "include_api")

    assert registry_dispatch._dispatch_event_alpha_command_section_2(args) is True
    assert calls and calls[0]["include_api"] is False


def test_event_alpha_service_modules_export_expected_categories():
    expected = {
        event_alpha_notifications: (
            "event_alpha_notify_preview",
            "event_alpha_notify_preview_from_artifacts",
            "event_alpha_notify_go_no_go",
            "event_alpha_export_notification_pack",
            "event_alpha_notify_fixture_smoke",
            "event_alpha_send_readiness_report",
            "event_alpha_telegram_final_check_report",
            "event_alpha_notification_deliveries_report",
            "event_alpha_notification_runs_report",
        ),
        event_alpha_integrated: (
            "event_alpha_integrated_radar_cycle_report",
            "event_alpha_market_anomaly_scan_report",
            "event_alpha_official_exchange_report",
            "event_alpha_scheduled_catalyst_report",
            "event_alpha_derivatives_report",
            "event_alpha_replay_report",
        ),
        event_alpha_outcomes: (
            "event_alpha_integrated_radar_fill_outcomes_report",
            "event_alpha_integrated_radar_outcome_report",
            "event_alpha_integrated_radar_calibration_report",
            "event_alpha_calibration_report",
            "event_alpha_fill_outcomes",
            "event_alpha_feedback_readiness_report",
        ),
        event_alpha_provider_preflights: (
            "event_alpha_live_provider_readiness_report",
            "event_alpha_coinalyze_preflight_report",
            "event_alpha_coinalyze_no_send_rehearsal",
            "event_alpha_bybit_announcements_preflight_report",
            "event_alpha_bybit_announcements_no_send_rehearsal",
            "event_alpha_unlock_calendar_preflight_report",
            "event_alpha_dex_onchain_readiness_report",
            "event_alpha_cryptopanic_preflight",
            "event_alpha_provider_health_report",
            "event_alpha_provider_health_reset",
        ),
        event_alpha_namespace: (
            "event_alpha_mark_namespace_stale",
            "event_alpha_mark_known_stale_namespaces",
            "event_alpha_prune_or_archive_stale_namespace",
            "event_alpha_namespace_lifecycle_report",
            "event_alpha_list_active_namespaces",
            "event_alpha_archive_stale_namespaces",
        ),
        event_alpha_reports: (
            "event_alpha_source_coverage_report",
            "event_alpha_daily_brief_report",
            "event_alpha_artifact_doctor_report",
            "event_alpha_status",
            "event_alpha_runs_report",
            "event_alpha_preflight_report",
            "event_alpha_environment_doctor_report",
            "event_alpha_health_guard_report",
            "event_alpha_v1_readiness_report",
        ),
        event_alpha_research: (
            "event_impact_hypotheses_report",
            "event_impact_hypotheses_inbox",
            "event_incidents_report",
            "event_catalyst_search_report",
            "event_watchlist_report",
            "event_watchlist_refresh",
            "event_watchlist_monitor_report",
            "event_alpha_router_report",
            "event_alpha_near_miss_report",
            "event_opportunity_audit_report",
            "event_alpha_quality_review_report",
            "event_alpha_quality_coverage_report",
            "event_alpha_signal_quality_eval",
            "event_alpha_export_signal_quality_cases",
            "event_feedback_mark",
            "event_feedback_shortcut",
            "event_feedback_report",
            "event_alpha_alerts_report",
            "event_alpha_notification_inbox_report",
            "event_alpha_missed_report",
            "event_source_reliability_report",
            "event_alpha_burn_in_scorecard",
            "event_alpha_burn_in_checklist",
            "event_alpha_export_burn_in_pack",
        ),
        event_alpha_fade_review: (
            "_write_event_fade_review_bundle",
            "_event_fade_review_bundle_manifest",
            "_event_fade_review_bundle_readme",
            "_event_fade_review_guide",
        ),
    }
    for module, names in expected.items():
        assert [name for name in names if not hasattr(module, name)] == []
